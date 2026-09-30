#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주간 '띠별 운세 풀이' 롱폼(8~12분 · 16:9) — 주 배정 · 순위표 · 대본 검사 · 올리기 (2026-10-01).

왜: 매일 아침 8초짜리 '12띠 한 장 표' 쇼츠가 처음으로 쇼츠 천장을 넘었다(9/30 첫 편 18시간 5,700회 ·
  좋아요 101 · 스튜디오 "다른 쇼츠보다 9.8배"). 그런데 유입의 98.4% 가 쇼츠 피드이고, 쇼츠 피드 시청은
  YPP 시청 시간에 들어가지 않는다. 표를 본 시청자(55세 이상 87%)가 이어서 볼 롱폼이 필요하다 —
  경쟁 채널은 시니어 대상 '띠별 운세 풀이' 롱폼을 돌리고 있고 우리는 없다.

구성(코드가 고정): 인트로(이번 주 흐름 20~30초) → 쥐띠~돼지띠 12장(장마다 40~50초:
  이번 주 한 줄 · 금전 · 건강 · 사람/가족 · 행운의 요일/색 · 조심할 것) → 마무리(매일 아침 8초 표 안내).
  한 여성 목소리(Supertonic 프리셋 하나), 큰 글자. '재미로 보는 운세' 고지는 화면·말·설명란 셋 다.

루틴(Sonnet 5.5)은 ★글만 쓴다. 어느 주인지·순위(1~12위)·점수·출생연도·장 순서·섹션 이름은 코드가 정하고,
  분량·순서·금지어·반복은 코드가 검사한다. 못 넘으면 렌더도 업로드도 없이 빨간불이다
  (루틴 프롬프트의 부탁은 자주 무시된다 — 코드로 막은 것만 지켜진다). 루틴은 git 을 손으로 만지지 않는다:

    python pipeline/weekly_fortune.py week           # 이번에 쓸 주·파일 이름·순위표·분량·빈 뼈대(JSON)
    python pipeline/weekly_fortune.py check <파일>   # 파이프라인과 똑같은 검사
    python pipeline/weekly_fortune.py push <파일>    # 검사 통과 시 routine/weekly_fortune 에 올린다(= 실제 업로드)

순위표: fortune_card(매일 표)와 ★같은 방식 — 해시로 순서·점수·한 줄을 정한다. 씨앗만 날짜 대신 주 번호
  ('2026-W41')라 같은 주면 언제 돌려도 같은 표이고, 월요일 하루 표와 똑같아지지는 않는다.
주: '내일이 속한 ISO 주'. 일요일 저녁 루틴 → 다음 주(월~일) · 늦게 돌아 월요일이 돼도 같은 주.
멱등(주 단위): ① push 가 같은 주 파일이 이미 있으면 거절 ② 워크플로는 이 push 에서 ★새로 추가된 파일만
  ③ ledger(주 번호) ④ 유튜브 설명란 끝 줄 '주간 띠별 운세 2026-W41' 표식.
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

import fortune_card as FC  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
ANIMALS = FC.ANIMALS
WEEKDAYS = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")
WD1 = "월화수목금토일"

BRANCH = "routine/weekly_fortune"      # ★누적 브랜치 — 지난 대본이 곧 반복 검사 이력이다
OUT_DIR = "output/weekly_fortune"      # shorts.yml(output/news/**_storyboard.json)과 겹치지 않는 경로
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_weekly_fortune\.json$")
WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
SAMPLE = os.path.join(ROOT, "docs", "samples", "weekly_fortune_sample.json")

MARKER = "주간 띠별 운세"              # 설명란 끝 줄 '주간 띠별 운세 2026-W41' — 유튜브 쪽 중복 판정
PLAYLIST = os.environ.get("WEEKLY_PLAYLIST") or "주간 띠별 운세"
PLAYLIST_DESC = ("매주 일요일 저녁, 다음 한 주의 띠별 운세를 쥐띠부터 돼지띠까지 풀어 드려요. "
                 "금전·건강·가족운과 행운의 요일·색까지. 45~96년생 전부, 재미로 보는 운세예요.")
DAILY_PLAYLIST = "오늘의 띠별 운세 | 매일 아침 1위~12위"     # run_pipeline.FORTUNE_PLAYLIST 와 같아야 한다
CATEGORY = "24"                        # 엔터테인먼트(run_pipeline.category_for 의 운세와 같다)
SYNTHETIC = False                      # 그림체 토픽(운세)은 표시 대상 아님 — run_pipeline.ILLUSTRATED_TOPICS 관례
VOICE = os.environ.get("WEEKLY_VOICE") or "F2"   # 차분한 여성(사연 드라마 화자). F3·F4 는 '1위'를 '2비'로 읽는다
TAGS = ["운세", "띠별운세", "주간운세", "이번주운세", "12띠운세", "띠운세", "금전운", "건강운", "재물운", "오늘의운세"]
HASHTAGS = "#운세 #띠별운세 #주간운세 #이번주운세 #띠별운세풀이"
CREDIT = "🎙️ 목소리: Supertonic (Supertone · OpenRAIL-M) · 🎨 그림: AI 생성"
DISCLAIMER = "※ 재미로 보는 운세입니다. 건강·돈 문제는 꼭 전문가와 상의하세요."

