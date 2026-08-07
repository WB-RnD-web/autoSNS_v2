#!/usr/bin/env python3
"""공용 이미지 생성 — NVIDIA FLUX.2 klein-4b (소설 novel_render 와 동일 엔드포인트).

NVIDIA_API_KEY 있으면 FLUX.2 klein-4b(호스팅·Apache-2.0 상업OK)로 이미지 생성 → PNG 저장.
키/오프/4xx/형식불일치 → None(호출측 폴백). 429·5xx·타임아웃·네트워크는 짧게 재시도.

env: NVIDIA_API_KEY, FLUX_URL, FLUX_TIMEOUT, FLUX_RETRIES (NOVEL_* 도 폴백 인식).
"""
from __future__ import annotations
import json
import os
import sys

DEFAULT_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b"


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def _extract_img_b64(body) -> str | None:
    """응답에서 base64 이미지 추출(모델별 응답 키 편차 대비 방어적).

    알려진 키(artifacts/data/image/b64_json)를 먼저 보고, 못 찾으면 응답 전체를
    재귀 탐색해 '디코드하면 PNG/JPEG/WebP 매직이 나오는 긴 문자열'을 찾는다.
    (2026-07 관측: 동일 엔드포인트가 간헐적으로 다른 중첩 구조를 반환해
    keys=['artifacts'] 인데도 기존 고정 키 탐색이 실패 → 매 런 불필요한 폴백 유발)
    """
    def clean(s):
        return s.split(",", 1)[1] if isinstance(s, str) and s.startswith("data:") else s

    def is_img_b64(s) -> bool:
        if not isinstance(s, str) or len(s) < 500:
            return False
        import base64 as _b
        try:
            head = _b.b64decode(clean(s)[:64] + "==", validate=False)
        except Exception:  # noqa: BLE001
            return False
        return head[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
                            b"\xff\xd8\xff\xdb", b"RIFF")

    cands = []
    try:
        art = body["artifacts"][0]
        cands += [art.get("b64_json"), art.get("base64"), art.get("image")]
    except Exception:  # noqa: BLE001
        pass
    for k in ("image", "b64_json"):
        if isinstance(body, dict) and isinstance(body.get(k), str):
            cands.append(body[k])
    try:
        cands.append(body["data"][0].get("b64_json"))
    except Exception:  # noqa: BLE001
        pass
    for c in cands:
        if isinstance(c, str) and len(c) > 100:
            return clean(c)

    # 고정 키 실패 → 재귀 탐색(깊이 제한, 이미지 매직 검증)
    stack, depth = [(body, 0)], 6
    while stack:
        node, d = stack.pop()
        if d > depth:
            continue
        if isinstance(node, dict):
            stack += [(v, d + 1) for v in node.values()]
        elif isinstance(node, list):
            stack += [(v, d + 1) for v in node[:8]]
        elif is_img_b64(node):
            return clean(node)
    return None


def _shape(body, depth: int = 3):
    """응답 구조 요약(값 내용 제외 — 키/타입/길이만). 파싱 실패 진단용."""
    if depth < 0:
        return "…"
    if isinstance(body, dict):
        return {k: _shape(v, depth - 1) for k, v in list(body.items())[:12]}
    if isinstance(body, list):
        return [_shape(v, depth - 1) for v in body[:3]] + (["…"] if len(body) > 3 else [])
    if isinstance(body, str):
        return f"str({len(body)})"
    return type(body).__name__


def flux_image(prompt: str, out_png: str, w: int = 1344, h: int = 768, seed: int = 0) -> str | None:
    """FLUX.2 klein-4b 로 이미지 1장 생성 → out_png. 실패/무키 시 None."""
    key = _env("NVIDIA_API_KEY")
    if not key or not (prompt or "").strip():
        if not key:
            sys.stderr.write("[warn] NVIDIA_API_KEY 없음 — FLUX 이미지 스킵\n")
        return None
    import urllib.request
    import urllib.error
    import base64 as _b64
    import time as _time
    url = _env("FLUX_URL", "NOVEL_FLUX_URL", default=DEFAULT_URL)
    payload = json.dumps({"prompt": prompt[:9000], "width": w, "height": h,
                          "seed": int(seed), "steps": 4}).encode()
    timeout = int(_env("FLUX_TIMEOUT", "NOVEL_FLUX_TIMEOUT", default="150"))
    retries = int(_env("FLUX_RETRIES", "NOVEL_FLUX_RETRIES", default="2"))
    for attempt in range(1, retries + 2):
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "curl/8.4.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                sys.stderr.write(f"[warn] FLUX {e.code}(혼잡/서버) {attempt}/{retries + 1} — 재시도\n")
                _time.sleep(min(2 ** attempt, 20)); continue
            body_txt = ""
            try:
                body_txt = (e.read() or b"")[:300].decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            sys.stderr.write(f"[warn] FLUX {e.code} 요청오류 → 폴백: {body_txt}\n")
            return None
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] FLUX 네트워크/타임아웃 {attempt}/{retries + 1} → {e}\n")
            _time.sleep(min(2 ** attempt, 20)); continue
        b64 = _extract_img_b64(data)
        if not b64:
            sys.stderr.write(f"[warn] FLUX 200인데 이미지 필드 못 찾음 → 폴백. shape={_shape(data)}\n")
            return None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out_png)) or ".", exist_ok=True)
            with open(out_png, "wb") as f:
                f.write(_b64.b64decode(b64))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] FLUX 디코드 실패 → 폴백: {e}\n")
            return None
        print(f"  · FLUX(klein-4b) 이미지 생성 OK: {os.path.basename(out_png)}")
        return out_png
    sys.stderr.write("[warn] FLUX 재시도 소진 → 폴백\n")
    return None


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="FLUX 이미지 생성(테스트)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", default="flux_out.png")
    ap.add_argument("--w", type=int, default=1344)
    ap.add_argument("--h", type=int, default=768)
    args = ap.parse_args()
    p = flux_image(args.prompt, args.out, args.w, args.h)
    print(("✅ " + p) if p else "❌ 실패/무키")
    return 0 if p else 1


if __name__ == "__main__":
    raise SystemExit(main())
