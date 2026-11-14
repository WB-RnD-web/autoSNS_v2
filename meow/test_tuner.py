#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meow/tuner.py(틀 자동 조정) · meow/notes.py(정리 노트) 시험 — 네트워크·API 없이. 2026-11-14."""
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
import notes as NO  # noqa: E402
import plan_api as PA  # noqa: E402
import tuner as TU  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("✅ " if cond else "❌ ") + name + ("" if cond else f"\n     {str(detail)[:700]}"))
    if not cond:
        FAIL += 1


os.environ.pop("MEOW_AUTOTUNE", None)
os.environ.pop("MEOW_SLOTS", None)
NOW = dt.datetime(2026, 11, 20, 3, 0, tzinfo=dt.timezone.utc)
DAY = dt.date(2026, 11, 20)
EQ = dict(TU.START["weights"])


def vid(i, fmt, views, pct, age_h=72, tease=None, feed=0.6):
    pub = (NOW - dt.timedelta(hours=age_h)).isoformat().replace("+00:00", "Z")
    return {"id": f"m2611{i:02d}", "video": f"v{i}", "published": pub, "format": fmt, "caption": f"cap {i}",
            "title": f"T{i}", "views": views, "avg_pct": pct, "avg_sec": 8.0, "likes": 1, "subs": 0,
            "feed_views": int(views * feed), "feed_share": feed, "tease": tease}


def stats_of(vs, at=NOW):
    return {"at": at.isoformat(timespec="minutes"), "channel": "UC", "videos": vs}


def dir_with(stats=None, mix=None):
    d = tempfile.mkdtemp()
    if stats is not None:
        with open(os.path.join(d, AN.STATS), "w", encoding="utf-8") as f:
            json.dump(stats, f)
    if mix is not None:
        with open(os.path.join(d, TU.MIX), "w", encoding="utf-8") as f:
            json.dump(mix, f)
    return d


# ── 편마다 꼴 · 미리 보기 ──
seq = TU.sequence(EQ, 12, DAY)
ck("같은 비율·12편 → 꼴마다 3편 · 첫 편(a · 인스타)은 동점이면 변신", sorted(seq) == sorted(list(TU.FORMATS) * 3) and seq[0] == "morph", seq)
ck("비율대로 편 수(최대 나머지) — 합은 늘 편 수",
   TU.counts({"morph": 0.4, "meme": 0.2, "dance": 0.25, "game": 0.15}, 12, DAY) == {"morph": 5, "meme": 2, "dance": 3, "game": 2}
   and all(sum(TU.counts(EQ, n, DAY + dt.timedelta(days=k)).values()) == n for n in range(1, 13) for k in range(4)))
ck("첫 편 = 비율이 가장 큰 꼴", TU.sequence({"morph": 0.2, "meme": 0.4, "dance": 0.25, "game": 0.15}, 12, DAY)[0] == "meme")
drop = [next(f for f, c in TU.counts(EQ, 3, DAY + dt.timedelta(days=k)).items() if c == 0) for k in range(4)]
ck("편이 3편뿐인 날 빠지는 꼴은 날마다 돈다(늘 같은 꼴이 빠지지 않게)", sorted(drop) == sorted(TU.FORMATS), drop)
ck("같은 날·같은 비율이면 다시 돌려도 같다", TU.sequence(EQ, 12, DAY) == TU.sequence(EQ, 12, DAY)
   and TU.sequence(EQ, 12, DAY)[1:] != TU.sequence(EQ, 12, DAY + dt.timedelta(days=1))[1:])
sl = list(PA.SLOTS)
off = TU.tease_off_slots(0.5, DAY, sl)
ck("미리 보기 끄는 편 = 정확히 비율 × 편 수 · 날짜로 정해진다", len(off) == 6 and off == TU.tease_off_slots(0.5, DAY, sl)
   and len(TU.tease_off_slots(0.15, DAY, sl)) == 2 and TU.tease_off_slots(0.0, DAY, sl) == set())

# ── 안전장치 ──
w = TU.toward(EQ, {"morph": 0.55, "meme": 0.15, "dance": 0.15, "game": 0.15})
ck("하루에 가장 크게 움직이는 꼴도 10%p 까지 · 합 1 · 바닥 15% 지킴",
   abs(w["morph"] - 0.35) < 1e-6 and abs(sum(w.values()) - 1) < 1e-3 and all(v >= 0.15 - 1e-6 for v in w.values())
   and max(abs(w[f] - EQ[f]) for f in w) <= 0.1 + 1e-9, w)
