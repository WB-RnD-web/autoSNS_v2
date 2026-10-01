#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 소식 쇼츠(하루 두 번) 회귀 테스트 — 네트워크·자격증명 없이 돈다.

    python pipeline/test_ai_news.py

지키는 것: 출처·날짜 필수(48시간) · 14일 중복 · 슬롯 멱등(같은 슬롯 두 번 = 한 번만) ·
카테고리 28 · 재생목록 · 크로스포스트는 AI 토픽만(INSTA_PUBLISH 없으면 dry-run) ·
숫자·용어·확인 안 된 보도·캡션·형식 돌려쓰기 · 진행자 금지 · 워크플로 연결 ·
원문 피드(data/ai-news-feed): 출처는 피드의 기사만 · published_at 그대로 · facts 숫자는 본문에 ·
피드 만들기(RSS/Atom·기사 본문·ODT 첨부·48시간·AI 거르기) · 피드 브랜치 push 가 업로드를 깨우지 않는다.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ai_news as A  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


NOW = dt.datetime(2026, 9, 30, 10, 20, tzinfo=A.KST)
PATH = "output/news/2026-09-30_ai_am_storyboard.json"


def base(date="2026-09-30", slot="am", published="2026-09-30T08:10:00+09:00"):
    return {
        "date": date, "topic": "ai", "slot": slot, "privacy": "public",
        "format": "guard", "angle": "사기·딥페이크", "topic_keyword": "목소리 복제 사기",
        "headline": "AI 목소리 복제 보이스피싱 신고, 작년의 3배",
        "hook_title": "엄마 목소리, 3초면 복제됩니다",
        "thumbnail_hook": "A worried elderly hand holding an old flip phone on a kitchen table at night, "
                          "soft blue light, no text, no faces",
        "thumbnail_text": "3초면 복제",
        "glossary": [{"term": "딥페이크", "plain": "AI로 진짜처럼 만든 가짜"}],
        "sources": [{"outlet": "연합뉴스", "title": "AI 목소리 복제 보이스피싱 신고 3배",
                     "url": "https://www.yna.co.kr/view/AKR20260930000100017",
                     "published_at": published, "confirmed": True,
                     "facts": ["올해 1~8월 AI 목소리 복제 의심 신고 1,245건, 작년 같은 기간의 3배",
                               "목소리 3초 분량이면 복제할 수 있다고 경찰이 설명"]}],
        "scenes": [
            {"type": "hook", "pill": "사기 주의", "lines": ["엄마 목소리", "3초면 복제"], "highlight": "3초",
             "narration": "전화 속에서 들리는 엄마 목소리가, 사실은 AI가 만든 가짜일 수 있습니다."},
            {"type": "stat", "label": "AI 목소리 사기 신고", "from": 0, "to": 1245, "suffix": "건", "bar": True,
             "sub": "작년의 <b>3배</b>",
             "narration": "올해 여덟 달 동안 신고가 천이백 건을 넘었고, 작년 같은 기간의 세 배입니다."},
            {"type": "statement", "text": "딥페이크, 이제 목소리도", "highlight": "목소리",
             "narration": "딥페이크, 그러니까 AI로 진짜처럼 만든 가짜가 이제 목소리까지 흉내 냅니다."},
            {"type": "keypoint", "label": "막는 법 3가지",
             "points": ["가족끼리 <b>암호 한 단어</b>", "끊고 <b>다시 걸기</b>", "돈 얘기면 <b>일단 멈춤</b>"],
             "narration": "막는 법은 간단합니다. 가족끼리 암호 한 단어를 정하고, 일단 끊고 다시 걸고, "
                          "돈 얘기가 나오면 멈추세요."},
            {"type": "statement", "text": "우리 집 암호, 정하셨나요?", "highlight": "암호",
             "narration": "오늘 저녁 식사 자리에서, 가족끼리 암호 한 단어 정해 두시면 어떨까요?"},
        ],
        "platforms": {
            "youtube": {"title": "엄마 목소리, 3초면 복제됩니다 #shorts",
                        "description": "AI 목소리 복제 보이스피싱 신고가 작년의 3배로 늘었습니다.\n\n#AI #보이스피싱 #shorts"},
            "instagram": {"caption": "엄마 목소리, 3초면 복제됩니다\n\n가족끼리 암호 한 단어 정해 두세요.\n"
                                     "매일 오전·저녁 AI 소식은 유튜브 '왕별이'에서 쉽게 풀어 드려요.\n"
                                     "출처 연합뉴스\n\n#AI #보이스피싱 #딥페이크"},
            "threads": {"text": "엄마 목소리도 3초면 복제된대요. 가족끼리 암호 한 단어 정해 두세요. "
                                "매일 AI 소식은 유튜브 왕별이에서 쉽게 풀어요. #AI소식"},
        },
    }


def feed_item(url, published, text, title="", outlet="연합뉴스", official=False):
    return {"id": A.feed_id(url), "source": "t", "outlet": outlet, "official": official, "lang": "ko",
            "title": title, "url": url, "published_at": published, "text": text, "text_chars": len(text),
            "text_from": "page"}


def feed_of(*sbs, name="2026-09-30_am.json", today=None):
    """대본의 출처를 그대로 담은 피드(본문 = facts) — 피드 대조 말고 다른 규칙을 볼 때의 기본값."""
    items = [feed_item(s["url"], s.get("published_at", ""),
                       " ".join(f for f in s.get("facts") or [] if isinstance(f, str)), s.get("title", ""))
             for sb in sbs for s in sb.get("sources") or [] if isinstance(s, dict) and s.get("url")]
    return A.feed_index([(name, {"items": items})], today or NOW.date())


MIRROR = object()


def errs(sb, path=PATH, now=NOW, history=None, lenient=False, feed=MIRROR):
    return A.check(sb, path, now=now, history=history or [], lenient=lenient,
                   feed=feed_of(sb) if feed is MIRROR else feed)


def has(lst, word):
    return any(word in x for x in lst)


print("\n── 0. 기준 대본은 통과 ──")
e, w = errs(base())
ck("기준 대본 오류 0건", e == [] and w == [], str(e))

print("\n── 1. 출처·날짜 필수(48시간) ──")
sb = base(); sb["sources"] = []
ck("출처가 없으면 탈락", has(errs(sb)[0], "sources 가 비었다"))
sb = base(); sb["sources"][0]["url"] = ""
ck("url 없으면 탈락", has(errs(sb)[0], "url 이 없다"))
sb = base(); sb["sources"][0]["url"] = "https://www.google.com/search?q=ai"
ck("검색 결과 링크는 출처가 아니다", has(errs(sb)[0], "검색·모음 링크"))
sb = base(); del sb["sources"][0]["published_at"]
ck("published_at 없으면 탈락", has(errs(sb)[0], "published_at 이 없거나"))
sb = base(published="2026-09-27T09:00:00+09:00")
ck("72시간 지난 출처뿐이면 탈락", has(errs(sb)[0], "48시간 안에 나온 출처"))
ck("…느슨 모드에선 경고로만", errs(sb, lenient=True)[0] == [] and has(errs(sb, lenient=True)[1], "48시간"))
sb = base(published="2026-09-28T12:00:00+09:00")
ck("46시간 전 출처는 통과", errs(sb)[0] == [], str(errs(sb)[0]))
sb = base(published="2026-10-01T12:00:00+09:00")
ck("미래 시각은 탈락", has(errs(sb)[0], "미래"))
sb = base(); sb["sources"][0]["facts"] = []
ck("facts 비면 탈락", has(errs(sb)[0], "facts 가 비었다"))
sb = base(); del sb["sources"][0]["confirmed"]
ck("confirmed 없으면 탈락", has(errs(sb)[0], "confirmed"))
sb = base(); sb["sources"][0]["published_at"] = "2026-09-30"
ck("날짜만 적으면 그날 00:00 으로 본다(통과)", errs(sb)[0] == [], str(errs(sb)[0]))

print("\n── 2. 14일 중복(URL·제목) ──")
old = A.entry(base(date="2026-09-25", slot="pm"))
e, _ = errs(base(), history=[old])
ck("같은 URL 은 탈락", has(e, "출처 URL 이"))
sim = base(date="2026-09-25", slot="pm")
sim["sources"][0]["url"] = "https://www.hani.co.kr/arti/society/1234567.html"
sim["headline"] = "AI 목소리 복제 보이스피싱 신고 작년의 3배"
e, _ = errs(base(), history=[A.entry(sim)])
ck("비슷한 제목은 탈락", has(e, "비슷하다"), str(e))
far = copy.deepcopy(sim); far["headline"] = "병원 AI 문진표, 대기 20분 줄였다"; far["hook_title"] = "병원 대기, AI가 줄였다"
e, _ = errs(base(), history=[A.entry(far)])
ck("다른 이야기는 통과", not has(e, "비슷하다") and not has(e, "URL"), str(e))
ck("유사도: 같은 이야기 ≥0.5", A.similarity("오픈AI GPT-6 공개", "오픈AI, GPT-6 공개… 뭐가 달라지나") >= A.SIMILAR)
ck("유사도: 다른 이야기 <0.5", A.similarity("딥페이크 보이스피싱 급증", "딥페이크 성범죄 처벌 강화") < A.SIMILAR)
ck("URL 정규화(www·utm·끝 슬래시)",
   A.norm_url("https://www.yna.co.kr/view/X1/?utm_source=a") == A.norm_url("http://yna.co.kr/view/X1"))
