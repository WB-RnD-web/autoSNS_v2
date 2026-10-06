#!/usr/bin/env python3
"""운세 등급표(tier_card) 오프라인 테스트 — 등급 규칙·칸 배치·문구·연결."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fortune_card as FC  # noqa: E402
import motion_short as M  # noqa: E402
import pulli_card as P  # noqa: E402
import tier_card as T  # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


print("── 등급 규칙 ──")
ck("합 → S · 충·원진·형 → C · 해·파 → B", [T.tier_of(r, "관성") for r in ("육합", "삼합", "충", "원진", "형", "해", "파")]
   == ["S", "S", "C", "C", "C", "B", "B"])
ck("관계 없음: 인성·비겁 → A · 식상·재성·관성 → B · 같은 띠 → A",
   [T.tier_of("", c) for c in ("인성", "비겁", "식상", "재성", "관성")] == ["A", "A", "B", "B", "B"]
   and T.tier_of("같은 띠", "관성") == "A")
d8 = dt.date(2026, 10, 8)
t8 = {t["id"]: [r["animal"] for r in t["items"]] for t in T.build_tiers(d8)}
ck("10/8 을묘일: S = 개(육합)·돼지·양(해묘미 삼합) · C = 닭(충)·원숭이(원진)·쥐(형)",
   t8["S"] == ["개", "돼지", "양"] and t8["C"] == ["닭", "원숭이", "쥐"], t8)
ck("…pulli_card 와 같은 일진 계산(같은 날 풀이형 1위가 S 안에 있다)", P.build_rows(d8)[0]["animal"] in t8["S"])

print("── 120일 ──")
days = [dt.date(2026, 10, 8) + dt.timedelta(days=k) for k in range(120)]
bad, texts, shapes, combos = [], [], set(), set()
for d in days:
    tiers = T.build_tiers(d)
    animals = [r["animal"] for t in tiers for r in t["items"]]
    if sorted(animals) != sorted(FC.ANIMALS):
        bad.append((d, "12띠가 한 번씩"))
    if len(tiers[0]["items"]) != 3:
        bad.append((d, "S 는 늘 3띠(육합 1 + 삼합 2)"))
    if not tiers[3]["items"]:
        bad.append((d, "C 가 비었다"))
    if any(len(r["line"]) > 9 for t in tiers for r in t["items"]):
        bad.append((d, "칸 한 줄 9자"))
    sb = T.storyboard(d)
    if len(T.title(d)) > 95 or len(sb["scenes"][0]["narration"]) > 80:
        bad.append((d, "제목 95자·내레이션 80자", len(T.title(d)), len(sb["scenes"][0]["narration"])))
    lay = M.tier_layout(sb["scenes"][0]["tiers"])
    if lay["bottom"] > M.TIER_BOTTOM + 1 or min(lay["fn"], lay["fy"], lay["fl"]) < 24 or lay["fn"] < 44:
        bad.append((d, "배치(아래 22% 침범·글자 너무 작음)", lay["bottom"], lay["fn"], lay["fy"], lay["fl"]))
    shapes.add(tuple(len(t["items"]) for t in tiers))
    combos.add(tuple(tuple(r["animal"] for r in t["items"]) for t in tiers))
    texts += [T.title(d), T.description(d), sb["scenes"][0]["narration"], sb["scenes"][0]["foot"]]
    texts += [r["line"] for t in tiers for r in t["items"]]
ck("12띠 한 번씩 · S 3띠 · C 비지 않음 · 한 줄 9자 · 제목 95자 · 내레이션 80자 · 칸 배치", not bad, bad[:3])
ck("칸 수 모양이 날마다 다르다(S·A·B·C 띠 수 조합 8가지 이상 — 틀에 찍은 표가 아니다)", len(shapes) >= 8, sorted(shapes))
ck("등급 조합이 날마다 다르다(120일에 50가지 이상 · 60일 주기)", len(combos) >= 50, len(combos))
hits = sorted({w for w in BANNED for t in texts if w in t})
ck("금지어 없음(의료·투자·겁주기)", not hits, hits)
ck("같은 날짜면 같은 표", T.storyboard(d8) == T.storyboard(d8))

print("── 스토리보드·메타 ──")
sb = T.storyboard(d8)
sc = dict(sb["scenes"][0], start=0.0, dur=9.6, clip=9.6)
ck("토픽 fortune_tier · 장면 = tier 하나 · 9초 이상 머문다", sb["topic"] == "fortune_tier"
   and [s["type"] for s in sb["scenes"]] == ["tier"] and sb["_min_total"] >= 9)
ck("등급 칸: S·A·B·C 순서 · 색 · 띠마다 이름·출생연도·한 줄", [t["id"] for t in sc["tiers"]] == ["S", "A", "B", "C"]
   and all(t["color"].startswith("#") for t in sc["tiers"])
   and set(sc["tiers"][0]["items"][0]) == {"animal", "years", "line"})
ck("내레이션: 영문 등급은 소리 나는 대로(에스급·씨급) · 일진 이름", "에스급" in sc["narration"] and "씨급" in sc["narration"]
   and "을묘일" in sc["narration"] and not re.search(r"[SABC]급", sc["narration"]))
desc = T.description(d8)
ck("설명란: 12띠 등급·출생연도·이유 전부 · 정한 방법 · 재미 고지", all(f"· {a}띠(" in desc for a in FC.ANIMALS)
   and "등급은 이렇게 정했어요" in desc and "재미로" in desc and all(f"[{x}급" in desc for x in "SABC"))
ck("제목: 등급표 · 일진 이름 · 45~96년생", T.title(d8) == "오늘 띠별 운세 등급표 S급~C급 | 10월 8일 을묘일 · 45~96년생 전부")
ck("배경 그림: 글자·간판 금지 꼬리 · 중국 설 장식 없음(10/7 견본 快乐 글자)",
   sb["thumbnail_hook"].endswith(P.HOOK_TAIL) and "knot" not in sb["thumbnail_hook"] and "festive" not in sb["thumbnail_hook"])

print("── 화면(motion_short) ──")
html = M.scene_html(0, dict(sc), "#C9A227")
ck("띠 칸 12개 · 등급 칸 4개 · 아래 한 줄", html.count('class="tchip') == 12 and html.count('class="tlab"') == 4 and "tfoot" in html)
xs = [float(x) + float(w) for x, w in re.findall(r'class="tchip[^"]*"[^>]*left:([\d.]+)px;top:[\d.]+px;width:([\d.]+)px', html)]
ck("오른쪽 쇼츠 버튼 열(x 960~)을 비운다", xs and max(xs) <= 961, max(xs) if xs else None)
ck("S 칸은 등급 색 테두리", html.count('class="tchip top"') == 3)
js = M.scene_js(0, dict(sc), "#C9A227", bar_h=560, presenter=False)
ck("0초부터 전부 보이고(등장 애니메이션 없음) S 칸만 톡", "tl.from(" not in js and "-t0-0" in js)
empty = dict(sc, tiers=[dict(t, items=[]) if t["id"] == "B" else t for t in sc["tiers"]])
ck("빈 등급이면 '오늘은 없어요'", "오늘은 없어요" in M.scene_html(0, empty, "#C9A227"))
full = M.build_html([dict(sc)], 9.6, "#C9A227")
ck("CSS 가 붙는다 · 진행자는 등급표에 서지 않는다", ".tchip{" in full
   and '"tier")' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1][:200])

print("── 파이프라인 연결 ──")
ck("아침 운세 표(fortune_card)가 등급표를 덮어쓰지 않는다", not FC.use_card(sb))
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
ck("run_pipeline: 재생목록·카피 점검 제외·제목/설명", "TIER_PLAYLIST" in rp and "tier_card.is_tier(sb)" in rp and "tier_card.meta(sb)" in rp)
path = T.path_for(d8, root="/repo")
ck("파일 경로 = output/news/<날짜>_fortune_tier_storyboard.json (shorts.yml 이 집는다)",
   path.replace("\\", "/").endswith("output/news/2026-10-08_fortune_tier_storyboard.json"))
fm = json.load(open(os.path.join(os.path.dirname(HERE), "tools", "pulse_formats.json"), encoding="utf-8"))
rules = fm["channels"]["wb"]["rules"]
hit = next((r["key"] for r in rules if "title_re" in r and re.search(r["title_re"], T.title(d8))
            or "title_prefix" in r and T.title(d8).startswith(r["title_prefix"])), None)
ck("채널 맥박이 등급표를 따로 센다(pulse_formats 'tier')", hit == "tier", hit)

print("── 06:13 매일 운세 자리 격일 A/B ──")
os.environ.pop("FORTUNE_TIER", None)


def daily(d, notes=""):
    return {"date": d, "topic": "fortune", "notes": notes, "scenes": []}


ab = {d: T.use_ab(daily(d)) for d in ("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-21", "2026-10-22", "2026-10-23")}
ck("10/9 시작 · 하루씩 번갈아 · 10/22 끝(10/23 부터 기존 표)", ab == {"2026-10-08": False, "2026-10-09": True, "2026-10-10": False,
   "2026-10-11": True, "2026-10-21": True, "2026-10-22": False, "2026-10-23": False}, ab)
n_tier = sum(T.use_ab(daily((dt.date(2026, 10, 9) + dt.timedelta(days=k)).isoformat())) for k in range(14))
ck("2주(10/9~22) 중 짝수 번째 날 7번 — 그중 10/19 월요일은 주간 운세라 실제 등급표는 6편", n_tier == 7, n_tier)
ck("월요일 '이번 주 운세'(MODE=weekly)는 건드리지 않는다", not T.use_ab(daily("2026-10-19", "MODE=weekly")))
ck("테마·이름·풀이형·등급표 자체 대본은 건드리지 않는다",
   not any(T.use_ab({"date": "2026-10-09", "topic": t}) for t in ("fortune_theme", "fortune_name", "fortune_pulli", "fortune_tier", "politics")))
os.environ["FORTUNE_TIER"] = "0"
ck("FORTUNE_TIER=0 이면 끈다", not T.use_ab(daily("2026-10-09")))
os.environ["FORTUNE_TIER"] = "1"
ck("FORTUNE_TIER=1 이면 10/9 부터 매일", T.use_ab(daily("2026-10-10")) and T.use_ab(daily("2026-11-30")) and not T.use_ab(daily("2026-10-08")))
os.environ.pop("FORTUNE_TIER", None)
spec = T.build_spec(daily("2026-10-09"))
ck("등급표 날 스펙 = 그날 등급표 장면(9초 이상)", [s["type"] for s in spec["scenes"]] == ["tier"] and spec["_min_total"] >= 9
   and spec["scenes"][0]["pill"].startswith("10월 9일"))
ck("run_pipeline: 등급표 분기가 기존 표(fortune_card)보다 먼저 · 제목/설명도 등급표",
   rp.index("tier_card.use_ab(sb)") < rp.index("fortune_card.use_card(sb)") and "elif fortune_card.use_card(sb):" in rp
   and rp.count("tier_card.use_ab(sb)") == 2)
wf = open(os.path.join(os.path.dirname(HERE), ".github", "workflows", "shorts.yml"), encoding="utf-8").read()
ck("shorts.yml 이 FORTUNE_TIER 레포 변수를 파이썬에 넘긴다(끄기 스위치)", "FORTUNE_TIER: ${{ vars.FORTUNE_TIER || 'ab' }}" in wf)
exs = json.load(open(os.path.join(os.path.dirname(HERE), "tools", "pulse_experiments.json"), encoding="utf-8"))["experiments"]
e = next((x for x in exs if x["id"] == "tier-ab"), None)
ck("실험 달력: tier-ab 10/9~10/23 · tier vs daily", e and e["start"] == T.AB_START.isoformat() and e["judge"] == "2026-10-23"
   and e["formats"] == ["tier", "daily"], e)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
