#!/usr/bin/env python3
"""Gumiho Tales 렌더 — 대본 JSON → 롱폼(1920×1080) · 쇼츠(1080×1920) · 썸네일 · 자막 · 메타.

    python gumiho/tales/render_tale.py gumiho/tales/scripts/001_gumiho.json
    python gumiho/tales/render_tale.py <script> --mock          # Spark 없이(테스트: 단색 그림·가짜 목소리)
    python gumiho/tales/render_tale.py <script> --skip-short

① 목소리: 장면마다 Supertonic(F2) 한 건 — Spark 공용이라 동시 2건만, 같은 문장은 캐시.
② 그림: 장면 프롬프트마다 Spark 이미지 한 장(z-image-turbo, 17초 실측) — ★한 건씩, 대기열이 길면 기다린다.
③ 화면: 그림마다 켄 번스(확대·축소·좌우·상하) + 장면 사이 교차 전환 + 입자(안개·불티·눈·비·반딧불·먼지)
   + 비네트 + 주석 자막. PIL 로 프레임을 그려 ffmpeg 로 넘긴다(여러 프로세스가 구간을 나눠 인코딩 → 이어 붙임).
④ 소리: 내레이션 + 절차적 배경음(낮은 드론·바람·오음계 뜯는 소리 — 저작권 걱정 없음) + 장 카드 효과음,
   내레이션 아래서는 배경음을 낮춘다(덕킹). 마지막에 -14 LUFS.
"""
from __future__ import annotations

import argparse
import bisect
import concurrent.futures as cf
import hashlib
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import time
import wave

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
GUMIHO = os.path.dirname(HERE)
ROOT = os.path.dirname(GUMIHO)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import tales as T  # noqa: E402

W, H = 1920, 1080
SW, SH = 1080, 1920                       # 쇼츠
FPS = int(os.environ.get("TALES_FPS", "24"))
SR = 44100
XF = 0.5                                  # 교차 전환(초)
CARD_SEC = 2.4                            # 9/30 검수: 글자만 있는 화면은 짧게
LEAD = 0.15                               # 장면이 바뀌고 말이 시작되기까지
GAP = 0.5                                 # 말 끝나고 다음 장면까지
TEMPO = float(os.environ.get("TALES_TEMPO", "0.97"))   # 이야기는 아주 조금 느리게
ZOOM = 1.12                               # 켄 번스 최대 확대(준비 그림은 이만큼 크게 만든다)
PW, PH = round(W * ZOOM), round(H * ZOOM)
WORKERS = int(os.environ.get("TALES_TTS_WORKERS", "2"))
SPARK_MAX_WAITING = int(os.environ.get("GUMIHO_SPARK_MAX_WAITING", "6"))
IMG_MODEL = os.environ.get("TALES_IMG_MODEL", "z-image-turbo")
LOOK = ("anime film still, Korean folklore, Joseon dynasty era, painterly detailed background, "
        "cinematic lighting, atmospheric, ")      # look 없는 옛 대본(1~9화) — 글자 하나 안 바꾼다(그림 캐시·화풍 유지)
# 화풍(레포 변수 TALES_STYLE): anime(기본 — 구미 초상화와 같은 결) | film(영화 같은 반실사). 10/5 같은 장면 비교:
#   C:\wbtmpench\look\compare.jpg — 옛 화풍은 현대 엘리베이터를 한옥 마당에, 손톱 깎는 사람을 한복 차림으로 그렸다.
STYLES = {
    "anime": ("anime film still, ", "painterly detailed background, cinematic lighting, atmospheric, "),
    "film": ("cinematic horror film still, ", "digital painting, moody low-key lighting, shallow depth of field, atmospheric, "),
}
STYLE_HEAD, STYLE_TAIL = STYLES.get(os.environ.get("TALES_STYLE", "anime"), STYLES["anime"])


def look_prefix(look: str | None) -> str:
    """그림 프롬프트 앞에 붙는 화풍 + 시대. look 은 대본(또는 장면)의 'look' — tales.LOOKS 키."""
    if not look:
        return LOOK
    return STYLE_HEAD + T.LOOKS[look] + STYLE_TAIL
ASSETS = os.path.join(GUMIHO, "assets", "tales")
GOLD, RED, CREAM = (236, 196, 110), (214, 52, 40), (246, 238, 222)
SHORT_MAX = 59.0


