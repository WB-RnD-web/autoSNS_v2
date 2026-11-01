#!/usr/bin/env python3
"""Nine Tails 트렌드 편(trend_api) 회귀 테스트 — 네트워크·키 없이(가짜 클라이언트).

    python gumiho/tales/test_trend_api.py
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story as ST  # noqa: E402
import trend_api as TA  # noqa: E402

FAIL = 0
DAY = dt.date(2026, 11, 1)


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


def msg(stop, text="", fetched=(), searched=()):
    content = []
    for u in searched:
        content.append(block("web_search_tool_result", content=[SimpleNamespace(type="web_search_result", url=u, title="t")]))
    for u in fetched:
        content.append(block("web_fetch_tool_result", content=SimpleNamespace(type="web_fetch_result", url=u)))
    content.append(block("text", text=text))
    return SimpleNamespace(stop_reason=stop, content=content,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=1000,
                                                 cache_read_input_tokens=2000,
                                                 server_tool_use=SimpleNamespace(web_search_requests=len(searched),
                                                                                 web_fetch_requests=len(fetched))))


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        m = self.replies.pop(0)

        class St:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def get_final_message(s):
                return m
        return St()


SRC = ["https://www.noaa.gov/a", "https://www.nasa.gov/b"]
EV = "https://news.example.com/viral"


def good():
    e = copy.deepcopy(ST.find("9"))
    for k in ("id", "from"):
        e.pop(k)
    e["slug"] = "rescuer-sixteen-people"
    e["title"] = "The Rescuer Who Pulled 16 People From a Black Ocean"
    e["sources"] = [{"title": "NOAA", "url": SRC[0], "used": "x"}, {"title": "NASA", "url": SRC[1], "used": "y"}]
    e["trend"] = {"why_now": "rescue video viral this week", "pattern": "decisive-moment cold open",
                  "evidence": [{"title": "viral", "url": EV, "date": "2026-10-30"}]}
    return e


with tempfile.TemporaryDirectory() as td:
    radar, scout, trend = (os.path.join(td, x) for x in ("radar", "scout", "trend"))
    for d in (radar, scout, trend):
        os.makedirs(d)
    open(os.path.join(radar, "report.md"), "w", encoding="utf-8").write(
        "# r\n## 운세(왕별이)\nx\n## Horror stories (Nine Tails)\nhorror rows\n## Sleep stories (Nine Tails 수면판)\nsleep rows\n")
    json.dump({"date": DAY.isoformat(), "hot": [
        {"topic": "운세", "market": "kr", "fit": ["wb_table"], "why_now": "w", "evidence": [{"url": "https://k.example"}]},
        {"topic": "Coast Guard rescue", "market": "us", "fit": ["nt_story"], "why_now": "viral", "evidence": [{"url": EV}]}],
        "candidates": [{"line": "nt_story", "title_idea": "He Followed One Searchlight",
                        "facts": [{"fact": "16 people", "source_url": SRC[0]}]}]},
        open(os.path.join(scout, f"{DAY.isoformat()}.json"), "w", encoding="utf-8"))

    print("── 1. 입력 ──")
    ck("레이더는 Nine Tails 칸만", "horror rows" in TA.radar_nt(radar) and "운세" not in TA.radar_nt(radar))
    sb = TA.scout_brief(scout, DAY)
    ck("정찰: nt_story 에 맞는 hot 이 먼저 · nt_story 후보 포함", sb.index("Coast Guard") < sb.index("운세") and "searchlight" in sb.lower())
    um = TA.user_message(DAY, dt.date(2026, 11, 5), radar, scout, trend)
    ck("사용자 메시지: 공개일 · 허용 값 · 예시 스키마 · 이미 쓴 소재(카탈로그 제목)", "2026-11-05 21:30 KST" in um
       and "loop_end" in um and '"shots"' in um and "The Astronaut Whose Helmet Filled With Water" in um)
    ck("작가 지시문: 영어 · 베끼기·재업로드 금지 · 출처는 web_fetch 로 연 페이지 · skip", all(
        w in TA.WRITER for w in ("Never copy", "re-upload", "web_fetch", '"skip"', "mannequin")))

    print("── 2. 공개일(코드가 정한다) ──")
    s = ST.trend_slot
    ck("11/1 에 쓴 편 → 11/5(목, 첫 트렌드일)", s(DAY, set()) == dt.date(2026, 11, 5))
    ck("첫 주 자리: 11/2 → 11/7(토) · 11/3 → 11/8(일)", s(dt.date(2026, 11, 2), {dt.date(2026, 11, 5)}) == dt.date(2026, 11, 7)
       and s(dt.date(2026, 11, 3), {dt.date(2026, 11, 5), dt.date(2026, 11, 7)}) == dt.date(2026, 11, 8))
    ck("D+1~D+2 에 빈 자리가 없으면 None(쓰지 않는다)", s(dt.date(2026, 11, 4), {dt.date(2026, 11, 5), dt.date(2026, 11, 7),
                                                                         dt.date(2026, 11, 8)}) is None)
    ck("월요일에 쓴 편 → 화요일 · 화·목·토·일만", s(dt.date(2026, 11, 16), set()) == dt.date(2026, 11, 17)
       and all(s(dt.date(2026, 11, 9) + dt.timedelta(days=k), set()).weekday() in ST.TREND_DAYS for k in range(14)))
    taken, made = set(), []
    for k in range(28):
        d0 = dt.date(2026, 11, 8) + dt.timedelta(days=k)
        sl = s(d0, taken)
        if sl:
            taken.add(sl)
            made.append(sl)
    ck("4주 동안 매일 돌리면 트렌드 자리(화·목·토·일)를 빠짐없이 한 편씩 채운다(묵은 편이 쌓이지 않는다)",
       len(made) == len(set(made)) and all((made[i + 1] - made[i]).days <= 2 for i in range(len(made) - 1))
       and len(made) >= 15, made[:6])

    print("── 3. 검사 ──")
    slot = dt.date(2026, 11, 5)
    ep = TA.finalize(good(), DAY, slot)
    ck("코드가 id·kind·written·from 을 정한다(모델 값은 덮어쓴다)", ep["id"] == 20261101 and ep["kind"] == "trend"
       and ep["written"] == "2026-11-01" and ep["from"] == "2026-11-05" and ST.stem(ep) == "trend_2026-11-01_rescuer-sixteen-people")
    fetched = {TA.norm(u) for u in SRC}
    ck("좋은 편은 통과", TA.check(ep, DAY, slot, [], fetched, {TA.norm(EV)}) == [], TA.check(ep, DAY, slot, [], fetched, {TA.norm(EV)}))
    errs = TA.check(ep, DAY, slot, [], {TA.norm(SRC[0])}, {TA.norm(EV)})
    ck("web_fetch 로 열지 않은 출처는 막는다", any("web_fetch" in x for x in errs), errs)
    ck("트렌드 근거가 검색·읽기에 없으면 막는다", any("evidence" in x for x in TA.check(ep, DAY, slot, [], fetched, set())))
    ck("이미 쓴 소재(slug·제목)는 막는다", any("이미" in x for x in TA.check(ep, DAY, slot, [f"{ep['slug']} / x"], fetched, {TA.norm(EV)})))
    bad = dict(ep, trend={"why_now": "", "pattern": "", "evidence": []})
    ck("trend 칸(why_now·pattern·evidence)이 비면 막는다", any("trend" in x for x in TA.check(bad, DAY, slot, [], fetched, {TA.norm(EV)})))
    ck("skip 은 사유만 있으면 통과", TA.check({"skip": "nothing fits today"}, DAY, slot, [], set(), set()) == []
       and TA.check({"skip": " "}, DAY, slot, [], set(), set()) != [])
    ck("카탈로그 편과 id·표식·키가 겹치지 않는다", ep["id"] > 999 and ST.marker(ep).startswith("Nine Tails Tales · Trend")
       and all(ST.stem(ep) != ST.stem(c) and ST.marker(ep) != ST.marker(c) for c in ST.episodes()))

    print("── 4. 쓰기(가짜 클라이언트) ──")
    bad_text = json.dumps(dict(good(), sources=[{"title": "x", "url": "https://unread.example.org/z", "used": "z"},
                                                good()["sources"][1]]))
    fc = FakeClient([msg("pause_turn", "", searched=[EV]),
                     msg("end_turn", bad_text, fetched=[SRC[1]]),
                     msg("end_turn", json.dumps(good()), fetched=[SRC[0]])])
    info = TA.write(DAY, radar, scout, trend, client=fc)
    out = json.load(open(os.path.join(trend, f"{DAY.isoformat()}.json"), encoding="utf-8"))
    ck("pause_turn 은 이어 가고, 연 적 없는 출처는 오류를 붙여 다시 묻는다 → 2번째에 통과", info["ok"] and info["tries"] == 2
       and len(fc.calls) == 3 and "web_fetch" in fc.calls[2]["messages"][-1]["content"], info.get("history"))
    ck("결과 = 트렌드 편(공개일 11/5) · 편성에 합쳐진다", out.get("kind") == "trend" and out["from"] == "2026-11-05"
       and ST.find(ST.stem(out), trends=ST.load_trends(trend))["slug"] == "rescuer-sixteen-people")
    api = json.load(open(os.path.join(trend, f"{DAY.isoformat()}_api.json"), encoding="utf-8"))
    ck("비용 기록: 토큰·검색·읽기·달러 · 도구 설정(검색·읽기 횟수 제한) · 스트리밍 · effort", api["usd"] > 0 and api["tokens"]["web_fetch"] == 2
       and fc.calls[0]["tools"][1]["type"] == "web_fetch_20260209" and fc.calls[0]["extra_body"]["output_config"]["effort"] == TA.EFFORT)
    # 같은 폴더에서 다음 날: 11/5 는 찼다 → 11/2 는 11/7
    fc2 = FakeClient([msg("end_turn", json.dumps({"skip": "nothing current fits"}))])
    info2 = TA.write(dt.date(2026, 11, 2), radar, scout, trend, client=fc2)
    out2 = json.load(open(os.path.join(trend, "2026-11-02.json"), encoding="utf-8"))
    ck("맞는 게 없으면 skip 을 남긴다(억지로 만들지 않는다)", info2["slot"] == "2026-11-07" and out2.get("skip") == "nothing current fits")
    for k, d0 in enumerate(("2026-11-07", "2026-11-08")):
        fake = TA.finalize(dict(good(), slug=f"fill-{k}", title=f"Filler Episode Number {k}"), dt.date(2026, 11, 2 + k), dt.date.fromisoformat(d0))
        json.dump(fake, open(os.path.join(trend, f"2026-11-0{2 + k}.json"), "w", encoding="utf-8"))
    fc3 = FakeClient([])
    info3 = TA.write(dt.date(2026, 11, 4), radar, scout, trend, client=fc3)
    ck("빈 자리가 없으면 API 를 부르지 않고 skip(비용 0)", info3.get("slot") is None and not fc3.calls and info3["usd"] == 0
       and "자리 없음" in json.load(open(os.path.join(trend, "2026-11-04.json"), encoding="utf-8"))["skip"])
    fc4 = FakeClient([msg("end_turn", "not json")] * 3)
    info4 = TA.write(dt.date(2026, 11, 9), radar, scout, trend, client=fc4)
    ck("세 번 다 검사를 못 넘으면 그날은 skip(틀린 편을 편성에 넣지 않는다)", not info4["ok"] and info4["tries"] == 3
       and "검사 실패" in json.load(open(os.path.join(trend, "2026-11-09.json"), encoding="utf-8"))["skip"])
    ck("편성: 검사를 통과한 트렌드 편만(skip·실패한 날은 빠진다)",
       sorted(e["written"] for e in ST.load_trends(trend, quiet_errors=True)) == ["2026-11-01", "2026-11-02", "2026-11-03"])

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
