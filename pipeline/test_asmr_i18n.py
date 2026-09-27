#!/usr/bin/env python3
"""ASMR 영어 제목(현지화) 회귀 테스트.

    python pipeline/test_asmr_i18n.py

2026-09-27 스튜디오 실측: ASMR 13편 전부 동영상 언어 미설정·현지화 0개였다(스펙에 번역이 없어
yt_i18n 이 건너뜀). 루틴이 번역을 안 써줘도 영어 제목이 붙는지, 써주면 그걸 우선하는지 본다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_asmr as R  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


spec = {"theme_id": "paper-crumpling", "narration_text": "",
        "platforms": {"youtube": {"title": "📄 종이 구기는 소리 ASMR 3시간 | 귀르가즘 트리거 사운드"}}}
en = R.english_localization(spec, 11427)
ck("슬러그 → 영어 이름", R.english_name("paper-crumpling") == "Paper Crumpling")
ck("asmr 낱말은 이름에서 뺀다", R.english_name("rain-asmr") == "Rain")
ck("제목에 이모지·이름·실제 길이", en["title"].startswith("📄 Paper Crumpling ASMR 3 Hours"), en["title"])
ck("제목에 한글이 없다", not any("가" <= c <= "힣" for c in en["title"]), en["title"])
ck("제목 100자 이하", len(en["title"]) <= 100)
ck("나레이션 없으면 No talking", "No talking" in en["description"])
ck("나레이션 있으면 No talking 을 쓰지 않는다",
   "No talking" not in R.english_localization({**spec, "narration_text": "안녕"}, 3600)["description"])
ck("1시간은 단수", "1 Hour |" in R.english_localization(spec, 3601)["title"])

loc = R.asmr_localizations(spec, 11427)
ck("스펙에 번역이 없어도 en 이 생긴다", "en" in loc and loc["en"]["title"] == en["title"])
given = {**spec, "platforms": {"youtube": {**spec["platforms"]["youtube"],
         "localizations": {"en": {"title": "Routine title", "description": "d"}}}}}
ck("루틴이 써준 en 이 우선", R.asmr_localizations(given, 11427)["en"]["title"] == "Routine title")
ck("영문 태그가 붙는다", "paper crumpling" in R.build_meta(spec, "", False)["tags"])

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