with tempfile.TemporaryDirectory() as td:
    for d, slot in (("2026-09-15", "am"), ("2026-09-29", "pm"), ("2026-09-30", "am")):
        with open(os.path.join(td, f"{d}_ai_{slot}_storyboard.json"), "w", encoding="utf-8") as f:
            json.dump(base(date=d, slot=slot), f, ensure_ascii=False)
    h = A.load_history(NOW.date(), exclude="2026-09-30_ai_am", dirs=[td], refs=())
    ck("이력: 14일 창 안 + 자기 자신 제외", [x["key"] for x in h] == ["2026-09-29_ai_pm"], str([x["key"] for x in h]))
led = {"2026-09-29_ai_am": {"video_id": "v", "ai": A.entry(base(date="2026-09-29", slot="am"))},
       "2026-09-29_politics": {"video_id": "p"}}
h = A.load_history(NOW.date(), ledger=led, refs=())
ck("이력: ledger 의 AI 요약도 읽는다(정치는 무시)", [x["key"] for x in h] == ["2026-09-29_ai_am"])

print("\n── 2b. 이력은 누적 브랜치(routine/ai_am·ai_pm)에서 git 으로 읽는다 ──")
with tempfile.TemporaryDirectory() as td:
    def sh(*a, cwd):
        subprocess.run(a, cwd=cwd, check=True, capture_output=True)
    origin, work, reader = (os.path.join(td, x) for x in ("origin.git", "work", "reader"))
    sh("git", "init", "-q", "--bare", origin, cwd=td)
    sh("git", "clone", "-q", origin, work, cwd=td)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        sh("git", "config", k, v, cwd=work)
    os.makedirs(os.path.join(work, "output", "news"))
    with open(os.path.join(work, "output", "news", "2026-09-29_ai_pm_storyboard.json"), "w", encoding="utf-8") as f:
        json.dump(base(date="2026-09-29", slot="pm"), f, ensure_ascii=False)
    sh("git", "checkout", "-q", "-b", "routine/ai_pm", cwd=work)
    sh("git", "add", "-A", cwd=work)
    sh("git", "commit", "-q", "-m", "ai pm", cwd=work)
    sh("git", "push", "-q", "origin", "routine/ai_pm", cwd=work)
    sh("git", "clone", "-q", origin, reader, cwd=td)
    A.fetch_branches(root=reader)
    got = A.entries_from_refs(root=reader)
    ck("원격 routine/ai_pm 의 지난 대본을 읽는다", [x["key"] for x in got] == ["2026-09-29_ai_pm"], str(got))
    e, _ = errs(base(), history=A.load_history(NOW.date(), exclude="2026-09-30_ai_am", root=reader))
    ck("…그 대본과 URL 이 겹치면 탈락", has(e, "출처 URL 이"))

print("\n── 3. 슬롯 멱등 — 이름·슬롯·날짜 ──")
ck("파일 이름에 슬롯이 없으면 탈락", has(errs(base(), path="output/news/2026-09-30_ai_storyboard.json")[0], "파일 이름"))
ck("slot 과 파일 이름이 다르면 탈락", has(errs(base(slot="pm"))[0], "slot('pm')"))
sb = base(); sb["slot"] = "noon"
ck("슬롯은 am/pm 뿐", has(errs(sb, path="output/news/2026-09-30_ai_noon_storyboard.json")[0], "파일 이름"))
ck("date 가 파일 날짜와 다르면 탈락", has(errs(base(date="2026-09-29"), path=PATH)[0], "date("))
ck("사흘 지난 원고는 탈락", has(errs(base(date="2026-09-27", published="2026-09-29T09:00:00+09:00"),
                             path="output/news/2026-09-27_ai_am_storyboard.json")[0], "오늘"))
import ledger as L  # noqa: E402
ck("ledger 키에 슬롯이 붙는다", L.key_for(base(slot="am")) == "2026-09-30_ai_am"
   and L.key_for(base(slot="pm")) == "2026-09-30_ai_pm")
ck("슬롯 없는 토픽 키는 그대로", L.key_for({"date": "2026-09-30", "topic": "politics"}) == "2026-09-30_politics")
ups = [{"title": "엄마 목소리, 3초면 복제됩니다 #shorts", "video_id": "VID1",
        "description": "…\n\nAI 소식 2026-09-30 오전", "published": "2026-09-30T01:40:00Z"}]
vid, dup = A.youtube_conflicts(base(), ups, NOW)
ck("유튜브에 같은 슬롯 표식이 있으면 '이미 올라감'", vid == "VID1" and dup == [])
vid, dup = A.youtube_conflicts(base(slot="pm"), ups, NOW)
ck("…다른 슬롯(pm)은 이미 올라감이 아니지만 제목이 같으면 중복", vid is None and has(dup, "비슷하다"))
ups2 = [{"title": "딴 이야기 #shorts", "video_id": "V2", "published": "2026-09-29T10:00:00Z",
         "description": "📰 출처\n· 연합뉴스 (9/29) https://www.yna.co.kr/view/AKR20260930000100017\n\nAI 소식 2026-09-29 저녁"}]
ck("유튜브 설명의 출처 URL 과 겹치면 중복", has(A.youtube_conflicts(base(), ups2, NOW)[1], "URL"))
ck("AI 소식이 아닌 영상은 보지 않는다",
   A.youtube_conflicts(base(), [{"title": "엄마 목소리, 3초면 복제됩니다", "description": "정치"}], NOW) == (None, []))
desc = A.youtube_description(base())
ck("설명란: 출처 주소·날짜 + 슬롯 표식", "https://www.yna.co.kr/view/AKR20260930000100017" in desc
   and "(9/30)" in desc and desc.rstrip().endswith("AI 소식 2026-09-30 오전"), desc)

print("\n── 4. 숫자·어려운 말·확인 안 된 보도 ──")
sb = base(); sb["scenes"][1]["to"] = 1500
ck("facts 에 없는 숫자(stat)는 탈락", has(errs(sb)[0], "1500"))
sb = base(); sb["hook_title"] = "엄마 목소리, 5초면 복제됩니다"
ck("facts 에 없는 제목 숫자도 탈락", has(errs(sb)[0], "facts 에 없는 숫자: 5"))
ck("'3가지' 같은 구성 숫자는 사실 주장이 아니다", "3" not in A.numbers("막는 법 3가지"))
ck("천 단위 쉼표 정규화", A.numbers("1,245건과 4.50%") == {"1245", "4.5"})
sb = base(); sb["glossary"] = []
ck("어려운 말에 풀이가 없으면 탈락", has(errs(sb)[0], "'딥페이크'"))
sb = base(); sb["glossary"][0]["plain"] = "사람 얼굴을 바꿔 치는 기술"
ck("풀이를 말로 안 읽으면 탈락", has(errs(sb)[0], "내레이션에 글자 그대로 없다"))
sb = base(); sb["scenes"][2]["narration"] = "새로 나온 LLM이 목소리까지 흉내 냅니다, AI로 진짜처럼 만든 가짜죠."
ck("영문 약어(LLM)도 잡는다", has(errs(sb)[0], "'LLM'"))
sb = base(); sb["sources"][0]["confirmed"] = False
ck("확인 안 된 보도인데 단정하면 탈락", has(errs(sb)[0], "단정한다"))
sb["scenes"][1]["narration"] = "올해 여덟 달 동안 신고가 천이백 건을 넘었고, 작년의 세 배라고 보도됐습니다."
ck("'보도됐습니다'로 전하면 통과", errs(sb)[0] == [], str(errs(sb)[0]))
sb = base(); sb["hook_title"] = "충격, 엄마 목소리 3초면 복제"
ck("반응 요구 단어(충격)는 탈락", has(errs(sb)[0], "충격"))

