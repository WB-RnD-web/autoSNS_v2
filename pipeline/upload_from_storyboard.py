#!/usr/bin/env python3
"""스토리보드 JSON + 완성 mp4 → YouTube 업로드 (메타 매핑은 v1 run_daily 포팅).

v1 `run_daily.process_topic`의 upload 단계 로직을 그대로 옮긴다:
  - 제목 우선순위: hook_title > platforms.youtube.title > headline, 그리고 '#shorts' 자동 부착
  - 설명: platforms.youtube.description
  - privacy: JSON "privacy" > 환경변수 DEFAULT_PRIVACY (★강등 없이 JSON 값을 그대로 존중.
    현재 운영은 전 토픽 public — 정치 포함. 테스트 강제 private 은 --force-private 로만)
실제 업로드는 v1 upload_youtube.upload() 재사용.

안전장치:
  --dry-run        업로드 안 하고 매핑 결과만 출력(자격증명 불필요)
  --force-private  privacy를 강제로 private (테스트 단계 권장)

사용:
  # 매핑 검증(자격증명 없이):
  python upload_from_storyboard.py --storyboard ../docs/samples/2026-06-26_economy_storyboard.json \
      --video ../render/m3-short/out/2026-06-26_economy_final.mp4 --dry-run --force-private
  # 실제 업로드(자격증명 필요, 테스트는 강제 private):
  python upload_from_storyboard.py --storyboard <sb.json> --video <final.mp4> --force-private
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import config


def build_meta(sb: dict, force_private: bool) -> dict:
    """v1 run_daily upload 단계와 동일한 메타 매핑."""
    yt = sb["platforms"]["youtube"]
    title = (sb.get("hook_title") or yt.get("title") or sb.get("headline") or "").strip()
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"
    privacy = sb.get("privacy") or config.env("DEFAULT_PRIVACY", "private")
    if force_private:
        privacy = "private"
    return {
        "title": title,
        "description": yt["description"],
        "privacy": privacy,
        "tags": ["뉴스", "이슈", "쇼츠", "shorts"],   # v1 upload() 기본 태그
        "categoryId": "25",                            # News & Politics
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="스토리보드+영상 → YouTube 업로드(메타=JSON)")
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--dry-run", action="store_true", help="업로드 없이 매핑만 출력")
    ap.add_argument("--force-private", action="store_true", help="privacy 강제 private(테스트)")
    args = ap.parse_args()
    config.load_dotenv()

    with open(args.storyboard, encoding="utf-8") as f:
        sb = json.load(f)
    meta = build_meta(sb, args.force_private)

    json_privacy = sb.get("privacy", "(none)")
    print("──── 업로드 메타 매핑 (v1 포팅) ────")
    print(f"  video        : {args.video}")
    print(f"  title        : {meta['title']}")
    print(f"  privacy      : {meta['privacy']}"
          + (f"   (JSON='{json_privacy}', --force-private 적용)" if args.force_private
             else f"   (JSON='{json_privacy}' 존중)"))
    print(f"  categoryId   : {meta['categoryId']} (News & Politics)")
    print(f"  tags         : {meta['tags']}")
    print(f"  description  :\n    " + meta["description"].replace("\n", "\n    "))

    if not os.path.exists(args.video):
        print(f"\n[warn] 영상 파일 없음: {args.video}", file=sys.stderr)

    if args.dry_run:
        print("\n[dry-run] 실제 업로드는 수행하지 않음. (매핑 검증 완료)")
        return 0

    # 실제 업로드: v1 upload_youtube 재사용
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    if not os.path.exists(token) and not config.env("YT_TOKEN_JSON"):
        print("\n[error] YouTube 자격증명 없음(token.json / YT_TOKEN_JSON). "
              "업로드하려면 자격증명을 연결하거나 --dry-run 사용.", file=sys.stderr)
        return 1
    import upload_youtube
    import yt_i18n
    vid = upload_youtube.upload(args.video, meta["title"], meta["description"],
                                meta["privacy"], tags=meta["tags"],
                                localizations=yt_i18n.from_spec(sb))
    print(f"✅ 업로드 완료: https://youtu.be/{vid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
