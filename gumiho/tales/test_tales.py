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
S = T.load(os.path.join(HERE, "scripts", "001_gumiho.json"))          # 설화편(예전 규칙 회귀)
XP = os.path.join(HERE, "scripts", "027_places-you-cant-survive.json")  # 해설편 견본(2026-10-09~)
X = T.load(XP)

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
ck("10/10 부터 설화 편성 없음(10/14·10/21 은 해설편 또는 없음)",
   T.assigned_id("2026-10-14") in (None, 27) and T.assigned_id("2026-10-21") == 28)
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
ids = [T.assigned_id(f"2026-10-{d:02d}") for d in range(4, 10)]
ck("10/4~10/9 하루 한 편 = 3~8화(기록)", ids == list(range(3, 9)), ids)
ck("스프린트 끝: 10/10 은 9화(설화)를 배정하지 않는다", T.assigned_id("2026-10-10") is None)
fmts = [T.entry(i).get("format", "tale") for i in range(3, 10)]
ck("스프린트 7편은 형식이 전부 다르다", len(set(fmts)) == 7, fmts)
ck("스프린트 전: 10/3 = 2화(이미 씀), 9/30 = 2화", T.assigned_id("2026-10-03") == 2 and T.assigned_id("2026-09-30") == 2)
ck("10/10·10/11 은 쓸 편 없음(설화 9·10화 대신 쉰다)", T.assigned_id("2026-10-10") is None and T.assigned_id("2026-10-11") is None)
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
_w = open(os.path.join(T.HERE, "WRITING.md"), encoding="utf-8").read()
ck("WRITING.md 에 해설편 형식 설명(places·zones·whatif·ranked·abandoned)", all(f"- `{f}`" in _w for f in T.EXPLAINER_FORMATS))
ck("render·upload 가 스프린트 편 추가 쇼츠를 건너뛴다",
   "T.sprint_day(s[\"id\"])" in open(os.path.join(T.HERE, "render_tale.py"), encoding="utf-8").read()
   and "[] if day else" in open(os.path.join(T.HERE, "upload_tale.py"), encoding="utf-8").read())

print("── 해설편 편성(2026-10-09 개편: 설화 금지 · 일요일 14:00 UTC) ──")
import datetime as _d2  # noqa: E402
import subprocess  # noqa: E402
_cat = T.load(T.CATALOG)
FOLK_REGIONS = {"KR", "JP", "CN", "EA"}
ck("설화 편(지역 KR·JP·CN·EA)은 전부 retired 로 남아 있다(지우지 않는다)",
   all(e.get("retired") for e in _cat["tales"] if e.get("region") in FOLK_REGIONS)
   and len([e for e in _cat["tales"] if e.get("region") in FOLK_REGIONS]) == 26)
_day, _bad = _d2.date(2026, 10, 10), []
while _day <= _d2.date(2027, 3, 31):
    _e = T.next_entry(_day.isoformat())
    if _e and (_e.get("retired") or _e.get("region") in FOLK_REGIONS or _e.get("format") not in T.EXPLAINER_FORMATS):
        _bad.append((_day.isoformat(), _e["id"]))
    _day += _d2.timedelta(days=1)
ck("10/10 ~ 2027-03-31 어느 날에도 설화 편이 배정되지 않는다", not _bad, str(_bad[:3]))
_new = [e for e in _cat["tales"] if not e.get("retired")]
ck("새 편 3개: 10/18·10/25·11/1", [e["date"] for e in _new] == ["2026-10-18", "2026-10-25", "2026-11-01"], str(_new))
ck("새 편은 전부 일요일", all(_d2.date.fromisoformat(e["date"]).weekday() == 6 for e in _new))
ck("공개 시각 = 그 일요일 14:00 UTC", [T.publish_at(e) for e in _new]
   == ["2026-10-18T14:00:00Z", "2026-10-25T14:00:00Z", "2026-11-01T14:00:00Z"])
ck("10/10~10/17 사이에 공개되는 편이 없다",
   not [e for e in _new if "2026-10-10" <= e["date"] <= "2026-10-17"])
ck("새 편 제목(카운트다운·심해·태양)", [e["title_idea"] for e in _new] == [
    "10 Places on Earth You Can't Survive — Explained",
    "The Deep Sea, Explained: Every Zone and What Lives There",
    "What If the Sun Disappeared? Minute by Minute"])
