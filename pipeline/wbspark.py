#!/usr/bin/env python3
"""wbSpark 게이트웨이 클라이언트 — 비동기 잡큐.

사내 Spark 서버의 이미지 생성을 회사 도메인 게이트웨이로 노출한 것.
외부 공인(211.168.38.218, split-horizon DNS)이라 GitHub Actions 러너에서도 호출된다.

★모델은 게이트웨이가 고른다 — 여기서 정하는 게 아니다 (2026-09-07 실측 확인)
  기본 경로는 Z-Image(21GB). 프롬프트에 글자 관련 낱말(글자·간판·text·sign·title·
  word·logo…)이 있으면 서버의 needs_text() 가 걸려 Qwen-Image(30GB)로 간다.
  이 검사는 원문뿐 아니라 ★LLM 이 재작성한 enhanced_prompt 에도 적용되므로,
  지정하지 않으면 같은 프롬프트라도 실행마다 다른 모델로 갈 수 있다.
  고정이 필요하면 WBSPARK_MODEL 이나 model= 인자를 쓴다. 기본은 '보내지 않음' 이다
  — 라우팅 정책은 서버 것이고, 클라이언트가 넘겨짚지 않는다.

  ※ 이 파일을 호출하는 쪽들은 프롬프트 끝에 "no text, no letters" 를 붙인다.
    부정형이지만 낱말 자체는 들어 있으므로 needs_text 가 걸릴 수 있다.
    완료 로그에 서버가 알려준 실제 모델을 찍어두니 Actions 로그에서 확인할 것.

API:
  POST {BASE}/jobs   {"type":"image","prompt":"...", "model"?:"..."} → {"job_id","status"}
  GET  {BASE}/jobs/{id}                → {"status":"queued|...|done|error|failed","elapsed","model"}
  GET  {BASE}/jobs/{id}/file           → PNG 바이너리

환경변수:
  WBSPARK_BASE   기본 https://wangbyul.com/wbSpark
  WBSPARK_TOKEN  (선택) 있으면 Authorization: Bearer 로 전송
  WBSPARK_MODEL  (선택) 있으면 model 필드로 전송해 라우팅을 고정. 기본은 미전송.

썸네일은 best-effort — 실패해도 예외 대신 False 를 반환해 파이프라인을 막지 않는다.
"""
from __future__ import annotations
import os
import sys
import time

DEFAULT_BASE = "https://wangbyul.com/wbSpark"


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def _base() -> str:
    return (os.environ.get("WBSPARK_BASE") or DEFAULT_BASE).rstrip("/")


def _headers() -> dict:
    tok = os.environ.get("WBSPARK_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def generate_image(prompt: str, out_path: str,
                   timeout_sec: int = 720, poll_sec: float = 4.0,
                   model: str | None = None) -> bool:
    """프롬프트로 이미지 1장 생성 → out_path 에 PNG 저장. 성공 시 True.

    GPU 는 직렬 레인이라 앞선 작업이 있으면 그만큼 밀린다(2026-08-08 부터 gpu·cpu·llm
    3레인). 그래서 timeout_sec 기본을 12분으로 넉넉히 둔다. 실패는 경고 후 False.

    model 을 주면(또는 WBSPARK_MODEL 이 있으면) 그대로 실어 보내 라우팅을 고정한다.
    아무것도 안 주면 필드를 아예 빼고 서버가 고르게 둔다 — 그게 기본이다.
    """
    requests = _requests()
    base, headers = _base(), _headers()
    body = {"type": "image", "prompt": prompt}
    mdl = model or os.environ.get("WBSPARK_MODEL")
    if mdl:
        body["model"] = mdl
    try:
        r = requests.post(f"{base}/jobs", json=body, headers=headers, timeout=40)
        if r.status_code != 200:
            sys.stderr.write(f"[warn] wbSpark 제출 실패 {r.status_code}: {r.text[:200]}\n")
            return False
        job_id = r.json().get("job_id")
        if not job_id:
            sys.stderr.write(f"[warn] wbSpark job_id 없음: {r.text[:200]}\n")
            return False
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] wbSpark 제출 예외: {e}\n")
        return False

    deadline = time.monotonic() + timeout_sec
    status = "?"
    while time.monotonic() < deadline:
        time.sleep(poll_sec)
        js = {}
        try:
            s = requests.get(f"{base}/jobs/{job_id}", headers=headers, timeout=30)
            js = s.json() or {}
            status = js.get("status", "?")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] wbSpark 폴링 예외(계속): {e}\n")
            continue
        if status == "done":
            # 기준시간을 하드코딩하지 않는다 — 서버가 알려주는 사실만 남긴다.
            # 어느 모델로 갔는지가 여기 찍히므로 needs_text 라우팅을 로그로 추적할 수 있다.
            sys.stderr.write(
                f"[info] wbSpark 완료 — 서버측 {js.get('elapsed', '?')}초"
                f" / 모델 {js.get('model') or '?'}\n")
            break
        if status in ("error", "failed"):
            sys.stderr.write(f"[warn] wbSpark 생성 실패: {s.text[:200]}\n")
            return False
    else:
        sys.stderr.write(f"[warn] wbSpark 타임아웃({timeout_sec}s, 마지막 status={status})\n")
        return False

    try:
        f = requests.get(f"{base}/jobs/{job_id}/file", headers=headers, timeout=60)
        if f.status_code != 200 or not f.content:
            sys.stderr.write(f"[warn] wbSpark 파일 수신 실패 {f.status_code}\n")
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "wb") as fp:
            fp.write(f.content)
        return True
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] wbSpark 다운로드 예외: {e}\n")
        return False


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="wbSpark 이미지 생성(테스트)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", default="wbspark_out.png")
    ap.add_argument("--timeout", type=int, default=720)
    ap.add_argument("--model", help="라우팅 고정(미지정이면 서버가 고른다)")
    args = ap.parse_args()
    ok = generate_image(args.prompt, args.out, timeout_sec=args.timeout,
                        model=args.model)
    print(("✅ 저장: " + args.out) if ok else "❌ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
