#!/usr/bin/env python3
"""소설(novel) YouTube 업로드 — 일반 동영상(16:9) + 재생목록(시리즈 정주행).

쇼츠 업로드(upload_youtube.py)와 ★별개 모듈이다. 차이:
  - 스코프 확장: youtube.upload(업로드) + youtube(재생목록 생성/추가).
  - 일반 동영상으로 업로드(#shorts 금지, 16:9). categoryId 기본 24(Entertainment).
  - series_title 재생목록을 찾거나 생성하고, 업로드한 영상을 그 재생목록에 추가.
  - privacy 준수(mature/teen 회차는 보통 unlisted — spec/force 로 제어).

★ 토큰(쇼츠 무영향 + 폴백):
  - OAuth '앱'(client_secret.json)은 공유 가능. 바뀌는 건 '토큰'의 스코프뿐.
  - 소설 전용 토큰(secrets/token_novel.json / 시크릿 YT_TOKEN_JSON_NOVEL)이 있으면 그걸 쓴다(재생목록 가능).
  - 없으면 ★쇼츠 토큰(secrets/token.json / YT_TOKEN_JSON)으로 폴백 — 일반 동영상 업로드는 정상,
    재생목록만 스코프 부족으로 자동 스킵(publish 에서 graceful). 쇼츠 token.json 은 읽기만, 변경 안 함.

최초 1회(로컬, 브라우저 인증 → 확장 스코프 토큰 발급):
  python pipeline/upload_youtube_novel.py --auth-only
  → 출력된 secrets/token_novel.json '내용 전체'를 GitHub Secret 'YT_TOKEN_JSON_NOVEL' 에 저장.

업로드:
  python pipeline/upload_youtube_novel.py --video out.mp4 --title "..." \
      --description "..." --privacy unlisted --playlist "시리즈명"
"""
from __future__ import annotations
import argparse
import os

import config

# 업로드 + 재생목록(생성/추가) 둘 다 필요 → 확장 스코프
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _paths() -> tuple[str, str]:
    secret = (config.env("YT_CLIENT_SECRET_NOVEL")
              or config.env("YT_CLIENT_SECRET")
              or str(config.ROOT / "pipeline/secrets/client_secret.json"))
    # 토큰: 소설 전용(확장 스코프) 우선 → 없으면 쇼츠 토큰으로 폴백.
    #   쇼츠 토큰(youtube.upload 전용)으로도 일반 동영상 업로드는 동작하고,
    #   재생목록만 스코프 부족으로 자동 스킵된다(publish 에서 graceful).
    novel_tok = config.env("YT_TOKEN_NOVEL") or str(config.ROOT / "pipeline/secrets/token_novel.json")
    shorts_tok = config.env("YT_TOKEN") or str(config.ROOT / "pipeline/secrets/token.json")
    token = novel_tok if os.path.exists(novel_tok) else (shorts_tok if os.path.exists(shorts_tok) else novel_tok)
    return secret, token


def get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise SystemExit(f"[error] 의존성 필요: pip install -r pipeline/requirements.txt ({e})")

    secret, token = _paths()
    creds = None
    if os.path.exists(token):
        # ★토큰이 '실제 보유한 스코프'로 로드한다(SCOPES 강제 X).
        #   쇼츠 토큰(youtube.upload 전용)으로 폴백해도 토큰 갱신 시 invalid_scope 없이 업로드된다.
        #   전용 토큰(upload+youtube)이면 그 스코프 그대로 → 재생목록까지 동작.
        creds = Credentials.from_authorized_user_file(token)
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


# ── 업로드(일반 동영상) ──
def upload_video(yt, video: str, title: str, description: str,
                 privacy: str = "unlisted", tags: list[str] | None = None,
                 category_id: str | None = None) -> str:
    from googleapiclient.http import MediaFileUpload
    category_id = category_id or config.env("NOVEL_YT_CATEGORY", "24")  # 24=Entertainment
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["오디오소설", "소설낭독", "잠들기전", "이야기"],
            "categoryId": category_id,
        },
        # 16:9 일반 동영상. #shorts 없음. 성인 대상(아동용 아님).
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
    print(f"✅ YouTube 업로드: https://youtu.be/{vid} (privacy={privacy}, 16:9 일반영상)")
    return vid


