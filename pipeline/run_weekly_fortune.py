#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주간 띠별 운세 풀이 — 검사 → 렌더 → 업로드 (2026-10-01).

입력은 루틴이 routine/weekly_fortune 에 올린 output/weekly_fortune/<월요일>_weekly_fortune.json.
검사(weekly_fortune.check)를 못 넘으면 렌더도 업로드도 하지 않는다. 같은 주는 두 번 올리지 않는다
(ledger + 유튜브 설명란 표식 '주간 띠별 운세 <주>').

    python run_weekly_fortune.py ../output/weekly_fortune/2026-10-05_weekly_fortune.json
    python run_weekly_fortune.py ../docs/samples/weekly_fortune_sample.json --lenient --no-upload   # 견본 렌더만
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import config
import weekly_fortune as WF


def load_ledger(path: str | None) -> dict:
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_ledger(path: str | None, led: dict):
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(led, f, ensure_ascii=False, indent=1)


def has_credentials() -> bool:
    import upload_youtube_novel as N
    return os.path.exists(N._paths()[1])


def daily_playlist_id(yt) -> str | None:
    """설명란에 넣을 '오늘의 띠별 운세' 재생목록 id(1 unit). 실패하면 None."""
    try:
        import upload_youtube_novel as N
        return N.find_playlist(yt, WF.DAILY_PLAYLIST)
    except Exception as e:  # noqa: BLE001
        print(f"   (오늘의 띠별 운세 재생목록 조회 건너뜀: {str(e)[:120]})")
        return None


def youtube_twice(yt, week: str) -> str | None:
    """유튜브 쪽 이중 확인 — 최근 업로드 설명란에 이 주 표식이 있으면 그 영상 id(3 units)."""
    import ai_news
    return WF.already_uploaded(ai_news.recent_uploads(yt, max_items=50), week)


def process(path: str, args, led: dict) -> dict:
    res = {"script": path, "error": None, "uploaded": None, "skipped": None}
    now = dt.datetime.now(WF.KST)
    errs, warns, sc = WF.check_file(path, now=now, strict=not args.lenient)
    week = WF._s(sc.get("week"))
    res["week"] = week
    for w in warns:
        print(f"::warning title=주간 운세 검사(느슨)::{w}")
    if errs:
        for e in errs:
            print(f"::error title=주간 운세 검사::{e}")
        res["error"] = f"검사 실패 {len(errs)}건: {errs[0]}"
        return res
    plan = WF.compose(sc)
    st = plan["stats"]
    print(f"▶ {week} ({plan['range']}) · {st['chars']:,}자 · 조각 {st['chunks']}개 · 예상 {st['est_min']}분")
    if week in led and not args.force:
        print(f"   ⏭️ 이미 올림({led[week]}) — 건너뜀")
        res.update(skipped="ledger", uploaded=str(led[week]))
        return res
    uploading = not args.no_upload and has_credentials()
    yt = None
    if uploading:
        try:
            import upload_youtube_novel as N
            yt = N.get_service()
            vid = youtube_twice(yt, week)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 유튜브 이중 확인 건너뜀(ledger 만으로 판정): {str(e)[:160]}")
            vid = None
        if vid and not args.force:
            print(f"   ⏭️ '{WF.marker(week)}' 영상이 이미 채널에 있다({vid}) — 다시 올리지 않는다")
            led[week] = {"video_id": vid, "privacy": "?", "at": time.time()}
            res.update(skipped="uploaded", uploaded=f"https://youtu.be/{vid}")
            return res

    import weekly_fortune_render as R
    wd = os.path.join(str(config.OUTPUT), "_work", f"weekly_fortune_{plan['monday']}")
    out = R.render(plan, str(config.RENDERS_DIR), wd)
    res.update({k: out[k] for k in ("video", "thumb", "table", "duration_min", "fallback", "tts_sec")})
    msg = WF.check_duration(out["duration_sec"])
    if msg:
        print(f"::error title=주간 운세 길이::{msg}")
        res["error"] = msg
        return res
    if not WF.EST_MIN[0] <= out["duration_min"] <= WF.EST_MIN[1]:
        print(f"::warning title=주간 운세 길이::{out['duration_min']}분 — 목표 {WF.EST_MIN[0]:.0f}~{WF.EST_MIN[1]:.0f}분 밖"
              " (CPM 추정을 실측에 맞출 것)")
    title = WF.title_for(plan)
    desc = WF.description_for(plan, out["chapters"], daily_playlist_id(yt) if yt else None)
    print(f"   제목: {title}\n   ── 설명 ──\n{desc}\n   ──────────")
    if not uploading:
        print("   ⏭️ 업로드 안 함(--no-upload 또는 자격증명 없음)")
        return res
    privacy = "private" if args.force_private else "public"
    at = None if args.force_private else WF.publish_at(dt.date.fromisoformat(plan["monday"]), now)
    import upload_youtube_novel as N
    pub = N.publish(out["video"], title, desc, privacy,
                    playlist_title=WF.PLAYLIST, tags=list(WF.TAGS), category_id=WF.CATEGORY,
                    thumbnail=out["thumb"], default_language="ko", playlist_description=WF.PLAYLIST_DESC,
                    synthetic=WF.SYNTHETIC, audio_language="ko", publish_at=at)
    res["uploaded"] = pub.get("url")
    led[week] = {"video_id": pub.get("video_id"), "privacy": privacy, "publish_at": at, "at": time.time()}
    print(f"✅ 업로드 {pub.get('url')} ({'예약 ' + at if at else privacy}) · 재생목록 {pub.get('playlist_id')}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="주간 띠별 운세 풀이 — 검사·렌더·업로드")
    ap.add_argument("scripts", nargs="+", help="output/weekly_fortune/<월요일>_weekly_fortune.json")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--lenient", action="store_true",
                    help="주·파일 이름이 달라도 경고로(견본 점검 — 업로드 없음 또는 비공개일 때만 먹힌다)")
    ap.add_argument("--force", action="store_true", help="ledger·유튜브 표식이 있어도 다시")
    ap.add_argument("--ledger-path", default=None)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()
    config.load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if args.lenient and not (args.no_upload or args.force_private):
        print("::warning::--lenient 무시 — 공개 업로드에서는 느슨 모드를 쓰지 않는다")
        args.lenient = False
    led = load_ledger(args.ledger_path)
    results, t0 = [], time.time()
    for p in args.scripts:
        try:
            results.append(process(p, args, led))
        except Exception as e:  # noqa: BLE001
            print(f"::error title=주간 운세::{p}: {e}")
            results.append({"script": p, "error": str(e)})
        save_ledger(args.ledger_path, led)          # 올라간 건 올라간 거다 — 바로 남긴다
    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)) or ".", exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results, "sec": round(time.time() - t0)}, f, ensure_ascii=False, indent=1)
    print("\n──────── 요약 ────────")
    for r in results:
        print(f"  {os.path.basename(r['script'])}: "
              + (f"SKIP({r['skipped']}) " if r.get("skipped") else "")
              + (f"{r.get('duration_min')}분 " if r.get("duration_min") else "")
              + (f"yt={r['uploaded']} " if r.get("uploaded") else "")
              + (f"⚠️ {r['error']}" if r.get("error") else ""))
    return 1 if any(r.get("error") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
