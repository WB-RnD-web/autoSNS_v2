#!/usr/bin/env python3
"""v2 오케스트레이터: 스토리보드 1개 이상 → 완성 쇼츠 → 업로드.

v1 run_daily 의 v2판. 차이:
  - 영상화 = make_short(HyperFrames 베드 기반)
  - 입력 = 인자로 받은 스토리보드 경로들 (Actions가 git diff로 신규 파일을 넘김)
    또는 --today 로 오늘(KST) output/news/*_storyboard.json 자동 탐색(로컬 테스트).

업로드 안전장치(v1 동일):
  - privacy: JSON 존중(politics=unlisted). --force-private 로 테스트 강제 private.
  - 자격증명(YT_TOKEN_JSON/token.json) 없으면 업로드 건너뜀(영상은 생성).

사용:
  python run_pipeline.py path/to/sb.json [more.json ...] --force-private
  python run_pipeline.py --today
  python run_pipeline.py sb.json --no-upload          # 영상만
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import json
import os
import sys

import config
import make_short
import upload_youtube
from upload_from_storyboard import build_meta

HERE = os.path.dirname(os.path.abspath(__file__))


def today_storyboards() -> list:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return sorted(glob.glob(str(config.NEWS_DIR / f"{today}_*_storyboard.json")))


def has_credentials() -> bool:
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    return bool(config.env("YT_TOKEN_JSON")) or os.path.exists(token)


def process(sb_path: str, args) -> dict:
    res = {"storyboard": os.path.basename(sb_path), "video": None, "uploaded": None, "error": None}
    try:
        video = make_short.make_short(sb_path, max_shots=args.shots,
                                      skip_bed=args.skip_bed, quality=args.quality)
        res["video"] = video
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    if args.no_upload:
        return res

    with open(sb_path, encoding="utf-8") as f:
        sb = json.load(f)
    meta = build_meta(sb, args.force_private)
    print(f"   업로드 메타: title='{meta['title']}' privacy={meta['privacy']}")

    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}"
        return res
    if not has_credentials():
        res["uploaded"] = "[skip] 자격증명 없음"
        print("   ⏭️  업로드 건너뜀(자격증명 없음). --no-upload 또는 자격증명 연결 필요.")
        return res
    try:
        vid = upload_youtube.upload(video, meta["title"], meta["description"],
                                    meta["privacy"], tags=meta["tags"])
        res["uploaded"] = f"https://youtu.be/{vid} ({meta['privacy']})"
    except Exception as e:  # noqa: BLE001
        res["error"] = f"upload: {e}"
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 파이프라인: 스토리보드 → 쇼츠 → 업로드")
    ap.add_argument("storyboards", nargs="*", help="스토리보드 JSON 경로(들)")
    ap.add_argument("--today", action="store_true", help="오늘(KST) output/news 자동 탐색")
    ap.add_argument("--no-upload", action="store_true", help="영상만 생성")
    ap.add_argument("--force-private", action="store_true", help="privacy 강제 private(테스트)")
    ap.add_argument("--dry-run-upload", action="store_true", help="업로드 매핑만(실업로드 X)")
    ap.add_argument("--shots", type=int, default=0)
    ap.add_argument("--skip-bed", action="store_true")
    ap.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    args = ap.parse_args()
    config.load_dotenv()

    boards = list(args.storyboards)
    if args.today:
        boards += today_storyboards()
    boards = [b for b in dict.fromkeys(boards) if b.endswith("_storyboard.json")]
    if not boards:
        print("[stop] 처리할 스토리보드가 없습니다. 경로를 넘기거나 --today 사용.", file=sys.stderr)
        return 1

    print(f"# 처리 대상 {len(boards)}개: {', '.join(os.path.basename(b) for b in boards)}")
    results = []
    for b in boards:
        print(f"\n──── {os.path.basename(b)} ────")
        results.append(process(b, args))

    print("\n──────── 요약 ────────")
    rc = 0
    for r in results:
        line = f"  {r['storyboard']}: "
        line += f"video={'OK' if r['video'] else 'FAIL'}"
        if r["uploaded"]:
            line += f", upload={r['uploaded']}"
        if r["error"]:
            line += f"  ⚠️ {r['error']}"; rc = 1
        print(line)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
