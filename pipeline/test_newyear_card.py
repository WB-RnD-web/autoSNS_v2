#!/usr/bin/env python3
"""2027 신년운세 표(newyear_card) 오프라인 테스트 — 간지·관계·4편 편성·문구·화면·연결."""
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
import newyear_card as N  # noqa: E402
import tier_card as T  # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


print("── 간지 ──")
ck("2027 = 정미(丁未) · 불 · 흙 · 양띠", N.YP["name"] == "정미" and N.YP["hanja"] == "丁未" and N.YP["stem_el"] == "화"
   and N.YP["branch_el"] == "토" and N.YP["animal"] == "양", N.YP)
ck("2026 = 병오 · 2024 = 갑진 · 1984 = 갑자", N.year_pillar(2026)["name"] == "병오" and N.year_pillar(2024)["name"] == "갑진"
   and N.year_pillar(1984)["name"] == "갑자")
ck("끝자리 → 천간: 0 경 · 4 갑 · 7 정 · 9 기", [N.STEMS[N.digit_stem(d)] for d in (0, 4, 7, 9)] == ["경", "갑", "정", "기"])

print("── 1편 총운 등급표 ──")
tot = {t["id"]: [r["animal"] for r in t["items"]] for t in N.build_tiers("total")}
ck("S = 말(오미 육합) · 돼지·토끼(해묘미 삼합)", tot["S"] == ["말", "돼지", "토끼"], tot["S"])
ck("C = 소(축미 충) · 쥐(자미 원진) · 개(축술미 형)", tot["C"] == ["소", "쥐", "개"], tot["C"])
ck("A = 양(같은 띠) · 용(불이 흙을 살림) · 뱀(같은 불) / B = 호랑이·원숭이·닭",
   tot["A"] == ["양", "용", "뱀"] and tot["B"] == ["호랑이", "원숭이", "닭"], (tot["A"], tot["B"]))
ck("12띠가 한 번씩", sorted(a for v in tot.values() for a in v) == sorted(FC.ANIMALS))

print("── 2편 재물운 등급표 ──")
mon = {t["id"]: [r["animal"] for r in t["items"]] for t in N.build_tiers("money")}
ck("S = 토끼(흙이 재물 + 삼합) · 돼지(불이 재물 + 삼합)", mon["S"] == ["토끼", "돼지"], mon["S"])
ck("A = 말(육합) · 호랑이(흙이 재물) · C = 개(형) · 소(충)", mon["A"] == ["말", "호랑이"] and mon["C"] == ["개", "소"], (mon["A"], mon["C"]))
ck("쥐는 재물 기운이지만 원진이라 B", "쥐" in mon["B"] and N.money_line("원진", N.money_cats(0)) == "재물 기운·원진")
ck("총운과 재물운 표가 다르다", tot != mon)

print("── 3편 좋은 달·조심할 달 ──")
mr = {r["animal"]: r for r in N.month_rows()}
ck("월건: 1월 축 · 2월 인 · 7월 미 · 12월 자", [N.BRANCHES[N.MONTH_BRANCH[m]] for m in (1, 2, 7, 12)] == ["축", "인", "미", "자"])
ck("쥐: 좋은 달 1월(육합)·4·8월(삼합) · 조심 6월(충)·7월(원진)·3월(형)",
   mr["쥐"]["good"] == [(1, "육합"), (4, "삼합"), (8, "삼합")] and mr["쥐"]["bad"] == [(6, "충"), (7, "원진"), (3, "형")],
   (mr["쥐"]["good"], mr["쥐"]["bad"]))
ck("말: 좋은 달 7월(육합) · 조심 12월(충)", mr["말"]["good"][0] == (7, "육합") and mr["말"]["bad"][0] == (12, "충"))
ok = all(r["good"] and r["bad"] and not ({m for m, _ in r["good"]} & {m for m, _ in r["bad"]}) and len(r["bad"]) <= 3
         for r in mr.values())
ck("모든 띠: 좋은 달·조심할 달이 있고 겹치지 않고 조심할 달은 셋까지", ok)

