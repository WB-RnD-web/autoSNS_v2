#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""콘텐츠 재고(runway) 오프라인 테스트 — 줄기 목록 · 각 모듈 편성 함수와 같은 날짜 · 경고 · 출력.

    python tools/test_runway.py

★catalog 를 채우면 마지막 날이 바뀐다 — 그래서 날짜를 못 박지 않고 각 모듈의 함수와 맞춰 본다(코드 상수인 것만 못 박는다).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runway as RW  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


D = lambda m, d, y=2026: dt.date(y, m, d)  # noqa: E731
TODAY = D(10, 25)
rows = RW.collect(TODAY)
by = {r["id"]: r for r in rows}

print("── 줄기 목록 ──")
WANT = {"wb_daily", "wb_theme", "wb_name", "wb_pulli", "wb_gunghap", "wb_newyear_card", "wb_newyear_series", "wb_lf27",
        "wb_weekly_lf", "nt_shorts", "nt_longform", "nt_sleep", "insta_pick", "insta_sci", "insta_teardown", "insta_bm"}
ck("세 채널 줄기 전부(왕별이 9 · Nine Tails 3 · 인스타 4) · 확인 실패 없음", set(by) == WANT
   and not any(r["limit"] == "error" for r in rows), sorted(set(by) ^ WANT) or [r["note"] for r in rows if r["limit"] == "error"])
ck("한계 종류는 다섯 중 하나 · 채널 이름", all(r["limit"] in RW.LIMITS for r in rows) and all(r["ch"] in RW.CHANNELS for r in rows))
ck("끝없음: 매일 운세·띠 테마·내 것 찾기·풀이형·골라보기 (마지막 날·남은 날 없음)",
   all(by[k]["limit"] == "open" and by[k]["last"] is None and by[k]["days_left"] is None
       for k in ("wb_daily", "wb_theme", "wb_name", "wb_pulli", "insta_pick")))

print("── 각 모듈 편성 함수와 같은 날짜(다시 계산하지 않는다) ──")
import gunghap_card as G  # noqa: E402
import longform_2027 as L  # noqa: E402
import newyear_card as NC  # noqa: E402
import newyear_series as NS  # noqa: E402
import pick_plan as P  # noqa: E402
import rules as R  # noqa: E402
import tales as T  # noqa: E402
import weekly_fortune as W  # noqa: E402

g = by["wb_gunghap"]
ck("띠 궁합표: 마지막 = gunghap_card.last_day() — 편성일이고 그 뒤로는 편성일이 없다 · 남은 편 = 편성일 수",
   g["last"] == G.last_day() and G.is_post_day(g["last"]) and not any(G.is_post_day(g["last"] + dt.timedelta(days=k)) for k in range(1, 60))
   and g["left"] == sum(G.is_post_day(TODAY + dt.timedelta(days=k)) for k in range(60)), g)
ck("띠 궁합표 접음(GUNGHAP_STOPPED)이면 꺼짐 · 끝 사유 · 재고 경고에 안 뜬다",
   not RW.GUNGHAP_STOPPED or (g["limit"] == "off" and g["ended"] == RW.GUNGHAP_STOPPED and g["days_left"] is None
                              and "wb_gunghap" not in {r["id"] for r in RW.low(rows)}), g)
ns = by["wb_newyear_series"]
ck("신년운세 시리즈: 마지막 = newyear_series.last_day() · 남은 편 = schedule 의 오늘 이후", ns["last"] == NS.last_day()
   and ns["left"] == sum(d >= TODAY for d, _ in NS.schedule(D(12, 31, 2027))), ns)
ck("깊이 보기 롱폼: 16편 · 마지막 12/07(코드 상수) = longform_2027.EPISODES 끝", by["wb_lf27"]["last"] == L.last_day() == D(12, 7)
   and by["wb_lf27"]["left"] == 16 and len(L.EPISODES) == 16)
ck("주간 롱폼: STOP_FROM 앞 주 월요일의 전날(10/25 일) · 일부러 끝냄(대체 표시)", by["wb_weekly_lf"]["last"] == W.last_day() == D(10, 25)
   and by["wb_weekly_lf"]["ended"] and W.publish_at(D(10, 26), now=dt.datetime(2026, 10, 1, tzinfo=RW.KST)).startswith("2026-10-24T23:00"))
