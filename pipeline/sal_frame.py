#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""살·삼재 낱말은 '조언 틀' 안에서만 — 쇼츠·롱폼 공통 검사 (2026-10-20 사용자 '삼재 조언형 ㅇㅋ').

왜: 그동안 '삼재'는 겁주는 말이라 통째로 금지였다(theme_card.BANNED · weekly_fortune.BAN).
  그런데 지금 작은 채널에서 터지는 2027 롱폼이 바로 이 말을 쓴다(10/20 조사 — 소문만복 '2027년 천살 드는 띠 …
  꼭 지킬 3가지' 6일 48.6만 · 반안살 편 10.4만). 어르신들이 찾아보는 말이다.
  → 낱말은 허용하되, 한 문장(제목은 제목 전체) 안에 ★조언 틀이 있어야 하고 ★겁주는 말·한 해를 깎아내리는 말은
    같이 쓸 수 없다. 예: '꼭 지킬 3가지' · '잘 넘기는 법' · '복삼재로 바꾸는 법' · '조심할 달'.

    violations("2027년 천살 드는 띠 꼭 지킬 3가지", unit="whole")   → []
    violations("올해는 삼재입니다.")                                 → ['…조언 틀이 없다…']
    violations("삼재가 들면 큰일 납니다. 이렇게 하세요.")             → ['…겁주는 말…']

unit="sentence"(기본): 말·설명 — 문장마다 본다. unit="whole": 제목·화면 한 줄 — 통째로 하나로 본다.
"""
from __future__ import annotations

import re

# 살·삼재 낱말. '살'만으로는 살다·살림과 구분이 안 되니 이름을 다 적는다(뒤에 아·았·림이 붙은 '살다' 꼴은 뺀다).
SAL_NAMES = ("천", "반안", "화개", "월", "겁", "재", "지", "년", "연", "망신", "장성", "역마", "육해", "도화",
             "백호", "상문", "조객", "원진", "귀문", "양인", "고신", "과숙", "홍염", "고초")
SAL_RE = re.compile(r"(?:[들눌날복악]?삼재|삼살|대장군|(?:" + "|".join(sorted(SAL_NAMES, key=len, reverse=True))
                    + r")살(?!아|았|림|면서|던))")

# 조언 틀 — 이 가운데 하나가 같은 문장(제목이면 제목 전체)에 있어야 한다.
ADVICE_RE = re.compile(
    r"(지킬|지키|지켜|넘기|넘겨|넘어가|복삼재|바꾸는|바꿔|바꿀|조심할|조심하|챙기|챙길|챙겨|대비|준비|살리|살려|"
    r"다스리|다스려|비결|요령|방법|는 법|잘 쓰|도움이|도움을|기회|"
    r"세요|십시오|시면 좋|면 좋아요|면 좋습니다|면 됩니다|면 돼요|괜찮아요|괜찮습니다|걱정 마|걱정하지|겁낼|겁먹|"
    r"두려워하지|미리 알|알아 두|알아두|"
    # 몸가짐 조언(낮추기·천천히·나누기·채우기 …)
    r"겸손|낮추|낮춰|천천히|차분히|쉬어 가|아끼|아껴|줄이|줄여|나누|나눠|베풀|살피|돌보|다지|채우|마무리|정리)")

# 살·삼재 낱말과 같은 문장에 올 수 없는 말 — 겁주기 · 한 해를 통째로 깎아내리기
FEAR = ("큰일", "망한", "망하", "망할", "망해", "망칩", "망쳐", "죽는", "죽을", "죽음", "죽습", "재앙", "흉하", "흉한", "흉사",
        "불길", "액운", "저주", "횡액", "무서운", "무섭", "끔찍", "피할 수 없", "화를 입", "화를 당", "사고가", "사고를",
        "사고 나", "사고 납", "교통사고", "불행", "최악", "나쁜 해", "안 좋은 해", "좋지 않은 해", "힘든 해", "힘든 한 해",
        "되는 일이 없", "운이 없는 해", "파산", "쫄딱", "박살")

_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def units(text: str, unit: str = "sentence") -> list[str]:
    t = str(text or "").strip()
    if not t:
        return []
    if unit == "whole":
        return [t]
    return [u.strip() for u in _SPLIT.split(t) if u and u.strip()]


def sal_words(text: str) -> list[str]:
    return list(dict.fromkeys(SAL_RE.findall(str(text or ""))))


def fear_words(text: str) -> list[str]:
    t = str(text or "")
    return [w for w in FEAR if w in t]


def violations(text: str, unit: str = "sentence", question: bool = False) -> list[str]:
    """살·삼재 낱말이 든 단위(문장 또는 통째)마다 — 조언 틀이 없거나, 겁주는 말이 같이 있으면 한 줄씩.

    question=True: 시청자 질문 칸('천살이 든 해에는 이사를 미뤄야 하나요?') — 답이 조언 틀이므로 겁주는 말만 본다."""
    out = []
    for u in units(text, unit):
        sw = sal_words(u)
        if not sw:
            continue
        fw = fear_words(u)
        short = u if len(u) <= 60 else u[:57] + "…"
        if fw:
            out.append(f"'{'·'.join(sw)}'와 겁주는 말({', '.join(fw)})을 같이 썼다: {short!r} — 조언으로만 쓴다")
        elif not question and not ADVICE_RE.search(u):
            out.append(f"'{'·'.join(sw)}'에 조언 틀이 없다: {short!r} — '꼭 지킬 3가지'·'잘 넘기는 법'·"
                       "'복삼재로 바꾸는 법'·'조심할 달'·'…하세요'처럼 같은 문장에서 조언으로 이어 쓴다")
    return out


def ok(text: str, unit: str = "sentence", question: bool = False) -> bool:
    return not violations(text, unit, question)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for s in sys.argv[1:] or ["2027년 천살 드는 띠 꼭 지킬 3가지", "올해는 삼재입니다.", "삼재라 큰일 납니다. 조심하세요."]:
        print(s, "→", violations(s) or "OK")
