#!/usr/bin/env python3
"""트렌드 레이더 — 참고 채널 새 영상이 '그 채널 평소'보다 얼마나 잘 되는지로 주제별 떡상·끝물을 가린다.

    python tools/trend_radar.py collect --dir <data>     # 유튜브 API → registry.json(영상) · channels.json(채널 전체) 스냅숏
    python tools/trend_radar.py analyze --dir <data>     # trends.json · report.md · weekly/<날짜>.json
    python tools/trend_radar.py run --dir <data>         # 둘 다(워크플로가 매일 부른다)

왜 '채널 평소 대비'인가: 구독자 100만 채널의 10만 회는 실패고 1만 채널의 10만 회는 대박이다. 절대 조회수로 보면
  큰 채널의 주제만 뜨는 것처럼 보인다. 그래서 배수 = 영상 조회수 ÷ 그 채널 같은 형식(쇼츠/롱폼) 영상의 중앙값.
  배수 2 이상 = 대박. 주제(제목 규칙, tools/trend_niches.json)마다 배수의 중앙값을 내고, 지난주와 비교해
  떡상·식는 중·끝물을 붙인다. 지난주 기록이 없으면 강세·약세·보통(한 시점 판정)만 붙인다.

공정하게 재기: 갓 올라온 영상은 조회수가 덜 찼다 → 3일 이상 지난 영상만 잰다. 매일 스냅숏이 쌓이면
  '7일째 조회수'끼리 비교하고, 그 전에는 '지금 조회수' 기준이다(보고서에 '추정'이라고 적는다).
비용: 채널마다 playlistItems 1 unit + videos.list 50개당 1 unit — 하루 약 150~300 units(업로드 1건 = 1,600 units).
  RSS(쿼터 0)는 2026-10-01 오후 404 로 막혀 있어 쓰지 않는다.
★근거와 추측을 나눈다: 이 파일은 숫자만 낸다. '그래서 무엇을 바꿀까'는 주간 검토(사람·Claude)가 PR 로 한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NICHES = os.path.join(HERE, "trend_niches.json")
UTC = dt.timezone.utc

MIN_AGE = 3.0          # 이보다 어린 영상은 재지 않는다(조회수가 덜 찼다)
TRACK_DAYS = 30        # 이 나이까지 매일 조회수를 다시 읽는다
KEEP_DAYS = 75         # 레지스트리 보관(주간 비교에 두 달 남짓)
CH_KEEP_DAYS = 400     # channels.json(채널 전체 조회수·구독자 스냅숏) 보관 — 채널 맥박(tools/pulse.py)이 읽는다
WINDOW = 21            # 주제 판정에 쓰는 '최근' 범위(게시일 기준)
HIT = 2.0              # 대박 = 채널 평소의 2배 이상
MIN_N = 3              # 표본이 이보다 적으면 판정하지 않는다
SHORT_MAX_SEC = 180    # 쇼츠는 3분까지
PER_CHANNEL = 50       # 채널마다 최신 업로드 몇 개를 읽나(우리 채널 첫 실행은 200)


# ── 시간 ────────────────────────────────────────────────
def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def stamp(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H")


def parse_t(s: str) -> dt.datetime:
    if len(s) == 13:                                   # 스냅숏 키 'YYYY-MM-DDTHH'
        return dt.datetime.strptime(s, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def age_days(rec: dict, at: dt.datetime) -> float:
    return (at - parse_t(rec["pub"])).total_seconds() / 86400


def iso_dur(s: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


# ── 설정·저장 ───────────────────────────────────────────
def load_niches(path: str = NICHES) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)["niches"]
    for c in cfg.values():
        c["_re"] = {t: re.compile(p) for t, p in c["tags"].items()}
    return cfg


def load_json(path: str, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


# ── 모으기 ──────────────────────────────────────────────
def service(token_path: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    d = load_json(token_path, {})
    cr = Credentials(token=d.get("token"), refresh_token=d["refresh_token"], token_uri=d["token_uri"],
                     client_id=d["client_id"], client_secret=d["client_secret"], scopes=d.get("scopes"))
    cr.refresh(Request())
    return build("youtube", "v3", credentials=cr, cache_discovery=False)


def uploads(yt, ch: str, n: int = PER_CHANNEL) -> list[str]:
    """채널 업로드 목록(최신순) 영상 id. 업로드 재생목록 = 'UU' + 채널 id[2:]."""
    ids, tok = [], None
    while len(ids) < n:
        kw = {"part": "contentDetails", "playlistId": "UU" + ch[2:], "maxResults": min(50, n - len(ids))}
        if tok:
            kw["pageToken"] = tok
        r = yt.playlistItems().list(**kw).execute()
        ids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
        tok = r.get("nextPageToken")
        if not tok:
            break
    return ids


def details(yt, ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for it in r.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            out[it["id"]] = {"title": sn.get("title", ""), "pub": sn.get("publishedAt", ""), "ch": sn.get("channelId", ""),
                             "dur": iso_dur(it.get("contentDetails", {}).get("duration", "")),
                             "views": int(st.get("viewCount", 0) or 0), "likes": int(st.get("likeCount", 0) or 0),
                             "comments": int(st.get("commentCount", 0) or 0)}
    return out


def collect(reg: dict, cfg: dict, yt, at: dt.datetime | None = None) -> dict:
    """registry 를 갱신한다(제자리). 반환: 통계."""
    at = at or now_utc()
    key = stamp(at)
    owner = {}
    errors = []
    new_ids = set()
    for niche, c in cfg.items():
        for ch in c["channels"]:
            owner[ch] = niche
            first = c.get("own") and not any(r.get("ch") == ch for r in reg.values())
            try:
                for vid in uploads(yt, ch, 200 if first else PER_CHANNEL):
                    if vid not in reg:
                        new_ids.add(vid)
            except Exception as e:  # noqa: BLE001 — 채널 하나가 막혀도 나머지는 모은다
                errors.append(f"{ch}: {str(e)[:120]}")
    track = [v for v, r in reg.items() if age_days(r, at) <= TRACK_DAYS]
    want = sorted(new_ids | set(track))
    got = details(yt, want)
    for vid, d in got.items():
        niche = owner.get(d["ch"])
        if not niche:
            continue
        r = reg.setdefault(vid, {"ch": d["ch"], "niche": niche, "first": key, "views": {}})
        r.update({"title": d["title"], "pub": d["pub"], "dur": d["dur"], "likes": d["likes"], "comments": d["comments"],
                  "niche": niche})
        r["views"][key] = d["views"]
    dropped = [v for v, r in reg.items() if age_days(r, at) > KEEP_DAYS]
    for v in dropped:
        del reg[v]
    return {"new": len(new_ids), "updated": len(got), "tracked": len(track), "dropped": len(dropped),
            "videos": len(reg), "errors": errors, "units_est": len(owner) + (len(want) + 49) // 50}


def collect_channels(chans: dict, cfg: dict, yt, at: dt.datetime | None = None) -> dict:
    """channels.json 을 갱신한다(제자리): 채널마다 {name, niche, own, snaps: {스탬프: {views, subs, videos}}}.
    channels.list 50개당 1 unit. 30일 넘은 영상까지 포함한 '채널 전체' 조회수라 우리 채널 하루 조회의 기준이 된다."""
    at = at or now_utc()
    key = stamp(at)
    meta = {ch: (niche, name, bool(c.get("own"))) for niche, c in cfg.items() for ch, name in c["channels"].items()}
    ids, errors = sorted(meta), []
    for i in range(0, len(ids), 50):
        try:
            r = yt.channels().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        except Exception as e:  # noqa: BLE001 — 채널 통계가 막혀도 영상 스냅숏은 이미 모았다
            errors.append(f"channels.list: {str(e)[:120]}")
            continue
        for it in r.get("items", []):
            st = it.get("statistics", {})
            niche, name, own = meta.get(it["id"], ("", "", False))
            c = chans.setdefault(it["id"], {"snaps": {}})
            c.update({"name": name, "niche": niche, "own": own})
            c["snaps"][key] = {"views": int(st.get("viewCount", 0) or 0),
                               "subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
                               "videos": int(st.get("videoCount", 0) or 0)}
    cut = at - dt.timedelta(days=CH_KEEP_DAYS)
    for c in chans.values():
        c["snaps"] = {k: v for k, v in c.get("snaps", {}).items() if parse_t(k) >= cut}
    return {"channels": len(chans), "errors": errors}


# ── 재기 ────────────────────────────────────────────────
def snaps(rec: dict) -> list[tuple[float, int]]:
    """(나이(일), 조회수) 시간순."""
    pub = parse_t(rec["pub"])
    return sorted(((parse_t(k) - pub).total_seconds() / 86400, v) for k, v in rec.get("views", {}).items())


def views_at(rec: dict, day: float = 7.0) -> float | None:
    """나이 day 일 때 조회수(앞뒤 스냅숏 사이 선형 보간). 그 나이를 앞뒤로 못 잡았으면 None."""
    s = snaps(rec)
    for (a1, v1), (a2, v2) in zip(s, s[1:]):
        if a1 <= day <= a2:
            return v1 + (v2 - v1) * (day - a1) / max(1e-9, a2 - a1)
    return None


def latest(rec: dict) -> int:
    s = snaps(rec)
    return s[-1][1] if s else 0


def fmt(rec: dict) -> str:
    return "short" if 0 < rec.get("dur", 0) <= SHORT_MAX_SEC else "long"


def ratios(reg: dict, at: dt.datetime) -> dict:
    """영상 id → {ratio, basis('7d'|'now'), views}. 채널·형식별 평소(중앙값) 대비."""
    groups: dict = {}
    for vid, r in reg.items():
        groups.setdefault((r["ch"], fmt(r)), []).append(vid)
    out = {}
    for _, vids in groups.items():
        v7 = {v: views_at(reg[v]) for v in vids}
        base7 = [x for x in v7.values() if x is not None]
        now_pool = [latest(reg[v]) for v in vids if MIN_AGE <= age_days(reg[v], at) <= TRACK_DAYS]
        b7 = statistics.median(base7) if len(base7) >= MIN_N else None
        bnow = statistics.median(now_pool) if len(now_pool) >= MIN_N else None
        for v in vids:
            a = age_days(reg[v], at)
            if a < MIN_AGE:
                continue
            # ★중앙값 0 도 '평소'다(갓 생긴 채널) — `if b7` 로 쓰면 0 을 거짓으로 봐서 채널이 통째로 빠졌다(10/5 NT n=0)
            if b7 is not None and v7[v] is not None:
                out[v] = {"ratio": v7[v] / max(1.0, b7), "basis": "7d", "views": latest(reg[v])}
            elif bnow is not None and a <= TRACK_DAYS:
                out[v] = {"ratio": latest(reg[v]) / max(1.0, bnow), "basis": "now", "views": latest(reg[v])}
    return out


def tags_of(title: str, c: dict) -> list[str]:
    return [t for t, rx in c["_re"].items() if rx.search(title or "")]


def label(cur: dict, prev: dict | None) -> str:
    if cur["n"] < MIN_N:
        return "표본 부족"
    m = cur["med"]
    if prev and prev.get("n", 0) >= MIN_N and prev.get("med"):
        r = m / prev["med"]
        if cur["n"] >= prev["n"] * 1.5 and r <= 0.9:
            return "끝물"            # 너도나도 올리는데(공급↑) 반응은 줄었다
        if r >= 1.25 and m >= 1.0:
            return "떡상"
        if r <= 0.8:
            return "식는 중"
        return "유지"
    if m >= 1.5:
        return "강세"
    if m <= 0.7:
        return "약세"
    return "보통"


def analyze(reg: dict, cfg: dict, at: dt.datetime | None = None, prev: dict | None = None) -> dict:
    at = at or now_utc()
    rt = ratios(reg, at)
    res = {"generated": at.isoformat(timespec="minutes"), "window_days": WINDOW, "hit": HIT, "niches": {}}
    pn = (prev or {}).get("niches", {})
    for niche, c in cfg.items():
        rows = []
        for vid, r in reg.items():
            if r.get("niche") != niche or vid not in rt or age_days(r, at) > WINDOW:
                continue
            tg = tags_of(r.get("title", ""), c) + [f"형식: {'쇼츠' if fmt(r) == 'short' else '롱폼'}"]
            rows.append({"id": vid, "ch": c["channels"].get(r["ch"], r["ch"]), "title": r.get("title", ""),
                         "ratio": round(rt[vid]["ratio"], 2), "basis": rt[vid]["basis"], "views": rt[vid]["views"],
                         "days": round(age_days(r, at), 1), "tags": tg, "fmt": fmt(r)})
        tags = {}
        for t in list(c["tags"]) + ["형식: 쇼츠", "형식: 롱폼"]:
            rs = sorted((x for x in rows if t in x["tags"]), key=lambda x: -x["ratio"])
            if not rs:
                continue
            cur = {"n": len(rs), "med": round(statistics.median(x["ratio"] for x in rs), 2),
                   "hit": round(sum(x["ratio"] >= HIT for x in rs) / len(rs), 2),
                   "views_med": int(statistics.median(x["views"] for x in rs)),
                   "ex": [{k: x[k] for k in ("id", "ch", "title", "ratio", "views")} for x in rs[:3]]}
            p = pn.get(niche, {}).get("tags", {}).get(t)
            cur["prev_med"] = p.get("med") if p else None
            cur["label"] = label(cur, p)
            tags[t] = cur
        top = sorted(rows, key=lambda x: -x["ratio"])[:10]
        res["niches"][niche] = {"label": c["label"], "own": bool(c.get("own")), "n": len(rows),
                                "basis_7d": sum(x["basis"] == "7d" for x in rows), "tags": tags,
                                "top": [{k: x[k] for k in ("id", "ch", "title", "ratio", "views", "days", "basis")} for x in top]}
    return res


# ── 보고서 ──────────────────────────────────────────────
ORDER = {"떡상": 0, "강세": 1, "유지": 2, "보통": 3, "식는 중": 4, "약세": 5, "끝물": 6, "표본 부족": 9}
ICON = {"떡상": "📈", "강세": "🔥", "유지": "·", "보통": "·", "식는 중": "📉", "약세": "🧊", "끝물": "⚠️", "표본 부족": "…"}


def report_md(res: dict) -> str:
    out = [f"# 트렌드 레이더 — {res['generated'][:10]}", "",
           f"배수 = 영상 조회수 ÷ 그 채널 같은 형식 영상의 평소(중앙값). 1.0 = 평소, {res['hit']:g} 이상 = 대박. "
           f"최근 {res['window_days']}일 게시 · 3일 이상 지난 영상만.", ""]
    for niche, n in res["niches"].items():
        basis = "7일째 조회수 기준" if n["n"] and n["basis_7d"] >= n["n"] / 2 else "지금 조회수 기준(추정 — 7일 기록이 쌓이는 중)"
        out += [f"## {n['label']}", f"영상 {n['n']}개 · {basis}", "",
                "| 판정 | 주제 | 영상 | 배수(중앙) | 대박 비율 | 지난주 |", "|---|---|---:|---:|---:|---:|"]
        for t, s in sorted(n["tags"].items(), key=lambda kv: (ORDER.get(kv[1]["label"], 5), -kv[1]["med"])):
            pm = f"{s['prev_med']:.2f}" if s.get("prev_med") else "–"
            out.append(f"| {ICON.get(s['label'], '')} {s['label']} | {t} | {s['n']} | {s['med']:.2f} | {s['hit']:.0%} | {pm} |")
        if n["top"]:
            out += ["", "대박 영상(배수 순):"]
            for x in n["top"][:5]:
                out.append(f"- {x['ratio']:.1f}배 · {x['views']:,}회 · {x['ch']} — [{x['title'][:60]}](https://youtu.be/{x['id']})")
        out.append("")
    return "\n".join(out)


# ── 실행 ────────────────────────────────────────────────
def prev_weekly(d: str, at: dt.datetime) -> dict | None:
    """6일 이상 지난 가장 최근 주간 기록(지난주와 비교)."""
    best = None
    for p in sorted(glob.glob(os.path.join(d, "weekly", "*.json"))):
        day = dt.date.fromisoformat(os.path.basename(p)[:10])
        if (at.date() - day).days >= 6:
            best = p
    return load_json(best, None) if best else None


def run_analyze(d: str, cfg: dict, at: dt.datetime) -> dict:
    reg = load_json(os.path.join(d, "registry.json"), {})
    res = analyze(reg, cfg, at, prev_weekly(d, at))
    save_json(os.path.join(d, "trends.json"), res)
    with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
        f.write(report_md(res))
    weeks = sorted(glob.glob(os.path.join(d, "weekly", "*.json")))
    last = dt.date.fromisoformat(os.path.basename(weeks[-1])[:10]) if weeks else None
    if not last or (at.date() - last).days >= 7:
        save_json(os.path.join(d, "weekly", f"{at.date()}.json"), res)
        print(f"   🗓️ 주간 기록 weekly/{at.date()}.json")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="트렌드 레이더")
    ap.add_argument("cmd", choices=["collect", "analyze", "run"])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--token", default=os.environ.get("TREND_TOKEN", ""))
    ap.add_argument("--niches", default=NICHES)
    a = ap.parse_args()
    cfg = load_niches(a.niches)
    at = now_utc()
    if a.cmd in ("collect", "run"):
        if not a.token or not os.path.exists(a.token):
            print("::error::토큰 없음(TREND_TOKEN) — 모으지 못한다")
            return 2
        reg = load_json(os.path.join(a.dir, "registry.json"), {})
        yt = service(a.token)
        st = collect(reg, cfg, yt, at)
        save_json(os.path.join(a.dir, "registry.json"), reg)
        print(f"   📥 새 영상 {st['new']} · 갱신 {st['updated']} · 추적 {st['tracked']} · 정리 {st['dropped']} · 전체 {st['videos']}"
              f" · 약 {st['units_est']} units")
        chans = load_json(os.path.join(a.dir, "channels.json"), {})
        cs = collect_channels(chans, cfg, yt, at)
        save_json(os.path.join(a.dir, "channels.json"), chans)
        print(f"   📊 채널 통계 {cs['channels']}곳")
        for e in st["errors"] + cs["errors"]:
            print(f"   ⚠️ {e}")
    if a.cmd in ("analyze", "run"):
        res = run_analyze(a.dir, cfg, at)
        for n in res["niches"].values():
            hot = [t for t, s in n["tags"].items() if s["label"] in ("떡상", "강세")]
            print(f"   {n['label']}: 영상 {n['n']} · 강세/떡상 {hot[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