print("\n── 5. 첫 화면·길이·캡션 ──")
sb = base(); sb["scenes"][0]["lines"] = ["엄마", "목소리", "3초면 복제"]
ck("hook 은 딱 두 줄", has(errs(sb)[0], "딱 2줄"))
sb = base(); sb["scenes"][0]["lines"] = ["엄마 목소리가 전화로", "3초면 복제"]
ck("긴 줄은 첫 화면 글자가 작아져 탈락", has(errs(sb)[0], "px 로 작아진다"))
sb = base(); sb["scenes"][0]["type"] = "statement"
ck("첫 장면은 hook", has(errs(sb)[0], "첫 장면은 type 'hook'"))
sb = base(); sb["scenes"] = sb["scenes"][:3]
ck("장면 4개 미만 탈락", has(errs(sb)[0], "장면 3개"))
sb = base()
for s in sb["scenes"]:
    s["narration"] = s["narration"][:20]
ck("너무 짧으면(≈30초 미만) 탈락", has(errs(sb)[0], "읽는 글자"))
ck("렌더 길이 60초는 탈락, 42초는 통과", A.check_duration(60.2) and A.check_duration(42.0) is None)
sb = base(); sb["platforms"]["threads"]["text"] += " #AI"
ck("쓰레드 해시태그는 딱 1개", has(errs(sb)[0], "해시태그 2개"))
sb = base(); sb["platforms"]["threads"]["text"] = "가" * 495 + " 왕별이 #AI소식"
ck("쓰레드 500자 초과 탈락", has(errs(sb)[0], "쓰레드 글"))
sb = base(); sb["platforms"]["instagram"]["caption"] = sb["platforms"]["instagram"]["caption"].replace("왕별이", "우리 채널")
ck("인스타 캡션에 '왕별이' 언급 필수", has(errs(sb)[0], "인스타 캡션에 유튜브 채널"))
sb = base(); sb["platforms"]["instagram"]["caption"] = "왕별이 " + "가" * 2200
ck("인스타 2,200자 초과 탈락", has(errs(sb)[0], "인스타 캡션 2204자"))

print("\n── 6. 틀 돌려쓰기(대량 생산처럼 보이지 않게) ──")
prev = base(date="2026-09-29", slot="pm")
prev["sources"][0]["url"] = "https://www.hani.co.kr/arti/1.html"
prev["headline"] = "병원 AI 문진표 도입"; prev["hook_title"] = "병원 대기, AI가 줄였다"
e, _ = errs(base(), history=[A.entry(prev)])
ck("직전 편과 같은 format 이면 탈락", has(e, "직전 편"))
ck("…장면 구성이 같아도 탈락", has(e, "장면 구성"))
ck("…pill 이 같아도 탈락", has(e, "pill"))
prev2 = copy.deepcopy(prev); prev2["format"] = "explain"; prev2["scenes"][0]["pill"] = "새 기능"
prev2["scenes"] = [prev2["scenes"][i] for i in (0, 2, 1, 3, 4)]
e, _ = errs(base(), history=[A.entry(prev2)])
ck("형식·구성·pill 이 다르면 통과", e == [], str(e))
sb = base(); sb["format"] = "listicle"
ck("format 은 정해진 목록 중 하나", has(errs(sb)[0], "format 은"))
sb = base(); sb["angle"] = "기술"
ck("angle 은 정해진 목록 중 하나", has(errs(sb)[0], "angle 은"))

print("\n── 7. 렌더 설정 — 진행자 금지 · 큰 첫 제목 · 색 ──")
import motion_short as M  # noqa: E402
_saved = {k: os.environ.get(k) for k in ("PRESENTER", "PRESENTER_TOPICS", "TOP_HOOK")}
os.environ["PRESENTER"] = "1"
os.environ["PRESENTER_TOPICS"] = "ai,fortune"
os.environ.pop("TOP_HOOK", None)
ck("AI 소식은 레포 변수로도 진행자를 못 켠다", M.presenter_on("ai") is False)
ck("TOP_HOOK(큰 두 줄 제목)은 AI 소식에 켜진다", M.top_hook_on("ai") is True)
ck("AI 소식 액센트 청록", M.topic_accent("ai") == A.ACCENT)
for k, v in _saved.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
nb = A.normalize(base())
ck("브랜드 띠·액센트는 코드가 채운다", all(s["brand"] == A.BRAND for s in nb["scenes"]) and nb["accent"] == A.ACCENT)

print("\n── 8. 카테고리 28 · 재생목록 · 크로스포스트(AI 토픽만) ──")
import run_pipeline as P  # noqa: E402
ck("AI 소식 = 과학·기술(28)", P.category_for("ai") == "28")
ck("운세 = 24 · 정치 = 25 그대로", P.category_for("fortune") == "24" and P.category_for("politics") == "25")
ck("AI 재생목록 'AI 소식 …'", (P.playlist_for("ai") or ("",))[0].startswith("AI 소식"))
ck("운세 재생목록 그대로 · 정치는 없음",
   P.playlist_for("fortune")[0] == P.FORTUNE_PLAYLIST and P.playlist_for("politics") is None)
_env = {k: os.environ.pop(k, None) for k in ("SOCIAL_CROSSPOST", "SOCIAL_CROSSPOST_TOPICS", "INSTA_PUBLISH",
                                             "INSTA_THREADS", "IG_USER_ID", "IG_ACCESS_TOKEN",
                                             "THREADS_USER_ID", "THREADS_ACCESS_TOKEN", "SHORTS_PAUSED_TOPICS")}
ck("크로스포스트: 기본은 AI 소식만", P.social_crosspost_on("ai") and not P.social_crosspost_on("politics")
   and not P.social_crosspost_on("fortune"))
os.environ["SOCIAL_CROSSPOST_TOPICS"] = "none"
ck("SOCIAL_CROSSPOST_TOPICS=none 이면 전부 끔", not P.social_crosspost_on("ai"))
del os.environ["SOCIAL_CROSSPOST_TOPICS"]
r = {}
P.do_social("x.mp4", base(), r)
ck("INSTA_PUBLISH 없으면 dry-run(아무것도 안 올림)", str(r.get("social", "")).startswith("[dry-run]"), str(r))
ck("쿼터 소진은 재시도하지 않는다",
   P.is_quota_error(Exception("<HttpError 403 ... reason: quotaExceeded>")) and not P.is_quota_error(Exception("503")))

print("\n── 9. process() 끝까지(렌더·업로드는 가짜) — 같은 슬롯 두 번 = 한 번만 ──")
import config  # noqa: E402
import upload_youtube_novel as N  # noqa: E402
calls = {"upload": [], "playlist": []}
today = dt.datetime.now(A.KST)
D = today.strftime("%Y-%m-%d")
pub = (today - dt.timedelta(hours=2)).isoformat()
_orig = (P._prepare_bg, M.build_motion, M.probe_dur, P.has_credentials, P.upload_with_retry,
         P.add_playlist, A.recent_uploads, N.get_service, config.OUTPUT, config.RENDERS_DIR,
         config.NEWS_DIR, config.ASSETS_DIR, A.load_feed, A.entries_from_refs)
# ★테스트는 레포의 진짜 원격 브랜치(routine/ai_am·ai_pm)를 읽지 않는다 — 2026-10-01 실물 첫 대본(오늘 날짜·explain)이
#   이 절의 '오늘' 견본과 같은 키라서 이력에 끼어들어, 깨진 코드가 아닌데도 테스트가 실패하고 업로드가 통째로 막혔다.
A.entries_from_refs = lambda refs=A.BRANCHES, root=None: []


def fake_build(spec, out_mp4, wd, quality="standard"):
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    open(out_mp4, "wb").close()
    return out_mp4


