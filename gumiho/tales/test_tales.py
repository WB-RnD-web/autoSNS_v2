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
ck("수 9/30 → 2편 · 토 10/3 → 2편", T.assigned_id("2026-09-30") == 2 and T.assigned_id("2026-10-03") == 2)
# 10/4~10/10 은 1주 형식 실험(하루 한 편, 아래 sprint 검사) — 수 10/14 부터 다시 수요일마다 +1
ck("수 10/14 → 10편 · 수 10/21 → 11편", T.assigned_id("2026-10-14") == 10 and T.assigned_id("2026-10-21") == 11)
cat = T.load(T.CATALOG)["tales"]
ck("catalog 번호 1부터 연속·slug 중복 없음", [e["id"] for e in cat] == list(range(1, len(cat) + 1))
   and len({e["slug"] for e in cat}) == len(cat))
ck("format 은 tale·urban·list·versus·behind·mystery 중 하나", all(e.get("format", "tale") in T.FORMATS for e in cat))
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
    texts = [x["say"] for x in shots if x["say"]] + [ln["say"] for ln in S["short"]["lines"]] + [R.CTA_SAY]
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
    # 끝맺음(2026-10-09): 설명란 링크는 안 눌린다 → 마지막 3~5초에 말+화면으로 '관련 동영상' 링크(채널 이름 아래)를 짚는다
    end = SP["rows"][-1]
    ck("쇼츠 끝맺음 장면이 들어간다(말 = 링크 안내)", bool(end.get("cta")) and end["say"] == R.CTA_SAY, str(end.get("say")))
    cta_sec = SP["total"] - end["start"]
    ck("끝맺음 3~5초", 3.0 <= cta_sec <= 5.0, f"{cta_sec:.2f}")
    ck("끝맺음은 앞 그림·카메라를 끊김 없이 잇는다",
       end["raw"] == SP["rows"][-2]["raw"] and end.get("cam") == SP["rows"][-2].get("cam") and end.get("cont"))

    def _gold(a, y0, y1):
        reg = a[y0:y1, R.CTA_ARROW_X - 5:R.CTA_ARROW_X + 5].astype(int)
        return float(np.mean(np.all(np.abs(reg - np.array(R.GOLD)) < 40, axis=-1)))
    f_cta = np.asarray(spa.frame(end["start"] + 1.5))
    f_pre = np.asarray(spa.frame(end["start"] - 0.5))
    ck("끝맺음 화면에 아래 화살표(그 전 줄엔 없다)", _gold(f_cta, 1400, 1455) > 0.6 and _gold(f_pre, 1400, 1455) < 0.2,
       f"{_gold(f_cta, 1400, 1455):.2f} / {_gold(f_pre, 1400, 1455):.2f}")
    ck("화살표 끝이 아래 UI(채널 이름·링크, y≈1580~)를 덮지 않는다",
       R.CTA_ARROW_TIP <= 1550 and _gold(f_cta, R.CTA_ARROW_TIP + 10, 1600) < 0.1)
    ck("끝맺음 카드는 오른쪽 버튼 열(x≥950)을 피한다", float(np.abs(f_cta[1200:1350, 960:].astype(int)
                                                     - np.asarray(spa.frame(end["start"] - 0.5))[1200:1350, 960:]).mean()) < 8)
    ck("cta=False 면 끝맺음 없음(예전 꼴)", not any(r.get("cta") for r in R.short_plan(S, shots, voices, td, cta=False)["rows"]))
    ck("render 가 끝맺음 목소리를 같이 합성한다", "texts.append(CTA_SAY)" in open(R.__file__, encoding="utf-8").read())
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
voices_ = {ln["say"]: "v.wav" for ln in S["short"]["lines"]} | {R.CTA_SAY: "v.wav"}
_wd = R.wav_dur
R.wav_dur = lambda _p: 3.0
try:
    sp = R.short_plan(S, shots_, voices_, ".", thumb_raw="/img/THUMB.png")
    sp0 = R.short_plan(S, shots_, voices_, ".")
finally:
    R.wav_dur = _wd
ck("쇼츠 첫 줄 그림 = 썸네일 그림", sp["rows"][0]["raw"] == "/img/THUMB.png", sp["rows"][0]["raw"])
ck("썸네일 없으면 원래 그림", sp0["rows"][0]["raw"] != "/img/THUMB.png")

