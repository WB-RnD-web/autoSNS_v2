#!/usr/bin/env python3
"""ASMR 오케스트레이터: 테마 스펙 JSON → 배경(FLUX) + Freesound 앰비언트(1h) → 유튜브(+재생목록).

소설(run_novel)과 사상 동일. 업로드·재생목록·썸네일 지정은 upload_youtube_novel 재사용
(같은 채널 → YT_TOKEN_JSON_NOVEL 확장 스코프 토큰 그대로 사용).

각 스펙 JSON 마다:
  ① Freesound 로 테마 클립 수집(CC0) → asmr_render.render(정적 이미지 + 심리스 1h 오디오 + 낮은 나레이션)
  ② FLUX 썸네일 생성 → upload_youtube_novel.publish(업로드 + 커스텀 썸네일 + 재생목록 추가)
  ③ ledger dedupe(키=<date>_<theme_id>), 로그 기록

사용:
  python run_asmr.py ../output/asmr/<date>_asmr.json [...] --use-ledger --log ../output/asmr_log.json
  python run_asmr.py <spec.json> --no-upload            # 렌더만(검증)
  python run_asmr.py <spec.json> --dry-run-upload       # 업로드 매핑만(자격증명 불필요)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import config
import ledger as ledgermod


def _led_key(spec: dict) -> dict:
    return {"date": spec.get("date", ""), "topic": spec.get("theme_id", "asmr")}


def build_meta(spec: dict, attrs_block: str, force_private: bool) -> dict:
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    desc = yt.get("description", "")
    if attrs_block:
        desc = f"{desc}\n\n{attrs_block}"
    privacy = "private" if force_private else (spec.get("privacy") or "public")
    theme = spec.get("theme_name", "")
    tags = ["ASMR", "백색소음", "수면", "잠들기전", "asmr", "white noise", "sleep"]
    if theme:
        tags.append(theme)
    # 재생목록: 레포 변수 ASMR_PLAYLIST 가 있으면 그걸 우선(오타/불일치로 새 재생목록 생성 방지)
    playlist = config.env("ASMR_PLAYLIST") or yt.get("playlist", "")
    return {
        "title": yt.get("title", theme or "ASMR"),
        "description": desc,
        "privacy": privacy,
        "playlist": playlist,
        "tags": tags,
        "category_id": config.env("ASMR_YT_CATEGORY", "24"),  # 24=Entertainment
    }


def has_credentials() -> bool:
    novel_tok = config.env("YT_TOKEN_NOVEL") or str(config.ROOT / "pipeline/secrets/token_novel.json")
    shorts_tok = config.env("YT_TOKEN") or str(config.ROOT / "pipeline/secrets/token.json")
    return (bool(config.env("YT_TOKEN_JSON_NOVEL")) or bool(config.env("YT_TOKEN_JSON"))
            or os.path.exists(novel_tok) or os.path.exists(shorts_tok))


def process(spec_path: str, args, led) -> dict:
    res = {"spec": os.path.basename(spec_path), "video": None, "uploaded": None,
           "playlist": None, "skipped": False, "error": None}
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    if led is not None and ledgermod.is_done(led, _led_key(spec)):
        res["skipped"] = True
        print(f"   ⏭️  ledger 처리됨({_led_key(spec)}) — 건너뜀")
        return res

    theme_id = spec.get("theme_id", "asmr")
    date = spec.get("date", "out")
    out_mp4 = str(config.RENDERS_DIR / f"asmr_{date}_{theme_id}.mp4")
    wd = str(config.OUTPUT / "_work" / "asmr" / f"{date}_{theme_id}")
    config.ensure_dirs()
    os.makedirs(wd, exist_ok=True)

    # ① Freesound 소스 수집
    import freesound
    target_sec = float(spec.get("duration_min", 60)) * 60.0
    want = min(int(config.env("ASMR_SOURCE_SEC", "1200")), int(target_sec))
    queries = ((spec.get("freesound") or {}).get("queries")) or [spec.get("theme_name", "ambience")]
    try:
        clips, attrs = freesound.fetch_theme(queries, os.path.join(wd, "src"), want_sec=want)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"freesound: {e}"
        return res
    if not clips:
        res["error"] = "freesound: 소스 음원 0개(키/쿼리/네트워크 확인)"
        return res
    attrs_block = freesound.attribution_block(attrs)

    # ② 렌더
    import asmr_render
    try:
        info = asmr_render.render(spec, clips, out_mp4, wd)
        res["video"] = info["out"]
        res["duration_sec"] = info["duration_sec"]
        res["size_mb"] = info["size_mb"]
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    if args.no_upload:
        return res
    meta = build_meta(spec, attrs_block, args.force_private)
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
        thumb_path = str(config.RENDERS_DIR / f"asmr_{date}_{theme_id}_thumb.jpg")
        thumb = asmr_render.build_thumbnail(yt.get("thumbnail_hook", ""),
                                            yt.get("thumbnail_text", spec.get("theme_name", "")),
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
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="ASMR 파이프라인 오케스트레이터")
    ap.add_argument("specs", nargs="*", help="테마 스펙 JSON 경로(들)")
    ap.add_argument("--no-upload", action="store_true", help="렌더만(업로드 안 함)")
    ap.add_argument("--force-private", action="store_true", help="privacy 강제 private(테스트)")
    ap.add_argument("--dry-run-upload", action="store_true", help="업로드 매핑만(자격증명 불필요)")
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=str(config.OUTPUT / "asmr_ledger.json"))
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    config.load_dotenv()

    specs = [s for s in dict.fromkeys(args.specs) if s.endswith(".json")]
    if not specs:
        print("[stop] 처리할 ASMR 스펙 JSON 없음.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# ASMR 처리 {len(specs)}개: {', '.join(os.path.basename(s) for s in specs)}")
    results = []
    for s in specs:
        print(f"\n──── {os.path.basename(s)} ────")
        results.append(process(s, args, led))

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
            line += f"  ⚠️ {r['error']}"
            rc = 1
        print(line)
    if args.log:
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n로그: {args.log}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
