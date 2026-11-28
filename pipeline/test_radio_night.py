#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""왕별이 라디오 밤 편 — 오프라인 테스트(네트워크·자격증명 없이). ffmpeg 가 있으면 짧은 가짜 목소리 렌더까지."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import fortune_card as FC  # noqa: E402
import radio_night as N  # noqa: E402

FAIL = []


def ck(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got and not cond else ""))
    if not cond:
        FAIL.append(name)


D = dt.date(2026, 11, 28)
with open(os.path.join(ROOT, "docs", "samples", "radio_night_2026-11-28.json"), encoding="utf-8") as f:
    SAMPLE = json.load(f)

print("■ 말로 읽는 숫자")
ck("29 → 이십구 · 10 → 십 · 11 → 십일 · 31 → 삼십일",
   (N.num_ko(29), N.num_ko(10), N.num_ko(11), N.num_ko(31)) == ("이십구", "십", "십일", "삼십일"))
ck("1948 → 사십팔 · 1960 → 육십 · 1995 → 구십오", (N.yy(1948), N.yy(1960), N.yy(1995)) == ("사십팔", "육십", "구십오"))
ck("6월 = 유월 · 10월 = 시월", N.date_ko(dt.date(2026, 6, 1)) == "유월 일일" and N.date_ko(dt.date(2026, 10, 9)) == "시월 구일")

print("■ 사실(코드가 정한다)")
fa = N.facts(D)
rows = {r["animal"]: r for r in FC.build_rows(FC.make_storyboard(D + dt.timedelta(days=1)))}
ck("내일 순위·한 줄 = 다음 날 아침 표(fortune_card)와 같다",
   all(fa["ddi"][a]["rank"] == rows[a]["rank"] and fa["ddi"][a]["key"] == rows[a]["line"] for a in N.ANIMALS))
ck("순위 1~12 한 번씩 · 좋은 세 띠 = 1~3위",
   sorted(x["rank"] for x in fa["ddi"].values()) == list(range(1, 13))
   and fa["top"] == [a for a in sorted(N.ANIMALS, key=lambda a: rows[a]["rank"])[:3]])
ck("행운의 색·좋은 시간은 띠마다 다르다", len({x["color"] for x in fa["ddi"].values()}) == 12
   and len({x["time_say"] for x in fa["ddi"].values()}) == 12)
ck("같은 날은 같은 사실(다시 돌려도 같다)", N.facts(D) == fa)
ck("색은 화면 색표에 다 있다", all(c in __import__("radio_night_render").COLOR_RGB for c in N.COLORS))
ck("11/28 = 견본 이야기·옛말(의좋은 형제 · 웃는 집에 복이 온다)",
   fa["story"]["title"] == "의좋은 형제" and fa["saying"]["line"] == "웃는 집에 복이 온다")
days = [D + dt.timedelta(days=i) for i in range(len(N.STORIES))]
ck("이야기는 목록 길이만큼 날마다 다르다", len({N.pick_story(x)["title"] for x in days}) == len(N.STORIES))
ck("옛말도 이어진 날 같은 것이 없다", all(N.pick_saying(x) != N.pick_saying(x + dt.timedelta(days=1)) for x in days))
ck("11월 말일 → 남은 날 0 · 28일 → 이틀", N.facts(dt.date(2026, 11, 30))["days_left"] == 0 and fa["days_left"] == 2)

print("■ 목록(이야기·옛말)이 검사를 통과하는 글인가")
for s in N.STORIES:
    intro = f"오늘 이야기는 {s['title']} 이야기예요."
    if N.bad_chars(intro) or N.ban_hits(intro) or N.ban_hits(s["gist"]):
        ck(f"이야기 '{s['title']}'", False, str(N.bad_chars(intro) + N.ban_hits(intro) + N.ban_hits(s["gist"])))
ck("이야기 제목·줄거리 전부 금지어·글자 문제 없음", True)
ck("이야기 배경 프롬프트에 사람·글자 요청이 없다",
   all("no people" not in s["scene"] and "text" not in s["scene"].lower() for s in N.STORIES))
for s in N.SAYINGS:
    if N.bad_chars(s["line"], N.SCREEN_OK) or N.ban_hits(s["line"]) or N.HANJA.search(s["line"] + s["sub"]) \
            or max(len(x) for x in s["line"].split("\n")) > 16:
        ck(f"옛말 '{s['line']}'", False)
