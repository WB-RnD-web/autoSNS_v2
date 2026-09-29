#!/usr/bin/env python3
"""쇼츠 업로드 메타 — AI 합성 표시 판정 회귀 테스트.

    python pipeline/test_shorts_meta.py
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_pipeline as P  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


bg = {"_bg": "assets/_bg.jpg"}
ck("정치 쇼츠 + AI 배경 → 표시", P.synthetic_label({"topic": "politics"}, bg) is True)
ck("미장(stock_us) + AI 배경 → 표시", P.synthetic_label({"topic": "stock_us"}, bg) is True)
ck("운세(캐릭터 그림) → 표시 안 함", P.synthetic_label({"topic": "fortune"}, bg) is False)
ck("별자리(천체 일러스트) → 표시 안 함", P.synthetic_label({"topic": "horoscope"}, bg) is False)
ck("AI 배경이 없으면 필드 자체를 안 보냄", P.synthetic_label({"topic": "politics"}, {}) is None)

print("── 일시정지 토픽(2026-09-29) ──")
_saved = os.environ.pop("SHORTS_PAUSED_TOPICS", None)
ck("기본: 별자리·국장·미장은 멈춤",
   all(P.is_paused({"topic": t}) for t in ("horoscope", "stock", "stock_us")))
ck("기본: 정치·운세는 나간다", not P.is_paused({"topic": "politics"}) and not P.is_paused({"topic": "fortune"}))
ck("토픽이 없으면 멈추지 않는다", not P.is_paused({}))
os.environ["SHORTS_PAUSED_TOPICS"] = "none"
ck("none 이면 전부 재개", not any(P.is_paused({"topic": t}) for t in ("horoscope", "stock", "stock_us")))
os.environ["SHORTS_PAUSED_TOPICS"] = " Stock_US , horoscope "
ck("레포 변수 목록(공백·대소문자 무시, 정확히 일치)",
   P.is_paused({"topic": "stock_us"}) and P.is_paused({"topic": "horoscope"})
   and not P.is_paused({"topic": "stock"}))
os.environ["SHORTS_PAUSED_TOPICS"] = ""
ck("빈 값이면 기본값", P.is_paused({"topic": "stock"}))
if _saved is None:
    os.environ.pop("SHORTS_PAUSED_TOPICS", None)
else:
    os.environ["SHORTS_PAUSED_TOPICS"] = _saved

# process() 가 렌더 전에 건너뛰는지 — 스토리보드 파일만 있으면 된다(렌더·업로드 안 감).
import json as _json  # noqa: E402
import tempfile  # noqa: E402
from types import SimpleNamespace  # noqa: E402
with tempfile.TemporaryDirectory() as _d:
    _p = os.path.join(_d, "2026-09-30_stock_us_storyboard.json")
    with open(_p, "w", encoding="utf-8") as _f:
        _json.dump({"date": "2026-09-30", "topic": "stock_us"}, _f)
    _r = P.process(_p, SimpleNamespace(include_paused=False), None)
    ck("process: 멈춘 토픽은 렌더 없이 SKIP", _r["skipped"] == "paused" and _r["video"] is None and not _r["error"])

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