# ── 분량 ─────────────────────────────────────────────────────
# Supertonic 은 분당 ~450자(공백 포함 · 조각 앞뒤 무음 포함)를 읽는다(2026-09-29 실측). 어르신 청취용으로
#   0.92배로 늦춘다(사연 드라마와 같다). 이 파이프라인은 조각 앞뒤 무음(각 ~0.5초)을 잘라 쉼을 직접 넣으므로
#   말만 재면 조금 빠르다 — 2026-10-01 F2 재측정: 줄글 469자 · 출생연도 목록 줄 422자 · 짧은 줄 ~560자/분.
#   → 예상 길이는 470자/분으로 잰다(8분 하한을 넘기려면 빠른 쪽으로 잡는 게 안전하다).
CPM = 470
TEMPO = float(os.environ.get("WEEKLY_TEMPO", "0.92"))
GAP_SECTION = 0.45        # 섹션 사이(원본 속도 기준 초)
GAP_PART = 1.2            # 장이 바뀔 때 — 장 제목 카드가 먼저 뜬다
LEAD, TAIL = 0.3, 1.5     # 맨 앞 · 맨 뒤
EST_MIN = (8.0, 12.0)     # 예상 길이(분) — 이 밖이면 검사 실패
RENDER_MIN = (7.0, 13.0)  # 렌더 후 실제 길이(분) — 합성이 깨졌을 때 잡는다
FIELD = {                 # 루틴이 쓰는 칸 — 글자 수(공백 포함)
    "headline": (10, 40),
    "money": (30, 120), "health": (30, 120), "people": (30, 120),
    "caution": (20, 90),
}
INTRO_CHARS = (60, 150)   # 코드 인사(~30자)·안내(~40자)가 붙어 20~30초
CLOSING_CHARS = (0, 90)
TITLE_HOOK_MAX = 24
CH_SPOKEN = (230, 360)    # 장 하나 읽는 글(코드 문구 포함) ≈ 37~56초. 권장 250~320(≈40~50초)
SIMILAR = 0.8             # 같은 칸끼리 글자쌍 자카드 — 이 이상이면 복사로 본다
HISTORY_SIMILAR = 0.85
MIN_DAYS, MIN_COLORS = 4, 5   # 12장에 걸쳐 행운의 요일·색이 이만큼은 달라야 한다(찍어 낸 티 방지)

SECTIONS = (("money", "금전운", "금전운."), ("health", "건강운", "건강운."), ("people", "사람·가족운", "사람과 가족."))
COLORS = {
    "빨간색": (214, 58, 58), "주황색": (238, 138, 48), "노란색": (245, 205, 60), "연두색": (158, 208, 88),
    "초록색": (64, 158, 92), "청록색": (38, 158, 158), "하늘색": (118, 188, 238), "파란색": (48, 108, 208),
    "남색": (52, 62, 150), "보라색": (140, 92, 190), "자주색": (152, 52, 112), "분홍색": (240, 150, 180),
    "살구색": (250, 190, 150), "베이지색": (225, 205, 170), "갈색": (140, 95, 60), "흰색": (245, 245, 245),
    "회색": (150, 150, 156), "검은색": (40, 40, 44), "금색": (212, 175, 55), "은색": (196, 196, 206),
}

INTRO_TAIL = "쥐띠부터 돼지띠까지 차례로 풀어 드릴게요. 내 띠 시간은 설명란 목차에 있어요."
OUTRO_FIXED = ("매일 아침 여섯 시에는 팔 초짜리 오늘의 띠별 운세 표가 올라와요. "
               "내 띠가 오늘 몇 위인지 아침마다 확인해 보세요. "
               "오늘 들으신 운세는 재미로 보시고, 이번 한 주도 건강하고 편안하게 보내세요.")

# ── 금지어(루틴이 쓴 모든 칸) ─────────────────────────────────
BAN = {
    "자극적인 말": ("충격", "경악", "역대급", "미쳤", "소름", "헉", "대박", "패닉", "폭망", "무조건",
                  "인생역전", "떼돈", "벼락부자"),
    "겁주는 말": ("죽음", "죽는", "죽을", "사망", "급사", "횡사", "객사", "파산", "망한다", "망합니다", "망해요",
                "망할", "쫄딱", "재앙", "저주", "흉사", "삼재", "큰일 납", "큰일 나", "사고가 납", "사고가 나",
                "사고 납", "불행이 닥", "액운이 닥", "이혼", "사기당", "배신당"),
    "의료 조언": ("치료", "완치", "처방", "복용", "약을 끊", "약 끊", "약을 줄", "약 줄이", "병원에 가지",
                "병원 갈 필요", "수술", "항암", "진단", "당뇨", "고혈압", "혈압약", "영양제", "건강식품",
                "효능", "특효", "보약", "한약"),
    "투자·도박 조언": ("주식", "코인", "비트코인", "가상화폐", "암호화폐", "매수", "매도", "종목", "로또", "복권",
                   "대출", "빚을 내", "빚내", "투자하세요", "투자해 보", "투자하기 좋", "투자 적기", "재테크",
                   "펀드", "부동산", "원금", "수익률", "몇 배"),
    "단정·장담": ("반드시 돈", "틀림없이", "확실히 돈", "백 퍼센트", "백프로", "퍼센트"),
    "무속 영업": ("부적", "굿을", "굿 한", "굿판", "천도재", "기도비", "점집"),
}
CANCER_RE = re.compile(r"(?<![가-힣])암(?=[이을은에도과\s.,!?]|$)")
# 읽는 글에 쓸 수 있는 글자 — 한글·공백·문장부호만. 숫자·영어·이모지·주소·해시태그는 TTS 가 엉뚱하게 읽는다.
SPOKEN_OK = re.compile(r"[가-힣\s.,!?~…'\"“”‘’()\-:·]")
TITLE_OK = re.compile(r"[가-힣\s.,!?~…'\"“”‘’()\-:·0-9]")
ANIMAL_NAME_RE = re.compile(r"(" + "|".join(sorted(ANIMALS, key=len, reverse=True)) + r")띠")


