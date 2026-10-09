#!/usr/bin/env python3
"""Nine Tails 쇼츠 렌더 — 대본(JSON) → 목소리(Spark Supertonic) · 세로 그림(Spark) → 1080x1920 mp4.

    python gumiho/tales/render_rule.py output/tales_rules/R101_mariana-trench-floor.json
    python gumiho/tales/render_rule.py gumiho/tales/rules_scripts/R101_mariana-trench-floor.json --mock   # 가짜 그림·목소리

형식마다 화면(2026-10-09 새 라인업 — rules.py 머리말):
  survival  위: 'HOW LONG WOULD YOU LAST? · PT.N' + 상황 큰 글자(첫 1초) · 생존 시계(0:00 → 출처가 준 시각까지 굴러가거나,
            출처가 단위만 주면 SECONDS·HOURS 같은 낱말, 시간이 없으면 --:--) · 박자 카드(큰 글자 + 작은 출처) ·
            끝: "GUMI'S ODDS 2%" 카드 + 다음 편 예고(글자만)
  compare   위: 'RANKED · PT.N' + 주제 · 지금 항목 이름·값 · 코드로 그린 막대(작은 것부터 쌓인다, log/linear) ·
            마지막 반전(막대가 표를 뚫고 나가거나 큰 글자) · 끝: 구미 판정 + 예고
  liminal   옛 규칙 화면 그대로(규칙 카드 튀어나옴·번쩍·흔들림) + 'FICTION' 표시 · 끝 → 첫 장면 루프
  rules·versus·pov(옛 설화, 10/9까지) 그대로 — 끝에 치비 구미
★새 형식에는 구미·여우를 그리지 않는다(구미는 목소리만 — 끝 판정 자막이 노랗게).
★새 형식은 쇼츠 UI 를 피한다: 글자·상자 x ≤ 960 · y ≤ 1500, 자막 아랫변 ≤ 1480(Base 설명).
소리: 목소리 + 낮은 드론 + 첫 '쿵' + 줄마다 작은 '쿵'(survival 은 시계 '똑딱'). 전부 코드로 만든다(저작권 없음). -14 LUFS.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import render_tale as R  # noqa: E402
import rules as RU  # noqa: E402

SW, SH = R.SW, R.SH
FPS = int(os.environ.get("RULES_FPS", "30"))
SR = R.SR
GAP = 0.22                     # 줄 사이 쉼 — 짧게(도파민)
POP = 0.18                     # 카드 튀어나오는 시간
LOOP = 0.4                     # 끝 → 첫 장면 섞기(rules·liminal)
END_HOLD = 1.3                 # survival·compare 끝 화면(판정·예고)이 머무는 시간
SPIN = 0.6                     # 생존 시계가 다음 박자 시각까지 굴러가는 시간
GROW = 0.45                    # 막대가 자라는 시간
MAX_SEC = 40.0
MAX_SEC_NEW = {"survival": 52.0, "compare": 52.0, "liminal": 45.0}
OUT = os.path.join(ROOT, "output", "gumiho", "rules")
ASSETS = R.ASSETS
SERIES = "NINE TAILS RULES"
YELLOW = (255, 214, 64)
FX_OF = {"deep": "dust", "space": "dust", "earth": "dust", "ancient": "dust", "liminal": "dust"}
# 쇼츠 UI 피하기(2026-10-10 검수): 아래 22%(y > 1500) = 제목·채널 덮개, 오른쪽 x > 960 = 버튼 열.
SAFE_X0, SAFE_X1, SAFE_Y1 = 60, 960, 1500
CAP_BOTTOM = 1480              # 자막 아랫변
SAFE_CX, SAFE_W = 510, 820     # 새 형식 글자 가운데(60–960 의 가운데)와 최대 폭 → x 100–920
PANEL_W = 580                  # 생존 시계 상자 폭
TEASER_W = 840                 # 예고·반전 글자 최대 폭(상자 여백 22px 더해도 x 60–960 안)


def fit_width(d, text: str, sizes, width):
    """주어진 크기들 중 폭 안에 드는 가장 큰 글꼴."""
    for z in sizes:
        f = R.font("sans_bold", z)
        if d.textlength(text, font=f) <= width:
            return f
    return R.font("sans_bold", sizes[-1])


def prefix_of(s: dict, ln: dict) -> str:
    """그림 프롬프트 앞 화풍. 새 형식은 rules.LOOKS(실사), 옛 형식은 render_tale.look_prefix(그림 캐시 그대로)."""
    look = ln.get("look") or s.get("look")
    if s.get("format") in RU.NEW_FORMATS:
        return RU.LOOKS[look] + RU.LOOK_TAIL
    return R.look_prefix(look)


def gen_vertical(prompt: str, out: str, prefix: str, mock: bool) -> bool:
    if mock:
        return R.gen_image(prompt, out, mock=True)
    import wbspark
    for attempt in range(3):
        R.spark_wait()
        if wbspark.generate_image(prefix + prompt, out, aspect="9:16", no_llm=True,
                                  model=R.IMG_MODEL or None, timeout_sec=900):
            return True
    return False


def fit_vertical(src: str, dst: str):
    """세로 화면보다 8% 크게(천천히 다가가는 여유) — 가로 그림(mock)도 가운데를 잘라 쓴다."""
    im = ImageOps.fit(Image.open(src).convert("RGB"), (int(SW * 1.08), int(SH * 1.08)), Image.Resampling.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    im = ImageEnhance.Color(im).enhance(1.1)
    im.filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=3)).save(dst, "JPEG", quality=92)


def chibi(react: str) -> Image.Image:
    """치비 구미 스티커(흰 바탕) → 가장자리에서 이어진 흰 배경만 투명하게. 옛 형식만."""
    p = os.path.join(ASSETS, f"chibi_{react}.png")
    im = Image.open(p).convert("RGB")
    im.thumbnail((560, 560), Image.Resampling.LANCZOS)
    mask = Image.new("L", im.size, 255)
    w, h = im.size
    flood = im.copy()
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(flood, xy, (255, 0, 255), thresh=28)
    px, mp = flood.load(), mask.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] == (255, 0, 255):
                mp[x, y] = 0
    out = im.convert("RGBA")
    out.putalpha(mask.filter(ImageFilter.GaussianBlur(1.2)))
    return out


def looped(s: dict) -> bool:
    return s.get("format") not in ("survival", "compare")


def plan(s: dict, voices: dict, raws: list[str]) -> dict:
    rows, t = [], 0.0
    fmt = s.get("format")
    for i, ln in enumerate(RU.lines_of(s)):
        d = R.wav_dur(voices[ln["say"]])
        text = ln.get("name") if fmt == "compare" else ln.get("text")
        rows.append({"i": i, "say": ln["say"], "text": (text or "").upper(), "rule": ln.get("rule"),
                     "raw": raws[i], "wav": voices[ln["say"]], "start": round(t, 3), "vdur": d,
                     "dur": round(d + GAP, 3), "t": (ln.get("t") or "").strip(), "sec": RU.clock_sec(ln.get("t") or ""),
                     "word": RU.clock_word(ln.get("t") or ""),
                     "value": ln.get("value"), "label": (ln.get("label") or "").upper(), "twist": bool(ln.get("twist")),
                     "big": (ln.get("text") or "").upper(), "src": ln.get("src")})
        t += d + GAP
    g = s["gumi"]
    gd = R.wav_dur(voices[g["say"]])
    gumi = {"say": g["say"], "react": g.get("react"), "wav": voices[g["say"]], "start": round(t + 0.1, 3), "vdur": gd,
            "odds": g.get("odds")}
    tail = 0.35 + LOOP if looped(s) else END_HOLD
    total = round(gumi["start"] + gd + tail, 3)
    rows[-1]["dur"] = round(total - rows[-1]["start"], 3)       # 마지막 그림이 구미 대사 동안 남는다
    return {"rows": rows, "gumi": gumi, "total": total, "loop": looped(s)}


def fmt_clock(sec: float, style_label: str) -> str:
    """시계 글자 — 목표 박자의 꼴(M:SS · H:MM:SS · DAY N)을 따른다."""
    sec = max(0, int(sec))
    if RU.DAYS.match(style_label or "") and sec >= 86400:
        return f"DAY {sec // 86400}"
    h, rem = divmod(sec, 3600)
    m, ss = divmod(rem, 60)
    if h or (style_label or "").count(":") == 2 or RU.DAYS.match(style_label or ""):
        return f"{h}:{m:02d}:{ss:02d}"
    return f"{m}:{ss:02d}"


class Base:
    """공통: 배경 그림(천천히 다가감) · 입자 · 비네트 · 위 배지 · 아래 자막.

    새 형식은 쇼츠 UI 를 피한다(2026-10-10 검수: 자막이 y 1590–1660 = 제목·채널 덮개 안이었다):
      아래 22%(y > 1500)는 제목·채널, 오른쪽 x > 960 은 버튼 열 → 글자는 x ≤ 960 · y ≤ 1500, 자막 아랫변 ≤ 1480.
      가운데를 x 510(60–960 의 가운데)으로 옮기고 폭은 SAFE_W 안. 그린 글자·상자는 self.boxes 에 남긴다(테스트가 본다).
    옛 형식(rules·versus·pov, 10/9까지)은 예전 자리 그대로.
    """

    def __init__(self, P: dict, s: dict):
        self.P, self.s = P, s
        self.new = s.get("format") in RU.NEW_FORMATS
        self.rows = P["rows"]
        self.starts = [r["start"] for r in self.rows]
        self.imgs = {r["raw"]: Image.open(r["raw"]).convert("RGB") for r in self.rows}
        self.fx = R.FX(SW, SH, seed=11)
        self.fx_kind = s.get("fx") or FX_OF.get(s.get("look"), "embers")
        self.vig = R.vignette(SW, SH)
        self.ftop = R.font("sans_bold", 34)
        self.fcap = R.font("sans", 64)
        self.cx = SAFE_CX if self.new else SW / 2
        self.tw = SAFE_W if self.new else SW - 110
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        bot = d.textbbox((0, 0), "Agjy", font=self.fcap, stroke_width=8)[3]
        self.cap_y = (CAP_BOTTOM - bot) if self.new else 1585
        self.boxes: list[tuple] = []
        for r in self.rows:
            r["chunks"] = R.caption_chunks(r["say"])

    def _fit(self, text: str, sizes, width, kind: str = "sans") -> tuple[list[str], object]:
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        ws = text.split()
        for size in sizes:
            f = R.font(kind, size)
            cands = [[text]] if len(ws) < 3 else []
            cands += [[" ".join(ws[:k]), " ".join(ws[k:])] for k in range(1, len(ws))]
            best = min(cands, key=lambda ls: max(d.textlength(x, font=f) for x in ls)) if cands else [text]
            if max(d.textlength(x, font=f) for x in best) <= width:
                return best, f
        f = R.font(kind, sizes[-1])
        return R.wrap(d, text, f, width)[:3], f

    def row_at(self, t: float) -> tuple[int, dict]:
        k = max(0, min(len(self.rows) - 1, R.bisect.bisect_right(self.starts, t) - 1))
        return k, self.rows[k]

    def base(self, r: dict, t: float) -> Image.Image:
        im = self.imgs[r["raw"]]
        p = R.ease((t - r["start"]) / max(0.5, r["dur"]))
        z = 1.0 + 0.06 * p                                     # 천천히 다가간다
        cw, ch = im.width / z, im.height / z
        cx, cy = im.width / 2, im.height / 2
        crop = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
        return crop.resize((SW, SH), Image.Resampling.BILINEAR)

    def box(self, name: str, b, dy: float = 0):
        self.boxes.append((name, b[0], b[1] + dy, b[2], b[3] + dy))

    def text(self, d, xy, text, f, fill, sw=9, name="text", dy=0):
        d.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0))
        self.box(name, d.textbbox(xy, text, font=f, stroke_width=sw), dy)

    def center(self, d, y, text, f, fill, sw=9, name="text", dy=0):
        w_ = d.textlength(text, font=f)
        self.text(d, (self.cx - w_ / 2, y), text, f, fill, sw, name, dy)

    def rect(self, d, b, r, name="box", dy=0, **kw):
        d.rounded_rectangle(b, r, **kw)
        self.box(name, b, dy)

    def badge(self, d, text: str, y: int = 150, tag: str | None = None):
        tl = d.textlength(text, font=self.ftop)
        tg = d.textlength(tag, font=self.ftop) if tag else 0
        extra = tg + 58 if tag else 0                          # 빨간 배지 오른쪽 14px 띄우고 FICTION 배지
        x0 = self.cx - (tl + extra) / 2
        self.rect(d, [x0 - 24, y, x0 + tl + 24, y + 56], 12, "badge", fill=R.RED)
        d.text((x0, y + 7), text, font=self.ftop, fill=(255, 255, 255))
        if tag:                                                 # 'FICTION' — 리미널은 분명한 창작
            bx = x0 + tl + 38
            self.rect(d, [bx, y, bx + tg + 32, y + 56], 12, "badge", fill=(20, 20, 24), outline=(255, 255, 255), width=2)
            d.text((bx + 16, y + 7), tag, font=self.ftop, fill=(255, 255, 255))

    def caption(self, d, t: float, r: dict, lt: float, hidden: bool = False):
        """아래: 지금 말하는 조각(3단어). 구미(목소리만) 판정은 노랗게 + 'GUMI' 표시."""
        g = self.P["gumi"]
        speaking = None
        if 0 <= lt <= r["vdur"] + 0.15 and t < g["start"]:
            speaking = (r, lt)
        elif g["start"] <= t <= g["start"] + g["vdur"] + 0.15:
            speaking = ({"chunks": R.caption_chunks(g["say"]), "vdur": g["vdur"]}, t - g["start"])
        if not speaking or hidden:
            return
        rr, ll = speaking
        tot = sum(len(c) for c in rr["chunks"]) or 1
        acc, cur = 0.0, rr["chunks"][-1]
        for c in rr["chunks"]:
            acc += rr["vdur"] * len(c) / tot
            if ll < acc:
                cur = c
                break
        gumi = t >= g["start"]
        self.center(d, self.cap_y, cur, self.fcap, YELLOW if gumi else (255, 255, 255), 8, "caption")
        if gumi and self.new:
            self.center(d, self.cap_y - 50, "GUMI", self.ftop, YELLOW, 6, "caption")

    def finish(self, fr: Image.Image, t: float) -> Image.Image:
        fr = self.fx.draw(fr, self.fx_kind, t)
        return ImageChops.multiply(fr, self.vig)

    @staticmethod
    def pop_scale(lt: float) -> float:
        s_ = min(1.0, lt / POP) if lt >= 0 else 1.0
        return 1.0 + 0.25 * (1 - s_) ** 2 if s_ < 1 else 1.0          # 크게 → 제자리(튀어나옴)

    def paste_card(self, fr, card, y: int, sc: float):
        """카드 붙이기. 튀어나올 때(sc > 1)는 글자 가운데(cx)를 축으로 키운다. 새 형식은 x 60–960 밖을 잘라 낸다
        (10/10 검수: 가운데 540 축으로 키우면 0.18초 동안 오른쪽 버튼 열 x > 960 을 넘었다)."""
        h = card.height
        if sc != 1.0:
            cw_, ch_ = int(SW * sc), int(h * sc)
            left = int(self.cx * sc - self.cx)
            card = card.resize((cw_, ch_), Image.Resampling.BILINEAR).crop((left, (ch_ - h) // 2, left + SW, (ch_ - h) // 2 + h))
        if self.new:
            m = Image.new("L", card.size, 0)
            ImageDraw.Draw(m).rectangle([SAFE_X0, 0, SAFE_X1, h], fill=255)
            card.putalpha(ImageChops.multiply(card.getchannel("A"), m))
        fr.paste(card, (0, y), card)


class Painter(Base):
    """옛 규칙괴담(rules·versus·pov) + 리미널(liminal) — 규칙 카드 · 루프."""

    def __init__(self, P: dict, s: dict):
        super().__init__(P, s)
        if not self.new:
            self.fx_kind = "embers"
        self.frule = R.font("sans_bold", 40)
        self.hook_lines, self.fhook = self._fit(s["hook"].upper(), (118, 106, 96, 86, 76, 68), self.tw)
        self.gumi = None if self.new else chibi(P["gumi"]["react"])     # 새 형식: 구미는 목소리만
        self.card_y = 880 if self.new else 1020                         # 새 형식: 자막(아랫변 1480) 위로
        for r in self.rows:
            r["tlines"], r["ftext"] = self._fit(r["text"], (104, 94, 84, 76, 68, 60), self.tw - 10) if r["text"] else ([], None)

    def frame(self, t: float) -> Image.Image:
        P = self.P
        self.boxes = []
        k, r = self.row_at(t)
        fr = self.base(r, t)
        lt = t - r["start"]
        # 끝 → 첫 장면(루프)
        if t > P["total"] - LOOP:
            q = (t - (P["total"] - LOOP)) / LOOP
            fr = Image.blend(fr, self.base(self.rows[0], 0.0), min(1.0, q))
        fr = self.finish(fr, t)
        # 규칙이 바뀌는 순간: 흔들림 + 번쩍
        if r["text"] and lt < 0.1:
            dx = int(10 * math.sin(lt * 90))
            fr = ImageChops.offset(fr, dx, 0)
        if r["text"] and lt < 0.09 and k > 0:
            fr = Image.blend(fr, Image.new("RGB", (SW, SH), (255, 255, 255)), 0.35 * (1 - lt / 0.09))
        d = ImageDraw.Draw(fr)
        # 위: 시리즈 표시 + hook
        if self.new:
            self.badge(d, "LIMINAL RULES", tag="FICTION")
        else:
            self.badge(d, SERIES)
        y = 232
        lh = int(self.fhook.size * 1.12)
        for ln in self.hook_lines:
            self.center(d, y, ln, self.fhook, (255, 255, 255), 10, "hook")
            y += lh
        in_loop = t > P["total"] - LOOP
        # 규칙 카드(가운데 아래) — 구미가 나오면 비킨다(10/5 실렌더: 치비가 마지막 규칙 글자를 가렸다)
        gumi_on = t >= P["gumi"]["start"] - 0.05
        if r["text"] and not in_loop and not (gumi_on and not self.new):
            card = Image.new("RGBA", (SW, 520), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            yy = 20
            if r["rule"]:
                lab = f"RULE {r['rule']}"
                lw = cd.textlength(lab, font=self.frule)
                self.rect(cd, [self.cx - lw / 2 - 22, yy, self.cx + lw / 2 + 22, yy + 62], 14, "card", self.card_y,
                          fill=(12, 8, 12, 230), outline=YELLOW + (255,), width=3)
                cd.text((self.cx - lw / 2, yy + 9), lab, font=self.frule, fill=YELLOW)
                yy += 86
            lh2 = int(r["ftext"].size * 1.1)
            for ln in r["tlines"]:
                self.center(cd, yy, ln, r["ftext"], (255, 255, 255), 11, "card", self.card_y)
                yy += lh2
            self.paste_card(fr, card, self.card_y, self.pop_scale(lt))
        self.caption(d, t, r, lt, hidden=in_loop)
        # 끝: 치비 구미(옛 형식만 — 통통 튀며 등장)
        g = P["gumi"]
        if self.gumi is not None and t >= g["start"] - 0.05 and not in_loop:
            q = min(1.0, (t - g["start"] + 0.05) / 0.3)
            sc = 0.3 + 0.7 * q + 0.12 * math.sin(q * math.pi)
            gi = self.gumi.resize((max(8, int(self.gumi.width * sc)), max(8, int(self.gumi.height * sc))), Image.Resampling.BILINEAR)
            gx, gy = (SW - gi.width) // 2, 1540 - gi.height          # 가운데, 자막(1585) 바로 위
            fr.paste(gi, (gx, gy), gi)
        return fr


def shade_mask() -> Image.Image:
    """위·아래를 어둡게(글자 읽힘) — 곱하기용 RGB 세로 그라데이션."""
    col = Image.new("L", (1, SH))
    px = col.load()
    for y in range(SH):
        top = max(0.0, 1 - y / 760) * 0.62
        bot = max(0.0, (y - 900) / (SH - 900)) * 0.72
        px[0, y] = int(255 * (1 - max(top, bot)))
    return Image.merge("RGB", [col.resize((SW, SH))] * 3)


class SurvivalPainter(Base):
    """How Long Would You Last — 상황 글자 · 생존 시계 · 박자 카드 · 끝 'GUMI'S ODDS'.

    시계(2026-10-10): catalog beat_ideas 의 시각 그대로 — 출처가 준 시각만 숫자로 굴러가고, 단위만 있으면 낱말(HOURS …),
    출처에 시간이 없으면 --:--. 마지막이 --:-- 면 끝 화면에 시계를 내리고 구미의 확률만.
    """

    CARD_Y = 1000

    def __init__(self, P: dict, s: dict):
        super().__init__(P, s)
        self.shade = shade_mask()
        self.sit_lines, self.fsit = self._fit(s["situation"].upper(), (104, 96, 88, 80, 72, 64), self.tw)
        self.fclock = R.font("sans", 150)
        self.flab = R.font("sans_bold", 30)
        self.fsrc = R.font("sans_bold", 28)
        self.fodds_l = R.font("sans", 64)
        self.ftz = R.font("sans_bold", 38)
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        self.cell = max(d.textlength(c, font=self.fclock) for c in "0123456789")
        for r in self.rows:
            r["tlines"], r["ftext"] = self._fit(r["big"], (100, 92, 84, 76, 68), self.tw) if r["big"] else ([], None)
            r["notime"] = r["t"] == RU.NO_TIME
            if r["word"]:
                r["fword"] = next((R.font("sans", z) for z in (150, 124, 104, 88, 74, 62, 52)
                                   if d.textlength(r["t"], font=R.font("sans", z)) <= PANEL_W - 60), R.font("sans", 46))
        self.badge_text = f"HOW LONG WOULD YOU LAST? · PT.{s['part']}"
        self.srcs = s.get("sources") or []

    def last_number(self, k: int) -> float:
        return next((x["sec"] for x in reversed(self.rows[:k]) if x["sec"] is not None), 0.0)

    def clock_value(self, k: int, lt: float) -> tuple[str, float]:
        """(화면 글자, 순서용 값). 숫자 박자는 앞 숫자에서 굴러오고, 낱말 박자는 낱말 그대로,
        출처 없는 박자(--:--)는 '--:--'(시간을 말하지 않는다 — 순서용 값은 앞 값 그대로)."""
        r = self.rows[k]
        if r.get("notime"):
            return RU.NO_TIME, max([self.clock_value(j, 99.0)[1] for j in range(k) if not self.rows[j].get("notime")] or [0.0])
        if r["word"]:
            return r["t"], float(RU.WORD_RANK[r["word"]])
        prev = self.last_number(k)
        q = R.ease(min(1.0, max(0.0, lt) / SPIN)) if k > 0 else 1.0
        v = prev + (r["sec"] - prev) * q
        return fmt_clock(v, r["t"]), v

    def draw_clock(self, d, text: str, y: int, color, f=None):
        if f is not None:                                      # 낱말(SECONDS·HOURS …)
            w_ = d.textlength(text, font=f)
            self.text(d, (self.cx - w_ / 2, y + (150 - f.size) * 0.55), text, f, color, 8, "clock")
            return
        widths = [self.cell if c.isdigit() else d.textlength(c, font=self.fclock) for c in text]
        x = self.cx - sum(widths) / 2
        for c, w_ in zip(text, widths):
            cw = d.textlength(c, font=self.fclock)
            self.text(d, (x + (w_ - cw) / 2, y), c, self.fclock, color, 8, "clock")
            x += w_

    def frame(self, t: float) -> Image.Image:
        P, g = self.P, self.P["gumi"]
        self.boxes = []
        k, r = self.row_at(t)
        lt = t - r["start"]
        fr = ImageChops.multiply(self.finish(self.base(r, t), t), self.shade)
        if k > 0 and lt < 0.09:                                  # 박자 바뀜: 짧게 번쩍
            fr = Image.blend(fr, Image.new("RGB", (SW, SH), (255, 255, 255)), 0.28 * (1 - lt / 0.09))
        d = ImageDraw.Draw(fr)
        self.badge(d, self.badge_text)
        y = 226
        lh = int(self.fsit.size * 1.1)
        for ln in self.sit_lines:
            self.center(d, y, ln, self.fsit, (255, 255, 255), 10, "situation")
            y += lh
        # 생존 시계 — 출처가 준 시각까지 굴러가고, 끝(판정)에는 빨갛게 멈춘다
        end = t >= g["start"] - 0.05
        cy = max(y + 24, 490)
        # 끝: 마지막 박자에 출처 있는 시각이 있을 때만 'CLOCK STOPPED' — 없으면 시계를 내리고 구미의 확률(의견)만
        show_clock = not (end and self.rows[-1].get("notime"))
        if show_clock:
            self.rect(d, [self.cx - PANEL_W / 2, cy, self.cx + PANEL_W / 2, cy + 214], 22, "clock", fill=(8, 8, 12),
                      outline=(255, 70, 60) if end else (YELLOW if not r.get("notime") else (150, 150, 160)), width=5)
            self.center(d, cy + 12, "CLOCK STOPPED" if end else "SURVIVAL CLOCK", self.flab, (220, 220, 220), 0, "clock")
            label, _ = self.clock_value(k, lt)
            pulse = k > 0 and (r["word"] and lt < 0.2 or SPIN <= lt < SPIN + 0.15)
            col = (255, 70, 60) if end else ((150, 150, 160) if r.get("notime") else ((255, 255, 255) if pulse else YELLOW))
            self.draw_clock(d, label, cy + 44, col, r.get("fword"))
        if not end and r["tlines"]:
            card = Image.new("RGBA", (SW, 420), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            yy = 10
            lh2 = int(r["ftext"].size * 1.08)
            for ln in r["tlines"]:
                self.center(cd, yy, ln, r["ftext"], (255, 255, 255), 11, "card", self.CARD_Y)
                yy += lh2
            if isinstance(r["src"], int) and 0 <= r["src"] < len(self.srcs):
                lab = "SOURCE: " + RU.source_label(self.srcs[r["src"]]).upper()
                self.center(cd, yy + 8, lab, self.fsrc, (225, 225, 225), 5, "source", self.CARD_Y)
            self.paste_card(fr, card, self.CARD_Y, self.pop_scale(lt))
        if end:                                                  # 끝: 구미의 확률(목소리만 — 그림 없음)
            q = min(1.0, (t - g["start"] + 0.05) / 0.25)
            sc = 0.6 + 0.4 * q + 0.1 * math.sin(q * math.pi)
            self.center(d, 920, "GUMI'S ODDS", self.fodds_l, YELLOW, 8, "odds")
            od = str(g.get("odds") or "")
            f = R.font("sans", max(40, int(230 * sc)))
            self.center(d, 985 + (230 - f.size) * 0.4, od, f, (255, 255, 255), 12, "odds")
            tz = (self.s.get("teaser") or "").upper()
            if tz and t >= g["start"] + 0.6:
                ft = fit_width(d, tz, (38, 34, 30, 26), TEASER_W)
                w_ = d.textlength(tz, font=ft)
                self.rect(d, [self.cx - w_ / 2 - 22, 1278, self.cx + w_ / 2 + 22, 1338], 14, "teaser", fill=(12, 12, 16),
                          outline=(255, 255, 255), width=2)
                d.text((self.cx - w_ / 2, 1284 + (38 - ft.size) * 0.5), tz, font=ft, fill=(255, 255, 255))
        self.caption(d, t, r, lt)
        return fr


class ComparePainter(Base):
    """Ranked — 항목 이름·값 · 코드로 그린 막대(작은 것부터 쌓임) · 마지막 반전. 전부 x ≤ 960 · y ≤ 1500."""

    X0, X1 = 320, 800              # 막대 영역(오른쪽에 값 글자 자리)
    BOX_L, BOX_R = 40, 930
    TOP, ROW = 985, 54

    def __init__(self, P: dict, s: dict):
        super().__init__(P, s)
        self.shade = shade_mask()
        self.hook_lines, self.fhook = self._fit(s["hook"].upper(), (104, 96, 88, 80, 72, 64), self.tw)
        self.fname = R.font("sans", 76)
        self.fval = R.font("sans", 96)
        self.flab = R.font("sans_bold", 28)
        self.fsrc = R.font("sans_bold", 26)
        self.ftz = R.font("sans_bold", 38)
        self.log = s.get("scale") == "log"
        vals = [r["value"] for r in self.rows if not r["twist"] and r["value"]]
        self.vmin, self.vmax = min(vals), max(vals)
        self.srcs = s.get("sources") or []
        self.badge_text = f"RANKED · PT.{s['part']}"
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        for r in self.rows:
            r["tlines"], r["ftext"] = self._fit(r["big"], (84, 76, 68, 60, 52, 46), TEASER_W) if r["big"] else ([], None)
            r["fname"] = next((R.font("sans", z) for z in (76, 68, 60, 54, 48) if d.textlength(r["text"], font=R.font("sans", z)) <= self.tw),
                              R.font("sans", 44))

    def capped(self, d, text: str, size: int):
        """튀어나올 때(크게)도 안전 폭(SAFE_W)을 넘지 않게."""
        while size > 30 and d.textlength(text, font=R.font("sans", size)) + 22 > self.tw:
            size -= 4
        return R.font("sans", size)

    def row_font(self, d, text: str):
        """표 왼쪽 이름 칸에 맞게 글자를 줄인다 — 자르지 않는다."""
        for size in (30, 27, 24, 21):
            f = R.font("sans_bold", size)
            if d.textlength(text, font=f) <= self.X0 - 70:
                return f
        return R.font("sans_bold", 19)

    def frac(self, v: float) -> float:
        if self.log:
            lo = math.log10(self.vmin) - 0.6                     # 가장 작은 막대도 보이게
            return (math.log10(v) - lo) / (math.log10(self.vmax) - lo)
        return v / self.vmax

    def frame(self, t: float) -> Image.Image:
        P, g = self.P, self.P["gumi"]
        self.boxes = []
        k, r = self.row_at(t)
        lt = t - r["start"]
        fr = ImageChops.multiply(self.finish(self.base(r, t), t), self.shade)
        shake = 0
        if r["twist"] and 0 <= lt < 0.35:                        # 반전: 크게 흔들림
            shake = int(16 * math.sin(lt * 70) * (1 - lt / 0.35))
        if k > 0 and lt < 0.09:
            fr = Image.blend(fr, Image.new("RGB", (SW, SH), (255, 255, 255)), (0.45 if r["twist"] else 0.25) * (1 - lt / 0.09))
        if shake:
            fr = ImageChops.offset(fr, shake, 0)
        d = ImageDraw.Draw(fr, "RGBA")
        self.badge(d, self.badge_text)
        y = 226
        lh = int(self.fhook.size * 1.1)
        for ln in self.hook_lines:
            self.center(d, y, ln, self.fhook, (255, 255, 255), 10, "hook")
            y += lh
        end = t >= g["start"] - 0.05
        tz = (self.s.get("teaser") or "").upper()
        if end and tz and t >= g["start"] + 0.4:
            ft = fit_width(d, tz, (38, 34, 30, 26), TEASER_W)
            w_ = d.textlength(tz, font=ft)
            self.rect(d, [self.cx - w_ / 2 - 22, y + 18, self.cx + w_ / 2 + 22, y + 78], 14, "teaser",
                      fill=(12, 12, 16, 235), outline=(255, 255, 255, 255), width=2)
            d.text((self.cx - w_ / 2, y + 24 + (38 - ft.size) * 0.5), tz, font=ft, fill=(255, 255, 255))
        # 지금 항목: 이름 + 값(반전이 값 없이 오면 큰 글자)
        pop = 1.0 + 0.2 * (1 - min(1.0, lt / POP)) ** 2 if 0 <= lt < POP else 1.0
        fn = self.capped(d, r["text"], int(r["fname"].size * pop))
        self.center(d, 700, r["text"], fn, (255, 70, 60) if r["twist"] else (255, 255, 255), 10, "name")
        if r["label"]:
            fv = self.capped(d, r["label"], int(self.fval.size * pop))
            self.center(d, 780, r["label"], fv, YELLOW, 11, "label")
        elif r["tlines"]:
            yy = 780
            for ln in r["tlines"][:2]:
                self.center(d, yy, ln, r["ftext"], YELLOW, 10, "label")
                yy += int(r["ftext"].size * 1.05)
        if isinstance(r["src"], int) and 0 <= r["src"] < len(self.srcs) and not end:
            lab = "SOURCE: " + RU.source_label(self.srcs[r["src"]]).upper()
            self.center(d, 935, lab, self.fsrc, (225, 225, 225), 4, "source")
        # 막대 표
        shown = [x for x in self.rows[:k + 1] if x["value"]]
        if shown:
            top = self.TOP
            self.rect(d, [self.BOX_L, top - 12, self.BOX_R, top + len(shown) * self.ROW + 6], 18, "chart", fill=(6, 6, 10, 175))
            for j, x in enumerate(shown):
                yy = top + j * self.ROW
                cur = x is r
                grow = R.ease(min(1.0, max(0.0, lt) / GROW)) if cur else 1.0
                over = x["twist"] and x["value"] > self.vmax
                full = (self.BOX_R - 8 - self.X0) if over else max(6, (self.X1 - self.X0) * self.frac(x["value"]))
                L = full * grow
                col = (255, 70, 60, 255) if x["twist"] else (YELLOW + (255,) if cur else (200, 202, 214, 220))
                fnm = self.row_font(d, x["text"])
                self.text(d, (60, yy + 6 + (30 - fnm.size) * 0.6), x["text"], fnm,
                          (255, 255, 255) if cur else (210, 210, 220), 3, "chart")
                self.rect(d, [self.X0, yy + 8, self.X0 + L, yy + 42], 8, "chart", fill=col)
                lab = "OFF THE CHART" if over else x["label"]
                lw = d.textlength(lab, font=self.flab)
                inside = self.X0 + L + 12 + lw > self.BOX_R - 10
                lx = (self.X0 + L - lw - 12) if inside else (self.X0 + L + 12)
                lx = max(self.X0 + 8, lx)
                if inside:
                    d.text((lx, yy + 9), lab, font=self.flab, fill=(12, 12, 12))
                    self.box("chart", d.textbbox((lx, yy + 9), lab, font=self.flab))
                else:
                    self.text(d, (lx, yy + 9), lab, self.flab, (255, 255, 255), 3, "chart")
        self.caption(d, t, r, lt)
        return fr


def tick(np, sr: int):
    """시계 '똑딱'(코드로 — 저작권 없음)."""
    n = int(sr * 0.05)
    tt = np.arange(n) / sr
    return (np.sin(2 * math.pi * 1800 * tt) * np.exp(-tt * 90)).astype("float32")


def painter_for(P: dict, s: dict):
    fmt = s.get("format")
    if fmt == "survival":
        return SurvivalPainter(P, s)
    if fmt == "compare":
        return ComparePainter(P, s)
    return Painter(P, s)


def prepare(s: dict, wd: str, mock: bool) -> tuple[dict, object]:
    """목소리 · 그림 → (plan, painter). 테스트는 이걸로 프레임만 본다."""
    ls = RU.lines_of(s)
    texts = [ln["say"] for ln in ls] + [s["gumi"]["say"]]
    voices = R.synth(texts, os.path.join(wd, "voice"), mock)
    raws = []
    for i, ln in enumerate(ls):
        pre = prefix_of(s, ln)
        raw = os.path.join(wd, f"raw_{R.h16(pre, ln['img'], mock, 'v')}.png")
        if not (os.path.exists(raw) and os.path.getsize(raw) > 10000):
            if not gen_vertical(ln["img"], raw, pre, mock):
                raise RuntimeError(f"그림 실패: {ln['img'][:60]}")
        prep = raw[:-4] + "_v.jpg"
        if not os.path.exists(prep):
            fit_vertical(raw, prep)
        raws.append(prep)
        print(f"   🖼️ 그림 {i + 1}/{len(ls)}", flush=True)
    P = plan(s, voices, raws)
    return P, painter_for(P, s)


def sample_times(P: dict) -> dict:
    """확인용 프레임 3장: 첫 1초 · 가운데 · 끝(루프 섞기 전 / 판정 화면)."""
    end = P["total"] - (LOOP + 0.25 if P["loop"] else 0.3)
    return {"first": 0.05, "mid": round(P["total"] / 2, 2), "end": round(end, 2)}


def render(path: str, out_dir: str = OUT, work: str | None = None, mock: bool = False, allow_retired: bool = False) -> dict:
    import numpy as np
    s = json.load(open(path, encoding="utf-8"))
    errs = RU.check(s, allow_retired=allow_retired)          # 옛 설화 RULES(10/9 끝)는 --allow-retired 없이는 렌더하지 않는다
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stem = RU.stem_of(s)
    wd = work or os.path.join(ROOT, "work", "rules", stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    P, pa = prepare(s, wd, mock)
    cap = MAX_SEC_NEW.get(s.get("format"), MAX_SEC)
    if P["total"] > cap:
        raise RuntimeError(f"{P['total']}초 > {cap}")
    silent = os.path.join(wd, "silent.mp4")
    proc = subprocess.Popen([R.ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "19", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for n in range(int(math.ceil(P["total"] * FPS))):
        proc.stdin.write(pa.frame(n / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("인코딩 실패")
    # 소리
    n = int(P["total"] * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for r in P["rows"] + [P["gumi"]]:
        v = R.wav_read(r["wav"])
        a = int(r["start"] * SR)
        voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = R.bed(n, 13, plucks=False)
    b *= vr * 0.22 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)
    rng = np.random.default_rng(5)
    mix = voice + b
    bm = R.boom(rng) * vr * 2.0
    mix[: len(bm)] += bm[:n]
    tk = tick(np, SR) * vr * 1.4
    for r in P["rows"][1:]:
        a = int(r["start"] * SR)
        if r["text"] or r["big"]:
            hit = R.boom(rng)[: int(SR * 0.6)] * vr * (1.6 if r["twist"] else 0.9)
            mix[a:a + len(hit)] += hit[: max(0, n - a)]
        if s.get("format") == "survival":                       # 시계가 굴러가는 동안 똑딱 4번
            for j in range(4):
                b_ = a + int(j * SPIN / 4 * SR)
                mix[b_:b_ + len(tk)] += tk[: max(0, n - b_)]
    mix = mix[: int(P["total"] * SR)]
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    R.wav_write(raw, mix)
    aud = os.path.join(wd, "audio.m4a")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
          "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", aud])
    video = os.path.join(out_dir, f"{stem}.mp4")
    R.mux(silent, aud, video)
    # 확인용 프레임(첫 프레임은 썸네일 겸 — 워크플로 아티팩트가 *_first.jpg 를 올린다)
    frames = {}
    for key, tt in sample_times(P).items():
        p = os.path.join(out_dir, f"{stem}_{key}.jpg")
        pa.frame(tt).save(p, quality=88)
        frames[key] = p
    meta = {"video": video, "first": frames["first"], "frames": frames, "sec": P["total"], "lines": len(P["rows"]),
            "mock": mock, "stem": stem, "format": s.get("format")}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"✅ {video} · {P['total']}초 · {len(P['rows'])}줄")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--work")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--allow-retired", action="store_true", help="옛 설화 RULES(10/9 끝)를 일부러 다시 렌더할 때만")
    a = ap.parse_args()
    render(a.script, a.out, a.work, a.mock, a.allow_retired)
    return 0


if __name__ == "__main__":
    sys.exit(main())
