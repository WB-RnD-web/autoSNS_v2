#!/usr/bin/env python3
"""ASMR 오케스트레이터: 테마 스펙 JSON → 배경(FLUX) + Freesound 앰비언트(1h) → 유튜브(+재생목록).

소설(run_novel)과 사상 동일. 업로드·재생목록·썸네일 지정은 upload_youtube_novel 재사용
(같은 채널 → YT_TOKEN_JSON_NOVEL 확장 스코프 토큰 그대로 사용).

각 스펙 JSON 마다:
  ① Freesound 로 테마 클립 수집(CC0) → asmr_render.render(정적 이미지 + ★3~4시간 루프 오디오)
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
    tags = ["ASMR", "백색소음", "수면", "잠들기전", "asmr", "white noise", "sleep",
            "sleep sounds", "study sounds"]
    if theme:
        tags.append(theme)
    if spec.get("theme_id"):
        tags.append(english_name(spec["theme_id"]).lower())
    series = bool(spec.get("series"))
    if series and spec.get("tags"):
        tags = list(spec["tags"])            # 시리즈 스펙(korea_sounds.py)이 영어 태그를 직접 준다
    # 재생목록: 레포 변수 ASMR_PLAYLIST 가 있으면 그걸 우선(오타/불일치로 새 재생목록 생성 방지).
    #   단 시리즈는 자기 재생목록이 있다 — ASMR_PLAYLIST 로 한국어 재생목록에 섞이면 안 된다.
    playlist = (yt.get("playlist", "") if series
                else config.env("ASMR_PLAYLIST") or yt.get("playlist", ""))
    return {
        "title": yt.get("title", theme or "ASMR"),
        "description": desc,
        "privacy": privacy,
        "playlist": playlist,
        "playlist_description": yt.get("playlist_description") or None,
        "tags": tags,
        "category_id": config.env("ASMR_YT_CATEGORY", "24"),  # 24=Entertainment
        "default_language": spec.get("default_language") or None,
        # 시리즈 배경은 실제 장소를 사실적으로 그린 AI 이미지다 → 합성 콘텐츠 표시
        "synthetic": True if series else None,
    }


# ── 영어 제목(현지화) — 루틴이 안 써줘도 코드가 채운다 (2026-09-27) ─────────
# 스튜디오 실측: ASMR 13편 전부 '동영상 언어' 미설정 · 현지화 0개 → 해외 시청자도 한글 제목만 봤다.
# 그런데 해외 시청자가 ASMR 시청시간의 절반 이상이다(파도 3h: 해외 41회가 45시간,
# 한국 130회가 50시간 · 얼음 3h: 해외 53회가 52시간, 한국 270회가 9시간).
# 스펙에 localizations 가 없어 yt_i18n 이 조용히 건너뛰고 있었다 → theme_id(영문 슬러그)와
# 실제 길이로 영어 제목·설명을 결정론적으로 만든다. 루틴이 en 을 써주면 그걸 우선한다.
import re as _re

_LEAD_EMOJI = _re.compile(r"^\s*([^\w\s가-힣]+)\s*")


_SMALL = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "the", "to"}


def english_name(theme_id: str) -> str:
    words = [w for w in _re.split(r"[-_\s]+", theme_id or "") if w and w.lower() != "asmr"]
    return " ".join(w.lower() if (i and w.lower() in _SMALL) else w[:1].upper() + w[1:]
                    for i, w in enumerate(words)) or "Relaxing"


def audio_language(spec: dict) -> str:
    """나레이션이 있으면 한국어. 말소리가 없는 소리 영상은 ''(오디오 언어를 넣지 않는다).

    ★2026-10-01: 'zxx'(관련 없음)를 넣었더니 videos.insert 가 400 INVALID_REQUEST_METADATA 로
    거부했다(Korea Sleep Sounds 9/30 편 업로드 3회 실패). 유튜브 언어 목록에 zxx 가 없다.
    """
    return "ko" if (spec.get("narration_text") or "").strip() else ""


def english_localization(spec: dict, duration_sec: float | None) -> dict:
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    name = english_name(spec.get("theme_id", ""))
    m = _LEAD_EMOJI.match(yt.get("title", ""))
    emoji = (m.group(1).strip() + " ") if m else ""
    # 내림 — 한글 제목과 같은 규칙(3시간 40분 → "3 Hours"). 올리면 없는 시간을 약속하게 된다.
    hours = max(1, int((duration_sec or 0) // 3600)) if duration_sec else None
    length = f"{hours} Hour{'s' if hours != 1 else ''}" if hours else "Long"
    title = f"{emoji}{name} ASMR {length} | Sounds for Sleep, Study & Relaxing"
    if len(title) > 100:
        title = f"{emoji}{name} ASMR {length} | Sleep Sounds"[:100]
    talk = "" if (spec.get("narration_text") or "").strip() else " No talking."
    desc = (f"{name} sounds for {length.lower()} — to fall asleep, focus or unwind.{talk}\n\n"
            f"Sound sources: Freesound (CC0) · background image generated.\n"
            f"#ASMR #{name.replace(' ', '')} #SleepSounds #WhiteNoise")
    return {"title": title, "description": desc}


def asmr_localizations(spec: dict, duration_sec: float | None) -> dict:
    import yt_i18n
    if (spec.get("default_language") or "ko") != "ko":
        # 영어가 기본인 시리즈 — 스펙이 준 번역(ko 등)을 언어 목록 제한 없이 그대로 쓴다
        raw = ((spec.get("platforms") or {}).get("youtube") or {}).get("localizations") or {}
        return yt_i18n.normalize_localizations(raw, list(raw))
    loc = dict(yt_i18n.from_spec(spec))
    if "en" not in loc and "en" in yt_i18n.LANGS:
        loc["en"] = english_localization(spec, duration_sec)
    return loc


def series_thumbnail(bg_png: str | None, out_jpg: str) -> str | None:
    """시리즈 썸네일 = 영상 배경 그대로(1280×720 JPEG). 새로 그리면 영상과 다른 장면이 된다."""
    if not bg_png or not os.path.exists(bg_png):
        return None
    try:
        from PIL import Image
        Image.open(bg_png).convert("RGB").resize((1280, 720)).save(out_jpg, quality=90)
        return out_jpg
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 시리즈 썸네일 실패 → 스킵: {e}\n")
        return None


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
    fs = spec.get("freesound") or {}
    queries = fs.get("queries") or [spec.get("theme_name", "ambience")]
    try:
        clips, attrs = freesound.fetch_theme(queries, os.path.join(wd, "src"), want_sec=want,
                                             must=fs.get("must"))
    except Exception as e:  # noqa: BLE001
        res["error"] = f"freesound: {e}"
        return res
    if not clips:
        res["error"] = "freesound: 소스 음원 0개(키/쿼리/네트워크 확인)"
        return res

    # ★트리거 소재(귀르가즘 모드) — 짧은 클립이라 별도 경로로 긁는다. 없어도 렌더는 계속.
    trig_clips = []
    if str(spec.get("mode") or "sleep").lower() in ("trigger", "mixed"):
        tq = fs.get("trigger_queries") or []
        if tq:
            try:
                trig_clips, tattrs = freesound.fetch_triggers(tq, os.path.join(wd, "trg"))
                attrs += tattrs
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"[warn] 트리거 수집 실패(베드만 진행): {e}\n")
        else:
            sys.stderr.write("[warn] mode 가 trigger/mixed 인데 trigger_queries 가 비었다\n")

    # ★배경 음악(피아노 등) — 있으면 아주 낮게 깐다. 없으면 그냥 없이 간다.
    music_clips = []
    if fs.get("music_queries"):
        try:
            music_clips, mattrs = freesound.fetch_music(fs["music_queries"], os.path.join(wd, "mus"))
            attrs += mattrs
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 배경음악 수집 실패(음악 없이 진행): {e}\n")
    attrs_block = freesound.attribution_block(attrs)

    # ② 렌더
    import asmr_render
    try:
        info = asmr_render.render(spec, clips, out_mp4, wd, trigger_clips=trig_clips,
                                  music_clips=music_clips)
        res["video"] = info["out"]
        res["duration_sec"] = info["duration_sec"]
        res["size_mb"] = info["size_mb"]
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res

    # 시리즈는 배경 그림을 그대로 썸네일로 쓴다 — 렌더만 하는 검증 실행에서도 만들어 둔다(아티팩트로 확인).
    series_thumb = None
    if spec.get("series"):
        series_thumb = series_thumbnail(info.get("bg"),
                                        str(config.RENDERS_DIR / f"asmr_{date}_{theme_id}_thumb.jpg"))
        if info.get("loop"):
            import shutil
            shutil.copy(info["loop"], str(config.RENDERS_DIR / f"asmr_{date}_{theme_id}_loop.mp4"))

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
    thumb = series_thumb
    try:
        if not thumb:
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
            loc = asmr_localizations(spec, res.get("duration_sec"))
            pub = upload_youtube_novel.publish(
                res["video"], meta["title"], meta["description"], meta["privacy"],
                playlist_title=meta["playlist"], tags=meta["tags"],
                category_id=meta["category_id"], thumbnail=thumb,
                localizations=loc,
                default_language=meta["default_language"],
                i18n_langs=list(loc) if meta["default_language"] else None,
                playlist_description=meta["playlist_description"],
                synthetic=meta["synthetic"], audio_language=audio_language(spec))
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