# ── 글꼴 ──────────────────────────────────────────────
# ★2026-09-30: 우분투 fonts-noto-core 에는 NotoSans Regular/Bold 뿐이라 Black 이 없었다 → 기본 비트맵 글꼴로 떨어져
#   2화 썸네일 큰 글자·쇼츠 자막이 깨알만 하게 나갔다. Black 은 fonts-noto-extra 에 있다(워크플로가 설치).
#   그래도 없으면 ExtraBold → Bold → DejaVu 순으로 내려가고, 하나도 없으면 ★멈춘다(조용히 기본 글꼴 금지).
_NOTO = "/usr/share/fonts/truetype/noto"
_DEJAVU_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONTS = {
    "sans": [f"{_NOTO}/NotoSans-Black.ttf", f"{_NOTO}/NotoSans-ExtraBold.ttf", f"{_NOTO}/NotoSans-Bold.ttf",
             _DEJAVU_B, r"C:\Windows\Fonts\NotoSansKR-VF.ttf", r"C:\Windows\Fonts\arialbd.ttf"],
    "sans_bold": [f"{_NOTO}/NotoSans-Bold.ttf", _DEJAVU_B, r"C:\Windows\Fonts\NotoSansKR-VF.ttf",
                  r"C:\Windows\Fonts\arialbd.ttf"],
    "serif": [f"{_NOTO}/NotoSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              r"C:\Windows\Fonts\georgiab.ttf", r"C:\Windows\Fonts\NotoSerifKR-VF.ttf"],
    # 한글·한자 주석(여우구슬 · 九尾狐)
    "cjk": ["/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", r"C:\Windows\Fonts\NotoSansKR-VF.ttf",
            r"C:\Windows\Fonts\malgunbd.ttf"],
}
_WEIGHT = {"sans": 900, "sans_bold": 700, "serif": 700, "cjk": 700}
_fc: dict = {}


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    k = (kind, size)
    if k not in _fc:
        f = None
        for p in _FONTS[kind]:
            if os.path.exists(p):
                f = ImageFont.truetype(p, size)
                if p.endswith("-VF.ttf"):
                    try:
                        f.set_variation_by_axes([_WEIGHT[kind]])
                    except Exception:  # noqa: BLE001
                        pass
                break
        if f is None:
            raise RuntimeError(f"글꼴 '{kind}' 없음 — {_FONTS[kind][:3]} (fonts-noto-extra·fonts-nanum 설치 확인)")
        _fc[k] = f
    return _fc[k]


def font_path(kind: str) -> str | None:
    return next((p for p in _FONTS[kind] if os.path.exists(p)), None)


def needs_cjk(t: str) -> bool:
    return any(ord(c) > 0x2FFF for c in t)


def wrap(d: ImageDraw.ImageDraw, text: str, f, width: int) -> list[str]:
    out, cur = [], ""
    for w_ in text.split():
        t = f"{cur} {w_}".strip()
        if cur and d.textlength(t, font=f) > width:
            out.append(cur)
            cur = w_
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


# ── 도구 ──────────────────────────────────────────────
def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore  # 로컬 테스트용(러너에는 apt ffmpeg)
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def sh(cmd: list, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(map(str, cmd))[:240]}\n{r.stderr[-1200:]}")
    return r


def h16(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def wav_read(p: str):
    import numpy as np
    with wave.open(p) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    assert (sr, ch, sw) == (SR, 1, 2), f"{p}: {sr}/{ch}/{sw}"
    return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0


def wav_write(p: str, x):
    import numpy as np
    y = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(p, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(y.tobytes())


# ── ① 장면 목록 ───────────────────────────────────────
def plan(s: dict) -> list[dict]:
    shots = []
    for i, x in enumerate(s["scenes"]):
        kind = "card" if x.get("card") else ("gumi" if x.get("gumi") else "img")
        shots.append({
            "i": i, "kind": kind, "say": x.get("say", ""), "img": x.get("img"), "gumi": x.get("gumi"),
            "card": x.get("card"), "sub": x.get("sub", ""), "note": x.get("note", ""),
            "fx": x.get("fx") or ("embers" if kind != "img" else "dust"),
            "move": "in" if kind == "card" else (x.get("move") or T.MOVES[i % len(T.MOVES)]),
            "hold": float(x.get("hold", 0)), "key": x.get("key")})
    return shots


# ── ② 목소리 ──────────────────────────────────────────
def _fake_tts(text: str, out: str, voice: str) -> bool:
    """테스트용: 단어 수에 비례한 조용한 톤."""
    import numpy as np
    n = int(SR * max(0.6, len(text.split()) / (T.WPM / 60)))
    t = np.arange(n) / SR
    wav_write(out, 0.05 * np.sin(2 * math.pi * 220 * t))
    return True


def synth(texts: list[str], wd: str, mock: bool = False) -> dict:
    """문장 → (정규화·속도 적용된) wav 경로. 캐시: 목소리+문장+속도."""
    os.makedirs(wd, exist_ok=True)
    if mock:
        tts = _fake_tts
    else:
        import wbspark
        tts = lambda text, out, voice: wbspark.tts(text, out, voice, timeout_sec=900)  # noqa: E731
    ff = ffmpeg()
    todo = list(dict.fromkeys(t for t in texts if t))

    def one(text):
        key = h16(T.VOICE, text, TEMPO, mock)
        out = os.path.join(wd, f"v_{key}.wav")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return text, out
        raw = out[:-4] + "_raw.wav"
        for attempt in range(4):
            if tts(text, raw, T.VOICE):
                break
            time.sleep(5 + attempt * 10)
        else:
            return text, None
        af = f"atempo={TEMPO}," if abs(TEMPO - 1) > 1e-3 and not mock else ""
        sh([ff, "-y", "-loglevel", "error", "-i", raw, "-af",
            f"{af}silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
            f"silenceremove=start_periods=1:start_threshold=-50dB,areverse",
            "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])
        os.remove(raw)
        return text, out

    t0, got, failed = time.time(), {}, []
    with cf.ThreadPoolExecutor(1 if mock else WORKERS) as ex:
        for n, (text, out) in enumerate(ex.map(one, todo), 1):
            got[text] = out
            if out is None:
                failed.append(text[:40])
            if n % 15 == 0 or n == len(todo):
                print(f"   🎙️ 목소리 {n}/{len(todo)} · 실패 {len(failed)} · {time.time() - t0:.0f}s", flush=True)
    if failed:
        raise RuntimeError(f"목소리 합성 실패 {len(failed)}건: {failed[:3]}")
    return got


def wav_dur(p: str) -> float:
    with wave.open(p) as w:
        return w.getnframes() / float(w.getframerate())


# ── ③ 그림 ────────────────────────────────────────────
def spark_wait():
    """공용 서버 — 앞에 기다리는 작업이 많으면 줄어들 때까지 기다린다(최대 20분)."""
    try:
        import requests
        import wbspark
        for _ in range(60):
            q = requests.get(f"{wbspark._base()}/queue", timeout=15).json()
            if int(q.get("waiting", 0)) <= SPARK_MAX_WAITING:
                return
            print(f"   ⏳ Spark 대기열 {q.get('waiting')} — 20초 쉼", flush=True)
            time.sleep(20)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 대기열 확인 실패(계속): {e}")


def gen_image(prompt: str, out_png: str, mock: bool = False, seed: int = 0, look: str = LOOK) -> bool:
    if mock:
        rnd = random.Random(prompt)
        im = Image.new("RGB", (1216, 832), tuple(rnd.randint(30, 200) for _ in range(3)))
        d = ImageDraw.Draw(im)
        for k in range(12):
            x = rnd.randint(0, 1216)
            d.ellipse([x - 80, 300 + k * 20, x + 80, 460 + k * 20], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
        im.save(out_png)
        return True
    import wbspark
    for attempt in range(3):
        spark_wait()
        if wbspark.generate_image(look + prompt, out_png, aspect="16:9", no_llm=True,
                                  model=IMG_MODEL or None, timeout_sec=900):
            return True
        time.sleep(10 + attempt * 20)
    try:                                   # 폴백: NVIDIA 무료 FLUX
        import imagegen
        return bool(imagegen.flux_image(look + prompt, out_png, 1344, 768, seed=seed))
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ FLUX 폴백 실패: {e}")
    return False


def prepare(src: str, dst: str, size=(PW, PH)):
    """켄 번스용: 목표보다 ZOOM 배 크게 채워 자르고 살짝 선명하게."""
    im = ImageOps.fit(Image.open(src).convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.45))
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
    im.save(dst, "JPEG", quality=93)


def card_image(sh_: dict, bg: str | None, out: str):
    """장 카드: 다음 장면 그림을 어둡게 흐린 배경 + 금색 번호 + 흰 제목(준비 그림 크기로)."""
    if bg and os.path.exists(bg):
        img = Image.open(bg).convert("RGB").resize((PW, PH)).filter(ImageFilter.GaussianBlur(18))
        img = ImageEnhance.Brightness(img).enhance(0.28)
    else:
        img = Image.new("RGB", (PW, PH), (14, 10, 14))
    d = ImageDraw.Draw(img)
    cx, cy = PW / 2, PH / 2
    big = sh_["card"]
    fb = font("serif", 150 if len(big) <= 4 else 118)
    tw = d.textlength(big, font=fb)
    has_sub = bool(sh_.get("sub"))
    y0 = cy - (150 if has_sub else 80)
    d.text((cx - tw / 2, y0), big, font=fb, fill=GOLD)
    if has_sub:
        # 가는 장식선
        d.line([(cx - 260, y0 + 200), (cx - 40, y0 + 200)], fill=GOLD, width=2)
        d.line([(cx + 40, y0 + 200), (cx + 260, y0 + 200)], fill=GOLD, width=2)
        d.ellipse([cx - 8, y0 + 192, cx + 8, y0 + 208], outline=GOLD, width=2)
        fs = font("serif", 84)
        for k, ln in enumerate(wrap(d, sh_["sub"], fs, PW - 400)[:2]):
            d.text((cx - d.textlength(ln, font=fs) / 2, y0 + 240 + k * 104), ln, font=fs, fill=CREAM)
    img.save(out, "JPEG", quality=93)


def make_images(s: dict, shots: list[dict], wd: str, mock: bool = False) -> dict:
    os.makedirs(wd, exist_ok=True)
    prompts = list(dict.fromkeys(x["img"] for x in shots if x["kind"] == "img"))
    prompts.append(s["thumb"]["img"])
    # 장면별 look(현대 이야기 속 회상 장면 등) — 없으면 대본 look, 그것도 없으면 옛 조선 화풍(LOOK)
    scene_look = {x["img"]: x.get("look") for x in (s.get("scenes") or []) if x.get("img") and x.get("look")}
    if s.get("id", 0) < T.GLOBAL_FROM:      # 실험 주간(3~9화)은 대본에 look 이 있어도 예전 화풍 — 형식만 비교한다
        scene_look, s = {}, dict(s, look=None)
    raw = {}
    t0 = time.time()
    for n, p in enumerate(prompts, 1):
        lp = look_prefix(scene_look.get(p) or s.get("look"))
        out = os.path.join(wd, f"raw_{h16(lp, p, mock)}.png")
        if not (os.path.exists(out) and os.path.getsize(out) > 10000):
            if not gen_image(p, out, mock, seed=n, look=lp):
                raise RuntimeError(f"그림 실패: {p[:60]}")
        raw[p] = out
        if n % 5 == 0 or n == len(prompts):
            print(f"   🖼️ 그림 {n}/{len(prompts)} · {time.time() - t0:.0f}s", flush=True)
    for x in shots:
        if x["kind"] == "img":
            x["raw"] = raw[x["img"]]
        elif x["kind"] == "gumi":
            x["raw"] = os.path.join(ASSETS, f"gumi_{x['gumi']}.jpg")
    for x in shots:
        if x["kind"] == "card":
            continue
        x["prep"] = os.path.join(wd, f"prep_{h16(x['raw'], PW)}.jpg")
        if not os.path.exists(x["prep"]):
            prepare(x["raw"], x["prep"])
    for k, x in enumerate(shots):
        if x["kind"] == "card":
            nxt = next((y.get("prep") for y in shots[k + 1:] if y.get("prep")), None)
            x["prep"] = os.path.join(wd, f"card_{k:02d}.jpg")
            card_image(x, nxt, x["prep"])
    return {"thumb_raw": raw[s["thumb"]["img"]], "images": len(prompts)}


# ── 타임라인 ──────────────────────────────────────────
def timeline(shots: list[dict], voices: dict) -> float:
    t = 0.0
    for x in shots:
        x["start"] = round(t, 3)
        if x["kind"] == "card":
            x["dur"] = CARD_SEC
        else:
            x["wav"] = voices[x["say"]]
            x["vdur"] = wav_dur(x["wav"])
            x["dur"] = round(LEAD + x["vdur"] + GAP + x["hold"], 3)
        t += x["dur"]
    shots[-1]["dur"] += 1.0                      # 끝 여운(검은 화면으로 사라짐)
    return round(t + 1.0, 3)


# ── ④ 화면 ────────────────────────────────────────────
class FX:
    """입자 — 시간 t 의 함수(결정론적). RGBA 채우기로 RGB 프레임 위에 바로 그린다."""

    def __init__(self, w: int, h: int, seed: int = 7):
        self.w, self.h = w, h
        r = random.Random(seed)
        self.p = {
            "dust": [(r.random(), r.random(), r.uniform(0.004, 0.012), r.uniform(1.0, 2.6), r.randint(40, 110),
                      r.uniform(0, 6.3)) for _ in range(46)],
            "embers": [(r.uniform(0.15, 0.85), r.random(), r.uniform(0.04, 0.09), r.uniform(1.6, 3.6),
                        r.uniform(10, 45), r.uniform(0, 6.3)) for _ in range(60)],
            "snow": [(r.random(), r.random(), r.uniform(0.05, 0.12), r.uniform(1.6, 4.2), r.randint(140, 225),
                      r.uniform(0, 6.3)) for _ in range(170)],
            "rain": [(r.random(), r.random(), r.uniform(0.9, 1.5), r.uniform(28, 70), r.randint(40, 90), 0)
                     for _ in range(200)],
            "fireflies": [(r.random(), r.uniform(0.25, 0.95), r.uniform(0.3, 0.9), r.uniform(2.5, 4.5),
                           r.uniform(20, 70), r.uniform(0, 6.3)) for _ in range(34)],
        }
        # 안개: 작은 잡음 → 크게 → 흐림(가로로 두 배, 천천히 흐른다)
        n = Image.effect_noise((48, 14), 90).resize((w * 2, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
        self.fog = ImageOps.autocontrast(n).point(lambda v: int(max(0, v - 90) * 0.55))
        self.fog_color = Image.new("RGB", (w, h), (196, 206, 222))

    def draw(self, img: Image.Image, kind: str, t: float):
        if kind in ("none", None):
            return img
        w, h = self.w, self.h
        if kind == "fog":
            off = int((t * 26) % w)
            m = self.fog.crop((off, 0, off + w, h))
            img = Image.composite(self.fog_color, img, m)
            kind = "dust"
        d = ImageDraw.Draw(img, "RGBA")
        if kind == "dust":
            for x0, y0, sp, r_, a, ph in self.p["dust"]:
                x = (x0 + sp * t * 0.6) % 1 * w + 14 * math.sin(t * 0.5 + ph)
                y = (y0 - sp * t * 0.35) % 1 * h
                d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(255, 238, 205, a))
        elif kind == "embers":
            for x0, y0, sp, r_, amp, ph in self.p["embers"]:
                u = (y0 + sp * t) % 1
                y = h * 1.02 - u * h * 0.9
                x = x0 * w + amp * math.sin(t * 1.3 + ph)
                a = int(220 * (1 - u) ** 1.4 * (0.75 + 0.25 * math.sin(t * 9 + ph)))
                d.ellipse([x - r_ * 2.6, y - r_ * 2.6, x + r_ * 2.6, y + r_ * 2.6], fill=(255, 120, 40, a // 6))
                d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(255, 176, 80, a))
        elif kind == "snow":
            for x0, y0, sp, r_, a, ph in self.p["snow"]:
                y = (y0 + sp * t) % 1 * (h + 20) - 10
                x = (x0 * w + 30 * math.sin(t * 0.8 + ph) + t * 12) % w
                d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(250, 250, 255, a))
        elif kind == "rain":
            for x0, y0, sp, ln, a, _ in self.p["rain"]:
                y = (y0 + sp * t) % 1 * (h + 80) - 80
                x = (x0 * w + y * 0.12) % w
                d.line([(x, y), (x + ln * 0.12, y + ln)], fill=(200, 215, 235, a), width=2)
        elif kind == "fireflies":
            for x0, y0, sp, r_, amp, ph in self.p["fireflies"]:
                x = x0 * w + amp * math.sin(t * sp + ph)
                y = y0 * h + amp * 0.5 * math.sin(t * sp * 1.3 + ph * 2)
                a = int(230 * max(0.0, math.sin(t * sp * 2 + ph)) ** 2)
                d.ellipse([x - r_ * 3, y - r_ * 3, x + r_ * 3, y + r_ * 3], fill=(220, 255, 140, a // 6))
                d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(230, 255, 160, a))
        return img


def vignette(w: int, h: int) -> Image.Image:
    m = Image.radial_gradient("L").resize((w, h), Image.BICUBIC)       # 가운데 0 → 가장자리 255
    m = m.point(lambda v: int(255 - min(255, max(0, (v - 110) * 0.9))))
    return Image.merge("RGB", (m, m, m))


def note_band(text: str) -> Image.Image:
    f = font("cjk" if needs_cjk(text) else "sans_bold", 44)
    tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = int(tmp.textlength(text, font=f))
    band = Image.new("RGBA", (tw + 90, 92), (0, 0, 0, 0))
    d = ImageDraw.Draw(band)
    d.rounded_rectangle([0, 0, tw + 89, 91], 16, fill=(12, 8, 12, 190), outline=GOLD + (230,), width=2)
    d.text((45, 18), text, font=f, fill=CREAM)
    return band


def ease(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 0.7 * p + 0.3 * (0.5 - 0.5 * math.cos(math.pi * p))


def cam(move: str, p: float, pw: int, ph: int, ow: int, oh: int, zmax: float) -> tuple:
    """(가로 자르기 폭, 중심 x, 중심 y) — 준비 그림 좌표계. p: 0→1 진행."""
    e = ease(p)
    if move in ("in", "out"):
        z = 1 + (zmax - 1) * (e if move == "in" else 1 - e)
        return pw / z, pw / 2, ph / 2
    z = 1 + (zmax - 1) * 0.6
    cw, ch = pw / z, ph / z
    ox, oy = (pw - cw) / 2, (ph - ch) / 2
    k = (e - 0.5) * 2                               # -1 → 1
    if move == "right":
        return cw, pw / 2 + ox * k, ph / 2
    if move == "left":
        return cw, pw / 2 - ox * k, ph / 2
    if move == "down":
        return cw, pw / 2, ph / 2 + oy * k
    return cw, pw / 2, ph / 2 - oy * k               # up


def view(img: Image.Image, cw: float, cx: float, cy: float, ow: int, oh: int) -> Image.Image:
    s = cw / ow
    ch = oh * s
    return img.transform((ow, oh), Image.AFFINE, (s, 0, cx - cw / 2, 0, s, cy - ch / 2), resample=Image.BILINEAR)


class Painter:
    """plan(JSON) → 시각 t 의 프레임. 프로세스마다 하나씩 만든다."""

    def __init__(self, P: dict):
        self.P = P
        self.shots = P["shots"]
        self.starts = [x["start"] for x in self.shots]
        self.total = P["total"]
        # 수면판(sleep.py)은 전환을 길게·화면을 어둡게·끝을 길게 사라지게 한다 — 본편은 기본값 그대로
        self.xf = float(P.get("xf", XF))
        self.dim = float(P.get("dim", 1.0))
        self.fade_out = float(P.get("fade_out", 1.2))
        self.fx = FX(W, H)
        self.vig = vignette(W, H)
        self._img: dict = {}
        self._note: dict = {}

    def img(self, path: str) -> Image.Image:
        if path not in self._img:
            if len(self._img) > 4:
                self._img.pop(next(iter(self._img)))
            self._img[path] = Image.open(path).convert("RGB")
        return self._img[path]

    def shot(self, k: int, t: float) -> Image.Image:
        x = self.shots[k]
        p = (t - x["start"] + self.xf / 2) / (x["dur"] + self.xf)
        zmax = 1.035 if x["kind"] == "card" else ZOOM
        cw, cx, cy = cam(x["move"], p, PW, PH, W, H, zmax)
        fr = view(self.img(x["prep"]), cw, cx, cy, W, H)
        fr = self.fx.draw(fr, x["fx"], t)
        if x.get("note"):
            if k not in self._note:
                self._note[k] = note_band(x["note"])
            band = self._note[k]
            lt = t - x["start"]
            a = min(1.0, max(0.0, (lt - 0.6) / 0.4)) * min(1.0, max(0.0, (x["dur"] - lt - 0.3) / 0.4))
            if a > 0:
                m = band.getchannel("A").point(lambda v: int(v * a))
                fr.paste(band.convert("RGB"), ((W - band.width) // 2, H - 190), m)
        return fr

    def frame(self, t: float) -> Image.Image:
        k = max(0, bisect.bisect_right(self.starts, t) - 1)
        x = self.shots[k]
        end = x["start"] + x["dur"]
        xf = self.xf
        if k > 0 and t < x["start"] + xf / 2:
            a = (t - (x["start"] - xf / 2)) / xf
            fr = Image.blend(self.shot(k - 1, t), self.shot(k, t), a)
        elif k + 1 < len(self.shots) and t >= end - xf / 2:
            a = (t - (end - xf / 2)) / xf
            fr = Image.blend(self.shot(k, t), self.shot(k + 1, t), a)
        else:
            fr = self.shot(k, t)
        fr = ImageChops.multiply(fr, self.vig)
        fade = min(1.0, t / 0.6, max(0.0, (self.total - t) / self.fade_out)) * self.dim
        if fade < 1:
            fr = ImageEnhance.Brightness(fr).enhance(max(0.0, fade))
        return fr


def _encode_part(args):
    plan_path, f0, f1, out = args
    with open(plan_path, encoding="utf-8") as f:
        P = json.load(f)
    pa = Painter(P)
    proc = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "20", "-pix_fmt", "yuv420p", "-g", str(FPS * 2), out], stdin=subprocess.PIPE)
    for n in range(f0, f1):
        proc.stdin.write(pa.frame(n / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg 구간 인코딩 실패 {f0}-{f1}")
    return out


def render_video(P: dict, wd: str, out_silent: str, procs: int | None = None):
    plan_path = os.path.join(wd, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(P, f)
    nf = int(math.ceil(P["total"] * FPS))
    procs = procs or max(1, min(int(os.environ.get("TALES_PROCS", "0")) or (os.cpu_count() or 2), 8))
    step = int(math.ceil(nf / procs))
    parts = [(plan_path, a, min(nf, a + step), os.path.join(wd, f"part_{k:02d}.mp4"))
             for k, a in enumerate(range(0, nf, step))]
    t0 = time.time()
    if procs == 1:
        for p in parts:
            _encode_part(p)
    else:
        with mp.get_context("spawn").Pool(procs) as pool:
            pool.map(_encode_part, parts)
    lst = os.path.join(wd, "parts.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p[3])}'\n")
    sh([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_silent])
    print(f"   🎞️ 프레임 {nf} · 프로세스 {procs} · {time.time() - t0:.0f}s", flush=True)


# ── ⑤ 소리 ────────────────────────────────────────────
def _pluck(freq: float, sec: float, rng) -> "np.ndarray":
    """Karplus-Strong — 가야금 비슷한 뜯는 소리(블록 단위로 벡터화)."""
    import numpy as np
    n, N = int(SR * sec), max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, N).astype("float32")
    buf = np.convolve(buf, np.ones(3) / 3, mode="same").astype("float32")   # 조금 부드럽게
    out = np.empty(n + N, dtype="float32")
    out[:N] = buf
    k = N
    while k < n:
        prev = out[k - N:k]
        blk = 0.996 * 0.5 * (prev + np.roll(prev, 1))
        m = min(N, n + N - k)
        out[k:k + m] = blk[:m]
        k += N
    y = out[:n]
    return y * np.exp(-np.arange(n) / (SR * sec * 0.45)).astype("float32")


def bed(n: int, seed: int, plucks: bool = True):
    """배경음: 낮은 드론(D) + 바람 + 드문드문 오음계 뜯는 소리. 전부 코드로 만든다(저작권 없음)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    y = np.zeros(n, dtype="float32")
    blk = SR * 20
    tones = [(73.42, 0.5, 0.031), (73.9, 0.34, 0.047), (110.0, 0.26, 0.023), (146.83, 0.14, 0.057), (220.0, 0.05, 0.071)]
    ph = rng.uniform(0, 6.28, len(tones))
    for a in range(0, n, blk):
        t = (np.arange(a, min(n, a + blk)) / SR).astype("float64")
        seg = np.zeros(len(t))
        for (f, amp, lfo), p in zip(tones, ph):
            seg += amp * np.sin(2 * np.pi * f * t + p) * (0.62 + 0.38 * np.sin(2 * np.pi * lfo * t + p * 3))
        y[a:a + len(t)] = seg.astype("float32")
    # 바람: 30초 원형 잡음을 주파수 영역에서 저역 통과(원형이라 이어 붙여도 이음새가 없다)
    L = SR * 30
    spec = np.fft.rfft(rng.standard_normal(L))
    fr = np.fft.rfftfreq(L, 1 / SR)
    spec *= 1 / (1 + (fr / 260) ** 2)
    wind = np.fft.irfft(spec, L).astype("float32")
    wind /= np.abs(wind).max() + 1e-9
    reps = int(math.ceil(n / L))
    wind = np.tile(wind, reps)[:n]
    t = np.arange(n, dtype="float32") / SR
    wind *= (0.55 + 0.45 * np.sin(2 * np.pi * 0.05 * t + 1.0)).astype("float32")
    y = y / (np.abs(y).max() + 1e-9) * 0.55 + wind * 0.35
    if plucks:
        notes = [146.83, 174.61, 196.0, 220.0, 261.63, 293.66, 349.23]
        tt = 4.0
        while tt < n / SR - 4:
            f = notes[int(rng.integers(len(notes)))]
            p = _pluck(f, 3.2, rng) * 0.22
            a = int(tt * SR)
            y[a:a + len(p)] += p[: max(0, n - a)]
            tt += float(rng.uniform(6, 12))
    return y


def boom(rng) -> "np.ndarray":
    import numpy as np
    n = int(SR * 2.2)
    t = np.arange(n) / SR
    f = 38 + 34 * np.exp(-t * 2.2)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.8)
    hit = rng.standard_normal(n) * np.exp(-t * 30) * 0.3
    return ((y + hit) * 0.55).astype("float32") + _pluck(146.83, 2.2, rng) * 0.3


def movavg(x, win: int):
    """이동 평균(누적합 — 길이 n 에 선형. np.convolve 는 10분짜리에 몇 시간 걸린다)."""
    import numpy as np
    c = np.cumsum(np.concatenate([[0.0], x.astype("float64")]))
    half = win // 2
    idx = np.arange(len(x))
    a = np.clip(idx - half, 0, len(x))
    b = np.clip(idx + half + 1, 0, len(x))
    return ((c[b] - c[a]) / np.maximum(1, b - a)).astype("float32")


def build_audio(shots: list[dict], total: float, out_m4a: str, wd: str, seed: int = 1):
    import numpy as np
    n = int(total * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for x in shots:
        if x.get("wav"):
            v = wav_read(x["wav"])
            a = int((x["start"] + LEAD) * SR)
            voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = bed(n, seed)
    b *= vr * 0.13 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)          # 말 사이 약 -18dB(9/29 1화 실측 -16dB → 조금 낮춤)
    # 덕킹: 말하는 동안 배경을 한 번 더 낮춘다(0.25초 창 → 부드럽게)
    win = int(SR * 0.25)
    env = movavg(np.abs(voice), win)
    duck = movavg(1 - 0.45 * np.clip(env / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
    rng = np.random.default_rng(seed + 1)
    sfx = np.zeros(n, dtype="float32")
    for x in shots:
        if x["kind"] == "card":
            bm = boom(rng) * vr * 2.2
            a = int(x["start"] * SR)
            sfx[a:a + len(bm)] += bm[: max(0, n - a)]
    mix = voice + b * duck + sfx
    # 앞뒤 페이드
    fin, fout = int(SR * 0.6), int(SR * 1.5)
    mix[:fin] *= np.linspace(0, 1, fin, dtype="float32")
    mix[-fout:] *= np.linspace(1, 0, fout, dtype="float32")
    mix = mix[: int(total * SR)]
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    wav_write(raw, mix)
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", out_m4a])


def mux(video: str, audio: str, out: str):
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", video, "-i", audio, "-c:v", "copy", "-c:a", "copy",
        "-shortest", "-movflags", "+faststart", out])


# ── 자막 ──────────────────────────────────────────────
def srt_time(sec: float) -> str:
    ms = int(round(max(0.0, sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s_, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"


def split_cues(text: str, limit: int = 84) -> list[str]:
    import re
    out = []
    for sent in [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]:
        while len(sent) > limit:
            cut = sent.rfind(", ", 0, limit)
            cut = cut + 1 if cut > limit // 3 else sent.rfind(" ", 0, limit)
            out.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        out.append(sent)
    return out


def build_srt(shots: list[dict], out: str) -> int:
    n = 0
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for x in shots:
            if not x.get("wav"):
                continue
            cues = split_cues(x["say"])
            tot = sum(len(c) for c in cues) or 1
            t = x["start"] + LEAD
            for c in cues:
                d = x["vdur"] * len(c) / tot
                n += 1
                f.write(f"{n}\n{srt_time(t)} --> {srt_time(t + d)}\n{c}\n\n")
                t += d
    return n


# ── 썸네일 ────────────────────────────────────────────
def thumbnail(s: dict, raw: str, out: str):
    tw_, th_ = 1280, 720
    base = ImageOps.fit(Image.open(raw).convert("RGB"), (tw_, th_), Image.LANCZOS, centering=(0.5, 0.45))
    # 주인공(대개 그림 가운데)을 오른쪽으로 밀어 왼쪽을 글자 자리로 비운다 — 빈 곳은 가장자리를 뒤집어 흐려 채운다
    sh_x = 300
    img = Image.new("RGB", (tw_, th_))
    img.paste(base.crop((0, 0, tw_ - sh_x, th_)), (sh_x, 0))
    img.paste(base.crop((0, 0, sh_x, th_)).transpose(Image.FLIP_LEFT_RIGHT), (0, 0))
    ramp = Image.new("L", (tw_, th_), 0)
    rd = ImageDraw.Draw(ramp)
    for x in range(sh_x + 80):                       # 왼쪽은 흐리게, 이음새 둘레 80px 에서 서서히 선명하게
        rd.line([(x, 0), (x, th_)], fill=int(255 * min(1.0, max(0.0, (sh_x + 80 - x) / 160))))
    img = Image.composite(img.filter(ImageFilter.GaussianBlur(14)), img, ramp)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.15)
    grad = Image.linear_gradient("L").rotate(90, expand=True).resize((tw_, th_))   # 왼쪽 255 → 오른쪽 0
    grad = grad.point(lambda v: int(max(0, v - 70) * 1.05))
    img = Image.composite(Image.new("RGB", (tw_, th_), (8, 4, 8)), img, grad)
    d = ImageDraw.Draw(img)
    text = s["thumb"]["text"].upper()
    words_ = text.split()
    mid = max(1, (len(words_) + 1) // 2)
    lines = [" ".join(words_[:mid]), " ".join(words_[mid:])] if len(words_) > 1 else [text]
    lines = [ln for ln in lines if ln]
    size = 168
    while size > 70:
        f = font("sans", size)
        if max(d.textlength(ln, font=f) for ln in lines) <= 690 and len(lines) * size * 1.02 <= 470:
            break
        size -= 6
    f = font("sans", size)
    y = (th_ - len(lines) * size * 1.02) / 2 + 20
    for k, ln in enumerate(lines):
        col = (255, 255, 255) if k < len(lines) - 1 else (255, 214, 77)
        d.text((56, y), ln, font=f, fill=col, stroke_width=max(6, size // 18), stroke_fill=(0, 0, 0))
        y += size * 1.02
    # 태그
    tag = f"KOREAN LEGEND · TALE {s['id']:03d}"
    ft = font("sans_bold", 34)
    tl = d.textlength(tag, font=ft)
    d.rounded_rectangle([50, 44, 50 + tl + 40, 100], 12, fill=RED)
    d.text((70, 50), tag, font=ft, fill=(255, 255, 255))
    # 구미 배지(오른쪽 아래)
    g = Image.open(os.path.join(ASSETS, "gumi_wink.jpg")).convert("RGB")
    g = g.crop((g.width * 0.28, 0, g.width * 0.72, g.height * 0.64)).resize((210, 210), Image.LANCZOS)
    m = Image.new("L", (210, 210), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 209, 209], fill=255)
    bx, by = tw_ - 250, th_ - 250
    d.ellipse([bx - 8, by - 8, bx + 218, by + 218], fill=RED)
    img.paste(g, (bx, by), m)
    img.save(out, "JPEG", quality=92)
    return out


# ── 쇼츠 ──────────────────────────────────────────────
def short_hook(s: dict) -> str:
    """쇼츠 위에 끝까지 떠 있는 두 줄 제목. short.hook 이 없으면 썸네일 문구."""
    return (s["short"].get("hook") or s["thumb"]["text"]).upper()


def short_plan(s: dict, shots: list[dict], voices: dict, wd: str, thumb_raw: str | None = None) -> dict:
    """첫 줄 그림은 썸네일 그림(이 편에서 가장 강한 그림)으로 바꾼다.

    1화 쇼츠(2026-09-30): 첫 화면이 산길에 선 평범한 소녀 + 'In Korea,' → 계속 시청함 11.9%.
    피드에서 첫 1초에 멈추게 하는 건 그림과 위 제목이다.
    """
    by_key = {x["key"]: x for x in shots if x.get("key")}
    rows, t = [], 0.25
    for j, ln in enumerate(s["short"]["lines"]):
        if j == 0 and thumb_raw and not ln.get("gumi"):
            raw = thumb_raw
        elif ln.get("scene"):
            raw = by_key[ln["scene"]]["raw"]
        elif ln.get("gumi"):
            raw = os.path.join(ASSETS, f"gumi_{ln['gumi']}.jpg")
        else:
            raw = next(x["raw"] for x in shots if x.get("img") == ln["img"])
        v = voices[ln["say"]]
        d = wav_dur(v)
        rows.append({"say": ln["say"], "raw": raw, "wav": v, "start": round(t, 3), "vdur": d,
                     "dur": round(d + 0.3, 3), "gumi": bool(ln.get("gumi")), "dir": 1 if j % 2 == 0 else -1,
                     "hook": raw == thumb_raw})
        t += d + 0.3
    total = round(t + 0.9, 3)
    rows[-1]["dur"] += 0.9
    return {"rows": rows, "total": total}


def caption_chunks(text: str, max_words: int = 3, max_chars: int = 16) -> list[str]:
    out, cur = [], []
    for w_ in text.split():
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w_])) > max_chars):
            out.append(" ".join(cur))
            cur = []
        cur.append(w_)
        if w_.endswith((".", "?", "!", ",", ":")):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


class ShortPainter:
    def __init__(self, SP: dict, s: dict):
        self.SP, self.s = SP, s
        self.rows = SP["rows"]
        self.starts = [r["start"] for r in self.rows]
        self.fx = FX(SW, SH, seed=3)
        self.vig = vignette(SW, SH)
        self.imgs = {}
        for r in self.rows:
            if r["raw"] not in self.imgs:
                im = Image.open(r["raw"]).convert("RGB")
                sc = SH * 1.06 / im.height
                self.imgs[r["raw"]] = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
            r["chunks"] = caption_chunks(r["say"])
        self.fcap = font("sans", 92)
        self.ftop = font("sans_bold", 34)
        self.fhook = font("sans", 104)
        self.hook_lines = self._hook_lines(short_hook(s))

    def _hook_lines(self, text: str) -> list[str]:
        """두 줄로 고르게 나눈다('SHE ATE THEM / ALL' 처럼 한 단어만 떨어지지 않게), 들어가는 가장 큰 글자."""
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        ws = text.split()
        for size in (124, 112, 100, 90, 80, 70):
            f = font("sans", size)
            cands = [[text]] if len(ws) < 3 else []
            cands += [[" ".join(ws[:k]), " ".join(ws[k:])] for k in range(1, len(ws))]
            best = min(cands, key=lambda ls: max(d.textlength(x, font=f) for x in ls))
            if max(d.textlength(x, font=f) for x in best) <= SW - 110:
                self.fhook = f
                return best
        self.fhook = font("sans", 70)
        return wrap(d, text, self.fhook, SW - 110)[:2]

    def base(self, r: dict, t: float) -> Image.Image:
        im = self.imgs[r["raw"]]
        p = ease((t - r["start"] + 0.25) / (r["dur"] + 0.5))
        span = min(im.width - SW, 900)
        cx = im.width / 2 + r["dir"] * (p - 0.5) * span
        if r["gumi"] or r.get("hook"):          # 첫 그림은 가운데(주인공)에서 천천히 다가간다
            cx = im.width / 2
        cw = SW / (1 + (0.08 if r.get("hook") else 0.04) * p)
        return view(im, cw, cx, im.height / 2, SW, SH)

    def frame(self, t: float) -> Image.Image:
        k = max(0, bisect.bisect_right(self.starts, t) - 1)
        r = self.rows[k]
        fr = self.base(r, t)
        if k > 0 and t < r["start"] + 0.2:
            fr = Image.blend(self.base(self.rows[k - 1], t), fr, (t - r["start"] + 0.2) / 0.4)
        fr = self.fx.draw(fr, "embers", t)
        fr = ImageChops.multiply(fr, self.vig)
        d = ImageDraw.Draw(fr)
        # 위: 시리즈 표시 + 끝까지 떠 있는 두 줄 제목(소리 없이 넘겨 보는 사람도 첫 프레임에 읽는다)
        top = "KOREAN LEGEND"
        tl = d.textlength(top, font=self.ftop)
        d.rounded_rectangle([(SW - tl) / 2 - 24, 150, (SW + tl) / 2 + 24, 206], 12, fill=RED)
        d.text(((SW - tl) / 2, 157), top, font=self.ftop, fill=(255, 255, 255))
        y = 232
        lh = int(self.fhook.size * 1.12)
        for ln in self.hook_lines:
            w_ = d.textlength(ln, font=self.fhook)
            d.text(((SW - w_) / 2, y), ln, font=self.fhook, fill=(255, 255, 255), stroke_width=10,
                   stroke_fill=(0, 0, 0))
            y += lh
        # 가운데 아래: 지금 말하는 조각
        lt = t - r["start"]
        if 0 <= lt <= r["vdur"] + 0.25:
            tot = sum(len(c) for c in r["chunks"]) or 1
            acc, cur = 0.0, r["chunks"][-1]
            for c in r["chunks"]:
                acc += r["vdur"] * len(c) / tot
                if lt < acc:
                    cur = c
                    break
            lines = wrap(d, cur, self.fcap, SW - 140)
            y = 1180 - len(lines) * 55
            for ln in lines:
                w_ = d.textlength(ln, font=self.fcap)
                d.text(((SW - w_) / 2, y), ln, font=self.fcap, fill=(255, 255, 255), stroke_width=9,
                       stroke_fill=(0, 0, 0))
                y += 110
        if k == len(self.rows) - 1:
            end = "Full tale on the channel"
            fe = font("sans_bold", 46)
            el = d.textlength(end, font=fe)
            d.rounded_rectangle([(SW - el) / 2 - 30, 1420, (SW + el) / 2 + 30, 1500], 16, fill=(12, 8, 12))
            d.text(((SW - el) / 2, 1432), end, font=fe, fill=GOLD)
        fade = min(1.0, max(0.0, (self.SP["total"] - t) / 0.8))     # 첫 프레임부터 밝게(피드 자동 재생 첫 장)
        if fade < 1:
            fr = ImageEnhance.Brightness(fr).enhance(max(0.0, fade))
        return fr


def render_short(s: dict, shots: list[dict], voices: dict, wd: str, out: str, thumb_raw: str | None = None) -> dict:
    import numpy as np
    SP = short_plan(s, shots, voices, wd, thumb_raw)
    if SP["total"] > SHORT_MAX:
        raise RuntimeError(f"쇼츠 {SP['total']}초 > {SHORT_MAX}")
    pa = ShortPainter(SP, s)
    silent = os.path.join(wd, "short_silent.mp4")
    proc = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "20", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for n in range(int(math.ceil(SP["total"] * FPS))):
        proc.stdin.write(pa.frame(n / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("쇼츠 인코딩 실패")
    n = int(SP["total"] * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for r in SP["rows"]:
        v = wav_read(r["wav"])
        a = int(r["start"] * SR)
        voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = bed(n, 5, plucks=False)
    b *= vr * 0.2 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)
    rng = np.random.default_rng(9)
    bm = boom(rng) * vr * 2.0
    mix = voice + b
    mix[: len(bm)] += bm[: n]
    mix = mix[: int(SP["total"] * SR)]
    fo = int(SR * 0.8)
    mix[-fo:] *= np.linspace(1, 0, fo, dtype="float32")
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "short_mix.wav")
    wav_write(raw, mix)
    aud = os.path.join(wd, "short_audio.m4a")
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", aud])
    mux(silent, aud, out)
    return {"video": out, "sec": SP["total"], "lines": len(SP["rows"])}


# ── 미리보기(사람 확인용) ─────────────────────────────
def contact_sheet(P: dict, out: str, cols: int = 6):
    pa = Painter(P)
    shots = P["shots"]
    tw_, th_ = 480, 270
    rows = int(math.ceil(len(shots) / cols))
    sheet = Image.new("RGB", (cols * tw_, rows * th_), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for k, x in enumerate(shots):
        fr = pa.frame(x["start"] + x["dur"] / 2).resize((tw_, th_))
        sheet.paste(fr, ((k % cols) * tw_, (k // cols) * th_))
        d.text(((k % cols) * tw_ + 8, (k // cols) * th_ + 6), f"{k}", fill=(255, 255, 0))
    sheet.save(out, "JPEG", quality=80)


# ── 전체 ──────────────────────────────────────────────
def render(path: str, out_dir: str, work: str, mock: bool = False, skip_short: bool = False,
           procs: int | None = None) -> dict:
    s = T.load(path)
    errs = T.check(s, path)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stem = f"{s['id']:03d}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    shots = plan(s)
    texts = [x["say"] for x in shots if x["say"]] + [ln["say"] for ln in s["short"]["lines"]]
    # 스프린트 편(catalog.sprint)은 추가 쇼츠를 만들지 않는다 — 매일 본편이 나와 쇼츠가 너무 많아진다
    extras = [] if T.sprint_day(s["id"]) else (s.get("shorts_extra") or [])
    texts += [ln["say"] for ex in extras for ln in ex["lines"]]
    voices = synth(texts, os.path.join(wd, "tts"), mock)
    total = timeline(shots, voices)
    print(f"   ⏱️ 본편 {total / 60:.1f}분 · 장면 {len(shots)}", flush=True)
    im = make_images(s, shots, os.path.join(wd, "img"), mock)
    P = {"shots": shots, "total": total}
    base = os.path.join(out_dir, stem)
    contact_sheet(P, base + "_sheet.jpg")
    silent = os.path.join(wd, "silent.mp4")
    render_video(P, wd, silent, procs)
    audio = os.path.join(wd, "audio.m4a")
    build_audio(shots, total, audio, wd, seed=s["id"])
    mux(silent, audio, base + ".mp4")
    n_cues = build_srt(shots, base + ".srt")
    thumbnail(s, im["thumb_raw"], base + "_thumb.jpg")
    md = T.meta(s, [x["start"] for x in shots])
    res = {"stem": stem, "video": base + ".mp4", "thumb": base + "_thumb.jpg", "srt": base + ".srt",
           "sheet": base + "_sheet.jpg", "minutes": round(total / 60, 2), "cues": n_cues,
           "images": im["images"], "mock": mock, "starts": [x["start"] for x in shots], **md}
    if not skip_short:
        res["short"].update(render_short(s, shots, voices, wd, base + "_short.mp4", im["thumb_raw"]))
        # 추가 쇼츠(2026-10-01) — 첫 줄은 썸네일이 아니라 그 쇼츠가 고른 장면 그림(첫 프레임이 서로 다르게)
        for k, ex in enumerate(extras, start=2):
            wdk = os.path.join(wd, f"short{k}")
            os.makedirs(wdk, exist_ok=True)
            r = render_short(dict(s, short=ex), shots, voices, wdk, base + f"_short{k}.mp4", None)
            res["shorts_extra"][k - 2].update(r)
    with open(base + "_meta.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"✅ {base}.mp4 · {res['minutes']}분 · 그림 {im['images']} · 자막 {n_cues}"
          f"{'' if skip_short else ' · 쇼츠 ' + str(res['short'].get('sec')) + '초'} · {time.time() - t0:.0f}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Gumiho Tales 렌더")
    ap.add_argument("script")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "gumiho", "tales"))
    ap.add_argument("--work", default=os.path.join(ROOT, "output", "gumiho", ".work"))
    ap.add_argument("--mock", action="store_true", help="Spark 없이(단색 그림·가짜 목소리) — 테스트")
    ap.add_argument("--skip-short", action="store_true")
    ap.add_argument("--procs", type=int)
    a = ap.parse_args()
    render(a.script, a.out, a.work, a.mock, a.skip_short, a.procs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
