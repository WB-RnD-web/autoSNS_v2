#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""왕별이 라디오 · 밤 편 '잠들기 전 복 받는 시간' 렌더 (2026-11-28 견본).

왜(2026-11-28 사용자): "운전하면서·조깅하면서·자기 전에·집에서 라디오 듣는 것처럼 자연스럽게 보는 채널".
  스튜디오: 55세 이상 71.7% · 휴대폰 95% · 정기 시청자 0.0% · 댓글 = 띠·생년을 적고 '복 받아 갑니다'(의식).
  백그라운드 재생은 프리미엄만 → 화면을 켠 채 틀어 두는 롱폼. 계획 https://claude.ai/artifact/6s17X6McBnS27PAKTxMXFd

구성(대본 JSON 의 parts 순서 그대로): 안부 → 내일 띠별 운세(쥐~돼지, 생년 호명) → 옛날이야기 → 옛말 한 마디
  → 따라 하는 좋은 말(줄마다 쉼) → 잘 자요 → 빗소리 꼬리.

소리: 목소리(Supertonic 한 목소리, 0.9배) · 피아노(아주 작게, 말할 때 더 줄인다 — sidechaincompress)
  · 빗소리(합성 · 끝에 30분). 피아노 = Kevin MacLeod 'Gymnopedie No 1'(CC BY 4.0 · 설명란에 출처).
화면: 밤 그림(10% 크게 두고 아주 천천히 흐른다) 위에 큰 글자 판(RGBA PNG)을 얹는다 · 10fps.

    python pipeline/radio_night_render.py <plan.json> --out <mp4> [--bg <배경 폴더>] [--voice F2] [--no-rain]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import birth_basis  # noqa: E402
import weekly_fortune_render as R  # noqa: E402

W, H = 1920, 1080
BW, BH = 2112, 1188           # 배경은 10% 크게 — crop 으로 아주 천천히 흐른다
FPS = int(os.environ.get("RADIO_FPS", "10"))
SR = 44100
TEMPO = float(os.environ.get("RADIO_TEMPO", "0.9"))    # 잠자리 — 주간 롱폼(0.92)보다 조금 더 천천히
LEAD = 4.0                    # 첫 말 앞 피아노만(원본 초)
GAP_CHUNK = 0.75
GAP_PART = 2.0
XF = 2.5                      # 배경이 바뀔 때 겹치는 초
# ★11/28 견본 뒤 사용자 "빗소리 30분으로 늘려서" — 말 15~19분 + 빗소리 30분(잠든 뒤에도 틀어 두게)
RAIN_MIN = float(os.environ.get("RADIO_RAIN_MIN", "30"))
MUSIC_DB = float(os.environ.get("RADIO_MUSIC_DB", "-8"))
RAIN_DB = float(os.environ.get("RADIO_RAIN_DB", "-3"))
ASSETS = os.path.join(HERE, "assets", "radio")
MUSIC = os.environ.get("RADIO_MUSIC") or os.path.join(ASSETS, "gymnopedie1.mp3")
TW, TH = 1280, 720
STYLE = "peaceful nostalgic Korean folk tale mood at night, soft painterly illustration, wide shot, no people"
BRAND = "왕별이 · 잠들기 전 복 받는 시간"
MUSIC_CREDIT = ("🎹 피아노: \"Gymnopedie No 1\" Kevin MacLeod (incompetech.com) · "
                "Licensed under Creative Commons: By Attribution 4.0 · http://creativecommons.org/licenses/by/4.0/")

GOLD, BEIGE, WHITE, DIM, NAVY = R.GOLD, R.BEIGE, R.WHITE, (200, 196, 214), R.NAVY
COLOR_RGB = {"하늘색": (118, 188, 238), "초록색": (64, 158, 92), "노란색": (245, 205, 60), "분홍색": (240, 150, 180),
             "남색": (70, 82, 170), "보라색": (140, 92, 190), "빨간색": (214, 58, 58), "베이지색": (225, 205, 170),
             "주황색": (238, 138, 48), "금색": (212, 175, 55), "갈색": (150, 105, 66), "연두색": (158, 208, 88)}
