#!/usr/bin/env python3
"""Threads 업로드 (Threads API / Meta).

준비:
  - Threads '프로' 계정 + Meta 앱 + Threads API 권한
  - 장기 액세스 토큰 → THREADS_ACCESS_TOKEN
  - Threads 사용자 ID → THREADS_USER_ID
  - ⚠️ IG와 동일하게 '공개 URL'의 영상을 가져간다(로컬 파일 직접 업로드 불가).

흐름: 컨테이너 생성(VIDEO) → status FINISHED 까지 폴링 → threads_publish
카드(캐러셀): 이미지마다 컨테이너(media_type=IMAGE, is_carousel_item=true) → CAROUSEL 컨테이너(children, text)
  → FINISHED 폴링 → threads_publish  (publish_carousel — 2~20장, 글 500자, 주제 태그는 topic_tag 하나)
http/sleep/user_id/token 인자는 테스트·dry-run 용(가짜 전송으로 호출 순서만 확인). 안 주면 requests + 환경변수.

사용:
  python pipeline/upload_threads.py --video-url https://.../final.mp4 --text "..."
"""
from __future__ import annotations
import argparse
import time

import config

GRAPH = "https://graph.threads.net/v1.0"


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def _check(r, ctx: str):
    """비200이면 Meta 에러 본문까지 담아 RuntimeError(raise_for_status 는 원인을 버린다)."""
    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
            detail = f"{err.get('message','')} (code={err.get('code')}, subcode={err.get('error_subcode')})"
        except Exception:  # noqa: BLE001
            detail = r.text[:400]
        raise RuntimeError(f"{ctx} {r.status_code}: {detail}")


