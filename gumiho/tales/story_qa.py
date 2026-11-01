#!/usr/bin/env python3
"""Nine Tails 쇼츠 그림 검수(비전) — 그림을 다 받은 뒤, 렌더 전에 컷마다 Claude 에게 보여 준다(2026-11-01).

왜: 7화 첫 렌더에서 헬륨 연구 기구가 열기구로 그려졌고, 낙하 컷에 곤돌라가 남았다(사람이 1초 시트로 찾았다).
  제작 중에 사람이 볼 수 없으니 컷마다 '보여 줘야 할 것'과 축소본을 보내 ① 대본과 안 맞는 물체 ② 녹음·일그러짐(손·몸)
  ③ 글자·로고 ④ 잔혹함 ⑤ 실제 사람 같은 얼굴 을 찾게 한다.
규칙: 걸린 컷은 고친 프롬프트로 한 번 다시 그려 다시 본다. 그래도 걸리면
  · 트렌드 편 → 올리지 않는다(qa_block — story.upload 가 사유를 ledger 에 남긴다)
  · 카탈로그 편 → 그 컷을 가까운 통과 컷의 그림으로 바꿔 올린다(공개일이 정해져 있다) — 바꾼 것은 기록한다.
★키가 없거나 API 가 실패하면 검수 없이 그대로 간다(검수 때문에 업로드가 막히지 않게). 비용은 qa 결과에 남긴다.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story as ST  # noqa: E402

MODEL = os.environ.get("NT_QA_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("NT_QA_EFFORT", "medium")
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}     # 입력·출력(달러/100만 토큰)
THUMB_W = 384

SYSTEM = """You review AI-generated stills for a faceless 3D-animation YouTube Short before it is rendered.
Every cut comes with what it must show (the image prompt) and the narration line it sits under.
Flag a cut (ok=false) only for real problems a viewer would notice:
- mismatch: a key object or setting contradicts what the cut must show (wrong vehicle or craft type, a person shown where the
  narration says they are alone or falling, an extra object that changes the meaning)
