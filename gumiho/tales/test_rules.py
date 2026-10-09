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
ck("teaser_idea: 매일(A)은 TOMORROW, 격일(B)은 NEXT(요일은 시간대마다 달라 안 쓴다), liminal·마지막 편은 없음",
   RU.teaser_idea(sv[0], sc).startswith("PT.2 TOMORROW: ") and RU.teaser_idea(cp[0], sc) == "PT.2 NEXT: BLACK HOLES"
   and not any(w in (RU.teaser_idea(e, sc) or "") for e in cp for w in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
                                                                     "FRIDAY", "SATURDAY", "SUNDAY"))
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
ck("모범 대본 통과 — 옛 rules R001(--allow-retired)", not RU.check(S, allow_retired=True), RU.check(S, allow_retired=True))
for nm, x in (("survival R101", A), ("compare R201", B1), ("liminal R301", B2)):
    ck(f"모범 대본 통과 — {nm}", not RU.check(x), RU.check(x))
ck("모범 대본끼리 그림 프롬프트가 안 겹친다", not RU.check(A, others=[B1, B2, S]) and not RU.check(B1, others=[A, B2]))


def errs_of(base, mut, others=None):
    s = copy.deepcopy(base)
    mut(s)
    return RU.check(s, others=others, allow_retired=True)


def has(errs, word):
    return any(word in e for e in errs)


print("── 옛 설화 RULES 종료(10/9) — --allow-retired 없이는 검사·업로드 거부 ──")
ck("10/10(UTC)부터 옛 R001 검사 거부", has(RU.check(S, today=D(2026, 10, 10)), "--allow-retired"))
ck("10/9 까지는 옛 R001 검사 통과(그날 배정분)", not RU.check(S, today=D(2026, 10, 9)))
ck("--allow-retired 면 10/10 뒤에도 검사", not RU.check(S, today=D(2026, 10, 20), allow_retired=True))
import upload_rule as UR  # noqa: E402
_late = dt.datetime(2026, 10, 10, 12, 20, tzinfo=dt.timezone.utc)
try:
    UR.when(S, _late)
    _refused = False
except RuntimeError as _e:
    _refused = "--allow-retired" in str(_e)
