#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주간 띠별 운세 풀이(weekly_fortune · weekly_fortune_render · run_weekly_fortune) 회귀 테스트.

네트워크·ffmpeg 없이 돈다(워크플로가 렌더 전에 돌린다). git 은 쓴다(루틴 push 경로를 임시 레포로 확인).

    python pipeline/test_weekly_fortune.py
"""
from __future__ import annotations

import copy
import datetime as dt
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fortune_card as FC  # noqa: E402
import weekly_fortune as WF  # noqa: E402
import weekly_fortune_render as R  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


KST = WF.KST


def at(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=KST)


with open(WF.SAMPLE, encoding="utf-8") as f:
    SAMPLE = json.load(f)
SUN = at("2026-09-27T17:00")          # 견본 주(W40, 9/28~10/4) 전날 — 루틴이 도는 시각


def errs_of(sc, now=SUN, history=None, strict=True, path=""):
    return WF.check(sc, path, now=now, history=history or [], strict=strict)[0]


def has(errs, word):
    return any(word in e for e in errs)


print("── 주 배정 ──")
ck("일 17:00 → 다음 주 월요일", WF.target_monday(at("2026-10-04T17:00")) == dt.date(2026, 10, 5))
ck("늦게 돌아 월 01:00 → 같은 주", WF.target_monday(at("2026-10-05T01:00")) == dt.date(2026, 10, 5))
ck("토요일 → 이번 주", WF.target_monday(at("2026-10-10T12:00")) == dt.date(2026, 10, 5))
ck("일 23:59 → 다음 주", WF.target_monday(at("2026-10-11T23:59")) == dt.date(2026, 10, 12))
ck("주 번호 ↔ 월요일", WF.week_key(dt.date(2026, 10, 5)) == "2026-W41" and WF.monday_of("2026-W41") == dt.date(2026, 10, 5))
ck("해가 바뀌는 주(ISO)", WF.week_key(dt.date(2026, 12, 28)) == "2026-W53" and WF.monday_of("2027-W01") == dt.date(2027, 1, 4))
ck("잘못된 주 번호는 None", WF.monday_of("2026-41") is None and WF.monday_of("2026-W99") is None)
ck("파일 이름 = 월요일 날짜", WF.file_name(dt.date(2026, 10, 5)) == "2026-10-05_weekly_fortune.json"
   and WF.NAME_RE.match("2026-10-05_weekly_fortune.json"))
ck("날짜 범위(달이 바뀌면 달을 다시 쓴다)", WF.range_label(dt.date(2026, 9, 28)) == "9월 28일(월) ~ 10월 4일(일)"
   and WF.range_label(dt.date(2026, 10, 5), short=True) == "10월 5일~11일")
ck("출력 경로가 shorts.yml(output/news/**_storyboard.json)과 겹치지 않는다",
   not WF.OUT_DIR.startswith("output/news") and not WF.file_name(dt.date(2026, 10, 5)).endswith("_storyboard.json"))

print("── 공개 시각(일 20:00 KST 예약) ──")
ck("일 17:40 에 렌더 끝 → 그날 20:00 KST = 11:00Z",
   WF.publish_at(dt.date(2026, 10, 5), at("2026-10-04T17:40")) == "2026-10-04T11:00:00Z")
ck("이미 20:00 이 지났으면 바로 공개(None)", WF.publish_at(dt.date(2026, 10, 5), at("2026-10-04T20:30")) is None)
ck("10분 안이면 바로 공개", WF.publish_at(dt.date(2026, 10, 5), at("2026-10-04T19:55")) is None)
ck("시각 바꾸기(WEEKLY_PUBLISH_HHMM)", WF.publish_at(dt.date(2026, 10, 5), at("2026-10-04T12:00"), "19:30")
   == "2026-10-04T10:30:00Z")

print("── 순위표(매일 표와 같은 방식 · 씨앗은 주 번호) ──")
rows = WF.table_rows("2026-W41")
ck("12띠 · 1~12위 한 번씩", sorted(r["animal"] for r in rows) == sorted(WF.ANIMALS)
   and [r["rank"] for r in rows] == list(range(1, 13)))
ck("점수는 내려간다", all(a["score"] > b["score"] for a, b in zip(rows, rows[1:])), [r["score"] for r in rows])
ck("같은 주면 늘 같은 표", rows == WF.table_rows("2026-W41"))
ck("주가 바뀌면 표도 바뀐다", [r["animal"] for r in rows] != [r["animal"] for r in WF.table_rows("2026-W42")])
mon_daily = FC.build_rows({"topic": "fortune", "date": "2026-10-05"})
ck("월요일 하루 표와 똑같지 않다", [r["animal"] for r in rows] != [r["animal"] for r in mon_daily])
ck("매일 표(기본 씨앗 = 날짜)는 그대로", mon_daily == FC.build_rows({"topic": "fortune", "date": "2026-10-05"}, key=None)
   and FC.build_rows({"date": "2026-10-05"}, key=dt.date(2026, 10, 5)) == FC.build_rows({"date": "2026-10-05"}))
ck("출생연도 라벨", WF.years_label("쥐") == "48·60·72·84·96년생" and WF.years_spoken("소").startswith("49년생, 61년생"))

print("── 견본 대본(검사 통과) ──")
e, w = WF.check(SAMPLE, "", now=SUN, history=[])
ck("견본은 엄격 검사도 통과(그 주 전날 기준)", e == [], e)
e, w = WF.check(SAMPLE, WF.SAMPLE, now=at("2026-10-18T17:00"), strict=False)
ck("느슨 모드: 지난 주·파일 이름은 경고로만", e == [] and any("이번에 쓸 주" in x for x in w)
   and any("파일 이름" in x for x in w), (e, w))
ck("엄격 모드: 지난 주면 실패", has(errs_of(SAMPLE, now=at("2026-10-18T17:00")), "이번에 쓸 주"))
plan = WF.compose(SAMPLE)
st = plan["stats"]
ck("견본 예상 길이 8~12분", WF.EST_MIN[0] <= st["est_min"] <= WF.EST_MIN[1], st)
ck("파트 = 인트로 + 12장 + 마무리", [p["id"] for p in plan["parts"]] == ["intro"] + [f"ch{i:02d}" for i in range(1, 13)] + ["outro"])
ch1 = plan["parts"][1]
ck("장 순서 쥐→돼지", [p.get("animal") for p in plan["parts"][1:13]] == WF.ANIMALS)
ck("장마다 7조각(띠·한 줄·금전·건강·사람/가족·행운·조심)", all(len(p["chunks"]) == 7 for p in plan["parts"][1:13]))
ck("장 첫 조각: 띠·출생연도·순위(코드가 말한다)", ch1["chunks"][0]["text"].startswith("쥐띠입니다. 48년생")
   and f"{ch1['rank']}위" in ch1["chunks"][0]["text"])
ck("섹션 순서", [c["slide"].get("key") or c["slide"]["kind"] for c in ch1["chunks"]]
   == ["card", "card", "money", "health", "people", "lucky", "caution"])
ck("행운 문장", ch1["chunks"][5]["text"] == "행운의 요일은 목요일, 행운의 색은 노란색이에요.")
ck("마무리: 매일 아침 8초 표 안내 + '재미로' 고지를 코드가 말한다",
   "매일 아침 여섯 시" in plan["parts"][-1]["chunks"][-1]["text"] and "재미로" in plan["parts"][-1]["chunks"][-1]["text"])
ck("장 제목(유튜브 챕터)", ch1["title"] == f"쥐띠 (48·60·72·84·96년생) · {ch1['rank']}위")

print("── 검사가 막는 것 ──")


def mut(fn):
    sc = copy.deepcopy(SAMPLE)
    fn(sc)
    return sc


ck("11장이면 실패", has(errs_of(mut(lambda s: s["chapters"].pop())), "12장"))
ck("순서가 바뀌면 실패", has(errs_of(mut(lambda s: s["chapters"].insert(0, s["chapters"].pop(1)))), "순서"))
ck("'쥐띠'·'범' 같은 표기는 받아 준다", errs_of(mut(lambda s: (s["chapters"][0].update(animal="쥐띠"),
                                                     s["chapters"][2].update(animal="범")))) == [])
ck("칸이 너무 길면 실패", has(errs_of(mut(lambda s: s["chapters"][3].update(money="돈이 들어와요. " * 20))), "money"))
ck("칸이 비면 실패", has(errs_of(mut(lambda s: s["chapters"][3].update(health=""))), "health"))
ck("요일이 틀리면 실패 · '수' 는 수요일로", has(errs_of(mut(lambda s: s["chapters"][0].update(lucky_day="주말"))), "lucky_day")
   and errs_of(mut(lambda s: s["chapters"][0].update(lucky_day="목"))) == [])
ck("색 목록 밖이면 실패", has(errs_of(mut(lambda s: s["chapters"][0].update(lucky_color="무지개색"))), "lucky_color"))
ck("요일이 한두 가지로 몰리면 실패", has(errs_of(mut(lambda s: [c.update(lucky_day="월요일") for c in s["chapters"]])), "요일이"))
ck("색이 한두 가지로 몰리면 실패", has(errs_of(mut(lambda s: [c.update(lucky_color="금색") for c in s["chapters"]])), "색이"))
ck("숫자는 한글로(읽는 글에 숫자 금지)", has(errs_of(mut(lambda s: s["chapters"][1].update(
    caution="3일 동안은 큰 약속을 잡지 마세요. 몸이 먼저예요."))), "쓸 수 없는 글자"))
ck("영어·이모지·주소 금지", has(errs_of(mut(lambda s: s["chapters"][1].update(
    people="가족과 함께 웃을 일이 생겨요 🙂 자세한 건 youtu.be 에서"))), "쓸 수 없는 글자"))
for word, field in (("주식", "money"), ("대박", "headline"), ("치료", "health"), ("로또", "money"), ("부적", "caution")):
    ck(f"금지어 '{word}'", has(errs_of(mut(lambda s, w_=word, f_=field: s["chapters"][4].update(
        {f_: (s["chapters"][4][f_] + f" {w_} 이야기는 넘기세요.")[:80]}))), "금지어"))
ck("'암' 은 병 이름일 때만(암호·명암은 괜찮다)", bool(WF.ban_hits("암이 걱정되면")) and not WF.ban_hits("암호를 바꾸세요")
   and not WF.ban_hits("명암이 갈려요"))
rank = {r["animal"]: r["rank"] for r in WF.table_rows(SAMPLE["week"])}
low = next(a for a in WF.ANIMALS if rank[a] > 3)
ck("인트로가 4위 아래 띠를 부르면 실패(표와 어긋나는 말)",
   has(errs_of(mut(lambda s: s.update(intro=s["intro"] + f" {low}띠도 좋아요."))), "intro 가"))
ck("제목 훅도 1~3위만 부른다", has(errs_of(mut(lambda s: s.update(title_hook=f"{low}띠 웃는 한 주"))), "title_hook 가"))
ck("rank 를 적었다면 순위표와 같아야", has(errs_of(mut(lambda s: s["chapters"][0].update(rank=12))), "rank"))
ck("다른 띠 칸을 복사하면 실패", has(errs_of(mut(lambda s: s["chapters"][5].update(money=s["chapters"][4]["money"]))), "거의 같다"))
nxt = mut(lambda s: s.update(week="2026-W41"))
ck("견본·지난 대본을 옮겨 적으면 실패", has(errs_of(nxt, now=at("2026-10-04T17:00"), history=[{**SAMPLE, "_sample": True}]),
                                     "견본"))
ck("같은 주 이력(방금 올린 자기 자신)은 비교하지 않는다", errs_of(SAMPLE, history=[SAMPLE]) == [])
short = mut(lambda s: [c.update(headline=c["headline"][:11], money=c["money"][:31], health=c["health"][:31],
                                people=c["people"][:31], caution=c["caution"][:21]) for c in s["chapters"]])
ck("장이 너무 짧으면 실패(40~50초)", has(errs_of(short), "장이"))
ck("전체가 8분 안 되면 실패", has(errs_of(short), "예상 길이"))
ck("title_hook 24자 넘으면 실패", has(errs_of(mut(lambda s: s.update(title_hook="가" * 25))), "title_hook"))
ck("파일 이름 날짜가 주와 다르면 실패", has(errs_of(SAMPLE, path="output/weekly_fortune/2026-10-05_weekly_fortune.json"),
                                    "파일 이름 날짜"))
ck("JSON 객체가 아니면 실패", WF.check([], "", now=SUN)[0] != [])

print("── 화면 · 타임라인 · 목차(ffmpeg 없이) ──")
durs = {c["text"]: max(1.0, len(c["text"]) / 7.8) for p in plan["parts"] for c in p["chunks"]}
items, parts, total = R.timeline(plan, durs)
ck("첫 챕터 00:00", parts[0]["card"] == 0.0)
ck("조각은 겹치지 않는다", all(a["end"] <= b["start"] + 1e-9 for a, b in zip(items, items[1:])))
ck("장 카드는 쉼이 시작될 때(목소리보다 먼저)", all(p["card"] < next(i["start"] for i in items if i["part"] == p["id"])
                                         for p in parts[1:]))
segs = R.segments(items, total)
ck("화면 구간이 처음부터 끝까지 이어진다", segs[0][1] == 0.0 and abs(segs[-1][2] - total) < 1e-6
   and all(abs(a[2] - b[1]) < 1e-6 for a, b in zip(segs, segs[1:])))
ck("같은 화면은 한 구간(장 카드 = 이름 + 한 줄)", len(segs) == len(items) - 12 - 1 - (len(plan["parts"][-1]["chunks"]) - 1),
   (len(segs), len(items)))
chap = R.chapters_text(parts)
lines = chap.splitlines()
secs = [int(x.split()[0].split(":")[0]) * 60 + int(x.split()[0].split(":")[1]) for x in lines]
ck("유튜브 챕터: 00:00 시작 · 14개 · 10초 이상 간격", lines[0].startswith("00:00 ") and len(lines) == 14
   and all(b - a >= 10 for a, b in zip(secs, secs[1:])), chap)
ck("챕터 제목에 띠·출생연도", lines[1].split(" ", 1)[1].startswith("쥐띠 (48·60"))
ck("한 시간 넘으면 h:mm:ss", R._ts(3725) == "1:02:05" and R._ts(65) == "01:05")
kinds = {}
for p in plan["parts"]:
    for c in p["chunks"]:
        kinds.setdefault(c["slide"]["kind"], c["slide"])
ok = True
for k, sp in kinds.items():
    im = R.draw_slide(plan, sp)
    ok = ok and im.size == (R.W, R.H)
ck("화면 6종(제목·표·장 카드·섹션·행운·마무리)을 1920×1080 으로 그린다",
   ok and set(kinds) == {"title", "table", "card", "section", "lucky", "outro"}, sorted(kinds))
ck("썸네일 1280×720", R.draw_thumbnail(plan).size == (1280, 720))
ck("띠 그림 12장이 레포에 있다(작게)", all(os.path.exists(R.asset_path(a)) and os.path.getsize(R.asset_path(a)) < 150_000
                                   for a in WF.ANIMALS))
_saved_assets = R.ASSETS
R.ASSETS = os.path.join(tempfile.gettempdir(), "no_such_zodiac_dir")
try:
    ck("그림 파일이 없어도 이름 원으로 그린다(렌더를 멈추지 않는다)",
       R.ensure_animal("원숭이", None) is None and R.animal_tile("원숭이", 120, None).size == (120, 120))
finally:
    R.ASSETS = _saved_assets
with tempfile.TemporaryDirectory() as td:
    got, stt = R.synth(["첫 문장이에요.", "두 번째 문장이에요.", "첫 문장이에요."], td, tts=lambda t, o, v: R.mock_tts(t, o),
                       clean=False)
    ck("목소리: 같은 글은 한 번만 · 한 건씩(기본 WORKERS=1)", len(got) == 2 and stt["clips"] == 2 and R.WORKERS == 1)
    calls = []
    R.RETRY_WAIT = 0

    def flaky(t, o, v):
        calls.append(t)
        return False
    try:
        R.synth(["가" * 5, "나" * 5, "다" * 5, "라" * 5], os.path.join(td, "b"), tts=flaky, clean=False)
        ck("실패가 많으면 멈춘다(목소리가 섞이지 않게)", False)
    except RuntimeError:
        ck("실패가 많으면 멈춘다(목소리가 섞이지 않게)", True)

print("── 업로드 메타 ──")
title = WF.title_for(plan)
ck("제목: '이번 주 띠별 운세' + 날짜 + 100자 이내", title.startswith("이번 주 띠별 운세 9월 28일~10월 4일") and len(title) <= 100, title)
desc = WF.description_for(plan, chap, "PLabc")
ck("설명: 목차(00:00)·8초 표 안내·재생목록 링크·'재미로' 고지·표식", "⏱ 목차\n00:00" in desc and "8초짜리" in desc
   and "list=PLabc" in desc and "재미로 보는 운세" in desc and desc.rstrip().endswith(WF.marker("2026-W40")))
ck("설명 5,000자 이내", len(desc) <= 5000)
ck("카테고리 24 · 합성 표시 안 함(운세 쇼츠와 같은 관례)", WF.CATEGORY == "24" and WF.SYNTHETIC is False)
try:
    import run_pipeline as P
    ck("…run_pipeline 의 운세 판정과 같다", P.category_for("fortune") == WF.CATEGORY
       and P.synthetic_label({"topic": "fortune"}, {"_bg": "x"}) is WF.SYNTHETIC
       and P.FORTUNE_PLAYLIST == WF.DAILY_PLAYLIST)
except ImportError as e:  # pragma: no cover
    P = None
    ck("…run_pipeline 을 불러올 수 있다", False, str(e))
ck("유튜브 쪽 중복 판정(설명란 표식)", WF.already_uploaded([{"description": "x\n주간 띠별 운세 2026-W40", "video_id": "v1"}],
                                                   "2026-W40") == "v1"
   and WF.already_uploaded([{"description": "주간 띠별 운세 2026-W39"}], "2026-W40") is None)


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class FakeYT:
    """playlists.list · playlistItems.list · videos.insert 만 흉내 낸다(호출 수 = 쿼터 확인)."""

    def __init__(self, playlists=(), items=()):
        self._pl, self._items, self.calls, self.body = list(playlists), list(items), [], None

    def playlists(self):
        return self

    def playlistItems(self):
        return self

    def videos(self):
        return self

    def list(self, **kw):
        self.calls.append(kw)
        if "mine" in kw:
            return _Req({"items": [{"id": pid, "snippet": {"title": t}} for pid, t in self._pl]})
        return _Req({"items": self._items})

    def insert(self, part=None, body=None, media_body=None):
        self.body = body
        outer = self

        class _Up:
            def next_chunk(self_inner):
                return None, {"id": "NEWVID"}
        outer.calls.append({"insert": part})
        return _Up()


def _it(vid, when, privacy):
    return {"status": {"privacyStatus": privacy}, "contentDetails": {"videoId": vid, "videoPublishedAt": when},
            "snippet": {"resourceId": {"videoId": vid}}}


yt = FakeYT([("PL1", "다른 목록"), ("PLW", WF.PLAYLIST)],
            [_it("old", "2026-09-27T11:00:00Z", "public"), _it("new", "2026-10-04T11:00:00Z", "public"),
             _it("sched", "2026-10-11T11:00:00Z", "private")])
ck("최신 공개 주간 영상(예약 전 비공개는 건너뜀)", WF.latest_public_video(yt) == "new")
ck("…쿼터 2~3 units(목록 1 + 항목 1)", len(yt.calls) == 2, yt.calls)
ck("재생목록이 없으면 None", WF.latest_public_video(FakeYT([("PL1", "다른 목록")])) is None)
ck("공개 영상이 없으면 None", WF.latest_public_video(FakeYT([("PLW", WF.PLAYLIST)], [_it("s", "2026-10-11", "private")])) is None)

print("── 매일 운세 쇼츠 → 주간 롱폼 링크 ──")
base_desc = FC.meta({"topic": "fortune", "date": "2026-10-05"})["description"] + "\n\n🎙️ Voice: Supertonic"
d2 = WF.append_link(base_desc, "VID1")
ck("설명 형식은 그대로, 맨 끝에 한 줄만", d2.startswith(base_desc) and d2[len(base_desc):] == "\n\n" + WF.link_line("VID1")
   and d2.count("\n") == base_desc.count("\n") + 2)
ck("두 번 붙이지 않는다 · 영상이 없으면 그대로", WF.append_link(d2, "VID1") == d2 and WF.append_link(base_desc, None) == base_desc)
if P is not None:
    import upload_youtube_novel as N
    _gs, _lp = N.get_service, WF.latest_public_video
    N.get_service = lambda: yt
    try:
        m = {"description": base_desc}
        ck("운세 쇼츠: 링크를 붙인다", P.add_weekly_link(m, "fortune") == "new" and m["description"].endswith("youtu.be/new"))
        m2 = {"description": "정치"}
        ck("다른 토픽(정치·AI·별자리)은 건드리지 않는다", P.add_weekly_link(m2, "politics") is None
           and P.add_weekly_link(m2, "horoscope") is None and m2["description"] == "정치")
        os.environ["WEEKLY_LINK"] = "0"
        m3 = {"description": base_desc}
        ck("WEEKLY_LINK=0 이면 끈다", P.add_weekly_link(m3, "fortune") is None and m3["description"] == base_desc)
        os.environ.pop("WEEKLY_LINK")

        def boom():
            raise RuntimeError("토큰 없음")
        N.get_service = boom
        m4 = {"description": base_desc}
        ck("조회가 실패해도 조용히 넘어간다(업로드는 계속)", P.add_weekly_link(m4, "fortune") is None and m4["description"] == base_desc)
    finally:
        N.get_service, WF.latest_public_video = _gs, _lp
    src = inspect.getsource(P.process)
    ck("process: 업로드 ★전에 링크를 붙인다(업로드 뒤 수정은 50 units)",
       0 < src.find("add_weekly_link(meta") < src.find("upload_with_retry("))

print("── 롱폼 업로드 본문(카테고리·언어·아동용·예약) ──")
import upload_youtube_novel as N  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    vf = os.path.join(td, "v.mp4")
    with open(vf, "wb") as f:
        f.write(b"\x00" * 2048)
    fy = FakeYT()
    vid = N.upload_video(fy, vf, "t", "d", "public", ["운세"], WF.CATEGORY, default_language="ko",
                         synthetic=WF.SYNTHETIC, audio_language="ko", publish_at="2026-10-04T11:00:00Z")
    b = fy.body
ck("videos.insert: 카테고리 24 · ko · 오디오 ko · 아동용 아님 · 합성 False",
   vid == "NEWVID" and b["snippet"]["categoryId"] == "24" and b["snippet"]["defaultLanguage"] == "ko"
   and b["snippet"]["defaultAudioLanguage"] == "ko" and b["status"]["selfDeclaredMadeForKids"] is False
   and b["status"]["containsSyntheticMedia"] is False, b)
ck("예약 공개면 비공개 + publishAt", b["status"]["privacyStatus"] == "private" and b["status"]["publishAt"] == "2026-10-04T11:00:00Z")
ck("오디오 언어에 'zxx' 를 쓰지 않는다", "zxx" not in json.dumps(b))
src = inspect.getsource(sys.modules["run_weekly_fortune"]) if "run_weekly_fortune" in sys.modules else \
    open(os.path.join(HERE, "run_weekly_fortune.py"), encoding="utf-8").read()
ck("run_weekly_fortune: 재생목록·ko·카테고리·예약을 넘긴다",
   all(x in src for x in ("playlist_title=WF.PLAYLIST", 'default_language="ko"', 'audio_language="ko"',
                          "category_id=WF.CATEGORY", "publish_at=at", "synthetic=WF.SYNTHETIC")))

print("── 루틴 명령(week · push) ──")
txt = WF.week_text(at("2026-10-04T17:00"))
ck("week: 주·파일·순위표·뼈대", "WEEK=2026-W41" in txt and "FILE=output/weekly_fortune/2026-10-05_weekly_fortune.json" in txt
   and all(f"{a}띠" in txt for a in WF.ANIMALS) and "TAKEN=no" in txt)
skel = json.loads(txt[txt.index("{"):])
ck("…뼈대 JSON: 12장 쥐→돼지", [c["animal"] for c in skel["chapters"]] == WF.ANIMALS and skel["week"] == "2026-W41")
ok_, msg = WF.push(os.path.join(tempfile.gettempdir(), "bad_name.json"))
ck("push: 파일 이름이 틀리면 git 을 건드리기 전에 거절", not ok_ and "파일 이름" in msg)


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


with tempfile.TemporaryDirectory() as td:
    remote, clone = os.path.join(td, "remote.git"), os.path.join(td, "clone")
    git("init", "-q", "--bare", remote)
    git("init", "-q", clone)
    with open(os.path.join(clone, "README"), "w") as f:
        f.write("x")
    ident = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    git("add", "README", cwd=clone)
    git(*ident, "commit", "-q", "-m", "init", cwd=clone)
    git("remote", "add", "origin", remote, cwd=clone)
    git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=clone)
    sc = copy.deepcopy(SAMPLE)
    sc["week"] = "2026-W41"
    sc["title_hook"] = "쉬어 가며 복을 모으는 한 주"
    sc["intro"] = ("이번 주는 아침저녁 바람이 차가워지면서 몸도 마음도 한 박자 쉬어 가는 한 주예요. "
                   "주 후반으로 갈수록 반가운 소식이 늘어나니, 조급해하지 말고 차분히 기다려 보세요.")
    p = os.path.join(td, "2026-10-05_weekly_fortune.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False)
    _smp = WF.SAMPLE
    WF.SAMPLE = os.path.join(td, "no_sample.json")        # 견본 복사 검사는 위에서 따로 봤다
    try:
        now = at("2026-10-04T17:00")
        ok1, m1 = WF.push(p, now=now, root=clone)
        ls = git("ls-tree", "-r", "--name-only", "refs/heads/routine/weekly_fortune", cwd=remote).stdout
        ck("push: routine/weekly_fortune 에 파일 하나(없던 브랜치는 main 에서)", ok1 and
           ls.split() == ["README", "output/weekly_fortune/2026-10-05_weekly_fortune.json"], (m1, ls))
        ck("…세션 브랜치(작업 폴더)는 그대로", not os.path.exists(os.path.join(clone, "output")))
        ok2, m2 = WF.push(p, now=now, root=clone)
        ck("push: 같은 주는 두 번 올리지 않는다", not ok2 and "이미" in m2, m2)
        bad = copy.deepcopy(sc)
        bad["chapters"].pop()
        p3 = os.path.join(td, "x", "2026-10-05_weekly_fortune.json")
        os.makedirs(os.path.dirname(p3))
        with open(p3, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        ok3, m3 = WF.push(p3, now=now, root=clone)
        ck("push: 검사 실패면 올리지 않는다", not ok3 and "검사 실패" in m3)
    finally:
        WF.SAMPLE = _smp

print("── 워크플로 연결(가드) ──")
wfd = os.path.join(ROOT, ".github", "workflows")
flows = {n: open(os.path.join(wfd, n), encoding="utf-8").read() for n in sorted(os.listdir(wfd)) if n.endswith(".yml")}


def push_branches(text):
    """on.push.branches (push 트리거가 없으면 None · 브랜치 필터가 없으면 ['**'])."""
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
            if s.startswith("push:"):
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
    hit = False
    for p in pats or []:
        neg = p.startswith("!")
        rx = re.escape(p[1:] if neg else p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(rx, ref):
            hit = not neg
    return hit


trig = {n: push_branches(t) for n, t in flows.items()}
ck("routine/weekly_fortune 에 반응하는 push 워크플로는 weekly-fortune.yml 하나",
   [n for n, p in trig.items() if p is not None and gh_match(p, WF.BRANCH)] == ["weekly-fortune.yml"],
   str({n: p for n, p in trig.items() if p}))
ck("shorts.yml: 날짜 브랜치는 그대로 · routine/weekly_fortune 은 뺀다",
   gh_match(trig["shorts.yml"], "routine/2026-10-05_fortune") and not gh_match(trig["shorts.yml"], WF.BRANCH))
tramp, run = flows["weekly-fortune.yml"], flows["weekly-fortune-run.yml"]
ck("weekly-fortune.yml: 경로 output/weekly_fortune/** · main 의 실행 파일을 부른다(누적 브랜치 사본 방지)",
   '"output/weekly_fortune/**"' in tramp and "weekly-fortune-run.yml@main" in tramp and "secrets: inherit" in tramp)
ck("…수동 실행 기본 = 견본 · 업로드 없음 · 비공개",
   re.search(r'script:\n\s+description:[^\n]*\n\s+default: "docs/samples/weekly_fortune_sample.json"', tramp)
   and re.search(r"no_upload:\n(?:\s+[^\n]*\n){2}\s+default: true", tramp)
   and re.search(r"force_private:\n(?:\s+[^\n]*\n){2}\s+default: true", tramp))
ck("…견본 파일이 레포에 있다", os.path.exists(os.path.join(ROOT, "docs", "samples", "weekly_fortune_sample.json")))
ck("weekly-fortune-run.yml: 코드는 main · 새로 추가된 대본만 · 테스트 먼저",
   "ref: main" in run and "--diff-filter=A" in run
   and run.index("pipeline/test_weekly_fortune.py") < run.index("python run_weekly_fortune.py"))
ck("…ledger 캐시 접두가 다른 워크플로와 안 겹친다",
   "key: weeklyfortune-ledger-" in run and not any(
       re.search(r"restore-keys:\s*(\S+)", t) and "weeklyfortune-ledger-".startswith(
           re.search(r"restore-keys:\s*(\S+)", t).group(1)) for n, t in flows.items() if n != "weekly-fortune-run.yml"))
ck("…목소리 한 건씩 · 번역 끔 · 읽기 권한만", 'WEEKLY_TTS_WORKERS: "1"' in run and 'I18N_LOCALIZE: "0"' in run
   and not re.search(r"(?m)^\s*contents:\s*write", run + tramp))
ck("…수동 실행만 영상·썸네일·순위표를 아티팩트로", "if: always() && inputs.manual" in run
   and "*_weekly_fortune.mp4" in run and "*_weekly_fortune_thumb.jpg" in run)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import find_orphan_storyboards as FO  # noqa: E402
ck("미아 감시가 output/weekly_fortune 를 본다 · 목적지 routine/weekly_fortune",
   "output/weekly_fortune/*.json" in FO.WATCH
   and FO.guess_topic("output/weekly_fortune/2026-10-05_weekly_fortune.json") == "weekly_fortune")
ck("orphan-rescue 트리거에 output/weekly_fortune", '"output/weekly_fortune/**.json"' in flows["orphan-rescue.yml"])
ck("ledger·로그는 커밋하지 않는다", all(x in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
                                  for x in ("/output/weekly_fortune_ledger.json", "/output/weekly_fortune_log.json")))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