ck("새 편 형식은 해설편(places·zones·whatif)", [e["format"] for e in _new] == ["places", "zones", "whatif"])
ck("새 편 facts 10개 이상·출처 3개 이상(모두 링크)", all(len(e["facts"]) >= 10 and len(e["sources"]) >= 3
                                                and all("https://" in x for x in e["sources"]) for e in _new))
ck("새 편 facts 에 숫자가 있다(편마다 조사한 수치)", all(sum(bool(T.NUM.search(f)) for f in e["facts"]) >= 8 for e in _new))
ck("backlog 후보 6개(제목만)", len(_cat.get("backlog") or []) == 6 and all(isinstance(x, str) for x in _cat["backlog"]))
ck("토요일(공개 하루 전) next → 그 주 편", T.next_entry("2026-10-17")["id"] == 27 and T.next_entry("2026-10-24")["id"] == 28
   and T.next_entry("2026-10-31")["id"] == 29)
ck("일요일 당일도 그 편 · 다음 날(월)은 다음 주 편", T.next_entry("2026-10-18")["id"] == 27 and T.next_entry("2026-10-19")["id"] == 28)
ck("catalog 끝 뒤(11/2~)는 없음", T.next_entry("2026-11-02") is None)
ck("날짜 없이 next 도 retired 를 고르지 않는다", T.next_entry(None) is None or not T.next_entry(None).get("retired"))
_tp = os.path.join(HERE, "tales.py")
_o = subprocess.run([sys.executable, _tp, "next", "--date", "2026-10-10"], capture_output=True, text=True, encoding="utf-8")
ck("CLI next 10/10 → {\"none\": true}(루틴은 아무것도 안 쓴다)", _o.returncode == 0 and json.loads(_o.stdout).get("none") is True,
   _o.stdout[:120])
_o = subprocess.run([sys.executable, _tp, "next", "--date", "2026-10-17"], capture_output=True, text=True, encoding="utf-8")
_j = json.loads(_o.stdout)
ck("CLI next 10/17 → 027 · 공개 시각 · 다음 주 예고 · 견본 준비", _j.get("file") == "027_places-you-cant-survive.json"
   and _j.get("publish_at") == "2026-10-18T14:00:00Z" and _j.get("teaser", {}).get("date") == "2026-10-25"
   and _j["teaser"]["line"].startswith("Next Sunday: The Deep Sea") and _j.get("exemplar_ready") is True, _o.stdout[:200])
_t29 = T.teaser_for(T.entry(29))
ck("마지막 편(11/1) 예고는 편성 안 된 backlog 를 약속하지 않는다", _t29["title"] == "" and _t29["date"] is None
   and _t29["line"] == "A new one next Sunday.", str(_t29))
import upload_tale as UW  # noqa: E402
_sat = _d2.datetime(2026, 10, 17, 3, 0, tzinfo=_d2.timezone.utc)
ck("업로드 예약: 토요일에 올리면 일요일 14:00 UTC", UW.weekly_time("2026-10-18", _sat) == "2026-10-18T14:00:00Z")
_late = _d2.datetime(2026, 10, 18, 13, 30, tzinfo=_d2.timezone.utc)
ck("늦으면 한 주 미루지 않고 지금+2시간 정각", UW.weekly_time("2026-10-18", _late) == "2026-10-18T15:00:00Z")
ck("해설편 본 쇼츠는 본편 하루 뒤(월) · 설화편은 하루 전", UW.main_short_at("2026-10-18T14:00:00Z", True) == "2026-10-19T14:00:00Z"
   and UW.main_short_at("2026-10-10T15:00:00Z", False) == "2026-10-09T15:00:00Z")
ck("추가 쇼츠: 일요일 본편 → 수·금", UW.extra_short_at("2026-10-18T14:00:00Z", 2) == "2026-10-21T14:00:00Z"
   and UW.extra_short_at("2026-10-18T14:00:00Z", 3) == "2026-10-23T14:00:00Z")
ck("AI 합성 고지(containsSyntheticMedia) — RULES 도 같은 status_body", UW.CONTAINS_SYNTHETIC_MEDIA is True
   and UW.status_body("private", None)["containsSyntheticMedia"] is True)
