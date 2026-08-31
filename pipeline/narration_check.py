#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""낭독 대본이 ★기계처럼 들리는지 구조로 잰다.

2026-08-31. 발행된 4편을 나란히 놓고 보니 원인이 두 가지였다.

  ① ★프롬프트의 예문이 그대로 대본에 나온다.
     "확보. 격리. 보호." · "이 이야기를 시작하기 전에 하나만 짚고 갈게요."
     · "객체 등급, 세이프." — 4편 중 3편이 ★같은 다섯 번째 문장으로 시작했다.
     마지막 문장도 3편이 똑같았다("댓글로 한번 들려주세요. 다음 이야기에서 뵙겠습니다").
  ② ★문장의 리듬이 없다. 163개 세그먼트짜리 대본에 물음표가 1개, 말줄임표가 1개,
     줄표가 0개였다. 마침표 107 · 쉼표 73. TTS 는 문장부호로 호흡을 잡는데
     줄 게 없으니 전부 같은 높이로 읽는다.

그래서 여기서 재는 건 ★문체의 다양성이지 내용이 아니다.
소재 단어는 한 글자도 안 본다 — 어떤 이야기가 와도 같은 방식으로 동작한다.
(상투구 목록만은 문자열이지만, 그건 소재가 아니라 ★프롬프트가 찍어낸 관용구다.
 SCP_RITUAL_BANLIST 로 통째로 갈아끼울 수 있고, 빈 문자열이면 그 검사만 꺼진다.)

