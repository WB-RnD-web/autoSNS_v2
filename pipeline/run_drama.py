#!/usr/bin/env python3
"""사연 오디오드라마 파이프라인 — 검사 → 렌더 → 업로드 (2026-09-29 파일럿).

입력은 루틴이 routine/drama 에 올린 폴더(또는 그 안의 spec.json). ★spec.json 을 믿지 않고
장별 대본(chNN.txt)·meta.json 에서 다시 조립해 검사한다 — 검사를 못 넘으면 올리지 않는다.

    python run_drama.py ../output/drama/2026-10-02_mother-house/spec.json --no-upload
    python run_drama.py ../docs/samples/drama_sample --no-upload --allow-short   # 짧은 견본으로 경로 점검
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

import config
import drama_plan
import drama_render

PLAYLIST = os.environ.get("DRAMA_PLAYLIST") or "사연 드라마 (전편 듣기)"
PLAYLIST_DESC = "AI 기술로 만든 창작 사연 오디오드라마 · 매주 한 편 · 잠들기 전, 일하면서 들으세요"
DISCLAIMER = ("※ 이 이야기는 AI 기술을 활용해 만든 창작(허구)입니다. "
              "등장인물·단체·사건은 실제와 관계없습니다.")
CREDIT = "🎙️ 목소리: Supertonic (Supertone · OpenRAIL-M) · 🎨 그림: AI 생성"
HASHTAGS = "#사연 #오디오드라마 #인생사연 #사연라디오 #노후사연"
BASE_TAGS = ["사연", "오디오드라마", "인생사연", "사연라디오", "노후사연", "라디오드라마", "시니어"]


def compose_description(spec: dict, chapters: str) -> str:
    body = (spec.get("description") or "").strip()
    desc = f"{body}\n\n⏱ 목차\n{chapters}\n\n{DISCLAIMER}\n{CREDIT}\n\n{HASHTAGS}"
    return desc[:4900]


def load_ledger(path: str | None) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_ledger(path: str | None, led: dict):
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(led, f, ensure_ascii=False, indent=1)


def process(target: str, args, led: dict) -> dict:
    folder = os.path.dirname(target) if target.endswith(".json") else target
    res = {"folder": folder, "error": None, "uploaded": None}
    spec = drama_plan.build(folder)
    probs = drama_plan.check(spec, allow_short=args.allow_short)
    st = spec["stats"]
    print(f"▶ {spec['date']} {spec['archetype']} — {spec['title']}\n"
          f"   {st['chars']:,}자 · {st['chapters']}장 · 화자 {st['narrator_share']:.0%} · 예상 {st['est_min']}분")
    if probs:
        for p in probs:
            print(f"::error title=사연 드라마 검사::{p}")
        res["error"] = "검사 실패: " + " / ".join(probs[:5])
        return res
    if spec["story_id"] in led and not args.force:
        print(f"   ⏭️ 이미 올림({led[spec['story_id']]}) — 건너뜀")
        res["uploaded"] = led[spec["story_id"]]
        return res
    wd = os.path.join(str(config.OUTPUT), "_work", f"drama_{spec['date']}")
    out = drama_render.render(spec, str(config.RENDERS_DIR), wd)
    res.update({k: out[k] for k in ("video", "duration_min", "fallback", "tts_sec")})
    if args.no_upload:
        print("   ⏭️ --no-upload")
        return res
    privacy = "private" if args.force_private else "public"
    import upload_youtube_novel as U
    pub = U.publish(out["video"], spec["title"], compose_description(spec, out["chapters"]), privacy,
                    playlist_title=PLAYLIST, tags=(spec.get("tags") or [])[:10] + BASE_TAGS,
                    category_id="24", thumbnail=out["thumb"], srt=out["srt"],
                    default_language="ko", playlist_description=PLAYLIST_DESC, synthetic=True)
    res["uploaded"] = pub.get("url")
    led[spec["story_id"]] = pub.get("url")
    print(f"✅ 업로드 {pub.get('url')} ({privacy}) · 재생목록 {pub.get('playlist_id')}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="사연 오디오드라마 렌더·업로드")
    ap.add_argument("targets", nargs="+", help="output/drama/<폴더> 또는 그 안의 spec.json")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--allow-short", action="store_true", help="분량 검사 생략(견본 점검용 — 업로드 금지와 함께)")
    ap.add_argument("--force", action="store_true", help="ledger 에 있어도 다시")
    ap.add_argument("--ledger-path", default=None)
    ap.add_argument("--log", default=None)
    args = ap.parse_args()
    config.load_dotenv()
    if args.allow_short and not args.no_upload:
        print("::error::--allow-short 는 --no-upload 와 함께만 쓴다(짧은 견본이 공개되지 않게)")
        return 2
    led = load_ledger(args.ledger_path)
    results, t0 = [], time.time()
    for t in args.targets:
        try:
            results.append(process(t, args, led))
        except Exception as e:  # noqa: BLE001
            print(f"::error title=사연 드라마::{t}: {e}")
            results.append({"folder": t, "error": str(e)})
    save_ledger(args.ledger_path, led)
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results, "sec": round(time.time() - t0)}, f, ensure_ascii=False, indent=1)
    return 1 if any(r.get("error") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
