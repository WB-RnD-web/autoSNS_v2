#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'2027 정미년 깊이 보기' 롱폼 16편(12~15분) — 편성 · 사실 계산 · 카탈로그 · 대본 검사 · 다음 편 (2026-10-20).

승인(사용자 10/20): "롱폼도 ㄱㄱ · 삼재 조언형 ㅇㅋ".

왜(10/20 조사 — 숫자는 사용자 확인):
  · 광고 수익 기준은 롱폼 시청 4,000시간인데 지금 565시간 → 2027-01-31까지 하루 ~40시간. 쇼츠 길은 지금 유효 조회의 4.2배.
  · 2027 정미년 롱폼이 작은 채널에서 지금 터진다 — 소문만복(10/2 개설 · 구독 3,190) '2027년 천살 드는 띠 … 꼭 지킬 3가지
    (출생연도별 풀이)' 13.6분 6일 485,946회 · 반안살 편 103,752 · 선명원격(1,080) 2027 총운 14.4분 26,925(중앙값 ×135).
    지난 시즌도 롱폼은 12~1월이 정점.
  · 우리 주간 롱폼은 254 → 101 → 47회로 꺼진다. 시청자는 쇼츠로만 내 띠를 본다 → 11/2부터 이 시리즈가 주간 롱폼을 대신한다
    (월요일 06:13 '이번 주 띠별 운세' 쇼츠는 06:13 루틴(MODE=weekly) 이 만든다 — 주간 롱폼과 무관해 그대로 나간다).

편성(날짜로 정한다 — 루틴 판단이 아니다): 2026-11-02(월)부터 월·수·금 20:00 KST, 16편 한 번씩(E01~E16).
  A. 신살 묶음 4편: 천살(신자진) → 화개살·날삼재(해묘미) → 반안살(인오술) → 월살(사유축)
  B. 띠 단독 12편: 양띠(2027 = 양의 해)부터 — 정미년(未)과의 관계가 센 띠부터, 좋은 편·조심 편을 번갈아:
     양(같은 띠·날삼재) → 말(육합) → 소(충) → 돼지(삼합·날삼재) → 쥐(원진·천살) → 토끼(삼합·날삼재) → 개(형)
     → 호랑이 → 용 → 원숭이 → 뱀 → 닭.

사실(코드가 계산 — 루틴은 옮겨 적기만): 십이신살(삼합 그룹의 지살부터 겁살…화개살) · 삼재(역마·육해·화개 해 = 들·눌·날) ·
  대장군(사오미년 = 동쪽) · 삼살(해묘미년 = 서쪽) · 未와의 합·충·형·원진·해·파 · 천간 丁의 십신 · 등급(newyear_card 총운·재물) ·
  좋은 달·조심할 달(절기 달 · newyear_card/newyear_series 표와 같다) · 출생연도별(1930~2009 · 천간 십신·합·충 · 환갑) ·
  행운의 색·숫자·방향(newyear_series 행운 표와 같다). → pipeline/longform_2027_catalog.json(이 코드가 만든다, 테스트가 대조).

루틴(클라우드 · 며칠 앞서 한 편)은 ★글만 쓴다. 장 순서·장 제목·화면(표·출생연도 목록·행운)은 코드가 정하고,
  분량·금지어·살 조언 틀·반복·사실(띠↔신살)은 코드가 검사한다(못 넘으면 렌더도 업로드도 없다):

    python pipeline/longform_2027.py next [--date 2026-10-31]     # 이번에 쓸 편 · 공개 시각 · 사실 · 뼈대
    python pipeline/longform_2027.py check <대본.json> [--lenient]
    python pipeline/longform_2027.py show --episode E05            # 한 편의 사실·장 계획
    python pipeline/longform_2027.py schedule                       # 16편 날짜·제목
    python pipeline/longform_2027.py catalog [--write]              # 카탈로그 JSON

글쓰기 안내: pipeline/LONGFORM_2027_WRITING.md · 견본(E01, 실제 첫 편): docs/samples/longform_2027_E01.json
데이터 브랜치: routine/fortune_lf27 (output/fortune_lf27/E01_2026-11-02.json) → .github/workflows/fortune-lf27.yml(코드는 main).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import birth_basis  # noqa: E402
import newyear_card as NY  # noqa: E402
import newyear_series as NS  # noqa: E402
import sal_frame  # noqa: E402
import weekly_fortune as WF  # noqa: E402
from fortune_card import ANIMALS  # noqa: E402
from pulli_card import (BRANCH_EL, BRANCHES, EL_WORD, HAE, HYEONG, PA, SAMHAP, WONJIN, YUKHAP,  # noqa: E402
                        relation, sipsin)
from tier_card import TIERS  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SERIES = "2027 정미년 깊이 보기"
PLAYLIST = os.environ.get("LF27_PLAYLIST") or SERIES
PLAYLIST_DESC = ("2027 정미년, 띠별로 깊이 풀어 드려요. 천살·화개살·반안살·월살 드는 띠와 꼭 지킬 것, "
                 "띠마다 총운·재물·가정·좋은 달과 출생연도별 풀이까지. 재미로 보는 운세예요.")
START = dt.date(2026, 11, 2)            # 첫 편(월)
POST_DAYS = (0, 2, 4)                   # 월·수·금
PUBLISH_HHMM = os.environ.get("LF27_PUBLISH_HHMM") or "20:00"
BRANCH = "routine/fortune_lf27"         # 데이터 브랜치(루틴이 main + 대본 한 장으로 강제 push)
OUT_DIR = "output/fortune_lf27"
NAME_RE = re.compile(r"^(E\d{2})_(\d{4}-\d{2}-\d{2})\.json$")
CATALOG_PATH = os.path.join(HERE, "longform_2027_catalog.json")
SAMPLE = os.path.join(ROOT, "docs", "samples", "longform_2027_E01.json")
MARKER = SERIES                          # 설명란 끝 줄 '2027 정미년 깊이 보기 E01' — 유튜브 쪽 중복 판정
CATEGORY = "24"
SYNTHETIC = os.environ.get("LF27_SYNTHETIC", "0") == "1"   # 그림체 배경(동화 그림) — 채널 운세 관례대로 표시 안 함
VOICE = os.environ.get("LF27_VOICE") or WF.VOICE
CREDIT = WF.CREDIT
DISCLAIMER = WF.DISCLAIMER
YEAR = 2027
YP = NY.YP                               # 정미 · 丁未
YEARS = (1930, 2009)                     # 출생연도 목록(1930~2000년대)
TIER_LABEL = {t["id"]: t["label"] for t in TIERS}       # S 대길 · A 길 · B 보통 · C 조심


# ══ 길이·분량 — 설정으로 바꾼다(주간 롱폼의 8~12분 · 12장 · 장당 230~360자 고정값과 따로) ══════════
def _pair(name: str, default: tuple) -> tuple:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        a, b = (float(x) for x in raw.split(","))
        return (a, b)
    except ValueError:
        return default


class Spec:
    """시리즈 길이 규칙. 환경변수로 바꿀 수 있다(LF27_EST_MIN='12,15' · LF27_CHAPTERS_MIN=10 …)."""
    def __init__(self):
        self.est_min = _pair("LF27_EST_MIN", (12.0, 15.0))       # 예상 길이(분) — 밖이면 검사 실패
        self.render_min = _pair("LF27_RENDER_MIN", (11.0, 16.5))  # 렌더 뒤 실제 길이(분) — 합성이 깨졌을 때
        self.chapters_min = int(os.environ.get("LF27_CHAPTERS_MIN", "10"))
        self.cpm = float(os.environ.get("LF27_CPM", "470"))      # Supertonic F2 말 속도(자/분 · 무음 자른 뒤 · 원본 속도)
        self.tempo = float(os.environ.get("LF27_TEMPO", os.environ.get("WEEKLY_TEMPO", "0.92")))
        self.gap_section = 0.45
        self.gap_part = 1.4
        self.lead, self.tail = 0.4, 2.0
        # 장 하나(코드 문구 포함)의 읽는 글자 수 — 꼴마다
        self.chapter_chars = {"card": (260, 820), "table": (200, 700), "lucky": (180, 650), "qa": (360, 1300),
                              "years": None}            # 출생연도 장은 줄 수에 따라(year_line × n)
        self.year_line = (60, 240)                      # 출생연도 한 줄(루틴 글)
        self.field = {"question": (12, 70), "cold_open": (150, 380), "say": (30, 300), "point": (4, 24),
                      "intro": (0, 200), "q": (10, 80), "a": (80, 340), "teaser": (50, 240), "closing": (0, 160)}
        self.counts = {"card_say": (2, 5), "card_points": (2, 4), "table_say": (1, 4), "lucky_say": (1, 4),
                       "qa": (2, 4)}
        self.similar = 0.6                              # 같은 대본 안 두 단락 — 글자쌍 자카드
        self.history_similar = 0.6                      # 지난 대본·견본과
        self.max_chunk = 190                            # TTS 한 번에 읽힐 최대 글자(문장 단위로 나눈다)

    @property
    def TEMPO(self):  # weekly_fortune_render.timeline/build_audio 가 쓰는 이름
        return self.tempo

    @property
    def LEAD(self):
        return self.lead

    @property
    def TAIL(self):
        return self.tail

    @property
    def GAP_PART(self):
        return self.gap_part

    @property
    def GAP_SECTION(self):
        return self.gap_section

    @property
    def CPM(self):
        return self.cpm


SPEC = Spec()


# ══ 1. 사실 — 십이신살 · 삼재 · 대장군 · 삼살 · 관계 ══════════════════════════════════════════
GROUPS = (("신자진", (8, 0, 4)), ("인오술", (2, 6, 10)), ("사유축", (5, 9, 1)), ("해묘미", (11, 3, 7)))
GROUP_ORDER = {"신자진": ("원숭이", "쥐", "용"), "인오술": ("호랑이", "말", "개"), "사유축": ("뱀", "닭", "소"),
               "해묘미": ("돼지", "토끼", "양")}
