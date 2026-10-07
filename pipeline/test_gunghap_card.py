#!/usr/bin/env python3
"""띠 궁합표(gunghap_card) 오프라인 테스트 — 지지·오행 관계·6편 시리즈 편성·문구·화면·연결."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cover_short as CS  # noqa: E402
import fortune_card as FC  # noqa: E402
import gunghap_card as G  # noqa: E402
import motion_short as M  # noqa: E402
import tier_card as T  # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


A = FC.ANIMALS
d0 = G.START

print("── 관계 ──")
couple = {r["animal"]: (r["good"][0]["animal"], r["bad"][0]["animal"]) for r in G.build_rows(d0, G.THEMES[0])}
ck("부부: 육합 짝(쥐↔소·호랑이↔돼지·토끼↔개·용↔닭·뱀↔원숭이·말↔양)",
   all(couple[a][0] == b and couple[b][0] == a for a, b in [("쥐", "소"), ("호랑이", "돼지"), ("토끼", "개"), ("용", "닭"), ("뱀", "원숭이"), ("말", "양")]))
ck("부부: 조심할 띠 = 충(6칸 건너편)", all(couple[A[k]][1] == A[(k + 6) % 12] for k in range(12)))
fr = {r["animal"]: [x["animal"] for x in r["good"]] for r in G.build_rows(d0, G.THEMES[1])}
ck("친구·동업: 삼합 두 띠(쥐 → 원숭이·용 · 호랑이 → 말·개)", sorted(fr["쥐"]) == sorted(["원숭이", "용"]) and sorted(fr["호랑이"]) == sorted(["말", "개"]), fr["쥐"])
mrows = {r["animal"]: r for r in G.build_rows(d0, G.THEMES[2])}
money = {a: [x["animal"] for x in r["good"]] for a, r in mrows.items()}
ck("재물: 호랑이(나무)가 다스리는 흙 = 소·용·양·개", money["호랑이"] == ["소", "용", "양", "개"], money["호랑이"])
ck("재물: 쥐(물)가 다스리는 불 = 뱀·말 중 충인 말은 '재물 다툼'으로(같은 띠가 양쪽에 오지 않게)",
   money["쥐"] == ["뱀"] and mrows["쥐"]["bad"][0]["animal"] == "말" and mrows["쥐"]["bad"][0]["rel"] == "충(재물)"
   and sum(r["bad"][0]["rel"] == "충(재물)" for r in mrows.values()) == 4, (money["쥐"], mrows["쥐"]["bad"]))
helper = {r["animal"]: ([x["animal"] for x in r["good"]], [x["animal"] for x in r["bad"]]) for r in G.build_rows(d0, G.THEMES[3])}
ck("귀인: 쥐(물)를 살리는 쇠 = 원숭이·닭 · 누르는 흙 = 소·용·양·개",
   helper["쥐"] == (["원숭이", "닭"], ["소", "용", "양", "개"]), helper["쥐"])
ok_rows = True
for th in G.THEMES:
    for r in G.build_rows(d0, th):
        g = {x["animal"] for x in r["good"]}
        b = {x["animal"] for x in r["bad"]}
        ok_rows &= bool(g) and bool(b) and not (g & b) and r["animal"] not in g | b
ck("모든 묶음 · 12띠: 좋은 짝·조심할 띠가 있고 서로 겹치지 않고 자기 띠가 없다", ok_rows)
gr = G.build_rows(d0, G.THEMES[5])
ck("손주 묶음: 짝의 출생연도는 2008~2025 아이 해", all(2008 <= y <= 2025 for r in gr for x in r["good"] for y in x["years"]))

print("── 6편 시리즈 편성 ──")
days = [d0 + dt.timedelta(days=k) for k in range(40)]
posts = [(d, G.theme_for(d)["id"]) for d in days if G.is_post_day(d)]
ck("화·금 · 10/9 부터 6편 · 그 뒤로는 쓰지 않는다", [d.isoformat() for d, _ in posts] ==
   ["2026-10-09", "2026-10-13", "2026-10-16", "2026-10-20", "2026-10-23", "2026-10-27"], posts)
ck("6편 묶음이 전부 다르다(같은 표를 다시 올리지 않는다)", len({t for _, t in posts}) == 6 == len(G.THEMES))
ck("첫 편은 부부, 셋째는 재물", posts[0][1] == "couple" and posts[2][1] == "money")

print("── 문구 ──")
bad, texts = [], []
for d, _ in posts:
    sb = G.storyboard(d)
    sc = sb["scenes"][0]
    if len(G.title(d)) > 95 or len(sc["narration"]) > 80:
        bad.append((d, len(G.title(d)), len(sc["narration"])))
    if any(len(r[k]) > 10 for r in sc["rows"] for k in ("good_line", "bad_line")):
        bad.append((d, "한 줄 10자"))
    texts += [G.title(d), G.description(d), sc["narration"], sc["foot"]]
ck("제목 95자 · 내레이션 80자 · 칸 한 줄 10자", not bad, bad[:3])
hits = sorted({w for w in BANNED for t in texts if w in t})
ck("금지어 없음", not hits, hits)
desc = G.description(d0)
ck("설명란: 12띠 전부(출생연도·짝·근거) · 정한 방법 · 재미 고지", all(f"· {a}띠(" in desc for a in A)
   and "궁합은 이렇게 봤어요" in desc and "재미로" in desc)
ck("제목: '궁합표 |' 꼴 · 45~96년생", G.title(d0) == "부부 띠 궁합표 | 내 띠의 찰떡 짝·조심할 띠 · 45~96년생 전부")
ck("내레이션: 예시 두 띠 · 찾아보라는 말", G.narration(d0) == "부부 띠 궁합표예요. 쥐띠의 찰떡 짝은 소띠, 호랑이띠는 돼지띠예요. 내 띠도 찾아보세요.",
   G.narration(d0))
ck("편성일이 아니면 make 가 아무것도 안 쓴다", not G.is_post_day(dt.date(2026, 10, 10)) and not G.is_post_day(dt.date(2026, 10, 30)))

print("── 화면(motion_short) ──")
sb = G.storyboard(d0)
sc = dict(sb["scenes"][0], start=0.0, dur=9.0, clip=9.0)
html = M.scene_html(0, sc, G.ACCENT)
ck("12줄 · 머리글 3개 · 아래 한 줄", html.count('class="ghrow"') == 12 and html.count('class="ghhead"') == 3 and "ghfoot" in html)
ck("머리글 = 내 띠 · 묶음의 두 열 이름", "찰떡 짝" in html and "조심할 띠" in html)
ck("오른쪽 쇼츠 버튼 열(x 960~)을 비운다", M.GH_X0 + M.GH_W <= 960)
worst = min((M.gunghap_layout(G.storyboard(d)["scenes"][0]["rows"]) for d, _ in posts), key=lambda l: l["fs"])
ck("모든 편: 띠 이름 36px · 짝 30px · 출생연도 20px 이상", min(M.gunghap_layout(G.storyboard(d)["scenes"][0]["rows"])["fa"] for d, _ in posts) >= 36
   and min(M.gunghap_layout(G.storyboard(d)["scenes"][0]["rows"])["fg"] for d, _ in posts) >= 30 and worst["fs"] >= 20, worst)
js = M.scene_js(0, sc, G.ACCENT, bar_h=560, presenter=False)
ck("0초부터 전부 보이고 줄이 차례로 톡", "tl.from(" not in js and "-r11" in js)
full = M.build_html([sc], 9.0, G.ACCENT)
ck("CSS 가 붙는다 · 진행자는 궁합표에 서지 않는다", ".ghrow{" in full
   and '"gunghap"' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1].splitlines()[0])

print("── 배경 그림 ──")
ck("운세 그림체: 한옥 실내·민무늬 벽 · 'lucky' 없음(중국 설 글자 快乐 방지 — 부정 문구는 지워지므로 긍정형으로)",
   "hanok" in CS.TOPIC_STYLE_PROMPT["fortune"] and "plain" in CS.TOPIC_STYLE_PROMPT["fortune"]
   and "lucky" not in CS.TOPIC_STYLE_PROMPT["fortune"])
ck("배경 묘사: 사람 없음 · 글자 금지 꼬리", all(th["hook"].endswith("no people") for th in G.THEMES)
   and sb["thumbnail_hook"].endswith(G.HOOK_TAIL))

print("── 파이프라인 연결 ──")
ck("아침 운세 표·등급표 A/B 가 궁합표를 덮어쓰지 않는다", not FC.use_card(sb) and not T.use_ab(sb))
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
ck("run_pipeline: 재생목록·카피 점검 제외·제목/설명", "GUNGHAP_PLAYLIST" in rp and "gunghap_card.is_gunghap(sb)" in rp
   and "gunghap_card.meta(sb)" in rp)
ck("파일 경로 = output/news/<날짜>_fortune_gunghap_storyboard.json",
   G.path_for(d0, root="/repo").replace("\\", "/").endswith("output/news/2026-10-09_fortune_gunghap_storyboard.json"))
fm = json.load(open(os.path.join(os.path.dirname(HERE), "tools", "pulse_formats.json"), encoding="utf-8"))
rules = fm["channels"]["wb"]["rules"]
for d, tid in posts:
    t = G.title(d)
    hit = next((r["key"] for r in rules if "title_re" in r and re.search(r["title_re"], t)
                or "title_prefix" in r and t.startswith(r["title_prefix"])), None)
    if hit != "gunghap":
        ck(f"채널 맥박이 '{tid}' 편을 궁합표로 센다", False, hit)
        break
else:
    ck("채널 맥박이 6편 모두 '궁합표'로 센다(pulse_formats gunghap)", True)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
