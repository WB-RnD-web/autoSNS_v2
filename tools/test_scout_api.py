#!/usr/bin/env python3
"""웹 정찰(scout_api) 회귀 테스트 — 네트워크·키 없이(가짜 클라이언트).

    python tools/test_scout_api.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scout_api as S  # noqa: E402

FAIL = 0
DAY = dt.date(2026, 11, 1)


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def msg(stop, text="", searches=0):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)],
                           usage=SimpleNamespace(input_tokens=100, output_tokens=50, cache_creation_input_tokens=0,
                                                 cache_read_input_tokens=0,
                                                 server_tool_use=SimpleNamespace(web_search_requests=searches, web_fetch_requests=1)))


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


def good(**over):
    s = {"date": DAY.isoformat(), "note": "총평",
         "hot": [{"topic": f"주제 {i}", "market": "kr", "where": "기사", "why_now": "이번 주 화제", "fit": ["insta_danger"],
                  "idea": "카드로", "evidence": [{"title": "기사", "url": f"https://news.example.com/{i}", "date": "2026-10-30"}]}
                 for i in range(3)],
         "candidates": [{"line": "insta_danger", "title_idea": "해마가 위험한 진짜 이유", "careful": "",
                         "facts": [{"fact": "수컷이 새끼를 낳는다", "source_url": "https://aquarium.example.org/seahorse"}]}]}
    s.update(over)
    return s


print("\n── 1. 검사 ──")
ck("좋은 출력은 통과", S.check(good(), DAY) == [], str(S.check(good(), DAY)))
bad = good()
bad["hot"][0]["evidence"] = [{"title": "링크 없음", "url": "없음"}]
ck("링크 없는 근거는 막는다", any("evidence" in e for e in S.check(bad, DAY)))
bad = good()
bad["candidates"][0]["facts"] = [{"fact": "출처 없는 사실"}]
ck("출처 없는 사실은 막는다", any("source_url" in e for e in S.check(bad, DAY)))
bad = good()
bad["hot"][1]["fit"] = ["tiktok_dance"]
ck("모르는 줄기는 막는다", any("fit" in e for e in S.check(bad, DAY)))
ck("hot 이 3개 미만이면 막는다", any("hot" in e for e in S.check(good(hot=good()["hot"][:2]), DAY)))
ck("날짜가 다르면 막는다", any("date" in e for e in S.check(good(date="2026-10-01"), DAY)))
ck("후보 0개도 된다", S.check(good(candidates=[]), DAY) == [])

print("\n── 2. pause_turn 이어 가기 · 검사 오류 다시 묻기 ──")
with tempfile.TemporaryDirectory() as td:
    radar = os.path.join(td, "radar")
    os.makedirs(radar)
    with open(os.path.join(radar, "report.md"), "w", encoding="utf-8") as f:
        f.write("# 레이더 표시\n")
    fc = FakeClient([msg("pause_turn", searches=5), msg("end_turn", json.dumps(good(hot=good()["hot"][:1]), ensure_ascii=False), 4),
                     msg("end_turn", json.dumps(good(), ensure_ascii=False), 2)])
    info = S.write(DAY, radar, os.path.join(td, "out"), client=fc)
    ck("pause 뒤 이어 가고, 검사 오류로 한 번 더 묻고 통과", info["ok"] and info["tries"] == 2 and len(fc.calls) == 3, str(info))
    ck("pause 턴을 assistant 로 붙여 다시 보낸다", fc.calls[1]["messages"][-1]["role"] == "assistant")
    ck("다시 물을 때 오류를 붙인다", "hot: 3~8개" in fc.calls[2]["messages"][-1]["content"])
    ck("검색·읽기 도구를 붙이고 횟수 상한을 건다",
       {t["name"]: t.get("max_uses") for t in fc.calls[0]["tools"]} == {"web_search": S.MAX_SEARCH, "web_fetch": S.MAX_FETCH})
    ck("검색 횟수를 세고 달러에 넣는다", info["tokens"]["web_search"] == 11 and info["usd"] >= 0.11, str(info["tokens"]))
    um = fc.calls[0]["messages"][0]["content"][0]
    ck("사용자 메시지: 채널·줄기·레이더·재고·이미 쓴 소재 · 캐시", "레이더 표시" in um["text"] and "insta_worker" in um["text"]
       and "콘텐츠 재고" in um["text"] and "used" in um["text"] and um.get("cache_control") == {"type": "ephemeral"})
    out = os.path.join(td, "out", f"{DAY.isoformat()}.json")
    b = S.brief(out)
    ck("brief: 맥박이 읽을 요약(링크 포함)", "주제 0" in b and "https://news.example.com/0" in b and "후보 insta_danger" in b, b)
    ck("latest: 가장 늦은 날 파일(api 파일은 빼고)", S.latest(os.path.join(td, "out")) == out)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
