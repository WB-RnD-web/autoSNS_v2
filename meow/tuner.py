#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""틀 자동 조정(2단계) — 성적(stats.json)으로 꼴 비율과 '결말 미리 보기' 켬/끔 비율을 하루 한 번 고친다 (2026-11-14).

왜: 11/14 사용자 "스스로 발전하는 형태로도 할 수 있나" → 추천안(2단계 + 정리 노트)에 "응 그렇게 해줘".
  1단계(분석 담당 #189)는 '다음 편 내용'만 배운다. 꼴의 비율(변신·밈·춤·게임)과 미리 보기는 사람이 정해 왔다.
  → 이 파일이 매일 기획 직전에 비율을 고친다. API 를 쓰지 않는다(코드가 정한다 — 루틴에게 맡기지 않는다).

안전장치(전부 코드):
  · 꼴마다 최소 15%(FLOOR) — 진 꼴도 계속 시험한다 · 하루에 10%p(STEP) 넘게 안 움직인다(가장 크게 움직이는 꼴 기준)
  · 2일 넘은 편이 8편(MIN_JUDGED) 안 되거나 성적이 36시간 넘게 묵었으면 그대로 둔다 · 꼴은 3편 넘게 있어야 점수를 낸다
  · 미리 보기 A/B: 켬·끔 각각 6편 넘게 · 점수 차 0.05 넘을 때만 이긴 쪽으로 · 진 쪽도 최소 15% 는 남긴다
  · 하루 한 번만(mix.json 의 date 가 오늘이면 다시 고치지 않는다 — 같은 날 예비 실행이 꼴을 바꾸지 않게)
  · 끄기: 레포 변수 MEOW_AUTOTUNE=0 → plan_api 가 mix.json 을 안 보고 예전처럼(a=변신 · 나머지 요일 순환).

점수(편마다): 2일 넘은 편끼리 조회수 순위(0~1)와 평균 시청 % 순위(0~1)의 평균. 조회수 20회 안 되는 편은
  평균 시청 % 가 우연이라 조회수 순위만 쓴다(피드가 안 받아 준 것 자체가 나쁜 성적이다).

    python meow/tuner.py tune --dir <기획 폴더(data/meow)> --day 2026-11-15
      → <기획 폴더>/mix.json {date, weights{morph,meme,dance,game}, tease_off, why[], basis{}, log[]}
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyst as AN  # noqa: E402

FORMATS = ("morph", "meme", "dance", "game")       # 순서 = 동점일 때 먼저(변신이 간판)
MIX = "mix.json"
FLOOR = 0.15
STEP = 0.10
MIN_JUDGED = 8
MIN_PER_FORMAT = 3
MIN_PER_ARM = 6
ARM_GAP = 0.05
TEASE_FLOOR = 0.15
STALE_H = 36
LOG_MAX = 60
START = {"weights": {f: 0.25 for f in FORMATS}, "tease_off": 0.5}


# ── 성적 → 점수 ──
def _ranks(vals: list[float]) -> list[float]:
    """순위 0~1(같은 값은 평균 순위) · 하나뿐이면 0.5."""
    n = len(vals)
    if n == 1:
        return [0.5]
    out = []
    for v in vals:
        lo = sum(x < v for x in vals)
        eq = sum(x == v for x in vals) - 1
        out.append((lo + eq / 2) / (n - 1))
    return out


def scored(stats: dict | None, now: dt.datetime) -> list[dict]:
    """2일 넘고 꼴을 아는 편 → [{video, format, tease, views, avg_pct, s}]."""
    vids = [v for v in (stats or {}).get("videos") or []
            if AN._age_h(v, now) >= AN.JUDGE_AGE_H and v.get("format") in FORMATS]
    if not vids:
        return []
    rv = _ranks([float(v.get("views", 0)) for v in vids])
    sure = [v for v in vids if v.get("views", 0) >= AN.JUDGE_MIN_VIEWS]
    rp = dict(zip([v["video"] for v in sure], _ranks([float(v.get("avg_pct", 0)) for v in sure]))) if sure else {}
    out = []
    for v, r in zip(vids, rv):
        s = (r + rp[v["video"]]) / 2 if v["video"] in rp else r
        out.append({"video": v["video"], "format": v.get("format"), "tease": v.get("tease"),     # None = A/B 전(비교에서 뺀다)
                    "views": v.get("views", 0), "avg_pct": v.get("avg_pct", 0), "s": round(s, 3)})
    return out


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def format_scores(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for f in FORMATS:
        ss = [r["s"] for r in rows if r["format"] == f]
        out[f] = {"n": len(ss), "score": _mean(ss) if len(ss) >= MIN_PER_FORMAT else None}
    return out


def format_target(fs: dict[str, dict]) -> dict[str, float]:
    """점수 제곱에 비례 + 바닥 15%(모르는 꼴은 0.5 = 보통)."""
    sq = {f: (fs[f]["score"] if fs[f]["score"] is not None else 0.5) ** 2 for f in FORMATS}
    tot = sum(sq.values()) or 1.0
    room = 1.0 - FLOOR * len(FORMATS)
    return {f: FLOOR + room * sq[f] / tot for f in FORMATS}


def toward(cur: dict, target: dict, step: float = STEP) -> dict:
    """target 쪽으로 — 가장 크게 움직이는 칸이 step 을 넘지 않게 같은 비율로 줄인다(합 1·바닥은 그대로 지켜진다)."""
    gap = max(abs(target[k] - cur[k]) for k in cur)
    lam = 1.0 if gap <= step else step / gap
    return {k: round(cur[k] + lam * (target[k] - cur[k]), 4) for k in cur}


def tease_arms(rows: list[dict]) -> dict:
    on = [r["s"] for r in rows if r["tease"] is True]           # A/B 가 정한 편만(기획에 tease 가 적힌 편)
    off = [r["s"] for r in rows if r["tease"] is False]
    return {"on": {"n": len(on), "score": _mean(on)}, "off": {"n": len(off), "score": _mean(off)}}


# ── 하루 비율 → 편마다 꼴 · 미리 보기 ──
def _order(day: dt.date) -> list[str]:
    k = day.toordinal() % len(FORMATS)               # 동점 깨기를 날마다 돌린다(편이 적은 날 늘 같은 꼴이 빠지지 않게)
    return list(FORMATS[k:] + FORMATS[:k])


def counts(weights: dict, n: int, day: dt.date) -> dict[str, int]:
    """편 n개를 비율대로(최대 나머지 방식)."""
    tot = sum(weights.get(f, 0) for f in FORMATS) or 1.0
    raw = {f: weights.get(f, 0) / tot * n for f in FORMATS}
    c = {f: math.floor(raw[f]) for f in FORMATS}
    order = _order(day)
    for f in sorted(FORMATS, key=lambda f: (-(raw[f] - c[f]), order.index(f)))[: n - sum(c.values())]:
        c[f] += 1
    return c


def sequence(weights: dict, n: int, day: dt.date) -> list[str]:
    """편 순서대로 꼴 — 첫 편(a · 인스타로 가는 편)은 비율이 가장 큰 꼴 · 나머지는 고르게 섞고 날마다 돌린다."""
    if n <= 0:
        return []
    c = counts(weights, n, day)
    acc = {f: 0 for f in FORMATS}
    seq = []
    for _ in range(n):                                 # 부드러운 가중 라운드 로빈(같은 꼴이 몰리지 않게)
        for f in FORMATS:
            acc[f] += c[f]
        best = max(FORMATS, key=lambda f: (acc[f], -FORMATS.index(f)))     # 동점이면 변신 먼저(첫 편 = 간판)
        acc[best] -= n
        seq.append(best)
    head, rest = seq[0], seq[1:]
    if rest:
        k = day.toordinal() % len(rest)
        rest = rest[k:] + rest[:k]
    return [head] + rest


def tease_off_slots(tease_off: float, day: dt.date, slots: list[str]) -> set[str]:
    """미리 보기를 끌 편 — 정확히 round(비율 × 편 수)개 · 날짜·편으로 정한 해시 순서(다시 돌려도 같다)."""
    k = round(max(0.0, min(1.0, tease_off)) * len(slots))
    ranked = sorted(slots, key=lambda s: hashlib.sha1(f"{day.isoformat()}-{s}-tease".encode()).hexdigest())
    return set(ranked[:k])


def load(data_dir: str) -> dict | None:
    try:
        with open(os.path.join(data_dir, MIX), encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m.get("weights"), dict) else None
    except (OSError, ValueError, AttributeError):
        return None


def enabled() -> bool:
    return os.environ.get("MEOW_AUTOTUNE", "1") != "0"


def slots_today(all_slots: tuple) -> list[str]:
    want = (os.environ.get("MEOW_SLOTS") or " ".join(all_slots)).split()
    return [s for s in want if s in all_slots] or list(all_slots)


def plan_for(data_dir: str | None, day: dt.date, slot: str, all_slots: tuple) -> dict | None:
    """plan_api 가 부른다 → {"format", "tease"} 또는 None(자동 조정 꺼짐·mix.json 없음·오늘 안 쓰는 편 → 예전 방식)."""
    if not data_dir or not enabled():
        return None
    m = load(data_dir)
    sl = slots_today(all_slots)
    if m is None or slot not in sl:
        return None
    try:                       # mix.json 이 망가져도 그날 기획은 멈추지 않는다(예전 방식으로)
        w = {f: float(m["weights"].get(f, 0)) for f in FORMATS}
        if sum(w.values()) <= 0:
            raise ValueError("비율 합이 0")
        return {"format": sequence(w, len(sl), day)[sl.index(slot)],
                "tease": slot not in tease_off_slots(float(m.get("tease_off", START["tease_off"])), day, sl)}
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as e:
        print(f"   ⚠️ mix.json 을 못 읽어 예전 방식으로: {e}", file=sys.stderr)
        return None


# ── 하루 한 번 고치기 ──
def _stats_age_h(stats: dict | None, now: dt.datetime) -> float:
    try:
        return (now - dt.datetime.fromisoformat(stats["at"])).total_seconds() / 3600
    except (TypeError, KeyError, ValueError):
        return 1e9


def _pct(w: dict) -> str:
    return " · ".join(f"{f} {round(100 * w[f])}%" for f in FORMATS)


def tune(data_dir: str, day: dt.date, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    prev = load(data_dir) or {**copy.deepcopy(START), "date": None, "log": []}
    if prev.get("date") == day.isoformat():
        return {**prev, "kept": True}
    stats = AN.load(data_dir)
    rows = scored(stats, now)
    fs, arms = format_scores(rows), tease_arms(rows)
    w0 = {f: float(prev["weights"].get(f, 0.25)) for f in FORMATS}
    t0 = float(prev.get("tease_off", START["tease_off"]))
    w1, t1, why = dict(w0), t0, []
    if stats is None:
        why.append("성적(stats.json) 없음 — 비율 그대로")
    elif _stats_age_h(stats, now) > STALE_H:
        why.append(f"성적이 {STALE_H}시간 넘게 묵었다(분석 담당 실패?) — 비율 그대로")
    elif len(rows) < MIN_JUDGED:
        why.append(f"2일 넘은 편 {len(rows)}편 < {MIN_JUDGED} — 비율 그대로(아직 이르다)")
    else:
        if sum(fs[f]["score"] is not None for f in FORMATS) >= 2:
            w1 = toward(w0, format_target(fs))
            why.append("꼴 점수 " + " · ".join(f"{f} {fs[f]['score'] if fs[f]['score'] is not None else '-'}({fs[f]['n']}편)"
                                               for f in FORMATS) + f" → {_pct(w1)}")
        else:
            why.append("점수 낼 수 있는 꼴(3편 넘게)이 둘 안 됨 — 꼴 비율 그대로")
        on, off = arms["on"], arms["off"]
        if on["n"] >= MIN_PER_ARM and off["n"] >= MIN_PER_ARM:
            gap = off["score"] - on["score"]
            if abs(gap) >= ARM_GAP:
                goal = 1 - TEASE_FLOOR if gap > 0 else TEASE_FLOOR
                t1 = toward({"x": t0}, {"x": goal})["x"]
                why.append(f"미리 보기 켬 {on['score']}({on['n']}편) vs 끔 {off['score']}({off['n']}편) → "
                           f"{'끈 쪽' if gap > 0 else '켠 쪽'}이 낫다 · 끄는 편 {round(100 * t0)}% → {round(100 * t1)}%")
            else:
                why.append(f"미리 보기 켬 {on['score']} vs 끔 {off['score']} — 차이 {ARM_GAP} 안 됨 · 그대로")
        else:
            why.append(f"미리 보기 A/B 편 수 모자람(켬 {on['n']} · 끔 {off['n']} · 각 {MIN_PER_ARM}편 필요) — 그대로")
    out = {"date": day.isoformat(), "weights": w1, "tease_off": t1, "why": why,
           "basis": {"stats_at": (stats or {}).get("at"), "judged": len(rows), "formats": fs, "tease": arms}}
    out["log"] = ((prev.get("log") or []) + [{"date": day.isoformat(), "weights": w1, "tease_off": t1, "why": why}])[-LOG_MAX:]
    with open(os.path.join(data_dir, MIX), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return {**out, "prev": {"weights": w0, "tease_off": t0}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="틀 자동 조정 — 꼴 비율·미리 보기 켬/끔 비율(mix.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tune")
    t.add_argument("--dir", required=True)
    t.add_argument("--day", required=True)
    a = ap.parse_args(argv)
    m = tune(a.dir, dt.date.fromisoformat(a.day))
    if m.get("kept"):
        print(f"🎛️ {a.day} 비율은 이미 정했다 — {_pct(m['weights'])} · 미리 보기 끄는 편 {round(100 * m['tease_off'])}%")
        return 0
    print(f"🎛️ {a.day} 꼴 {_pct(m['weights'])} · 미리 보기 끄는 편 {round(100 * m['tease_off'])}%")
    for x in m["why"]:
        print("   -", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
