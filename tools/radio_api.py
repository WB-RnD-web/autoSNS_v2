"""왕별이 라디오 · 밤 편 대본 — Claude API 로 쓴다(.github/workflows/wb-radio.yml).

    python tools/radio_api.py write --out output/radio/2026-11-29.json [--date 2026-11-29]

pipeline/radio_night.py 의 사실(내일 띠 순위·한 줄·이야기·옛말)과 글쓰기 안내(pipeline/RADIO_NIGHT_WRITING.md)·견본
(docs/samples/radio_night_2026-11-28.json)을 주고 쓰게 한 뒤, radio_night.check 가 통과할 때까지 고쳐 쓰게 한다(최대 TRIES).
렌더·업로드는 pipeline/run_radio_night.py 가 한다. 비용은 API 크레딧(편당 약 0.3~0.6달러 · 추측).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

import radio_night as N  # noqa: E402

MODEL = os.environ.get("RADIO_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("RADIO_EFFORT", "high")
TRIES = 4
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}
WRITING = os.path.join(ROOT, "pipeline", "RADIO_NIGHT_WRITING.md")
SAMPLE = os.path.join(ROOT, "docs", "samples", "radio_night_2026-11-28.json")

RULES = """너는 왕별이 라디오 밤 편 '잠들기 전 복 받는 시간'(55세 이상 어르신이 잠들기 전에 라디오처럼 듣는 방송) 작가다.
- 아래 '글쓰기 안내'를 전부 따르고, 사용자 메시지가 준 사실로 대본 JSON 하나를 쓴다.
- 사실(띠 순위·화면 한 줄·이야기 제목·옛말)은 준 그대로 쓴다. 바꾸거나 지어내지 않는다.
- 견본은 형식과 말투만 참고한다. 견본 문장을 옮기지 않는다(매일 듣는 분들이 같은 말을 듣지 않게).
- '금지어' 목록의 낱말은 코드 검사에서 걸린다. 비슷한 말로 바꿔 쓴다.
- 출력은 ```json 블록 하나에 대본 JSON 전체만. 다른 말은 쓰지 않는다."""


def extract_json(text: str) -> dict:
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def system_prompt() -> str:
    with open(WRITING, encoding="utf-8") as f:
        writing = f.read()
    with open(SAMPLE, encoding="utf-8") as f:
        sample = f.read()
    return (f"{RULES}\n\n# 글쓰기 안내(pipeline/RADIO_NIGHT_WRITING.md)\n\n{writing}\n\n"
            f"# 금지어(코드 검사 — radio_night.BAN)\n{N.ban_list_text()}\n\n"
            f"# 견본 2026-11-28(형식·말투만 — 문장은 옮기지 않는다)\n\n{sample}")


def ask(client, system, messages):
    with client.messages.stream(model=MODEL, max_tokens=32000, system=system, messages=messages,
                                extra_body={"output_config": {"effort": EFFORT}}) as s:
        msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), msg.usage


def write_script(d: dt.date, out: str, client=None) -> dict:
    """쓰기 → check → 고쳐 쓰기(최대 TRIES). {ok, tries, usd, errors}."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    system = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": N.brief(d) + "\n\n오늘 밤 대본 JSON 전체를 ```json 블록 하나로 내라."}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    errs: list[str] = []
    n = 0
    for n in range(1, TRIES + 1):
        text, usage = ask(client, system, messages)
        for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            tok[k] += getattr(usage, f, 0) or 0
        try:
            data = extract_json(text)
            os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            errs = N.check(data, d)
        except (ValueError, KeyError, TypeError) as e:
            errs = [f"JSON 을 읽을 수 없다: {e}"]
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"), flush=True)
        if not errs:
            break
        for x in errs[:30]:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "코드 검사(radio_night.check)에서 오류가 났다. 고쳐서 대본 JSON 전체를 다시 내라.\n"
                                                 + "\n".join(f"- {x}" for x in errs[:30])}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6
    return {"ok": not errs, "tries": n, "usd": round(usd, 3), "tokens": tok, "errors": errs}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["write"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=None, help="오늘 밤 날짜(기본: 지금 KST)")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else N.tonight()
    info = write_script(d, a.out)
    print(f"🧾 밤 편 {d} · {MODEL} · 시도 {info['tries']} · 약 {info['usd']}달러")
    if not info["ok"]:
        print("::error::검사를 끝내 통과하지 못했다 — 렌더·업로드하지 않는다\n  " + "\n  ".join(info["errors"][:20]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
