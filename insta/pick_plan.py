#!/usr/bin/env python3
"""인스타 릴스 편성·게시 — 날짜·편(slot)으로 꼴을 정하고(로테이션), 편마다 한 번만 올린다 (2026-10-07).

편성(코드가 정한다 — 쓰는 쪽이 고르지 않는다):
  '오늘의 골라보기' FORMATS 를 START 부터 한 편씩 돌린다: 10/8 그림 고르기 → 10/9 상식 퀴즈 → 10/10 타로 카드 → 10/11 밸런스 게임
  → 10/12 태어난 달 표 (여기까지 하루 한 편 = 저녁 편 b · 같은 꼴 연달아 금지 — 왕별이 10/7 교훈)
  ★10/11 사용자 "하루 2편 이상" → TWICE_FROM(10/13)부터 하루 두 편: 낮 편 a(12시대) · 저녁 편 b(7~8시대, 예전 그 자리).
    로테이션은 끊기지 않고 이어진다: 10/13 a 그림 고르기 · b 상식 퀴즈 → 10/14 a 타로 · b 밸런스 → 10/15 a 태어난 달 …
  ★10/14 sci(도파민 과학 — 심해·우주·극한 생존) 2주 시험 SCI_FROM(10/15)~SCI_TO(10/28 → ★10/20 11/07 연장): 하루 두 편 중 한 편은 sci,
    다른 편은 골라보기 다음 꼴. sci 편은 날마다 저녁·낮을 번갈아 든다(10/15 b · 10/16 a · 10/17 b … — 시간대 치우침 없이 비교).
    골라보기 로테이션은 sci 를 건너뛰고 하루 한 꼴씩 그대로 이어진다(10/15 a 태어난 달 → 10/16 b 그림 고르기 → 10/17 a 퀴즈 …).
    sci 내용은 SCI_ORDER[k](k = 10/15부터 몇 번째 sci 편) = shorts_catalog 의 n(901~ 은 insta/sci_extra.json).
  ★10/20 sci 연장(SCI_TO 11/07) + 병맛(bm) 2주 시험 BM_FROM(10/25)~BM_TO(11/07): sci 가 아닌 편이 골라보기 대신 병맛이다.
    꼴은 ABBA ABBA ABBA AB: BM_FROM 부터 i 번째 날 i%4 가 0·3 이면 bm_paper(A '이거 진짜 논문임'), 1·2 면 bm_animal(B '정색 동물 다큐')
    — 7편씩. sci 가 짝수 날 저녁이라 병맛은 짝수 날 낮·홀수 날 저녁 → A 낮 4·저녁 3, B 낮 3·저녁 4(시간대가 한쪽에 몰리지 않게).
    무엇을 쓸지도 코드가 정한다: BM_ORDER[i] = insta/bm_catalog.json 의 n(사실·출처는 미리 확인 — 클라우드 작가는 웹을 못 본다).
    골라보기 로테이션은 그동안 쉬고, 11/08부터 다음 꼴로 이어진다(회차 series_no 도 골라보기만 이어서 센다 · bm·sci 는 None).
    11/08부터 다시 골라보기 두 편. 10/24 까지 꼴·회차·sci 순서는 그대로다(테스트가 못 박는다).
  ★10/24 sci 모양 바꿈 SCI_XRAY_FROM(10/25 저녁)~: '속이 보이는 과학'(투시·단면 3D + 원인 3단계) — 주제·편성은 그대로(sci_xray).
  ★10/25 sci 끝없이(사용자 "잘 되는 건 단발로 끝내지 말고 계속 돌게"): SCI_TO 는 더 이상 끝이 아니다 — 11/08(SCI_OPEN_FROM)부터도
    sci 는 같은 자리(날마다 저녁·낮 번갈아)로, 안 쓴 항목이 남아 있는 동안 이어진다(open_plan · src_n 은 한 번씩만).
    항목 = insta/sci_extra.json 의 SCI_ORDER 밖 항목(904~) + shorts_catalog 의 insta_from 단 항목, (from, n) 순서.
    바닥나면 그날은 11/08 처럼 골라보기 두 편(runway 0 — tools/runway.py · 맥박이 14일 전부터 알린다).
    ★11/09~ '과학으로 뜯어보는 물건'(teardown — 생활 물건을 cutaway 단면으로): 화·금 sci 자리는 insta/teardown_catalog.json
    항목(951~ · 주 2편), 다른 날은 보통 sci. 뜯어보기 항목이 없거나 바닥나면 그날도 보통 sci(그것도 없으면 골라보기).
    ★새 항목은 끝에 붙이고 from(쓸 수 있는 첫날)을 '붙이는 날 다음 날 이후'로 단다 — 그래야 지난 날 편성(회차·src_n)이 안 바뀐다
    (from 없는 열린 항목은 편성하지 않는다 · test_pick 이 막는다).
  (같은 날 두 편은 늘 다른 꼴 — 그래서 꼴만 보면 그날 어느 편인지 하나로 정해진다: slot_of)
  회차 번호는 골라보기 편만 센다: 10/8 = '오늘의 골라보기 #1' · 10/12 = #5 · 10/13 낮 = #6 · 10/13 저녁 = #7 (series_no · sci 는 None)
  어느 편 차례인지(due_slot)도 코드가 정한다: KST NOON_UNTIL(16)시 전이면 낮 편, 뒤면 저녁 편.
  쓰레드(pick_threads)는 그날 골라보기 편만 따라간다(sci·병맛은 안 간다) — 쓰레드 2주 시험(10/11~10/24) 조건을 그대로 두려고.
흐름:
  ① 대본 작가 — 클라우드 루틴(11:50 낮 편 · 19:50 저녁 편 대타) 또는 로컬 예약 작업(insta-pick-daily, 19:20 저녁 편, 크롬 서칭)이
     `next` 가 알려 준 편·꼴로 대본 JSON 을 쓴다(`writing` 파일을 따른다: 골라보기 PICK_WRITING · sci SCI_WRITING · 병맛 BM_WRITING)
     → `pick_reel.py check` → routine/insta_pick 에 push
  ② insta-pick.yml(Actions) — 코드는 main, 대본은 routine/insta_pick 의 오늘 파일 중 가장 늦은 편 → 렌더 → `post` 로 인스타 릴스 게시
게시 막기: 레포 변수 INSTA_PICK_PUBLISH=0 (기본: push 로 온 오늘 대본은 올린다 — 사용자 10/8 "매일 올려줘")

    python insta/pick_plan.py next [--date 2026-10-13] [--slot a|b]   # 지금 차례인 편·꼴·파일 이름·견본·최근 주제(sci 는 catalog 항목)
    python insta/pick_plan.py targets [--date …]             # 오늘 대본 중 가장 늦은 편 하나(워크플로가 쓴다)
    python insta/pick_plan.py post <script.json>             # 렌더 결과를 게시(INSTA_PICK_PUBLISH=1 일 때만 실제로)
"""
from __future__ import annotations