print("── 4편 태어난 해 끝자리 ──")
dr = {r["digit"]: r for r in N.digit_rows()}
gods = {d: r["god"] for d, r in dr.items()}
ck("십신: 0 정관·1 편관·2 정재·3 편재·4 상관·5 식신·6 겁재·7 비견·8 정인·9 편인",
   gods == {0: "정관", 1: "편관", 2: "정재", 3: "편재", 4: "상관", 5: "식신", 6: "겁재", 7: "비견", 8: "정인", 9: "편인"}, gods)
ck("천간합은 끝자리 2(정임) · 천간충은 끝자리 3(정계)만", [d for d in dr if dr[d]["hap"]] == [2] and [d for d in dr if dr[d]["chung"]] == [3])
ck("끝자리 출생연도 = 45~96 안 · 끝자리 일치", all(y % 10 == d and 1945 <= y <= 1996 for d, r in dr.items() for y in r["years"]))

print("── 4편 편성 ──")
days = [N.START + dt.timedelta(days=k) for k in range(30)]
posts = [(d, N.episode_for(d)["id"]) for d in days if N.is_post_day(d)]
ck("월·목 · 10/12 부터 4편 · 그 뒤로는 쓰지 않는다", [d.isoformat() for d, _ in posts] ==
   ["2026-10-12", "2026-10-15", "2026-10-19", "2026-10-22"], posts)
ck("편이 전부 다르다(같은 표를 다시 올리지 않는다) · 첫 편 총운", len({e for _, e in posts}) == 4 and posts[0][1] == "total")
ck("화·금(궁합표 날)과 겹치지 않는다", all(d.weekday() not in (1, 4) for d, _ in posts))

print("── 문구 ──")
bad, texts = [], []
for d, eid in posts:
    sb = N.storyboard(d)
    sc = sb["scenes"][0]
    if len(N.title(N.episode_by_id(eid))) > 95 or len(sc["narration"]) > 80:
        bad.append((eid, len(N.title(N.episode_by_id(eid))), len(sc["narration"])))
    if sc["type"] == "gunghap" and any(len(r[k]) > 10 for r in sc["rows"] for k in ("good_line", "bad_line")):
        bad.append((eid, "한 줄 10자"))
    if sc["type"] == "tier" and any(len(r["line"]) > 10 for t in sc["tiers"] for r in t["items"]):
        bad.append((eid, "칸 한 줄 10자"))
    texts += [sb["platforms"]["youtube"]["title"], sb["platforms"]["youtube"]["description"], sc["narration"], sc["foot"],
              sc["title"], sc["pill"]]
ck("제목 95자 · 내레이션 80자 · 칸 한 줄 10자", not bad, bad[:3])
hits = sorted({w for w in BANNED for t in texts if w in t})
ck("금지어 없음('삼재'·'대박'·'투자' 포함)", not hits, hits)
ck("제목마다 '정미년'(채널 맥박이 신년운세로 센다)", all("정미년" in N.title(e) for e in N.EPISODES))
nar = N.narration(N.EPISODES[0])
ck("내레이션: 우리말 등급(대길) · 조심 띠는 조언으로(어르신 눈높이 10/7)", "대길은 말, 돼지, 토끼띠" in nar
   and "소, 쥐, 개띠는 서두르지 말고" in nar and not re.search(r"[SABC]급|에스급|씨급", nar), nar)
scr = [x for e in N.EPISODES for x in [N.title(e)] + [json.dumps(N.scene_for(e), ensure_ascii=False)]]
jargon = sorted({w for w in ("편관", "상관", "겁재", "비견", "편인", "정인", "정관", "편재", "정재", "식신", "S급", "C급") for t in scr if w in t})
ck("제목·화면에 영문 등급·십신 이름이 없다(근거 용어는 설명란에만)", not jargon, jargon)
desc = N.description(N.EPISODES[0])
ck("설명란: 12띠 전부(출생연도·이유) · 정한 방법 · 재미 고지", all(f"· {a}띠(" in desc for a in FC.ANIMALS)
   and "이렇게 정했어요" in desc and "재미로" in desc)