t = TU.format_target({"morph": {"score": 1.0}, "meme": {"score": 0.0}, "dance": {"score": 0.0}, "game": {"score": 0.0}})
ck("목표 비율도 바닥 15%(아무리 진 꼴도) · 최대 55%", abs(t["meme"] - 0.15) < 1e-9 and abs(t["morph"] - 0.55) < 1e-9, t)

# ── 하루 한 번 고치기 ──
# 변신은 잘 되고(조회수·시청 % 높음) 게임은 안 된다 · 미리 보기 끈 편이 더 낫다
good = [vid(i, "morph", 900 + i, 95.0 + i) for i in range(1, 5)]
mid = [vid(10 + i, f, 300 + i, 60.0 + i) for i, f in enumerate(["meme", "meme", "meme", "dance", "dance", "dance"])]
bad = [vid(20 + i, "game", 5 + i, 30.0) for i in range(1, 5)]         # 피드가 안 받아 준 편(20회 안 됨)
young = [vid(30, "game", 2000, 140.0, age_h=10)]                         # 2일 안 된 편 — 안 센다
vs = good + mid + bad + young
d = dir_with(stats_of(vs))
m = TU.tune(d, DAY, now=NOW)
ck("성적이 충분하면: 잘 된 꼴(변신)은 늘고 안 된 꼴(게임)은 준다 · 10%p 안쪽 · 바닥 15%",
   m["weights"]["morph"] > 0.25 and m["weights"]["game"] < 0.25 and m["weights"]["game"] >= 0.15 - 1e-6
   and max(abs(m["weights"][f] - 0.25) for f in TU.FORMATS) <= 0.1 + 1e-6 and m["basis"]["judged"] == 14, m)
ck("이유를 남긴다(꼴 점수 · 편 수) · 기록(log)에 쌓인다", "꼴 점수" in m["why"][0] and len(m["log"]) == 1 and m["date"] == "2026-11-20")
m2 = TU.tune(d, DAY, now=NOW)
ck("같은 날 다시 돌면 고치지 않는다(예비 실행이 꼴을 바꾸지 않게)", m2.get("kept") and m2["weights"] == m["weights"])
ws = [m["weights"]]
for k in range(1, 15):
    ws.append(TU.tune(d, DAY + dt.timedelta(days=k), now=NOW)["weights"])
ck("같은 성적이 2주 이어져도 진 꼴은 15% 밑으로 안 가고 이긴 꼴도 55% 를 안 넘는다 · 날마다 10%p 안쪽",
   all(min(x.values()) >= 0.15 - 1e-3 and max(x.values()) <= 0.55 + 1e-3 for x in ws)
   and all(max(abs(a[f] - b[f]) for f in TU.FORMATS) <= 0.1 + 1e-6 for a, b in zip(ws, ws[1:])), ws[-1])

d = dir_with(stats_of(good + mid[:2]))
ck("2일 넘은 편이 8편 안 되면 그대로", TU.tune(d, DAY, now=NOW)["weights"] == EQ)
d = dir_with(stats_of(vs, at=NOW - dt.timedelta(hours=40)))
ck("성적이 36시간 넘게 묵었으면(분석 담당 실패) 그대로", TU.tune(d, DAY, now=NOW)["weights"] == EQ)
ck("성적이 없으면 그대로(첫날) · 미리 보기는 반반으로 시작", (lambda r: r["weights"] == EQ and r["tease_off"] == 0.5)(TU.tune(dir_with(), DAY, now=NOW)))

arm = [vid(40 + i, "meme", 300, 60.0 + i, tease=True) for i in range(6)] + [vid(50 + i, "meme", 300, 90.0 + i, tease=False) for i in range(6)]
d = dir_with(stats_of(arm))
r = TU.tune(d, DAY, now=NOW)
ck("미리 보기 A/B: 끈 쪽이 낫다(켬·끔 각 6편 넘게 · 점수 차 0.05 넘음) → 끄는 편 50% → 60%(하루 10%p)",
   abs(r["tease_off"] - 0.6) < 1e-6 and any("끈 쪽이 낫다" in x for x in r["why"]), r["why"])
d = dir_with(stats_of(arm[:5] + arm[6:] + good))
ck("A/B 편 수가 모자라면 그대로 · A/B 전 편(tease 없음)은 비교에서 뺀다",
   TU.tune(d, DAY, now=NOW)["tease_off"] == 0.5 and TU.tease_arms(TU.scored(stats_of(good), NOW))["on"]["n"] == 0)

