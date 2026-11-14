#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meow/analyst.py 시험 — 네트워크 없이(가짜 YouTube·Analytics). 2026-11-14."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyst as AN  # noqa: E402
import plan_api as PA  # noqa: E402
import post as P  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("✅ " if cond else "❌ ") + name + ("" if cond else f"\n     {str(detail)[:600]}"))
    if not cond:
        FAIL += 1


class _Ex:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


NOW = dt.datetime(2026, 11, 20, 3, 0, tzinfo=dt.timezone.utc)
VIDS = {  # 영상 id → (편 id, 공개 시각, 공개 상태)
    "v1": ("m261115", "2026-11-15T01:00:00Z", "public"), "v2": ("m261115b", "2026-11-15T03:00:00Z", "public"),
    "v3": ("m261116", "2026-11-16T01:00:00Z", "public"), "v4": ("m261117c", "2026-11-17T05:00:00Z", "public"),
    "v5": ("m261119", "2026-11-19T20:00:00Z", "public"), "v6": ("m261120d", "2026-11-21T01:00:00Z", "private"),
}


class _YT:
    def __init__(self, cid=None):
        self.cid = cid or P.CHANNEL_ID

    def channels(self):
        return types.SimpleNamespace(list=lambda **k: _Ex({"items": [{"id": self.cid, "contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]}))

    def playlistItems(self):
        items = [{"snippet": {"description": f"... Meow Remix · {p[:10]} {c}"}, "contentDetails": {"videoId": v}}
                 for v, (c, p, _) in VIDS.items()]
        items.append({"snippet": {"description": "no mark"}, "contentDetails": {"videoId": "vX"}})
        return types.SimpleNamespace(list=lambda **k: _Ex({"items": items}))

    def videos(self):
        def lst(**k):
            ids = k["id"].split(",")
            return _Ex({"items": [{"id": v, "status": {"privacyStatus": VIDS[v][2]}, "snippet": {"publishedAt": VIDS[v][1]}}
                                  for v in ids if v in VIDS]})
        return types.SimpleNamespace(list=lst)


M = {"v1": (400, 92.0, 8.6, 9, 1, 300), "v2": (60, 41.0, 3.9, 0, 0, 10), "v3": (250, 110.5, 10.4, 6, 2, 210),
     "v4": (30, 35.0, 3.3, 0, 0, 3), "v5": (5, 80.0, 7.0, 0, 0, 0)}


class _YA:
    def __init__(self):
        self.calls = []

    def reports(self):
        return self

    def query(self, **k):
        self.calls.append(k)
        if k["dimensions"] == "video":
            ids = k["filters"].split("==")[1].split(",")
            return _Ex({"rows": [[v, *M[v][:5]] for v in ids if v in M]})
        v = k["filters"].split("==")[1]
        return _Ex({"rows": [["SHORTS", M[v][5]], ["YT_SEARCH", M[v][0] - M[v][5]]]})


d = tempfile.mkdtemp()
for name, cid, fmt, cap in (("2026-11-15", "m261115", "morph", "Wait… this bun has ears"),
                            ("2026-11-15-b", "m261115b", "meme", "Me at 5:59 PM vs 6:00 PM"),
                            ("2026-11-16", "m261116", "morph", "This tangerine purrs")):
    with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"date": name[:10], "concepts": [{"id": cid, "format": fmt, "caption": cap, "title": f"T {cid}", "slug": cid}]}, f)

ya = _YA()
st = AN.pull(d, "unused", now=NOW, yt=_YT(), ya=ya)
by = {v["video"]: v for v in st["videos"]}
ck("표식으로 편과 맞춘다 · 공개 영상만(예약·비공개 X) · 표식 없는 영상 X · 새것부터",
   [v["video"] for v in st["videos"]] == ["v5", "v4", "v3", "v2", "v1"] and "v6" not in by and "vX" not in by, list(by))
ck("숫자: 평균 시청 % · 쇼츠 피드 비중(SHORTS / 전체) · 기획의 꼴·자막이 붙는다",
   by["v1"]["avg_pct"] == 92.0 and by["v1"]["feed_share"] == 0.75 and by["v1"]["format"] == "morph"
   and by["v2"]["caption"] == "Me at 5:59 PM vs 6:00 PM" and by["v4"].get("format") is None, by["v1"])
ck("stats.json 으로 저장 · 다시 읽힌다", AN.load(d)["channel"] == P.CHANNEL_ID and len(AN.load(d)["videos"]) == 5)
ck("통계는 채널 내 것만(ids=channel==MINE) · 영상 묶음은 한 번 · 트래픽은 영상마다",
   all(c["ids"] == "channel==MINE" for c in ya.calls) and sum(c["dimensions"] == "video" for c in ya.calls) == 1
   and sum(c["dimensions"] == "insightTrafficSourceType" for c in ya.calls) == 5)
try:
    AN.pull(d, "unused", now=NOW, yt=_YT("UCoPIsIO_ximUdyh-n_-rIfQ"), ya=_YA())
    wrong = False
except SystemExit:
    wrong = True
ck("옛 채널 토큰이면 멈춘다(엉뚱한 채널 성적을 배우지 않게)", wrong)

L = AN.lessons(st, NOW)
txt = "\n".join(L)
ck("기획용 줄: 2일 넘고 20회 넘은 편만 순위(위·아래 1/3 — 겹치지 않게) — ★ 가장 오래 본 편 · ✗ 가장 빨리 넘긴 편 · 어린 편은 '아직 이르다'",
   "★ held viewers" in [x for x in L if "This tangerine purrs" in x][0] and "✗ lost viewers" in [x for x in L if x.startswith("- 2026-11-17")][0]
   and "too early" in [x for x in L if x.startswith("- 2026-11-19")][0] and "feed 75%" in txt
   and txt.count("★ held") == 1 and txt.count("✗ lost") == 1, txt)
ck("성적이 없으면 아무 줄도 안 넣는다", AN.lessons(None) == [] and AN.lessons({"videos": []}) == [])
few = {"videos": st["videos"][:2]}
ck("순위 낼 편이 모자라면 '서로 다른 훅으로 계속 시험' 한 줄", "Too few Shorts" in "\n".join(AN.lessons(few, NOW)))

um = PA.user_message(dt.date(2026, 11, 20), d, "b")
ck("기획 담당(plan_api)에게 가는 글 끝에 성적이 들어간다", "How our recent Shorts did on YouTube" in um and "avg viewed 110.5%" in um, um[-600:])
os.remove(os.path.join(d, AN.STATS))
ck("stats.json 이 없으면 기획 글은 예전 그대로", "How our recent Shorts did" not in PA.user_message(dt.date(2026, 11, 20), d, "b"))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