ck("업로드 시각(when)도 10/10 뒤 옛 편은 거부", _refused)
ck("업로드 시각(when) --allow-retired 면 준다", UR.when(S, _late, allow_retired=True).startswith("2026-10-10T"))
_cli = subprocess.run([sys.executable, os.path.join(HERE, "rules.py"), "check", os.path.join(HERE, "rules_scripts", "R001_name-called-at-night.json")],
                      capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
ck("rules.py check CLI 에 --allow-retired 가 있고, 워크플로는 그 플래그를 쓰지 않는다",
   "--allow-retired" in open(RU.__file__, encoding="utf-8").read()
   and "allow-retired" not in open(os.path.join(ROOT, ".github", "workflows", "tales-rules.yml"), encoding="utf-8").read())
if RU.retired():
    ck("오늘(UTC) 옛 R001 CLI 검사 거부", _cli.returncode == 1 and "allow-retired" in _cli.stdout, _cli.stdout[-200:])

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
# 10/10 검수: 숫자만 보고 단위는 안 봤다 · 글자로 쓴 숫자 · 줄 밖 글자 · URL · value 와 label 이 다른 막대
ck("단위가 다르면 거부('23 SECONDS LEFT' — fact 는 23 days)", has(errs_of(A, lambda s: s["beats"][3].update(text="23 SECONDS LEFT")), "facts 에 없다"))
ck("단위가 다르면 거부('1 minute' — fact 는 1 atmosphere)", has(errs_of(A, lambda s: s["beats"][1].update(say="You have 1 minute.")), "facts 에 없다"))
ck("글자로 쓴 숫자도 검사('ninety seconds')", has(errs_of(A, lambda s: s["beats"][1].update(say="You have ninety seconds.")), "facts 에 없다"))
ck("글자로 쓴 숫자도 검사('TEN SECONDS LEFT')", has(errs_of(A, lambda s: s["beats"][1].update(text="TEN SECONDS LEFT")), "facts 에 없다"))
for _f in ("title", "hook", "situation", "description_hook"):
    _v = {"title": "How Long Would You Last 99 Minutes Down? Pt.1 #shorts", "hook": "99 MINUTES DOWN",
          "situation": "99 MINUTES DOWN", "description_hook": "You have 99 minutes."}[_f]
    ck(f"{_f} 의 숫자도 facts 에서만", has(errs_of(A, lambda s, _f=_f, _v=_v: s.update({_f: _v})), "facts 에 없다"))
ck("compare name 의 숫자도 facts 에서만", has(errs_of(B1, lambda s: s["items"][1].update(name="VAMPIRE SQUID 99")), "facts 에 없다"))
ck("compare value 가 label 과 다르면 거부(value 130 · '13 M')", has(errs_of(B1, lambda s: s["items"][5].update(value=130)), "value"))
ck("compare label 단위가 unit 과 안 맞으면 거부", has(errs_of(B1, lambda s: s["items"][5].update(label="13 KG")), "단위"))
ck("구미 한 줄: 확률(odds) 말고 다른 숫자는 facts 에서만", has(errs_of(A, lambda s: s["gumi"].update(say="Gumi's odds: zero. Try 50 times.")), "gumi.say"))
ck("구미 한 줄: odds 50% 라고 50 을 끼워 넣을 수 없다",
   has(errs_of(A, lambda s: s["gumi"].update(odds="50%", say="Gumi's odds: fifty percent. 50 meters more.")), "gumi.say"))
ck("구미 한 줄: 말한 확률이 odds 와 다르면 거부", has(errs_of(A, lambda s: s["gumi"].update(say="Gumi's odds: two percent. You won't.")), "확률"))
ck("글에 URL 거부(say)", has(errs_of(A, lambda s: s["beats"][1].update(say="Read more at https://example.com now.")), "URL"))
ck("글에 URL 거부(description_hook · 도메인만)", has(errs_of(A, lambda s: s.update(description_hook="Sources at noaa.gov.")), "URL"))
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
                  ("Titanic", lambda s: s["beats"][1].update(img="the wreck of the Titanic on the sea floor")),
                  ("Japanese", lambda s: s["beats"][1].update(say="A Japanese legend lives down here.")),
                  ("Chinese", lambda s: s.update(description_hook="A Chinese tale of the deep.")),
                  ("legends(복수)", lambda s: s["beats"][1].update(say="Sailors' legends warn about it.")),
                  ("kappa", lambda s: s["tags"].append("kappa")),
                  ("oni", lambda s: s["beats"][1].update(img="an oni mask on the sea floor")),
                  ("urban legend", lambda s: s["beats"][1].update(say="It sounds like an urban legend.")),
                  ("mythology", lambda s: s["tags"].append("mythology")),
                  ("Shinto", lambda s: s["beats"][1].update(img="a Shinto gate under water")),
                  ("creepypasta", lambda s: s["tags"].append("creepypasta")),
                  ("folk tales(복수)", lambda s: s["beats"][1].update(say="Old folk tales lied.")),
                  ("kitsunes(복수)", lambda s: s["tags"].append("kitsunes")),
                  ("Subnautica", lambda s: s["beats"][1].update(say="Like Subnautica, but real.")),
                  ("Alien", lambda s: s["beats"][1].update(img="an alien creature in the dark")),
                  ("Silent Hill", lambda s: s["tags"].append("silent hill")),
                  ("Resident Evil", lambda s: s["tags"].append("resident evil")),
                  ("Slender Man", lambda s: s["beats"][1].update(img="slender man in the deep")),
                  ("Siren Head", lambda s: s["tags"].append("siren head")),
                  ("Netflix", lambda s: s.update(description_hook="Better than Netflix.")),
                  ("Kisaragi Station", lambda s: s["tags"].append("kisaragi station")),
                  ("The Exit 8", lambda s: s["tags"].append("the exit 8"))):
    ck(f"금지 주제 거부 — {word}", has(errs_of(A, mut), "금지 주제"), errs_of(A, mut)[:2])
ck("새 형식도 욕설·날짜 타는 말 거부", has(errs_of(A, lambda s: s["beats"][1].update(say="A gore scene, right now.")), "금지어")
   and has(errs_of(A, lambda s: s["beats"][1].update(say="It is dark right now down here at 1,000 meters.")), "날짜"))
