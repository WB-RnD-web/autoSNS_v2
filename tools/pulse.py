#!/usr/bin/env python3
"""채널 맥박 — 우리 두 채널이 오르는지·내리는지·그게 며칠째인지를 매일 숫자로 낸다.

    python tools/pulse.py build --radar <data/trend-radar 를 푼 폴더> --out output/pulse [--date YYYY-MM-DD]
        → output/pulse/<날짜>/pulse.json  (숫자·플래그·실험 달력·트렌드·어제 예측 채점)
    python tools/pulse.py check output/pulse/<날짜>
        → 분석 루틴이 쓴 fill.json 을 검사하고 report.md · page.html 을 만든다. 못 넘으면 종료 코드 1.
    python tools/pulse.py pr output/pulse/<날짜> --field slug|title|branch|body

역할 나누기 — ★루틴에게 '숫자를 정확히 써라'는 지켜지지 않는다. 숫자는 전부 이 파일이 낸다.
  - 이 파일: 하루 조회(24시간 환산)·추세와 며칠째인지·형식별 첫 24시간·문제 신호(플래그)와 며칠째 이어지는지·
    실험 남은 날·어제 예측 채점.
  - 분석 루틴(Opus, tools/PULSE.md): fill.json 에 해석만 — 요약·근거/추측·방향 판정·트렌드·할 일·PR 제안·내일 예측.
  - 워크플로(.github/workflows/pulse.yml): routine/pulse push 를 받아 다시 검사하고, PR 제안이 있으면
    모든 테스트를 돌린 뒤 pulse/<날짜>-<slug> 브랜치와 PR 을 만든다.
데이터: data/trend-radar(트렌드 레이더가 매일 아침 모은다)의 registry.json(영상별 조회수 스냅숏 — 게시 30일 안 영상만
  매일 갱신)과 channels.json(채널 전체 조회수·구독자 스냅숏). 유튜브 API 를 직접 부르지 않는다(루틴 환경엔 토큰이 없다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import shutil
import statistics
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FORMATS = os.path.join(HERE, "pulse_formats.json")
EXPERIMENTS = os.path.join(HERE, "pulse_experiments.json")
REPO = "WB-RnD-web/autoSNS_v2"
UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))

SHORT_MAX = 180          # 쇼츠 = 3분까지(트렌드 레이더와 같다)
UP, DOWN = 1.05, 0.95    # 3일 이동평균이 전날보다 5% 넘게 오르면 '오름', 5% 넘게 내리면 '내림'
STALE_H = 30             # 레이더 데이터가 이보다 오래되면 DATA_STALE
COLD, HOT, HOT_MIN = 0.5, 3.0, 1000
NEW_H = 36               # '새 영상' = 게시 36시간 안
PR_MIN_DAYS = 3          # PR 근거 플래그는 3일 이상 이어진 것(실험 판정일 EXP_DUE 는 예외)
PATCH_MAX_LINES = 400
# 분석 루틴의 PR 이 건드리면 안 되는 곳 — 업로드 경로·토큰·맥박 자신(검사기를 스스로 느슨하게 못 하게)
FORBIDDEN = (".github/", "output/", "pipeline/secrets/", "tools/pulse.py", "tools/test_pulse.py", "tools/PULSE.md")
LEVELS = ("bad", "warn", "good", "info")
VERDICTS = ("맞다", "틀리다", "아직 모름")
WHO = ("pr", "local", "user", "watch")
OPS = (">=", "<=")
TREND_LABELS = {"떡상": 0, "강세": 1, "식는 중": 2, "끝물": 3}
WEEKDAY = "월화수목금토일"


# ── 작은 도구 ────────────────────────────────────────────
def load(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def parse_t(s: str) -> dt.datetime:
    s = s.replace("Z", "+00:00")
    if len(s) == 13:            # 레이더 스탬프 '2026-10-05T00'(UTC 시)
        s += ":00+00:00"
    t = dt.datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def kst_day(t: dt.datetime) -> str:
    return t.astimezone(KST).date().isoformat()


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def rnd(x, n=0):
    return None if x is None else (round(x) if n == 0 else round(x, n))


def man(n) -> str:
    """조회수를 한국식으로: 187,000 → 18.7만 · 4,200 → 4,200."""
    if n is None:
        return "–"
    n = float(n)
    if abs(n) >= 10000:
        v = n / 10000
        return f"{v:.1f}만".replace(".0만", "만") if abs(v) < 100 else f"{v:,.0f}만"
    return f"{n:,.0f}"


def load_formats(path: str = FORMATS) -> dict:
    return load(path, {})["channels"]


def classify(rec: dict, rules: list) -> str:
    """pulse_formats.json 규칙 중 처음 맞는 것의 key. 아무것도 안 맞으면 'etc'."""
    title = rec.get("title", "")
    pub = parse_t(rec["pub"])
    d = rec.get("dur", 0) or 0
    short = 0 < d <= SHORT_MAX
    day = kst_day(pub)
    k = pub.astimezone(KST)
    m = k.hour * 60 + k.minute
    for r in rules:
        if r.get("dur") == "short" and not short or r.get("dur") == "long" and short:
            continue
        if "title_prefix" in r and not title.startswith(r["title_prefix"]):
            continue
        if "title_re" in r and not re.search(r["title_re"], title):
            continue
        if "kst_min" in r and not any(a <= m <= b for a, b in r["kst_min"]):
            continue
        if "before" in r and not day < r["before"]:
            continue
        if "after" in r and not day >= r["after"]:
            continue
        return r["key"]
    return "etc"


def labels(rules: list) -> dict:
    return {r["key"]: r["label"] for r in rules} | {"etc": "기타"}


# ── 시계열 ───────────────────────────────────────────────
def day_ends(stamps) -> dict:
    """KST 날짜 → 그날 마지막 스냅숏 스탬프(손으로 한 번 더 돌린 날도 하루 하나로)."""
    out = {}
    for s in sorted(stamps):
        out[kst_day(parse_t(s))] = s
    return out


def video_series(recs: dict) -> list[dict]:
    """하루 조회 증가(24시간 환산) — 추적 중(게시 30일 안) 영상의 합. 날짜 = 그 구간이 끝난 아침의 KST 날짜.
    새 영상은 앞 스냅숏 뒤에 올라왔으면 전부 증가로 친다. 앞 스냅숏 전부터 있었는데 기록이 없던 영상은 뺀다."""
    ends = day_ends({s for r in recs.values() for s in r.get("views", {})})
    days = sorted(ends)
    out = []
    for da, db in zip(days, days[1:]):
        a, b = ends[da], ends[db]
        ta, tb = parse_t(a), parse_t(b)
        h = (tb - ta).total_seconds() / 3600
        if h <= 0:
            continue
        per = {}
        for vid, r in recs.items():
            v = r.get("views", {})
            if b not in v:
                continue
            if a in v:
                per[vid] = max(0, v[b] - v[a])
            elif parse_t(r["pub"]) > ta:
                per[vid] = v[b]
        k = 24 / h
        out.append({"d": db, "views": round(sum(per.values()) * k), "hours": round(h, 1),
                    "per": {x: round(g * k) for x, g in per.items()}})
    return out


def channel_series(snaps: dict) -> list[dict]:
    """채널 전체 조회수·구독자 스냅숏 → 하루 증가(24시간 환산)."""
    ends = day_ends(snaps)
    days = sorted(ends)
    out = []
    for da, db in zip(days, days[1:]):
        a, b = snaps[ends[da]], snaps[ends[db]]
        h = (parse_t(ends[db]) - parse_t(ends[da])).total_seconds() / 3600
        if h <= 0:
            continue
        k = 24 / h
        subs_d = None
        if a.get("subs") is not None and b.get("subs") is not None:
            subs_d = round((b["subs"] - a["subs"]) * k)
        out.append({"d": db, "views": round(max(0, b["views"] - a["views"]) * k), "subs": b.get("subs"),
                    "subs_d": subs_d, "hours": round(h, 1)})
    return out


def trend(vals: list) -> dict:
    """3일 이동평균의 날마다 방향 → 지금 흐름(오름/내림/보합)과 그 흐름이 며칠째인지.
    며칠째 = 마지막으로 반대 방향이었던 날 다음부터 오늘까지(중간의 보합 날 포함)."""
    n = len(vals)
    if n < 3:
        return {"state": "short", "streak": 0, "today": None, "days": n}
    ma = [statistics.fmean(vals[max(0, i - 2): i + 1]) for i in range(n)]
    dirs = []
    for p, c in zip(ma, ma[1:]):
        r = c / max(1.0, p)
        dirs.append("up" if r >= UP else "down" if r <= DOWN else "flat")
    state = next((d for d in reversed(dirs) if d != "flat"), "flat")
    opp = {"up": "down", "down": "up"}.get(state)
    streak = 0
    for d in reversed(dirs):
        if d == opp:
            break
        streak += 1
    return {"state": state, "streak": streak, "today": dirs[-1], "days": n}


def window(vals: list) -> dict | None:
    """최근 k일 평균 vs 그 전 k일 평균(k = 7, 기록이 짧으면 절반)."""
    k = min(7, len(vals) // 2)
    if k < 1:
        return None
    cur, prev = statistics.fmean(vals[-k:]), statistics.fmean(vals[-2 * k:-k])
    return {"k": k, "cur": round(cur), "prev": round(prev), "ratio": round(cur / max(1.0, prev), 2)}


def views_at(rec: dict, age_d: float) -> float | None:
    """게시 후 age_d 일 때 조회수(앞뒤 스냅숏 사이 선형 보간, 게시 순간 = 0회).
    앞뒤 간격이 1.6일보다 넓으면 믿지 않는다(None)."""
    pub = parse_t(rec["pub"])
    s = [(0.0, 0)] + sorted(((parse_t(k) - pub).total_seconds() / 86400, v) for k, v in rec.get("views", {}).items())
    for (a1, v1), (a2, v2) in zip(s, s[1:]):
        if a1 <= age_d <= a2 and a2 - a1 <= 1.6:
            return v1 + (v2 - v1) * (age_d - a1) / max(1e-9, a2 - a1)
    return None


def latest(rec: dict) -> int:
    v = rec.get("views", {})
    return v[max(v)] if v else 0


# ── 채널 하나 ─────────────────────────────────────────────
def analyze_channel(key: str, spec: dict, reg: dict, chans: dict, at: dt.datetime) -> dict:
    rules = spec["rules"]
    lab = labels(rules)
    recs = {v: r for v, r in reg.items() if r.get("ch") == spec["id"]}
    fk = {v: classify(r, rules) for v, r in recs.items()}
    age = {v: (at - parse_t(r["pub"])).total_seconds() / 86400 for v, r in recs.items()}

    vs = video_series(recs)
    cs = channel_series(chans.get(spec["id"], {}).get("snaps", {}))
    basis = "channel" if len(cs) >= 4 else "videos"
    main = cs if basis == "channel" else vs
    vals = [x["views"] for x in main]
    tr = trend(vals)
    win = window(vals)
    peak = max(main, key=lambda x: x["views"]) if main else None

    # 형식별 첫 24시간 조회 — 지난 7일(게시 1~8일 전) vs 그 전 7일, 그리고 30일 기준선
    fmts = []
    for k in sorted(set(fk.values()), key=lambda k: [r["key"] for r in rules].index(k) if k in lab and k != "etc" else 99):
        vids = [v for v in recs if fk[v] == k]
        m24 = {v: views_at(recs[v], 1.0) for v in vids}
        cur = [m24[v] for v in vids if 1 <= age[v] < 8]
        prev = [m24[v] for v in vids if 8 <= age[v] < 15]
        base = [m24[v] for v in vids if 1 <= age[v] < 31]
        fmts.append({"key": k, "label": lab.get(k, k), "n7": sum(age[v] < 7 for v in vids),
                     "med24": rnd(med(cur)), "n24": sum(x is not None for x in cur),
                     "prev24": rnd(med(prev)), "nprev": sum(x is not None for x in prev),
                     "base24": rnd(med(base)), "nbase": sum(x is not None for x in base)})
    fby = {f["key"]: f for f in fmts}

    # 오늘 조회를 끈 형식(마지막 하루, 추적 영상 기준)
    drivers, movers = [], []
    if vs:
        per = vs[-1]["per"]
        tot = max(1, sum(per.values()))
        g = {}
        for v, x in per.items():
            g.setdefault(fk[v], [0, 0])
            g[fk[v]][0] += x
            g[fk[v]][1] += 1
        drivers = [{"key": k, "label": lab.get(k, k), "gain": x, "share": round(x / tot, 3), "n": n}
                   for k, (x, n) in sorted(g.items(), key=lambda kv: -kv[1][0]) if x > 0][:8]
        for v, x in sorted(per.items(), key=lambda kv: -kv[1])[:6]:
            if x <= 0:
                break
            movers.append({"id": v, "title": recs[v].get("title", "")[:90], "fmt": lab.get(fk[v], fk[v]),
                           "gain": x, "views": latest(recs[v]), "age_d": round(age[v], 1)})

    # 새 영상(36시간 안) — 같은 형식 다른 영상의 '같은 나이' 조회 중앙값과 비교
    new = []
    for v in sorted((v for v in recs if age[v] * 24 < NEW_H), key=lambda v: recs[v]["pub"], reverse=True):
        a = age[v]
        peers = [views_at(recs[p], a) for p in recs if p != v and fk[p] == fk[v] and 1 <= age[p] < 31]
        exp = med(peers)
        nv = latest(recs[v])
        new.append({"id": v, "title": recs[v].get("title", "")[:90], "fmt": lab.get(fk[v], fk[v]),
                    "age_h": round(a * 24), "views": nv, "expect": rnd(exp),
                    # 평소가 20회도 안 되면 배수는 뜻이 없다(0회 대비 423배 같은 숫자) — 표본 3편 이상·평소 20회 이상일 때만
                    "ratio": round(nv / exp, 2) if exp is not None and exp >= 20 and len([p for p in peers if p is not None]) >= 3 else None})

    # 업로드 수(게시 KST 날짜)
    up = {}
    for v, r in recs.items():
        up[kst_day(parse_t(r["pub"]))] = up.get(kst_day(parse_t(r["pub"])), 0) + 1
    subs = None
    if cs:
        s7 = [x["subs"] for x in cs[-8:] if x.get("subs") is not None]
        subs = {"now": cs[-1].get("subs"), "d1": cs[-1].get("subs_d"),
                "d7": (s7[-1] - s7[0]) if len(s7) >= 2 else None, "days": len(s7)}
    last_pub = max((parse_t(r["pub"]) for r in recs.values()), default=None)
    return {
        "key": key, "name": spec["name"], "id": spec["id"], "basis": basis,
        "series": [{"d": x["d"], "views": x["views"], "hours": x["hours"]} for x in main[-21:]],
        "series_videos": [{"d": x["d"], "views": x["views"]} for x in vs[-21:]],
        "today": main[-1]["views"] if main else None, "today_d": main[-1]["d"] if main else None,
        "trend": tr, "window": win,
        "peak": {"d": peak["d"], "views": peak["views"]} if peak else None,
        "vs_peak": round(main[-1]["views"] / max(1, peak["views"]), 2) if peak else None,
        "subs": subs, "formats": fmts, "drivers": drivers, "movers": movers, "new": new,
        "uploads": {d: up[d] for d in sorted(up)[-14:]},
        "uploads_7d": sum(a < 7 for a in age.values()),
        "last_pub_h": round((at - last_pub).total_seconds() / 3600) if last_pub else None,
        "_m24": {v: views_at(recs[v], 1.0) for v in recs}, "_fk": fk, "_age": age, "_fby": fby,
    }


# ── 플래그(문제·기회 신호) ─────────────────────────────────
def channel_flags(c: dict) -> list[dict]:
    out = []
    k, nm = c["key"], c["name"]
    tr, win = c["trend"], c["window"]
    wtxt = f"최근 {win['k']}일 평균 {man(win['cur'])} · 그 전 {win['k']}일의 ×{win['ratio']}" if win else "기록 짧음"
    if tr["state"] == "up" and (tr["streak"] >= 3 or win and win["ratio"] >= 1.5):
        out.append({"id": f"CH_UP:{k}", "level": "good", "text": f"{nm} 하루 조회 상승 {tr['streak']}일째 ({wtxt})"})
    if tr["state"] == "down" and (tr["streak"] >= 3 or win and win["ratio"] <= 0.7):
        out.append({"id": f"CH_DOWN:{k}", "level": "bad", "text": f"{nm} 하루 조회 하락 {tr['streak']}일째 ({wtxt})"})
    if c["last_pub_h"] is not None and c["last_pub_h"] > NEW_H and c["uploads_7d"] >= 5:
        out.append({"id": f"NO_UPLOAD:{k}", "level": "bad",
                    "text": f"{nm} 마지막 업로드 {c['last_pub_h']}시간 전 — 지난 7일엔 {c['uploads_7d']}편이었다(발행이 멈췄나?)"})
    s = c.get("subs")
    if s and s.get("d7") is not None and s["d7"] < 0:
        out.append({"id": f"SUBS_DOWN:{k}", "level": "warn", "text": f"{nm} 구독자 {s['days']}일 사이 {s['d7']:+d} (지금 {s['now']:,})"})
    fby, fk, m24, age = c["_fby"], c["_fk"], c["_m24"], c["_age"]
    for f in c["formats"]:
        base = f["base24"]
        if not base or f["nbase"] < 6:
            continue
        vids = sorted((v for v in fk if fk[v] == f["key"] and m24[v] is not None and 1 <= age[v] < 31), key=lambda v: age[v])
        last3 = vids[:3]
        if len(last3) == 3 and all(m24[v] < COLD * base for v in last3):
            out.append({"id": f"FMT_COLD:{k}:{f['key']}", "level": "warn",
                        "text": f"{nm} '{f['label']}' 최근 3편 첫 24시간이 모두 30일 중앙값({man(base)})의 절반 미만 "
                                f"({', '.join(man(m24[v]) for v in last3)})"})
        hot = [v for v in vids if age[v] <= 3 and m24[v] >= max(HOT * base, HOT_MIN)]
        if hot:
            out.append({"id": f"FMT_HOT:{k}:{f['key']}", "level": "good",
                        "text": f"{nm} '{f['label']}' 첫 24시간 {man(max(m24[v] for v in hot))} — 30일 중앙값({man(base)})의 "
                                f"×{max(m24[v] for v in hot) / max(1, base):.1f}"})
    return out


def exp_status(today: dt.date, chans: dict) -> tuple[list, list]:
    rows, flags = [], []
    for e in load(EXPERIMENTS, {"experiments": []})["experiments"]:
        left = None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.get("judge", "")):
            left = (dt.date.fromisoformat(e["judge"]) - today).days
        started = dt.date.fromisoformat(e["start"]) <= today
        c = chans.get(e["ch"])
        nums = []
        if c:
            for fkey in e.get("formats", []):
                f = c["_fby"].get(fkey)
                if f:
                    nums.append({"fmt": f["label"], "n7": f["n7"], "med24": f["med24"], "base24": f["base24"]})
        rows.append({k: e[k] for k in ("id", "ch", "title", "start", "judge", "criterion", "owner", "status")}
                    | {"days_left": left, "started": started, "nums": nums})
        if left is not None and e["status"] in ("running", "scheduled") and started:
            if 0 <= left <= 1:
                flags.append({"id": f"EXP_DUE:{e['id']}", "level": "info",
                              "text": f"실험 '{e['title']}' 판정 {'오늘' if left == 0 else '내일'} ({e['owner']})"})
            elif left < 0 and e["owner"] == "pulse":
                flags.append({"id": f"EXP_DUE:{e['id']}", "level": "warn",
                              "text": f"실험 '{e['title']}' 판정일 {e['judge']} 지남 — 판정하고 pulse_experiments.json 을 닫을 것"})
    return rows, flags


def radar_trends(trends: dict) -> dict:
    rows, hits = [], []
    for niche, n in (trends or {}).get("niches", {}).items():
        if n.get("own"):
            continue
        for t, s in n.get("tags", {}).items():
            if s.get("label") in TREND_LABELS and not t.startswith("형식:"):
                rows.append({"niche": n["label"], "tag": t, "label": s["label"], "med": s["med"], "prev": s.get("prev_med"),
                             "n": s["n"], "hit": s.get("hit")})
        for x in n.get("top", []):
            if x.get("ratio", 0) >= 5:
                hits.append({"niche": n["label"], "ch": x["ch"], "title": x["title"][:90], "ratio": x["ratio"],
                             "views": x["views"], "id": x["id"]})
    rows.sort(key=lambda r: (TREND_LABELS[r["label"]], -r["med"]))
    hits.sort(key=lambda r: -r["ratio"])
    return {"rows": rows[:16], "hits": hits[:8]}


# ── 예측 채점 ─────────────────────────────────────────────
def metric_value(P: dict, metric: str):
    parts = metric.split(":")
    c = P["channels"].get(parts[1]) if len(parts) >= 2 else None
    if not c:
        return None
    if parts[0] == "views" and len(parts) == 2:
        return c["today"] if c.get("today_d") == P["date"] else None
    if parts[0] == "subs" and len(parts) == 2:
        return (c.get("subs") or {}).get("now")
    if parts[0] == "share" and len(parts) == 3:
        return next((d["share"] for d in c["drivers"] if d["key"] == parts[2]), 0.0) if c["drivers"] else None
    if parts[0] == "med24" and len(parts) == 3:
        return next((f["med24"] for f in c["formats"] if f["key"] == parts[2]), None)
    return None


def metric_ok(metric: str, chans: dict, fmts: dict) -> bool:
    parts = metric.split(":")
    if len(parts) == 2 and parts[0] in ("views", "subs"):
        return parts[1] in chans
    if len(parts) == 3 and parts[0] in ("share", "med24"):
        return parts[1] in chans and parts[2] in {r["key"] for r in fmts[parts[1]]["rules"]}
    return False


def score(P: dict, prev_fill: dict | None) -> list[dict]:
    out = []
    for p in (prev_fill or {}).get("predictions", []) or []:
        v = metric_value(P, p.get("metric", ""))
        ok = None if v is None else (v >= p["value"] if p["op"] == ">=" else v <= p["value"])
        out.append({"text": p.get("text", ""), "metric": p.get("metric"), "op": p.get("op"), "value": p.get("value"),
                    "actual": v, "ok": ok})
    return out


# ── build ────────────────────────────────────────────────
def prev_dirs(out_root: str, day: str, n: int = 14) -> list[str]:
    ds = sorted(d for d in os.listdir(out_root) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and d < day) if os.path.isdir(out_root) else []
    return [os.path.join(out_root, d) for d in ds[-n:]]


def flag_days(fid: str, history: list[dict], day: str) -> int:
    """오늘 포함 며칠 연속 이 플래그가 떴나(어제·그제… pulse.json 을 거슬러 센다, 하루라도 빠지면 끊긴다)."""
    by = {h["date"]: {f["id"] for f in h.get("flags", [])} for h in history}
    n, d = 1, dt.date.fromisoformat(day)
    while True:
        d -= dt.timedelta(days=1)
        if fid in by.get(d.isoformat(), set()):
            n += 1
        else:
            return n


def build(radar_dir: str, out_root: str, day: str | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(UTC)
    day = day or kst_day(now)
    reg = load(os.path.join(radar_dir, "registry.json"), {})
    chans_raw = load(os.path.join(radar_dir, "channels.json"), {})
    trends = load(os.path.join(radar_dir, "trends.json"), {})
    fmts = load_formats()
    stamps = {s for r in reg.values() for s in r.get("views", {})}
    at = max((parse_t(s) for s in stamps), default=now)
    radar_t = parse_t(trends["generated"]) if trends.get("generated") else at
    chans = {k: analyze_channel(k, spec, reg, chans_raw, at) for k, spec in fmts.items()}
    flags = []
    age_h = (now - radar_t).total_seconds() / 3600
    if age_h > STALE_H:
        flags.append({"id": "DATA_STALE", "level": "bad",
                      "text": f"트렌드 레이더 데이터가 {age_h:.0f}시간 묵었다(마지막 {radar_t.astimezone(KST):%m-%d %H:%M} KST) — 오늘 숫자는 어제 것"})
    for c in chans.values():
        flags += channel_flags(c)
    exps, ef = exp_status(dt.date.fromisoformat(day), chans)
    flags += ef
    hist_dirs = prev_dirs(out_root, day)
    history = [h for h in (load(os.path.join(d, "pulse.json")) for d in hist_dirs) if h]
    P = {"date": day, "generated": now.isoformat(timespec="minutes"), "data_at": at.isoformat(timespec="minutes"),
         "radar_at": radar_t.isoformat(timespec="minutes"), "radar_age_h": round(age_h, 1),
         "channels": {k: {x: y for x, y in c.items() if not x.startswith("_")} for k, c in chans.items()},
         "experiments": exps, "trends": radar_trends(trends)}
    prev_fill = load(os.path.join(out_root, (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), "fill.json"))
    P["pred_scored"] = score(P, prev_fill)
    misses = sum(p["ok"] is False for p in P["pred_scored"])
    if misses >= 2:
        flags.append({"id": "PRED_MISS", "level": "info", "text": f"어제 예측 {len(P['pred_scored'])}개 중 {misses}개 빗나감 — 왜 틀렸는지 적을 것"})
    for f in flags:
        f["days"] = flag_days(f["id"], history, day)
    flags.sort(key=lambda f: (LEVELS.index(f["level"]), -f["days"], f["id"]))
    P["flags"] = flags
    P["history"] = [{"date": h["date"], "summary": (load(os.path.join(out_root, h["date"], "fill.json"), {}) or {}).get("summary", ""),
                     "views": {k: c.get("today") for k, c in h.get("channels", {}).items()}} for h in history[-7:]]
    save(os.path.join(out_root, day, "pulse.json"), P)
    return P


# ── fill.json 검사 ────────────────────────────────────────
def _s(x, lo, hi) -> bool:
    return isinstance(x, str) and lo <= len(x.strip()) <= hi


def patch_info(text: str) -> dict:
    paths = {p for ab in re.findall(r"(?m)^diff --git a/(\S+) b/(\S+)", text) for p in ab}
    paths |= set(re.findall(r"(?m)^(?:\+\+\+|---) [ab]/(\S+)", text))
    changed = sum(1 for ln in text.splitlines() if (ln.startswith("+") or ln.startswith("-"))
                  and not ln.startswith("+++") and not ln.startswith("---"))
    bad = sorted(p for p in paths if p.startswith(FORBIDDEN) or re.search(r"(?i)token|secret|\.env$|credential", p))
    return {"paths": sorted(paths), "changed": changed, "forbidden": bad, "is_diff": bool(re.search(r"(?m)^diff --git ", text))}


def check_fill(P: dict, F: dict, day_dir: str) -> list[str]:
    errs = []
    fmts = load_formats()
    if not isinstance(F, dict):
        return ["fill.json 이 JSON 객체가 아니다"]
    if F.get("date") != P["date"]:
        errs.append(f"date 가 {P['date']} 가 아니다: {F.get('date')!r}")
    if not _s(F.get("summary"), 10, 240):
        errs.append("summary: 10~240자 한두 문장")
    ch = F.get("channels")
    if not isinstance(ch, dict) or set(ch) != set(P["channels"]):
        errs.append(f"channels: 키는 정확히 {sorted(P['channels'])}")
    else:
        for k, c in ch.items():
            if not _s(c.get("state"), 2, 80):
                errs.append(f"channels.{k}.state: 2~80자")
            ev, gu = c.get("evidence"), c.get("guess", [])
            if not isinstance(ev, list) or not 1 <= len(ev) <= 4 or not all(_s(x, 5, 220) for x in ev):
                errs.append(f"channels.{k}.evidence: 1~4개, 각 5~220자")
            elif not all(re.search(r"\d", x) for x in ev):
                errs.append(f"channels.{k}.evidence: 근거에는 숫자가 있어야 한다(pulse.json 의 숫자) — 숫자 없는 건 guess 로")
            if not isinstance(gu, list) or len(gu) > 3 or not all(_s(x, 5, 220) for x in gu):
                errs.append(f"channels.{k}.guess: 0~3개, 각 5~220자")
    dr = F.get("direction")
    if not isinstance(dr, list) or not 1 <= len(dr) <= 6 or not all(
            isinstance(d, dict) and _s(d.get("topic"), 2, 40) and d.get("verdict") in VERDICTS and _s(d.get("why"), 5, 260) for d in dr):
        errs.append(f"direction: 1~6개, 각 {{topic ≤40, verdict {'/'.join(VERDICTS)}, why ≤260}}")
    tr = F.get("trends")
    if not isinstance(tr, list) or not 1 <= len(tr) <= 5 or not all(_s(x, 5, 220) for x in tr):
        errs.append("trends: 1~5개, 각 5~220자")
    want = {f["id"] for f in P["flags"]}
    fl = F.get("flags", {})
    if not isinstance(fl, dict):
        errs.append("flags: {플래그 id: 대응 한 줄}")
    else:
        miss, extra = sorted(want - set(fl)), sorted(set(fl) - want)
        if miss:
            errs.append(f"flags: 오늘 플래그 전부에 대응을 적어야 한다 — 빠짐 {miss}")
        if extra:
            errs.append(f"flags: 오늘 없는 플래그 {extra}")
        if not all(_s(v, 2, 200) for v in fl.values()):
            errs.append("flags: 대응은 각 2~200자")
    ac = F.get("actions", [])
    if not isinstance(ac, list) or len(ac) > 5 or not all(
            isinstance(a, dict) and _s(a.get("what"), 3, 160) and a.get("who") in WHO and _s(a.get("when", "-"), 1, 30) for a in ac):
        errs.append(f"actions: 0~5개, 각 {{what ≤160, who {'/'.join(WHO)}, when ≤30}}")
    pr = F.get("pr")
    patch = os.path.join(day_dir, "pr.patch")
    if pr is None:
        if os.path.exists(patch):
            errs.append("pr 이 null 인데 pr.patch 가 있다")
    elif not isinstance(pr, dict):
        errs.append("pr: null 또는 {slug, title, why, evidence, revert}")
    else:
        if not (isinstance(pr.get("slug"), str) and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", pr["slug"]) and len(pr["slug"]) <= 40):
            errs.append("pr.slug: 영문 소문자·숫자·하이픈 40자 이하")
        if not _s(pr.get("title"), 5, 72):
            errs.append("pr.title: 5~72자")
        if not _s(pr.get("why"), 10, 600):
            errs.append("pr.why: 10~600자")
        if not _s(pr.get("revert"), 5, 200):
            errs.append("pr.revert: 되돌리는 법 5~200자")
        ev = pr.get("evidence")
        days = {f["id"]: f["days"] for f in P["flags"]}
        if not isinstance(ev, list) or not ev or not all(x in days for x in ev):
            errs.append("pr.evidence: 오늘 플래그 id 목록(1개 이상)")
        elif not any(days[x] >= PR_MIN_DAYS or x.startswith("EXP_DUE:") for x in ev):
            errs.append(f"pr.evidence: {PR_MIN_DAYS}일 이상 이어진 플래그나 실험 판정(EXP_DUE)이 근거여야 한다 — 하루 출렁임으로 PR 금지")
        if not os.path.exists(patch):
            errs.append("pr 이 있는데 pr.patch 가 없다(git diff 결과를 그대로 저장)")
        else:
            pi = patch_info(open(patch, encoding="utf-8", errors="replace").read())
            if not pi["is_diff"]:
                errs.append("pr.patch: git diff 형식이 아니다")
            if pi["forbidden"]:
                errs.append(f"pr.patch: 건드리면 안 되는 곳 {pi['forbidden']} — 워크플로·업로드·토큰·맥박 자신은 텍스트 제안만")
            if pi["changed"] > PATCH_MAX_LINES:
                errs.append(f"pr.patch: {pi['changed']}줄 — {PATCH_MAX_LINES}줄 이하의 작은 변경만")
    pd = F.get("predictions")
    chans = set(P["channels"])
    if not isinstance(pd, list) or not 1 <= len(pd) <= 3:
        errs.append("predictions: 내일 숫자 예측 1~3개")
    else:
        for p in pd:
            if not (isinstance(p, dict) and _s(p.get("text"), 5, 120) and isinstance(p.get("metric"), str)
                    and metric_ok(p["metric"], chans, fmts) and p.get("op") in OPS and isinstance(p.get("value"), (int, float))):
                errs.append(f"predictions: {{text, metric(views:<ch>|subs:<ch>|share:<ch>:<형식>|med24:<ch>:<형식>), op >=|<=, value 숫자}} — {p!r}"[:240])
    if P.get("pred_scored") and not _s(F.get("review"), 5, 300):
        errs.append("review: 어제 예측 채점(pulse.json pred_scored)에 대한 한두 문장 — 틀렸으면 왜")
    if len(json.dumps(F, ensure_ascii=False)) > 12000:
        errs.append("fill.json 이 너무 길다(12,000자 이하) — 짧게")
    return errs


# ── 보고서(md) · 페이지(html) ──────────────────────────────
STATE = {"up": ("▲", "상승"), "down": ("▼", "하락"), "flat": ("■", "보합"), "short": ("·", "기록 쌓는 중")}


def state_text(c: dict) -> str:
    t = c["trend"]
    if t["state"] == "short":
        return f"기록 쌓는 중({t['days']}일)"
    ic, w = STATE[t["state"]]
    s = f"{ic} {w} {t['streak']}일째" if t["state"] != "flat" else f"{ic} 보합 {t['streak']}일째"
    if t["state"] != "flat" and t["today"] == "flat":
        s += " · 오늘은 주춤"
    return s


def compare_link(P: dict, F: dict) -> str | None:
    pr = F.get("pr")
    if not pr:
        return None
    return f"https://github.com/{REPO}/compare/main...{branch_name(P['date'], pr['slug'])}?expand=1"


def branch_name(day: str, slug: str) -> str:
    return f"pulse/{day}-{slug}"


def report_md(P: dict, F: dict) -> str:
    d = dt.date.fromisoformat(P["date"])
    o = [f"# 채널 맥박 — {P['date']} ({WEEKDAY[d.weekday()]})", "", f"> {F['summary']}", ""]
    for k, c in P["channels"].items():
        fc = F["channels"][k]
        w = c["window"]
        o += [f"## {c['name']} — {state_text(c)}", "",
              f"- 하루 조회 {man(c['today'])} ({c['today_d']} 아침까지 24시간 · {'채널 전체' if c['basis'] == 'channel' else '게시 30일 안 영상 합'})"
              + (f" · 최근 {w['k']}일 평균 {man(w['cur'])}, 그 전의 ×{w['ratio']}" if w else ""),
              f"- 상태: {fc['state']}"]
        o += [f"- 근거: {x}" for x in fc["evidence"]] + [f"- 추측: {x}" for x in fc.get("guess", [])]
        if c["drivers"]:
            o.append("- 오늘 조회를 끈 형식: " + " · ".join(f"{x['label']} {x['share']:.0%}" for x in c["drivers"][:5]))
        o.append("")
    if P["flags"]:
        o += ["## 신호", ""] + [f"- **{f['id']}** ({f['days']}일째) {f['text']} → {F['flags'].get(f['id'], '')}" for f in P["flags"]] + [""]
    o += ["## 방향 점검", ""] + [f"- {x['topic']}: **{x['verdict']}** — {x['why']}" for x in F["direction"]] + [""]
    o += ["## 트렌드", ""] + [f"- {x}" for x in F["trends"]] + [""]
    if F.get("actions"):
        o += ["## 할 일", ""] + [f"- [{a['who']}] {a['what']} ({a.get('when', '')})" for a in F["actions"]] + [""]
    if F.get("pr"):
        o += ["## PR 제안", "", f"- {F['pr']['title']} — {F['pr']['why']}", f"- 되돌리기: {F['pr']['revert']}",
              f"- 열기: {compare_link(P, F)}", ""]
    if P.get("pred_scored"):
        o += ["## 어제 예측 채점", ""] + [
            f"- {'✅' if p['ok'] else '❌' if p['ok'] is False else '…'} {p['text']} (실제 {p['actual']})" for p in P["pred_scored"]]
        o += [f"- 돌아보기: {F.get('review', '')}", ""]
    o += ["## 내일 예측", ""] + [f"- {p['text']} (`{p['metric']} {p['op']} {p['value']}`)" for p in F["predictions"]] + [""]
    return "\n".join(o)


def spark(series: list[dict], w: int = 320, h: int = 64) -> str:
    vals = [x["views"] for x in series]
    if len(vals) < 2:
        return '<p class="muted small">그래프는 이틀 치가 쌓이면 나온다</p>'
    hi = max(vals) or 1
    pad = 6
    xs = [pad + i * (w - 2 * pad) / (len(vals) - 1) for i in range(len(vals))]
    ys = [h - pad - v / hi * (h - 2 * pad) for v in vals]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"{xs[0]:.1f},{h - pad} " + pts + f" {xs[-1]:.1f},{h - pad}"
    pk = vals.index(hi)
    first, last = series[0]["d"][5:], series[-1]["d"][5:]
    return (f'<svg class="spark" viewBox="0 0 {w} {h + 16}" role="img" aria-label="하루 조회 {len(vals)}일 추이">'
            f'<polygon points="{area}" fill="var(--accent-soft)"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{xs[pk]:.1f}" cy="{ys[pk]:.1f}" r="3.2" fill="var(--accent)"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.2" fill="var(--bg)" stroke="var(--accent)" stroke-width="2"/>'
            f'<text x="{pad}" y="{h + 13}" class="axis">{first}</text>'
            f'<text x="{w - pad}" y="{h + 13}" class="axis" text-anchor="end">{last}</text></svg>')


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


CSS = """
:root{--bg:#f6f7f9;--panel:#ffffff;--fg:#17202b;--muted:#5d6876;--line:#dfe3e8;--accent:#0f8b6d;--accent-soft:rgba(15,139,109,.12);
--up:#0f8b6d;--down:#c2412d;--warn:#b7791f;--info:#3b6ea8;--chip:#eef1f4;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1419;--panel:#161d24;--fg:#e6ebf0;--muted:#98a3af;--line:#2a333d;
--accent:#3cc9a3;--accent-soft:rgba(60,201,163,.14);--up:#3cc9a3;--down:#f07a64;--warn:#e0b252;--info:#7fb0ea;--chip:#1f2830;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0f1419;--panel:#161d24;--fg:#e6ebf0;--muted:#98a3af;--line:#2a333d;
--accent:#3cc9a3;--accent-soft:rgba(60,201,163,.14);--up:#3cc9a3;--down:#f07a64;--warn:#e0b252;--info:#7fb0ea;--chip:#1f2830;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "Noto Sans KR",system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding-inline:16px;padding-block:28px 48px;display:grid;gap:22px}
h1{font-size:1.5rem;margin:0;letter-spacing:-.01em;text-wrap:balance}
h2{font-size:1.05rem;margin:0 0 10px;text-wrap:balance}
.top{display:grid;gap:6px}
.kicker{font:600 .72rem/1 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.summary{font-size:1.12rem;line-height:1.55;max-width:62ch;margin:0}
.muted{color:var(--muted)}.small{font-size:.84rem}
.num{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px;align-items:start}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;display:grid;gap:12px;min-width:0;align-content:start}
.big{font:600 2.1rem/1 "IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.row{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;background:var(--chip);font-size:.84rem;font-weight:600;white-space:nowrap}
.up{color:var(--up)}.down{color:var(--down)}.warn{color:var(--warn)}.info{color:var(--info)}.flat{color:var(--muted)}
.spark{width:100%;height:auto;max-width:100%;display:block}
.axis{font:10px "IBM Plex Mono",ui-monospace,monospace;fill:var(--muted)}
.bars{display:grid;gap:5px}
.bar{display:grid;grid-template-columns:minmax(0,9.5em) 1fr 3.4em;gap:8px;align-items:center;font-size:.86rem}
.bar i{display:block;height:8px;border-radius:4px;background:var(--accent);min-width:2px}
.bar span:last-child{text-align:right}
ul.plain{margin:0;padding-left:1.1em;display:grid;gap:4px}
.tag{font:600 .7rem/1 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.06em;padding:2px 6px;border-radius:4px;background:var(--chip);margin-right:6px;vertical-align:1px}
.flags{display:grid;gap:10px}
.flag{display:grid;grid-template-columns:10px 1fr;gap:10px;align-items:start}
.dot{width:10px;height:10px;border-radius:50%;margin-top:7px;background:currentColor}
.flag p{margin:0}.flag .resp{color:var(--muted);font-size:.9rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:.78rem}
td.n,th.n{text-align:right;font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:var(--info)}
.pr{border-left:3px solid var(--accent)}
footer{font-size:.8rem;color:var(--muted);display:grid;gap:4px}
"""


def page_html(P: dict, F: dict) -> str:
    d = dt.date.fromisoformat(P["date"])
    radar = parse_t(P["radar_at"]).astimezone(KST)
    out = ['<title>채널 맥박</title>',
           '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=Noto+Sans+KR:wght@400;600;700&display=swap">',
           f"<style>{CSS}</style>", '<main class="wrap">',
           f'<header class="top"><span class="kicker">Channel pulse · {e(P["date"])} ({WEEKDAY[d.weekday()]})</span>'
           f'<h1>채널 맥박</h1><p class="summary">{e(F["summary"])}</p>'
           f'<span class="muted small">데이터: 트렌드 레이더 {radar:%m-%d %H:%M} KST 수집 · 하루 조회 = 아침 기준 24시간</span></header>',
           '<section class="grid2">']
    for k, c in P["channels"].items():
        fc = F["channels"][k]
        t = c["trend"]["state"]
        w = c["window"]
        s = c.get("subs") or {}
        basis = "채널 전체" if c["basis"] == "channel" else "게시 30일 안 영상 합"
        out.append(f'<article class="panel"><div class="row"><h2>{e(c["name"])}</h2>'
                   f'<span class="chip {t}">{e(state_text(c))}</span></div>')
        out.append(f'<div class="row"><span class="big">{e(man(c["today"]))}</span><span class="muted small">회 / 하루 ({basis})</span></div>')
        meta = []
        if w:
            meta.append(f'최근 {w["k"]}일 평균 <span class="num">{e(man(w["cur"]))}</span> · 그 전의 <b class="num">×{w["ratio"]}</b>')
        if c.get("peak"):
            meta.append(f'최고 <span class="num">{e(man(c["peak"]["views"]))}</span>({e(c["peak"]["d"][5:])}) 대비 <span class="num">{int(round((c["vs_peak"] or 0) * 100))}%</span>')
        if s.get("now") is not None:
            meta.append(f'구독 <span class="num">{s["now"]:,}</span>' + (f' ({s["d7"]:+d} / {s["days"]}일)' if s.get("d7") is not None else ""))
        out.append(f'<div class="muted small">{" · ".join(meta)}</div>')
        out.append(spark(c["series"]))
        if c["drivers"]:
            top = max(x["share"] for x in c["drivers"]) or 1
            out.append('<div class="bars"><span class="muted small">오늘 조회를 끈 형식(게시 30일 안 영상)</span>' + "".join(
                f'<div class="bar"><span>{e(x["label"])}</span><i style="width:{x["share"] / top * 100:.0f}%"></i>'
                f'<span class="num">{x["share"]:.0%}</span></div>' for x in c["drivers"][:6]) + "</div>")
        out.append(f'<p style="margin:0"><b>{e(fc["state"])}</b></p><ul class="plain">'
                   + "".join(f'<li><span class="tag up">근거</span>{e(x)}</li>' for x in fc["evidence"])
                   + "".join(f'<li><span class="tag warn">추측</span>{e(x)}</li>' for x in fc.get("guess", [])) + "</ul></article>")
    out.append("</section>")
    if P["flags"]:
        col = {"bad": "down", "warn": "warn", "good": "up", "info": "info"}
        out.append('<section class="panel"><h2>신호</h2><div class="flags">' + "".join(
            f'<div class="flag"><span class="dot {col[f["level"]]}"></span><div><p>{e(f["text"])} '
            f'<span class="muted small num">{e(f["id"])} · {f["days"]}일째</span></p>'
            f'<p class="resp">→ {e(F["flags"].get(f["id"], ""))}</p></div></div>' for f in P["flags"]) + "</div></section>")
    vc = {"맞다": "up", "틀리다": "down", "아직 모름": "flat"}
    out.append('<section class="panel"><h2>방향 점검</h2><div class="scroll"><table><tr><th>무엇</th><th>판정</th><th>왜</th></tr>' + "".join(
        f'<tr><td>{e(x["topic"])}</td><td><span class="chip {vc[x["verdict"]]}">{e(x["verdict"])}</span></td><td>{e(x["why"])}</td></tr>'
        for x in F["direction"]) + "</table></div></section>")
    if F.get("pr") or F.get("actions"):
        out.append('<section class="panel pr"><h2>할 일 · PR</h2>')
        if F.get("pr"):
            pr = F["pr"]
            out.append(f'<p style="margin:0"><b>PR 제안: {e(pr["title"])}</b><br><span class="muted">{e(pr["why"])}</span><br>'
                       f'<span class="small">되돌리기: {e(pr["revert"])} · <a href="{e(compare_link(P, F))}">PR 열기 →</a></span></p>')
        if F.get("actions"):
            who = {"pr": "PR", "local": "PC 작업", "user": "사용자", "watch": "지켜보기"}
            out.append('<ul class="plain">' + "".join(f'<li><span class="tag">{who[a["who"]]}</span>{e(a["what"])} '
                                                      f'<span class="muted small">{e(a.get("when", ""))}</span></li>' for a in F["actions"]) + "</ul>")
        out.append("</section>")
    out.append('<section class="grid2">')
    for k, c in P["channels"].items():
        rows = [f for f in c["formats"] if f["n7"] or f["med24"] is not None]
        if not rows:
            continue
        out.append(f'<article class="panel"><h2>{e(c["name"])} 형식별 첫 24시간</h2><div class="scroll"><table>'
                   '<tr><th>형식</th><th class="n">7일 편수</th><th class="n">지난 7일</th><th class="n">그 전 7일</th><th class="n">30일 기준</th></tr>' + "".join(
                       f'<tr><td>{e(f["label"])}</td><td class="n">{f["n7"]}</td><td class="n">{e(man(f["med24"]))}</td>'
                       f'<td class="n">{e(man(f["prev24"]))}</td><td class="n">{e(man(f["base24"]))}</td></tr>' for f in rows)
                   + '</table></div><span class="muted small">중앙값 · 게시 1~8일 전 영상의 첫 24시간 조회(30일 기준 = 게시 1~31일 전)</span></article>')
    out.append("</section>")
    mv = [(c["name"], m) for c in P["channels"].values() for m in c["movers"][:4]]
    nw = [(c["name"], m) for c in P["channels"].values() for m in c["new"][:5]]
    if mv or nw:
        out.append('<section class="grid2">')
        if mv:
            out.append('<article class="panel"><h2>오늘 가장 많이 늘어난 영상</h2><div class="scroll"><table><tr><th>영상</th><th class="n">+하루</th><th class="n">누적</th></tr>' + "".join(
                f'<tr><td><a href="https://youtu.be/{e(m["id"])}">{e(m["title"][:46])}</a><br><span class="muted small">{e(n)} · {e(m["fmt"])} · {m["age_d"]}일</span></td>'
                f'<td class="n">{e(man(m["gain"]))}</td><td class="n">{e(man(m["views"]))}</td></tr>' for n, m in mv) + "</table></div></article>")
        if nw:
            out.append('<article class="panel"><h2>새 영상(36시간 안)</h2><div class="scroll"><table><tr><th>영상</th><th class="n">지금</th><th class="n">같은 나이 평소</th></tr>' + "".join(
                f'<tr><td><a href="https://youtu.be/{e(m["id"])}">{e(m["title"][:46])}</a><br><span class="muted small">{e(n)} · {e(m["fmt"])} · {m["age_h"]}시간</span></td>'
                f'<td class="n">{e(man(m["views"]))}</td><td class="n">{e(man(m["expect"]))}'
                + (f' <b class="{"up" if m["ratio"] >= 1 else "down"}">×{m["ratio"]}</b>' if m["ratio"] is not None else "") + "</td></tr>"
                for n, m in nw) + "</table></div></article>")
        out.append("</section>")
    tr = P["trends"]
    out.append('<section class="panel"><h2>트렌드</h2><ul class="plain">' + "".join(f"<li>{e(x)}</li>" for x in F["trends"]) + "</ul>")
    if tr["rows"]:
        tc = {"떡상": "up", "강세": "up", "식는 중": "down", "끝물": "down"}
        out.append('<div class="scroll"><table><tr><th>분야</th><th>주제</th><th>판정</th><th class="n">배수</th><th class="n">지난주</th><th class="n">영상</th></tr>' + "".join(
            f'<tr><td>{e(r["niche"])}</td><td>{e(r["tag"])}</td><td><span class="chip {tc[r["label"]]}">{e(r["label"])}</span></td>'
            f'<td class="n">{r["med"]:.2f}</td><td class="n">{e(r["prev"] if r["prev"] is not None else "–")}</td><td class="n">{r["n"]}</td></tr>'
            for r in tr["rows"][:12]) + '</table></div><span class="muted small">배수 = 영상 조회수 ÷ 그 채널 같은 형식의 평소(중앙값) · 참고 채널 기준(트렌드 레이더)</span>')
    if tr["hits"]:
        out.append('<ul class="plain small">' + "".join(
            f'<li><b class="num">×{h["ratio"]:.1f}</b> {e(h["ch"])} — <a href="https://youtu.be/{e(h["id"])}">{e(h["title"][:70])}</a></li>'
            for h in tr["hits"][:6]) + "</ul>")
    out.append("</section>")
    out.append('<section class="panel"><h2>실험 달력</h2><div class="scroll"><table><tr><th>실험</th><th>판정일</th><th>기준</th><th>지금 숫자(첫 24시간 중앙값)</th></tr>')
    for x in P["experiments"]:
        left = x["days_left"]
        when = x["judge"] if left is None else f'{x["judge"][5:]} ' + ("오늘" if left == 0 else f"D-{left}" if left > 0 else f"{-left}일 지남")
        nums = " · ".join(f'{n["fmt"]} {man(n["med24"])}({n["n7"]}편)' for n in x["nums"]) or "–"
        out.append(f'<tr><td>{e(x["title"])}<br><span class="muted small">{e(x["owner"])}{"" if x["started"] else " · 시작 전"}</span></td>'
                   f'<td class="n">{e(when)}</td><td class="small">{e(x["criterion"])}</td><td class="small">{e(nums)}</td></tr>')
    out.append("</table></div></section>")
    out.append('<section class="grid2">')
    if P.get("pred_scored"):
        out.append('<article class="panel"><h2>어제 예측 채점</h2><ul class="plain">' + "".join(
            f'<li>{"✅" if p["ok"] else "❌" if p["ok"] is False else "…"} {e(p["text"])} <span class="muted small num">실제 {e(man(p["actual"]) if p["metric"].startswith(("views", "subs", "med24")) else p["actual"])}</span></li>'
            for p in P["pred_scored"]) + f'</ul><p class="muted small" style="margin:0">{e(F.get("review", ""))}</p></article>')
    out.append('<article class="panel"><h2>내일 예측</h2><ul class="plain">' + "".join(
        f'<li>{e(p["text"])} <span class="muted small num">{e(p["metric"])} {e(p["op"])} {e(p["value"])}</span></li>' for p in F["predictions"])
        + '</ul><span class="muted small">내일 맥박이 자동으로 채점한다</span></article>')
    out.append("</section>")
    if P.get("history"):
        out.append('<section class="panel"><h2>지난 날</h2><ul class="plain small">' + "".join(
            f'<li><span class="num">{e(h["date"][5:])}</span> {e(h["summary"])}</li>' for h in reversed(P["history"]) if h.get("summary")) + "</ul></section>")
    out.append(f'<footer><span>숫자는 tools/pulse.py 가 냈고(근거), 해석은 분석 루틴(Opus 5.5)이 썼다(근거/추측 구분). '
               f'하루 조회 추세 = 3일 이동평균이 전날보다 5% 넘게 오르면 상승, 내리면 하락 · 며칠째 = 반대 방향이 나온 다음 날부터.</span>'
               f'<span>원본: github.com/{REPO}/tree/routine/pulse/output/pulse/{e(P["date"])} · 만든 시각 {e(parse_t(P["generated"]).astimezone(KST).strftime("%m-%d %H:%M"))} KST</span></footer>')
    out.append("</main>")
    return "\n".join(out)


def check(day_dir: str) -> list[str]:
    P = load(os.path.join(day_dir, "pulse.json"))
    if not P:
        return ["pulse.json 이 없다 — 먼저 build"]
    F = load(os.path.join(day_dir, "fill.json"))
    if F is None:
        return ["fill.json 이 없거나 JSON 이 아니다"]
    errs = check_fill(P, F, day_dir)
    if not errs:
        with open(os.path.join(day_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write(report_md(P, F))
        with open(os.path.join(day_dir, "page.html"), "w", encoding="utf-8") as f:
            f.write(page_html(P, F))
    return errs


def verify_pr(day_dir: str, radar_dir: str) -> list[str]:
    """워크플로가 PR 을 열기 전에: 레이더 데이터로 숫자를 다시 내서 pr.evidence 플래그가 정말 있고 3일 이상
    이어졌는지(또는 실험 판정일인지) 확인한다. 루틴이 pulse.json 을 잘못 고쳤어도 PR 은 못 연다."""
    P, F = load(os.path.join(day_dir, "pulse.json")), load(os.path.join(day_dir, "fill.json"))
    pr = (F or {}).get("pr")
    if not P or not pr:
        return ["pulse.json·fill.json 의 pr 이 없다"]
    root = os.path.dirname(os.path.abspath(day_dir))
    with tempfile.TemporaryDirectory() as td:
        for d in prev_dirs(root, P["date"]):
            os.makedirs(os.path.join(td, os.path.basename(d)), exist_ok=True)
            for n in ("pulse.json", "fill.json"):
                if os.path.exists(os.path.join(d, n)):
                    shutil.copy(os.path.join(d, n), os.path.join(td, os.path.basename(d), n))
        Q = build(radar_dir, td, P["date"])
    days = {f["id"]: f["days"] for f in Q["flags"]}
    errs = [f"근거 {x} 가 다시 낸 숫자에 없다" for x in pr.get("evidence", []) if x not in days]
    if not any(x in days and (days[x] >= PR_MIN_DAYS or x.startswith("EXP_DUE:")) for x in pr.get("evidence", [])):
        errs.append(f"다시 낸 숫자로는 {PR_MIN_DAYS}일 이상 이어진 근거가 없다: {[(x, days.get(x)) for x in pr.get('evidence', [])]}")
    return errs


def pr_field(day_dir: str, field: str) -> str:
    P, F = load(os.path.join(day_dir, "pulse.json")), load(os.path.join(day_dir, "fill.json"))
    pr = (F or {}).get("pr")
    if not pr:
        return ""
    if field in ("slug", "title"):
        return pr[field]
    if field == "branch":
        return branch_name(P["date"], pr["slug"])
    if field == "body":
        days = {f["id"]: f for f in P["flags"]}
        lines = [f"채널 맥박 {P['date']} 이 제안한 변경이다(분석 루틴이 쓰고, 워크플로가 모든 테스트를 통과시킨 뒤 열었다).", "",
                 "## 왜", "", pr["why"], "", "## 근거(플래그)", ""]
        lines += [f"- `{x}` ({days[x]['days']}일째) {days[x]['text']}" for x in pr["evidence"] if x in days]
        lines += ["", "## 되돌리기", "", pr["revert"], "",
                  f"보고서: https://github.com/{REPO}/blob/routine/pulse/output/pulse/{P['date']}/report.md", "",
                  "🤖 Generated with [Claude Code](https://claude.com/claude-code)"]
        return "\n".join(lines)
    raise SystemExit(f"모르는 field: {field}")


def main() -> int:
    ap = argparse.ArgumentParser(description="채널 맥박")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--radar", required=True)
    b.add_argument("--out", default=os.path.join("output", "pulse"))
    b.add_argument("--date")
    c = sub.add_parser("check")
    c.add_argument("dir")
    v = sub.add_parser("verify-pr")
    v.add_argument("dir")
    v.add_argument("--radar", required=True)
    p = sub.add_parser("pr")
    p.add_argument("dir")
    p.add_argument("--field", required=True, choices=["slug", "title", "branch", "body"])
    a = ap.parse_args()
    if a.cmd == "build":
        P = build(a.radar, a.out, a.date)
        print(f"📈 {P['date']} · 데이터 {parse_t(P['radar_at']).astimezone(KST):%m-%d %H:%M} KST ({P['radar_age_h']}시간 전)")
        for k, ch in P["channels"].items():
            print(f"   {ch['name']}: 하루 {man(ch['today'])} · {state_text(ch)} · 기준 {ch['basis']}")
        for f in P["flags"]:
            print(f"   [{f['level']}] {f['id']} ({f['days']}일째) {f['text']}")
        print(f"   → {os.path.join(a.out, P['date'], 'pulse.json')}")
        return 0
    if a.cmd == "check":
        errs = check(a.dir)
        if errs:
            print("❌ fill.json 검사 실패:")
            for x in errs:
                print(f"   - {x}")
            return 1
        print(f"✅ 통과 — {os.path.join(a.dir, 'report.md')} · page.html")
        return 0
    if a.cmd == "verify-pr":
        errs = verify_pr(a.dir, a.radar)
        for x in errs:
            print(f"❌ {x}")
        if not errs:
            print("✅ PR 근거 재확인 통과")
        return 1 if errs else 0
    print(pr_field(a.dir, a.field))
    return 0


if __name__ == "__main__":
    sys.exit(main())
