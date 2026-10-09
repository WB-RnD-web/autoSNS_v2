#!/usr/bin/env python3
"""Nine Tails 쇼츠 오프라인 테스트 — 편성(옛 RULES 종료 + 새 라인업 A 매일·B 격일) · 검사 · 메타 · 업로드 시각 ·
워크플로 · 렌더 프레임(형식마다 0초·가운데·끝) + ffmpeg 가 있으면 가짜 렌더."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import rules as RU  # noqa: E402
import tales as T  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


D = dt.date
cat = RU.catalog()
rs = cat["rules"]
print("── 옛 규칙괴담 편성(10/9 배정분까지) ──")
ck("번호가 1부터 빠짐없이", [r["n"] for r in rs] == list(range(1, len(rs) + 1)))
ck("slug 가 겹치지 않는다", len({r["slug"] for r in rs}) == len(rs))
ck("format 은 rules·versus·pov", all(r["format"] in RU.OLD_FORMATS for r in rs))
ck("look 은 tales.LOOKS", all(r["look"] in T.LOOKS for r in rs), [r["slug"] for r in rs if r["look"] not in T.LOOKS])
start = D.fromisoformat(cat["start"])
ck("시작 전날은 쓰지 않는다", RU.assigned(start - dt.timedelta(days=1)) is None)
ck("시작일 = 1편", RU.assigned(start)["n"] == 1)
ck("until = 2026-10-09(사용자 10/9: 설화 금지)", cat["until"] == "2026-10-09")
ck("10/9 = 마지막 옛 편(2편)", RU.assigned(D(2026, 10, 9))["n"] == 2)
ck("10/10부터 옛 목록은 하나도 배정되지 않는다",
   all(RU.assigned(D(2026, 10, 10) + dt.timedelta(days=k)) is None for k in range(0, 40)))
ck("10/10–10/12 에 옛 RULES 편이 없다",
   all(e["format"] not in RU.OLD_FORMATS for d in (10, 11, 12) for e in RU.on_date(D(2026, 10, d))))
ck("10/10·10/11 은 빈 날(새 시험은 10/13 공개부터)", RU.on_date(D(2026, 10, 10)) == [] and RU.on_date(D(2026, 10, 11)) == [])
ck("파일 경로", RU.file_for(rs[0]) == "output/tales_rules/R001_name-called-at-night.json")
ck("배정일 역산(day_of) = assigned 의 역", all(RU.assigned(RU.day_of(n))["n"] == n for n in (1, 2)))

print("── 새 라인업 catalog(shorts_catalog.json) ──")
sc = RU.shorts()
sv, cp, lm = sc["survival"], sc["compare"], sc["liminal"]
ck("A survival 14 · B compare 7 · liminal 7", (len(sv), len(cp), len(lm)) == (14, 7, 7), (len(sv), len(cp), len(lm)))
allx = sv + cp + lm
ck("id 가 겹치지 않고 옛 id(≤100)와도 안 겹친다", len({e["n"] for e in allx}) == 28 and min(e["n"] for e in allx) > 100)
ck("slug 가 겹치지 않는다(옛 목록 포함)", len({e["slug"] for e in allx} | {r["slug"] for r in rs}) == 28 + len(rs))
ck("format 이 시리즈와 같다", all(e["format"] == f for f in RU.NEW_FORMATS for e in sc[f]))
ck("Pt 번호가 시리즈마다 1부터 차례로", all([e["part"] for e in sc[f]] == list(range(1, len(sc[f]) + 1)) for f in RU.NEW_FORMATS))
ck("look 은 rules.LOOKS", all(e["look"] in RU.LOOKS for e in allx))
fact_es = sv + cp
ck("survival·compare: facts 3개 이상, fact 마다 src", all(len(e["facts"]) >= 3 and all(isinstance(f.get("src"), int)
   and 0 <= f["src"] < len(e["sources"]) for f in e["facts"]) for e in fact_es),
   [e["slug"] for e in fact_es if len(e["facts"]) < 3])
ck("출처는 https 이고 믿을 만한 곳(NASA·NOAA·USGS·Britannica·학술지…)",
   all(u.startswith("https://") and RU.REPUTABLE.search(u) for e in fact_es for u in e["sources"]),
   [u for e in fact_es for u in e["sources"] if not RU.REPUTABLE.search(u)])
ck("편마다 숫자 있는 fact 3개 이상", all(sum(bool(RU.nums(f["fact"])) for f in e["facts"]) >= 3 for e in fact_es),
   [e["slug"] for e in fact_es if sum(bool(RU.nums(f["fact"])) for f in e["facts"]) < 3])
ck("편마다 자기 숫자(다른 편과 숫자 묶음이 같지 않다)",
   len({frozenset().union(*[RU.nums(f["fact"]) for f in e["facts"]]) for e in fact_es}) == len(fact_es))
ck("편마다 자기 출처(출처 목록이 같은 편이 없다)", len({tuple(sorted(e["sources"])) for e in fact_es}) == len(fact_es))
ck("catalog 에 금지 주제가 없다(설화·한국·실존 피해자·프랜차이즈·SCP·Backrooms)",
   not [e["slug"] for e in allx if RU.BANNED_TOPICS.search(json.dumps(e, ensure_ascii=False).replace("nine tails tales", ""))],
   [e["slug"] for e in allx if RU.BANNED_TOPICS.search(json.dumps(e, ensure_ascii=False))])
ck("survival 제목 아이디어 = 'How Long Would You Last…'", all(RU.SURVIVAL_TITLE.match(e["title_idea"]) for e in sv))
ck("compare 제목 아이디어에 Ranked/by Size", all(RU.COMPARE_TITLE.search(e["title_idea"]) for e in cp))
ck("liminal 제목 아이디어에 Rules/Theory", all(RU.LIMINAL_TITLE.search(e["title_idea"]) for e in lm))
ck("survival: situation ≤36자 · odds_idea", all(len(e["situation"]) <= RU.SITUATION_MAX and RU.ODDS.match(e["odds_idea"]) for e in sv))
ck("survival·compare: 예고용 teaser(짧은 이름)", all(e.get("teaser") and len(e["teaser"]) <= 22 for e in fact_es))
ck("liminal: premise·setting·seeds·twist_idea", all(e.get("premise") and e.get("setting") and len(e.get("seeds", [])) >= 4
                                                   and e.get("twist_idea") for e in lm))

print("── 편성: A 매일 20:00 · B 격일 23:30(compare ↔ liminal) · 공개 전날 쓴다 ──")
p0 = D(2026, 10, 13)
ck("첫 공개일 10/13 · 쓰는 날 = 공개 전날", sc["first_publish"] == "2026-10-13" and sc.get("write_ahead_days") == 1)
days = [p0 + dt.timedelta(days=k) for k in range(14)]
ok_sched, seen = True, []
for k, pd in enumerate(days):
    es = RU.on_date(pd - dt.timedelta(days=1))
    fm = [e["format"] for e in es]
    want_b = "compare" if k % 2 == 0 else "liminal"
    ats = [e["publish_at"] for e in es]
    good = (fm == ["survival", want_b] and ats == [f"{pd}T20:00:00Z", f"{pd}T23:30:00Z"]
            and [e["slot"] for e in es] == ["A", "B"])
    if not good:
        ok_sched = False
        print("     ", pd, fm, ats)
    seen += [e["n"] for e in es]
ck("10/13–10/26 공개: 날마다 A survival + B(짝수 날 compare · 홀수 날 liminal), 20:00 · 23:30 UTC", ok_sched)
ck("28편이 한 번씩 다 쓰인다", sorted(seen) == sorted(e["n"] for e in allx))
ck("파일 이름이 편마다 다르다", len({RU.file_for(e) for e in allx}) == 28)
ck("10/12(쓰는 날) = 10/13 공개 Pt.1 둘", [(e["format"], e["part"]) for e in RU.on_date(D(2026, 10, 12))]
   == [("survival", 1), ("compare", 1)])
ck("10/26부터(목록 끝) 쓰지 않는다 — 판정 10/27 뒤 채운다", RU.on_date(D(2026, 10, 26)) == [] and RU.on_date(D(2026, 11, 1)) == [])
first_lim = RU.on_date(D(2026, 10, 13))
ck("10/13(쓰는 날) = Pt.2 survival + liminal Pt.1", [(e["format"], e["part"]) for e in first_lim] == [("survival", 2), ("liminal", 1)])
ck("teaser_idea: 매일(A)은 TOMORROW, 격일(B)은 요일, liminal·마지막 편은 없음",
   RU.teaser_idea(sv[0], sc).startswith("PT.2 TOMORROW: ") and RU.teaser_idea(cp[0], sc).startswith("PT.2 THURSDAY: ")
   and RU.teaser_idea(lm[0], sc) is None and RU.teaser_idea(sv[-1], sc) is None and RU.teaser_idea(cp[-1], sc) is None,
   (RU.teaser_idea(sv[0], sc), RU.teaser_idea(cp[0], sc)))
out = subprocess.run([sys.executable, os.path.join(HERE, "rules.py"), "next", "--date", "2026-10-12"], capture_output=True,
                     text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
nx = json.loads(out.stdout)
ck("rules.py next: entries 전부(편마다 file·format·publish_at)", nx["count"] == 2 and all(
   e["file"].startswith("output/tales_rules/R") and e["format"] and e["publish_at"] for e in nx["entries"]), out.stdout[:200])
out2 = subprocess.run([sys.executable, os.path.join(HERE, "rules.py"), "next", "--date", "2026-10-10"], capture_output=True,
                      text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
ck("rules.py next 빈 날: none + entries []", json.loads(out2.stdout).get("none") is True and json.loads(out2.stdout)["entries"] == [])

print("── 대본 검사: 모범 대본 ──")
SC = os.path.join(HERE, "rules_scripts")


def load(name):
    with open(os.path.join(SC, name), encoding="utf-8") as f:
        return json.load(f)


S = load("R001_name-called-at-night.json")
A = load("R101_mariana-trench-floor.json")
B1 = load("R201_deep-sea-creatures-by-size.json")
B2 = load("R301_empty-mall-3am.json")
for nm, x in (("옛 rules R001", S), ("survival R101", A), ("compare R201", B1), ("liminal R301", B2)):
    ck(f"모범 대본 통과 — {nm}", not RU.check(x), RU.check(x))
ck("모범 대본끼리 그림 프롬프트가 안 겹친다", not RU.check(A, others=[B1, B2, S]) and not RU.check(B1, others=[A, B2]))


def errs_of(base, mut, others=None):
    s = copy.deepcopy(base)
    mut(s)
    return RU.check(s, others=others)


def has(errs, word):
    return any(word in e for e in errs)


print("── 대본 검사: 옛 형식(그대로) ──")
ck("catalog 에 없는 id 거부", has(errs_of(S, lambda s: s.update(id=999)), "catalog"))
ck("첫 줄 화면 글자 없으면 거부", has(errs_of(S, lambda s: s["lines"][0].pop("text")), "첫 줄"))
ck("규칙 번호가 차례가 아니면 거부", has(errs_of(S, lambda s: s["lines"][2].update(rule=7)), "규칙 번호"))
ck("loop_back 없으면 거부", has(errs_of(S, lambda s: s.pop("loop_back")), "loop_back"))
ck("source 없으면 거부", has(errs_of(S, lambda s: s.pop("source")), "source"))

print("── 대본 검사: 출처·숫자(새 형식) ──")
ck("숫자가 있는데 sources 가 없으면 거부", has(errs_of(A, lambda s: s.update(sources=[])), "sources 가 비었다"))
ck("줄에 src 가 없으면 거부", has(errs_of(A, lambda s: s["beats"][1].pop("src")), "src"))
ck("src 번호가 sources 밖이면 거부", has(errs_of(A, lambda s: s["beats"][1].update(src=99)), "src"))
ck("catalog 에 없는 출처 URL 거부(지어낸 URL)", has(errs_of(A, lambda s: s["sources"].append("https://example.com/x")), "catalog 출처"))
ck("catalog facts 에 없는 숫자 거부", has(errs_of(A, lambda s: s["beats"][2].update(text="9,999 BAR")), "facts 에 없다"))
ck("compare: 값 글자도 facts 에서만", has(errs_of(B1, lambda s: s["items"][0].update(label="77 CM")), "facts 에 없다"))
ck("liminal: 사실처럼 보이는 숫자(단위·%) 거부", has(errs_of(B2, lambda s: s["lines"][1].update(say="Rule two. 87% of people never leave.")), "숫자"))
ck("liminal: 3 A.M.·RULE 번호는 괜찮다", not errs_of(B2, lambda s: s["lines"][1].update(say="Rule two. At 3 A.M. the music plays. If it stops, freeze until it starts again.")))

print("── 대본 검사: 금지 주제·구미·그림 ──")
for word, mut in (("korea", lambda s: s["beats"][0].update(say="In Korea the sea is deep.")),
                  ("joseon", lambda s: s.update(description_hook="A Joseon-era tale of the sea.")),
                  ("gumiho", lambda s: s["tags"].append("gumiho")),
                  ("folklore", lambda s: s["beats"][1].update(say="Old folklore says the trench is cursed.")),
                  ("Backrooms", lambda s: s["beats"][1].update(img="the backrooms yellow hallway")),
                  ("SCP", lambda s: s.update(title="How Long Would You Last in SCP-173's Cell? Pt.1 #shorts")),
                  ("victims", lambda s: s["beats"][1].update(say="Real victims felt this pressure.")),
                  ("franchise", lambda s: s["beats"][1].update(say="Just like in Interstellar.")),
                  ("Titanic", lambda s: s["beats"][1].update(img="the wreck of the Titanic on the sea floor"))):
    ck(f"금지 주제 거부 — {word}", has(errs_of(A, mut), "금지 주제"), errs_of(A, mut)[:2])
ck("새 형식도 욕설·날짜 타는 말 거부", has(errs_of(A, lambda s: s["beats"][1].update(say="A gore scene, right now.")), "금지어")
   and has(errs_of(A, lambda s: s["beats"][1].update(say="It is dark right now down here at 1,000 meters.")), "날짜"))
ck("그림에 구미 거부", has(errs_of(A, lambda s: s["beats"][1].update(img="Gumi floating in the deep sea")), "구미"))
ck("그림에 여우 거부", has(errs_of(B1, lambda s: s["items"][1].update(img="a red fox swimming underwater")), "여우"))
ck("그림 프롬프트에 글자 거부", has(errs_of(A, lambda s: s["beats"][1].update(img="a sign with text that says DANGER")), "글자"))
ck("같은 편 안에서 그림 재사용 거부", has(errs_of(A, lambda s: s["beats"][2].update(img=s["beats"][1]["img"])), "두 번"))
other = copy.deepcopy(B1)
other["items"][0]["img"] = A["beats"][1]["img"]
ck("다른 편과 같은 그림 프롬프트 거부(재사용 금지)", has(RU.check(A, others=[other]), "다른 편"))
ck("siblings(): 같은 폴더의 다른 대본을 읽는다", {x["id"] for x in RU.siblings(os.path.join(SC, "R101_mariana-trench-floor.json"))}
   >= {1, 201, 301})

print("── 대본 검사: survival ──")
ck("situation 없으면 거부", has(errs_of(A, lambda s: s.pop("situation")), "situation"))
ck("첫 박자가 0:00 이 아니면 거부", has(errs_of(A, lambda s: s["beats"][0].update(t="0:05")), "0:00"))
ck("시계가 뒤로 가면 거부", has(errs_of(A, lambda s: (s["beats"][2].update(t="HOURS"), s["beats"][3].update(t="INSTANT"))), "앞으로만"))
# 2026-10-10 검수: 마리아나 편 시계가 출처 없는 1:00 에서 멈췄다 → 시각은 facts 의 '수 + 단위'에서만, 없으면 낱말
ck("출처 없는 생존 시각 거부(지어낸 1:00)", has(errs_of(A, lambda s: s["beats"][3].update(t="1:00")), "지어내지"))
ck("출처 없는 생존 시각 거부(지어낸 0:12)", has(errs_of(A, lambda s: s["beats"][3].update(t="0:12")), "지어내지"))
ck("낱말 시각(INSTANT·SECONDS·MINUTES)은 된다", not errs_of(A, lambda s: s["beats"][3].update(t="SECONDS")))
ck("clock_backed: facts 의 '수 + 단위'와 맞을 때만",
   RU.clock_backed("0:12", ["about 9-12 seconds of useful consciousness"]) and RU.clock_backed("5:00", ["frostbite in 5 minutes"])
   and RU.clock_backed("3:00:13", ["about 3 hours", "just 12.8 seconds later"]) and RU.clock_backed("23:30:00", ["a day lasted 23.5 hours"])
   and RU.clock_backed("DAY 3", ["in as little as 3 days"]) and RU.clock_backed("1:30", ["1-1.5 minutes after"])
   and not RU.clock_backed("1:00", ["2.4 °C water", "1 atmosphere every 10.06 meters"])
   and not RU.clock_backed("1:20:00", ["1 hour and 10 minutes"]) and RU.clock_backed("0:00", []))
_bad = []
for e in sv:
    _prev = -1
    for b in e.get("beat_ideas", []):
        if b["t"] == "GUMI":
            continue
        _lb = RU.clock_lb(b["t"])
        if _lb is None or not (RU.clock_word(b["t"]) or RU.clock_backed(b["t"], [f["fact"] for f in e["facts"]])) or _lb < _prev:
            _bad.append((e["slug"], b["t"]))
        _prev = _lb if _lb is not None else _prev
ck("catalog survival 14편: beat_ideas 시각이 전부 facts 에 기대거나 낱말·앞으로만", not _bad and all(e["beat_ideas"][0]["t"] == "0:00" for e in sv), _bad)
ck("시계 꼴이 틀리면 거부", has(errs_of(A, lambda s: s["beats"][1].update(t="soon")), "꼴"))
ck("박자 3개면 거부(4–6)", has(errs_of(A, lambda s: s.update(beats=s["beats"][:3])), "beats"))
ck("odds 없으면 거부", has(errs_of(A, lambda s: s["gumi"].pop("odds")), "odds"))
ck("제목에 Pt.N 없으면 거부", has(errs_of(A, lambda s: s.update(title="How Long Would You Last in the Mariana Trench? #shorts")), "Pt."))
ck("제목이 How Long Would You Last 가 아니면 거부", has(errs_of(A, lambda s: s.update(title="The Mariana Trench Pt.1 #shorts")), "How Long"))
ck("teaser 는 다음 Pt", has(errs_of(A, lambda s: s.update(teaser="PT.5 TOMORROW: MARS")), "teaser"))
ck("clock_sec: 0:10 · 1:00:00 · DAY 3", (RU.clock_sec("0:10"), RU.clock_sec("1:00:00"), RU.clock_sec("DAY 3")) == (10, 3600, 259200))

print("── 대본 검사: compare · liminal ──")
ck("compare: 작은 것 → 큰 것 순서가 아니면 거부", has(errs_of(B1, lambda s: s["items"].insert(0, s["items"].pop(2))), "오름차순"))
ck("compare: 마지막 twist 없으면 거부", has(errs_of(B1, lambda s: s["items"][-1].pop("twist")), "twist"))
ck("compare: scale 없으면 거부", has(errs_of(B1, lambda s: s.pop("scale")), "scale"))
ck("compare: 제목에 Ranked/by Size", has(errs_of(B1, lambda s: s.update(title="Deep Sea Creatures Pt.1 #shorts")), "Ranked"))
ck("liminal: fiction 표시 필수", has(errs_of(B2, lambda s: s.pop("fiction")), "fiction"))
ck("liminal: loop_back 필수", has(errs_of(B2, lambda s: s.pop("loop_back")), "loop_back"))
ck("liminal: teaser 금지(루프가 끊긴다)", has(errs_of(B2, lambda s: s.update(teaser="PT.2 SUNDAY: GAS STATION")), "teaser"))

print("── 메타·업로드 ──")
import upload_rule as UR  # noqa: E402
import upload_tale as UT  # noqa: E402
ch = "https://www.youtube.com/@NineTailsTales"
md = RU.meta(A, ch)
ck("설명에 출처 전부 · AI 고지 · 시리즈", all(u in md["description"] for u in A["sources"]) and "AI-generated" in md["description"]
   and "How Long Would You Last?" in md["description"])
ck("새 형식 메타에 설화 태그가 없다", not any("folklore" in t for t in md["tags"]) and "folklore" not in md["description"])
ck("liminal 설명은 FICTION 고지", "FICTION" in RU.meta(B2, ch)["description"])
ck("태그 15개 이하", all(len(RU.meta(x, ch)["tags"]) <= 15 for x in (A, B1, B2, S)))
ck("재생목록: How Long Would You Last? · Ranked by Size · Liminal Rules",
   [RU.playlist_for(x)[0] for x in (A, B1, B2)] == ["How Long Would You Last?", "Ranked by Size", "Liminal Rules"]
   and RU.playlist_for(S) is None)
st = UT.status_body("private", "2026-10-13T20:00:00Z")
ck("업로드: containsSyntheticMedia=true(실사) · madeForKids=false · 예약은 private",
   st.get("containsSyntheticMedia") is True and st["selfDeclaredMadeForKids"] is False and st["privacyStatus"] == "private")
up = dt.datetime(2026, 10, 12, 12, 20, tzinfo=dt.timezone.utc)      # 루틴 12:00 UTC → 업로드 12:20 무렵
ck("A(survival) Pt.1: 10/13 20:00 UTC(16:00 ET)", UR.when(A, up) == "2026-10-13T20:00:00Z", UR.when(A, up))
ck("B1(compare) Pt.1: 10/13 23:30 UTC(19:30 ET)", UR.when(B1, up) == "2026-10-13T23:30:00Z", UR.when(B1, up))
ck("B2(liminal) Pt.1: 10/14 23:30 UTC", UR.when(B2, up + dt.timedelta(days=1)) == "2026-10-14T23:30:00Z")
ck("재실행이 늦으면(슬롯 1시간 안) 다음 날 같은 시각",
   UR.when(A, dt.datetime(2026, 10, 13, 19, 30, tzinfo=dt.timezone.utc)) == "2026-10-14T20:00:00Z")
ck("옛 RULES 는 그대로 13:00 UTC", UR.when(S, dt.datetime(2026, 10, 8, 12, 20, tzinfo=dt.timezone.utc)) == "2026-10-09T13:00:00Z")
ck("rules.py next 의 publish_at = 업로드 예약 시각", all(UR.when(json.loads(json.dumps({"id": e["n"], "format": e["format"]})), up)
                                                       == e["publish_at"] for e in RU.on_date(D(2026, 10, 12))))
_ur = open(UR.__file__, encoding="utf-8").read()
ck("업로드가 편마다 예약하고 재생목록을 고르고, ledger 에 공개 시각·쇼츠 조건을 남긴다",
   "when(s)" in _ur and "RU.playlist_for(s)" in _ur and '"publish_at": at, "shorts": facts' in _ur)

print("── 워크플로 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "tales-rules.yml"), encoding="utf-8").read()
ck("routine/tales_rules 의 output/tales_rules 만 · 코드는 main", '"routine/tales_rules"' in wf
   and '"output/tales_rules/**"' in wf and "ref: main" in wf and "rules.py check" in wf)
ck("한 push 의 대본 여러 편을 편마다 돈다(검사·렌더·업로드 루프)",
   "for f in $TARGETS" in wf and 'rules.py check "$f"' in wf and "for f in $OK" in wf and "upload_rule.py \"$f\"" in wf)
ck("권한은 contents: read 그대로", "permissions:\n  contents: read" in wf)
ck("실패한 편이 있으면 빨간불(다른 편은 올린다)", "steps.build.outputs.bad != ''" in wf)

print("── 렌더 프레임(가짜 그림·목소리) ──")
import render_rule as RR  # noqa: E402
ck("fmt_clock: 1:15 · 0:00:10 · 1:00:00 · DAY 3",
   (RR.fmt_clock(75, "1:15"), RR.fmt_clock(10, "1:00:00"), RR.fmt_clock(3600, "1:00:00"), RR.fmt_clock(259200, "DAY 3"))
   == ("1:15", "0:00:10", "1:00:00", "DAY 3"))
assets_ok = all(os.path.exists(os.path.join(RR.ASSETS, f"chibi_{r}.png")) for r in RU.REACTS)
ck("치비 구미 4종이 있다(옛 형식)", assets_ok)
have_ff = bool(shutil.which("ffmpeg") or os.path.exists(r"C:\wbtmp\ffbin\ffmpeg.exe"))


def yellowish(im, box):
    px = im.crop(box).convert("RGB").getdata()
    return sum(1 for r, g, b in px if r > 200 and g > 170 and b < 120)


tmp = tempfile.mkdtemp()
try:
    if have_ff:
        for nm, x in (("survival", A), ("compare", B1), ("liminal", B2)):
            P, pa = RR.prepare(x, os.path.join(tmp, nm), mock=True)
            ts = RR.sample_times(P)
            fr = {k: pa.frame(v) for k, v in ts.items()}
            ck(f"{nm}: 0초·가운데·끝 프레임 1080×1920", all(f.size == (1080, 1920) for f in fr.values()))
            ck(f"{nm}: 세 프레임이 서로 다르다", len({f.tobytes()[::997] for f in fr.values()}) == 3)
            ck(f"{nm}: 새 형식은 구미를 그리지 않는다(치비 없음)", getattr(pa, "gumi", None) is None)
            ck(f"{nm}: 30–45초 안쪽(상한 {RR.MAX_SEC_NEW[nm]}초)", 15 <= P["total"] <= RR.MAX_SEC_NEW[nm], P["total"])
            if nm == "survival":
                ck("survival 0초: 생존 시계(노란 0:00)가 첫 프레임에", yellowish(fr["first"], (220, 480, 800, 720)) > 1500)
                ck("survival 끝: GUMI'S ODDS(노란 글자)", yellowish(fr["end"], (150, 910, 900, 1000)) > 1500)
                cv = [pa.clock_value(*((lambda k, r: (k, tt - r["start"]))(*pa.row_at(tt))))
                      for tt in [i * 0.25 for i in range(int(P["total"] * 4))]]
                ck("survival: 시계는 앞으로만 간다", all(b[1] >= a[1] for a, b in zip(cv, cv[1:])))
                ck("survival: 시계는 마지막 박자 시각(대본 t 그대로)에서 멈춘다", cv[-1][0] == P["rows"][-1]["t"], cv[-1])
                ck("survival: 출처 없는 시각은 낱말(INSTANT)로 뜬다", any(c[0] == "INSTANT" for c in cv))
            if nm == "compare":
                ck("compare 가운데: 노란 막대(지금 항목)", yellowish(fr["mid"], (320, 975, 930, 1370)) > 800)
            if nm == "liminal":
                ck("liminal: 끝은 첫 장면으로 섞인다(루프)", P["loop"] is True)
            # 2026-10-10 검수: 자막이 y 1590–1660(제목·채널 덮개 안) → 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 침범
            bx = []
            for i in range(int(P["total"] * 2)):
                pa.frame(i * 0.5)
                bx += pa.boxes
            cap = [b for b in bx if b[0] == "caption"]
            ck(f"{nm}: 글자·상자가 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 침범",
               bx and max(b[3] for b in bx) <= RR.SAFE_X1 + 1 and max(b[4] for b in bx) <= RR.SAFE_Y1 and min(b[1] for b in bx) >= 0,
               (max(bx, key=lambda b: b[3]), max(bx, key=lambda b: b[4])))
            ck(f"{nm}: 자막 아랫변 ≤ y 1480", cap and max(b[4] for b in cap) <= RR.CAP_BOTTOM, max(b[4] for b in cap) if cap else None)
        m = RR.render(os.path.join(SC, "R101_mariana-trench-floor.json"), out_dir=os.path.join(tmp, "out"),
                      work=os.path.join(tmp, "survival"), mock=True)
        ck("가짜 렌더(survival): 영상 · 프레임 3장 · 메타", os.path.exists(m["video"]) and all(os.path.exists(p) for p in m["frames"].values())
           and m["mock"] and m["stem"] == "R101_mariana-trench-floor")
        fx_ = UT.shorts_facts(m["video"])
        ck("쇼츠 판정 조건: 세로 1080×1920 · 3분 이하 · madeForKids=false",
           fx_["vertical"] and fx_["le_3min"] and fx_["made_for_kids"] is False and (fx_["w"], fx_["h"]) == (1080, 1920), fx_)
        m0 = RR.render(os.path.join(SC, "R001_name-called-at-night.json"), out_dir=os.path.join(tmp, "out"),
                       work=os.path.join(tmp, "old"), mock=True)
        ck("옛 형식 가짜 렌더도 그대로(40초 이하·치비)", os.path.exists(m0["video"]) and m0["sec"] <= RR.MAX_SEC)
    else:
        print("  (ffmpeg 없음 — 렌더 테스트 건너뜀)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