def _creds(user_id: str | None, token: str | None) -> tuple[str, str]:
    user_id = user_id or config.env("THREADS_USER_ID")
    token = token or config.env("THREADS_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit("[error] THREADS_USER_ID / THREADS_ACCESS_TOKEN 필요(.env)")
    return user_id, token


def _wait(requests, cid, token, sleep=time.sleep, tries: int = 60, every: float = 5):
    """FINISHED 까지 대기. (컨테이너ID, None) 또는 (None, 실패사유)."""
    for _ in range(tries):
        s = requests.get(f"{GRAPH}/{cid}",
                         params={"fields": "status,error_message", "access_token": token},
                         timeout=30)
        status = s.json().get("status")
        if status in ("FINISHED", "PUBLISHED"):
            return cid, None
        if status in ("ERROR", "EXPIRED"):
            return None, s.json()
        sleep(every)
    return None, f"처리 타임아웃({int(tries * every)}초)"


def _create_and_wait(requests, user_id, token, video_url, text, topic_tag=None, sleep=time.sleep):
    """컨테이너 생성 → FINISHED 대기. (컨테이너ID, None) 또는 (None, 실패사유)."""
    data = {"media_type": "VIDEO", "video_url": video_url, "text": text, "access_token": token}
    if topic_tag:
        data["topic_tag"] = topic_tag
    r = requests.post(f"{GRAPH}/{user_id}/threads", data=data, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"   컨테이너 생성: {cid} — 처리 대기…")
    # 영상은 권장 대기 후 FINISHED 확인
    return _wait(requests, cid, token, sleep)


def publish_carousel(image_urls: list[str], text: str, topic_tag: str | None = None, *, http=None,
                     sleep=time.sleep, user_id: str | None = None, token: str | None = None) -> str:
    """카드(캐러셀) 게시 → thread id. image_urls = 공개 URL 이미지 2~20장(순서 = 넘기는 순서), text 500자 안."""
    requests = http or _requests()
    user_id, token = _creds(user_id, token)
    if not 2 <= len(image_urls) <= 20:
        raise RuntimeError(f"Threads 캐러셀은 2~20장 — 지금 {len(image_urls)}장")
    children = []
    for k, url in enumerate(image_urls, 1):                 # 1) 장마다 컨테이너
        r = requests.post(f"{GRAPH}/{user_id}/threads", data={
            "media_type": "IMAGE", "image_url": url, "is_carousel_item": "true", "access_token": token}, timeout=60)
        _check(r, f"카드 {k} 컨테이너 생성")
        children.append(r.json()["id"])
    for k, cid in enumerate(children, 1):
        ok, err = _wait(requests, cid, token, sleep, tries=24)
        if not ok:
            raise RuntimeError(f"Threads 카드 {k} 처리 실패: {err}")
    data = {"media_type": "CAROUSEL", "children": ",".join(children), "text": text, "access_token": token}
    if topic_tag:
        data["topic_tag"] = topic_tag
    r = requests.post(f"{GRAPH}/{user_id}/threads", data=data, timeout=60)   # 2) 캐러셀 컨테이너
    _check(r, "캐러셀 컨테이너 생성")
    cid = r.json()["id"]
    print(f"   캐러셀 컨테이너 생성: {cid}({len(children)}장) — 처리 대기…")
    ok, err = _wait(requests, cid, token, sleep)
    if not ok:
        raise RuntimeError(f"Threads 캐러셀 처리 실패: {err}")
    p = requests.post(f"{GRAPH}/{user_id}/threads_publish",  # 3) 게시
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    _check(p, "캐러셀 게시")
    tid = p.json()["id"]
    print(f"✅ Threads 카드(캐러셀) 게시 완료: id={tid}")
    return tid


def publish_image(image_url: str, text: str, topic_tag: str | None = None, *, http=None,
                  sleep=time.sleep, user_id: str | None = None, token: str | None = None) -> str:
    """이미지 한 장 + 글(500자 안) → thread id. 쓰레드 '글' 형식(2026-10-06 A/B) — 카드 첫 장을 붙인다."""
    requests = http or _requests()
    user_id, token = _creds(user_id, token)
    data = {"media_type": "IMAGE", "image_url": image_url, "text": text, "access_token": token}
    if topic_tag:
        data["topic_tag"] = topic_tag
    r = requests.post(f"{GRAPH}/{user_id}/threads", data=data, timeout=60)     # 1) 컨테이너
    _check(r, "이미지 글 컨테이너 생성")
    cid = r.json()["id"]
    ok, err = _wait(requests, cid, token, sleep, tries=24)
    if not ok:
        raise RuntimeError(f"Threads 이미지 글 처리 실패: {err}")
    p = requests.post(f"{GRAPH}/{user_id}/threads_publish",                    # 2) 게시
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    _check(p, "이미지 글 게시")
    tid = p.json()["id"]
    print(f"✅ Threads 글+이미지 게시 완료: id={tid}")
    return tid


def publish_thread(video_url: str, text: str, topic_tag: str | None = None, *, http=None,
                   sleep=time.sleep, user_id: str | None = None, token: str | None = None) -> str:
    requests = http or _requests()
    user_id, token = _creds(user_id, token)

    # ⚠️ 2026-09-27: 처리 실패를 SystemExit 가 아니라 RuntimeError 로 올린다.
    #   SystemExit 는 do_social 의 except Exception 을 뚫고 나가 ★잡 전체를 exit 1 로 끝냈다
    #   (YouTube·IG 는 이미 올라갔는데 실행이 '실패'로 찍힘 — shorts 395회 중 75회).
    #   'status: ERROR, error_message: UNKNOWN' 은 같은 영상으로 다시 만들면 통과하는 경우가 있어
    #   컨테이너를 한 번 새로 만들어 본다.
    attempts = 2
    for attempt in range(1, attempts + 1):
        cid, err = _create_and_wait(requests, user_id, token, video_url, text, topic_tag, sleep)
        if cid:
            break
        if attempt < attempts:
            print(f"   ↻ Threads 처리 실패 — 컨테이너 새로 만들어 재시도({attempt}/{attempts - 1}): {err}")
            sleep(20)
    else:
        raise RuntimeError(f"Threads 처리 실패: {err}")

    # 3) 게시
    p = requests.post(f"{GRAPH}/{user_id}/threads_publish",
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    p.raise_for_status()
    tid = p.json()["id"]
    print(f"✅ Threads 게시 완료: id={tid}")
    return tid


def main() -> int:
    ap = argparse.ArgumentParser(description="Threads 업로드")
    ap.add_argument("--video-url", required=True, help="공개 접근 가능한 mp4 URL")
    ap.add_argument("--text", default="")
    args = ap.parse_args()
    config.load_dotenv()
    publish_thread(args.video_url, args.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
