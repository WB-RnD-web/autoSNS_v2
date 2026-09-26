#!/usr/bin/env python3
"""Threads 업로드 (Threads API / Meta).

준비:
  - Threads '프로' 계정 + Meta 앱 + Threads API 권한
  - 장기 액세스 토큰 → THREADS_ACCESS_TOKEN
  - Threads 사용자 ID → THREADS_USER_ID
  - ⚠️ IG와 동일하게 '공개 URL'의 영상을 가져간다(로컬 파일 직접 업로드 불가).

흐름: 컨테이너 생성(VIDEO) → status FINISHED 까지 폴링 → threads_publish

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


def _create_and_wait(requests, user_id, token, video_url, text):
    """컨테이너 생성 → FINISHED 대기. (컨테이너ID, None) 또는 (None, 실패사유)."""
    r = requests.post(f"{GRAPH}/{user_id}/threads", data={
        "media_type": "VIDEO", "video_url": video_url, "text": text,
        "access_token": token,
    }, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"   컨테이너 생성: {cid} — 처리 대기…")
    # 영상은 권장 대기 후 FINISHED 확인
    for _ in range(60):
        s = requests.get(f"{GRAPH}/{cid}",
                         params={"fields": "status,error_message", "access_token": token},
                         timeout=30)
        status = s.json().get("status")
        if status == "FINISHED":
            return cid, None
        if status in ("ERROR", "EXPIRED"):
            return None, s.json()
        time.sleep(5)
    return None, "처리 타임아웃(5분)"


def publish_thread(video_url: str, text: str) -> str:
    requests = _requests()
    user_id = config.env("THREADS_USER_ID")
    token = config.env("THREADS_ACCESS_TOKEN")
    if not user_id or not token:
        raise SystemExit("[error] THREADS_USER_ID / THREADS_ACCESS_TOKEN 필요(.env)")

    # ⚠️ 2026-09-27: 처리 실패를 SystemExit 가 아니라 RuntimeError 로 올린다.
    #   SystemExit 는 do_social 의 except Exception 을 뚫고 나가 ★잡 전체를 exit 1 로 끝냈다
    #   (YouTube·IG 는 이미 올라갔는데 실행이 '실패'로 찍힘 — shorts 395회 중 75회).
    #   'status: ERROR, error_message: UNKNOWN' 은 같은 영상으로 다시 만들면 통과하는 경우가 있어
    #   컨테이너를 한 번 새로 만들어 본다.
    attempts = 2
    for attempt in range(1, attempts + 1):
        cid, err = _create_and_wait(requests, user_id, token, video_url, text)
        if cid:
            break
        if attempt < attempts:
            print(f"   ↻ Threads 처리 실패 — 컨테이너 새로 만들어 재시도({attempt}/{attempts - 1}): {err}")
            time.sleep(20)
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
