#!/usr/bin/env python3
"""Gumiho Games 업로드 — ★항상 비공개로 올린다. 사람이 스튜디오에서 보고 공개한다(주 30분 확인).

    python gumiho/upload.py output/gumiho/matches/<판>.json --renders output/gumiho/renders

올리지 않는 경우(코드로 막는다):
  - 한 백엔드로 모든 자리를 채운 점검용 판(test_backend) — 출연진 이름과 실제 모델이 다르다
  - drama.usable 이 아닌 판(메움 비율 초과·욕설 필터)
  - ledger 에 이미 올린 판
토큰: YT_TOKEN_NOVEL 이 가리키는 파일(워크플로가 시크릿 YT_TOKEN_JSON_GUMIHO 로 만든다).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

PLAYLIST = {"fox-hunt": "Fox Hunt — every match"}
PLAYLIST_DESC = "Six AI models, one hidden fox. Every match of Fox Hunt on Gumiho Games."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("match")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "gumiho", "renders"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "gumiho", "ledger.json"))
    args = ap.parse_args()
    with open(args.match, encoding="utf-8") as f:
        m = json.load(f)
    stem = os.path.splitext(os.path.basename(args.match))[0]
    if m.get("test_backend"):
        print(f"::error::점검용 판(모든 자리 {m['test_backend']})은 올리지 않는다")
        return 2
    if not m.get("drama", {}).get("usable"):
        print(f"::error::사용 불가 판(메움 {m.get('drama', {}).get('fallback_ratio')} · flags {m.get('flags')})")
        return 2
    led = {}
    if os.path.exists(args.ledger):
        with open(args.ledger, encoding="utf-8") as f:
            led = json.load(f)
    if stem in led:
        print(f"⏭️ 이미 올림: {led[stem]}")
        return 0
    with open(os.path.join(args.renders, f"{stem}_meta.json"), encoding="utf-8") as f:
        md = json.load(f)
    import upload_youtube_novel as U
    pub = U.publish(os.path.join(args.renders, f"{stem}.mp4"), md["title"], md["description"], "private",
                    playlist_title=PLAYLIST.get(m["game"], "Gumiho Games"), tags=md["tags"], category_id="20",
                    thumbnail=os.path.join(args.renders, f"{stem}_thumb.jpg"),
                    srt=os.path.join(args.renders, f"{stem}.srt"), default_language="en",
                    playlist_description=PLAYLIST_DESC, synthetic=True)
    led[stem] = pub.get("url")
    os.makedirs(os.path.dirname(args.ledger), exist_ok=True)
    with open(args.ledger, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)
    print(f"✅ 비공개 업로드 {pub.get('url')} — 스튜디오에서 확인 후 공개하세요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
