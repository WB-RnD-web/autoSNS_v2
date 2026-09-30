#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 소식 쇼츠(하루 두 번) 회귀 테스트 — 네트워크·자격증명 없이 돈다.

    python pipeline/test_ai_news.py

지키는 것: 출처·날짜 필수(48시간) · 14일 중복 · 슬롯 멱등(같은 슬롯 두 번 = 한 번만) ·
카테고리 28 · 재생목록 · 크로스포스트는 AI 토픽만(INSTA_PUBLISH 없으면 dry-run) ·
숫자·용어·확인 안 된 보도·캡션·형식 돌려쓰기 · 진행자 금지 · 워크플로 연결.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
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


def errs(sb, path=PATH, now=NOW, history=None, lenient=False):
    return A.check(sb, path, now=now, history=history or [], lenient=lenient)


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
         config.NEWS_DIR, config.ASSETS_DIR)


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
        paths = {}
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
        # 느슨 모드는 공개 업로드에서 무시된다
        ck("--ai-lenient 는 공개 업로드에서 무시", P.ai_lenient(SimpleNamespace(ai_lenient=True)) is False
           and P.ai_lenient(SimpleNamespace(ai_lenient=True, force_private=True)) is True)
finally:
    (P._prepare_bg, M.build_motion, M.probe_dur, P.has_credentials, P.upload_with_retry, P.add_playlist,
     A.recent_uploads, N.get_service, config.OUTPUT, config.RENDERS_DIR, config.NEWS_DIR, config.ASSETS_DIR) = _orig
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

print("\n── 10. 워크플로 연결 ──")
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

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