ck("그림에 구미 거부", has(errs_of(A, lambda s: s["beats"][1].update(img="Gumi floating in the deep sea")), "구미"))
ck("그림에 여우 거부", has(errs_of(B1, lambda s: s["items"][1].update(img="a red fox swimming underwater")), "여우"))
for _img in ("a vulpine face in the dark", "Vulpes vulpes under water", "a creature with nine tails", "fluffy tails glowing",
             "a figure with animal ears", "a girl with a tail floating", "a woman with a fluffy tail", "a silver-haired anime girl"):
    ck(f"그림에 구미·여우 우회 표현 거부 — {_img}", has(errs_of(B1, lambda s, _img=_img: s["items"][1].update(img=_img)), "구미"))
ck("그림 프롬프트에 글자 거부", has(errs_of(A, lambda s: s["beats"][1].update(img="a sign with text that says DANGER")), "글자"))
ck("같은 편 안에서 그림 재사용 거부", has(errs_of(A, lambda s: s["beats"][2].update(img=s["beats"][1]["img"])), "두 번"))
other = copy.deepcopy(B1)
other["items"][0]["img"] = A["beats"][1]["img"]
ck("다른 편과 같은 그림 프롬프트 거부(재사용 금지)", has(RU.check(A, others=[other]), "다른 편"))
# 10/10 검수: 낱말 하나 바꾸기 · ', 4k' 붙이기로 같은 그림을 다시 쓸 수 있었다 → 비슷함 ≥ 0.85 면 거부
_near = copy.deepcopy(B1)
_near["items"][0]["img"] = A["beats"][1]["img"] + ", 4k"
ck("다른 편 그림 + ', 4k' 거부", has(RU.check(A, others=[_near]), "다른 편"))
_near2 = copy.deepcopy(B1)
_near2["items"][0]["img"] = A["beats"][1]["img"].replace("pitch", "deep").replace("total", "complete")
ck("다른 편 그림 낱말 하나 바꾸기 거부", has(RU.check(A, others=[_near2]), "다른 편"))
ck("같은 편 안에서 거의 같은 그림 거부", has(errs_of(A, lambda s: s["beats"][2].update(img=s["beats"][1]["img"] + ", ultra detailed")), "두 번"))
ck("모범 대본끼리는 안 겹친다(비슷함 기준)", not any(RU.img_similar(RU._norm_img(x.get("img")), RU._norm_img(y.get("img")))
                                           for a_ in (A, B1, B2) for b_ in (A, B1, B2) if a_ is not b_
                                           for x in RU.lines_of(a_) for y in RU.lines_of(b_)))
ck("siblings(): 같은 폴더의 다른 대본을 읽는다", {x["id"] for x in RU.siblings(os.path.join(SC, "R101_mariana-trench-floor.json"))}
   >= {1, 201, 301})

print("── 대본 검사: survival ──")
ck("situation 없으면 거부", has(errs_of(A, lambda s: s.pop("situation")), "situation"))
ck("첫 박자가 0:00 이 아니면 거부", has(errs_of(A, lambda s: s["beats"][0].update(t="0:05")), "0:00"))
# 2026-10-10 검수 두 번: ① 지어낸 1:00 ② INSTANT·DAY 23·'SECONDS NINETY'·INSTANT→MINUTES 가 통과
#   → 대본 시각은 catalog beat_ideas 그대로, catalog 시각은 clock_fact 의 '같은 수 + 같은 단위'
ck("출처 없는 생존 시각 거부(지어낸 1:00)", has(errs_of(A, lambda s: s["beats"][3].update(t="1:00")), "지어내지"))
ck("출처 없는 생존 시각 거부(지어낸 0:12)", has(errs_of(A, lambda s: s["beats"][3].update(t="0:12")), "지어내지"))
ck("다른 fact 의 수로 시계 만들기 거부(DAY 23 — 마이크가 23일 버텼다)", has(errs_of(A, lambda s: s["beats"][3].update(t="DAY 23")), "지어내지"))
ck("꼬리 붙은 낱말 거부('SECONDS NINETY')", has(errs_of(A, lambda s: s["beats"][3].update(t="SECONDS NINETY")), "지어내지"))
ck("꼬리 붙은 낱말 거부('HOURS SEVENTY TWO')", has(errs_of(A, lambda s: s["beats"][3].update(t="HOURS SEVENTY TWO")), "지어내지"))
ck("beat_ideas 와 다른 낱말 거부(--:-- 자리에 MINUTES)", has(errs_of(A, lambda s: s["beats"][3].update(t="MINUTES")), "지어내지"))
ck("INSTANT 는 이제 없다(출처 없는 '죽기까지 시간')", "INSTANT" not in RU.WORD_RANK and not any(
   "INSTANT" in RU.beat_labels(e) for e in sv))