SINSAL = ("겁살", "재살", "천살", "지살", "년살", "월살", "망신살", "장성살", "반안살", "역마살", "육해살", "화개살")
SAMJAE = ("들삼재", "눌삼재", "날삼재")
# 화면·말에 쓰는 쉬운 뜻 — ★조언 틀(sal_frame)을 지키는 한 줄
SINSAL_PLAIN = {
    "천살": ("하늘의 기운이 드는 해", "몸을 낮추고 겸손하게, 큰 욕심보다 마음 다스리기"),
    "화개살": ("빛나는 덮개, 마음이 깊어지는 해", "배움·정리·신앙에 좋은 때 — 혼자 끙끙대지 않기"),
    "반안살": ("말 안장에 오르는 해", "자리를 다지고 명예를 챙기기 좋은 때 — 기운 살리는 해"),
    "월살": ("달빛이 마른 듯 쉬어 가는 해", "서두르지 말고 준비·저축으로 속을 채우기"),
}
SINSAL_SHORT = {"천살": "몸 낮추고 겸손하게", "화개살": "배움·정리에 좋은 때", "반안살": "자리 다지기 좋은 때",
                "월살": "준비·저축으로 채우기"}        # 표 한 칸(조언 틀)
SAMJAE_PLAIN = {"들삼재": "삼재가 들어오는 해", "눌삼재": "삼재가 머무는 해", "날삼재": "삼재가 나가는 마지막 해"}


def year_branch(y: int) -> int:
    return (y - 4) % 12


def group_of(b: int) -> tuple[str, tuple]:
    for name, g in GROUPS:
        if b in g:
            return name, g
    raise ValueError(b)


def sinsal_of(b: int, yb: int = YP["branch"]) -> str:
    """띠 b 에게 지지 yb 의 해가 무슨 신살인가 — 삼합 그룹의 지살(생지)부터 겁살·재살·천살·지살 … 화개살."""
    _, g = group_of(b)
    return SINSAL[(yb - g[0] + 3) % 12]


def samjae_stage(b: int, yb: int = YP["branch"]) -> str:
    """삼재 = 그 띠의 역마·육해·화개 해 → 들·눌·날삼재. 아니면 ''."""
    _, g = group_of(b)
    k = (yb - g[0] + 3) % 12
    return SAMJAE[k - 9] if k >= 9 else ""


def samjae_years(b: int, around: int = YEAR) -> dict:
    """그 띠의 삼재 세 해 — 2027 이 들어 있으면 now, 아니면 지난(last)·다음(next)."""
    _, g = group_of(b)
    first = (g[0] + 6) % 12                                       # 들삼재 = 역마 지지
    starts = [y for y in range(around - 12, around + 13) if year_branch(y) == first]
    out = {}
    for y0 in starts:
        span = [y0, y0 + 1, y0 + 2]
        if around in span:
            out["now"] = span
        elif y0 + 2 < around:
            out["last"] = span
        elif y0 > around and "next" not in out:
            out["next"] = span
    return out


def daejanggun(yb: int = YP["branch"]) -> str:
    """대장군 방위 — 인묘진년 북 · 사오미년 동 · 신유술년 남 · 해자축년 서."""
    return {2: "북쪽", 3: "북쪽", 4: "북쪽", 5: "동쪽", 6: "동쪽", 7: "동쪽", 8: "남쪽", 9: "남쪽", 10: "남쪽",
            11: "서쪽", 0: "서쪽", 1: "서쪽"}[yb]


def samsal(yb: int = YP["branch"]) -> str:
    """삼살 방위 — 신자진년 남 · 인오술년 북 · 사유축년 동 · 해묘미년 서."""
    name, _ = group_of(yb)
    return {"신자진": "남쪽", "인오술": "북쪽", "사유축": "동쪽", "해묘미": "서쪽"}[name]


def all_relations(yb: int, b: int) -> list[str]:
    """지지 둘의 관계 전부(같은 띠·육합·삼합·충·원진·형·해·파) — relation() 은 가장 센 하나만 준다."""
    pair, out = {yb, b}, []
    if b == yb:
        out.append("같은 띠")
    if any(pair == set(p) for p in YUKHAP):
        out.append("육합")
    if any(yb in g and b in g and b != yb for g, _ in SAMHAP):
        out.append("삼합")
    if (b - yb) % 12 == 6:
        out.append("충")
    if any(pair == set(p) for p in WONJIN):
        out.append("원진")
    if b != yb and any(pair <= g for g in HYEONG):
        out.append("형")
    if any(pair == set(p) for p in HAE):
        out.append("해")
    if any(pair == set(p) for p in PA):
        out.append("파")
    return out


REL_PLAIN = {"같은 띠": "내 띠의 해 — 기운이 겹쳐요", "육합": "손발이 맞는 짝(육합)", "삼합": "한 팀(해묘미 삼합)",
             "충": "정면으로 부딪히는 기운(충) — 큰 결정은 천천히", "원진": "서운함이 쌓이기 쉬운 사이(원진) — 말 아끼기",
             "형": "서두르면 엇나가는 사이(축술미 형) — 한 박자 쉬기", "해": "작은 엇갈림(해) — 다시 확인하기",
             "파": "약속이 흔들리는 사이(파) — 약속 다시 확인"}
CAT_PLAIN = {"인성": "나를 돕는 기운", "비겁": "나와 같은 기운", "식상": "내가 베푸는 기운(재물을 낳음)",
             "재성": "재물 기운", "관성": "나를 다잡는 기운(맡을 일이 늚)"}
SINO = {1: "일", 2: "이", 3: "삼", 4: "사", 5: "오", 6: "육", 7: "칠", 8: "팔", 9: "구", 10: "십"}
MONTH_SPOKEN = {1: "일월", 2: "이월", 3: "삼월", 4: "사월", 5: "오월", 6: "유월", 7: "칠월", 8: "팔월", 9: "구월",
                10: "시월", 11: "십일월", 12: "십이월"}
ORD = ("첫", "두", "세", "네", "다섯")


def josa(w: str, a: str, b: str) -> str:
    return NY.josa(w, a, b)


def ddi_years(animal: str, lo: int = YEARS[0], hi: int = YEARS[1]) -> list[int]:
    k = ANIMALS.index(animal)
    return [y for y in range(lo, hi + 1) if year_branch(y) == k]


def yy(y: int) -> str:
    return f"{y % 100:02d}"


def years_label(animal: str) -> str:
    return "·".join(yy(y) for y in ddi_years(animal)) + "년생"


def year_spoken(y: int) -> str:
    """말: 1900년대는 '68년생'(주간 롱폼에서 검증된 읽기), 2000년대는 '2004년생'('공사'로 읽히지 않게)."""
    return f"{y}년생" if y >= 2000 else f"{yy(y)}년생"


def spoken_list(words: list[str], a: str = "과", b: str = "와") -> str:
    """['흰색', '은색'] → '흰색과 은색'."""
    ws = [w for w in words if w]
    if len(ws) <= 1:
        return "".join(ws)
    return ", ".join(ws[:-2] + [josa(ws[-2], a, b) + " " + ws[-1]]) if len(ws) > 2 else josa(ws[0], a, b) + " " + ws[1]


def months_spoken(ms: list[int]) -> str:
    return spoken_list([MONTH_SPOKEN[m] for m in sorted(ms)])


def nums_spoken(nums: str) -> str:
    return spoken_list([SINO[int(x)] for x in nums.split("·")])


def year_rows_for(animal: str) -> list[dict]:
    """출생연도 한 줄씩 — 천간 십신(丁에서 본) · 천간합(정임)·천간충(정계) · 환갑(같은 간지)."""
    out = []
    for y in ddi_years(animal):
        i, s, b = NS.gz_of_year(y)
        god = NY.ten_god(s)
        good, gl, bad, bl = NY.GOD[god]
        pair = frozenset((s, YP["stem"]))
        note = ("정임 천간합 — 돈과 인연이 붙는 해" if pair in NY.HAP else
                "정계 천간충 — 서명·돈 약속은 천천히" if pair in NY.CHUNG else "")
        out.append({"year": y, "yy": yy(y), "age_2027": YEAR - y, "hwangap": (y - YEAR) % 60 == 0,
                    "stem_god": god, "good": good, "good_line": gl, "caution": bad, "caution_line": bl,
                    "stem_note": note, "decade": f"{(y // 10) * 10}년대"})
    return out


def ddi_facts(animal: str) -> dict:
    b = ANIMALS.index(animal)
    grp, _ = group_of(b)
    rels = all_relations(YP["branch"], b)
    top, _ = relation(YP["branch"], b)
    cats = NS.cats(b)
    tot = {r["animal"]: r for r in NY.total_items()}[animal]
    mon = {r["animal"]: r for r in NY.money_items()}[animal]
    mr = {r["animal"]: r for r in NY.month_rows()}[animal]
    mt = {k: {r["animal"]: r for r in NS.month_table(k)}[animal] for k in ("money", "body", "trip")}
    lk = {r["animal"]: r for r in NS.lucky_rows()}[animal]
    hl = {r["animal"]: r for r in NS.health_rows()}[animal]
    ss = sinsal_of(b)
    sj = samjae_stage(b)
    le = lk["lucky_el"]
    return {
        "animal": animal, "branch": BRANCHES[b], "element": EL_WORD[BRANCH_EL[b]], "group": grp,
        "group_animals": list(GROUP_ORDER[grp]),
        "sinsal_2027": ss, "sinsal_plain": SINSAL_PLAIN[ss][0], "sinsal_advice": SINSAL_PLAIN[ss][1],
        "samjae_2027": sj, "samjae_plain": SAMJAE_PLAIN.get(sj, ""), "samjae_years": samjae_years(b),
        "relations_with_2027": rels, "relation_main": top,
        "relation_plain": [REL_PLAIN[r] for r in rels],
        "stem_ding_is": cats[0], "branch_mi_is": cats[1],
        "energy_plain": [f"정(丁) 불 → {CAT_PLAIN[cats[0]]}", f"미(未) 흙 → {CAT_PLAIN[cats[1]]}"],
        "tier_total": TIER_LABEL[tot["tier"]], "tier_total_line": tot["line"].replace("큰일", "큰 결정"),
        "tier_money": TIER_LABEL[mon["tier"]], "tier_money_line": mon["line"],
        "months_good": [m for m, _ in mr["good"]], "months_good_why": [f"{m}월 {r}" for m, r in mr["good"]],
        "months_caution": [m for m, _ in mr["bad"]], "months_caution_why": [f"{m}월 {r}" for m, r in mr["bad"]],
        "months_money_good": [m for m, _ in mt["money"]["good_tags"]],
        "months_money_caution": [m for m, _ in mt["money"]["bad_tags"]],
        "months_body_good": [m for m, _ in mt["body"]["good_tags"]],
        "months_body_caution": [m for m, _ in mt["body"]["bad_tags"]],
        "months_trip_good": [m for m, _ in mt["trip"]["good_tags"]],
        "health": {"part": hl["good"], "why": hl["good_line"], "habit": hl["bad"], "line": hl["bad_line"]},
        "lucky": {"colors": lk["good"], "numbers": NS.EL_NUM[le], "direction": NS.EL_DIR[le], "tip": NS.EL_DIR_TIP[le],
                  "element": EL_WORD[le], "why": lk["good_line"]},
        "years": year_rows_for(animal),
    }