import argparse
import bisect
import contextlib
import datetime as dt
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

FORMATS = ("pick", "quiz", "card", "balance", "birth")
START = dt.date(2026, 10, 8)
TWICE_FROM = dt.date(2026, 10, 13)       # 10/11 사용자 "하루 2편 이상" — 이날부터 낮(a)·저녁(b) 두 편
SLOTS = ("a", "b")
SLOT_LABEL = {"a": "낮 편(12시대)", "b": "저녁 편(7~8시대)"}
NOON_UNTIL = 16                          # KST 이 시각 전에 부르면 낮 편 차례, 뒤면 저녁 편 차례
KST = dt.timezone(dt.timedelta(hours=9))
SCRIPTS = os.path.join(ROOT, "output", "insta_pick")
RENDERS = os.path.join(ROOT, "output", "insta_pick_render")
LEDGER = os.path.join(RENDERS, "posted.json")
EXEMPLAR = {"pick": "pick_door", "card": "pick_card", "quiz": "pick_quiz", "balance": "pick_balance", "birth": "pick_birth"}
LABEL = {"pick": "그림 고르기 심리테스트", "card": "타로 카드 고르기", "quiz": "상식 퀴즈", "balance": "밸런스 게임",
         "birth": "태어난 달 표", "sci": "도파민 과학(심해·우주·극한 생존)",
         "bm_paper": "병맛 A — 이거 진짜 논문임(황당 연구 + 진짜 숫자)", "bm_animal": "병맛 B — 정색 동물 다큐(사람 일 하는 동물)"}
# ★10/14 sci 2주 시험 — 인스타 검색 '심해' 상위 릴스 620만·370만·225만·210만·190만(전부 과학 호기심 계정, 10/14)
SCI = "sci"
SCI_FROM = dt.date(2026, 10, 15)         # 첫날(KST) — 이날 저녁 편부터
SCI_TO = dt.date(2026, 11, 7)            # SCI_ORDER 마지막 날(KST, 포함) · ★10/20 10/28 → 11/07 연장(24일) · ★10/25 끝이 아니다 — 뒤는 open_plan
# k번째 sci 편 = shorts_catalog n(앞 14개 = 10/15~10/28 그대로) · 10/29~ 안 쓴 catalog 7개 → sci_extra.json 3개(901~)
SCI_ORDER = (101, 201, 107, 102, 203, 104, 202, 105, 206, 109, 205, 103, 207, 106,
             108, 110, 111, 112, 113, 114, 204, 901, 902, 903)