_us = open(UW.__file__, encoding="utf-8").read()
ck("업로드가 retired 편을 막는다", "T.retired(s[\"id\"]) and not a.allow_retired" in _us)
ck("해설편 재생목록 3개 = CHANNEL.md", all(v[0] in open(os.path.join(HERE, "CHANNEL.md"), encoding="utf-8").read()
                                       for v in UW.EX_PLAYLISTS.values()) and len({v[0] for v in UW.EX_PLAYLISTS.values()}) == 3)
_o = subprocess.run([sys.executable, _tp, "check", os.path.join(HERE, "scripts", "001_gumiho.json")],
                    capture_output=True, text=True, encoding="utf-8")
ck("CLI check: retired 편은 ❌(워크플로가 렌더 전에 멈춘다)", _o.returncode == 1 and "retired" in _o.stdout, _o.stdout[-160:])

print("── 해설편 대본 검사 ──")
ck("해설편 견본 통과", not T.check(X, XP), str(T.check(X, XP)[:4]))
_st = T.stats(X)
ck(f"견본 분량 10~12분(추정 {_st['est_min']}분 · {_st['words']}단어)", 9.6 <= _st["est_min"] <= 12.0)
ck("explainer = 27화부터", T.explainer(X) and not T.explainer(S))


def _bad(fn):
    b = copy.deepcopy(X)
    fn(b)
    return T.check(b, XP)


def _img_i(b):
    return next(i for i, x in enumerate(b["scenes"]) if x.get("img"))


ck("말에 설화 단어(gumiho) → 거부", any("금지 주제" in e for e in _bad(lambda b: b["scenes"][4].update(say=b["scenes"][4]["say"] + " Like a gumiho."))))
ck("그림에 hanbok → 거부", any("금지 주제" in e for e in _bad(lambda b: b["scenes"][_img_i(b)].update(img=b["scenes"][_img_i(b)]["img"] + ", a woman in hanbok"))))
ck("그림에 fox → 거부", any("여우" in e for e in _bad(lambda b: b["scenes"][_img_i(b)].update(img=b["scenes"][_img_i(b)]["img"] + ", a red fox watching"))))
ck("제목에 Joseon → 거부", any("금지 주제" in e for e in _bad(lambda b: b.update(title="Joseon " + b["title"][:50]))))
ck("태그에 korean folklore → 거부", any("금지 주제" in e for e in _bad(lambda b: b["tags"].append("korean folklore"))))
ck("SCP·Backrooms → 거부", any("금지 주제" in e for e in _bad(lambda b: b["scenes"][4].update(say=b["scenes"][4]["say"] + " Like the Backrooms."))))
ck("출처 없음 → 거부", any("출처" in e or "'sources' 없음" in e for e in _bad(lambda b: b.update(sources=[]))))
ck("출처에 링크 없음 → 거부", any("링크" in e for e in _bad(lambda b: b.update(sources=["NASA", "NOAA", "USGS"]))))
ck("구미 그림 장면 → 거부", any("구미를 그리지" in e for e in _bad(lambda b: b["scenes"].insert(2, {"say": "Hello there.", "gumi": "front"}))))
ck("look 이 real 이 아니면 → 거부", any("real" in e for e in _bad(lambda b: b.update(look="modern"))))
ck("catalog 에 없는 숫자 → 거부(지어낸 통계)", any("catalog facts 에 없는 숫자" in e
                                         for e in _bad(lambda b: b["scenes"][4].update(say=b["scenes"][4]["say"] + " It is 4,321 meters deep."))))
ck("작은 수(순위·셋)는 자유", not T.loose_numbers("Number 10. Three of 7 people.", set(), 27))
ck("첫 장면에 숫자 없음 → 거부", any("첫 장면에 숫자" in e for e in _bad(lambda b: b["scenes"][0].update(say="This place is very hot and very dry and not friendly at all."))))


def _no_odds(b):
    k = next(i for i, x in enumerate(b["scenes"]) if x.get("odds"))
    del b["scenes"][k]["odds"]


ck("꼭지에 판정 띠(odds) 없음 → 거부", any("판정 띠" in e for e in _bad(_no_odds)))
ck("VERDICT 카드 없음 → 거부", any("VERDICT" in e for e in _bad(lambda b: b.update(scenes=[x for x in b["scenes"] if str(x.get("card", "")).upper() != "VERDICT"]))))
ck("다음 주 예고 없음 → 거부", any("예고" in e for e in _bad(lambda b: [x.update(say=x["say"].replace("Next", "Then").replace("next", "then")) for x in b["scenes"][-3:] if x.get("say")])))