ck("옛말 전부 한글·금지어 없음·줄마다 16자 이하", True)
long_t = max(N.STORIES, key=lambda s: len(s["title"]))["title"]
ck("제일 긴 이야기 제목으로도 영상 제목 100자 이하",
   len(N.title_for({"for_label": "12월 31일 수요일", "story": long_t})) <= 100)

print("■ 견본 대본 → 검사 · 구성")
ck("견본(11/28) 검사 통과", N.check(SAMPLE, D) == [], str(N.check(SAMPLE, D)[:3]))
plan = N.compose(SAMPLE, D)
st = N.stats(plan)
ck("구성 = 안부 · 띠 소개 · 12띠 · 이야기 · 옛말 · 좋은 말 · 잘 자요",
   [p["id"] for p in plan["parts"]] == ["hello", "ddi_intro"] + [f"ddi_{a}" for a in N.ANIMALS]
   + ["story", "saying", "wish", "night"])
ck("전체 글자·예상 길이(말 15~20분)", N.LIMITS["plan_chars"][0] <= st["chars"] <= N.LIMITS["plan_chars"][1], str(st))
texts = [c["text"] for p in plan["parts"] for c in p["chunks"]]
bad = [(t, N.bad_chars(t) + N.ban_hits(t)) for t in texts if N.bad_chars(t) or N.ban_hits(t)]
ck("코드가 붙이는 말까지 전부 한글·금지어 없음", not bad, str(bad[:3]))
ck("생년을 처음과 끝에 부른다(쥐띠: 사십팔년생 … 구십육년생)",
   "사십팔년생, 육십년생, 칠십이년생, 팔십사년생, 구십육년생" in plan["parts"][2]["chunks"][0]["text"]
   and plan["parts"][2]["chunks"][-1]["text"].startswith("사십팔년생부터 구십육년생까지, 쥐띠 분들"))
ck("좋은 세 띠는 금테·'반가운 말씀'", all(
    p["chunks"][0]["slide"]["top"] == (p["id"][4:] in plan["top"])
    and ("반가운 말씀" in p["chunks"][0]["text"]) == (p["id"][4:] in plan["top"])
    for p in plan["parts"] if p["id"].startswith("ddi_") and p["id"] != "ddi_intro"))
night = [c["text"] for c in plan["parts"][-1]["chunks"]]
ck("잘 자요 파트에 빗소리 신호가 있다(렌더가 여기서 빗소리를 연다)", any("빗소리" in t for t in night))
ck("따라 하는 좋은 말 8줄 · 줄마다 5.5초 쉼",
   [c.get("pause") for c in plan["parts"][-2]["chunks"] if c["slide"]["kind"] == "wish"] == [5.5] * 8)
ck("화면 글(옛말)에 한자가 없다", not N.HANJA.search(json.dumps(plan, ensure_ascii=False)))

print("■ 검사가 막는 것")


def bad_with(fn, needle):
    sc = copy.deepcopy(SAMPLE)
    fn(sc)
    errs = N.check(sc, D)
    return any(needle in e for e in errs), errs


def setp(path, val):
    def fn(sc):
        o = sc
        for k in path[:-1]:
            o = o[k]
        o[path[-1]] = val
    return fn