try:
    with tempfile.TemporaryDirectory() as td:
        import pathlib
        config.OUTPUT = pathlib.Path(td)
        config.RENDERS_DIR, config.NEWS_DIR, config.ASSETS_DIR = (config.OUTPUT / x for x in ("renders", "news", "assets"))
        P._prepare_bg = lambda *a, **k: None
        M.build_motion = fake_build
        M.probe_dur = lambda p: 41.5
        P.has_credentials = lambda: True
        P.upload_with_retry = lambda video, meta: (calls["upload"].append((video, dict(meta))) or f"VID{len(calls['upload'])}")
        P.add_playlist = lambda vid, title, desc: calls["playlist"].append((vid, title))
        A.recent_uploads = lambda yt, max_items=100: []
        N.get_service = lambda: object()
        news = os.path.join(td, "news")
        os.makedirs(news)
        paths, sbs = {}, []
        for slot in ("am", "pm"):
            sb = base(date=D, slot=slot, published=pub)
            if slot == "pm":                           # 저녁 편은 다른 이야기·다른 형식
                sb["sources"][0]["url"] = "https://www.hani.co.kr/arti/economy/7654321.html"
                sb["headline"] = "병원 AI 문진, 대기 3배 줄여"; sb["hook_title"] = "병원 대기, AI가 3배 줄였다"
                sb["format"] = "explain"; sb["scenes"][0]["pill"] = "새 기능"
                sb["scenes"] = [sb["scenes"][i] for i in (0, 2, 1, 3, 4)]
            paths[slot] = os.path.join(news, f"{D}_ai_{slot}_storyboard.json")
            with open(paths[slot], "w", encoding="utf-8") as f:
                json.dump(sb, f, ensure_ascii=False)
            sbs.append(sb)
        # Actions 에서는 data/ai-news-feed 를 읽는다 — 여기선 두 편의 출처를 담은 피드로 바꿔 낀다
        A.load_feed = lambda now=None, **k: feed_of(*sbs, name=f"{D}_am.json", today=today.date())
        led_path = os.path.join(td, "ai_ledger.json")
        args = SimpleNamespace(include_paused=False, no_upload=False, no_social=False, force_private=False,
                               dry_run_upload=False, quality="draft", ledger_path=led_path, ai_lenient=False,
                               spec=None)
        led = {}
        r1 = P.process(paths["am"], args, led)
        ck("오전 편 업로드", r1["error"] is None and str(r1["uploaded"]).startswith("https://youtu.be/VID1"), str(r1))
        meta = calls["upload"][0][1] if calls["upload"] else {}
        ck("…카테고리 28", meta.get("category") == "28", str(meta.get("category")))
        ck("…설명에 출처와 슬롯 표식", f"AI 소식 {D} 오전" in meta.get("description", "")
           and "yna.co.kr" in meta.get("description", ""))
        ck("…태그는 AI 소식용", "인공지능" in (meta.get("tags") or []))
        ck("…공개면 'AI 소식' 재생목록에 추가", calls["playlist"] and calls["playlist"][0][1] == P.AI_PLAYLIST)
        ck("…ledger 키에 슬롯 + 중복 검사용 요약", f"{D}_ai_am" in led and "ai" in led[f"{D}_ai_am"])
        ck("…인스타·쓰레드는 dry-run(INSTA_PUBLISH 없음)", str(r1["social"]).startswith("[dry-run]"), str(r1["social"]))
        r2 = P.process(paths["am"], args, led)
        ck("같은 슬롯을 다시 밀어도 한 번만(ledger)", r2["skipped"] is True and len(calls["upload"]) == 1)
        r3 = P.process(paths["pm"], args, led)
        ck("저녁 편은 따로 올라간다", r3["error"] is None and len(calls["upload"]) == 2, str(r3))
        ck("…렌더 파일도 슬롯별", calls["upload"][1][0].endswith(f"{D}_ai_pm_final.mp4"), calls["upload"][1][0])
        # ledger 캐시가 날아가도 — 유튜브에 표식이 있으면 다시 올리지 않는다
        A.recent_uploads = lambda yt, max_items=100: [
            {"title": "x", "video_id": "VIDX", "description": f"AI 소식 {D} 오전", "published": today.isoformat()}]
        r4 = P.process(paths["am"], args, {})
        ck("ledger 가 비어도 유튜브 표식으로 '이미 올라감'", r4["skipped"] == "uploaded" and len(calls["upload"]) == 2)
        A.recent_uploads = lambda yt, max_items=100: []
        # 정치 대본: 크로스포스트·재생목록 대상 아님
        pol = {"date": D, "topic": "politics", "privacy": "public", "hook_title": "정치 제목",
               "scenes": [{"type": "hook", "lines": ["a", "b"], "narration": "정치 뉴스입니다."}],
               "platforms": {"youtube": {"description": "d"}, "instagram": {"caption": "c"}, "threads": {"text": "t"}}}
        pp = os.path.join(news, f"{D}_politics_storyboard.json")
        with open(pp, "w", encoding="utf-8") as f:
            json.dump(pol, f, ensure_ascii=False)
        r5 = P.process(pp, args, led)
        ck("정치는 인스타·쓰레드로 안 간다", str(r5["social"]).startswith("[skip] 크로스포스트 대상 토픽 아님"), str(r5))
        ck("…재생목록 추가 없음 · 카테고리 25", len(calls["playlist"]) == 2 and calls["upload"][-1][1]["category"] == "25")
        # 검사 실패면 렌더도 안 한다
        bad = base(date=D, slot="am", published=pub); bad["sources"] = []
        bp = os.path.join(td, "x", f"{D}_ai_am_storyboard.json")
        os.makedirs(os.path.dirname(bp))
        with open(bp, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        n_up = len(calls["upload"])
        r6 = P.process(bp, args, {})
        ck("출처 없는 대본은 렌더·업로드 없이 실패", str(r6["error"]).startswith("ai_check") and r6["video"] is None
           and len(calls["upload"]) == n_up)
        # 루틴이 check 를 건너뛰고 밀어도 — Actions 가 피드와 다시 대조한다
        other = base(date=D, slot="am", published=pub)
        other["sources"][0]["url"] = "https://www.etnews.com/20260930000999"
        A.load_feed = lambda now=None, **k: feed_of(other, name=f"{D}_am.json", today=today.date())
        r7 = P.process(paths["am"], args, {})
        ck("피드에 없는 출처면 Actions 에서도 렌더·업로드 없이 실패",
           str(r7["error"]).startswith("ai_check") and "피드에 없는 기사" in str(r7["error"])
           and r7["video"] is None and len(calls["upload"]) == n_up, str(r7))
        A.load_feed = lambda now=None, **k: {"files": [], "docs": {}, "by_url": {}, "by_id": {}, "error": "없음"}
        r8 = P.process(paths["am"], args, {})
        ck("피드를 못 읽으면(브랜치 없음) 올리지 않는다", "대조할 수 없다" in str(r8["error"]) and len(calls["upload"]) == n_up,
           str(r8))
        # 느슨 모드는 공개 업로드에서 무시된다
        ck("--ai-lenient 는 공개 업로드에서 무시", P.ai_lenient(SimpleNamespace(ai_lenient=True)) is False
           and P.ai_lenient(SimpleNamespace(ai_lenient=True, force_private=True)) is True)
finally:
    (P._prepare_bg, M.build_motion, M.probe_dur, P.has_credentials, P.upload_with_retry, P.add_playlist,
     A.recent_uploads, N.get_service, config.OUTPUT, config.RENDERS_DIR, config.NEWS_DIR, config.ASSETS_DIR,
     A.load_feed, A.entries_from_refs) = _orig
    for k, v in _env.items():
        if v is not None:
            os.environ[k] = v

print("\n── 9b. 루틴 도구: 슬롯은 시계로 · push 는 routine/ai_<slot> 로만 ──")
ck("10:07 → 그날 오전", A.slot_now(dt.datetime(2026, 9, 30, 10, 7, tzinfo=A.KST)) == ("2026-09-30", "am"))
ck("19:07 → 그날 저녁", A.slot_now(dt.datetime(2026, 9, 30, 19, 7, tzinfo=A.KST)) == ("2026-09-30", "pm"))
ck("00:40(늦게 돈 저녁 편) → 전날 저녁", A.slot_now(dt.datetime(2026, 10, 1, 0, 40, tzinfo=A.KST)) == ("2026-09-30", "pm"))
with tempfile.TemporaryDirectory() as td:
    def g(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    origin, seed, sess, drafts = (os.path.join(td, x) for x in ("origin.git", "seed", "sess", "drafts"))
    os.makedirs(drafts)
    g("init", "-q", "--bare", origin, cwd=td)
    g("clone", "-q", origin, seed, cwd=td)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        g("config", k, v, cwd=seed)
    g("checkout", "-q", "-b", "main", cwd=seed)
    open(os.path.join(seed, "README.md"), "w").write("x\n")
    g("add", "-A", cwd=seed)
    g("commit", "-q", "-m", "init", cwd=seed)
    g("push", "-q", "origin", "main", cwd=seed)
    # 원문 피드 브랜치(Actions 가 만든다) — 오전·저녁 편 출처 기사가 들어 있다
    g("checkout", "-q", "--orphan", "data/ai-news-feed", cwd=seed)
    g("rm", "-q", "-f", "README.md", cwd=seed)
    os.makedirs(os.path.join(seed, "feed", "ai"))
    facts_txt = " ".join(base()["sources"][0]["facts"])
    with open(os.path.join(seed, "feed", "ai", "2026-09-30_am.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "date": "2026-09-30", "slot": "am", "generated_at": "2026-09-30T09:40:00+09:00",
                   "items": [feed_item(base()["sources"][0]["url"], "2026-09-30T08:10:00+09:00", facts_txt),
                             feed_item("https://www.hani.co.kr/arti/economy/7654321.html",
                                       "2026-09-30T08:10:00+09:00", facts_txt)]}, f, ensure_ascii=False)
    g("add", "-A", cwd=seed)
    g("commit", "-q", "-m", "feed", cwd=seed)
    g("push", "-q", "origin", "data/ai-news-feed", cwd=seed)
    g("clone", "-q", "-b", "main", origin, sess, cwd=td)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        g("config", k, v, cwd=sess)
    g("checkout", "-q", "-b", "claude/session-xyz", cwd=sess)          # 루틴 세션에 주입되는 브랜치 흉내
    am = os.path.join(drafts, "2026-09-30_ai_am_storyboard.json")
    with open(am, "w", encoding="utf-8") as f:
        json.dump(base(), f, ensure_ascii=False)
    ok, msg = A.push(am, now=NOW, root=sess)
    files = g("ls-tree", "-r", "--name-only", "routine/ai_am", cwd=origin) if ok else ""
    ck("검사 통과한 대본을 routine/ai_am 에 올린다(main 위에 한 커밋)",
       ok and "output/news/2026-09-30_ai_am_storyboard.json" in files and "README.md" in files, msg)
    ck("…세션 브랜치(claude/*)는 건드리지 않는다",
       g("rev-parse", "--abbrev-ref", "HEAD", cwd=sess) == "claude/session-xyz"
       and g("status", "--porcelain", cwd=sess) == "" and "claude/session-xyz" not in g("branch", "-a", cwd=origin))
    ok2, msg2 = A.push(am, now=NOW, root=sess)
    ck("같은 슬롯은 두 번 못 올린다", not ok2 and "이미" in msg2, msg2)
    bad = base(); bad["sources"] = []
    badp = os.path.join(drafts, "x", "2026-09-30_ai_pm_storyboard.json")
    os.makedirs(os.path.dirname(badp))
    with open(badp, "w", encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False)
    ok3, msg3 = A.push(badp, now=NOW, root=sess)
    ck("검사 실패면 올리지 않는다", not ok3 and "검사 실패" in msg3
       and "routine/ai_pm" not in g("branch", "-a", cwd=origin))
    stray = base(slot="pm")
    stray["sources"][0]["url"] = "https://www.seoul.co.kr/news/2026/09/30/20260930500123"   # 검색으로만 본 기사
    stray["headline"] = "병원 AI 문진, 대기 3배 줄여"; stray["hook_title"] = "병원 대기, AI가 3배 줄였다"
    stray["format"] = "explain"; stray["scenes"][0]["pill"] = "새 기능"
    stray["scenes"] = [stray["scenes"][i] for i in (0, 2, 1, 3, 4)]
    strayp = os.path.join(drafts, "y", "2026-09-30_ai_pm_storyboard.json")
    os.makedirs(os.path.dirname(strayp))
    with open(strayp, "w", encoding="utf-8") as f:
        json.dump(stray, f, ensure_ascii=False)
    ok5, msg5 = A.push(strayp, now=NOW, root=sess)
    ck("피드(origin/data/ai-news-feed)에 없는 기사는 push 못 한다", not ok5 and "피드에 없는 기사" in msg5
       and "routine/ai_pm" not in g("branch", "-a", cwd=origin), msg5)
    ck("…피드는 원격 브랜치에서 읽는다(기사 2건)",
       len(A.load_feed(NOW, root=sess)["by_url"]) == 2 and A.load_feed(NOW, root=sess)["files"] == ["2026-09-30_am.json"])
    pm = base(slot="pm")
    pm["sources"][0]["url"] = "https://www.hani.co.kr/arti/economy/7654321.html"
    pm["headline"] = "병원 AI 문진, 대기 3배 줄여"; pm["hook_title"] = "병원 대기, AI가 3배 줄였다"
    pm["format"] = "explain"; pm["scenes"][0]["pill"] = "새 기능"
    pm["scenes"] = [pm["scenes"][i] for i in (0, 2, 1, 3, 4)]
    pmp = os.path.join(drafts, "2026-09-30_ai_pm_storyboard.json")
    with open(pmp, "w", encoding="utf-8") as f:
        json.dump(pm, f, ensure_ascii=False)
    ok4, msg4 = A.push(pmp, now=NOW, root=sess)
    ck("저녁 편은 routine/ai_pm 으로(오전 편 이력을 보고 검사한 뒤)", ok4 and "routine/ai_pm" in g("branch", "-a", cwd=origin), msg4)

print("\n── 10. 피드 대조 —출처는 피드의 기사만 · published_at 그대로 · facts 숫자는 본문에 ──")
URL = base()["sources"][0]["url"]
ART = ("(서울=연합뉴스) 경찰청은 올해 1~8월 AI 목소리 복제 의심 신고가 1,245건으로 작년 같은 기간의 3배라고 "
       "30일 밝혔다. 경찰은 목소리 3초 분량이면 복제할 수 있다고 설명했다.")
FEED = A.feed_index([("2026-09-30_am.json", {"items": [feed_item(URL, "2026-09-30T08:10:00+09:00", ART,
                                                                  "AI 목소리 복제 보이스피싱 신고 3배")]})], NOW.date())
e, w = errs(base(), feed=FEED)
ck("기준 대본은 실제 기사 본문과 대조해도 통과", e == [] and w == [], str(e))
e, w = errs(base(), feed=None)
ck("피드를 안 넘기면(None) 탈락 — 빠뜨려서 새지 않게", has(e, "대조할 수 없다"), str(e))
e, w = errs(base(), feed=None, lenient=True)
ck("…느슨 모드(수동 점검)에선 경고로만", e == [] and has(w, "대조할 수 없다"), str(e))
empty = A.feed_index([], NOW.date())
ck("피드 파일이 없으면(워크플로가 안 돌았다) 탈락", has(errs(base(), feed=empty)[0], "피드 파일이 없다"))
sb = base(); sb["sources"][0]["url"] = "https://www.seoul.co.kr/news/2026/09/30/20260930500123"
e, w = errs(sb, feed=FEED)
ck("피드에 없는 기사(검색으로만 본 것)는 탈락", has(e, "피드에 없는 기사"), str(e))
ck("…느슨 모드에선 경고로만", errs(sb, feed=FEED, lenient=True)[0] == []
   and has(errs(sb, feed=FEED, lenient=True)[1], "피드에 없는 기사"))
_allow = A.FEED_ALLOW_DOMAINS
A.FEED_ALLOW_DOMAINS = ("seoul.co.kr",)
ck("허용 도메인(루틴이 실제로 열 수 있는 곳)이면 피드 밖도 받는다 — 지금 목록은 비어 있다",
   not has(errs(sb, feed=FEED)[0], "피드에 없는 기사") and _allow == ())
A.FEED_ALLOW_DOMAINS = _allow
sb = base(); sb["sources"][0]["url"] = "https://m.yna.co.kr/view/AKR20260930000100017?utm_source=x"
ck("주소 모양이 달라도(m.·utm) 같은 기사면 통과", errs(sb, feed=FEED)[0] == [], str(errs(sb, feed=FEED)[0]))
sb = base(published="2026-09-30T09:10:00+09:00")
ck("published_at 이 피드와 다르면 탈락", has(errs(sb, feed=FEED)[0], "피드의 '2026-09-30T08:10:00+09:00'"))
sb = base(published="2026-09-29T23:10:00Z")
ck("…같은 시각을 UTC 로 적으면 통과", errs(sb, feed=FEED)[0] == [], str(errs(sb, feed=FEED)[0]))
sb = base(); sb["sources"][0]["facts"][0] = "올해 1~8월 AI 목소리 복제 의심 신고 1,500건"
e, _ = errs(sb, feed=FEED)
ck("facts 숫자가 기사 본문에 없으면 탈락(느슨 모드도)", has(e, "숫자 1500 가 기사 본문(피드)에 없다")
   and has(errs(sb, feed=FEED, lenient=True)[0], "기사 본문"), str(e))
sb = base(); sb["sources"][0]["facts"][0] = "올해 1~8월 AI 목소리 복제 의심 신고 1245건, 작년 같은 기간의 3배"
ck("쉼표 없는 1245 = 본문의 1,245", errs(sb, feed=FEED)[0] == [], str(errs(sb, feed=FEED)[0]))
ck("피드 대조는 전각 숫자도 같게 본다(NFKC)", A._feed_nums("１，２４５건 ４．５％") == {"1245", "4.5"})
sb = base(); sb["sources"][0]["facts"][0] = "2026년 1~8월 AI 목소리 복제 의심 신고 1,245건, 작년의 3배"
ck("기사 날짜의 연도(2026)는 본문에 없어도 된다('올해')", errs(sb, feed=FEED)[0] == [], str(errs(sb, feed=FEED)[0]))
sb = base(); sb["sources"][0]["title"] = "AI 목소리 복제 신고 5배"
ck("출처 title 의 숫자도 본문 대조", has(errs(sb, feed=FEED)[0], "숫자 5 가"))
old_ver = feed_item(URL, "2026-09-30T08:10:00+09:00", ART + " 피해액은 42억원이다.")
two = A.feed_index([("2026-09-30_am.json", {"items": [feed_item(URL, "2026-09-30T08:10:00+09:00", ART)]}),
                    ("2026-09-29_pm.json", {"items": [old_ver]})], NOW.date())
sb = base(); sb["sources"][0]["facts"].append("피해액은 42억원")
ck("같은 기사의 이전 판(다른 파일) 본문도 대조에 쓴다", errs(sb, feed=two)[0] == [] and two["files"][0] == "2026-09-30_am.json",
   str(errs(sb, feed=two)[0]))
sample_p = os.path.join(ROOT, "docs", "samples", "2026-01-01_ai_am_storyboard.json")
with open(sample_p, encoding="utf-8") as f:
    sample = json.load(f)
e, w = A.check(sample, sample_p, now=NOW, history=[], lenient=True, feed=None)
ck("견본 대본(수동 점검 기본값)은 느슨 모드에서 여전히 통과(경고만)", e == [] and has(w, "대조할 수 없다"), str(e))
e, _ = A.check(sample, sample_p, now=NOW, history=[], lenient=True, feed=FEED)
ck("…피드가 있어도 견본 주소는 경고로만", e == [], str(e))

print("\n── 11. 피드 읽기 —파일 고르기·후보 목록·본문 보기 ──")
with tempfile.TemporaryDirectory() as td:
    PM_URL = "https://www.aitimes.com/news/articleView.html?idxno=215817"
    docs = {
        "2026-09-30_am.json": [feed_item(URL, "2026-09-30T08:10:00+09:00", ART, "AI 목소리 복제 보이스피싱 신고 3배")],
        "2026-09-29_pm.json": [feed_item(PM_URL, "2026-09-29T18:22:02+09:00", "배경훈 장관 독파모 " * 20,
                                         "배경훈 장관 “독파모 계속된다”", "AI타임스"),
                               feed_item("https://www.msit.go.kr/bbs/view.do?nttSeqNo=1", "2026-09-28T09:00:00+09:00",
                                         "과기정통부 보도자료 " * 20, "오래된 보도자료", "과학기술정보통신부", True)],
        "2026-09-20_am.json": [feed_item("https://old.example/1", "2026-09-20T08:00:00+09:00", "x" * 300, "아주 옛날")],
    }
    for name, its in docs.items():
        with open(os.path.join(td, name), "w", encoding="utf-8") as f:
            json.dump({"generated_at": f"{name[:10]}T09:40:00+09:00", "items": its}, f, ensure_ascii=False)
    fd = A.load_feed(NOW, refs=(), dirs=[td])
    ck("최근 4일 파일만 · 최신 먼저", fd["files"] == ["2026-09-30_am.json", "2026-09-29_pm.json"], str(fd["files"]))
    cands = A.feed_candidates(fd, NOW)
    ck("후보 = 48시간 안 기사만(50시간 전 보도자료 제외) · 최신 순", [c["url"] for c in cands] == [URL, PM_URL],
       str([c["url"] for c in cands]))
    ck("14일 안 다룬 기사는 후보에서 뺀다", [c["url"] for c in A.feed_candidates(fd, NOW, [A.norm_url(URL)])] == [PM_URL])
    txt, n = A.feed_listing(fd, NOW)
    ck("목록: id·매체·제목", n == 2 and f"[{A.feed_id(URL)}]" in txt and "AI타임스" in txt and "독파모 계속된다" in txt, txt)
    ck("…이번 슬롯 파일이 있으면 경고 없음", "아직 없다" not in txt)
    txt, _ = A.feed_listing(fd, dt.datetime(2026, 9, 30, 19, 7, tzinfo=A.KST))
    ck("…저녁 편인데 저녁 파일이 없으면(워크플로 지연) 직전 파일로 대신한다고 알린다",
       "2026-09-30_pm.json)이 아직 없다" in txt, txt)
    txt, n = A.feed_listing(A.feed_index([], NOW.date()), NOW)
    ck("…피드가 없으면 ❌ + 올리지 않는다고 안내", n == 0 and "❌" in txt and "올리지 않고" in txt)
    shown = A.feed_show(fd, A.feed_id(URL))
    ck("--show: 본문 + 출처 뼈대(published_at 그대로)", shown and ART in shown
       and '"published_at": "2026-09-30T08:10:00+09:00"' in shown and '"url": "' + URL in shown, shown)
    ck("--show: 주소로도 찾는다 · 없는 id 는 None", A.feed_show(fd, PM_URL) and A.feed_show(fd, "zzzzzzzz") is None)
    ck("id 는 주소 모양이 달라도 같다", A.feed_id("https://m.yna.co.kr/view/AKR20260930000100017/?utm_source=a")
       == A.feed_id(URL))
    r = subprocess.run([sys.executable, os.path.join(HERE, "ai_news.py"), "feed", "--dir", td, "--no-fetch",
                        "--now", "2026-09-30T10:07:00+09:00"], capture_output=True, text=True, encoding="utf-8")
    ck("CLI: feed --dir 가 목록을 찍는다(종료코드 0)", r.returncode == 0 and "독파모" in r.stdout, r.stdout[-300:] + r.stderr[-300:])

print("\n── 12. 피드 만들기(ai_news_feed.py) — 네트워크 없이 가짜 응답으로 ──")
import ai_news_feed as FE  # noqa: E402
import io as _io  # noqa: E402
import zipfile as _zip  # noqa: E402

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>테스트</title>
<item><title><![CDATA[AI 목소리 복제 보이스피싱 신고 3배]]></title>
 <link><![CDATA[https://news.test/view.do?a=1&amp;b=2]]></link>
 <pubDate>Wed, 30 Sep 2026 08:10:00 +0900</pubDate>
 <description><![CDATA[경찰청은 AI 목소리 복제 신고가 늘었다고 밝혔다.]]></description></item>
<item><title>반도체 수출 늘었다</title><link>https://news.test/2</link>
 <pubDate>Wed, 30 Sep 2026 07:00:00 +0900</pubDate><description>수출이 늘었다&nbsp;발표 &middot; 산업부</description></item>
<item><title>AI 사흘 지난 기사</title><link>https://news.test/3</link>
 <pubDate>Sun, 27 Sep 2026 07:00:00 +0900</pubDate><description>AI</description></item>
<item><title>Thai food said to be great</title><link>https://news.test/4</link>
 <pubDate>Wed, 30 Sep 2026 07:30:00 +0900</pubDate><description>food</description></item>
<item><title>AI 요약만 있는 기사</title><link>https://news.test/5</link>
 <pubDate>Wed, 30 Sep 2026 06:00:00 +0900</pubDate><description>짧은 요약</description></item>
</channel></rss>"""
ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Lab</title>
<entry><title>Introducing a safer model</title><link rel="alternate" href="https://lab.test/news/safer"/>
 <published>2026-09-29T22:00:00Z</published>
 <summary>We are releasing a new model for everyone with stronger safety checks and 40% fewer errors on hard tasks today.</summary></entry>
<entry><title>Long post</title><link href="https://lab.test/news/long"/><updated>2026-09-30T00:30:00+00:00</updated>
 <content type="html">&lt;p&gt;LONG&lt;/p&gt;</content></entry>
</feed>""".replace("LONG", "The new assistant answers questions in 12 languages. " * 30)
PAGE = """<html><head><meta property="article:published_time" content="2026-09-30T08:10:00+09:00">
<script>var t = "AI AI AI";</script><title>제목</title></head><body><div class="header">메뉴 로그인</div>
<div id="article-view-content-div">
<p>(서울=연합뉴스) 경찰청은 올해 1~8월 AI 목소리 복제 의심 신고가 1,245건으로 작년 같은 기간의 3배라고 30일 밝혔다.</p>
<p>경찰은 목소리 3초 분량이면 복제할 수 있다며, 가족끼리 암호를 정해 두라고 당부했다. 인공지능을 이용한 사기는
갈수록 정교해지고 있어 모르는 번호로 걸려 온 가족의 다급한 목소리는 일단 의심해야 한다고 경찰은 설명했다.
특히 돈을 보내 달라는 전화라면 끊고 가족에게 직접 다시 걸어 확인하는 것이 가장 확실한 방법이라고 덧붙였다.</p>
<script>Util.copyToClipboardToast(selector, '', url);</script>
<ul class="related"><li><a href="/9">관련기사 AI에 99조원 투자</a></li></ul>
<p><a href="/8">다른 기사 77만 명 몰렸다</a> 2026.09.23</p>
<p>저작권자 © 테스트 무단전재 및 재배포 금지</p>
</div><div class="footer">© 2026 테스트</div></body></html>"""
LD = ('<html><head><script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage"},'
      '{"@type":"NewsArticle","datePublished":"2026-09-30T09:00:00+09:00","articleBody":"' + "생성형 AI 규칙이 바뀐다. " * 20
      + '"}]}</script></head><body><div class="menu">x</div></body></html>')


def odt_bytes(text_xml):
    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", '<?xml version="1.0" encoding="UTF-8"?><office:document-content '
                   'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                   'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text>'
                   + text_xml + "</office:text></office:body></office:document-content>")
    return buf.getvalue()


class FakeHttp:
    def __init__(self, pages, blocked=()):
        self.pages, self.blocked, self.calls = pages, set(blocked), []

    def get(self, url, data=None, referer=""):
        self.calls.append((url, data))
        if url in self.blocked:
            raise PermissionError("robots.txt 가 막는다")
        key = (url, data) if data else url
        if key not in self.pages:
            raise OSError("404")
        b = self.pages[key]
        return url, (b if isinstance(b, bytes) else b.encode("utf-8")), "text/html; charset=utf-8"


es = FE.parse_feed(RSS.encode("utf-8"))
ck("RSS: CDATA 주소의 &amp; 를 푼다", es[0]["url"] == "https://news.test/view.do?a=1&b=2", es[0]["url"])
ck("RSS: pubDate(RFC 822) → 시간대 있는 시각", es[0]["published"] == dt.datetime(2026, 9, 30, 8, 10, tzinfo=A.KST))
ck("RSS: XML 에 없는 HTML 엔터티(&nbsp;)도 죽지 않는다", "수출이 늘었다" in FE.html_to_text(es[1]["body"]))
ea = FE.parse_feed(ATOM, FE.UTC)
ck("Atom: link href · published(Z) · content(HTML 이스케이프)",
   ea[0]["url"] == "https://lab.test/news/safer" and ea[0]["published"].utcoffset() == dt.timedelta(0)
   and "12 languages" in FE.html_to_text(ea[1]["body"]))
ck("시간대 없는 날짜 → 그 피드의 기본 시간대(국내=KST)",
   FE.parse_date("2026-09-30 18:22:02") == dt.datetime(2026, 9, 30, 18, 22, 2, tzinfo=A.KST)
   and FE.parse_date("Wed, 30 Sep 2026 20:53:47 +09:00") == dt.datetime(2026, 9, 30, 20, 53, 47, tzinfo=A.KST))
ck("AI 판별: 'AI'·인공지능 O · Thai·said X", FE.is_ai("AI 목소리 복제") and FE.is_ai("생성형 인공지능 규칙")
   and not FE.is_ai("Thai food said to be great") and not FE.is_ai("반도체 수출", "AI 한 번"))
art = FE.extract_article(PAGE)
ck("본문 칸: 기사 문단만 — 숫자·문장 그대로", "1,245건" in art["text"] and "3초 분량" in art["text"], art["text"])
ck("…스크립트·메뉴·관련 기사 링크 줄·저작권 줄은 뺀다",
   not any(x in art["text"] for x in ("Util.copy", "메뉴", "99조원", "77만", "저작권자", "AI AI AI")), art["text"])
ck("…게시 시각 메타도 읽는다", art["published"] == "2026-09-30T08:10:00+09:00")
ld = FE.extract_article(LD)
ck("JSON-LD articleBody(@graph 안)도 읽는다", ld["how"] == "jsonld" and ld["text"].startswith("생성형 AI 규칙이"), str(ld))
ck("두 번 이스케이프된 조각·한글 문서 주석은 버린다",
   FE.html_to_text("&lt;p&gt;첫 문장&lt;/p&gt;<!--[data-hwpjson]{\"a\": 1}-->") == "첫 문장")
odt = odt_bytes('<text:h>AI 기본법 시행령</text:h><text:p>과기정통부는 시행령을<text:s/>1월 22일부터 시행한다.</text:p>')
ck("ODT 첨부(과기정통부 '기계판독용') 본문", FE.odt_text(odt) == "AI 기본법 시행령\n과기정통부는 시행령을 1월 22일부터 시행한다.",
   FE.odt_text(odt))
att = FE.odt_attachment("<a onclick=\"fn_download('55214', '2', 'odt')\">", "https://www.msit.go.kr/bbs/view.do?x=1")
ck("…게시판 페이지에서 ODT 첨부 주소를 찾는다(과기정통부만)",
   att == ("https://www.msit.go.kr/ssm/file/fileDown.do", b"atchFileNo=55214&fileOrd=2&fileBtn=A")
   and FE.odt_attachment("fn_download('1', '1', 'odt')", "https://other.test/x") is None, str(att))

SRC = [{"id": "news", "outlet": "테스트뉴스", "lang": "ko", "official": False, "ai_only": False,
        "url": "https://news.test/rss"},
       {"id": "lab", "outlet": "Lab", "lang": "en", "official": True, "ai_only": True, "url": "https://lab.test/rss"},
       {"id": "dup", "outlet": "테스트뉴스", "lang": "ko", "official": False, "ai_only": True,
        "url": "https://news.test/rss2"},
       {"id": "dead", "outlet": "죽은 피드", "lang": "ko", "official": False, "ai_only": True,
        "url": "https://dead.test/rss"},
       {"id": "gov", "outlet": "과학기술정보통신부", "lang": "ko", "official": True, "ai_only": False,
        "url": "https://www.msit.go.kr/rss"}]
GOV_RSS = ("<rss><channel><item><title>AI 기본법 시행령 시행</title>"
           "<link>https://www.msit.go.kr/bbs/view.do?sCode=user&amp;nttSeqNo=9</link>"
           "<pubDate>Wed, 30 Sep 2026 09:00:00 +0900</pubDate><description>- 부제</description></item></channel></rss>")
GOV_PAGE = "<div class='bbs_view'>자세한 내용은 첨부파일을 참고하시기 바랍니다.</div><a onclick=\"fn_download('77', '2', 'odt')\">"
GOV_ODT = odt_bytes("<text:p>" + "과기정통부는 AI 기본법 시행령을 1월 22일부터 시행한다고 밝혔다. " * 5 + "</text:p>")
http = FakeHttp({"https://news.test/rss": RSS, "https://news.test/rss2": RSS, "https://lab.test/rss": ATOM,
                 "https://news.test/view.do?a=1&b=2": PAGE, "https://www.msit.go.kr/rss": GOV_RSS,
                 "https://www.msit.go.kr/bbs/view.do?sCode=user&nttSeqNo=9": GOV_PAGE,
                 ("https://www.msit.go.kr/ssm/file/fileDown.do", b"atchFileNo=77&fileOrd=2&fileBtn=A"): GOV_ODT},
                blocked={"https://lab.test/news/safer"})
items, stats = FE.collect(NOW, SRC, http, log=lambda *a: None)
by = {it["url"]: it for it in items}
ck("48시간 안 AI 기사만(사흘 지난 것·AI 아닌 것·Thai 제외)",
   set(by) == {"https://news.test/view.do?a=1&b=2", "https://lab.test/news/safer", "https://lab.test/news/long",
               "https://www.msit.go.kr/bbs/view.do?sCode=user&nttSeqNo=9"}, str(sorted(by)))
k = by.get("https://news.test/view.do?a=1&b=2", {})
ck("피드 요약이 짧으면 기사 페이지에서 본문(숫자 그대로)", k.get("text_from") == "page" and "1,245건" in k.get("text", ""), str(k))
ck("…published_at 은 KST ISO(시간대 포함)", k.get("published_at") == "2026-09-30T08:10:00+09:00")
ck("…같은 기사가 두 피드에 있으면 하나로", sum(1 for it in items if it["url"] == k.get("url")) == 1)
ck("…id = ai_news.feed_id(주소)", k.get("id") == A.feed_id("https://news.test/view.do?a=1&b=2"))
s = by.get("https://lab.test/news/safer", {})
ck("robots 가 막은 페이지는 열지 않는다 — 공식 발표는 요약(100자↑)만이라도 남긴다",
   s.get("text_from") == "feed" and "40% fewer errors" in s.get("text", "") and s.get("official") is True
   and s.get("published_at") == "2026-09-30T07:00:00+09:00", str(s))
ck("…매체 기사는 요약뿐이면(페이지 404) 버린다", "https://news.test/5" not in by)
ck("피드 본문이 충분하면 페이지를 열지 않는다", not any(u == "https://lab.test/news/long" for u, _ in http.calls))
g_ = by.get("https://www.msit.go.kr/bbs/view.do?sCode=user&nttSeqNo=9", {})
ck("부처 보도자료: 게시판 → ODT 첨부 본문", g_.get("text_from") == "odt" and "1월 22일부터" in g_.get("text", ""), str(g_))
st = {x["id"]: x for x in stats}
ck("피드 하나가 죽어도 나머지는 간다(통계에 오류)", st["dead"]["ok"] is False and st["dead"]["error"] and st["news"]["ok"])
ck("긴 본문은 4,000자로 자른다", len(FE.trim("가나다라. " * 2000)) <= FE.TEXT_MAX)
with tempfile.TemporaryDirectory() as td:
    keep = feed_item("https://keep.test/a", "2026-09-30T06:00:00+09:00", "x" * 300, "아까 받은 기사")
    with open(os.path.join(td, "2026-09-30_am.json"), "w", encoding="utf-8") as f:
        json.dump({"items": [keep]}, f)
    for old_name in ("2026-09-26_pm.json", "2026-09-27_am.json"):
        open(os.path.join(td, old_name), "w").write("{}")
    path, doc = FE.build(td, NOW, SRC, FakeHttp(http.pages, http.blocked), log=lambda *a: None)
    ck("build: 슬롯 파일 이름 = 시계로 정한 슬롯(10:20 → 오전)", os.path.basename(path) == "2026-09-30_am.json")
    ck("…같은 슬롯 파일이 있으면 합친다(피드에서 밀려난 기사도 남게)",
       any(it["url"] == "https://keep.test/a" for it in doc["items"]) and len(doc["items"]) == len(items) + 1)
    ck("…오래된 파일은 지운다(오늘 포함 4일치만)", sorted(os.listdir(td)) == ["2026-09-27_am.json", "2026-09-30_am.json"],
       str(sorted(os.listdir(td))))
    fd = A.load_feed(NOW, refs=(), dirs=[td])
    ck("…만든 파일을 ai_news 가 그대로 읽는다", A.norm_url("https://news.test/view.do?a=1&b=2") in fd["by_url"])
ck("User-Agent 에 이름과 레포 주소를 밝힌다", FE.UA.startswith("autoSNS-ai-news-feed/") and "github.com/WB-RnD-web" in FE.UA)
ck("피드 목록: 전부 https · id 중복 없음 · 국내·해외·공식 섞임",
   all(s["url"].startswith("https://") for s in FE.SOURCES) and len({s["id"] for s in FE.SOURCES}) == len(FE.SOURCES)
   and {"ko", "en"} <= {s["lang"] for s in FE.SOURCES} and any(s["official"] for s in FE.SOURCES))

print("\n── 13. 워크플로 연결 ──")
wf = os.path.join(ROOT, ".github", "workflows")
shorts = open(os.path.join(wf, "shorts.yml"), encoding="utf-8").read()
tramp = open(os.path.join(wf, "ai-news.yml"), encoding="utf-8").read()
run = open(os.path.join(wf, "ai-news-run.yml"), encoding="utf-8").read()
ck("shorts.yml 은 routine/ai_* 를 처리하지 않는다(두 번 업로드 방지)", '"!routine/ai_*"' in shorts)
ck("ai-news.yml 은 main 의 실행 파일을 부른다(누적 브랜치의 낡은 사본 방지)",
   "ai-news-run.yml@main" in tramp and "routine/ai_am" in tramp and "routine/ai_pm" in tramp)
ck("ai-news-run.yml 은 코드를 main 에서", "ref: main" in run)
ck("…이 push 에서 ★새로 추가된 AI 대본만 고른다", "--diff-filter=A" in run)
ck("…PRESENTER 는 고정으로 끔", 'PRESENTER: "0"' in run)
ck("…INSTA_PUBLISH 가 없으면 dry-run", "INSTA_PUBLISH: ${{ vars.INSTA_PUBLISH || '0' }}" in run)
ck("…ledger 캐시 키가 쇼츠와 안 겹친다(ledger- 접두 금지)", "key: ailedger-" in run and "restore-keys: ailedger-" in run)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import find_orphan_storyboards as F  # noqa: E402
ck("미아 복구 목적지: AI 오전 → routine/ai_am",
   F.guess_topic("output/news/2026-09-30_ai_am_storyboard.json") == "ai_am")
ck("ai-news-run.yml 은 원문 피드 브랜치도 받아 온다(Actions 에서 출처를 다시 대조)",
   "for b in routine/ai_am routine/ai_pm data/ai-news-feed; do" in run)


def push_branches(text):
    """워크플로의 on.push.branches (push 트리거가 없으면 None · 브랜치 필터가 없으면 ['**'] = 전부)."""
    pats, in_on, push_ind, br_ind = None, False, None, None
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip()
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        if ind == 0:
            in_on, push_ind, br_ind = s.startswith("on:"), None, None
            continue
        if not in_on:
            continue
        if push_ind is not None and ind <= push_ind:
            push_ind = br_ind = None
        if push_ind is None:
            if s == "push:" or s.startswith("push:"):
                push_ind, pats = ind, ["**"]
            continue
        if s.startswith("branches:"):
            br_ind, pats = ind, []
        elif br_ind is not None and s.startswith("- ") and ind >= br_ind:
            pats.append(s[2:].strip().strip("\"'"))
        elif br_ind is not None and ind <= br_ind:
            br_ind = None
    return pats


def gh_match(pats, ref):
    """GitHub 브랜치 필터: * = '/' 빼고 아무거나 · ** = 아무거나 · '!' = 빼기(뒤 규칙이 이긴다)."""
    hit = False
    for p in pats or []:
        neg = p.startswith("!")
        rx = re.escape(p[1:] if neg else p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(rx, ref):
            hit = not neg
    return hit


flows ={n: open(os.path.join(wf, n), encoding="utf-8").read() for n in sorted(os.listdir(wf)) if n.endswith(".yml")}
trig = {n: push_branches(t) for n, t in flows.items()}
ck("(가드 점검) 필터 해석이 맞다: shorts 는 routine/날짜 O · routine/ai_am X · ai-news 는 routine/ai_am O",
   gh_match(trig["shorts.yml"], "routine/2026-06-26_politics") and not gh_match(trig["shorts.yml"], "routine/ai_am")
   and gh_match(trig["ai-news.yml"], "routine/ai_am")
   # korea-sounds 는 PR #97 부터 routine/korea_sounds push 로도 돈다 — 그 브랜치에만 반응해야 한다
   and gh_match(trig["korea-sounds.yml"], "routine/korea_sounds")
   and not gh_match(trig["korea-sounds.yml"], "routine/ai_am"), str(trig["shorts.yml"]))
ck("어떤 push 트리거 워크플로도 data/ai-news-feed 에 반응하지 않는다(업로드가 깨어나지 않게)",
   not [n for n, p in trig.items() if p is not None and gh_match(p, "data/ai-news-feed")],
   str([n for n, p in trig.items() if p is not None and gh_match(p, "data/ai-news-feed")]))
ck("routine/weekly_fortune(주간 띠별 운세)에 반응하는 push 워크플로는 weekly-fortune.yml 하나(shorts.yml 아님)",
   [n for n, p in trig.items() if p is not None and gh_match(p, "routine/weekly_fortune")] == ["weekly-fortune.yml"],
   str([n for n, p in trig.items() if p is not None and gh_match(p, "routine/weekly_fortune")]))
feedwf = flows.get("ai-news-feed.yml", "")
ck("ai-news-feed.yml: 루틴 30분 전 두 번(정각 피함) + 수동 실행",
   re.findall(r'cron:\s*"(\d+) (\d+) \* \* \*"', feedwf) == [("37", "0"), ("37", "9")] and "workflow_dispatch:" in feedwf)
ck("…contents: write 는 이 워크플로에만",
   [n for n, t in flows.items() if re.search(r"(?m)^\s*contents:\s*write", t)] == ["ai-news-feed.yml"])
pushes = [ln for ln in feedwf.splitlines() if "git" in ln and " push" in ln and not ln.strip().startswith("#")]
ck("…push 는 data/ai-news-feed 하나로만(main·routine/* 아님)",
   len(pushes) == 1 and 'refs/heads/$FEED_BRANCH"' in pushes[0] and "FEED_BRANCH: data/ai-news-feed" in feedwf
   and "routine/" not in pushes[0] and "main" not in pushes[0], str(pushes))
ck("…코드는 main 에서 · 테스트가 깨지면 피드를 덮어쓰지 않는다",
   "ref: main" in feedwf and "run: python3 pipeline/ai_news_feed.py build" in feedwf
   and feedwf.index("run: python3 pipeline/test_ai_news.py") < feedwf.index("run: python3 pipeline/ai_news_feed.py build"))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
