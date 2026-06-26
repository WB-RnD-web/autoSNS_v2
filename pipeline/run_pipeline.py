#!/usr/bin/env python3
"""v2 오케스트레이터(모션그래픽): 스토리보드 → 장면스펙 → 모션그래픽 쇼츠 → 업로드.

각 스토리보드마다:
  ① 장면 스펙 확보:
     - --spec 로 직접 지정(단일) 또는
     - 미리 만든 output/specs/<date>_<topic>_spec.json 있으면 사용 또는
     - ANTHROPIC_API_KEY 있으면 extract_scenes 로 생성(→ specs 저장)
  ② motion_short.build_motion → output/renders/<date>_<topic>_final.mp4
  ③ 업로드(privacy 준수, ledger dedupe, 로그) — v1 재사용

루프 가드: main에 커밋하지 않음(산출물·ledger·spec 전부 .gitignore).

사용:
  python run_pipeline.py <sb.json> [...] --force-private
  python run_pipeline.py <sb.json> --spec <spec.json> --no-upload
  python run_pipeline.py --today
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
import motion_short
import upload_youtube
from upload_from_storyboard import build_meta

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS_DIR = config.OUTPUT / "specs"


def today_storyboards():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return sorted(glob.glob(str(config.NEWS_DIR / f"{today}_*_storyboard.json")))


def has_credentials():
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    return bool(config.env("YT_TOKEN_JSON")) or os.path.exists(token)


def upload_with_retry(video, meta, retries=2):
    last = None
    for attempt in range(1, retries + 2):
        try:
            return upload_youtube.upload(video, meta["title"], meta["description"],
                                         meta["privacy"], tags=meta["tags"])
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write(f"[upload 재시도 {attempt}/{retries + 1}] {e}\n")
    raise last


def resolve_spec(sb_path, sb, args):
    """장면 스펙 확보: 직접 스펙 > --spec > 사전생성 파일 > LLM 추출."""
    # 루틴이 스펙을 직접 커밋한 경우(scenes 키 보유) → 그대로 사용(CI LLM 불필요)
    if isinstance(sb.get("scenes"), list) and sb["scenes"]:
        return sb
    if args.spec:
        with open(args.spec, encoding="utf-8") as f:
            return json.load(f)
    date, topic = sb.get("date", ""), sb.get("topic", "")
    pre = SPECS_DIR / f"{date}_{topic}_spec.json"
    if pre.exists():
        with open(pre, encoding="utf-8") as f:
            return json.load(f)
    if config.env("ANTHROPIC_API_KEY"):
        import extract_scenes
        spec = extract_scenes.extract_scenes(sb)
        SPECS_DIR.mkdir(parents=True, exist_ok=True)
        with open(pre, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        return spec
    raise RuntimeError("장면 스펙 없음 — --spec 지정, output/specs/ 사전생성, 또는 ANTHROPIC_API_KEY 필요")


def do_social(video, sb, res):
    """IG Reels + Threads 업로드(자격증명 있을 때만). 공개 URL 은 Cloudinary 경유."""
    ig = config.env("IG_USER_ID") and config.env("IG_ACCESS_TOKEN")
    th = config.env("THREADS_USER_ID") and config.env("THREADS_ACCESS_TOKEN")
    if not ig and not th:
        return  # 자격증명 없음 → 조용히 스킵
    import host_video
    public_id = os.path.splitext(os.path.basename(video))[0]
    url = host_video.host(video, public_id)
    if not url:
        res["social"] = "[skip] Cloudinary 자격증명 없음(공개 URL 불가)"
        print("   ⏭️  IG/Threads 스킵 — Cloudinary 자격증명 없음")
        return
    print(f"   공개 URL: {url}")
    plat = sb.get("platforms", {})
    out = []
    if ig:
        try:
            import upload_instagram
            mid = upload_instagram.publish_reel(url, plat.get("instagram", {}).get("caption", ""))
            out.append(f"IG:{mid}")
        except Exception as e:  # noqa: BLE001
            out.append(f"IG실패:{e}")
    if th:
        try:
            import upload_threads
            tid = upload_threads.publish_thread(url, plat.get("threads", {}).get("text", ""))
            out.append(f"Threads:{tid}")
        except Exception as e:  # noqa: BLE001
            out.append(f"Threads실패:{e}")
    res["social"] = " · ".join(out)


def process(sb_path, args, led):
    res = {"storyboard": os.path.basename(sb_path), "video": None,
           "uploaded": None, "social": None, "skipped": False, "error": None}
    with open(sb_path, encoding="utf-8") as f:
        sb = json.load(f)
    if led is not None and ledgermod.is_done(led, sb):
        res["skipped"] = True
        print(f"   ⏭️  ledger 처리됨({ledgermod.key_for(sb)}) — 건너뜀")
        return res
    try:
        spec = resolve_spec(sb_path, sb, args)
        spec.setdefault("topic", sb.get("topic", ""))
        suffix = f"_{sb.get('topic','')}" if sb.get("topic") else ""
        out_mp4 = str(config.RENDERS_DIR / f"{sb.get('date','out')}{suffix}_final.mp4")
        wd = str(config.OUTPUT / "_work" / f"{sb.get('date','')}{suffix}")
        config.ensure_dirs()
        res["video"] = motion_short.build_motion(spec, out_mp4, wd, quality=args.quality)
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

    # ── YouTube (자격증명 있을 때) ──
    if has_credentials():
        try:
            vid = upload_with_retry(res["video"], meta)
            res["uploaded"] = f"https://youtu.be/{vid} ({meta['privacy']})"
            if led is not None:
                ledgermod.mark(led, sb, vid, meta["privacy"], time.time(), args.ledger_path)
        except Exception as e:  # noqa: BLE001
            res["error"] = f"upload: {e}"
    else:
        res["uploaded"] = "[skip] YT 자격증명 없음"
        print("   ⏭️  YouTube 스킵(자격증명 없음).")

    # ── Instagram Reels + Threads (자격증명 있을 때, 독립) ──
    if not args.no_social:
        try:
            do_social(res["video"], sb, res)
        except Exception as e:  # noqa: BLE001
            res["social"] = f"social실패:{e}"
    return res


def main():
    ap = argparse.ArgumentParser(description="v2 모션그래픽 파이프라인")
    ap.add_argument("storyboards", nargs="*")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--spec", help="장면 스펙 직접 지정(단일 스토리보드)")
    ap.add_argument("--no-upload", action="store_true", help="유튜브 업로드 안 함")
    ap.add_argument("--no-social", action="store_true", help="IG/Threads 업로드 안 함")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--dry-run-upload", action="store_true")
    ap.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=ledgermod.DEFAULT_PATH)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    config.load_dotenv()

    boards = list(args.storyboards)
    if args.today:
        boards += today_storyboards()
    boards = [b for b in dict.fromkeys(boards) if b.endswith("_storyboard.json")]
    if not boards:
        print("[stop] 처리할 스토리보드 없음. 경로 지정 또는 --today.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# 처리 {len(boards)}개: {', '.join(os.path.basename(b) for b in boards)}")
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
            line += f", yt={r['uploaded']}"
        if r.get("social"):
            line += f", social={r['social']}"
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