def year_facts() -> dict:
    return {"year": YEAR, "pillar": YP["name"], "pillar_hanja": YP["hanja"], "animal": "양",
            "stem": "정(丁) — 불", "branch": "미(未) — 흙 · 양", "daejanggun": daejanggun(), "samsal": samsal(),
            "ipchun_2027": birth_basis.IPCHUN[YEAR], "hwangap_year": YEAR - 60,
            "sinsal_by_group": {g: sinsal_of(gb[0]) for g, gb in GROUPS},
            "samjae_2027": {g: samjae_stage(gb[0]) for g, gb in GROUPS},
            "month_spans": {str(m): NS.month_span(m) for m in range(1, 13)},
            "next_year": {"year": YEAR + 1, "pillar": "무신", "samjae_starts": [a for a in ANIMALS
                                                                              if samjae_stage(ANIMALS.index(a), year_branch(YEAR + 1)) == "들삼재"]}}


# ══ 2. 편 목록 ═══════════════════════════════════════════════════════════════════════════
SINGLE_ORDER = ("양", "말", "소", "돼지", "쥐", "토끼", "개", "호랑이", "용", "원숭이", "뱀", "닭")
GROUP_EPISODES = (("신자진", "천살"), ("해묘미", "화개살"), ("인오술", "반안살"), ("사유축", "월살"))
REL_HOOK = {"같은 띠": "내 띠의 해", "육합": "정미년과 육합", "삼합": "해묘미 삼합", "충": "정미년과 충",
            "원진": "정미년과 원진", "형": "정미년과 형"}
# 띠마다 제목의 살 꼭지를 다르게(같은 신살 띠 셋이 같은 제목이 되지 않게) — ★조언 틀(sal_frame) 안에서만
SAL_HOOK = {"양": "날삼재 잘 넘기는 법", "돼지": "날삼재 마무리 잘하는 법", "토끼": "날삼재 복삼재로 바꾸는 법",
            "쥐": "천살 잘 넘기는 법", "용": "천살에 꼭 지킬 것", "원숭이": "천살 겸손하게 넘기는 법",
            "말": "반안살 기운 살리는 법", "개": "반안살 자리 지키는 법", "호랑이": "반안살 기운 키우는 법",
            "소": "월살 조심할 달과 지킬 것", "뱀": "월살 잘 넘기는 법", "닭": "월살 내실 다지는 법"}
GROUP_TIP = {"천살": "꼭 지킬", "화개살": "잘 넘기는 법", "반안살": "꼭 챙길", "월살": "꼭 지킬"}
# 배경(Spark · 동화 그림체 · ★글자가 나오지 않게 긍정형 묘사 — 한옥 방 '무늬 없는 창호지' 처럼. '행운·축제·설날'은 쓰지 않는다)
STYLE = ("soft warm storybook illustration, gentle painterly digital art, calm Korean countryside mood, "
         "wide composition with open sky or plain walls, no people")
SCENES = (
    "a quiet hanok courtyard at dawn with a persimmon tree heavy with orange fruit and plain paper sliding doors",
    "misty layered Korean mountains at sunrise above a calm river valley",
    "a low wooden table with a celadon teapot and a bowl of persimmons in a sunlit hanok room with plain paper walls",
    "a country path lined with golden ginkgo trees in late autumn afternoon light",
    "a calm lake with a small wooden pavilion in soft morning mist",
    "rows of brown earthenware jars on a sunny stone terrace beside a hanok house",
    "white sheep grazing on a gentle green hillside under a soft morning sky",
    "snow-covered hanok roofs under a clear pale winter sky",
    "a stone wall path in a traditional village with maple trees glowing red",
    "a wide field of golden rice at harvest time under a clear blue sky",
    "a quiet temple garden with a stone pagoda and pine trees in soft light",
    "a full moon rising over dark hills and a quiet hanok village",
    "a warm hanok kitchen with a cast iron pot and wooden shelves in evening lamplight",
    "a pine forest path with sunbeams through the trees",
    "plum blossoms on a branch beside a plain paper window in early spring",
    "a quiet seaside with gentle waves and distant islands at golden hour",
)
LAMB = ("a cute fluffy white lamb mascot wearing a small red knitted scarf, sitting on a wooden hanok porch "
        "looking at an autumn garden with a persimmon tree")


def _schedule_dates(n: int) -> list[dt.date]:
    out, d = [], START
    while len(out) < n:
        if d.weekday() in POST_DAYS:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def _single_title(a: str, f: dict) -> tuple[str, str]:
    hook = REL_HOOK.get(f["relation_main"]) or NY.LINE_CAT[f["stem_ding_is"]]
    sal = SAL_HOOK[a]
    return f"2027년 {a}띠 운세 | {hook} · {sal} · 출생연도별 풀이", sal


def _chapters_group(grp: str, ss: str) -> list[dict]:
    a1, a2, a3 = GROUP_ORDER[grp]
    sj = "날삼재" if ss == "화개살" else ""
    about = f"{ss}·{sj}이란 — 겁낼 것 없는 이유" if sj else f"{ss}이란 — 겁낼 것 없는 이유"
    if ss == "반안살":
        about = "반안살이란 — 기운 살리는 해"
    tip = GROUP_TIP[ss]
    tips = ([f"날삼재 잘 넘기는 법 {o}째" for o in ("첫", "둘", "셋")] if sj else
            [f"{tip} 것 {o}째" for o in ("첫", "둘", "셋")])
    ch = [{"id": "c01", "layout": "table", "table": "sinsal12", "title": "2027 정미년 12띠 신살 표 — 내 띠는 어디에"},
          {"id": "c02", "layout": "card", "topic": "about", "title": about}]
    for k, a in enumerate((a1, a2, a3)):
        ch.append({"id": f"c{3 + k:02d}", "layout": "years", "animal": a, "years": ddi_years(a),
                   "title": f"{a}띠 출생연도별 풀이 ({years_label(a)})"})
    for k, t in enumerate(tips):
        ch.append({"id": f"c{6 + k:02d}", "layout": "card", "topic": f"tip{k + 1}", "title": t})
    ch += [{"id": "c09", "layout": "table", "table": "months3", "title": "좋은 달·조심할 달 — 세 띠 한눈에"},
           {"id": "c10", "layout": "qa", "title": "자주 묻는 질문"},
           {"id": "c11", "layout": "lucky", "title": "행운의 색·숫자·방향"}]
    return ch


def _chapters_single(a: str, f: dict) -> list[dict]:
    ss, sj = f["sinsal_2027"], f["samjae_2027"]
    sal_title = {"천살": "천살 잘 넘기는 법", "화개살": "화개살·날삼재 잘 넘기는 법" if sj else "화개살 잘 쓰는 법",
                 "반안살": "반안살 기운 살리는 법", "월살": "월살 — 조심할 점과 지킬 것"}[ss]
    ys = ddi_years(a)
    old = [y for y in ys if y < 1970]
    new = [y for y in ys if y >= 1970]
    lab = lambda yl: "·".join(yy(y) for y in yl) + "년생"  # noqa: E731
    return [
        {"id": "c01", "layout": "card", "topic": "total", "title": f"2027 {a}띠 총운"},
        {"id": "c02", "layout": "card", "topic": "sinsal", "title": sal_title},
        {"id": "c03", "layout": "card", "topic": "money", "title": "재물운 — 돈이 도는 때와 지킬 것"},
        {"id": "c04", "layout": "card", "topic": "health", "title": "건강운 — 챙길 곳과 좋은 습관"},
        {"id": "c05", "layout": "card", "topic": "family", "title": "가정·자녀운"},
        {"id": "c06", "layout": "table", "table": "people12", "title": "올해 힘이 되는 띠·말 아낄 띠"},
        {"id": "c07", "layout": "table", "table": "months1", "title": "좋은 달·조심할 달"},
        {"id": "c08", "layout": "years", "animal": a, "years": old, "title": f"출생연도별 풀이 ① {lab(old)}"},
        {"id": "c09", "layout": "years", "animal": a, "years": new, "title": f"출생연도별 풀이 ② {lab(new)}"},
        {"id": "c10", "layout": "qa", "title": "자주 묻는 질문"},
        {"id": "c11", "layout": "lucky", "title": "행운의 색·숫자·방향"},
    ]


def _qa_seeds_group(grp: str, ss: str) -> list[str]:
    a1, a2, a3 = GROUP_ORDER[grp]
    out = [f"{ss}이 든 해에는 이사나 큰 계약을 미뤄야 하나요?",
           f"{a1}띠·{a2}띠·{a3}띠 부부라면 둘 다 {ss}인데 괜찮을까요?",
           "양력 일월생인데 제 띠가 맞는지 헷갈려요."]
    for a in (a1, a2, a3):
        rels = all_relations(YP["branch"], ANIMALS.index(a))
        for r in rels:
            if r in ("원진", "충", "형"):
                out.insert(1, f"{a}띠는 {ss}에 {r}까지 겹친다는데 어떻게 지내면 좋을까요?")
    if ss == "화개살":
        out.insert(0, "날삼재는 들삼재보다 조심할 게 적나요?")
    return out[:5]


