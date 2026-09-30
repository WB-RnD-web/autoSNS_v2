#!/usr/bin/env python3
"""두 채널의 실제 숫자 → stats.json (릴스 자리표시자 {{wb.…}}·{{ntt.…}}·{{vid.…}} 와 일요일 성적표). YouTube Data API 읽기만.

    python insta/stats.py --out output/insta_render/stats.json [--date 2026-10-04]
    python insta/stats.py --mock --out output/insta_render/stats.json      # 네트워크 없이(테스트 — 가짜 숫자, mock 표시)

토큰: 공개 통계만 읽으므로 토큰 하나면 두 채널 다 된다(채널 ID 로 조회).
  INSTA_TOKEN_FILES = 쉼표로 구분한 토큰 파일(기본 pipeline/secrets/token_novel.json,pipeline/secrets/token_gumiho.json)
  워크플로가 시크릿 YT_TOKEN_JSON_NOVEL(왕별이)·YT_TOKEN_JSON_GUMIHO(Nine Tails Tales)로 만든다.
  ★토큰은 메모리에서만 갱신한다(파일에 다시 쓰지 않는다) · 토큰 내용은 어디에도 찍지 않는다.
공개 영상만 센다 — 비공개·예약 영상의 제목·숫자가 릴스로 새지 않게.
이번 주 = 기준일(KST)과 그 앞 6일, 그 사이에 공개된 영상. 조회수는 지금까지 누적(공개 API 값은 스튜디오보다 조금 늦다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import insta as I  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
DEFAULT_TOKENS = [os.path.join(ROOT, "pipeline", "secrets", "token_novel.json"),
                  os.path.join(ROOT, "pipeline", "secrets", "token_gumiho.json")]


def token_files() -> list[str]:
    env = os.environ.get("INSTA_TOKEN_FILES", "")
    files = [p.strip() for p in env.split(",") if p.strip()] or DEFAULT_TOKENS
    return [p for p in files if os.path.exists(p)]


def service():
    """존재하는 첫 토큰으로 YouTube 서비스. 없으면 None."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    for p in token_files():
        try:
            creds = Credentials.from_authorized_user_file(p)       # 파일에 적힌 스코프 그대로(invalid_scope 방지)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())                            # 메모리에서만 — 파일에 다시 쓰지 않는다
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            print(f"   🔑 토큰: {os.path.basename(p)}")
            return yt
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 토큰 {os.path.basename(p)} 사용 실패(다음 후보): {str(e)[:120]}")
    return None


def clean_title(t: str) -> str:
    t = re.sub(r"#\S+", "", t or "")
    t = re.sub(r"\s+", " ", t).strip(" |·-")
    return t if len(t) <= 60 else t[:59].rstrip() + "…"


def iso_sec(d: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s


def _utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def video_rows(yt, ids: list[str]) -> dict:
    """영상 ID → 공개 통계(공개 영상만)."""
    out = {}
    for k in range(0, len(ids), 50):
        chunk = [i for i in ids[k:k + 50] if i]
        if not chunk:
            continue
        resp = yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(chunk)).execute()
        for it in resp.get("items", []):
            if it.get("status", {}).get("privacyStatus") != "public":
                continue
            st = it.get("statistics", {})
            out[it["id"]] = {"title": clean_title(it["snippet"]["title"]), "views": int(st.get("viewCount", 0)),
                             "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0)),
                             "published": it["snippet"]["publishedAt"],
                             "sec": iso_sec(it.get("contentDetails", {}).get("duration", ""))}
    return out


