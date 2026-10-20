#!/usr/bin/env python3
"""2027 신년운세 시리즈(newyear_series — 06:13 자리) 오프라인 테스트 — 편성·실험 안 건드림·편마다 새 정보·문구·화면·연결."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import birth_basis as BB  # noqa: E402
import fortune_card as FC  # noqa: E402
import motion_short as M  # noqa: E402
import newyear_card as NY  # noqa: E402
import newyear_series as S  # noqa: E402
import pulse as PU  # noqa: E402
import tier_card as T  # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0
D = dt.date


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def routine_sb(d: dt.date, topic: str = "fortune", mode: str = "daily") -> dict:
    """06:13 루틴이 올리는 '오늘 운세' 대본과 같은 꼴(필요한 칸만)."""
    return {"date": d.isoformat(), "topic": topic, "privacy": "public", "hook_title": "오늘 94점 나온 딱 한 띠",
            "headline": "띠별 운세 TOP3", "thumbnail_hook": "golden tiger emblem, starry night", "thumbnail_text": "94점",
            "scenes": [{"type": "hook", "narration": "오늘"}],
            "platforms": {"youtube": {"title": "오늘 94점 나온 딱 한 띠 #shorts", "description": "루틴 설명"}},
            "notes": f"모션그래픽 · MODE={mode}."}


print("── 편성 ──")
END = D(2026, 12, 31)
plan = S.schedule(D(2027, 3, 1))
days = [d for d, _ in plan]
ck("첫 편 2026-10-27(화) = 끝자리 재물운", plan[0] == (D(2026, 10, 27), "d_money"), plan[:1])
ck("10/27 전에는 시리즈가 없다(등급표 A/B 10/22·덕담표 10/24·신년 1차 10/22·판정 10/23~10/26 그대로)",
   all(S.episode_for(D(2026, 10, 1) + dt.timedelta(days=k)) is None for k in range(26)))
nov = [d for d in days if d < D(2026, 12, 8)]
dec = [d for d in days if d >= D(2026, 12, 8)]
ck("12/7 까지 화·토만 · 12/8 부터 화·금·토", {d.weekday() for d in nov} == {1, 5} and {d.weekday() for d in dec} == {1, 4, 5},
   ({d.weekday() for d in nov}, {d.weekday() for d in dec}))
ck("월(이번 주 운세)·목(08:13 신년운세 자리)·수·일엔 안 낸다 · 매달 1일도 안 낸다",
   all(d.weekday() not in (0, 2, 3, 6) and d.day != 1 for d in days))
slots = [D(2026, 10, 27) + dt.timedelta(days=k) for k in range((END - D(2026, 10, 27)).days + 1)]
slots = [d for d in slots if S.is_slot_day(d)]
ck("12/31 까지 시리즈 자리마다 편이 있다(목록이 모자라지 않다)", all(S.episode_for(d) for d in slots), [d for d in slots if not S.episode_for(d)])
ck(f"12/31 까지 {len(slots)}편 · 마지막 편 {S.last_day()} (12/31 뒤)", len(slots) >= 20 and S.last_day() > END, (len(slots), S.last_day()))
ids = [e for _, e in plan]
ck("편마다 한 번씩만(같은 표를 다시 올리지 않는다) · 목록 순서 그대로", ids == [e["id"] for e in S.EPISODES] and len(set(ids)) == len(ids))
fam = [S.episode_by_id(e)["family"] for e in ids]
ck("같은 꼴(family)이 연달아 나오지 않는다", all(a != b for a, b in zip(fam, fam[1:])), list(zip(ids, fam)))
weeks = {}
for k in range((END - D(2026, 10, 26)).days + 1):
    d = D(2026, 10, 26) + dt.timedelta(days=k)
    weeks.setdefault(d.isocalendar()[1], []).append(d)
full = [w for w in weeks.values() if len(w) == 7]
ck("매주 매일 운세(오늘 운세)가 사흘 이상 남는다(월 = 이번 주 운세 따로) — 습관 시청자",
   all(sum(1 for d in w if d.weekday() != 0 and not S.episode_for(d)) >= 3 for w in full))
ck("1차 묶음(08:13 월·목 newyear_card)은 10/22 뒤로 다시 살아나지 않는다(트리거는 그대로 건너뜀)",
   not any(NY.is_post_day(D(2026, 10, 23) + dt.timedelta(days=k)) for k in range(200)))
_keep = S.SERIES_FROM
S.SERIES_FROM = None
_off = (S.episode_for(D(2026, 10, 27)), S.use_slot(routine_sb(D(2026, 10, 27))), S.schedule(D(2027, 1, 31)))
S.SERIES_FROM = _keep
ck("끄기 스위치: SERIES_FROM = None 이면 아무 날도 안 바꾼다", _off == (None, False, []), _off)

print("── 루틴 대본 가로채기(use_slot) ──")
ck("10/27 06:13 오늘 운세 대본 → 시리즈", S.use_slot(routine_sb(D(2026, 10, 27))))
ck("10/28(수) 오늘 운세 → 그대로(매일 운세 표)", not S.use_slot(routine_sb(D(2026, 10, 28))))
ck("월요일 이번 주 운세(MODE=weekly)·이번 달(MODE=monthly)은 건드리지 않는다",
   not S.use_slot(routine_sb(D(2026, 10, 27), mode="weekly")) and not S.use_slot(routine_sb(D(2026, 10, 27), mode="monthly")))
others = ("fortune_theme", "fortune_name", "fortune_pulli", "fortune_tier", "fortune_gunghap", "fortune_newyear", "horoscope", "politics")
ck("다른 토픽(띠 테마·내 것 찾기·풀이형·덕담·등급표·궁합·신년 1차 …)은 건드리지 않는다",
   not any(S.use_slot(routine_sb(D(2026, 10, 27), topic=t)) for t in others))
ck("등급표 A/B 기간(10/9~10/22)엔 한 번도 바꾸지 않는다", not any(S.use_slot(routine_sb(D(2026, 10, 9) + dt.timedelta(days=k)))
                                                     for k in range(14)))
sb = routine_sb(D(2026, 10, 27))
ep = S.apply(sb)
ck("apply: 배경 묘사·커버 글자를 이 편 것으로(토픽·날짜 = ledger 키는 그대로)",
   sb["thumbnail_hook"].startswith(S.LAMB) and sb["hook_title"] == ep["card"] and sb["topic"] == "fortune"
   and sb["date"] == "2026-10-27" and "tiger" not in sb["thumbnail_hook"])
sp = S.build_spec(sb)
ck("build_spec: 표 한 장(gunghap) · 9초 이상", sp["scenes"][0]["type"] == "gunghap" and sp["_min_total"] >= 9 and len(sp["scenes"]) == 1)
ck("meta: 편 제목·설명", S.meta(sb)["title"].startswith("태어난 해 끝자리로 보는 2027 정미년 재물운")
   and "끝자리 9(" in S.meta(sb)["description"])
os.environ["FORTUNE_TIER"] = "1"
ck("등급표가 매일로 바뀌어도(판정 뒤 FORTUNE_TIER=1) 시리즈 날은 시리즈가 먼저 — run_pipeline 순서",
   S.use_slot(routine_sb(D(2026, 10, 31))) and T.use_ab(routine_sb(D(2026, 10, 31))))
os.environ.pop("FORTUNE_TIER")
ck("기본(FORTUNE_TIER=ab)이면 10/23 뒤 매일 운세 날은 1~12위 표(fortune_card) — 판정이 바꾸기 전까지",
   not T.use_ab(routine_sb(D(2026, 10, 28))) and FC.use_card(routine_sb(D(2026, 10, 28))))

print("── 간지·근거 ──")
ck("월주: 2027-01 신축(병오년 끝 달) · 02 임인(정임년 = 임인 머리) · 03 계묘 · 12 임자",
   [S.month_pillar(m)["name"] for m in (1, 2, 3, 12)] == ["신축", "임인", "계묘", "임자"])
ck("절기 입춘 = 2월 4일(birth_basis 입춘 표와 같은 날)", S.JEOLGI[2] == (BB.ipchun(2027).day, "입춘") and BB.ipchun(2027).month == 2)
ck("절기 날짜: 경칩 3/6 · 입하 5/6 · 입추 8/8 · 입동 11/8 · 대설 12/7",
   [S.JEOLGI[m][0] for m in (3, 5, 8, 11, 12)] == [6, 6, 8, 8, 7])
ck("1월 = 1월 5일~2월 3일 · 2월 = 2월 4일~3월 5일", S.month_span(1) == "1월 5일~2월 3일" and S.month_span(2) == "2월 4일~3월 5일")
gu = {S.STEMS[s]: "".join(S.BRANCHES[b] for b in bs) for s, bs in S.GUIIN.items()}
ck("천을귀인: 갑무경 축미 · 을기 자신 · 병정 해유 · 신 인오 · 임계 사묘",
   gu == {"갑": "축미", "무": "축미", "경": "축미", "을": "자신", "기": "자신", "병": "해유", "정": "해유", "신": "인오",
          "임": "사묘", "계": "사묘"}, gu)
ck("2027(미년)이 귀인 해인 끝자리 = 0·4·8(경·갑·무)", [r["digit"] for r in S.d_helper_rows() if r["year_guiin"]] == [0, 4, 8])
nap = {y: S.NAPEUM[S.gz_of_year(y)[0] // 2] for y in (1984, 1962, 1966, 2027, 1954, 1990)}
ck("납음: 84 갑자 해중금 · 62 임인 금박금 · 66 병오 천하수 · 2027 정미 천하수 · 54 사중금 · 90 노방토",
   nap == {1984: "해중금", 1962: "금박금", 1966: "천하수", 2027: "천하수", 1954: "사중금", 1990: "노방토"}, nap)
ck("역마: 신자진 → 인 · 해묘미 → 사 · 인오술 → 신 · 사유축 → 해",
   [S.YEOKMA[b] for b in (0, 3, 6, 9)] == [2, 5, 8, 11])
dm = {r["digit"]: r for r in S.d_money_rows()}
ck("끝자리 재물: 2(정재·정관+정임합)·4(상관·정재)·5(식신·편재)가 맨 위 · 8(정인·겁재)이 맨 아래",
   sorted(d for d, r in dm.items() if r["points"] >= 3) == [2, 4, 5] and min(dm, key=lambda d: dm[d]["points"]) == 8
   and dm[2]["gods"] == ("정재", "정관"), {d: r["points"] for d, r in dm.items()})
mo = {r["digit"]: r for r in S.d_month_rows()}
ck("끝자리 좋은 달: 2(임)는 7월 정미(정임합) · 조심 6월 병오(병임충) · 8(무)은 충 없음",
   7 in mo[2]["good_m"] and 6 in mo[2]["bad_m"] and mo[8]["chung"] == [] and mo[8]["bad_m"] == [4])

print("── 편마다 새 정보(서로 바꿔 끼워도 될 만큼 비슷한 영상 금지) ──")


def fingerprint(sc: dict) -> str:
    if sc["type"] == "tier":
        return json.dumps([[r["animal"] for r in t["items"]] for t in sc["tiers"]], ensure_ascii=False)
    return json.dumps([[r.get("good"), r.get("good_line"), r.get("bad"), r.get("bad_line")] for r in sc["rows"]], ensure_ascii=False)


probe = {e["id"]: NY.scene_for(e) for e in NY.EPISODES}
scenes = {e["id"]: S.scene_for(e) for e in S.EPISODES}
fps = [fingerprint(sc) for sc in scenes.values()]
ck("시리즈 편 화면 데이터가 서로 다 다르다", len(set(fps)) == len(fps))
ck("1차 묶음 총운·재물운·끝자리와도 다르다(달 표는 1차의 셋째 편 그대로 — 한 번도 안 나간 편)",
   not ({fingerprint(probe[k]) for k in ("total", "money", "digit")} & set(fps))
   and fingerprint(probe["months"]) == fingerprint(scenes["months"]))


def tiers_of(sc):
    return {r["animal"]: t["id"] for t in sc["tiers"] for r in t["items"]}


base = [tiers_of(probe["total"]), tiers_of(probe["money"])]
for e in S.EPISODES:
    if e["scene"] != "tier":
        continue
    tt = tiers_of(scenes[e["id"]])
    diff = min(sum(tt[a] != b[a] for a in FC.ANIMALS) for b in base + [tiers_of(scenes[x["id"]]) for x in S.EPISODES
                                                                         if x["scene"] == "tier" and x["id"] != e["id"]])
    ck(f"{e['id']}: 다른 등급표들과 4띠 이상 등급이 다르다 · 12띠 한 번씩 · 대길 1띠 이상 · 조심 4띠 이하",
       diff >= 4 and sorted(tt) == sorted(FC.ANIMALS) and list(tt.values()).count("S") >= 1 and list(tt.values()).count("C") <= 4,
       (diff, tt))
god_rows = {(g, b) for g, _, b, _ in NY.GOD.values()}
ck("끝자리 재물운 줄이 1차 끝자리 편(GOD)의 '좋은 기운·조심할 것' 짝과 겹치지 않는다",
   not ({(r["good"], r["bad"]) for r in S.d_money_rows()} & god_rows))
dig = {r["digit"]: r for r in NY.digit_rows()}
same = [r["year"] for e in S.EPISODES if e["family"] == "year" for r in S.year_rows(*e["years"])
        if (r["good_line"], r["bad_line"]) == (dig[r["year"] % 10]["good_line"], dig[r["year"] % 10]["bad_line"])]
ck("출생연도 줄 = 천간 × 띠 새 조합 — 1차 끝자리 줄을 그대로 옮긴 해가 없다", not same, same)
yrs = [r["year"] for e in S.EPISODES if e["family"] == "year" for r in S.year_rows(*e["years"])]
ck("출생연도 표 넷이 46~93년생을 겹치지 않게 나눈다", yrs == list(range(1946, 1994)))
for e in S.EPISODES:
    if e["scene"] == "gunghap" and not e.get("probe"):
        rows = scenes[e["id"]]["rows"]
        keys = [json.dumps([r.get("label") or r.get("animal"), r.get("sub")], ensure_ascii=False) for r in rows]
        n_good = len({r["good"] for r in rows})
        ok = len(set(keys)) == len(rows) and n_good >= 4 and len(rows) in (10, 12)
        if e["family"] in ("bmonth", "year"):
            ok = ok and len({fingerprint({"type": "x", "rows": [r]}) for r in rows}) == len(rows)
        ck(f"{e['id']}: {len(rows)}줄 · 줄 이름 겹침 없음 · 서로 다른 값 {n_good}가지", ok, (n_good, len(rows)))
for kind in ("money", "body", "trip"):
    rows = S.month_table(kind)
    ok = all(r["good"] and not (set(r["good"]) & set(r["bad"])) and len(r["good"]) <= 3 and len(r["bad"]) <= 3 for r in rows)
    ck(f"달 표 {kind}: 띠마다 좋은 달 1~3 · 조심 달 3 이하 · 서로 겹치지 않는다", ok)
mm = {r["animal"]: (r["good"], r["bad"]) for r in NY.month_rows()}
ck("돈 달·몸 달·나들이 달이 1차 '좋은 달·조심할 달'과 다른 달을 낸다(띠 열둘 중 여덟 이상)",
   all(sum((sorted(r["good"]), sorted(r["bad"])) != (sorted(m for m, _ in mm[r["animal"]][0]), sorted(m for m, _ in mm[r["animal"]][1]))
           for r in S.month_table(k)) >= 8 for k in ("money", "body", "trip")))

print("── 문구(어르신 눈높이 · 금지어 · 근거 기준) ──")
texts, screen, bad = [], [], []
for e in S.EPISODES:
    sb = S.storyboard(D(2026, 10, 27), e)
    sc = sb["scenes"][0]
    t, desc, nar = S.title(e), sb["platforms"]["youtube"]["description"], sc["narration"]
    texts += [t, desc, nar, sc["foot"], sc["title"], sc["pill"]]
    screen += [t, nar, json.dumps(sc, ensure_ascii=False)]
    if len(t) > 95 or len(nar) > 80:
        bad.append((e["id"], "제목 95·말 80", len(t), len(nar)))
    lines = ([r["line"] for x in sc["tiers"] for r in x["items"]] if sc["type"] == "tier"
             else [r[k] for r in sc["rows"] for k in ("good_line", "bad_line")])
    mains = [] if sc["type"] == "tier" else [r[k] for r in sc["rows"] for k in ("good", "bad")]
    if any(len(x) > 10 for x in lines) or any(len(x) > 11 for x in mains):
        bad.append((e["id"], "칸 글자", [x for x in lines if len(x) > 10], [x for x in mains if len(x) > 11]))
    if "재미로" not in desc or not ("이렇게 정했어요" in desc or "이렇게 봤어요" in desc or e.get("probe")):
        bad.append((e["id"], "설명란 근거·재미 고지"))
ck("제목 95자 · 말 80자 · 칸 한 줄 10자 · 설명란에 정한 방법과 '재미로'", not bad, bad[:4])
hits = sorted({w for w in BANNED for x in texts if w in x})
ck("금지어 없음('대박'·'투자'·'고혈압'·'부동산' …)", not hits, hits)
import sal_frame  # noqa: E402
sal = [v for x in texts for v in sal_frame.violations(x, unit="whole" if len(x) < 60 else "sentence")]
ck("살·삼재 낱말은 조언 틀 안에서만(sal_frame · 10/20 '삼재 조언형')", not sal, sal[:3])
jar = sorted({w for w in S.JARGON + ("에스급", "씨급") for x in screen if w in x})
ck("제목·말·화면에 영문 등급·십신·신살 이름이 없다(근거 용어는 설명란에만)", not jar, jar)
han = sorted({c for x in screen for c in x if "一" <= c <= "鿿"})
ck("제목·말·화면에 한자가 없다(어르신 · 배경 글자 규칙과 같은 결)", not han, han)
ck("제목마다 '정미년'(채널 맥박이 신년운세로 센다) · 제목이 서로 다르고 1차 묶음과도 다르다(달 표만 1차 편 그대로)",
   all("정미년" in S.title(e) for e in S.EPISODES) and len({S.title(e) for e in S.EPISODES}) == len(S.EPISODES)
   and {S.title(e) for e in S.EPISODES} & {NY.title(e) for e in NY.EPISODES} == {NY.title(NY.episode_by_id("months"))})
harsh = [x[:40] for x in screen + texts if re.search(r"최악|나쁜 띠|흉한|망하|재수 없|고집", x)]
ck("한 해를 깎아내리는 말·'고집' 같은 말이 없다 · 등급표 말은 '대길은 …띠' + 조언", not harsh and all(
   "대길은" in S.narration(e) and ("세요" in S.narration(e) or "좋아요" in S.narration(e)) for e in S.EPISODES if e["scene"] == "tier"))
want = {"tier": BB.SCREEN_DDI, "ddi": BB.SCREEN_DDI, "month": BB.SCREEN_DDI, "year": BB.SCREEN_DDI, "digit": BB.SCREEN_YEAR,
        "bmonth": BB.SCREEN_MONTH, "solar": BB.SCREEN_CAL_MONTH}
ck("기준 줄: 띠·출생연도 = 입춘(띠) · 끝자리 = 입춘(끝자리) · 태어난 달 = 음력 생일 달 · 절기 = 양력 절기 달",
   all(scenes[e["id"]]["basis"] == want[e["family"]] for e in S.EPISODES), {e["id"]: scenes[e["id"]]["basis"] for e in S.EPISODES})
ck("설명란 기준 안내: 띠·출생연도는 입춘 · 끝자리는 끝자리 입춘 · 태어난 달은 음력 생일 달",
   all("입춘" in S.description(e) for e in S.EPISODES if e["family"] in ("tier", "ddi", "month", "year", "digit"))
   and "음력 생일 달" in S.description(S.episode_by_id("b_month")))
ck("건강 편: 생활 습관 이야기 · '병원' 안내 · 의료 낱말 없음",
   "병원" in S.description(S.episode_by_id("r_health")) and "병원" in S.episode_by_id("r_health")["foot"])
ck("배경 묘사: 붉은 목도리 양 · 사람 없음 · 글자 금지 꼬리 · '새해·축제·lucky·달력·등불·매듭' 없음(중국 설 글자 방지)",
   all(e["hook"].startswith(S.LAMB) and e["hook"].endswith("no people") for e in S.EPISODES)
   and not any(w in e["hook"].lower() for e in S.EPISODES for w in ("new year", "festive", "lucky", "calendar", "lantern",
                                                                 "knot", "ornament", "text", "letter", "sign", "book", "paper money"))
   and S.storyboard(D(2026, 10, 27))["thumbnail_hook"].endswith(S.HOOK_TAIL))
ck("끝자리 말: 숫자 읽는 소리로 조사('2, 4, 5는' · '0, 4, 8은')",
   "2, 4, 5는" in S.narration(S.episode_by_id("d_money")) and "0, 4, 8은" in S.narration(S.episode_by_id("d_helper")))

print("── 화면(motion_short) ──")
for e in S.EPISODES:
    sc = dict(scenes[e["id"]], start=0.0, dur=9.0, clip=9.0)
    html = M.scene_html(0, sc, S.ACCENT)
    if sc["type"] == "tier":
        lay = M.tier_layout(sc["tiers"], M.TIER_BOTTOM - M.BASIS_H)
        ok = (html.count('class="tlab"') == 4 and lay["bottom"] <= 1446 and lay["fn"] >= 36 and lay["fl"] >= 22
              and ">대길<" in html and ">★★★★<" in html and "오늘은 없어요" not in html)
        ck(f"{e['id']}: 등급 4칸 · 아래 22% 비움 · 띠 36px·이유 22px 이상 · '오늘은 없어요' 안 씀", ok, (lay["bottom"], lay["fn"], lay["fl"]))
    else:
        lay = M.gunghap_layout(sc["rows"], M.GH_BOTTOM - M.BASIS_H)
        n = len(sc["rows"])
        ok = html.count('class="ghrow"') == n and lay["fa"] >= 32 and lay["fs"] >= 20 and 'class="basis"' in html
        ck(f"{e['id']}: {n}줄 · 이름 32px·작은 글자 20px 이상 · 기준 줄", ok, lay)
yh = M.scene_html(0, dict(scenes["y_58"], start=0.0, dur=9.0, clip=9.0), S.ACCENT)
ck("출생연도 표: 줄 이름 '62년생' · 밑 글자 '임인 · 호랑이띠'(년생이 두 번 안 나온다) · 머리글 '출생연도'",
   ">62년생<" in yh and ">임인 · 호랑이띠<" in yh and "62년생년생" not in yh and ">출생연도<" in yh)
bh = M.scene_html(0, dict(scenes["b_month"], start=0.0, dur=9.0, clip=9.0), S.ACCENT)
ck("태어난 달 표: '1월생' · '이른 봄' · 머리글 '음력 생일 달' · 빈 '년생' 없음", ">1월생<" in bh and ">이른 봄<" in bh
   and ">음력 생일 달<" in bh and ">년생<" not in bh)
tsc = dict(scenes["t_kids"], start=0.0, dur=9.0, clip=9.0)
tsc["tiers"] = [dict(t, items=[]) if t["id"] == "C" else t for t in tsc["tiers"]]
ck("빈 등급 칸은 '올해는 없어요'(신년)", "올해는 없어요" in M.scene_html(0, tsc, S.ACCENT))
old = M.scene_html(0, dict(T.storyboard(D(2026, 10, 13))["scenes"][0], start=0.0, dur=9.0, clip=9.0), T.ACCENT)
ck("일진 등급표는 그대로('오늘은 없어요' 기본값 · 띠 줄 '…년생')", "tlab" in old
   and ">쥐띠<" in M.scene_html(0, dict(NY.scene_for(NY.episode_by_id("months")), start=0.0, dur=9.0, clip=9.0), NY.ACCENT))

print("── 파이프라인 연결 ──")
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
proc = rp[rp.index("def process("):]
ck("run_pipeline: 시리즈가 등급표·매일 운세보다 먼저(장면·제목/설명) · 재생목록 신년운세 · 카피 점검 제외",
   proc.index("newyear_series.use_slot(sb)") < proc.index("tier_card.use_ab(sb)")
   and proc.count("newyear_series.use_slot(sb)") >= 3 and "newyear_series.apply(sb)" in proc and "newyear_series.meta(sb)" in proc
   and "(NEWYEAR_PLAYLIST, NEWYEAR_PLAYLIST_DESC) if newyear_series.use_slot(sb)" in proc
   and re.search(r"if newyear_series\.use_slot\(sb\):\n\s+# 시리즈 날 — 제목", proc) is not None)
fm = json.load(open(os.path.join(ROOT, "tools", "pulse_formats.json"), encoding="utf-8"))
rules = fm["channels"]["wb"]["rules"]


def cls(title, kst):
    t = dt.datetime.fromisoformat(kst).replace(tzinfo=PU.KST).astimezone(dt.timezone.utc)
    return PU.classify({"title": title, "pub": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "dur": 9}, rules)


miss = [(e["id"], cls(S.title(e) + " #shorts", f"{d.isoformat()}T06:14")) for d, eid in plan[:30] for e in [S.episode_by_id(eid)]]
ck("채널 맥박: 06시 시리즈 편은 전부 newyear_slot", all(k == "newyear_slot" for _, k in miss), [m for m in miss if m[1] != "newyear_slot"])
ck("채널 맥박: 08:13 신년운세 1차는 newyear · 시리즈 전 06시 정미년(없음)도 newyear",
   cls(NY.title(NY.EPISODES[1]) + " #shorts", "2026-10-15T08:17") == "newyear"
   and cls(NY.title(NY.EPISODES[0]) + " #shorts", "2026-10-26T06:14") == "newyear"
   and cls("오늘 띠별 운세 1위~12위 | 10월 28일 수요일 · 45~96년생 전부 #shorts", "2026-10-28T06:14") == "daily")
ex = {e["id"]: e for e in json.load(open(os.path.join(ROOT, "tools", "pulse_experiments.json"), encoding="utf-8"))["experiments"]}
ck("실험 달력: newyear-slot(10/27 시작 · 11/25 판정 · pulse) · 다른 실험 판정일은 그대로",
   ex.get("newyear-slot", {}).get("start") == "2026-10-27" and ex["newyear-slot"]["judge"] == "2026-11-25"
   and ex["tier-ab"]["judge"] == "2026-10-23" and ex["blessing"]["judge"] == "2026-10-25"
   and ex["newyear-probe"]["judge"] == "2026-10-26" and ex["gunghap-series"]["judge"] == "2026-10-30"
   and ex["lunar-digit"]["judge"] == "2026-11-02")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
