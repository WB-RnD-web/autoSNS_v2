#!/usr/bin/env python3
"""트렌드 레이더 회귀 테스트 — 네트워크 없이(가짜 유튜브).

    python tools/test_trend_radar.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trend_radar as TR  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 20, 0, tzinfo=UTC)


class Req:
    def __init__(self, f):
        self.f = f

    def execute(self):
        return self.f()


class FakeYT:
    """채널 A(평소 1,000회 · '말년' 영상만 5,000회) · 채널 B(평소 100회) · 우리 채널 W."""

    def __init__(self, videos: dict):
        self.v = videos          # id → dict(ch, title, pub, dur, views)
        self.calls = {"pl": 0, "vid": 0}

    def playlistItems(self):
        yt = self

        class P:
            def list(self, part, playlistId, maxResults, pageToken=None):
                yt.calls["pl"] += 1
                ch = "UC" + playlistId[2:]
                ids = sorted((k for k, x in yt.v.items() if x["ch"] == ch), key=lambda k: yt.v[k]["pub"], reverse=True)
                return Req(lambda: {"items": [{"contentDetails": {"videoId": i}} for i in ids[:maxResults]]})
        return P()

    def videos(self):
        yt = self

        class V:
            def list(self, part, id):
                yt.calls["vid"] += 1
                ids = id.split(",")
                return Req(lambda: {"items": [
                    {"id": i, "snippet": {"title": yt.v[i]["title"], "publishedAt": yt.v[i]["pub"], "channelId": yt.v[i]["ch"]},
                     "statistics": {"viewCount": str(yt.v[i]["views"])},
                     "contentDetails": {"duration": f"PT{yt.v[i]['dur']}S"}} for i in ids if i in yt.v]})
        return V()

    def channels(self):
        yt = self

        class C:
            def list(self, part, id):
                yt.calls["ch"] = yt.calls.get("ch", 0) + 1
                ids = id.split(",")
                return Req(lambda: {"items": [
                    {"id": c, "statistics": {"viewCount": str(sum(x["views"] for x in yt.v.values() if x["ch"] == c)),
                                             "subscriberCount": "42", "videoCount": str(sum(x["ch"] == c for x in yt.v.values()))}}
                    for c in ids]})
        return C()


def mk(ch, n, views, title="오늘의 띠별 운세", start_day=4, dur=40, pre=""):
    return {f"{ch}_{pre}{k}": {"ch": ch, "title": title, "views": views, "dur": dur,
                          "pub": (NOW - dt.timedelta(days=start_day + k)).strftime("%Y-%m-%dT%H:%M:%SZ")} for k in range(n)}


cfg = {
    "fortune_kr": {"label": "운세", "channels": {"UCaaaa": "A", "UCbbbb": "B"},
                   "tags": {"띠별": "띠", "말년·노후": "말년|노후"}},
    "own_wb": {"label": "우리", "own": True, "channels": {"UCwwww": "W"}, "tags": {"정치": "국회"}},
}
for c in cfg.values():
    c["_re"] = {t: __import__("re").compile(p) for t, p in c["tags"].items()}

vids = {}
vids.update(mk("UCaaaa", 8, 1000))
vids.update({f"UCaaaa_hit{k}": dict(v, title="말년에 돈복 터지는 띠", views=5000) for k, v in
             enumerate(mk("UCaaaa", 3, 0, start_day=5).values())})
vids.update(mk("UCbbbb", 6, 100))
vids.update(mk("UCwwww", 5, 200, title="국회 소식 #shorts"))
vids.update(mk("UCaaaa", 1, 50, title="갓 올라온 띠 영상", start_day=1, pre="new"))
vids.update({"old": dict(mk("UCbbbb", 1, 9, start_day=100)["UCbbbb_0"])})
vids["long1"] = dict(mk("UCaaaa", 1, 30000, title="띠별 1시간 몰아보기", dur=3600)["UCaaaa_0"])

print("── 모으기 ──")
yt = FakeYT(vids)
reg = {}
st = TR.collect(reg, cfg, yt, NOW)
ck("새 영상을 레지스트리에 넣는다", st["new"] >= len(vids) - 1 and "UCaaaa_0" in reg, str(st))
ck("75일 지난 영상은 정리", "old" not in reg)
ck("스냅숏 키는 시각(UTC 시)", list(reg["UCaaaa_0"]["views"]) == ["2026-10-20T00"])
ck("쇼츠·롱폼 구분(3분)", TR.fmt(reg["UCaaaa_0"]) == "short" and TR.fmt(reg["long1"]) == "long")
ck("quota 추정 = 채널 수 + 50개 묶음", st["units_est"] == 3 + (st["new"] + 49) // 50, str(st["units_est"]))

print("── 채널 전체 스냅숏(channels.json — 채널 맥박이 읽는다) ──")
chans = {}
cs = TR.collect_channels(chans, cfg, yt, NOW)
ck("참고·우리 채널 전부 한 번에(50개 묶음 1 unit)", cs["channels"] == 3 and yt.calls.get("ch") == 1, str(cs))
ck("스냅숏 = 채널 전체 조회수·구독자·영상 수", chans["UCwwww"]["snaps"]["2026-10-20T00"] == {"views": 1000, "subs": 42, "videos": 5}
   and chans["UCwwww"]["own"] is True and chans["UCwwww"]["niche"] == "own_wb", str(chans["UCwwww"]))
chans["UCwwww"]["snaps"]["2025-01-01T00"] = {"views": 1, "subs": 1, "videos": 1}
TR.collect_channels(chans, cfg, yt, NOW + dt.timedelta(days=1))
ck("400일 지난 채널 스냅숏은 정리 · 하루 하나씩 쌓인다", sorted(chans["UCwwww"]["snaps"]) == ["2026-10-20T00", "2026-10-21T00"])

print("── 7일째 조회수 ──")
rec = {"pub": "2026-10-01T00:00:00Z", "views": {"2026-10-06T00": 600, "2026-10-09T00": 900}}
ck("5일 600 · 8일 900 → 7일 800(보간)", abs(TR.views_at(rec, 7) - 800) < 1e-6, str(TR.views_at(rec, 7)))
ck("7일을 앞뒤로 못 잡으면 None", TR.views_at({"pub": rec["pub"], "views": {"2026-10-09T00": 900}}, 7) is None)

print("── 배수·판정 ──")
rt = TR.ratios(reg, NOW)
ck("평소 영상 배수 ≈ 1", abs(rt["UCaaaa_0"]["ratio"] - 1.0) < 0.01, str(rt["UCaaaa_0"]))
ck("대박 영상 = 평소의 5배", abs(rt["UCaaaa_hit0"]["ratio"] - 5.0) < 0.01, str(rt["UCaaaa_hit0"]))
ck("작은 채널도 자기 평소 대비(100회 = 1배)", abs(rt["UCbbbb_0"]["ratio"] - 1.0) < 0.01)
zero = {f"z{k}": {"ch": "UCzz", "niche": "own_tales", "title": "t", "dur": 30, "likes": 0, "comments": 0,
                  "pub": (NOW - dt.timedelta(days=4 + k)).strftime("%Y-%m-%dT%H:%M:%SZ"), "views": {"2026-10-20T00": 0 if k else 7}}
        for k in range(4)}
ck("평소(중앙값)가 0 인 갓 생긴 채널도 빼지 않는다(10/5 NT n=0 버그)", len(TR.ratios(zero, NOW)) == 4, str(TR.ratios(zero, NOW)))
ck("3일 안 된 영상은 재지 않는다", "UCaaaa_0" in rt and not any(k for k in rt if reg[k]["title"].startswith("갓")))
res = TR.analyze(reg, cfg, NOW)
f = res["niches"]["fortune_kr"]["tags"]
ck("'말년' 주제 = 강세(배수 5)", f["말년·노후"]["label"] == "강세" and f["말년·노후"]["med"] == 5.0, str(f["말년·노후"]))
ck("대박 비율", f["말년·노후"]["hit"] == 1.0)
ck("형식 비교 줄(쇼츠/롱폼)", "형식: 쇼츠" in f)
ck("대박 영상 목록 맨 위 = 말년 영상", res["niches"]["fortune_kr"]["top"][0]["title"].startswith("말년"))
prev = json.loads(json.dumps(res))
prev["niches"]["fortune_kr"]["tags"]["말년·노후"]["med"] = 2.0
ck("지난주 2.0 → 이번 5.0 = 떡상", TR.label(f["말년·노후"], prev["niches"]["fortune_kr"]["tags"]["말년·노후"]) == "떡상")
ck("반응 30%↓ = 식는 중", TR.label({"n": 5, "med": 0.7}, {"n": 5, "med": 1.0}) == "식는 중")
ck("공급 1.5배↑·반응↓ = 끝물", TR.label({"n": 15, "med": 0.85}, {"n": 8, "med": 1.0}) == "끝물")
ck("표본 3개 미만 = 판정 안 함", TR.label({"n": 2, "med": 9.0}, None) == "표본 부족")

print("── 저장·보고서 ──")
with tempfile.TemporaryDirectory() as td:
    TR.save_json(os.path.join(td, "registry.json"), reg)
    r1 = TR.run_analyze(td, cfg, NOW)
    ck("첫 실행에 주간 기록을 남긴다", os.path.exists(os.path.join(td, "weekly", "2026-10-20.json")))
    TR.run_analyze(td, cfg, NOW + dt.timedelta(days=2))
    ck("7일 안에는 주간 기록을 또 만들지 않는다", not os.path.exists(os.path.join(td, "weekly", "2026-10-22.json")))
    r3 = TR.run_analyze(td, cfg, NOW + dt.timedelta(days=7))
    ck("일주일 뒤엔 지난주와 비교한다(prev_med)", r3["niches"]["own_wb"]["tags"].get("정치", {}).get("prev_med") is not None
       or any(s.get("prev_med") for s in r3["niches"]["fortune_kr"]["tags"].values()))
    md = open(os.path.join(td, "report.md"), encoding="utf-8").read()
    ck("보고서: 배수 설명·표·대박 링크", "배수 =" in md and "| 판정 |" in md and "https://youtu.be/" in md)
    ck("보고서: '지금 조회수 기준(추정)' 표시", "추정" in md)

print("── 실제 설정 파일 ──")
real = TR.load_niches()
ck("분야마다 채널·주제", all(c["channels"] and c["tags"] for c in real.values()))
ck("채널 id 형식(UC + 22자)", all(len(k) == 24 and k.startswith("UC") for c in real.values() for k in c["channels"]))
ck("우리 채널(own) 둘", sum(bool(c.get("own")) for c in real.values()) == 2)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
