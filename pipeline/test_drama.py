#!/usr/bin/env python3
"""사연 오디오드라마(drama_plan · drama_render · run_drama) 회귀 테스트 — 네트워크·ffmpeg 없이.

    python pipeline/test_drama.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drama_plan as P     # noqa: E402
import drama_render as R   # noqa: E402
import run_drama as RD     # noqa: E402

FAIL = 0
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "samples", "drama_sample")


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


print("── 배정 ──")
D = dt.date
ck("첫 회 10-02 = 1화 mother-house", P.assign(D(2026, 10, 2))["episode"] == 1
   and P.assign(D(2026, 10, 2))["archetype"] == "mother-house")
ck("다음 주 = 2화 다른 유형", P.assign(D(2026, 10, 9))["episode"] == 2
   and P.assign(D(2026, 10, 9))["archetype"] != "mother-house")
ck("유형 16개를 다 돌고 처음으로", P.assign(P.START + dt.timedelta(days=7 * 16))["archetype"] == "mother-house")
ck("유형 키 중복 없음", len({a["key"] for a in P.ARCHETYPES}) == len(P.ARCHETYPES))
ck("화자 목소리에 F3·F4 안 씀", all(v not in ("F3", "F4") for v in P.NARRATOR_VOICE.values())
   and all(v not in ("F3", "F4") for vs in P.CAST_VOICES.values() for v in vs))

print("── 대본 파싱 ──")
c = P.parse_chapter("# 3장. 봉투\n[화자] 그날.\n\n[며느리] “어머님.”\n이름 없는 줄\n", 3)
ck("장 제목", c["title"] == "봉투")
ck("발화 두 줄 · 따옴표 제거", [(x["spk"], x["text"]) for x in c["lines"]] == [("화자", "그날."), ("며느리", "어머님.")],
   str(c["lines"]))
ck("[이름] 없는 줄은 오류로 잡는다", len(c["_bad"]) == 1)

spec = P.build(SAMPLE)
ck("견본 조립: 2장 · 12줄", spec["stats"]["chapters"] == 2 and spec["stats"]["lines"] == 12, str(spec["stats"]))
ck("목소리: 화자 F2 · 며느리 F · 아들 M", spec["voices"]["화자"] == "F2" and spec["voices"]["며느리"].startswith("F")
   and spec["voices"]["아들"].startswith("M") and spec["voices"]["며느리"] != "F2", str(spec["voices"]))

print("── 검사(게이트) ──")
ck("견본은 분량 검사 생략 시 통과", P.check(spec, allow_short=True) == [], str(P.check(spec, allow_short=True)))
full = P.check(spec)
ck("실제 회차 기준으론 분량 부족으로 막힌다", any("분량 부족" in x for x in full) and any("장 수" in x for x in full))
bad = {**spec, "chapters": spec["chapters"] + [{"index": 3, "title": "x", "lines": [{"spk": "옆집", "text": "안녕"}]}]}
bad["stats"] = P.stats(bad)
ck("선언 안 된 등장인물은 막는다", any("옆집" in x for x in P.check(bad, allow_short=True)))
ck("그림 없는 장은 막는다", any("3장 그림" in x for x in P.check(bad, allow_short=True)))
talky = {**spec, "chapters": [{"index": 1, "title": "t", "lines": [{"spk": "며느리", "text": "가" * 100}]}]}
talky["stats"] = P.stats(talky)
ck("대사만 이어지면 막는다(화자 비중)", any("화자 비중" in x for x in P.check(talky, allow_short=True)))
ck("긴 제목은 막는다", any("제목" in x for x in P.check({**spec, "title": "가" * 61}, allow_short=True)))

print("── 조각 나누기 ──")
long = "가나다라마바사. " * 60
parts = R.split_text(long)
ck("220자 이하 조각", all(len(p) <= R.CHUNK_MAX for p in parts), str([len(p) for p in parts]))
ck("글자를 잃지 않는다", "".join(parts).replace(" ", "") == long.replace(" ", ""))
ck("쉼표·마침표 없는 긴 문장도 자른다", all(len(p) <= R.CHUNK_MAX for p in R.split_text("가 " * 300)))
chunks = R.plan_chunks(spec)
ck("조각마다 목소리", all(c["voice"] for c in chunks) and chunks[2]["voice"] == spec["voices"]["며느리"])

print("── 타임라인 · 자막 · 목차 ──")
for c in chunks:
    c["dur"] = 5.0
chaps, total = R.timeline(chunks)
ck("1장은 0초에 시작(첫 30초에 카드 없음)", chaps[0]["start"] == 0.0)
ck("2장 앞에 장 제목 카드 3초(속도 보정)", abs((chaps[1]["start"] - chaps[1]["card_start"]) - R.GAP_CHAPTER / R.TEMPO) < 1e-6)
ck("조각은 겹치지 않는다", all(a["end"] <= b["start"] + 1e-9 for a, b in zip(chunks, chunks[1:])))
ck("대사가 바뀌면 쉼이 더 길다", R.GAP_SWITCH > R.GAP_SAME)
txt = R.chapters_text(spec, chaps)
ck("목차 첫 줄 00:00", txt.splitlines()[0].startswith("00:00 1장"), txt)
ck("한 시간 넘으면 h:mm:ss", R._ts(3725.0, srt=False) == "1:02:05" and R._ts(65.0, srt=False) == "01:05")
with tempfile.TemporaryDirectory() as td:
    n = R.build_srt(chunks, os.path.join(td, "a.srt"))
    s = open(os.path.join(td, "a.srt"), encoding="utf-8").read()
ck("자막: 대사 앞에 (이름)", "(며느리)" in s and n >= len(chunks))
ck("자막 시각 형식", re.search(r"\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}", s) is not None)
segs = R.video_segments(spec, chaps, total, {1: ["a.jpg", "b.jpg"], 2: ["c.jpg"]}, tempfile.gettempdir())
ck("그림 구간이 끝까지 이어진다", abs(segs[-1][2] - total) < 1e-6 and all(abs(a[2] - b[1]) < 1e-6 for a, b in zip(segs, segs[1:])))

print("── 업로드 메타 ──")
desc = RD.compose_description(spec, txt)
ck("설명: 목차·AI 창작 고지·목소리 출처", "⏱ 목차" in desc and "AI 기술을 활용해 만든 창작" in desc and "Supertonic" in desc)
ck("설명 5,000자 이내", len(desc) <= 5000)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
