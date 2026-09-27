#!/usr/bin/env python3
"""앰비언트 영상 배경 — 정지 이미지 위에 '이음새 없는' 짧은 움직임 루프(비·눈·불티·반딧불·불빛).

왜: 정지 이미지 + 공개 음원 반복은 유튜브 수익 창출 정책의 '대량 생산·반복 콘텐츠'로 볼 여지가 있다
(Help 1311392). 8시간 영상을 프레임마다 그리면 러너에서 몇 시간이 걸리므로,
  ① LOOP_SEC 초짜리 루프를 한 번만 그리고(PIL → ffmpeg 파이프)
  ② 최종 조립에서 `-stream_loop -1 … -c copy` 로 재인코딩 없이 오디오 길이만큼 이어 붙인다.

이음새가 안 보이려면 t=0 과 t=LOOP_SEC 의 화면이 같아야 한다. 그래서 모든 움직임을 주기 함수로 만든다.
  · 떨어지는 입자: 한 루프 동안 정확히 k 바퀴(정수) 돈다 → y = (y0 + k·t/T) mod 1
  · 흔들림·깜빡임: sin(2π·m·t/T), m 은 정수
외부 의존은 Pillow 와 ffmpeg 뿐(numpy 없음).

  python ambient_motion.py --bg bg.png --kind rain --out loop.mp4        # 루프만
  python ambient_motion.py --bg bg.png --kind snow --out loop.mp4 --preview frames/  # 프레임 몇 장 저장
"""
from __future__ import annotations
import math
import os
import random
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

W, H = 1920, 1080
# 8시간을 -c copy 로 이어 붙이므로 파일 크기 = 루프 비트레이트 × 8시간. 빗줄기는 정보량이 많아
# 비트레이트가 튄다 → fps·CRF 로 누른다. 레포 변수로 조정 가능(워크플로 env 로 전달).
FPS = int(os.environ.get("AMBIENT_FPS", "12"))
LOOP_SEC = float(os.environ.get("AMBIENT_LOOP_SEC", "16"))
CRF = os.environ.get("AMBIENT_CRF", "30")
PRESET = os.environ.get("AMBIENT_PRESET", "medium")
KINDS = ("rain", "snow", "embers", "fireflies", "lights", "leaves", "dust")


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore  # 로컬 테스트용(러너에는 apt ffmpeg 가 있다)
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


# ── 입자 정의 ─────────────────────────────────────────────
def _rain(rnd: random.Random, n: int):
    ps = []
    for _ in range(n):
        ln = rnd.uniform(38, 95)
        ps.append({"x": rnd.uniform(-120, W + 40), "y0": rnd.random(), "k": rnd.randint(9, 16),
                   "len": ln, "a": rnd.randint(34, 80), "w": 1 if ln < 70 else 2})
    return ps


def _draw_rain(d: ImageDraw.ImageDraw, ps, ph: float):
    slant = 0.10                                   # 살짝 비스듬히
    for p in ps:
        y = ((p["y0"] + p["k"] * ph) % 1.0) * (H + 200) - 120
        x = p["x"] + y * slant
        d.line([(x, y), (x + p["len"] * slant, y + p["len"])], fill=(215, 225, 240, p["a"]), width=p["w"])


def _flakes(rnd: random.Random, n: int, big: float):
    return [{"x0": rnd.uniform(0, W), "y0": rnd.random(), "k": rnd.choice((1, 1, 2)),
             "r": rnd.uniform(1.2, big), "amp": rnd.uniform(8, 38), "m": rnd.choice((1, 2, 3)),
             "ph": rnd.uniform(0, 2 * math.pi), "a": rnd.randint(120, 225)} for _ in range(n)]


def _draw_flakes(d, ps, ph, color=(245, 247, 255)):
    for p in ps:
        y = ((p["y0"] + p["k"] * ph) % 1.0) * (H + 40) - 20
        x = p["x0"] + p["amp"] * math.sin(2 * math.pi * p["m"] * ph + p["ph"])
        r = p["r"]
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*color, p["a"]))


