#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주간 띠별 운세 롱폼 렌더 (2026-10-01) — 화면(PIL) · 목소리(Supertonic, 한 건씩) · ffmpeg.

  ① 조각(섹션 하나 = 한 조각)을 Supertonic 한 목소리(WEEKLY_VOICE, 기본 F2)로 ★한 건씩 합성
     (Spark 는 여럿이 같이 쓰는 서버다 — 대기열이 길면 기다린다). 앞뒤 무음은 잘라 쉼을 코드가 정한다.
  ② 조각 사이 0.45초 · 장이 바뀔 때 1.2초 → 한 줄 오디오 → 0.92배(어르신 청취) · 음량 정규화
  ③ 화면(1920×1080, 큰 글자): 제목 · 12띠 순위표 · 장 제목 카드(띠 그림) · 섹션(금전·건강·사람/가족·행운·조심)
     · 마무리(매일 아침 8초 표 안내). 모든 화면 아래에 '재미로 보는 운세예요'.
  ④ 정지 화면 + 오디오 → mp4(-tune stillimage, 10fps) · 목차(유튜브 챕터) · 썸네일(1280×720)

띠 그림: pipeline/assets/zodiac/NN_<영어>.jpg (12장, 2026-10-01 Spark z-image-turbo · no_llm 로 한 번 만들어 커밋 —
  아래 ZODIAC_PROMPT). 파일이 없으면 같은 프롬프트로 Spark 에서 한 번 만들어 작업 폴더에 두고, 그것도 안 되면
  이름을 쓴 원으로 대신한다(렌더를 멈추지 않는다).

실측(2026-10-01, F2): 조각 앞뒤에 무음이 ~0.5초씩 붙어 나온다(잘라 낸다). 말만 재면 줄글 분당 469자 ·
  출생연도 목록 줄 422자 · 짧은 줄 ~560자. 한 건 처리 13~21초(서버 기준 소리 1초에 ~0.75초).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import math
import os
import shutil
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import weekly_fortune as WF  # noqa: E402

