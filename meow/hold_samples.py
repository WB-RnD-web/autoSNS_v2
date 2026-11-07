"""견본 10편 중 아직 공개 안 된 것의 예약 공개를 취소한다(비공개로 남김). 이미 공개된 편은 건드리지 않는다.

    python meow/hold_samples.py      # YT_TOKEN_NOVEL = 구미호(Meow Remix) 채널 토큰 경로

videos.update(part=status) 는 빠진 필드를 지우므로 지금 status 의 바꿀 수 있는 값을 그대로 옮기고 publishAt 만 뺀다.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import upload_youtube_novel as U  # noqa: E402

IDS = ["sSWy8Mza044", "WIfTqYlQHNU", "cl69LZVXb2I", "yhT5zfw8aZU", "p2FLRp7Hg5M",
       "lo4ls5DEb9Q", "8nO83FKP6Pc", "3beSXEeWTwo", "Y2PC_5M7MlI", "O_zq5Z8sbcA"]
MUTABLE = ("privacyStatus", "embeddable", "license", "publicStatsViewable",
           "selfDeclaredMadeForKids", "containsSyntheticMedia")


def main() -> int:
    yt = U.get_service()
    items = yt.videos().list(part="status,snippet", id=",".join(IDS)).execute().get("items", [])
    now = dt.datetime.now(dt.timezone.utc)
    held = fails = 0
    for it in items:
        st, vid = it["status"], it["id"]
        at = st.get("publishAt")
        if st.get("privacyStatus") != "private" or not at:
            print(f"그대로 {vid} · {st.get('privacyStatus')} · {it['snippet']['title'][:40]}")
            continue
        if dt.datetime.fromisoformat(at.replace("Z", "+00:00")) <= now:
            print(f"그대로 {vid} · 공개 시각 지남({at})")
            continue
        body = {k: st[k] for k in MUTABLE if k in st}
        body["privacyStatus"] = "private"
        try:
            yt.videos().update(part="status", body={"id": vid, "status": body}).execute()
            held += 1
            print(f"✅ 예약 취소 {vid} (원래 {at}) · {it['snippet']['title'][:40]}")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"::error::{vid} 예약 취소 실패: {str(e)[:300]}")
    print(f"예약 취소 {held}편 · 실패 {fails} · 찾은 영상 {len(items)}/{len(IDS)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