# ── 기획(plan_api)이 mix.json 을 따른다 ──
mix = {"date": "2026-11-20", "weights": {"morph": 0.15, "meme": 0.55, "dance": 0.15, "game": 0.15}, "tease_off": 0.5}
d = dir_with(mix=mix)
fm = [PA.fmt_of(DAY, s, d) for s in PA.SLOTS]
ck("mix.json 이 있으면 꼴은 그 비율대로(밈 55% → 12편 중 6편 · 나머지 2편씩 · 첫 편 밈) · 없으면 예전(a 변신)",
   fm == TU.sequence(mix["weights"], 12, DAY) and fm.count("meme") == 6 and all(fm.count(f) == 2 for f in ("morph", "dance", "game")) and fm[0] == "meme"
   and PA.fmt_of(DAY, "a", tempfile.mkdtemp()) == "morph" and PA.fmt_of(DAY, "a") == "morph", fm)
fin = [PA.finalize({"slug": "x", "tease": "모델이 넣음"}, DAY, s, d) for s in PA.SLOTS]
ck("미리 보기 켬/끔은 코드가 concept 에 적는다(정확히 반) · 꼴도 같은 비율 · 모델이 넣은 값은 덮는다",
   sum(c["tease"] is False for c in fin) == 6 and all(isinstance(c["tease"], bool) for c in fin)
   and [c["format"] for c in fin] == fm and {c["tease"] for c in fin} == {True, False}, [c.get("tease") for c in fin])
ck("자동 조정이 꺼졌거나 mix.json 이 없으면 tease 를 안 적는다(렌더 기본 = 켬)",
   "tease" not in PA.finalize({"slug": "x", "tease": False}, DAY, "a", tempfile.mkdtemp()))
os.environ["MEOW_SLOTS"] = "a b c"
f3 = [PA.fmt_of(DAY, s, d) for s in "abc"]
ck("편 수를 줄이면(MEOW_SLOTS='a b c') 그 편 수로 나눈다 · 오늘 안 쓰는 편은 예전 방식",
   f3 == TU.sequence(mix["weights"], 3, DAY) and TU.plan_for(d, DAY, "d", PA.SLOTS) is None, f3)
os.environ.pop("MEOW_SLOTS")
os.environ["MEOW_AUTOTUNE"] = "0"
ck("MEOW_AUTOTUNE=0 이면 mix.json 을 안 본다(예전 방식)", [PA.fmt_of(DAY, s, d) for s in PA.SLOTS] == [PA.fmt_of(DAY, s) for s in PA.SLOTS])
os.environ.pop("MEOW_AUTOTUNE")
bad_d = dir_with(mix={"date": "x", "weights": {"morph": "많이"}})
ck("mix.json 이 망가져도 기획은 멈추지 않는다(예전 방식)", PA.fmt_of(DAY, "a", bad_d) == "morph"
   and TU.plan_for(dir_with(mix={"weights": {f: 0 for f in TU.FORMATS}}), DAY, "a", PA.SLOTS) is None)
um = PA.user_message(DAY, d, "a")
ck("기획 담당에게 가는 글의 꼴도 mix.json 대로", f"format: {fm[0]}" in um.split("\n")[0], um.split("\n")[0])

# ── 분석 담당: 기획의 tease 를 성적에 붙인다 · 피드가 안 받아 준 편도 보인다 ──
pd = tempfile.mkdtemp()
with open(os.path.join(pd, "2026-11-17.json"), "w", encoding="utf-8") as f:
    json.dump({"date": "2026-11-17", "concepts": [{"id": "m261117", "format": "morph", "tease": False}, ]}, f)
with open(os.path.join(pd, "2026-11-17-b.json"), "w", encoding="utf-8") as f:
    json.dump({"date": "2026-11-17", "concepts": [{"id": "m261117b", "format": "meme"}]}, f)
pl = AN.plans(pd)
ck("analyst.plans: 기획의 tease(A/B) 를 가져온다 · 없으면 None", pl["m261117"]["tease"] is False and pl["m261117b"]["tease"] is None)
L = "\n".join(AN.lessons(stats_of(vs), NOW))
ck("기획용 줄: 2일 넘고 20회 안 된 편은 '피드가 안 받아 줬다'(✗) · 2일 안 된 편은 '아직 이르다'",
   "the feed skipped it" in L and "too early" in L and L.count("★ held") >= 1, L[-900:])


