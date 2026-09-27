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

# ── 번역 폴백(Spark gemma) — 루틴 번역·Claude 키가 없어도 영어가 빠지지 않게 ──
import yt_i18n as Y  # noqa: E402
calls = []
_orig = (Y._claude, Y._spark_llm)
Y._claude = lambda s, u, m=4000: calls.append("claude") or None
Y._spark_llm = lambda s, u, timeout_sec=300: calls.append("spark") or '{"en":{"title":"T","description":"D"}}'
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("I18N_SPARK", None)
ck("키가 없으면 Spark 로 번역한다", Y.translate_meta("제목", "설명", ["en"]) == {"en": {"title": "T", "description": "D"}}
   and calls == ["spark"], str(calls))
calls.clear()
os.environ["ANTHROPIC_API_KEY"] = "x"
Y._llm("s", "u")
ck("키가 있으면 Claude 먼저, 실패하면 Spark", calls == ["claude", "spark"], str(calls))
del os.environ["ANTHROPIC_API_KEY"]
os.environ["I18N_SPARK"] = "0"
calls.clear()
ck("I18N_SPARK=0 이면 Spark 도 안 부른다", Y._llm("s", "u") is None and calls == [], str(calls))
del os.environ["I18N_SPARK"]
Y._claude, Y._spark_llm = _orig

import asmr_i18n_backfill as B  # noqa: E402
ck("소급: ASMR 제목은 템플릿으로", B.english_for("🌊 파도 소리 ASMR 1시간 | 수면", 3601)["title"].startswith("🌊 Ocean Waves ASMR 1 Hour"))
ck("소급: 라디오 제목은 매핑 없음(→ 번역 모드)", B.english_for("탄약고 자물쇠에, 손가락 성에가 맺혔습니다 | 괴담라디오", 900) is None)
ck("ISO 길이 파싱", B.iso_sec("PT3H26M54S") == 12414 and B.iso_sec("PT42S") == 42)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
