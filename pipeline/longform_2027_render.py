#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'2027 정미년 깊이 보기' 롱폼 렌더 (2026-10-20) — 주간 운세 렌더러(weekly_fortune_render)를 그대로 쓴다.

  ① 목소리: Supertonic 한 목소리(F2)로 조각마다 한 건씩(공용 Spark) — 주간 운세와 같은 synth · 쉼·속도는 longform_2027.SPEC
  ② 배경: 장(=유튜브 챕터)마다 Spark 그림 한 장(동화 그림체 · 글자 없는 장면) — ★목소리(cpu 레인)와 ★동시에 만든다(gpu 레인)
     · 장마다 천천히 다가가는 켄 번스(줌·패닝 방향을 장마다 바꾼다) · 그림이 안 오면 짙은 남색 그라데이션
  ③ 화면(PIL 투명 판 → 배경 위에 겹침): 꼴 4가지를 장마다 돌린다 — 표(시리즈 계산) · 띠 카드(요점이 하나씩 켜짐) ·
     출생연도 목록(지금 해에 금색 막대) · 질문·답 카드 — 그리고 행운(색 동그라미·나침반) · 시작 질문 · 다음 편.
     ★'찍어 낸 슬라이드쇼'로 보이지 않게(유튜브 '반복·비진정성 콘텐츠'): 배경이 장마다 다르고 움직이며, 표는 편마다 계산이 다르다.
  ④ 장마다 mp4 조각(같은 설정) → 이어 붙이기(-c copy) → 오디오 합치기 · 목차 · 썸네일(1280×720 · 어르신 눈높이 큰 글자)

    python longform_2027_render.py sheets <대본.json> <폴더>    # 꼴마다 화면 한 장씩(검수용 · 네트워크 없이)
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import longform_2027 as LF  # noqa: E402
import weekly_fortune_render as R  # noqa: E402
from fortune_card import ANIMALS  # noqa: E402

W, H = 1920, 1080
TW, TH = 1280, 720
FPS = int(os.environ.get("LF27_FPS", "24"))
BG_W, BG_H = 2304, 1296                   # 켄 번스 여유(1.2배)
ZOOM = float(os.environ.get("LF27_ZOOM", "0.07"))
IMG_MODEL = os.environ.get("LF27_IMG_MODEL", "z-image-turbo")
GOLD, BEIGE, WHITE, DIM, NAVY = R.GOLD, R.BEIGE, R.WHITE, R.DIM, R.NAVY
PANEL = (22, 26, 58, 228)                 # 판(반투명 남색) — 배경이 비치되 글자가 또렷하게
PANEL2 = (34, 40, 84, 236)
GREEN, ORANGE, SKY = (126, 211, 150), (255, 150, 100), (150, 200, 255)
SAL_COLOR = {"천살": (186, 168, 255), "화개살": (244, 160, 190), "반안살": (126, 211, 150), "월살": (150, 200, 255)}
BRAND = f"왕별이 · {LF.SERIES}"
MOCK = os.environ.get("LF27_MOCK") == "1" or os.environ.get("WEEKLY_MOCK_TTS") == "1"

font, fit, text_c, paste = R.font, R.fit, R.text_c, R.paste


def tile(animal: str, size: int, wd: str | None = None, ring=None, ring_w: int = 0, radius=None):
    return R.animal_tile(animal, size, wd, radius=radius, ring=ring, ring_w=ring_w)


# ── 공통 판 ───────────────────────────────────────────────────
def canvas():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(H):                     # 위·아래를 살짝 어둡게(배경은 비치고 글자는 또렷하게)
        t = y / (H - 1)
        a = int(110 * (1 - t) ** 3 + 150 * t ** 3 + 40)
        d.line([(0, y), (W, y)], fill=(8, 10, 26, a))
    return img, d