class _YTp:
    """업로드 목록이 두 쪽(50 + 30) — 둘 다 읽는다 · videos.list 는 50개씩."""
    def __init__(self):
        self.vcalls = []

    def channels(self):
        return types.SimpleNamespace(list=lambda **k: _Ex({"items": [{"id": "UCx", "contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]}))

    def playlistItems(self):
        def lst(**k):
            lo = 50 if k.get("pageToken") else 0
            n = 30 if lo else 50
            items = [{"snippet": {"description": f"Meow Remix · 2026-11-{10 + (i % 9):02d} m2611{10 + (i % 9):02d}{'abcdefghijkl'[i % 12]}"},
                      "contentDetails": {"videoId": f"p{i}"}} for i in range(lo, lo + n)]
            return _Ex({"items": items, **({} if lo else {"nextPageToken": "T2"})})
        return types.SimpleNamespace(list=lst)

    def videos(self):
        def lst(**k):
            ids = k["id"].split(",")
            self.vcalls.append(len(ids))
            return _Ex({"items": [{"id": v, "status": {"privacyStatus": "public"}, "snippet": {"publishedAt": "2026-11-15T01:00:00Z"}} for v in ids]})
        return types.SimpleNamespace(list=lst)


class _Ex:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


yp = _YTp()
ups = AN.uploads(yp, "UCx")
ck("업로드 목록 두 쪽(최대 100편 ≈ 하루 12편 × 8일)까지 읽는다 · videos.list 는 50개씩", len(ups) == 80
   and max(yp.vcalls) <= 50 and sum(yp.vcalls) == 80, (len(ups), yp.vcalls))

# ── 정리 노트 ──


class _Msg:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.stop_reason = "end_turn"
        self.usage = types.SimpleNamespace(input_tokens=6000, output_tokens=900, cache_read_input_tokens=0)


class _Stream:
    def __init__(self, m):
        self.m = m

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.m


class _Client:
    def __init__(self, text=None, boom=False):
        self.text, self.boom, self.calls, self.messages = text, boom, [], self

    def stream(self, **kw):
        self.calls.append(kw)
        if self.boom:
            raise RuntimeError("크레딧 없음")
        return _Stream(_Msg(self.text))


d = dir_with(stats_of(vs))
TU.tune(d, DAY, now=NOW)
fc = _Client("## 해석(AI · 추측 포함)\n- 변신이 가장 오래 붙잡는다\n## 유지 · 고칠 후보\n- 게임 줄이기(조회수 6~9)\n## 다음에 볼 것\n- 미리 보기 A/B")
r = NO.write(d, DAY, client=fc, now=NOW)
txt = open(r["path"], encoding="utf-8").read()
ck("노트 = 근거(코드가 센 숫자: 꼴별 표 · 피드가 안 받아 준 편 · 오늘 틀과 이유) + 해석(API)",
   "## 근거(숫자 · 코드가 셈)" in txt and "| morph | 4 |" in txt and "피드가 안 받아 준 편(20회 안 됨) 4편" in txt
   and "오늘 틀(자동 조정)" in txt and "꼴 점수" in txt and "## 해석(AI · 추측 포함)" in txt and "변신이 가장 오래" in txt
   and r["api"]["usd"] > 0 and r["old"] == 14, txt)
um = fc.calls[0]["messages"][0]["content"]
ck("해석 담당에게: 근거 + 편별 숫자 + 지난 노트 · effort 설정 · 웹 검색 없음",
   "# 근거(오늘)" in um and '"caption": "cap 1"' in um and "(없음 — 첫 노트)" in um
   and fc.calls[0]["extra_body"]["output_config"]["effort"] == NO.EFFORT and "tools" not in fc.calls[0], um[:300])
ck("같은 날 다시 돌면 건너뛴다(API 한 번)", NO.write(d, DAY, client=fc, now=NOW).get("kept") and len(fc.calls) == 1)
r2 = NO.write(d, DAY + dt.timedelta(days=1), client=fc, now=NOW)
ck("다음 날 노트는 지난 노트를 읽는다(바꾼 것 → 결과를 잇게)", "고양이 쇼츠 정리 노트 — 2026-11-20" in fc.calls[1]["messages"][0]["content"])
d0 = dir_with(stats_of(young))
f0 = _Client("x")
r0 = NO.write(d0, DAY, client=f0, now=NOW)
ck("2일 넘은 편이 없으면 API 를 안 부른다(돈 안 씀) · 근거는 남긴다", not f0.calls and r0["api"] is None
   and "해석은 건너뜀" in open(r0["path"], encoding="utf-8").read())
db = dir_with(stats_of(vs))
rb = NO.write(db, DAY, client=_Client(boom=True), now=NOW)
tb = open(rb["path"], encoding="utf-8").read()
ck("API 가 실패해도 근거는 남고 '해석 실패'만 적는다(기획은 그대로)", "해석 실패" in tb and "| morph | 4 |" in tb and "error" in rb)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
