#!/usr/bin/env python3
"""스토리보드 JSON → 모션그래픽 장면 스펙(JSON). (Claude / Anthropic API)

루틴이 만든 뉴스 스토리보드(헤드라인·후크·대사·출처)를 읽어,
모션그래픽 4~6장면 스펙으로 변환한다. 장면 타입: hook / stat / gauge / trend.
각 장면엔 단일 내레이터 내레이션 1줄 포함.

요구: ANTHROPIC_API_KEY (CI 시크릿). CLAUDE_MODEL(기본 claude-sonnet-4-6).
키가 없으면 에러 — 파이프라인은 미리 만든 스펙 파일로 폴백 가능(run_pipeline 참고).

사용:
  python extract_scenes.py --storyboard <sb.json> --out <spec.json>
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

SCHEMA_GUIDE = """\
출력은 아래 JSON 형식만(설명/마크다운 없이):
{
  "topic": "<topic>",
  "scenes": [
    // 1) 반드시 첫 장면은 hook
    {"type":"hook","pill":"BREAKING","ghost":"<영문 토픽 한 단어, 예 ECONOMY>",
     "lines":["짧게","2~3줄로","나눈 후크"], "highlight":"<lines 안에 등장하는 짧은 강조 토큰(숫자/단어)>",
     "brand":"일상공감뉴스 · <한글 토픽>", "narration":"<도입 내레이션 1문장>"},
    // 2~) 핵심 숫자별로 stat/gauge/trend 중 선택 (2~4개)
    {"type":"stat","label":"<무엇의 수치인가>","prefix":"<예 +$ 또는 빈칸>","suffix":"<예 만원/% 또는 빈칸>",
     "from":0,"to":<숫자>,"bar":true,"sub":"<보조설명, <b>강조</b> 가능>","brand":"...","narration":"<1문장>"},
    {"type":"gauge","label":"...","from":1,"to":<배수>,"unit":"배","sub":"...","brand":"...","narration":"..."},
    {"type":"trend","label":"...","from":0,"to":<음수면 하락>,"suffix":"%","dir":"down|up",
     "sub":"...","closer":"<마지막 장면이면 마무리 한마디(선택)>","brand":"...","narration":"..."}
  ]
}
규칙:
- 숫자(to/from)는 반드시 기사 내용에서 가져온다. 없는 숫자 지어내지 말 것.
- stat: 절대값 증감(가격 +200 등). gauge: 배수(4배 등). trend: 퍼센트 추세(주가 -6% 등).
- 마지막 장면은 보통 trend 또는 stat이며 closer로 한 줄 마무리.
- narration은 단일 앵커가 읽는 자연스러운 한국어 1문장(존댓말). 대사 말투가 아니라 뉴스 내레이션.
- 장면 4~6개. highlight는 lines 중 한 토큰과 정확히 일치해야 함.
"""


def build_prompt(sb: dict) -> str:
    lines = " ".join((s.get("line") or "").strip() for s in sb.get("shots", []))
    return (
        f"다음 뉴스 스토리보드를 모션그래픽 쇼츠 장면 스펙으로 변환해줘.\n\n"
        f"topic: {sb.get('topic','')}\n"
        f"headline: {sb.get('headline','')}\n"
        f"hook_title: {sb.get('hook_title','')}\n"
        f"sources: {', '.join(sb.get('sources', []))}\n"
        f"credit: {sb.get('credit','')}\n"
        f"대사(사실 포함): {lines}\n\n"
        + SCHEMA_GUIDE
    )


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("응답에서 JSON을 찾지 못함")
    return json.loads(m.group(0))


def extract_scenes(sb: dict) -> dict:
    import anthropic  # noqa
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("[error] ANTHROPIC_API_KEY 없음 — 키 설정 또는 미리 만든 스펙 사용")
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=MODEL, max_tokens=2000,
        system="너는 한국 뉴스 모션그래픽 영상의 장면 설계자다. 반드시 유효한 JSON만 출력한다.",
        messages=[{"role": "user", "content": build_prompt(sb)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    spec = extract_json(text)
    spec.setdefault("topic", sb.get("topic", ""))
    return spec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.storyboard, encoding="utf-8") as f:
        sb = json.load(f)
    spec = extract_scenes(sb)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(f"✅ {args.out}  ({len(spec.get('scenes', []))} scenes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
