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
    꼴은 날마다 번갈아: BM_FROM 부터 짝수 날 bm_paper(A '이거 진짜 논문임') · 홀수 날 bm_animal(B '정색 동물 다큐') — 7편씩.
    (sci 가 짝수 날 저녁이라 A 는 늘 낮 편, B 는 늘 저녁 편이 된다 — 판정 때 시간대 차이를 감안할 것.)
    골라보기 로테이션은 그동안 쉬고, 11/08부터 다음 꼴로 이어진다(회차 series_no 도 골라보기만 이어서 센다 · bm·sci 는 None).
    11/08부터 다시 골라보기 두 편. 10/24 까지 꼴·회차·sci 순서는 그대로다(테스트가 못 박는다).
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
import datetime as dt
import glob
import json
import os
import sys

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
SCI_TO = dt.date(2026, 11, 7)            # 마지막 날(KST, 포함) · ★10/20 10/28 → 11/07 연장(24일) · 더 늘리려면 코드로(PR)
# k번째 sci 편 = shorts_catalog n(앞 14개 = 10/15~10/28 그대로) · 10/29~ 안 쓴 catalog 7개 → sci_extra.json 3개(901~)
SCI_ORDER = (101, 201, 107, 102, 203, 104, 202, 105, 206, 109, 205, 103, 207, 106,
             108, 110, 111, 112, 113, 114, 204, 901, 902, 903)
SCI_EXEMPLAR = "insta/samples/sci_mariana.json"
SCI_WRITING = "insta/SCI_WRITING.md"
SHORTS = os.path.join(ROOT, "gumiho", "tales", "shorts_catalog.json")   # 영어 쇼츠 survival·compare — 출처 달린 사실(facts)
SCI_EXTRA = os.path.join(HERE, "sci_extra.json")                         # 인스타 sci 전용 추가 주제(n ≥ 901, 같은 모양)
# ★10/20 병맛(bm) 2주 시험 — 골라보기 자리를 바꾼다(10/15~10/20 sci 중앙값 약 440 vs 골라보기 약 117 · 사용자 승인)
BM_FROM = dt.date(2026, 10, 25)          # 첫날(KST)
BM_TO = dt.date(2026, 11, 7)             # 마지막 날(KST, 포함) · 14일 = A 7편 + B 7편
BM_KINDS = ("bm_paper", "bm_animal")     # BM_FROM 부터 짝수 날 A · 홀수 날 B
BM_EXEMPLAR = {"bm_paper": "insta/samples/bm_paper_wombat.json", "bm_animal": "insta/samples/bm_animal_penguin.json"}
BM_WRITING = "insta/BM_WRITING.md"
BM_FORMAT = {"bm_paper": "A", "bm_animal": "B"}
BM_SERIES = {"bm_paper": "이거 진짜 논문임", "bm_animal": "정색 동물 다큐"}
BM_SEC = {"bm_paper": (18.0, 23.0), "bm_animal": (18.0, 22.0)}   # 전체 길이(초) — 렌더가 맞춘다
ALL_KINDS = FORMATS + (SCI,) + BM_KINDS
SCI_ENTRY_KEYS = ("n", "format", "slug", "look", "title_idea", "facts", "sources", "careful", "beat_ideas", "items_idea",
                  "situation", "odds_idea", "hook_idea", "unit", "scale", "twist_idea")
# 그날 꼴의 서칭 키워드(로컬 크롬 · 인스타 검색 상위 조회수) — 쓰는 쪽이 참고만 한다
KEYWORDS = {"pick": ["심리테스트", "성격테스트", "그림 고르기"], "card": ["타로", "타로 골라보세요", "오늘의 타로"],
            "quiz": ["상식 퀴즈", "넌센스 퀴즈", "퀴즈"], "balance": ["밸런스 게임", "둘 중 하나"],
            "birth": ["태어난 달", "생일 운세", "탄생월"], "sci": ["심해", "우주 과학", "극한 생존"],
            "bm_paper": ["이그노벨상", "황당 연구", "쓸데없는 과학"], "bm_animal": ["동물 병맛", "AI 동물", "동물 다큐"]}


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


def sci_slot(d: dt.date) -> str | None:
    """그날 sci 편 — SCI_FROM~SCI_TO 안에서만. 날마다 저녁·낮을 번갈아(10/15 b → 10/16 a → 10/17 b …). 밖이면 None."""
    if not SCI_FROM <= d <= SCI_TO:
        return None
    return "b" if (d - SCI_FROM).days % 2 == 0 else "a"


