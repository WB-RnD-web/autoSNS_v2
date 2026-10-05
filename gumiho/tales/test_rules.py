#!/usr/bin/env python3
"""Nine Tails RULES 오프라인 테스트 — 편성·검사·메타·업로드 시각(+ ffmpeg 가 있으면 가짜 렌더 한 편)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules as RU  # noqa: E402
import tales as T  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


cat = RU.catalog()
rs = cat["rules"]
print("── 편성표 ──")
ck("번호가 1부터 빠짐없이", [r["n"] for r in rs] == list(range(1, len(rs) + 1)))
ck("slug 가 겹치지 않는다", len({r["slug"] for r in rs}) == len(rs))
ck("format 은 rules·versus·pov", all(r["format"] in RU.FORMATS for r in rs))
ck("look 은 tales.LOOKS", all(r["look"] in T.LOOKS for r in rs), [r["slug"] for r in rs if r["look"] not in T.LOOKS])
ck("facts 2개 이상(규칙은 여기서만)", all(len(r["facts"]) >= 2 for r in rs))
ck("제목 아이디어가 형식에 맞다(rules=규칙형·versus=vs·pov=POV:)",
   all((r["format"] != "rules" or RU.RULE_TITLE.match(r["title_idea"]))
       and (r["format"] != "versus" or RU.VS_TITLE.search(r["title_idea"]))
       and (r["format"] != "pov" or RU.POV_TITLE.match(r["title_idea"])) for r in rs),
   [r["title_idea"] for r in rs if r["format"] == "rules" and not RU.RULE_TITLE.match(r["title_idea"])])
wk = [r["format"] for r in rs[:7]]
ck("첫 주 = 규칙 5 · 대결 1 · POV 1", wk.count("rules") == 5 and wk.count("versus") == 1 and wk.count("pov") == 1, wk)
ck("같은 형식(대결·POV)이 이틀 연속 없다",
   all(not (a["format"] == b["format"] != "rules") for a, b in zip(rs, rs[1:])))
start = dt.date.fromisoformat(cat["start"])
ck("시작 전날은 쓰지 않는다", RU.assigned(start - dt.timedelta(days=1)) is None)
ck("시작일 = 1편", RU.assigned(start)["n"] == 1)
ck("마지막 날 = 마지막 편", RU.assigned(start + dt.timedelta(days=len(rs) - 1))["n"] == len(rs))
ck("목록이 바닥나면 쓰지 않는다(채워 넣을 때까지)", RU.assigned(start + dt.timedelta(days=len(rs))) is None)
ck("파일 경로", RU.file_for(rs[0]) == "output/tales_rules/R001_name-called-at-night.json")

print("── 대본 검사 ──")
ex_path = os.path.join(HERE, "rules_scripts", "R001_name-called-at-night.json")
with open(ex_path, encoding="utf-8") as f:
    S = json.load(f)
ck("모범 대본 통과", not RU.check(S), RU.check(S))


def errs_of(mut):
    s = copy.deepcopy(S)
    mut(s)
    return RU.check(s)


ck("catalog 에 없는 id 거부", any("rules_catalog" in e for e in errs_of(lambda s: s.update(id=999))))
ck("첫 줄 화면 글자 없으면 거부", any("첫 줄" in e for e in errs_of(lambda s: s["lines"][0].pop("text"))))
ck("규칙 번호가 차례가 아니면 거부", any("규칙 번호" in e for e in errs_of(lambda s: s["lines"][2].update(rule=7))))
ck("loop_back 없으면 거부", any("loop_back" in e for e in errs_of(lambda s: s.pop("loop_back"))))
ck("규칙형이 아닌 제목 거부", any("규칙형" in e for e in errs_of(lambda s: s.update(title="A Spooky Night #shorts"))))
ck("#shorts 없는 제목 거부", any("#shorts" in e for e in errs_of(lambda s: s.update(title="Never Answer at Night"))))
ck("그림에 구미를 그리면 거부", any("구미" in e for e in errs_of(lambda s: s["lines"][1].update(img="Gumi smiling in a hoodie"))))
ck("금지어 거부", any("금지어" in e for e in errs_of(lambda s: s["lines"][1].update(say="A gore scene appears."))))
ck("너무 길면 거부(35초 넘게)", any("단어" in e for e in errs_of(lambda s: [ln.update(say=ln["say"] + " and then it waited there in the dark for a long time")
                                                                   for ln in s["lines"]])))
ck("치비 리액션 이름 검사", any("gumi.react" in e for e in errs_of(lambda s: s["gumi"].update(react="cry"))))
ck("source 없으면 거부", any("source" in e for e in errs_of(lambda s: s.pop("source"))))
vs = copy.deepcopy(S)
vs.update(id=6, slug="dokkaebi-vs-kappa", format="versus", title="Dokkaebi vs Kappa: Who Wins? #shorts")
ck("versus 는 vote 필수", any("vote" in e for e in RU.check(vs)))
vs["vote"] = "Team Kappa or Team Dokkaebi?"
ck("versus 는 규칙 번호·loop_back 이 없어도 된다", not any("규칙 번호" in e or "loop_back" in e for e in RU.check(vs)), RU.check(vs))

print("── 메타·업로드 ──")
md = RU.meta(S, "https://www.youtube.com/@NineTailsTales")
ck("설명에 출처·AI 고지·13+", S["source"] in md["description"] and "AI-generated" in md["description"] and "13+" in md["description"])
ck("태그 15개 이하", len(md["tags"]) <= 15)
import upload_rule as UR  # noqa: E402
now = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.timezone.utc)
ck("예약: 같은 날 21:00 UTC", UR.publish_time(now) == "2026-10-14T21:00:00Z")
ck("예약: 1시간 안이면 다음 날", UR.publish_time(now.replace(hour=20, minute=30)) == "2026-10-15T21:00:00Z")
wf = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), ".github", "workflows", "tales-rules.yml"), encoding="utf-8").read()
ck("워크플로: routine/tales_rules 의 output/tales_rules 만 · 코드는 main", '"routine/tales_rules"' in wf
   and '"output/tales_rules/**"' in wf and "ref: main" in wf and "rules.py check" in wf)

print("── 렌더(가짜 그림·목소리) ──")
import render_rule as RR  # noqa: E402
assets_ok = all(os.path.exists(os.path.join(RR.ASSETS, f"chibi_{r}.png")) for r in RU.REACTS)
ck("치비 구미 4종이 있다", assets_ok)
ck("롱폼 구미: 10화부터 후드티, 그 전은 한복 그대로",
   all(RR.R.gumi_asset(p, {"id": 10}).endswith(f"gumi_{p}_hoodie.jpg") and RR.R.gumi_asset(p, {"id": 9}).endswith(f"gumi_{p}.jpg")
       for p in ("front", "wink", "bead")))
if shutil.which("ffmpeg") or os.path.exists(r"C:\wbtmp\ffbin\ffmpeg.exe"):
    tmp = tempfile.mkdtemp()
    try:
        m = RR.render(ex_path, out_dir=os.path.join(tmp, "out"), work=os.path.join(tmp, "work"), mock=True)
        ck("가짜 렌더: 영상·첫 프레임·메타", os.path.exists(m["video"]) and os.path.exists(m["first"]) and m["mock"])
        ck("가짜 렌더: 40초 이하", m["sec"] <= RR.MAX_SEC, m["sec"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
else:
    print("  (ffmpeg 없음 — 렌더 테스트 건너뜀)")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
