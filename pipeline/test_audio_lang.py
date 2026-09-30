#!/usr/bin/env python3
"""오디오 언어·태그 보존 회귀 테스트.

    python pipeline/test_audio_lang.py

2026-09-30: yt_i18n.localize 가 snippet 을 덮어쓰며 defaultAudioLanguage 를 빼먹어 한국어 쇼츠·SCP 가
'오디오 언어 영어(en-US)'가 됐고(쇼츠 0~183회), 업로드 직후 태그가 비어 있을 때 태그도 지웠다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_i18n as I  # noqa: E402
import fix_audio_lang as F  # noqa: E402
import run_asmr as A  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


print("── 현지화 덮어쓰기 ──")
sn = {"title": "t", "description": "d", "categoryId": "25", "tags": ["뉴스"], "defaultLanguage": "ko",
      "defaultAudioLanguage": "ko"}
b = I.snippet_for_update(sn)
ck("읽은 오디오 언어를 그대로 싣는다", b["defaultAudioLanguage"] == "ko", b)
ck("읽은 태그를 그대로 싣는다", b["tags"] == ["뉴스"], b)
ck("카테고리 유지", b["categoryId"] == "25")
bare = {"title": "t", "description": "d", "categoryId": "25"}
b = I.snippet_for_update(bare, audio_lang="ko", tags=["운세", "shorts"])
ck("오디오 언어가 비어 있으면 업로드한 쪽 값", b["defaultAudioLanguage"] == "ko", b)
ck("태그가 비어 있으면 업로드한 쪽 값", b["tags"] == ["운세", "shorts"], b)
b = I.snippet_for_update(bare)
ck("아무것도 없어도 오디오 언어를 비워 보내지 않는다", bool(b["defaultAudioLanguage"]), b)
ck("영어 채널(구미)은 읽은 en 유지", I.snippet_for_update({**bare, "defaultAudioLanguage": "en"}, audio_lang="ko")[
    "defaultAudioLanguage"] == "en")

print("── 되돌리기 대상 ──")
ck("한국어 쇼츠 → ko", F.target({"title": "총장은 남는데 검찰청만 사라진다 #shorts"}) == "ko")
ck("SCP 한국어 → ko", F.target({"title": "SCP-682 불사의 파충류 — 산성 격리실 녹취 [SCP-682]"}) == "ko")
ck("ASMR 은 건드리지 않음", F.target({"title": "🌧️ 창가에 부딪히는 빗소리 ASMR 3시간"}) is None)
ck("영어 제목은 건드리지 않음", F.target({"title": "Korea Sleep Sounds — Rain on Hanok Roof 8 Hours"}) is None)

print("── ASMR 오디오 언어 ──")
ck("말소리 없는 ASMR → zxx(관련 없음)", A.audio_language({"narration_text": ""}) == "zxx")
ck("나레이션 있으면 ko", A.audio_language({"narration_text": "편안한 밤 되세요"}) == "ko")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
