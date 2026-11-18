#!/usr/bin/env python3
"""왕별이 표 예약 공개(2026-11-18) 회귀 테스트 — publish_at → 비공개 + publishAt.

    python pipeline/test_publish_ahead.py

왜: GitHub 예약이 6~10시간씩 늦게 돌아 표가 새벽(01~04시)에 올라갔다. 트리거(tools/wb_trigger.py)가 12시간 먼저
스토리보드를 만들고 publish_at 을 적으면, run_pipeline 이 그 시각까지 비공개로 두고 그때 공개되게 올린다.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import run_pipeline as R   # noqa: E402
import upload_youtube as U  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 18, 9, 10, tzinfo=UTC)          # 18:10 KST

print("── publish_at_for")
ck("내일 06:00 KST → 예약(UTC RFC3339 · 전날 21:00Z)",
   R.publish_at_for({"publish_at": "2026-11-19T06:00+09:00"}, NOW) == "2026-11-18T21:00:00Z")
ck("이미 지난 시각 → None(바로 공개 — 예전과 같다)", R.publish_at_for({"publish_at": "2026-11-18T17:40+09:00"}, NOW) is None)
ck("15분 안쪽 → None(유튜브가 너무 가까운 예약을 거절할 수 있다)",
   R.publish_at_for({"publish_at": "2026-11-18T18:20+09:00"}, NOW) is None
   and R.publish_at_for({"publish_at": "2026-11-18T18:40+09:00"}, NOW) == "2026-11-18T09:40:00Z")
ck("없음·빈 값·못 읽는 값 → None", R.publish_at_for({}, NOW) is None and R.publish_at_for({"publish_at": ""}, NOW) is None
   and R.publish_at_for({"publish_at": "내일 아침"}, NOW) is None)
ck("시간대 없는 값은 KST 로 읽는다", R.publish_at_for({"publish_at": "2026-11-19T06:00"}, NOW) == "2026-11-18T21:00:00Z")

print("── 업로드 몸통(videos.insert)")


class _Req:
    def next_chunk(self):
        return None, {"id": "vid123"}


class _Videos:
    def __init__(self, box):
        self.box = box

    def insert(self, part, body, media_body):
        self.box["body"] = body
        return _Req()


class _YT:
    def __init__(self, box):
        self.box = box

    def videos(self):
        return _Videos(self.box)


box: dict = {}
U.get_service = lambda: _YT(box)
sys.modules["yt_i18n"] = types.SimpleNamespace(localize=lambda *a, **k: None)
with tempfile.TemporaryDirectory() as td:
    mp4 = os.path.join(td, "a.mp4")
    open(mp4, "wb").write(b"\0" * 16)
    vid = U.upload(mp4, "제목", "설명", "public", category="24", publish_at="2026-11-18T21:00:00Z")
    st = box["body"]["status"]
    ck("예약이면 비공개 + publishAt", vid == "vid123" and st["privacyStatus"] == "private"
       and st["publishAt"] == "2026-11-18T21:00:00Z", st)
    box.clear()
    U.upload(mp4, "제목", "설명", "public", category="24")
    st = box["body"]["status"]
    ck("예약이 없으면 예전 그대로(공개 · publishAt 없음)", st["privacyStatus"] == "public" and "publishAt" not in st, st)

print("── run_pipeline 연결")
src = open(R.__file__, encoding="utf-8").read()
ck("업로드에 publish_at 을 넘긴다", 'publish_at=meta.get("publish_at")' in src)
ck("손으로 돌린 비공개 시험(force_private)은 예약하지 않는다 · 공개 편만 예약으로 바꾼다",
   "at = None if args.force_private else publish_at_for(sb)" in src and 'if at and meta["privacy"] == "public":' in src)
ck("예약 편도 재생목록에 넣는다(공개되면 보인다)", 'meta["privacy"] == "public" or meta.get("publish_at")' in src)
ck("ledger 에 예약 시각을 남긴다", 'extra["publish_at"] = meta["publish_at"]' in src)

print("\n" + ("✅ 전부 통과" if not FAIL else f"❌ 실패 {FAIL}개"))
sys.exit(1 if FAIL else 0)
