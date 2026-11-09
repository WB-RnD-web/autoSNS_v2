#!/usr/bin/env python3
"""Meow Remix 매일 한 편 — 그림 → 그림 검수 → HD 영상 → 영상 검수 → 조립(2026-11-09).

기획은 plan_api.py 가 data/meow/<날짜>.json 에 쓴다(편 하나 · 2컷째는 1컷 그림을 edit = 같은 고양이).
여기서는 render.py 를 차례로 부르고 검수 결과·고친 것을 작업 폴더의 qa.json 에 남긴다(예비 실행이 이어 받는다).

    python meow/daily.py render <날짜>.json [--no-qa]
      종료 코드 0 = 완성(output/meow/<stem>.mp4) · 3 = 검수에 두 번 걸려 그날은 안 올림 · 75 = 05:45~08:00 KST(다음 실행이 잇는다)
    python meow/daily.py day                     # 오늘(KST) 날짜

검수 규칙(qa_api.py — 키가 없거나 API 가 실패하면 검수 없이 간다):
  · 그림: 걸린 컷은 검수가 준 fix 글·새 seed 로 한 번 다시 그린다(그 컷에서 편집한 컷도 다시). 그래도 걸리면 영상 검수에 맡긴다.
  · 영상: 걸린 클립은 새 seed 로 한 번 다시 만든다(HD 약 16분). 그래도 걸리면 그날은 올리지 않는다(종료 코드 3).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qa_api as Q  # noqa: E402
import render as R  # noqa: E402

BUMP = 1000                     # 다시 만들 때 seed 를 이만큼 옮긴다


def today(now: dt.datetime | None = None) -> str:
    return (now or dt.datetime.now(R.KST)).astimezone(R.KST).date().isoformat()


def qa_path(c: dict) -> str:
    return os.path.join(R.WORK, R.stem(c), "qa.json")


def load_state(c: dict) -> dict:
    p = qa_path(c)
    return R.load(p) if os.path.exists(p) else {"fixes": {}}


def save_state(c: dict, st: dict) -> None:
    os.makedirs(os.path.dirname(qa_path(c)), exist_ok=True)
    with open(qa_path(c), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def apply_fixes(c: dict, st: dict) -> None:
    """검수가 고친 글·seed 를 기획에 덮는다(예비 실행도 같은 것으로 잇게)."""
    for k, fx in st.get("fixes", {}).items():
        s = c["shots"][int(k) - 1]
        if fx.get("text"):
            s["edit" if s.get("edit") else "image"] = fx["text"]
        for key in ("seed", "vseed"):
            if fx.get(key) is not None:
                s[key] = fx[key]


def dependents(c: dict, i: int) -> list[int]:
    """컷 i 그림에서 (이어서) 편집한 컷들."""
    out, src = [], {i}
    for j, s in enumerate(c["shots"], 1):
        if j > i and s.get("edit") and int(s.get("from", 1)) in src:
            out.append(j)
            src.add(j)
    return out


def _rm(p: str) -> None:
    if os.path.exists(p):
        os.remove(p)


def fix_stills(c: dict, st: dict, bad: list[dict]) -> None:
    for r in bad:
        i = r["shot"]
        fx = st["fixes"].setdefault(str(i), {})
        if r.get("fix") and not R.BANNED.search(r["fix"]):
            fx["text"] = r["fix"]
        fx["seed"] = c["seed"] + i + BUMP
        for j in [i] + dependents(c, i):
            st["fixes"].setdefault(str(j), {}).setdefault("seed", c["seed"] + j + BUMP)
            _rm(R.shot_png(c, j))
            _rm(R.clip_path(c, j))


def render(doc: dict, qa: bool = True) -> int:
    if doc.get("skip") or not doc.get("concepts"):
        print(f"⏭️ {doc.get('date')} 기획 없음: {doc.get('skip', '편 없음')}")
        return 0
    errs = R.check(doc)
    if errs:
        print("❌ 검사 실패\n  " + "\n  ".join(errs))
        return 1
    c = doc["concepts"][0]
    st = load_state(c)
    apply_fixes(c, st)
    if st.get("blocked"):
        print(f"⛔ {R.stem(c)} 이미 검수에서 막힘: {st['blocked']}")
        return 3
    try:
        R.images(c)
        if qa and "stills" not in st:
            res = Q.review_stills(c)
            bad = Q.flagged(res, "shots")
            st["stills"] = res or {"skipped": "키 없음 또는 API 실패"}
            if bad:
                print(f"   그림 검수: 컷 {[r['shot'] for r in bad]} 다시 그림 — " + " | ".join(
                    "; ".join(r["issues"]) for r in bad)[:400], flush=True)
                fix_stills(c, st, bad)
                st["stills_bad"] = [r["shot"] for r in bad]
            save_state(c, st)
            apply_fixes(c, st)
            R.images(c)
        if qa and st.get("stills_bad") and "stills2" not in st:
            st["stills2"] = Q.review_stills(c) or {"skipped": "API 실패"}
            left = Q.flagged(st["stills2"], "shots")
            if left:
                print("   ⚠️ 다시 그려도 걸림(영상 검수에 맡긴다): " + " | ".join("; ".join(r["issues"]) for r in left)[:300])
            save_state(c, st)

        R.clips(c)
        if qa and "clips" not in st:
            res = Q.review_clips(c)
            bad = Q.flagged(res, "clips")
            st["clips"] = res or {"skipped": "키 없음 또는 API 실패"}
            if bad:
                print(f"   영상 검수: 클립 {[r['clip'] for r in bad]} 다시 만듦 — " + " | ".join(
                    "; ".join(r["issues"]) for r in bad)[:400], flush=True)
                for r in bad:
                    st["fixes"].setdefault(str(r["clip"]), {})["vseed"] = c["seed"] + r["clip"] + BUMP
                    _rm(R.clip_path(c, r["clip"]))
                st["clips_bad"] = [r["clip"] for r in bad]
            save_state(c, st)
            apply_fixes(c, st)
            R.clips(c)
        if qa and st.get("clips_bad") and "clips2" not in st:
            res = Q.review_clips(c, st["clips_bad"])
            st["clips2"] = res or {"skipped": "API 실패"}
            left = Q.flagged(res, "clips")
            if left:
                st["blocked"] = " | ".join(f"클립{r['clip']}: " + "; ".join(r["issues"]) for r in left)[:600]
            save_state(c, st)
            if left:
                print(f"⛔ {R.stem(c)} 다시 만들어도 검수에 걸림 — 오늘은 올리지 않는다: {st['blocked']}")
                return 3
    except R.QuietHours:
        save_state(c, st)
        return 75
    m = R.build(c)
    usd = sum(float((st.get(k) or {}).get("usd") or 0) for k in ("stills", "stills2", "clips", "clips2"))
    print(f"✅ {m['stem']} {m['sec']}초 → {m['video']} · 검수 약 {usd:.3f}달러")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Meow Remix 매일 한 편")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("doc")
    r.add_argument("--no-qa", action="store_true")
    sub.add_parser("day")
    a = ap.parse_args()
    if a.cmd == "day":
        print(today())
        return 0
    return render(R.load(a.doc), qa=not a.no_qa)


if __name__ == "__main__":
    sys.exit(main())
