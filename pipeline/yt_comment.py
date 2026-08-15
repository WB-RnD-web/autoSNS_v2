#!/usr/bin/env python3
"""영상에 채널 계정으로 댓글 달기 — 쇼츠→롱폼 유도용.

왜 필요한가:
  쇼츠 시청자는 ★설명란을 열지 않는다(제목을 탭해야 펼쳐진다). 반면 댓글창은 습관적으로 연다.
  그래서 전편 링크가 실제로 클릭되는 자리는 설명란이 아니라 **댓글**이다.

⚠️ 유튜브 Data API 에는 ★댓글 고정(pin) 엔드포인트가 ★없다.
   여기서 다는 건 '첫 댓글'이지 '고정 댓글'이 아니다. 업로드 직후에 달리니 보통은 맨 위에
   보이지만, 확실히 하려면 스튜디오에서 한 번 클릭해 고정해야 한다(영상당 1초).

스코프: `youtube.force-ssl` 필요(댓글 쓰기). token_forcessl.json 이 없으면 조용히 스킵한다.
쿼터: commentThreads.insert = 50 units (하루 10,000 중).
"""
from __future__ import annotations
import sys
import time

import yt_i18n


def post(video_id: str, text: str, retries: int = 2) -> str | None:
    """댓글 1개 게시. 성공하면 comment id, 실패하면 None(★예외를 밖으로 던지지 않는다).

    업로드는 이미 끝난 뒤에 호출되므로, 여기서 실패해도 영상은 무사하다.
    그래서 절대 런을 깨뜨리지 않는다 — 경고만 남기고 넘어간다.
    """
    text = (text or "").strip()
    if not video_id or not text:
        return None
    yt = yt_i18n._service(["forcessl"], [yt_i18n.SCOPE_FORCE])
    if yt is None:
        print("   · 댓글 스킵 — force-ssl 토큰 없음(token_forcessl.json)")
        return None

    body = {"snippet": {"videoId": video_id,
                        "topLevelComment": {"snippet": {"textOriginal": text}}}}
    last = None
    for attempt in range(1, retries + 2):
        try:
            r = yt.commentThreads().insert(part="snippet", body=body).execute()
            cid = r.get("id")
            print(f"   💬 댓글 게시됨({cid}) — ★고정은 스튜디오에서 수동 클릭")
            return cid
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt <= retries:
                time.sleep(2 * attempt)
    sys.stderr.write(f"[warn] 댓글 게시 실패(무시하고 진행): {last}\n")
    return None


def longform_comment(longform_url: str, codename: str = "") -> str:
    """쇼츠에 달 전편 유도 댓글. URL 이 없으면 재생목록 안내로 폴백."""
    what = f"「{codename}」 전편" if codename else "전편(풀버전)"
    if longform_url:
        return (f"▶ {what} 풀버전 보러가기\n{longform_url}\n\n"
                "무슨 일이 있었는지는 전편에 전부 나옵니다.")
    return (f"▶ {what} 은 채널의 'SCP 아카이브' 재생목록에 있습니다.\n"
            "무슨 일이 있었는지는 전편에 전부 나옵니다.")