SERIF = [os.environ.get("RADIO_SERIF") or "",
         "/usr/share/fonts/truetype/nanum/NanumMyeongjoExtraBold.ttf",
         "/usr/share/fonts/truetype/nanum/NanumMyeongjoBold.ttf",
         "C:/Windows/Fonts/HANBatangB.ttf", "C:/Windows/Fonts/batang.ttc"]
_serif: dict = {}


def serif(size: int):
    from PIL import ImageFont
    if size not in _serif:
        p = next((x for x in SERIF if x and os.path.exists(x)), None)
        _serif[size] = ImageFont.truetype(p, size) if p else R.font(size)
    return _serif[size]


# ── 글자 판 ───────────────────────────────────────────────────
def _canvas():
    from PIL import Image
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _shadowed(img, draw_fn, blur: int = 10, alpha: int = 200):
    """draw_fn(draw, fill_override) 로 그림자(검정·흐림)를 먼저 깔고 위에 글자."""
    from PIL import Image, ImageDraw, ImageFilter
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sh), (0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(sh)
    draw_fn(ImageDraw.Draw(img), None)


def center_lines(img, lines: list[str], f, y: float, fill, gap: float = 1.3):
    lh = f.size * gap

    def fn(d, over):
        for i, s in enumerate(lines):
            w = d.textlength(s, font=f)
            d.text(((W - w) / 2, y + i * lh), s, font=f, fill=over or fill)
    _shadowed(img, fn)
    return y + len(lines) * lh


def brand(img, right: str | None = None):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    f = R.font(32)
    d.text((64, 46), BRAND, font=f, fill=DIM + (230,))
    if right:
        d.text((W - 64 - d.textlength(right, font=f), 46), right, font=f, fill=DIM + (230,))


def draw_open(sp):
    img = _canvas()
    brand(img)
    y = center_lines(img, ["왕별이 라디오"], R.font(46), 250, GOLD)
    y = center_lines(img, ["잠들기 전", "복 받는 시간"], serif(132), y + 20, WHITE, 1.22)
    y = center_lines(img, [sp.get("date", "")], R.font(54), y + 36, BEIGE)
    center_lines(img, ["내일 띠별 운세 · 옛날이야기 · 따라 하는 좋은 말 · 빗소리"], R.font(38), y + 40, DIM)
    return img


def draw_ddi_intro(sp, wd):
    img = _canvas()
    brand(img, "재미로 보는 운세예요")
    y = center_lines(img, [sp["date"]], R.font(50), 170, BEIGE)
    y = center_lines(img, ["내일 띠별 운세"], serif(120), y + 10, WHITE)
    y = center_lines(img, ["기운이 특히 좋은 띠"], R.font(46), y + 30, GOLD)
    size, gap = 230, 90
    x0 = (W - (3 * size + 2 * gap)) / 2
    from PIL import ImageDraw
    for i, a in enumerate(sp.get("top") or []):
        t = R.animal_tile(a, size, wd, radius=size // 2, ring=GOLD, ring_w=6)
        R.paste(img, t, (x0 + i * (size + gap), y + 20))
        center = x0 + i * (size + gap) + size / 2
        f = serif(60)

        def fn(d, over, a=a, center=center, f=f):
            s = a + "띠"
            d.text((center - d.textlength(s, font=f) / 2, y + 30 + size), s, font=f, fill=over or WHITE)
        _shadowed(img, fn)
    d = ImageDraw.Draw(img)
    f = R.font(34)
    s = birth_basis.SCREEN_DDI
    d.text(((W - d.textlength(s, font=f)) / 2, H - 92), s, font=f, fill=DIM + (235,))
    return img


def draw_ddi(sp, wd):
    from PIL import ImageDraw
    img = _canvas()
    a = sp["animal"]
    d = ImageDraw.Draw(img)
    R.top_strip(d, a)
    size = 460
    tile = R.animal_tile(a, size, wd, radius=size // 2, ring=GOLD if sp.get("top") else BEIGE, ring_w=8)
    R.paste(img, tile, (150, 290))
    x = 700
    big = serif(150)
    ys = " · ".join(str(y)[2:] for y in sp["years"]) + "년생"
    key = sp.get("key", "")

    def fn(dd, over):
        dd.text((x, 230), a + "띠", font=big, fill=over or GOLD)
        dd.text((x + 6, 440), ys, font=R.font(66), fill=over or WHITE)
        dd.text((x + 6, 560), "내일 한마디", font=R.font(40), fill=over or DIM)
        dd.text((x + 6, 618), key, font=serif(80), fill=over or BEIGE)
    _shadowed(img, fn)
    d = ImageDraw.Draw(img)
    f = R.font(44)
    cy = 790
    col = COLOR_RGB.get(sp.get("color"), BEIGE)
    d.rounded_rectangle([x, cy - 8, x + 1080, cy + 76], radius=38, fill=(14, 16, 36, 170))
    d.text((x + 36, cy + 6), "행운의 색", font=f, fill=DIM)
    tx = x + 36 + d.textlength("행운의 색 ", font=f)
    d.ellipse([tx + 6, cy + 14, tx + 50, cy + 58], fill=col)
    d.text((tx + 66, cy + 6), sp.get("color", ""), font=f, fill=WHITE)
    tx2 = x + 560
    d.text((tx2, cy + 6), "좋은 시간", font=f, fill=DIM)
    d.text((tx2 + d.textlength("좋은 시간  ", font=f), cy + 6), sp.get("time", ""), font=f, fill=WHITE)
    R.footer(d, brand=BRAND)
    return img


def draw_ddi_outro(sp, wd):
    img = _canvas()
    brand(img)
    y = center_lines(img, ["열두 띠 운세, 다 들려 드렸어요"], serif(96), 330, WHITE)
    center_lines(img, ["댓글에 내 띠랑 식구들 띠를", "적어 두세요"], R.font(60), y + 50, BEIGE, 1.35)
    return img


def draw_story(sp, wd):
    img = _canvas()
    brand(img)
    y = center_lines(img, ["옛날이야기 한 토막"], R.font(52), 330, GOLD)
    center_lines(img, [sp.get("title", "")], serif(150), y + 30, WHITE)
    return img


def draw_line_card(label: str, line: str, sub: str | None = None, size: int = 100):
    img = _canvas()
    brand(img)
    from PIL import ImageDraw
    lines = line.split("\n")
    d = ImageDraw.Draw(img)
    f = serif(size)
    while max(d.textlength(s, font=f) for s in lines) > W - 240 and size > 50:
        size -= 4
        f = serif(size)
    block = len(lines) * size * 1.3
    y0 = (H - block) / 2 - 40
    center_lines(img, [label], R.font(46), y0 - 90, GOLD)
    y = center_lines(img, lines, f, y0, WHITE)
    if sub:
        center_lines(img, [sub], R.font(46), y + 30, BEIGE)
    return img


def draw_slide(sp: dict, wd: str):
    k = sp.get("kind")
    if k == "open":
        return draw_open(sp)
    if k == "ddi_intro":
        return draw_ddi_intro(sp, wd)
    if k == "ddi":
        return draw_ddi(sp, wd)
    if k == "ddi_outro":
        return draw_ddi_outro(sp, wd)
    if k == "story":
        return draw_story(sp, wd)
    if k == "story_think":
        return draw_line_card("오늘 이야기에서", sp["line"], size=92)
    if k == "saying":       # 한자는 화면에 쓰지 않는다(채널 규칙) — 둘째 줄은 한글 이름만
        return draw_line_card("옛말 한 마디", sp["line"], sp.get("sub") or None, size=120)
    if k == "wish_intro":
        return draw_line_card("따라 하는 좋은 말", "제가 먼저 읽으면\n천천히 따라 해 보세요", size=92)
    if k == "wish":
        return draw_line_card(f"따라 해 보세요 · {sp['n']} / {sp['of']}", sp["line"], size=104)
    if k == "wish_family":
        return draw_line_card("마음속으로", "사랑하는 식구들 이름을\n한 번씩 불러 주세요", "댓글에 · 내 띠 · 식구들 띠 · 좋은 말 한 줄",
                              size=88)
    if k == "night":
        img = _canvas()
        brand(img)
        y = center_lines(img, ["안녕히 주무세요"], serif(140), 360, WHITE)
        center_lines(img, ["내일 밤에도 이 시간에 만나요"], R.font(52), y + 40, BEIGE)
        return img
    if k == "rain":
        img = _canvas()
        center_lines(img, ["빗소리와 함께 편히 주무세요"], R.font(44), H - 150, DIM)
        return img
    raise ValueError(f"모르는 화면 {k}")


# ── 시간표 ────────────────────────────────────────────────────
def timeline(plan: dict, durs: dict) -> tuple[list[dict], list[dict], float]:
    """조각(보이기 시작·말 시작·끝) · 파트(시작) · 말 끝 — 모두 최종(TEMPO 적용) 초."""
    t, items, parts, prev_pause = 0.0, [], [], None
    for pi, p in enumerate(plan["parts"]):
        for ci, c in enumerate(p["chunks"]):
            if pi == 0 and ci == 0:
                gap = LEAD
            else:
                gap = max(GAP_PART if ci == 0 else GAP_CHUNK, prev_pause or 0)
            show = t
            if ci == 0:
                parts.append({"id": p["id"], "title": p["title"], "bg": p["bg"], "start": show / TEMPO})
            t += gap
            d = durs[c["text"]]
            items.append({"text": c["text"], "slide": c["slide"], "part": p["id"], "bg": p["bg"], "gap": gap,
                          "show": show / TEMPO, "start": t / TEMPO, "end": (t + d) / TEMPO})
            t += d
            prev_pause = c.get("pause")
    return items, parts, t / TEMPO


def chapters(parts: list[dict], voice_end: float) -> str:
    out = []
    for i, p in enumerate(parts):
        out.append(f"{R._ts(0 if i == 0 else p['start'])} {p['title']}")
    out.append(f"{R._ts(voice_end + 2)} 빗소리")
    return "\n".join(out)


# ── 소리 ──────────────────────────────────────────────────────
def build_voice(items: list[dict], wavs: dict, wd: str, out_wav: str):
    lst = os.path.join(wd, "voice_list.txt")
    sil: dict = {}
    with open(lst, "w", encoding="utf-8") as f:
        for it in items:
            g = round(it["gap"], 2)
            if g not in sil:
                sil[g] = os.path.join(wd, f"sil_{g:.2f}.wav")
                R.write_silence(sil[g], g)
            f.write(f"file '{os.path.abspath(sil[g])}'\n")
            f.write(f"file '{os.path.abspath(wavs[it['text']])}'\n")
    R.sh([R.FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
          "-af", f"atempo={TEMPO},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1", out_wav])


def build_music_unit(wd: str) -> str:
    """피아노 한 곡 — 앞뒤 무음 자르고, 페이드, 뒤에 2초 쉼(이어 붙일 때 덜컥하지 않게)."""
    out = os.path.join(wd, "music_unit.wav")
    if not os.path.exists(out):
        R.sh([R.FFMPEG, "-y", "-v", "error", "-i", MUSIC, "-af",
              "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
              "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
              "afade=t=in:d=2,areverse,afade=t=in:d=6,areverse,apad=pad_dur=2",
              "-ar", str(SR), "-ac", "2", out])
    return out


def build_rain(sec: float, out: str):
    """빗소리 합성 — 분홍 잡음(쏴아) + 갈색 잡음(웅) + 드문 물방울. 좌우 다른 씨앗."""
    d = f"{sec:.2f}"

    def side(seed):
        return (f"anoisesrc=c=pink:r={SR}:a=0.5:d={d}:s={seed},highpass=f=350,lowpass=f=6500,"
                f"tremolo=f=0.13:d=0.25[p{seed}];"
                f"anoisesrc=c=brown:r={SR}:a=0.6:d={d}:s={seed + 7},lowpass=f=260,volume=0.7[b{seed}];"
                f"aevalsrc=if(lt(random(0)\\,0.0012)\\,random(1)*2-1\\,0):s={SR}:d={d},"
                f"highpass=f=1800,lowpass=f=5200,volume=1.6[k{seed}];"
                f"[p{seed}][b{seed}][k{seed}]amix=inputs=3:normalize=0[s{seed}]")
    graph = side(1) + ";" + side(2) + ";[s1][s2]join=inputs=2:channel_layout=stereo,volume=0.6[o]"
    R.sh([R.FFMPEG, "-y", "-v", "error", "-filter_complex", graph, "-map", "[o]", "-ar", str(SR), out])


def mix(voice_wav: str, voice_end: float, rain_from: float | None, total: float, wd: str, out_m4a: str):
    unit = build_music_unit(wd)
    music_end = voice_end + 20.0
    inputs = ["-i", voice_wav, "-stream_loop", "-1", "-i", unit]
    g = [f"[0:a]aformat=sample_rates={SR}:channel_layouts=stereo,apad=whole_dur={total:.2f}[v]",
         "[v]asplit=2[v1][vsc]",
         f"[1:a]atrim=0:{music_end:.2f},asetpts=N/SR/TB,volume={MUSIC_DB}dB,afade=t=in:d=3,"
         f"afade=t=out:st={music_end - 22:.2f}:d=22,apad=whole_dur={total:.2f}[m]",
         "[m][vsc]sidechaincompress=threshold=0.03:ratio=3:attack=150:release=1400[md]"]
    mixin = "[v1][md]"
    n = 2
    if rain_from is not None and total - rain_from > 5:
        rain = os.path.join(wd, "rain.wav")
        build_rain(total - rain_from + 1, rain)
        inputs += ["-i", rain]
        ms = int(rain_from * 1000)
        g.append(f"[2:a]volume={RAIN_DB}dB,afade=t=in:d=10,afade=t=out:st={total - rain_from - 20:.2f}:d=20,"
                 f"adelay={ms}|{ms},apad=whole_dur={total:.2f}[r]")
        mixin += "[r]"
        n = 3
    g.append(f"{mixin}amix=inputs={n}:normalize=0:duration=longest,atrim=0:{total:.2f},alimiter=limit=0.95[out]")
    R.sh([R.FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(g), "-map", "[out]",
          "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), out_m4a])


# ── 화면 ──────────────────────────────────────────────────────
def prep_bg(src: str, out: str):
    """배경: 10% 크게 · 어둡게(글자가 읽히게) · 아래·가운데를 조금 더."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    im = ImageOps.fit(Image.open(src).convert("RGB"), (BW, BH), Image.Resampling.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    im = ImageEnhance.Brightness(im).enhance(0.52)
    import numpy as np
    col = np.clip((np.arange(BH) / BH - 0.55) / 0.45, 0, 1) * 70
    shade = Image.fromarray(np.repeat(col[:, None], BW, axis=1).astype("uint8"), "L")
    im = Image.composite(Image.new("RGB", (BW, BH), (6, 6, 16)), im, shade)
    im.save(out, "JPEG", quality=92)


def find_bg(name: str, dirs: list[str]) -> str:
    for d in dirs:
        for ext in (".png", ".jpg"):
            p = os.path.join(d, name + ext)
            if d and os.path.exists(p):
                return p
    raise FileNotFoundError(f"배경 '{name}' 없음: {dirs}")


def story_bg(plan: dict, wd: str) -> str | None:
    """오늘 이야기 배경 한 장(Spark z-image · 사람 없이). 실패하면 None → assets/radio/story.jpg."""
    scene = plan.get("story_scene")
    if not scene or os.environ.get("WEEKLY_MOCK_TTS") == "1" or os.environ.get("RADIO_STORY_BG", "1") == "0":
        return None
    out = os.path.join(wd, "bg", "story.png")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        import wbspark
        R.spark_wait()
        if wbspark.generate_image(f"{scene}, {STYLE}", out, model="z-image-turbo", aspect="16:9", no_llm=True,
                                  timeout_sec=600):
            return out
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 이야기 배경 생성 실패(기본 그림으로): {str(e)[:160]}")
    return None


def draw_thumbnail(plan: dict, bg_path: str | None, wd: str):
    """1280×720 — 왼쪽 큰 글자(잠들기 전 / 복 받는 시간) · 오른쪽 내일 기운 좋은 세 띠 · 아래 날짜 알약."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
    if bg_path and os.path.exists(bg_path):
        bg = ImageOps.fit(Image.open(bg_path).convert("RGB"), (TW, TH), Image.Resampling.LANCZOS)
        bg = ImageEnhance.Brightness(bg).enhance(0.78)
    else:
        bg = R.background((TW, TH), glow=(980, 360, 330))
    img = bg.convert("RGBA")
    shade = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(TW):
        sd.line([(x, 0), (x, TH)], fill=(8, 10, 30, int(215 * max(0.0, 1 - x / (TW * 0.78)))))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)
    d.text((48, 40), "왕별이 라디오 · 밤 편", font=R.font(40), fill=BEIGE, stroke_width=4,
           stroke_fill=NAVY)
    d.text((44, 100), "잠들기 전", font=serif(124), fill=WHITE, stroke_width=7, stroke_fill=NAVY)
    d.text((44, 238), "복 받는 시간", font=serif(124), fill=GOLD, stroke_width=7, stroke_fill=NAVY)
    d.text((50, 392), "내일 띠별 운세 · 생년 다 불러 드려요", font=R.font(48), fill=WHITE, stroke_width=5, stroke_fill=NAVY)
    sub = f"옛날이야기 '{plan.get('story', '')}' · 빗소리 {int(RAIN_MIN)}분"
    f = R.font(44)
    while d.textlength(sub, font=f) > 800 and f.size > 30:
        f = R.font(f.size - 2)
    d.text((50, 462), sub, font=f, fill=BEIGE, stroke_width=5, stroke_fill=NAVY)
    pill = f"{plan.get('for_label', '')} 운세"
    fp = R.font(56)
    w = d.textlength(pill, font=fp)
    d.rounded_rectangle([44, TH - 150, 44 + w + 60, TH - 54], radius=48, fill=WHITE)
    d.text((74, TH - 150 + (96 - fp.size) / 2 - 6), pill, font=fp, fill=NAVY)
    for k, a in enumerate((plan.get("top") or [])[:3]):
        s = 230
        R.paste(img, R.animal_tile(a, s, wd, ring=GOLD, ring_w=8, radius=s // 2), ((1010, 880, 1010)[k], (20, 245, 470)[k]))
    return img.convert("RGB")


def build_video(items, parts, total, bg_dirs, wd, audio, out_mp4, rain_from):
    # 글자 판들
    segs = []
    for i, it in enumerate(items):
        end = items[i + 1]["show"] if i + 1 < len(items) else total
        segs.append([it["slide"], it["show"], end])
    if rain_from is not None:
        last_end = items[-1]["end"] + 4
        segs[-1][2] = last_end
        segs.append([{"kind": "rain"}, last_end, total])
    merged = []
    for sp, a, b in segs:
        if merged and merged[-1][0] == sp:
            merged[-1][2] = b
        else:
            merged.append([sp, a, b])
    made, lst = {}, os.path.join(wd, "slides.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for sp, a, b in merged:
            key = hashlib.sha1(json.dumps(sp, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
            if key not in made:
                p = os.path.join(wd, f"t_{len(made):03d}_{sp.get('kind')}.png")
                draw_slide(sp, wd).save(p)
                made[key] = p
            f.write(f"file '{os.path.abspath(made[key])}'\nduration {max(0.1, b - a):.3f}\n")
        f.write(f"file '{os.path.abspath(made[key])}'\n")
    # 배경 구간
    bsegs = []
    for p in parts:
        if bsegs and bsegs[-1][0] == p["bg"]:
            continue
        bsegs.append([p["bg"], p["start"]])
    bsegs = [(b, s, (bsegs[i + 1][1] if i + 1 < len(bsegs) else total)) for i, (b, s) in enumerate(bsegs)]
    bsegs[0] = (bsegs[0][0], 0.0, bsegs[0][2])
    inputs, chain = [], []
    for i, (b, s, e) in enumerate(bsegs):
        src = os.path.join(wd, f"bg_{b}.jpg")
        if not os.path.exists(src):
            prep_bg(find_bg(b, bg_dirs), src)
        dur = (e - s) + (XF if i + 1 < len(bsegs) else 0)
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", src]
    n = len(bsegs)
    if n == 1:
        chain.append("[0:v]setpts=PTS-STARTPTS[bg]")
    else:
        cur, off = "[0:v]", 0.0
        for i in range(1, n):
            off += bsegs[i - 1][2] - bsegs[i - 1][1]
            outl = "[bg]" if i == n - 1 else f"[x{i}]"
            chain.append(f"{cur}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}{outl}")
            cur = outl
    chain.append(f"[bg]crop={W}:{H}:x='({BW - W}/2)*(1+sin(2*PI*t/97))':y='({BH - H}/2)*(1+sin(2*PI*t/131+1))',"
                 f"fps={FPS}[bgm]")
    chain.append(f"[{n}:v]fps={FPS},format=rgba[tx]")
    chain.append("[bgm][tx]overlay=0:0:format=auto,format=yuv420p[vout]")
    R.sh([R.FFMPEG, "-y", "-v", "error", *inputs, "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
          "-filter_complex", ";".join(chain), "-map", "[vout]", "-map", f"{n + 1}:a",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-g", str(FPS * 10), "-r", str(FPS),
          "-c:a", "copy", "-t", f"{total:.2f}", "-movflags", "+faststart", out_mp4])


# ── 목소리 ────────────────────────────────────────────────────
def edge_tts_fn(rate: str = "-8%"):
    def fn(text: str, out: str, voice: str) -> bool:
        mp3 = out[:-4] + ".mp3"
        try:
            R.sh([sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={rate}", "--text", text,
                  "--write-media", mp3])
            R.sh([R.FFMPEG, "-y", "-v", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])
            os.remove(mp3)
            return True
        except Exception as e:  # noqa: BLE001
            print("edge 실패", str(e)[:200])
            return False
    return fn


def render(plan: dict, out_mp4: str, wd: str, voice: str = "F2", rain: bool = True, bg_dir: str | None = None) -> dict:
    """대본 계획 → mp4 · 썸네일 jpg · _info.json. 배경: (bg_dir) → 오늘 이야기 그림(wd/bg) → assets/radio."""
    import time
    t0 = time.time()
    os.makedirs(wd, exist_ok=True)
    sb = story_bg(plan, wd)
    bg_dirs = [x for x in (bg_dir, os.path.join(wd, "bg") if sb else None, ASSETS) if x]
    texts = [c["text"] for p in plan["parts"] for c in p["chunks"]]
    tts = edge_tts_fn() if voice.startswith("ko-KR") else None
    wavs, st = R.synth(texts, os.path.join(wd, "tts_" + voice), voice=voice, tts=tts,
                       clean=True)
    durs = {t: R.wav_dur(p) for t, p in wavs.items()}
    items, parts, voice_end = timeline(plan, durs)
    rain_from = None
    total = voice_end + 24.0
    if rain:
        night = [it for it in items if it["part"] == "night"]
        cue = next((it for it in night if "빗소리" in it["text"]), night[-1] if night else items[-1])
        rain_from = cue["end"] - 1.0
        total = voice_end + RAIN_MIN * 60
    vw = os.path.join(wd, "voice.wav")
    build_voice(items, wavs, wd, vw)
    audio = os.path.join(wd, "mix.m4a")
    mix(vw, voice_end, rain_from, total, wd, audio)
    t1 = time.time()
    build_video(items, parts, total, bg_dirs, wd, audio, out_mp4, rain_from)
    thumb = os.path.splitext(out_mp4)[0] + "_thumb.jpg"
    draw_thumbnail(plan, sb or find_bg("story", bg_dirs), wd).save(thumb, "JPEG", quality=90)
    ch = chapters(parts, voice_end) if rain else chapters(parts, voice_end).rsplit("\n", 1)[0]
    info = {"video": out_mp4, "thumb": thumb, "total_min": round(total / 60, 2), "duration_sec": round(total, 1),
            "voice_end_min": round(voice_end / 60, 2), "chapters": ch, "tts": st, "story_bg": bool(sb),
            "media_sec": round(t1 - t0), "video_sec": round(time.time() - t1),
            "mb": round(os.path.getsize(out_mp4) / 1e6, 1)}
    with open(os.path.splitext(out_mp4)[0] + "_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="왕별이 라디오 밤 편 렌더")
    ap.add_argument("plan")
    ap.add_argument("--bg", default=None, help="배경 폴더(hello·ddi·story·wish·night .png/.jpg) — 기본 assets/radio")
    ap.add_argument("--out", required=True)
    ap.add_argument("--wd", default=None)
    ap.add_argument("--voice", default=os.environ.get("RADIO_VOICE") or "F2")
    ap.add_argument("--no-rain", action="store_true")
    a = ap.parse_args(argv)
    with open(a.plan, encoding="utf-8") as f:
        plan = json.load(f)
    wd = a.wd or os.path.join(os.path.dirname(os.path.abspath(a.out)), ".work")
    info = render(plan, a.out, wd, voice=a.voice, rain=not a.no_rain, bg_dir=a.bg)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