def _dup_img(b):
    ims = [x for x in b["scenes"] if x.get("img")]
    ims[1]["img"] = ims[0]["img"]


ck("같은 그림 프롬프트 두 번(재사용 정지 화면) → 거부", any("새 그림" in e for e in _bad(_dup_img)))
ck("쇼츠 제목이 한 꼭지 질문 꼴이 아니면 → 거부", any("제목 꼴" in e for e in _bad(lambda b: b["short"].update(title="Ten Scary Places #shorts"))))
_seg = T.segments(X["scenes"])
_keys = {x["key"]: _seg[i] for i, x in enumerate(X["scenes"]) if x.get("key")}


def _two_seg(b):
    own = {_keys[ln["scene"]] for ln in b["short"]["lines"] if ln.get("scene")}
    other = next(k for k, v in _keys.items() if v not in own)
    ln = next(ln for ln in b["short"]["lines"][1:] if ln.get("scene"))
    ln["scene"] = other


ck("쇼츠가 여러 꼭지 장면을 섞으면 → 거부(한 꼭지만)", any("여러 꼭지" in e for e in _bad(_two_seg)))
ck("쇼츠에 구미 줄 → 거부", any("구미 그림 금지" in e for e in _bad(lambda b: b["short"]["lines"].__setitem__(-1, {"say": "Full video on my channel.", "gumi": "wink"}))))
ck("한 꼭지 제목 판별", bool(T.SINGLE_ITEM.search("How Long Would You Last at the Floor of the Mariana Trench? #shorts"))
   and bool(T.SINGLE_ITEM.search("Lut Desert vs Death Valley: Which Is Hotter? #shorts"))
   and not T.SINGLE_ITEM.search("They Wished for a Daughter #shorts"))
ck("본편 쇼츠 = 같은 꼭지 장면만(견본 쇼츠 전부)", all(len({_keys[ln["scene"]] for ln in sh["lines"] if ln.get("scene")}) == 1
                                         for sh in [X["short"]] + X["shorts_extra"]))

_X0 = T.load(XP)


def _bad2(fn):
    b = copy.deepcopy(_X0)
    fn(b)
    return T.check(b, XP)


def _odds_i(b):
    return next(i for i, x in enumerate(b["scenes"]) if x.get("odds"))


print("── 리뷰 10/9: 검사 구멍 ──")
ck("띠에 출처 없는 작은 수 시간('TIME YOU'D LAST: 10 SECONDS') → 거부",
   any("odds" in e for e in _bad2(lambda b: b["scenes"][_odds_i(b)].update(odds="TIME YOU'D LAST: 10 SECONDS"))))
ck("띠 이름이 SURVIVAL ODDS 라도 출처 없는 시간 → 거부",
   any("시간" in e for e in _bad2(lambda b: b["scenes"][_odds_i(b)].update(odds="SURVIVAL ODDS: 10 SECONDS"))))
ck("띠에 글자로 쓴 수 → 거부", any("글자로 쓴 수" in e for e in _bad2(lambda b: b["scenes"][_odds_i(b)].update(odds="SURVIVAL ODDS: TEN MINUTES"))))
ck("말에 글자로 쓴 시간('ninety seconds') → 거부",
   any("글자로 쓴 시간" in e for e in _bad2(lambda b: b["scenes"][4].update(say=b["scenes"][4]["say"] + " You'd last ninety seconds."))))
ck("말에 출처 없는 작은 수 시간('2 hours') → 거부",
   any("시간" in e and "2 hour" in e for e in _bad2(lambda b: b["scenes"][4].update(say=b["scenes"][4]["say"] + " You'd last 2 hours."))))
ck("출처에 있는 시간('9 to 12 seconds')은 통과", not T.time_errs("x", "about 9 to 12 seconds of useful consciousness", T.entry(27)))
ck("썸네일 문구 숫자 대조", any("숫자" in e for e in _bad2(lambda b: b["thumb"].update(text="4,321 METERS"))))
ck("쇼츠 hook 숫자 대조", any("숫자" in e for e in _bad2(lambda b: b["short"].update(hook="999°C GROUND"))))
ck("쇼츠 제목 숫자 대조", any("숫자" in e for e in _bad2(lambda b: b["shorts_extra"][0].update(
    title="What Happens If You Go 99,000 Feet Up? #shorts"))))
