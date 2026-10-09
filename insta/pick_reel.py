#!/usr/bin/env python3
"""인스타 '오늘의 골라보기' 릴스 렌더 — 보는 사람이 멈춰서 고르는 짧은 영상 5가지 (2026-10-07).

왜: 사용자 10/7 "유튜브 홍보는 아예 하지 말고 인스타 자체를 키우자 · 매일 바이럴을 찾아 벤치마킹해서 AI로 ·
  히트성 아이디어 몇 개를 로테이션으로". 로컬 크롬(@zerocrew.studio)으로 인스타 검색 상위를 잰 결과(10/7):
  심리테스트·성격테스트 517만~1,934만 · 상식 퀴즈 694만~1,407만 · 운세·사주·타로 135만~409만.
  다섯 꼴 모두 ★보는 사람이 멈춰서 고르고★ 댓글에 번호를 남기는 꼴이다(왕별이 '내 것 찾기'와 같은 원리).

꼴(kind) — 편성은 pick_plan.py 가 날짜로 정한다:
  pick    그림 넷 중 하나 고르기 → 번호별 결과(그림 고르기형 심리테스트)
  card    뒤집힌 카드 넷 중 하나 → 앞면과 메시지(타로 고르기)
  quiz    상식 퀴즈 두세 문제 · 3초 세고 정답('이거 맞히면 상위 10%')
  balance 밸런스 게임 세 판 · 둘 중 하나(댓글로 A·B)
  birth   태어난 달로 보는 표 한 장(12칸 · 내 달 찾기)

★남의 것을 베끼지 않는다: 빌리는 건 '꼴'뿐. 그림은 매번 새로 그리고(Spark z-image), 문구는 새로 쓰고,
  소리는 코드로 만든 배경음 + 우리 목소리(Supertonic F1). 인스타는 남의 영상·음원을 살짝 바꾼 재게시를 추천에서 뺀다.
화면은 파스텔(2030 인스타 테스트 계정의 밝은 결). 아래 약 25%(y 1480~)는 인스타 캡션·버튼 자리라 비운다.
캡션·커버(10/9): 회차 '오늘의 골라보기 #N' · 보내기 한 줄 · 숫자 댓글 한 줄 · 해시태그 5개는 코드가 붙인다(caption_of·cover_of).

    python insta/pick_reel.py check <script.json> [...]
    python insta/pick_reel.py render <script.json> --out output/insta_pick_render [--mock]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402  (회차 번호 = 편성 시작일 기준)
import render_reel as R  # noqa: E402  (글꼴·목소리·배경음·인코딩 도구를 같이 쓴다)

W, H, FPS, SR = R.W, R.H, R.FPS, R.SR
LZ = getattr(Image, "Resampling", Image).LANCZOS
KINDS = ("pick", "card", "quiz", "balance", "birth")
BG_TOP, BG_BOT = (246, 238, 255), (255, 236, 228)
INK, SUB, ACC, OK = (40, 32, 58), (110, 98, 130), (124, 92, 230), (46, 170, 110)
NUM_BG = [(255, 140, 140), (255, 186, 110), (110, 200, 160), (120, 160, 255)]
STYLE = ("dreamy pastel storybook illustration, soft diffused light, one subject centered on a plain soft pastel "
         "background, gentle colors, clean shapes, cozy and calm, high detail, ")
COUNT = 3
BANNED = ("치료", "완치", "진단", "우울증", "투자", "주식", "코인", "로또", "대박", "무조건", "죽음", "사망", "저주",
          "팔로우", "링크", "DM", "정확도")
# 캡션 고정 문구(10/9) — Mosseri 2025-01-22: 비팔로워 도달에 가장 무거운 신호는 '보내기(DM 공유)'.
#   대본 작가(루틴)가 지시를 안 지켜서 코드가 꼴마다 붙인다. 대본 caption 의 비슷한 줄은 뺀다(겹치지 않게).
SERIES = "오늘의 골라보기"
SHARE = {"pick": "친구한테 보내서 뭐 골랐는지 물어봐요 💌", "card": "친구한테 보내서 몇 번 카드 골랐는지 물어봐요 💌",
         "quiz": "친구한테 보내서 몇 개 맞히나 물어봐요 💌", "balance": "친구한테 보내서 뭐 골랐는지 물어봐요 💌",
         "birth": "친구한테 보내서 그 친구 달도 찾아 줘요 💌"}
# 숫자 하나만 쓰면 되는 댓글 — balance 는 영상 끝이 '세 글자'라 같은 말로(세 판 A·B)
REPLY = {"pick": "몇 번? 숫자만 댓글로 남겨 줘요", "card": "몇 번? 숫자만 댓글로 남겨 줘요",
         "quiz": "정답 몇 개 맞혔어요? 숫자만 댓글로", "balance": "A·B 세 글자만 댓글로 (예: ABA)",
         "birth": "몇 월생? 숫자만 댓글로 남겨 줘요"}
ASK_WORDS = ("댓글", "보내", "공유", "태그", "친구")     # 대본 caption 에서 이런 말이 든 줄(첫 줄 빼고)은 코드 문구와 겹친다
HASHTAG_MAX = 5                                           # 인스타 2025-12-18부터 5개 제한 · 검색에만 돕고 도달은 안 늘린다
_SERIES_RE = re.compile(SERIES + r"\s*#\d+\s*[·|:-]?\s*")
_TAG_RE = re.compile(r"(?<!\S)#(?!\d+(?:\s|$))[^\s#]+")   # 본문 속 해시태그(숫자만인 #5 는 회차라 남긴다)


def load(p: str) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _texts(s: dict) -> list[str]:
    out = [*s.get("headline", []), s.get("say_intro", ""), s.get("say_outro", ""), s.get("outro_text", ""), s.get("caption", "")]
    for o in s.get("options", []):
        out += [o.get(k, "") for k in ("name", "result", "lines", "say")]
    for r in s.get("rounds", []):
        out += [r.get("q", ""), r.get("why", ""), r.get("say_q", ""), r.get("say_a", ""), r.get("say", ""),
                *r.get("choices", []), (r.get("a") or {}).get("label", ""), (r.get("b") or {}).get("label", "")]
    out += [c.get("text", "") for c in s.get("cells", [])]
    return out


def check(s: dict) -> list[str]:
    errs = []
    kind = s.get("kind")
    if kind not in KINDS:
        return [f"kind 는 {KINDS}"]
    if not (isinstance(s.get("headline"), list) and len(s["headline"]) == 2 and all(0 < len(x) <= 14 for x in s["headline"])):
        errs.append("headline 은 두 줄 · 줄마다 14자 이내")
    if not s.get("say_intro") or len(s["say_intro"]) > 50:
        errs.append("say_intro 1~50자")
    if not s.get("caption"):
        errs.append("caption 없음")
    if not s.get("bench", {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    try:                                                   # 회차 번호(#N)가 날짜로 정해진다 — 시작일 전은 #0 이하가 된다
        if dt.date.fromisoformat(s.get("date", "")) < P.START:
            errs.append(f"date 는 {P.START} 이후")
    except (TypeError, ValueError):
        errs.append("date 는 YYYY-MM-DD")
    if kind in ("pick", "card"):
        opts = s.get("options") or []
        if len(opts) != 4:
            errs.append("options 는 4개")
        for k, o in enumerate(opts, 1):
            need = ("img", "name", "result", "lines", "say") + (("reveal_img",) if kind == "card" else ())
            errs += [f"{k}번 {key} 없음" for key in need if not o.get(key)]
            if len(o.get("name", "")) > 8:
                errs.append(f"{k}번 name 8자 이내")
            if len(o.get("result", "")) > 12:
                errs.append(f"{k}번 result 12자 이내")
            if len(o.get("lines", "")) > 46:
                errs.append(f"{k}번 lines 46자 이내")
            if not o.get("say", "").startswith(f"{k}번") or len(o.get("say", "")) > 30:
                errs.append(f"{k}번 say 는 '{k}번'으로 시작 · 30자 이내(결과 한 마디만 읽는다)")
    elif kind == "quiz":
        rs = s.get("rounds") or []
        if not 2 <= len(rs) <= 3:
            errs.append("rounds 는 2~3개")
        for k, r in enumerate(rs, 1):
            ch = r.get("choices") or []
            if len(ch) != 4 or any(not c or len(c) > 12 for c in ch):
                errs.append(f"{k}번 문제 choices 4개 · 12자 이내")
            if r.get("answer") not in (0, 1, 2, 3):
                errs.append(f"{k}번 문제 answer 는 0~3")
            if not r.get("q") or len(r["q"]) > 40:
                errs.append(f"{k}번 문제 q 1~40자")
            if len(r.get("why", "")) > 40:
                errs.append(f"{k}번 문제 why 40자 이내")
            if not r.get("say_q") or not r.get("say_a"):
                errs.append(f"{k}번 문제 say_q·say_a 없음")
            elif r.get("answer") in (0, 1, 2, 3) and len(ch) == 4 and ch[r["answer"]] not in r["say_a"]:
                errs.append(f"{k}번 문제 say_a 에 정답 '{ch[r['answer']]}'이 없다")
    elif kind == "balance":
        rs = s.get("rounds") or []
        if len(rs) != 3:
            errs.append("rounds 는 3개")
        for k, r in enumerate(rs, 1):
            for side in ("a", "b"):
                x = r.get(side) or {}
                if not x.get("img") or not x.get("label") or len(x["label"]) > 12:
                    errs.append(f"{k}판 {side} img·label(12자 이내) 필요")
            if not r.get("say") or len(r["say"]) > 40:
                errs.append(f"{k}판 say 1~40자")
    elif kind == "birth":
        cells = s.get("cells") or []
        if [c.get("m") for c in cells] != list(range(1, 13)):
            errs.append("cells 는 1~12월 순서대로 12칸")
        if any(not c.get("text") or len(c["text"]) > 14 for c in cells):
            errs.append("cells text 1~14자")
        if not s.get("bg"):
            errs.append("bg(배경 그림 묘사) 없음")
    hits = sorted({w for w in BANNED for t in _texts(s) if w in t})
    if hits:
        errs.append(f"금지어 {hits}")
    return errs


def warns(s: dict) -> list[str]:
    """막지는 않고 알리기만 한다(10/9) — 렌더 때 코드가 알아서 고친다."""
    out = []
    tags = s.get("hashtags") or []
    if len(tags) > HASHTAG_MAX:
        out.append(f"hashtags {len(tags)}개 — 앞 {HASHTAG_MAX}개만 쓴다(인스타 5개 제한) · 빠지는 것 {tags[HASHTAG_MAX:]}")
    lines = (s.get("caption") or "").strip().splitlines()[1:]
    if any(w in ln for ln in lines for w in ASK_WORDS) or SERIES in (s.get("caption") or ""):
        out.append("caption 의 댓글·보내기·회차 말은 코드가 붙인다 — 그 줄은 빼고 렌더한다")
    return out


# ── 그림 ──────────────────────────────────────────────
def gen(prompt: str, out: str, mock: bool) -> None:
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return
    if mock:
        R.gen_image(prompt, out, True)
        return
    import wbspark
    for attempt in range(3):
        R.spark_wait()
        if wbspark.generate_image(STYLE + prompt, out, no_llm=True, model=R.IMG_MODEL or None, timeout_sec=600):
            return
        time.sleep(10 + attempt * 20)
    raise RuntimeError(f"그림 실패: {prompt[:50]}")


def rounded(im: Image.Image, r: int) -> Image.Image:
    im = im.convert("RGBA")
    im.putalpha(R.rounded_mask(im.width, im.height, r))
    return im


def fade(im: Image.Image, a: float) -> Image.Image:
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def bg() -> Image.Image:
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
    return g.resize((W, H))


def ctext(d, y, text, f, fill):
    d.text(((W - R.tlen(d, text, f)) / 2, y), text, font=f, fill=fill)


def badge(d, cx, cy, r, label, color, f):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,), outline=(255, 255, 255), width=6)
    d.text((cx - R.tlen(d, label, f) / 2, cy - f.size * 0.62), label, font=f, fill=(255, 255, 255))


def shadow(im: Image.Image, box, r=40):
    x0, y0, x1, y1 = [int(v) for v in box]
    sh = Image.new("RGBA", (x1 - x0 + 60, y1 - y0 + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([30, 36, x1 - x0 + 30, y1 - y0 + 36], r, fill=(90, 60, 140, 60))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x0 - 30, y0 - 30))


def tile_of(path: str, w: int, h: int, r: int) -> Image.Image:
    return rounded(R.cover(Image.open(path).convert("RGB"), w, h), r)


# ── 화면 ──────────────────────────────────────────────
class Painter:
    """segs: [{kind, start, dur, ...}] — 꼴마다 그린다. 늘 위 두 줄 제목, 아래 25%는 비운다."""

    def __init__(self, s: dict, a: dict, segs: list[dict]):
        self.s, self.a, self.segs = s, a, segs
        self.base = bg().convert("RGBA")
        F = R.font
        self.f = {"head": F("head", 78), "head2": F("head", 62), "num": F("head", 58), "big": F("head", 84),
                  "line": F("bold", 50), "small": F("bold", 40), "chip": F("bold", 36)}
        self.cache: dict = {}
        self.for_cover = False                             # 커버를 그릴 때만 True(cover_of) — 회차 라벨 자리를 비운다

    def seg_at(self, t: float) -> dict:
        for sg in self.segs:
            if sg["start"] <= t < sg["start"] + sg["dur"]:
                return sg
        return self.segs[-1]

    def headline(self, d, y0=150, small=False):
        f = self.f["head2"] if small else self.f["head"]
        for i, line in enumerate(self.s["headline"]):
            ctext(d, y0 + i * (f.size + 18), line, f, INK if i == 0 else ACC)

    def countdown(self, d, left: float, y: int):
        n = max(1, math.ceil(left))
        p = 1 - (left - (n - 1))
        ctext(d, y, str(n), R.font("head", int(140 * (1.25 - 0.25 * min(1, p * 3)))), ACC)

    def frame(self, t: float) -> Image.Image:
        sg = self.seg_at(t)
        kind = "pick" if self.s["kind"] == "card" else self.s["kind"]
        return getattr(self, f"f_{kind}")(sg, t - sg["start"]).convert("RGB")

    def chip(self, d, y, text):
        d.rounded_rectangle([W / 2 - 90, y, W / 2 + 90, y + 60], 30, fill=ACC + (255,))
        ctext(d, y + 4, text, self.f["chip"], (255, 255, 255))

    # pick · card ─────────────────────────────────────
    def _grid(self) -> Image.Image:
        if "grid" not in self.cache:
            im = self.base.copy()
            d = ImageDraw.Draw(im)
            self.headline(d)
            tile, gap = 460, 36
            x0, y0 = (W - 2 * tile - gap) // 2, 400
            for k, p in enumerate(self.a["opts"]):
                x, y = x0 + (k % 2) * (tile + gap), y0 + (k // 2) * (tile + gap)
                shadow(im, (x, y, x + tile, y + tile))
                im.alpha_composite(tile_of(p, tile, tile, 40), (x, y))
                badge(d, x + 58, y + 58, 44, str(k + 1), NUM_BG[k], self.f["num"])
            self.cache["grid"] = im
        return self.cache["grid"]

    def _get(self, key, path, w, h, r):
        if key not in self.cache:
            self.cache[key] = tile_of(path, w, h, r)
        return self.cache[key]

    def f_pick(self, sg, lt):
        if sg["kind"] in ("intro", "outro"):
            im = self._grid().copy()
            d = ImageDraw.Draw(im)
            if sg["kind"] == "outro":
                ctext(d, 1405, self.s.get("outro_text", "몇 번 골랐어요?"), self.f["head2"], ACC)
            elif sg["dur"] - lt <= COUNT:
                self.countdown(d, sg["dur"] - lt, 1385)
            elif not self.for_cover:                       # 커버는 이 자리에 회차 라벨(제목이 이미 '골라 봐요')
                ctext(d, 1420, "하나 골라 보세요", self.f["line"], SUB)
            return im
        k = sg["k"]
        o = self.s["options"][k]
        card = self.s["kind"] == "card"
        face = self._get(f"big{k}", self.a["reveal"][k] if card else self.a["opts"][k], 700, 700, 56)
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if card and lt < 0.36:                               # 카드 뒤집기 — 가로로 접혔다 펴진다
            back = self._get(f"back{k}", self.a["opts"][k], 700, 700, 56)
            wv = max(8, int(700 * abs(1 - lt / 0.18)))
            big = (back if lt < 0.18 else face).resize((wv, 700), LZ)
        else:
            z = 1.0 + 0.04 * min(1, lt / max(0.1, sg["dur"]))
            big = face.resize((int(700 * z), int(700 * z)), LZ)
        im.alpha_composite(big, ((W - big.width) // 2, 300 - (big.height - 700) // 2))
        badge(d, (W - 700) // 2 + 66, 366, 54, str(k + 1), NUM_BG[k], R.font("head", 70))
        pop = min(1.0, lt / 0.25)
        head = f"{o['name']} → {o['result']}"
        fr = R.font("head", int(84 * (0.85 + 0.15 * pop)))
        if R.tlen(d, head, fr) > W - 120:
            fr = R.font("head", 64)
        ctext(d, 1040, head, fr, INK)
        fl, lines = R.fit_wrap(d, o["lines"], "bold", 50, 40, W - 170, 2)
        for i, ln in enumerate(lines):
            ctext(d, 1165 + i * (fl.size + 16), ln, fl, SUB)
        mx0 = (W - 4 * 150 - 3 * 30) // 2
        for j in range(4):
            m = self._get(f"mini{j}", self.a["opts"][j], 150, 150, 24)
            x, y = mx0 + j * 180, 1330
            im.alpha_composite(m if j == k else fade(m, 0.35), (x, y))
            if j == k:
                d.rounded_rectangle([x - 6, y - 6, x + 156, y + 156], 28, outline=NUM_BG[k], width=8)
            badge(d, x + 26, y + 26, 22, str(j + 1), NUM_BG[j], R.font("head", 30))
        return im

    # quiz ────────────────────────────────────────────
    def f_quiz(self, sg, lt):
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if sg["kind"] == "outro":
            ctext(d, 760, self.s.get("outro_text", "몇 개 맞혔어요?"), self.f["big"], ACC)
            return im
        intro = sg["kind"] == "intro"                         # ★첫 장면부터 1번 문제가 보인다(첫 1초가 멈추게 한다)
        k = 0 if intro else sg["k"]
        r = self.s["rounds"][k]
        self.chip(d, 290, f"{k + 1} / {len(self.s['rounds'])}")
        fq, ql = R.fit_wrap(d, r["q"], "head", 66, 50, W - 140, 3)
        for i, ln in enumerate(ql):
            ctext(d, 400 + i * (fq.size + 14), ln, fq, INK)
        reveal = (not intro) and lt >= sg["phase_at"]
        y0 = 400 + len(ql) * (fq.size + 14) + 50
        for j, c in enumerate(r["choices"]):
            y = y0 + j * 150
            good = reveal and j == r["answer"]
            fill = (232, 250, 240, 255) if good else (255, 255, 255, 150 if reveal else 235)
            d.rounded_rectangle([90, y, W - 90, y + 124], 30, fill=fill, outline=OK if good else (226, 216, 245),
                                width=6 if good else 3)
            badge(d, 160, y + 62, 38, str(j + 1), NUM_BG[j], self.f["chip"])
            d.text((230, y + 30), c, font=self.f["line"], fill=INK if (not reveal or good) else SUB)
            if good:
                d.text((W - 200, y + 34), "정답", font=self.f["small"], fill=OK)
        if intro:
            ctext(d, y0 + 4 * 150 + 30, "3초 안에 맞혀 보세요", self.f["line"], SUB)
        elif not reveal:
            if sg["phase_at"] - lt <= COUNT:
                self.countdown(d, sg["phase_at"] - lt, y0 + 4 * 150 + 10)
        elif r.get("why"):
            fw, wl = R.fit_wrap(d, r["why"], "bold", 44, 36, W - 160, 2)
            for i, ln in enumerate(wl):
                ctext(d, y0 + 4 * 150 + 20 + i * (fw.size + 12), ln, fw, SUB)
        return im

    # balance ─────────────────────────────────────────
    def f_balance(self, sg, lt):
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if sg["kind"] == "outro":
            ctext(d, 720, self.s.get("outro_text", "나는 A·B·?"), self.f["big"], ACC)
            ctext(d, 850, "댓글로 세 글자만 남겨 줘요", self.f["line"], SUB)
            return im
        intro = sg["kind"] == "intro"                         # ★첫 장면부터 1판 그림이 보인다
        k = 0 if intro else sg["k"]
        r = self.s["rounds"][k]
        if intro:
            lt = 1.0
        self.chip(d, 270, f"{k + 1} / 3")
        cw, chh = W - 180, 470
        for side, (y, col) in zip(("a", "b"), ((370, NUM_BG[0]), (900, NUM_BG[3]))):
            t = self._get(f"bal{k}{side}", self.a["bal"][k][side], cw, chh, 44)
            pop = min(1.0, max(0.0, (lt - (0 if side == "a" else 0.2)) / 0.25))
            shadow(im, (90, y, 90 + cw, y + chh), 44)
            im.alpha_composite(fade(t, 0.4 + 0.6 * pop), (90, y))
            lab, fl = r[side]["label"], self.f["line"]
            tw = R.tlen(d, lab, fl)
            d.rounded_rectangle([W / 2 - tw / 2 - 30, y + chh - 96, W / 2 + tw / 2 + 30, y + chh - 20], 36,
                                fill=(255, 255, 255, 235))
            ctext(d, y + chh - 92, lab, fl, INK)
            badge(d, 150, y + 60, 42, side.upper(), col, self.f["num"])
        d.ellipse([W / 2 - 62, 843, W / 2 + 62, 967], fill=(255, 255, 255, 255), outline=ACC, width=6)
        ctext(d, 868, "VS", self.f["head2"], ACC)
        left = sg["dur"] - lt
        if not intro and left <= COUNT:
            d.text((W - 160, 850), str(max(1, math.ceil(left))), font=R.font("head", 90), fill=ACC)
        return im

    # birth ───────────────────────────────────────────
    def f_birth(self, sg, lt):
        if "birth" not in self.cache:
            im = self.base.copy()
            if self.a.get("bg"):
                b = R.cover(Image.open(self.a["bg"]).convert("RGB"), W, H).filter(ImageFilter.GaussianBlur(18))
                im = Image.blend(b, Image.new("RGB", (W, H), (255, 255, 255)), 0.62).convert("RGBA")
            d = ImageDraw.Draw(im)
            self.headline(d, 120)
            cw, chh, gx, gy = 300, 230, 18, 18
            x0, y0 = (W - 3 * cw - 2 * gx) // 2, 360
            for i, c in enumerate(self.s["cells"]):
                x, y = x0 + (i % 3) * (cw + gx), y0 + (i // 3) * (chh + gy)
                d.rounded_rectangle([x, y, x + cw, y + chh], 30, fill=(255, 255, 255, 225), outline=(226, 216, 245), width=3)
                d.text((x + 24, y + 18), f"{c['m']}월", font=self.f["num"], fill=NUM_BG[i % 4])
                ft, tl = R.fit_wrap(d, c["text"], "bold", 40, 30, cw - 40, 2)
                for j, ln in enumerate(tl):
                    d.text((x + 24, y + 100 + j * (ft.size + 10)), ln, font=ft, fill=INK)
            self.cache["birth"] = im
            self.cache["xy"] = (x0, y0, cw, chh, gx, gy)
        im = self.cache["birth"].copy()
        x0, y0, cw, chh, gx, gy = self.cache["xy"]
        k = int(lt / 0.12)                                   # 칸이 차례로 한 번 반짝
        if k < 12:
            x, y = x0 + (k % 3) * (cw + gx), y0 + (k // 3) * (chh + gy)
            ImageDraw.Draw(im).rounded_rectangle([x - 4, y - 4, x + cw + 4, y + chh + 4], 32, outline=ACC, width=8)
        return im


# ── 시간표 · 소리 ──────────────────────────────────────
def says_of(s: dict) -> list[str]:
    out = [s["say_intro"]]
    out += [o["say"] for o in s.get("options", [])]
    for r in s.get("rounds", []):
        out += [x for x in (r.get("say_q"), r.get("say_a"), r.get("say")) if x]
    if s["kind"] != "birth":
        out.append(s.get("say_outro") or "몇 번 골랐어요?")
    return out


def plan(s: dict, dur: dict) -> tuple[list[dict], list[float]]:
    """장면(segs)과 틱 시각. dur = 말 → 초."""
    segs, ticks = [], []
    kind = s["kind"]

    def add(**kw):
        kw.setdefault("start", segs[-1]["start"] + segs[-1]["dur"] if segs else 0.0)
        segs.append(kw)
        return kw

    if kind in ("pick", "card"):
        d0 = max(6.5, dur[s["say_intro"]] + 0.4 + COUNT)
        add(kind="intro", dur=d0, say=s["say_intro"], at=0.3)
        ticks += [d0 - c for c in range(COUNT, 0, -1)]
        for k, o in enumerate(s["options"]):
            sg = add(kind="res", k=k, dur=dur[o["say"]] + 1.0, say=o["say"])
            sg["at"] = sg["start"] + 0.25
            ticks.append(sg["start"])
    elif kind == "quiz":
        add(kind="intro", dur=dur[s["say_intro"]] + 0.6, say=s["say_intro"], at=0.2)
        for k, r in enumerate(s["rounds"]):
            pa = dur[r["say_q"]] + 0.3 + COUNT
            sg = add(kind="q", k=k, dur=pa + dur[r["say_a"]] + 1.2, say=r["say_q"], phase_at=pa, say2=r["say_a"])
            sg["at"], sg["at2"] = sg["start"] + 0.2, sg["start"] + pa + 0.15
            ticks += [sg["start"]] + [sg["start"] + pa - c for c in range(COUNT, 0, -1)]
    elif kind == "balance":
        add(kind="intro", dur=dur[s["say_intro"]] + 0.5, say=s["say_intro"], at=0.2)
        for k, r in enumerate(s["rounds"]):
            sg = add(kind="r", k=k, dur=dur[r["say"]] + 0.4 + COUNT, say=r["say"])
            sg["at"] = sg["start"] + 0.2
            ticks += [sg["start"]] + [sg["start"] + sg["dur"] - c for c in range(COUNT, 0, -1)]
    else:  # birth — 짧게 · 다시 돈다
        add(kind="table", dur=max(9.0, dur[s["say_intro"]] + 5.0), say=s["say_intro"], at=0.3)
        ticks.append(0.05)
    if kind != "birth":
        out = s.get("say_outro") or "몇 번 골랐어요?"
        sg = add(kind="outro", dur=max(2.2, dur[out] + 0.9), say=out)
        sg["at"] = sg["start"] + 0.2
        ticks.append(sg["start"])
    return segs, ticks


def mix_audio(segs, ticks, got, total, wd) -> str:
    import numpy as np
    n = int(total * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for sg in segs:
        for say_k, at_k in (("say", "at"), ("say2", "at2")):
            if sg.get(say_k):
                v = R.wav_read(got[sg[say_k]])
                a = int(sg[at_k] * SR)
                voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = R.bed(n, seed=11)
    b *= vr * 0.18 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)
    win = int(SR * 0.2)
    duck = R.movavg(1 - 0.5 * np.clip(R.movavg(np.abs(voice), win) / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
    sfx = np.zeros(n, dtype="float32")
    rng = np.random.default_rng(5)
    for tt in ticks:
        tk = R.tick(rng) * vr * 1.1
        a = int(tt * SR)
        sfx[a:a + len(tk)] += tk[: max(0, n - a)]
    mix = (voice + b * duck + sfx)[: int(total * SR)]
    fo = int(SR * 0.5)
    mix[-fo:] *= np.linspace(1, 0, fo, dtype="float32")
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    R.wav_write(raw, mix)
    m4a = os.path.join(wd, "mix.m4a")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
          "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", m4a])
    return m4a


def assets(s: dict, wd: str, mock: bool) -> dict:
    def g(prompt, tag):
        p = os.path.join(wd, f"{tag}_{hashlib.sha1((STYLE + prompt + str(mock)).encode()).hexdigest()[:10]}.png")
        gen(prompt, p, mock)
        return p
    a: dict = {}
    if s["kind"] in ("pick", "card"):
        a["opts"] = [g(o["img"], f"opt{k}") for k, o in enumerate(s["options"])]
        if s["kind"] == "card":
            a["reveal"] = [g(o["reveal_img"], f"rev{k}") for k, o in enumerate(s["options"])]
    elif s["kind"] == "balance":
        a["bal"] = [{side: g(r[side]["img"], f"bal{k}{side}") for side in ("a", "b")} for k, r in enumerate(s["rounds"])]
    elif s["kind"] == "birth":
        a["bg"] = g(s["bg"], "bg")
    return a


def series_label(s: dict) -> str:
    return f"{SERIES} #{P.series_no(dt.date.fromisoformat(s['date']))}"


def hashtags_of(s: dict) -> list[str]:
    """앞 5개만(겹친 것 빼고) — 10/9: 인스타 2025-12-18부터 5개 제한."""
    out: list[str] = []
    for t in s.get("hashtags") or []:
        if t and t not in out:
            out.append(t)
    return out[:HASHTAG_MAX]


def _hook(caption: str) -> str:
    """대본 caption 에서 코드가 붙이는 말(회차·댓글·보내기·본문 해시태그)을 뺀 나머지."""
    text = _SERIES_RE.sub("", caption)
    lines = [re.sub(r"\s{2,}", " ", _TAG_RE.sub("", ln)).rstrip() for ln in text.strip().splitlines()]
    keep = lines[:1] + [ln for ln in lines[1:] if not any(w in ln for w in ASK_WORDS)]
    return "\n".join(keep).strip()


def caption_of(s: dict) -> str:
    # 10/9: 첫 줄 앞에 회차('오늘의 골라보기 #N') · 끝에 보내기·숫자 댓글 두 줄 · 해시태그 5개 — 전부 코드가 강제한다
    body = f"{series_label(s)} · {_hook(s['caption'])}"
    if s["kind"] in ("pick", "card"):
        body += "\n\n" + "\n".join(f"{k}번 {o['name']} — {o['result']}: {o['lines']}" for k, o in enumerate(s["options"], 1))
    elif s["kind"] == "quiz":
        body += "\n\n" + "\n".join(f"{k}번 문제 정답: {r['choices'][r['answer']]}" + (f" — {r['why']}" if r.get("why") else "")
                                   for k, r in enumerate(s["rounds"], 1))
    elif s["kind"] == "birth":
        body += "\n\n" + "\n".join(f"{c['m']}월 — {c['text']}" for c in s["cells"])
    body += f"\n\n{SHARE[s['kind']]}\n{REPLY[s['kind']]}"
    tags = hashtags_of(s)
    return body + ("\n\n" + " ".join(tags) if tags else "")


def cover_of(pa: Painter, s: dict) -> Image.Image:
    """커버 = 첫 장면 + 작은 회차 라벨(10/9). 라벨은 그리드 3:4 가운데 자르기(y 240~1680)에도 남고
    아래 25%(y 1440~, 캡션 자리)는 넘지 않게 y 1384~1432 에 둔다. 글꼴·색은 화면과 같은 토큰(bold · ACC)."""
    pa.for_cover = True
    try:
        im = pa.frame(0.5 if s["kind"] != "birth" else 2.0).convert("RGBA")
    finally:
        pa.for_cover = False
    d = ImageDraw.Draw(im)
    text, f = series_label(s), R.font("bold", 32)
    tw, (y0, y1) = R.tlen(d, text, f), (1384, 1432)
    d.rounded_rectangle([W / 2 - tw / 2 - 26, y0, W / 2 + tw / 2 + 26, y1], (y1 - y0) // 2, fill=(255, 255, 255, 255),
                        outline=ACC, width=3)
    bb = f.getbbox(text)
    ctext(d, y0 + (y1 - y0 - (bb[3] - bb[1])) / 2 - bb[1], text, f, ACC)
    return im.convert("RGB")


def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    s = load(path)
    errs = check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    for w in warns(s):
        print(f"⚠️ {w}")
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    got, how = R.synth(says_of(s), os.path.join(wd, "voice"), mock)
    dur = {t: R.wav_dur(p) for t, p in got.items()}
    segs, ticks = plan(s, dur)
    total = round(segs[-1]["start"] + segs[-1]["dur"], 3)
    m4a = mix_audio(segs, ticks, got, total, wd)
    pa = Painter(s, a, segs)
    silent = os.path.join(wd, "silent.mp4")
    R.encode(pa, total, silent)
    out = os.path.join(out_dir, f"{stem}.mp4")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-c:v", "copy", "-c:a", "copy", "-shortest", out])
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    cover_of(pa, s).save(cover, "JPEG", quality=90)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    picks = [0.5] + [sg["start"] + sg["dur"] * f for sg in segs for f in ((0.35, 0.9) if sg["kind"] == "q" else (0.7,))]
    tw, th = 360, 640
    sh_im = Image.new("RGB", (tw * 3, th * 2), (0, 0, 0))
    for i, tt in enumerate(picks[:6]):
        sh_im.paste(pa.frame(tt).resize((tw, th), LZ), ((i % 3) * tw, (i // 3) * th))
    sh_im.save(sheet, "JPEG", quality=85)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "video": out, "cover": cover,
            "sheet": sheet, "seconds": total, "voice": how, "caption": caption_of(s)}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 '오늘의 골라보기' 릴스")
    ap.add_argument("cmd", choices=["check", "render"])
    ap.add_argument("script", nargs="+")
    ap.add_argument("--out", default=os.path.join(R.ROOT, "output", "insta_pick_render"))
    ap.add_argument("--work", default=os.path.join(R.ROOT, "output", "insta_pick_work"))
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    bad = 0
    for p in a.script:
        if a.cmd == "check":
            s = load(p)
            errs, ws = check(s), warns(s)
            print(f"{'✅' if not errs else '❌'} {p}" + ("" if not errs else "\n   " + "\n   ".join(errs))
                  + "".join(f"\n   ⚠️ {w}" for w in ws))
            bad += bool(errs)
            continue
        meta = render(p, a.out, a.work, a.mock)
        print(json.dumps({k: meta[k] for k in ("video", "seconds", "voice")}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
