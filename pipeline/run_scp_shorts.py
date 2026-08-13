#!/usr/bin/env python3
"""SCP 쇼츠 오케스트레이터 — 금요일 롱폼 스펙 → 토요일 9:16 쇼츠 업로드.

롱폼(run_scp)과의 차이:
  ① 렌더러가 scp_shorts_render(9:16, 개체 정면, 상단 큰 글자 번인, 새 TTS).
  ② ★같은 스펙 JSON 을 쓴다 — 루틴은 금요일 1회만 돌면 된다.
  ③ dedupe 키에 '-shorts' 를 붙여 롱폼 ledger 와 충돌하지 않게 한다.
  ④ ★설명란에 '전편' 링크를 붙인다 — 채널 업로드 목록에서 롱폼 제목이 일치하는 영상을
     찾아 URL 을 가져온다(쿼터 2 units, 실패하면 재생목록 안내 문구로 폴백).

업로드는 upload_youtube_novel 재사용(같은 채널 · 재생목록 스코프).
쇼츠 판정은 세로 비율 + #shorts 태그로 유튜브가 자동으로 한다.

사용:
  python run_scp_shorts.py --latest-in ../output/scp --use-ledger
  python run_scp_shorts.py ../output/scp/<spec>.json --no-upload
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
import time

import config
import ledger as ledgermod

TAGS = ["SCP", "SCP재단", "괴담", "무서운이야기", "미스터리", "쇼츠", "shorts"]

CC_NOTE = ("※ SCP 재단 세계관 기반 오리지널 창작 · 허구의 이야기입니다\n"
           "※ 본 콘텐츠는 CC BY-SA 3.0 라이선스를 따릅니다 · 원작: SCP Foundation "
           "(scp-wiki.wikidot.com)")
HASHTAGS = "#SCP #SCP재단 #괴담 #무서운이야기 #미스터리 #shorts"


def _led_key(spec: dict) -> dict:
    """롱폼과 같은 스펙을 쓰므로 topic 에 '-shorts' 를 붙여 키를 분리한다."""
    return {"date": spec.get("iso_week") or spec.get("date", ""),
            "topic": f"{spec.get('story_id', 'scp')}-shorts"}


def pick_latest(d: str) -> str | None:
    """디렉터리에서 가장 최근 스펙 1개(date 필드 기준). library.json 은 제외."""
    cands: list[tuple[str, str]] = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        if os.path.basename(p) == "library.json":
            continue
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        cands.append((str(s.get("date") or ""), p))
    if not cands:
        return None
    cands.sort()
    print(f"# 최신 스펙 선택: {os.path.basename(cands[-1][1])} (후보 {len(cands)}개)")
    return cands[-1][1]


def find_longform_url(spec: dict) -> str:
    """채널 업로드 목록에서 롱폼(같은 제목)을 찾아 URL 반환. best-effort — 실패는 빈 문자열.

    ledger 를 공유할 수 없어서(스케줄 런은 main 브랜치 → routine/scp 의 캐시를 못 읽는다)
    유튜브에 직접 물어본다. channels.list(1) + playlistItems.list(1) = 2 units 로 충분히 싸다.
    """
    want = ((spec.get("platforms") or {}).get("youtube") or {}).get("title", "").strip()
    if not want:
        return ""
    try:
        import upload_youtube_novel as UN
        yt = UN.get_service()
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="snippet", playlistId=up, maxResults=30).execute()
        for it in items.get("items", []):
            sn = it.get("snippet") or {}
            if (sn.get("title") or "").strip() == want:
                vid = (sn.get("resourceId") or {}).get("videoId")
                if vid:
                    print(f"   🔗 전편 발견: https://youtu.be/{vid}")
                    return f"https://youtu.be/{vid}"
        print(f"   · 전편 못 찾음(최근 30개에 {want!r} 없음) — 재생목록 안내로 폴백")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 전편 조회 실패(무시): {e}\n")
    return ""


def build_meta(spec: dict, sh: dict, longform_url: str, force_private: bool) -> dict:
    title = (sh.get("title") or spec.get("title") or "SCP").strip()
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    desc = (sh.get("description") or "").strip()
    link = (f"▶ 전편(풀버전): {longform_url}" if longform_url
            else "▶ 전편(풀버전)은 채널의 'SCP 아카이브' 재생목록에 있습니다.")
    desc = "\n\n".join(x for x in (desc, link, CC_NOTE, HASHTAGS) if x)

    tags = list(TAGS)
    for k in ("object_class", "scp_number", "theme"):
        if spec.get(k):
            tags.append(str(spec[k]))
    return {
        "title": title[:100],
        "description": desc,
        "privacy": "private" if force_private else (spec.get("privacy") or "public"),
        "playlist": config.env("SCP_SHORTS_PLAYLIST") or sh.get("playlist") or "",
        "tags": tags[:15],
        "category_id": config.env("SCP_YT_CATEGORY", "24"),   # 24=Entertainment
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
    out_mp4 = str(config.RENDERS_DIR / f"{story_id}_shorts.mp4")
    wd = str(config.OUTPUT / "_work" / "scp_shorts" / story_id)
    config.ensure_dirs()
    os.makedirs(wd, exist_ok=True)

    import scp_shorts_render
    try:
        info = scp_shorts_render.render(spec, out_mp4, wd)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res
    res.update({"video": info["out"], "duration_sec": info["duration_sec"],
                "size_mb": info["size_mb"], "scenes": info["scenes"],
                "captions": info["captions"], "fallback_spec": info["shorts"]["fallback"]})

    if args.no_upload:
        return res
    meta = build_meta(spec, info["shorts"], "" if args.dry_run_upload else find_longform_url(spec),
                      args.force_private)
    print(f"   업로드 메타: title={meta['title']!r} privacy={meta['privacy']} "
          f"playlist={meta['playlist']!r}")
    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}, playlist={meta['playlist']!r}"
        return res
    if not has_credentials():
        res["uploaded"] = "[skip] YT 자격증명 없음"
        print("   ⏭️  업로드 스킵 — 토큰 없음.")
        return res

    import upload_youtube_novel
    last = None
    for attempt in range(1, args.retries + 2):
        try:
            pub = upload_youtube_novel.publish(
                res["video"], meta["title"], meta["description"], meta["privacy"],
                playlist_title=meta["playlist"], tags=meta["tags"],
                category_id=meta["category_id"], thumbnail=info.get("thumbnail"),
                srt=info.get("srt"))
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
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="SCP 쇼츠 파이프라인(토요일)")
    ap.add_argument("specs", nargs="*")
    ap.add_argument("--latest-in", default="", help="이 디렉터리에서 가장 최근 스펙 1개 자동 선택")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--dry-run-upload", action="store_true")
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=str(config.OUTPUT / "scp_shorts_ledger.json"))
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--log", default="")
    args = ap.parse_args()
    config.load_dotenv()

    specs = [s for s in dict.fromkeys(args.specs) if s.endswith(".json")]
    if not specs and args.latest_in:
        p = pick_latest(args.latest_in)
        if p:
            specs = [p]
    if not specs:
        print("[stop] 처리할 SCP 스펙 JSON 없음.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# SCP 쇼츠 처리 {len(specs)}개: {', '.join(os.path.basename(s) for s in specs)}")
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
            line += (f"({r['duration_sec']:.0f}s,{r.get('size_mb','?')}MB,"
                     f"장면{r.get('scenes','?')},자막{r.get('captions','?')})")
        if r.get("fallback_spec"):
            line += "  ⚠️ shorts 블록 없어 폴백 합성(루틴 v3 적용 권장)"
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
        for r in results:
            r.pop("fallback_spec", None)
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n로그: {args.log}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