def header(d, sp: dict, total: int | None = None):
    n = sp.get("index")
    x = 64
    if n:
        s = f"{n}장"
        f = font(40)
        w = d.textlength(s, font=f)
        d.rounded_rectangle([x, 42, x + w + 44, 104], radius=31, fill=GOLD)
        d.text((x + 22, 50), s, font=f, fill=NAVY)
        x += w + 70
    size, lines, _ = fit(d, sp.get("title", ""), W - x - 520, 70, 56, 36)
    d.text((x, 44 + (60 - size) // 2), lines[0] if lines else "", font=font(size), fill=WHITE,
           stroke_width=2, stroke_fill=NAVY)
    f = font(30)
    s = LF.SERIES
    d.text((W - 64 - d.textlength(s, font=f), 58), s, font=f, fill=BEIGE)


def footer(d, note: str = ""):
    f = font(30)
    d.text((64, H - 60), BRAND, font=f, fill=DIM)
    s = "재미로 보는 운세예요"
    d.text((W - 64 - d.textlength(s, font=f), H - 60), s, font=f, fill=DIM)
    if note:
        fn = font(32)
        w = d.textlength(note, font=fn)
        d.rounded_rectangle([W / 2 - w / 2 - 26, H - 122, W / 2 + w / 2 + 26, H - 72], radius=25, fill=(10, 12, 30, 200))
        d.text((W / 2 - w / 2, H - 116), note, font=fn, fill=BEIGE)


def pill(d, x, y, s, f, fill, color, pad=26, h=None):
    w = d.textlength(s, font=f)
    hh = h or int(f.size * 1.5)
    d.rounded_rectangle([x, y, x + w + pad * 2, y + hh], radius=hh // 2, fill=fill)
    d.text((x + pad, y + (hh - f.size) / 2 - f.size * 0.08), s, font=f, fill=color)
    return x + w + pad * 2


# ── 1. 시작(질문) ─────────────────────────────────────────────
def draw_open(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    ep = plan["ep"]
    pill(d, 64, 48, LF.SERIES, font(38), (10, 12, 30, 210), BEIGE)
    x0, y0, x1, y1 = 160, 210, W - 160, 610
    d.rounded_rectangle([x0, y0, x1, y1], radius=48, fill=(250, 246, 236, 240))
    d.polygon([(x0 + 180, y1), (x0 + 260, y1), (x0 + 170, y1 + 70)], fill=(250, 246, 236, 240))
    d.text((x0 + 56, y0 + 34), "여쭤 오신 질문", font=font(40), fill=(150, 110, 40))
    size, lines, lh = fit(d, f"“{plan['question']}”", x1 - x0 - 120, y1 - y0 - 140, 84, 52)
    yy = y0 + 104 + max(0, (y1 - y0 - 140 - len(lines) * lh) // 2)
    for ln in lines:
        text_c(d, (x0 + x1) / 2, yy, ln, font(size), NAVY)
        yy += lh
    if sp.get("step"):
        f = font(58)
        s = ep["search"]
        text_c(d, W / 2, 712, s, f, GOLD, stroke=3, stroke_fill=NAVY)
        anim = plan["animals"]
        size_ = 200 if len(anim) > 1 else 240
        gap = 40
        x = W / 2 - (len(anim) * size_ + (len(anim) - 1) * gap) / 2
        for a in anim:
            paste(img, tile(a, size_, wd, ring=GOLD, ring_w=5, radius=size_ // 2), (x, 800 - (size_ - 200) // 2))
            x += size_ + gap
    footer(d)
    return img


# ── 2. 띠 카드(요점이 하나씩 켜진다) ──────────────────────────
def draw_card(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    header(d, sp)
    anim = sp.get("animals") or plan["animals"]
    if len(anim) == 1:
        paste(img, tile(anim[0], 560, wd, ring=GOLD, ring_w=6, radius=44), (90, 190))
        text_c(d, 370, 772, f"{anim[0]}띠", font(84), GOLD, stroke=3, stroke_fill=NAVY)
        text_c(d, 370, 880, LF.years_label(anim[0]), font(34), BEIGE)
    else:
        for k, a in enumerate(anim[:3]):
            y = 160 + k * 270
            paste(img, tile(a, 230, wd, ring=GOLD, ring_w=4, radius=115), (120, y))
            d.text((380, y + 70), f"{a}띠", font=font(64), fill=GOLD, stroke_width=2, stroke_fill=NAVY)
    x0, y0, x1, y1 = 660, 150, 1856, 990
    d.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=PANEL)
    pts = sp.get("points") or []
    shown = sp.get("shown", len(pts))
    n = max(1, len(pts))
    room = (y1 - y0 - 80) // n
    for k, p in enumerate(pts):
        y = y0 + 50 + k * room
        on = k < shown
        cur = k == shown - 1
        col = GOLD if cur else (WHITE if on else (90, 96, 140))
        d.ellipse([x0 + 50, y + 18, x0 + 104, y + 72], fill=col if on else (60, 66, 110))
        text_c(d, x0 + 77, y + 18, str(k + 1), font(40), NAVY if on else DIM)
        size, lines, lh = fit(d, p, x1 - x0 - 200, room - 20, 76, 44)
        for j, ln in enumerate(lines):
            d.text((x0 + 140, y + j * lh), ln, font=font(size), fill=col)
    footer(d)
    return img


# ── 3. 표(시리즈 계산) ────────────────────────────────────────
def _table_sinsal12(img, d, plan, sp, wd):
    rows = LF.table_sinsal12()
    mine = set(plan["animals"])
    cw, rh, top = 880, 124, 132
    for k, r in enumerate(rows):
        col, row = k // 6, k % 6
        x, y = 64 + col * (cw + 32), top + row * (rh + 10)
        on = r["animal"] in mine
        d.rounded_rectangle([x, y, x + cw, y + rh], radius=24, fill=PANEL2 if on else PANEL,
                            outline=GOLD if on else (58, 66, 118, 255), width=5 if on else 2)
        paste(img, tile(r["animal"], 104, wd, radius=52), (x + 16, y + 14))
        nm = f"{r['animal']}띠"
        d.text((x + 136, y + 12), nm, font=font(52), fill=GOLD if on else WHITE)
        sc = SAL_COLOR.get(r["sinsal"], WHITE)
        nx = pill(d, x + 136 + d.textlength(nm, font=font(52)) + 24, y + 14, r["sinsal"], font(42), (*sc, 255), NAVY,
                  pad=20, h=64)
        if r["samjae"]:
            pill(d, nx + 12, y + 14, r["samjae"], font(38), (255, 214, 120, 255), NAVY, pad=16, h=64)
        d.text((x + 136, y + 80), r["advice"], font=font(30), fill=BEIGE)
        if r["rel"]:
            s = r["rel"]
            d.text((x + cw - 24 - d.textlength(s, font=font(30)), y + 80), s, font=font(30), fill=DIM)
    return "띠는 입춘 기준 · 양력 1월~2월 3일생은 앞 해 띠"


def _month_pills(d, x, y, ms, color, f, label):
    d.text((x, y + 8), label, font=font(34), fill=DIM)
    x += d.textlength(label, font=font(34)) + 20
    for m in sorted(ms):
        x = pill(d, x, y, f"{m}월", f, (*color, 255), NAVY, pad=18, h=70) + 14
    return x


def _table_months3(img, d, plan, sp, wd):
    rows = LF.table_months(plan["animals"])
    top, rh = 150, 255
    f = font(50)
    for k, r in enumerate(rows):
        y = top + k * (rh + 18)
        d.rounded_rectangle([64, y, W - 64, y + rh], radius=30, fill=PANEL)
        paste(img, tile(r["animal"], 190, wd, radius=95, ring=GOLD, ring_w=4), (96, y + 32))
        d.text((310, y + 30), f"{r['animal']}띠", font=font(64), fill=GOLD)
        d.text((310, y + 118), LF.years_label(r["animal"]), font=font(30), fill=BEIGE)
        _month_pills(d, 760, y + 40, r["good"], GREEN, f, "좋은 달")
        _month_pills(d, 760, y + 140, r["caution"], ORANGE, f, "조심할 달")
    return "절기로 나눈 양력 달 · 매달 4~8일께 바뀌어요"


def _table_months1(img, d, plan, sp, wd):
    a = plan["animals"][0]
    f = LF.ddi_facts(a)
    good = dict(zip(f["months_good"], f["months_good_why"]))
    bad = dict(zip(f["months_caution"], f["months_caution_why"]))
    money, body = set(f["months_money_good"]), set(f["months_body_good"])
    cw, chh, top, gx, gy = 420, 196, 150, 24, 20
    for m in range(1, 13):
        c, r = (m - 1) % 4, (m - 1) // 4
        x, y = 64 + c * (cw + gx), top + r * (chh + gy)
        kind = "good" if m in good else "bad" if m in bad else ""
        outline = GREEN if kind == "good" else ORANGE if kind == "bad" else (58, 66, 118)
        d.rounded_rectangle([x, y, x + cw, y + chh], radius=26, fill=PANEL2 if kind else PANEL,
                            outline=(*outline, 255), width=6 if kind else 2)
        d.text((x + 26, y + 16), f"{m}월", font=font(68), fill=WHITE)
        tag = (good.get(m) or bad.get(m) or "").split(" ", 1)[-1]
        if kind:
            lab = "좋은 달" if kind == "good" else "조심할 달"
            pill(d, x + 190, y + 26, lab, font(36), (*(GREEN if kind == "good" else ORANGE), 255), NAVY, pad=14, h=56)
            d.text((x + 28, y + 110), tag, font=font(36), fill=BEIGE)
        marks = [s for s, on in (("돈", m in money), ("몸", m in body)) if on]
        xx = x + cw - 26
        for s in reversed(marks):
            w = d.textlength(s, font=font(34)) + 30
            xx -= w
            d.rounded_rectangle([xx, y + chh - 64, xx + w, y + chh - 18], radius=23, fill=GOLD if s == "돈" else SKY)
            d.text((xx + 15, y + chh - 60), s, font=font(34), fill=NAVY)
            xx -= 10
    return "돈 = 돈이 도는 달 · 몸 = 몸이 가벼운 달 · 절기로 나눈 양력 달"


def _table_people12(img, d, plan, sp, wd):
    a = plan["animals"][0]
    rows = LF.table_people12(a)
    cw, rh, top = 880, 124, 132
    for k, r in enumerate(rows):
        col, row = k // 6, k % 6
        x, y = 64 + col * (cw + 32), top + row * (rh + 10)
        good = r["rel"] in ("육합", "삼합", "같은 띠")
        care = r["rel"] in ("충", "원진", "형")
        oc = GREEN if good else ORANGE if care else (58, 66, 118)
        d.rounded_rectangle([x, y, x + cw, y + rh], radius=24, fill=PANEL2 if (good or care) else PANEL,
                            outline=(*oc, 255), width=5 if (good or care) else 2)
        paste(img, tile(r["animal"], 104, wd, radius=52), (x + 16, y + 14))
        d.text((x + 136, y + 18), f"{r['animal']}띠", font=font(52), fill=WHITE)
        d.text((x + 136, y + 84), f"올해 {r['line_2027']}", font=font(30), fill=DIM)
        s = r["tag"]
        fs = font(40)
        d.text((x + cw - 28 - d.textlength(s, font=fs), y + 44), s, font=fs, fill=GREEN if good else ORANGE if care else BEIGE)
    return f"{a}띠와 각 띠의 사이 · 아래 작은 글씨는 그 띠의 2027 정미년 한 줄"


TABLES = {"sinsal12": _table_sinsal12, "months3": _table_months3, "months1": _table_months1, "people12": _table_people12}


def draw_table(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    header(d, sp)
    note = TABLES[sp.get("table") or "sinsal12"](img, d, plan, sp, wd)
    footer(d, note)
    return img


# ── 4. 출생연도 목록 ─────────────────────────────────────────
def draw_years(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    header(d, sp)
    a, yrs, focus = sp["animal"], sp["years"], sp.get("focus")
    rows = {r["year"]: r for r in LF.ddi_facts(a)["years"]}
    x0, y0, x1 = 64, 140, 600
    rh = min(118, (H - 150 - y0) // max(1, len(yrs)))
    for k, y in enumerate(yrs):
        yy_ = y0 + k * rh
        on = y == focus
        d.rounded_rectangle([x0, yy_, x1, yy_ + rh - 12], radius=22, fill=(*GOLD, 255) if on else PANEL)
        lab = LF.yy(y) + "년생"
        d.text((x0 + 30, yy_ + (rh - 12 - 58) / 2 - 4), lab, font=font(58), fill=NAVY if on else WHITE)
        s = str(y)
        d.text((x1 - 30 - d.textlength(s, font=font(36)), yy_ + (rh - 12 - 36) / 2), s, font=font(36),
               fill=NAVY if on else DIM)
    px0, py0, px1, py1 = 650, 140, 1856, 960
    d.rounded_rectangle([px0, py0, px1, py1], radius=40, fill=PANEL)
    paste(img, tile(a, 240, wd, ring=GOLD, ring_w=5, radius=120), (px0 + 50, py0 + 50))
    if focus:
        r = rows[focus]
        d.text((px0 + 330, py0 + 50), LF.yy(focus) + "년생", font=font(150), fill=GOLD, stroke_width=4, stroke_fill=NAVY)
        sub = f"{focus}년 · {a}띠"
        d.text((px0 + 340, py0 + 230), sub, font=font(44), fill=BEIGE)
        y = py0 + 330
        if sp.get("hwangap"):
            pill(d, px0 + 50, y, "올해 환갑 — 같은 정미년", font(46), (255, 214, 120, 255), NAVY, pad=24, h=72)
            y += 96
        nx = pill(d, px0 + 50, y, f"좋은 기운 · {r['good']}", font(44), (*GREEN, 255), NAVY, pad=24, h=72)
        if nx + 40 + d.textlength(f"챙길 것 · {r['caution_line']}", font=font(44)) + 48 < px1 - 30:
            pill(d, nx + 24, y, f"챙길 것 · {r['caution_line']}", font(44), (*ORANGE, 255), NAVY, pad=24, h=72)
        else:
            y += 92
            pill(d, px0 + 50, y, f"챙길 것 · {r['caution_line']}", font(44), (*ORANGE, 255), NAVY, pad=24, h=72)
        y += 116
        pt = sp.get("point") or r["good_line"]
        size, lines, lh = fit(d, pt, px1 - px0 - 100, py1 - y - 40, 92, 52)
        for ln in lines:
            d.text((px0 + 50, y), ln, font=font(size), fill=WHITE)
            y += lh
    else:
        d.text((px0 + 330, py0 + 70), f"{a}띠", font=font(150), fill=GOLD, stroke_width=4, stroke_fill=NAVY)
        d.text((px0 + 340, py0 + 250), "출생연도별 풀이", font=font(56), fill=WHITE)
        size, lines, lh = fit(d, "양력 1월 1일 ~ 2월 3일생은 앞 해 띠로 보세요", px1 - px0 - 100, 260, 64, 44)
        y = py0 + 420
        for ln in lines:
            d.text((px0 + 50, y), ln, font=font(size), fill=BEIGE)
            y += lh
    footer(d, "띠는 입춘 기준 · 양력 1월~2월 3일생은 앞 해 띠")
    return img


# ── 5. 질문·답 카드 ──────────────────────────────────────────
def draw_qa(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    header(d, sp)
    x0, y0, x1 = 120, 190, W - 120
    d.ellipse([x0, y0, x0 + 150, y0 + 150], fill=GOLD)
    text_c(d, x0 + 75, y0 + 22, "Q", font(96), NAVY)
    d.rounded_rectangle([x0 + 190, y0 - 10, x1, y0 + 330], radius=40, fill=(250, 246, 236, 240))
    size, lines, lh = fit(d, sp.get("q", ""), x1 - x0 - 270, 300, 74, 46)
    y = y0 + 20 + max(0, (300 - len(lines) * lh) // 2)
    for ln in lines:
        d.text((x0 + 230, y), ln, font=font(size), fill=NAVY)
        y += lh
    if sp.get("answer"):
        ya = y0 + 400
        d.ellipse([x0, ya, x0 + 150, ya + 150], fill=GREEN)
        text_c(d, x0 + 75, ya + 22, "A", font(96), NAVY)
        d.rounded_rectangle([x0 + 190, ya - 10, x1, ya + 330], radius=40, fill=PANEL2)
        size, lines, lh = fit(d, sp.get("point", ""), x1 - x0 - 270, 300, 84, 50)
        y = ya + 20 + max(0, (300 - len(lines) * lh) // 2)
        for ln in lines:
            d.text((x0 + 230, y), ln, font=font(size), fill=WHITE)
            y += lh
    d.text((x0 + 200, 112), f"{LF.ORD[min(4, sp.get('n', 1) - 1)]} 번째 질문", font=font(36), fill=GOLD)
    footer(d)
    return img


# ── 6. 행운 ──────────────────────────────────────────────────
COLOR_RGB = {"초록": (64, 158, 92), "연두": (158, 208, 88), "빨강": (214, 58, 58), "분홍": (240, 150, 180),
             "노랑": (245, 205, 60), "황토": (196, 140, 64), "흰색": (245, 245, 245), "은색": (196, 196, 206),
             "검정": (40, 40, 44), "남색": (52, 62, 150)}


def draw_lucky(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    header(d, sp)
    anim = sp.get("animals") or plan["animals"]
    if sp.get("compass"):
        cx, cy, r = W / 2, 560, 300
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PANEL, outline=(*GOLD, 255), width=6)
        for s, (dx, dy) in (("북", (0, -1)), ("남", (0, 1)), ("동", (1, 0)), ("서", (-1, 0))):
            text_c(d, cx + dx * (r - 70), cy + dy * (r - 70) - 36, s, font(64), WHITE)
        pill(d, cx + r + 40, cy - 60, "대장군 동쪽", font(52), (255, 214, 120, 255), NAVY, pad=26, h=84)
        x = cx - r - 40 - d.textlength("삼살 서쪽", font=font(52)) - 52
        pill(d, x, cy - 60, "삼살 서쪽", font(52), (*SKY, 255), NAVY, pad=26, h=84)
        text_c(d, W / 2, 900, "이사·큰 공사 방향 잡을 때 참고하세요", font(48), BEIGE)
        footer(d)
        return img
    n = len(anim)
    top, rh = 150, (H - 150 - 150) // n - 16
    for k, a in enumerate(anim):
        lk = LF.ddi_facts(a)["lucky"]
        y = top + k * (rh + 16)
        on = a == sp.get("focus") or n == 1
        d.rounded_rectangle([64, y, W - 64, y + rh], radius=32, fill=PANEL2 if on else PANEL,
                            outline=(*GOLD, 255) if on else (58, 66, 118, 255), width=5 if on else 2)
        ts = min(rh - 40, 220)
        paste(img, tile(a, ts, wd, radius=ts // 2), (96, y + (rh - ts) / 2))
        nm = f"{a}띠"
        d.text((96 + ts + 30, y + rh / 2 - 44), nm, font=font(76), fill=GOLD)
        x = max(560, 96 + ts + 30 + d.textlength(nm, font=font(76)) + 50)
        for c in lk["colors"].split("·"):
            rgb = COLOR_RGB.get(c, GOLD)
            cr = min(56, rh // 4)
            d.ellipse([x, y + rh / 2 - cr - 20, x + cr * 2, y + rh / 2 + cr - 20], fill=rgb, outline=WHITE, width=4)
            text_c(d, x + cr, y + rh / 2 + cr - 10, c, font(34), WHITE)
            x += cr * 2 + 50
        x += 20
        d.text((x, y + rh / 2 - 70), "숫자", font=font(34), fill=DIM)
        d.text((x, y + rh / 2 - 30), lk["numbers"], font=font(66), fill=WHITE)
        x += 230
        d.text((x, y + rh / 2 - 70), "방향", font=font(34), fill=DIM)
        d.text((x, y + rh / 2 - 30), lk["direction"], font=font(66), fill=WHITE)
        x += 270
        size, lines, lh = fit(d, lk["tip"], W - 100 - x, rh - 30, 46, 30)
        yy_ = y + (rh - len(lines) * lh) / 2
        for ln in lines:
            d.text((x, yy_), ln, font=font(size), fill=BEIGE)
            yy_ += lh
    footer(d, "오행의 색·숫자·방향 — 불·흙이 강한 해에 내 띠 기운을 고르게")
    return img


# ── 7. 다음 편 ───────────────────────────────────────────────
def draw_outro(plan: dict, sp: dict, wd=None):
    img, d = canvas()
    ep = plan["ep"]
    d.rounded_rectangle([120, 150, W - 120, 860], radius=48, fill=PANEL)
    if ep.get("next_title"):
        pill(d, 180, 200, "다음 편", font(54), (*GOLD, 255), NAVY, pad=30, h=86)
        size, lines, lh = fit(d, ep["next_title"], W - 360, 300, 96, 56)
        y = 330
        for ln in lines:
            d.text((180, y), ln, font=font(size), fill=WHITE, stroke_width=2, stroke_fill=NAVY)
            y += lh
        nxt = LF.BY_ID[ep["next"]]
        x = 180
        for a in nxt["animals"][:3]:
            paste(img, tile(a, 170, wd, radius=85, ring=GOLD, ring_w=4), (x, 640))
            x += 200
    else:
        text_c(d, W / 2, 260, "16편을 모두 들어 주셔서 고맙습니다", font(80), WHITE)
        text_c(d, W / 2, 420, f"재생목록 '{LF.PLAYLIST}'", font(64), GOLD)
    s = "구독 · 알림을 켜 두세요"
    text_c(d, W / 2 + 300, 700, s, font(56), BEIGE)
    footer(d)
    return img


DRAW = {"open": draw_open, "card": draw_card, "table": draw_table, "years": draw_years, "qa": draw_qa,
        "lucky": draw_lucky, "outro": draw_outro}


def draw_slide(plan: dict, sp: dict, wd=None):
    return DRAW[sp["kind"]](plan, sp, wd)


# ── 썸네일(1280×720 · 어르신 눈높이: 큰 글자 · 굵은 테두리 · 영어·한자 없이) ────────
def draw_thumbnail(plan: dict, bg_path: str | None = None, wd=None):
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
    ep = plan["ep"]
    th = ep["thumb"]
    if bg_path and os.path.exists(bg_path):
        bg = ImageOps.fit(Image.open(bg_path).convert("RGB"), (TW, TH), Image.LANCZOS)
        bg = ImageEnhance.Brightness(bg).enhance(0.8)
    else:
        bg = R.background((TW, TH), glow=(980, 360, 330))
    img = bg.convert("RGBA")
    shade = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(TW):
        a = int(200 * max(0.0, 1 - x / (TW * 0.75)))
        sd.line([(x, 0), (x, TH)], fill=(8, 10, 30, a))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    anim = ep["animals"]
    if len(anim) == 1:
        paste(img, tile(anim[0], 400, wd, ring=GOLD, ring_w=10, radius=200), (856, 170))
    else:
        for k, a in enumerate(anim[:3]):
            s = 250
            paste(img, tile(a, s, wd, ring=GOLD, ring_w=8, radius=s // 2), ((1000, 870, 1000)[k], (24, 240, 456)[k]))
    size, lines, lh = fit(d, th["big"], 760 if len(anim) == 1 else 800, 330, 170, 96, gap=1.05)
    y = 60
    for ln in lines:
        d.text((44, y), ln, font=font(size), fill=GOLD, stroke_width=8, stroke_fill=NAVY)
        y += lh
    size2, lines2, lh2 = fit(d, th["sub"], 720, 120, 92, 56, gap=1.1)
    for ln in lines2:
        d.text((48, y + 10), ln, font=font(size2), fill=WHITE, stroke_width=6, stroke_fill=NAVY)
        y += lh2
    f = font(64)
    s = th["pill"]
    while d.textlength(s, font=f) > 700 and f.size > 40:
        f = font(f.size - 4)
    w = d.textlength(s, font=f)
    d.rounded_rectangle([44, TH - 150, 44 + w + 60, TH - 50], radius=50, fill=WHITE)
    d.text((74, TH - 150 + (100 - f.size) / 2 - 6), s, font=f, fill=NAVY)
    return img.convert("RGB")


# ── 배경 그림 ────────────────────────────────────────────────
def _fallback_bg(seed: int):
    from PIL import Image, ImageDraw, ImageFilter
    import random
    rnd = random.Random(seed)
    img = R.background((BG_W, BG_H), glow=(rnd.randint(400, BG_W - 400), rnd.randint(300, BG_H - 300), 520))
    d = ImageDraw.Draw(img)
    for _ in range(18):                                   # 은은한 별빛 — 움직일 때 깊이감
        x, y, r = rnd.randint(0, BG_W), rnd.randint(0, BG_H // 2), rnd.randint(2, 5)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(200, 190, 150))
    return img.filter(ImageFilter.GaussianBlur(1.2))


def bg_prompt(scene: str) -> str:
    return f"{scene}, {LF.STYLE}"


def ensure_bg(scene: str, wd: str, seed: int = 0) -> str:
    """장 배경 한 장(BG_W×BG_H JPG). Spark → 실패하면 그라데이션. 캐시: 장면 글."""
    from PIL import Image, ImageEnhance, ImageOps
    os.makedirs(os.path.join(wd, "bg"), exist_ok=True)
    key = hashlib.sha1(bg_prompt(scene).encode("utf-8")).hexdigest()[:12]
    out = os.path.join(wd, "bg", f"bg_{key}.jpg")            # ★진짜 그림만 이 이름으로 캐시한다
    if os.path.exists(out) and not MOCK:
        return out
    raw = os.path.join(wd, "bg", f"raw_{key}.png")
    ok = os.path.exists(raw)
    if not ok and not MOCK:
        try:
            import wbspark
            ok = wbspark.generate_image(bg_prompt(scene), raw, model=IMG_MODEL or None, aspect="16:9", no_llm=True,
                                        timeout_sec=600)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 배경 그림 실패(그라데이션으로): {str(e)[:120]}")
            ok = False
    if ok and not MOCK:
        im = ImageOps.fit(Image.open(raw).convert("RGB"), (BG_W, BG_H), Image.LANCZOS)
        ImageEnhance.Brightness(im).enhance(0.78).save(out, "JPEG", quality=92)
        return out
    fb = os.path.join(wd, "bg", f"fb_{key}.jpg")              # 그라데이션 대신 — 다음 실행은 Spark 를 다시 시도한다
    _fallback_bg(int(key, 16) % 10_000 + seed).save(fb, "JPEG", quality=92)
    return fb


# ── 영상 ─────────────────────────────────────────────────────
MOVES = (("0.5", "0.45"), ("0.0", "0.3"), ("1.0", "0.5"), ("0.5", "0.0"), ("0.2", "1.0"), ("0.8", "0.2"))


def part_clip(bg: str, ovs: list[tuple[str, float]], frames: int, out: str, k: int):
    """배경 켄 번스(장마다 다른 방향) + 투명 판(시간 맞춰 바뀜) → mp4 조각(소리 없음)."""
    lst = out[:-4] + "_ov.txt"
    with open(lst, "w", encoding="utf-8") as fp:
        for p, dur in ovs:
            fp.write(f"file '{os.path.abspath(p)}'\nduration {max(0.05, dur):.3f}\n")
        fp.write(f"file '{os.path.abspath(ovs[-1][0])}'\n")
    px, py = MOVES[k % len(MOVES)]
    zin = k % 2 == 0                                     # 짝수 장은 다가가고, 홀수 장은 물러난다
    z = f"1+{ZOOM}*on/{max(1, frames)}" if zin else f"{1 + ZOOM}-{ZOOM}*on/{max(1, frames)}"
    dur = frames / FPS
    vf = (f"[0:v]zoompan=z='{z}':x='(iw-iw/zoom)*{px}':y='(ih-ih/zoom)*{py}':d=1:s={W}x{H}:fps={FPS}[bg];"
          f"[1:v]format=rgba[ov];[bg][ov]overlay=0:0:eof_action=repeat,"
          f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, dur - 0.3):.3f}:d=0.3,scale=out_range=tv,format=yuv420p[v]")
    R.sh([R.FFMPEG, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", bg,
          "-f", "concat", "-safe", "0", "-i", lst, "-filter_complex", vf, "-map", "[v]", "-frames:v", str(frames),
          "-r", str(FPS), "-c:v", "libx264", "-preset", os.environ.get("LF27_PRESET", "veryfast"), "-crf", "22",
          "-pix_fmt", "yuv420p", out])


def build_video(plan: dict, items: list[dict], total: float, wd: str, bgs: dict, out_mp4: str, audio: str) -> int:
    """파트마다 조각 → 이어 붙이기 → 오디오. 반환: 화면(판) 수."""
    os.makedirs(wd, exist_ok=True)
    starts = [next(it["show"] for it in items if it["part"] == p["id"]) for p in plan["parts"]]
    bounds = [round(s * FPS) for s in starts] + [round(total * FPS)]
    made, clips = {}, []
    for k, p in enumerate(plan["parts"]):
        its = [it for it in items if it["part"] == p["id"]]
        f0, f1 = bounds[k], bounds[k + 1]
        segs = []
        for i, it in enumerate(its):
            a = it["show"] if i else starts[k]
            b = its[i + 1]["show"] if i + 1 < len(its) else f1 / FPS
            key = hashlib.sha1(json.dumps(it["slide"], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            if key not in made:
                path = os.path.join(wd, f"ov_{len(made):03d}_{it['slide']['kind']}.png")
                draw_slide(plan, it["slide"], wd).save(path, "PNG")
                made[key] = path
            if segs and segs[-1][0] == made[key]:
                segs[-1] = (made[key], segs[-1][1] + (b - a))
            else:
                segs.append((made[key], b - a))
        clip = os.path.join(wd, f"part_{k:02d}.mp4")
        part_clip(bgs[p["id"]], segs, f1 - f0, clip, k)
        clips.append(clip)
        print(f"   🎞️ {k + 1}/{len(plan['parts'])} {p['id']} {(f1 - f0) / FPS:.1f}초 · 판 {len(segs)}", flush=True)
    lst = os.path.join(wd, "parts.txt")
    with open(lst, "w", encoding="utf-8") as fp:
        for c in clips:
            fp.write(f"file '{os.path.abspath(c)}'\n")
    silent = os.path.join(wd, "video_silent.mp4")
    R.sh([R.FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    R.sh([R.FFMPEG, "-y", "-v", "error", "-i", silent, "-i", audio, "-map", "0:v", "-map", "1:a", "-c", "copy",
          "-shortest", "-movflags", "+faststart", out_mp4])
    return len(made)


def render(plan: dict, out_dir: str, wd: str, tts=None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(wd, exist_ok=True)
    base = os.path.join(out_dir, f"{plan['episode']}_{plan['publish']}_lf27")
    texts = [c["text"] for p in plan["parts"] for c in p["chunks"]]
    st0 = plan["stats"]
    print(f"   📜 {st0['chars']:,}자 · 조각 {len(texts)}개 · 파트 {len(plan['parts'])} · 예상 {st0['est_min']}분 · 목소리 {LF.VOICE}")
    t0 = time.time()
    for a in ANIMALS:
        R.ensure_animal(a, wd)
    with cf.ThreadPoolExecutor(1) as ex:                  # 그림(gpu 레인)은 목소리(cpu 레인)와 동시에
        fut = {p["id"]: ex.submit(ensure_bg, p["scene"], wd, k) for k, p in enumerate(plan["parts"])}
        wavs, st = R.synth(texts, os.path.join(wd, "tts"), voice=LF.VOICE, tts=tts)
        bgs = {k: f.result() for k, f in fut.items()}
    t_media = time.time() - t0
    durs = {t: R.wav_dur(p) for t, p in wavs.items()}
    items, parts, total = R.timeline(plan, durs, cfg=LF.SPEC)
    audio = base + "_audio.m4a"
    R.build_audio(items, wavs, os.path.join(wd, "tts"), audio, cfg=LF.SPEC)
    t1 = time.time()
    video = base + ".mp4"
    nslides = build_video(plan, items, total, os.path.join(wd, "slides"), bgs, video, audio)
    t_video = time.time() - t1
    thumb = base + "_thumb.jpg"
    draw_thumbnail(plan, bgs.get("open"), wd).save(thumb, "JPEG", quality=92)
    speech = sum(durs.values())
    res = {"video": video, "thumb": thumb, "audio": audio, "chapters": R.chapters_text(parts),
           "duration_sec": round(total, 1), "duration_min": round(total / 60, 1), "slides": nslides,
           "speech_sec": round(speech, 1), "chars": st0["chars"],
           "cpm_measured": round(st0["chars"] / (speech / 60.0), 1) if speech else None,
           "media_sec": round(t_media), "video_sec": round(t_video), **st}
    print(f"✅ {video} · {res['duration_min']}분 · 판 {nslides} · 목소리·그림 {res['media_sec']}초 · 영상 {res['video_sec']}초"
          f" · 말 속도 {res['cpm_measured']}자/분(원본) · 대체 {st['fallback']}")
    return res


def sheets(plan: dict, out: str, wd=None) -> list[str]:
    """꼴마다 대표 화면 한 장씩(배경 없이 남색 위에) — 검수용."""
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    seen, files = set(), []
    for p in plan["parts"]:
        for c in p["chunks"]:
            sp = c["slide"]
            key = (sp["kind"], sp.get("table"), sp.get("focus") is None, sp.get("answer"), sp.get("compass"), sp.get("step"))
            if key in seen:
                continue
            seen.add(key)
            ov = draw_slide(plan, sp, wd)
            bg = R.background((W, H)).convert("RGBA")
            path = os.path.join(out, f"{len(files) + 1:02d}_{sp['kind']}{'_' + sp['table'] if sp.get('table') else ''}.jpg")
            Image.alpha_composite(bg, ov).convert("RGB").save(path, "JPEG", quality=88)
            files.append(path)
    th = os.path.join(out, "thumb.jpg")
    draw_thumbnail(plan, None, wd).save(th, "JPEG", quality=90)
    files.append(th)
    return files


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if len(sys.argv) >= 3 and sys.argv[1] == "sheets":
        with open(sys.argv[2], encoding="utf-8") as fp:
            _plan = LF.compose(json.load(fp))
        _out = sys.argv[3] if len(sys.argv) > 3 else "."
        print("\n".join(sheets(_plan, _out)))
    else:
        print(__doc__)
