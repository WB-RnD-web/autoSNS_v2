#!/usr/bin/env python3
"""YouTube Shorts 업로드 (YouTube Data API v3).

준비:
  1) Google Cloud Console에서 OAuth 클라이언트(데스크톱) 생성 → client_secret.json 다운로드
  2) pipeline/secrets/client_secret.json 에 둔다 (YT_CLIENT_SECRET 로 경로 변경 가능)
  3) 최초 실행 시 브라우저 인증 → token.json 캐시(이후 무인 갱신)
세로(9:16) 영상 + 제목/설명에 #Shorts 면 Shorts로 인식된다.

사용:
  python pipeline/upload_youtube.py --video output/renders/2026-06-19_final.mp4 \
      --title "[일상공감뉴스] ... #Shorts" --description "..." --privacy private
"""
from __future__ import annotations
import argparse
import os

import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise SystemExit(f"[error] 의존성 필요: pip install -r pipeline/requirements.txt ({e})")

    secret = config.env("YT_CLIENT_SECRET", str(config.ROOT / "pipeline/secrets/client_secret.json"))
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    creds = None
    if os.path.exists(token):
        creds = Credentials.from_authorized_user_file(token, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secret, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token), exist_ok=True)
        with open(token, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(video: str, title: str, description: str, privacy: str = "private",
           tags: list[str] | None = None) -> str:
    from googleapiclient.http import MediaFileUpload
    yt = get_service()
    body = {
        "snippet": {"title": title[:100], "description": description,
                    "tags": tags or ["뉴스", "이슈", "쇼츠", "shorts"],
                    "categoryId": "25"},  # News & Politics
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"   업로드 {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"✅ YouTube 업로드 완료: https://youtu.be/{vid} (privacy={privacy})")
    return vid


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube Shorts 업로드")
    ap.add_argument("--video")
    ap.add_argument("--title")
    ap.add_argument("--description", default="")
    ap.add_argument("--privacy", default=config.env("DEFAULT_PRIVACY", "private"),
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--auth-only", action="store_true",
                    help="브라우저 인증만 수행해 token.json 생성(업로드 안 함). 최초 1회용")
    args = ap.parse_args()
    config.load_dotenv()

    if args.auth_only:   # 최초 1회: 로컬 브라우저 인증 → token.json(리프레시 토큰) 발급
        get_service()
        token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
        print(f"✅ 인증 완료 — {token} 생성됨.\n"
              f"   이 파일 '내용 전체'를 GitHub Secret 'YT_TOKEN_JSON' 에 넣으세요.")
        return 0

    if not args.video or not args.title:
        print("[error] --video 와 --title 필요 (또는 최초 인증은 --auth-only)")
        return 1
    if not os.path.exists(args.video):
        print(f"[error] 영상 없음: {args.video}")
        return 1
    upload(args.video, args.title, args.description, args.privacy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
