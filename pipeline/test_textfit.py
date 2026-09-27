#!/usr/bin/env python3
"""textfit / motion_short 글자 맞춤 회귀 테스트.

    python pipeline/test_textfit.py

브라우저 없이 도는 순수 파이썬 검사다. 실제 렌더 결과(줄 수·넘침)는
헤드리스 크롬으로 따로 확인했고, 여기서는 ★로직이 다시 망가지지 않는지만 잡는다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textfit as TF          # noqa: E402
import motion_short as M      # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


print("── 1. 어절 분해가 원문을 훼손하지 않는다 ──")
# 하이라이트가 어절 경계에 안 맞으면 없던 띄어쓰기가 생기는 사고가 있었다:
#   "몇 번째였나요?" → "몇 번째 였나요?"
for text, big in [
    ("당신의 별자리는 오늘 몇 번째였나요?", "몇 번째"),
    ("20년 만의 여성 총리, 당신 생각은?", "여성 총리"),
    ("오늘 코스피, 여러분은 어디에 베팅하시겠습니까?", "어디에 베팅"),
    ("집 3채를", "3"),
    ("어제 코스피 외국인 순매도 금액", ""),
]:
    got = TF.join(TF.tokens(text, big))
    ck(f"{text[:18]}… (big={big or '-'})", got == text, f"→ {got!r}")

print("\n── 2. 하이라이트가 한 토큰 안에 온전히 남는다 ──")
for text, big in [("20년 만의 여성 총리, 당신 생각은?", "여성 총리"),
                  ("당신의 별자리는 오늘 몇 번째였나요?", "몇 번째")]:
    toks = [t for t, _ in TF.tokens(text, big)]
    ck(f"{big!r} 가 쪼개지지 않음", any(big in t for t in toks), f"→ {toks}")

print("\n── 3. 태그는 폭 계산에서 빠진다 ──")
a = TF.measure("청문회 이틀 전 3채 전격 매도", 68)
b = TF.measure("청문회 <b>이틀 전</b> 3채 전격 매도", 68)
ck("<b> 유무가 폭을 바꾸지 않는다", abs(a - b) < 0.01, f"{a:.1f} vs {b:.1f}")

print("\n── 4. 줄 수·폭 제약을 지킨다 ──")
CASES = [
    ("환율이 1,390원을 다시 넘어섰다는 점, 외국인 수급에 직결된다", 836, 68, 54, 3, ""),
    ("지금은 사는 자리가 아니라 지키는 자리라고 봅니다", 920, 90, 62, 3, ""),
    ("오늘 코스피, 여러분은 어디에 베팅하시겠습니까?", 920, 116, 78, 3, "어디에 베팅"),
    ("물고기자리 — 오늘 만나는 사람 중에 답이 있습니다", 836, 68, 54, 3, ""),
]
for text, box, base, mn, ml, big in CASES:
    px, lines = TF.fit(text, box, base, min_px=mn, max_lines=ml, big=big)
    widest = max(TF.measure(ln, px, big) for ln in lines)
    ok = len(lines) <= ml and widest <= box and mn <= px <= base
    ck(f"{px}px / {len(lines)}줄 / 최대 {widest:.0f}px  «{text[:22]}…»", ok,
       f"제약: ≤{ml}줄, ≤{box}px, {mn}~{base}px")
    # 줄을 다시 이었을 때 원문과 같아야 한다(글자 유실 없음)
    ck("   재조합 == 원문", " ".join(lines) == text, f"→ {' '.join(lines)!r}")

print("\n── 5. 줄이 문장부호로 시작하지 않는다 ──")
px, lines = TF.fit("20년 만의 여성 총리, 당신 생각은?", 920, 116,
                   min_px=78, max_lines=3, big="여성 총리")
ck("쉼표 고아 없음", not any(ln[0] in ",.!?)]}" for ln in lines), f"→ {lines}")

print("\n── 6. 한 줄로 들어오면 크기를 안 깎는다 ──")
px, lines = TF.fit("코스피 3일 누적", 920, 48, min_px=34, max_lines=1)
ck("짧은 라벨은 기본 크기 유지", (px, len(lines)) == (48, 1), f"→ {px}px {lines}")

print("\n── 7. 조금 줄여 줄 수를 아낄 수 있으면 그렇게 한다 ──")
t = "당신의 별자리는 오늘 몇 번째였나요?"
big3, _ = TF.fit(t, 920, 116, min_px=78, max_lines=3, big="몇 번째", prefer_fewer=0)
px, lines = TF.fit(t, 920, 116, min_px=78, max_lines=3, big="몇 번째")
ck(f"prefer_fewer 끄면 3줄(116px) → 켜면 {len(lines)}줄({px}px)", len(lines) == 2,
   f"→ {lines}")

print("\n── 8. 토픽별 액센트 ──")
for topic, want in [("politics", "#D97757"), ("stock_us", "#E5484D"),
                    ("zodiac", "#7C6BD6"), ("fortune", "#C9A227"),
                    ("", "#D97757"), ("무엇인가", "#D97757")]:
    got = M.topic_accent(topic)
    ck(f"{topic or '(빈값)'} → {got}", got == want, f"기대 {want}")

print("\n── 9. scene_html 이 모든 타입에서 안 터진다 ──")
TYPES = [
    {"type": "hook", "lines": ["어젯밤 미국이", "이렇게 끝났는데"], "highlight": "이렇게",
     "pill": "국장", "ghost": "KOSPI"},
    {"type": "stat", "label": "외국인 순매도", "from": 0, "to": 4820, "suffix": "억",
     "bar": True, "sub": "이틀 연속 <b>순매도</b>"},
    {"type": "gauge", "label": "거래대금", "from": 1, "to": 3, "unit": "배", "sub": "평소의 <b>3배</b>"},
    {"type": "trend", "dir": "down", "label": "코스피 3일", "from": 0, "to": -3,
     "sub": "기관도 <b>순매도</b>", "closer": "반등이 나올 수 있을까요?"},
    {"type": "quote", "text": "지금은 지키는 자리라고 봅니다", "attr": "— 리서치센터장"},
    {"type": "keypoint", "label": "관전 포인트", "points": ["<b>3.2%</b> 하락", "환율 <b>1,390원</b>"]},
    {"type": "statement", "text": "여러분은 어디에 베팅하시겠습니까?", "highlight": "어디에 베팅"},
]
for i, sc in enumerate(TYPES):
    sc.update(start=i * 5.0, clip=6.0, narration="테스트")
    try:
        html = M.scene_html(i, sc, "#D97757")
        js = M.scene_js(i, sc, "#D97757")
        ck(f"{sc['type']:<10} html {len(html):>5}B · js {len(js.splitlines()):>2}줄",
           len(html) > 200 and len(js) > 50)
    except Exception as e:  # noqa: BLE001
        ck(f"{sc['type']} 렌더", False, f"{type(e).__name__}: {e}")

print("\n── 10. 타임라인 셀렉터가 실제 HTML 에 존재한다 ──")
import re  # noqa: E402
for i, sc in enumerate(TYPES):
    html = M.scene_html(i, sc, "#D97757")
    js = M.scene_js(i, sc, "#D97757")
    miss = []
    for sel in set(re.findall(r'"(#s\d+[\w -]*)"', js)):
        m = re.match(r"^#([\w-]+)(?: \.([\w-]+))?$", sel)
        if not m:
            continue
        if f'id="{m.group(1)}"' not in html:
            miss.append(sel)
        elif m.group(2) and f'class="{m.group(2)}"' not in html:
            miss.append(sel)
    ck(f"{sc['type']:<10} 셀렉터 정합", not miss, f"없는 것: {miss}")

print("── 키비주얼 배경 on/off ──")
# 그림이 없을 때는 ★기존 화면과 한 글자도 다르면 안 된다(실패 시 폴백이 기존 모습이어야 한다).
_sc = [{"type": "statement", "text": "가나다 라마", "highlight": "라마", "narration": "x",
        "start": 0.0, "clip": 3.0},
       {"type": "statement", "text": "바사 아자", "highlight": "아자", "narration": "y",
        "start": 2.6, "clip": 3.0}]
_off = M.build_html(_sc, 5.6, "#D97757")
_on = M.build_html(_sc, 5.6, "#D97757", bg=True)
ck("bg=False 면 배경 레이어 없음", 'id="bg"' not in _off and "_bg.jpg" not in _off)
ck("bg=True 면 배경·스크림 레이어", 'id="bg"' in _on and 'id="scrim"' in _on)
ck("bg=True 면 나가는 장면을 지운다(글자 겹침 방지)",
   'tl.to("#s0",{opacity:0' in _on and 'tl.to("#s1",{opacity:0' not in _on)
ck("bg=True 면 배경을 영상 길이만큼 당긴다", 'tl.fromTo("#bg"' in _on and "duration:5.60" in _on)

import cover_short as CS  # noqa: E402
ck("운세 토픽은 캐릭터 그림체", CS._fields({"topic": "fortune"})[2] == "topic:fortune")
ck("별자리(horoscope)는 천체 그림체", CS._fields({"topic": "horoscope"})[2] == "topic:horoscope")
ck("정치는 보도사진 톤 유지", CS._style_prompt(CS._fields({"topic": "politics"})[2]) == CS.NEWS_PRESET)
ck("스토리보드 thumbnail_style 이 토픽보다 우선",
   CS._fields({"topic": "fortune", "thumbnail_style": "webtoon"})[2] == "webtoon")

print("── 진행자(별이·별하) ──")
ck("진행자 이미지 두 장이 레포에 있다(없으면 조용히 꺼진다)", M.presenter_on())
_sp = M.assign_speakers([dict(s) for s in _sc] + [dict(_sc[0])], duo=True)
ck("별하부터 번갈아 말한다", [s["_spk"] for s in _sp] == ["byeolha", "byeori", "byeolha"])
ck("duo=False 면 별하 혼자", {s["_spk"] for s in M.assign_speakers([dict(s) for s in _sc], duo=False)} == {"byeolha"})
_pon = M.build_html(M.assign_speakers([dict(s) for s in _sc]), 5.6, "#D97757", presenter=True)
ck("presenter=False 면 진행자 레이어 없음", 'id="pr"' not in _off)
ck("presenter=True 면 두 캐릭터·데스크", 'id="pr-byeori"' in _pon and 'id="pr-byeolha"' in _pon and 'id="desk"' in _pon)
ck("진행자 이미지 경로가 실제 파일", all(os.path.exists(os.path.join(M.PROJ, p)) for p in
                                  re.findall(r'src="(assets/presenter/[^"]+)"', _pon)))
_stat = [{"type": "stat", "label": "x", "from": 0, "to": 3, "bar": True, "sub": "y",
          "narration": "z", "start": 0.0, "clip": 3.0}]
ck("진행자 모드에선 막대가 낮아진다(캐릭터 자리 비움)",
   "height:360" in M.build_html(_stat, 3.0, presenter=True) and "height:560" in M.build_html(_stat, 3.0))
ck("말하는 쪽 이름표가 켜진다", 'tl.to("#nm-byeolha",{opacity:1' in _pon and 'tl.to("#nm-byeori",{opacity:1' in _pon)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
