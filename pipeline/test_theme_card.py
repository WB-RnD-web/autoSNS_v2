#!/usr/bin/env python3
"""띠별 테마 순위 표(theme_card) 회귀 테스트.

    python pipeline/test_theme_card.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import theme_card as T        # noqa: E402
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


def width_px(s: str, hangul: float, space: float) -> float:
    return sum(space if c == " " else hangul for c in s)


print("── 테마 목록")
ids = [t["id"] for t in T.THEMES]
ck("테마 id 겹치지 않음", len(ids) == len(set(ids)), ids)
for th in T.THEMES:
    card = th["card"]
    # .ctitle 96px · letter-spacing -3px · 폭 960 — 한 줄에 들어가야 표가 밀리지 않는다
    ck(f"[{th['id']}] 화면 제목 한 줄({card})", len(re.findall(r"[가-힣]", card)) <= 9
       and width_px(card, 88, 26) <= 940, card)
    for tier, n in T.TIERS:
        bank = th[tier]
        ck(f"[{th['id']}] {tier} 문구 {n}개 이상", len(bank) >= n, len(bank))
        long = [x for x in bank if len(x) > 9]
        ck(f"[{th['id']}] {tier} 한 줄 9자 이내", not long, long)
    allines = th["top"] + th["mid"] + th["low"]
    ck(f"[{th['id']}] 문구 중복 없음", len(allines) == len(set(allines)))
    text = " | ".join(allines + [card, th["yt"], T.description(dt.date(2026, 10, 2), th)])
    bad = [w for w in T.BANNED if w in text]
    ck(f"[{th['id']}] 금지어 없음", not bad, bad)
    ck(f"[{th['id']}] 키비주얼에 글자·사람 금지 문구", "no text" in th["hook"] and "no people" in th["hook"]
       or "no faces" in th["hook"])

print("── 순환·결정성")
d0 = dt.date(2026, 10, 2)
seq = [T.theme_for(d0 + dt.timedelta(days=i))["id"] for i in range(len(T.THEMES))]
ck("첫 편 10/2 = 돈", seq[0] == "money", seq[0])
ck(f"{len(T.THEMES)}일 동안 테마가 다 다르다", len(set(seq)) == len(T.THEMES), seq)
ck("같은 날짜 → 같은 표", T.build_rows(d0, T.THEMES[0]) == T.build_rows(d0, T.THEMES[0]))
ck("날짜가 다르면 순위가 바뀐다",
   [r["animal"] for r in T.build_rows(d0, T.THEMES[0])] != [r["animal"] for r in T.build_rows(d0 + dt.timedelta(days=11), T.THEMES[0])])

for i in range(40):
    d = d0 + dt.timedelta(days=i)
    rows = T.build_rows(d, T.theme_for(d))
    ok = (len(rows) == 12 and sorted(r["animal"] for r in rows) == sorted(T.ANIMALS)
          and [r["rank"] for r in rows] == list(range(1, 13))
          and all(a["score"] > b["score"] for a, b in zip(rows, rows[1:]))
          and 90 <= rows[0]["score"] <= 98 and rows[-1]["score"] >= 58
          and all(r["years"] == FC.years_of(r["animal"]) for r in rows)
          and len({r["line"] for r in rows}) == 12)
    if not ok:
        ck(f"{d} 표 형식", False, rows)
        break
else:
    ck("40일치 표: 12띠·순위·점수 내림차순·출생연도·한 줄 중복 없음", True)

print("── 스토리보드·메타")
sb = T.storyboard(d0)
ck("topic = fortune_theme", sb["topic"] == "fortune_theme")
ck("장면은 card 하나(CI 에서 LLM 안 씀)", len(sb["scenes"]) == 1 and sb["scenes"][0]["type"] == "card")
ck("아침 표(fortune_card)로 오인하지 않는다", not FC.use_card(sb))
ck("아침 운세는 그대로 표", FC.use_card({"topic": "fortune", "date": "2026-10-02"}))
m = T.meta(sb)
ck("제목에 1위~12위 · 45~96년생 전부", "1위~12위" in m["title"] and "45~96년생 전부" in m["title"], m["title"])
ck("제목 + #shorts 100자 이내", len(m["title"] + " #shorts") <= 100, len(m["title"]))
ck("설명에 재미로 보는 운세 고지", "재미로 보는 운세" in m["description"])
ck("{m} 이 달로 바뀐다", "10월 돈 들어오는 띠 순위" in m["title"], m["title"])
ck("hook_title 짧게(20자 이내)", len(sb["hook_title"]) <= 20, sb["hook_title"])

import ledger as L            # noqa: E402
ck("ledger 키 = <날짜>_fortune_theme", L.key_for(sb) == "2026-10-02_fortune_theme", L.key_for(sb))

import run_pipeline as R      # noqa: E402
ck("재생목록 = 띠별 순위 특집", R.playlist_for("fortune_theme")[0] == R.THEME_PLAYLIST)
ck("아침 운세 재생목록은 그대로", R.playlist_for("fortune")[0] == R.FORTUNE_PLAYLIST)
ck("카테고리 24(엔터테인먼트)", R.category_for("fortune_theme") == "24")
ck("일시정지 아님", not R.is_paused(sb))
bm = R.build_meta(sb, False)
ck("build_meta 가 읽힌다(공개)", bm["privacy"] == "public" and bm["description"] == T.description(d0, T.THEMES[0]))
ck("AI 표시 안 함(그림체 토픽)", R.synthetic_label(sb, {"_bg": "x.png"}) is False)

print("── 렌더 HTML")
sc = {**sb["scenes"][0], "start": 0.0, "clip": 7.0}
html = M.scene_html(0, sc, sb["accent"])
ck("12칸", html.count('class="cell') == 12, html.count('class="cell'))
ck("화면 제목", sc["title"] in html)
ck("CSS 붙음", ".ctitle{" in M.build_html([sc], 7.0, sb["accent"]))

print("── make")
import json as _j        # noqa: E402
import tempfile          # noqa: E402
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "x.json")
    rc = T.main(["make", "--date", "2026-10-03", "--out", p])
    got = _j.load(open(p, encoding="utf-8"))
    ck("make 가 파일을 쓴다", rc == 0 and got["date"] == "2026-10-03" and got["theme"] == T.THEMES[1]["id"])
ck("path = output/news/<날짜>_fortune_theme_storyboard.json",
   T.path_for(d0).replace("\\", "/").endswith("output/news/2026-10-02_fortune_theme_storyboard.json"))

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ {FAIL}건 실패'}")
sys.exit(1 if FAIL else 0)