ck("beat_ideas 보다 박자를 빼거나 더하면 거부", has(errs_of(A, lambda s: s["beats"].append(dict(s["beats"][-1], img="another picture of the deep ocean floor with a lamp"))), "지어내지"))
_e101 = RU.entry(101)
ck("beat_ok: 단위가 다른 fact 로는 시계가 안 된다", not RU.beat_ok({"t": "0:23", "fact": 6}, _e101)
   and not RU.beat_ok({"t": "1:00", "fact": 3}, _e101))
ck("beat_ok: 낱말은 clock_fact 에 그 단위가 있을 때만", RU.beat_ok({"t": "HOURS", "fact": 8}, RU.entry(108))
   and not RU.beat_ok({"t": "HOURS", "fact": 0}, RU.entry(108)) and not RU.beat_ok({"t": "MINUTES", "fact": 0}, _e101))
ck("clock_backed: facts 의 '같은 수 + 같은 단위'와 맞을 때만",
   RU.clock_backed("0:12", ["about 9-12 seconds of useful consciousness"]) and RU.clock_backed("5:00", ["frostbite in 5 minutes"])
   and RU.clock_backed("3:00:13", ["about 3 hours", "just 12.8 seconds later"]) and RU.clock_backed("23:30:00", ["a day lasted 23.5 hours"])
   and RU.clock_backed("DAY 3", ["in as little as 3 days"]) and RU.clock_backed("1:30", ["1-1.5 minutes after"])
   and not RU.clock_backed("1:00", ["2.4 °C water", "1 atmosphere every 10.06 meters"])
   and not RU.clock_backed("0:23", ["recorded sound for 23 days"]) and not RU.clock_backed("1:20:00", ["1 hour and 10 minutes"])
   and RU.clock_backed("0:00", []))
_bad = []
for e in sv:
    _prev = -1
    for b in e.get("beat_ideas", []):
        if b["t"] == "GUMI":
            continue
        _lb = RU.clock_lb(b["t"])
        if _lb is None or not RU.beat_ok(b, e) or (_lb >= 0 and _lb < _prev):
            _bad.append((e["slug"], b["t"]))
        _prev = _lb if _lb is not None and _lb >= 0 else _prev
ck("catalog survival 14편: beat_ideas 시각이 전부 clock_fact 의 '수 + 단위'·낱말·--:-- 이고 앞으로만",
   not _bad and all(e["beat_ideas"][0]["t"] == "0:00" for e in sv), _bad)
ck("R103 의 23.5시간은 '하루 길이' — 시계 값이 아니다", "23:30:00" not in RU.beat_labels(RU.entry(103)))
ck("시계 꼴이 틀리면 거부", has(errs_of(A, lambda s: s["beats"][1].update(t="soon")), "꼴"))
ck("박자 3개면 거부(4–6)", has(errs_of(A, lambda s: s.update(beats=s["beats"][:3])), "beats"))
ck("odds 없으면 거부", has(errs_of(A, lambda s: s["gumi"].pop("odds")), "odds"))
ck("제목에 Pt.N 없으면 거부", has(errs_of(A, lambda s: s.update(title="How Long Would You Last in the Mariana Trench? #shorts")), "Pt."))
ck("제목이 How Long Would You Last 가 아니면 거부", has(errs_of(A, lambda s: s.update(title="The Mariana Trench Pt.1 #shorts")), "How Long"))
ck("teaser 는 다음 Pt", has(errs_of(A, lambda s: s.update(teaser="PT.5 TOMORROW: MARS")), "teaser"))
ck("teaser 는 teaser_idea 글자 그대로(같은 Pt 라도 다르면 거부)", has(errs_of(A, lambda s: s.update(teaser="PT.2 TOMORROW: MARS!")), "teaser"))
ck("teaser_idea 가 null 이면 teaser 없음(마지막 편)", RU.teaser_idea(sv[-1], sc) is None)
ck("clock_sec: 0:10 · 1:00:00 · DAY 3", (RU.clock_sec("0:10"), RU.clock_sec("1:00:00"), RU.clock_sec("DAY 3")) == (10, 3600, 259200))