- distortion: melted, fused or broken bodies, hands, faces or objects
- text: readable letters, numbers, logos or signage
- gore: blood, wounds, corpses
- face: a realistic human face (people must be smooth featureless mannequins with blank heads)
Style choices, small inaccuracies and mild oddities are fine. Do not flag a cut for being stylized.
For each flagged cut write "fix": a corrected English image prompt for the same cut (describe positively what to draw; no
negations such as "no text"; people as faceless mannequins).
Return only JSON: {"shots": [{"shot": <number>, "ok": true|false, "issues": ["mismatch: ..."], "fix": "..."}]} with one entry
per cut you were given."""


def thumb_b64(path: str, w: int = THUMB_W) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im = im.resize((w, int(im.height * w / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def wants(ep: dict, i: int) -> str:
    sh = ep["shots"][i]
    what = sh.get("prompt") or sh.get("edit") or ""
    if sh.get("edit") and ep.get("character"):
        what = f"{what} (the person: {ep['character']['prompt']})"
    return what


def request(ep: dict, imgs: dict) -> list:
    """imgs = {컷 번호: 그림 경로}"""
    content = [{"type": "text", "text": f"Short: {ep['title']}\nCuts to review: {len(imgs)}"}]
    for i, p in sorted(imgs.items()):
        content.append({"type": "text", "text": f"Cut {i} — must show: {wants(ep, i)}\nNarration: {ep['shots'][i]['say']}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": thumb_b64(p)}})
    return content


def parse(text: str, asked: set) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("검수 답에 JSON 이 없다")
    out = {}
    for r in json.loads(t[a:b + 1]).get("shots", []):
        try:
            i = int(r.get("shot"))
        except (TypeError, ValueError):
            continue
        if i in asked:
            out[i] = {"ok": bool(r.get("ok", True)), "issues": [str(x)[:200] for x in r.get("issues") or []][:5],
                      "fix": str(r.get("fix") or "")[:900]}
    for i in asked - set(out):                      # 답이 없는 컷은 통과로 본다(검수가 업로드를 막지 않게)
        out[i] = {"ok": True, "issues": [], "fix": "", "unanswered": True}
    return out


def review(ep: dict, imgs: dict, client, tok: dict) -> dict:
    msg = client.messages.create(model=MODEL, max_tokens=6000, system=SYSTEM,
                                 messages=[{"role": "user", "content": request(ep, imgs)}],
                                 extra_body={"output_config": {"effort": EFFORT}})
    u = msg.usage
    tok["input"] += getattr(u, "input_tokens", 0) or 0
    tok["output"] += getattr(u, "output_tokens", 0) or 0
    tok["calls"] += 1
    return parse("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), set(imgs))


def safe_fix(ep: dict, i: int, fix: str) -> str:
    """고친 프롬프트도 카탈로그 규칙(글자·상표·잔혹 금지어 · 사람은 마네킹)을 지키게 — 아니면 원래 프롬프트로 다시 그린다."""
    sh = ep["shots"][i]
    orig = sh.get("prompt") or sh.get("edit") or ""
    if not fix.strip() or ST.PROMPT_BANNED.search(fix):
        return orig
    if "prompt" in sh and ST.HUMAN.search(fix) and "mannequin" not in fix:
        return orig
    return fix.strip()


def nearest_ok(i: int, ok: list[int]) -> int | None:
    return min(ok, key=lambda j: (abs(j - i), j > i)) if ok else None


def run(ep: dict, A: dict, redraw, client=None) -> dict:
    """그림(A['img'])을 검수 → 걸린 컷은 redraw(i, 프롬프트) 로 한 번 다시 → 다시 검수. A 를 고친다. → qa 결과."""
    own = sorted(int(k) for k in A["img"] if "reuse" not in ep["shots"][int(k)])
    qa = {"model": MODEL, "kind": ep.get("kind", "catalog"), "checked": own, "flagged": {}, "fixed": [], "failed": [],
          "replaced": {}, "block": False}
    tok = {"input": 0, "output": 0, "calls": 0}
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return dict(qa, skipped="ANTHROPIC_API_KEY 없음 — 검수 없이 진행")
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception as e:  # noqa: BLE001
            return dict(qa, skipped=f"anthropic 불러오기 실패: {e}")
    try:
        r1 = review(ep, {i: A["img"][str(i)] for i in own}, client, tok)
        bad = [i for i in own if not r1[i]["ok"]]
        qa["flagged"] = {str(i): r1[i]["issues"] for i in bad}
        redrawn = {}
        for i in bad:
            p = redraw(i, safe_fix(ep, i, r1[i]["fix"]))
            if p:
                A["img"][str(i)] = p
                redrawn[i] = p
        r2 = review(ep, redrawn, client, tok) if redrawn else {}
        qa["fixed"] = [i for i in redrawn if r2[i]["ok"]]
        qa["failed"] = [i for i in bad if i not in qa["fixed"]]
        qa["second"] = {str(i): r2[i]["issues"] for i in redrawn if not r2[i]["ok"]}
    except Exception as e:  # noqa: BLE001 — 검수가 업로드를 막지 않는다
        qa["skipped"] = f"검수 API 오류: {type(e).__name__}: {str(e)[:200]}"
    if qa["failed"]:
        if ST.is_trend(ep):
            qa["block"] = True
        else:
            ok = [i for i in own if i not in qa["failed"]]
            for i in qa["failed"]:
                j = nearest_ok(i, ok)
                if j is not None:
                    A["img"][str(i)] = A["img"][str(j)]
                    qa["replaced"][str(i)] = j
    pi, po = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    qa["tokens"] = tok
    qa["usd"] = round((tok["input"] * pi + tok["output"] * po) / 1e6, 4)
    return qa