ck("신년운세 1차 묶음: newyear_card.last_day() · 끝(대체)", by["wb_newyear_card"]["last"] == NC.last_day() and by["wb_newyear_card"]["ended"])
sc = R.shorts()
nt = by["nt_shorts"]
ck("영어 쇼츠: 시험(쉬는 중이면 꺼짐) · 마지막 = rules.publish_date(형식마다 끝 편)의 가장 늦은 날 · 판정 = shorts_catalog judge",
   nt["limit"] == ("off" if RW.NT_PAUSED else "trial") and nt["last"] == max(R.publish_date(sc[f][-1], sc) for f in R.NEW_FORMATS)
   and nt["judge"] == dt.date.fromisoformat(sc["judge"]), nt)
ck("해설 롱폼: 마지막 = tales.last_date() · 남은 편 = 그 뒤 편성된 편", by["nt_longform"]["last"] == T.last_date()
   and by["nt_longform"]["left"] == sum(1 for e in T.load(T.CATALOG)["tales"]
                                        if e.get("date") and not e.get("retired") and e["date"] >= TODAY.isoformat()))
ck("Nine Tails 쉬는 중(NT_PAUSED)이면 쇼츠·롱폼은 꺼짐 · 끝 사유 표시 · 재고 경고에 안 뜬다",
   not RW.NT_PAUSED or (all(by[i]["limit"] == "off" and by[i]["ended"] == RW.NT_PAUSED and by[i]["days_left"] is None
                            for i in ("nt_shorts", "nt_longform"))
                        and not {"nt_shorts", "nt_longform"} & {r["id"] for r in RW.low(rows)}))
ck("수면판: sleep.ENABLED 를 실행 없이 읽는다(렌더러를 안 끌고 온다) · 꺼짐이면 경고 안 함",
   (by["nt_sleep"]["limit"] == "off") == (RW._const(os.path.join(RW.ROOT, "gumiho", "tales", "sleep.py"), "ENABLED") is False)
   and "render_tale" not in sys.modules)
pr = {r["id"]: r for r in P.runway(TODAY)}
ck("인스타: pick_plan.runway 그대로(sci · 뜯어보기 · 병맛 · 골라보기)", all(
    (by[k]["last"], by[k]["left"], by[k]["limit"]) == (pr[k]["last"], pr[k]["left"], pr[k]["limit"]) for k in pr))
ck("병맛 시험: 마지막 BM_TO(11/07) · 판정 11/08 · 남은 날 13", (by["insta_bm"]["last"], by["insta_bm"]["judge"], by["insta_bm"]["days_left"])
   == (P.BM_TO, D(11, 8), 13))

print("── 남은 날·경고 ──")
ck("남은 날 = 마지막 날 - 오늘(지났으면 0) · 끝없음·꺼짐은 None", all(
    r["days_left"] is None if r["limit"] in ("open", "off") else r["days_left"] == (max(0, (r["last"] - TODAY).days) if r["last"] else 0)
    for r in rows))
lw = RW.low(rows)
ck("경고 = 14일 안 · 일부러 끝낸 것(1차 묶음·주간 롱폼·수면판)·끝없음은 빼고", all(r["days_left"] < 14 and not r["ended"] for r in lw)
   and not {"wb_newyear_card", "wb_weekly_lf", "nt_sleep", "wb_daily", "insta_pick"} & {r["id"] for r in lw})
ck("10/25: 바닥이 가까운 줄기를 잡는다(병맛 시험 13일 · 깊이 보기 43일은 아님)", "insta_bm" in {r["id"] for r in lw}
   and "wb_lf27" not in {r["id"] for r in lw}, [r["id"] for r in lw])
far = {r["id"]: r for r in RW.collect(D(3, 1, 2027))}
ck("2027-03-01: 깊이 보기·신년 시리즈는 끝(0일) → 경고 · 매일 운세는 그대로 끝없음",
   far["wb_lf27"]["days_left"] == 0 and far["wb_newyear_series"]["days_left"] == 0
   and {"wb_lf27", "wb_newyear_series"} <= {r["id"] for r in RW.low(list(far.values()))} and far["wb_daily"]["days_left"] is None)
ck("--warn 을 바꾸면 경고 범위가 바뀐다(60일 → 깊이 보기도)", "wb_lf27" in {r["id"] for r in RW.low(rows, 60)})