print("── 대본 검사: compare · liminal ──")
ck("compare: 작은 것 → 큰 것 순서가 아니면 거부", has(errs_of(B1, lambda s: s["items"].insert(0, s["items"].pop(2))), "오름차순"))
ck("compare: 마지막 twist 없으면 거부", has(errs_of(B1, lambda s: s["items"][-1].pop("twist")), "twist"))
ck("compare: scale 없으면 거부", has(errs_of(B1, lambda s: s.pop("scale")), "scale"))
ck("compare: 제목에 Ranked/by Size", has(errs_of(B1, lambda s: s.update(title="Deep Sea Creatures Pt.1 #shorts")), "Ranked"))
ck("compare: 값 없는 반전 글자 길이 상한", has(errs_of(B1, lambda s: (s["items"][-1].pop("value"), s["items"][-1].pop("label"),
                                                  s["items"][-1].update(text="A VERY LONG TWIST LINE THAT WILL NOT FIT ON SCREEN"))), "반전"))
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
ck("재생목록: How Long Would You Last? · Ranked: Biggest, Heaviest, Fastest · Liminal Rules",
   [RU.playlist_for(x)[0] for x in (A, B1, B2)] == ["How Long Would You Last?", "Ranked: Biggest, Heaviest, Fastest", "Liminal Rules"]
   and RU.playlist_for(S) is None)
ck("깊은 바다 편 해시태그에 #space 가 없다", "#space" not in RU.meta(A, ch)["description"] and "#space" not in RU.meta(B1, ch)["description"]
   and "#ocean" in RU.meta(B1, ch)["description"])
st = UT.status_body("private", "2026-10-13T20:00:00Z")
ck("업로드: containsSyntheticMedia=true(실사) · madeForKids=false · 예약은 private",
   st.get("containsSyntheticMedia") is True and st["selfDeclaredMadeForKids"] is False and st["privacyStatus"] == "private")
up = dt.datetime(2026, 10, 12, 12, 20, tzinfo=dt.timezone.utc)      # 루틴 12:00 UTC → 업로드 12:20 무렵
ck("A(survival) Pt.1: 10/13 20:00 UTC(16:00 ET)", UR.when(A, up) == "2026-10-13T20:00:00Z", UR.when(A, up))
ck("B1(compare) Pt.1: 10/13 23:30 UTC(19:30 ET)", UR.when(B1, up) == "2026-10-13T23:30:00Z", UR.when(B1, up))
ck("B2(liminal) Pt.1: 10/14 23:30 UTC", UR.when(B2, up + dt.timedelta(days=1)) == "2026-10-14T23:30:00Z")
# 10/10 검수: 늦은 업로드를 다음 날 같은 시각으로 미루면 다음 편(Pt.2) 칸에 겹친다 → 지금 + 1시간(15분 올림), 같은 날
_l = UR.when(A, dt.datetime(2026, 10, 13, 19, 30, tzinfo=dt.timezone.utc))
ck("늦은 업로드(슬롯 1시간 안): 지금 + 1시간 · 같은 날 — 다음 편 칸(10/14 20:00)에 안 겹친다",
   _l == "2026-10-13T20:30:00Z" and _l != "2026-10-14T20:00:00Z", _l)
ck("늦은 업로드(슬롯 지남): 15분 단위로 올림",
   UR.when(B1, dt.datetime(2026, 10, 13, 23, 41, 5, tzinfo=dt.timezone.utc)) == "2026-10-14T00:45:00Z"
   and UR.when(A, dt.datetime(2026, 10, 13, 21, 7, tzinfo=dt.timezone.utc)) == "2026-10-13T22:15:00Z")
ck("옛 RULES 는 그대로 13:00 UTC(10/9 까지)", UR.when(S, dt.datetime(2026, 10, 8, 12, 20, tzinfo=dt.timezone.utc)) == "2026-10-09T13:00:00Z")
ck("rules.py next 의 publish_at = 업로드 예약 시각", all(UR.when(json.loads(json.dumps({"id": e["n"], "format": e["format"]})), up)
                                                       == e["publish_at"] for e in RU.on_date(D(2026, 10, 12))))
_ur = open(UR.__file__, encoding="utf-8").read()
ck("업로드가 편마다 예약하고 재생목록을 고르고, ledger 에 공개 시각·쇼츠 조건을 남긴다",
   "when(s, allow_retired=a.allow_retired)" in _ur and "RU.playlist_for(s)" in _ur and '"publish_at": at, "shorts": facts' in _ur)

