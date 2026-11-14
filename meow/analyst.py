#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""분석 담당 — 새 고양이 채널(Meow Remix TV) 최근 쇼츠 성적을 읽어 기획(plan_api)에 넘긴다 (2026-11-14).

왜: 11/14 사용자 '분석 직원도 붙여줘'. 옛 채널에서 고양이 쇼츠는 피드에 거의 안 떴고(편당 0~17회), 떴던 한 편도
  69.9% 가 넘겼다. 기획이 '무엇이 시청자를 붙잡았나'를 모른 채 매일 12편을 썼다 → 매일 기획 직전에 성적을 읽어
  사용자 메시지에 넣는다. 보고서·알림은 만들지 않는다(기획에만 들어간다).

    python meow/analyst.py pull --dir <기획 폴더(data/meow)> --token <토큰 파일> [--days 10]
      → <기획 폴더>/stats.json  {at, channel, videos: [{id, video, published, format, caption, title, views,
                                   avg_pct, avg_sec, likes, subs, feed_views, feed_share}]}

읽는 것(읽기만): YouTube Data API(업로드 목록 · 설명의 표식 'Meow Remix · <날짜> <id>' 로 편과 맞춘다 · 공개 영상만) +
  YouTube Analytics API(views · averageViewPercentage · averageViewDuration · likes · subscribersGained ·
  트래픽 소스 SHORTS = 쇼츠 피드). 토큰에 yt-analytics.readonly 가 없거나 실패하면 stats.json 을 안 쓴다(기획은 그대로).
토큰 값은 어디에도 찍지 않는다 · 메모리에서만 갱신한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
MARK = re.compile(r"Meow Remix · (\d{4}-\d{2}-\d{2}) (m\d{6}[a-l]?)")
STATS = "stats.json"
SHOW = 20                 # 기획에 보여 줄 최근 편 수
JUDGE_AGE_H = 48          # 이보다 어린 편은 순위에서 뺀다(통계가 아직 덜 쌓였다)
JUDGE_MIN_VIEWS = 20      # 조회수가 이보다 적으면 순위에서 뺀다(우연이 크다)


