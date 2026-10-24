#!/usr/bin/env python3
"""오디오 언어·태그 보존 · 번역 폴백(yt_i18n) 회귀 테스트.

    python pipeline/test_audio_lang.py

2026-09-30: yt_i18n.localize 가 snippet 을 덮어쓰며 defaultAudioLanguage 를 빼먹어 한국어 쇼츠·SCP 가
'오디오 언어 영어(en-US)'가 됐고(쇼츠 0~183회), 업로드 직후 태그가 비어 있을 때 태그도 지웠다.
2026-10-24: ASMR·일회성 되돌리기(fix_audio_lang)를 지우며 그 검사는 뺐다 — 남은 건 공용 yt_i18n 검사뿐이다
  (번역 폴백 절은 지운 test_asmr_i18n.py 에서 옮겼다 — upload_tale 이 translate_meta 를 쓴다).
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yt_i18n as I  # noqa: E402

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

print("── 말소리 없는 영상의 오디오 언어 ──")
ck("소리 영상(audio_lang='')은 번역 때도 오디오 언어를 채우지 않음",
   "defaultAudioLanguage" not in I.snippet_for_update({"title": "Rain 8 Hours"}, audio_lang=""))
ck("이미 들어 있는 값은 그대로", I.snippet_for_update({"title": "x", "defaultAudioLanguage": "en-US"}, audio_lang="")["defaultAudioLanguage"] == "en-US")
ck("audio_lang 을 안 주면 예전처럼 기본값", bool(I.snippet_for_update({"title": "x"}).get("defaultAudioLanguage")))
_here = os.path.dirname(os.path.abspath(__file__))
ck("코드 어디에도 'zxx' 값을 싣지 않는다", all('"zxx"' not in open(os.path.join(_here, f), encoding="utf-8").read()
                                          for f in ("upload_youtube_novel.py", "yt_i18n.py")))

# ── 번역 폴백(Spark gemma) — 루틴 번역·Claude 키가 없어도 영어가 빠지지 않게 ──
print("── 번역 폴백(Spark gemma) ──")
calls = []
_orig = (I._claude, I._spark_llm)
_env = {k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "I18N_SPARK")}
try:
    I._claude = lambda s, u, m=4000: calls.append("claude") or None
    I._spark_llm = lambda s, u, timeout_sec=300: calls.append("spark") or '{"en":{"title":"T","description":"D"}}'
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("I18N_SPARK", None)
    ck("키가 없으면 Spark 로 번역한다", I.translate_meta("제목", "설명", ["en"]) == {"en": {"title": "T", "description": "D"}}
       and calls == ["spark"], str(calls))
    calls.clear()
    os.environ["ANTHROPIC_API_KEY"] = "x"
    I._llm("s", "u")
    ck("키가 있으면 Claude 먼저, 실패하면 Spark", calls == ["claude", "spark"], str(calls))
    del os.environ["ANTHROPIC_API_KEY"]
    os.environ["I18N_SPARK"] = "0"
    calls.clear()
    ck("I18N_SPARK=0 이면 Spark 도 안 부른다", I._llm("s", "u") is None and calls == [], str(calls))
finally:
    I._claude, I._spark_llm = _orig
    for k, v in _env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
