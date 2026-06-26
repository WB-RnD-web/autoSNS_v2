#!/usr/bin/env python3
"""완성 mp4 를 공개 HTTPS URL 로 호스팅 (Cloudinary).

IG Reels / Threads 는 '공개 URL의 영상'을 가져가므로(파일 직접 업로드 불가),
업로드 전에 mp4 를 공개 호스트에 올려 secure_url 을 얻는다.

요구 환경변수(시크릿): CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
  (또는 단일 CLOUDINARY_URL=cloudinary://<key>:<secret>@<cloud_name>)
없으면 None 반환 → 호출측에서 IG/Threads 스킵.
"""
from __future__ import annotations
import os
import sys

import config


def host(video_path: str, public_id: str) -> str | None:
    cloud = config.env("CLOUDINARY_CLOUD_NAME")
    key = config.env("CLOUDINARY_API_KEY")
    secret = config.env("CLOUDINARY_API_SECRET")
    url_env = config.env("CLOUDINARY_URL")
    if not url_env and not (cloud and key and secret):
        return None
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        sys.stderr.write("[warn] cloudinary 미설치 — pip install cloudinary\n")
        return None
    if not url_env:
        cloudinary.config(cloud_name=cloud, api_key=key, api_secret=secret, secure=True)
    else:
        cloudinary.config(secure=True)  # CLOUDINARY_URL 자동 인식
    res = cloudinary.uploader.upload_large(
        video_path, resource_type="video", public_id=public_id,
        overwrite=True, folder="autosns_v2")
    return res.get("secure_url")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="mp4 → Cloudinary 공개 URL")
    ap.add_argument("--video", required=True)
    ap.add_argument("--public-id", default="test")
    args = ap.parse_args()
    config.load_dotenv()
    u = host(args.video, args.public_id)
    print(u or "[skip] Cloudinary 자격증명 없음")
    return 0 if u else 1


if __name__ == "__main__":
    raise SystemExit(main())
