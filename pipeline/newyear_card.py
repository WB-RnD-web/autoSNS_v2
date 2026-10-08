#!/usr/bin/env python3
"""2027 정미년(丁未年) 신년운세 표 쇼츠 — 4편 1차 묶음 (2026-10-07).

왜: 왕별이 수익화 방향(10/7)의 핵심 시즌이 '2027 신년운세'다. 수요는 벌써 올라왔다(10/7 실측, 지난 30일):
  '2027 운세' 상위 20편 중앙값 10.4만 — 그중 쇼츠 상위는 전부 9초 안팎 표(소문만복 '2027 띠 순위 TOP 12' 17.9만 ·
  가화만사성 '2027 재물운 점수 50~91년생' 17.4만 · '2027 돈방석 띠 순위' 13만). 우리 표 형식과 그대로 맞는다.
  - 남들은 순위·점수에 근거가 없다. 우리는 2027년의 간지(丁未)와 내 띠·태어난 해의 관계로 정하고 이유를 적는다
    (pulli_card 와 같은 지지 관계·오행 표). 같은 해(2027)면 늘 같은 표 — 날짜 해시가 없다.
  - 편마다 보는 것이 다르다(총운 = 띠와 未의 관계 · 재물운 = 재물 오행 · 달 = 월건 · 끝자리 = 천간 십신).
    ★한 번씩만 낸다(같은 표를 다시 올리지 않는다). 12~1월 본편성(띠별 단독·롱폼)은 1차 성적을 보고 PR 로 채운다.
  - '삼재'는 쓰지 않는다 — 운세 문구 금지어(겁주는 말, theme_card.BANNED)다.
  - ★어르신 눈높이(사용자 10/7 '위화감·거부감 없게'): 등급은 'S급·에스급' 대신 '대길 ★★★★ · 길 · 보통 · 조심',
    조심 띠는 꾸짖지 않고 조언으로 말한다, 화면엔 십신 이름(편관·상관·겁재…) 대신 쉬운 말 — 근거 용어는 설명란에.

근거(전통 명리 — 재미로 보는 운세라는 고지는 그대로):
  2027년 = 정미(丁未). 천간 丁 = 불(음) · 지지 未 = 양띠 · 흙.
  - 총운: 내 띠와 未의 관계 — 육합(오·미)·삼합(해묘미)은 S, 충(축)·원진(자)·형(술)은 C, 그 사이는 丁(불)과 내 띠 오행의
    관계로 A(돕는 기운·같은 기운·같은 띠)와 B(식상·재성·관성)를 나눈다(tier_card.tier_of 와 같은 규칙).
  - 재물운: 2027년의 두 기운(丁 불 · 未 흙)이 내 띠의 재물 오행(재성)이면 +1.5, 식상(재물을 낳는 기운) +0.5,
    같은 기운(비겁 — 나눠 쓸 일) −0.5 · 未와 육합 +2 · 삼합 +1.5 · 충 −2 · 원진·형 −1.5 · 해·파 −0.5.
    S ≥ 3 · A ≥ 1.5 · C ≤ −1 · 나머지 B.
  - 좋은 달·조심할 달: 달마다 바뀌는 월건(절기 기준 — 1월 축 · 2월 인 … 12월 자)과 내 띠가 육합·삼합인 달은 좋은 달,
    충·원진·형인 달은 조심할 달(세 개까지, 충 → 원진 → 형).
  - 태어난 해 끝자리: 끝자리 = 태어난 해의 천간(0 경 · 1 신 · 2 임 · 3 계 · 4 갑 · 5 을 · 6 병 · 7 정 · 8 무 · 9 기).
    2027년 천간 丁이 내 천간에 무엇인지(십신 — 정관·편관·정재·편재·상관·식신·겁재·비견·정인·편인)와
    천간합(정임)·천간충(정계)으로 한 줄씩.

편성: 월·목 08:13 KST(POST_DAYS) · 2026-10-12 부터 4편 — 날짜로 편을 정한다(루틴 판단이 아니다).

    python pipeline/newyear_card.py show [--date 2026-10-12]
    python pipeline/newyear_card.py make [--date …] --out <path>   # 편성일이 아니면 아무것도 안 쓴다(종료 코드 0)
    python pipeline/newyear_card.py path [--date …]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fortune_card import ANIMALS, YEAR_MAX, YEAR_MIN, years_of  # noqa: E402
import birth_basis  # noqa: E402
from pulli_card import (BRANCH_EL, BRANCHES, CAT_BASE, CTL, EL_WORD, GEN, HOOK_TAIL, REL, STEM_EL, STEMS,  # noqa: E402
                        STEMS_HJ, BRANCHES_HJ, kst_today, relation, sipsin)
from tier_card import TIERS, tier_of  # noqa: E402

TOPIC = "fortune_newyear"
ACCENT = "#E8590C"                    # 丁火 — 붉은 양의 해
BRAND = "왕별이 · 2027 정미년 신년운세"
YEAR = 2027
START = dt.date(2026, 10, 12)         # 첫 편(월)
POST_DAYS = (0, 3)                    # 월·목(월=0)


def year_pillar(y: int = YEAR) -> dict:
    i = (y - 4) % 60
    s, b = i % 10, i % 12
    return {"stem": s, "branch": b, "name": STEMS[s] + BRANCHES[b], "hanja": STEMS_HJ[s] + BRANCHES_HJ[b],
            "stem_el": STEM_EL[s], "branch_el": BRANCH_EL[b], "animal": ANIMALS[b]}


YP = year_pillar()                    # 정미 · 丁未 · 불 · 흙 · 양


def josa(word: str, a: str, b: str) -> str:
    c = word[-1]
    return word + (a if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else b)


def yrs_text(years: list[int]) -> str:
    return "·".join(f"{y % 100:02d}" for y in years) + "년생"


# ── 1·2편: 총운·재물운 등급표(tier 장면) ─────────────────────────────
LINE_REL = {"육합": "정미년과 육합", "삼합": "해묘미 삼합", "같은 띠": "내 띠의 해", "충": "충·큰일은 천천히",
            "원진": "원진·말 아끼기", "형": "형·서두르지 않기", "해": "해·한 박자 쉬기", "파": "파·약속 확인"}
LINE_CAT = {"인성": "돕는 기운의 해", "비겁": "같은 기운의 해", "식상": "베풀수록 좋은 해", "재성": "재물 기운의 해",
            "관성": "맡은 일 많은 해"}
SAY_CAT = {"인성": "올해 불 기운이 내 띠를 살려 주는 돕는 기운", "비겁": "올해 불 기운이 내 띠와 같은 기운",
           "식상": "내 띠가 올해 불 기운을 낳는 식상 — 베풀수록 돌아오는 기운",
           "재성": "내 띠가 올해 불 기운을 다스리는 재성 — 재물 기운", "관성": "올해 불 기운이 내 띠를 다잡는 관성 — 맡을 일이 느는 기운"}
SAY_REL = {"육합": "양띠해(未)와 육합 — 손발이 맞는 짝의 해", "삼합": "해묘미 삼합 — 양띠해와 한 팀",
           "같은 띠": "내 띠의 해 — 기운이 겹쳐요", "충": "양띠해(未)와 정면으로 부딪히는 충",
           "원진": "양띠해(未)와 원진 — 서운함이 쌓이기 쉬워요", "형": "축술미 형 — 서두르면 엇나가요",
           "해": "양띠해와 해 — 한 박자 쉬어 가요", "파": "양띠해와 파 — 약속은 다시 확인해요"}


def total_items() -> list[dict]:
    out = []
    for b, a in enumerate(ANIMALS):
        rel, grp = relation(YP["branch"], b)
        cat = sipsin(YP["stem_el"], b)
        out.append({"animal": a, "branch": b, "rel": rel, "cat": cat, "years": years_of(a), "tier": tier_of(rel, cat),
                    "line": LINE_REL[rel] if rel else LINE_CAT[cat],
                    "why": SAY_REL[rel] if rel else SAY_CAT[cat]})
    out.sort(key=lambda r: (REL[r["rel"]][1], -CAT_BASE[r["cat"]], (r["branch"] - YP["branch"]) % 12))
    return out


def money_cats(b: int) -> list[str]:
    """2027년의 두 기운(천간 丁 · 지지 未)이 내 띠에게 각각 무슨 기운인가."""
    return [sipsin(YP["stem_el"], b), sipsin(YP["branch_el"], b)]


MONEY_CAT = {"재성": 1.5, "식상": 0.5, "비겁": -0.5, "인성": 0.0, "관성": 0.0}
MONEY_REL = {"육합": 2.0, "삼합": 1.5, "같은 띠": 0.0, "충": -2.0, "원진": -1.5, "형": -1.5, "해": -0.5, "파": -0.5, "": 0.0}


def money_line(rel: str, cats: list[str]) -> str:
    if "재성" in cats:
        return f"재물 기운·{rel}" if rel in ("육합", "삼합", "원진") else "재물 기운 드는 해"
    if rel in ("육합", "삼합"):
        return f"정미년과 {rel}"
    if rel == "충":
        return "충·큰 지출 조심"
    if rel in ("형", "원진"):
        return f"{rel}·돈 약속 조심"
    if "식상" in cats:
        return "베풀면 도는 해"
    if "비겁" in cats:
        return "씀씀이 챙길 해"
    return "꾸준히 모으는 해"


def money_why(b: int, rel: str, cats: list[str]) -> str:
    me = EL_WORD[BRANCH_EL[b]]
    parts = []
    for src, el, cat in (("정(丁) 불", YP["stem_el"], cats[0]), ("미(未) 흙", YP["branch_el"], cats[1])):
        if cat == "재성":
            parts.append(f"{src}이 {me} 띠의 재물 기운")
        elif cat == "식상":
            parts.append(f"{src}은 {me} 띠가 낳는 기운(재물을 낳음)")
        elif cat == "비겁":
            parts.append(f"{src}은 {me} 띠와 같은 기운(나눠 쓸 일)")
    if rel in ("육합", "삼합", "충", "원진", "형", "해", "파"):
        parts.append(f"양띠해와 {rel}")
    return " · ".join(parts) or "올해 두 기운 모두 재물과 무관 — 꾸준히 모으는 해"


def money_items() -> list[dict]:
    out = []
    for b, a in enumerate(ANIMALS):
        rel, _ = relation(YP["branch"], b)
        cats = money_cats(b)
        pts = sum(MONEY_CAT[c] for c in cats) + MONEY_REL[rel]
        tier = "S" if pts >= 3 else "A" if pts >= 1.5 else "C" if pts <= -1 else "B"
        out.append({"animal": a, "branch": b, "rel": rel, "cats": cats, "points": pts, "years": years_of(a), "tier": tier,
                    "line": money_line(rel, cats), "why": money_why(b, rel, cats)})
    out.sort(key=lambda r: (-r["points"], REL[r["rel"]][1], (r["branch"] - YP["branch"]) % 12))
    return out


TIER_BASIS = {
    "total": {"S": "양띠해(未)와 합(육합·삼합)", "A": "같은 띠 · 올해 불 기운이 돕거나 같은 기운",
              "B": "올해 불 기운을 낳거나·다스리거나·다잡히는 띠", "C": "양띠해와 충·원진·형"},
    "money": {"S": "재물 기운 + 합", "A": "재물 기운 또는 육합", "B": "무난 — 꾸준히 모으기", "C": "충·형 — 큰돈 약속은 천천히"},
}


def build_tiers(ep_id: str) -> list[dict]:
    items = total_items() if ep_id == "total" else money_items()
    return [dict(t, basis=TIER_BASIS[ep_id][t["id"]], items=[r for r in items if r["tier"] == t["id"]]) for t in TIERS]


# ── 3편: 좋은 달·조심할 달(궁합표 장면) ───────────────────────────────
MONTH_BRANCH = {m: m % 12 for m in range(1, 13)}     # 양력 달 → 월건 지지(절기 기준: 1월 축 · 2월 인 … 12월 자)


def month_rows() -> list[dict]:
    rows = []
    for b, a in enumerate(ANIMALS):
        good, bad = [], []
        for m, mb in MONTH_BRANCH.items():
            rel, _ = relation(mb, b)
            if rel in ("육합", "삼합"):
                good.append((m, rel))
            elif rel in ("충", "원진", "형"):
                bad.append((m, rel))
        good.sort(key=lambda x: (REL[x[1]][1], x[0]))
        bad.sort(key=lambda x: (REL[x[1]][1], x[0]))
        good, bad = good[:3], bad[:3]
        rows.append({"animal": a, "branch": b, "years": years_of(a), "good": good, "bad": bad})
    return rows


def months_text(ms: list[tuple[int, str]]) -> str:
    return "·".join(str(m) for m, _ in sorted(ms)) + "월"


def rels_text(ms: list[tuple[int, str]]) -> str:
    return "·".join(dict.fromkeys(r for _, r in ms))


# ── 4편: 태어난 해 끝자리(궁합표 장면 · 10줄) ─────────────────────────
def digit_stem(d: int) -> int:
    return (d + 6) % 10                                  # 1984 → 4 → 갑 · 1990 → 0 → 경


def ten_god(me: int, other: int = YP["stem"]) -> str:
    """내 천간(me)에게 2027년 천간(other)이 무엇인가 — 음양까지 보는 십신."""
    em, eo = STEM_EL[me], STEM_EL[other]
    same = me % 2 == other % 2
    if em == eo:
        return "비견" if same else "겁재"
    if GEN[eo] == em:
        return "편인" if same else "정인"
    if GEN[em] == eo:
        return "식신" if same else "상관"
    if CTL[em] == eo:
        return "편재" if same else "정재"
    return "편관" if same else "정관"


HAP = {frozenset((0, 5)), frozenset((1, 6)), frozenset((2, 7)), frozenset((3, 8)), frozenset((4, 9))}    # 갑기·을경·병신·정임·무계
CHUNG = {frozenset((0, 6)), frozenset((1, 7)), frozenset((2, 8)), frozenset((3, 9))}                    # 갑경·을신·병임·정계
# 십신 → (좋은 기운, 그 한 줄, 조심할 것, 그 한 줄) — 줄은 10자 이내
# ★화면엔 십신 이름(편관·상관·겁재…)을 쓰지 않는다 — 어르신께 어려운 말(10/7). 근거 용어는 설명란(GOD_SAY)에.
GOD = {
    "정관": ("명예·자리", "체면이 서는 해", "체면 지출", "겉치레 줄이기"),
    "편관": ("결단·정리", "미룬 일 끝내기", "무리한 일정", "쉬어 가며 하기"),
    "정재": ("돈·인연", "합이 드는 해", "정에 끌린 돈", "빌려주기 조심"),
    "편재": ("큰돈 흐름", "돈이 크게 도는 해", "돈 약속", "서명은 천천히"),
    "상관": ("재주·말솜씨", "솜씨 보일 해", "말실수", "한 번 더 생각"),
    "식신": ("먹을 복·자식", "넉넉한 해", "늘어지기", "자주 걷기"),
    "겁재": ("형제·동료", "함께하면 좋은 해", "돈거래", "같이 쓰는 돈 정리"),
    "비견": ("친구·자신감", "친구가 힘인 해", "혼자 결정", "의논하고 정하기"),
    "정인": ("문서·도장", "도움 받는 해", "미루기", "때 놓치지 않기"),
    "편인": ("배움·취미", "배우기 좋은 해", "걱정 많음", "생각은 짧게"),
}
GOD_SAY = {
    "정관": "나를 바르게 세워 주는 기운(정관) — 자리와 체면이 서는 해",
    "편관": "나를 세게 다잡는 기운(편관) — 미뤄 둔 일을 결단하는 해",
    "정재": "내가 다스리는 재물 기운(정재)에 정임 천간합까지 — 돈과 인연이 붙는 해",
    "편재": "크게 움직이는 재물 기운(편재)이지만 정계 천간충 — 서명·돈 약속은 천천히",
    "상관": "내 재주가 밖으로 나가는 기운(상관) — 말솜씨가 빛나지만 말실수 조심",
    "식신": "먹을 복·자식 복의 기운(식신) — 넉넉하지만 늘어지기 쉬운 해",
    "겁재": "나와 같은 불이지만 음양이 다른 기운(겁재) — 형제·동료와 함께, 돈거래는 조심",
    "비견": "나와 똑같은 기운(비견) — 친구가 힘이 되는 해, 고집은 내려놓기",
    "정인": "나를 살려 주는 기운(정인) — 문서·도장 운, 미루지 않기",
    "편인": "나를 살려 주는 다른 결의 기운(편인) — 배움·취미에 좋은 해, 걱정은 짧게",
}


def digit_years(d: int) -> list[int]:
    return [y for y in range(YEAR_MIN, YEAR_MAX + 1) if y % 10 == d]


def digit_rows() -> list[dict]:
    rows = []
    for d in range(10):
        s = digit_stem(d)
        god = ten_god(s)
        g, gl, b, bl = GOD[god]
        pair = frozenset((s, YP["stem"]))
        rows.append({"digit": d, "stem": s, "god": god, "hap": pair in HAP, "chung": pair in CHUNG,
                     "years": digit_years(d), "good": g, "good_line": gl, "bad": b, "bad_line": bl})
    return rows


# ── 편 목록 ───────────────────────────────────────────────────────────
LAMB = "a cute fluffy white lamb mascot wearing a small red knitted scarf, "
EPISODES = [
    {"id": "total", "scene": "tier", "card": "2027 띠별 운세 등급표",
     "yt": "2027 정미년 띠별 운세 등급표 | 대길부터 조심까지 내 띠는? · 45~96년생 전부",
     "foot": "대길 = 합 · 조심 = 충·원진·형 — 2027 정미년 풀이, 재미로 보세요",
     "hook": LAMB + "sitting by a low wooden table with persimmons and a celadon teacup in a hanok room, first "
                    "morning sunlight through plain paper sliding doors, calm hopeful mood, no people"},
    {"id": "money", "scene": "tier", "card": "2027 재물운 등급표",
     "yt": "2027 정미년 띠별 재물운 등급표 | 재물 대길은 어느 띠? · 45~96년생 전부",
     "foot": "재물 오행 + 합·충 — 2027 정미년 풀이, 재미로 보세요",
     "hook": LAMB + "beside a traditional Korean wooden chest with brass fittings, silk pouches and persimmons on a "
                    "tray, warm golden light in a hanok room with plain paper walls, no people"},
    {"id": "months", "scene": "gunghap", "card": "2027 좋은 달·조심할 달",
     "yt": "2027 정미년 띠별 좋은 달·조심할 달 | 12띠 전부 · 45~96년생",
     "cols": ("좋은 달", "조심할 달"),
     "foot": birth_basis.SCREEN_CAL_MONTH + " — 재미로 보세요",
     "hook": LAMB + "sitting on a hanok wooden porch looking at a garden with a maple tree and a plum tree, "
                    "soft seasonal light, peaceful mood, no people"},
    {"id": "digit", "scene": "gunghap", "card": "끝자리로 보는 2027",
     "yt": "태어난 해 끝자리로 보는 2027 정미년 운세 | 0~9 전부 · 45~96년생",
     "cols": ("2027 좋은 기운", "조심할 것"), "head": "태어난 해 끝자리",
     "foot": "끝자리 = 태어난 해 천간 · 2027 천간은 정(丁) — 재미로 보세요",
     "hook": LAMB + "next to a low wooden table with a small potted pine and a celadon teacup in a sunlit hanok "
                    "room with plain paper walls, calm mood, no people"},
]


def is_post_day(d: dt.date) -> bool:
    """월·목 · START 부터 · 4편 안(목록이 바닥나면 쓰지 않는다 — 새 편은 PR 로 채운다)."""
    return d >= START and d.weekday() in POST_DAYS and post_index(d) < len(EPISODES)


def post_index(d: dt.date) -> int:
    return sum(1 for k in range((d - START).days) if (START + dt.timedelta(days=k)).weekday() in POST_DAYS)


def episode_for(d: dt.date) -> dict:
    """그날의 편. 편성일이 아닌 날(견본)은 가장 가까운 다음 편, 시리즈가 끝났으면 마지막 편."""
    return EPISODES[min(post_index(d), len(EPISODES) - 1)]


def episode_by_id(ep_id: str) -> dict:
    return next(e for e in EPISODES if e["id"] == ep_id)


def title(ep: dict) -> str:
    return ep["yt"]


def narration(ep: dict) -> str:
    """9~11초 — 표는 짧아야 다시 돈다. 우리말 등급(대길) · 조심 띠는 조언으로(어르신 눈높이, 10/7)."""
    if ep["scene"] == "tier":
        tiers = build_tiers(ep["id"])
        s, c = ", ".join(r["animal"] for r in tiers[0]["items"]), ", ".join(r["animal"] for r in tiers[3]["items"])
        if ep["id"] == "total":
            return (f"2027년 정미년 띠별 운세예요. 대길은 {s}띠. {c}띠는 서두르지 말고 차분히 가면 좋아요. "
                    "내 띠도 찾아보세요.")
        return f"2027년 정미년 재물운이에요. 재물 대길은 {s}띠. {c}띠는 큰돈 약속만 천천히 하세요. 내 띠도 찾아보세요."
    if ep["id"] == "months":
        r = month_rows()[0]                                  # 쥐띠를 예로
        best = r["good"][0][0]
        worst = r["bad"][0][0]
        return (f"2027년 띠별 좋은 달과 조심할 달이에요. 쥐띠는 {best}월이 가장 좋고, {worst}월은 조심하세요. "
                "내 띠도 찾아보세요.")
    rows = {r["digit"]: r for r in digit_rows()}
    return (f"태어난 해 끝자리로 보는 2027년 운세예요. 끝자리 2는 {rows[2]['good'].replace('·', '과 ')}이 붙는 해, "
            f"8은 {rows[8]['good'].replace('·', ' ')} 운이에요. 내 끝자리도 찾아보세요.")


def description(ep: dict) -> str:
    head = {"total": "2027년 정미년(丁未年) 띠별 운세 등급표 — 양띠해의 지지(未)와 내 띠가 합인지 충인지로 네 등급을 나눴어요.",
            "money": "2027년 정미년(丁未年) 띠별 재물운 등급표 — 올해의 두 기운(정 = 불 · 미 = 흙)이 내 띠의 재물 기운인지 봤어요.",
            "months": "2027년 띠별 좋은 달·조심할 달 — 달마다 바뀌는 월건(月建)과 내 띠의 관계로 정했어요.",
            "digit": "태어난 해 끝자리로 보는 2027년 운세 — 끝자리는 태어난 해의 천간이에요. 2027년 천간 정(丁)이 나에게 무엇인지 봤어요."}
    note = {"digit": birth_basis.year_note(),
            "months": birth_basis.ddi_note() + "\n" + birth_basis.cal_month_note()}.get(ep["id"]) or birth_basis.ddi_note()
    lines = [head[ep["id"]], "", note, ""]
    if ep["scene"] == "tier":
        for t in build_tiers(ep["id"]):
            lines.append(f"[{t['label']} {t['stars']}] {t['basis']}")
            lines += [f"· {r['animal']}띠({yrs_text(r['years'])}) — {r['why']}." for r in t["items"]] or ["· 없어요."]
            lines.append("")
        how = ("등급은 이렇게 정했어요: 양띠해(未)와 육합·삼합이면 대길, 충·원진·형이면 조심, 그 사이는 올해 천간 정(丁, 불)과 "
               "내 띠 오행의 관계로 길·보통을 나눴어요." if ep["id"] == "total" else
               "등급은 이렇게 정했어요: 올해의 정(불)·미(흙)가 내 띠가 다스리는 오행(재성 = 재물)이면 더하고, "
               "재물을 낳는 기운(식상)은 조금 더하고, 같은 기운(비겁 — 나눠 쓸 일)은 조금 빼고, 양띠해와 합이면 더하고 "
               "충·원진·형이면 뺐어요.")
        lines += [how, "조심 칸이어도 걱정 마세요 — 서두르지 않으면 되는 해예요. 내 띠는 어디에 있나요? 댓글로 남겨 주세요 🙏"]
    elif ep["id"] == "months":
        for r in month_rows():
            g = " · ".join(f"{m}월({rel})" for m, rel in r["good"])
            b = " · ".join(f"{m}월({rel})" for m, rel in r["bad"])
            lines.append(f"· {r['animal']}띠({yrs_text(r['years'])}) — 좋은 달: {g} / 조심할 달: {b}")
        lines += ["", "달은 이렇게 봤어요: 1월 축 · 2월 인 · 3월 묘 … 12월 자처럼 달마다 바뀌는 지지(월건)와 내 띠가 "
                  "육합·삼합이면 좋은 달, 충·원진·형이면 조심할 달이에요. 절기 기준이라 매달 4~8일께 바뀌어요.",
                  "내 띠의 좋은 달은 언제인가요? 댓글로 남겨 주세요 🙏"]
    else:
        for r in digit_rows():
            lines.append(f"· 끝자리 {r['digit']}({STEMS[r['stem']]} {STEMS_HJ[r['stem']]} · {yrs_text(r['years'])}) — "
                         f"{GOD_SAY[r['god']]}.")
        lines += ["", "끝자리는 이렇게 봤어요: 태어난 해 끝자리가 그해의 천간이에요(0 경 · 1 신 · 2 임 · 3 계 · 4 갑 · 5 을 · "
                  "6 병 · 7 정 · 8 무 · 9 기). 2027년 천간 정(丁, 음의 불)이 내 천간에게 무엇인지(십신)와 "
                  "정임 천간합·정계 천간충으로 풀었어요.",
                  "내 끝자리는 몇 번인가요? 댓글로 남겨 주세요 🙏"]
    lines += ["", "※ 전통 명리의 신년운세 풀이를 재미로 정리한 운세입니다.", "",
              "#2027운세 #정미년 #신년운세 #띠별운세 #운세 #shorts"]
    return "\n".join(lines)


def scene_for(ep: dict) -> dict:
    pill = "2027 정미년 · 끝자리 0~9 · 45~96년생" if ep["id"] == "digit" else "2027 정미년 · 12띠 · 45~96년생"
    base = {"type": ep["scene"], "pill": pill, "title": ep["card"], "foot": ep["foot"], "brand": BRAND,
            "basis": birth_basis.SCREEN_YEAR if ep["id"] == "digit" else birth_basis.SCREEN_DDI,
            "narration": narration(ep)}
    if ep["scene"] == "tier":
        base["tiers"] = [{"id": t["id"], "label": t["label"], "big": t["label"], "small": t["stars"], "color": t["color"],
                          "items": [{k: r[k] for k in ("animal", "years", "line")} for r in t["items"]]}
                         for t in build_tiers(ep["id"])]
        return base
    base["cols"] = list(ep["cols"])
    if ep["id"] == "months":
        base["rows"] = [{"animal": r["animal"], "years": r["years"], "good": months_text(r["good"]),
                         "good_line": rels_text(r["good"]), "bad": months_text(r["bad"]),
                         "bad_line": rels_text(r["bad"])} for r in month_rows()]
    else:
        base["head"] = ep["head"]
        base["rows"] = [{"label": f"끝자리 {r['digit']}", "years": r["years"], "good": r["good"],
                         "good_line": r["good_line"], "bad": r["bad"], "bad_line": r["bad_line"]} for r in digit_rows()]
    return base


def storyboard(d: dt.date, ep: dict | None = None) -> dict:
    ep = ep or episode_for(d)
    t = title(ep)
    return {
        "date": d.isoformat(), "topic": TOPIC, "episode": ep["id"], "privacy": "public",
        "accent": ACCENT, "_min_total": 9.0,
        "hook_title": ep["card"], "headline": t, "thumbnail_hook": ep["hook"] + HOOK_TAIL,
        "scenes": [scene_for(ep)],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(ep)}},
        "notes": f"2027 신년운세 · episode={ep['id']} · newyear_card.py 가 만든 스토리보드",
    }


def is_newyear(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    ep = episode_by_id(sb.get("episode") or episode_for(dt.date.fromisoformat(sb["date"]))["id"])
    return {"title": title(ep)[:95], "description": description(ep)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="2027 정미년 신년운세 표")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--episode", choices=[e["id"] for e in EPISODES], help="편을 직접 고른다(견본용)")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true", help="편성일이 아니어도 만든다(견본용)")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(path_for(d))
        return 0
    if a.cmd == "make" and not (a.force or a.episode or is_post_day(d)):
        print(f"{d}: 신년운세 편성일이 아니다(월·목 4편, {START} 부터) — 건너뜀")
        return 0
    ep = episode_by_id(a.episode) if a.episode else episode_for(d)
    sb = storyboard(d, ep)
    if a.cmd == "show":
        sc = sb["scenes"][0]
        print(f"{d} · {ep['id']} · {sb['platforms']['youtube']['title']}")
        if sc["type"] == "tier":
            for t in sc["tiers"]:
                print(f"  {t['id']} " + " · ".join(f"{r['animal']}({r['line']})" for r in t["items"]))
        else:
            for r in sc["rows"]:
                print(f"  {r.get('label') or r['animal']:<6} {r['good']:<10} ({r['good_line']}) | {r['bad']:<8} ({r['bad_line']})")
        print("  🎙️", sc["narration"])
        return 0
    out = a.out or path_for(d)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