cases = [
    ("숫자", setp(["ddi", "쥐", "msg"], "내일 쥐띠는 3가지 일이 술술 풀리는 날이에요. 작은 일에서 기분 좋은 일이 생겨요."), "읽기 어려운 글자"),
    ("영어", setp(["hello", 0], "오늘 하루도 참 good 하셨어요."), "읽기 어려운 글자"),
    ("순위 말(삼 위예요)", setp(["ddi", "토끼", "msg"], "내일 토끼띠는 삼 위예요. 마음에 걸려 있던 일이 스르르 풀리는 날이에요."), "순위 말"),
    ("종교 말", setp(["wish", 0], "오늘도 기도하며 잘 지냈습니다."), "종교 말"),
    ("명리 용어", setp(["ddi", "말", "msg"], "내일 말띠는 육합이 들어 귀인이 가까이 오는 날이에요. 좋은 사람을 만나요."), "명리 용어"),
    ("투자 조언", setp(["ddi", "닭", "tip"], "내일은 주식을 조금 사 보세요. 작은 행운이 따라올 거예요."), "투자"),
    ("의료 조언", setp(["ddi", "용", "tip"], "아침에 혈압약을 꼭 챙겨 드세요. 하루가 든든해요."), "의료"),
    ("다른 띠 이름", setp(["ddi", "소", "more"], "돼지띠 식구가 있으면 같이 웃어 보세요. 짐을 나눠요."), "다른 띠"),
    ("끝 인사 틀", setp(["ddi", "개", "bye"], "내일은 빈틈없이, 마음 편한 하루 되세요."), "띠 분들"),
    ("좋은 말 7줄", lambda sc: sc["wish"].pop(), "딱 8줄"),
    ("좋은 말 끝", setp(["wish", 0], "오늘 하루도 무사히 잘 지냈어요."), "니다"),
    ("이야기 제목", setp(["story", "title"], "흥부와 놀부"), "story.title"),
    ("날짜", setp(["date"], "2026-11-27"), "date"),
    ("옛말을 안 말함", setp(["saying", "lines"], ["좋은 말이 있지요.", "서로 웃으면 좋아요.", "내일 웃어 보세요.", "복이 와요."]), "그대로 말해야"),
    ("띠 글 복사", lambda sc: sc["ddi"]["양"].update(msg=sc["ddi"]["쥐"]["msg"].replace("쥐띠", "양띠")), "비슷하다"),
    ("화면 한 줄 너무 김", setp(["story", "card"], "서로 몰래 챙겨 주는 그 따뜻한 마음이야말로\n우리 집의 진짜 복"), "story.card"),
    ("띠 빠짐", lambda sc: sc["ddi"].pop("원숭이"), "ddi.원숭이: 없다"),
    ("너무 짧음", lambda sc: sc["story"].update(lines=sc["story"]["lines"][:16]), "story.lines"),
]
for name, fn, needle in cases:
    hit, errs = bad_with(fn, needle)
    ck(f"막는다 — {name}", hit, str(errs[:3]))

print("■ 잘못 막지 않는 것(낱말 속에 숨은 금지어)")
for text in ("할머니가 팥죽을 쑤어 호랑이를 기다렸어요.", "평강 공주님은 온달을 찾아갔어요.", "아궁이 위에 솥을 걸었어요.",
             "청소, 빨래, 집안일 등 할 일이 많지요.", "헉헉 숨을 고르며 산을 넘었어요.", "큰일보다 작은 일에서 기분 좋은 일이 생겨요.",
             "곶감이 그렇게 무서운 놈인가 했지요.", "손주한테 과자를 사주며 웃었어요.", "조용한 편인데도 마음이 따뜻해요.",
             "이 위에 볏단을 얹어 두었어요."):
    ck(f"통과 — '{text}'", N.ban_hits(text) == [] and N.bad_chars(text) == [], str(N.ban_hits(text)))

print("■ 업로드 글")
desc = N.description_for(plan, "00:00 안부 인사\n00:55 내일 띠별 운세\n16:14 빗소리")
ck("설명란: 피아노 출처(CC BY) · 재미로 · 입춘 기준 · 표식 끝 줄",
   "Kevin MacLeod" in desc and "creativecommons.org/licenses/by/4.0" in desc and "재미로" in desc and "입춘" in desc
   and desc.rstrip().endswith(N.marker("2026-11-28")))
ck("제목 100자 이하 · 내일 날짜·이야기·빗소리 30분", len(N.title_for(plan)) <= 100 and "11월 29일 일요일" in N.title_for(plan)
   and "의좋은 형제" in N.title_for(plan) and "빗소리 30분" in N.title_for(plan))
ck("이미 올렸나 — 설명란 표식으로", N.already_uploaded([{"description": desc, "video_id": "abc"}], D) == "abc"
   and N.already_uploaded([{"description": desc}], dt.date(2026, 11, 29)) is None)
ck("예약 공개 — 17:30 이면 그날 20:00 KST(11:00Z)",
   N.publish_at(D, dt.datetime(2026, 11, 28, 17, 30, tzinfo=N.KST)) == "2026-11-28T11:00:00Z")
ck("예약 공개 — 19:55 지나면 바로 공개(None)", N.publish_at(D, dt.datetime(2026, 11, 28, 19, 55, tzinfo=N.KST)) is None)

print("■ 화면·시간표(렌더러)")
import radio_night_render as R  # noqa: E402