def _qa_seeds_single(a: str, f: dict) -> list[str]:
    out = [f"{a}띠는 올해 이사해도 괜찮을까요?", f"{a}띠 자녀가 올해 결혼하는데 날을 어떻게 볼까요?",
           f"{f['years'][0]['yy']}년생도 이 풀이가 맞나요?"]
    if f["samjae_2027"]:
        out.insert(0, "날삼재에 꼭 피해야 할 일이 있나요?")
    if f["relation_main"] in ("충", "원진", "형"):
        out.insert(0, f"정미년과 {f['relation_main']}이라는데 한 해 내내 조심해야 하나요?")
    if any(y["hwangap"] for y in f["years"]):
        out.insert(0, "올해 환갑인데 잔치는 언제 하면 좋을까요?")
    return out[:5]


def episodes() -> list[dict]:
    dates = _schedule_dates(16)
    eps = []
    for k, (grp, ss) in enumerate(GROUP_EPISODES):
        a = GROUP_ORDER[grp]
        sj = "날삼재" if ss == "화개살" else ""
        if sj:
            title = f"2027년 날삼재 드는 띠 {a[0]}띠·{a[1]}띠·{a[2]}띠 | 복삼재로 바꾸는 법 · 출생연도별 풀이"
            thumb = {"big": "2027 날삼재", "sub": f"{a[0]}·{a[1]}·{a[2]}띠", "pill": "복삼재로 바꾸는 법"}
            angle = ("2025년 들삼재부터 이어진 삼재가 나가는 해(날삼재) + 정미년의 화개살. 마무리를 잘하면 복삼재로 — "
                     "겁주지 말고 '정리·배움·마무리'로 푼다. 2027이 양띠 해라 양띠는 내 띠의 해까지 겹친다.")
        elif ss == "반안살":
            title = f"2027년 반안살 드는 띠 {a[0]}띠·{a[1]}띠·{a[2]}띠 | 기운 살리는 3가지 · 출생연도별 풀이"
            thumb = {"big": "2027 반안살", "sub": f"{a[0]}·{a[1]}·{a[2]}띠", "pill": "기운 살리는 3가지"}
            angle = ("반안살은 말 안장에 오르는 기운 — 자리·명예·안정. 말띠는 정미년과 육합까지, 개띠는 형이 겹치니 "
                     "서두르지 않기. 내년(2028)이 이 세 띠의 들삼재라 '미리 준비'도 한 꼭지.")
        elif ss == "월살":
            title = f"2027년 월살 드는 띠 {a[0]}띠·{a[1]}띠·{a[2]}띠 | 조심할 달과 꼭 지킬 3가지 · 출생연도별 풀이"
            thumb = {"big": "2027 월살", "sub": f"{a[0]}·{a[1]}·{a[2]}띠", "pill": "꼭 지킬 3가지"}
            angle = ("월살은 달빛이 마른 듯 쉬어 가는 기운 — 서두르지 말고 준비·저축. 소띠는 정미년과 충까지 겹치니 "
                     "큰 결정은 천천히. 조심할 달을 달력처럼 짚어 준다.")
        else:
            title = f"2027년 천살 드는 띠 {a[0]}띠·{a[1]}띠·{a[2]}띠 | 꼭 지킬 3가지 · 출생연도별 풀이"
            thumb = {"big": "2027 천살", "sub": f"{a[0]}·{a[1]}·{a[2]}띠", "pill": "꼭 지킬 3가지"}
            angle = ("천살은 하늘의 기운이 드는 해 — 몸을 낮추고 겸손하게, 윗사람·건강·마음 다스리기. 쥐띠는 원진까지, "
                     "용띠는 돕는 기운의 해라 같은 천살이라도 결이 다르다. 삼재는 이미 지나간 띠들(2022~2024).")
        eps.append({"id": f"E{k + 1:02d}", "kind": "group", "group": grp, "animals": list(a), "sinsal": ss,
                    "samjae": sj, "title": title, "search": title.split(" | ")[0], "thumb": thumb, "angle": angle,
                    "chapters": _chapters_group(grp, ss), "qa_seeds": _qa_seeds_group(grp, ss)})
    for a in SINGLE_ORDER:
        f = ddi_facts(a)
        title, sal = _single_title(a, f)
        ys = ddi_years(a)
        rel = f["relation_main"] or "관계 없음"
        angle = (f"{a}띠 단독 — 정미년과 {rel}, {f['sinsal_2027']}" + (f"·{f['samjae_2027']}" if f["samjae_2027"] else "")
                 + f", 총운 {f['tier_total']} · 재물 {f['tier_money']}. 정(丁) 불은 {CAT_PLAIN[f['stem_ding_is']]}, "
                 f"미(未) 흙은 {CAT_PLAIN[f['branch_mi_is']]}. 좋은 달 {NY.months_text([(m, '') for m in f['months_good']])}"
                 f" · 조심할 달 {NY.months_text([(m, '') for m in f['months_caution']])}."
                 + (" 67년생은 올해 환갑(정미생이 다시 정미년)." if a == "양" else ""))
        eps.append({"id": f"E{len(eps) + 1:02d}", "kind": "single", "group": f["group"], "animals": [a],
                    "sinsal": f["sinsal_2027"], "samjae": f["samjae_2027"], "title": title,
                    "search": title.split(" | ")[0],
                    "thumb": {"big": f"2027 {a}띠", "sub": f"{yy(ys[0])}~{yy(ys[-1])}년생", "pill": sal},
                    "angle": angle, "chapters": _chapters_single(a, f), "qa_seeds": _qa_seeds_single(a, f)})
    for k, ep in enumerate(eps):
        ep["publish"] = dates[k].isoformat()
        ep["weekday"] = "월화수목금토일"[dates[k].weekday()]
        ep["scenes"] = [SCENES[(k * 5 + j) % len(SCENES)] for j in range(len(ep["chapters"]))]
        ep["next"] = eps[k + 1]["id"] if k + 1 < len(eps) else None
        ep["next_title"] = eps[k + 1]["title"] if k + 1 < len(eps) else None     # 제목 통째(살 낱말이 조언 틀 안에 있게)
    return eps


EPISODES = episodes()
BY_ID = {e["id"]: e for e in EPISODES}


def episode(eid: str) -> dict:
    if eid not in BY_ID:
        raise KeyError(f"편 {eid!r} 없음 — E01~E{len(EPISODES):02d}")
    return BY_ID[eid]


def last_day() -> dt.date:
    """시리즈 마지막 편 공개일(E16) — tools/runway.py 가 부른다."""
    return dt.date.fromisoformat(EPISODES[-1]["publish"])


def publish_dt(ep: dict) -> dt.datetime:
    h, m = (int(x) for x in PUBLISH_HHMM.split(":"))
    return dt.datetime.combine(dt.date.fromisoformat(ep["publish"]), dt.time(h, m), tzinfo=KST)


def publish_at(ep: dict, now: dt.datetime | None = None) -> str | None:
    """예약 공개 시각(UTC RFC3339) — 그 편의 날 20:00 KST. 이미 지났거나 10분 안이면 None(바로 공개)."""
    when = publish_dt(ep)
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    if when <= now + dt.timedelta(minutes=10):
        return None
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_name(ep: dict) -> str:
    return f"{ep['id']}_{ep['publish']}.json"


def ep_facts(ep: dict) -> dict:
    return {a: ddi_facts(a) for a in ep["animals"]}


# ══ 3. 표(화면) — 시리즈 계산으로 만든다 ══════════════════════════════════════════════════════
def table_sinsal12() -> list[dict]:
    rows = []
    for a in ANIMALS:
        b = ANIMALS.index(a)
        ss, sj = sinsal_of(b), samjae_stage(b)
        rels = all_relations(YP["branch"], b)
        rel = "내 띠의 해" if rels[:1] == ["같은 띠"] else ("정미년과 " + "·".join(rels[:2]) if rels else "")
        rows.append({"animal": a, "sinsal": ss, "samjae": sj, "rel": rel, "advice": SINSAL_SHORT[ss]})
    return rows


def table_months(animals: list[str]) -> list[dict]:
    out = []
    for a in animals:
        f = ddi_facts(a)
        out.append({"animal": a, "good": f["months_good"], "good_why": f["months_good_why"],
                    "caution": f["months_caution"], "caution_why": f["months_caution_why"],
                    "money": f["months_money_good"], "body": f["months_body_good"]})
    return out


PEOPLE_TAG = {"육합": "짝꿍 · 힘이 돼요", "삼합": "한 팀 · 같이 하면 좋아요", "같은 띠": "같은 띠 · 마음이 통해요",
              "충": "충 · 큰 결정은 상의해서", "원진": "원진 · 말 아끼기", "형": "형 · 서두르지 않기",
              "해": "해 · 한 번 더 확인", "파": "파 · 약속 다시 확인"}


def table_people12(animal: str) -> list[dict]:
    me = ANIMALS.index(animal)
    lines = {r["animal"]: r["line"].replace("큰일", "큰 결정") for r in NY.total_items()}   # 롱폼은 '큰일'을 쓰지 않는다
    rows = []
    for a in ANIMALS:
        rels = all_relations(me, ANIMALS.index(a))
        main = rels[0] if rels else ""
        rows.append({"animal": a, "rel": main, "tag": PEOPLE_TAG.get(main, "무난 · 편하게 지내요"),
                     "line_2027": lines[a]})
    return rows


# ══ 4. 대본 → 렌더 계획 ═══════════════════════════════════════════════════════════════════
def _s(v) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _end(t: str) -> str:
    t = _s(t)
    return t if not t or t[-1] in ".!?…" else t + "."


def split_chunks(text: str, limit: int | None = None) -> list[str]:
    """TTS 한 번에 읽힐 만큼(문장 단위) — 한 문장이 길면 쉼표에서 한 번 더."""
    limit = limit or SPEC.max_chunk
    t = _end(text)
    if len(t) <= limit:
        return [t] if t else []
    sents = [x for x in re.split(r"(?<=[.!?…])\s+", t) if x]
    out, cur = [], ""
    for s in sents:
        if len(s) > limit:
            parts = re.split(r"(?<=,)\s+", s)
            for p in parts:
                if cur and len(cur) + 1 + len(p) > limit:
                    out.append(cur)
                    cur = p
                else:
                    cur = f"{cur} {p}".strip()
            continue
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


IPCHUN_SPOKEN = ("띠는 입춘을 기준으로 봐요. 양력으로 일월 일일부터 이월 삼일 사이에 태어나셨으면 "
                 "앞 해 띠로 보시면 됩니다.")
