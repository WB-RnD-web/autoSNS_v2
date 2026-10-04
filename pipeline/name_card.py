#!/usr/bin/env python3
"""'내 것 찾기' 표 쇼츠 — 태어난 해 끝자리(07:40) · 이름 글자(09:40) · 성씨(13:40) · 태어난 달(15:40).

2026-10-04 하루 2편 추가: 10/3 표 쇼츠가 채널 기록을 갈았다(띠 테마 13시간 1만 회 · 태어난 달 9시간 9천 회 ·
  이름 6,566회) — 같은 틀에 '찾을 축'만 바꾼 새 표 두 가지(해 끝자리 10칸 · 성씨 20칸)를 빈 시간대에 넣는다.

왜(10/2 떡상 채널 해부 https://claude.ai/artifact/Xz3JeJNVox4nB7ZCXJxJ8r):
  가화만사성 '이름에 이 글자 있으면 나이 들수록 돈이 붙어요' — 9초짜리 정지 표 한 장이 529만 회.
  보는 사람이 자기 이름·생일을 ★찾느라★ 멈추고, 다시 보고, 댓글을 단다. 우리 띠 순위 표(6,437회)도
  같은 계열로 처음 1천 회 천장을 뚫었고, 트렌드 레이더도 운세판 '이름·성씨'를 강세로 잡았다(평소 1.8배).
  → 하루 두 편 더: 09:40 이름 글자 표 · 15:40 태어난 달 표. 12:00 띠 테마 표와 합쳐 '내 것 찾기' 하루 3편.

전부 코드가 정한다(루틴은 실행 스위치만): 테마 = 날짜 순환, 칸·순위 = 날짜 해시. 같은 날짜·같은 슬롯이면 늘 같은 표.
  글자 표는 ★한자 뜻이 테마와 맞는 글자만★ 싣는다(富 부자 부 → 재물). 아무 글자나 '돈 붙는 글자'라 하지 않는다.
  문구 금지어는 theme_card.BANNED 와 같다(의료·투자·겁주기). 렌더는 motion_short 'grid' 장면.

    python pipeline/name_card.py show [--date …] [--slot year|am|surname|pm]
    python pipeline/name_card.py make [--date …] [--slot …] [--out <path>]
    python pipeline/name_card.py path [--date …] [--slot …]       # 슬롯을 안 주면 지금 KST 시각으로
    python pipeline/name_card.py slot                              # 지금 시각의 슬롯(루틴 트리거가 쓴다)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fortune_card import WEEKDAY, _h  # noqa: E402
import theme_card  # noqa: E402

TOPIC = "fortune_name"
EPOCH = dt.date(2026, 10, 2)
KST = dt.timezone(dt.timedelta(hours=9))
ACCENT = "#C9A227"
BRAND = "왕별이 · 내 것 찾기"
SLOTS = ("am", "pm", "year", "surname")
SLOT_TIME = {"year": "아침 7시 40분", "am": "아침 9시 40분", "surname": "오후 1시 40분", "pm": "오후 3시 40분"}
NAME_CELLS = 24                  # 4칸 × 6줄 — 한 화면에서 내 글자를 찾을 수 있는 크기
LINE_MAX = 11                    # 제목 한 줄(76px) 한글 11자

# ── 오전: 이름 글자 표 ─────────────────────────────────────────
# (글자, 한자, 훈) — 훈은 그 한자의 뜻(새김). ★뜻이 테마와 맞는 것만. 한 테마 안에서 글자는 겹치지 않는다.
NAME_THEMES = [
    {"id": "wealth", "l1": "이름에 이 글자 있으면", "l2": "나이 들수록 재물 붙어요",
     "yt": "이름에 이 글자 있으면 나이 들수록 재물이 붙어요",
     "bank": [("부", "富", "부자"), ("재", "財", "재물"), ("금", "金", "쇠"), ("보", "寶", "보배"), ("창", "昌", "창성할"),
              ("흥", "興", "일어날"), ("영", "榮", "영화"), ("풍", "豊", "풍년"), ("윤", "潤", "윤택할"), ("성", "盛", "성할"),
              ("진", "珍", "보배"), ("옥", "玉", "구슬"), ("은", "銀", "은"), ("록", "祿", "녹"), ("길", "吉", "길할"),
              ("상", "祥", "상서"), ("경", "慶", "경사"), ("복", "福", "복"), ("희", "禧", "복"), ("태", "泰", "클"),
              ("형", "亨", "형통할"), ("달", "達", "통달할"), ("우", "祐", "도울"), ("연", "衍", "넉넉할"), ("유", "裕", "넉넉할"),
              ("만", "萬", "일만"), ("융", "隆", "높을"), ("환", "煥", "빛날"), ("찬", "燦", "빛날"), ("원", "元", "으뜸"),
              ("호", "浩", "넓을"), ("기", "基", "터")],
     "hook": "warm golden light on traditional Korean hanji paper with an ink brush and an old brass coin, "
             "soft bokeh, calm lucky mood, no people"},
    {"id": "health", "l1": "이름에 이 글자 있으면", "l2": "오래오래 건강해요",
     "yt": "이름에 이 글자 있으면 오래오래 건강해요",
     "bank": [("수", "壽", "목숨"), ("강", "康", "편안할"), ("영", "永", "길"), ("태", "泰", "클"), ("안", "安", "편안할"),
              ("송", "松", "소나무"), ("장", "長", "길"), ("연", "延", "늘일"), ("건", "健", "굳셀"), ("녕", "寧", "편안할"),
              ("평", "平", "평평할"), ("항", "恒", "항상"), ("구", "久", "오랠"), ("학", "鶴", "두루미"), ("산", "山", "뫼"),
              ("석", "石", "돌"), ("근", "根", "뿌리"), ("정", "靖", "편안할"), ("화", "和", "화할"), ("순", "順", "순할"),
              ("용", "勇", "날랠"), ("무", "茂", "무성할"), ("왕", "旺", "왕성할"), ("균", "均", "고를"), ("청", "淸", "맑을"),
              ("선", "仙", "신선"), ("기", "氣", "기운"), ("생", "生", "날")],
     "hook": "an old pine tree on a quiet Korean mountain at dawn, soft mist, cranes flying far away, "
             "serene long life mood, no people"},
    {"id": "children", "l1": "이름에 이 글자 있으면", "l2": "자식 덕 보고 살아요",
     "yt": "이름에 이 글자 있으면 자식 덕 보고 살아요",
     "bank": [("효", "孝", "효도"), ("자", "慈", "사랑"), ("화", "和", "화할"), ("순", "順", "순할"), ("가", "家", "집"),
              ("경", "敬", "공경"), ("애", "愛", "사랑"), ("은", "恩", "은혜"), ("의", "義", "옳을"), ("예", "禮", "예도"),
              ("인", "仁", "어질"), ("덕", "德", "큰"), ("현", "賢", "어질"), ("숙", "淑", "맑을"), ("정", "貞", "곧을"),
              ("희", "喜", "기쁠"), ("락", "樂", "즐길"), ("손", "孫", "손자"), ("윤", "胤", "자손"), ("계", "繼", "이을"),
              ("승", "承", "이을"), ("종", "宗", "마루"), ("모", "慕", "그릴"), ("융", "融", "화할"), ("혜", "惠", "은혜"),
              ("선", "善", "착할"), ("세", "世", "대")],
     "hook": "cozy Korean living room at golden hour, family photos on a wooden shelf, warm tea on a low table, "
             "soft bokeh, no faces"},
    {"id": "helper", "l1": "이름에 이 글자 있으면", "l2": "귀인이 따라다녀요",
     "yt": "이름에 이 글자 있으면 귀인이 따라다녀요",
     "bank": [("인", "仁", "어질"), ("덕", "德", "큰"), ("선", "善", "착할"), ("은", "恩", "은혜"), ("현", "賢", "어질"),
              ("신", "信", "믿을"), ("의", "義", "옳을"), ("우", "祐", "도울"), ("숙", "淑", "맑을"), ("예", "禮", "예도"),
              ("혜", "惠", "은혜"), ("진", "眞", "참"), ("성", "誠", "정성"), ("화", "和", "화할"), ("명", "明", "밝을"),
              ("지", "智", "슬기"), ("호", "好", "좋을"), ("연", "緣", "인연"), ("보", "輔", "도울"), ("필", "弼", "도울"),
              ("익", "益", "더할"), ("귀", "貴", "귀할"), ("홍", "弘", "클"), ("광", "光", "빛"),
              ("준", "俊", "준걸"), ("영", "英", "꽃부리"), ("협", "協", "화할"), ("친", "親", "친할")],
     "hook": "two warm cups of Korean tea on a wooden table by a sunny window, autumn leaves outside, "
             "friendly welcoming mood, no people"},
    {"id": "lateluck", "l1": "이름에 이 글자 있으면", "l2": "말년이 편안해요",
     "yt": "이름에 이 글자 있으면 말년이 편안해요",
     "bank": [("안", "安", "편안할"), ("평", "平", "평평할"), ("강", "康", "편안할"), ("녕", "寧", "편안할"), ("유", "裕", "넉넉할"),
              ("여", "餘", "남을"), ("한", "閑", "한가할"), ("정", "靜", "고요할"), ("화", "和", "화할"), ("순", "順", "순할"),
              ("태", "泰", "클"), ("복", "福", "복"), ("수", "壽", "목숨"), ("연", "延", "늘일"), ("영", "永", "길"),
              ("만", "晩", "늦을"), ("성", "成", "이룰"), ("원", "圓", "둥글"), ("송", "松", "소나무"), ("학", "鶴", "두루미"),
              ("길", "吉", "길할"), ("경", "慶", "경사"), ("덕", "德", "큰"), ("희", "熙", "빛날"),
              ("휴", "休", "쉴"), ("락", "樂", "즐길"), ("록", "祿", "녹"), ("풍", "豊", "풍년"), ("윤", "潤", "윤택할")],
     "hook": "peaceful Korean hanok courtyard in autumn afternoon, persimmon tree, warm sunlight, "
             "calm abundant mood, no people"},
]

# ── 오후: 태어난 달 표(12칸) — 문구는 띠 테마 표(theme_card.THEMES)와 같은 은행을 쓴다 ──
MONTH_LABEL = {"money": "{m}월 돈복", "children": "자식 덕", "lateluck": "말년 복", "helper": "{m}월 귀인운",
               "couple": "부부 금슬", "grandkids": "손주 복", "doublejoy": "{m}월 겹경사", "light": "{m}월 몸 가벼움",
               "openluck": "{m}월 운 트임", "friends": "친구 복", "home": "{m}월 집안 평안"}


def kst_now() -> dt.datetime:
    return dt.datetime.now(KST)


def slot_now(t: dt.datetime | None = None) -> str:
    """07:40 해 끝자리 · 09:40 이름 · 13:40 성씨 · 15:40 태어난 달 — 루틴이 정시에 깨우니 시(時)만 본다."""
    h = (t or kst_now()).hour
    return "year" if h < 9 else "am" if h < 13 else "surname" if h < 15 else "pm"


def name_theme(d: dt.date) -> dict:
    return NAME_THEMES[(d - EPOCH).days % len(NAME_THEMES)]


def month_theme(d: dt.date) -> dict:
    # 같은 날 12시 띠 테마 표와 겹치지 않게 다섯 칸 밀어서 고른다
    return theme_card.THEMES[((d - EPOCH).days + 5) % len(theme_card.THEMES)]


# ── 07:40 태어난 해 끝자리(10칸) — 끝자리 = 천간(1984 갑자 → 4 = 갑) ──
STEMS = [(0, "경", "庚"), (1, "신", "辛"), (2, "임", "壬"), (3, "계", "癸"), (4, "갑", "甲"),
         (5, "을", "乙"), (6, "병", "丙"), (7, "정", "丁"), (8, "무", "戊"), (9, "기", "己")]
# ── 13:40 성씨(20칸) — 인구 많은 성씨 20(2015 통계청 순). 한자는 본관마다 달라 싣지 않는다.
SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "전", "홍"]
TIERS = {10: (("top", 3), ("mid", 4), ("low", 3)), 20: (("top", 4), ("mid", 10), ("low", 6))}


def year_theme(d: dt.date) -> dict:
    return theme_card.THEMES[((d - EPOCH).days + 8) % len(theme_card.THEMES)]


def surname_theme(d: dt.date) -> dict:
    return theme_card.THEMES[((d - EPOCH).days + 3) % len(theme_card.THEMES)]


def ranked(d: dt.date, th: dict, keys: list, kind: str) -> dict:
    """keys 를 날짜 해시로 줄 세우고 순위·한 줄을 붙인다 → {key: (순위, 한 줄)}."""
    k = f"{d.isoformat()}|{kind}|{th['id']}"
    order = sorted(keys, key=lambda x: _h(k, "order", x))
    out, i = {}, 0
    for tier, n in TIERS[len(keys)]:
        bank = sorted(th[tier], key=lambda x: _h(k, "line", tier, x))
        for j in range(n):
            out[order[i]] = (i + 1, bank[j % len(bank)])
            i += 1
    return out


def year_cells(d: dt.date, th: dict) -> list[dict]:
    r = ranked(d, th, [n for n, _, _ in STEMS], "year")
    return [{"big": f"{n}년생", "small": f"{r[n][0]}위", "note": f"{hj} · {r[n][1]}", "hi": r[n][0] <= 3}
            for n, _, hj in STEMS]


def surname_cells(d: dt.date, th: dict) -> list[dict]:
    r = ranked(d, th, SURNAMES, "surname")
    return [{"big": f"{s}씨", "small": f"{r[s][0]}위", "note": r[s][1], "hi": r[s][0] <= 3}
            for s in sorted(SURNAMES)]                 # 찾기 쉽게 가나다순


def name_cells(d: dt.date, th: dict) -> list[dict]:
    """은행에서 24자 — 날짜마다 고르는 글자·순서가 바뀐다(같은 표를 되풀이하지 않게). 가나다순으로 보여 준다."""
    k = f"{d.isoformat()}|name|{th['id']}"
    pick = sorted(th["bank"], key=lambda x: _h(k, x[0]))[:NAME_CELLS]
    pick.sort(key=lambda x: x[0])                    # 찾기 쉽게 가나다순
    return [{"big": s, "small": h, "note": f"{n} {s}", "hi": False} for s, h, n in pick]


def month_rows(d: dt.date, th: dict) -> list[dict]:
    k = f"{d.isoformat()}|month|{th['id']}"
    order = sorted(range(1, 13), key=lambda m: _h(k, "order", m))
    rows, i = [], 0
    for tier, n in theme_card.TIERS:
        bank = sorted(th[tier], key=lambda x: _h(k, "line", tier, x))
        for j in range(n):
            rows.append({"month": order[i], "rank": i + 1, "line": bank[j % len(bank)]})
            i += 1
    return rows


def month_cells(rows: list[dict]) -> list[dict]:
    """칸은 1월~12월 순서(찾기 쉽게), 순위는 작은 글씨 · 1~3위는 테두리."""
    return [{"big": f"{r['month']}월생", "small": f"{r['rank']}위", "note": r["line"], "hi": r["rank"] <= 3}
            for r in sorted(rows, key=lambda r: r["month"])]


def month_label(d: dt.date, th: dict) -> str:
    return MONTH_LABEL[th["id"]].format(m=d.month)


def title(d: dt.date, slot: str) -> str:
    if slot == "am":
        th = name_theme(d)
        return f"{th['yt']} | 이름 한자 풀이"
    if slot == "year":
        return f"태어난 해 끝자리로 보는 {month_label(d, year_theme(d))} 순위 1위~10위 | 0년생~9년생 전부"
    if slot == "surname":
        return f"성씨로 보는 {month_label(d, surname_theme(d))} 순위 1위~20위 | 김·이·박·최… 많은 성씨 20개"
    th = month_theme(d)
    return f"태어난 달로 보는 {month_label(d, th)} 순위 1위~12위 | 1월생~12월생 전부"


def description(d: dt.date, slot: str) -> str:
    if slot == "am":
        th = name_theme(d)
        head = (f"{th['yt']} — 뜻이 좋은 이름 한자 {NAME_CELLS}자를 한 장에 모았어요. "
                "내 이름 글자가 있나요? 댓글로 남겨 주세요 🙏")
        tags = "#이름풀이 #이름한자 #운세 #shorts"
    elif slot == "year":
        head = (f"태어난 해 끝자리로 보는 {month_label(d, year_theme(d))} 순위 — 0년생부터 9년생까지 한 장에 모았어요. "
                "1954년생이면 4년생이에요. 내 끝자리는 몇 위인가요? 댓글로 남겨 주세요 🙏")
        tags = "#태어난해 #띠별운세 #운세 #shorts"
    elif slot == "surname":
        head = (f"성씨로 보는 {month_label(d, surname_theme(d))} 순위 — 많은 성씨 20개를 한 장에 모았어요. "
                "내 성씨는 몇 위인가요? 표에 없는 성씨는 댓글로 알려 주세요 🙏")
        tags = "#성씨 #성씨운세 #운세 #shorts"
    else:
        th = month_theme(d)
        head = (f"태어난 달로 보는 {month_label(d, th)} 순위 — 1월생부터 12월생까지 한 장에 모았어요. "
                "내 생일 달은 몇 위인가요? 댓글로 남겨 주세요 🙏")
        tags = "#생일운세 #태어난달 #운세 #shorts"
    sched = " · ".join(f"{SLOT_TIME[k]} {lab}" for k, lab in
                       (("year", "태어난 해"), ("am", "이름 글자"), ("surname", "성씨"), ("pm", "태어난 달")))
    note = "한자 뜻은 사전의 새김을 따랐어요." if slot == "am" else "순위는 재미로 정한 것이에요."
    return (f"{head}\n매일 {sched} 표가 올라와요.\n\n"
            f"※ 재미로 보는 풀이입니다. {note}\n\n{tags}")


def storyboard(d: dt.date, slot: str) -> dict:
    if slot not in SLOTS:
        raise ValueError(f"slot 은 {SLOTS}")
    pill = f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · 내 것 찾기"
    if slot == "am":
        th = name_theme(d)
        scene = {"type": "grid", "pill": pill, "title": th["l1"], "title2": th["l2"], "cols": 4,
                 "cells": name_cells(d, th), "foot": "※ 재미로 보는 이름 풀이 · 한자 뜻은 사전 새김", "brand": BRAND,
                 "narration": f"{th['yt']}. 내 이름 글자가 있는지 찾아보세요."}
        hook, theme_id = th["hook"], f"name:{th['id']}"
    elif slot == "year":
        th = year_theme(d)
        lab = month_label(d, th)
        scene = {"type": "grid", "pill": pill, "title": "태어난 해 끝자리로 보는", "title2": f"{lab} 순위",
                 "cols": 2, "cells": year_cells(d, th), "foot": "※ 끝자리: 1954년생 → 4년생 · 재미로 보는 운세",
                 "brand": BRAND, "narration": f"태어난 해 끝자리로 보는 {lab} 순위예요. 내 끝자리는 몇 위인지 찾아보세요."}
        hook, theme_id = th["hook"], f"year:{th['id']}"
    elif slot == "surname":
        th = surname_theme(d)
        lab = month_label(d, th)
        scene = {"type": "grid", "pill": pill, "title": "성씨로 보는", "title2": f"{lab} 순위",
                 "cols": 4, "cells": surname_cells(d, th), "foot": "※ 많은 성씨 20개 · 재미로 보는 운세",
                 "brand": BRAND, "narration": f"성씨로 보는 {lab} 순위예요. 내 성씨는 몇 위인지 찾아보세요."}
        hook, theme_id = th["hook"], f"surname:{th['id']}"
    else:
        th = month_theme(d)
        rows = month_rows(d, th)
        scene = {"type": "grid", "pill": pill, "title": "태어난 달로 보는", "title2": f"{month_label(d, th)} 순위",
                 "cols": 2, "cells": month_cells(rows), "foot": "※ 재미로 보는 운세", "brand": BRAND,
                 "narration": f"태어난 달로 보는 {month_label(d, th)} 순위예요. 내 생일 달은 몇 위인지 찾아보세요."}
        hook, theme_id = th["hook"], f"month:{th['id']}"
    t = title(d, slot)
    return {
        "date": d.isoformat(), "topic": TOPIC, "slot": slot, "theme": theme_id, "privacy": "public",
        "accent": ACCENT, "_min_total": 9.0,
        "hook_title": scene["title2"], "headline": t, "thumbnail_hook": hook,
        "scenes": [scene],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d, slot)}},
        "notes": f"내 것 찾기 표 · {theme_id} · name_card.py 가 만든 스토리보드(루틴은 실행 스위치만)",
    }


def is_name(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(str(sb.get("date"))[:10])
    slot = sb.get("slot") if sb.get("slot") in SLOTS else "am"
    return {"title": title(d, slot)[:95], "description": description(d, slot)}


def path_for(d: dt.date, slot: str, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_{slot}_storyboard.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="내 것 찾기 표(해 끝자리·이름 글자·성씨·태어난 달) 스토리보드")
    ap.add_argument("cmd", choices=["show", "make", "path", "slot"])
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--slot", choices=SLOTS, help="year=해 끝자리 · am=이름 글자 · surname=성씨 · pm=태어난 달 (기본: 지금 KST 시각)")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else kst_now().date()
    slot = a.slot or slot_now()
    if a.cmd == "slot":
        print(slot)
        return 0
    if a.cmd == "path":
        print(os.path.relpath(path_for(d, slot)))
        return 0
    sb = storyboard(d, slot)
    if a.cmd == "show":
        print(json.dumps(sb, ensure_ascii=False, indent=1))
        return 0
    out = a.out or path_for(d, slot)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(f"NAME={sb['theme']} · {slot} · {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
