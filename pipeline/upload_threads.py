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
글(2026-10-10 publish_text): media_type=TEXT 컨테이너 → FINISHED → threads_publish. 공식 문서(developers.facebook.com/docs/threads)로 확인:
  - 투표 poll_attachment = {"option_a", "option_b", "option_c"?, "option_d"?} — 2~4개 · 한 개 1~25자 · 글(TEXT)에만
  - 스포일러 text_entities = [{"entity_type": "SPOILER", "offset", "length"}] — 글 하나에 10개까지
    (문서에 offset 단위가 없다 → UTF-16 단위로 센다. 이모지 없는 한글이면 글자 수와 같다 — 스포일러 글엔 이모지를 넣지 않는다)
  - 그림 스포일러 is_spoiler_media=true — IMAGE·VIDEO·CAROUSEL 만
  - 답글 reply_to_id = 게시된 글 id (publish_reply — 내 글에 내가 다는 답글)
  - 상태 확인 GET /{container}?fields=status,error_message (FINISHED·PUBLISHED·ERROR·EXPIRED)
http/sleep/user_id/token 인자는 테스트·dry-run 용(가짜 전송으로 호출 순서만 확인). 안 주면 requests + 환경변수.

사용:
  python pipeline/upload_threads.py --video-url https://.../final.mp4 --text "..."
