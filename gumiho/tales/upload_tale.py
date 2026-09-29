#!/usr/bin/env python3
"""Nine Tails Tales 업로드 — 본편 + 쇼츠. ★기본은 비공개(private).

    python gumiho/tales/upload_tale.py <script.json> --renders output/gumiho/tales
    python gumiho/tales/upload_tale.py <script.json> --publish-at 2026-10-10T15:00:00Z   # 예약 공개(그때까지 비공개)

공개 방식은 레포 변수 TALES_PUBLISH 로 정한다(워크플로가 넘긴다):
  private   (기본) 비공개로만 올린다 — 사람이 스튜디오에서 보고 공개
  scheduled 비공개 + 예약 공개(다음 토요일 15:00 UTC = 미국 동부 오전 11시·한국 자정)
올리지 않는 경우(코드로 막는다): mock 렌더 · 이미 올린 편(ledger) · 대본 검사 실패.
토큰: YT_TOKEN_NOVEL 이 가리키는 파일(워크플로가 시크릿 YT_TOKEN_JSON_GUMIHO 로 만든다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import tales as T  # noqa: E402

PLAYLIST = "Nine Tails Tales — Every Tale"
PLAYLIST_DESC = "Every tale Gumi has told so far, in order. Korean and East Asian myths, monsters and ghost stories."
CATEGORY = "24"          # Entertainment


def next_saturday_15utc(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    d = now + dt.timedelta(days=(5 - now.weekday()) % 7)
    t = d.replace(hour=15, minute=0, second=0, microsecond=0)
    if t <= now + dt.timedelta(hours=6):          # 너무 가까우면 다음 주
        t += dt.timedelta(days=7)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def insert(yt, video: str, md: dict, privacy: str, publish_at: str | None) -> str:
    from googleapiclient.http import MediaFileUpload
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}
    if publish_at:
        status["publishAt"] = publish_at
    body = {"snippet": {"title": md["title"][:100], "description": md["description"][:4900], "tags": md["tags"],
                        "categoryId": CATEGORY, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, chunksize=32 * 1024 * 1024, resumable=True))
    resp, last = None, -1
    while resp is None:
        st, resp = req.next_chunk()
        if st and int(st.progress() * 10) != last:
            last = int(st.progress() * 10)
            print(f"   업로드 {last * 10}%", flush=True)
    return resp["id"]


def captions(yt, vid: str, srt: str) -> bool:
    """영어 자막 트랙. force-ssl 스코프가 없으면 실패한다 — 그래도 유튜브 자동 자막이 있으니 건너뛴다."""
    from googleapiclient.http import MediaFileUpload
    try:
        yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English",
                                                               "isDraft": False}},
                             media_body=MediaFileUpload(srt, mimetype="application/octet-stream")).execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   ⏭️ 자막 트랙 건너뜀(자동 자막 사용): {str(e)[:140]}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "gumiho", "tales"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "gumiho", "tales_ledger.json"))
    ap.add_argument("--mode", default=os.environ.get("TALES_PUBLISH", "private"), choices=["private", "scheduled"])
    ap.add_argument("--publish-at", help="예약 공개 시각(UTC ISO) — 주면 mode 무시")
    ap.add_argument("--no-short", action="store_true")
    a = ap.parse_args()

    s = T.load(a.script)
    errs = T.check(s, a.script)
    if errs:
        print("::error::대본 검사 실패 — 올리지 않는다\n  " + "\n  ".join(errs))
        return 2
    stem = f"{s['id']:03d}_{s['slug']}"
    with open(os.path.join(a.renders, f"{stem}_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    if rm.get("mock"):
        print("::error::mock 렌더(가짜 그림·목소리)는 올리지 않는다")
        return 2
    led = {}
    if os.path.exists(a.ledger):
        with open(a.ledger, encoding="utf-8") as f:
            led = json.load(f)
    done = led.get(stem, {})
    publish_at = a.publish_at or (next_saturday_15utc() if a.mode == "scheduled" else None)
    md = T.meta(s, rm.get("starts"))

    import upload_youtube_novel as U
    yt = U.get_service()
    if not done.get("long"):
        vid = insert(yt, rm["video"], md, "private", publish_at)
        done["long"] = f"https://youtu.be/{vid}"
        print(f"✅ 본편 {done['long']} · {'예약 ' + publish_at if publish_at else '비공개'}")
        done["thumb"] = bool(U.set_thumbnail(yt, vid, rm["thumb"]))
        if not done["thumb"]:
            print("   ⚠️ 썸네일 실패 — 채널 전화 인증(youtube.com/verify)이 안 됐으면 맞춤 썸네일이 막힌다")
        done["captions"] = captions(yt, vid, rm["srt"])
        if publish_at:
            try:
                pid = U.ensure_playlist(yt, PLAYLIST, PLAYLIST_DESC, privacy="public")
                U.add_to_playlist(yt, pid, vid)
            except Exception as e:  # noqa: BLE001
                print(f"   ⚠️ 재생목록 실패(업로드는 성공): {e}")
        led[stem] = done
        _save(a.ledger, led)
    else:
        print(f"⏭️ 본편 이미 올림: {done['long']}")
    short = rm.get("short", {})
    if not a.no_short and short.get("video") and not done.get("short"):
        smd = T.meta(s, None, short_of=done["long"])["short"]
        s_at = None
        if publish_at:                               # 쇼츠는 본편 하루 전에 풀어 본편으로 끌어온다
            s_at = (dt.datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%SZ") - dt.timedelta(days=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        sid = insert(yt, short["video"], smd, "private", s_at)
        done["short"] = f"https://youtu.be/{sid}"
        print(f"✅ 쇼츠 {done['short']}")
        led[stem] = done
        _save(a.ledger, led)
    print(json.dumps({stem: done}, ensure_ascii=False))
    return 0


def _save(path: str, led: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