def sci_index(d: dt.date) -> int | None:
    """몇 번째 sci 편인가(0 = 10/15) — sci 날이 아니면 None."""
    return (d - SCI_FROM).days if sci_slot(d) else None


def sci_n(d: dt.date) -> int | None:
    """그날 sci 편이 쓸 shorts_catalog 항목 번호(SCI_ORDER) — sci 날이 아니면 None."""
    k = sci_index(d)
    return None if k is None else SCI_ORDER[k]


def sci_entry(n: int, path: str = SHORTS, extra: str = SCI_EXTRA) -> dict | None:
    """sci 항목(n) 그대로 — shorts_catalog 의 survival·compare, 없으면 인스타 전용 sci_extra.json(901~)."""
    for p in (path, extra):
        try:
            with open(p, encoding="utf-8") as f:
                cat = json.load(f)
        except FileNotFoundError:
            continue
        e = next((e for e in (cat.get("survival") or []) + (cat.get("compare") or []) if e.get("n") == n), None)
        if e:
            return e
    return None


def bm_kind(d: dt.date) -> str | None:
    """그날 병맛 꼴 — BM_FROM~BM_TO 안에서만: BM_FROM 부터 짝수 날 bm_paper(A) · 홀수 날 bm_animal(B). 밖이면 None."""
    if not BM_FROM <= d <= BM_TO:
        return None
    return BM_KINDS[(d - BM_FROM).days % 2]


def bm_slot(d: dt.date) -> str | None:
    """그날 병맛 편 — sci 가 아닌 편(병맛 기간엔 sci 가 날마다 있다). 병맛 날이 아니면 None."""
    if bm_kind(d) is None:
        return None
    return next((sl for sl in slots_on(d) if sl != sci_slot(d)), None)


def bm_index(d: dt.date) -> int | None:
    """몇 번째 병맛 편인가(0 = 10/25) — 병맛 날이 아니면 None."""
    return (d - BM_FROM).days if bm_kind(d) else None


def _window_before(d: dt.date, start: dt.date, end: dt.date) -> int:
    """[start, end] 기간 중 d 보다 앞선 날 수."""
    return min(max(0, (d - start).days), (end - start).days + 1)


def _skipped_before(d: dt.date, sl: str) -> int:
    """(d, sl) 편보다 먼저 올라가는 sci·병맛 편 수 — 골라보기 로테이션·회차에서 뺀다(둘 다 하루 한 편씩)."""
    n = _window_before(d, SCI_FROM, SCI_TO) + _window_before(d, BM_FROM, BM_TO)
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
    sci 편(10/15~11/07)·병맛 편(10/25~11/07)은 세지 않는다(그래서 로테이션이 건너뛰지도 겹치지도 않는다).
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
        exemplar, writing = SCI_EXEMPLAR, SCI_WRITING
    elif k in BM_KINDS:
        exemplar, writing = BM_EXEMPLAR[k], BM_WRITING
    else:
        exemplar, writing = f"insta/samples/{EXEMPLAR[k]}.json", "insta/PICK_WRITING.md"
    out = {"date": d.isoformat(), "due": True, "slot": sl, "slot_label": SLOT_LABEL[sl], "series_no": series_no(d, sl),
           "kind": k, "label": LABEL[k], "file": f"output/insta_pick/{d.isoformat()}_{k}_<slug>.json",
           "exemplar": exemplar, "writing": writing,
           "keywords": KEYWORDS[k], "already_written": bool(script_for(d, sl, root)), "recent": recent(d, root, kind=k)}
    if k in BM_KINDS:                                      # 병맛: 몇 번째 편·형식(A/B)·길이 — 소재는 작가가 고른다(BM_WRITING)
        out.update(bm_no=bm_index(d) + 1, bm_total=(BM_TO - BM_FROM).days + 1, format=BM_FORMAT[k], series=BM_SERIES[k],
                   length_sec=list(BM_SEC[k]))
    if k == SCI:                                           # 무엇을 쓸지도 코드가 정한다 — 그날 catalog 항목 그대로(숫자는 facts 에서만)
        e = sci_entry(sci_n(d)) or {}
        out.update(src_n=e.get("n"), sci_no=sci_index(d) + 1, format=e.get("format"),
                   entry={k_: e[k_] for k_ in SCI_ENTRY_KEYS if k_ in e})
    return out


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