SCI_EXEMPLAR = "insta/samples/sci_mariana.json"
SCI_WRITING = "insta/SCI_WRITING.md"
# ★10/24 sci → '속이 보이는 과학'(사용자 승인 10/24) — 벤치마크: so.thats.how 'Dishwasher' 3D 단면 808만 · 해외 건강 쇼츠
#   투명 피부 3D 사람(첫 달 1,000만, 0~6초 대조 훅 → '왜?' → 원인 3단계 → 결과). 이날부터 sci 대본은 훅 → 왜? → 박자 정확히 3개
#   (1/3·2/3·3/3) → 판정, 박자마다 view(xray 투시 · cutaway 단면 · scene)로 그린다(검사·렌더 insta/sci_xray.py).
#   주제·편성(SCI_ORDER·sci_slot)은 그대로 · 이 날짜 전 대본은 옛 모양(박자 4~6개 · 어두운 실사) 그대로 검사·렌더한다.
SCI_XRAY_FROM = dt.date(2026, 10, 25)    # 10/25 저녁 sci 편부터
SCI_XRAY_EXEMPLAR = "insta/samples/sci_xray_heaviest-life.json"   # 10/25 저녁 편(205) 실제 견본 — 그날은 그대로 복사해도 된다
SCI_XRAY_VIEWS = ("xray", "cutaway", "scene")   # 투시(몸속 뼈·장기) · 단면(기계·행성·바다 층을 잘라 연 모습) · 그냥 장면(대체)
SCI_XRAY_SEC = (20.0, 35.0)              # 전체 길이(초) — 렌더가 맞춘다(길면 말을 조금 빠르게 · 짧으면 끝 화면을 늘린다)
SHORTS = os.path.join(ROOT, "gumiho", "tales", "shorts_catalog.json")   # 영어 쇼츠 survival·compare — 출처 달린 사실(facts)
SCI_EXTRA = os.path.join(HERE, "sci_extra.json")                         # 인스타 sci 전용 추가 주제(n ≥ 901, 같은 모양)
# ★10/25 끝없는 sci(open_plan) — SCI_TO 다음 날부터 안 쓴 항목이 남아 있는 동안 같은 자리로 이어진다
SCI_OPEN_FROM = SCI_TO + dt.timedelta(days=1)                            # 11/08
SCI_OPEN_N0 = 904                                                        # 새 sci_extra 항목 번호(904~950)
TEARDOWN = "teardown"                                                    # 항목 series 값 · open_plan 의 줄기 이름
TEARDOWN_SERIES = "과학으로 뜯어보는 물건"
TEARDOWN_FROM = dt.date(2026, 11, 9)                                     # 이 주부터 화·금(첫 편 11/10 화)
TEARDOWN_DAYS = (1, 4)                                                   # 화·금(월=0)
TEARDOWN_CATALOG = os.path.join(HERE, "teardown_catalog.json")           # sci_extra 와 같은 모양 · n 951~ · cutaway 로 속을 연다
TEARDOWN_N0 = 951
OPEN_MAX_DAYS = 3660                                                     # 편성 걷기 상한(from 을 먼 미래로 잘못 단 항목이 있어도 끝난다)
# ★10/20 병맛(bm) 2주 시험 — 골라보기 자리를 바꾼다(10/15~10/20 sci 중앙값 약 440 vs 골라보기 약 117 · 사용자 승인)
BM_FROM = dt.date(2026, 10, 25)          # 첫날(KST)
BM_TO = dt.date(2026, 11, 7)             # 마지막 날(KST, 포함) · 14일 = A 7편 + B 7편
BM_KINDS = ("bm_paper", "bm_animal")     # A · B — BM_FROM 부터 ABBA ABBA ABBA AB(bm_kind)
BM_CATALOG = os.path.join(HERE, "bm_catalog.json")   # 병맛 14편 소재 — 사실(facts)·출처(sources)·주의(careful)를 미리 확인
BM_ORDER = tuple(range(401, 415))        # i 번째 병맛 편 = bm_catalog 의 n(꼴은 entry format 과 같아야 한다 — 테스트)
BM_FMT_KIND = {"paper": "bm_paper", "animal": "bm_animal"}
BM_ENTRY_KEYS = ("n", "format", "slug", "topic", "animal", "animal_ko", "premise", "stamp_idea", "quote_idea", "punch_idea",
                 "facts", "sources", "careful")
BM_EXEMPLAR = {"bm_paper": "insta/samples/bm_paper_wombat.json", "bm_animal": "insta/samples/bm_animal_penguin.json"}
BM_WRITING = "insta/BM_WRITING.md"
BM_FORMAT = {"bm_paper": "A", "bm_animal": "B"}
BM_SERIES = {"bm_paper": "이거 진짜 논문임", "bm_animal": "정색 동물 다큐"}
BM_SEC = {"bm_paper": (18.0, 23.0), "bm_animal": (18.0, 22.0)}   # 전체 길이(초) — 렌더가 맞춘다
ALL_KINDS = FORMATS + (SCI,) + BM_KINDS
SCI_ENTRY_KEYS = ("n", "format", "slug", "look", "title_idea", "facts", "sources", "careful", "beat_ideas", "items_idea",
                  "situation", "odds_idea", "hook_idea", "unit", "scale", "twist_idea",
                  "series", "topic_ko", "topic_en", "why_idea", "steps", "result_idea", "mechanism_refs")   # 뒤 줄 = 뜯어보기 항목
# 그날 꼴의 서칭 키워드(로컬 크롬 · 인스타 검색 상위 조회수) — 쓰는 쪽이 참고만 한다
KEYWORDS = {"pick": ["심리테스트", "성격테스트", "그림 고르기"], "card": ["타로", "타로 골라보세요", "오늘의 타로"],
            "quiz": ["상식 퀴즈", "넌센스 퀴즈", "퀴즈"], "balance": ["밸런스 게임", "둘 중 하나"],
            "birth": ["태어난 달", "생일 운세", "탄생월"], "sci": ["심해", "우주 과학", "극한 생존"],
            "bm_paper": ["이그노벨상", "황당 연구", "쓸데없는 과학"], "bm_animal": ["동물 병맛", "AI 동물", "동물 다큐"]}
TEARDOWN_KEYWORDS = ("작동 원리", "단면", "속 구조")


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def slots_on(d: dt.date) -> tuple[str, ...]:
    """그날 편들 — TWICE_FROM 전에는 저녁 편 하나(b), 뒤로는 낮·저녁 두 편."""
    return SLOTS if d >= TWICE_FROM else ("b",)


def _slot(d: dt.date, slot: str | None) -> str:
    sl = slot or slots_on(d)[0]
    if sl not in slots_on(d):
        raise ValueError(f"{d} 에는 {sl} 편이 없다(그날 편: {slots_on(d)})")
    return sl


