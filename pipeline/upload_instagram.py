#!/usr/bin/env python3
"""Instagram Reels 업로드 (Instagram Graph API).

준비:
  - 인스타 '프로(비즈니스/크리에이터)' 계정 + 연결된 Facebook 페이지
  - Meta 앱 + 장기 액세스 토큰 → IG_ACCESS_TOKEN
  - IG 비즈니스 계정 ID → IG_USER_ID
  - ⚠️ IG는 '공개 URL'의 영상을 가져간다(로컬 파일 직접 업로드 불가).
    최종 mp4를 공개 호스팅(클라우드 버킷/Drive 공개링크/CDN)에 올린 뒤 그 URL을 전달.

흐름: 컨테이너 생성(REELS) → status FINISHED 까지 폴링 → media_publish
카드(캐러셀): 이미지마다 컨테이너(is_carousel_item=true) → CAROUSEL 컨테이너(children) → FINISHED 폴링 → media_publish
  (publish_carousel — 이미지는 공개 URL 의 JPEG, 2~10장, 모든 장이 첫 장 비율로 잘린다)
http/sleep/user_id/token 인자는 테스트·dry-run 용(가짜 전송으로 호출 순서만 확인). 안 주면 requests + 환경변수.

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


def _creds(user_id: str | None, token: str | None) -> tuple[str, str]:
    user_id = user_id or config.env("IG_USER_ID")
    token = token or config.env("IG_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit("[error] IG_USER_ID / IG_ACCESS_TOKEN 환경변수 필요(.env)")
    return user_id, token


def _wait(requests, cid: str, token: str, what: str, sleep=time.sleep, tries: int = 60, every: float = 5) -> None:
    """컨테이너 status_code 가 FINISHED 가 될 때까지(ERROR·EXPIRED 면 RuntimeError)."""
    for _ in range(tries):
        s = requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code", "access_token": token}, timeout=30)
        code = s.json().get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG {what} 처리 실패: {s.json()}")
        sleep(every)
    raise RuntimeError(f"IG {what} 처리 타임아웃")


def publish_carousel(image_urls: list[str], caption: str, *, http=None, sleep=time.sleep,
                     user_id: str | None = None, token: str | None = None) -> str:
    """카드(캐러셀) 게시 → media_id. image_urls = 공개 URL 의 JPEG 2~10장(순서 = 넘기는 순서)."""
    requests = http or _requests()
    user_id, token = _creds(user_id, token)
    if not 2 <= len(image_urls) <= 10:
        raise RuntimeError(f"IG 캐러셀은 2~10장 — 지금 {len(image_urls)}장")
    children = []
    for k, url in enumerate(image_urls, 1):                 # 1) 장마다 컨테이너
        r = requests.post(f"{GRAPH}/{user_id}/media", data={
            "image_url": url, "is_carousel_item": "true", "access_token": token}, timeout=60)
        _check(r, f"카드 {k} 컨테이너 생성")
        children.append(r.json()["id"])
    for k, cid in enumerate(children, 1):
        _wait(requests, cid, token, f"카드 {k}", sleep, tries=24)
    r = requests.post(f"{GRAPH}/{user_id}/media", data={    # 2) 캐러셀 컨테이너
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption,
        "access_token": token}, timeout=60)
    _check(r, "캐러셀 컨테이너 생성")
    cid = r.json()["id"]
    print(f"   캐러셀 컨테이너 생성: {cid}({len(children)}장) — 처리 대기…")
    _wait(requests, cid, token, "캐러셀", sleep)
    p = requests.post(f"{GRAPH}/{user_id}/media_publish",   # 3) 게시
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    _check(p, "캐러셀 게시")
    media_id = p.json()["id"]
    print(f"✅ Instagram 카드(캐러셀) 게시 완료: media_id={media_id}")
    return media_id


def publish_reel(video_url: str, caption: str, share_to_feed: bool = True,
                 cover_url: str | None = None, *, http=None, sleep=time.sleep,
                 user_id: str | None = None, token: str | None = None) -> str:
    requests = http or _requests()
    user_id = user_id or config.env("IG_USER_ID")
    token = token or config.env("IG_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit("[error] IG_USER_ID / IG_ACCESS_TOKEN 환경변수 필요(.env)")

    # 1) 컨테이너 생성
    #    cover_url(공개 이미지 URL)을 주면 릴스 커버로 사용 → 검은 첫프레임 미리보기 방지.
    #    (안 주면 IG 는 thumb_offset 기본값 0 = 첫 프레임을 커버로 씀.)
    data = {
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": str(share_to_feed).lower(), "access_token": token,
    }
    if cover_url:
        data["cover_url"] = cover_url
    r = requests.post(f"{GRAPH}/{user_id}/media", data=data, timeout=60)
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
        # ★SystemExit 가 아니라 RuntimeError — do_social 이 잡아 요약에 남기고 잡은 계속 간다
        #   (SystemExit 는 except Exception 을 뚫고 잡 전체를 exit 1 로 끝냈다)
        if code == "ERROR":
            raise RuntimeError(f"IG 미디어 처리 실패: {s.json()}")
        sleep(5)
    else:
        raise RuntimeError("IG 미디어 처리 타임아웃")

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