dd = N.description(N.EPISODES[3])
ck("끝자리 설명란: 0~9 전부 · 천간 · 십신", all(f"· 끝자리 {d}(" in dd for d in range(10)) and "정임 천간합" in dd)
ck("편성일이 아니면 make 가 쓰지 않는다", not N.is_post_day(dt.date(2026, 10, 13)) and not N.is_post_day(dt.date(2026, 10, 26)))

print("── 화면(motion_short) ──")
for d, eid in posts:
    sb = N.storyboard(d)
    sc = dict(sb["scenes"][0], start=0.0, dur=9.0, clip=9.0)
    html = M.scene_html(0, sc, N.ACCENT)
    if sc["type"] == "tier":
        lay = M.tier_layout(sc["tiers"])
        ok = (html.count('class="tlab"') == 4 and lay["bottom"] <= 1446 and lay["fn"] >= 36 and lay["fl"] >= 22
              and ">대길<" in html and ">★★★★<" in html)
        ck(f"{eid}: 등급 4칸 · 아래 22% 비움 · 띠 36px·이유 22px 이상", ok, (lay["bottom"], lay["fn"], lay["fl"]))
    else:
        lay = M.gunghap_layout(sc["rows"])
        n = len(sc["rows"])
        ok = html.count('class="ghrow"') == n and lay["fa"] >= 32 and lay["fs"] >= 20
        ck(f"{eid}: {n}줄 · 이름 32px·작은 글자 20px 이상", ok, lay)
dsc = N.storyboard(dt.date(2026, 10, 22))["scenes"][0]
dh = M.scene_html(0, dict(dsc, start=0.0, dur=9.0, clip=9.0), N.ACCENT)
ck("끝자리 표: 머리글 '태어난 해 끝자리' · 줄 이름 '끝자리 2' (띠가 붙지 않는다)", "태어난 해 끝자리" in dh and "끝자리 2<" in dh
   and "끝자리 2띠" not in dh)
gh = M.scene_html(0, dict(N.storyboard(dt.date(2026, 10, 19))["scenes"][0], start=0.0, dur=9.0, clip=9.0), N.ACCENT)
ck("달 표: 기본 머리글 '내 띠' · '쥐띠' 줄", ">내 띠<" in gh and ">쥐띠<" in gh)

print("── 배경 그림 ──")
ck("배경 묘사: 붉은 목도리 양 · 사람 없음 · 글자 금지 꼬리 · '새해·축제·lucky' 없음(중국 설 글자 방지)",
   all("lamb" in e["hook"] and e["hook"].endswith("no people") for e in N.EPISODES)
   and not any(w in e["hook"].lower() for e in N.EPISODES for w in ("new year", "festive", "lucky", "calendar", "lantern")))

print("── 파이프라인 연결 ──")
sb0 = N.storyboard(N.START)
ck("아침 운세 표·등급표 A/B 가 신년운세를 덮어쓰지 않는다", not FC.use_card(sb0) and not T.use_ab(sb0))
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
ck("run_pipeline: 재생목록·카피 점검 제외·제목/설명", "NEWYEAR_PLAYLIST" in rp and "newyear_card.is_newyear(sb)" in rp
   and "newyear_card.meta(sb)" in rp)
ck("meta: 편 이름으로 제목·설명", N.meta(N.storyboard(dt.date(2026, 10, 15)))["title"].startswith("2027 정미년 띠별 재물운"))
ck("파일 경로 = output/news/<날짜>_fortune_newyear_storyboard.json",
   N.path_for(N.START, root="/repo").replace("\\", "/").endswith("output/news/2026-10-12_fortune_newyear_storyboard.json"))
fm = json.load(open(os.path.join(os.path.dirname(HERE), "tools", "pulse_formats.json"), encoding="utf-8"))
rules = fm["channels"]["wb"]["rules"]
miss = []
for e in N.EPISODES:
    t = N.title(e) + " #shorts"
    hit = next((r["key"] for r in rules if "title_re" in r and re.search(r["title_re"], t)
                or "title_prefix" in r and t.startswith(r["title_prefix"])), None)
    if hit != "newyear":
        miss.append((e["id"], hit))
ck("채널 맥박이 4편 모두 '신년운세'로 센다(등급표·해 끝자리 표보다 먼저)", not miss, miss)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
