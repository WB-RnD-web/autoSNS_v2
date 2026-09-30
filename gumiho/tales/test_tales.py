#!/usr/bin/env python3
"""Nine Tails Tales 회귀 테스트 — 네트워크 없이(가짜 그림·가짜 목소리). 영상 전체 인코딩은 하지 않는다.

    python gumiho/tales/test_tales.py
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_tale as R  # noqa: E402
import tales as T        # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


SAMPLES = sorted(glob.glob(os.path.join(HERE, "scripts", "*.json")))
S = T.load(SAMPLES[0])

print("── 대본 검사 ──")
for p in SAMPLES:
    errs = T.check(T.load(p), p)
    ck(f"{os.path.basename(p)} 통과", not errs, str(errs[:3]))
bad = copy.deepcopy(S)
bad["scenes"] = bad["scenes"][:10]
ck("짧은 대본은 막힌다", any("단어" in e or "장면" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["scenes"][5]["say"] = "word " * 90
ck("한 장면 70단어 초과는 막힌다", any("70" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["scenes"][0] = {"gumi": "front", "say": "hi"}
ck("첫 장면이 그림+내레이션이 아니면 막힌다", any("첫 장면" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["short"]["lines"][0]["scene"] = "nope"
ck("쇼츠가 없는 장면 key 를 가리키면 막힌다", any("key" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["scenes"][0]["img"] += ", a naked woman"
ck("금지어는 막힌다", any("금지어" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["thumb"]["text"] = "THIS IS WAY TOO LONG A LINE"
ck("썸네일 문구 4단어 초과는 막힌다", any("썸네일" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
k = next(i for i, x in enumerate(bad["scenes"]) if x.get("card"))
bad["scenes"].insert(k + 1, {"card": "I", "sub": "Extra"})
ck("카드 두 장이 연달아 나오면 막힌다", any("연달아" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["scenes"][5]["say"] = "This Halloween, everyone is talking about foxes."
ck("날짜를 타는 표현은 막힌다(역주행 가능하게)", any("날짜" in e for e in T.check(bad)))
bad = copy.deepcopy(S)
bad["title"] = "A Very Scary Story"
ck("제목에 검색어가 없으면 막힌다", any("검색어" in e for e in T.check(bad)))
ck("설명에 다른 편 링크", "Tale X — https://youtu.be/A" in T.meta(S, None, more=[("Tale X", "https://youtu.be/A")])["description"])
ck("파일 이름이 id_slug 와 다르면 막힌다", any("파일 이름" in e for e in T.check(S, "/x/002_other.json")))

print("── 편성(날짜로 결정론적) ──")
# 루틴은 매주 수요일(9/30 첫 실행) — 수요일마다 번호가 하나씩 올라야 한다(9/29 발견: start 가 목요일이면 9/30·10/7 이 같은 번호)
ck("수 9/30 → 2편 · 화 10/6 → 2편", T.assigned_id("2026-09-30") == 2 and T.assigned_id("2026-10-06") == 2)
ck("수 10/7 → 3편 · 수 10/14 → 4편", T.assigned_id("2026-10-07") == 3 and T.assigned_id("2026-10-14") == 4)
cat = T.load(T.CATALOG)["tales"]
ck("catalog 번호 1부터 연속·slug 중복 없음", [e["id"] for e in cat] == list(range(1, len(cat) + 1))
   and len({e["slug"] for e in cat}) == len(cat))
ck("format 은 tale·urban·list·versus 중 하나", all(e.get("format", "tale") in T.FORMATS for e in cat))
ck("같은 format 이 4편 넘게 연속되지 않는다",
   max(len(list(g)) for _, g in __import__("itertools").groupby(e.get("format", "tale") for e in cat)) <= 4)
ck("아직 안 쓴 편은 facts·sources 가 있다", all(e.get("facts") and e.get("sources") for e in cat if not e.get("done")))

print("── 메타데이터 ──")
starts = [i * 10.0 for i in range(len(S["scenes"]))]
md = T.meta(S, starts)
chap = [ln for ln in md["description"].splitlines() if ln[:2].isdigit() and ":" in ln[:6]]
ck("챕터는 00:00 부터 3개 이상", chap and chap[0].startswith("00:00") and len(chap) >= 3, str(chap[:4]))
ck("설명에 AI 고지·출처", "AI-generated" in md["description"] and "Sources" in md["description"])
ck("제목 100자 이내", len(md["title"]) <= 100)
ck("쇼츠 설명에 본편 링크", "youtu.be/X" in T.meta(S, None, short_of="https://youtu.be/X")["short"]["description"])

print("── 목소리·타임라인(가짜) ──")
with tempfile.TemporaryDirectory() as td:
    shots = R.plan(S)
    texts = [x["say"] for x in shots if x["say"]] + [ln["say"] for ln in S["short"]["lines"]]
    voices = R.synth(texts, os.path.join(td, "tts"), mock=True)
    total = R.timeline(shots, voices)
    ck("장면 시간이 이어진다", all(abs(a["start"] + a["dur"] - b["start"]) < 1e-2 for a, b in zip(shots, shots[1:])))
    ck("카드는 CARD_SEC", all(abs(x["dur"] - R.CARD_SEC) < 1e-6 for x in shots if x["kind"] == "card"))
    ck("말하는 장면은 목소리보다 길다", all(x["dur"] > x["vdur"] for x in shots if x.get("vdur")))
    info = R.make_images(S, shots, os.path.join(td, "img"), mock=True)
    ck("그림 수 = 고유 프롬프트 + 썸네일", info["images"] == len({x["img"] for x in shots if x.get("img")}) + 1)
    ck("모든 장면에 준비 그림", all(os.path.exists(x["prep"]) for x in shots))
    P = {"shots": shots, "total": total}
    pa = R.Painter(P)
    ok = True
    for k, x in enumerate(shots):
        for t in (x["start"] + 0.01, x["start"] + x["dur"] / 2, x["start"] + x["dur"] - 0.01):
            im = pa.frame(t)
            ok &= im.size == (R.W, R.H)
    ck(f"모든 장면(시작·가운데·끝) 프레임 {R.W}×{R.H}", ok)
    import numpy as np
    first = np.asarray(pa.frame(0.0)).mean()
    ck("첫 프레임은 검은 화면에서 시작", first < 5, f"{first:.1f}")
    fx = R.FX(R.W, R.H)
    base = R.Image.new("RGB", (R.W, R.H), (40, 40, 60))
    ok = all(fx.draw(base.copy(), k, 3.3).size == (R.W, R.H) for k in T.FX)
    ck("입자 효과 전 종류", ok)
    srt = os.path.join(td, "a.srt")
    n = R.build_srt(shots, srt)
    ck("자막 줄이 생긴다·84자 이하", n > 50 and all(len(l) <= 84 for l in open(srt, encoding="utf-8").read().split("\n")))
    R.thumbnail(S, info["thumb_raw"], os.path.join(td, "t.jpg"))
    ck("썸네일 1280×720", R.Image.open(os.path.join(td, "t.jpg")).size == (1280, 720))
    SP = R.short_plan(S, shots, voices, td)
    ck(f"쇼츠 {R.SHORT_MAX}초 이하", SP["total"] <= R.SHORT_MAX, str(SP["total"]))
    spa = R.ShortPainter(SP, S)
    ck("쇼츠 프레임 1080×1920", spa.frame(SP["total"] / 2).size == (R.SW, R.SH))
    b = R.bed(R.SR * 20, 1)
    ck("배경음 20초·클리핑 없음", len(b) == R.SR * 20 and float(abs(b).max()) < 1.5)
    ck("이동 평균 길이 보존", len(R.movavg(np.ones(1000, dtype="float32"), 50)) == 1000)
    ck("캡션 조각 3단어 이하", all(len(c.split()) <= 3 for c in R.caption_chunks("The boy swallowed it and the girl screamed, loudly.")))

print("── 글꼴(9/30 사고: 리눅스에 Black 이 없어 썸네일·쇼츠 자막이 깨알 글꼴로 나갔다) ──")
from PIL import ImageFont  # noqa: E402
ok = True
for kind in ("sans", "sans_bold", "serif", "cjk"):
    f = R.font(kind, 100)
    ok &= isinstance(f, ImageFont.FreeTypeFont) and f.size == 100
    print(f"     {kind}: {R.font_path(kind)}")
ck("모든 글꼴이 실제 트루타입(크기 적용)", ok)
ck("큰 글자용 sans 는 Bold 이상 굵기", any(w in (R.font_path("sans") or "") for w in ("Black", "ExtraBold", "-VF", "arialbd", "Bold")))

print("── 쇼츠 첫 1초 ──")
bad = copy.deepcopy(S)
bad["short"]["hook"] = "THIS HOOK IS FAR TOO LONG TO FIT ON TWO LINES AT THE TOP"
ck("쇼츠 hook 너무 길면 거부", any("hook" in e for e in T.check(bad, "x.json")))
ok_ = copy.deepcopy(S)
ok_["short"]["hook"] = "SHE ATE THEM ALL"
ck("쇼츠 hook 짧으면 통과", not any("hook" in e for e in T.check(ok_, "x.json")))
ck("hook 없으면 썸네일 문구", R.short_hook(S) == S["thumb"]["text"].upper())
fake = {x.get("key"): {"key": x.get("key"), "raw": f"/img/{x.get('key')}.png"} for x in S["scenes"] if x.get("key")}
shots_ = list(fake.values())
voices_ = {ln["say"]: "v.wav" for ln in S["short"]["lines"]}
_wd = R.wav_dur
R.wav_dur = lambda _p: 3.0
try:
    sp = R.short_plan(S, shots_, voices_, ".", thumb_raw="/img/THUMB.png")
    sp0 = R.short_plan(S, shots_, voices_, ".")
finally:
    R.wav_dur = _wd
ck("쇼츠 첫 줄 그림 = 썸네일 그림", sp["rows"][0]["raw"] == "/img/THUMB.png", sp["rows"][0]["raw"])
ck("썸네일 없으면 원래 그림", sp0["rows"][0]["raw"] != "/img/THUMB.png")

print("── 업로드 가드 ──")
import upload_tale as U  # noqa: E402
import datetime as dt  # noqa: E402
sat = U.next_saturday_15utc(dt.datetime(2026, 10, 1, 3, 0, tzinfo=dt.timezone.utc))
ck("예약: 다음 토요일 15:00 UTC", sat == "2026-10-03T15:00:00Z", sat)
sat = U.next_saturday_15utc(dt.datetime(2026, 10, 3, 12, 0, tzinfo=dt.timezone.utc))
ck("토요일 6시간 안이면 그다음 주", sat == "2026-10-10T15:00:00Z", sat)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