OPEN_TAIL = "목차는 설명란에 있으니, 내 띠 부분부터 골라 들으셔도 됩니다."
OUTRO_FIXED = ("오늘 풀이는 재미로 들으시고, 좋은 마음으로 새해를 준비하세요. 건강과 돈 문제는 꼭 전문가와 상의하시고요. "
               "구독과 알림을 켜 두시면 다른 띠 이야기도 편하게 이어서 보실 수 있어요.")
LUCKY_FIXED = "이사나 큰 공사 방향을 잡으실 때는, 올해 대장군이 동쪽이고 삼살이 서쪽이라는 것만 참고해 두세요."


def lucky_spoken(animal: str) -> str:
    lk = ddi_facts(animal)["lucky"]
    colors = spoken_list(lk["colors"].split("·"))
    return (f"{animal}띠의 행운의 색은 {colors}, 숫자는 {nums_spoken(lk['numbers'])}, "
            f"방향은 {lk['direction']}이에요.").replace("방향은 가운데이에요", "방향은 집 가운데예요")


def compose(sc: dict, upto: int | None = None) -> dict:
    """검사를 통과한 대본 → 렌더 계획(파트 = 유튜브 챕터 하나 · 조각 = TTS 한 번 · 화면). upto: 앞 파트 n 개만(시험 렌더)."""
    ep = episode(_s(sc.get("episode")))
    plan_ch = {c["id"]: c for c in ep["chapters"]}
    animals = ep["animals"]
    parts = []
    q = _s(sc.get("question"))
    opening = [{"text": _end(q) if q.endswith("?") else _end(q), "slide": {"kind": "open", "step": 0}}]
    for t in split_chunks(sc.get("cold_open")):
        opening.append({"text": t, "slide": {"kind": "open", "step": 1}})
    opening.append({"text": OPEN_TAIL, "slide": {"kind": "open", "step": 1}})
    parts.append({"id": "open", "title": "시작 · 오늘의 질문", "layout": "open",
                  "scene": LAMB, "chunks": opening})
    first_years = True
    chapters = [c for c in sc.get("chapters") or [] if isinstance(c, dict)]
    for n, ch in enumerate(chapters, 1):
        cp = plan_ch[_s(ch.get("id"))]
        lay = cp["layout"]
        base = {"chapter": cp["id"], "index": n, "title": cp["title"], "layout": lay}
        chunks = []
        if lay == "card":
            pts = [_s(p) for p in ch.get("points") or []]
            says = [x for x in (ch.get("say") or []) if _s(x)]
            for k, s in enumerate(says):
                shown = min(len(pts), max(1, round((k + 1) * len(pts) / len(says))))
                for t in split_chunks(s):
                    chunks.append({"text": t, "slide": {"kind": "card", **base, "animals": animals,
                                                        "points": pts, "shown": shown}})
        elif lay in ("table", "lucky"):
            kind = "lucky" if lay == "lucky" else "table"
            extra = {"table": cp.get("table")} if lay == "table" else {}
            if lay == "lucky":
                for a in animals:
                    chunks.append({"text": lucky_spoken(a), "slide": {"kind": kind, **base, "animals": animals,
                                                                      "focus": a}})
            for s in ch.get("say") or []:
                for t in split_chunks(s):
                    chunks.append({"text": t, "slide": {"kind": kind, **base, "animals": animals, **extra,
                                                        "focus": animals[0] if lay == "lucky" else ""}})
            if lay == "lucky":
                chunks.append({"text": LUCKY_FIXED, "slide": {"kind": kind, **base, "animals": animals, "focus": "",
                                                              "compass": True}})
        elif lay == "years":
            a = cp["animal"]
            rows = {r["year"]: r for r in ddi_facts(a)["years"]}
            yrs = cp["years"]
            lines = {int(x.get("year")): x for x in ch.get("years") or [] if isinstance(x, dict) and str(x.get("year", "")).isdigit()}
            if first_years:
                chunks.append({"text": IPCHUN_SPOKEN, "slide": {"kind": "years", **base, "animal": a, "years": yrs,
                                                                "focus": None, "points": {}}})
                first_years = False
            pts = {y: _s(lines[y].get("point")) for y in yrs if y in lines}
            if _s(ch.get("intro")):
                for t in split_chunks(ch.get("intro")):
                    chunks.append({"text": t, "slide": {"kind": "years", **base, "animal": a, "years": yrs,
                                                        "focus": None, "points": {}}})
            for y in yrs:
                ln = lines.get(y) or {}
                r = rows[y]
                tag = r["good"]
                body = split_chunks(f"{year_spoken(y)}. {_s(ln.get('say'))}")
                for t in body:
                    chunks.append({"text": t, "slide": {"kind": "years", **base, "animal": a, "years": yrs, "focus": y,
                                                        "point": pts.get(y, ""), "tag": tag,
                                                        "hwangap": r["hwangap"]}})
        elif lay == "qa":
            for k, item in enumerate([x for x in ch.get("qa") or [] if isinstance(x, dict)]):
                qq, pt = _s(item.get("q")), _s(item.get("point"))
                sl = {"kind": "qa", **base, "q": qq, "point": pt, "n": k + 1}
                chunks.append({"text": f"{ORD[k]} 번째 질문이에요. {_end(qq)}", "slide": {**sl, "answer": False}})
                for t in split_chunks(item.get("a")):
                    chunks.append({"text": t, "slide": {**sl, "answer": True}})
        parts.append({"id": cp["id"], "title": cp["title"], "layout": lay, "scene": ep["scenes"][n - 1],
                      "animal": cp.get("animal"), "years": cp.get("years"), "chunks": chunks})
    outro = []
    for t in split_chunks(sc.get("teaser")):
        outro.append({"text": t, "slide": {"kind": "outro"}})
    for t in split_chunks(sc.get("closing")):
        outro.append({"text": t, "slide": {"kind": "outro"}})
    outro.append({"text": OUTRO_FIXED, "slide": {"kind": "outro"}})
    parts.append({"id": "outro", "title": "다음 편 예고" if ep["next"] else "마무리", "layout": "outro",
                  "scene": LAMB.replace("autumn garden", "garden at sunset"), "chunks": outro})
    if upto:
        parts = parts[:upto]
    plan = {"episode": ep["id"], "ep": ep, "publish": ep["publish"], "question": q, "parts": parts,
            "animals": animals, "title": ep["title"]}
    plan["stats"] = stats(plan)
    return plan


def stats(plan: dict, spec: Spec = SPEC) -> dict:
    chars = sum(len(c["text"]) for p in plan["parts"] for c in p["chunks"])
    gaps = sum(spec.gap_section * max(0, len(p["chunks"]) - 1) for p in plan["parts"]) \
        + spec.gap_part * max(0, len(plan["parts"]) - 1)
    sec = (chars / (spec.cpm / 60.0) + gaps + spec.lead + spec.tail) / spec.tempo
    per = {p["id"]: sum(len(c["text"]) for c in p["chunks"]) for p in plan["parts"]}
    return {"chars": chars, "est_sec": round(sec, 1), "est_min": round(sec / 60.0, 1), "per_part": per,
            "chunks": sum(len(p["chunks"]) for p in plan["parts"]), "parts": len(plan["parts"])}


def target_chars(spec: Spec = SPEC, chunks: int = 75, parts: int = 13) -> tuple[int, int]:
    """예상 길이 범위를 글자 수로(코드 문구 포함) — 검사·안내문이 같은 식을 쓴다."""
    gaps = spec.gap_section * (chunks - parts) + spec.gap_part * (parts - 1) + spec.lead + spec.tail
    f = lambda m: int((m * 60 * spec.tempo - gaps) * spec.cpm / 60.0)  # noqa: E731
    return f(spec.est_min[0]), f(spec.est_min[1])


# ══ 5. 검사 ══════════════════════════════════════════════════════════════════════════════
# 금지어 — 주간 롱폼 BAN(의료·투자·무속·자극) 그대로 + 겁주기·한 해 깎아내리기·게임 말투 · '삼재'는 sal_frame 이 따로 본다
BAN = {k: tuple(w for w in v if w != "삼재") for k, v in WF.BAN.items()}
BAN["겁주는 말"] = BAN["겁주는 말"] + ("큰일", "재앙", "흉하", "흉한", "불길", "액운", "횡액", "무서운", "끔찍", "피할 수 없",
                                     "화를 입", "화를 당", "불행")
BAN["한 해 깎아내리기"] = ("최악", "나쁜 해", "안 좋은 해", "좋지 않은 해", "힘든 해", "힘든 한 해", "되는 일이 없",
                       "운이 없는 해", "흉년", "꽝", "고생만", "불운")
BAN["게임·젊은 말투"] = ("레벨", "만렙", "버프", "너프", "꿀팁", "개꿀", "레전드", "끝판왕", "치트키", "존버", "떡상", "떡락",
                    "인생템", "핵이득", "ㅋㅋ", "ㅎㅎ", "등급표", "급이에요", "티어")
# 실제로 누가 물은 것처럼 쓰지 않는다(질문은 '시청자가 할 법한' 질문이다 — 지어낸 사연·시청자 금지, 10/21 검수)
BAN["지어낸 질문자"] = ("질문 주신", "질문을 주신", "보내 주신", "보내주신", "사연 주신", "여쭤 오신", "여쭤오신", "물어 오신",
                    "물어오신", "댓글로 물어", "댓글 주신")
BAN["요일·날짜 약속"] = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일", "내일", "모레", "다음 주",
                     "이번 주", "매주", "주말에", "저녁 여덟 시", "여덟 시에")
EN_GRADE = re.compile(r"(?<![A-Za-z])[SABCDF]\s?급|에스급|에이급|비급|씨급")
HANJA = re.compile(r"[一-鿿㐀-䶿]")
SPOKEN_OK = WF.SPOKEN_OK
SCREEN_OK = re.compile(r"[가-힣\s.,!?~…'\"“”‘’()\-:·0-9%]")
ANIMAL_RE = re.compile(r"(" + "|".join(sorted(ANIMALS, key=len, reverse=True)) + r")띠")
SINSAL_2027 = ("천살", "화개살", "반안살", "월살")


def ban_hits(text: str) -> list[str]:
    out = []
    for group, words in BAN.items():
        hit = [w for w in words if w in text]
        if group == "의료 조언" and WF.CANCER_RE.search(text):
            hit.append("암")
        if hit:
            out.append(f"{group}: {', '.join(hit)}")
    if EN_GRADE.search(text):
        out.append(f"영문 등급: {EN_GRADE.search(text).group(0)}")
    return out