def channel(yt, cid: str, date: dt.date) -> tuple[dict, dict]:
    resp = yt.channels().list(part="snippet,statistics,contentDetails", id=cid).execute()
    items = resp.get("items") or []
    if not items:
        raise RuntimeError(f"채널 {cid} 없음")
    ch = items[0]
    st = ch["statistics"]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    lo = dt.datetime.combine(date - dt.timedelta(days=6), dt.time(0, 0), KST)
    hi = dt.datetime.combine(date, dt.time(23, 59, 59), KST)
    ids, token = [], None
    for _ in range(4):                                   # 최신순 — 최대 200개, 기간보다 오래되면 멈춘다
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50,
                                     pageToken=token).execute()
        old = False
        for it in pl.get("items", []):
            pub = it["contentDetails"].get("videoPublishedAt")
            ids.append(it["contentDetails"]["videoId"])
            if pub and _utc(pub) < lo - dt.timedelta(days=30):
                old = True
        token = pl.get("nextPageToken")
        if old or not token:
            break
    rows = video_rows(yt, ids)
    recent = sorted(rows.items(), key=lambda kv: kv[1]["published"], reverse=True)
    week = [(vid, r) for vid, r in recent if lo <= _utc(r["published"]).astimezone(KST) <= hi]
    top = max(week, key=lambda kv: kv[1]["views"], default=None)
    return {
        "id": cid, "title": ch["snippet"]["title"],
        "subs": int(st.get("subscriberCount", 0)), "views": int(st.get("viewCount", 0)),
        "videos": int(st.get("videoCount", 0)),
        "week": {"from": lo.date().isoformat(), "to": hi.date().isoformat(), "uploads": len(week),
                 "views": sum(r["views"] for _, r in week),
                 "shorts": sum(1 for _, r in week if 0 < r["sec"] <= 180),
                 "top": ({"id": top[0], "title": top[1]["title"], "views": top[1]["views"]} if top else None)},
        "recent": [{"id": vid, **r} for vid, r in recent[:12]],
    }, rows


def catalog_video_ids() -> list[str]:
    cat = I.catalog()
    ids = set(cat.get("videos", {}).values())
    for t in cat["topics"]:
        ids |= set((t.get("videos") or {}).values())
    return sorted(ids)


def collect(date: dt.date) -> dict:
    yt = service()
    if yt is None:
        raise SystemExit("❌ 쓸 수 있는 YouTube 토큰이 없다 — INSTA_TOKEN_FILES 또는 pipeline/secrets/token_*.json")
    cat = I.catalog()
    out = {"generated_at": dt.datetime.now(KST).isoformat(timespec="seconds"), "date": date.isoformat(),
           "mock": False, "channels": {}, "videos": {}}
    for key, meta in cat["channels"].items():
        ch, rows = channel(yt, meta["id"], date)
        out["channels"][key] = ch
        out["videos"].update(rows)
        wk = ch["week"]
        print(f"   📊 {meta['name']}: 구독 {ch['subs']:,} · 조회 {ch['views']:,} · 영상 {ch['videos']:,}"
              f" · 이번 주 {wk['uploads']}편/{wk['views']:,}회")
    extra = [v for v in catalog_video_ids() if v not in out["videos"]]
    out["videos"].update(video_rows(yt, extra))
    return out


def mock(date: dt.date) -> dict:
    """테스트용 가짜 숫자(★mock=true — 이 값으로 만든 영상은 게시하지 않는다)."""
    vids = {v: {"title": f"테스트 영상 {k}", "views": 100 + 37 * k, "likes": k, "comments": 0,
                "published": f"{date.isoformat()}T00:00:00Z", "sec": 30}
            for k, v in enumerate(catalog_video_ids(), 1)}
    ch = {}
    for k, (key, meta) in enumerate(I.catalog()["channels"].items()):
        top_id = f"mock{key}000000"[:11]
        vids[top_id] = {"title": "테스트 영상 이번 주 최고", "views": 1234, "likes": 5, "comments": 1,
                        "published": f"{date.isoformat()}T00:00:00Z", "sec": 40}
        ch[key] = {"id": meta["id"], "title": meta["name"], "subs": 194 - 190 * k, "views": 143930 - 143000 * k,
                   "videos": 462 - 458 * k,
                   "week": {"from": (date - dt.timedelta(days=6)).isoformat(), "to": date.isoformat(),
                            "uploads": 20 - 18 * k, "views": 12345 - 12000 * k, "shorts": 14 - 13 * k,
                            "top": {"id": top_id, "title": "테스트 영상 이번 주 최고", "views": 1234}},
                   "recent": []}
    return {"generated_at": dt.datetime.now(KST).isoformat(timespec="seconds"), "date": date.isoformat(),
            "mock": True, "channels": ch, "videos": vids}


def main() -> int:
    ap = argparse.ArgumentParser(description="두 채널 실제 숫자 → stats.json")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "insta_render", "stats.json"))
    ap.add_argument("--date", help="기준일(KST, 기본 오늘) — 이번 주 = 이 날과 앞 6일")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(KST).date()
    data = mock(date) if a.mock else collect(date)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"✅ {a.out} · {'MOCK' if data['mock'] else '실제'} · 영상 {len(data['videos'])}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
