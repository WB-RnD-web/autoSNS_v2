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
import time

import config
import ledger as ledgermod
import make_short
import upload_youtube
from upload_from_storyboard import build_meta

HERE = os.path.dirname(os.path.abspath(__file__))


def upload_with_retry(video, meta, retries: int = 2):
    """업로드 전환적 실패 재시도. 성공 시 video_id 반환."""
    last = None
    for attempt in range(1, retries + 2):
        try:
            return upload_youtube.upload(video, meta["title"], meta["description"],
                                         meta["privacy"], tags=meta["tags"])
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write(f"[upload 재시도 {attempt}/{retries + 1}] {e}\n")
    raise last


def today_storyboards() -> list:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return sorted(glob.glob(str(config.NEWS_DIR / f"{today}_*_storyboard.json")))


def has_credentials() -> bool:
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    return bool(config.env("YT_TOKEN_JSON")) or os.path.exists(token)


def process(sb_path: str, args, led: dict | None) -> dict:
    res = {"storyboard": os.path.basename(sb_path), "video": None,
           "uploaded": None, "skipped": False, "error": None}
    with open(sb_path, encoding="utf-8") as f:
        sb = json.load(f)

    # dedupe: 이미 업로드한 스토리보드면 건너뜀
    if led is not None and ledgermod.is_done(led, sb):
        res["skipped"] = True
        print(f"   ⏭️  ledger에 이미 처리됨({ledgermod.key_for(sb)}) — 건너뜀")
        return res

    try:
        video = make_short.make_short(sb_path, max_shots=args.shots,
                                      skip_bed=args.skip_bed, quality=args.quality)
        res["video"] = video
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    if args.no_upload:
        return res

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
        vid = upload_with_retry(res["video"], meta)
        res["uploaded"] = f"https://youtu.be/{vid} ({meta['privacy']})"
        if led is not None:
            ledgermod.mark(led, sb, vid, meta["privacy"], time.time(), args.ledger_path)
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
    ap.add_argument("--use-ledger", action="store_true", help="dedupe ledger 사용(이미 업로드면 skip)")
    ap.add_argument("--ledger-path", default=ledgermod.DEFAULT_PATH)
    ap.add_argument("--log", default="", help="실행 결과 JSON 로그 경로(비우면 미기록)")
    args = ap.parse_args()
    config.load_dotenv()

    boards = list(args.storyboards)
    if args.today:
        boards += today_storyboards()
    boards = [b for b in dict.fromkeys(boards) if b.endswith("_storyboard.json")]
    if not boards:
        print("[stop] 처리할 스토리보드가 없습니다. 경로를 넘기거나 --today 사용.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None

    print(f"# 처리 대상 {len(boards)}개: {', '.join(os.path.basename(b) for b in boards)}")
    results = []
    for b in boards:
        print(f"\n──── {os.path.basename(b)} ────")
        results.append(process(b, args, led))

    print("\n──────── 요약 ────────")
    rc = 0
    for r in results:
        line = f"  {r['storyboard']}: "
        line += "SKIP(ledger)" if r["skipped"] else f"video={'OK' if r['video'] else 'FAIL'}"
        if r["uploaded"]:
            line += f", upload={r['uploaded']}"
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