def _draw_leaves(d, ps, ph):
    for p in ps:
        y = ((p["y0"] + p["k"] * ph) % 1.0) * (H + 60) - 30
        x = p["x0"] + p["amp"] * 2 * math.sin(2 * math.pi * p["m"] * ph + p["ph"])
        ang = 2 * math.pi * p["m"] * ph + p["ph"]
        rx, ry = p["r"] * 2.2, p["r"] * 1.1 * abs(math.cos(ang)) + 1
        col = (200 + int(40 * math.sin(p["ph"])), 110 + int(40 * math.cos(p["ph"])), 40)
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=(*col, min(230, p["a"] + 20)))


def _embers(rnd, n):
    return [{"x0": rnd.uniform(W * 0.25, W * 0.75), "y0": rnd.random(), "k": rnd.choice((1, 2)),
             "r": rnd.uniform(1.8, 4.2), "amp": rnd.uniform(10, 50), "m": rnd.choice((1, 2)),
             "ph": rnd.uniform(0, 2 * math.pi)} for _ in range(n)]


def _draw_embers(d, ps, ph):
    for p in ps:
        u = (p["y0"] + p["k"] * ph) % 1.0             # 0=바닥 → 1=사라짐
        y = H * 0.95 - u * H * 0.75
        x = p["x0"] + p["amp"] * math.sin(2 * math.pi * p["m"] * ph + p["ph"])
        a = int(230 * (1 - u) ** 1.5)
        r = p["r"]
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 170, 70, a))


def _glows(rnd, n, lower=False):
    return [{"x": rnd.uniform(60, W - 60), "y": rnd.uniform(H * (0.45 if lower else 0.2), H * 0.92),
             "r": rnd.uniform(3, 7) if not lower else rnd.uniform(9, 22), "m": rnd.randint(1, 4),
             "ph": rnd.uniform(0, 2 * math.pi), "ax": rnd.uniform(10, 60), "ay": rnd.uniform(6, 30),
             "mx": rnd.randint(1, 2), "my": rnd.randint(1, 3)} for _ in range(n)]


def _draw_fireflies(d, ps, ph):
    for p in ps:
        x = p["x"] + p["ax"] * math.sin(2 * math.pi * p["mx"] * ph + p["ph"])
        y = p["y"] + p["ay"] * math.sin(2 * math.pi * p["my"] * ph + p["ph"] * 1.3)
        a = int(max(0.0, math.sin(2 * math.pi * p["m"] * ph + p["ph"])) ** 2 * 230)
        for rr, aa in ((p["r"] * 3, a // 6), (p["r"], a)):
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(215, 255, 120, aa))


def _draw_lights(d, ps, ph):
    for p in ps:
        a = int(70 + 100 * (0.5 + 0.5 * math.sin(2 * math.pi * p["m"] * ph + p["ph"])))
        r = p["r"]
        d.ellipse([p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r], fill=(255, 214, 150, a))


# ── 루프 생성 ─────────────────────────────────────────────
def _layer_fn(kind: str, rnd: random.Random):
    """(입자 그리기 함수, 블러 반경, 밝기 흔들림 폭)."""
    if kind == "rain":
        ps = _rain(rnd, 260)
        return (lambda d, ph: _draw_rain(d, ps, ph)), 0.0, 0.0
    if kind == "snow":
        ps = _flakes(rnd, 190, 3.8)
        return (lambda d, ph: _draw_flakes(d, ps, ph)), 1.1, 0.0
    if kind == "leaves":
        ps = _flakes(rnd, 38, 5.5)
        return (lambda d, ph: _draw_leaves(d, ps, ph)), 0.6, 0.0
    if kind == "embers":
        ps = _embers(rnd, 90)
        return (lambda d, ph: _draw_embers(d, ps, ph)), 0.8, 0.035
    if kind == "fireflies":
        ps = _glows(rnd, 46)
        return (lambda d, ph: _draw_fireflies(d, ps, ph)), 1.6, 0.0
    if kind == "lights":
        ps = _glows(rnd, 34, lower=True)
        return (lambda d, ph: _draw_lights(d, ps, ph)), 4.0, 0.0
    # dust: 떠다니는 먼지 + 아주 약한 숨쉬기 밝기
    ps = _flakes(rnd, 45, 1.8)
    for p in ps:
        p["a"] = rnd.randint(40, 110)
    return (lambda d, ph: _draw_flakes(d, ps, ph, (255, 240, 215))), 0.8, 0.015


def frames(bg: Image.Image, kind: str, seed: str = "", fps: int = FPS, loop_sec: float = LOOP_SEC):
    """루프 프레임(RGB Image) 제너레이터. 마지막 프레임 다음이 첫 프레임과 이어진다."""
    if kind not in KINDS:
        raise ValueError(f"motion kind 는 {KINDS} 중 하나: {kind!r}")
    rnd = random.Random(f"{kind}|{seed}")
    draw_fn, blur, flicker = _layer_fn(kind, rnd)
    base = bg.convert("RGB").resize((W, H))
    n = max(1, int(round(fps * loop_sec)))
    for i in range(n):
        ph = i / n                                    # 0 ≤ ph < 1 — ph=1 은 다음 루프의 0
        frame = base
        if flicker:
            f = 1 + flicker * (math.sin(2 * math.pi * 3 * ph) * 0.6 + math.sin(2 * math.pi * 7 * ph + 1) * 0.4)
            frame = ImageEnhance.Brightness(base).enhance(f)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer), ph)
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        yield Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")


