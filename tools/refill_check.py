#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채우기(refill) 검사 — 주간 채우기 루틴이 catalog 에 붙인 것이 규칙을 지켰는지 코드가 본다 (2026-10-25).

왜: 사용자 10/24 "잘 되는 루틴은 끝내지 말고 계속 돌게" → 주간 클라우드 루틴이 바닥나기 전에 catalog 를 채운다
  (tools/REFILL.md). 루틴은 글보다 코드 검사를 훨씬 잘 지킨다 — 그래서 PR 전에 이것이 ✅ 여야 한다.

보는 것(줄기: nt_shorts · nt_longform · wb_gunghap · wb_lf27 · insta_sci · insta_teardown):
  ① 번호(id·n)가 겹치지 않는다
  ② 새 항목(기준 트리에 없던 번호)은 from 이 있고 from ≥ 내일(KST, --date 기준)
  ③ 지난·정해진 편성이 안 바뀐다 — 기준 트리(기본 origin/main)와 지금 트리의 '날짜 → 편' 표를 --date 14일 전부터
     --days(60)일 뒤까지 만들어, 그 줄기 새 항목의 가장 이른 from 전 날짜는 하나도 달라지면 안 된다
  ④ 사실 줄기(NT 쇼츠 survival·compare · NT 해설 롱폼 · 인스타 sci·뜯어보기)의 새 항목은 sources 가 있고
     fact 마다 {fact, src(출처 번호), evidence(출처 원문 문장)}
  ⑤ 금지어 — 줄기마다 이미 있는 목록(rules·tales 금지 주제 · 왕별이 금지어 · 롱폼 ban_hits · 인스타 entry_errs(상표 포함))
  ⑥ 2027 깊이 보기 이어 가는 편 명세(longform_2027_more.json)는 more_errs 가 비어야 한다(틀리면 편성에서 빠진다)

    python tools/refill_check.py [--date 2026-10-25] [--base origin/main] [--days 60] [--json]
    python tools/refill_check.py --base-root <기준 트리 폴더> [--root <지금 트리>]     # git 없이(테스트)
편성 표는 각 트리의 모듈로 따로 만든다(하위 프로세스 — 같은 이름 모듈이 섞이지 않게). 날짜 셈은 그 트리 코드 그대로.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KST = dt.timezone(dt.timedelta(hours=9))
DIRS = ("pipeline", "gumiho/tales", "insta")            # 편성 모듈·catalog 가 있는 곳(이 아래 *.py·*.json 만 꺼낸다)
STREAMS = ("nt_shorts", "nt_longform", "wb_gunghap", "wb_lf27", "insta_sci", "insta_teardown")
SCHEDULE_OF = {"insta_sci": "insta", "insta_teardown": "insta"}   # 인스타 두 줄기는 한 편성(하루 두 편)을 나눠 쓴다
FACT_BASED = ("nt_longform", "insta_sci", "insta_teardown")      # + nt_shorts 의 survival·compare
LOOKBACK = 14


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


# ── 하위 프로세스: 한 트리의 편성·항목 ─────────────────────────
def _plain(v):
    if callable(v):
        return None
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items() if not callable(x)}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def _entries_of(cat) -> list[dict]:
    if isinstance(cat, list):
        return [e for e in cat if isinstance(e, dict)]
    return [e for k in ("survival", "compare", "entries") for e in (cat.get(k) or []) if isinstance(e, dict)]


