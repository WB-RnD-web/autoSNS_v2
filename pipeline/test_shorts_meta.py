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

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