# ── 재생목록(시리즈 정주행) ──
def find_playlist(yt, title: str) -> str | None:
    """내 채널에서 같은 제목의 재생목록 검색(있으면 id)."""
    token = None
    while True:
        resp = yt.playlists().list(part="snippet", mine=True, maxResults=50,
                                   pageToken=token).execute()
        for it in resp.get("items", []):
            if (it["snippet"].get("title") or "").strip() == title.strip():
                return it["id"]
        token = resp.get("nextPageToken")
        if not token:
            return None


def create_playlist(yt, title: str, description: str = "", privacy: str = "public") -> str:
    resp = yt.playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": title[:150], "description": description[:5000]},
              "status": {"privacyStatus": privacy}}).execute()
    pid = resp["id"]
    print(f"   ＋ 재생목록 생성: {title!r} ({pid})")
    return pid


def ensure_playlist(yt, title: str, description: str = "", privacy: str = "public") -> str:
    if not title.strip():
        raise ValueError("재생목록 제목이 비어있음")
    pid = find_playlist(yt, title)
    if pid:
        print(f"   ↺ 기존 재생목록 사용: {title!r} ({pid})")
        return pid
    return create_playlist(yt, title, description, privacy)


def add_to_playlist(yt, playlist_id: str, video_id: str) -> None:
    yt.playlistItems().insert(
        part="snippet",
        body={"snippet": {"playlistId": playlist_id,
                          "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
    print(f"   ＋ 재생목록에 추가: {video_id} → {playlist_id}")


# ── 고수준 퍼블리시(업로드 → 재생목록 보장 → 추가) ──
def publish(video: str, title: str, description: str, privacy: str,
            playlist_title: str = "", tags: list[str] | None = None,
            category_id: str | None = None) -> dict:
    yt = get_service()
    vid = upload_video(yt, video, title, description, privacy, tags, category_id)
    res = {"video_id": vid, "url": f"https://youtu.be/{vid}", "privacy": privacy, "playlist_id": None}
    if playlist_title.strip():
        try:
            # 재생목록 공개도(영상이 unlisted 라도 재생목록은 public 으로 노출 가능 — 운영 선택)
            pl_privacy = config.env("NOVEL_PLAYLIST_PRIVACY", "public")
            pid = ensure_playlist(yt, playlist_title,
                                  description="시리즈 정주행 재생목록 · 오리지널 창작",
                                  privacy=pl_privacy)
            add_to_playlist(yt, pid, vid)
            res["playlist_id"] = pid
        except Exception as e:  # noqa: BLE001
            res["playlist_error"] = str(e)
            print(f"   ⚠️ 재생목록 처리 실패(업로드는 성공): {e}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="소설 YouTube 업로드(일반영상 + 재생목록)")
    ap.add_argument("--video")
    ap.add_argument("--title")
    ap.add_argument("--description", default="")
    ap.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    ap.add_argument("--playlist", default="")
    ap.add_argument("--auth-only", action="store_true",
                    help="브라우저 인증만 수행해 token_novel.json(확장 스코프) 발급")
    args = ap.parse_args()
    config.load_dotenv()

    if args.auth_only:
        get_service()
        _, token = _paths()
        print(f"✅ 인증 완료 — {token} 생성됨(스코프: upload + youtube).\n"
              f"   이 파일 '내용 전체'를 GitHub Secret 'YT_TOKEN_JSON_NOVEL' 에 넣으세요.\n"
              f"   (쇼츠 token.json 은 건드리지 않습니다.)")
        return 0

    if not args.video or not args.title:
        print("[error] --video 와 --title 필요 (또는 최초 인증은 --auth-only)")
        return 1
    if not os.path.exists(args.video):
        print(f"[error] 영상 없음: {args.video}")
        return 1
    res = publish(args.video, args.title, args.description, args.privacy, args.playlist)
    print(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