def dump(root: str, d0: dt.date, d1: dt.date) -> dict:
    """root 트리의 모듈로 [d0, d1) 편성표와 채울 수 있는 항목 전부. 옛 트리(origin/main)에서도 돌게 오래된 함수만 쓴다
    (rules.publish_date · tales.assigned_id · gunghap_card.is_post_day/theme_for · longform_2027.EPISODES ·
    pick_plan.kind_for/sci_n/bm_n/series_no)."""
    for p in DIRS:
        sys.path.insert(0, os.path.join(root, *p.split("/")))
    days = [d0 + dt.timedelta(days=k) for k in range((d1 - d0).days)]
    out: dict = {"schedules": {}, "entries": {}, "spec_errors": {}, "errors": []}

    def guard(name, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — 한 줄기가 깨져도 나머지는 낸다
            out["errors"].append(f"{name}: {type(e).__name__}: {e}"[:300])

    def nt_shorts():
        import rules as RU
        sc = RU.shorts()
        sch: dict = {}
        ents = []
        for f in RU.NEW_FORMATS:
            for e in sc.get(f) or []:
                d = RU.publish_date(e, sc)
                if d0 <= d < d1:
                    sch.setdefault(d.isoformat(), []).append(e["n"])
                ents.append({"id": e["n"], "from": e.get("from"), "fact_based": f != "liminal", "data": e})
        out["schedules"]["nt_shorts"] = {k: sorted(v) for k, v in sch.items()}
        out["entries"]["nt_shorts"] = ents

    def nt_longform():
        import tales as T
        # 공개일(일요일) → 편. 쓰는 창(그 주 월~일)은 보지 않는다 — from 이 화요일이면 그 주 월요일부터 쓸 수 있어서
        out["schedules"]["nt_longform"] = {d.isoformat(): T.assigned_id(d.isoformat()) for d in days if d.weekday() == 6}
        out["entries"]["nt_longform"] = [{"id": e["id"], "from": e.get("from"), "fact_based": True, "data": e}
                                         for e in T.load(T.CATALOG)["tales"] if not e.get("retired")]

    def gunghap():
        import gunghap_card as G
        out["schedules"]["wb_gunghap"] = {d.isoformat(): G.theme_for(d)["id"] for d in days if G.is_post_day(d)}
        out["entries"]["wb_gunghap"] = [{"id": th["id"], "from": th.get("from"), "fact_based": False, "data": _plain(th)}
                                        for th in G.THEMES]

    def lf27():
        import longform_2027 as LF
        out["schedules"]["wb_lf27"] = {e["publish"]: e["id"] for e in LF.EPISODES if d0.isoformat() <= e["publish"] < d1.isoformat()}
        keep = ("title", "search", "thumb", "angle", "qa_seeds", "chapters", "animals")
        out["entries"]["wb_lf27"] = [{"id": e["id"], "from": e.get("from"), "fact_based": False,
                                      "data": _plain({k: e.get(k) for k in keep})} for e in LF.EPISODES]
        if hasattr(LF, "more_specs"):
            specs, before, errs = LF.more_specs(), [e["id"] for e in LF.EPISODES[:getattr(LF, "FIRST_N", 16)]], []
            for sp in specs:
                es = LF.more_errs(sp, before)
                if es:
                    errs.append(f"{sp.get('id')}: " + " · ".join(es))
                    break                                # 틀린 편 뒤로는 하나도 편성되지 않는다
                before.append(sp["id"])
            out["spec_errors"]["wb_lf27"] = errs

    def insta():
        import pick_plan as P
        sch = {}
        for d in days:
            for sl in P.slots_on(d):
                k = P.kind_for(d, sl)
                v = f"{k}:{P.sci_n(d)}" if k == "sci" else f"{k}:{P.bm_n(d)}" if k.startswith("bm_") else f"{k}#{P.series_no(d, sl)}"
                sch[f"{d.isoformat()}{sl}"] = v
        out["schedules"]["insta"] = sch
        with open(os.path.join(root, "insta", "sci_extra.json"), encoding="utf-8") as f:
            extra = _entries_of(json.load(f))
        out["entries"]["insta_sci"] = [{"id": e["n"], "from": e.get("from"), "fact_based": True, "data": e}
                                       for e in extra if isinstance(e.get("n"), int) and e["n"] >= 904]
        tp = os.path.join(root, "insta", "teardown_catalog.json")
        td = []
        if os.path.exists(tp):
            with open(tp, encoding="utf-8") as f:
                td = _entries_of(json.load(f))
        out["entries"]["insta_teardown"] = [{"id": e.get("n"), "from": e.get("from"), "fact_based": True, "data": e} for e in td]

    for name, fn in (("nt_shorts", nt_shorts), ("nt_longform", nt_longform), ("wb_gunghap", gunghap), ("wb_lf27", lf27),
                     ("insta", insta)):
        guard(name, fn)
    return out


def dump_tree(root: str, d0: dt.date, d1: dt.date) -> dict:
    """하위 프로세스로 dump(같은 이름 모듈이 두 트리에서 섞이지 않게)."""
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--dump", root, "--from", d0.isoformat(), "--to", d1.isoformat()],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        raise RuntimeError(f"편성표를 못 만들었다({root}): {r.stderr.strip()[-400:]}")
    return json.loads(r.stdout)


def base_tree(ref: str, repo: str = ROOT) -> str:
    """git archive <ref> 의 편성 모듈·catalog(*.py·*.json)만 임시 폴더에 꺼낸다."""
    r = subprocess.run(["git", "-C", repo, "archive", "--format=tar", ref, *DIRS], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git archive {ref} 실패: {r.stderr.decode('utf-8', 'replace').strip()[:300]} — git fetch origin 했나?")
    td = tempfile.mkdtemp(prefix="refill_base_")
    pat = re.compile(r"^(?:%s)/[^/]+\.(?:py|json)$" % "|".join(re.escape(d) for d in DIRS))
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for m in tf.getmembers():
            if m.isfile() and pat.match(m.name):
                dst = os.path.join(td, *m.name.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(tf.extractfile(m).read())
    return td


# ── 검사 ─────────────────────────────────────────────
def _date(v) -> dt.date | None:
    try:
        return dt.date.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        return None


def fact_errs(e: dict) -> list[str]:
    """사실 항목: sources 가 있고 fact 마다 {fact, src(출처 번호), evidence(원문 문장)}."""
    srcs = e.get("sources") or []
    errs = []
    if not srcs or not all(isinstance(u, str) and "https://" in u for u in srcs):
        errs.append("sources(https 주소) 없음")
    facts = e.get("facts") or []
    if not facts:
        errs.append("facts 없음")
    for k, f in enumerate(facts):
        if not isinstance(f, dict) or not isinstance(f.get("fact"), str):
            errs.append(f"facts[{k}] 는 {{fact, src, evidence}}")
            continue
        if not (isinstance(f.get("src"), int) and not isinstance(f.get("src"), bool) and 0 <= f["src"] < len(srcs)):
            errs.append(f"facts[{k}].src 는 sources 번호")
        if not (isinstance(f.get("evidence"), str) and f["evidence"].strip()):
            errs.append(f"facts[{k}].evidence(출처를 열어 옮긴 원문 문장) 없음")
    return errs


def ban_errs(stream: str, e: dict) -> list[str]:
    """줄기마다 이미 있는 금지어 목록(지금 트리 모듈)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    for p in DIRS:
        d = os.path.join(ROOT, *p.split("/"))
        if d not in sys.path:
            sys.path.insert(0, d)
    text = json.dumps(e, ensure_ascii=False)
    if stream == "nt_shorts":
        import rules as RU
        hits = {m.group(0) for rx in (RU.BANNED_TOPICS, RU.PROFANITY) for m in rx.finditer(text.replace("nine tails tales", ""))}
        return [f"금지 주제·말 {sorted(hits)}"] if hits else []
    if stream == "nt_longform":
        import tales as T
        hits = {m.group(0) for rx in (T.BANNED_TOPICS, T.FOLKLORE, T.BANNED) for m in rx.finditer(text)}
        return [f"금지 주제·말 {sorted(hits)}"] if hits else []
    if stream == "wb_gunghap":
        import theme_card
        hits = sorted({w for w in theme_card.BANNED if w in text})
        return [f"왕별이 금지어 {hits}"] if hits else []
    if stream == "wb_lf27":
        import longform_2027 as LF
        texts = [e.get("title") or "", e.get("angle") or "", *(e.get("thumb") or {}).values(), *(e.get("qa_seeds") or []),
                 *[c.get("title") or "" for c in e.get("chapters") or [] if isinstance(c, dict)]]
        hits = sorted({h for t in texts if isinstance(t, str) for h in LF.ban_hits(t)})
        return [f"금지어 {hits}"] if hits else []
    if stream in ("insta_sci", "insta_teardown"):
        import pick_reel as K                           # 숫자·출처·잔혹·실존 인물·프랜차이즈·상표·from 까지(entry_errs)
        return K.entry_errs(e)
    return []


def check(cur: dict, base: dict, today: dt.date, d0: dt.date, d1: dt.date) -> dict:
    """줄기마다 {new: [id…], errors: [...]} + 전체 errors."""
    tomorrow = today + dt.timedelta(days=1)
    res: dict = {"streams": {}, "errors": [f"지금 트리: {x}" for x in cur.get("errors", [])]
                 + [f"기준 트리: {x}" for x in base.get("errors", [])]}
    cutoff: dict[str, dt.date] = {}
    for s in STREAMS:
        ents = cur["entries"].get(s, [])
        old = {x["id"] for x in base["entries"].get(s, [])}
        errs = []
        ids = [x["id"] for x in ents]
        dup = sorted({str(i) for i in ids if ids.count(i) > 1})
        if dup:
            errs.append(f"번호가 겹친다 {dup}")
        new = [x for x in ents if x["id"] not in old]
        for x in new:
            f = _date(x.get("from"))
            if f is None:
                errs.append(f"{x['id']}: from(YYYY-MM-DD) 없음 — 새 항목은 from 을 단다")
            elif f < tomorrow:
                errs.append(f"{x['id']}: from {f} 는 내일({tomorrow}) 이후여야 한다 — 지난 날짜에 끼우면 편성이 바뀐다")
            if s == "nt_longform" and x["data"].get("date"):
                errs.append(f"{x['id']}: date 는 적지 않는다(from 만 — 일요일은 코드가 정한다)")
            if x.get("fact_based"):
                errs += [f"{x['id']}: {m}" for m in fact_errs(x["data"])]
            try:
                errs += [f"{x['id']}: {m}" for m in ban_errs(s, x["data"])]
            except Exception as ex:  # noqa: BLE001
                errs.append(f"{x['id']}: 금지어 검사 실패 {type(ex).__name__}: {ex}"[:200])
            if f:
                key = SCHEDULE_OF.get(s, s)
                cutoff[key] = min(cutoff.get(key, f), f)
        errs += [f"이어 가는 편 명세: {m}" for m in cur.get("spec_errors", {}).get(s, [])]
        res["streams"][s] = {"new": [x["id"] for x in new], "errors": errs}
    for key in sorted(set(cur["schedules"]) | set(base["schedules"])):
        a, b = base["schedules"].get(key, {}), cur["schedules"].get(key, {})
        cut = cutoff.get(key, d1).isoformat()
        changed = [k for k in sorted(set(a) | set(b)) if k[:10] < cut and a.get(k) != b.get(k)]
        if changed:
            k = changed[0]
            where = f"새 항목 from {cut} 전" if key in cutoff else f"새 항목 없음 · {d1.isoformat()} 전 전부"
            res["errors"].append(f"{key}: 정해진 편성이 바뀌었다({len(changed)}곳 · {where}) — 첫 곳 {k}: "
                                 f"{a.get(k)} → {b.get(k)} · 항목은 끝에 붙이고 from 을 단다(중간에 끼우기·순서 바꾸기·지우기 X)")
    res["ok"] = not res["errors"] and not any(v["errors"] for v in res["streams"].values())
    return res


def run(today: dt.date, days: int = 60, base: str = "origin/main", base_root: str | None = None, root: str = ROOT) -> dict:
    d0, d1 = today - dt.timedelta(days=LOOKBACK), today + dt.timedelta(days=days)
    br = base_root or base_tree(base)                     # git 기준은 늘 이 레포(--root 가 다른 폴더여도)
    res = check(dump_tree(root, d0, d1), dump_tree(br, d0, d1), today, d0, d1)
    res.update(date=today.isoformat(), base=base_root or base, window=[d0.isoformat(), d1.isoformat()])
    return res


def text(res: dict) -> str:
    o = [f"🧺 채우기 검사 — {res['date']}(KST) · 기준 {res['base']} · 편성 비교 {res['window'][0]} ~ {res['window'][1]}"]
    for s, v in res["streams"].items():
        mark = "❌" if v["errors"] else "✓"
        o.append(f"  {mark} {s}: 새 항목 {len(v['new'])}개" + (f" {v['new']}" if v["new"] else ""))
        o += [f"      - {m}" for m in v["errors"]]
    o += [f"  ❌ {m}" for m in res["errors"]]
    o.append("✅ 통과 — PR 을 열어도 된다(전체 테스트도 돌릴 것)" if res["ok"] else "❌ 고친 뒤 다시 — tools/REFILL.md")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="채우기(refill) 검사 — 새 항목 from · 지난 편성 그대로 · 사실 근거 · 금지어")
    ap.add_argument("--date", help="기준 날짜(KST 오늘이 기본) — 새 항목 from 은 이 다음 날 이후")
    ap.add_argument("--days", type=int, default=60, help="앞으로 며칠 편성을 비교할지(기본 60)")
    ap.add_argument("--base", default="origin/main", help="비교할 기준(git ref, 기본 origin/main)")
    ap.add_argument("--base-root", help="기준 트리 폴더(git 대신 — 테스트)")
    ap.add_argument("--root", default=ROOT, help="지금 트리 폴더(기본 이 레포)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dump", help=argparse.SUPPRESS)
    ap.add_argument("--from", dest="d_from", help=argparse.SUPPRESS)
    ap.add_argument("--to", dest="d_to", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.dump:
        print(json.dumps(dump(a.dump, dt.date.fromisoformat(a.d_from), dt.date.fromisoformat(a.d_to)), ensure_ascii=False, default=str))
        return 0
    today = dt.date.fromisoformat(a.date) if a.date else kst_today()
    try:
        res = run(today, a.days, a.base, a.base_root, a.root)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=1) if a.json else text(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