경고만 한다. 렌더가 끝난 뒤에 대본을 트집 잡아 영상을 버리는 건 손해다.
빨간불로 세우려면 SCP_FAIL_ON_NARRATION=1.
"""
from __future__ import annotations

import os
import re

# 프롬프트가 예문으로 준 문장들이 그대로 나온 자리. 소재와 무관한 ★의례 문구다.
DEFAULT_RITUALS = (
    "확보. 격리. 보호",
    "이 이야기를 시작하기 전에",
    "하나만 짚고 갈게요",
    "특수 격리 절차입니다",
    "격리 방법은 이미 나와",
    "지킬 사람이 있느냐",
    "지킬 사람이 남아",
    "다음 이야기에서 뵙겠습니다",
    "댓글로 한번 들려주세요",
    "무슨 일이 있었는지, 처음부터",
)

SENT_END = re.compile(r"[.!?]+")
# 문장을 여는 상투 — `SCP-9758은 …입니다` 로 시작하면 매 회 같은 소리가 난다.
OPENER_RE = re.compile(r"^\s*SCP[-\s]?\d{3,4}(?:-[A-Z]{2})?\s*(?:은|는)\s")
# 호흡 부호 — TTS 가 여기서 쉰다. 마침표·쉼표만으로는 리듬이 안 생긴다.
BREATH = "…—"

MAX_ENDING_SHARE = float(os.environ.get("SCP_MAX_ENDING_SHARE", "0.55"))
MIN_QUESTIONS_K = float(os.environ.get("SCP_MIN_QUESTIONS_K", "0.5"))   # 1000자당
MIN_BREATH_K = float(os.environ.get("SCP_MIN_BREATH_K", "0.5"))         # 1000자당
# 인용은 ★밀도로 본다 — 편당 몇 개로 재면 짧은 대본이 억울하게 걸린다.
# 프롬프트 권장(3,300자에 5~8쌍) ≈ 1.5~2.4/1000자. 그 아래쪽을 기준으로 둔다.
MIN_QUOTES_K = float(os.environ.get("SCP_MIN_QUOTES_K", "1.2"))


def rituals() -> tuple[str, ...]:
    raw = os.environ.get("SCP_RITUAL_BANLIST")
    if raw is None:
        return DEFAULT_RITUALS
    return tuple(w.strip() for w in raw.split("|") if w.strip())


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_END.split(text or "") if s.strip()]


def ending_of(sent: str) -> str:
    """종결부 3글자. 어미 사전을 두지 않는다 — ★분포만 보면 되기 때문이다."""
    s = re.sub(r"[^가-힣]", "", sent or "")
    return s[-3:] if len(s) >= 3 else s


def measure(narration: str, segments: list[dict] | None = None) -> dict:
    n = narration or ""
    k = max(len(n), 1) / 1000.0
    sents = sentences(n)
    ends: dict[str, int] = {}
    for s in sents:
        e = ending_of(s)
        if e:
            ends[e] = ends.get(e, 0) + 1
    top, top_n = ("", 0)
    if ends:
        top, top_n = max(ends.items(), key=lambda kv: kv[1])
    quotes = min(n.count("「"), n.count("」"))
    return {
        "chars": len(n),
        "sentences": len(sents),
        "top_ending": top,
        "top_ending_share": (top_n / len(sents)) if sents else 0.0,
        "questions_per_k": n.count("?") / k,
        "breath_per_k": sum(n.count(c) for c in BREATH) / k,
        "quotes": quotes,
        "quotes_per_k": quotes / k,
        "first_sentence": sents[0] if sents else "",
        "segments": len(segments or []),
    }


def check(narration: str, segments: list[dict] | None = None) -> list[str]:
    n = narration or ""
    if not n.strip():
        return ["narration_full 이 비어 있다"]
    m = measure(n, segments)
    out: list[str] = []

    hit = [r for r in rituals() if r in n]
    if hit:
        out.append("프롬프트 예문이 그대로 들어갔다(회차마다 같은 소리가 난다): "
                   + " / ".join(hit))

    if OPENER_RE.match(m["first_sentence"]):
        out.append(f"첫 문장이 `SCP-####는 …입니다` 형식이다 — 매 회 같은 문장으로 열린다: "
                   f"{m['first_sentence'][:40]}")

    if m["top_ending_share"] > MAX_ENDING_SHARE:
        out.append(f"종결어미가 한쪽으로 쏠렸다 — `…{m['top_ending']}` 가 "
                   f"{m['top_ending_share']:.0%} (권장 {MAX_ENDING_SHARE:.0%} 이하)")

    if m["questions_per_k"] < MIN_QUESTIONS_K:
        out.append(f"청자에게 묻는 문장이 거의 없다 — 물음표 {n.count('?')}개 "
                   f"({m['questions_per_k']:.2f}/1000자, 권장 {MIN_QUESTIONS_K}+)")

    if m["breath_per_k"] < MIN_BREATH_K:
        out.append(f"호흡 부호(… —)가 거의 없다 — {sum(n.count(c) for c in BREATH)}개 "
                   f"({m['breath_per_k']:.2f}/1000자). TTS 가 쉴 자리를 못 찾아 "
                   "전부 같은 높이로 읽는다")

    if m["quotes_per_k"] < MIN_QUOTES_K:
        out.append(f"직접 인용(「 」)이 {m['quotes']}쌍뿐이다 "
                   f"({m['quotes_per_k']:.1f}/1000자, 권장 {MIN_QUOTES_K}+). "
                   "감정은 서술이 아니라 사람의 말에서 나온다")
    return out


def report(narration: str, segments: list[dict] | None = None) -> list[str]:
    """검사 + 사람이 읽는 요약. 대본은 ★고치지 않는다 — 문장은 기계가 손댈 게 아니다."""
    m = measure(narration, segments)
    problems = check(narration, segments)
    print(f"   📖 대본 {m['chars']:,}자 · {m['sentences']}문장 · 자막 {m['segments']}장 · "
          f"물음표 {m['questions_per_k']:.1f}/1k · 호흡 {m['breath_per_k']:.1f}/1k · "
          f"인용 {m['quotes']}쌍 · 최빈어미 `…{m['top_ending']}` {m['top_ending_share']:.0%}")
    if problems:
        print(f"   ⚠️  낭독 점검({len(problems)}건)")
        for p in problems:
            print(f"      · {p}")
            print(f"::warning title=낭독 문체::{p}")
        if os.environ.get("SCP_FAIL_ON_NARRATION") == "1":
            raise SystemExit(f"[narration_check] 문체 규칙 위반 {len(problems)}건 "
                             "(SCP_FAIL_ON_NARRATION=1)")
    else:
        print("   ✅ 낭독 문체 OK")
    return problems
