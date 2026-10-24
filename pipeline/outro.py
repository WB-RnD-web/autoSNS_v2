#!/usr/bin/env python3
"""왕별이 표 쇼츠 끝인사 — '오늘의 덕담 한마디' + 댓글 초대 (2026-10-24 사용자 승인 '1번 ㄱㄱ').

왜: 댓글을 보면 어르신들이 이미 댓글 창에 자기 띠·출생연도를 적고 소원을 빈다('로또 대박 기원합니다', '조상님 고맙습니다').
  사장님이 그런 댓글에 띠·년생별 덕담 답글을 단다(스튜디오 스크립트) → '띠 남기시면 덕담 드려요'는 실제로 지키는 약속이다.
  답글은 알림으로 가고, 알림은 다시 들어오게 한다.

무엇: 모든 표 쇼츠(12띠 표·내 것 찾기·나이 표·등급표·궁합표·덕담표·신년 표) 끝에 2.0~2.5초 끝인사를 붙인다.
  화면 = 같은 배경 위에 큰 글자 한 줄(오늘의 덕담) + 작은 글자 한 줄('띠 남기시면 덕담 드려요'). 음악은 새로 넣지 않는다.
  목소리 = 내레이터가 두 문장을 짧게(덕담 → 초대). 설명란에도 같은 초대 한 줄(끝인사가 붙은 편만 — 아래 A/B).
  ★2.5초 안에 두 문장이 들어가야 한다 — Supertonic F1 실측(10/25, 줄마다): '띠 남기시면 덕담 드려요' 말소리 1.42초,
    덕담 0.66~1.22초(한글 5~8자 · 합성할 때마다 ±0.15초 흔들린다). 그래서 덕담은 한글 8자 이내로 짧게 쓰고(넘던 7줄은 10/25 바꿈),
    목소리는 쉼표 없이 읽히고, 렌더러(motion_short.outro_timing)가 앞뒤 무음을 잘라 붙인다 — 넘칠 때만 조금 빠르게(대개 1.00~1.07배).

덕담 고르기 — 코드가 날짜로 정한다(루틴 판단 없음 · 같은 날짜면 늘 같은 줄 · 그날 표 쇼츠 전부 같은 줄):
  절기 날(입동·동지·입춘 …)이면 그 절기 한 줄. 아니면 '그 요일 줄 + 그 계절 줄 + 언제나 줄' 묶음에서
  날짜 해시 순서로 보고(월·금은 그 요일 줄을 먼저 — 한 주 시작·끝 인사 · 화·수·목은 계절 줄을 먼저 · 토·일은 섞어서), 앞선 REPEAT_GAP 일에 나온 줄은 건너뛴다
  (어제와 같은 줄이 나오지 않는다 — 테스트가 1년을 본다).
  ★금지(테스트가 막는다): 겁주는 말 · 의료 장담·조언(따뜻하게 입기·물 한 잔·천천히 걷기 같은 생활 말까지만) ·
    돈·로또 약속 · '댓글 달면 복 받는다' 같은 미끼 · 종교 말 · 영어·게임 말투.

A/B(2026-10-26~11-08, 14일): 그날 나가는 표 쇼츠 '전부'에 붙이거나 '전부' 안 붙인다.
  날을 그냥 하루씩 번갈아 고르면 낮 12시 자리(띠 테마 표 ↔ 나이 표가 격일 — theme_card.ALT_FROM)와 딱 겹친다:
  끝인사 있는 날 = 늘 띠 테마 표, 없는 날 = 늘 나이 표 → 형식 차이를 끝인사 효과로 착각한다.
  그래서 거의 하루씩 번갈아 가되(같은 쪽은 많아야 이틀 연속), 두 쪽이 ① 요일을 하나씩 다 갖고(월~일 각 1번)
  ② 띠 테마 표·나이 표를 4:3 으로 나누고 ③ 06:13 신년운세 시리즈(화·토)를 2:2 로 나누게 날을 박았다(OUTRO_AB_ON).
  판정: tools/pulse_experiments.json 'outro-blessing'(11/9). 채널 맥박은 게시일(KST)로 arm() 을 불러 영상을 나눈다.
  ★끝나는 날을 조용히 넘기지 않는다: 11/9 부터는 OUTRO_DEFAULT(기본 True = 매일 켬)가 그대로 간다 — 판정에서 접으면 False 로.

    python pipeline/outro.py show [--date 2026-10-26] [--days 14]     # 날짜별 켜짐·덕담 미리보기
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys

D = dt.date
KST = dt.timezone(dt.timedelta(hours=9))

# ── 켜는 날 ────────────────────────────────────────────────
OUTRO_AB: tuple[dt.date, dt.date] | None = (D(2026, 10, 26), D(2026, 11, 8))   # A/B 기간(양 끝 포함). None = A/B 없음
# A/B 기간에 끝인사가 붙는 날 7일 — 월 10/26 · 목 10/29 · 일 11/1 · 화 11/3 · 수 11/4 · 금 11/6 · 토 11/7(입동)
#   없는 날 7일 — 화 10/27 · 수 10/28 · 금 10/30 · 토 10/31 · 월 11/2 · 목 11/5 · 일 11/8
OUTRO_AB_ON = frozenset({D(2026, 10, 26), D(2026, 10, 29), D(2026, 11, 1), D(2026, 11, 3), D(2026, 11, 4),
                         D(2026, 11, 6), D(2026, 11, 7)})
OUTRO_DEFAULT = True              # A/B 뒤(11/9~) 기본. 판정이 '끈다'면 False — 그 전엔 바꾸지 않는다
OUTRO_FROM = D(2026, 10, 26)      # 이 날 전에는 붙이지 않는다(OUTRO_AB 를 None 으로 해도)

# ── 대상 ──────────────────────────────────────────────────
TOPIC_PREFIX = "fortune"          # 왕별이 운세 토픽(fortune · fortune_theme · fortune_name · fortune_pulli · …)
TABLE_TYPES = ("card", "grid", "tier", "gunghap", "bless", "agetable")   # motion_short 의 표 장면

# ── 글 ────────────────────────────────────────────────────
LABEL = "오늘의 덕담 한마디"                       # 화면 위 작은 알약
INVITE_SCREEN = "띠 남기시면 덕담 드려요"           # 화면 둘째 줄(14자 이내 · 글꼴에 없는 이모지는 화면에 쓰지 않는다)
INVITE_VO = "띠 남기시면 덕담 드려요."
DESC_LINE = "댓글에 띠를 남겨 주시면 왕별이가 덕담 드려요 🙏"   # 설명란 한 줄(첫 문단 바로 아래)
LINE_MAX_HANGUL = 8               # 덕담 한 줄 한글 글자 수 — 목소리가 2.5초 안에 들어가는 한계
LINE_MAX_CHARS = 16               # 화면 큰 글자 한 줄(빈칸·문장부호 포함)
REPEAT_GAP = 13                   # 앞선 13일 안에 나온 줄은 다시 쓰지 않는다(어제와 같은 줄 금지 — 2주 A/B 안에서도 겹치지 않게)
SEQ_EPOCH = D(2026, 10, 1)        # 반복을 피할 때 이 날부터 차례로 센다(이 날 전 날짜는 앞선 날을 보지 않는다)

# 덕담 — 어르신께 건네는 말투(…세요/…요). 한글 8자 이내. 화면 글 = 목소리 글.
# 절기 날(KST 날짜 — ephem 태양 황경으로 10/25 계산, 시각은 몇 분 오차) — 그날만 이 줄.
JEOLGI = {
    D(2026, 11, 7): ("입동", "입동, 든든히 드세요"), D(2026, 11, 22): ("소설", "소설, 목도리 하세요"),
    D(2026, 12, 7): ("대설", "대설, 길 살펴 걸어요"), D(2026, 12, 22): ("동지", "동지 팥죽 드세요"),
    D(2027, 1, 5): ("소한", "소한, 장갑 끼세요"), D(2027, 1, 20): ("대한", "대한, 든든히 드세요"),
    D(2027, 2, 4): ("입춘", "입춘, 봄이 와요"), D(2027, 2, 19): ("우수", "우수, 봄비 반가워요"),
    D(2027, 3, 6): ("경칩", "경칩, 기지개 켜세요"), D(2027, 3, 21): ("춘분", "춘분, 봄볕 쬐세요"),
    D(2027, 4, 5): ("청명", "청명, 하늘 보세요"), D(2027, 4, 20): ("곡우", "곡우, 햇차 드세요"),
    D(2027, 5, 6): ("입하", "입하, 물 한 잔 드세요"), D(2027, 5, 21): ("소만", "소만, 초록 길 걸어요"),
    D(2027, 6, 6): ("망종", "망종, 쉬엄쉬엄 가요"), D(2027, 6, 21): ("하지", "하지, 긴 낮 즐겨요"),
    D(2027, 7, 7): ("소서", "소서, 시원히 지내요"), D(2027, 7, 23): ("대서", "대서, 물 자주 드세요"),
    D(2027, 8, 8): ("입추", "입추, 가을이 와요"), D(2027, 8, 23): ("처서", "처서, 선선해져요"),
    D(2027, 9, 8): ("백로", "백로, 이슬 고와요"), D(2027, 9, 23): ("추분", "추분, 푹 주무세요"),
    D(2027, 10, 8): ("한로", "한로, 한 겹 더 입어요"), D(2027, 10, 24): ("상강", "상강, 차 한잔해요"),
    D(2027, 11, 8): ("입동", "입동, 든든히 드세요"), D(2027, 11, 22): ("소설", "소설, 목도리 하세요"),
    D(2027, 12, 7): ("대설", "대설, 길 살펴 걸어요"), D(2027, 12, 22): ("동지", "동지 팥죽 드세요"),
}
SEASON_OF = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
             6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON = {
    "autumn": ["한 겹 더 입으세요", "따끈한 차 드세요", "목도리 챙기세요", "단풍 구경 가세요", "가을볕 쬐어 보세요",
               "낙엽 길 걸어 보세요", "무릎 덮고 쉬세요", "따뜻한 국 드세요", "고운 가을 되세요"],
    "winter": ["장갑 꼭 끼세요", "목도리 챙기세요", "따끈한 차 드세요", "내복 챙겨 입으세요", "볕 날 때 걸으세요",
               "군고구마 드세요", "포근한 밤 되세요", "따뜻한 국 드세요", "모자 꼭 쓰세요"],
    "spring": ["꽃구경 가 보세요", "봄볕 쬐며 걸어요", "창문 열어 보세요", "봄나물 드세요", "새싹처럼 웃어요",
               "꽃향기 맡아 보세요", "가벼운 산책 어때요"],
    "summer": ["물 한 잔 챙기세요", "그늘에서 쉬세요", "시원한 데 계세요", "수박 한 쪽 드세요", "낮잠도 좋아요",
               "부채 하나 챙기세요"],
}
WEEKDAY_LINES = {   # 0 = 월요일
    0: ["새 한 주 응원해요", "한 주 힘내세요"], 1: ["차근차근 가세요"], 2: ["한 주 절반 왔어요"],
    3: ["조금만 더 힘내세요"], 4: ["한 주 수고하셨어요"], 5: ["주말 푹 쉬세요", "주말 잘 보내세요"],
    6: ["푹 쉬는 일요일", "내일도 평안하세요"],
}
ALWAYS = ["오늘도 평안하세요", "웃는 하루 되세요", "고운 하루 되세요", "천천히 걸으세요", "물 한 잔 챙기세요",
          "푹 주무세요", "든든히 드세요", "안부 전화 해 봐요", "하늘 한번 보세요", "노래 한 곡 들어요",
          "마음 편히 쉬세요", "따뜻한 밥 드세요", "참 잘하고 계세요", "기지개 켜 보세요", "크게 한번 웃어요"]


def all_lines() -> list[str]:
    out = [x for _, x in JEOLGI.values()] + [x for v in SEASON.values() for x in v] + ALWAYS
    out += [x for v in WEEKDAY_LINES.values() for x in v]
    return list(dict.fromkeys(out))


def hangul(s: str) -> int:
    return len(re.findall(r"[가-힣]", s))


# ── 날짜 → 켜짐 ───────────────────────────────────────────
def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def arm(d: dt.date) -> str | None:
    """A/B 기간이면 'on'/'off', 기간 밖이면 None. 채널 맥박(tools/pulse.py)이 게시일(KST)로 부른다."""
    if OUTRO_AB is None or not (OUTRO_AB[0] <= d <= OUTRO_AB[1]):
        return None
    return "on" if d in OUTRO_AB_ON else "off"


def is_on(d: dt.date) -> bool:
    """그날 표 쇼츠에 끝인사를 붙이나. A/B 기간은 날짜표대로, 그 뒤는 OUTRO_DEFAULT, OUTRO_FROM 전은 끈다."""
    if d < OUTRO_FROM:
        return False
    a = arm(d)
    if a is not None:
        return a == "on"
    if OUTRO_AB is not None and d < OUTRO_AB[0]:
        return False
    return bool(OUTRO_DEFAULT)


def ab_calendar() -> dict[str, list[str]]:
    """{'on': [...], 'off': [...]} — 실험 달력(pulse_experiments.json 'outro-blessing')과 같아야 한다(테스트가 본다)."""
    if OUTRO_AB is None:
        return {"on": [], "off": []}
    n = (OUTRO_AB[1] - OUTRO_AB[0]).days + 1
    days = [OUTRO_AB[0] + dt.timedelta(days=k) for k in range(n)]
    return {a: [d.isoformat() for d in days if arm(d) == a] for a in ("on", "off")}


# ── 날짜 → 덕담 ───────────────────────────────────────────
def _h(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest(), 16)


WEEKDAY_FIRST = (0, 4)            # 월(한 주 시작)·금(한 주 끝)은 그 요일 줄을 먼저
SEASON_FIRST = (1, 2, 3)          # 화·수·목은 계절 줄을 먼저 · 토·일은 전부 섞어서


def candidates(d: dt.date) -> list[str]:
    """그날 고를 줄들(앞에서부터 본다). 절기 날은 그 줄 하나."""
    if d in JEOLGI:
        return [JEOLGI[d][1]]
    key = lambda x: _h(d.isoformat(), "outro", x)  # noqa: E731
    wd = sorted(WEEKDAY_LINES.get(d.weekday(), []), key=key)
    se = sorted(SEASON[SEASON_OF[d.month]], key=key)
    al = sorted(ALWAYS, key=key)
    if d.weekday() in WEEKDAY_FIRST:
        order = wd + sorted(se + al, key=key)
    elif d.weekday() in SEASON_FIRST:
        order = se + sorted(wd + al, key=key)
    else:
        order = sorted(wd + se + al, key=key)
    return list(dict.fromkeys(order))


_SEQ: dict[dt.date, str] = {}     # SEQ_EPOCH 부터 이어진 날짜만 담는다(빈 날 없이)


def blessing(d: dt.date) -> str:
    """오늘의 덕담 한 줄. SEQ_EPOCH 부터 하루씩 차례로 고르며 앞선 REPEAT_GAP 일에 나온 줄은 건너뛴다(절기 날은 그 줄).
    SEQ_EPOCH 전 날짜는 앞선 날을 보지 않는다(견본용)."""
    if d < SEQ_EPOCH:
        return candidates(d)[0]
    if d not in _SEQ:
        x = max(_SEQ) + dt.timedelta(days=1) if _SEQ else SEQ_EPOCH
        recent = [_SEQ[x - dt.timedelta(days=k)] for k in range(REPEAT_GAP, 0, -1) if x - dt.timedelta(days=k) in _SEQ]
        while x <= d:
            cand = candidates(x)
            pick = next((c for c in cand if c not in recent[-REPEAT_GAP:]), cand[0])
            _SEQ[x] = pick
            recent.append(pick)
            x += dt.timedelta(days=1)
    return _SEQ[d]


# ── 스토리보드 → 끝인사 ───────────────────────────────────
def sb_date(sb: dict) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(sb.get("date") or "")[:10])
    except ValueError:
        return None


def is_table(sb: dict, spec: dict | None = None) -> bool:
    """왕별이 표 쇼츠인가(운세 토픽 + 표 장면이 하나라도)."""
    spec = spec or sb
    topic = str(sb.get("topic") or spec.get("topic") or "").strip().lower()
    if not topic.startswith(TOPIC_PREFIX):
        return False
    return any(isinstance(sc, dict) and sc.get("type") in TABLE_TYPES for sc in spec.get("scenes") or [])


def day_for(sb: dict, now: dt.datetime | None = None) -> dt.date | None:
    """끝인사를 정하는 날 = 스토리보드 날짜. 단 늦게 도는 실행(자정 넘김)은 그날(KST)로 — 채널 맥박이 게시일로 나누기 때문."""
    d = sb_date(sb)
    if d is None:
        return None
    today = (now.astimezone(KST) if now else dt.datetime.now(KST)).date()
    return max(d, today)


def vo_text(line: str) -> str:
    """목소리로 읽을 덕담 — 쉼표를 뺀다(절기 이름 뒤 쉼이 0.1~0.3초 늘어 2.5초를 넘겼다 · 10/25 실측). 화면엔 쉼표 그대로."""
    return re.sub(r"\s+", " ", line.replace(",", " ")).strip().rstrip(".") + "."


def build(d: dt.date) -> dict:
    """렌더러(motion_short)가 받는 끝인사 스펙."""
    line = blessing(d)
    return {"date": d.isoformat(), "label": LABEL, "line1": line, "line2": INVITE_SCREEN,
            "vo": [vo_text(line), INVITE_VO]}


def for_storyboard(sb: dict, spec: dict | None = None, now: dt.datetime | None = None) -> dict | None:
    """표 쇼츠이고 그날 켜는 날이면 끝인사 스펙, 아니면 None."""
    if not is_table(sb, spec):
        return None
    d = day_for(sb, now)
    if d is None or not is_on(d):
        return None
    return build(d)


def with_line(desc: str) -> str:
    """설명란 첫 문단 바로 아래에 초대 한 줄(이미 있으면 그대로). 나머지 글은 손대지 않는다."""
    desc = desc or ""
    if DESC_LINE in desc:
        return desc
    head, sep, rest = desc.partition("\n\n")
    if not sep:
        return f"{head}\n\n{DESC_LINE}" if head else DESC_LINE
    return f"{head}\n\n{DESC_LINE}\n\n{rest}"


# ── 보기 ──────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="표 쇼츠 끝인사(오늘의 덕담) 미리보기")
    ap.add_argument("cmd", choices=["show"])
    ap.add_argument("--date")
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args(argv)
    d0 = dt.date.fromisoformat(a.date) if a.date else (OUTRO_AB[0] if OUTRO_AB else kst_today())
    for k in range(a.days):
        d = d0 + dt.timedelta(days=k)
        ab = arm(d)
        print(f"{d} {'월화수목금토일'[d.weekday()]} {'켬' if is_on(d) else '끔'}"
              f"{f' (A/B {ab})' if ab else ''} · {blessing(d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