def make_loop(bg_png: str, kind: str, out_mp4: str, seed: str = "",
              preview_dir: str | None = None) -> str:
    """bg_png 위에 kind 움직임을 얹은 LOOP_SEC 초 루프 mp4 를 만든다."""
    bg = Image.open(bg_png)
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    n = int(round(FPS * LOOP_SEC))
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", "yuv420p",
           # 루프 전체를 GOP 하나로 — 이어 붙일 때 루프 시작이 곧 키프레임이다
           "-g", str(n), "-keyint_min", str(n), "-sc_threshold", "0",
           "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i, fr in enumerate(frames(bg, kind, seed)):
            proc.stdin.write(fr.tobytes())
            if preview_dir and i in (0, n // 3, 2 * n // 3):
                os.makedirs(preview_dir, exist_ok=True)
                fr.save(os.path.join(preview_dir, f"{kind}_{i:03d}.jpg"), quality=88)
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ambient loop 인코딩 실패(rc={rc})")
    return out_mp4


def mux_loop(loop_mp4: str, audio: str, out_mp4: str, dur_sec: float) -> str:
    """루프 영상을 재인코딩 없이 dur_sec 만큼 이어 붙이고 오디오를 얹는다."""
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", loop_mp4,
                    "-i", audio, "-map", "0:v", "-map", "1:a", "-c", "copy",
                    "-t", f"{dur_sec:.2f}", "-movflags", "+faststart", out_mp4], check=True)
    return out_mp4


def main() -> int:
    import argparse
    import time
    ap = argparse.ArgumentParser(description="앰비언트 움직임 루프 생성")
    ap.add_argument("--bg", required=True)
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", default="")
    ap.add_argument("--preview", default=None, help="프레임 3장을 저장할 폴더")
    a = ap.parse_args()
    t0 = time.monotonic()
    make_loop(a.bg, a.kind, a.out, a.seed, a.preview)
    kb = os.path.getsize(a.out) / 1024
    kbps = kb * 8 / LOOP_SEC
    print(f"✅ {a.out}  {LOOP_SEC:.0f}s·{FPS}fps · {kb:.0f}KB · {kbps:.0f}kbps"
          f" → 8시간이면 약 {kbps * 28800 / 8 / 1024 / 1024:.2f}GB · {time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