wd = tempfile.mkdtemp(prefix="radio_t_")
try:
    kinds = {}
    for p in plan["parts"]:
        for c in p["chunks"]:
            kinds.setdefault(c["slide"]["kind"], c["slide"])
    kinds["rain"] = {"kind": "rain"}
    ok = True
    for k, sp in kinds.items():
        im = R.draw_slide(sp, wd)
        ok = ok and im.size == (R.W, R.H) and im.mode == "RGBA"
    ck(f"화면 {len(kinds)}가지 전부 그려진다(1920×1080 투명 판)", ok, str(sorted(kinds)))
    th = R.draw_thumbnail(plan, R.find_bg("story", [R.ASSETS]), wd)
    ck("썸네일 1280×720", th.size == (1280, 720))
    ck("배경 그림 다섯 장(hello·ddi·story·wish·night)이 레포에 있다",
       all(os.path.exists(R.find_bg(b, [R.ASSETS])) for b in ("hello", "ddi", "story", "wish", "night")))
    ck("피아노 파일·출처가 레포에 있다", os.path.exists(R.MUSIC) and os.path.exists(os.path.join(R.ASSETS, "CREDITS.md")))
    durs = {t: 2.0 for t in texts}
    items, parts, vend = R.timeline(plan, durs)
    ck("시간표: 조각 수 = 대본 조각 수 · 끝이 늘어난다", len(items) == len(texts)
       and all(items[i]["start"] < items[i + 1]["start"] for i in range(len(items) - 1)))
    ck("시간표: 좋은 말 다음 쉼 5.5초가 반영된다",
       any(abs(it["gap"] - 5.5) < 1e-6 for it in items if it["part"] == "wish"))
    ch = R.chapters(parts, vend)
    ck("목차: 00:00 으로 시작 · 빗소리로 끝", ch.startswith("00:00 안부 인사") and ch.rstrip().endswith("빗소리"))
    ck("빗소리 기본 30분", R.RAIN_MIN == 30.0 and N.RAIN_MIN == 30.0)
    _req = open(os.path.join(HERE, "requirements.txt"), encoding="utf-8").read().lower()
    _src = "".join(open(os.path.join(HERE, n), encoding="utf-8").read()
                   for n in ("radio_night.py", "radio_night_render.py", "run_radio_night.py"))
    ck("Actions 에 없는 모듈(numpy 등)을 쓰지 않는다 — requirements 에 있는 것만(11/28 시험 실행 실패)",
       all(m not in _src or m in _req for m in ("import numpy", "import cv2", "import scipy")))

    if shutil.which(R.R.FFMPEG) or os.path.exists(R.R.FFMPEG):
        print("■ 짧은 가짜 목소리 렌더(ffmpeg)")
        os.environ["WEEKLY_MOCK_TTS"] = "1"
        mini = {"date": plan["date"], "story": plan["story"], "story_scene": plan["story_scene"], "top": plan["top"],
                "for_label": plan["for_label"],
                "parts": [dict(plan["parts"][0], chunks=plan["parts"][0]["chunks"][:2]),
                          dict(plan["parts"][2], chunks=plan["parts"][2]["chunks"][:2]),
                          dict(plan["parts"][-1], chunks=plan["parts"][-1]["chunks"][-3:])]}
        old = R.RAIN_MIN
        R.RAIN_MIN = 0.5
        try:
            out = os.path.join(wd, "mini.mp4")
            info = R.render(mini, out, os.path.join(wd, "work"))
        finally:
            R.RAIN_MIN = old
        ck("mp4·썸네일·정보 파일이 생긴다", os.path.getsize(out) > 10000 and os.path.exists(info["thumb"])
           and os.path.exists(out[:-4] + "_info.json"))
        ck("전체 = 말 + 빗소리 꼬리", abs(info["total_min"] - info["voice_end_min"] - 0.5) < 0.02, str(info))
        import run_radio_night as RUN
        ck("길이 검사: 짧은 시험 영상은 막는다", RUN.check_length(info) is not None)
        ck("길이 검사: 말 16분 + 빗소리 30분은 통과",
           RUN.check_length({"voice_end_min": 16.2, "total_min": 46.2}) is None)
    else:
        print("  (ffmpeg 없음 — 렌더 시험 건너뜀)")
finally:
    shutil.rmtree(wd, ignore_errors=True)

print()
if FAIL:
    print(f"❌ 실패 {len(FAIL)}개: {FAIL}")
    sys.exit(1)
print("✅ 전부 통과")