def _read(path: str) -> dict:
    """catalog JSON — 파일이 없으면 빈 것(뜯어보기 catalog 가 아직 없어도 편성은 돈다)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def catalog_entries(cat: dict) -> list[dict]:
    """catalog 의 항목 전부 — survival·compare(sci_extra·shorts_catalog 모양), entries 도 받는다."""
    return [e for k in ("survival", "compare", "entries") for e in (cat.get(k) or []) if isinstance(e, dict)]


def _date_or_none(v) -> dt.date | None:
    try:
        return dt.date.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        return None


def open_pools() -> dict:
    """끝없는 sci 의 항목 줄(SCI_TO 뒤) — {"sci": [(from, n)…], "teardown": [(from, n)…], "unscheduled": {…}}.
    보통 sci = sci_extra 의 SCI_ORDER 밖 항목(from 필수) + shorts_catalog 의 insta_from 단 항목(구미호 쇼츠 것은 달아야만 쓴다).
    뜯어보기 = teardown_catalog 항목(from 필수). 줄마다 (from, n) 순서 · 같은 n 은 한 번만 · SCI_ORDER 는 다시 안 쓴다.
    from 이 없거나 날짜가 아니면 편성하지 않고 unscheduled 에 남긴다(runway 가 알린다)."""
    used = set(SCI_ORDER)
    pools: dict = {SCI: [], TEARDOWN: [], "unscheduled": {"no_from": [], "shorts_unused": []}}
    for e in catalog_entries(_read(SHORTS)):
        n = e.get("n")
        if n in used or not isinstance(n, int):
            continue
        f = _date_or_none(e.get("insta_from"))
        if f:
            pools[SCI].append((max(f, SCI_OPEN_FROM), n))
            used.add(n)
        elif e.get("format") in ("survival", "compare"):
            pools["unscheduled"]["shorts_unused"].append(n)
    for key, path, start in ((SCI, SCI_EXTRA, SCI_OPEN_FROM), (TEARDOWN, TEARDOWN_CATALOG, TEARDOWN_FROM)):
        for e in catalog_entries(_read(path)):
            n = e.get("n")
            if n in used or not isinstance(n, int):
                continue
            f = _date_or_none(e.get("from"))
            if f is None:
                pools["unscheduled"]["no_from"].append(n)
                continue
            pools[key].append((max(f, start), n))
            used.add(n)
    pools[SCI].sort()
    pools[TEARDOWN].sort()
    return pools


def is_teardown_day(d: dt.date) -> bool:
    """뜯어보기 자리인 날 — TEARDOWN_FROM 부터 화·금(항목이 남았는지는 보지 않는다 · open_plan 이 본다)."""
    return d >= TEARDOWN_FROM and d.weekday() in TEARDOWN_DAYS


_PLAN: dict = {}


def _stamp(p: str) -> tuple:
    try:
        st = os.stat(p)
        return p, st.st_mtime_ns, st.st_size
    except OSError:
        return p, None, None


def reload() -> None:
    """catalog 를 다시 읽게(테스트가 catalog 경로를 바꾼 뒤 부른다)."""
    _PLAN.clear()


def open_plan() -> dict[dt.date, tuple[str, int]]:
    """SCI_TO 다음 날(11/08)부터 sci 자리에 나가는 것 — {날짜: (줄기 "sci"|"teardown", n)}.
    날마다 걷는다: 뜯어보기 날(화·금)이고 쓸 수 있는(from ≤ 그날) 뜯어보기 항목이 있으면 그것, 아니면 쓸 수 있는 보통 sci 항목,
    둘 다 없으면 그날은 sci 가 없다(골라보기 두 편). 항목이 다 쓰이면 끝 — 그래서 dict 에 없는 날 = sci 없는 날."""
    key = tuple(_stamp(p) for p in (SHORTS, SCI_EXTRA, TEARDOWN_CATALOG))
    if _PLAN.get("key") == key:
        return _PLAN["plan"]
    pools = open_pools()
    reg, td = pools[SCI], pools[TEARDOWN]
    plan: dict[dt.date, tuple[str, int]] = {}
    d, ri, ti = SCI_OPEN_FROM, 0, 0
    end = SCI_OPEN_FROM + dt.timedelta(days=OPEN_MAX_DAYS)
    while (ri < len(reg) or ti < len(td)) and d <= end:
        if is_teardown_day(d) and ti < len(td) and td[ti][0] <= d:
            plan[d] = (TEARDOWN, td[ti][1])
            ti += 1
        elif ri < len(reg) and reg[ri][0] <= d:
            plan[d] = (SCI, reg[ri][1])
            ri += 1
        d += dt.timedelta(days=1)
    _PLAN.update(key=key, plan=plan, days=sorted(plan), pools=pools)
    return plan


@contextlib.contextmanager
def catalogs(extra: str | None = None, teardown: str | None = None, shorts: str | None = None):
    """catalog 경로를 잠깐 바꾼다(테스트·미리보기) — 끝나면 되돌리고 다시 읽는다."""
    global SCI_EXTRA, TEARDOWN_CATALOG, SHORTS
    saved = SCI_EXTRA, TEARDOWN_CATALOG, SHORTS
    SCI_EXTRA, TEARDOWN_CATALOG, SHORTS = extra or SCI_EXTRA, teardown or TEARDOWN_CATALOG, shorts or SHORTS
    reload()
    try:
        yield
    finally:
        SCI_EXTRA, TEARDOWN_CATALOG, SHORTS = saved
        reload()


@contextlib.contextmanager
def only_order():
    """열린 항목 없이 — SCI_ORDER(11/07 까지)만 남긴 catalog 로. 'catalog 가 바닥난 뒤'(11/08~ 골라보기 두 편)를 못 박는
    테스트가 쓴다 — 그래서 catalog 를 채워도 그 테스트는 깨지지 않는다."""
    with tempfile.TemporaryDirectory() as td:
        paths = []
        for name, src in (("sci_extra.json", SCI_EXTRA), ("shorts_catalog.json", SHORTS)):
            cat = _read(src)
            for k in ("survival", "compare", "entries"):
                if isinstance(cat.get(k), list):
                    cat[k] = [e for e in cat[k] if e.get("n") in SCI_ORDER or not (e.get("from") or e.get("insta_from"))]
                    for e in cat[k]:
                        e.pop("insta_from", None)
            p = os.path.join(td, name)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cat, f, ensure_ascii=False)
            paths.append(p)
        with catalogs(extra=paths[0], shorts=paths[1], teardown=os.path.join(td, "none.json")):
            yield


def _open_days() -> list[dt.date]:
    open_plan()
    return _PLAN["days"]


def sci_slot(d: dt.date) -> str | None:
    """그날 sci 편 — SCI_FROM~SCI_TO(SCI_ORDER) 와 그 뒤 open_plan 의 날. 날마다 저녁·낮을 번갈아
    (10/15 b → 10/16 a → 10/17 b … 11/08 b · 11/09 a … — 항목이 끊긴 날이 있어도 번갈이는 날짜로 이어진다). 없으면 None."""
    if not (SCI_FROM <= d <= SCI_TO or (d > SCI_TO and d in open_plan())):
        return None
    return "b" if (d - SCI_FROM).days % 2 == 0 else "a"


def sci_index(d: dt.date) -> int | None:
    """몇 번째 sci 편인가(0 = 10/15 · 뜯어보기 편도 센다) — sci 날이 아니면 None."""
    if sci_slot(d) is None:
        return None
    if d <= SCI_TO:
        return (d - SCI_FROM).days
    return (SCI_TO - SCI_FROM).days + 1 + bisect.bisect_left(_open_days(), d)


def sci_n(d: dt.date) -> int | None:
    """그날 sci 편이 쓸 항목 번호 — 11/07 까지 SCI_ORDER, 그 뒤 open_plan. sci 날이 아니면 None."""
    if sci_slot(d) is None:
        return None
    return SCI_ORDER[(d - SCI_FROM).days] if d <= SCI_TO else open_plan()[d][1]


def sci_series(d: dt.date) -> str | None:
    """그날 sci 편의 줄기 — 'teardown'(과학으로 뜯어보는 물건) · 'sci'(보통) · sci 날이 아니면 None."""
    if sci_slot(d) is None:
        return None
    return SCI if d <= SCI_TO else open_plan()[d][0]


def teardown_index(d: dt.date) -> int | None:
    """몇 번째 뜯어보기 편인가(0 = 첫 편) — 뜯어보기 날이 아니면 None."""
    if sci_series(d) != TEARDOWN:
        return None
    plan = open_plan()
    return sum(1 for x in _open_days() if x < d and plan[x][0] == TEARDOWN)


def sci_xray(d: dt.date) -> bool:
    """그날 sci 편이 '속이 보이는 과학' 모양인가 — SCI_XRAY_FROM(10/25) 부터. 그 전 날짜는 옛 모양 그대로."""
    return d >= SCI_XRAY_FROM


def sci_entry(n: int, path: str | None = None, extra: str | None = None, teardown: str | None = None) -> dict | None:
    """sci 항목(n) 그대로 — shorts_catalog 의 survival·compare, 없으면 인스타 전용 sci_extra.json(901~),
    그다음 teardown_catalog.json(951~ · series 'teardown')."""
    for p in (path or SHORTS, extra or SCI_EXTRA, teardown or TEARDOWN_CATALOG):
        e = next((e for e in catalog_entries(_read(p)) if e.get("n") == n), None)
        if e:
            return e
    return None


def is_teardown_entry(e: dict | None) -> bool:
    """뜯어보기 항목인가 — series 'teardown' 이거나 번호가 951~(teardown_catalog)."""
    return bool(e) and (e.get("series") == TEARDOWN or (isinstance(e.get("n"), int) and e["n"] >= TEARDOWN_N0))


def bm_kind(d: dt.date) -> str | None:
    """그날 병맛 꼴 — BM_FROM~BM_TO 안에서만: ABBA ABBA ABBA AB(i%4 가 0·3 이면 bm_paper, 1·2 면 bm_animal). 밖이면 None.
    (10/20 사용자: 날마다 A/B 번갈면 A 는 늘 낮·B 는 늘 저녁이라 시간대와 꼴이 섞인다 → ABBA 로 둘 다 낮·저녁에 나간다)"""
    if not BM_FROM <= d <= BM_TO:
        return None
    return BM_KINDS[0] if (d - BM_FROM).days % 4 in (0, 3) else BM_KINDS[1]


def bm_slot(d: dt.date) -> str | None:
    """그날 병맛 편 — sci 가 아닌 편(병맛 기간엔 sci 가 날마다 있다). 병맛 날이 아니면 None."""
    if bm_kind(d) is None:
        return None
    return next((sl for sl in slots_on(d) if sl != sci_slot(d)), None)


def bm_index(d: dt.date) -> int | None:
    """몇 번째 병맛 편인가(0 = 10/25) — 병맛 날이 아니면 None."""
    return (d - BM_FROM).days if bm_kind(d) else None


def bm_n(d: dt.date) -> int | None:
    """그날 병맛 편이 쓸 bm_catalog 항목 번호(BM_ORDER) — 병맛 날이 아니면 None."""
    k = bm_index(d)
    return None if k is None else BM_ORDER[k]


def bm_entry(n: int, path: str = BM_CATALOG) -> dict | None:
    """bm_catalog 항목(n) 그대로."""
    try:
        with open(path, encoding="utf-8") as f:
            cat = json.load(f)
    except FileNotFoundError:
        return None
    return next((e for e in cat.get("entries") or [] if e.get("n") == n), None)


def _window_before(d: dt.date, start: dt.date, end: dt.date) -> int:
    """[start, end] 기간 중 d 보다 앞선 날 수."""
    return min(max(0, (d - start).days), (end - start).days + 1)


def _skipped_before(d: dt.date, sl: str) -> int:
    """(d, sl) 편보다 먼저 올라가는 sci·병맛 편 수 — 골라보기 로테이션·회차에서 뺀다(둘 다 하루 한 편씩).
    sci 는 SCI_ORDER 기간 + 그 뒤 open_plan 의 날(뜯어보기 포함)."""
    n = (_window_before(d, SCI_FROM, SCI_TO) + bisect.bisect_left(_open_days(), d)
         + _window_before(d, BM_FROM, BM_TO))
    for x in (sci_slot(d), bm_slot(d)):
        if x is not None and SLOTS.index(x) < SLOTS.index(sl):
            n += 1
    return n


def _not_pick(d: dt.date, sl: str) -> str | None:
    """그 편이 골라보기가 아니면 그 꼴(sci·병맛), 골라보기면 None."""
    if sl == sci_slot(d):
        return SCI
    if sl == bm_slot(d):
        return bm_kind(d)
    return None


def post_index(d: dt.date, slot: str | None = None) -> int:
    """골라보기 로테이션에서 몇 번째 편인가(0부터) — 하루 한 편이던 날들 뒤로 하루 두 편이 끊김 없이 이어지고,
    sci 편(10/15~11/07 · 그 뒤 open_plan 의 날)·병맛 편(10/25~11/07)은 세지 않는다(그래서 로테이션이 건너뛰지도 겹치지도 않는다).
    sci·병맛 편을 물으면 ValueError."""
    sl = _slot(d, slot)
    other = _not_pick(d, sl)
    if other:
        raise ValueError(f"{d} {sl} 편은 {other} — 골라보기 순번이 없다")
    if d < TWICE_FROM:
        return (d - START).days
    return (TWICE_FROM - START).days + 2 * (d - TWICE_FROM).days + SLOTS.index(sl) - _skipped_before(d, sl)


def kind_for(d: dt.date, slot: str | None = None) -> str:
    """그날 그 편의 꼴(sci · 병맛 · 골라보기 꼴). slot 을 안 주면 그날 첫 편."""
    sl = _slot(d, slot)
    return _not_pick(d, sl) or FORMATS[post_index(d, sl) % len(FORMATS)]


def is_pick(kind: str) -> bool:
    """골라보기 꼴인가(회차·쓰레드 대상) — sci·병맛은 아니다."""
    return kind in FORMATS


def series_no(d: dt.date, slot: str | None = None) -> int | None:
    """'오늘의 골라보기 #N' — 10/8 이 #1, 골라보기 편마다 하나씩 는다(sci·병맛 편은 번호가 없다 → None).
    10/9: 매일 이어지는 시리즈로 보이게(캡션 첫 줄·커버 라벨)."""
    sl = _slot(d, slot)
    return None if _not_pick(d, sl) else post_index(d, sl) + 1


def slot_of(d: dt.date, kind: str) -> str | None:
    """그날 그 꼴은 어느 편인가 — 같은 날 두 편은 꼴이 늘 달라서 하나로 정해진다. 그날 꼴이 아니면 None."""
    return next((sl for sl in slots_on(d) if kind_for(d, sl) == kind), None)


def due_slot(d: dt.date, now: dt.datetime | None = None) -> str | None:
    """지금 쓸 차례인 편 — NOON_UNTIL 시 전이면 낮 편(없는 날이면 None = 쓸 차례 아님), 뒤면 저녁 편."""
    now = now or dt.datetime.now(KST)
    if now.astimezone(KST).hour < NOON_UNTIL:
        return "a" if "a" in slots_on(d) else None
    return "b"


def ledger_key(date: str, slot: str) -> str:
    """게시 ledger 열쇠 — 저녁 편은 예전처럼 날짜 그대로, 낮 편은 날짜+'a'. 쓰레드는 그날 골라보기 편의 열쇠로 찾는다."""
    return date if slot == "b" else f"{date}{slot}"


def _kind_of_file(p: str) -> str:
    """파일 이름 '<날짜>_<kind>_<slug>.json' 의 kind — bm_paper·bm_animal 처럼 밑줄이 든 꼴도 알아본다."""
    name = os.path.basename(p)
    rest = name[11:] if len(name) > 11 and name[10] == "_" else ""
    for k in sorted(ALL_KINDS, key=len, reverse=True):
        if rest.startswith(k + "_"):
            return k
    parts = name.split("_")
    return parts[1] if len(parts) >= 3 else ""


def scripts_on(d: dt.date, root: str = SCRIPTS) -> list[str]:
    return sorted(glob.glob(os.path.join(root, f"{d.isoformat()}_*.json")))


def script_for(d: dt.date, slot: str, root: str = SCRIPTS) -> str | None:
    """그날 그 편의 대본 파일(파일 이름의 꼴로 찾는다) — 없으면 None."""
    k = kind_for(d, slot)
    return next((p for p in scripts_on(d, root) if _kind_of_file(p) == k), None)


def latest_target(d: dt.date, root: str = SCRIPTS) -> str | None:
    """워크플로가 처리할 오늘 대본 — 있는 편 중 가장 늦은 편(저녁 push 때 낮 대본을 다시 집지 않게)."""
    for sl in reversed(slots_on(d)):
        p = script_for(d, sl, root)
        if p:
            return p
    return None


def recent(d: dt.date, root: str = SCRIPTS, n: int = 40, kind: str | None = None) -> list[dict]:
    """지난 대본(오늘 전 + 오늘의 다른 편) — 같은 주제·같은 문제를 다시 쓰지 않게."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "*.json")), reverse=True):
        name = os.path.basename(p)
        if name[:10] > d.isoformat() or (name[:10] == d.isoformat() and (kind is None or _kind_of_file(p) == kind)):
            continue
        try:
            s = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        item = {"date": s.get("date"), "kind": s.get("kind"), "slug": s.get("slug"),
                "headline": " / ".join(s.get("headline") or s.get("hook") or [])}
        if s.get("kind") == "quiz":
            item["questions"] = [r.get("q") for r in s.get("rounds", [])]
        if s.get("kind") == SCI:
            item["src_n"] = s.get("src_n")
        if s.get("kind") in BM_KINDS:                       # 병맛: 같은 소재·같은 동물을 다시 쓰지 않게
            item["topic"] = s.get("topic")
            if s.get("animal_ko"):
                item["animal"] = s.get("animal_ko")
        out.append(item)
        if len(out) >= n:
            break
    return out


