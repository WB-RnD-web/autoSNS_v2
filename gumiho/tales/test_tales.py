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
ck("파일 이름이 id_slug 와 다르면 막힌다", any("파일 이름" in e for e in T.check(S, "/x/002_other.json")))

print("── 편성(날짜로 결정론적) ──")
ck("10/1 주 → 2편", T.assigned_id("2026-10-01") == 2 and T.assigned_id("2026-10-07") == 2)
ck("10/8 → 3편 · 10/15 → 4편", T.assigned_id("2026-10-08") == 3 and T.assigned_id("2026-10-15") == 4)
cat = T.load(T.CATALOG)["tales"]
ck("catalog 번호 1부터 연속·slug 중복 없음", [e["id"] for e in cat] == list(range(1, len(cat) + 1))
   and len({e["slug"] for e in cat}) == len(cat))
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
