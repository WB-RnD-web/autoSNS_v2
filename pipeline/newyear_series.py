#!/usr/bin/env python3
"""2027 정미년 신년운세 '시리즈' — 06:13 매일 운세 자리의 일부를 강한 표로 (2026-10-20 사용자 승인 '2번 ㄱㄱ').

왜(채널 맥박 10/20 · 형식별 첫 24시간 중앙값, 영상별 실측은 data/trend-radar registry):
  2027 신년운세 표 29,581(2편: 총운 18,456 · 재물운 40,706) · 해 끝자리 40,234 · 성씨 20,212 · 태어난 달 17,612
  · 띠 테마 13,962 · 운세 등급표 9,507 · ★매일 운세 표 8,387(그 전 7,350 · 30일 기준 6,310 — 표 가운데 가장 약한 축).
  시각별(10/2~10/19 표 쇼츠 첫 24시간 중앙값): 07시 21,578 · 08시 29,581 · 15시 14,320 · 09시 12,465 · 12시 11,659 ·
  06시 9,594 · 13시 4,354 · 10시 3,792 · 18시 3,301. 06시는 가운데 — 자리가 약한 게 아니라 '매일 운세 1~12위' 꼴이 약하다.
  늦게 올린 오늘 운세는 더 약했다(10/6 14:40 → 1,404). 그래서 매일 운세를 다른 시각으로 옮기지 않고 ★몇 요일만 남긴다.
  월요일 06:13 '이번 주 띠별 운세'(쇼츠 34,706 · 3편 중앙값)는 강해서 그대로 둔다.
  수요는 12~1월로 갈수록 오른다(2027 정미년 = 양띠 해) → 12/8 부터 한 칸 더(금).

편성(날짜로 정한다 — 루틴 판단이 아니다. 루틴 명령은 그대로):
  2026-10-27(화)부터 화·토 06:13, 2026-12-08 부터 화·금·토. 매달 1일은 건너뛴다(그날 루틴이 '이번 달' 운세를 쓸 수 있다).
  그 밖의 날 06:13 은 원래대로 — 월 = 이번 주 운세, 나머지 = 매일 운세 표(등급표 A/B 판정 10/23 결과를 그대로 따른다:
  tier_card.use_ab · fortune_card.use_card). 06:13 루틴(routine/fortune, 토픽 fortune)은 늘 하던 대로 '오늘 운세'
  대본을 올리고, 시리즈 날엔 파이프라인(run_pipeline)이 화면·제목·설명·배경·재생목록만 이 시리즈 편으로 바꾼다
  (등급표 A/B 와 같은 방식). 어느 날 무엇이 나가는지: python pipeline/newyear_series.py plan
  끄기 = SERIES_FROM 을 None 으로(그날부터 06:13 은 매일 운세로 돌아간다). 판정: pulse_experiments 'newyear-slot'(11/25).

편(EPISODES — 이 순서로 한 번씩만 낸다 · 같은 꼴(family)이 연달아 나오지 않는다):
  ★편마다 보는 근거가 다르다(유튜브 '서로 바꿔 끼워도 될 만큼 비슷한 영상' 정책 — 순위만 섞은 표는 내지 않는다).
  - 등급표(tier): 자식·손주 덕(식상) · 문서·집(인성) · 일복·명예(관성) · 친구·모임(비겁) — 올해 두 기운(丁 불 · 未 흙)이
    내 띠에게 무엇인지(십신)와 양띠해(未)와의 합·충을 편마다 다른 무게로. 2027년 1·2·3월 — 그 달의 월주(신축·임인·계묘)와 띠.
  - 띠 줄 표(gunghap 장면): 건강(오행 장부 — 챙길 곳·좋은 습관) · 행운의 색·숫자·방향(통관·조후 오행).
  - 띠 × 달 표: 돈 들어오는 달(재성 달) · 몸 가벼운 달(인성·비겁 달) · 나들이 좋은 달(역마·식상 달) ·
    좋은 달·조심할 달(newyear_card 1차 묶음의 셋째 편 — 10/19 루틴이 올리지 않아 한 번도 안 나갔다).
  - 태어난 해 끝자리 표: 재물운(丁·未 둘 다의 십신) · 귀인(천을귀인 — 귀인 띠·귀인 오는 달) · 좋은 달(그 달 천간과 합·충).
  - 출생연도 표(46~57 · 58~69 · 70~81 · 82~93년생): 천간 십신 × 지지 관계 — 해마다 다른 조합.
  - 태어난 달 표(음력 생일 달 · 조후 — 계절 태생과 뜨거운 해).
  - 2027 절기 달력(달이 바뀌는 날 · 그 달 월주 · 할 일) — 날짜는 ephem 으로 태양 황경을 구해 표로 박았다.
  '삼재'·살 이름은 ★조언 틀 안에서만(2026-10-20 사용자 '삼재 조언형 ㅇㅋ' — sal_frame.violations · 테스트가 본다).
  화면엔 십신 이름 대신 쉬운 말, 근거 용어는 설명란에. 띠별 깊은 풀이는 롱폼 '2027 정미년 깊이 보기'(longform_2027.py).
  ★목록이 바닥나면(2027-01-05) 06:13 은 매일 운세로 돌아간다 — 그 전에 새 편을 채운다(판정·주간 검토).

    python pipeline/newyear_series.py plan [--until 2027-01-10]      # 날짜별 편성
    python pipeline/newyear_series.py show [--date 2026-10-27 | --episode d_money]
    python pipeline/newyear_series.py sample --episode d_money --out <path>   # 견본용 스토리보드(06:13 대본 꼴)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import birth_basis  # noqa: E402
import newyear_card as NY  # noqa: E402
from fortune_card import ANIMALS, sb_date, scope_of, years_of  # noqa: E402
from pulli_card import (BRANCH_EL, BRANCHES, BRANCHES_HJ, CTL, EL_WORD, GEN, HOOK_TAIL, REL, STEM_EL, STEMS,  # noqa: E402
                        STEMS_HJ, kst_today, relation, sipsin)
from tier_card import TIERS, tier_of  # noqa: E402

TOPIC = "fortune"                     # 06:13 루틴 대본의 토픽 — 이 토픽(정확히)만 바꾼다
SERIES_FROM: dt.date | None = dt.date(2026, 10, 27)
CADENCE = ((dt.date(2026, 10, 27), (1, 5)),          # 화·토
           (dt.date(2026, 12, 8), (1, 4, 5)))        # 화·금·토(시즌)
ACCENT = NY.ACCENT
BRAND = NY.BRAND
YP = NY.YP                            # 정미 · 丁未
SRC = (("정(丁) 불", YP["stem_el"]), ("미(未) 흙", YP["branch_el"]))
WD = "월화수목금토일"
LAMB = NY.LAMB
STRONG_REL = ("육합", "삼합", "충", "원진", "형")
JARGON = ("편관", "상관", "겁재", "비견", "편인", "정인", "정관", "편재", "정재", "식신", "식상", "재성", "관성", "인성",
          "비겁", "십신", "천을귀인", "역마", "조후", "신살", "S급", "C급")      # 삼재는 10/20부터 조언 틀 안에서 허용(sal_frame)


def josa(word: str, a: str, b: str) -> str:
    return NY.josa(word, a, b)


def yrs_text(years: list[int]) -> str:
    return NY.yrs_text(years)


def cats(b: int) -> list[str]:
    """2027년의 두 기운(丁 불 · 未 흙)이 띠 b 에게 각각 무엇인가(십신 묶음)."""
    return [sipsin(YP["stem_el"], b), sipsin(YP["branch_el"], b)]


def yrel(b: int) -> tuple[str, str]:
    return relation(YP["branch"], b)


def el_rel(src: str, me: str) -> str:
    """오행 둘 — me 에게 src 가 무엇인가."""
    if src == me:
        return "비겁"
    if GEN[src] == me:
        return "인성"
    if GEN[me] == src:
        return "식상"
    if CTL[me] == src:
        return "재성"
    return "관성"


# ── 2027년의 달(절기로 나눈 양력 달) ─────────────────────────────────
# 월주: 1월(소한~입춘 전)은 아직 병오년의 신축월, 2월(입춘)부터 정미년 임인월 … 12월 임자월(오호둔: 정임년 = 임인 머리)
MONTH_STEM = {1: 7, 2: 8, 3: 9, 4: 0, 5: 1, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6, 11: 7, 12: 8}
MONTH_BRANCH = NY.MONTH_BRANCH        # 1월 축 · 2월 인 … 12월 자
# 2027 절기(12절) — ephem 태양 겉보기 황경(285°·315°…)을 한국 시각으로(10/20 계산). 날짜만 싣는다(시각은 몇 분 오차).
JEOLGI = {1: (5, "소한"), 2: (4, "입춘"), 3: (6, "경칩"), 4: (5, "청명"), 5: (6, "입하"), 6: (6, "망종"),
          7: (7, "소서"), 8: (8, "입추"), 9: (8, "백로"), 10: (8, "한로"), 11: (8, "입동"), 12: (7, "대설")}


def month_pillar(m: int) -> dict:
    s, b = MONTH_STEM[m], MONTH_BRANCH[m]
    return {"stem": s, "branch": b, "name": STEMS[s] + BRANCHES[b], "hanja": STEMS_HJ[s] + BRANCHES_HJ[b],
            "stem_el": STEM_EL[s], "branch_el": BRANCH_EL[b], "animal": ANIMALS[b]}


def month_span(m: int) -> str:
    """'1월 5일~2월 3일' — 그 달 절기부터 다음 절기 전날까지."""
    d0 = dt.date(2027, m, JEOLGI[m][0])
    d1 = (dt.date(2028, 1, 6) if m == 12 else dt.date(2027, m + 1, JEOLGI[m + 1][0])) - dt.timedelta(days=1)
    return f"{d0.month}월 {d0.day}일~{d1.month}월 {d1.day}일"


def months_text(ms: list[int]) -> str:
    return "·".join(str(m) for m in sorted(ms)) + "월" if ms else "없어요"


# ══ 1. 등급표 — 올해 두 기운의 십신 × 양띠해와의 관계(편마다 다른 무게) ══════════════════════
TIER_THEMES = {
    "t_kids": {
        "W": {"식상": 1.5, "재성": 0.5, "비겁": 0.3, "인성": -0.3, "관성": 0.0}, "RW": 0.3, "S": 2.0, "A": 1.0, "C": -0.8,
        "LINE": {"육합": "자식과 손발 척척", "삼합": "온 가족 한 팀", "충": "충·자식 일 천천히", "원진": "원진·서운함 풀기",
                 "형": "형·잔소리 줄이기", "식상": "자식 복 드는 해", "재성": "살림 보태는 자식", "비겁": "함께 나누는 정",
                 "인성": "내가 챙겨 줄 해", "관성": "자식 걱정 덜기"},
        "SAY": {"식상": "{src}은 내 띠가 낳는 기운(식상) — 자식·손주 기운",
                "재성": "{src}은 내 띠가 다스리는 기운(재성) — 자식 덕이 살림으로 이어져요",
                "비겁": "{src}은 내 띠와 같은 기운(비겁) — 함께 나누는 정",
                "인성": "{src}은 나를 돕는 기운(인성) — 받기보다 챙겨 줄 해"},
        "BASIS": {"S": "자식 기운(식상) + 양띠해와 합", "A": "자식 기운이 들거나 살림으로 이어짐", "B": "무난 — 내가 챙겨 주는 해",
                  "C": "충·형 — 자식 일은 천천히"},
        "HOW": "올해의 두 기운(정 = 불 · 미 = 흙)이 내 띠가 낳는 기운(식상 — 자식·손주)이면 크게 더하고, 살림으로 이어지는 "
               "재물 기운(재성)·같은 기운(비겁)은 조금 더하고, 나를 돕는 기운(인성)은 조금 뺐어요(받기보다 주는 해).",
        "SAY_N": "자식 손주 덕 등급표", "C_ADVICE": "자식 일은 천천히 가면 좋아요"},
    "t_docs": {
        "W": {"인성": 1.5, "관성": 0.5, "재성": -0.5, "식상": 0.0, "비겁": 0.0}, "RW": 0.5, "S": 2.0, "A": 1.0, "C": -1.0,
        "LINE": {"육합": "좋은 계약 짝", "삼합": "함께 정하면 좋아요", "충": "충·이사 이동수", "원진": "원진·두 번 확인",
                 "형": "형·문서 꼼꼼히", "인성": "문서·도장 복", "관성": "자리 문서 들어와요", "재성": "도장은 천천히",
                 "식상": "말로 한 약속 적기", "비겁": "명의는 분명히"},
        "SAY": {"인성": "{src}은 나를 살려 주는 기운(인성) — 문서·도장·집 운",
                "관성": "{src}은 나를 다잡는 기운(관성) — 자리와 문서가 따라와요",
                "재성": "{src}은 내가 다스리는 재물 기운(재성) — 돈이 문서를 앞서니 도장은 천천히"},
        "BASIS": {"S": "문서 기운(인성)이 겹치는 띠", "A": "문서 기운 또는 양띠해와 합", "B": "무난 — 꼼꼼히 보면 되는 해",
                  "C": "원진·충·형 — 서명은 한 번 더"},
        "HOW": "올해의 두 기운(정 = 불 · 미 = 흙)이 나를 살려 주는 기운(인성 — 문서·도장·집)이면 크게 더하고, 나를 다잡는 "
               "기운(관성)은 문서를 낳으니 조금 더하고, 재물 기운(재성)은 문서를 누르니 조금 뺐어요. 충은 이사·이동수로도 봐요.",
        "SAY_N": "문서 집 운 등급표", "C_ADVICE": "서명만 한 번 더 보세요"},
    "t_work": {
        "W": {"관성": 1.5, "인성": 0.5, "재성": 0.3, "식상": -0.5, "비겁": 0.0}, "RW": 0.4, "S": 2.0, "A": 0.6, "C": -0.6,
        "LINE": {"육합": "손발 맞는 일", "삼합": "모임 일 잘 풀려요", "충": "충·일은 나눠서", "원진": "원진·말 아끼기",
                 "형": "형·서두르지 않기", "관성": "맡을 일 많은 해", "인성": "도움 받아 일해요", "재성": "일이 살림 돼요",
                 "식상": "말 한마디 아끼기", "비겁": "함께 나눠 맡기"},
        "SAY": {"관성": "{src}은 나를 다잡는 기운(관성) — 자리·감투·맡을 일",
                "인성": "{src}은 나를 돕는 기운(인성) — 일을 거들어 줄 손",
                "재성": "{src}은 재물 기운(재성) — 일한 만큼 살림이 돼요",
                "식상": "{src}은 내 띠가 내보내는 기운(식상) — 말이 앞서면 자리가 흔들려요"},
        "BASIS": {"S": "일 기운(관성) + 돕는 기운", "A": "일 기운 또는 양띠해와 합", "B": "무난 — 하던 일 그대로",
                  "C": "충 — 일은 나눠서 천천히"},
        "HOW": "올해의 두 기운(정 = 불 · 미 = 흙)이 나를 다잡는 기운(관성 — 자리·감투·맡을 일)이면 크게 더하고, 일을 거드는 "
               "기운(인성)과 재물 기운(재성)은 조금 더하고, 내가 내보내는 기운(식상)은 자리를 흔드니 조금 뺐어요. "
               "일을 쉬고 계시면 모임·봉사 자리로 보세요.",
        "SAY_N": "일복 명예운 등급표", "C_ADVICE": "일을 나눠서 하면 좋아요"},
    "t_friends": {
        "W": {"비겁": 1.5, "식상": 0.5, "인성": 0.3, "재성": -0.3, "관성": 0.0}, "RW": 0.5, "S": 2.0, "A": 0.8, "C": -0.8,
        "LINE": {"육합": "찰떡 친구 생겨요", "삼합": "모임이 한 팀", "충": "충·한 발 양보", "원진": "원진·서운함 풀기",
                 "형": "형·말 천천히", "비겁": "친구가 힘인 해", "식상": "함께 베풀면 좋아요", "인성": "모임에서 도움",
                 "재성": "돈거래는 따로", "관성": "모임 일 맡아요"},
        "SAY": {"비겁": "{src}은 내 띠와 같은 기운(비겁) — 친구·형제가 힘",
                "식상": "{src}은 내 띠가 내보내는 기운(식상) — 베풀수록 사람이 모여요",
                "인성": "{src}은 나를 돕는 기운(인성) — 모임에서 도움 받아요",
                "재성": "{src}은 재물 기운(재성) — 친구 사이 돈거래는 따로"},
        "BASIS": {"S": "같은 기운(비겁) + 합 — 사람 복", "A": "같은 기운 또는 양띠해와 합", "B": "무난 — 아는 사람과 편하게",
                  "C": "원진·충 — 서운함은 바로 풀기"},
        "HOW": "올해의 두 기운(정 = 불 · 미 = 흙)이 내 띠와 같은 기운(비겁 — 친구·형제·모임)이면 크게 더하고, 베푸는 기운(식상)과 "
               "돕는 기운(인성)은 조금 더하고, 재물 기운(재성)은 친구 사이 돈 문제라 조금 뺐어요.",
        "SAY_N": "친구 모임 운 등급표", "C_ADVICE": "서운한 일은 바로 풀어 보세요"},
}
REL_SAY = NY.SAY_REL                  # '양띠해(未)와 육합 — 손발이 맞는 짝의 해' …


def theme_items(tid: str) -> list[dict]:
    th = TIER_THEMES[tid]
    W = th["W"]
    out = []
    for b, a in enumerate(ANIMALS):
        rel, _ = yrel(b)
        cs = cats(b)
        pts = round(sum(W[c] for c in cs) + th["RW"] * REL[rel][0], 2)
        tier = "S" if pts >= th["S"] else "C" if pts <= th["C"] else "A" if pts >= th["A"] else "B"
        if rel in STRONG_REL:
            cause = rel
        else:
            cause = max(cs, key=lambda c: W[c]) if max(W[c] for c in cs) > 0 else min(cs, key=lambda c: W[c])
        parts = [th["SAY"][c].format(src=src) for (src, _), c in zip(SRC, cs) if c in th["SAY"]]
        if rel:
            parts.append(REL_SAY[rel])
        out.append({"animal": a, "branch": b, "rel": rel, "cats": cs, "points": pts, "years": years_of(a), "tier": tier,
                    "line": th["LINE"][cause], "why": " · ".join(parts) or "올해 두 기운이 이 일과는 무난해요"})
    out.sort(key=lambda r: (-r["points"], REL[r["rel"]][1], (r["branch"] - YP["branch"]) % 12))
    return out


# ── 2027년 N월 등급표 — 그 달의 월주와 띠(일진 등급표와 같은 규칙, 날 대신 달) ──
M_LINE_REL = {"육합": "이달과 육합", "삼합": "{g} 삼합", "같은 띠": "내 띠의 달", "충": "충·큰일은 다음 달",
              "원진": "원진·말 아끼기", "형": "형·천천히", "해": "해·한 박자 쉬기", "파": "파·약속 확인"}
M_LINE_CAT = {"인성": "도움 받는 달", "비겁": "기운이 같은 달", "식상": "베푸는 달", "재성": "재물 기운 달",
              "관성": "맡은 일 꼼꼼히"}
M_SAY_REL = {"육합": "이달({m})과 육합 — 손발이 맞는 달", "삼합": "{g} 삼합 — 이달과 한 팀", "같은 띠": "내 띠의 달 — 기운이 겹쳐요",
             "충": "이달({m})과 정면으로 부딪히는 충 — 큰일은 다음 달로", "원진": "이달({m})과 원진 — 말 한마디 아끼기",
             "형": "이달({m})과 형 — 서두르지 않기", "해": "이달과 해 — 한 박자 쉬어 가기", "파": "이달과 파 — 약속은 다시 확인"}
M_SAY_CAT = {"인성": "이달 천간 {e} 기운이 나를 돕는 달(인성)", "비겁": "이달 천간 {e} 기운이 내 띠와 같은 달(비겁)",
             "식상": "내 띠가 이달 {e} 기운을 낳는 달(식상) — 베풀수록 좋아요", "재성": "내 띠가 이달 {e} 기운을 다스리는 달(재성) — 재물 기운",
             "관성": "이달 {e} 기운이 나를 다잡는 달(관성) — 맡은 일은 꼼꼼히"}
M_BASIS = {"S": "이달과 합(육합·삼합)", "A": "같은 띠 · 나를 돕는 기운 · 같은 기운", "B": "무난한 기운 · 가벼운 엇갈림(해·파)",
           "C": "충·원진·형"}


def month_items(m: int) -> list[dict]:
    p = month_pillar(m)
    out = []
    for b, a in enumerate(ANIMALS):
        rel, grp = relation(p["branch"], b)
        cat = sipsin(p["stem_el"], b)
        line = M_LINE_REL[rel].format(g=grp) if rel else M_LINE_CAT[cat]
        why = (M_SAY_REL[rel].format(m=p["name"] + "월", g=grp) if rel else
               M_SAY_CAT[cat].format(e=EL_WORD[p["stem_el"]]))
        out.append({"animal": a, "branch": b, "rel": rel, "cat": cat, "years": years_of(a), "tier": tier_of(rel, cat),
                    "line": line, "why": why})
    out.sort(key=lambda r: (REL[r["rel"]][1], -NY.CAT_BASE[r["cat"]], (r["branch"] - p["branch"]) % 12))
    return out


# ══ 2. 띠 줄 표 — 건강 · 행운 ═════════════════════════════════════════════════════
# 전통 오행 장부(목 = 간·눈 · 화 = 심장 · 토 = 위장 · 금 = 폐·기관지 · 수 = 콩팥·허리)와 2027년(불·흙)의 관계.
HEALTH = {  # 띠 오행 → (챙길 곳, 왜 한 줄, 좋은 습관, 관계 없는 띠의 둘째 줄, 설명)
    "수": ("허리·콩팥", "흙이 물을 누름", "물 자주 마시기", "따뜻한 물 한 잔",
          "올해 흙 기운(未)이 물을 누르는 해(관성). 오행에서 물은 콩팥·허리·귀 — 물을 자주 드시고 허리는 무리하지 마세요"),
    "토": ("위장·소화", "흙 기운이 겹침", "천천히 먹기", "배는 조금 덜 차게",
          "올해 불(丁)이 흙을 살리고 흙(未)까지 겹쳐 흙 기운이 많은 해(인성·비겁). 흙은 위장·소화 — 천천히, 조금씩 드세요"),
    "목": ("눈·피로", "불로 기운이 빠짐", "일찍 자기", "눈 자주 쉬기",
          "나무가 올해 불(丁)을 키우느라 기운이 빠지고(식상) 흙(未)을 다스리느라 바쁜 해(재성). 나무는 간·눈·힘줄 — 피로가 쌓이지 않게 일찍 주무세요"),
    "화": ("심장·열", "불 기운이 겹침", "더울 땐 쉬기", "땀나면 바로 쉬기",
          "올해 불(丁)이 겹치는 해(비겁). 불은 심장·피 흐름 — 더울 때 무리하지 말고 땀나면 쉬세요"),
    "금": ("목·기관지", "불이 쇠를 누름", "목 따뜻하게", "환절기 목 감싸기",
          "올해 불(丁)이 쇠를 누르는 해(관성) — 흙(未)이 쇠를 살려 주긴 해요(인성). 쇠는 폐·목·기관지·피부 — 환절기에 목을 따뜻하게 하세요"),
}
HEALTH_REL = {"육합": "합·같이 걷기", "삼합": "삼합·모여 걷기", "같은 띠": "내 띠의 해·천천히", "충": "충·운동은 가볍게",
              "원진": "원진·마음 편히", "형": "형·넘어짐 조심", "해": "해·한 박자 쉬기", "파": "파·일정 다시 보기"}
HEALTH_REL_SAY = {"육합": "양띠해와 육합 — 짝과 같이 걸으면 좋아요", "삼합": "해묘미 삼합 — 여럿이 모여 걷기 좋아요",
                  "같은 띠": "내 띠의 해 — 기운이 겹치니 쉬엄쉬엄", "충": "양띠해와 충 — 무리한 운동보다 가볍게",
                  "원진": "양띠해와 원진 — 서운한 마음을 오래 두지 마세요", "형": "축술미 형 — 서두르다 넘어지지 않게",
                  "해": "양띠해와 해 — 한 박자 쉬어 가요", "파": "양띠해와 파 — 일정은 다시 확인"}

# 행운 오행 — 2027년은 불·흙이 강하다. 내 띠 오행이 올해 무엇을 받는지 보고, 막힌 데를 이어 주는(통관)·식혀 주는(조후) 오행.
EL_COLOR = {"목": "초록·연두", "화": "빨강·분홍", "토": "노랑·황토", "금": "흰색·은색", "수": "검정·남색"}
EL_NUM = {"목": "3·8", "화": "2·7", "토": "5·10", "금": "4·9", "수": "1·6"}
EL_DIR = {"목": "동쪽", "화": "남쪽", "토": "가운데", "금": "서쪽", "수": "북쪽"}
EL_DIR_TIP = {"목": "동쪽 창 열기", "화": "남쪽 볕 쬐기", "토": "집 가운데 정리", "금": "서쪽으로 산책", "수": "북쪽 창 환기"}
LUCKY = {  # 띠 오행 → (행운 오행, 한 줄, 설명)
    "수": ("금", "쇠가 이어 줘요", "흙(未)이 물을 누르니 흙 → 쇠 → 물로 이어 주는 쇠 기운이 도와요(통관)"),
    "목": ("수", "물이 채워 줘요", "나무가 불을 키우느라 기운이 빠지니 나무를 살리는 물 기운이 채워 줘요"),
    "화": ("토", "흙이 열을 덜어요", "불이 겹쳐 뜨거우니 넘치는 불을 받아 주는 흙 기운으로 덜어 내요"),
    "토": ("목", "나무가 흙을 풀어요", "흙이 겹쳐 무거우니 흙을 풀어 주는 나무 기운이 좋아요"),
    "금": ("수", "물이 불을 식혀요", "불이 쇠를 누르니 불을 식혀 주는 물 기운이 좋아요(조후)"),
}


def health_rows() -> list[dict]:
    rows = []
    for b, a in enumerate(ANIMALS):
        e = BRANCH_EL[b]
        part, why1, habit, plain, say = HEALTH[e]
        rel, _ = yrel(b)
        rows.append({"animal": a, "branch": b, "years": years_of(a), "good": part, "good_line": why1, "bad": habit,
                     "bad_line": HEALTH_REL[rel] if rel else plain,
                     "why": f"{EL_WORD[e]} 기운의 띠 — {say}" + (f" · {HEALTH_REL_SAY[rel]}" if rel else "")})
    return rows


def lucky_rows() -> list[dict]:
    rows = []
    for b, a in enumerate(ANIMALS):
        e = BRANCH_EL[b]
        le, line, say = LUCKY[e]
        rows.append({"animal": a, "branch": b, "years": years_of(a), "good": EL_COLOR[le], "good_line": line,
                     "bad": f"{EL_NUM[le]} · {EL_DIR[le]}", "bad_line": EL_DIR_TIP[le], "lucky_el": le,
                     "why": f"{EL_WORD[e]} 기운의 띠 — {say}. 그래서 {EL_WORD[le]}의 색 {EL_COLOR[le]} · 숫자 {EL_NUM[le]} · {EL_DIR[le]}"})
    return rows


# ══ 3. 띠 × 달 표 ═══════════════════════════════════════════════════════════════
YEOKMA = {0: 2, 4: 2, 8: 2, 11: 5, 3: 5, 7: 5, 2: 8, 6: 8, 10: 8, 5: 11, 9: 11, 1: 11}   # 신자진→인 · 해묘미→사 · 인오술→신 · 사유축→해


def _month_of_branch(x: int) -> int:
    return 12 if x == 0 else x


def _pick(scored: list[tuple[float, int, str]], n: int = 3) -> list[tuple[int, str]]:
    """[(점수, 달, 꼬리표)] — 점수 큰 것부터 n 개 → [(달, 꼬리표)]."""
    return [(m, tag) for _, m, tag in sorted(scored, key=lambda x: (-x[0], x[1]))[:n]]


def month_table(kind: str) -> list[dict]:
    """kind: money(돈 들어오는 달·지갑 닫을 달) · body(몸 가벼운 달·쉬어 갈 달) · trip(나들이 좋은 달·먼 길 미룰 달)."""
    rows = []
    for b, a in enumerate(ANIMALS):
        good, bad = [], []
        for m in range(1, 13):
            mb = MONTH_BRANCH[m]
            cat = sipsin(BRANCH_EL[mb], b)
            rel, _ = relation(mb, b)
            if kind == "money":
                if rel == "충" or cat == "비겁":
                    bad.append((3.0 if rel == "충" else 1.0, m, "충" if rel == "충" else "나눠 쓸 돈"))
                elif rel not in ("원진", "형"):
                    sc = {"재성": 2.0, "식상": 1.0}.get(cat, 0.0) + {"육합": 1.5, "삼합": 0.5}.get(rel, 0.0)
                    if sc >= 1.0:
                        tag = "재물" if cat == "재성" else "육합" if rel == "육합" else "돈 낳음" if cat == "식상" else "삼합"
                        good.append((sc, m, tag))
            elif kind == "body":
                if rel in ("충", "형", "원진") or cat == "관성":
                    if rel not in ("육합", "삼합"):
                        sc = {"충": 2.0, "형": 1.0, "원진": 1.0}.get(rel, 0.0) + (1.5 if cat == "관성" else 0.0)
                        tag = rel if rel in ("충", "형", "원진") else "눌리는 달"
                        bad.append((sc, m, tag))
                else:
                    sc = {"인성": 2.0, "비겁": 1.0}.get(cat, 0.0) + {"육합": 1.0, "삼합": 0.5}.get(rel, 0.0)
                    if sc >= 1.0:
                        tag = "도움 달" if cat == "인성" else "힘 나는 달" if cat == "비겁" else rel
                        good.append((sc, m, tag))
            else:  # trip
                if rel in ("충", "형"):
                    bad.append((2.0 if rel == "충" else 1.0, m, rel))
                else:
                    sc = (2.0 if mb == YEOKMA[b] else 0.0) + (1.0 if cat == "식상" else 0.0)
                    if sc >= 1.0:
                        good.append((sc, m, "나들이 달" if mb == YEOKMA[b] else "활동 달"))
        g, bd = _pick(good), _pick(bad)
        rows.append({"animal": a, "branch": b, "years": years_of(a), "good": [m for m, _ in g], "good_tags": g,
                     "bad": [m for m, _ in bd], "bad_tags": bd})
    return rows


TAG_JOIN = {("도움 달", "힘 나는 달"): "도움·힘 나는 달", ("힘 나는 달", "도움 달"): "도움·힘 나는 달"}


def tags_text(tags: list[tuple[int, str]], empty: str) -> str:
    u = tuple(dict.fromkeys(tag for _, tag in tags))
    return TAG_JOIN.get(u[:2], "·".join(u)) if u else empty


MONTH_KINDS = {
    "mo_money": {"kind": "money", "cols": ("돈 들어오는 달", "지갑 닫을 달"), "empty_bad": "편한 지갑",
                 "head": "2027년 띠별 돈 들어오는 달·지갑 닫을 달 — 달마다 바뀌는 지지(월건)의 오행이 내 띠의 재물 기운인지 봤어요.",
                 "how": "달은 이렇게 봤어요: 그 달 지지(1월 축 · 2월 인 … 12월 자)의 오행을 내 띠가 다스리면(재성) 재물 기운 달, "
                        "내 띠가 낳는 오행이면(식상) 돈을 낳는 달, 육합이면 돈이 붙는 달. 충인 달과 내 띠와 같은 오행인 달"
                        "(비겁 — 나눠 쓸 돈)은 지갑을 닫는 달이에요. 원진·형인 달은 돈 달에서 뺐어요."},
    "mo_body": {"kind": "body", "cols": ("몸 가벼운 달", "쉬어 갈 달"), "empty_bad": "편한 한 해",
                "head": "2027년 띠별 몸 가벼운 달·쉬어 갈 달 — 달마다 바뀌는 지지(월건)의 오행이 내 띠를 돕는지 누르는지 봤어요.",
                "how": "달은 이렇게 봤어요: 그 달 오행이 내 띠를 살려 주면(인성) 몸이 가벼운 달, 같은 오행이면(비겁) 힘이 나는 달, "
                       "내 띠를 누르는 오행(관성)이거나 충·형·원진인 달은 쉬어 갈 달이에요. 합이 드는 달은 쉬어 갈 달에서 뺐어요."},
    "mo_trip": {"kind": "trip", "cols": ("나들이 좋은 달", "먼 길 미룰 달"), "empty_bad": "없어요",
                "head": "2027년 띠별 나들이 좋은 달·먼 길 미룰 달 — 띠마다 정해진 '길 떠나는 지지(역마)'의 달과 활동 기운의 달을 봤어요.",
                "how": "달은 이렇게 봤어요: 역마(驛馬 — 신자진 띠는 인월 · 해묘미 띠는 사월 · 인오술 띠는 신월 · 사유축 띠는 해월)가 "
                       "드는 달은 나들이 기운, 내 띠가 낳는 오행의 달(식상)은 활동 기운 달이에요. 충·형인 달은 먼 길을 다음으로."},
}


# ══ 4. 태어난 해 끝자리 ═════════════════════════════════════════════════════════
GI = 5                                 # 未 본기 = 기(己) 토 — 끝자리 재물운은 丁과 己를 함께 본다
D_MONEY = {  # 끝자리 → (좋은 기운, 한 줄, 조심할 것, 한 줄) — 1차 묶음 끝자리 편(GOD)과 겹치지 않게 돈 쪽 말로
    0: ("일한 만큼 돈", "자리가 돈 돼요", "체면 쓰는 돈", "겉치레 줄이기"),
    1: ("지키는 돈", "문서로 지켜요", "급한 결정", "서명은 하루 뒤"),
    2: ("돈 붙는 해", "재물 기운·합", "인정에 쓰는 돈", "빌려줄 땐 적게"),
    3: ("큰돈 도는 해", "재물 기운 드는 해", "충·급한 약속", "계약은 이틀 생각"),
    4: ("재물 대길", "흙이 재물 기운", "큰 씀씀이", "계획 세워 쓰기"),
    5: ("재물 대길", "먹을 복·재물 복", "작은 돈 새기", "가계부 쓰기"),
    6: ("베풀면 도는 돈", "솜씨가 돈 돼요", "빌려주는 돈", "받을 날 정하기"),
    7: ("솜씨가 돈", "먹을 복 드는 해", "나눠 쓰는 지갑", "몫은 미리 정하기"),
    8: ("문서 복", "도움 받는 해", "나갈 돈", "보증은 사양"),
    9: ("배움이 돈", "취미가 재주 돼요", "나눠 쓸 일", "씀씀이 챙기기"),
}
MONEY_GOD = {"정재": 2.0, "편재": 2.0, "식신": 1.0, "상관": 1.0, "겁재": -1.5, "비견": -0.5}
GOD_PLAIN = {"정관": "바르게 세워 주는 기운", "편관": "세게 다잡는 기운", "정재": "차곡차곡 재물 기운", "편재": "크게 도는 재물 기운",
             "상관": "재주가 밖으로 나가는 기운", "식신": "먹을 복의 기운", "겁재": "나와 같지만 음양이 다른 기운",
             "비견": "나와 똑같은 기운", "정인": "나를 살려 주는 기운", "편인": "배움으로 살려 주는 기운"}


def d_money_rows() -> list[dict]:
    rows = []
    for d in range(10):
        s = NY.digit_stem(d)
        g1, g2 = NY.ten_god(s, YP["stem"]), NY.ten_god(s, GI)
        pair = frozenset((s, YP["stem"]))
        pts = MONEY_GOD.get(g1, 0.0) + MONEY_GOD.get(g2, 0.0) + (1.0 if pair in NY.HAP else -1.0 if pair in NY.CHUNG else 0.0)
        good, gl, bad, bl = D_MONEY[d]
        why = (f"올해 천간 정(丁)은 {GOD_PLAIN[g1]}({g1}), 미(未) 속 기(己) 흙은 {GOD_PLAIN[g2]}({g2})"
               + (" · 정임 천간합 — 돈과 인연이 붙어요" if pair in NY.HAP else " · 정계 천간충 — 큰돈 약속은 천천히" if pair in NY.CHUNG else ""))
        rows.append({"digit": d, "stem": s, "gods": (g1, g2), "points": pts, "years": NY.digit_years(d),
                     "good": good, "good_line": gl, "bad": bad, "bad_line": bl, "why": why})
    return rows


GUIIN = {0: (1, 7), 4: (1, 7), 6: (1, 7), 1: (0, 8), 5: (0, 8), 2: (11, 9), 3: (11, 9), 7: (2, 6), 8: (5, 3), 9: (5, 3)}
# 천간(번호 0 갑 … 9 계) → 천을귀인 지지 두 개: 갑무경 = 축미 · 을기 = 자신 · 병정 = 해유 · 신 = 인오 · 임계 = 사묘


def d_helper_rows() -> list[dict]:
    rows = []
    for d in range(10):
        s = NY.digit_stem(d)
        gb = GUIIN[s]
        ms = sorted(_month_of_branch(x) for x in gb)
        year_g = YP["branch"] in gb
        rows.append({"digit": d, "stem": s, "guiin": gb, "years": NY.digit_years(d), "year_guiin": year_g,
                     "good": "·".join(ANIMALS[x] for x in gb) + "띠", "good_line": "그 띠 사람이 귀인",
                     "bad": months_text(ms), "bad_line": "올해가 귀인 해" if year_g else "그달 부탁 잘 돼요",
                     "why": (f"천간 {STEMS[s]}({STEMS_HJ[s]})의 귀인 지지는 {BRANCHES[gb[0]]}·{BRANCHES[gb[1]]} — "
                             f"{ANIMALS[gb[0]]}띠·{ANIMALS[gb[1]]}띠 사람, 그리고 {months_text(ms)}(그 지지의 달)에 도움이 와요"
                             + (" · 2027년이 미(未)년이라 한 해 내내 귀인 기운이 들어요" if year_g else ""))})
    return rows


def d_month_rows() -> list[dict]:
    rows = []
    for d in range(10):
        s = NY.digit_stem(d)
        hap = [m for m in range(1, 13) if frozenset((s, MONTH_STEM[m])) in NY.HAP]
        chung = [m for m in range(1, 13) if frozenset((s, MONTH_STEM[m])) in NY.CHUNG]
        insung = [m for m in range(1, 13) if GEN[STEM_EL[MONTH_STEM[m]]] == STEM_EL[s] and m not in hap]
        pyeon = [m for m in range(1, 13) if CTL[STEM_EL[MONTH_STEM[m]]] == STEM_EL[s]
                 and MONTH_STEM[m] % 2 == s % 2 and m not in chung]
        good = sorted((hap + insung)[:3])
        bad = sorted((chung + pyeon)[:3])
        hap_t = "·".join(f"{m}월 {month_pillar(m)['name']}" for m in hap)
        chung_t = "·".join(f"{m}월 {month_pillar(m)['name']}" for m in chung)
        rows.append({"digit": d, "stem": s, "years": NY.digit_years(d), "hap": hap, "chung": chung,
                     "good": months_text(good), "good_line": "합·도움 받는 달" if hap else "돕는 기운 달",
                     "bad": months_text(bad), "bad_line": "충·큰일 미루기" if chung else "다잡는 달·쉬기",
                     "good_m": good, "bad_m": bad,
                     "why": (f"천간 {STEMS[s]}({STEMS_HJ[s]}) — 좋은 달 {months_text(good)}"
                             + (f"(천간합 {hap_t} · 나를 살려 주는 천간의 달)" if hap else "(나를 살려 주는 천간의 달)")
                             + f" · 조심할 달 {months_text(bad)}"
                             + (f"(천간충 {chung_t})" if chung else "(나를 세게 다잡는 천간의 달)"))})
    return rows


# ══ 5. 출생연도 — 천간 십신 × 지지 관계 ══════════════════════════════════════════════
NAPEUM = ["해중금", "노중화", "대림목", "노방토", "검봉금", "산두화", "간하수", "성두토", "백랍금", "양류목",
          "천중수", "옥상토", "벽력화", "송백목", "장류수", "사중금", "산하화", "평지목", "벽상토", "금박금",
          "복등화", "천하수", "대역토", "차천금", "상자목", "대계수", "사중토", "천상화", "석류목", "대해수"]


def gz_of_year(y: int) -> tuple[int, int, int]:
    i = (y - 4) % 60
    return i, i % 10, i % 12


# 1차 묶음의 천간 풀이 그대로 — 단 '고집'은 어르신이 듣기 싫어하는 말이라 바꾼다(elder-friendly 10/7)
Y_GOD_SAY = {k: v.replace("고집은 내려놓기", "큰 결정은 의논해서") for k, v in NY.GOD_SAY.items()}


def year_rows(lo: int, hi: int) -> list[dict]:
    rows = []
    for y in range(lo, hi + 1):
        i, s, b = gz_of_year(y)
        god = NY.ten_god(s)
        g, gl, bd, bl = NY.GOD[god]
        rel, _ = yrel(b)
        cat = sipsin(YP["stem_el"], b)
        rows.append({"year": y, "stem": s, "branch": b, "god": god, "rel": rel, "years": [y],
                     "label": f"{y % 100:02d}년생", "sub": f"{STEMS[s]}{BRANCHES[b]} · {ANIMALS[b]}띠",
                     "good": g, "good_line": NY.LINE_REL[rel] if rel in ("육합", "삼합", "같은 띠") else NY.LINE_CAT[cat],
                     "bad": bd, "bad_line": NY.LINE_REL[rel] if rel in ("충", "원진", "형", "해", "파") else bl,
                     "why": f"{STEMS[s]}{BRANCHES[b]}({STEMS_HJ[s]}{BRANCHES_HJ[b]} · {NAPEUM[i // 2]}) — 천간: {Y_GOD_SAY[god]}"
                            f" · 띠: {NY.SAY_REL[rel] if rel else NY.SAY_CAT[cat]}"})
    return rows


# ══ 6. 태어난 달(음력 생일 달) — 조후: 계절 태생과 뜨거운 해 ══════════════════════════════
SEASON_OF = {1: "봄", 2: "봄", 3: "봄", 4: "여름", 5: "여름", 6: "여름", 7: "가을", 8: "가을", 9: "가을",
             10: "겨울", 11: "겨울", 12: "겨울"}
SEASON_WORD = {1: "이른 봄", 2: "한봄", 3: "늦봄", 4: "이른 여름", 5: "한여름", 6: "늦여름", 7: "이른 가을", 8: "한가을",
               9: "늦가을", 10: "이른 겨울", 11: "한겨울", 12: "늦겨울"}
JOHU_SAY = {
    "봄": "봄 나무 기운이 올해 불(丁)을 키워 솜씨가 밖으로 나가는 해예요. 기운이 빠지기 쉬우니 잠을 넉넉히",
    "여름": "이미 뜨거운 여름 태생에 불·흙 해가 겹쳐 사람이 모이고 바빠요. 열이 오르지 않게 쉬어 가세요",
    "가을": "가을 쇠 기운을 올해 불이 단련해 다듬어지는 해예요. 무리하지 말고 차근차근",
    "겨울": "추운 겨울 태생에 올해 불 기운이 들어 몸도 마음도 풀리는 해예요(조후 — 차고 더운 기운의 균형)",
}
# 음력 달 → (좋은 기운, 한 줄, 조심할 것, 한 줄) — 계절의 첫 달(인신사해)·한가운데(자오묘유)·끝 달(진술축미 = 환절기 흙)을 나눠 본다
JOHU = {
    1: ("새 일 트이는 해", "나무가 불을 키워요", "기운 빠짐", "잠은 넉넉히"),
    2: ("솜씨 펴는 해", "나무가 불을 키워요", "바쁜 손", "하루 한 가지씩"),
    3: ("차곡차곡 쌓는 해", "흙 기운이 겹쳐요", "욕심", "조금씩 나누기"),
    4: ("사람 모이는 해", "여름 기운이 겹쳐요", "열·과로", "더울 땐 쉬기"),
    5: ("인기·활기", "여름 기운이 겹쳐요", "열 오름", "물 자주 마시기"),
    6: ("기운 넘치는 해", "흙 기운이 겹쳐요", "고단함", "낮잠 한숨"),
    7: ("다듬어지는 해", "불이 쇠를 단련해요", "무리", "쉬어 가며 하기"),
    8: ("빛나는 솜씨", "불이 쇠를 다듬어요", "날 선 말", "부드럽게 말하기"),
    9: ("결실 거두는 해", "흙 기운이 겹쳐요", "서두름", "한 박자 쉬기"),
    10: ("따뜻해지는 해", "언 땅에 불 기운", "들뜬 마음", "천천히 정하기"),
    11: ("몸 풀리는 해", "언 땅에 불 기운", "서운한 말", "말 아끼기"),
    12: ("얼음 녹는 해", "언 땅에 불 기운", "큰일", "천천히 가기"),
}
B_GOOD_REL = {"육합": "육합·짝이 맞는 해", "삼합": "삼합·한 팀인 해", "같은 띠": "같은 기운의 해"}
B_BAD_REL = {"충": "충·천천히 가기", "원진": "원진·말 아끼기", "형": "형·한 박자 쉬기", "해": "해·다시 확인하기",
             "파": "파·다시 확인하기"}


def birth_month_rows() -> list[dict]:
    rows = []
    for m in range(1, 13):
        mb = (m + 1) % 12                                    # 음력 정월 = 인월(옛 풀이)
        g, gl, bd, bl = JOHU[m]
        rel, _ = yrel(mb)
        gl = B_GOOD_REL.get(rel, gl)
        bl = B_BAD_REL.get(rel, bl)
        rows.append({"month": m, "branch": mb, "label": f"{m}월생", "sub": SEASON_WORD[m], "years": [],
                     "good": g, "good_line": gl, "bad": bd, "bad_line": bl,
                     "why": f"음력 {m}월생({BRANCHES[mb]}월 · {SEASON_WORD[m]}) — {JOHU_SAY[SEASON_OF[m]]}"
                            + (f" · {NY.SAY_REL[rel]}" if rel else "")})
    return rows


# ══ 7. 2027 절기 달력 ═════════════════════════════════════════════════════════════
EL_DO = {"목": "새로 시작하기", "화": "사람 만나기", "토": "정리·저축", "금": "마무리하기", "수": "쉬며 계획하기"}
YUKHAP_OF = {a: b for p in ((0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)) for a, b in (p, p[::-1])}


def el_pair(a: str, b: str) -> str:
    return f"{EL_WORD[a]} 기운 두 겹" if a == b else f"{EL_WORD[a]}·{EL_WORD[b]} 기운"


def solar_rows() -> list[dict]:
    rows = []
    for m in range(1, 13):
        p = month_pillar(m)
        day, name = JEOLGI[m]
        mate = YUKHAP_OF[p["branch"]]
        rows.append({"month": m, "label": f"{m}월 {day}일", "sub": f"{name} · {p['name']}월", "years": [],
                     "good": EL_DO[p["branch_el"]], "good_line": el_pair(p["stem_el"], p["branch_el"]),
                     "bad": f"{ANIMALS[mate]}띠", "bad_line": "이달 육합 짝",
                     "why": f"{m}월 {day}일 {name} — {p['name']}월({p['hanja']}月) 시작 · {el_pair(p['stem_el'], p['branch_el'])}"
                            f" — {EL_DO[p['branch_el']]} 좋은 달 · 이달 지지 {BRANCHES[p['branch']]}와 육합인 띠: {ANIMALS[mate]}띠"
                            + (" · ★입춘부터 정미년" if m == 2 else " · 아직 병오년의 끝 달(입춘 전)" if m == 1 else "")})
    return rows


# ══ 편 목록(방송 순서) ══════════════════════════════════════════════════════════════
def _ep(eid, family, scene, card, yt, foot, hook, **kw):
    return dict(id=eid, family=family, scene=scene, card=card, yt=yt, foot=foot, hook=LAMB + hook, **kw)


P12 = "2027 정미년 · 12띠 · 45~96년생"
PD = "2027 정미년 · 끝자리 0~9 · 45~96년생"
EPISODES = [
    _ep("d_money", "digit", "gunghap", "끝자리 2027 재물운",
        "태어난 해 끝자리로 보는 2027 정미년 재물운 | 0~9 전부 · 45~96년생",
        "끝자리 = 태어난 해 천간 · 올해 두 기운으로 본 재물 — 재미로 보세요",
        "beside a small wooden abacus and a brass bowl on a low table in a hanok room with plain paper walls, "
        "warm afternoon light, no people",
        cols=("2027 재물 기운", "조심할 돈"), head="태어난 해 끝자리", pill=PD),
    _ep("t_kids", "tier", "tier", "2027 자식·손주 덕",
        "2027 정미년 띠별 자식·손주 덕 등급표 | 자식 덕 대길은 어느 띠? · 45~96년생 전부",
        "대길 = 자식 기운 + 합 — 2027 정미년 풀이, 재미로 보세요",
        "with two small lambs playing on a sunny hanok wooden porch, soft warm light, gentle family mood, no people",
        pill=P12),
    _ep("y_46", "year", "gunghap", "46~57년생 2027 운세",
        "2027 정미년 출생연도별 운세 | 46~57년생 전부 · 내 해를 찾아보세요",
        "천간 = 해 끝자리 · 띠 = 양띠해와의 관계 — 재미로 보세요",
        "sitting beside a celadon vase with pine branches in a hanok room with plain paper walls, calm morning "
        "light, no people",
        cols=("2027 좋은 기운", "조심할 것"), head="출생연도", pill="2027 정미년 · 46~57년생", years=(1946, 1957)),
    _ep("mo_money", "month", "gunghap", "2027 돈 들어오는 달",
        "2027 정미년 띠별 돈 들어오는 달·지갑 닫을 달 | 12띠 전부 · 45~96년생",
        birth_basis.SCREEN_CAL_MONTH + " — 재미로 보세요",
        "next to a woven basket of persimmons and chestnuts on a hanok wooden floor, golden autumn light, no people",
        pill=P12),
    _ep("t_docs", "tier", "tier", "2027 문서·집 운",
        "2027 정미년 띠별 문서·집 운 등급표 | 도장 복 대길은? · 45~96년생 전부",
        "대길 = 문서 기운 + 합 — 2027 정미년 풀이, 재미로 보세요",
        "in front of a traditional Korean wooden house gate with a small stone path, clear blue sky, calm mood, "
        "no people",
        pill=P12),
    _ep("d_helper", "digit", "gunghap", "끝자리 2027 귀인운",
        "태어난 해 끝자리로 보는 2027 정미년 귀인운 | 내 귀인 띠·귀인 오는 달 · 0~9 전부",
        "끝자리 = 태어난 해 천간 · 천간마다 정해진 귀인 — 재미로 보세요",
        "walking beside a gentle white crane in a hanok courtyard with a golden ginkgo tree, warm light, no people",
        cols=("내 귀인 띠", "귀인 오는 달"), head="태어난 해 끝자리", pill=PD),
    _ep("r_health", "ddi", "gunghap", "2027 건강 챙길 곳",
        "2027 정미년 띠별 건강운 | 내 띠가 챙길 곳·좋은 습관 · 45~96년생 전부",
        "오행으로 본 생활 습관 — 불편하면 꼭 병원에 가 보세요",
        "on a quiet pine forest walking path at dawn with soft mist, fresh calm mood, no people",
        cols=("챙길 곳", "좋은 습관"), pill=P12),
    _ep("y_58", "year", "gunghap", "58~69년생 2027 운세",
        "2027 정미년 출생연도별 운세 | 58~69년생 전부 · 내 해를 찾아보세요",
        "천간 = 해 끝자리 · 띠 = 양띠해와의 관계 — 재미로 보세요",
        "sitting on a cushion beside a low table with a teapot and two cups in a hanok room with plain paper "
        "walls, soft light, no people",
        cols=("2027 좋은 기운", "조심할 것"), head="출생연도", pill="2027 정미년 · 58~69년생", years=(1958, 1969)),
    _ep("t_work", "tier", "tier", "2027 일복·명예운",
        "2027 정미년 띠별 일복·명예운 등급표 | 감투 쓰는 대길 띠는? · 45~96년생 전부",
        "대길 = 일 기운 + 돕는 기운 — 2027 정미년 풀이, 재미로 보세요",
        "beside a neat wooden shelf with folded silk cloth and a small brass bell in a hanok room with plain "
        "paper walls, morning light, no people",
        pill=P12),
    _ep("b_month", "bmonth", "gunghap", "태어난 달 2027 운세",
        "태어난 달로 보는 2027 정미년 운세 | 음력 1월생~12월생 전부",
        "음력 정월 = 인월로 본 옛 풀이 — 재미로 보세요",
        "in a hanok garden where spring blossoms, green summer leaves, red autumn maple and white winter snow "
        "meet in four corners, soft dreamy light, no people",
        cols=("2027 좋은 기운", "조심할 것"), head="음력 생일 달", pill="2027 정미년 · 음력 1~12월생"),
    _ep("months", "month", "gunghap", NY.episode_by_id("months")["card"], NY.episode_by_id("months")["yt"],
        NY.episode_by_id("months")["foot"], NY.episode_by_id("months")["hook"][len(LAMB):], probe=True, pill=P12),
    _ep("r_lucky", "ddi", "gunghap", "2027 행운의 색·숫자",
        "2027 정미년 띠별 행운의 색·숫자·방향 | 12띠 전부 · 45~96년생",
        "올해 불·흙 기운을 고르게 하는 오행 — 재미로 보세요",
        "with colorful silk pouches in white, navy, yellow and green arranged on a wooden tray in a hanok room "
        "with plain paper walls, warm light, no people",
        cols=("행운의 색", "숫자 · 방향"), pill=P12),
    _ep("d_months", "digit", "gunghap", "끝자리 2027 좋은 달",
        "태어난 해 끝자리로 보는 2027 정미년 좋은 달·조심할 달 | 0~9 전부 · 45~96년생",
        birth_basis.SCREEN_CAL_MONTH + " — 재미로 보세요",
        "looking at a quiet lotus pond beside a small hanok pavilion, soft seasonal light, peaceful mood, no people",
        cols=("좋은 달", "조심할 달"), head="태어난 해 끝자리", pill=PD),
    _ep("t_friends", "tier", "tier", "2027 친구·모임 운",
        "2027 정미년 띠별 친구·모임 운 등급표 | 사람 복 대길은? · 45~96년생 전부",
        "대길 = 같은 기운 + 합 — 2027 정미년 풀이, 재미로 보세요",
        "with a small group of fluffy lambs sharing persimmons on a hanok porch, cheerful warm light, no people",
        pill=P12),
    _ep("y_70", "year", "gunghap", "70~81년생 2027 운세",
        "2027 정미년 출생연도별 운세 | 70~81년생 전부 · 내 해를 찾아보세요",
        "천간 = 해 끝자리 · 띠 = 양띠해와의 관계 — 재미로 보세요",
        "next to a low table with a plate of rice cakes and green tea in a hanok room with plain paper walls, "
        "calm afternoon light, no people",
        cols=("2027 좋은 기운", "조심할 것"), head="출생연도", pill="2027 정미년 · 70~81년생", years=(1970, 1981)),
    _ep("mo_body", "month", "gunghap", "2027 몸 가벼운 달",
        "2027 정미년 띠별 몸 가벼운 달·쉬어 갈 달 | 12띠 전부 · 45~96년생",
        birth_basis.SCREEN_CAL_MONTH + " — 재미로 보세요",
        "stretching gently on a soft mat in a sunny hanok room with plain paper walls and a potted plant, "
        "fresh light, no people",
        pill=P12),
    _ep("h_solar", "solar", "gunghap", "2027 절기 달력",
        "2027 정미년 절기 달력 | 달이 바뀌는 날·이달 할 일 · 1월~12월",
        "날짜는 태양 위치로 계산 — 그날 낮이나 밤에 바뀌어요",
        "on a hanok rooftop terrace watching a gentle sunrise over far mountains, soft golden sky, no people",
        cols=("이달 할 일", "이달 짝꿍 띠"), head="달이 바뀌는 날", pill="2027 정미년 · 1월~12월"),
    _ep("m_jan", "tier", "tier", "2027년 1월 운세",
        "2027년 1월 띠별 운세 등급표 | 정미년 입춘 전 신축월 · 45~96년생 전부",
        "1월은 아직 병오년 끝 달 — 입춘(2월 4일)부터 정미년",
        "in a warm hanok room with a small iron kettle on a brazier, snowy courtyard beyond the paper doors, "
        "cozy light, no people",
        month=1, pill=f"2027년 1월 · 신축월 · {month_span(1)}"),
    _ep("y_82", "year", "gunghap", "82~93년생 2027 운세",
        "2027 정미년 출생연도별 운세 | 82~93년생 전부 · 내 해를 찾아보세요",
        "천간 = 해 끝자리 · 띠 = 양띠해와의 관계 — 재미로 보세요",
        "next to a bicycle with a basket of apples in front of a stone hanok wall, bright morning, no people",
        cols=("2027 좋은 기운", "조심할 것"), head="출생연도", pill="2027 정미년 · 82~93년생", years=(1982, 1993)),
    _ep("m_feb", "tier", "tier", "2027년 2월 운세",
        "2027 정미년 2월 띠별 운세 등급표 | 입춘으로 여는 첫 달 · 45~96년생 전부",
        "2월 4일 입춘부터 정미년 — 재미로 보세요",
        "in a hanok courtyard where the first plum blossoms open on a cold clear morning, no people",
        month=2, pill=f"2027년 2월 · 임인월 · {month_span(2)}"),
    _ep("mo_trip", "month", "gunghap", "2027 나들이 좋은 달",
        "2027 정미년 띠별 나들이 좋은 달·먼 길 미룰 달 | 12띠 전부 · 45~96년생",
        birth_basis.SCREEN_CAL_MONTH + " — 재미로 보세요",
        "walking on a country road lined with cosmos flowers toward far blue mountains, light breeze, no people",
        pill=P12),
    _ep("m_mar", "tier", "tier", "2027년 3월 운세",
        "2027 정미년 3월 띠별 운세 등급표 | 경칩부터 계묘월 · 45~96년생 전부",
        "3월 6일 경칩부터 계묘월 — 재미로 보세요",
        "in a hanok garden with fresh green sprouts beside a small clear stream, soft spring light, no people",
        month=3, pill=f"2027년 3월 · 계묘월 · {month_span(3)}"),
]
BY_ID = {e["id"]: e for e in EPISODES}


def episode_by_id(eid: str) -> dict:
    return BY_ID[eid]


# ── 편성 ─────────────────────────────────────────────────────────────────────
def post_days(d: dt.date) -> tuple[int, ...]:
    days = ()
    for start, wds in CADENCE:
        if d >= start:
            days = wds
    return days


def is_slot_day(d: dt.date) -> bool:
    """06:13 을 시리즈가 쓰는 요일인가(목록이 남았는지는 보지 않는다)."""
    return SERIES_FROM is not None and d >= SERIES_FROM and d.weekday() in post_days(d) and d.day != 1


def series_index(d: dt.date) -> int:
    return sum(1 for k in range((d - SERIES_FROM).days) if is_slot_day(SERIES_FROM + dt.timedelta(days=k)))


def episode_for(d: dt.date) -> dict | None:
    """그날 06:13 에 나갈 시리즈 편 — 시리즈 날이 아니거나 목록이 바닥났으면 None(매일 운세 그대로)."""
    if not is_slot_day(d):
        return None
    i = series_index(d)
    return EPISODES[i] if i < len(EPISODES) else None


def schedule(until: dt.date) -> list[tuple[dt.date, str]]:
    out, d = [], SERIES_FROM
    while SERIES_FROM is not None and d <= until:
        ep = episode_for(d)
        if ep:
            out.append((d, ep["id"]))
        d += dt.timedelta(days=1)
    return out


def last_day() -> dt.date | None:
    s = schedule(SERIES_FROM + dt.timedelta(days=400)) if SERIES_FROM else []
    return s[-1][0] if s else None


def use_slot(sb: dict) -> bool:
    """06:13 '오늘 운세' 대본(토픽 fortune)을 오늘 시리즈 편으로 바꿀 날인가. 다른 운세 토픽·주간·월간은 건드리지 않는다."""
    if str(sb.get("topic") or "").strip().lower() != TOPIC:
        return False
    if scope_of(sb) != "오늘":
        return False
    d = sb_date(sb)
    return bool(d and episode_for(d))


# ── 화면·말·설명 ────────────────────────────────────────────────────────────────
def tier_list(ep: dict) -> list[dict]:
    if ep.get("month"):
        items, basis = month_items(ep["month"]), M_BASIS
    else:
        items, basis = theme_items(ep["id"]), TIER_THEMES[ep["id"]]["BASIS"]
    return [dict(t, basis=basis[t["id"]], items=[r for r in items if r["tier"] == t["id"]]) for t in TIERS]


def rows_for(ep: dict) -> list[dict]:
    eid = ep["id"]
    if eid == "d_money":
        return [dict(r, label=f"끝자리 {r['digit']}") for r in d_money_rows()]
    if eid == "d_helper":
        return [dict(r, label=f"끝자리 {r['digit']}") for r in d_helper_rows()]
    if eid == "d_months":
        return [dict(r, label=f"끝자리 {r['digit']}") for r in d_month_rows()]
    if eid == "r_health":
        return health_rows()
    if eid == "r_lucky":
        return lucky_rows()
    if eid == "b_month":
        return birth_month_rows()
    if eid == "h_solar":
        return solar_rows()
    if ep["family"] == "year":
        return year_rows(*ep["years"])
    if eid in MONTH_KINDS:
        mk = MONTH_KINDS[eid]
        out = []
        for r in month_table(mk["kind"]):
            out.append(dict(r, good=months_text(r["good"]), good_line=tags_text(r["good_tags"], "꾸준한 한 해"),
                            bad=months_text(r["bad"]), bad_line=tags_text(r["bad_tags"], mk["empty_bad"]),
                            good_m=r["good"], bad_m=r["bad"]))
        return out
    raise KeyError(eid)


DIGIT_READ = "영일이삼사오육칠팔구"


def digits_josa(ds: list[int], a: str = "은", b: str = "는") -> str:
    """'2, 4, 5는' · '0, 4, 8은' — 마지막 숫자 읽는 소리로 조사."""
    return ", ".join(map(str, ds)) + (a if (ord(DIGIT_READ[ds[-1]]) - 0xAC00) % 28 else b)


def _names(items: list[dict]) -> str:
    return ", ".join(r["animal"] for r in items)


def narration(ep: dict) -> str:
    """9~11초(80자 안) — 우리말 등급(대길) · 조심 칸은 조언으로(어르신 눈높이 10/7)."""
    eid = ep["id"]
    if ep.get("probe"):
        return NY.narration(NY.episode_by_id(eid))
    if ep["scene"] == "tier":
        tl = tier_list(ep)
        s, c = _names(tl[0]["items"]), _names(tl[3]["items"])
        if ep.get("month"):
            m = ep["month"]
            say = f"2027년 {m}월 띠별 운세예요. {m}월 대길은 {s}띠. "
            return say + (f"{c}띠는 큰일은 다음 달로 미루세요. " if c else "") + "내 띠도 찾아보세요."
        th = TIER_THEMES[eid]
        say = f"2027년 정미년 {th['SAY_N']}예요. 대길은 {s}띠. "
        return say + (f"{c}띠는 {th['C_ADVICE']}. " if c else "") + "내 띠도 찾아보세요."
    rows = rows_for(ep)
    if eid == "d_money":
        top = sorted(r["digit"] for r in rows if r["points"] >= 3)
        return f"태어난 해 끝자리로 보는 2027년 재물운이에요. 끝자리 {digits_josa(top)} 재물이 붙는 해예요. 내 끝자리도 찾아보세요."
    if eid == "d_helper":
        yg = [r["digit"] for r in rows if r["year_guiin"]]
        return f"태어난 해 끝자리로 보는 2027년 귀인이에요. 끝자리 {digits_josa(yg)} 올해가 귀인 드는 해예요. 내 끝자리도 찾아보세요."
    if eid == "d_months":
        r2 = next(r for r in rows if r["digit"] == 2)
        return (f"태어난 해 끝자리로 보는 2027년 좋은 달이에요. 끝자리 2는 {r2['good'].replace('·', ', ')}이 좋아요. "
                "내 끝자리도 찾아보세요.")
    if eid == "r_health":
        return ("2027년 정미년 띠별 건강운이에요. 소, 용, 양, 개띠는 소화를, 원숭이, 닭띠는 목을 따뜻하게 챙기세요. "
                "내 띠도 찾아보세요.")
    if eid == "r_lucky":
        by = {r["animal"]: r for r in rows}
        return (f"2027년 정미년 띠별 행운의 색이에요. 쥐띠와 돼지띠는 {by['쥐']['good'].split('·')[0]}, "
                f"소띠와 용띠는 {by['소']['good'].split('·')[0]}이 좋아요. 내 띠도 찾아보세요.")
    if eid == "b_month":
        return "태어난 달로 보는 2027년 운세예요. 겨울에 태어난 분은 따뜻해지는 해, 여름생은 쉬어 가며 가세요. 내 달도 찾아보세요."
    if eid == "h_solar":
        return "2027년 절기 달력이에요. 2월 4일 입춘부터 정미년, 달이 바뀌는 날과 그달 할 일을 담았어요. 저장해 두세요."
    if ep["family"] == "year":
        lo, hi = ep["years"]
        r2 = next(r for r in rows if r["year"] % 10 == 2)
        rh = next(r for r in rows if r["rel"] == "육합")
        return (f"{lo % 100}년생부터 {hi % 100}년생까지 2027년 운세예요. {r2['year'] % 100:02d}년생은 돈과 인연이 붙는 해, "
                f"{rh['year'] % 100:02d}년생은 손발이 맞는 해예요. 내 해도 찾아보세요.")
    if eid in MONTH_KINDS:
        by = {r["animal"]: r for r in rows}
        word = {"mo_money": "돈 들어오는 달", "mo_body": "몸 가벼운 달", "mo_trip": "나들이 좋은 달"}[eid]
        tail = {"mo_money": "돈 기운이 들어와요", "mo_body": "몸이 가벼워요", "mo_trip": "나들이하기 좋아요"}[eid]
        return (f"2027년 띠별 {word}이에요. 쥐띠는 {by['쥐']['good_m'][0]}월, 말띠는 {by['말']['good_m'][0]}월에 {tail}. "
                "내 띠도 찾아보세요.")
    raise KeyError(eid)


def basis_line(ep: dict) -> str:
    if ep["family"] == "digit":
        return birth_basis.SCREEN_YEAR
    if ep["family"] == "bmonth":
        return birth_basis.SCREEN_MONTH
    if ep["family"] == "solar":
        return birth_basis.SCREEN_CAL_MONTH
    return birth_basis.SCREEN_DDI


def scene_for(ep: dict) -> dict:
    if ep.get("probe"):
        return NY.scene_for(NY.episode_by_id(ep["id"]))
    base = {"type": ep["scene"], "pill": ep["pill"], "title": ep["card"], "foot": ep["foot"], "brand": BRAND,
            "basis": basis_line(ep), "narration": narration(ep)}
    if ep["scene"] == "tier":
        base["none"] = "이달은 없어요" if ep.get("month") else "올해는 없어요"
        base["tiers"] = [{"id": t["id"], "label": t["label"], "big": t["label"], "small": t["stars"], "color": t["color"],
                          "items": [{k: r[k] for k in ("animal", "years", "line")} for r in t["items"]]}
                         for t in tier_list(ep)]
        return base
    base["cols"] = list(ep.get("cols") or MONTH_KINDS[ep["id"]]["cols"])
    if ep.get("head"):
        base["head"] = ep["head"]
    keys = ("label", "animal", "sub", "years", "good", "good_line", "bad", "bad_line")
    base["rows"] = [{k: r[k] for k in keys if k in r and (k != "animal" or "label" not in r)} for r in rows_for(ep)]
    return base


def _note(ep: dict) -> str:
    fam = ep["family"]
    if fam == "digit":
        return birth_basis.year_note() + ("\n" + birth_basis.cal_month_note() if ep["id"] == "d_months" else "")
    if fam == "bmonth":
        return birth_basis.month_note() + "\n· 음력 달은 옛 풀이대로 정월 = 인월(寅月)로 봤어요. 절기와는 보름쯤 어긋날 수 있어요."
    if fam == "solar":
        return birth_basis.cal_month_note()
    if fam == "month":
        return birth_basis.ddi_note() + "\n" + birth_basis.cal_month_note()
    return birth_basis.ddi_note()


HEAD = {
    "t_kids": "2027년 정미년(丁未年) 띠별 자식·손주 덕 등급표 — 올해의 두 기운(정 = 불 · 미 = 흙)이 내 띠에게 자식 기운인지 봤어요.",
    "t_docs": "2027년 정미년(丁未年) 띠별 문서·집 운 등급표 — 집·땅 문서, 도장 찍을 일이 잘 풀리는지 올해의 두 기운으로 봤어요.",
    "t_work": "2027년 정미년(丁未年) 띠별 일복·명예운 등급표 — 맡을 일·감투·자리가 들어오는지 올해의 두 기운으로 봤어요.",
    "t_friends": "2027년 정미년(丁未年) 띠별 친구·모임 운 등급표 — 친구·형제·모임에서 사람 복이 드는지 올해의 두 기운으로 봤어요.",
    "d_money": "태어난 해 끝자리로 보는 2027년 재물운 — 끝자리는 태어난 해의 천간이에요. 올해 천간 정(丁)과 지지 미(未) 속 기(己)를 함께 봤어요.",
    "d_helper": "태어난 해 끝자리로 보는 2027년 귀인운 — 천간마다 정해진 귀인(천을귀인 天乙貴人)의 띠와 그 귀인이 오는 달이에요.",
    "d_months": "태어난 해 끝자리로 보는 2027년 좋은 달·조심할 달 — 달마다 바뀌는 그 달의 천간과 내 천간이 합인지 충인지 봤어요.",
    "r_health": "2027년 정미년 띠별 건강운 — 내 띠의 오행과 올해(불·흙)의 관계로 챙길 곳과 좋은 습관을 정리했어요.",
    "r_lucky": "2027년 정미년 띠별 행운의 색·숫자·방향 — 불·흙 기운이 강한 해에 내 띠의 기운을 고르게 해 주는 오행이에요.",
    "b_month": "태어난 달로 보는 2027년 정미년 운세 — 태어난 계절의 차고 더운 기운(조후)과 뜨거운 정미년이 만나면 어떤지 봤어요.",
    "h_solar": "2027년 정미년 절기 달력 — 운세에서 달이 바뀌는 날(절기)과 그 달의 월주, 그달에 하면 좋은 일이에요.",
    "m_jan": "2027년 1월 띠별 운세 등급표 — 1월(소한~입춘 전)은 아직 병오년의 끝 달, 신축월(辛丑月)이에요.",
    "m_feb": "2027년 2월 띠별 운세 등급표 — 2월 4일 입춘부터 정미년, 첫 달은 임인월(壬寅月)이에요.",
    "m_mar": "2027년 3월 띠별 운세 등급표 — 3월 6일 경칩부터 계묘월(癸卯月)이에요.",
}


def description(ep: dict) -> str:
    eid = ep["id"]
    if ep.get("probe"):
        return NY.description(NY.episode_by_id(eid))
    if eid in MONTH_KINDS:
        head = MONTH_KINDS[eid]["head"]
    elif ep["family"] == "year":
        lo, hi = ep["years"]
        head = (f"2027년 정미년 출생연도별 운세 {lo % 100}~{hi % 100}년생 — 태어난 해의 천간(끝자리)에게 올해 천간 정(丁)이 무엇인지와, "
                "내 띠와 양띠해(未)의 관계를 함께 봤어요. 같은 띠라도 해마다 달라요.")
    else:
        head = HEAD[eid]
    lines = [head, "", _note(ep), ""]
    if ep["scene"] == "tier":
        for t in tier_list(ep):
            lines.append(f"[{t['label']} {t['stars']}] {t['basis']}")
            lines += [f"· {r['animal']}띠({yrs_text(r['years'])}) — {r['why']}." for r in t["items"]] or ["· 없어요."]
            lines.append("")
        if ep.get("month"):
            p = month_pillar(ep["month"])
            lines.append(f"등급은 이렇게 정했어요: {ep['month']}월({month_span(ep['month'])})의 월주 {p['name']}({p['hanja']}) — "
                         f"지지 {BRANCHES[p['branch']]}({p['animal']})와 내 띠가 육합·삼합이면 대길, 충·원진·형이면 조심, "
                         f"그 사이는 천간 {STEMS[p['stem']]}({EL_WORD[p['stem_el']]})과 내 띠 오행의 관계로 길·보통을 나눴어요.")
        else:
            lines.append("등급은 이렇게 정했어요: " + TIER_THEMES[eid]["HOW"]
                         + " 양띠해(未)와 합이면 더하고 충·원진·형이면 뺐어요.")
        lines.append("조심 칸이어도 걱정 마세요 — 서두르지 않으면 되는 해예요. 내 띠는 어디에 있나요? 댓글로 남겨 주세요 🙏")
    else:
        rows = rows_for(ep)
        cols = scene_for(ep)["cols"]
        for r in rows:
            if eid in MONTH_KINDS:
                g = " · ".join(f"{m}월({t})" for m, t in sorted(r["good_tags"])) or "꾸준한 한 해"
                b = " · ".join(f"{m}월({t})" for m, t in sorted(r["bad_tags"])) or MONTH_KINDS[eid]["empty_bad"]
                lines.append(f"· {r['animal']}띠({yrs_text(r['years'])}) — {cols[0]}: {g} / {cols[1]}: {b}")
            elif ep["family"] == "digit":
                lines.append(f"· 끝자리 {r['digit']}({STEMS[r['stem']]} {STEMS_HJ[r['stem']]} · {yrs_text(r['years'])}) — "
                             f"{cols[0]}: {r['good']} · {cols[1]}: {r['bad']} — {r['why']}.")
            elif ep["family"] == "year":
                lines.append(f"· {r['year']}년생 — {r['why']}. 좋은 기운: {r['good']} · 조심할 것: {r['bad']}.")
            elif ep["family"] in ("bmonth", "solar"):
                lines.append(f"· {r['why']}.")
            else:
                lines.append(f"· {r['animal']}띠({yrs_text(r['years'])}) — {r['why']}.")
        how = {
            "d_money": "끝자리는 이렇게 봤어요: 끝자리 = 태어난 해 천간(0 경 · 1 신 · 2 임 · 3 계 · 4 갑 · 5 을 · 6 병 · 7 정 · 8 무 · 9 기). "
                       "올해 천간 정(丁)과 지지 미(未)의 본기 기(己)가 내 천간에게 재물 기운(정재·편재)이면 크게, 재물을 낳는 기운(식신·상관)이면 "
                       "조금 더하고, 나와 같은 기운(비견·겁재)은 나갈 돈으로 봤어요. 정임 천간합은 더하고 정계 천간충은 뺐어요.",
            "d_helper": "귀인은 이렇게 봤어요: 갑·무·경 = 축·미 · 을·기 = 자·신 · 병·정 = 해·유 · 신 = 인·오 · 임·계 = 사·묘. "
                        "그 지지의 띠 사람이 나를 돕고, 그 지지의 달(1월 축 … 12월 자)에 부탁이 잘 풀려요.",
            "d_months": "달은 이렇게 봤어요: 2027년 달마다 천간이 바뀌어요(1월 신 · 2월 임 · 3월 계 · 4월 갑 · 5월 을 · 6월 병 · 7월 정 · "
                        "8월 무 · 9월 기 · 10월 경 · 11월 신 · 12월 임). 내 천간과 합(갑기·을경·병신·정임·무계)이 되는 달과 나를 살려 주는 "
                        "천간의 달은 좋은 달, 충(갑경·을신·병임·정계)이 되는 달과 나를 세게 다잡는 천간의 달은 조심할 달이에요.",
            "r_health": "건강은 이렇게 봤어요: 오행마다 맡은 몸(나무 = 간·눈·힘줄 · 불 = 심장·피 흐름 · 흙 = 위장·소화 · "
                        "쇠 = 폐·목·기관지 · 물 = 콩팥·허리)에 올해 불·흙 기운이 겹치는지·누르는지·빠지게 하는지 보고, 둘째 줄은 "
                        "양띠해(未)와의 합·충이에요.\n※ 전통 오행으로 본 생활 습관 이야기예요. 몸이 불편하시면 꼭 병원에서 확인하세요.",
            "r_lucky": "행운은 이렇게 봤어요: 불·흙이 강한 해에 내 띠 오행이 막히거나(통관) 뜨거워지는(조후) 데를 고르게 해 주는 "
                       "오행을 골랐어요. 오행의 색·숫자·방향: 나무 = 초록·3·8·동쪽 · 불 = 빨강·2·7·남쪽 · 흙 = 노랑·5·10·가운데 · 쇠 = 흰색·4·9·서쪽 · "
                       "물 = 검정·1·6·북쪽(하도의 수).",
            "b_month": "태어난 달은 이렇게 봤어요: 봄(1~3월)·여름(4~6월)·가을(7~9월)·겨울(10~12월) 태생의 차고 더운 기운에 "
                       "불·흙이 강한 2027년이 들어오면 어떤지(조후), 그리고 그 달 지지와 양띠해(未)의 합·충이에요.",
            "h_solar": "날짜는 이렇게 봤어요: 태양이 그 절기 자리(황경 285°·315° …)에 오는 날을 한국 시각으로 계산했어요. 그날 낮이나 밤에 바뀌어요.",
        }.get(eid) or (MONTH_KINDS[eid]["how"] if eid in MONTH_KINDS else
                       "출생연도는 이렇게 봤어요: 태어난 해 천간에게 올해 천간 정(丁)이 무엇인지(십신 — 정관·편관·정재·편재·상관·식신·겁재·"
                       "비견·정인·편인)와 정임 천간합·정계 천간충, 그리고 내 띠와 양띠해(未)의 육합·삼합·충·원진·형이에요. "
                       "괄호 안은 그 해의 납음(納音)이에요.")
        lines += ["", how, "내 것은 어디에 있나요? 댓글로 남겨 주세요 🙏"]
    lines += ["", "※ 전통 명리의 신년운세 풀이를 재미로 정리한 운세입니다.", "",
              "#2027운세 #정미년 #신년운세 #띠별운세 #운세 #shorts"]
    return "\n".join(lines)


def title(ep: dict) -> str:
    return ep["yt"]


def storyboard(d: dt.date, ep: dict | None = None) -> dict:
    """견본·확인용 스토리보드 — 06:13 루틴 대본과 같은 꼴(토픽 fortune · MODE=daily)이라 run_pipeline 이 같은 길로 처리한다."""
    ep = ep or episode_for(d) or EPISODES[0]
    t = title(ep)
    return {
        "date": d.isoformat(), "topic": TOPIC, "series": ep["id"], "privacy": "public",
        "accent": ACCENT, "_min_total": 9.0,
        "hook_title": ep["card"], "headline": t, "thumbnail_hook": ep["hook"] + HOOK_TAIL, "thumbnail_text": ep["card"],
        "scenes": [scene_for(ep)],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(ep)}},
        "notes": f"2027 신년운세 시리즈 · episode={ep['id']} · newyear_series.py · MODE=daily",
    }


def apply(sb: dict) -> dict:
    """시리즈 날 — 루틴 대본의 배경 묘사·커버 글자를 이 편 것으로(메모리 안에서만, 파일·ledger 키는 그대로)."""
    ep = episode_for(sb_date(sb))
    sb["series"] = ep["id"]
    sb["thumbnail_hook"] = ep["hook"] + HOOK_TAIL
    sb["hook_title"] = sb["thumbnail_text"] = ep["card"]
    sb["headline"] = title(ep)
    sb.pop("thumbnail_style", None)
    return ep


def build_spec(sb: dict) -> dict:
    d = sb_date(sb)
    t = storyboard(d, episode_for(d))
    return {"topic": t["topic"], "date": t["date"], "accent": t["accent"], "_min_total": t["_min_total"], "scenes": t["scenes"]}


def meta(sb: dict) -> dict:
    ep = BY_ID.get(sb.get("series") or "") or episode_for(sb_date(sb))
    return {"title": title(ep)[:95], "description": description(ep)}


def main() -> int:
    ap = argparse.ArgumentParser(description="2027 신년운세 시리즈(06:13)")
    ap.add_argument("cmd", choices=["plan", "show", "sample"])
    ap.add_argument("--date")
    ap.add_argument("--until", default="2027-01-10")
    ap.add_argument("--episode", choices=list(BY_ID))
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "plan":
        until = dt.date.fromisoformat(a.until)
        d = SERIES_FROM
        while d and d <= until:
            ep = episode_for(d)
            if ep:
                what = f"2027 시리즈 {series_index(d) + 1:>2}편 {ep['id']:<9} {ep['card']}"
            elif d.weekday() == 0:
                what = "이번 주 운세(월)"
            elif is_slot_day(d):
                what = "매일 운세 표 — 시리즈 목록이 바닥났다(새 편을 채울 것)"
            elif d.weekday() in post_days(d):
                what = "매일 운세 표 — 1일은 건너뜀(이번 달 운세 자리)"
            else:
                what = "매일 운세 표"
            print(f"{d} ({WD[d.weekday()]}) 06:13  {what}")
            d += dt.timedelta(days=1)
        print(f"마지막 시리즈 편: {last_day()}  ({len(EPISODES)}편)")
        return 0
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    ep = BY_ID[a.episode] if a.episode else episode_for(d)
    if not ep:
        print(f"{d}: 시리즈 날이 아니다 — 06:13 은 매일 운세 그대로")
        return 0
    sb = storyboard(d, ep)
    if a.cmd == "show":
        sc = sb["scenes"][0]
        print(f"{d} · {ep['id']} · {sb['platforms']['youtube']['title']}")
        if sc["type"] == "tier":
            for t in sc["tiers"]:
                print(f"  {t['label']:<3} " + " · ".join(f"{r['animal']}({r['line']})" for r in t["items"]))
        else:
            for r in sc["rows"]:
                print(f"  {r.get('label') or r['animal']:<8} {r['good']:<10} ({r['good_line']}) | {r['bad']:<8} ({r['bad_line']})")
        print("  🎙️", sc["narration"])
        return 0
    out = a.out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "samples",
                                f"{d.isoformat()}_{ep['id']}_storyboard.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