def next_info(d: dt.date, root: str = SCRIPTS, slot: str | None = None, now: dt.datetime | None = None) -> dict:
    """지금 쓸 편 — slot 을 안 주면 due_slot(시각)으로. 쓸 차례가 아니면 due: false(아무것도 쓰지 않는다)."""
    sl = slot or due_slot(d, now)
    if sl is None or sl not in slots_on(d):
        return {"date": d.isoformat(), "due": False, "slot": sl, "already_written": False,
                "why": f"{d} 에는 낮 편이 없다 — 하루 두 편은 {TWICE_FROM} 부터(그 전엔 저녁 편 하나)"}
    k = kind_for(d, sl)
    if k == SCI:
        exemplar, writing = (SCI_XRAY_EXEMPLAR if sci_xray(d) else SCI_EXEMPLAR), SCI_WRITING
    elif k in BM_KINDS:
        exemplar, writing = BM_EXEMPLAR[k], BM_WRITING
    else:
        exemplar, writing = f"insta/samples/{EXEMPLAR[k]}.json", "insta/PICK_WRITING.md"
    out = {"date": d.isoformat(), "due": True, "slot": sl, "slot_label": SLOT_LABEL[sl], "series_no": series_no(d, sl),
           "kind": k, "label": LABEL[k], "file": f"output/insta_pick/{d.isoformat()}_{k}_<slug>.json",
           "exemplar": exemplar, "writing": writing,
           "keywords": KEYWORDS[k], "already_written": bool(script_for(d, sl, root)), "recent": recent(d, root, kind=k)}
    if k in BM_KINDS:                                      # 병맛: 무엇을 쓸지도 코드가 — 그날 bm_catalog 항목 그대로(숫자는 facts 에서만)
        e = bm_entry(bm_n(d)) or {}
        out.update(bm_no=bm_index(d) + 1, bm_total=(BM_TO - BM_FROM).days + 1, format=BM_FORMAT[k], series=BM_SERIES[k],
                   length_sec=list(BM_SEC[k]), bm_n=e.get("n"), src_n=e.get("n"),
                   entry={k_: e[k_] for k_ in BM_ENTRY_KEYS if k_ in e})
    if k == SCI:                                           # 무엇을 쓸지도 코드가 정한다 — 그날 catalog 항목 그대로(숫자는 facts 에서만)
        e = sci_entry(sci_n(d)) or {}
        out.update(src_n=e.get("n"), sci_no=sci_index(d) + 1, format=e.get("format"),
                   entry={k_: e[k_] for k_ in SCI_ENTRY_KEYS if k_ in e})
        if sci_xray(d):                                    # ★10/25~ '속이 보이는 과학' — 모양은 check 가 막는다(SCI_WRITING)
            out.update(series="속이 보이는 과학", length_sec=list(SCI_XRAY_SEC), views=list(SCI_XRAY_VIEWS),
                       structure="hook(대조·충격 질문) → why(왜?) → beats 정확히 3개(1/3·2/3·3/3, 박자마다 view) → verdict(결과)")
        if sci_series(d) == TEARDOWN:                      # ★11/10~ 화·금 '과학으로 뜯어보는 물건' — 같은 모양(sci_xray), 대상은 생활 물건
            out.update(series=TEARDOWN_SERIES, series_id=TEARDOWN, teardown_no=teardown_index(d) + 1,
                       label=f"{TEARDOWN_SERIES}(생활 물건을 단면으로)", keywords=list(TEARDOWN_KEYWORDS),
                       views_hint="cutaway 중심 — 물건 겉을 잘라 연 단면에 부품을 label 로(SCI_WRITING '뜯어보기')")
    return out


