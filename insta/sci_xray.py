#!/usr/bin/env python3
"""인스타 sci '속이 보이는 과학' — 투시(xray)·단면(cutaway) 3D 그림 + 원인 3단계 (2026-10-24, 10/25 저녁 편부터).

왜: 사용자 10/24 승인. 벤치마크 셋(사용자가 보낸 것):
  ① so.thats.how 'Dishwasher' 808만 — 기계를 잘라 연 3D 단면. 단순한 모양이라 폰에서 한눈에 읽힌다("잘 그린 게 아니라 잘 보여 준다").
  ② 해외 건강 쇼츠(첫 달 1,000만) — 피부가 투명한 픽사풍 3D 사람(뼈·장기가 비친다). 23초: 0~6초 대조 훅 → 6~7초 '왜?' →
     7~18초 원인 3단계 → 18~23초 결과.
  ③ '1,000만 뷰 등급표' — 바이럴 꼴과 저장률이 제일 크고 해시태그가 제일 작다.
그래서 sci 주제·편성(pick_plan SCI_ORDER — 심해·우주·극한 생존)은 그대로 두고 모양만 바꾼다(SCI_XRAY_FROM 부터):
  hook(대조·충격 질문 두 줄) → why('왜?' 한 박자) → beats 정확히 3개(화면에 1/3·2/3·3/3) → verdict(결과) · 20~35초.
  박자마다 view: xray(투명한 몸 속 뼈·장기) · cutaway(겉을 잘라 연 기계·행성·바다 층) · scene(대체 — 셋 중 하나까지).
  코드가 view 에 맞는 화풍 꼬리를 붙이고(그림은 밝은 단색 배경 3D · 정사각), 한글 이름표(label → pin 을 가리키는 칩 + 가는 선)·
  단계 배지·1→2→3 진행 표시·큰 숫자·설명을 그린다 — 글자는 그림 모델이 아니라 코드가 그린다.
  10/14 교훈(어두운 첫 화면은 피드에서 안 멈춘다): 밝은 배경 + 평균 밝기가 낮으면 끌어올림 · 첫 프레임 밝기를 meta 에 남긴다.

화면(1080×1920): 위 훅(첫 장면은 크게, 그 뒤 작게) · 진행 표시 · 큰 숫자 + 설명 · 가운데 무대(정사각 그림, 위아래는 그림 가장자리 색으로
  이어 붙임 · 천천히 다가감) · 그린 것은 모두 y 1440 위 — 아래 25%는 인스타 캡션·버튼 자리라 그림만 있다(pin ≤ 0.85).
숫자·출처·내용 한계는 옛 sci 와 같다(pick_reel 의 facts 맞춰 보기 · SCI_GORE·SCI_PEOPLE·SCI_FRANCHISE · SCI_IMG_BAN · ASK_BAN).

    python insta/pick_reel.py check <sci 대본.json>          # 날짜가 SCI_XRAY_FROM 이후면 pick_reel 이 이 모듈로 넘긴다
    python insta/pick_reel.py render <sci 대본.json> --out … [--mock]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402  (숫자 검사·내용 한계·출처·캡션·소리 섞기를 같이 쓴다)
import render_reel as R  # noqa: E402  (글꼴·목소리·인코딩)

W, H, FPS, SR = R.W, R.H, R.FPS, R.SR
LZ = getattr(Image, "Resampling", Image).LANCZOS
BIL = getattr(Image, "Resampling", Image).BILINEAR
EXTENT = getattr(Image, "Transform", Image).EXTENT

VIEWS = P.SCI_XRAY_VIEWS
N_STEPS = 3
SCENE_MAX = 1                                             # 세 박자 중 scene(그냥 장면)은 하나까지 — 나머지는 투시·단면
HOOK_MAX, INTRO_MAX = K.SCI_HOOK_MAX, K.SCI_INTRO_MAX     # 14 · 50
WHY_SAY_MAX, WHY_SUB_MAX = 20, 24
BIG_MAX, SUB_MAX, SAY_MAX = K.SCI_BIG_MAX, K.SCI_SUB_MAX, K.SCI_SAY_MAX   # 12 · 24 · 45
VERDICT_BIG_MAX, VERDICT_SAY_MAX = K.SCI_VERDICT_BIG_MAX, K.SCI_VERDICT_SAY_MAX   # 12 · 40
LABEL_MAX = 10
PIN_RANGE = (0.1, 0.85)                                   # 이름표가 가리키는 자리(그림 기준 0~1) — 가장자리·아래 캡션 자리 밖
PIN_DEFAULT = (0.5, 0.5)                                  # pin 을 안 주면 그림 가운데(그림은 '가운데 하나' 로 그린다)
SEC = P.SCI_XRAY_SEC                                      # (20, 35)
TEMPO = K.SCI_TEMPO                                       # 1.1 — 옛 sci 와 같은 빠르기
SPEEDUP = 1.15
CPS = 6.4                                                 # 길이 어림 = 읽는 글자(insta.speech_len)/초 — F1 5.9 × 1.1(sci 빠르기) 쯤
SERIES = "속이 보이는 과학"
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

# 그림 화풍 — view 마다 앞(head)·뒤(tail)를 코드가 붙인다. 밝은 단색 배경(10/14 교훈 · 무대 위아래를 그림 가장자리 색으로 잇는다)
# 10/24 Spark z-image 시험(27장): 어두운 배경(plain dark gradient)은 평균 밝기 80 → 밝은 회청색 배경 165~210.
#   9:16 은 몸이 화면을 꽉 채워 글자와 겹쳐서 정사각(1:1)으로 그리고 가운데 무대에 놓는다.
#   xray 는 'made of clear glass' 를 넣어야 고래·코끼리 머리까지 비친다(없으면 겉이 불투명하게 남았다).
VIEW_STYLE = {
    "xray": ("stylized 3D render, translucent see-through body made of clear glass, ",
             ", the whole body clear like glass so the glowing white skeleton and soft organs show inside, "
             "soft blue studio light, plain light grey-blue gradient background, centered, whole subject in frame"),
    "cutaway": ("clean 3D cutaway cross-section illustration, ",
                ", simple rounded shapes, outer shell cut open to reveal inner parts, soft studio lighting, "
                "plain light grey-blue gradient background, centered, whole subject in frame"),
    "scene": ("bright clean stylized 3D render, ",
              ", simple rounded shapes, soft studio lighting, plain light grey-blue gradient background, centered, "
              "whole subject in frame"),
}
ASPECT = "1:1"
BRIGHT_MIN = 165                                          # 그림 평균 밝기(0~255)가 이보다 낮으면 끌어올린다(첫 화면 ≥ 110 목표)

# ── 화면 자리(y) ─────────────────────────────────────
STAGE_Y0 = 480                                            # 정사각 그림(1080)의 윗변 → 무대 가운데 y 1020
STAGE_CY = STAGE_Y0 + W // 2
FEATHER = 130                                             # 무대 위아래를 바탕에 섞는 폭
HOOK_BIG_Y, HOOK_SMALL_Y = 196, 150
PROG_Y = 344                                              # 1→2→3 진행 표시 가운데
BIG_CY = 468                                              # 큰 숫자 가운데
SUB_GAP = 14
BADGE_BOX = (60, 712, 196, 784)                           # 단계 배지(무대 왼쪽 위) — 이름표가 피한다
LABEL_ZONE = (40, 712, 940, 1330)                         # 이름표 칩이 들어갈 곳(오른쪽 x 960~ 은 인스타 버튼 열)
SRC_Y = 1376                                              # 출처 칩 윗변
ZOOM = 0.05                                               # 같은 그림이 이어지는 동안 1 → 1.05
XF = 0.25                                                 # 그림 바뀔 때 섞는 시간
POP = 0.24                                                # 큰 글자 튀어나옴
LABEL_AT, LABEL_IN = 0.45, 0.3                            # 이름표: 박자 시작 뒤 이만큼 있다가 선이 자라며 나온다
YEL, WHITE, BLACK = K.ACC_SCI, (255, 255, 255), (0, 0, 0)
NAVY = (14, 20, 38)
CHIP_BG = (22, 26, 40, 225)


# ── 검사 ──────────────────────────────────────────────
def _str(x, lo: int, hi: int) -> bool:
    return isinstance(x, str) and lo <= len(x.strip()) and len(x) <= hi


def _view_errs(where: str, o: dict, need_img: bool = True) -> list[str]:
    """그림 묘사·view·이름표(label·pin) 검사 — why·박자·판정 공통."""
    errs = []
    img = o.get("img")
    if need_img or img is not None:
        if not isinstance(img, str) or len(img.strip()) < 12:
            errs.append(f"{where} img(영어 그림 묘사) 없음")
        else:
            if _HANGUL.search(img):
                errs.append(f"{where} img 는 영어로(한글 X — 한글 이름표는 label 에 쓰면 코드가 그린다)")
            m = K.SCI_IMG_BAN.search(img)
            if m:
                errs.append(f"{where} img 에 '{m.group(0)}' — 그림엔 글자·얼굴 클로즈업이 없게(장면만 긍정형으로)")
        if o.get("view") not in VIEWS:
            errs.append(f"{where} view 는 {VIEWS} 중 하나(xray 투시 · cutaway 단면 · scene 대체)")
    lab, pin = o.get("label"), o.get("pin")
    if lab is not None and not _str(lab, 1, LABEL_MAX):
        errs.append(f"{where} label(그림 위 한글 이름표)은 1~{LABEL_MAX}자")
    if pin is not None:
        if lab is None:
            errs.append(f"{where} pin 은 label 과 같이 써요(이름표가 가리키는 자리)")
        if not (isinstance(pin, list) and len(pin) == 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and PIN_RANGE[0] <= v <= PIN_RANGE[1] for v in pin)):
            errs.append(f"{where} pin 은 [x, y] — 그림 기준 0~1, 둘 다 {PIN_RANGE[0]}~{PIN_RANGE[1]}")
    return errs


def number_texts(s: dict) -> list[tuple[str, str]]:
    """숫자를 facts 와 맞춰 볼 글(어디, 글) — 판정의 확률·순위는 뺀다(옛 sci 와 같다)."""
    out = [(f"hook[{i}]", t) for i, t in enumerate(s.get("hook") or []) if isinstance(t, str)]
    out += [("say_intro", s.get("say_intro") or ""), ("caption", s.get("caption") or "")]
    why = s.get("why") if isinstance(s.get("why"), dict) else {}
    out += [(f"why.{f}", why.get(f) or "") for f in ("sub", "say", "label")]
    for k, b in enumerate(s.get("beats") or [], 1):
        if isinstance(b, dict):
            out += [(f"{k}번 박자 {f}", b.get(f) or "") for f in ("big", "sub", "say", "label")]
    v = s.get("verdict") if isinstance(s.get("verdict"), dict) else {}
    out += [(f"verdict.{f}", K._VERDICT_FREE.sub("", v.get(f) or "")) for f in ("big", "say")]
    out += [("verdict.label", v.get("label") or "")]
    return [(w, t) for w, t in out if isinstance(t, str)]


def teardown_errs(s: dict) -> list[str]:
    """'과학으로 뜯어보는 물건' 대본만 더 보는 것(SCI_WRITING '뜯어보기') — 상표·모델 이름 · 따라 하게 하는 말 · 안전·건강 단정."""
    texts = K._texts(s) + imgs_of(s)
    low = [t.lower() for t in texts]
    errs = []
    hits = K.brand_hits(texts)
    if hits:
        errs.append(f"뜯어보기: 상표·모델 이름 금지 {hits} — '전자레인지'·'무선 이어폰'처럼 물건 이름으로")
    for name, words in (("따라 하게 하는 말('직접 열어 보세요')", K.TEARDOWN_DIY), ("안전·건강 단정", K.TEARDOWN_CLAIMS)):
        hits = sorted({w for w in words for t in low if w.lower() in t})
        if hits:
            errs.append(f"뜯어보기: {name} 금지 {hits}")
    return errs


def series_of(s: dict) -> str:
    """화면 첫 장면 칩의 시리즈 이름 — 뜯어보기 항목이면 '과학으로 뜯어보는 물건', 아니면 '속이 보이는 과학'."""
    return P.TEARDOWN_SERIES if P.is_teardown_entry(K.sci_entry_of(s)) else SERIES


def imgs_of(s: dict) -> list[str]:
    objs = [s.get("why")] + list(s.get("beats") or []) + [s.get("verdict")]
    return [o.get("img") for o in objs if isinstance(o, dict) and isinstance(o.get("img"), str)]


def check(s: dict) -> list[str]:
    """'속이 보이는 과학' 대본 검사(SCI_XRAY_FROM 이후 sci) — 모양(훅 → 왜? → 3단계 → 결과)·view·이름표는 코드가 막는다.
    숫자는 그날 catalog 항목 facts 에서만 · src_n 은 그날 항목 · sources 그대로 · 부탁(pick_reel._word_errs)·잔혹·실존 인물·영화 X."""
    errs = []
    try:
        d = dt.date.fromisoformat(s.get("date", ""))
    except (TypeError, ValueError):
        return ["date 는 YYYY-MM-DD"]
    if not P.sci_xray(d):
        errs.append(f"{d} 는 '속이 보이는 과학' 전 — {P.SCI_XRAY_FROM} 부터(그 전 날짜는 옛 모양)")
    want = P.sci_n(d)
    if want is None:
        errs.append(f"{d} 는 sci 편이 없는 날 — sci 는 {P.SCI_FROM}~{P.SCI_TO}(SCI_ORDER) · 그 뒤는 항목이 남은 날만(open_plan)")
    elif s.get("src_n") != want:
        errs.append(f"src_n 은 그날 편성 항목 {want} 이어야 한다(SCI_ORDER·open_plan) — 대본은 {s.get('src_n')}")
    e = K.sci_entry_of(s)
    if e is None:
        return errs + [f"src_n {s.get('src_n')!r} 은 sci 항목이 아니다(shorts_catalog·sci_extra·teardown_catalog)"]
    if not _SLUG.fullmatch(s.get("slug") or ""):
        errs.append("slug 는 영어 소문자·숫자·하이픈")
    hook = s.get("hook")
    if not (isinstance(hook, list) and len(hook) == 2 and all(_str(x, 1, HOOK_MAX) for x in hook)):
        errs.append(f"hook 은 두 줄 · 줄마다 {HOOK_MAX}자 이내")
    elif not hook[1].rstrip().endswith("?"):
        errs.append("hook 둘째 줄은 물음표(?)로 끝나는 대조·충격 질문(예: '영하 40도' / '몸속에선 무슨 일?')")
    intro = s.get("say_intro") or ""
    if not _str(intro, 1, INTRO_MAX) or not intro.rstrip().endswith("?"):
        errs.append(f"say_intro 1~{INTRO_MAX}자 · 물음표(?)로 끝나는 질문")
    if intro.lstrip().startswith(("안녕", "여러분")):
        errs.append("say_intro 는 첫 문장이 바로 질문 — 인사·소개 없이")
    why = s.get("why")
    if not isinstance(why, dict):
        errs.append("why('왜?' 박자 — {sub, say, img, view}) 없음 · 훅 다음에 꼭 와요")
        why = {}
    else:
        if not _str(why.get("say"), 1, WHY_SAY_MAX) or "왜" not in why.get("say", ""):
            errs.append(f"why.say 1~{WHY_SAY_MAX}자 · '왜' 가 들어간 짧은 한 마디(예: '왜 그럴까요?')")
        if not _str(why.get("sub"), 1, WHY_SUB_MAX):
            errs.append(f"why.sub('왜?' 밑 한 줄) 1~{WHY_SUB_MAX}자")
        errs += _view_errs("why", why)
    beats = s.get("beats")
    if not isinstance(beats, list) or len(beats) != N_STEPS or not all(isinstance(b, dict) for b in beats):
        errs.append(f"beats 는 정확히 {N_STEPS}개(원인·단계 1/3·2/3·3/3)")
        beats = [b for b in beats or [] if isinstance(b, dict)] if isinstance(beats, list) else []
    srcs = e.get("sources") or []
    if s.get("sources") != srcs:
        errs.append(f"sources 는 catalog {e['n']} 의 sources 를 그대로(순서까지) 옮긴다")
    compare = e.get("format") == "compare"
    items = [float(x["value"]) for x in e.get("items_idea") or [] if isinstance(x.get("value"), (int, float))]
    prev = None
    for k, b in enumerate(beats, 1):
        for f, mx in (("big", BIG_MAX), ("sub", SUB_MAX), ("say", SAY_MAX)):
            if not _str(b.get(f), 1, mx):
                errs.append(f"{k}번 박자 {f} 1~{mx}자")
        errs += _view_errs(f"{k}번 박자", b)
        src = b.get("src")
        if not (isinstance(src, int) and not isinstance(src, bool) and 0 <= src < len(srcs)):
            errs.append(f"{k}번 박자 src 는 sources 번호(0~{len(srcs) - 1})")
        if compare:
            v = b.get("value")
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                errs.append(f"{k}번 박자 value(단위 {e.get('unit')}, 양수) 필요 — 작은 것 → 큰 것")
                continue
            if not K._backed(float(v), K.fact_values(e) + items):
                errs.append(f"{k}번 박자 value {v:g} 는 catalog(facts·items_idea)에 없는 값")
            if prev is not None and v <= prev:
                errs.append(f"{k}번 박자 value — 작은 것부터 큰 것 순서로({prev:g} → {v:g})")
            prev = v
    scenes = sum(1 for b in beats if b.get("view") == "scene")
    if scenes > SCENE_MAX:
        errs.append(f"세 박자 중 view 'scene' 은 {SCENE_MAX}개까지 — 나머지는 xray(투시)·cutaway(단면)로 속을 보여 줘요")
    v = s.get("verdict")
    if not isinstance(v, dict):
        errs.append("verdict(결과 — {big, say}) 없음")
        v = {}
    else:
        if not _str(v.get("big"), 1, VERDICT_BIG_MAX):
            errs.append(f"verdict.big 1~{VERDICT_BIG_MAX}자")
        if not _str(v.get("say"), 1, VERDICT_SAY_MAX):
            errs.append(f"verdict.say 1~{VERDICT_SAY_MAX}자")
        errs += _view_errs("verdict", v, need_img=False)
    cap = (s.get("caption") or "").strip()
    if not cap or "\n" in cap:
        errs.append("caption 은 한 줄(훅) — 출처·질문·해시태그는 코드가 붙인다")
    if not (s.get("bench") or {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    pool = K.fact_values(e)                               # 숫자는 그 항목 facts 에서만(콤마·단위 무시 · 판정의 확률·순위는 예외)
    for where, t in number_texts(s):
        bad = K.unbacked(t, pool)
        if bad:
            errs.append(f"{where}: facts({e['n']})에 없는 숫자 {bad} — 숫자는 catalog facts 에서만")
    low = [t.lower() for t in K._texts(s) + imgs_of(s)]
    for name, words in (("잔혹 묘사", K.SCI_GORE), ("실존 인물·희생자", K.SCI_PEOPLE), ("프랜차이즈 이름", K.SCI_FRANCHISE)):
        hits = sorted({w for w in words for t in low if w.lower() in t})
        if hits:
            errs.append(f"{name} 금지 {hits}")
    if P.is_teardown_entry(e):                            # ★11/10~ 뜯어보기: 상표·모델 X · '직접 열어 보세요' X · 안전·건강 단정 X
        errs += teardown_errs(s)
    if not errs:                                          # 길이 어림 — 20~35초(렌더가 말 빠르기·끝 화면으로 맞춘다)
        segs, _ = plan(s, est_durations(s))
        total = segs[-1]["start"] + segs[-1]["dur"]
        if total > SEC[1] * SPEEDUP:
            errs.append(f"길이 어림 {total:.1f}초 — {SEC[0]:g}~{SEC[1]:g}초가 되게 say 를 줄일 것(어림 {CPS}자/초)")
    return errs


# ── 말·시간표 ─────────────────────────────────────────
def says_of(s: dict) -> list[str]:
    """말로 읽을 글(sci_speech) — 훅 질문 → 왜? → 3단계 → 결과 → 열린 질문(코드)."""
    return [K.sci_speech(x) for x in [s["say_intro"], s["why"]["say"]] + [b["say"] for b in s["beats"]]
            + [s["verdict"]["say"], K.ask_of(s)]]


def est_durations(s: dict) -> dict:
    return {t: round(0.1 + R.I.speech_len(t) / CPS, 3) for t in says_of(s)}


def plan(s: dict, dur: dict) -> tuple[list[dict], list[float]]:
    """장면(segs)과 틱 시각. 훅(0초부터 말) → 왜? → 1/3·2/3·3/3 → 결과 + 열린 질문. 20초보다 짧으면 끝 화면을 늘린다.
    seg: {kind: intro|why|step|verdict, k, start, dur, img(그림 열쇠), say/at(, say2/at2, ask_at)}."""
    segs: list[dict] = []
    ticks: list[float] = []

    def add(**kw):
        kw.setdefault("start", segs[-1]["start"] + segs[-1]["dur"] if segs else 0.0)
        segs.append(kw)
        return kw

    intro = K.sci_speech(s["say_intro"])
    add(kind="intro", img="why", dur=round(dur[intro] + 0.45, 3), say=intro, at=0.0)
    wy = K.sci_speech(s["why"]["say"])
    sg = add(kind="why", img="why", dur=round(dur[wy] + 0.4, 3), say=wy)
    sg["at"] = sg["start"] + 0.12
    ticks.append(sg["start"])
    for k, b in enumerate(s["beats"]):
        sy = K.sci_speech(b["say"])
        sg = add(kind="step", k=k, img=k, dur=round(dur[sy] + 0.45, 3), say=sy)
        sg["at"] = sg["start"] + 0.2
        ticks.append(sg["start"])
    vs, ask = K.sci_speech(s["verdict"]["say"]), K.sci_speech(K.ask_of(s))
    sg = add(kind="verdict", img="verdict" if s["verdict"].get("img") else len(s["beats"]) - 1, dur=1.0, say=vs, say2=ask)
    sg["at"] = sg["start"] + 0.3
    sg["at2"] = sg["at"] + dur[vs] + 0.35
    sg["ask_at"] = sg["at2"] - sg["start"] - 0.1
    sg["dur"] = round(sg["at2"] - sg["start"] + dur[ask] + 1.2, 3)
    total = sg["start"] + sg["dur"]
    if total < SEC[0]:
        sg["dur"] = round(sg["dur"] + SEC[0] - total, 3)
    ticks.append(sg["start"])
    g, t0 = -1, 0.0                                       # 같은 그림이 이어지는 장면 묶음(훅 + 왜? = 한 그림)
    for i, x in enumerate(segs):
        if i == 0 or x["img"] != segs[i - 1]["img"]:
            g += 1
            t0 = x["start"]
        x["img_g"], x["img_t0"] = g, t0
    for x in segs:
        x["img_dur"] = sum(y["dur"] for y in segs if y["img_g"] == x["img_g"])
    return segs, ticks


def total_of(segs: list[dict]) -> float:
    return round(segs[-1]["start"] + segs[-1]["dur"], 3)


# ── 그림 ──────────────────────────────────────────────
def style_of(view: str) -> tuple[str, str]:
    return VIEW_STYLE.get(view) or VIEW_STYLE["scene"]


def prompt_of(o: dict) -> str:
    head, tail = style_of(o.get("view", "scene"))
    return head + o["img"].strip().rstrip(".,") + tail


def assets(s: dict, wd: str, mock: bool) -> dict:
    """그림 — why(훅·왜? 같이) · 박자 셋 · (판정 img 가 있으면) 판정. Spark z-image 정사각(1:1) · view 화풍."""
    objs = [("why", s["why"])] + [(k, b) for k, b in enumerate(s["beats"])]
    if s["verdict"].get("img"):
        objs.append(("verdict", s["verdict"]))
    out = {}
    for key, o in objs:
        pr = prompt_of(o)
        p = os.path.join(wd, f"x{key}_{hashlib.sha1((pr + ASPECT + str(mock)).encode()).hexdigest()[:10]}.png")
        K.gen(pr, p, mock, style="", aspect=ASPECT)
        out[key] = p
    return {"imgs": out}


def brighten(im: Image.Image) -> Image.Image:
    """밝고 선명하게(10/14 sci 교훈: 어두운 첫 화면은 피드에서 안 멈춘다) — 평균 밝기가 BRIGHT_MIN 아래면 감마로 끌어올리고
    대비·채도만 조금. autocontrast 는 쓰지 않는다(10/24 실측: 밝은 단색 배경 그림은 그림자 쪽이 늘어나 평균 178 → 154 로 어두워졌다)."""
    im = im.convert("RGB")
    mean = sum(ImageOps.grayscale(im).resize((64, 64)).getdata()) / (64 * 64)
    if mean < BRIGHT_MIN:
        g = math.log(BRIGHT_MIN / 255) / math.log(max(8.0, mean) / 255)
        lut = [min(255, int(255 * (i / 255) ** g + 0.5)) for i in range(256)]
        im = im.point(lut * 3)
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.1)).enhance(1.08)


def plate(path: str) -> Image.Image:
    """그림 한 장 → 1080×1920 바탕: 정사각 그림을 무대(y STAGE_Y0~)에 놓고, 위·아래는 그림 맨 윗줄·아랫줄 색을 세로로 늘려
    잇는다(열마다 제 색 — 배경이 단색 그러데이션이라 이음매가 안 보인다) + 위아래 FEATHER 만큼 섞는다."""
    sq = brighten(R.cover(Image.open(path).convert("RGB"), W, W, centering=(0.5, 0.5)))
    top = sq.crop((0, 0, W, 6)).resize((W, 1), BIL).filter(ImageFilter.BoxBlur(6)).resize((W, STAGE_Y0 + FEATHER), BIL)
    bot_h = H - (STAGE_Y0 + W) + FEATHER
    bot = sq.crop((0, W - 6, W, W)).resize((W, 1), BIL).filter(ImageFilter.BoxBlur(6)).resize((W, bot_h), BIL)
    pl = Image.new("RGB", (W, H))
    pl.paste(top, (0, 0))
    pl.paste(bot, (0, H - bot_h))
    m = Image.new("L", (1, W))
    for y in range(W):
        m.putpixel((0, y), int(255 * min(1.0, y / FEATHER, (W - 1 - y) / FEATHER)))
    pl.paste(sq, (0, STAGE_Y0), m.resize((W, W)))
    return pl


def shade() -> Image.Image:
    """위(훅·숫자 글자 뒤)를 살짝 어둡게, 아래 캡션 자리도 조금 — 곱하기 판(흰 = 그대로). 첫 화면이 어두워지지 않게 가볍게."""
    col = Image.new("L", (1, H))
    for y in range(H):
        top = 0.22 * max(0.0, 1 - y / 760) ** 1.25
        bot = 0.22 * max(0.0, (y - 1520) / (H - 1520))
        col.putpixel((0, y), int(255 * (1 - max(top, bot))))
    return Image.merge("RGB", [col.resize((W, H))] * 3)


def _layer(lines: list[str], kind: str, hi: int, lo: int, width: float, fill, stroke: int = 8, gap: int = 14) -> Image.Image:
    """글자 묶음(RGBA · 가운데 정렬 · 검은 테두리)."""
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    f = R.fit(d0, lines, kind, hi, lo, width)
    bbs = [d0.textbbox((0, 0), ln, font=f, stroke_width=stroke) for ln in lines]
    lh = f.size + gap
    w = int(max(b[2] - b[0] for b in bbs)) + 8
    h = int(lh * (len(lines) - 1) + max(b[3] for b in bbs)) + 8
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (ln, b) in enumerate(zip(lines, bbs)):
        d.text(((w - (b[2] - b[0])) / 2 - b[0], 4 + i * lh), ln, font=f, fill=fill, stroke_width=stroke, stroke_fill=BLACK)
    return im


def _fade(im: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


class Painter:
    """frame(t) = bg_at(t)(무대 그림·그늘) + 글·배지·진행 표시·이름표. bg_at(t) 에는 글이 없다(테스트: 아래 25% 는 바탕 그대로)."""

    def __init__(self, s: dict, a: dict, segs: list[dict]):
        self.s, self.a, self.segs = s, a, segs
        self.srcs = s.get("sources") or []
        self.cache: dict = {}
        self.shade = shade()

    def seg_at(self, t: float) -> dict:
        for sg in self.segs:
            if sg["start"] <= t < sg["start"] + sg["dur"]:
                return sg
        return self.segs[-1]

    # 바탕 ───────────────────────────────────────────
    def _plate(self, key) -> Image.Image:
        if ("plate", key) not in self.cache:
            self.cache[("plate", key)] = plate(self.a["imgs"][key])
        return self.cache[("plate", key)]

    def zoom(self, sg: dict, t: float) -> float:
        p = R.ease(min(1.0, max(0.0, (t - sg["img_t0"]) / max(0.5, sg["img_dur"]))))
        return 1.0 + ZOOM * p

    def _layer_at(self, sg: dict, t: float) -> Image.Image:
        z = self.zoom(sg, t)
        box = (W / 2 - (W / 2) / z, STAGE_CY - STAGE_CY / z, W / 2 + (W / 2) / z, STAGE_CY + (H - STAGE_CY) / z)
        return self._plate(sg["img"]).transform((W, H), EXTENT, box, BIL)

    def bg_at(self, t: float) -> Image.Image:
        sg = self.seg_at(t)
        fr = self._layer_at(sg, t)
        k = self.segs.index(sg)
        lt = t - sg["start"]
        if k > 0 and lt < XF and self.segs[k - 1]["img_g"] != sg["img_g"]:
            fr = Image.blend(self._layer_at(self.segs[k - 1], t), fr, R.ease(max(0.0, lt) / XF))
        return ImageChops.multiply(fr, self.shade)

    def pin_xy(self, sg: dict, t: float, pin) -> tuple[float, float]:
        """그림 기준 pin(0~1) → 화면 좌표(다가가는 확대를 따라간다)."""
        z = self.zoom(sg, t)
        px, py = pin[0] * W, STAGE_Y0 + pin[1] * W
        return W / 2 + (px - W / 2) * z, STAGE_CY + (py - STAGE_CY) * z

    # 글 ─────────────────────────────────────────────
    def _hook(self, big: bool) -> tuple[Image.Image, int]:
        key = ("hook", big)
        if key not in self.cache:
            lay = (_layer(self.s["hook"], "head", 104, 72, W - 110, WHITE, 8, 18) if big
                   else _layer(self.s["hook"], "head", 60, 44, W - 180, WHITE, 6, 10))
            self.cache[key] = lay
        lay = self.cache[key]
        return lay, (HOOK_BIG_Y if big else HOOK_SMALL_Y)

    def _text(self, key, lines, kind, hi, lo, width, fill, stroke=8, gap=14):
        if key not in self.cache:
            self.cache[key] = _layer(lines, kind, hi, lo, width, fill, stroke, gap)
        return self.cache[key]

    def _pop(self, im: Image.Image, layer: Image.Image, cy: float, lt: float) -> int:
        """가운데 cy 에 붙인다 — 처음 POP 초는 크게 → 제자리. 아랫변(y)을 돌려준다."""
        q = R.ease(min(1.0, max(0.0, lt) / POP))
        sc = max(1.0, min(1.0 + 0.28 * (1 - q), (W - 40) / layer.width))
        ly = layer if sc == 1.0 else layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))), LZ)
        if q < 1:
            ly = _fade(ly, 0.35 + 0.65 * q)
        im.alpha_composite(ly, (int((W - ly.width) / 2), int(cy - ly.height / 2)))
        return int(cy + layer.height / 2)

    def _chip(self, d, x0: float, y0: float, text: str, f, fg=WHITE, bg=CHIP_BG, pad=(22, 11), center=False):
        tw = R.tlen(d, text, f)
        if center:
            x0 = (W - tw) / 2 - pad[0]
        bb = f.getbbox("가")
        h = bb[3] - bb[1] + 2 * pad[1]
        d.rounded_rectangle([x0, y0, x0 + tw + 2 * pad[0], y0 + h], h // 2, fill=bg)
        d.text((x0 + pad[0], y0 + pad[1] - bb[1]), text, font=f, fill=fg)
        return x0, y0, x0 + tw + 2 * pad[0], y0 + h

    def _progress(self, d, cur: int | None, done: int):
        """작은 1→2→3 진행 표시(훅 밑) — 지난 단계 흰 원 · 지금 단계 노랗고 크게 · 남은 단계 빈 원."""
        f = R.font("head", 30)
        xs = [W / 2 - 132, W / 2, W / 2 + 132]
        for i in range(N_STEPS - 1):                       # 화살표(선 + 끝 삼각)
            x0, x1 = xs[i] + 36, xs[i + 1] - 40
            col = WHITE if i < done else (255, 255, 255, 150)
            d.line([(x0, PROG_Y), (x1 - 8, PROG_Y)], fill=col, width=4)
            d.polygon([(x1, PROG_Y), (x1 - 12, PROG_Y - 8), (x1 - 12, PROG_Y + 8)], fill=col)
        for i, x in enumerate(xs):
            r = 30 if i == cur else 23
            if i == cur:
                fill, ink, ol = YEL + (255,), NAVY, BLACK
            elif i < done:
                fill, ink, ol = (255, 255, 255, 255), NAVY, BLACK
            else:
                fill, ink, ol = (0, 0, 0, 120), WHITE, (255, 255, 255)
            d.ellipse([x - r, PROG_Y - r, x + r, PROG_Y + r], fill=fill, outline=ol, width=3)
            txt = str(i + 1)
            bb = f.getbbox(txt)
            d.text((x - (bb[2] - bb[0]) / 2 - bb[0], PROG_Y - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=f, fill=ink)

    def _badge(self, d, text: str):
        """단계 배지(무대 왼쪽 위) — '1/3' · '2/3' · '3/3' · 결과는 '결과'."""
        f = R.font("head", 44)
        x0, y0, x1, y1 = BADGE_BOX
        d.rounded_rectangle([x0, y0, x1, y1], (y1 - y0) // 2, fill=YEL + (255,), outline=BLACK, width=4)
        bb = f.getbbox(text)
        d.text(((x0 + x1) / 2 - (bb[2] - bb[0]) / 2 - bb[0], (y0 + y1) / 2 - (bb[3] - bb[1]) / 2 - bb[1]), text, font=f,
               fill=NAVY)

    def _label(self, im: Image.Image, sg: dict, t: float, lt: float, o: dict):
        """그림 위 한글 이름표 — pin(그림 속 자리)에서 가는 선이 자라 칩에 닿는다. 칩은 LABEL_ZONE 안 · 배지를 피한다."""
        text = o.get("label")
        p = R.ease((lt - LABEL_AT) / LABEL_IN)
        if not text or p <= 0:
            return
        px, py = self.pin_xy(sg, t, o.get("pin") or PIN_DEFAULT)
        d = ImageDraw.Draw(im)
        f = R.font("bold", 44)
        tw = R.tlen(d, text, f)
        bb = f.getbbox("가")
        cw, ch = tw + 2 * 24, bb[3] - bb[1] + 2 * 13
        right = px < W / 2                                  # 그림 왼쪽을 가리키면 칩은 오른쪽 위, 오른쪽이면 왼쪽 위
        x0 = px + 110 if right else px - 110 - cw
        y0 = py - 150 - ch / 2
        zx0, zy0, zx1, zy1 = LABEL_ZONE
        x0 = min(max(x0, zx0), zx1 - cw)
        y0 = min(max(y0, zy0), zy1 - ch)
        bx0, by0, bx1, by1 = BADGE_BOX
        if x0 < bx1 + 12 and y0 < by1 + 12:                 # 배지와 겹치면 배지 밑으로
            y0 = by1 + 16
        if x0 - 20 <= px <= x0 + cw + 20 and y0 - 20 <= py <= y0 + ch + 20:   # 칩이 가리킬 자리를 덮으면 아래로
            y0 = min(py + 90, zy1 - ch)
        ax = min(max(px, x0 + 26), x0 + cw - 26)            # 선이 칩에 닿는 자리(칩 아랫변 또는 윗변)
        ay = y0 + ch if y0 + ch / 2 < py else y0
        ex, ey = px + (ax - px) * p, py + (ay - py) * p
        d.line([(px, py), (ex, ey)], fill=NAVY, width=9)
        d.line([(px, py), (ex, ey)], fill=WHITE, width=4)
        d.ellipse([px - 13, py - 13, px + 13, py + 13], fill=YEL + (255,), outline=NAVY, width=4)
        if p > 0.5:
            chip = Image.new("RGBA", (int(cw) + 2, int(ch) + 2), (0, 0, 0, 0))
            cd = ImageDraw.Draw(chip)
            cd.rounded_rectangle([0, 0, cw, ch], 16, fill=CHIP_BG, outline=YEL + (255,), width=3)
            cd.text((24, 13 - bb[1]), text, font=f, fill=WHITE)
            im.alpha_composite(_fade(chip, min(1.0, (p - 0.5) / 0.5)), (int(x0), int(y0)))

    def frame(self, t: float) -> Image.Image:
        sg = self.seg_at(t)
        lt = t - sg["start"]
        im = self.bg_at(t).convert("RGBA")
        d = ImageDraw.Draw(im)
        kind = sg["kind"]
        hook, hy = self._hook(kind == "intro")
        im.alpha_composite(hook, (int((W - hook.width) / 2), hy))
        if kind == "intro":
            self._chip(d, 0, hy + hook.height + 18, series_of(self.s), R.font("bold", 40), fg=YEL, center=True)
            return im.convert("RGB")
        if kind == "why":
            self._progress(d, None, 0)
            why = self.s["why"]
            yb = self._pop(im, self._text("why_big", ["왜?"], "head", 190, 120, W - 120, YEL, 10), BIG_CY, lt)
            sub = self._text("why_sub", R.wrap(d, why["sub"], R.font("bold", 56), W - 140)[:2], "bold", 56, 40, W - 140, WHITE, 7)
            im.alpha_composite(sub, (int((W - sub.width) / 2), yb + SUB_GAP))
            self._label(im, sg, t, lt, why)
            return im.convert("RGB")
        if kind == "verdict":
            self._progress(d, None, N_STEPS)
            self._badge(d, "결과")
            v = self.s["verdict"]
            yb = self._pop(im, self._text("v_big", [v["big"]], "head", 140, 80, W - 120, YEL, 10), BIG_CY, lt)
            ask = self._text("v_ask", R.wrap(d, K.ask_of(self.s), R.font("bold", 58), W - 160)[:2], "bold", 58, 40, W - 160,
                             WHITE, 7)
            a = min(1.0, max(0.0, (lt - sg.get("ask_at", 0.6)) / 0.3))
            if a > 0:
                im.alpha_composite(_fade(ask, a), (int((W - ask.width) / 2), yb + SUB_GAP + 4))
            self._label(im, sg, t, lt, v)
            return im.convert("RGB")
        k = sg["k"]                                        # 1/3 · 2/3 · 3/3
        b = self.s["beats"][k]
        self._progress(d, k, k)
        self._badge(d, f"{k + 1}/{N_STEPS}")
        yb = self._pop(im, self._text(("big", k), [b["big"]], "head", 150, 90, W - 120, YEL, 10), BIG_CY, lt)
        sub = self._text(("sub", k), R.wrap(d, b["sub"], R.font("bold", 56), W - 140)[:2], "bold", 56, 40, W - 140, WHITE, 7)
        im.alpha_composite(sub, (int((W - sub.width) / 2), yb + SUB_GAP))
        src = b.get("src")
        if isinstance(src, int) and 0 <= src < len(self.srcs):
            self._chip(d, 0, SRC_Y, f"출처 · {K.source_host(self.srcs[src])}", R.font("bold", 28), fg=(232, 236, 244),
                       bg=(10, 14, 26, 160), pad=(18, 9), center=True)
        self._label(im, sg, t, lt, b)
        return im.convert("RGB")


# ── 확인·렌더 ─────────────────────────────────────────
def first_frame_brightness(pa: Painter) -> float:
    """첫 화면 평균 밝기(0~255) — 0.0초 프레임(커버와 같다)."""
    g = ImageOps.grayscale(pa.frame(0.0)).resize((108, 192))
    return sum(g.getdata()) / (108 * 192)


def sheet_times(segs: list[dict]) -> list[float]:
    """확인용 프레임 — 첫 프레임 · 장면마다 이름표·질문이 다 나온 뒤."""
    out = [0.0]
    for sg in segs:
        f = sg["dur"] * 0.7 if sg["kind"] != "verdict" else min(sg["dur"] - 0.2, sg["ask_at"] + 0.8)
        out.append(round(sg["start"] + f, 3))
    return out


def contact_sheet(pa: Painter, segs: list[dict], out: str) -> None:
    times = sheet_times(segs)
    tw, th, cols = 270, 480, 4
    rows = math.ceil(len(times) / cols)
    sh = Image.new("RGB", (tw * cols, th * rows), (0, 0, 0))
    d = ImageDraw.Draw(sh)
    for i, t in enumerate(times):
        x, y = (i % cols) * tw, (i // cols) * th
        sh.paste(pa.frame(t).resize((tw, th), LZ), (x, y))
        d.text((x + 8, y + 6), f"{t:.2f}s {pa.seg_at(t)['kind']}", fill=(255, 255, 0), font=R.font("bold", 20),
               stroke_width=2, stroke_fill=BLACK)
    sh.save(out, "JPEG", quality=88)


def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    s = K.load(path)
    errs = K.check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    for w in K.warns(s):
        print(f"⚠️ {w}")
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    got, how = R.synth(says_of(s), os.path.join(wd, "voice"), mock, tempo=TEMPO)
    dur = {t: R.wav_dur(p) for t, p in got.items()}
    segs, ticks = plan(s, dur)
    total = total_of(segs)
    if total > SEC[1]:                                    # 35초 넘으면 말만 조금 더 빠르게(최대 SPEEDUP)
        speech = sum(dur.values())
        factor = min(SPEEDUP, speech / max(1.0, speech - (total - SEC[1])))
        print(f"   ⏩ {total:.1f}초 > {SEC[1]:g} — 말 {factor:.2f}배")
        got = {t: R.retime(p_, factor, os.path.join(wd, "voice")) for t, p_ in got.items()}
        dur = {t: R.wav_dur(p_) for t, p_ in got.items()}
        segs, ticks = plan(s, dur)
        total = total_of(segs)
    if total > SEC[1] + 2:
        raise SystemExit(f"sci 릴스 {total:.1f}초 > {SEC[1]:g} — 대본(say)을 줄일 것")
    m4a = K.mix_audio(segs, ticks, got, total, wd)
    pa = Painter(s, a, segs)
    silent = os.path.join(wd, "silent.mp4")
    R.encode(pa, total, silent)
    out = os.path.join(out_dir, f"{stem}.mp4")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-c:v", "copy", "-c:a", "copy", "-shortest", out])
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    pa.frame(0.0).save(cover, "JPEG", quality=90)        # 커버 = 첫 프레임(회차 없음)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    contact_sheet(pa, segs, sheet)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "src_n": s.get("src_n"), "video": out,
            "cover": cover, "sheet": sheet, "seconds": total, "voice": how, "caption": K.caption_of(s), "threads_images": [],
            "look": "xray", "first_frame_brightness": round(first_frame_brightness(pa), 1)}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta
