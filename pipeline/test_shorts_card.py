#!/usr/bin/env python3
"""운세 '12띠 한 장 표'(fortune_card) · 뉴스 첫 화면 헤드라인(top hook) 회귀 테스트.

    python pipeline/test_shorts_card.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fortune_card as FC     # noqa: E402
import motion_short as M      # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# 2026-09-29 운세 스토리보드 실물에서 필요한 부분만 옮겼다
SB = {
    "date": "2026-09-30", "topic": "fortune", "accent": "#C9A24B", "notes": "… MODE=daily",
    "platforms": {"youtube": {"title": "오늘 93점 나온 띠", "description": "설명"}},
    "scenes": [
        {"type": "hook", "lines": ["오늘", "딱 한 띠만", "운이 열려요"], "narration": "…", "brand": "일상공감뉴스 · 운세"},
        {"type": "keypoint", "label": "오늘 3위·2위 먼저",
         "points": ["3위 <b>원숭이띠</b> — 오늘 삼합 기운을 타요", "2위 <b>용띠</b> — 인연운이 술술 풀려요"],
         "narration": "3위는 원숭이띠, 2위는 용띠인데, 1위는 잠시 뒤에 알려드릴게요."},
        {"type": "stat", "label": "오늘 종합운 1위 · 쥐띠", "to": 93, "narration": "1위는 쥐띠, …"},
    ],
}

print("── 배정(격일 A/B) ──")
D = dt.date
ck("09-30 은 표", FC.is_card_day(D(2026, 9, 30)))
ck("10-01 은 기존 형식", not FC.is_card_day(D(2026, 10, 1)))
ck("10-02 는 표", FC.is_card_day(D(2026, 10, 2)))
ck("시작 전은 기존 형식", not FC.is_card_day(D(2026, 9, 28)))
ck("운세가 아니면 표 안 함", not FC.use_card({**SB, "topic": "politics"}))
os.environ["FORTUNE_CARD"] = "0"
ck("FORTUNE_CARD=0 이면 끈다", not FC.use_card(SB))
os.environ.pop("FORTUNE_CARD")
ck("운세 + 표 날이면 켠다", FC.use_card(SB))
import datetime as _dt
_odd = {**SB, "date": str(FC.CARD_START + _dt.timedelta(days=1))}
ck("기본은 매일 표(홀수 날도)", FC.use_card(_odd))
os.environ["FORTUNE_CARD"] = "ab"
ck("FORTUNE_CARD=ab 면 홀수 날은 기존 형식", not FC.use_card(_odd) and FC.use_card(SB))
os.environ.pop("FORTUNE_CARD")
ck("CARD_START 이전 날짜는 표 아님", not FC.use_card({**SB, "date": str(FC.CARD_START - _dt.timedelta(days=1))}))

print("── 표 데이터 ──")
top, s1 = FC.top_from_storyboard(SB)
ck("루틴의 1~3위를 그대로 쓴다", top == ["쥐", "용", "원숭이"] and s1 == 93, f"{top} {s1}")
rows = FC.build_rows(SB)
ck("12띠가 한 번씩", sorted(r["animal"] for r in rows) == sorted(FC.ANIMALS), str([r["animal"] for r in rows]))
ck("1~3위는 스토리보드 순서", [r["animal"] for r in rows[:3]] == ["쥐", "용", "원숭이"])
ck("1위 점수 = 스토리보드 93", rows[0]["score"] == 93)
ck("점수는 순위대로 줄어든다", all(a["score"] > b["score"] for a, b in zip(rows, rows[1:])),
   str([r["score"] for r in rows]))
ck("쥐띠 출생연도 48·60·72·84·96", FC.years_of("쥐") == [1948, 1960, 1972, 1984, 1996])
ck("한 줄은 9자 이내", all(len(r["line"]) <= 9 for r in rows), str([r["line"] for r in rows]))
ck("같은 날짜면 같은 표", FC.build_rows(SB) == rows)
ck("날짜가 바뀌면 4~12위가 바뀐다",
   [r["animal"] for r in FC.build_rows({**SB, "date": "2026-10-02"})][3:] != [r["animal"] for r in rows][3:])
ck("순위를 못 찾아도 12띠 표가 나온다", len(FC.build_rows({"date": "2026-10-02", "scenes": []})) == 12)
m = FC.meta(SB)
ck("제목에 띠별 운세·출생연도 범위", "띠별 운세" in m["title"] and "45~96년생" in m["title"] and len(m["title"]) <= 95, m["title"])
ck("설명에 재미로 보는 운세 고지", "재미로 보는 운세" in m["description"])
ck("주간 모드면 '이번 주'", FC.meta({**SB, "notes": "MODE=weekly"})["title"].startswith("이번 주"))

print("── 표 화면 ──")
spec = FC.build_spec(SB)
sc = {**spec["scenes"][0], "start": 0.0, "clip": 7.0}
html = M.scene_html(0, sc, spec["accent"])
ck("칸 12개", html.count('class="cell') == 12)
ck("1~3위 칸 강조", html.count('class="cell top3"') == 3)
xs = [M.card_cell_xy(k) for k in range(12)]
ck("오른쪽 버튼 열·아래 제목 자리를 비운다",
   all(x + M.CARD_W <= 960 and y + M.CARD_H <= 1500 for x, y in xs), str(xs[-1]))   # 10/10: 1000 → 960(버튼 열)
js = M.scene_js(0, sc, spec["accent"])
ck("표는 0초부터 보인다(투명에서 시작하는 등장 없음)", "tl.from(" not in js and "opacity:0" not in js, js)
page = M.build_html([sc], 7.0, spec["accent"])
ck("표 CSS 가 붙는다", ".cell{" in page and ".topband" not in page)
ck("최소 길이 7초", spec["_min_total"] == 7.0)

print("── 뉴스 첫 화면 헤드라인 ──")
ck("정치는 켠다", M.top_hook_on("politics") and M.top_hook_on("stock_us"))
ck("운세·별자리는 끈다", not M.top_hook_on("fortune") and not M.top_hook_on("horoscope"))
os.environ["TOP_HOOK"] = "0"
ck("TOP_HOOK=0 이면 끈다", not M.top_hook_on("politics"))
os.environ.pop("TOP_HOOK")
hook = {"type": "hook", "pill": "국정감사", "lines": ["대법원장이", "증인석에", "선다"], "highlight": "증인석",
        "narration": "…", "start": 0.0, "clip": 3.0, "_top": True}
h = M.scene_html(0, hook, "#D97757")
band = int(re.search(r'id="s0-band" style="height:(\d+)px"', h).group(1))
ck("진한 띠 위에 흰 글씨", 'class="topband"' in h and 'class="h1 top"' in h)
ck("글자는 맨 위에서 시작", f'top:{M.TOP_PAD}px' in h)
ck(f"세 줄 헤드라인이 화면 위 1/3 안 ({band}px)", band <= 640, str(band))
ck("필은 띠 아래", f'top:{band + 40}px' in h)
ck("CSS 가 붙는다", ".topband{" in M.build_html([hook], 3.0, "#D97757"))
plain = {**hook, "_top": False}
ck("표시 없으면 기존 화면 그대로", 'topband' not in M.scene_html(0, plain, "#D97757"))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
