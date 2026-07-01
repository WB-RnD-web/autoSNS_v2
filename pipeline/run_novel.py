#!/usr/bin/env python3
"""소설(novel) 오케스트레이터: 에피소드 render-spec → 16:9 렌더 → YouTube(일반영상+재생목록).

쇼츠 run_pipeline.py 와 ★별개. 모션그래픽/IG/Threads 안 씀.

각 에피소드 JSON 마다:
  ① novel_spec.normalize 로 검증/정규화(privacy 는 ★루틴 값 존중, #shorts 제거)
  ② novel_render.render → output/renders/<series_id>_ep<N>.mp4 (16:9 정적배경+자막번인+낭독)
  ③ upload_youtube_novel.publish → 업로드 + series_title 재생목록 생성/추가
  ④ ledger 로 dedupe(키=<series_id>_ep<N>), 로그 기록

루프 가드: 레포에 ★아무것도 커밋하지 않는다(산출물·ledger 전부 .gitignore / cache).
상태 파일(library/canon)은 '루틴'이 쓴다 — 파이프라인은 읽지도 쓰지도 않는다.

사용:
  python run_novel.py ../output/novel/<sid>/ep1_<date>.json [...] --use-ledger --log ../output/novel_log.json
  python run_novel.py <ep.json> --no-upload                 # 렌더만(검증)
  python run_novel.py <ep.json> --force-private             # privacy 강제 private(테스트)
  python run_novel.py <ep.json> --dry-run-upload            # 업로드 매핑만(자격증명 불필요)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import config
import ledger as ledgermod
import novel_render
import novel_spec


def _led_sb(spec: dict) -> dict:
    """ledger 키를 <series_id>_ep<N> 로 만들기 위한 합성 dict(ledger.py 재사용)."""
    return {"date": spec["series_id"], "topic": f"ep{spec['episode_no']}"}


def build_meta(spec: dict, force_private: bool) -> dict:
    yt = spec["platforms"]["youtube"]
    privacy = "private" if force_private else spec["privacy"]
    genre = spec.get("genre", "")
    tags = ["오디오소설", "소설낭독", "잠들기전", "이야기"] + ([genre] if genre else [])
    return {
        "title": yt["title"],
        "description": yt["description"],
        "privacy": privacy,
        "playlist": yt.get("playlist", spec.get("series_title", "")),
        "tags": tags,
        "category_id": config.env("NOVEL_YT_CATEGORY", "24"),
    }


def has_credentials() -> bool:
    # 소설 전용 토큰 또는 쇼츠 토큰(폴백) 중 하나라도 있으면 업로드 시도
    novel_tok = config.env("YT_TOKEN_NOVEL") or str(config.ROOT / "pipeline/secrets/token_novel.json")
    shorts_tok = config.env("YT_TOKEN") or str(config.ROOT / "pipeline/secrets/token.json")
    return (bool(config.env("YT_TOKEN_JSON_NOVEL")) or bool(config.env("YT_TOKEN_JSON"))
            or os.path.exists(novel_tok) or os.path.exists(shorts_tok))


def process(ep_path: str, args, led) -> dict:
    res = {"episode": os.path.basename(ep_path), "video": None, "uploaded": None,
           "playlist": None, "skipped": False, "error": None}
    try:
        spec, warns = novel_spec.normalize(novel_spec.load(ep_path))
    except Exception as e:  # noqa: BLE001
        res["error"] = f"spec: {e}"
        return res
    for w in warns:
        print(f"  ⚠️ {w}")

    if led is not None and ledgermod.is_done(led, _led_sb(spec)):
        res["skipped"] = True
        print(f"   ⏭️  ledger 처리됨({spec['series_id']}_ep{spec['episode_no']}) — 건너뜀")
        return res

    # ② 렌더
    out_mp4 = str(config.RENDERS_DIR / f"{spec['series_id']}_ep{spec['episode_no']}.mp4")
    wd = str(config.OUTPUT / "_work" / "novel" / f"{spec['series_id']}_ep{spec['episode_no']}")
    cache = str(config.OUTPUT / "_work" / "novel_bg")
    try:
        config.ensure_dirs()
        info = novel_render.render(ep_path, out_mp4, wd, cache)
        res["video"] = info["out"]
        res["duration_sec"] = info["duration_sec"]
        res["thumb"] = info.get("thumbnail")
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    meta = build_meta(spec, args.force_private)
    print(f"   업로드 메타: title={meta['title']!r} privacy={meta['privacy']} playlist={meta['playlist']!r}")
    if args.no_upload:
        return res
    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}, playlist={meta['playlist']!r}"
        return res

    if not has_credentials():
        res["uploaded"] = "[skip] 소설 YT 자격증명 없음(YT_TOKEN_JSON_NOVEL/token_novel.json)"
        print("   ⏭️  업로드 스킵 — 소설 토큰 없음.")
        return res

    import upload_youtube_novel
    last = None
    for attempt in range(1, args.retries + 2):
        try:
            pub = upload_youtube_novel.publish(
                res["video"], meta["title"], meta["description"], meta["privacy"],
                playlist_title=meta["playlist"], tags=meta["tags"],
                category_id=meta["category_id"], thumbnail=res.get("thumb"))
            res["uploaded"] = f"{pub['url']} ({meta['privacy']})"
            res["playlist"] = pub.get("playlist_id")
            res["thumbnail"] = pub.get("thumbnail") or pub.get("thumbnail_error")
            if led is not None:
                ledgermod.mark(led, _led_sb(spec), pub["video_id"], meta["privacy"],
                               time.time(), args.ledger_path)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write(f"[upload 재시도 {attempt}/{args.retries + 1}] {e}\n")
    else:
        res["error"] = f"upload: {last}"
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="소설 파이프라인 오케스트레이터")
    ap.add_argument("episodes", nargs="*", help="에피소드 render-spec JSON 경로(들)")
    ap.add_argument("--no-upload", action="store_true", help="렌더만(업로드 안 함)")
    ap.add_argument("--force-private", action="store_true", help="privacy 강제 private(테스트)")
    ap.add_argument("--dry-run-upload", action="store_true", help="업로드 매핑만(자격증명 불필요)")
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=str(config.OUTPUT / "novel_ledger.json"))
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    config.load_dotenv()

    eps = [e for e in dict.fromkeys(args.episodes) if e.endswith(".json")]
    if not eps:
        print("[stop] 처리할 에피소드 JSON 없음.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# 소설 처리 {len(eps)}개: {', '.join(os.path.basename(e) for e in eps)}")
    results = []
    for e in eps:
        print(f"\n──── {os.path.basename(e)} ────")
        results.append(process(e, args, led))

    print("\n──────── 요약 ────────")
    rc = 0
    for r in results:
        line = f"  {r['episode']}: "
        line += "SKIP(ledger)" if r["skipped"] else f"video={'OK' if r['video'] else 'FAIL'}"
        if r.get("duration_sec"):
            line += f"({r['duration_sec']}s)"
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