print("── 워크플로 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "tales-rules.yml"), encoding="utf-8").read()
ck("routine/tales_rules 의 output/tales_rules 만 · 코드는 main", '"routine/tales_rules"' in wf
   and '"output/tales_rules/**"' in wf and "ref: main" in wf and "rules.py check" in wf)
ck("한 push 의 대본 여러 편을 편마다 돈다(검사·렌더·업로드 루프)",
   "for f in $TARGETS" in wf and 'rules.py check "$f"' in wf and "for f in $OK" in wf and "upload_rule.py \"$f\"" in wf)
ck("권한은 contents: read 그대로", "permissions:\n  contents: read" in wf)
ck("실패한 편이 있으면 빨간불(다른 편은 올린다)", "steps.build.outputs.bad != ''" in wf)
# 10/10 검수: actions/cache 하나로는 잡이 실패하면 ledger 가 저장되지 않아, 올라간 다른 편 기록을 잃었다
ck("ledger: cache/restore + cache/save(if: always()) — 실패해도 저장", "actions/cache/restore@v4" in wf
   and "actions/cache/save@v4" in wf and wf.index("actions/cache/save@v4") > wf.index("upload_rule.py")
   and "always()" in wf[wf.index("actions/cache/save@v4") - 300:wf.index("actions/cache/save@v4")])

print("── 렌더 프레임(가짜 그림·목소리) ──")
import render_rule as RR  # noqa: E402
ck("fmt_clock: 1:15 · 0:00:10 · 1:00:00 · DAY 3",
   (RR.fmt_clock(75, "1:15"), RR.fmt_clock(10, "1:00:00"), RR.fmt_clock(3600, "1:00:00"), RR.fmt_clock(259200, "DAY 3"))
   == ("1:15", "0:00:10", "1:00:00", "DAY 3"))
assets_ok = all(os.path.exists(os.path.join(RR.ASSETS, f"chibi_{r}.png")) for r in RU.REACTS)
ck("치비 구미 4종이 있다(옛 형식)", assets_ok)
have_ff = bool(shutil.which("ffmpeg") or os.path.exists(r"C:\wbtmp\ffbin\ffmpeg.exe"))


def _edge_clean(pa, t):
    """카드를 붙이기 전·후 프레임의 x 961–1079 띠가 같은가(카드가 그 띠를 건드리지 않았나)."""
    import render_rule as _RR
    _orig = _RR.Base.paste_card
    seen = {}

    def spy(self, fr, card, y, sc):
        before = fr.crop((961, y, 1080, y + card.height)).tobytes()
        _orig(self, fr, card, y, sc)
        seen["ok"] = fr.crop((961, y, 1080, y + card.height)).tobytes() == before
    _RR.Base.paste_card = spy
    try:
        pa.frame(t)
    finally:
        _RR.Base.paste_card = _orig
    return seen.get("ok", True)


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
                ck("survival: 출처 없는 박자는 '--:--'(시계가 시간을 말하지 않는다)", any(c[0] == RU.NO_TIME for c in cv))
                pa.frame(P["total"] - 0.3)
                ck("survival: 마지막 박자가 --:-- 면 끝 화면에 시계가 없다(구미의 확률만)",
                   not any(b[0] == "clock" for b in pa.boxes) and any(b[0] == "odds" for b in pa.boxes))
                Pm, pm = RR.prepare(x, os.path.join(tmp, nm), mock=True)
                pm.rows[-1]["notime"], pm.rows[-1]["sec"], pm.rows[-1]["t"] = False, 12, "0:12"
                pm.frame(Pm["total"] - 0.3)
                ck("survival: 출처 있는 시각으로 끝나면 'CLOCK STOPPED' 시계가 남는다", any(b[0] == "clock" for b in pm.boxes))
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
            # 카드가 튀어나오는 0.18초 동안 실제 픽셀이 x 960 을 넘지 않는다(10/10 검수: 540 축으로 키우면 넘었다)
            _pop = max((r_["start"] + 0.04 for r_ in P["rows"] if r_.get("text") or r_.get("big")), default=None)
            if _pop is not None and nm != "compare":
                ck(f"{nm}: 카드 튀어나올 때도 x 960 오른쪽에 카드 글자가 안 그려진다",
                   _edge_clean(pa, _pop), _pop)
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
                       work=os.path.join(tmp, "old"), mock=True, allow_retired=True)
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