print("── 쇼츠에만 있는 그림(10/5 4화 렌더 실패) ──")
new_img = "a Joseon family in white mourning clothes kneeling beside a low table of rice by a gate at dusk"
S4 = copy.deepcopy(S)
S4["short"]["lines"][1] = {k: v for k, v in S4["short"]["lines"][1].items() if k not in ("scene", "gumi")}
S4["short"]["lines"][1]["img"] = new_img
ck("쇼츠 전용 그림을 찾는다(본편에 있는 그림은 빼고)", R.short_only_prompts(S4, shots_) == [new_img], R.short_only_prompts(S4, shots_))
R.wav_dur = lambda _p: 3.0
try:
    v4 = {ln["say"]: "v.wav" for ln in S4["short"]["lines"]} | {R.CTA_SAY: "v.wav"}
    sp4 = R.short_plan(S4, shots_, v4, ".", thumb_raw="/img/THUMB.png", raw_map={new_img: "/img/NEW.png"})
    sp5 = R.short_plan(S4, shots_, v4, ".", thumb_raw="/img/THUMB.png")
    sp6 = R.short_plan(S4, shots_, v4, ".")
finally:
    R.wav_dur = _wd
ck("미리 그린 쇼츠 전용 그림을 쓴다", sp4["rows"][1]["raw"] == "/img/NEW.png", sp4["rows"][1]["raw"])
ck("없으면 썸네일 그림으로 대신(예외로 멈추지 않는다)", sp5["rows"][1]["raw"] == "/img/THUMB.png", sp5["rows"][1]["raw"])
ck("썸네일도 없으면 본편 첫 그림", sp6["rows"][1]["raw"] == shots_[0]["raw"], sp6["rows"][1]["raw"])
with tempfile.TemporaryDirectory() as td4:
    sh4 = R.plan(S4)
    inf4 = R.make_images(S4, sh4, os.path.join(td4, "img"), mock=True, extra_prompts=R.short_only_prompts(S4, sh4))
    ck("make_images 가 쇼츠 전용 그림도 그린다(그림 수 +1 · raw 지도에 있다)",
       inf4["images"] == len({x["img"] for x in sh4 if x.get("img")}) + 2 and os.path.exists(inf4["raw"][new_img]))
ck("render: 쇼츠 전용 그림을 본편 그림과 같이 만들고 쇼츠에 넘긴다",
   "short_only_prompts(s, shots, extras)" in open(R.__file__, encoding="utf-8").read() and 'im["raw"])' in open(R.__file__, encoding="utf-8").read())

