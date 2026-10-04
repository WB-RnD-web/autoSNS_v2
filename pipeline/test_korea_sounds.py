#!/usr/bin/env python3
"""Korea Sleep Sounds(korea_sounds · ambient_motion · run_asmr 시리즈 경로) 회귀 테스트.

    python pipeline/test_korea_sounds.py
"""
from __future__ import annotations
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ambient_motion as AM  # noqa: E402
import korea_sounds as K  # noqa: E402
import run_asmr as R  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


D = dt.date
print("── 날짜 → 테마 배정 ──")
ck("첫 수요일은 슬롯 0 · 한옥 빗소리", K.pick(D(2026, 9, 30))[:2] == (K.THEMES[0], 0) and K.THEMES[0]["id"] == "hanok-rain")
ck("토요일은 슬롯 1", K.slot_for(D(2026, 10, 3)) == 1)
ck("금요일에 돌려도 그 주 수요일 테마", K.slot_for(D(2026, 10, 2)) == 0)
ck("화요일은 직전 토요일 테마", K.slot_for(D(2026, 10, 6)) == 1)
ck("다음 주 수요일은 슬롯 2", K.slot_for(D(2026, 10, 7)) == 2)
ck("같은 날짜는 항상 같은 스펙", K.build_spec(D(2026, 10, 7)) == K.build_spec(D(2026, 10, 7)))
n = len(K.THEMES)
d_wrap = K.START + dt.timedelta(days=7 * (n // 2))
ck("한 바퀴 돌면 Vol. 2", K.pick(d_wrap)[2] == 2 and "Vol. 2" in K.build_spec(d_wrap)["platforms"]["youtube"]["title"])
try:
    K.slot_for(D(2026, 9, 1))
    ck("시작일 이전 날짜는 거부", False)
except ValueError:
    ck("시작일 이전 날짜는 거부", True)

print("── 테마 목록 ──")
ids = [t["id"] for t in K.THEMES]
ck("테마 id 중복 없음", len(ids) == len(set(ids)))
ck("배정 순서 목록과 테마가 일치", sorted(ids) == sorted(K._ORDER))
TEXTY = ("sign", "text", "title", "logo", "letter", "word", "caption")
for t in K.THEMES:
    bad = []
    if t["motion"] not in AM.KINDS:
        bad.append("motion")
    if t["mode"] not in ("sleep", "mixed", "trigger"):
        bad.append("mode")
    if t["mode"] != "sleep" and not t.get("trig"):
        bad.append("mixed 인데 trig 없음")
    if not t["must"] or not t["q"]:
        bad.append("쿼리/앵커")
    if any(w in t["scene"].lower() for w in TEXTY):
        bad.append("장면에 글자 낱말(느린 글자 모델로 감)")
    ck(f"{t['id']} 필드", not bad, ", ".join(bad))
long_en = max(len(K.build_spec(K.START + dt.timedelta(days=3 * i + i % 2))["platforms"]["youtube"]["title"])
              for i in range(3 * n))
ck("영어 제목 100자 이하(Vol. 3 까지)", long_en <= 100, str(long_en))
sp = K.build_spec(D(2026, 9, 30))
ck("한국어 제목 100자 이하", len(sp["platforms"]["youtube"]["localizations"]["ko"]["title"]) <= 100)
ck("기본 8시간", sp["duration_sec"] == 8 * 3600)

print("── 업로드 메타(시리즈) ──")
os.environ["ASMR_PLAYLIST"] = "일상공감 ASMR"
m = R.build_meta(sp, "", False)
ck("시리즈는 ASMR_PLAYLIST 를 따르지 않는다", m["playlist"] == "Korea Sleep Sounds", m["playlist"])
ck("기본 언어 en · 합성 표시", m["default_language"] == "en" and m["synthetic"] is True)
ck("영어 태그", "sleep sounds" in m["tags"] and "korea" in m["tags"])
loc = R.asmr_localizations(sp, 28800)
ck("현지화는 한국어만(영어는 원문)", list(loc) == ["ko"], str(list(loc)))
plain = {"theme_id": "ocean-waves", "platforms": {"youtube": {"title": "🌊 파도 소리 ASMR 3시간", "playlist": "p"}}}
mp = R.build_meta(plain, "", False)
ck("기존 ASMR 은 그대로(한국어 기본·ASMR_PLAYLIST)", mp["default_language"] is None and mp["synthetic"] is None
   and mp["playlist"] == "일상공감 ASMR")
del os.environ["ASMR_PLAYLIST"]
ck("영어 이름의 작은 낱말은 소문자", R.english_name("rain-on-the-window") == "Rain on the Window")

print("── 움직임 루프 이음새 ──")
for kind in AM.KINDS:
    import random
    draw_fn, _, _ = AM._layer_fn(kind, random.Random(f"{kind}|t"))
    a = Image.new("RGBA", (AM.W, AM.H))
    b = Image.new("RGBA", (AM.W, AM.H))
    draw_fn(ImageDraw.Draw(a), 0.0)
    draw_fn(ImageDraw.Draw(b), 1.0)
    ck(f"{kind}: 루프 끝 = 루프 처음", a.tobytes() == b.tobytes())
try:
    next(AM.frames(Image.new("RGB", (64, 36)), "fog"))
    ck("모르는 움직임은 거부", False)
except ValueError:
    ck("모르는 움직임은 거부", True)

print("── 슬롯 발행일(늦게 돈 예약이 중복으로 올리지 않게) ──")
import datetime as _d
_S = K.START
ck("수요일은 그대로", K.slot_date(_S) == _S)
ck("목요일 새벽 = 같은 슬롯의 수요일", K.slot_date(_S + _d.timedelta(days=1)) == _S)
ck("금요일도 수요일", K.slot_date(_S + _d.timedelta(days=2)) == _S)
ck("토요일은 토요일", K.slot_date(_S + _d.timedelta(days=3)) == _S + _d.timedelta(days=3))
ck("일·월·화는 그 주 토요일", all(K.slot_date(_S + _d.timedelta(days=k)) == _S + _d.timedelta(days=3) for k in (4, 5, 6)))
ck("다음 주 수요일", K.slot_date(_S + _d.timedelta(days=7)) == _S + _d.timedelta(days=7))
ck("같은 슬롯이면 테마도 같다", K.pick(_S)[0]["id"] == K.pick(_S + _d.timedelta(days=1))[0]["id"])

print("── 중복 업로드 막기(10/3 Jeju 두 번)")


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class _YT:
    def __init__(self, titles):
        self.titles = titles

    def channels(self):
        return type("C", (), {"list": lambda _s, **k: _Req({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}}]})})()

    def playlistItems(self):
        items = [{"snippet": {"title": t, "resourceId": {"videoId": f"v{i}"}}} for i, t in enumerate(self.titles)]
        return type("P", (), {"list": lambda _s, **k: _Req({"items": items})})()


_t = K.build_spec(_S)["platforms"]["youtube"]["title"]
ck("같은 슬롯 제목이 채널에 있으면 주소", K.on_youtube(_t, _YT(["다른 영상", _t])) == "https://youtu.be/v1")
ck("없으면 None(올린다)", K.on_youtube(_t, _YT(["다른 영상"])) is None)
ck("같은 슬롯이면 늦게 돈 실행도 같은 제목(예비 cron 이 알아본다)",
   K.build_spec(K.slot_date(_S + _d.timedelta(days=1)))["platforms"]["youtube"]["title"] == _t)
_wf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".github", "workflows", "korea-sounds.yml"),
           encoding="utf-8").read()
ck("워크플로: 렌더 전에 유튜브 확인 · 있으면 렌더·업로드 건너뜀",
   "--seen" in _wf and "if: steps.seen.outputs.skip != '1'" in _wf and _wf.index("--seen") < _wf.index("run_asmr.py"))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