def routine_units(sc: dict) -> list[tuple[str, str, str]]:
    """(어디, 글, 종류 say|screen) — 루틴이 쓴 모든 칸."""
    out = [("question", _s(sc.get("question")), "say"), ("cold_open", _s(sc.get("cold_open")), "say"),
           ("teaser", _s(sc.get("teaser")), "say"), ("closing", _s(sc.get("closing")), "say")]
    for ch in sc.get("chapters") or []:
        if not isinstance(ch, dict):
            continue
        cid = _s(ch.get("id"))
        for k, s in enumerate(ch.get("say") or []):
            out.append((f"{cid}.say[{k}]", _s(s), "say"))
        for k, p in enumerate(ch.get("points") or []):
            out.append((f"{cid}.points[{k}]", _s(p), "screen"))
        if _s(ch.get("intro")):
            out.append((f"{cid}.intro", _s(ch.get("intro")), "say"))
        for x in ch.get("years") or []:
            if isinstance(x, dict):
                out.append((f"{cid}.{x.get('year')}.say", _s(x.get("say")), "say"))
                out.append((f"{cid}.{x.get('year')}.point", _s(x.get("point")), "screen"))
        for k, x in enumerate(ch.get("qa") or []):
            if isinstance(x, dict):
                out.append((f"{cid}.qa[{k}].q", _s(x.get("q")), "say"))
                out.append((f"{cid}.qa[{k}].a", _s(x.get("a")), "say"))
                out.append((f"{cid}.qa[{k}].point", _s(x.get("point")), "screen"))
    return [(w, t, k) for w, t, k in out if t]


def _rng(errs, where, text, lo_hi):
    lo, hi = lo_hi
    n = len(_s(text))
    if not lo <= n <= hi:
        errs.append(f"{where} {n}자 — {lo}~{hi}자")


def fact_errors(sc: dict, ep: dict) -> list[str]:
    """띠 하나·2027 신살 하나만 나온 문장에서 짝이 틀리면 오류. 삼재 단계도 같은 식(아니·지난·내년이면 넘어간다)."""
    errs = []
    for where, text, kind in routine_units(sc):
        if kind != "say":
            continue
        for sent in sal_frame.units(text):
            an = list(dict.fromkeys(ANIMAL_RE.findall(sent)))
            ss = [s for s in SINSAL_2027 if s in sent]
            if len(an) == 1 and len(ss) == 1 and "아니" not in sent and an[0] in ANIMALS:
                want = sinsal_of(ANIMALS.index(an[0]))
                if ss[0] != want:
                    errs.append(f"{where}: '{an[0]}띠 … {ss[0]}' — 2027년 {an[0]}띠는 {want}이다(사실 오류)")
            st = [s for s in SAMJAE if s in sent]
            if len(an) == 1 and len(st) == 1 and an[0] in ANIMALS and not re.search(r"아니|지난|지나|내년|이천이십팔|끝났", sent):
                want = samjae_stage(ANIMALS.index(an[0]))
                if st[0] != want:
                    errs.append(f"{where}: '{an[0]}띠 … {st[0]}' — 2027년 {an[0]}띠는 "
                                + (f"{want}" if want else "삼재가 아니다") + "(사실 오류)")
    return errs


def check(sc, path: str = "", now: dt.datetime | None = None, history: list | None = None,
          strict: bool = True, spec: Spec = SPEC) -> tuple[list[str], list[str]]:
    """(오류, 경고). 오류가 하나라도 있으면 렌더·업로드하지 않는다.
    strict=False(견본·수동 점검): 날짜(너무 이르다)·파일 이름을 경고로만."""
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(sc, dict):
        return ["대본이 JSON 객체가 아니다"], []
    bad = errs.append
    if _s(sc.get("kind")) != "longform_2027":
        bad(f"kind {sc.get('kind')!r} — 'longform_2027'")
    eid = _s(sc.get("episode"))
    if eid not in BY_ID:
        return errs + [f"episode {eid!r} — E01~E{len(EPISODES):02d} 중 하나(next 명령의 EPISODE)"], warns
    ep = BY_ID[eid]
    now = (now or dt.datetime.now(KST)).astimezone(KST)

    # ① 편·날짜·파일 이름
    if _s(sc.get("publish")) != ep["publish"]:
        bad(f"publish {sc.get('publish')!r} ≠ 편성 {ep['publish']} — 날짜는 코드가 정한다(next 명령의 PUBLISH)")
    when = publish_dt(ep)
    if when - now > dt.timedelta(days=8):
        (bad if strict else warns.append)(f"{eid} 공개({ep['publish']})가 8일 넘게 남았다 — 며칠 앞 편만 쓴다(next 명령)")
    if when < now + dt.timedelta(minutes=90):
        warns.append(f"{eid} 공개 시각({ep['publish']} {PUBLISH_HHMM})이 90분 안이거나 지났다 — 렌더가 끝나면 바로 공개된다")
    if path:
        name = os.path.basename(path)
        if name != file_name(ep) and os.path.abspath(path) != os.path.abspath(SAMPLE):
            (bad if strict else warns.append)(f"파일 이름 {name!r} — {file_name(ep)} 이어야 한다(next 명령의 FILE)")

    # ② 장 — 순서·꼴·칸
    want = ep["chapters"]
    chs = sc.get("chapters") if isinstance(sc.get("chapters"), list) else []
    got_ids = [_s(c.get("id")) if isinstance(c, dict) else "" for c in chs]
    if got_ids != [c["id"] for c in want]:
        bad(f"chapters id 순서 {got_ids} ≠ {[c['id'] for c in want]} — 장 순서·개수는 코드가 정한다(뼈대 그대로)")
    if len(want) < spec.chapters_min:
        bad(f"장이 {len(want)}개 — {spec.chapters_min}개 이상(카탈로그 오류)")
    f = spec.field
    q = _s(sc.get("question"))
    _rng(errs, "question", q, f["question"])
    if q and not q.endswith("?"):
        bad("question 은 시청자 질문 한 문장 — 물음표(?)로 끝낸다")
    _rng(errs, "cold_open", sc.get("cold_open"), f["cold_open"])
    _rng(errs, "teaser", sc.get("teaser"), f["teaser"])
    _rng(errs, "closing", sc.get("closing"), f["closing"])
    teaser = _s(sc.get("teaser"))
    if ep["next"] and "다음 편" not in teaser:
        bad("teaser 에 '다음 편' 이 없다 — 다음 편 예고는 '다음 편'으로 말한다(요일·날짜 약속 없이)")
    shape_ok = got_ids == [c["id"] for c in want]
    for c, cp in zip(chs, want) if shape_ok else []:
        cid, lay = cp["id"], cp["layout"]
        if lay == "card":
            says = [x for x in c.get("say") or [] if _s(x)]
            pts = [x for x in c.get("points") or [] if _s(x)]
            lo, hi = spec.counts["card_say"]
            if not lo <= len(says) <= hi:
                bad(f"{cid}({cp['title']}) say {len(says)}단락 — {lo}~{hi}단락")
            lo, hi = spec.counts["card_points"]
            if not lo <= len(pts) <= hi:
                bad(f"{cid} points {len(pts)}줄 — 화면 요점 {lo}~{hi}줄")
            for k, s in enumerate(says):
                _rng(errs, f"{cid}.say[{k}]", s, f["say"])
            for k, p in enumerate(pts):
                _rng(errs, f"{cid}.points[{k}]", p, f["point"])
        elif lay in ("table", "lucky"):
            says = [x for x in c.get("say") or [] if _s(x)]
            lo, hi = spec.counts[f"{lay}_say"]
            if not lo <= len(says) <= hi:
                bad(f"{cid}({cp['title']}) say {len(says)}단락 — {lo}~{hi}단락(화면 표는 코드가 그린다)")
            for k, s in enumerate(says):
                _rng(errs, f"{cid}.say[{k}]", s, f["say"])
        elif lay == "years":
            lines = [x for x in c.get("years") or [] if isinstance(x, dict)]
            ys = []
            for x in lines:
                try:
                    ys.append(int(x.get("year")))
                except (TypeError, ValueError):
                    ys.append(None)
            if ys != cp["years"]:
                bad(f"{cid}({cp['animal']}띠) years {ys} ≠ {cp['years']} — 출생연도는 코드가 정한다(빠짐·순서 없이 전부)")
            for x in lines:
                _rng(errs, f"{cid}.{x.get('year')}.say", x.get("say"), spec.year_line)
                _rng(errs, f"{cid}.{x.get('year')}.point", x.get("point"), f["point"])
            _rng(errs, f"{cid}.intro", c.get("intro"), f["intro"])
        elif lay == "qa":
            items = [x for x in c.get("qa") or [] if isinstance(x, dict)]
            lo, hi = spec.counts["qa"]
            if not lo <= len(items) <= hi:
                bad(f"{cid} qa {len(items)}개 — {lo}~{hi}개")
            for k, x in enumerate(items):
                _rng(errs, f"{cid}.qa[{k}].q", x.get("q"), f["q"])
                _rng(errs, f"{cid}.qa[{k}].a", x.get("a"), f["a"])
                _rng(errs, f"{cid}.qa[{k}].point", x.get("point"), f["point"])
                if _s(x.get("q")) and not _s(x.get("q")).endswith("?"):
                    bad(f"{cid}.qa[{k}].q 는 질문 — 물음표(?)로 끝낸다")

    # ③ 글자 · 금지어 · 살 조언 틀 · 한자
    for where, text, kind in routine_units(sc):
        ok_re = SPOKEN_OK if kind == "say" else SCREEN_OK
        bc = sorted({ch for ch in text if not ok_re.fullmatch(ch)})
        if bc:
            bad(f"{where}: 쓸 수 없는 글자 {' '.join(repr(x) for x in bc[:6])} — "
                + ("말에는 숫자도 한글로(유월·시월·세 가지 · 연도는 코드가 읽는다), 영어·한자·이모지 없이" if kind == "say"
                   else "화면 요점은 한글·숫자·문장부호만(영어·한자 없이)"))
        for h in ban_hits(text):
            bad(f"{where}: 금지어({h})")
        isq = where == "question" or where.endswith(".q")
        for v in sal_frame.violations(text, unit="sentence" if kind == "say" else "whole", question=isq):
            bad(f"{where}: {v}")
    for v in sal_frame.violations(ep["title"], unit="whole"):
        bad(f"제목(카탈로그): {v}")

    # ④ 사실(띠 ↔ 신살 · 삼재 단계)
    errs += fact_errors(sc, ep)

    # ⑤ 반복 — 같은 대본 안 · 지난 대본·견본
    units = [(w, t) for w, t, k in routine_units(sc) if k == "say" and len(t) >= 40]
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            if WF.similarity(units[i][1], units[j][1]) >= spec.similar:
                bad(f"{units[i][0]} 와 {units[j][0]} 가 거의 같다 — 단락마다 다르게 쓴다")
    for old in history or []:
        if _s(old.get("episode")) == eid:
            continue
        src = "견본(E01)" if old.get("_sample") else _s(old.get("episode")) or "지난 대본"
        ou = [(w, t) for w, t, k in routine_units(old) if k == "say" and len(t) >= 40]
        for w, t in units:
            for ow, otx in ou:
                if WF.similarity(t, otx) >= spec.history_similar:
                    bad(f"{w} 가 {src} 의 {ow} 와 거의 같다 — 편마다 새로 쓴다(견본 옮기기 금지)")
                    break

    # ⑥ 길이 — 장마다 · 전체(모양이 맞으면 다른 오류가 있어도 잰다 — 루틴이 한 번에 다 고치게)
    if shape_ok:
        plan = compose(sc)
        st = plan["stats"]
        for p, cp in zip(plan["parts"][1:-1], want):
            n = st["per_part"][p["id"]]
            rng = spec.chapter_chars[cp["layout"]]
            if cp["layout"] == "years":
                k = len(cp["years"])
                rng = (spec.year_line[0] * k, spec.year_line[1] * k + 260)
            if not rng[0] <= n <= rng[1]:
                bad(f"{p['id']}({cp['title']}) 장이 {n}자 — 코드 문구 포함 {rng[0]}~{rng[1]}자")
        lo, hi = spec.est_min
        if not lo <= st["est_min"] <= hi:
            a, b = target_chars(spec, st["chunks"], st["parts"])
            bad(f"예상 길이 {st['est_min']}분({st['chars']:,}자) — {lo:.0f}~{hi:.0f}분(이 대본 조각 수로는 {a:,}~{b:,}자)")
    return errs, warns


