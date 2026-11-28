#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""왕별이 라디오 · 밤 편 — 검사 → 구성 → 렌더(목소리 F2·피아노·빗소리 30분) → 그날 20:00 예약 업로드 (2026-11-28).

입력은 tools/radio_api.py 가 쓴 대본(output/radio/<날짜>.json)이다.
- 검사(radio_night.check)를 못 넘으면 렌더도 업로드도 하지 않는다.
- 같은 날 편은 두 번 올리지 않는다. ledger(Actions 캐시)와 유튜브 설명란 끝 줄 '왕별이 라디오 · 밤 편 2026-11-29' 표식으로 본다.
- 업로드는 롱폼과 같은 길(upload_youtube_novel.publish)로 한다. 카테고리 24 · ko · 재생목록 '잠들기 전 복 받는 시간'
  · 그날 20:00 KST 예약 공개(이미 지났으면 바로 공개).

    python run_radio_night.py ../output/radio/2026-11-29.json --ledger-path ../output/radio_ledger.json
    python run_radio_night.py ../docs/samples/radio_night_2026-11-28.json --no-upload --lenient   # 시험 렌더
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import config
import radio_night as N

VOICE = os.environ.get("RADIO_VOICE") or "F2"


def load_json(path: str | None) -> dict:
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_json(path: str | None, data: dict):
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)


def has_credentials() -> bool:
    import upload_youtube_novel as U
    return os.path.exists(U._paths()[1])


def check_length(info: dict) -> str | None:
    """말 10~24분 · 전체가 빗소리 꼬리만큼 — 벗어나면 뭔가 고장 났다."""
    v, t = info["voice_end_min"], info["total_min"]
    if not 10 <= v <= 24:
        return f"말 {v}분 — 10~24분 밖(대본·목소리 확인)"
    if abs(t - v - N.RAIN_MIN) > 1.0:
        return f"전체 {t}분 — 말 {v}분 + 빗소리 {N.RAIN_MIN:.0f}분과 다르다"
    return None


def process(path: str, args, led: dict) -> dict:
    res = {"script": path, "error": None, "uploaded": None, "skipped": None}
    with open(path, encoding="utf-8") as f:
        sc = json.load(f)
    now = dt.datetime.now(N.KST)
    today = N.tonight(now)
    d = today
    if args.lenient:
        try:
            d = dt.date.fromisoformat(str(sc.get("date")))
        except ValueError:
            pass
    res["date"] = d.isoformat()
    errs = N.check(sc, d)
    if errs:
        for e in errs:
            print(f"::error title=밤 편 검사::{e}")
        res["error"] = f"검사 실패 {len(errs)}건: {errs[0]}"
        return res
    plan = N.compose(sc, d)
    st = N.stats(plan)
    print(f"▶ 밤 편 {d} · 내일 {plan['for_label']} · 이야기 '{plan['story']}' · {st['chars']:,}자 · 조각 {st['chunks']}"
          f" · 말 예상 {st['est_min']}분 + 빗소리 {N.RAIN_MIN:.0f}분")
    key = d.isoformat()
    if key in led and not args.force:
        print(f"   ⏭️ 이미 올림({led[key]}) — 건너뜀")
        res.update(skipped="ledger", uploaded=str(led[key]))
        return res
    uploading = not args.no_upload and has_credentials()
    if uploading:
        try:
            import ai_news
            import upload_youtube_novel as U
            vid = N.already_uploaded(ai_news.recent_uploads(U.get_service(), max_items=50), d)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 유튜브 이중 확인 건너뜀(ledger 만으로 판정): {str(e)[:160]}")
            vid = None
        if vid and not args.force:
            print(f"   ⏭️ '{N.marker(d)}' 영상이 이미 채널에 있다({vid}) — 다시 올리지 않는다")
            led[key] = {"video_id": vid, "privacy": "?", "at": time.time()}
            res.update(skipped="uploaded", uploaded=f"https://youtu.be/{vid}")
            return res

    import radio_night_render as R
    out_dir = args.out_dir or str(config.RENDERS_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out_mp4 = os.path.join(out_dir, f"{key}_radio_night.mp4")
    wd = os.path.join(str(config.OUTPUT), "_work", f"radio_{key}")
    info = R.render(plan, out_mp4, wd, voice=VOICE)
    res.update({k: info.get(k) for k in ("video", "thumb", "total_min", "voice_end_min", "mb", "media_sec",
                                         "video_sec", "story_bg")})
    res["tts"] = info.get("tts")
    msg = check_length(info)
    if msg:
        print(f"::error title=밤 편 길이::{msg}")
        res["error"] = msg
        return res
    title = N.title_for(plan)
    desc = N.description_for(plan, info["chapters"])
    at = None if args.force_private else N.publish_at(d, now)
    save_json(os.path.splitext(out_mp4)[0] + "_meta.json",
              {"title": title, "description": desc, "tags": N.tags_for(plan), "publish_at": at, "render": res})
    print(f"   제목: {title}\n   ── 설명 ──\n{desc}\n   ──────────")
    print(f"   🎬 {info['total_min']}분(말 {info['voice_end_min']}분) · {info['mb']}MB · 목소리·소리 {info['media_sec']}초"
          f" · 영상 {info['video_sec']}초")
    if not uploading:
        print("   ⏭️ 업로드 안 함(--no-upload · 자격증명 없음)")
        return res
    privacy = "private" if args.force_private else "public"
    import upload_youtube_novel as U
    pub = U.publish(info["video"], title, desc, privacy, playlist_title=N.PLAYLIST, tags=N.tags_for(plan),
                    category_id=N.CATEGORY, thumbnail=info["thumb"], default_language="ko",
                    playlist_description=N.PLAYLIST_DESC, synthetic=N.SYNTHETIC, audio_language="ko", publish_at=at)
    res["uploaded"] = pub.get("url")
    led[key] = {"video_id": pub.get("video_id"), "privacy": privacy, "publish_at": at, "at": time.time()}
    print(f"✅ 업로드 {pub.get('url')} ({'예약 ' + at if at else privacy}) · 재생목록 {pub.get('playlist_id')}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="왕별이 라디오 밤 편 — 검사·렌더·업로드")
    ap.add_argument("scripts", nargs="+")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--lenient", action="store_true", help="대본 날짜를 그대로 쓴다(업로드 없음·비공개일 때만)")
    ap.add_argument("--force", action="store_true", help="ledger·유튜브 표식이 있어도 다시")
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
    if args.lenient and not (args.no_upload or args.force_private):
        print("::warning::--lenient 무시 — 공개 업로드에서는 대본 날짜를 오늘 밤으로만 본다")
        args.lenient = False
    led = load_json(args.ledger_path)
    results, t0 = [], time.time()
    for p in args.scripts:
        try:
            results.append(process(p, args, led))
        except Exception as e:  # noqa: BLE001
            print(f"::error title=밤 편::{p}: {e}")
            results.append({"script": p, "error": str(e)})
        save_json(args.ledger_path, led)
    save_json(args.log, {"results": results, "sec": round(time.time() - t0)})
    print("\n──────── 요약 ────────")
    for r in results:
        print(f"  {os.path.basename(r['script'])}: "
              + (f"SKIP({r['skipped']}) " if r.get("skipped") else "")
              + (f"{r.get('total_min')}분 " if r.get("total_min") else "")
              + (f"yt={r['uploaded']} " if r.get("uploaded") else "")
              + (f"⚠️ {r['error']}" if r.get("error") else ""))
    print(f"  걸린 시간 {round(time.time() - t0)}초")
    return 1 if any(r.get("error") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
