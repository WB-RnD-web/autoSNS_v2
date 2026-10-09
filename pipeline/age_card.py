#!/usr/bin/env python3
"""'출생연도로 보는 ○○ 나이' 표 쇼츠 — 띠 테마 표가 쉬는 날(격일) 낮 12시 자리(theme_card 가 부른다).

왜(2026-10-09 시장 조사 — 경쟁 채널 24곳 쇼츠 탭·최근 30일 10만 회 넘은 운세 쇼츠 390편):
  '출생연도·나이' 꼴이 가장 많이 터졌다(137편 · 중앙 17만). 가화만사성 '출생년도로 보는 내 노후가 편안해지는 나이' 207만 ·
  복담 38만 · 행운백세 23만 · 소문만복 19만. 우리 채널 최근 150편엔 0편. 화면은 출생연도 옆에 나이를 빽빽이 깐 한 장 표.
우리 방식(★나이를 해시로 지어내지 않는다 — 정책: 템플릿만 바꾼 대량 생산처럼 보이면 수익화 불가 · 10/9 정책 조사):
  내 태어난 해 천간에게 다가오는 해(2027~)의 천간이 무엇인지(십신), 또는 지지가 합인지로 '그 기운이 처음 드는 해'를 찾아
  그해 만 나이를 적는다. 테마마다 기준이 달라 표가 실제로 다르고, 근거는 설명란에 해마다 다 적는다.
  해는 입춘으로 바뀐다(birth_basis) — 양력 1월~2월 3일생은 앞 해 칸으로 보시라고 화면에 적는다.

    python pipeline/age_card.py show [--date …]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import birth_basis  # noqa: E402
from fortune_card import WEEKDAY  # noqa: E402
from newyear_card import ten_god  # noqa: E402
from pulli_card import ANIMALS, STEMS, relation  # noqa: E402

YEARS = list(range(1950, 1986))   # 36칸 = 3열 × 12줄(경쟁 표와 같은 밀도). 55세 이상이 80%(10/9 스튜디오)
FROM_YEAR = 2027                  # 내년부터 — 이미 지난 해는 적지 않는다
BAD_REL = ("충",)                 # 십신이 맞아도 띠가 정면으로 부딪히는(충) 해는 건너뛴다 — 원진·형까지 빼면 24년 안에 없는 해가 생긴다(1955 을미 정인)
BRAND = "왕별이 · 출생연도로 보는 나이"
SCREEN_BASIS = "나이는 그해 만 나이 · 양력 1월~2월 3일생은 앞 해 칸으로"

# 테마 — god: 내 천간에게 그해 천간이 이 십신일 때 · rel: 내 띠와 그해 띠가 이 관계일 때
# l2 는 화면 둘째 줄(11자 이내) · line 은 설명란 한 줄의 말 · ★건강·돈 보장·겁주는 말 금지(theme_card.BANNED)
THEMES = [
    {"id": "comfort", "l2": "노후가 편안해지는 나이", "rel": ("육합",), "word": "내 띠와 육합인 해",
     "hook": "peaceful Korean hanok courtyard in autumn afternoon, persimmon tree, warm sunlight, calm abundant mood, no people"},
    {"id": "bigmoney", "l2": "큰돈 들어오는 나이", "god": "편재", "word": "큰 재물 기운(편재)",
     "hook": "warm golden light on traditional Korean hanji paper with an old brass coin and a small wooden abacus, soft bokeh, calm lucky mood, no people"},
    {"id": "helper", "l2": "귀인 만나는 나이", "god": "정인", "word": "나를 돕는 기운(정인)",
     "hook": "two warm cups of Korean tea on a wooden table by a sunny window, autumn leaves outside, friendly welcoming mood, no people"},
    {"id": "savings", "l2": "재물이 쌓이는 나이", "god": "정재", "word": "차곡차곡 모이는 재물 기운(정재)",
     "hook": "a small traditional Korean wooden chest on a low table, warm lamp light, rice in a brass bowl, calm mood, no people"},
    {"id": "children", "l2": "자식 덕 보는 나이", "god": "식신", "word": "베풀고 돌려받는 기운(식신)",
     "hook": "cozy Korean living room at golden hour, family photos on a wooden shelf, warm tea on a low table, soft bokeh, no faces"},
    {"id": "doublejoy", "l2": "겹경사 생기는 나이", "rel": ("삼합",), "word": "내 띠와 삼합인 해",
     "hook": "a sunny Korean countryside village in autumn, golden rice fields and a quiet hanok roof, warm mood, no people"},
    {"id": "honor", "l2": "체면이 서는 나이", "god": "정관", "word": "자리와 명예 기운(정관)",
     "hook": "an old pine tree on a quiet Korean mountain at dawn, soft mist, serene dignified mood, no people"},
    {"id": "talent", "l2": "솜씨가 빛나는 나이", "god": "상관", "word": "재주가 드러나는 기운(상관)",
     "hook": "a Korean calligraphy brush and ink stone on hanji paper by a window, warm afternoon light, no people"},
    {"id": "friend", "l2": "좋은 친구 생기는 나이", "god": "비견", "word": "어깨를 나란히 하는 기운(비견)",
     "hook": "two wooden chairs on a quiet Korean garden porch at sunset, warm light, autumn leaves, no people"},
    {"id": "fresh", "l2": "새 일이 트이는 나이", "god": "편인", "word": "새로 배우고 시작하는 기운(편인)",
     "hook": "morning sunlight through a Korean hanok paper door, an open book on a low desk, calm fresh mood, no people"},
]
EPOCH = dt.date(2026, 10, 11)       # 첫 편(띠 테마 쉬는 날) — 쉬는 날마다 테마 하나씩 돈다(20일에 한 바퀴)


def stem_of(y: int) -> int:
    return (y - 4) % 10


def branch_of(y: int) -> int:
    return (y - 4) % 12


def ganji(y: int) -> str:
    return STEMS[stem_of(y)] + "자축인묘진사오미신유술해"[branch_of(y)]


def fits(th: dict, born: int, year: int) -> bool:
    rel, _ = relation(branch_of(born), branch_of(year))
    if "god" in th:
        return ten_god(stem_of(born), stem_of(year)) == th["god"] and rel not in BAD_REL
    return rel in th["rel"]


def first_year(th: dict, born: int) -> int:
    for year in range(FROM_YEAR, FROM_YEAR + 24):
        if fits(th, born, year):
            return year
    raise ValueError(f"{th['id']}: {born}년생 기운이 24년 안에 없음")


def rows(th: dict) -> list[dict]:
    out = []
    for y in YEARS:
        year = first_year(th, y)
        out.append({"born": y, "year": year, "age": year - y, "label": f"{y % 100:02d}년생", "age_label": f"{year - y}세",
                    "ganji": ganji(y), "year_ganji": ganji(year), "animal": ANIMALS[branch_of(y)]})
    return out


def theme_for(d: dt.date) -> dict:
    """쉬는 날(이틀에 하루)마다 하나씩 — 같은 테마는 20일에 한 번."""
    k = (d - EPOCH).days // 2
    return THEMES[k % len(THEMES)]


def title(d: dt.date, th: dict) -> str:
    # 같은 테마가 20일 뒤 다시 와도 제목이 똑같지 않게 날짜를 붙인다(경쟁 채널 재탕 편 5편 중 3편이 1천 회대로 꺼졌다)
    return f"출생연도로 보는 {th['l2']} | {YEARS[0] % 100}~{YEARS[-1] % 100}년생 전부 · {d.month}월 {d.day}일"


def description(d: dt.date, th: dict) -> str:
    rs = rows(th)
    lines = [f"출생연도로 보는 {th['l2']} — {YEARS[0] % 100}년생부터 {YEARS[-1] % 100}년생까지 한 장에 모았어요. "
             "내 태어난 해를 찾아보세요 🙏", "",
             f"이렇게 정했어요: 태어난 해의 기운에게 다가오는 해({FROM_YEAR}년부터)가 {th['word']}이 처음 드는 해를 찾아, "
             "그해의 만 나이를 적었어요." + (" 내 띠와 정면으로 부딪히는 해(충)는 건너뛰었어요." if "god" in th else ""), ""]
    lines += [f"· {r['born']}년생({r['ganji']}생 {r['animal']}띠) → {r['year']}년({r['year_ganji']}년) {r['age']}세" for r in rs]
    lines += ["", birth_basis.year_note(YEARS[0], YEARS[-1]), "",
              "※ 전통 명리의 십신·띠 관계를 재미로 정리한 풀이입니다.", "",
              "#출생연도 #나이운세 #운세 #띠별운세 #shorts"]
    return "\n".join(lines)


def scene(d: dt.date, th: dict) -> dict:
    return {"type": "agetable", "pill": f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · {YEARS[0] % 100}~{YEARS[-1] % 100}년생",
            "title": "출생연도로 보는", "title2": th["l2"], "cols": 3,
            "cells": [{"label": r["label"], "age": r["age_label"]} for r in rows(th)],
            "basis": SCREEN_BASIS, "foot": "※ 태어난 해와 다가오는 해의 기운으로 본 풀이 · 재미로 보세요",
            "brand": BRAND, "narration": f"출생연도로 보는 {th['l2']}예요. 내 태어난 해를 찾아보세요."}


def storyboard(d: dt.date, topic: str) -> dict:
    """topic 은 부르는 쪽(theme_card)의 것을 그대로 쓴다 — 렌더·업로드·재생목록 길을 따로 만들지 않는다."""
    th = theme_for(d)
    t = title(d, th)
    return {
        "date": d.isoformat(), "topic": topic, "theme": f"age:{th['id']}", "privacy": "public",
        "accent": "#E8590C", "_min_total": 9.0,
        "hook_title": th["l2"], "headline": t, "thumbnail_hook": th["hook"] + ", no text, no letters, no signage, no logos",
        "scenes": [scene(d, th)],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d, th)}},
        "notes": f"출생연도로 보는 나이 표 · age:{th['id']} · age_card.py 가 만든 스토리보드(theme_card 쉬는 날)",
    }


def is_age(sb: dict) -> bool:
    return str(sb.get("theme") or "").startswith("age:")


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(str(sb.get("date"))[:10])
    tid = str(sb.get("theme"))[4:]
    th = next((x for x in THEMES if x["id"] == tid), None) or theme_for(d)
    return {"title": title(d, th)[:95], "description": description(d, th)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="출생연도로 보는 나이 표 스토리보드(보기)")
    ap.add_argument("cmd", choices=["show"])
    ap.add_argument("--date")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    print(json.dumps(storyboard(d, "fortune_theme"), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