def check_duration(sec: float | None, spec: Spec = SPEC) -> str | None:
    if sec is None:
        return None
    lo, hi = spec.render_min
    if not lo * 60 <= sec <= hi * 60:
        return f"렌더 길이 {sec / 60:.1f}분 — {lo:.0f}~{hi:.1f}분 밖(합성이 깨졌을 수 있다)"
    return None


# ══ 6. 이력 · 다음 편 ════════════════════════════════════════════════════════════════════
def _git(*args: str, root: str | None = None) -> str:
    try:
        r = subprocess.run(["git", "-C", root or ROOT, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def fetch_branch(root: str | None = None) -> None:
    _git("fetch", "-q", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", root=root)


def scripts_on_branch(root: str | None = None) -> dict:
    """원격 데이터 브랜치의 {편: 대본} — 루틴이 main + 한 장으로 강제 push 하니 보통 가장 최근 한 편만 있다."""
    out, ref = {}, f"origin/{BRANCH}"
    for name in _git("ls-tree", "-r", "--name-only", ref, "--", OUT_DIR, root=root).splitlines():
        m = NAME_RE.match(os.path.basename(name.strip()))
        if not m:
            continue
        try:
            sc = json.loads(_git("show", f"{ref}:{name.strip()}", root=root) or "null")
        except json.JSONDecodeError:
            continue
        if isinstance(sc, dict):
            out[m.group(1)] = sc
    return out


def load_history(root: str | None = None, dirs=()) -> list[dict]:
    by = dict(scripts_on_branch(root))
    for d in dirs or ():
        if d and os.path.isdir(d):
            for n in sorted(os.listdir(d)):
                m = NAME_RE.match(n)
                if m:
                    try:
                        with open(os.path.join(d, n), encoding="utf-8") as fp:
                            sc = json.load(fp)
                    except (OSError, json.JSONDecodeError):
                        continue
                    if isinstance(sc, dict):
                        by.setdefault(m.group(1), sc)
    hist = [by[k] for k in sorted(by)]
    try:
        with open(SAMPLE, encoding="utf-8") as fp:
            hist.append({**json.load(fp), "_sample": True})
    except (OSError, json.JSONDecodeError):
        pass
    return hist


def check_file(path: str, now: dt.datetime | None = None, root: str | None = None,
               strict: bool = True) -> tuple[list[str], list[str], dict]:
    with open(path, encoding="utf-8") as fp:
        sc = json.load(fp)
    hist = load_history(root, dirs=[os.path.join(root or ROOT, OUT_DIR), os.path.dirname(os.path.abspath(path))])
    errs, warns = check(sc, path, now=now, history=hist, strict=strict)
    return errs, warns, sc


MIN_LEAD = dt.timedelta(hours=3)        # 렌더(~45분)·실행기 대기를 넉넉히
MAX_AHEAD = dt.timedelta(hours=84)      # 3.5일 — 루틴(월·수·토 10시)은 이틀 반 앞 편 하나만 · 한 번 놓치면 다음 회차에 둘(MORE=1)


def pending(now: dt.datetime | None = None, last_pushed: str | None = None) -> list[dict]:
    """지금 써야 할 편들(가까운 순) — 공개가 3시간~3.5일 남았고, 데이터 브랜치에 마지막으로 올라간 편보다 뒤."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    out = []
    for ep in EPISODES:
        if last_pushed and ep["id"] <= last_pushed:
            continue
        when = publish_dt(ep)
        if now + MIN_LEAD <= when <= now + MAX_AHEAD:
            out.append(ep)
    return out


def skeleton(ep: dict) -> dict:
    chs = []
    for c in ep["chapters"]:
        lay = c["layout"]
        x = {"id": c["id"], "_title": c["title"], "_layout": lay}
        if lay == "card":
            x.update(say=["<단락 30~300자 · 2~5단락>"], points=["<화면 요점 4~24자 · 2~4줄>"])
        elif lay in ("table", "lucky"):
            x.update(say=["<표를 짚어 주는 말 30~300자 · 1~4단락>"])
        elif lay == "years":
            x.update(intro="<선택 · 0~200자>", years=[{"year": y, "say": "<60~240자 · 이 해에 태어난 분께>",
                                                       "point": "<화면 한 줄 4~24자>"} for y in c["years"]])
        elif lay == "qa":
            x.update(qa=[{"q": "<시청자 질문 10~80자?>", "a": "<답 80~340자>", "point": "<화면 답 요약 4~24자>"}])
        chs.append(x)
    return {"kind": "longform_2027", "episode": ep["id"], "publish": ep["publish"],
            "question": "<시청자 질문 한 문장 12~70자 · 물음표로 끝>", "cold_open": "<150~380자>",
            "chapters": chs, "teaser": "<50~240자 · '다음 편' 포함 · 요일·날짜 약속 없이>", "closing": "<선택 · 0~160자>"}


def next_text(now: dt.datetime | None = None, root: str | None = None) -> str:
    import tempfile
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    on = scripts_on_branch(root)
    last = max(on) if on else None
    todo = pending(now, last)
    lines = [f"NOW={now.strftime('%Y-%m-%d %H:%M')} KST", f"LAST_PUSHED={last or '-'}", f"BRANCH={BRANCH}"]
    if not todo:
        nxt = next((e for e in EPISODES if (not last or e["id"] > last) and publish_dt(e) > now), None)
        lines.append("EPISODE=NONE")
        lines.append("오늘 쓸 편이 없다 — 그대로 끝낸다." + (
            f" (다음 편 {nxt['id']} 은 {nxt['publish']} 공개 — 사흘 반 안에 들어오면 쓴다)" if nxt else " (16편 끝)"))
        return "\n".join(lines)
    ep = todo[0]
    out_dir = os.path.join(tempfile.gettempdir(), "fortune_lf27")
    os.makedirs(out_dir, exist_ok=True)
    when = publish_dt(ep)
    lines += [f"EPISODE={ep['id']}", f"PUBLISH={ep['publish']} {PUBLISH_HHMM} KST ({ep['weekday']})",
              f"FILE={OUT_DIR}/{file_name(ep)}", f"WRITE_TO={os.path.join(out_dir, file_name(ep))}",
              f"MORE={len(todo) - 1}", f"HOURS_LEFT={int((when - now).total_seconds() // 3600)}",
              f"TITLE={ep['title']}"]
    if ep["id"] == "E01" and os.path.exists(SAMPLE):
        lines.append(f"READY={os.path.relpath(SAMPLE, ROOT)}  ← 이 편은 견본이 곧 대본이다: WRITE_TO 로 복사 → check → push")
    lo, hi = target_chars()
    lines += ["", f"── 이 편(카탈로그 {os.path.relpath(CATALOG_PATH, ROOT)} 의 {ep['id']}) ──",
              f"각도: {ep['angle']}", "질문 씨앗(골라 쓰거나 바꿔 쓴다): " + " / ".join(ep["qa_seeds"]),
              f"다음 편: {ep['next_title'] or '없음(마지막 편 — teaser 는 재생목록 안내로)'}",
              "", "── 분량(코드가 검사) ──",
              f"전체 예상 {SPEC.est_min[0]:.0f}~{SPEC.est_min[1]:.0f}분 ≈ 코드 문구 포함 {lo:,}~{hi:,}자 · 장 {len(ep['chapters'])}개 + 시작·예고",
              "card: say 2~5단락(30~300자) + points 2~4줄(4~24자) · table/lucky: say 1~4단락 · "
              "years: 해마다 say 60~240자 + point · qa: 2~4개(q 10~80자? · a 80~340자 · point)",
              "", "── 사실(옮겨 적기만 · 바꾸지 않는다) ──"]
    lines.append(json.dumps({"year": year_facts(), "ddi": ep_facts(ep)}, ensure_ascii=False, indent=1))
    lines += ["", "── 뼈대(채워서 WRITE_TO 에 저장 → check → push · _title/_layout 은 지워도 된다) ──",
              json.dumps(skeleton(ep), ensure_ascii=False, indent=1)]
    return "\n".join(lines)


# ══ 7. 업로드 메타 ════════════════════════════════════════════════════════════════════════
def marker(eid: str) -> str:
    return f"{MARKER} {eid}"


def title_for(plan: dict) -> str:
    return plan["ep"]["title"][:100]


def tags_for(ep: dict) -> list[str]:
    tags = ["2027년 운세", "2027 운세", "정미년 운세", "2027 신년운세", "띠별 운세", "출생연도별 운세"]
    for a in ep["animals"]:
        tags += [f"2027년 {a}띠 운세", f"{a}띠 운세"]
    tags.append(f"2027 {ep['sinsal']}")
    if ep["samjae"] or any(samjae_stage(ANIMALS.index(a)) for a in ep["animals"]):
        tags += ["2027 삼재", "날삼재"]
    for a in ep["animals"]:
        tags += [f"{yy(y)}년생 운세" for y in ddi_years(a, 1940, 1999)]
    out, total = [], 0
    for t in dict.fromkeys(tags):
        if total + len(t) + 1 > 480:
            break
        out.append(t)
        total += len(t) + 1
    return out


def hashtags(ep: dict) -> str:
    hs = ["#2027운세", "#정미년", f"#{ep['sinsal']}"] + [f"#{a}띠운세" for a in ep["animals"]] + ["#띠별운세"]
    return " ".join(dict.fromkeys(hs))


def description_for(plan: dict, chapters: str, sc: dict | None = None) -> str:
    ep = plan["ep"]
    sc = sc or {}
    q = _s(sc.get("question"))
    if ep["kind"] == "group":
        head = f"{ep['search']} — 겁낼 것 없이 {josa(ep['thumb']['pill'], '과', '와')} 출생연도별 풀이를 차근차근 정리했어요."
    else:
        head = (f"{ep['search']} — 총운·재물·건강·가정, 좋은 달과 조심할 달, 출생연도별 풀이까지 "
                f"한 번에 정리했어요.")
    first = f"“{q}” — 이런 질문에, 미리 알고 준비하는 법으로 답해 드려요." if q else ""
    qa_lines = []
    for ch in sc.get("chapters") or []:
        for x in (ch.get("qa") or []) if isinstance(ch, dict) else []:
            if isinstance(x, dict) and _s(x.get("q")):
                qa_lines.append(f"Q. {_s(x.get('q'))}\nA. {_s(x.get('point')) or _s(x.get('a'))[:60]}")
    lucky = []
    for a in ep["animals"]:
        lk = ddi_facts(a)["lucky"]
        lucky.append(f"· {a}띠({years_label(a)}): {lk['colors']} · 숫자 {lk['numbers']} · {lk['direction']}")
    tease = (f"📌 다음 편: {ep['next_title']}\n▶ 재생목록 '{PLAYLIST}'에서 이어서 보세요." if ep["next"]
             else f"▶ 재생목록 '{PLAYLIST}'에서 다른 띠 편도 보세요.")
    ny = year_facts()["next_year"]
    nxt = (f"🔭 2028년(무신년) 미리 보기: {'·'.join(a + '띠' for a in ny['samjae_starts'])}는 들삼재가 시작돼요 — "
           "미리 알고 준비하면 걱정 없어요.")
    basis = ("🧭 이렇게 풀었어요: 2027년은 정미(丁未)년 — 천간 정(丁) 불 · 지지 미(未) 흙(양띠 해). 십이신살은 삼합 기준 "
             "(신자진 = 천살 · 해묘미 = 화개살 · 인오술 = 반안살 · 사유축 = 월살) · 삼재는 해묘미 띠의 날삼재 · "
             f"대장군 {daejanggun()} · 삼살 {samsal()} · 좋은 달은 절기로 나눈 양력 달이에요. "
             "이름에 겁먹지 마시고, 어떻게 지내면 좋은지를 참고하세요.")
    parts = [head, first, "",
             f"⏱ 목차\n{chapters}", ""]
    if qa_lines:
        parts += ["❓ 자주 묻는 질문", "\n".join(qa_lines[:4]), ""]
    parts += ["🍀 행운의 색 · 숫자 · 방향", "\n".join(lucky), "", tease, nxt, "", basis, "",
              birth_basis.ddi_note(1940, 2009), "", DISCLAIMER, CREDIT, "", hashtags(ep), "", marker(ep["id"])]
    desc = "\n".join(parts)
    if len(desc) > 4900:                      # 목차·표식은 지키고 질문을 줄인다
        desc = desc.replace("\n".join(qa_lines[:4]), "\n".join(qa_lines[:2]))
    return desc[:4900]


def already_uploaded(uploads: list[dict], eid: str) -> str | None:
    mk = marker(eid)
    for u in uploads or []:
        d = u.get("description") or ""
        if re.search(re.escape(mk) + r"(?!\d)", d):
            return u.get("video_id") or "?"
    return None


def link_series(now: dt.datetime | None = None) -> bool:
    """쇼츠 설명란 링크를 이 시리즈로 바꿀 때인가(첫 편 공개 뒤)."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    return now >= publish_dt(EPISODES[0]) and os.environ.get("LF27_LINK", "1") not in ("0", "false", "off")


def link_line(video_id: str) -> str:
    return f"📺 {SERIES}(띠별 13분 풀이 · 출생연도별): https://youtu.be/{video_id}"


def append_link(description: str, video_id: str | None) -> str:
    if not video_id or f"youtu.be/{video_id}" in (description or ""):
        return description
    return f"{(description or '').rstrip()}\n\n{link_line(video_id)}"


# ══ 8. 카탈로그 ══════════════════════════════════════════════════════════════════════════
def build_catalog() -> dict:
    eps = []
    for ep in EPISODES:
        e = {k: ep[k] for k in ("id", "publish", "weekday", "kind", "group", "animals", "sinsal", "samjae", "title",
                                "search", "thumb", "angle", "qa_seeds", "next", "next_title")}
        e["publish_kst"] = f"{ep['publish']} {PUBLISH_HHMM}"
        e["chapters"] = [{k: v for k, v in c.items()} for c in ep["chapters"]]
        e["facts"] = ep_facts(ep)
        eps.append(e)
    return {"about": ("'2027 정미년 깊이 보기' 롱폼 16편 카탈로그 — pipeline/longform_2027.py 가 만든다(손으로 고치지 않는다: "
                      "python pipeline/longform_2027.py catalog --write). 사실은 전통 명리 계산(재미로 보는 운세): "
                      "십이신살 = 띠의 삼합 그룹 지살부터 겁살·재살·천살·지살·년살·월살·망신살·장성살·반안살·역마살·육해살·화개살 · "
                      "삼재 = 역마·육해·화개 해(들·눌·날) · 대장군 사오미년 동쪽 · 삼살 해묘미년 서쪽 · "
                      "좋은 달은 절기로 나눈 양력 달(월건 · 1월 축 … 12월 자)."),
            "series": SERIES, "playlist": PLAYLIST, "schedule": "2026-11-02부터 월·수·금 20:00 KST",
            "branch": BRANCH, "year": year_facts(), "sinsal_table_2027": table_sinsal12(), "episodes": eps}


def catalog_json() -> str:
    return json.dumps(build_catalog(), ensure_ascii=False, indent=1) + "\n"


def show_text(eid: str) -> str:
    ep = episode(eid)
    return json.dumps({k: v for k, v in build_catalog()["episodes"][int(eid[1:]) - 1].items()},
                      ensure_ascii=False, indent=1) if ep else ""


def schedule_text() -> str:
    lines = []
    for ep in EPISODES:
        lines.append(f"{ep['id']}  {ep['publish']}({ep['weekday']}) {PUBLISH_HHMM}  {ep['title']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="2027 정미년 깊이 보기 — 편성·사실·검사(루틴용)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next", help="이번에 쓸 편 · 공개 시각 · 사실 · 뼈대")
    n.add_argument("--date", help="기준 날짜(KST, YYYY-MM-DD 또는 ISO 시각) — 기본 지금")
    n.add_argument("--no-fetch", action="store_true")
    c = sub.add_parser("check", help="대본 검사(루틴은 push 전에 반드시)")
    c.add_argument("paths", nargs="+")
    c.add_argument("--date", help="기준 시각 — 테스트용")
    c.add_argument("--lenient", action="store_true", help="견본·수동 점검: 날짜·파일 이름을 경고로")
    c.add_argument("--no-fetch", action="store_true")
    s = sub.add_parser("show", help="한 편의 사실·장 계획")
    s.add_argument("--episode", required=True)
    sub.add_parser("schedule", help="16편 날짜·제목")
    k = sub.add_parser("catalog", help="카탈로그 JSON(--write 면 파일로)")
    k.add_argument("--write", action="store_true")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    def when(v):
        if not v:
            return dt.datetime.now(KST)
        if len(v) == 10:
            return dt.datetime.combine(dt.date.fromisoformat(v), dt.time(10, 0), tzinfo=KST)
        t = dt.datetime.fromisoformat(v)
        return t if t.tzinfo else t.replace(tzinfo=KST)

    if a.cmd == "schedule":
        print(schedule_text())
        return 0
    if a.cmd == "show":
        print(show_text(a.episode))
        return 0
    if a.cmd == "catalog":
        if a.write:
            with open(CATALOG_PATH, "w", encoding="utf-8", newline="\n") as fp:
                fp.write(catalog_json())
            print(f"✅ {CATALOG_PATH}")
        else:
            print(catalog_json())
        return 0
    if not a.no_fetch:
        fetch_branch()
    if a.cmd == "next":
        print(next_text(when(a.date)))
        return 0
    bad = 0
    for p in a.paths:
        errs, warns, sc = check_file(p, now=when(a.date), strict=not a.lenient)
        st = compose(sc)["stats"] if not errs else None
        print(f"── {os.path.basename(p)} · {sc.get('episode')}"
              + (f" · {st['chars']:,}자 · 조각 {st['chunks']} · 예상 {st['est_min']}분" if st else ""))
        for x in warns:
            print(f"   ⚠️ {x}")
        for e in errs:
            print(f"   ❌ {e}")
        if not errs:
            print("   ✅ 통과")
        bad += len(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
