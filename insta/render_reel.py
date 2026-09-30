#!/usr/bin/env python3
"""인스타 릴스 렌더 — 대본 JSON → 1080×1920 mp4(30~45초) · 커버 · 한눈에 보기 · 메타(게시용 캡션).

    python insta/render_reel.py insta/samples/first-second.json --stats output/insta_render/stats.json
    python insta/render_reel.py <script> --mock            # Spark·네트워크 없이(가짜 목소리·그림·숫자) — 테스트
    INSTA_HOST=gumi python insta/render_reel.py <script>    # 아래 진행자 자리에 구미(기본 none = 비움)

화면(위 → 아래)
  ① 두 줄 제목 — ★첫 프레임부터 끝까지 고정(소리 없이 넘기며 봐도 무슨 영상인지 보인다)
  ② 실물 화면 — 그림(Spark)·유튜브 공개 썸네일·숫자 카드·막대·단계·흐름도·말풍선. 전부 데이터로 코드가 그린다
     (터미널·설정 화면·토큰이 찍힐 스크린샷은 쓰지 않는다)
  ③ 자막 — 지금 말하는 조각(숫자는 노란색)
  ④ 진행자 자리 — INSTA_HOST=none(기본) | gumi(원형 초상 · 'AI 진행자' 표시 · 말할 때 테두리가 빛난다)
소리: Spark Supertonic(F1 — 왕별이 쇼츠와 같은 목소리, 실패하면 edge-tts) 한 문장씩 + 코드로 만든 잔잔한 배경음
      (덕킹) + 장면 전환 틱, 마지막에 -14 LUFS. 숫자는 코드가 한글 읽기로 바꿔 읽힌다(insta.to_speech).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "gumiho", "tales"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import insta as I  # noqa: E402
from render_tale import ffmpeg, movavg, sh, spark_wait, wav_read, wav_write  # noqa: E402  (구미호 렌더러의 검증된 도구)

W, H = 1080, 1920
FPS = int(os.environ.get("INSTA_FPS", "30"))
SR = 44100
HOST = os.environ.get("INSTA_HOST", "none").strip().lower()
VOICE = os.environ.get("INSTA_VOICE", "F1")                      # Supertonic 프리셋 — 왕별이 쇼츠 별하와 같다(F3·F4 는 숫자 발음 오류)
EDGE_VOICE = os.environ.get("INSTA_EDGE_VOICE", "ko-KR-SunHiNeural")
TTS = os.environ.get("INSTA_TTS", "wbspark").strip().lower()     # wbspark | edge
TEMPO = float(os.environ.get("INSTA_TEMPO", "1.0"))
IMG_MODEL = os.environ.get("INSTA_IMG_MODEL", "z-image-turbo")
LOOK = ("clean editorial illustration, soft studio light, muted navy and warm amber palette, simple shapes, "
        "calm and friendly, high detail, ")
MIN_SEC, MAX_SEC, HARD_MAX = 30.0, 45.0, 47.0
LEAD, GAP, TAIL, XF = 0.12, 0.38, 0.7, 0.22
ASSETS = os.path.join(ROOT, "gumiho", "assets", "tales")
FONT_DIR = os.path.join(ROOT, "pipeline", "motion", "assets", "fonts")

# ── 배치(1080×1920) — 인스타 격자 미리보기(가운데 3:4 = y 240~1680) 안에 제목이 들어오게 ──
HEAD = (60, 236, 1020, 516)         # 두 줄 제목
TAG_Y = 530
PROG = (60, 590, 1020, 596)
PANEL = (60, 620, 1020, 1372)       # 실물 화면 960×752
PW, PH = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
CAP = (40, 1392, 1040, 1556)        # 자막
HOST_BOX = (60, 1586, 280, 1806)    # 진행자(원 220)

BG_TOP, BG_BOT = (13, 15, 21), (21, 25, 35)
INK, MUTED, DIM = (238, 240, 245), (150, 157, 172), (92, 100, 118)
ACCENT, GOOD, BAD = (255, 212, 71), (86, 214, 138), (246, 112, 112)
CARD, LINE = (26, 30, 41), (48, 54, 70)
TONE = {"good": GOOD, "bad": BAD, "neutral": ACCENT}


# ── 글꼴 ──────────────────────────────────────────────
# Pretendard(레포 pipeline/motion 의 woff2) → fontTools 로 ttf 변환해 쓴다(리눅스·윈도 같은 글꼴).
# 안 되면 Noto CJK(리눅스 fonts-noto-cjk) → Noto Sans KR VF(윈도) → 맑은 고딕. 하나도 없으면 ★멈춘다
# (2026-09-30 설화 채널 사고: 기본 비트맵 글꼴로 조용히 떨어져 큰 글자가 깨알처럼 나갔다).
_FALLBACK = {
    "head": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             r"C:\Windows\Fonts\NotoSansKR-VF.ttf", r"C:\Windows\Fonts\malgunbd.ttf"],
    "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", r"C:\Windows\Fonts\NotoSansKR-VF.ttf",
             r"C:\Windows\Fonts\malgunbd.ttf"],
    "reg": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            r"C:\Windows\Fonts\NotoSansKR-VF.ttf", r"C:\Windows\Fonts\malgun.ttf"],
}
_PRET = {"head": "ExtraBold", "bold": "Bold", "reg": "Regular"}
_VF_WEIGHT = {"head": 900, "bold": 700, "reg": 400}
_fc: dict = {}
_fp: dict = {}


def _pretendard(kind: str, cache: str) -> str | None:
    src = os.path.join(FONT_DIR, f"Pretendard-{_PRET[kind]}.woff2")
    dst = os.path.join(cache, f"Pretendard-{_PRET[kind]}.ttf")
    if os.path.exists(dst):
        return dst
    if not os.path.exists(src):
        return None
    try:
        from fontTools.ttLib import TTFont  # woff2 는 brotli 가 있어야 풀린다
        os.makedirs(cache, exist_ok=True)
        f = TTFont(src)
        f.flavor = None
        f.save(dst)
        return dst
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ Pretendard 변환 실패(대체 글꼴): {str(e)[:100]}")
        return None


def font_path(kind: str) -> str:
    if kind not in _fp:
        cache = os.environ.get("INSTA_FONT_CACHE") or os.path.join(ROOT, "output", "insta_render", ".fonts")
        p = _pretendard(kind, cache)
        if not p:
            p = next((x for x in _FALLBACK[kind] if os.path.exists(x)), None)
        if not p:
            raise RuntimeError(f"한글 글꼴 '{kind}' 없음 — fonttools+brotli 설치 또는 fonts-noto-cjk")
        _fp[kind] = p
    return _fp[kind]


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    k = (kind, size)
    if k not in _fc:
        p = font_path(kind)
        f = ImageFont.truetype(p, size)
        if p.endswith("-VF.ttf"):
            try:
                f.set_variation_by_axes([_VF_WEIGHT[kind]])
            except Exception:  # noqa: BLE001
                pass
        _fc[k] = f
    return _fc[k]


def tlen(d: ImageDraw.ImageDraw, s: str, f) -> float:
    return d.textlength(s, font=f)


def wrap(d: ImageDraw.ImageDraw, text: str, f, width: float) -> list[str]:
    """띄어쓰기 단위로 줄바꿈(한 낱말이 넘치면 글자 단위)."""
    out, cur = [], ""
    for w_ in text.split():
        t = f"{cur} {w_}".strip()
        if cur and tlen(d, t, f) > width:
            out.append(cur)
            cur = w_
        else:
            cur = t
        while tlen(d, cur, f) > width and len(cur) > 1:
            k = len(cur)
            while k > 1 and tlen(d, cur[:k], f) > width:
                k -= 1
            out.append(cur[:k])
            cur = cur[k:]
    if cur:
        out.append(cur)
    return out


def fit(d, lines: list[str], kind: str, hi: int, lo: int, width: float) -> ImageFont.FreeTypeFont:
    for size in range(hi, lo - 1, -2):
        f = font(kind, size)
        if all(tlen(d, ln, f) <= width for ln in lines):
            return f
    return font(kind, lo)


def fit_wrap(d, text: str, kind: str, hi: int, lo: int, width: float, max_lines: int):
    for size in range(hi, lo - 1, -2):
        f = font(kind, size)
        ls = wrap(d, text, f, width)
        if len(ls) <= max_lines:
            return f, ls
    f = font(kind, lo)
    return f, wrap(d, text, f, width)[:max_lines]


def h16(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


# ── 숫자 애니메이션(0 → 값, 같은 모양으로) ─────────────
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def count_up(display: str, p: float) -> str:
    m = _NUM.search(display)
    if not m or p >= 1:
        return display
    raw = m.group(0)
    val = float(raw.replace(",", ""))
    cur = val * ease(p)
    dec = len(raw.split(".")[1]) if "." in raw else 0
    s = f"{cur:,.{dec}f}" if "," in raw else f"{cur:.{dec}f}"
    return display[:m.start()] + s + display[m.end():]


def num_value(display: str) -> float:
    m = _NUM.search(display or "")
    if not m:
        return 0.0
    v = float(m.group(0).replace(",", ""))
    tail = display[m.end():m.end() + 2]
    if tail.startswith("만"):
        v *= 10000
    elif tail.startswith("억"):
        v *= 100000000
    return v


# ── ① 목소리 ──────────────────────────────────────────
def _fake_tts(text: str, out: str) -> bool:
    import numpy as np
    n = int(SR * max(0.8, I.speech_len(text) / I.CPS))
    t = np.arange(n) / SR
    wav_write(out, 0.05 * np.sin(2 * math.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * math.pi * 3 * t)))
    return True


def _edge(text: str, out_mp3: str) -> bool:
    r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", EDGE_VOICE, "--text", text,
                        "--write-media", out_mp3], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000


def synth(texts: list[str], wd: str, mock: bool = False) -> tuple[dict, str]:
    """말 → wav(무음 제거·속도 적용, 44.1k 모노). Spark 공용이라 ★한 문장씩 차례로. 같은 문장은 캐시."""
    os.makedirs(wd, exist_ok=True)
    got, used = {}, set()
    for text in dict.fromkeys(texts):
        key = h16(TTS, VOICE, text, TEMPO, mock)
        out = os.path.join(wd, f"v_{key}.wav")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            got[text] = out
            continue
        raw = out[:-4] + "_raw.wav"
        ok, how = False, "mock"
        if mock:
            ok = _fake_tts(text, raw)
        else:
            if TTS == "wbspark":
                import wbspark
                for attempt in range(3):
                    if wbspark.tts(text, raw, VOICE, timeout_sec=300):
                        ok, how = True, f"supertonic:{VOICE}"
                        break
                    time.sleep(4 + attempt * 8)
            if not ok:
                raw = out[:-4] + "_raw.mp3"
                ok, how = _edge(text, raw), f"edge:{EDGE_VOICE}"
        if not ok:
            raise RuntimeError(f"목소리 합성 실패: {text[:30]}")
        used.add(how)
        af = f"atempo={TEMPO}," if abs(TEMPO - 1) > 1e-3 and not mock else ""
        sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af",
            f"{af}silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
            f"silenceremove=start_periods=1:start_threshold=-45dB,areverse",
            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])
        os.remove(raw)
        got[text] = out
        print(f"   🎙️ {how} · {text[:28]}…", flush=True)
    return got, ",".join(sorted(used)) or "cache"


def wav_dur(p: str) -> float:
    import wave
    with wave.open(p) as w:
        return w.getnframes() / float(w.getframerate())


def retime(path: str, factor: float, wd: str) -> str:
    out = os.path.join(wd, f"t{factor:.3f}_{os.path.basename(path)}")
    if not os.path.exists(out):
        sh([ffmpeg(), "-y", "-loglevel", "error", "-i", path, "-af", f"atempo={factor:.4f}", "-ar", str(SR),
            "-ac", "1", "-sample_fmt", "s16", out])
    return out


# ── ② 그림·썸네일 ─────────────────────────────────────
def gen_image(prompt: str, out: str, mock: bool) -> bool:
    if mock:
        rnd = random.Random(prompt)
        im = Image.new("RGB", (1024, 1024), tuple(rnd.randint(40, 120) for _ in range(3)))
        d = ImageDraw.Draw(im)
        for _ in range(9):
            x, y, r = rnd.randint(0, 1024), rnd.randint(0, 1024), rnd.randint(60, 260)
            d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rnd.randint(60, 230) for _ in range(3)))
        im.save(out)
        return True
    import wbspark
    for attempt in range(2):
        spark_wait()
        if wbspark.generate_image(LOOK + prompt, out, no_llm=True, model=IMG_MODEL or None, timeout_sec=600):
            return True
        time.sleep(10 + attempt * 20)
    try:                                              # 폴백: NVIDIA 무료 FLUX
        import imagegen
        return bool(imagegen.flux_image(LOOK + prompt, out, 1024, 1024, seed=1))
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ FLUX 폴백 실패: {e}")
    return False


def fetch_thumb(vid: str, out: str, mock: bool) -> bool:
    """유튜브 공개 썸네일(i.ytimg.com). 쇼츠는 oar2(세로)가 있고, 없으면 maxres → hq."""
    if mock:
        rnd = random.Random(vid)
        im = Image.new("RGB", (1080, 1920), tuple(rnd.randint(30, 90) for _ in range(3)))
        d = ImageDraw.Draw(im)
        d.rectangle([80, 600, 1000, 1300], fill=tuple(rnd.randint(90, 200) for _ in range(3)))
        im.save(out, "JPEG")
        return True
    import requests
    for name in ("oar2.jpg", "maxresdefault.jpg", "hqdefault.jpg"):
        try:
            r = requests.get(f"https://i.ytimg.com/vi/{vid}/{name}", timeout=20)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(out, "wb") as f:
                    f.write(r.content)
                return True
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 썸네일 {vid}/{name}: {e}")
    return False


def video_id(key: str, entry: dict | None, stats: dict | None) -> str | None:
    if key in ("wb.week.top", "ntt.week.top"):
        ch = ((stats or {}).get("channels") or {}).get(key.split(".")[0]) or {}
        top = (ch.get("week") or {}).get("top") or {}
        return top.get("id")
    return I._videos(entry).get(key)


# ── ③ 실물 화면(패널) 그리기 ──────────────────────────
def rounded_mask(w: int, h: int, r: int) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    return m


def cover(im: Image.Image, w: int, h: int, centering=(0.5, 0.45)) -> Image.Image:
    return ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS, centering=centering)


def chip(d: ImageDraw.ImageDraw, xy, text: str, f, fg=INK, bg=(0, 0, 0, 170), pad=(22, 12)):
    x, y = xy
    tw = tlen(d, text, f)
    bb = f.getbbox("가")
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + bb[3] + pad[1] * 2], 16, fill=bg)
    d.text((x + pad[0], y + pad[1] - bb[1] // 2), text, font=f, fill=fg)


class Visuals:
    """scene → 패널 이미지(960×752). 시간 t(장면 안 초)와 진행 p(0→1)."""

    def __init__(self, shots: list[dict], ctx: dict, stats: dict | None):
        self.shots, self.ctx, self.stats = shots, ctx, stats
        self._img: dict = {}
        self.bg = Image.new("RGB", (PW, PH), CARD)
        d = ImageDraw.Draw(self.bg)
        for y in range(0, PH, 38):                   # 옅은 모눈
            d.line([(0, y), (PW, y)], fill=(30, 34, 46))
        for x in range(0, PW, 38):
            d.line([(x, 0), (x, PH)], fill=(30, 34, 46))

    def S(self, text: str) -> str:
        return I.resolve(text, self.ctx)

    def img(self, path: str, size) -> Image.Image:
        k = (path, size)
        if k not in self._img:
            self._img[k] = cover(Image.open(path), *size)
        return self._img[k]

    def draw(self, sh_: dict, t: float, settled: bool = False) -> Image.Image:
        show = sh_["show"]
        kind = sh_["kind"]
        p = 1.0 if settled else min(1.0, t / 0.7)
        q = min(1.0, max(0.0, t / max(0.1, sh_["dur"])))   # 장면 전체 진행
        return getattr(self, f"v_{kind}")(sh_, show, p, q, t)

    # 그림 — 아주 천천히 다가간다
    def v_img(self, sh_, show, p, q, t):
        base = self.img(sh_["asset"], (round(PW * 1.08), round(PH * 1.08)))
        z = 1 + 0.07 * ease(q)                          # 1.0 → 1.07 배로 천천히
        cw, ch = base.width / z, base.height / z
        x0, y0 = (base.width - cw) / 2, (base.height - ch) / 2
        fr = base.transform((PW, PH), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BILINEAR)
        if show.get("label"):
            d = ImageDraw.Draw(fr, "RGBA")
            chip(d, (28, PH - 96), self.S(show["label"]), font("bold", 38))
        return fr

    def v_gumi(self, sh_, show, p, q, t):
        fr = self.v_img(sh_, show, p, q, t)
        d = ImageDraw.Draw(fr, "RGBA")
        chip(d, (28, PH - 96), "Nine Tails Tales 진행자 구미 (AI)", font("bold", 34))
        return fr

    # 유튜브 썸네일 — 휴대폰 틀 + 오른쪽 설명
    def v_thumb(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        ph_h = PH - 64
        ph_w = round(ph_h * 9 / 16)
        x0, y0 = 40, 32
        d.rounded_rectangle([x0 - 8, y0 - 8, x0 + ph_w + 8, y0 + ph_h + 8], 44, fill=(6, 7, 10))
        shot = self.img(sh_["asset"], (ph_w, ph_h))
        fr.paste(shot, (x0, y0), rounded_mask(ph_w, ph_h, 36))
        rx = x0 + ph_w + 44
        rw = PW - rx - 36
        label = self.S(show.get("label", ""))
        if label:
            f, ls = fit_wrap(d, label, "bold", 54, 38, rw, 5)
            y = PH / 2 - len(ls) * f.size * 1.25 / 2 - 30
            for ln in ls:
                d.text((rx, y), ln, font=f, fill=INK)
                y += f.size * 1.25
            d.text((rx, y + 18), "유튜브 공개 썸네일", font=font("reg", 28), fill=MUTED)
        return fr

    # 큰 숫자 하나
    def v_stat(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr)
        val = count_up(self.S(show["stat"]), p)
        col = TONE.get(show.get("tone", "neutral"), ACCENT)
        f = fit(d, [self.S(show["stat"])], "head", 230, 90, PW - 100)
        bb = d.textbbox((0, 0), val, font=f)
        y = PH * 0.40 - (bb[3] - bb[1]) / 2 - bb[1]
        d.text(((PW - tlen(d, val, f)) / 2, y), val, font=f, fill=col)
        if show.get("label"):
            fl, ls = fit_wrap(d, self.S(show["label"]), "bold", 58, 40, PW - 120, 2)
            yy = PH * 0.40 + (bb[3] - bb[1]) / 2 + 60
            for ln in ls:
                d.text(((PW - tlen(d, ln, fl)) / 2, yy), ln, font=fl, fill=INK)
                yy += fl.size * 1.3
        return fr

    # 전·후 두 칸
    def v_vs(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        items = show["vs"]
        vals = [self.S(it["value"]) for it in items]
        mx = max(num_value(v) for v in vals) or 1
        cw_, gap = (PW - 3 * 36) / 2, 36
        fv = fit(d, vals, "head", 150, 64, cw_ - 96)
        for k, it in enumerate(items):
            x0 = 36 + k * (cw_ + gap)
            col = TONE.get(it.get("tone", "good" if k == 1 else "bad"), ACCENT)
            d.rounded_rectangle([x0, 40, x0 + cw_, PH - 40], 30, fill=(18, 21, 29), outline=LINE, width=2)
            fl, ls = fit_wrap(d, self.S(it["label"]), "bold", 44, 32, cw_ - 50, 2)
            y = 86
            for ln in ls:
                d.text((x0 + (cw_ - tlen(d, ln, fl)) / 2, y), ln, font=fl, fill=MUTED)
                y += fl.size * 1.3
            v = count_up(vals[k], p)
            d.text((x0 + (cw_ - tlen(d, v, fv)) / 2, PH * 0.44 - fv.size / 2), v, font=fv, fill=col)
            # 아래 막대 — 값 비율
            bh = (PH * 0.30) * (num_value(vals[k]) / mx) * ease(p)
            bx0, bx1 = x0 + cw_ * 0.3, x0 + cw_ * 0.7
            d.rounded_rectangle([bx0, PH - 80 - max(8, bh), bx1, PH - 80], 12, fill=col + (230,))
        # 가운데 vs
        cx, cy = PW / 2, PH * 0.44
        d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=(13, 15, 21), outline=LINE, width=3)
        fvs = font("head", 34)
        d.text((cx - tlen(d, "vs", fvs) / 2, cy - 24), "vs", font=fvs, fill=INK)
        return fr

    # 막대 2~6개
    def v_bars(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr)
        items = show["bars"]
        vals = [self.S(it["value"]) for it in items]
        nums = [num_value(v) for v in vals]
        mx = max(nums) or 1
        hi = int(show.get("hi", nums.index(max(nums))))
        n = len(items)
        row = (PH - 80) / n
        fl, fvv = font("bold", 42 if n <= 3 else 36), font("head", 50 if n <= 3 else 42)
        for k, it in enumerate(items):
            y = 40 + k * row + (row - (fl.size + 20 + 64)) / 2
            col = ACCENT if k == hi else (110, 120, 142)
            d.text((50, y), self.S(it["label"]), font=fl, fill=INK if k == hi else MUTED)
            by = y + fl.size + 20
            full = PW - 100 - 250
            ln = max(14, full * nums[k] / mx * ease(min(1.0, p * 1.5 - k * 0.08)))
            d.rounded_rectangle([50, by, 50 + ln, by + 56], 14, fill=col)
            d.text((50 + ln + 22, by + 28 - fvv.size * 0.62), count_up(vals[k], p), font=fvv, fill=col)
        return fr

    # 번호 목록
    def v_steps(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        steps = [self.S(s) for s in show["steps"]]
        hi = int(show.get("hi", -1))
        n = len(steps)
        row = min(150, (PH - 80) / n)
        top = (PH - row * n) / 2
        f = fit(d, steps, "bold", 54, 36, PW - 220)
        fn = font("head", 44)
        for k, s in enumerate(steps):
            a = ease(p * 1.6 - k * 0.18)
            y = top + k * row + (1 - a) * 30
            on = hi == -1 or k == hi
            if k == hi:
                d.rounded_rectangle([28, y + 8, PW - 28, y + row - 8], 26, fill=(255, 212, 71, 36),
                                    outline=ACCENT, width=3)
            cx, cy = 96, y + row / 2
            d.ellipse([cx - 36, cy - 36, cx + 36, cy + 36], fill=ACCENT if on else (60, 66, 82))
            if hi == -1:                               # 전부 완료 = 체크 표시
                d.line([(cx - 16, cy + 1), (cx - 4, cy + 14), (cx + 18, cy - 12)], fill=(20, 20, 24), width=8)
            else:
                num = str(k + 1)
                d.text((cx - tlen(d, num, fn) / 2, cy - fn.size * 0.62), num, font=fn, fill=(20, 20, 24))
            d.text((160, cy - f.size * 0.62), s, font=f, fill=(INK if on else DIM) + (int(255 * max(0.0, a)),))
        return fr

    # 흐름도 — 위에서 아래로, 불이 차례로 켜진다
    def v_flow(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        nodes = [self.S(s) for s in show["flow"]]
        n = len(nodes)
        gap = 44
        bh = min(118, (PH - 60 - gap * (n - 1)) / n)
        top = (PH - (bh * n + gap * (n - 1))) / 2
        f = fit(d, nodes, "bold", 50, 32, PW - 320)
        active = min(n - 1, int(q * n * 1.05))
        for k, s in enumerate(nodes):
            y = top + k * (bh + gap)
            on = k <= active
            d.rounded_rectangle([140, y, PW - 140, y + bh], 24, fill=(255, 212, 71, 40) if k == active else (18, 21, 29),
                                outline=ACCENT if on else LINE, width=4 if k == active else 2)
            d.text(((PW - tlen(d, s, f)) / 2, y + bh / 2 - f.size * 0.62), s, font=f, fill=INK if on else DIM)
            if k < n - 1:
                ax, ay = PW / 2, y + bh + 6
                col = ACCENT if k < active else LINE
                d.line([(ax, ay), (ax, ay + gap - 14)], fill=col, width=5)
                d.polygon([(ax - 13, ay + gap - 18), (ax + 13, ay + gap - 18), (ax, ay + gap - 4)], fill=col)
        return fr

    # 말풍선 — 차례로 뜬다
    def v_chat(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        items = show["chat"]
        n = len(items)
        f = font("bold", 54)
        fs = font("bold", 30)
        heights = [len(wrap(d, self.S(it["text"]), f, PW * 0.64)) * f.size * 1.3 + 50 for it in items]
        y = max(40, (PH - sum(heights) - 40 * (n - 1)) / 2)
        for k, it in enumerate(items):
            appear = 0.0 if k == 0 else (k / (n + 0.3)) * sh_["dur"]
            a = 1.0 if appear == 0 else min(1.0, max(0.0, (t - appear) / 0.3))
            if a <= 0:
                continue
            text = self.S(it["text"])
            ls = wrap(d, text, f, PW * 0.64)
            bw = max(tlen(d, ln, f) for ln in ls) + 72
            bh = len(ls) * f.size * 1.3 + 50
            me = it["who"] == "me"
            x0 = PW - 40 - bw if me else 132
            al = int(255 * a)
            if not me:
                d.ellipse([34, y + 6, 110, y + 82], fill=(80, 88, 110, al))
                d.text((72 - tlen(d, "AI", fs) / 2, y + 26), "AI", font=fs, fill=(INK[0], INK[1], INK[2], al))
            fill = (ACCENT[0], ACCENT[1], ACCENT[2], al) if me else (52, 58, 76, al)
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], 30, fill=fill)
            tc = (20, 20, 24, al) if me else (INK[0], INK[1], INK[2], al)
            yy = y + 24
            for ln in ls:
                d.text((x0 + 36, yy), ln, font=f, fill=tc)
                yy += f.size * 1.3
            y += bh + 40
        return fr

    # 큰 문장
    def v_text(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr)
        f, ls = fit_wrap(d, self.S(show["text"]), "head", 120, 60, PW - 120, 3)
        tot = len(ls) * f.size * 1.2
        y = PH * 0.45 - tot / 2
        for ln in ls:
            d.text(((PW - tlen(d, ln, f)) / 2, y), ln, font=f, fill=ACCENT)
            y += f.size * 1.2
        if show.get("sub"):
            fs, ss = fit_wrap(d, self.S(show["sub"]), "bold", 46, 32, PW - 140, 2)
            y += 40
            for ln in ss:
                d.text(((PW - tlen(d, ln, fs)) / 2, y), ln, font=fs, fill=MUTED)
                y += fs.size * 1.3
        return fr

    def _week_one(self, c: str, fr, d, p):
        """한 채널: 왼쪽 숫자 세 줄, 오른쪽 가장 많이 본 영상."""
        name = self.ctx[f"{c}.name"][0]
        d.rounded_rectangle([36, 36, PW - 36, PH - 36], 28, fill=(18, 21, 29), outline=LINE, width=2)
        fn = fit(d, [name], "head", 56, 32, PW - 120)
        d.text((72, 70), name, font=fn, fill=ACCENT)
        fl = font("bold", 36)
        y = 70 + fn.size + 44
        for lab, key in (("올린 영상", "week.uploads"), ("이번 주 조회", "week.views"), ("구독자", "subs")):
            d.text((72, y), lab, font=fl, fill=MUTED)
            fv = fit(d, [self.ctx[f"{c}.{key}"][0]], "head", 84, 40, PW / 2 - 110)
            d.text((72, y + 46), count_up(self.ctx[f"{c}.{key}"][0], p), font=fv, fill=INK)
            y += 46 + 84 + 36
        x2 = PW / 2 + 20
        d.line([(x2 - 30, 70 + fn.size + 44), (x2 - 30, PH - 90)], fill=LINE, width=2)
        d.text((x2, 70 + fn.size + 44), "가장 많이 본 영상", font=fl, fill=MUTED)
        top = self.ctx.get(f"{c}.week.top_title", ("", ""))[0]
        ft, ls = fit_wrap(d, top, "bold", 46, 30, PW - x2 - 70, 4)
        yy = 70 + fn.size + 44 + 60
        for ln in ls:
            d.text((x2, yy), ln, font=ft, fill=INK)
            yy += ft.size * 1.3
        fg = fit(d, [self.ctx[f"{c}.week.top_views"][0]], "head", 72, 40, PW - x2 - 70)
        d.text((x2, yy + 24), count_up(self.ctx[f"{c}.week.top_views"][0], p), font=fg, fill=GOOD)
        return fr

    # 주간 성적표 — 숫자는 전부 stats
    def v_week(self, sh_, show, p, q, t):
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        which = ["wb", "ntt"] if show["week"] == "both" else [show["week"]]
        if len(which) == 1:
            return self._week_one(which[0], fr, d, p)
        rows = [("올린 영상", "week.uploads"), ("이번 주 조회", "week.views"), ("구독자", "subs")]
        colw = (PW - 36 * (len(which) + 1)) / len(which)
        fh, fl, fv = font("head", 40), font("bold", 30), font("head", 54 if len(which) == 2 else 68)
        for k, c in enumerate(which):
            x0 = 36 + k * (colw + 36)
            d.rounded_rectangle([x0, 36, x0 + colw, PH - 36], 28, fill=(18, 21, 29), outline=LINE, width=2)
            name = self.ctx[f"{c}.name"][0]
            fn = fit(d, [name], "head", 44, 28, colw - 40)
            d.text((x0 + (colw - tlen(d, name, fn)) / 2, 66), name, font=fn, fill=ACCENT)
            y = 132
            for lab, key in rows:
                d.text((x0 + 34, y), lab, font=fl, fill=MUTED)
                v = count_up(self.ctx[f"{c}.{key}"][0], p)
                fvv = fit(d, [self.ctx[f"{c}.{key}"][0]], "head", fv.size, 34, colw - 68)
                d.text((x0 + 34, y + 38), v, font=fvv, fill=INK)
                y += 38 + fv.size + 26
            top = self.ctx.get(f"{c}.week.top_title", ("", ""))[0]
            if top:
                d.text((x0 + 34, y), "가장 많이 본 영상", font=fl, fill=MUTED)
                ft, ls = fit_wrap(d, top, "bold", 32, 24, colw - 68, 2)
                yy = y + 42
                for ln in ls:
                    d.text((x0 + 34, yy), ln, font=ft, fill=INK)
                    yy += ft.size * 1.3
                d.text((x0 + 34, yy + 4), self.ctx[f"{c}.week.top_views"][0], font=fh, fill=GOOD)
        return fr


# ── ④ 한 프레임 ───────────────────────────────────────
def background() -> Image.Image:
    g = Image.linear_gradient("L").resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), BG_BOT), Image.new("RGB", (W, H), BG_TOP), g)
    glow = Image.radial_gradient("L").resize((W, W)).point(lambda v: int(max(0, 150 - v) * 0.35))
    bg.paste(Image.new("RGB", (W, W), (60, 52, 20)), (0, -W // 2 + 360), glow)
    return bg


def _split(sent: str, limit: int) -> list[str]:
    """한 문장을 limit 안쪽 조각으로 — 가운데에 가까운 쉼표를 먼저, 없으면 띄어쓰기에서."""
    if len(sent) <= limit:
        return [sent]
    n = len(sent)
    commas = [m.end() for m in re.finditer(r",\s", sent) if 0.3 * n <= m.end() <= 0.7 * n]
    cuts = commas or [m.start() for m in re.finditer(r"\s", sent)]
    if not cuts:
        return [sent]
    c = min(cuts, key=lambda k: abs(k - n / 2))
    return _split(sent[:c].strip(), limit) + _split(sent[c:].strip(), limit)


def caption_chunks(text: str, limit: int = 32) -> list[str]:
    """자막 조각(한 조각 = 두 줄 이내). 문장 끝에서 끊고, 길 때만 나눈다 — ★'In Korea,' 처럼 뜻 없는 앞머리 조각을 만들지 않게."""
    out = []
    for sent in [x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x]:
        out += _split(sent, limit)
    return out


class Painter:
    def __init__(self, P: dict, s: dict, ctx: dict, stats: dict | None, host: str = "none"):
        self.P, self.s, self.ctx = P, s, ctx
        self.shots = P["shots"]
        self.total = P["total"]
        self.host = host
        self.vis = Visuals(self.shots, ctx, stats)
        self.mask = rounded_mask(PW, PH, 30)
        self.base = self._base()
        self._cap: dict = {}
        self._settled: dict = {}
        self.env = P.get("env") or []
        if host == "gumi":
            g = Image.open(os.path.join(ASSETS, "gumi_front.jpg")).convert("RGB")
            gw = g.width
            g = g.crop((gw * 0.335, 0.03 * g.height, gw * 0.665, 0.03 * g.height + gw * 0.33))
            size = HOST_BOX[2] - HOST_BOX[0]
            self.face = g.resize((size, size), Image.LANCZOS)
            self.face_mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(self.face_mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        for k, x in enumerate(self.shots):
            x["chunks"] = caption_chunks(x["show_say"], 42 if k == 0 else 32)   # 첫 장면은 훅 한 문장을 통째로(첫 프레임에 뜻이 보이게)
            tot = sum(I.speech_len(c) for c in x["chunks"]) or 1
            acc, x["cuts"] = 0.0, []
            for c in x["chunks"]:
                acc += x["vdur"] * I.speech_len(c) / tot
                x["cuts"].append(acc)

    def _base(self) -> Image.Image:
        img = background()
        d = ImageDraw.Draw(img)
        lines = [I.resolve(h, self.ctx) for h in self.s["headline"]]
        f = fit(d, lines, "head", 112 if len(lines) == 2 else 124, 70, HEAD[2] - HEAD[0])
        lh = f.size * 1.18
        y = HEAD[1] + ((HEAD[3] - HEAD[1]) - lh * len(lines)) / 2
        for k, ln in enumerate(lines):
            col = INK if (k == 0 and len(lines) == 2) else ACCENT
            d.text((HEAD[0], y), ln, font=f, fill=col, stroke_width=2, stroke_fill=(0, 0, 0))
            y += lh
        ft = font("bold", 30)
        left = "AI 유튜브 운영 · 실제 기록"
        entry = I.topic_entry(self.s["topic"]) if self.s["format"] == "guide" else None
        right = f"가이드 {entry['id']:02d}" if entry else "주간 성적표"
        d.text((HEAD[0], TAG_Y), left, font=ft, fill=MUTED)
        d.text((HEAD[2] - tlen(d, right, ft), TAG_Y), right, font=ft, fill=MUTED)
        d.rectangle(PROG, fill=(38, 42, 54))
        return img

    def panel(self, k: int, t: float) -> Image.Image:
        x = self.shots[k]
        lt = t - x["start"]
        first = k == 0                                   # ★첫 장면은 처음부터 다 보인다(첫 프레임 = 커버)
        animated = x["kind"] in ("img", "gumi", "flow", "chat")
        if not animated and (first or lt >= 0.7 * 1.6 + 0.4):
            if k not in self._settled:
                self._settled[k] = self.vis.draw(x, max(lt, x["dur"]), settled=True)
            return self._settled[k]
        return self.vis.draw(x, max(0.0, lt), settled=first and x["kind"] != "chat")

    def caption(self, k: int, t: float) -> Image.Image | None:
        x = self.shots[k]
        lt = t - x["start"] - LEAD
        if lt > x["vdur"] + 0.25:
            return None
        j = next((i for i, c in enumerate(x["cuts"]) if max(0.0, lt) < c), len(x["cuts"]) - 1)
        key = (k, j)
        if key not in self._cap:
            text = x["chunks"][j]
            im = Image.new("RGBA", (CAP[2] - CAP[0], CAP[3] - CAP[1]), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            f, ls = fit_wrap(d, text, "bold", 62, 46, im.width - 60, 2)
            y = (im.height - len(ls) * f.size * 1.22) / 2
            for ln in ls:
                words = ln.split(" ")
                x0 = (im.width - tlen(d, ln, f)) / 2
                for w_ in words:
                    col = ACCENT if re.search(r"\d", w_) else INK
                    d.text((x0, y), w_, font=f, fill=col, stroke_width=6, stroke_fill=(0, 0, 0))
                    x0 += tlen(d, w_ + " ", f)
                y += f.size * 1.22
            self._cap[key] = im
        return self._cap[key]

    def frame(self, t: float) -> Image.Image:
        fr = self.base.copy()
        d = ImageDraw.Draw(fr)
        d.rectangle([PROG[0], PROG[1], PROG[0] + (PROG[2] - PROG[0]) * min(1.0, t / self.total), PROG[3]], fill=ACCENT)
        k = max(0, next((i for i, x in enumerate(self.shots) if x["start"] > t), len(self.shots)) - 1)
        pan = self.panel(k, t)
        lt = t - self.shots[k]["start"]
        if k > 0 and lt < XF:
            prev = self.panel(k - 1, t)
            pan = Image.blend(prev, pan, ease(lt / XF))
        fr.paste(pan, (PANEL[0], PANEL[1]), self.mask)
        cap = self.caption(k, t)
        if cap is not None:
            fr.paste(cap, (CAP[0], CAP[1]), cap)
        if self.host == "gumi":
            e = self.env[min(len(self.env) - 1, int(t * FPS))] if self.env else 0.0
            x0, y0, x1, y1 = HOST_BOX
            ring = int(6 + 8 * e)
            d.ellipse([x0 - ring, y0 - ring, x1 + ring, y1 + ring], fill=(ACCENT if e > 0.05 else (70, 76, 92)))
            bob = int(3 * math.sin(t * 7) * e)
            fr.paste(self.face, (x0, y0 - bob), self.face_mask)
            d.text((x1 + 30, y0 + 58), "구미", font=font("head", 46), fill=INK)
            d.text((x1 + 30, y0 + 118), "AI 진행자", font=font("bold", 30), fill=MUTED)
        return fr


# ── ⑤ 소리 ────────────────────────────────────────────
def bed(n: int, seed: int = 3):
    """잔잔한 배경음(코드로 만든다 — 저작권 걱정 없음): Cmaj7–Am7–Fmaj7–G6 패드 + 부드러운 킥·하이햇, 84 BPM."""
    import numpy as np
    rng = np.random.default_rng(seed)
    bpm, beat = 84, 60 / 84
    chords = [(130.81, 261.63, 329.63, 392.00, 493.88), (110.00, 220.00, 261.63, 329.63, 392.00),
              (87.31, 174.61, 220.00, 261.63, 329.63), (98.00, 196.00, 246.94, 293.66, 329.63)]
    seg = int(SR * beat * 8)
    y = np.zeros(n, dtype="float32")
    t_all = np.arange(seg) / SR
    env = np.minimum(1, t_all / 0.9) * np.minimum(1, (seg / SR - t_all) / 0.9)
    k = 0
    for a in range(0, n, seg):
        ch = chords[k % len(chords)]
        m = min(seg, n - a)
        t = t_all[:m]
        s = np.zeros(m)
        for j, f in enumerate(ch):
            amp = 0.5 if j == 0 else 0.22
            det = 1 + (j % 2) * 0.0025
            s += amp * (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * det * 2 * t)) \
                * (0.8 + 0.2 * np.sin(2 * np.pi * 0.25 * t + j))
        y[a:a + m] += (s * env[:m]).astype("float32")
        k += 1
    y /= np.abs(y).max() + 1e-9
    # 킥(1·3박)·하이햇(엇박)
    kick_n = int(SR * 0.28)
    tk = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * np.cumsum(46 + 60 * np.exp(-tk * 18)) / SR) * np.exp(-tk * 11)
    hat_n = int(SR * 0.05)
    hat = rng.standard_normal(hat_n) * np.exp(-np.arange(hat_n) / SR * 90)
    hat = np.diff(np.concatenate([[0.0], hat]))                    # 간단한 고역 통과
    b = 0
    while True:
        a = int(b * beat * SR)
        if a >= n:
            break
        if b % 2 == 0:
            y[a:a + kick_n] += (0.55 * kick[: max(0, n - a)]).astype("float32")
        h = int((b + 0.5) * beat * SR)
        if h < n:
            y[h:h + hat_n] += (0.12 * hat[: max(0, n - h)]).astype("float32")
        b += 1
    return y / (np.abs(y).max() + 1e-9)


def tick(rng):
    import numpy as np
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1320 * t) * np.exp(-t * 60) * 0.5 + rng.standard_normal(n) * np.exp(-t * 120) * 0.1
            ).astype("float32")


def build_audio(shots: list[dict], total: float, out_m4a: str, wd: str) -> list[float]:
    """섞고 -14 LUFS. 진행자 테두리용 프레임별 말소리 크기(0~1)를 돌려준다."""
    import numpy as np
    n = int(total * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for x in shots:
        v = wav_read(x["wav"])
        a = int((x["start"] + LEAD) * SR)
        voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = bed(n)
    b *= vr * 0.16 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)          # 말 사이 약 -16dB
    win = int(SR * 0.2)
    envv = movavg(np.abs(voice), win)
    duck = movavg(1 - 0.5 * np.clip(envv / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
    sfx = np.zeros(n, dtype="float32")
    rng = np.random.default_rng(7)
    for x in shots[1:]:
        tk = tick(rng) * vr * 0.9
        a = int(x["start"] * SR)
        sfx[a:a + len(tk)] += tk[: max(0, n - a)]
    mix = voice + b * duck + sfx
    fo = int(SR * 0.6)
    mix = mix[: int(total * SR)]
    mix[-fo:] *= np.linspace(1, 0, fo, dtype="float32")
    mix[: int(SR * 0.05)] *= np.linspace(0, 1, int(SR * 0.05), dtype="float32")
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    wav_write(raw, mix)
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", out_m4a])
    # 프레임별 말소리 크기
    step = SR // FPS
    env = [float(min(1.0, np.sqrt(np.mean(voice[i:i + step] ** 2)) / (vr * 1.4 + 1e-9)))
           for i in range(0, int(total * SR), step)]
    return env


# ── 전체 ──────────────────────────────────────────────
def plan(s: dict, ctx: dict) -> list[dict]:
    shots = []
    for i, x in enumerate(s["scenes"]):
        show = x["show"]
        kind = next(k for k in I.VISUALS if k in show)
        shots.append({"i": i, "kind": kind, "show": show, "say": I.resolve(x["say"], ctx, "say"),
                      "show_say": I.resolve(x["say"], ctx), "hold": float(x.get("hold", 0))})
    return shots


def timeline(shots: list[dict]) -> float:
    t = 0.0
    for x in shots:
        x["start"] = round(t, 3)
        x["dur"] = round(LEAD + x["vdur"] + GAP + x["hold"], 3)
        t += x["dur"]
    shots[-1]["dur"] = round(shots[-1]["dur"] + TAIL, 3)
    total = t + TAIL
    if total < MIN_SEC:                              # 짧으면 마지막 화면(저장 목록)을 더 오래 보여 준다
        shots[-1]["dur"] = round(shots[-1]["dur"] + MIN_SEC - total, 3)
        total = MIN_SEC
    return round(total, 3)


def prepare_assets(s: dict, shots: list[dict], entry: dict | None, stats: dict | None, wd: str, mock: bool) -> dict:
    os.makedirs(wd, exist_ok=True)
    n_img = 0
    for x in shots:
        show = x["show"]
        if x["kind"] == "img":
            out = os.path.join(wd, f"img_{h16(LOOK, show['img'], mock)}.png")
            if not (os.path.exists(out) and os.path.getsize(out) > 5000):
                if not gen_image(show["img"], out, mock):
                    raise RuntimeError(f"그림 실패: {show['img'][:60]}")
                n_img += 1
            x["asset"] = out
        elif x["kind"] == "gumi":
            x["asset"] = os.path.join(ASSETS, f"gumi_{show['gumi']}.jpg")
        elif x["kind"] == "thumb":
            vid = video_id(show["thumb"], entry, stats)
            if not vid:
                raise RuntimeError(f"썸네일 영상을 찾을 수 없다: {show['thumb']} (stats 의 이번 주 영상이 없나?)")
            out = os.path.join(wd, f"thumb_{vid}{'_mock' if mock else ''}.jpg")
            if not os.path.exists(out) and not fetch_thumb(vid, out, mock):
                raise RuntimeError(f"썸네일 받기 실패: {vid}")
            x["asset"] = out
    return {"spark_images": n_img}


def encode(pa: Painter, total: float, out: str):
    proc = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "19", "-pix_fmt", "yuv420p", "-g", str(FPS * 2), out], stdin=subprocess.PIPE)
    for n in range(int(math.ceil(total * FPS))):
        proc.stdin.write(pa.frame(n / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg 인코딩 실패")


def contact_sheet(pa: Painter, out: str, n: int = 6):
    """사람 확인용 — 첫 프레임 + 장면 가운데 5장(3×2)."""
    shots = pa.shots
    L = len(shots)
    idx = sorted({round(1 + i * (L - 2) / max(1, n - 2)) for i in range(n - 1)}) if L > 1 else []
    picks = [0.0] + [shots[k]["start"] + shots[k]["dur"] * 0.6 for k in idx][: n - 1]
    tw, th = 360, 640
    sheet = Image.new("RGB", (tw * 3, th * math.ceil(len(picks) / 3)), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for k, t in enumerate(picks):
        sheet.paste(pa.frame(t).resize((tw, th), Image.LANCZOS), ((k % 3) * tw, (k // 3) * th))
        d.text(((k % 3) * tw + 10, (k // 3) * th + 8), f"{t:.1f}s", fill=(255, 255, 0), font=font("bold", 26))
    sheet.save(out, "JPEG", quality=85)


def render(path: str, out_dir: str, work: str, stats_path: str | None = None, mock: bool = False,
           host: str | None = None) -> dict:
    s = I.load(path)
    errs = I.check(s, path)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    host = (host or HOST or "none").lower()
    if host not in ("none", "gumi"):
        raise SystemExit(f"INSTA_HOST 는 none|gumi ({host!r})")
    stats = I.load(stats_path) if stats_path and os.path.exists(stats_path) else None
    if mock and stats is None:
        import stats as ST
        stats = ST.mock(I._date(s["date"]))
    entry = I.topic_entry(s["topic"]) if s["format"] == "guide" else None
    ctx = I.context(entry, stats, s["date"])
    stem = f"{s['date']}_{s['topic']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    try:                                              # 자리표시자를 못 채우면 여기서 멈춘다(목소리·그림 전)
        shots = plan(s, ctx)
        caption = I.final_caption(s, ctx)
        [I.resolve(h, ctx) for h in s["headline"]]
    except I.Missing as e:
        raise SystemExit(f"❌ {e}")
    voices, voice_used = synth([x["say"] for x in shots], os.path.join(wd, "tts"), mock)
    for x in shots:
        x["wav"] = voices[x["say"]]
        x["vdur"] = wav_dur(x["wav"])
    total = timeline(shots)
    if total > MAX_SEC:                               # 조금 빠르게 읽혀 45초 안으로(최대 1.12배)
        fixed = total - sum(x["vdur"] for x in shots)
        factor = min(1.12, sum(x["vdur"] for x in shots) / max(1.0, MAX_SEC - fixed))
        print(f"   ⏩ {total:.1f}초 > {MAX_SEC} — 말 {factor:.2f}배")
        for x in shots:
            x["wav"] = retime(x["wav"], factor, os.path.join(wd, "tts"))
            x["vdur"] = wav_dur(x["wav"])
        total = timeline(shots)
    if total > HARD_MAX:
        raise SystemExit(f"릴스 {total:.1f}초 > {HARD_MAX} — 대본을 줄일 것(insta.py SAY_CHARS)")
    info = prepare_assets(s, shots, entry, stats, os.path.join(wd, "img"), mock)
    audio = os.path.join(wd, "audio.m4a")
    env = build_audio(shots, total, audio, wd)
    P = {"shots": shots, "total": total, "env": env}
    pa = Painter(P, s, ctx, stats, host)
    base = os.path.join(out_dir, stem)
    pa.frame(0.0).save(base + "_cover.jpg", "JPEG", quality=92)
    contact_sheet(pa, base + "_sheet.jpg")
    silent = os.path.join(wd, "silent.mp4")
    encode(pa, total, silent)
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", audio, "-c:v", "copy", "-c:a", "copy",
        "-shortest", "-movflags", "+faststart", base + ".mp4"])
    speech = sum(x["vdur"] for x in shots)
    chars = sum(I.speech_len(x["show_say"]) for x in shots)
    res = {"stem": stem, "date": s["date"], "format": s["format"], "topic": s["topic"], "video": base + ".mp4",
           "cover": base + "_cover.jpg", "sheet": base + "_sheet.jpg", "sec": round(total, 2), "mock": mock,
           "stats_mock": bool((stats or {}).get("mock")), "stats_at": (stats or {}).get("generated_at"),
           "host": host, "voice": voice_used, "spark_images": info["spark_images"],
           "speech_sec": round(speech, 2), "speech_chars": chars, "cps": round(chars / max(0.1, speech), 2),
           "caption": caption, "threads": I.threads_text(s, ctx),
           "scenes": [{"start": x["start"], "dur": x["dur"], "kind": x["kind"]} for x in shots]}
    with open(base + "_meta.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"✅ {base}.mp4 · {total:.1f}초 · 말 {speech:.1f}초({res['cps']}자/초) · 장면 {len(shots)}"
          f" · 진행자 {host} · 목소리 {voice_used} · 그림 {info['spark_images']} · {time.time() - t0:.0f}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 릴스 렌더")
    ap.add_argument("script")
    ap.add_argument("--stats", default=os.path.join(ROOT, "output", "insta_render", "stats.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "insta_render"))
    ap.add_argument("--work", default=os.path.join(ROOT, "output", "insta_render", ".work"))
    ap.add_argument("--mock", action="store_true", help="Spark·네트워크 없이 — 테스트(게시 불가)")
    ap.add_argument("--host", choices=["none", "gumi"], help="기본: 환경변수 INSTA_HOST(none)")
    a = ap.parse_args()
    render(a.script, a.out, a.work, a.stats, a.mock, a.host)
    return 0


if __name__ == "__main__":
    sys.exit(main())
