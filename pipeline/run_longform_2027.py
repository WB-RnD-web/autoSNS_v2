#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'2027 정미년 깊이 보기' 롱폼 — 검사 → 렌더 → 예약 업로드 (2026-10-20).

입력: 루틴이 routine/fortune_lf27 에 올린 output/fortune_lf27/E01_2026-11-02.json.
검사(longform_2027.check)를 못 넘으면 렌더도 업로드도 없다. 같은 편은 두 번 올리지 않는다
(ledger + 유튜브 설명란 표식 '2027 정미년 깊이 보기 E01'). 업로드 길은 주간 롱폼과 같다(upload_youtube_novel.publish):
카테고리 24 · ko · 재생목록 '2027 정미년 깊이 보기' · 그 편의 날 20:00 KST 예약 공개(지났으면 바로 공개).

    python run_longform_2027.py ../output/fortune_lf27/E01_2026-11-02.json
    python run_longform_2027.py ../docs/samples/longform_2027_E01.json --lenient --no-upload [--upto 4]   # 시험 렌더
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import config
import longform_2027 as LF


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


def youtube_twice(yt, eid: str) -> str | None:
    import ai_news
    return LF.already_uploaded(ai_news.recent_uploads(yt, max_items=50), eid)


def process(path: str, args, led: dict) -> dict:
    res = {"script": path, "error": None, "uploaded": None, "skipped": None}
    now = dt.datetime.now(LF.KST)
    errs, warns, sc = LF.check_file(path, now=now, strict=not args.lenient)
    eid = LF._s(sc.get("episode"))
    res["episode"] = eid
    for w in warns:
        print(f"::warning title=2027 롱폼 검사::{w}")
    if errs:
        for e in errs:
            print(f"::error title=2027 롱폼 검사::{e}")
        res["error"] = f"검사 실패 {len(errs)}건: {errs[0]}"
        return res
    plan = LF.compose(sc, upto=args.upto or None)
    st = plan["stats"]
    print(f"▶ {eid} ({plan['publish']} {LF.PUBLISH_HHMM}) · {st['chars']:,}자 · 조각 {st['chunks']} · 파트 {st['parts']}"
          f" · 예상 {st['est_min']}분")
    if eid in led and not args.force:
        print(f"   ⏭️ 이미 올림({led[eid]}) — 건너뜀")
        res.update(skipped="ledger", uploaded=str(led[eid]))
        return res
    uploading = not args.no_upload and not args.upto and has_credentials()
    if uploading:
        try:
            import upload_youtube_novel as N
            vid = youtube_twice(N.get_service(), eid)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 유튜브 이중 확인 건너뜀(ledger 만으로 판정): {str(e)[:160]}")
            vid = None
        if vid and not args.force:
            print(f"   ⏭️ '{LF.marker(eid)}' 영상이 이미 채널에 있다({vid}) — 다시 올리지 않는다")
            led[eid] = {"video_id": vid, "privacy": "?", "at": time.time()}
            res.update(skipped="uploaded", uploaded=f"https://youtu.be/{vid}")
            return res

    import longform_2027_render as R
    wd = os.path.join(str(config.OUTPUT), "_work", f"lf27_{eid}")
    out = R.render(plan, args.out_dir or str(config.RENDERS_DIR), wd)
    res.update({k: out.get(k) for k in ("video", "thumb", "audio", "duration_min", "fallback", "tts_sec", "media_sec",
                                         "video_sec", "cpm_measured", "speech_sec", "chars")})
    if not args.upto:
        msg = LF.check_duration(out["duration_sec"])
        if msg:
            print(f"::error title=2027 롱폼 길이::{msg}")
            res["error"] = msg
            return res
        lo, hi = LF.SPEC.est_min
        if not lo <= out["duration_min"] <= hi:
            print(f"::warning title=2027 롱폼 길이::{out['duration_min']}분 — 목표 {lo:.0f}~{hi:.0f}분 밖(LF27_CPM 을 실측에 맞출 것)")
    title = LF.title_for(plan)
    desc = LF.description_for(plan, out["chapters"], sc)
    with open(os.path.splitext(out["video"])[0] + "_meta.json", "w", encoding="utf-8") as f:
        json.dump({"title": title, "description": desc, "tags": LF.tags_for(plan["ep"]), "chapters": out["chapters"],
                   "publish_at": LF.publish_at(plan["ep"], now), "render": {k: v for k, v in res.items() if k != "script"}},
                  f, ensure_ascii=False, indent=1)
    print(f"   제목: {title}\n   ── 설명 ──\n{desc}\n   ──────────")
    if not uploading:
        print("   ⏭️ 업로드 안 함(--no-upload · --upto · 자격증명 없음)")
        return res
    privacy = "private" if args.force_private else "public"
    at = None if args.force_private else LF.publish_at(plan["ep"], now)
    import upload_youtube_novel as N
    pub = N.publish(out["video"], title, desc, privacy, playlist_title=LF.PLAYLIST, tags=LF.tags_for(plan["ep"]),
                    category_id=LF.CATEGORY, thumbnail=out["thumb"], default_language="ko",
                    playlist_description=LF.PLAYLIST_DESC, synthetic=LF.SYNTHETIC, audio_language="ko", publish_at=at)
    res["uploaded"] = pub.get("url")
    led[eid] = {"video_id": pub.get("video_id"), "privacy": privacy, "publish_at": at, "at": time.time()}
    print(f"✅ 업로드 {pub.get('url')} ({'예약 ' + at if at else privacy}) · 재생목록 {pub.get('playlist_id')}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="2027 정미년 깊이 보기 — 검사·렌더·업로드")
    ap.add_argument("scripts", nargs="+", help="output/fortune_lf27/E01_2026-11-02.json")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--lenient", action="store_true", help="날짜·파일 이름을 경고로(업로드 없음·비공개일 때만)")
    ap.add_argument("--force", action="store_true", help="ledger·유튜브 표식이 있어도 다시")
    ap.add_argument("--upto", type=int, default=0, help="앞 파트 n 개만 렌더(시험 · 업로드 없음)")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--ledger-path", default=None)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()
    config.load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if args.lenient and not (args.no_upload or args.force_private or args.upto):
        print("::warning::--lenient 무시 — 공개 업로드에서는 느슨 모드를 쓰지 않는다")
        args.lenient = False
    led = load_ledger(args.ledger_path)
    results, t0 = [], time.time()
    for p in args.scripts:
        try:
            results.append(process(p, args, led))
        except Exception as e:  # noqa: BLE001
            print(f"::error title=2027 롱폼::{p}: {e}")
            results.append({"script": p, "error": str(e)})
        save_ledger(args.ledger_path, led)
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
    print(f"  걸린 시간 {round(time.time() - t0)}초")
    return 1 if any(r.get("error") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