# ── 재고(runway) — tools/runway.py 가 부른다 ─────────────────
def runway(today: dt.date) -> list[dict]:
    """인스타 줄기마다 남은 것 — {id, name, limit(open·catalog·trial), last(마지막 날 | None), left(오늘 포함 남은 편 | None),
    refill(채우는 곳), note}. 날짜 셈은 이 파일의 편성 함수(sci_n·open_plan·bm_kind) 그대로."""
    plan = open_plan()
    pools = _PLAN["pools"]
    reg = [SCI_FROM + dt.timedelta(days=k) for k in range((SCI_TO - SCI_FROM).days + 1)]
    reg += [d for d in _open_days() if plan[d][0] == SCI]
    td = [d for d in _open_days() if plan[d][0] == TEARDOWN]
    bm = [BM_FROM + dt.timedelta(days=k) for k in range((BM_TO - BM_FROM).days + 1)]
    un = pools["unscheduled"]
    note = []
    if un["no_from"]:
        note.append(f"from 없는 항목 {sorted(un['no_from'])} 은 편성 안 됨(from 을 달 것)")
    if un["shorts_unused"]:
        note.append(f"shorts_catalog 안 쓴 survival·compare {len(un['shorts_unused'])}개 — insta_from 을 달면 sci 로 이어진다")
    nxt = max(today + dt.timedelta(days=1), SCI_OPEN_FROM).isoformat()
    nxt_td = max(today + dt.timedelta(days=1), TEARDOWN_FROM).isoformat()
    n_sci = max([n for n in (e.get("n") for e in catalog_entries(_read(SCI_EXTRA))) if isinstance(n, int)
                 and SCI_OPEN_N0 <= n < TEARDOWN_N0] + [SCI_OPEN_N0 - 1]) + 1
    n_td = max([n for n in (e.get("n") for e in catalog_entries(_read(TEARDOWN_CATALOG))) if isinstance(n, int)]
               + [TEARDOWN_N0 - 1]) + 1
    return [
        {"id": "insta_pick", "name": "인스타 '오늘의 골라보기'(그림·퀴즈·타로·밸런스·태어난 달)", "limit": "open", "last": None,
         "left": None, "refill": "없음 — FORMATS 날짜 순환(BM 기간 10/25~11/07 엔 병맛이 자리를 쓴다)"},
        {"id": "insta_sci", "name": "인스타 sci(도파민 과학 · 속이 보이는 과학)", "limit": "catalog", "last": max(reg),
         "left": sum(d >= today for d in reg),
         "refill": f"insta/sci_extra.json 끝에 survival·compare 항목(n {n_sci}~, facts·sources 확인, from ≥ {nxt})",
         "note": " · ".join(note)},
        {"id": "insta_teardown", "name": f"인스타 '{TEARDOWN_SERIES}'(화·금, {TEARDOWN_FROM:%m/%d} 주부터)", "limit": "catalog",
         "last": max(td) if td else None, "left": sum(d >= today for d in td),
         "refill": f"insta/teardown_catalog.json 끝에 항목(n {n_td}~, series teardown, cutaway, from ≥ {nxt_td})",
         "note": "" if td else "catalog 가 비었다 — 화·금도 보통 sci(그것도 없으면 골라보기)"},
        {"id": "insta_bm", "name": "인스타 병맛(이거 진짜 논문임 · 정색 동물 다큐) 2주 시험", "limit": "trial", "last": BM_TO,
         "left": sum(d >= today for d in bm), "judge": BM_TO + dt.timedelta(days=1),
         "refill": "판정 뒤 이어 가려면 insta/bm_catalog.json 항목 + pick_plan BM_TO·BM_ORDER(코드 PR)"},
    ]


