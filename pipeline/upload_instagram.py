#!/usr/bin/env python3
"""Instagram Reels 업로드 (Instagram Graph API).

준비:
  - 인스타 '프로(비즈니스/크리에이터)' 계정 + 연결된 Facebook 페이지
  - Meta 앱 + 장기 액세스 토큰 → IG_ACCESS_TOKEN
  - IG 비즈니스 계정 ID → IG_USER_ID
  - ⚠️ IG는 '공개 URL'의 영상을 가져간다(로컬 파일 직접 업로드 불가).
    최종 mp4를 공개 호스팅(클라우드 버킷/Drive 공개링크/CDN)에 올린 뒤 그 URL을 전달.

흐름: 컨테이너 생성(REELS) → status FINISHED 까지 폴링 → media_publish

⚠️ 엔드포인트: 이 앱은 'Instagram API with Instagram Login' 방식이라 토큰이
   graph.instagram.com 에서만 유효(IGAA... 형식). graph.facebook.com 로 보내면
   code 190 "Cannot parse access token" 로 실패한다. IG_USER_ID 도 graph.facebook.com
   의 17841... 가 아니라 graph.instagram.com/me 가 주는 ID 여야 함.

사용:
  python pipeline/upload_instagram.py --video-url https://.../final.mp4 --caption "..."
"""
from __future__ import annotations
import argparse
import time

import config

GRAPH = "https://graph.instagram.com"


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def _check(r, ctx: str):
    """비200이면 Meta 에러 본문(error.message/code)까지 담아 RuntimeError.

    raise_for_status()는 status만 알려주고 원인(JSON)을 버려서 진단이 안 됨.
    RuntimeError 로 올려 do_social 의 except Exception 이 요약에 남기게 한다.
    """
    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
            detail = f"{err.get('message','')} (code={err.get('code')}, subcode={err.get('error_subcode')})"
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        raise RuntimeError(f"{ctx} {r.status_code}: {detail}")


def publish_reel(video_url: str, caption: str, share_to_feed: bool = True) -> str:
    requests = _requests()
    user_id = config.env("IG_USER_ID")
    token = config.env("IG_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit("[error] IG_USER_ID / IG_ACCESS_TOKEN 환경변수 필요(.env)")

    # 1) 컨테이너 생성
    r = requests.post(f"{GRAPH}/{user_id}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": str(share_to_feed).lower(), "access_token": token,
    }, timeout=60)
    _check(r, "컨테이너 생성")
    cid = r.json()["id"]
    print(f"   컨테이너 생성: {cid} — 처리 대기…")

    # 2) 처리 완료 대기(최대 ~5분)
    for _ in range(60):
        s = requests.get(f"{GRAPH}/{cid}",
                         params={"fields": "status_code", "access_token": token}, timeout=30)
        code = s.json().get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise SystemExit(f"[error] IG 미디어 처리 실패: {s.json()}")
        time.sleep(5)
    else:
        raise SystemExit("[error] IG 미디어 처리 타임아웃")

    # 3) 게시
    p = requests.post(f"{GRAPH}/{user_id}/media_publish",
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    _check(p, "게시")
    media_id = p.json()["id"]
    print(f"✅ Instagram Reels 게시 완료: media_id={media_id}")
    return media_id


def main() -> int:
    ap = argparse.ArgumentParser(description="Instagram Reels 업로드")
    ap.add_argument("--video-url", required=True, help="공개 접근 가능한 mp4 URL")
    ap.add_argument("--caption", default="")
    args = ap.parse_args()
    config.load_dotenv()
    publish_reel(args.video_url, args.caption)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
