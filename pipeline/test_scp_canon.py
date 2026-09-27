#!/usr/bin/env python3
"""원작 SCP 회차 배정·강제·저작자 표기 회귀 테스트.

    python pipeline/test_scp_canon.py
"""
from __future__ import annotations
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_scp as R  # noqa: E402
import scp_canon as C  # noqa: E402
import structure_rules as S  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


D = dt.date
print("── 배정 ──")
a = C.assign(D(2026, 9, 28))
ck("첫 월요일은 SCP-682 원작", a["origin"] == "canon" and a["scp_number"] == "SCP-682", str(a))
ck("다음 월요일은 SCP-096", C.assign(D(2026, 10, 5))["scp_number"] == "SCP-096")
ck("목요일은 오리지널", C.assign(D(2026, 10, 1))["origin"] == "original")
ck("시작 전 월요일은 오리지널", C.assign(D(2026, 9, 21))["origin"] == "original")
ck("큐를 다 쓰면 오리지널(같은 원작 반복 안 함)",
   C.assign(C.START + dt.timedelta(days=7 * len(C.QUEUE)))["origin"] == "original")
ck("structure_rules 도 같은 배정을 쓴다", S.origin_for("2026-09-28") == "canon" and S.origin_for("2026-10-01") == "original")

print("── 원문 팩 ──")
for n in C.QUEUE:
    meta = C.read_meta(os.path.join(C.PACK, f"scp-{n}.md"))
    ok = bool(meta.get("cite")) and "CC BY-SA" in meta.get("cite", "") and meta.get("url", "").endswith(f"scp-{n}")
    size = os.path.getsize(os.path.join(C.PACK, f"scp-{n}.md")) if os.path.exists(os.path.join(C.PACK, f"scp-{n}.md")) else 0
    ck(f"SCP-{n} 원문·저작자 표기", ok and size > 1000, f"{meta} {size}")
ck("큐 52편 · 중복 없음", len(C.QUEUE) == 52 and len(set(C.QUEUE)) == 52, str(len(C.QUEUE)))
ck("제외 개체가 큐에 없다",
   not set(C.QUEUE) & {"610", "231", "008", "058", "882", "1048", "012", "2521", "3125", "6000"})
packs = {f[4:-3] for f in os.listdir(C.PACK) if f.startswith("scp-") and f.endswith(".md")}
ck("팩 파일 = 큐(남는 파일·빠진 파일 없음)", packs == set(C.QUEUE), str(packs ^ set(C.QUEUE)))
ck("1년 뒤 월요일까지 원작", C.assign(C.START + dt.timedelta(days=7 * 51))["origin"] == "canon")

print("── 강제(gate) ──")
ck("원작 날에 오리지널이면 막는다",
   C.gate({"date": "2026-09-28", "origin": "original", "scp_number": "SCP-9412"}) != [])
ck("원작 날에 번호가 다르면 막는다",
   C.gate({"date": "2026-09-28", "origin": "canon", "scp_number": "SCP-096"}) != [])
ck("원작 날에 배정대로면 통과", C.gate({"date": "2026-09-28", "origin": "canon", "scp_number": "SCP-682"}) == [])
ck("오리지널 날은 검사 안 함", C.gate({"date": "2026-10-01", "origin": "original", "scp_number": "SCP-9412"}) == [])
ck("앞자리 0 표기도 같은 번호", C.gate({"date": "2026-10-05", "origin": "canon", "scp_number": "SCP-96"}) == [])

print("── 저작자 표기 ──")
spec = {"origin": "canon", "scp_number": "SCP-682",
        "platforms": {"youtube": {"title": "SCP-682", "description": "설명"}}}
m = R.build_meta(spec, [], False)
ck("원작 회차 설명란에 CC BY-SA 저작자 줄이 붙는다", "Dr Gears" in m["description"] and "CC BY-SA" in m["description"],
   m["description"])
m2 = R.build_meta({**spec, "origin": "original"}, [], False)
ck("오리지널 회차에는 안 붙는다", "Dr Gears" not in m2["description"])

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