def plans(data_dir: str) -> dict[str, dict]:
    """편 id → 기획(꼴·자막·제목·slug·곡)."""
    out = {}
    for p in glob.glob(os.path.join(data_dir, "20??-??-??.json")) + glob.glob(os.path.join(data_dir, "20??-??-??-?.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        for c in d.get("concepts") or []:
            if c.get("id"):
                out[c["id"]] = {"format": c.get("format", ""), "caption": c.get("caption", ""), "title": c.get("title", ""),
                                "slug": c.get("slug", ""), "track": c.get("track", "")}
    return out


def uploads(yt, channel_id: str, n: int = 50) -> list[dict]:
    """최근 업로드 n편 중 표식이 있는 공개 영상 — [{id, video, published}]."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    if ch.get("id") != channel_id:
        raise SystemExit(f"❌ 토큰 채널({ch.get('id')})이 고양이 채널({channel_id})이 아니다")
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet,contentDetails", playlistId=up, maxResults=n).execute().get("items", [])
    by = {}
    for it in items:
        m = MARK.search(it["snippet"].get("description", ""))
        if m:
            by[it["contentDetails"]["videoId"]] = m.group(2)
    if not by:
        return []
    vids = yt.videos().list(part="status,snippet", id=",".join(by), maxResults=50).execute().get("items", [])
    return [{"id": by[v["id"]], "video": v["id"], "published": v["snippet"].get("publishedAt", "")}
            for v in vids if v.get("status", {}).get("privacyStatus") == "public"]


def metrics(ya, videos: list[str], start: str, end: str) -> dict[str, dict]:
    """영상별 views·평균 시청 %·평균 시청 초·좋아요·구독 + 쇼츠 피드 조회수."""
    out: dict[str, dict] = {}
    if not videos:
        return out
    r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, dimensions="video",
                           metrics="views,averageViewPercentage,averageViewDuration,likes,subscribersGained",
                           filters="video==" + ",".join(videos), sort="-views", maxResults=200).execute()
    for row in r.get("rows") or []:
        vid, views, pct, sec, likes, subs = row[:6]
        out[vid] = {"views": int(views), "avg_pct": round(float(pct), 1), "avg_sec": round(float(sec), 1),
                    "likes": int(likes), "subs": int(subs), "feed_views": 0}
    for vid in out:
        t = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, dimensions="insightTrafficSourceType",
                               metrics="views", filters=f"video=={vid}").execute()
        out[vid]["feed_views"] = sum(int(v) for k, v in (t.get("rows") or []) if k == "SHORTS")
    for v in out.values():
        v["feed_share"] = round(v["feed_views"] / v["views"], 2) if v["views"] else 0.0
    return out


def build_stats(ups: list[dict], mets: dict[str, dict], plan_by_id: dict[str, dict], channel: str, now: dt.datetime) -> dict:
    rows = []
    for u in sorted(ups, key=lambda x: x["published"], reverse=True):
        m = mets.get(u["video"]) or {"views": 0, "avg_pct": 0.0, "avg_sec": 0.0, "likes": 0, "subs": 0, "feed_views": 0, "feed_share": 0.0}
        rows.append({**u, **(plan_by_id.get(u["id"]) or {}), **m})
    return {"at": now.isoformat(timespec="minutes"), "channel": channel, "videos": rows}


def _age_h(v: dict, now: dt.datetime) -> float:
    try:
        p = dt.datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return 0.0
    return (now - p).total_seconds() / 3600


def lessons(stats: dict | None, now: dt.datetime | None = None) -> list[str]:
    """기획 사용자 메시지에 넣을 줄들(영어 — 모델용). 성적이 없으면 []."""
    vids = (stats or {}).get("videos") or []
    if not vids:
        return []
    now = now or dt.datetime.now(dt.timezone.utc)
    judge = [v for v in vids if _age_h(v, now) >= JUDGE_AGE_H and v.get("views", 0) >= JUDGE_MIN_VIEWS]
    best, worst = set(), set()
    if len(judge) >= 4:
        rank = sorted(judge, key=lambda v: (v["avg_pct"], v["feed_share"]), reverse=True)
        k = max(1, min(3, len(rank) // 3))           # 위·아래 1/3(최대 3편) — 둘이 겹치지 않게
        best = {v["video"] for v in rank[:k]}
        worst = {v["video"] for v in rank[-k:]}
    out = ["\n## How our recent Shorts did on YouTube (analytics — learn from it; never reuse a title or idea)",
           "Newest first. avg viewed = average % of the Short watched (over 100% means people replayed it); "
           "feed = share of views that came from the Shorts feed (the feed only keeps showing Shorts people don't swipe away).",
           "Do more of what the ★ Shorts did in their first second (the opening image, motion and caption) and less of what the ✗ ones did."]
    for v in vids[:SHOW]:
        tag = " ★ held viewers" if v["video"] in best else " ✗ lost viewers" if v["video"] in worst else ""
        young = " (under 2 days old — too early)" if _age_h(v, now) < JUDGE_AGE_H else ""
        out.append(f"- {v.get('published', '')[:10]} {v.get('format', '?')} · caption \"{v.get('caption', '')}\" · "
                   f"{v.get('title', '')} · {v.get('views', 0)} views · avg viewed {v.get('avg_pct', 0)}% · "
                   f"feed {round(100 * v.get('feed_share', 0))}%{tag}{young}")
    if not best:
        out.append("Too few Shorts with enough views to rank yet — keep testing clearly different hooks (opening image, motion, caption).")
    return out


def load(data_dir: str) -> dict | None:
    try:
        with open(os.path.join(data_dir, STATS), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def pull(data_dir: str, token: str, days: int = 10, now: dt.datetime | None = None, yt=None, ya=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if yt is None or ya is None:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(token)
        if not creds.valid:
            creds.refresh(Request())                    # 메모리에서만 — 파일에 다시 쓰지 않는다
        yt = yt or build("youtube", "v3", credentials=creds, cache_discovery=False)
        ya = ya or build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    sys.path.insert(0, HERE)
    import post as P
    ups = uploads(yt, P.CHANNEL_ID)
    end = now.astimezone(KST).date()
    mets = metrics(ya, [u["video"] for u in ups], (end - dt.timedelta(days=days)).isoformat(), end.isoformat())
    st = build_stats(ups, mets, plans(data_dir), P.CHANNEL_ID, now)
    with open(os.path.join(data_dir, STATS), "w", encoding="utf-8", newline="\n") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    return st


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="분석 담당 — 새 고양이 채널 최근 쇼츠 성적 → stats.json(기획이 읽는다)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull")
    p.add_argument("--dir", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--days", type=int, default=10)
    a = ap.parse_args(argv)
    st = pull(a.dir, a.token, a.days)
    vs = st["videos"]
    print(f"📊 공개 쇼츠 {len(vs)}편 · 조회수 합 {sum(v['views'] for v in vs)} · "
          f"평균 시청 % 중앙값 {sorted(v['avg_pct'] for v in vs)[len(vs) // 2] if vs else '-'}")
    for line in lessons(st)[3:]:
        print(" ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