print("── 편당 쇼츠 2~3개(3화부터) ──")
keys_ = [x["key"] for x in S["scenes"] if x.get("key")]
main_first = T.first_src(S["short"])
alt = next(k for k in keys_ if k != main_first)
alt2 = next(k for k in keys_ if k not in (main_first, alt))
ex = copy.deepcopy(S["short"])
ex["hook"] = "DON'T LOOK BACK"
ex["title"] = "Never Look Back on a Korean Mountain Road #shorts"    # 규칙형(10화부터 하나 이상)
ex["lines"][0] = {"scene": alt, "say": ex["lines"][0]["say"]}
ex2 = copy.deepcopy(S["short"])
ex2["hook"] = "SHE KEPT THE BEAD"
ex2["title"] = "A different way in #shorts"
ex2["lines"][0] = {"scene": alt2, "say": ex2["lines"][0]["say"]}
three = copy.deepcopy(S)
three["id"] = 10                     # 스프린트(3~9화)는 추가 쇼츠 예외 — 그 밖의 편으로 검사
three["look"] = "modern"
three["title"] = "Gumiho " + three["title"][:40]
ck("10화부터 shorts_extra 없으면 거부", any("편당" in e for e in T.check(three, "x.json")))
three["shorts_extra"] = [ex]
ck("10화부터 추가 쇼츠 1개면 거부(2개 — 주 3편)", any("편당" in e for e in T.check(three, "x.json")))
three["shorts_extra"] = [ex, ex2]
errs3 = [e for e in T.check(three, "x.json") if "쇼츠" in e or "look" in e]
ck("추가 쇼츠 2개(다른 hook·첫 장면·제목)+규칙형 하나면 통과", not errs3, str(errs3))
b_ = copy.deepcopy(three)
b_["shorts_extra"][0]["hook"] = S["short"].get("hook") or S["thumb"]["text"]
ck("hook 이 본 쇼츠와 같으면 거부", any("hook 이 다른 쇼츠와 같다" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["shorts_extra"][0]["lines"][0] = {"gumi": "front", "say": "hello there dear human"}
ck("첫 줄이 구미면 거부", any("첫 줄은 구미" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["shorts_extra"][0]["lines"][0] = copy.deepcopy(S["short"]["lines"][0])
ck("첫 장면이 본 쇼츠와 같으면 거부", any("첫 장면 그림" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["shorts_extra"] = [ex, ex2, ex2]
ck("추가 쇼츠 3개(합계 4개)는 거부", any("편당" in e for e in T.check(b_, "x.json")))

print("── 글로벌 화풍·Korean Rules(10화부터, 2026-10-05) ──")
b_ = copy.deepcopy(three)
del b_["look"]
ck("10화부터 look 없으면 거부", any("look 필수" in e for e in T.check(b_, "x.json")))
b_["look"] = "victorian"
ck("look 이 목록 밖이면 거부", any("look 'victorian'" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["scenes"][5]["look"] = "space"
ck("장면 look 이 목록 밖이면 거부", any("장면 5: look" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["scenes"][5]["look"] = "joseon"
ck("현대 이야기 속 조선 회상 장면은 통과", not any("look" in e for e in T.check(b_, "x.json")))
b_ = copy.deepcopy(three)
b_["shorts_extra"][0]["title"] = "One more way in #shorts"
b_["short"]["title"] = "The Fox Bead Legend #shorts"          # 1화 본 쇼츠 제목도 규칙형(Never Kiss…)이라 바꿔서
ck("10화부터 규칙형 쇼츠가 하나도 없으면 거부", any("규칙형" in e for e in T.check(b_, "x.json")))
ck("1·2화(look 없음)는 look 검사 안 함", not any("look" in e for e in T.check(S, "x.json")))
ck("look 없는 옛 대본은 예전 화풍 문자열 그대로(그림 캐시 유지)", R.look_prefix(None) == R.LOOK)
ck("modern 은 조선이 아니라 현대", "present day" in R.look_prefix("modern") and "Joseon" not in R.look_prefix("modern"))
ck("joseon 은 조선 그대로", "Joseon dynasty era" in R.look_prefix("joseon"))
import inspect as _ins  # noqa: E402
ck("9화까지는 look 이 있어도 예전 화풍(실험 주간 보호)", "T.GLOBAL_FROM" in _ins.getsource(R.make_images))
ck("대결형 제목도 피드형(6화부터 · 10/6 대결 쇼츠 1,555회)", T.feed_title("Gumiho vs Kitsune vs Huli Jing: Which Fox Is Scariest? #shorts")
   and T.feed_title("Never Play the Elevator Game Alone #shorts") and not T.feed_title("They Wished for a Daughter. Then the Cows Started Dying #shorts"))
s6 = copy.deepcopy(S)
s6["id"] = 6
s6["short"]["title"] = "They Wished for a Daughter. Then the Cows Started Dying #shorts"
ck("6화(스프린트)부터 쇼츠 제목이 이야기형이면 거부", any("규칙형" in e for e in T.check(s6, "x.json")))
s6["short"]["title"] = "Gumiho vs Kitsune: Which Fox Is Deadlier? #shorts"
ck("…대결형이면 통과", not any("규칙형" in e for e in T.check(s6, "x.json")))
s5 = copy.deepcopy(S)
s5["id"] = 5
s5["short"]["title"] = "They Wished for a Daughter. Then the Cows Started Dying #shorts"
ck("5화까지는 그대로(이미 올라간 편)", not any("규칙형" in e for e in T.check(s5, "x.json")))
ck("규칙형 제목 판별", bool(T.RULE_TITLE.match("Never Cut Your Nails at Night in Korea. Here's Why #shorts"))
   and bool(T.RULE_TITLE.match("If You Hear Your Name, Don't Turn #shorts"))
   and not T.RULE_TITLE.match("They Wished for a Daughter #shorts"))
md3 = T.meta(three, None, short_of="https://youtu.be/X")
ck("메타에 추가 쇼츠 제목·본편 링크", md3["shorts_extra"][0]["title"] == ex["title"]
   and "youtu.be/X" in md3["shorts_extra"][0]["description"])
ck("1·2화는 추가 쇼츠 없어도 통과(이미 올라감)", not any("편당" in e for e in T.check(S, "x.json")))
fake2 = {x.get("key"): {"key": x.get("key"), "raw": f"/img/{x.get('key')}.png"} for x in S["scenes"] if x.get("key")}
_wd2 = R.wav_dur
R.wav_dur = lambda _p: 3.0
try:
    spx = R.short_plan(dict(S, short=ex), list(fake2.values()),
                       {ln["say"]: "v.wav" for ln in ex["lines"]} | {R.CTA_SAY: "v.wav"}, ".")
finally:
    R.wav_dur = _wd2
ck("추가 쇼츠 첫 줄 = 자기 장면 그림(썸네일 아님)", spx["rows"][0]["raw"] == f"/img/{alt}.png", spx["rows"][0]["raw"])
import upload_tale as UX  # noqa: E402
ck("추가 쇼츠 예약: 본편 토 → 화·목", UX.extra_short_at("2026-10-10T15:00:00Z", 2) == "2026-10-13T15:00:00Z"
   and UX.extra_short_at("2026-10-10T15:00:00Z", 3) == "2026-10-15T15:00:00Z")
ck("본편 비공개면 추가 쇼츠도 예약 없음", UX.extra_short_at(None, 2) is None)

print("── 제목·링크 ──")
long_ = copy.deepcopy(S)
long_["id"] = 3
long_["title"] = "Gumiho " + "x" * 70
ck("3화부터 제목 70자 넘으면 거부", any("70" in e for e in T.check(long_, "x.json")))
old_ = copy.deepcopy(long_)
old_["id"] = 1
ck("1·2화는 예외(이미 올라감)", not any("70" in e for e in T.check(old_, "x.json")))
import upload_tale as U0  # noqa: E402
m_, us_ = U0.protect_urls("Full tale: https://youtu.be/RhKwrpHRLeY\nMore: https://youtu.be/D0JiefhF73o")
ck("번역 전 링크를 자리표시로", "youtu" not in m_ and len(us_) == 2, m_)
ck("번역 뒤 링크 복원", U0.restore_urls("Histoire : ⟦0⟧\nPlus : ⟦1⟧", us_).count("https://youtu.be/") == 2)
ck("번역이 자리표시를 잃으면 끝에 붙인다", "RhKwrpHRLeY" in U0.restore_urls("Histoire complète", us_[:1]))
ck("재생목록 이름 = 스튜디오 이름(바뀌면 새 목록이 생긴다)", U0.PLAYLIST.startswith("Every Tale: Korean Folklore"))

print("── 업로드 가드 ──")
import upload_tale as U  # noqa: E402
st_ = U.status_body("private", "2026-10-10T13:00:00Z")
ck("업로드: madeForKids=false · 예약이면 비공개+publishAt", st_["selfDeclaredMadeForKids"] is False
   and st_["privacyStatus"] == "private" and st_["publishAt"] == "2026-10-10T13:00:00Z" and U.MADE_FOR_KIDS is False)
ck("insert 가 status_body 를 쓴다(기록과 같은 값)", "status = status_body(privacy, publish_at)" in open(U.__file__, encoding="utf-8").read())
_pr = ("  Duration: 00:00:44.75, start: 0.000000, bitrate: 2215 kb/s\n"
       "  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1080x1920, 2073 kb/s")
ck("쇼츠 판정 조건 읽기(ffmpeg -i)", U.parse_probe(_pr) == (1080, 1920, 44.75), str(U.parse_probe(_pr)))
_src = open(U.__file__, encoding="utf-8").read()
ck("업로드 기록에 쇼츠 공개 시각·판정 조건(본 쇼츠·추가 쇼츠)",
   _src.count('done.setdefault("shorts_meta", {})') == 2 and '"publish_at": s_at' in _src and '"publish_at": x_at' in _src)
import datetime as dt  # noqa: E402
sat = U.next_saturday_15utc(dt.datetime(2026, 10, 1, 3, 0, tzinfo=dt.timezone.utc))
ck("예약: 다음 토요일 15:00 UTC", sat == "2026-10-03T15:00:00Z", sat)
sat = U.next_saturday_15utc(dt.datetime(2026, 10, 3, 12, 0, tzinfo=dt.timezone.utc))
ck("토요일 6시간 안이면 그다음 주", sat == "2026-10-10T15:00:00Z", sat)

print("── 1주 형식 실험(sprint, 2026-10-04~10) ──")
import datetime as _dt  # noqa: E402
import upload_tale as US  # noqa: E402
sp = T.sprint()
ids = [T.assigned_id(f"2026-10-{d:02d}") for d in range(4, 11)]
ck("10/4~10/10 하루 한 편 = 3~9화", ids == list(range(3, 10)), ids)
fmts = [T.entry(i).get("format", "tale") for i in ids]
ck("스프린트 7편은 형식이 전부 다르다", len(set(fmts)) == 7, fmts)
ck("스프린트 전: 10/3 = 2화(이미 씀), 9/30 = 2화", T.assigned_id("2026-10-03") == 2 and T.assigned_id("2026-09-30") == 2)
ck("스프린트 뒤 재개 전(10/11~13)은 9화(이미 써서 루틴이 멈춘다)",
   {T.assigned_id(f"2026-10-{d}") for d in (11, 12, 13)} == {9})
ck("10/14(수)부터 다시 주 1편: 10화 · 10/21 11화 · 10/20 은 10화",
   T.assigned_id("2026-10-14") == 10 and T.assigned_id("2026-10-21") == 11 and T.assigned_id("2026-10-20") == 10)
ck("수면판 1호(1~4화)의 3·4화는 그대로(미신·케데헌)",
   T.entry(3)["slug"] == "korean-superstitions" and T.entry(4)["slug"] == "kpop-demon-hunters-legends")
ck("스프린트 편 날짜", T.sprint_day(3) == _dt.date(2026, 10, 4) and T.sprint_day(9) == _dt.date(2026, 10, 10)
   and T.sprint_day(2) is None and T.sprint_day(10) is None)
sp3 = copy.deepcopy(S)
sp3["id"] = 5
sp3["title"] = "Gumiho " + sp3["title"][:40]
ck("스프린트 편은 추가 쇼츠 없어도 통과", not any("편당" in e for e in T.check(sp3, "x.json")))
_now = _dt.datetime(2026, 10, 4, 2, 0, tzinfo=_dt.timezone.utc)
ck("스프린트 공개: 그날 15:00 UTC · 쇼츠 13:00", US.sprint_times(_dt.date(2026, 10, 4), _now)
   == ("2026-10-04T15:00:00Z", "2026-10-04T13:00:00Z"))
_late = _dt.datetime(2026, 10, 4, 14, 20, tzinfo=_dt.timezone.utc)
ck("렌더가 늦으면 지금+2시간 정각(쇼츠도 본편보다 늦지 않게)", US.sprint_times(_dt.date(2026, 10, 4), _late)
   == ("2026-10-04T16:00:00Z", "2026-10-04T16:00:00Z"))
_mid = _dt.datetime(2026, 10, 4, 12, 30, tzinfo=_dt.timezone.utc)
ck("쇼츠 시각만 지났으면 쇼츠만 민다", US.sprint_times(_dt.date(2026, 10, 4), _mid)
   == ("2026-10-04T15:00:00Z", "2026-10-04T14:00:00Z"))
ck("pov 형식은 WRITING.md 에 설명이 있다", "- `pov`" in open(os.path.join(T.HERE, "WRITING.md"), encoding="utf-8").read())
ck("render·upload 가 스프린트 편 추가 쇼츠를 건너뛴다",
   "T.sprint_day(s[\"id\"])" in open(os.path.join(T.HERE, "render_tale.py"), encoding="utf-8").read()
   and "[] if day else" in open(os.path.join(T.HERE, "upload_tale.py"), encoding="utf-8").read())

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