W, H = 1920, 1080
TW, TH = 1280, 720
FPS = int(os.environ.get("WEEKLY_FPS", "10"))
SR = 44100
WORKERS = int(os.environ.get("WEEKLY_TTS_WORKERS", "1"))     # ★1 = 한 건씩(공용 Spark)
SPARK_MAX_WAITING = int(os.environ.get("WEEKLY_SPARK_MAX_WAITING", "6"))
MAX_FALLBACK = 0.05          # Supertonic 실패 조각이 이 비율을 넘으면 목소리가 섞이므로 중단
EDGE_VOICE = "ko-KR-SunHiNeural"
RETRY_WAIT = float(os.environ.get("WEEKLY_TTS_RETRY_WAIT", "4"))   # 실패한 조각 다시 시도 전 쉼(초) × 1·3·5
ASSETS = os.path.join(HERE, "assets", "zodiac")
EN = ["rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "sheep", "monkey", "rooster", "dog", "pig"]
_DESC = {"dragon": "friendly little East Asian dragon with a long body, small horns and whiskers",
         "snake": "cute friendly little snake coiled up, smiling", "ox": "cute little ox calf with small horns",
         "sheep": "cute fluffy little sheep", "rooster": "cute little rooster with a red comb",
         "rat": "cute little mouse"}
ZODIAC_PROMPT = ("adorable 3D chibi zodiac mascot character, {desc}, wearing a tiny traditional Korean hanbok vest, "
                 "big expressive friendly eyes, gentle smile, soft pastel colors, warm glowing lucky atmosphere, "
                 "playful Pixar-like render, centered, full body, plain deep midnight blue background "
                 "with a soft golden glow behind the character")
IMG_MODEL = os.environ.get("WEEKLY_IMG_MODEL", "z-image-turbo")

# ── 색 ────────────────────────────────────────────────────────
BG_TOP, BG_BOT = (26, 30, 62), (9, 9, 20)
PANEL = (32, 38, 76)
GOLD = (240, 200, 90)
BEIGE = (237, 217, 188)
WHITE = (255, 255, 255)
DIM = (172, 170, 196)
NAVY = (18, 20, 44)
SEC_COLOR = {"money": GOLD, "health": (126, 211, 150), "people": (244, 160, 190),
             "caution": (255, 140, 105), "lucky": (186, 168, 255)}


def _bin(name: str) -> str:
    return os.environ.get(name.upper()) or shutil.which(name) or name


FFMPEG = _bin("ffmpeg")


def sh(cmd: list):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


# ── 글꼴 · 글 맞추기 ───────────────────────────────────────────
_fonts: dict = {}


def font(size: int):
    if size not in _fonts:
        import thumbnail as TH_
        _fonts[size] = TH_._load_font(size)
    return _fonts[size]


def wrap(draw, text: str, f, max_w: int) -> list[str]:
    import thumbnail as TH_
    out = []
    for para in str(text or "").split("\n"):
        out += TH_._wrap_words(draw, para, f, max_w, 99) or [""]
    return out


def fit(draw, text: str, max_w: int, max_h: int, hi: int, lo: int, gap: float = 1.32):
    """max_w×max_h 안에 들어가는 가장 큰 글자(어절 단위 줄바꿈). (크기, 줄들, 줄높이)."""
    size = hi
    while True:
        f = font(size)
        lines = wrap(draw, text, f, max_w)
        lh = int(size * gap)
        if (len(lines) * lh <= max_h and all(draw.textlength(x, font=f) <= max_w for x in lines)) or size <= lo:
            return size, lines, lh
        size -= 2


def text_c(draw, cx: float, y: float, s: str, f, fill, stroke: int = 0, stroke_fill=(0, 0, 0)):
    w = draw.textlength(s, font=f)
    draw.text((cx - w / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


# ── 배경 · 공통 ───────────────────────────────────────────────
_bg_cache: dict = {}


def background(size=(W, H), glow: tuple | None = None):
    from PIL import Image, ImageDraw, ImageFilter
    key = (size, glow)
    if key not in _bg_cache:
        w, h = size
        img = Image.new("RGB", size, BG_BOT)
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            d.line([(0, y), (w, y)], fill=tuple(int(BG_TOP[k] * (1 - t) + BG_BOT[k] * t) for k in range(3)))
        if glow:
            layer = Image.new("RGB", size, (0, 0, 0))
            gd = ImageDraw.Draw(layer)
            gx, gy, gr = glow
            gd.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(70, 58, 30))
            layer = layer.filter(ImageFilter.GaussianBlur(gr // 2))
            from PIL import ImageChops
            img = ImageChops.add(img, layer)
        _bg_cache[key] = img
    return _bg_cache[key].copy()


def top_strip(draw, current: str | None):
    """맨 위 12띠 이름 줄 — 지금 띠는 금색 칸."""
    f = font(34)
    gap = 30
    widths = [draw.textlength(a, font=f) for a in WF.ANIMALS]
    total = sum(widths) + gap * (len(widths) - 1)
    x = (W - total) / 2
    for a, w_ in zip(WF.ANIMALS, widths):
        if a == current:
            draw.rounded_rectangle([x - 14, 30, x + w_ + 14, 84], radius=14, fill=GOLD)
            draw.text((x, 38), a, font=f, fill=NAVY)
        else:
            draw.text((x, 38), a, font=f, fill=DIM)
        x += w_ + gap


def footer(draw, brand: str = "왕별이 · 주간 띠별 운세"):
    f = font(30)
    draw.text((64, H - 62), brand, font=f, fill=DIM)
    s = "재미로 보는 운세예요"
    draw.text((W - 64 - draw.textlength(s, font=f), H - 62), s, font=f, fill=DIM)


# ── 띠 그림 ───────────────────────────────────────────────────
def asset_path(animal: str) -> str:
    i = WF.ANIMALS.index(animal)
    return os.path.join(ASSETS, f"{i + 1:02d}_{EN[i]}.jpg")


def ensure_animal(animal: str, wd: str | None = None, allow_spark: bool = True) -> str | None:
    """커밋된 그림 → 작업 폴더 캐시 → Spark 한 장(z-image-turbo 고정 · no_llm). 다 안 되면 None."""
    p = asset_path(animal)
    if os.path.exists(p):
        return p
    if not wd:
        return None
    i = WF.ANIMALS.index(animal)
    cache = os.path.join(wd, "zodiac", f"{i + 1:02d}_{EN[i]}.png")
    if os.path.exists(cache):
        return cache
    if not allow_spark or os.environ.get("WEEKLY_MOCK_TTS") == "1":
        return None
    try:
        import wbspark
        spark_wait()
        prompt = ZODIAC_PROMPT.format(desc=_DESC.get(EN[i], f"cute little {EN[i]}"))
        if wbspark.generate_image(prompt, cache, model=IMG_MODEL or None, aspect="1:1", no_llm=True, timeout_sec=600):
            return cache
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ {animal}띠 그림 생성 실패(이름 원으로 대신): {e}")
    return None


def animal_tile(animal: str, size: int, wd: str | None = None, radius: int | None = None, ring: tuple | None = None,
                ring_w: int = 0):
    """정사각 띠 그림(둥근 모서리). 그림이 없으면 이름을 쓴 원."""
    from PIL import Image, ImageDraw, ImageOps
    p = ensure_animal(animal, wd)
    if p:
        im = ImageOps.fit(Image.open(p).convert("RGB"), (size, size), Image.LANCZOS, centering=(0.5, 0.42))
    else:
        im = Image.new("RGB", (size, size), PANEL)
        d = ImageDraw.Draw(im)
        d.ellipse([size * 0.08, size * 0.08, size * 0.92, size * 0.92], fill=(48, 56, 110), outline=GOLD,
                  width=max(2, size // 40))
        f = font(max(16, int(size * (0.34 if len(animal) <= 2 else 0.24))))
        text_c(d, size / 2, size / 2 - f.size * 0.62, animal, f, GOLD)
    r = size // 8 if radius is None else radius
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    if ring and ring_w:
        ImageDraw.Draw(out).rounded_rectangle([0, 0, size - 1, size - 1], radius=r, outline=ring, width=ring_w)
    return out


def paste(img, tile, xy):
    img.paste(tile, (int(xy[0]), int(xy[1])), tile)


# ── 화면들 ────────────────────────────────────────────────────
def draw_title(plan: dict, wd: str | None = None):
    from PIL import ImageDraw
    img = background(glow=(W // 2, 380, 420))
    d = ImageDraw.Draw(img)
    text_c(d, W / 2, 120, "이번 주", font(120), WHITE, stroke=4, stroke_fill=NAVY)
    text_c(d, W / 2, 260, "띠별 운세", font(190), GOLD, stroke=6, stroke_fill=NAVY)
    f = font(58)
    s = plan["range"]
    tw = d.textlength(s, font=f)
    d.rounded_rectangle([W / 2 - tw / 2 - 40, 520, W / 2 + tw / 2 + 40, 610], radius=45, fill=WHITE)
    text_c(d, W / 2, 532, s, f, NAVY)
    size, gap = 132, 14
    x0 = (W - (size * 12 + gap * 11)) / 2
    fn = font(30)
    for k, a in enumerate(WF.ANIMALS):
        x = x0 + k * (size + gap)
        paste(img, animal_tile(a, size, wd, radius=size // 2), (x, 700))
        text_c(d, x + size / 2, 846, a, fn, BEIGE)
    footer(d)
    return img


def draw_table(plan: dict, wd: str | None = None, title: str = "이번 주 띠별 운세 순위"):
    """2열 × 6줄 — 왼쪽 1~6위, 오른쪽 7~12위(매일 8초 표와 같은 순위표의 가로판)."""
    from PIL import ImageDraw
    img = background()
    d = ImageDraw.Draw(img)
    d.text((64, 44), title, font=font(70), fill=WHITE)
    f = font(40)
    s = plan["range"]
    tw = d.textlength(s, font=f)
    d.rounded_rectangle([W - 64 - tw - 56, 52, W - 64, 122], radius=35, fill=GOLD)
    d.text((W - 64 - tw - 28, 62), s, font=f, fill=NAVY)
    cw, chh, gx, gy, top = 880, 128, 40, 10, 170
    fn, fs, fy, fl, fr = font(52), font(38), font(28), font(36), font(44)
    for r in plan["rows"]:
        k = r["rank"] - 1
        col, row = k // 6, k % 6
        x, y = 64 + col * (cw + gx), top + row * (chh + gy)
        top3 = r["rank"] <= 3
        d.rounded_rectangle([x, y, x + cw, y + chh], radius=24, fill=PANEL,
                            outline=GOLD if top3 else (58, 66, 118), width=4 if top3 else 2)
        cx, cy = x + 58, y + chh / 2
        d.ellipse([cx - 38, cy - 38, cx + 38, cy + 38], fill=GOLD if top3 else (70, 78, 130))
        text_c(d, cx, cy - 26, str(r["rank"]), fr, NAVY if top3 else WHITE)
        paste(img, animal_tile(r["animal"], 104, wd, radius=52), (x + 112, y + 12))
        name = f"{r['animal']}띠"
        d.text((x + 236, y + 14), name, font=fn, fill=WHITE)
        d.text((x + 236 + d.textlength(name, font=fn) + 14, y + 26), f"{r['score']}점", font=fs, fill=GOLD)
        d.text((x + 236, y + 82), WF.years_label(r["animal"]), font=fy, fill=DIM)
        ln = r["line"]
        d.text((x + cw - 28 - d.textlength(ln, font=fl), y + 44), ln, font=fl, fill=BEIGE)
    footer(d)
    return img


def draw_card(plan: dict, sp: dict, wd: str | None = None):
    from PIL import ImageDraw
    img = background(glow=(460, 560, 380))
    d = ImageDraw.Draw(img)
    top_strip(d, sp["animal"])
    paste(img, animal_tile(sp["animal"], 700, wd, radius=48, ring=GOLD, ring_w=6), (110, 190))
    x = 900
    d.text((x, 150), f"{sp['index']} / 12", font=font(36), fill=DIM)
    d.text((x, 196), f"{sp['animal']}띠", font=font(180), fill=GOLD, stroke_width=4, stroke_fill=NAVY)
    d.text((x, 420), WF.years_label(sp["animal"]), font=font(52), fill=BEIGE)
    f = font(58)
    s = f"이번 주 {sp['rank']}위 · {sp['score']}점"
    d.rounded_rectangle([x, 508, x + d.textlength(s, font=f) + 64, 604], radius=48, fill=GOLD)
    d.text((x + 32, 522), s, font=f, fill=NAVY)
    d.text((x, 660), "이번 주 한 줄", font=font(38), fill=DIM)
    size, lines, lh = fit(d, sp.get("headline", ""), 900, 250, 74, 46)
    for k, ln in enumerate(lines):
        d.text((x, 714 + k * lh), ln, font=font(size), fill=WHITE)
    footer(d)
    return img


def _side(img, d, sp: dict, wd: str | None):
    paste(img, animal_tile(sp["animal"], 440, wd, radius=36, ring=GOLD, ring_w=4), (120, 200))
    text_c(d, 340, 672, f"{sp['animal']}띠 · {sp['rank']}위", font(60), GOLD)
    text_c(d, 340, 758, WF.years_label(sp["animal"]), font(36), BEIGE)


def draw_section(plan: dict, sp: dict, wd: str | None = None):
    from PIL import ImageDraw
    img = background()
    d = ImageDraw.Draw(img)
    top_strip(d, sp["animal"])
    _side(img, d, sp, wd)
    x0, y0, x1, y1 = 640, 140, 1840, 980
    d.rounded_rectangle([x0, y0, x1, y1], radius=36, fill=PANEL)
    col = SEC_COLOR.get(sp.get("key"), GOLD)
    d.rounded_rectangle([x0 + 50, y0 + 58, x0 + 64, y0 + 132], radius=7, fill=col)
    d.text((x0 + 88, y0 + 46), sp.get("label", ""), font=font(80), fill=col)
    size, lines, lh = fit(d, sp.get("body", ""), x1 - x0 - 110, y1 - y0 - 230, 80, 48)
    f = font(size)
    y = y0 + 190 + max(0, (y1 - y0 - 230 - len(lines) * lh) // 3)
    for ln in lines:
        d.text((x0 + 56, y), ln, font=f, fill=WHITE)
        y += lh
    footer(d)
    return img


def draw_lucky(plan: dict, sp: dict, wd: str | None = None):
    from PIL import ImageDraw
    img = background()
    d = ImageDraw.Draw(img)
    top_strip(d, sp["animal"])
    _side(img, d, sp, wd)
    x0, y0, x1, y1 = 640, 140, 1840, 980
    d.rounded_rectangle([x0, y0, x1, y1], radius=36, fill=PANEL)
    col = SEC_COLOR["lucky"]
    d.rounded_rectangle([x0 + 50, y0 + 58, x0 + 64, y0 + 132], radius=7, fill=col)
    d.text((x0 + 88, y0 + 46), "행운의 요일 · 색", font=font(80), fill=col)
    d.text((x0 + 60, 360), "요일", font=font(46), fill=DIM)
    d.text((x0 + 60, 420), sp.get("day", ""), font=font(140), fill=WHITE)
    d.text((x0 + 60, 640), "색", font=font(46), fill=DIM)
    rgb = WF.COLORS.get(sp.get("color", ""), GOLD)
    d.ellipse([x0 + 60, 710, x0 + 230, 880], fill=rgb, outline=WHITE, width=6)
    d.text((x0 + 270, 722), sp.get("color", ""), font=font(120), fill=WHITE)
    footer(d)
    return img


def draw_outro(plan: dict, wd: str | None = None):
    from PIL import ImageDraw
    img = background(glow=(1300, 470, 420))
    d = ImageDraw.Draw(img)
    size, gap = 150, 22
    for k, a in enumerate(WF.ANIMALS):
        c, r = k % 4, k // 4
        paste(img, animal_tile(a, size, wd, radius=size // 2), (90 + c * (size + gap), 200 + r * (size + gap + 40)))
        text_c(d, 90 + c * (size + gap) + size / 2, 200 + r * (size + gap + 40) + size + 4, a, font(30), BEIGE)
    x = 860
    d.text((x, 190), "매일 아침 6시", font=font(120), fill=GOLD, stroke_width=4, stroke_fill=NAVY)
    d.text((x, 350), "8초 띠별 운세 표", font=font(96), fill=WHITE)
    d.text((x, 500), "1위부터 12위까지 한눈에", font=font(56), fill=BEIGE)
    d.text((x, 590), "구독하고 알림을 켜 두세요", font=font(56), fill=BEIGE)
    f = font(48)
    s = "재미로 보는 운세예요 · 좋은 한 주 보내세요"
    d.rounded_rectangle([x, 720, x + d.textlength(s, font=f) + 60, 806], radius=43, fill=PANEL, outline=GOLD, width=3)
    d.text((x + 30, 734), s, font=f, fill=WHITE)
    footer(d)
    return img


def draw_slide(plan: dict, sp: dict, wd: str | None = None):
    k = sp.get("kind")
    if k == "title":
        return draw_title(plan, wd)
    if k == "table":
        return draw_table(plan, wd)
    if k == "card":
        return draw_card(plan, sp, wd)
    if k == "section":
        return draw_section(plan, sp, wd)
    if k == "lucky":
        return draw_lucky(plan, sp, wd)
    if k == "outro":
        return draw_outro(plan, wd)
    raise ValueError(f"모르는 화면 {k!r}")


def draw_thumbnail(plan: dict, wd: str | None = None):
    """1280×720 — 큰 '이번 주 / 띠별 운세' + 날짜 + 1위 띠 그림."""
    from PIL import ImageDraw
    img = background((TW, TH), glow=(990, 360, 330))
    d = ImageDraw.Draw(img)
    first = next(r for r in plan["rows"] if r["rank"] == 1)
    paste(img, animal_tile(first["animal"], 500, wd, radius=250, ring=GOLD, ring_w=10), (735, 150))
    f = font(52)
    s = f"이번 주 1위 {first['animal']}띠"
    tw = d.textlength(s, font=f)
    d.rounded_rectangle([985 - tw / 2 - 30, 70, 985 + tw / 2 + 30, 148], radius=39, fill=GOLD)
    text_c(d, 985, 80, s, f, NAVY)
    d.text((48, 70), "이번 주", font=font(128), fill=WHITE, stroke_width=6, stroke_fill=NAVY)
    d.text((40, 220), "띠별 운세", font=font(156), fill=GOLD, stroke_width=7, stroke_fill=NAVY)
    import datetime as _dt
    s = WF.range_label(_dt.date.fromisoformat(plan["monday"]), short=True)
    f = font(66)
    tw = d.textlength(s, font=f)
    d.rounded_rectangle([48, 440, 48 + tw + 60, 540], radius=50, fill=WHITE)
    d.text((78, 454), s, font=f, fill=NAVY)
    d.text((52, 580), "쥐띠~돼지띠 · 45~96년생", font=font(52), fill=BEIGE, stroke_width=3, stroke_fill=NAVY)
    return img


# ── 목소리 ────────────────────────────────────────────────────
def spark_wait():
    """공용 서버 — 앞에 기다리는 작업이 많으면 줄어들 때까지 기다린다(최대 20분)."""
    try:
        import requests
        import wbspark
        for _ in range(60):
            q = requests.get(f"{wbspark._base()}/queue", headers=wbspark._headers(), timeout=15).json()
            if int(q.get("waiting", 0)) <= SPARK_MAX_WAITING:
                return
            print(f"   ⏳ Spark 대기열 {q.get('waiting')} — 20초 쉼", flush=True)
            time.sleep(20)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 대기열 확인 실패(계속): {str(e)[:120]}")


def wav_dur(p: str) -> float:
    with wave.open(p) as w:
        return w.getnframes() / float(w.getframerate())


def write_silence(path: str, sec: float):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"\x00\x00" * int(SR * sec))


def mock_tts(text: str, out: str, voice: str = "") -> bool:
    """네트워크 없이(로컬·테스트) — 글자 수만큼(분당 450자) 조용한 톤."""
    import struct
    n = int(SR * max(0.6, len(text) / (WF.CPM / 60.0)))
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(1200 * math.sin(2 * math.pi * 220 * k / SR))) for k in range(n)))
    return True


def _edge(text: str, wav_out: str):
    mp3 = wav_out[:-4] + ".mp3"
    sh([sys.executable, "-m", "edge_tts", "--voice", EDGE_VOICE, "--text", text, "--write-media", mp3])
    sh([FFMPEG, "-y", "-v", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", wav_out])


def _clean(raw: str, out: str):
    """44.1kHz 모노 16bit 로 맞추고 앞뒤 무음을 자른다(쉼은 코드가 정한다)."""
    sh([FFMPEG, "-y", "-v", "error", "-i", raw, "-af",
        "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse,"
        "silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse",
        "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])


def synth(texts: list[str], wd: str, voice: str = WF.VOICE, tts=None, clean: bool | None = None) -> tuple[dict, dict]:
    """글 → wav 경로(캐시: 목소리+글). 반환 ({글: 경로}, 통계). 실패가 5% 를 넘으면 멈춘다.

    clean: 앞뒤 무음 자르기(ffmpeg). 기본은 진짜 목소리일 때만."""
    os.makedirs(wd, exist_ok=True)
    mock = tts is None and os.environ.get("WEEKLY_MOCK_TTS") == "1"
    clean = (not mock) if clean is None else clean
    real = tts is None and not mock                  # 진짜 Spark — 대기열을 보고 한 건씩
    if tts is None:
        if mock:
            tts = mock_tts
        else:
            import wbspark
            tts = wbspark.tts
    todo = list(dict.fromkeys(t for t in texts if t))

    def one(text):
        key = hashlib.sha1(f"{voice}|{mock}|{text}".encode("utf-8")).hexdigest()[:16]
        out = os.path.join(wd, f"v_{key}.wav")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return text, out, True
        raw = out[:-4] + "_raw.wav"
        for attempt in range(3):
            if real:
                spark_wait()
            if tts(text, raw, voice):
                if clean:
                    _clean(raw, out)
                    os.remove(raw)
                else:
                    os.replace(raw, out)
                return text, out, True
            time.sleep(RETRY_WAIT * (1 + 2 * attempt))
        return text, out, False

    t0, got, failed = time.time(), {}, []
    with cf.ThreadPoolExecutor(max(1, WORKERS)) as ex:
        for n, (text, out, ok) in enumerate(ex.map(one, todo), 1):
            got[text] = out
            if not ok:
                failed.append(text)
            if n % 10 == 0 or n == len(todo):
                print(f"   🎙️ 목소리 {n}/{len(todo)} · 실패 {len(failed)} · {time.time() - t0:.0f}s", flush=True)
    if len(failed) > max(2, int(len(todo) * MAX_FALLBACK)):
        raise RuntimeError(f"Supertonic 실패 {len(failed)}/{len(todo)} — 목소리가 섞이므로 중단")
    for text in failed:                              # 소수만 edge-tts 로 메운다
        _edge(text, got[text])
        print(f"   ⚠️ 조각 edge-tts 로 대체: {text[:30]}")
    return got, {"clips": len(todo), "fallback": len(failed), "tts_sec": round(time.time() - t0)}


# ── 타임라인 ──────────────────────────────────────────────────
def timeline(plan: dict, durs: dict) -> tuple[list[dict], list[dict], float]:
    """조각마다 시작·끝, 파트마다 시작(쉼 포함), 전체 길이 — 모두 ★최종(TEMPO 적용) 초.

    durs: {글: 원본 길이(초)}. 반환 (조각들, 파트들, 전체)."""
    t, items, parts = 0.0, [], []
    for pi, p in enumerate(plan["parts"]):
        for ci, c in enumerate(p["chunks"]):
            gap = WF.LEAD if (pi == 0 and ci == 0) else (WF.GAP_PART if ci == 0 else WF.GAP_SECTION)
            show = t                                   # 화면은 쉼이 시작될 때 바뀐다(장 카드가 먼저 뜬다)
            if ci == 0:
                parts.append({"id": p["id"], "title": p["title"], "card": show / WF.TEMPO})
            t += gap
            d = durs[c["text"]]
            items.append({"text": c["text"], "slide": c["slide"], "part": p["id"], "gap": gap,
                          "show": show / WF.TEMPO, "start": t / WF.TEMPO, "end": (t + d) / WF.TEMPO})
            t += d
    return items, parts, (t + WF.TAIL) / WF.TEMPO


def segments(items: list[dict], total: float) -> list[tuple[dict, float, float]]:
    """(화면, 시작, 끝) — 같은 화면이 이어지면 한 구간으로."""
    segs: list = []
    for i, it in enumerate(items):
        end = items[i + 1]["show"] if i + 1 < len(items) else total
        if segs and segs[-1][0] == it["slide"]:
            segs[-1] = (segs[-1][0], segs[-1][1], end)
        else:
            segs.append((it["slide"], it["show"], end))
    return segs


def _ts(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chapters_text(parts: list[dict]) -> str:
    """유튜브 챕터 — 첫 줄 00:00, 챕터마다 10초 이상(우리는 20초 이상)."""
    return "\n".join(f"{_ts(p['card'])} {p['title']}" for p in parts)


# ── 오디오 · 영상 ─────────────────────────────────────────────
def build_audio(items: list[dict], wavs: dict, wd: str, out_m4a: str):
    sil: dict = {}

    def silence(sec):
        key = round(sec, 2)
        if key not in sil:
            p = os.path.join(wd, f"sil_{key:.2f}.wav")
            write_silence(p, key)
            sil[key] = p
        return sil[key]

    lst = os.path.join(wd, "audio_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for it in items:
            if it["gap"] > 0.01:
                f.write(f"file '{os.path.abspath(silence(it['gap']))}'\n")
            f.write(f"file '{os.path.abspath(wavs[it['text']])}'\n")
        f.write(f"file '{os.path.abspath(silence(WF.TAIL))}'\n")
    sh([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
        "-af", f"atempo={WF.TEMPO},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1",
        "-c:a", "aac", "-b:a", "128k", out_m4a])


def build_video(segs: list[tuple], audio: str, out_mp4: str, wd: str):
    lst = os.path.join(wd, "video_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p, a, b in segs:
            f.write(f"file '{os.path.abspath(p)}'\nduration {max(0.1, b - a):.3f}\n")
        f.write(f"file '{os.path.abspath(segs[-1][0])}'\n")        # concat 은 마지막 항목을 한 번 더
    sh([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
        "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "24",
        "-c:a", "copy", "-shortest", "-movflags", "+faststart", out_mp4])


def slide_files(plan: dict, segs: list[tuple], wd: str) -> list[tuple[str, float, float]]:
    """화면을 그려 파일로(같은 화면은 한 번만)."""
    os.makedirs(wd, exist_ok=True)
    made: dict = {}
    out = []
    for sp, a, b in segs:
        key = hashlib.sha1(repr(sorted(sp.items())).encode("utf-8")).hexdigest()[:12]
        if key not in made:
            p = os.path.join(wd, f"s_{len(made):03d}_{sp.get('kind')}.jpg")
            draw_slide(plan, sp, wd).convert("RGB").save(p, "JPEG", quality=90)
            made[key] = p
        out.append((made[key], a, b))
    return out


def render(plan: dict, out_dir: str, wd: str, tts=None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(wd, exist_ok=True)
    base = os.path.join(out_dir, f"{plan['monday']}_weekly_fortune")
    texts = [c["text"] for p in plan["parts"] for c in p["chunks"]]
    print(f"   📜 {plan['stats']['chars']:,}자 · 조각 {len(texts)}개 · 예상 {plan['stats']['est_min']}분 · 목소리 {WF.VOICE}")
    for a in WF.ANIMALS:                                  # 그림 먼저(없으면 Spark 한 장씩)
        ensure_animal(a, wd)
    wavs, st = synth(texts, os.path.join(wd, "tts"), tts=tts)
    durs = {t: wav_dur(p) for t, p in wavs.items()}
    items, parts, total = timeline(plan, durs)
    audio = base + "_audio.m4a"
    build_audio(items, wavs, os.path.join(wd, "tts"), audio)
    segs = slide_files(plan, segments(items, total), os.path.join(wd, "slides"))
    video = base + ".mp4"
    build_video(segs, audio, video, os.path.join(wd, "slides"))
    thumb = base + "_thumb.jpg"
    draw_thumbnail(plan, wd).convert("RGB").save(thumb, "JPEG", quality=90)
    table = base + "_table.png"
    draw_table(plan, wd).convert("RGB").save(table, "PNG")
    res = {"video": video, "thumb": thumb, "table": table, "chapters": chapters_text(parts),
           "duration_sec": round(total, 1), "duration_min": round(total / 60, 1),
           "slides": len({p for p, _, _ in segs}), **st}
    print(f"✅ {video} · {res['duration_min']}분 · 화면 {res['slides']}장 · 합성 {st['tts_sec']}초 · 대체 {st['fallback']}")
    return res


if __name__ == "__main__":
    # 화면 미리보기: python weekly_fortune_render.py <대본.json> <폴더>
    import json
    with open(sys.argv[1], encoding="utf-8") as fp:
        _plan = WF.compose(json.load(fp))
    _out = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(_out, exist_ok=True)
    seen = set()
    for _p in _plan["parts"]:
        for _c in _p["chunks"]:
            _k = repr(sorted(_c["slide"].items()))
            if _k in seen:
                continue
            seen.add(_k)
            draw_slide(_plan, _c["slide"]).convert("RGB").save(os.path.join(_out, f"{len(seen):03d}.jpg"), quality=88)
    draw_thumbnail(_plan).convert("RGB").save(os.path.join(_out, "thumb.jpg"), quality=90)
    print(f"{len(seen)} 화면 + 썸네일 → {_out}")