# ── 주 ───────────────────────────────────────────────────────
def target_monday(now: dt.datetime | None = None) -> dt.date:
    """이번에 쓸 주의 월요일 — '내일이 속한 ISO 주'. 일요일 → 다음 주, 월~토 → 이번 주."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    t = now.date() + dt.timedelta(days=1)
    return t - dt.timedelta(days=t.weekday())


def week_key(monday: dt.date) -> str:
    y, w, _ = monday.isocalendar()
    return f"{y}-W{w:02d}"


def monday_of(week: str) -> dt.date | None:
    m = WEEK_RE.match(str(week or "").strip())
    if not m:
        return None
    try:
        return dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        return None


def file_name(monday: dt.date) -> str:
    return f"{monday.isoformat()}_weekly_fortune.json"


def range_label(monday: dt.date, short: bool = False) -> str:
    """'10월 5일(월) ~ 11일(일)' · 달이 바뀌면 '9월 28일(월) ~ 10월 4일(일)'. short 면 요일 없이."""
    s = monday + dt.timedelta(days=6)
    a = f"{monday.month}월 {monday.day}일" + ("" if short else "(월)")
    b = (f"{s.day}일" if s.month == monday.month else f"{s.month}월 {s.day}일") + ("" if short else "(일)")
    return f"{a} ~ {b}" if not short else f"{a}~{b}"


def publish_at(monday: dt.date, now: dt.datetime | None = None, hhmm: str | None = None) -> str | None:
    """공개 시각(UTC RFC3339) — 그 주 월요일 전날(일) 20:00 KST. 이미 지났거나 10분 안이면 None(바로 공개).

    일요일 19:07 KST 전후는 AI 소식 저녁 편이 올라가는 시간이라 피한다(렌더는 17시대에 끝난다)."""
    hhmm = hhmm or os.environ.get("WEEKLY_PUBLISH_HHMM") or "20:00"
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except ValueError:
        h, m = 20, 0
    when = dt.datetime.combine(monday - dt.timedelta(days=1), dt.time(h, m), tzinfo=KST)
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    if when <= now + dt.timedelta(minutes=10):
        return None
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 순위표 ───────────────────────────────────────────────────
def table_rows(week: str) -> list[dict]:
    """그 주의 12띠 순위표 — fortune_card.build_rows 와 같은 방식, 씨앗만 주 번호."""
    monday = monday_of(week) or dt.date.today()
    return FC.build_rows({"topic": "fortune", "date": monday.isoformat(), "notes": "MODE=weekly"}, key=week)


def tone_of(rank: int) -> str:
    return "밝게(좋은 소식 위주)" if rank <= 3 else ("차분하게(무난·소소한 기쁨)" if rank <= 8 else "다정하게(조심할 점을 부드럽게)")


def years_label(animal: str) -> str:
    return "·".join(f"{y % 100:02d}" for y in FC.years_of(animal)) + "년생"


def years_spoken(animal: str) -> str:
    return ", ".join(f"{y % 100:02d}년생" for y in FC.years_of(animal))


# ── 글 도구 ──────────────────────────────────────────────────
def _s(v) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _end(text: str) -> str:
    t = _s(text)
    return t if not t or t[-1] in ".!?…" else t + "."


def _bigrams(s: str) -> set:
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", s or "")
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def norm_animal(v) -> str:
    a = _s(v)
    a = a[:-1] if a.endswith("띠") else a
    return FC.ALIAS.get(a, a)


def norm_day(v) -> str:
    d = _s(v)
    if len(d) == 1 and d in WD1:
        return d + "요일"
    return d


def ban_hits(text: str) -> list[str]:
    out = []
    for group, words in BAN.items():
        hit = [w for w in words if w in text]
        if group == "의료 조언" and CANCER_RE.search(text):
            hit.append("암")
        if hit:
            out.append(f"{group}: {', '.join(hit)}")
    return out


def bad_chars(text: str, ok=SPOKEN_OK) -> list[str]:
    return sorted({c for c in text if not ok.fullmatch(c)})


def routine_texts(sc: dict) -> list[tuple[str, str]]:
    """(어디, 글) — 루틴이 쓴 모든 칸."""
    out = [("intro", _s(sc.get("intro"))), ("closing", _s(sc.get("closing"))), ("title_hook", _s(sc.get("title_hook")))]
    for i, ch in enumerate(sc.get("chapters") or []):
        if isinstance(ch, dict):
            nm = norm_animal(ch.get("animal")) or f"{i + 1}장"
            for k in ("headline", "money", "health", "people", "caution", "lucky_day", "lucky_color"):
                out.append((f"{nm}띠.{k}", _s(ch.get(k))))
    return [(w, t) for w, t in out if t]


# ── 조립 ─────────────────────────────────────────────────────
def compose(sc: dict) -> dict:
    """대본 → 렌더 계획(파트·조각·화면). 검사를 통과한 대본을 넣는다(모양이 틀리면 KeyError 가 날 수 있다)."""
    week = _s(sc.get("week"))
    monday = monday_of(week)
    if not monday:
        raise ValueError(f"week {week!r} — '2026-W41' 모양이어야 한다")
    rows = table_rows(week)
    by = {r["animal"]: r for r in rows}
    sun = monday + dt.timedelta(days=6)
    head = (f"{monday.month}월 {monday.day}일부터 "
            + (f"{sun.day}일" if sun.month == monday.month else f"{sun.month}월 {sun.day}일")
            + "까지, 이번 주 띠별 운세입니다.")
    parts = [{"id": "intro", "title": "이번 주 흐름", "chunks": [
        {"text": head, "slide": {"kind": "title"}},
        {"text": _end(sc.get("intro")), "slide": {"kind": "table"}},
        {"text": INTRO_TAIL, "slide": {"kind": "table"}},
    ]}]
    for n, ch in enumerate(sc.get("chapters") or [], 1):
        a = norm_animal(ch.get("animal"))
        r = by[a]
        base = {"animal": a, "rank": r["rank"], "score": r["score"], "index": n}
        card = {"kind": "card", **base, "headline": _s(ch.get("headline"))}
        chunks = [
            {"text": f"{a}띠입니다. {years_spoken(a)}. 이번 주 {r['rank']}위예요.", "slide": card},
            {"text": _end(ch.get("headline")), "slide": card},
        ]
        for key, label, spoken in SECTIONS:
            chunks.append({"text": f"{spoken} {_end(ch.get(key))}",
                           "slide": {"kind": "section", "key": key, "label": label, "body": _s(ch.get(key)), **base}})
        day, color = norm_day(ch.get("lucky_day")), _s(ch.get("lucky_color"))
        chunks.append({"text": f"행운의 요일은 {day}, 행운의 색은 {color}이에요.",
                       "slide": {"kind": "lucky", "day": day, "color": color, **base}})
        chunks.append({"text": f"조심할 것. {_end(ch.get('caution'))}",
                       "slide": {"kind": "section", "key": "caution", "label": "조심할 것",
                                 "body": _s(ch.get("caution")), **base}})
        parts.append({"id": f"ch{n:02d}", "title": f"{a}띠 ({years_label(a)}) · {r['rank']}위",
                      "animal": a, "rank": r["rank"], "chunks": chunks})
    outro = []
    if _s(sc.get("closing")):
        outro.append({"text": _end(sc.get("closing")), "slide": {"kind": "outro"}})
    outro.append({"text": OUTRO_FIXED, "slide": {"kind": "outro"}})
    parts.append({"id": "outro", "title": "마무리 · 매일 아침 8초 운세 표", "chunks": outro})
    plan = {"week": week, "monday": monday.isoformat(), "range": range_label(monday), "rows": rows,
            "parts": parts, "title_hook": _s(sc.get("title_hook")), "intro": _s(sc.get("intro"))}
    plan["stats"] = stats(plan)
    return plan


def stats(plan: dict) -> dict:
    chars = sum(len(c["text"]) for p in plan["parts"] for c in p["chunks"])
    gaps = sum(GAP_SECTION * (len(p["chunks"]) - 1) for p in plan["parts"]) + GAP_PART * (len(plan["parts"]) - 1)
    sec = (chars / (CPM / 60.0) + gaps + LEAD + TAIL) / TEMPO
    per = {p["id"]: sum(len(c["text"]) for c in p["chunks"]) for p in plan["parts"]}
    return {"chars": chars, "est_sec": round(sec, 1), "est_min": round(sec / 60.0, 1), "per_part": per,
            "chunks": sum(len(p["chunks"]) for p in plan["parts"])}


def part_sec(chars: int, chunks: int) -> float:
    return (chars / (CPM / 60.0) + GAP_SECTION * max(0, chunks - 1)) / TEMPO


# ── 검사 ─────────────────────────────────────────────────────
def check(sc, path: str = "", now: dt.datetime | None = None, history: list | None = None,
          strict: bool = True) -> tuple[list[str], list[str]]:
    """(오류, 경고). 오류가 하나라도 있으면 렌더·업로드하지 않는다.

    strict=False(수동 점검·견본): 주가 '이번에 쓸 주'가 아니어도 경고로만(업로드 없는 실행에서만 쓴다)."""
    errs: list[str] = []
    warns: list[str] = []
    if not isinstance(sc, dict):
        return ["대본이 JSON 객체가 아니다"], []
    bad = errs.append

    # ① 주·파일 이름
    week = _s(sc.get("week"))
    monday = monday_of(week)
    if not monday:
        bad(f"week {week!r} — '2026-W41' 처럼 ISO 주 번호여야 한다(week 명령의 WEEK)")
    else:
        want = target_monday(now)
        if monday != want:
            (bad if strict else warns.append)(
                f"week {week} 는 이번에 쓸 주({week_key(want)} · {range_label(want)})가 아니다")
        if path:
            name = os.path.basename(path)
            m = NAME_RE.match(name)
            if not m:
                (bad if strict else warns.append)(
                    f"파일 이름 {name!r} — <월요일 날짜>_weekly_fortune.json 이어야 한다(week 명령의 FILE)")
            elif m.group(1) != monday.isoformat():
                bad(f"파일 이름 날짜 {m.group(1)} ≠ week {week} 의 월요일 {monday.isoformat()}")
    if _s(sc.get("kind")) not in ("", "weekly_fortune"):
        bad(f"kind {sc.get('kind')!r} — 'weekly_fortune'")

    # ② 12장 · 순서
    chs = sc.get("chapters")
    if not isinstance(chs, list) or len(chs) != 12:
        bad(f"chapters 가 12장이 아니다({len(chs) if isinstance(chs, list) else '없음'}) — 쥐띠부터 돼지띠까지 12장")
        chs = chs if isinstance(chs, list) else []
    got = [norm_animal(c.get("animal")) if isinstance(c, dict) else "" for c in chs]
    if len(chs) == 12 and got != ANIMALS:
        wrong = [f"{i + 1}장={g or '?'}(→{w})" for i, (g, w) in enumerate(zip(got, ANIMALS)) if g != w]
        bad("띠 순서가 틀렸다 — 쥐·소·호랑이·토끼·용·뱀·말·양·원숭이·닭·개·돼지 순서: " + ", ".join(wrong[:4]))

    # ③ 칸마다 글자 수·요일·색
    days, colors = [], []
    for i, c in enumerate(chs):
        if not isinstance(c, dict):
            bad(f"{i + 1}장이 객체가 아니다")
            continue
        nm = (got[i] or f"{i + 1}장") + "띠"
        for k, (lo, hi) in FIELD.items():
            n = len(_s(c.get(k)))
            if not lo <= n <= hi:
                bad(f"{nm} {k} {n}자 — {lo}~{hi}자")
        day = norm_day(c.get("lucky_day"))
        if day not in WEEKDAYS:
            bad(f"{nm} lucky_day {c.get('lucky_day')!r} — 월요일~일요일 중 하나")
        col = _s(c.get("lucky_color"))
        if col not in COLORS:
            bad(f"{nm} lucky_color {col!r} — 이 중 하나: {' '.join(COLORS)}")
        days.append(day)
        colors.append(col)
        if "rank" in c and got[i] in ANIMALS and monday:
            want_rank = {r["animal"]: r["rank"] for r in table_rows(week)}[got[i]]
            if c.get("rank") != want_rank:
                bad(f"{nm} rank {c.get('rank')!r} ≠ 순위표 {want_rank}위 — 순위는 코드가 정한다(week 명령)")
    if len(chs) == 12:
        if len(set(days)) < MIN_DAYS:
            bad(f"행운의 요일이 {len(set(days))}가지뿐 — 12장에 걸쳐 {MIN_DAYS}가지 이상")
        if len(set(colors)) < MIN_COLORS:
            bad(f"행운의 색이 {len(set(colors))}가지뿐 — 12장에 걸쳐 {MIN_COLORS}가지 이상")

    n = len(_s(sc.get("intro")))
    if not INTRO_CHARS[0] <= n <= INTRO_CHARS[1]:
        bad(f"intro {n}자 — {INTRO_CHARS[0]}~{INTRO_CHARS[1]}자(코드 인사·안내가 붙어 20~30초 · 권장 90~120자)")
    n = len(_s(sc.get("closing")))
    if n > CLOSING_CHARS[1]:
        bad(f"closing {n}자 — {CLOSING_CHARS[1]}자 이내(8초 표 안내·고지는 코드가 붙인다)")
    th = _s(sc.get("title_hook"))
    if len(th) > TITLE_HOOK_MAX:
        bad(f"title_hook {len(th)}자 — {TITLE_HOOK_MAX}자 이내(유튜브 제목 뒤쪽에 붙는다)")
    if th and bad_chars(th, TITLE_OK):
        bad(f"title_hook 에 쓸 수 없는 글자: {' '.join(bad_chars(th, TITLE_OK))}")

    # ④ 글자·금지어
    for where, text in routine_texts(sc):
        if where == "title_hook":
            pass
        else:
            bc = bad_chars(text)
            if bc:
                bad(f"{where}: 읽는 글에 쓸 수 없는 글자 {' '.join(repr(x) for x in bc[:6])} — "
                    "숫자는 한글로(세 번·두 가지), 영어·이모지·주소·해시태그 없이")
        for h in ban_hits(text):
            bad(f"{where}: 금지어({h}) — 운세는 재미로, 겁주거나 병·약·투자를 권하지 않는다")

    # ⑤ 인트로·제목에서 이름을 부른 띠는 1~3위만(표와 어긋나는 말을 막는다)
    if monday:
        rank = {r["animal"]: r["rank"] for r in table_rows(week)}
        for key in ("intro", "title_hook"):
            for a in dict.fromkeys(ANIMAL_NAME_RE.findall(_s(sc.get(key)))):
                a = FC.ALIAS.get(a, a)
                if a in rank and rank[a] > 3:
                    bad(f"{key} 가 {a}띠를 불렀는데 {a}띠는 이번 주 {rank[a]}위다 — {key} 에서 이름을 부를 띠는 1~3위만")

    # ⑥ 반복 — 같은 대본 안(다른 띠끼리) · 지난 대본·견본(같은 띠)
    if len(chs) == 12 and all(isinstance(c, dict) for c in chs):
        for k in ("headline", "money", "health", "people", "caution"):
            vals = [(got[i], _s(c.get(k))) for i, c in enumerate(chs)]
            for x in range(12):
                for y in range(x + 1, 12):
                    if vals[x][1] and similarity(vals[x][1], vals[y][1]) >= SIMILAR:
                        bad(f"{vals[x][0]}띠와 {vals[y][0]}띠의 {k} 가 거의 같다 — 띠마다 다르게 쓴다")
        for old in history or []:
            ow = _s(old.get("week"))
            if ow and ow == week:
                continue
            oc = {norm_animal(c.get("animal")): c for c in old.get("chapters") or [] if isinstance(c, dict)}
            for i, c in enumerate(chs):
                o = oc.get(got[i])
                if not o:
                    continue
                for k in ("headline", "money", "health", "people", "caution"):
                    if _s(c.get(k)) and similarity(_s(c.get(k)), _s(o.get(k))) >= HISTORY_SIMILAR:
                        src = "견본" if old.get("_sample") else (ow or "지난 대본")
                        bad(f"{got[i]}띠 {k} 가 {src} 와 거의 같다 — 매주 새로 쓴다(복사·견본 옮기기 금지)")

    # ⑦ 길이 — 장마다 · 전체(모양만 맞으면 다른 오류가 있어도 잰다 — 루틴이 한 번에 다 고치게)
    shape_ok = bool(monday) and len(chs) == 12 and got == ANIMALS and all(isinstance(c, dict) for c in chs)
    if shape_ok:
        plan = compose(sc)
        for p in plan["parts"]:
            if not p["id"].startswith("ch"):
                continue
            n = plan["stats"]["per_part"][p["id"]]
            if not CH_SPOKEN[0] <= n <= CH_SPOKEN[1]:
                bad(f"{p['animal']}띠 장이 {n}자(≈{part_sec(n, len(p['chunks'])):.0f}초) — "
                    f"코드 문구 포함 {CH_SPOKEN[0]}~{CH_SPOKEN[1]}자(권장 250~320자 ≈ 40~50초)")
        est = plan["stats"]["est_min"]
        if not EST_MIN[0] <= est <= EST_MIN[1]:
            bad(f"예상 길이 {est}분({plan['stats']['chars']:,}자) — {EST_MIN[0]:.0f}~{EST_MIN[1]:.0f}분"
                "(목표 ~10분 ≈ 3,700~4,100자)")
    return errs, warns


def check_duration(sec: float | None) -> str | None:
    if sec is None:
        return None
    lo, hi = RENDER_MIN
    if not lo * 60 <= sec <= hi * 60:
        return f"렌더 길이 {sec / 60:.1f}분 — {lo:.0f}~{hi:.0f}분 밖(합성이 깨졌을 수 있다)"
    return None


# ── 업로드 메타 ───────────────────────────────────────────────
def marker(week: str) -> str:
    return f"{MARKER} {week}"


def title_for(plan: dict) -> str:
    monday = dt.date.fromisoformat(plan["monday"])
    hook = plan.get("title_hook") or "쥐띠부터 돼지띠까지 금전·건강·가족운"
    return f"이번 주 띠별 운세 {range_label(monday, short=True)} | {hook} · 45~96년생 전부"[:100]


def description_for(plan: dict, chapters: str, daily_playlist_id: str | None = None) -> str:
    monday = dt.date.fromisoformat(plan["monday"])
    daily = "📅 매일 아침 6시, 8초짜리 '오늘의 띠별 운세' 1위~12위 표가 올라와요."
    if daily_playlist_id:
        daily += f"\n▶ 오늘의 띠별 운세 모아 보기: https://www.youtube.com/playlist?list={daily_playlist_id}"
    desc = (f"{range_label(monday)}, 이번 주 12띠 운세를 띠마다 풀어 드려요.\n"
            "금전운 · 건강운 · 사람과 가족운 · 행운의 요일과 색 · 조심할 것\n\n"
            f"{plan.get('intro', '')}\n\n"
            f"⏱ 목차\n{chapters}\n\n{daily}\n\n{DISCLAIMER}\n{CREDIT}\n\n{HASHTAGS}\n\n{marker(plan['week'])}")
    return desc[:4900]


def link_line(video_id: str) -> str:
    return f"📺 이번 주 띠별 운세 풀이(약 10분): https://youtu.be/{video_id}"


def append_link(description: str, video_id: str | None) -> str:
    """운세 쇼츠 설명 끝에 주간 롱폼 한 줄. 이미 있으면 그대로."""
    if not video_id or f"youtu.be/{video_id}" in (description or ""):
        return description
    return f"{(description or '').rstrip()}\n\n{link_line(video_id)}"


def latest_public_video(yt, title: str = PLAYLIST, max_pages: int = 2) -> str | None:
    """'주간 띠별 운세' 재생목록에서 가장 최근에 공개된 영상 id. 없으면 None.

    쿼터: playlists.list 1 + playlistItems.list 1~2 = 2~3 units. 예약 공개 전(비공개)은 건너뛴다."""
    import upload_youtube_novel as N
    pid = N.find_playlist(yt, title)
    if not pid:
        return None
    best, token = None, None
    for _ in range(max_pages):
        r = yt.playlistItems().list(part="snippet,status,contentDetails", playlistId=pid,
                                    maxResults=50, pageToken=token).execute()
        for it in r.get("items") or []:
            if ((it.get("status") or {}).get("privacyStatus")) != "public":
                continue
            vid = ((it.get("contentDetails") or {}).get("videoId")
                   or ((it.get("snippet") or {}).get("resourceId") or {}).get("videoId"))
            when = ((it.get("contentDetails") or {}).get("videoPublishedAt")
                    or (it.get("snippet") or {}).get("publishedAt") or "")
            if vid and (best is None or when > best[0]):
                best = (when, vid)
        token = r.get("nextPageToken")
        if not token:
            break
    return best[1] if best else None


def already_uploaded(uploads: list[dict], week: str) -> str | None:
    """최근 업로드(ai_news.recent_uploads 모양)에 이 주 표식이 있으면 그 영상 id."""
    mk = marker(week)
    for u in uploads or []:
        if mk in (u.get("description") or ""):
            return u.get("video_id") or "?"
    return None


# ── 이력(반복 검사) ───────────────────────────────────────────
def _git(*args: str, root: str | None = None) -> str:
    try:
        r = subprocess.run(["git", "-C", root or ROOT, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def fetch_branch(root: str | None = None) -> None:
    _git("fetch", "-q", "--no-tags", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}", root=root)


def weeks_on_branch(root: str | None = None) -> dict:
    """원격 누적 브랜치의 {주: 대본}."""
    out = {}
    ref = f"origin/{BRANCH}"
    for name in _git("ls-tree", "-r", "--name-only", ref, "--", OUT_DIR, root=root).splitlines():
        if not NAME_RE.match(os.path.basename(name.strip())):
            continue
        try:
            sc = json.loads(_git("show", f"{ref}:{name.strip()}", root=root) or "null")
        except json.JSONDecodeError:
            continue
        if isinstance(sc, dict) and _s(sc.get("week")):
            out[_s(sc["week"])] = sc
    return out


def load_history(root: str | None = None, dirs=(), limit: int = 8) -> list[dict]:
    """반복 검사 이력 = 누적 브랜치 + 같은 폴더의 다른 대본(최근 limit 주) + 견본."""
    by = dict(weeks_on_branch(root))
    for d in dirs or ():
        if not d or not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if NAME_RE.match(n):
                try:
                    with open(os.path.join(d, n), encoding="utf-8") as f:
                        sc = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(sc, dict) and _s(sc.get("week")):
                    by.setdefault(_s(sc["week"]), sc)
    hist = [by[k] for k in sorted(by)[-limit:]]
    try:
        with open(SAMPLE, encoding="utf-8") as f:
            smp = json.load(f)
        hist.append({**smp, "_sample": True})
    except (OSError, json.JSONDecodeError):
        pass
    return hist


def check_file(path: str, now: dt.datetime | None = None, root: str | None = None,
               strict: bool = True) -> tuple[list[str], list[str], dict]:
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    hist = load_history(root, dirs=[os.path.join(root or ROOT, OUT_DIR), os.path.dirname(os.path.abspath(path))])
    if os.path.abspath(path) == os.path.abspath(SAMPLE):
        hist = [h for h in hist if not h.get("_sample")]
    errs, warns = check(sc, path, now=now, history=hist, strict=strict)
    return errs, warns, sc


# ── 올리기(루틴용) ────────────────────────────────────────────
def _run(args: list[str], cwd: str) -> tuple[int, str]:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def push(path: str, now: dt.datetime | None = None, root: str | None = None,
         remote: str = "origin") -> tuple[bool, str]:
    """검사를 통과한 대본을 routine/weekly_fortune 에 올린다. ★세션 브랜치(claude/*)를 건드리지 않는다.

    임시 작업 폴더(git worktree)에서 원격 routine/weekly_fortune(없으면 main) 위에 파일 하나만 커밋해 push 한다.
    같은 주 파일이 이미 있으면 올리지 않는다. 이 push 가 weekly-fortune.yml 을 깨운다(= 실제 업로드)."""
    root = root or ROOT
    name = os.path.basename(path)
    if not NAME_RE.match(name):
        return False, f"파일 이름 {name!r} — <월요일 날짜>_weekly_fortune.json 이어야 한다(week 명령의 FILE)"
    fetch_branch(root)
    _run(["git", "fetch", "-q", "--no-tags", remote, f"+refs/heads/main:refs/remotes/{remote}/main"], root)
    errs, _, sc = check_file(path, now=now, root=root)
    if _s(sc.get("week")) in weeks_on_branch(root):
        errs.append(f"{sc.get('week')} 는 이미 {BRANCH} 에 있다 — 같은 주는 다시 올리지 않는다")
    if errs:
        return False, "검사 실패 — 먼저 고쳐라:\n  " + "\n  ".join(errs)
    has = _run(["git", "rev-parse", "--verify", "-q", f"{remote}/{BRANCH}"], root)[0] == 0
    base = f"{remote}/{BRANCH}" if has else f"{remote}/main"
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="weekly_fortune_push_")
    wt = os.path.join(tmp, "wt")
    rc, out = _run(["git", "worktree", "add", "-q", "--detach", wt, base], root)
    if rc:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f"작업 폴더를 못 만들었다({base}): {out[-300:]}"
    try:
        dest = os.path.join(wt, OUT_DIR, name)
        if os.path.exists(dest):
            return False, f"{BRANCH} 에 {name} 가 이미 있다 — 같은 주는 다시 올리지 않는다"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(path, dest)
        ident = [] if _run(["git", "config", "user.email"], root)[1] else [
            "-c", "user.name=주간 운세 루틴", "-c", "user.email=weekly-fortune-routine@users.noreply.github.com"]
        _run(["git", "add", f"{OUT_DIR}/{name}"], wt)
        rc, out = _run(["git", *ident, "commit", "-q", "-m", f"chore: 주간 띠별 운세 대본(루틴) {sc.get('week')}"], wt)
        if rc:
            return False, f"커밋 실패: {out[-300:]}"
        rc, out = _run(["git", "push", "-q", remote, f"HEAD:refs/heads/{BRANCH}"], wt)
        if rc:
            return False, f"push 실패 — push 를 한 번 더 돌려라: {out[-300:]}"
        return True, f"{BRANCH} 에 올렸다({name}) — Actions(weekly-fortune.yml)가 렌더·업로드한다"
    finally:
        _run(["git", "worktree", "remove", "--force", wt], root)
        shutil.rmtree(tmp, ignore_errors=True)


# ── week 명령 출력 ────────────────────────────────────────────
def skeleton(week: str) -> dict:
    return {
        "kind": "weekly_fortune", "week": week,
        "title_hook": "<선택 · 24자 이내 · 이번 주를 한마디로>",
        "intro": "<이번 주 전체 흐름 · 60~150자(권장 90~120) · 1~3위 띠만 이름을 불러도 된다>",
        "chapters": [{"animal": a, "headline": "<이번 주 한 줄 10~40자>", "money": "<30~120자>",
                      "health": "<30~120자>", "people": "<30~120자>", "lucky_day": "<월요일~일요일>",
                      "lucky_color": "<색 목록 중 하나>", "caution": "<20~90자>"} for a in ANIMALS],
        "closing": "<선택 · 90자 이내 · 8초 표 안내와 '재미로' 고지는 코드가 붙인다>",
    }


def week_text(now: dt.datetime | None = None, taken: bool = False) -> str:
    import tempfile
    monday = target_monday(now)
    wk = week_key(monday)
    rows = {r["animal"]: r for r in table_rows(wk)}
    name = file_name(monday)
    out_dir = os.path.join(tempfile.gettempdir(), "weekly_fortune")      # 레포 밖 — 세션 브랜치에 커밋될 일이 없다
    os.makedirs(out_dir, exist_ok=True)
    lines = [f"WEEK={wk}", f"MONDAY={monday.isoformat()}", f"RANGE={range_label(monday)}",
             f"FILE={OUT_DIR}/{name}", f"WRITE_TO={os.path.join(out_dir, name)}", f"BRANCH={BRANCH}",
             f"TAKEN={'yes' if taken else 'no'}", "",
             "── 이번 주 순위표(코드가 정한다 — 바꾸지 말고, 순위에 맞는 말투로 쓴다) ──",
             "장  띠        순위  점수  출생연도                 표에 뜨는 한 줄      말투"]
    for n, a in enumerate(ANIMALS, 1):
        r = rows[a]
        lines.append(f"{n:>2}  {a + '띠':<6}  {r['rank']:>2}위  {r['score']:>2}점  {years_label(a):<22}  "
                     f"{r['line']:<14}  {tone_of(r['rank'])}")
    lines += ["", "── 분량(코드가 검사) ──",
              f"intro {INTRO_CHARS[0]}~{INTRO_CHARS[1]}자 · headline {FIELD['headline'][0]}~{FIELD['headline'][1]} · "
              f"money/health/people {FIELD['money'][0]}~{FIELD['money'][1]} · caution {FIELD['caution'][0]}~{FIELD['caution'][1]} · "
              f"closing ~{CLOSING_CHARS[1]} · title_hook ~{TITLE_HOOK_MAX}",
              f"장 하나(코드 문구 포함) {CH_SPOKEN[0]}~{CH_SPOKEN[1]}자 — 권장 250~320자 ≈ 40~50초 · "
              f"전체 예상 {EST_MIN[0]:.0f}~{EST_MIN[1]:.0f}분(목표 ~10분 ≈ 3,700~4,100자)",
              "행운의 색: " + " ".join(COLORS),
              "", "── 뼈대(채워서 WRITE_TO 에 저장 → check → push) ──",
              json.dumps(skeleton(wk), ensure_ascii=False, indent=1)]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="주간 띠별 운세 풀이 — 주·순위표·검사·올리기(루틴용)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week", help="이번에 쓸 주·파일 이름·순위표·뼈대")
    w.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    c = sub.add_parser("check", help="대본 검사(루틴은 push 전에 반드시)")
    c.add_argument("paths", nargs="+")
    c.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    c.add_argument("--lenient", action="store_true", help="수동 점검: 주가 달라도 경고로")
    pu = sub.add_parser("push", help="검사 통과한 대본을 routine/weekly_fortune 에 올린다(= 실제 업로드가 시작된다)")
    pu.add_argument("path")
    for x in (w, c):
        x.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):     # 윈도 콘솔(cp949)에서도 한글·기호가 깨져 죽지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    now = dt.datetime.fromisoformat(a.now).astimezone(KST) if getattr(a, "now", None) else dt.datetime.now(KST)
    if a.cmd == "push":
        ok, msg = push(a.path)
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    if not a.no_fetch:
        fetch_branch()
    if a.cmd == "week":
        print(week_text(now, taken=week_key(target_monday(now)) in weeks_on_branch()))
        return 0
    bad = 0
    for p in a.paths:
        errs, warns, sc = check_file(p, now=now, strict=not a.lenient)
        st = compose(sc)["stats"] if not errs else None
        print(f"── {os.path.basename(p)} · {sc.get('week')}"
              + (f" · {st['chars']:,}자 · 예상 {st['est_min']}분" if st else ""))
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