print("── 채우기(REFILL.md · refill_check) ──")
ck("채울 수 있는 줄기 = NT 쇼츠·NT 해설 롱폼·띠 궁합표·깊이 보기·인스타 sci·뜯어보기 · refill_doc = REFILL.md#<id>",
   {r["id"] for r in rows if r["refillable"]} == set(RW.REFILLABLE) == {"nt_shorts", "nt_longform", "wb_gunghap", "wb_lf27",
                                                                         "insta_sci", "insta_teardown"}
   and all(r["refill_doc"] == f"tools/REFILL.md#{r['id']}" for r in rows if r["refillable"])
   and all(r["refill_doc"] is None for r in rows if not r["refillable"]))
doc = open(os.path.join(RW.ROOT, "tools", "REFILL.md"), encoding="utf-8").read()
ck("REFILL.md: 줄기마다 앵커(<a id=…>) · 파일 · 배치 크기(28·2·6·12·14·10)",
   all(f'<a id="{i}"></a>' in doc for i in RW.REFILLABLE)
   and all(f in doc for f in ("gumiho/tales/shorts_catalog.json", "gumiho/tales/catalog.json", "pipeline/gunghap_card.py",
                              "pipeline/longform_2027_more.json", "insta/sci_extra.json", "insta/teardown_catalog.json"))
   and all(re.search(rf"\| `{i}` \|[^\n]*\| {n}", doc) for i, n in (("nt_shorts", "28편"), ("nt_longform", "2편"),
                                                                     ("wb_gunghap", "6묶음"), ("wb_lf27", "12편"),
                                                                     ("insta_sci", "14편"), ("insta_teardown", "10편"))))
ck("REFILL.md: from(다음 날·바닥났으면 내일) · 사실 규칙(evidence·기관 출처·상표 X) · 검사·전체 테스트 · 브랜치·PR · 하지 말 것",
   all(w in doc for w in ("from", "다음 날", "내일", "evidence", "기관", "상표", "python tools/refill_check.py",
                          "bash tools/run_tests.sh", "refill/<줄기 id>-<YYYYMMDD>", "시험 중인 줄기(NT 쇼츠·bm)는 판정이 '계속'일 때만 머지",
                          "routine/*", ".github/", "유료", "끝에만")))
ck("REFILL.md 가 가리키는 쓰는 법 문서가 다 있다", all(os.path.exists(os.path.join(RW.ROOT, p)) for p in re.findall(
    r"`((?:gumiho/tales|insta|pipeline)/[A-Z_0-9]+\.md)`", doc)) and len(re.findall(r"`((?:gumiho/tales|insta|pipeline)/[A-Z_0-9]+\.md)`", doc)) >= 4)

print("── 출력(글·JSON) · 한 줄기가 깨져도 ──")
txt = RW.text(rows, TODAY)
ck("글: 날짜(KST)·세 채널·경고 표시·채우는 곳", "2026-10-25(일) KST" in txt and all(f"[{c}]" in txt for c in RW.CHANNELS)
   and "⚠️" in txt and "채우기:" in txt and "insta/sci_extra.json" in txt)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = RW.main(["--date", "2026-10-25", "--json"])
js = json.loads(buf.getvalue())
ck("--json: 날짜·줄기·경고 id · 날짜는 문자열 · 채우기(refillable·refill_doc)", rc == 0 and js["date"] == "2026-10-25"
   and {s["id"] for s in js["streams"]} == WANT and all("refillable" in s and "refill_doc" in s for s in js["streams"])
   and set(js["low"]) == {r["id"] for r in lw} and all(s["last"] is None or isinstance(s["last"], str) for s in js["streams"]))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    RW.main(["--date", "2026-11-20"])
ck("--date 로 기준일을 바꾼다", "2026-11-20(금) KST" in buf.getvalue())
saved = RW.SOURCES


def boom(_today):
    raise RuntimeError("catalog 가 깨졌다")


RW.SOURCES = (("왕별이", boom),) + saved[1:]
broken = RW.collect(TODAY)
RW.SOURCES = saved
ck("한 모듈이 깨져도 나머지는 낸다(그 줄기는 '확인 실패' · 맥박이 멈추지 않는다)",
   any(r["limit"] == "error" and "깨졌다" in r["note"] for r in broken) and {"nt_shorts", "insta_sci"} <= {r["id"] for r in broken}
   and "확인 실패" in RW.line(next(r for r in broken if r["limit"] == "error")))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
