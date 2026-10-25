#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채우기 검사(refill_check) 오프라인 테스트 — 레포의 편성 모듈·catalog 를 임시 폴더 두 곳(기준·지금)에 복사해
지금 쪽에만 채우기를 해 보고, 잘 채운 것은 통과 · 규칙을 어긴 것은 막는지 본다(git·네트워크 없이).

    python tools/test_refill_check.py
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import refill_check as RC  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


TODAY = dt.date(2026, 10, 25)
TMP = tempfile.mkdtemp(prefix="refill_test_")


def tree(name: str) -> str:
    dst = os.path.join(TMP, name)
    for d in RC.DIRS:
        src = os.path.join(ROOT, *d.split("/"))
        os.makedirs(os.path.join(dst, *d.split("/")), exist_ok=True)
        for fn in os.listdir(src):
            if fn.endswith((".py", ".json")):
                shutil.copy(os.path.join(src, fn), os.path.join(dst, *d.split("/"), fn))
    return dst


def jload(root, *p):
    with open(os.path.join(root, *p), encoding="utf-8") as f:
        return json.load(f)


def jsave(obj, root, *p):
    with open(os.path.join(root, *p), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def with_evidence(facts):
    return [dict(f, evidence=f.get("evidence") or f["fact"][:60]) if isinstance(f, dict) else
            {"fact": f, "src": 0, "evidence": f[:60]} for f in facts]


BASE = tree("base")
EXPECT = {"wb_gunghap": ["refill-test"], "insta_teardown": []}   # good_tree 가 나머지를 채운다


def good_tree(name: str) -> str:
    """지금 쪽 — 여섯 줄기 모두에 규칙대로 채운다(from ≥ 내일 · 끝에 붙임 · 사실마다 evidence)."""
    t = tree(name)
    sc = jload(t, "gumiho", "tales", "shorts_catalog.json")
    # ★번호·from 은 지금 catalog 끝 기준(진짜 채우기가 먼저 붙어 있어도 겹치지 않게 — 10/25 refill PR 이 깨진 일)
    e = copy.deepcopy(sc["survival"][-1])
    n = max(x["n"] for x in sc["survival"]) + 1
    e.update(n=n, slug=f"refill-survival-{n}", part=len(sc["survival"]) + 1, facts=with_evidence(e["facts"]),
             **{"from": max(["2026-11-02", *[x.get("from", "") for k in ("survival", "compare", "liminal") for x in sc.get(k, [])]])})
    sc["survival"].append(e)
    EXPECT["nt_shorts"] = [n]
    jsave(sc, t, "gumiho", "tales", "shorts_catalog.json")
    cat = jload(t, "gumiho", "tales", "catalog.json")
    x = {k: v for k, v in copy.deepcopy(cat["tales"][-1]).items() if k != "date"}
    x.update(id=cat["tales"][-1]["id"] + 1, slug="refill-longform",
             facts=[dict(f, src=0) for f in with_evidence(x["facts"])],   # 출처를 하나로 바꾸니 src 도 0 으로
             sources=["https://www.noaa.gov/jetstream/ocean/layers-of-ocean"],
             **{"from": max(["2026-11-03", *[t.get("from", "") for t in cat["tales"]]])})
    cat["tales"].append(x)
    EXPECT["nt_longform"] = [x["id"]]
    jsave(cat, t, "gumiho", "tales", "catalog.json")
    with open(os.path.join(t, "pipeline", "gunghap_card.py"), "a", encoding="utf-8") as f:
        f.write('\nTHEMES.append(dict(THEMES[0], id="refill-test", **{"from": "2026-11-05"}))\n')
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import longform_2027 as LF
    e5 = LF.EPISODES[4]
    _mp = os.path.join(t, "pipeline", "longform_2027_more.json")
    more = jload(t, "pipeline", "longform_2027_more.json") if os.path.exists(_mp) else {"episodes": []}
    _eid = f"E{17 + len(more['episodes'])}"
    more["episodes"].append({"id": _eid, "from": max(["2026-12-09", *[m.get("from", "") for m in more["episodes"]]]), "animals": e5["animals"],
                         "title": "2027년 양띠 재물운 깊이 보기 | 돈이 도는 달과 지킬 것 · 출생연도별 풀이",
                         "thumb": {"big": "2027 양띠", "sub": "재물운", "pill": "돈이 도는 달"},
                         "angle": "양띠 재물만 깊게 — 앞 편(총운)과 달리 돈 흐름·달별 재물·지킬 것을 차근차근",
                         "chapters": e5["chapters"], "qa_seeds": e5["qa_seeds"][:3]})
    jsave(more, t, "pipeline", "longform_2027_more.json")
    EXPECT["wb_lf27"] = [_eid]
    ex = jload(t, "insta", "sci_extra.json")
    s = copy.deepcopy(ex["survival"][0])
    sn = max([x["n"] for k in ("survival", "compare") for x in ex.get(k, [])] + [903]) + 1
    s.update(n=sn, slug=f"refill-sci-{sn}", facts=with_evidence(s["facts"]),
             **{"from": max(["2026-11-08", *[x.get("from", "") for k in ("survival", "compare") for x in ex.get(k, [])]])})
    ex["survival"].append(s)
    EXPECT["insta_sci"] = [sn]
    jsave(ex, t, "insta", "sci_extra.json")
    return t


def run(cur):
    return RC.run(TODAY, 60, base_root=BASE, root=cur)


print("── 잘 채운 것은 통과 ──")
GOOD = good_tree("good")
r = run(GOOD)
ck("여섯 줄기 채우기(끝에 붙임 · from ≥ 내일 · evidence) → 통과", r["ok"], RC.text(r))
ck("새 항목을 줄기마다 알아본다", {s: v["new"] for s, v in r["streams"].items()} == EXPECT,
   ({s: v["new"] for s, v in r["streams"].items()}, EXPECT))
ck("같은 트리끼리는 새 항목 0 · 통과", RC.run(TODAY, 60, base_root=BASE, root=BASE)["ok"])


def bad(name, mutate, want, stream=None):
    t = good_tree(name)
    mutate(t)
    res = run(t)
    msgs = (res["streams"][stream]["errors"] if stream else []) + res["errors"] + \
        [m for v in res["streams"].values() for m in v["errors"]]
    ck(name, not res["ok"] and any(want in m for m in msgs), RC.text(res))
    return res


def edit_json(path, fn):
    def go(t):
        obj = jload(t, *path)
        fn(obj)
        jsave(obj, t, *path)
    return go


print("── 규칙을 어기면 막는다 ──")
SC = ("gumiho", "tales", "shorts_catalog.json")
bad("새 항목에 from 이 없다", edit_json(SC, lambda c: c["survival"][-1].pop("from")), "from(YYYY-MM-DD) 없음", "nt_shorts")
bad("from 이 오늘(내일 전)", edit_json(SC, lambda c: c["survival"][-1].update({"from": "2026-10-25"})), "내일", "nt_shorts")
bad("사실에 evidence 가 없다(출처를 안 열었다)", edit_json(("insta", "sci_extra.json"),
                                                lambda c: c["survival"][-1]["facts"][0].pop("evidence")), "evidence", "insta_sci")
bad("번호가 겹친다", edit_json(("gumiho", "tales", "catalog.json"),
                         lambda c: c["tales"].append(dict(c["tales"][-1]))), "겹친다", "nt_longform")
bad("금지 주제(실존 피해자 — Titanic)", edit_json(SC, lambda c: c["survival"][-1].update(title_idea="How Long Would You Last on the Titanic?")),
    "금지", "nt_shorts")
bad("해설 롱폼 새 편에 date 를 직접 적었다", edit_json(("gumiho", "tales", "catalog.json"),
                                             lambda c: c["tales"][-1].update(date="2026-11-08")), "date 는 적지", "nt_longform")
bad("이어 가는 편 번호가 틀렸다(E18 부터)", edit_json(("pipeline", "longform_2027_more.json"),
                                            lambda c: c["episodes"][0].update(id="E18")), "id 는 E17", "wb_lf27")
bad("인스타 새 항목의 숫자가 facts 에 없다(entry_errs)", edit_json(("insta", "sci_extra.json"), lambda c: c["survival"][-1][
    "beat_ideas"][0].update(what="9,999 km/h winds")), "facts 에 없다", "insta_sci")


def swap(c):
    # 113·114 를 번호로 찾아 바꾼다(끝자리 기준이면 진짜 채우기가 붙은 뒤 엉뚱한 편을 바꾼다)
    i, j = (next(k for k, e in enumerate(c["survival"]) if e["n"] == n) for n in (113, 114))
    c["survival"][i], c["survival"][j] = c["survival"][j], c["survival"][i]


r_sw = bad("순서를 바꿔 지난 편성이 달라졌다(113·114)", edit_json(SC, swap), "정해진 편성이 바뀌었다")
ck("…어디가 바뀌었는지 날짜·전→후를 알려 준다", any("2026-10-25" in m and "→" in m for m in r_sw["errors"]), r_sw["errors"])


def insert_mid(c):
    e = copy.deepcopy(c["compare"][0])
    e.update(n=290, slug="refill-mid", facts=with_evidence(e["facts"]), **{"from": "2026-12-01"})
    c["compare"].insert(1, e)


bad("중간에 끼운 편(from 이 있어도)은 뒤 편들 날짜를 밀어낸다 → 막힘", edit_json(SC, insert_mid), "정해진 편성이 바뀌었다")

print("── 명령줄 ──")
out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc = RC.main(["--date", "2026-10-25", "--base-root", BASE, "--root", GOOD, "--json"])
js = json.loads(out.getvalue())
ck("--json · 통과면 종료 코드 0 · 비교 창 = 14일 전 ~ 60일 뒤", rc == 0 and js["ok"] and js["window"] == ["2026-10-11", "2026-12-24"])
out = io.StringIO()
with contextlib.redirect_stdout(out):
    # 가장 이른 새 from 날을 기준 날짜로 → 그 from 은 '내일 이후'가 아니라 막혀야 한다(catalog 에 진짜 채우기가 붙어 있어도)
    _froms = [e.get("from") for e in (
        jload(GOOD, "gumiho", "tales", "shorts_catalog.json")["survival"][-1:] + jload(GOOD, "gumiho", "tales", "catalog.json")["tales"][-1:])]
    rc = RC.main(["--date", min(_froms), "--base-root", BASE, "--root", GOOD])
ck("기준 날짜가 늦으면 그 전·그날 from 은 막힌다 · 종료 코드 1", rc == 1 and "내일" in out.getvalue(), out.getvalue()[-400:])
out = io.StringIO()
with contextlib.redirect_stdout(out):
    rc = RC.main(["--base", "no-such-ref-xyz", "--date", "2026-10-25"])
ck("git 기준을 못 꺼내면 이유를 말하고 종료 코드 2", rc == 2 and "git archive" in out.getvalue(), out.getvalue())
shutil.rmtree(TMP, ignore_errors=True)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
