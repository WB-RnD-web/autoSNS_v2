#!/usr/bin/env python3
"""SCP 아카이브 오케스트레이터 — 주 1회 다장면 롱폼 → 유튜브(+재생목록).

사연/괴담(run_story)과의 차이:
  ① 렌더러가 scp_render(다장면 배경 크로스페이드).
  ② dedupe 키가 날짜가 아니라 ★iso_week(주 1회 발행이라 같은 주 재실행은 스킵).
  ③ 챕터를 ★실제 TTS 시각으로 재계산해 description 맨 앞에 삽입(유튜브 챕터 마커 생성).
  ④ 스펙의 thumbnail 이 top-level dict(hook/hook_alt/…)이고 문구는 platforms.youtube.thumbnail_text.

업로드/재생목록/썸네일 지정은 upload_youtube_novel 재사용(같은 채널 → YT_TOKEN_JSON_NOVEL).

사용:
  python run_scp.py ../output/scp/<story_id>_<DATE>.json --use-ledger --log ../output/scp_log.json
  python run_scp.py <spec.json> --no-upload        # 렌더만
  python run_scp.py <spec.json> --dry-run-upload   # 업로드 매핑만
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import config
import ledger as ledgermod

TAGS = ["SCP", "SCP재단", "괴담", "무서운이야기", "미스터리", "심야라디오", "공포라디오", "오디오북"]


def _led_key(spec: dict) -> dict:
    """주 1회 발행 → 주차 단위 dedupe. iso_week 없으면 story_id 로 폴백."""
    return {"date": spec.get("iso_week") or spec.get("date", ""),
            "topic": spec.get("story_id", "scp")}


def build_meta(spec: dict, chapters: list[str], force_private: bool) -> dict:
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    desc = yt.get("description", "") or spec.get("logline", "")
    # 유튜브 챕터: description 맨 앞 블록 + 첫 줄이 00:00 이어야 마커가 생성된다.
    if chapters and str(chapters[0]).strip().startswith("00:00"):
        desc = "\n".join(chapters) + "\n\n" + desc
    privacy = "private" if force_private else (spec.get("privacy") or "public")
    tags = list(TAGS)
    for k in ("theme", "object_class", "scp_number"):
        if spec.get(k):
            tags.append(str(spec[k]))
    playlist = config.env("SCP_PLAYLIST") or yt.get("playlist", "")
    return {
        "title": yt.get("title", spec.get("title", "SCP")),
        "description": desc,
        "privacy": privacy,
        "playlist": playlist,
        "tags": tags[:15],
        "category_id": config.env("SCP_YT_CATEGORY", "24"),  # 24=Entertainment
        "pinned_comment": yt.get("pinned_comment", ""),
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

    story_id = spec.get("story_id", f"scp-{spec.get('date','out')}")
    out_mp4 = str(config.RENDERS_DIR / f"{story_id}.mp4")
    wd = str(config.OUTPUT / "_work" / "scp" / story_id)
    config.ensure_dirs()
    os.makedirs(wd, exist_ok=True)

    import scp_render
    try:
        info = scp_render.render(spec, out_mp4, wd)
        res.update({"video": info["out"], "duration_sec": info["duration_sec"],
                    "size_mb": info["size_mb"], "scenes": info["scenes"]})
        chapters = info.get("chapters") or []
        srt = info.get("srt")     # 한국어 원본(API 폴백용)
        srts = info.get("srts") or {}   # ★루틴이 번역한 자막(번역 API 비용 0)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    if args.no_upload:
        return res
    meta = build_meta(spec, chapters, args.force_private)
    print(f"   업로드 메타: title={meta['title']!r} privacy={meta['privacy']} playlist={meta['playlist']!r}")
    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}, playlist={meta['playlist']!r}"
        return res
    if not has_credentials():
        res["uploaded"] = "[skip] YT 자격증명 없음(YT_TOKEN_JSON_NOVEL/token_novel.json)"
        print("   ⏭️  업로드 스킵 — 토큰 없음.")
        return res

    thumb = None
    try:
        thumb = scp_render.build_thumbnail(spec, str(config.RENDERS_DIR / f"{story_id}_thumb.jpg"), wd)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 단계 예외 → 스킵: {e}\n")
    res["thumbnail"] = thumb

    import upload_youtube_novel
    import yt_i18n
    last = None
    for attempt in range(1, args.retries + 2):
        try:
            pub = upload_youtube_novel.publish(
                res["video"], meta["title"], meta["description"], meta["privacy"],
                playlist_title=meta["playlist"], tags=meta["tags"],
                category_id=meta["category_id"], thumbnail=thumb, srt=srt,
                localizations=yt_i18n.from_spec(spec), srts=srts)
            res["uploaded"] = f"{pub['url']} ({meta['privacy']})"
            res["playlist"] = pub.get("playlist_id")
            res["i18n"] = {"localized": pub.get("localized", []), "captions": pub.get("captions", [])}
            if led is not None:
                ledgermod.mark(led, _led_key(spec), pub["video_id"], meta["privacy"],
                               time.time(), args.ledger_path)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write(f"[upload 재시도 {attempt}/{args.retries + 1}] {e}\n")
    else:
        res["error"] = f"upload: {last}"

    if meta["pinned_comment"] and res.get("uploaded"):
        res["pinned_comment"] = meta["pinned_comment"]
        print(f"   📌 고정댓글(수동으로 달아 고정): {meta['pinned_comment']}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="SCP 아카이브 파이프라인(주 1회)")
    ap.add_argument("specs", nargs="*")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--dry-run-upload", action="store_true")
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=str(config.OUTPUT / "scp_ledger.json"))
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    config.load_dotenv()

    specs = [s for s in dict.fromkeys(args.specs) if s.endswith(".json")]
    if not specs:
        print("[stop] 처리할 SCP 스펙 JSON 없음.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# SCP 처리 {len(specs)}개: {', '.join(os.path.basename(s) for s in specs)}")
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
            line += f"({r['duration_sec']:.0f}s,{r.get('size_mb','?')}MB,장면{r.get('scenes','?')})"
        if r["uploaded"]:
            line += f", yt={r['uploaded']}"
        if r.get("playlist"):
            line += f", playlist={r['playlist']}"
        if r.get("i18n"):
            line += (f", 현지화={','.join(r['i18n']['localized']) or '없음'}"
                     f", 자막={','.join(r['i18n']['captions']) or '없음'}")
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
