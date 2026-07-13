#!/usr/bin/env python3
"""낭독형 스토리 오케스트레이터 — 사연(sayeon)/괴담(gwedam) 완결형 단편 → 유튜브(+재생목록).

소설(run_novel) 사상과 동일하되 시리즈/캐논 없음. 업로드·재생목록·썸네일 지정은
upload_youtube_novel 재사용(같은 채널 → YT_TOKEN_JSON_NOVEL 확장 스코프 토큰).

각 스펙 JSON 마다:
  ① story_render.render(segments→TTS→자막 번인 + 정적 FLUX 배경) → mp4
  ② FLUX 썸네일 → upload_youtube_novel.publish(업로드 + 커스텀 썸네일 + 재생목록 추가)
  ③ pinned_comment 는 로그로 안내(YouTube API 로 '고정'은 불가 → 수동 고정)
  ④ ledger dedupe(키=<date>_<story_id>), 로그 기록

사용:
  python run_story.py --topic sayeon ../output/sayeon/<...>.json --use-ledger --log ../output/sayeon_log.json
  python run_story.py --topic gwedam <spec.json> --no-upload
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import config
import ledger as ledgermod

TAGS = {
    "sayeon": ["사연", "사연라디오", "실화같은사연", "인생이야기", "라디오사연", "시니어", "오디오북"],
    "gwedam": ["괴담", "괴담라디오", "무서운이야기", "미스터리", "괴담사연", "심야라디오", "공포라디오"],
}


def _led_key(spec: dict) -> dict:
    return {"date": spec.get("date", ""), "topic": spec.get("story_id", spec.get("topic", "story"))}


def build_meta(spec: dict, topic: str, force_private: bool) -> dict:
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    privacy = "private" if force_private else (spec.get("privacy") or "public")
    tags = list(TAGS.get(topic, ["오디오북"]))
    if spec.get("theme"):
        tags.append(spec["theme"])
    # 재생목록: 레포 변수 STORY_PLAYLIST(워크플로에서 토픽별 지정) 우선 → 없으면 스펙의 이름
    playlist = config.env("STORY_PLAYLIST") or yt.get("playlist", "")
    return {
        "title": yt.get("title", spec.get("title", "")),
        "description": yt.get("description", spec.get("logline", "")),
        "privacy": privacy,
        "playlist": playlist,
        "tags": tags,
        "category_id": config.env("STORY_YT_CATEGORY", "24"),  # 24=Entertainment
        "pinned_comment": yt.get("pinned_comment", ""),
    }


def has_credentials() -> bool:
    novel_tok = config.env("YT_TOKEN_NOVEL") or str(config.ROOT / "pipeline/secrets/token_novel.json")
    shorts_tok = config.env("YT_TOKEN") or str(config.ROOT / "pipeline/secrets/token.json")
    return (bool(config.env("YT_TOKEN_JSON_NOVEL")) or bool(config.env("YT_TOKEN_JSON"))
            or os.path.exists(novel_tok) or os.path.exists(shorts_tok))


def process(spec_path: str, topic: str, args, led) -> dict:
    res = {"spec": os.path.basename(spec_path), "video": None, "uploaded": None,
           "playlist": None, "skipped": False, "error": None}
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    if led is not None and ledgermod.is_done(led, _led_key(spec)):
        res["skipped"] = True
        print(f"   ⏭️  ledger 처리됨({_led_key(spec)}) — 건너뜀")
        return res

    story_id = spec.get("story_id", f"{topic}-{spec.get('date','out')}")
    out_mp4 = str(config.RENDERS_DIR / f"{story_id}.mp4")
    wd = str(config.OUTPUT / "_work" / topic / story_id)
    config.ensure_dirs()
    os.makedirs(wd, exist_ok=True)

    import story_render
    try:
        info = story_render.render(spec, out_mp4, wd)
        res["video"] = info["out"]
        res["duration_sec"] = info["duration_sec"]
        res["size_mb"] = info["size_mb"]
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    if args.no_upload:
        return res
    meta = build_meta(spec, topic, args.force_private)
    print(f"   업로드 메타: title={meta['title']!r} privacy={meta['privacy']} playlist={meta['playlist']!r}")
    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}, playlist={meta['playlist']!r}"
        return res
    if not has_credentials():
        res["uploaded"] = "[skip] YT 자격증명 없음(YT_TOKEN_JSON_NOVEL/token_novel.json)"
        print("   ⏭️  업로드 스킵 — 토큰 없음.")
        return res

    # 썸네일(FLUX) — best-effort
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    thumb = None
    try:
        thumb_path = str(config.RENDERS_DIR / f"{story_id}_thumb.jpg")
        thumb = story_render.build_thumbnail(yt.get("thumbnail_hook", ""),
                                             yt.get("thumbnail_text", spec.get("title", "")),
                                             thumb_path, wd)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 단계 예외 → 스킵: {e}\n")
    res["thumbnail"] = thumb

    import upload_youtube_novel
    last = None
    for attempt in range(1, args.retries + 2):
        try:
            pub = upload_youtube_novel.publish(
                res["video"], meta["title"], meta["description"], meta["privacy"],
                playlist_title=meta["playlist"], tags=meta["tags"],
                category_id=meta["category_id"], thumbnail=thumb)
            res["uploaded"] = f"{pub['url']} ({meta['privacy']})"
            res["playlist"] = pub.get("playlist_id")
            if led is not None:
                ledgermod.mark(led, _led_key(spec), pub["video_id"], meta["privacy"],
                               time.time(), args.ledger_path)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write(f"[upload 재시도 {attempt}/{args.retries + 1}] {e}\n")
    else:
        res["error"] = f"upload: {last}"

    # 고정댓글: YouTube API 는 '고정'을 지원하지 않음 → 문구를 로그로 안내(수동 고정)
    if meta["pinned_comment"] and res.get("uploaded"):
        res["pinned_comment"] = meta["pinned_comment"]
        print(f"   📌 고정댓글(수동으로 달아 고정): {meta['pinned_comment']}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="낭독형 스토리 파이프라인(사연/괴담)")
    ap.add_argument("--topic", required=True, choices=["sayeon", "gwedam"])
    ap.add_argument("specs", nargs="*", help="스펙 JSON 경로(들)")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--dry-run-upload", action="store_true")
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default="")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    if not args.ledger_path:
        args.ledger_path = str(config.OUTPUT / f"{args.topic}_ledger.json")
    config.load_dotenv()

    specs = [s for s in dict.fromkeys(args.specs) if s.endswith(".json")]
    if not specs:
        print("[stop] 처리할 스펙 JSON 없음.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# {args.topic} 처리 {len(specs)}개: {', '.join(os.path.basename(s) for s in specs)}")
    results = []
    for s in specs:
        print(f"\n──── {os.path.basename(s)} ────")
        results.append(process(s, args.topic, args, led))

    print("\n──────── 요약 ────────")
    rc = 0
    for r in results:
        line = f"  {r['spec']}: "
        line += "SKIP(ledger)" if r["skipped"] else f"video={'OK' if r['video'] else 'FAIL'}"
        if r.get("duration_sec"):
            line += f"({r['duration_sec']:.0f}s,{r.get('size_mb','?')}MB)"
        if r["uploaded"]:
            line += f", yt={r['uploaded']}"
        if r.get("playlist"):
            line += f", playlist={r['playlist']}"
        if r["error"]:
            line += f"  ⚠️ {r['error']}"; rc = 1
        print(line)
    if args.log:
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n로그: {args.log}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