ck("catalog 에 없는 출처 링크 → 거부", any("catalog 출처에 없다" in e for e in _bad2(
    lambda b: b["sources"].append("Some blog — Top 10 places: https://example.com/top10"))))


def _no_src(b):
    k = next(i for i, x in enumerate(b["scenes"]) if x.get("card") and x.get("src"))
    del b["scenes"][k]["src"]


ck("꼭지 카드 src 없음 → 거부", any("src" in e for e in _bad2(_no_src)))
for _w in ("Japanese folklore", "kappa", "oni", "urban legend", "Chinese legends", "folklore"):
    ck(f"금지어 '{_w}'(제목·태그·말) → 거부", any("금지 주제" in e for e in _bad2(lambda b, w=_w: b["tags"].append(w)))
       and any("금지 주제" in e for e in _bad2(lambda b, w=_w: b["scenes"][4].update(say=b["scenes"][4]["say"] + f" Like {w}."))))
ck("제목의 금지어 → 거부", any("금지 주제" in e for e in _bad2(lambda b: b.update(title="10 Yokai Places You Can't Survive"))))
_w = open(os.path.join(T.HERE, "WRITING.md"), encoding="utf-8").read()
ck("WRITING.md 예시에 살아남는 시간·'right now' 없음", "YOU'D LAST" not in _w and "Time you'd last" not in _w
   and "pressure you feel right now" not in _w)
ck("catalog 해설편 angle·facts 에 날짜 타는 말 없음", not any(T.DATED.search(e["angle"] + " ".join(e["facts"]))
                                         for e in T.load(T.CATALOG)["tales"] if not e.get("retired")))
_f27 = " ".join(T.entry(27)["facts"])
ck("옐로스톤 시추공 = NPS(1967 · 238 °C · 332 m) · 출처에 NPS 페이지",
   "238 °C" in _f27 and "332 m" in _f27 and "237" not in _f27 and "326" not in _f27
   and any("vitalsigns/temps.htm" in x for x in T.entry(27)["sources"]))
_y = next(x for x in X["scenes"] if "drill hole" in x.get("say", ""))
ck("견본 대본도 238 °C · 332 m", "238" in _y["say"] and "332" in _y["say"], _y["say"])
ck("견본 띠: 살아남는 시간 대신 AWAKE FOR", any(x.get("odds") == "AWAKE FOR: 1–5 MINUTES" for x in X["scenes"])
   and not any("hours, for a prepared climber" in x.get("say", "") for x in X["scenes"]))

print("── 해설편 메타·화면 ──")
_md = T.meta(X, [i * 10.0 for i in range(len(X["scenes"]))], more=[("Ep", "https://youtu.be/E")])
ck("설명: 출처 링크 전부·AI 합성 고지·일요일 안내", all(x in _md["description"] for x in X["sources"])
   and "AI-generated" in _md["description"] and "Sunday" in _md["description"])
ck("설명·태그에 설화 흔적 없음", not T.FOLKLORE.search(_md["description"]) and not any(T.FOLKLORE.search(x) for x in _md["tags"]))
_chap = [ln for ln in _md["description"].splitlines() if ln[:2].isdigit() and ":" in ln[:6]]
ck("챕터: 00:00 + 꼭지마다 + 판정", _chap[0].startswith("00:00") and any("#1 " in c for c in _chap)
   and any("Verdict" in c for c in _chap), str(_chap[:3]))
_smd = T.meta(X, None, short_of="https://youtu.be/L")
ck("쇼츠 설명: 본편 링크 + 출처", "Full video: https://youtu.be/L" in _smd["short"]["description"]
   and "Sources:" in _smd["short"]["description"] and all("youtu.be/L" in x["description"] for x in _smd["shorts_extra"]))
ck("쇼츠 설명 출처 = 그 쇼츠가 자른 꼭지 출처(에베레스트·암스트롱·루트)",
   "Matthews" in _smd["short"]["description"] and "Lut" not in _smd["short"]["description"]
   and "UBC" in _smd["shorts_extra"][0]["description"] and "Matthews" not in _smd["shorts_extra"][0]["description"]
   and "Lut" in _smd["shorts_extra"][1]["description"] and "Challenger" not in _smd["shorts_extra"][1]["description"])