"""
from __future__ import annotations
import argparse
import json
import time

import config

GRAPH = "https://graph.threads.net/v1.0"
TEXT_MAX = 500                      # 글 한도(이모지는 UTF-8 바이트 수로 센다)
POLL_KEYS = ("option_a", "option_b", "option_c", "option_d")
POLL_OPTION_MAX = 25                # 투표 보기 한 개 1~25자
SPOILER_MAX = 10                    # 글 하나에 스포일러 10개까지


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


# ── 글·투표·스포일러·답글(2026-10-10) ─────────────────────
def text_len(text: str) -> int:
    """쓰레드가 세는 글자 수 — 이모지는 UTF-8 바이트 수(공식 문서), 나머지는 한 글자(insta.threads_len 과 같은 규칙)."""
    n = 0
    for c in text:
        o = ord(c)
        emoji = o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0xFE0F, 0x200D, 0x20E3)
        n += len(c.encode("utf-8")) if emoji else 1
    return n


def _u16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def spoiler(text: str, part: str, start: int = 0) -> dict:
    """text 안의 part(start 글자 뒤 처음 나오는 것)를 가리는 스포일러 한 개 — offset·length 는 UTF-16 단위."""
    i = text.find(part, start)
    if not part or i < 0:
        raise ValueError(f"스포일러로 가릴 말이 글에 없다: {part[:30]!r}")
    return {"entity_type": "SPOILER", "offset": _u16(text[:i]), "length": _u16(part)}


def poll_attachment(options: list[str]) -> dict:
    """투표 보기 2~4개 → {"option_a": …}. 한 개 1~25자(공식 문서). 어기면 RuntimeError(보내기 전에 막는다)."""
    opts = [str(o).strip() for o in options]
    if not 2 <= len(opts) <= len(POLL_KEYS):
        raise RuntimeError(f"Threads 투표 보기는 2~4개 — 지금 {len(opts)}개")
    bad = [o for o in opts if not 1 <= len(o) <= POLL_OPTION_MAX]
    if bad:
        raise RuntimeError(f"Threads 투표 보기는 한 개 1~{POLL_OPTION_MAX}자 — {bad}")
    if len(set(opts)) != len(opts):
        raise RuntimeError(f"Threads 투표 보기가 겹친다: {opts}")
    return dict(zip(POLL_KEYS, opts))


def _check_spoilers(text: str, spoilers: list[dict] | None) -> None:
    if not spoilers:
        return
    if len(spoilers) > SPOILER_MAX:
        raise RuntimeError(f"Threads 스포일러는 글 하나에 {SPOILER_MAX}개까지 — 지금 {len(spoilers)}개")
    n = _u16(text)
    for e in spoilers:
        if e.get("entity_type") != "SPOILER" or e.get("offset", -1) < 0 or e.get("length", 0) < 1 \
                or e["offset"] + e["length"] > n:
            raise RuntimeError(f"Threads 스포일러 범위가 글 밖이다: {e} (글 {n})")


def _extras(data: dict, topic_tag=None, spoilers=None, spoiler_media=False, reply_to_id=None) -> dict:
    """선택 항목을 컨테이너 요청에 붙인다 — 빈 값은 아예 보내지 않는다."""
    if topic_tag:
        data["topic_tag"] = topic_tag
    if spoilers:
        data["text_entities"] = json.dumps(spoilers)
    if spoiler_media:
        data["is_spoiler_media"] = "true"
    if reply_to_id:
        data["reply_to_id"] = str(reply_to_id)
    return data


def publish_text(text: str, topic_tag: str | None = None, *, poll: list[str] | None = None,
                 spoilers: list[dict] | None = None, reply_to_id: str | None = None, http=None,
                 sleep=time.sleep, user_id: str | None = None, token: str | None = None) -> str:
    """글(TEXT) 게시 → thread id. poll = 투표 보기 2~4개(글에만) · spoilers = spoiler() 목록 · reply_to_id = 답글 달 글."""
    requests = http or _requests()
    user_id, token = _creds(user_id, token)
    text = (text or "").strip()
    if not text or text_len(text) > TEXT_MAX:
        raise RuntimeError(f"Threads 글은 1~{TEXT_MAX}자 — 지금 {text_len(text)}자")
    _check_spoilers(text, spoilers)
    data = _extras({"media_type": "TEXT", "text": text, "access_token": token}, topic_tag, spoilers, False, reply_to_id)
    if poll:
        data["poll_attachment"] = json.dumps(poll_attachment(poll), ensure_ascii=False)
    what = "답글" if reply_to_id else "글"
    r = requests.post(f"{GRAPH}/{user_id}/threads", data=data, timeout=60)      # 1) 컨테이너
    _check(r, f"{what} 컨테이너 생성")
    cid = r.json()["id"]
    ok, err = _wait(requests, cid, token, sleep, tries=24)
    if not ok:
        raise RuntimeError(f"Threads {what} 처리 실패: {err}")
    p = requests.post(f"{GRAPH}/{user_id}/threads_publish",                     # 2) 게시
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    _check(p, f"{what} 게시")
    tid = p.json()["id"]
    print(f"✅ Threads {what}{'+투표' if poll else ''} 게시 완료: id={tid}")
    return tid


def publish_reply(reply_to_id: str, text: str, *, spoilers: list[dict] | None = None, http=None,
                  sleep=time.sleep, user_id: str | None = None, token: str | None = None) -> str:
    """내 글에 내가 다는 답글(글) → reply id. 주제 태그는 붙이지 않는다(본 글에 하나만)."""
    if not reply_to_id:
        raise RuntimeError("Threads 답글: reply_to_id(게시된 글 id) 없음")
    return publish_text(text, None, spoilers=spoilers, reply_to_id=reply_to_id, http=http, sleep=sleep,
                        user_id=user_id, token=token)


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
                     sleep=time.sleep, user_id: str | None = None, token: str | None = None,
                     spoilers: list[dict] | None = None, spoiler_media: bool = False) -> str:
    """카드(캐러셀) 게시 → thread id. image_urls = 공개 URL 이미지 2~20장(순서 = 넘기는 순서), text 500자 안.
    spoilers = 글 스포일러(spoiler()) · spoiler_media = 그림 전부 가리기(10/10 — 둘 다 기본은 안 씀)."""
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
    _check_spoilers(text, spoilers)
    data = _extras({"media_type": "CAROUSEL", "children": ",".join(children), "text": text, "access_token": token},
                   topic_tag, spoilers, spoiler_media)
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
                  sleep=time.sleep, user_id: str | None = None, token: str | None = None,
                  spoilers: list[dict] | None = None, spoiler_media: bool = False) -> str:
    """이미지 한 장 + 글(500자 안) → thread id. 쓰레드 '글' 형식(2026-10-06 A/B) — 카드 첫 장을 붙인다."""
    requests = http or _requests()
    user_id, token = _creds(user_id, token)
    _check_spoilers(text, spoilers)
    data = _extras({"media_type": "IMAGE", "image_url": image_url, "text": text, "access_token": token},
                   topic_tag, spoilers, spoiler_media)
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
