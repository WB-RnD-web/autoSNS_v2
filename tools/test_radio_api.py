#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/radio_api.py — 가짜 API 로 쓰기·검사·고쳐 쓰기 흐름을 본다(네트워크·키 없이)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import radio_api as A  # noqa: E402

FAIL = []


def ck(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got and not cond else ""))
    if not cond:
        FAIL.append(name)


D = dt.date(2026, 11, 28)
with open(A.SAMPLE, encoding="utf-8") as f:
    GOOD = json.load(f)
BAD = copy.deepcopy(GOOD)
BAD["wish"] = BAD["wish"][:7]


class FakeStream:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return types.SimpleNamespace(
            stop_reason="end_turn", content=[types.SimpleNamespace(type="text", text=self.text)],
            usage=types.SimpleNamespace(input_tokens=3000, cache_creation_input_tokens=9000, cache_read_input_tokens=0,
                                        output_tokens=8000))


class FakeClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []
        self.messages = types.SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.answers.pop(0))


def block(sc):
    return "```json\n" + json.dumps(sc, ensure_ascii=False) + "\n```"


print("■ 시스템 프롬프트")
sp = A.system_prompt()
ck("글쓰기 안내·금지어 목록·견본이 들어간다", "누가 듣나" in sp and "종교 말" in sp and "의좋은 형제" in sp)
ck("오늘 사실(brief)에 생년·순위 금지 안내·이야기·옛말", all(x in A.N.brief(D) for x in ("48 · 60 · 72 · 84 · 96년생", "말하지 말 것",
                                                                              "의좋은 형제", "웃는 집에 복이 온다")))

print("■ 쓰기 흐름")
out = os.path.join(tempfile.mkdtemp(prefix="radio_api_"), "x.json")
c1 = FakeClient([block(GOOD)])
r1 = A.write_script(D, out, client=c1)
ck("한 번에 통과하면 시도 1 · 파일이 남는다", r1["ok"] and r1["tries"] == 1 and json.load(open(out, encoding="utf-8")) == GOOD,
   str(r1))
ck("시스템 프롬프트는 캐시(ephemeral)로 보낸다", c1.calls[0]["system"][0].get("cache_control") == {"type": "ephemeral"})
c2 = FakeClient([block(BAD), block(GOOD)])
r2 = A.write_script(D, out, client=c2)
ck("검사에 걸리면 오류를 알려 주고 다시 쓴다(시도 2)", r2["ok"] and r2["tries"] == 2
   and "딱 8줄" in c2.calls[1]["messages"][-1]["content"], str(r2))
c3 = FakeClient(["이건 JSON 이 아니다"] * A.TRIES)
r3 = A.write_script(D, out, client=c3)
ck("끝내 못 고치면 ok=False(렌더·업로드 안 함)", not r3["ok"] and r3["tries"] == A.TRIES)
ck("비용 계산(달러)이 숫자", isinstance(r1["usd"], float) and r1["usd"] > 0)

print()
if FAIL:
    print(f"❌ 실패 {len(FAIL)}개: {FAIL}")
    sys.exit(1)
print("✅ 전부 통과")