for _e in [e for e in T.load(T.CATALOG)["tales"] if not e.get("retired")]:
    _fake = dict(X, id=_e["id"], sources=_e["sources"], hook="h" * 200)
    _d = T.meta(_fake, [i * 10.0 for i in range(len(X["scenes"]))], more=[("A" * 90, "https://youtu.be/A")] * 4)["description"]
    ck(f"{_e['id']}화 설명 5,000바이트 이하 · 출처 전부·AI 고지 남음", len(_d.encode("utf-8")) <= 5000
       and all(x in _d for x in _e["sources"]) and "AI-generated" in _d, str(len(_d.encode("utf-8"))))
ck("화풍: real 은 TALES_STYLE 과 무관하게 실사", "photorealistic" in R.look_prefix("real") and "anime" not in R.look_prefix("real")
   and "no text" in R.look_prefix("real"))
ck("띠 문구: 해설편 EXPLAINED · 설화편 KOREAN LEGEND", T.badge(X) == "EXPLAINED" and T.badge(S) == "KOREAN LEGEND")
ck("쇼츠 끝맺음 문구(2026-10-09): FULL VIDEO ↓ / tap the link below", R.CTA_TOP == "FULL VIDEO ↓"
   and R.CTA_TEXT == "tap the link below" and "link" in R.CTA_SAY.lower() and "tale" not in R.CTA_SAY.lower()
   and "ENDING" not in R.CTA_TOP)
import sleep as SL  # noqa: E402
ck("수면판(설화 재편집) 꺼짐", SL.ENABLED is False)
with tempfile.TemporaryDirectory() as tdx:
    shx = R.plan(X)
    texts = [x["say"] for x in shx if x["say"]] + [ln["say"] for sh in [X["short"]] + X["shorts_extra"] for ln in sh["lines"]] + [R.CTA_SAY]
    vx = R.synth(texts, os.path.join(tdx, "tts"), mock=True)
    tot = R.timeline(shx, vx)
    ck(f"견본 타임라인 10~12.5분(가짜 목소리 {tot / 60:.1f}분)", 9.5 * 60 <= tot <= 12.5 * 60)
    ix = R.make_images(X, shx, os.path.join(tdx, "img"), mock=True,
                       extra_prompts=R.short_only_prompts(X, shx, X["shorts_extra"]))
    pax = R.Painter({"shots": shx, "total": tot})
    ko = next(k for k, x in enumerate(shx) if x.get("odds"))
    fo = np.asarray(pax.frame(shx[ko]["start"] + shx[ko]["dur"] * 0.6)).astype(int)
    fp = np.asarray(pax.frame(shx[ko]["start"] + 0.1)).astype(int)
    _red = lambda a: float(np.mean((a[80:150, 90:400, 0] > 150) & (a[80:150, 90:400, 1] < 90)))  # noqa: E731
    ck("판정 띠(odds)가 화면 왼쪽 위에 뜬다(장면 첫머리엔 없다)", _red(fo) > 0.2 and _red(fp) < 0.05, f"{_red(fo):.2f}/{_red(fp):.2f}")
    R.thumbnail(X, ix["thumb_raw"], os.path.join(tdx, "t.jpg"))
    th = np.asarray(R.Image.open(os.path.join(tdx, "t.jpg"))).astype(int)
    ck("해설편 썸네일 1280×720 · 오른쪽 아래 구미 배지(빨간 원) 없음",
       th.shape[:2] == (720, 1280) and float(np.mean((th[470:690, 1030:1250, 0] > 180) & (th[470:690, 1030:1250, 1] < 80))) < 0.2)
    spx = R.short_plan(X, shx, vx, tdx, ix["thumb_raw"], ix["raw"])
    ck(f"해설편 쇼츠 {spx['total']:.0f}초 ≤ {R.SHORT_MAX:.0f} · 끝맺음 있음", spx["total"] <= R.SHORT_MAX and spx["rows"][-1].get("cta"))
    sppx = R.ShortPainter(spx, X)
    endx = spx["rows"][-1]
    fcx = np.asarray(sppx.frame(endx["start"] + 1.5)).astype(int)
    _white = float(np.mean(np.all(fcx[1150:1290, 140:800] > 235, axis=-1)))
    ck("끝맺음 카드에 글자(FULL VIDEO + 도형 ↓)", _white > 0.03, f"{_white:.3f}")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
