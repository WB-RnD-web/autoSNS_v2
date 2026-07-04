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

FOLDER = "autosns_v2"


def _configure() -> bool:
    """Cloudinary SDK 설정. 자격증명/미설치 시 False."""
    cloud = config.env("CLOUDINARY_CLOUD_NAME")
    key = config.env("CLOUDINARY_API_KEY")
    secret = config.env("CLOUDINARY_API_SECRET")
    url_env = config.env("CLOUDINARY_URL")
    if not url_env and not (cloud and key and secret):
        return False
    try:
        import cloudinary
    except ImportError:
        sys.stderr.write("[warn] cloudinary 미설치 — pip install cloudinary\n")
        return False
    if not url_env:
        cloudinary.config(cloud_name=cloud, api_key=key, api_secret=secret, secure=True)
    else:
        cloudinary.config(secure=True)  # CLOUDINARY_URL 자동 인식
    return True


def host(video_path: str, public_id: str) -> str | None:
    if not _configure():
        return None
    import cloudinary.uploader
    res = cloudinary.uploader.upload_large(
        video_path, resource_type="video", public_id=public_id,
        overwrite=True, folder=FOLDER)
    return res.get("secure_url")


def cleanup(public_id: str) -> bool:
    """게시 완료 후 Cloudinary 원본 삭제(저장공간 회수). 성공 시 True.

    IG/Threads 는 게시 시점에 영상을 자기 서버로 복사하므로, 게시 이후
    Cloudinary 원본은 불필요 → 삭제해서 무료 플랜 저장 한도 누수를 막는다.
    삭제 실패는 치명적이지 않음(다음 실행에 overwrite 됨) → 경고만 남기고 False.
    """
    if not _configure():
        return False
    try:
        import cloudinary.uploader
        res = cloudinary.uploader.destroy(
            f"{FOLDER}/{public_id}", resource_type="video", invalidate=True)
        return res.get("result") == "ok"
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] Cloudinary 정리 실패({public_id}): {e}\n")
        return False


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