# ── 게시 ──────────────────────────────────────────────
def load_ledger(path: str = LEDGER) -> dict:
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def blockers(s: dict, meta: dict | None, led: dict, today: dt.date) -> list[str]:
    bad = []
    sl = None
    if s.get("date") != today.isoformat():
        bad.append(f"오늘({today}) 대본이 아니다: {s.get('date')}")
    else:
        d = dt.date.fromisoformat(s["date"])
        sl = slot_of(d, s.get("kind", ""))
        if sl is None:
            bad.append(f"오늘 꼴은 {[kind_for(d, x) for x in slots_on(d)]} — 대본은 {s.get('kind')}")
    key = ledger_key(s.get("date", ""), sl or "b")
    if sl and key in led:
        bad.append(f"{s.get('date')} {SLOT_LABEL[sl]}은 이미 올렸다: {led[key].get('media_id')}")
    if not meta or not os.path.exists(meta.get("video", "")):
        bad.append("렌더 결과(영상)가 없다")
    elif not 8 <= float(meta.get("seconds", 0)) <= 60:
        bad.append(f"길이가 이상하다: {meta.get('seconds')}초")
    return bad


def post(path: str, renders: str = RENDERS, ledger: str = LEDGER, today: dt.date | None = None) -> int:
    s = json.load(open(path, encoding="utf-8"))
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    mp = os.path.join(renders, f"{stem}_meta.json")
    meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else None
    led = load_ledger(ledger)
    today = today or kst_today()
    bad = blockers(s, meta, led, today)
    if bad:
        print("⏭️ 게시 안 함:\n  " + "\n  ".join(bad))
        return 0 if any("이미 올렸다" in b for b in bad) else 1
    caption = meta["caption"][:2150]
    if os.environ.get("INSTA_PICK_PUBLISH", "0").strip() != "1":
        print(f"🔸 dry-run — INSTA_PICK_PUBLISH=1 이 아니라 올리지 않는다 · {stem} · {meta['seconds']}초\n{caption[:300]}…")
        return 0
    import host_video
    import upload_instagram as UI
    pid = f"insta_pick_{stem}"
    url = host_video.host(meta["video"], pid)
    cover = host_video.host_image(meta["cover"], pid + "_cover") if meta.get("cover") else None
    if not url:
        print("❌ 영상 공개 URL 실패(Cloudinary)")
        return 1
    try:
        mid = UI.publish_reel(url, caption, cover_url=cover)
    finally:
        host_video.cleanup(pid)
        if cover:
            host_video.cleanup(pid + "_cover", "image")
    sl = slot_of(dt.date.fromisoformat(s["date"]), s["kind"])
    led[ledger_key(s["date"], sl)] = {"media_id": mid, "kind": s["kind"], "slug": s["slug"], "slot": sl,
                                      "seconds": meta["seconds"], "at": dt.datetime.now(KST).isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    json.dump(led, open(ledger, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 인스타 릴스 게시({LABEL.get(s['kind'], s['kind'])}): {stem} · media_id={mid}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 릴스('오늘의 골라보기' · sci · 병맛) 편성·게시")
    ap.add_argument("cmd", choices=["next", "targets", "post"])
    ap.add_argument("script", nargs="?")
    ap.add_argument("--date")
    ap.add_argument("--slot", choices=SLOTS, help="next: 이 편으로(안 주면 지금 시각으로 정한다)")
    ap.add_argument("--root", default=SCRIPTS)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "next":
        print(json.dumps(next_info(d, a.root, a.slot), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "targets":
        t = latest_target(d, a.root)
        print(os.path.relpath(t, ROOT).replace("\\", "/") if t else "")
        return 0
    if not a.script:
        ap.error("post 는 대본 경로가 필요하다")
    return post(a.script)


if __name__ == "__main__":
    sys.exit(main())
