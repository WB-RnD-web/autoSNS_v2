#!/usr/bin/env python3
"""인스타 밤 편(c) 두 꼴의 공용 도구 — '심해 직장인'(worker_reel) · '위험한 진짜 이유'(danger_reel) (2026-10-31).

왜: 10/31 벤치마크 — 얼굴 없는 자동 계정이 만들 수 있으면서 한국 10~20대에서 지금 터지는 두 꼴.
  · AI 동물 캐릭터 + 공감 한 줄(꾸이꾸이 김꾸이 '꿈꾸던 어른이 되었나요?' 1,700만 · 큰 한국어 한 줄 · 잔잔한 피아노 · 목소리 없음)
  · 카드형 반전 '~가 위험한 이유'(뭘보냥 '전기장판이 위험한 이유' 이틀 585만 · 크림 카드 + 제목 + 동물 + 끝 한 줄)
  견본 4편(C:\\wbtmp\\insta_samples_1031)을 사용자가 보고 "전부 너가 원하는 방향으로" → 11/08 부터 밤 편(c) 21:20 에 하루씩 번갈아.

여기 있는 것: 글꼴 글자 그리기(그림자·외곽선·강조) · 켄 번스 화면(view) · 5B 클립 앞→뒤 재생(pingpong) · 코드로 만든 피아노 배경음 ·
  Spark 잡(이미지 seed 고정 · from_job 편집 = qwen-image-edit · 5B 영상) · 숫자·금지어·그림 묘사 검사 · 캡션.
목소리는 없다(벤치마크 둘 다 글 + 잔잔한 음악). 배경음은 코드로 만든다(저작권 걱정 없음 — 남의 녹음 파일을 레포에 넣지 않는다).
Spark 주소는 다른 꼴과 같이 WBSPARK_BASE(pipeline/wbspark.py). ★실패 동작은 다른 꼴과 같다: 그림을 끝내 못 그리면 렌더가 멈춘다
  (게시 안 됨). 단 캐릭터 편집(from_job)이 실패하면 같은 캐릭터 묘사 + 같은 seed 로 새로 그리고(덜 닮지만 계속), 5B 영상은 장식이라
  실패하면 정지 그림만 쓴다(경고만).
"""
from __future__ import annotations

import datetime as dt
import math
import os
import re
import subprocess
import sys
import time
import wave

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402  (숫자 검사·금지어·해시태그·그림 금지 낱말을 같이 쓴다)
import render_reel as R  # noqa: E402  (글꼴·인코딩·ffmpeg)

W, H, FPS, SR = R.W, R.H, R.FPS, R.SR
LZ = getattr(Image, "Resampling", Image).LANCZOS
BIC = getattr(Image, "Resampling", Image).BICUBIC
Y_MAX = 1440                                              # 그린 글자의 아랫변 — 아래 25%는 인스타 캡션·버튼 자리
X_MAX = 960                                               # 글자의 오른쪽 끝 — 오른쪽 120px 는 좋아요·댓글 버튼 자리
SRC_PX = 32                                               # 화면 출처 줄 글씨(견본 24~27px 은 폰에서 안 읽혔다)
CAPTION_MAX, QUESTION_MAX = 40, 40
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_HANGUL = re.compile(r"[가-힣]")
_LATIN3 = re.compile(r"[A-Za-z]{3,}")
_TIME = re.compile(r"\d+\s*(?:시|분|월|일|요일|년차|년생)")      # 직장 상황의 시각·날짜는 사실 숫자가 아니다
# 그림 금지 낱말 — sci 와 같되 'face' 는 둔다(캐릭터·동물의 얼굴 표정이 이 꼴의 핵심). 사람 얼굴 클로즈업·셀피는 막는다
IMG_BAN = re.compile(r"(?i)\b(text|letters?|words?|captions?|logos?|watermarks?|typography|signs?|signage|labels?|writing|"
                     r"portraits?|selfies?|headshots?|close-?up of (?:a |the )?(?:man|woman|person|people|human|child))\b")
ASK_MORE = ("유튜브", "youtube", "구독", "팔로우", "좋아요 눌", "저장 부탁", "저장해 두", "공유 부탁", "링크")   # + ASK_BAN·bm ASK_EXTRA


# ── 검사 도구 ──────────────────────────────────────────
def bm():
    import bm_reel
    return bm_reel


def entry_numbers(e: dict) -> list[float]:
    return K.fact_values({"facts": [f for f in e.get("facts") or [] if isinstance(f, dict)]})


def unbacked(text: str, e: dict, allow_time: bool = False) -> list[str]:
    """entry facts 에 없는 수 — allow_time 이면 '9시'·'3분' 같은 시각은 뺀다."""
    t = _TIME.sub("", text) if allow_time else text
    return K.unbacked(t, entry_numbers(e))


def word_errs(texts: list[str], imgs: list[str]) -> list[str]:
    """금지어 · 부탁 말 · 유튜브 · 잔혹·IP·실존 인물·성적·외모 비하·따라 하면 위험 · 상표(그림 묘사 포함)."""
    B = bm()
    errs = []
    low = [t.lower() for t in texts if isinstance(t, str)]
    hits = sorted({w for w in K.BANNED for t in texts if w in t})
    if hits:
        errs.append(f"금지어 {hits}")
    asks = sorted({w for w in K.ASK_BAN + B.ASK_EXTRA + ASK_MORE for t in low if w.lower() in t})
    if asks:
        errs.append(f"부탁·유튜브 말 {asks} — 댓글·저장·공유·팔로우 부탁과 유튜브 언급은 쓰지 않는다(캡션 포함)")
    allx = low + [i.lower() for i in imgs if isinstance(i, str)]
    for name, words in (("잔혹 묘사", K.SCI_GORE), ("브레인롯", B.BRAINROT), ("캐릭터·영화 IP", B.CHARACTERS + K.SCI_FRANCHISE),
                        ("실존 인물", B.CELEBS + K.SCI_PEOPLE), ("성적인 말", B.SEXUAL), ("외모 비하", B.BODY),
                        ("따라 하면 위험", B.DANGER)):
        h = B._hits(words, allx)
        if h:
            errs.append(f"{name} 금지 {h}")
    for t in allx:
        m = B.BRAND.search(t)
        if m:
            errs.append(f"상표·노선 이름 금지 '{m.group(0)}'")
            break
    return errs


def img_errs(where: str, text, lo: int = 30, hi: int = 420) -> list[str]:
    """그림 묘사(영어) — 글자·간판·로고 낱말 없이, 한글 없이."""
    if not isinstance(text, str) or not lo <= len(text) <= hi:
        return [f"{where}: 영어 그림 묘사 {lo}~{hi}자"]
    errs = []
    if _HANGUL.search(text):
        errs.append(f"{where}: 그림 묘사는 영어로(한글이 있으면 그림에 글자가 생긴다)")
    m = IMG_BAN.search(text)
    if m:
        errs.append(f"{where}: '{m.group(0)}' — 그림엔 글자·간판·로고·얼굴 클로즈업이 없게(장면만 긍정형으로)")
    if re.search(r"(?i)\bphones?\b", text):
        errs.append(f"{where}: 'phone' 은 쓰지 않는다(부정형으로 써도 폰이 생긴다 — 10/2 실측)")
    return errs


def line_count(text: str, kind: str, size: int, width: float) -> int:
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    return len(wrap_lines(d, text, R.font(kind, size), width))


def caption_errs(s: dict, e: dict) -> list[str]:
    errs = []
    cap, q = s.get("caption"), s.get("question")
    if not isinstance(cap, str) or not cap.strip() or "\n" in cap.strip() or len(cap.strip()) > CAPTION_MAX:
        errs.append(f"caption 은 한 줄 · {CAPTION_MAX}자 이내(짧은 구어체) — 회차·출처·AI 표시·해시태그는 코드가 붙인다")
    elif "#" in cap or "출처" in cap:
        errs.append("caption 에 '#'·'출처' 를 쓰지 않는다 — 코드가 붙인다")
    if not isinstance(q, str) or not q.strip() or "\n" in q.strip() or len(q.strip()) > QUESTION_MAX or not q.strip().endswith("?"):
        errs.append(f"question 은 열린 질문 한 줄 · {QUESTION_MAX}자 이내 · '?' 로 끝")
    tags = s.get("hashtags")
    if not isinstance(tags, list) or len(tags) > K.HASHTAG_MAX or not all(
            isinstance(t, str) and re.fullmatch(r"#[^\s#]+", t) for t in tags):
        errs.append(f"hashtags 는 '#낱말' {K.HASHTAG_MAX}개까지")
    if not (s.get("bench") or {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    for f in ("caption", "question"):
        bad = unbacked(s.get(f) or "", e, allow_time=True)
        if bad:
            errs.append(f"{f}: catalog {e.get('n')} facts 에 없는 숫자 {bad}")
    return errs


def head_errs(s: dict, kind: str, want_n_fn, no_fn, no_key: str) -> tuple[list[str], dict | None, dt.date | None]:
    """날짜·꼴·src_n·회차·sources — 편성은 코드가 정한다(pick_plan.c_kind·c_n)."""
    errs = []
    if s.get("kind") != kind:
        return [f"kind 는 {kind}"], None, None
    try:
        d = dt.date.fromisoformat(s.get("date", ""))
    except (TypeError, ValueError):
        return ["date 는 YYYY-MM-DD"], None, None
    want = P.c_kind(d)
    if want is None:
        errs.append(f"{d} 는 밤 편(c)이 없는 날 — 밤 편은 {P.C_FROM} 부터 · catalog 가 남아 있는 날만")
    elif want != kind:
        errs.append(f"{d} 밤 편 꼴은 {want} — 대본은 {kind}(꼴은 코드가 날짜로 정한다)")
    wn = want_n_fn(d) if want == kind else None
    if wn is not None and s.get("src_n") != wn:
        errs.append(f"src_n 은 그날 편성 항목 {wn} 이어야 한다 — 대본은 {s.get('src_n')}")
    no = no_fn(d) if want == kind else None
    if no is not None and s.get(no_key) != no:
        errs.append(f"{no_key} 는 {no}(코드가 센다) — 대본은 {s.get(no_key)}")
    e = P.c_entry(s.get("src_n")) if isinstance(s.get("src_n"), int) else None
    if e is None or P.c_kind_of_n(e.get("n")) != kind:
        return errs + [f"src_n {s.get('src_n')!r} 은 {kind} catalog 항목이 아니다"], None, d
    if s.get("sources") != e.get("sources"):
        errs.append(f"sources 는 catalog {e['n']} 의 sources 를 그대로(순서까지) 옮긴다")
    if not _SLUG.fullmatch(s.get("slug") or ""):
        errs.append("slug 는 영어 소문자·숫자·하이픈")
    return errs, e, d


# ── 글자 ──────────────────────────────────────────────
def wrap_lines(d, text: str, f, width: float) -> list[str]:
    """'\\n' 은 사람이 정한 줄바꿈 — 그 안에서만 띄어쓰기로 더 끊는다."""
    out = []
    for para in str(text).split("\n"):
        cur = ""
        for w_ in para.split():
            t = f"{cur} {w_}".strip()
            if cur and d.textlength(t, font=f) > width:
                out.append(cur)
                cur = w_
            else:
                cur = t
        out.append(cur)
    return [x for x in out if x] or [""]


def fit_lines(d, text: str, kind: str, hi: int, lo: int, width: float, max_lines: int):
    for size in range(hi, lo - 1, -2):
        f = R.font(kind, size)
        ls = wrap_lines(d, text, f, width)
        if len(ls) <= max_lines and all(d.textlength(x, font=f) <= width for x in ls):
            return f, ls
    f = R.font(kind, lo)
    return f, wrap_lines(d, text, f, width)


def _layer(text: str, f, fill, stroke: int = 0, stroke_fill=None):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    pad = 4
    im = Image.new("RGBA", (int(r - l) + pad * 2, int(b - t) + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=tuple(fill)[:3] + (255,), stroke_width=stroke,
                            stroke_fill=(tuple(stroke_fill)[:3] + (255,)) if stroke_fill else None)
    return im, (l - pad, t - pad)


def _paste(base: Image.Image, lay: Image.Image, xy, off, a: float):
    if a <= 0:
        return
    if a < 1:
        lay = lay.copy()
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    base.paste(lay, (int(xy[0] + off[0]), int(xy[1] + off[1])), lay)


def text_a(base, xy, text, f, fill, a: float = 1.0):
    lay, off = _layer(text, f, fill)
    _paste(base, lay, xy, off, a)


def text_stroke(base, xy, text, f, fill, stroke_fill, sw: int, a: float = 1.0):
    lay, off = _layer(text, f, fill, sw, stroke_fill)
    sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    sh.putalpha(lay.getchannel("A").filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.55)))
    _paste(base, sh, (xy[0] + 3, xy[1] + 6), off, a)
    _paste(base, lay, xy, off, a)


def rich_line(base, xy, line: str, f, fill, accent, hls: list[str], a: float = 1.0):
    """한 줄 안에서 hls 낱말만 강조색."""
    if a <= 0:
        return
    d = ImageDraw.Draw(base)
    spans, i = [], 0
    hs = [h for h in hls if isinstance(h, str) and h]
    if hs:
        pat = "|".join(re.escape(h) for h in sorted(hs, key=len, reverse=True))
        for m in re.finditer(pat, line):
            if m.start() > i:
                spans.append((line[i:m.start()], fill))
            spans.append((m.group(0), accent))
            i = m.end()
    spans.append((line[i:], fill))
    x = xy[0]
    for seg, col in spans:
        if seg:
            text_a(base, (x, xy[1]), seg, f, col, a)
            x += d.textlength(seg, font=f)


def shade_band(im: Image.Image, y0: int, y1: int, strength: int = 160):
    h = y1 - y0
    m = Image.new("L", (1, h))
    for y in range(h):
        m.putpixel((0, y), int(strength * math.sin(math.pi * y / max(1, h - 1)) ** 0.8))
    im.paste(Image.new("RGB", (W, h), (0, 0, 0)), (0, y0), m.resize((W, h)))


def vgrad(size, top, bot) -> Image.Image:
    w, h = size
    col = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    return col.resize((w, h))


def rounded_mask(w: int, h: int, r: int) -> Image.Image:
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), r * 3, fill=255)
    return m.resize((w, h), LZ)


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def ease(p: float) -> float:
    p = clamp(p)
    return p * p * (3 - 2 * p)


# ── 화면(켄 번스 · 5B 클립) ─────────────────────────────
def cover(im: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), LZ)
    x0, y0 = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x0, y0, x0 + w, y0 + h))


def view(big: Image.Image, z: float, out_w: int, out_h: int, over: float, cy: float = 0.5,
         angle: float = 0.0, dx: float = 0.0) -> Image.Image:
    """over 배 크게 준비한 그림에서 z 배율만큼 잘라 out 크기로. angle(도)·dx(폭 비율)는 흔들림·초점 이동."""
    bw, bh = big.size
    pad = 1.04 if angle else 1.0
    cw, ch = int(bw / over / z * pad), int(bh / over / z * pad)
    cx, cyy = bw // 2 + int(dx * bw), int(bh * cy)
    x0 = max(0, min(bw - cw, cx - cw // 2))
    y0 = max(0, min(bh - ch, cyy - ch // 2))
    if not angle:
        return big.crop((x0, y0, x0 + cw, y0 + ch)).resize((out_w, out_h), BIC)
    ow, oh = int(out_w * pad), int(out_h * pad)
    r = big.crop((x0, y0, x0 + cw, y0 + ch)).resize((ow, oh), BIC).rotate(angle, BIC)
    return r.crop(((ow - out_w) // 2, (oh - out_h) // 2, (ow - out_w) // 2 + out_w, (oh - out_h) // 2 + out_h))


def clip_info(path: str) -> tuple[int, int, float]:
    p = subprocess.run([R.ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5}).*?([\d.]+) fps", p.stderr)
    if not m:
        raise RuntimeError(f"클립 정보 없음: {path}")
    return int(m.group(1)), int(m.group(2)), float(m.group(3))


def load_clip(path: str, w: int, h: int, max_sec: float = 1.45) -> tuple[list[Image.Image], float]:
    """5B 클립 앞 max_sec 초를 w×h 로 cover — 뒤로 갈수록 흔들리고 얼굴이 뭉개져 앞만 쓴다(10/2·10/31 실측)."""
    sw, sh, fps = clip_info(path)
    s = max(w / sw, h / sh)
    rw, rh = math.ceil(sw * s / 2) * 2, math.ceil(sh * s / 2) * 2
    # ★crop 은 rgb24 로 바꾼 뒤에 — yuv420p 에서 홀수 폭으로 자르면 짝수로 반올림돼 프레임이 기울어진다(10/31 실측)
    vf = f"scale={rw}:{rh}:flags=lanczos,unsharp=5:5:0.5,format=rgb24,crop={w}:{h}"
    p = subprocess.run([R.ffmpeg(), "-v", "error", "-i", path, "-t", str(max_sec), "-vf", vf, "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True)
    n = len(p.stdout) // (w * h * 3)
    return [Image.frombytes("RGB", (w, h), p.stdout[i * w * h * 3:(i + 1) * w * h * 3]) for i in range(n)], fps


def pingpong(clip: list, fps: float, lt: float, xf: float = 0.25):
    """클립을 앞으로 → 거꾸로 재생해 첫 프레임(= 정지 그림 구도)으로 돌아온 뒤 정지 그림으로 넘긴다.
    반환: (클립 프레임 | None, 정지 그림 섞는 비율 0~1)."""
    n = len(clip)
    if not n:
        return None, 1.0
    L = n / fps
    if lt >= 2 * L + xf:
        return None, 1.0
    if lt < L:
        k = int(lt * fps)
    elif lt < 2 * L:
        k = n - 1 - int((lt - L) * fps)
    else:
        k = 0
    return clip[max(0, min(n - 1, k))], clamp((lt - 2 * L) / xf)


def clip_span(clip: list, fps: float) -> float:
    return 2 * len(clip) / fps if clip else 0.0


# ── 소리: 코드로 만든 잔잔한 피아노(3/4 · Gmaj7 ↔ Dmaj7) ─────
PIANO_BPM = 69
_CHORDS = (((98.00,), (246.94, 293.66, 369.99)), ((73.42,), (220.00, 277.18, 369.99)))   # (베이스, 화음) 두 마디 번갈아
_MELODY = (739.99, 880.00, 783.99, 739.99, 554.37, 493.88, 554.37, 587.33)             # 두 마디에 한 음 — 띄엄띄엄


def _note(freq: float, sec: float, amp: float):
    import numpy as np
    t = np.arange(int(SR * sec)) / SR
    env = np.minimum(1.0, t / 0.008) * np.exp(-t / 1.4)
    tone = sum(a * np.sin(2 * math.pi * freq * k * t) for k, a in ((1, 1.0), (2, 0.42), (3, 0.16), (4, 0.06)))
    return (amp * env * tone).astype("float32")


def piano_bed(total: float, out_wav: str, gain_db: float = -21.0) -> str:
    """잔잔한 왈츠 피아노 total 초 — 처음 0.3초 들어오고 끝 1.2초 사라진다. RMS 를 gain_db 로 맞춘다(낮게)."""
    import numpy as np
    n = int(SR * (total + 0.5))
    y = np.zeros(n + SR * 3, dtype="float32")
    beat = 60.0 / PIANO_BPM
    bar = 3 * beat
    k = 0
    while k * bar < total + 0.5:
        bass, chord = _CHORDS[k % 2]
        a = int(SR * k * bar)
        for f in bass:
            nt = _note(f, 2.6, 0.55)
            y[a:a + len(nt)] += nt
        for b in (1, 2):
            s = int(SR * (k * bar + b * beat))
            for f in chord:
                nt = _note(f, 1.8, 0.16)
                y[s:s + len(nt)] += nt
        if k % 2 == 0 and k >= 2:
            f = _MELODY[(k // 2 - 1) % len(_MELODY)]
            s = int(SR * (k * bar + beat))
            nt = _note(f, 3.0, 0.22)
            y[s:s + len(nt)] += nt
        k += 1
    y = y[:n]
    t = np.arange(n) / SR
    y *= np.minimum(1.0, t / 0.3) * np.clip((total - t) / 1.2, 0.0, 1.0)
    rms = float(np.sqrt(np.mean(y[: int(SR * max(1.0, total - 1.5))] ** 2)) or 1e-6)
    y *= (10 ** (gain_db / 20)) / rms
    y = np.clip(y, -0.95, 0.95)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype("<i2").tobytes())
    return out_wav


def mux(painter_frame, total: float, wav: str, out: str, wd: str) -> None:
    """프레임 → 무음 mp4(R.encode) → 배경음과 합쳐 AAC."""
    class _PA:
        frame = staticmethod(painter_frame)
    silent = os.path.join(wd, "silent.mp4")
    R.encode(_PA, total, silent)
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
          "-shortest", "-movflags", "+faststart", out])


def contact_sheet(frame, times: list[float], out: str) -> None:
    tw, th = 270, 480
    sheet = Image.new("RGB", (tw * len(times), th), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for k, t in enumerate(times):
        sheet.paste(frame(t).resize((tw, th), LZ), (k * tw, 0))
        d.text((k * tw + 8, 6), f"{t:.1f}s", fill=(255, 230, 0), font=R.font("bold", 22), stroke_width=2,
               stroke_fill=(0, 0, 0))
    sheet.save(out, "JPEG", quality=88)


# ── Spark ─────────────────────────────────────────────
class SparkError(RuntimeError):
    pass


def _api():
    import requests
    import wbspark
    return requests, wbspark


def spark_job(payload: dict, timeout: int = 900, poll: float = 4.0) -> tuple[str, dict, float]:
    """잡 하나 — (job_id, 마지막 상태, 걸린 초). 제출 실패·시간 초과·error 는 SparkError."""
    requests, wb = _api()
    R.spark_wait()
    t0 = time.time()
    r = requests.post(f"{wb._base()}/jobs", json=payload, headers=wb._headers(), timeout=40)
    if r.status_code != 200 or not (r.json() or {}).get("job_id"):
        raise SparkError(f"제출 실패 {r.status_code}: {r.text[:160]}")
    jid = r.json()["job_id"]
    d: dict = {}
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            d = requests.get(f"{wb._base()}/jobs/{jid}", headers=wb._headers(), timeout=40).json() or {}
        except Exception:  # noqa: BLE001
            continue
        if d.get("status") == "done":
            return jid, d, round(time.time() - t0, 1)
        if d.get("status") in ("error", "failed"):
            raise SparkError(f"잡 실패 {jid}: {str(d)[:160]}")
    raise SparkError(f"잡 시간 초과 {jid} ({timeout}s, 마지막 {d.get('status')})")


def spark_fetch(jid: str, path: str) -> None:
    requests, wb = _api()
    f = requests.get(f"{wb._base()}/jobs/{jid}/file", headers=wb._headers(), timeout=300)
    if f.status_code != 200 or not f.content:
        raise SparkError(f"파일 받기 실패 {jid}: {f.status_code}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(f.content)


def broken_image(path: str, frac: float = 0.10) -> str | None:
    """망가진 그림인가 — 위·아래에서 이어지는 거의 검은 줄이 높이의 frac 넘게(10/31 실측: qwen 편집 결과 아래 35%가 검게 나왔다)
    또는 통째로 한 색. 망가졌으면 까닭, 멀쩡하면 None."""
    from PIL import ImageOps, ImageStat
    g = ImageOps.grayscale(Image.open(path).convert("RGB")).resize((64, 128))
    rows = [ImageStat.Stat(g.crop((0, y, 64, y + 1))) for y in range(128)]
    dark = [r.mean[0] < 6 and r.stddev[0] < 4 for r in rows]
    top = next((i for i, x in enumerate(dark) if not x), 128)
    bot = next((i for i, x in enumerate(reversed(dark)) if not x), 128)
    if max(top, bot) > 128 * frac:
        return f"검은 띠 {max(top, bot) / 128:.0%}({'위' if top >= bot else '아래'})"
    if ImageStat.Stat(g).stddev[0] < 3:
        return "한 색"
    return None


def spark_alive(jid: str | None) -> bool:
    """서버가 아직 이 잡 결과를 갖고 있나(결과는 1시간 뒤 지워진다 — from_job 은 그 안에만)."""
    if not jid:
        return False
    try:
        requests, wb = _api()
        return (requests.get(f"{wb._base()}/jobs/{jid}", headers=wb._headers(), timeout=20).json() or {}).get("status") == "done"
    except Exception:  # noqa: BLE001
        return False


def spark_image(prompt: str, path: str, w: int, h: int, seed: int | None, tries: int = 3, log: list | None = None) -> str:
    """z-image-turbo 한 장(no_llm · 크기 직접) → job id. tries 번 다 실패하면 SparkError."""
    import wbspark
    body = {"type": "image", "prompt": wbspark.strip_text_negatives(prompt), "width": w, "height": h, "no_llm": True}
    if seed is not None:
        body["seed"] = seed
    if R.IMG_MODEL:
        body["model"] = R.IMG_MODEL
    last = None
    for k in range(tries):
        try:
            jid, d, sec = spark_job(body, timeout=900)
            spark_fetch(jid, path)
            bad = broken_image(path)
            if bad:
                raise SparkError(f"망가진 그림 {jid}: {bad}")
            if log is not None:
                log.append({"what": "image", "model": d.get("model"), "sec": sec})
            return jid
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"   ⚠️ Spark 그림 {k + 1}/{tries} 실패: {str(e)[:160]}", flush=True)
            time.sleep(10 + 20 * k)
    raise SparkError(f"그림 실패: {last}")


def spark_edit(src_job: str, prompt: str, path: str, tries: int = 2, log: list | None = None) -> str:
    """같은 캐릭터를 새 장면에 — image 잡에 from_job 을 실으면 서버가 qwen-image-edit-2511 로 편집한다(게이트웨이 문서엔 없다 ·
    10/31 실측: 서버 약 150초 · 대기 포함 3~6분)."""
    last = None
    for k in range(tries):
        try:
            jid, d, sec = spark_job({"type": "image", "from_job": src_job, "prompt": prompt, "no_llm": True}, timeout=1200)
            spark_fetch(jid, path)
            bad = broken_image(path)
            if bad:
                raise SparkError(f"망가진 편집 그림 {jid}: {bad}")
            if log is not None:
                log.append({"what": "edit", "model": d.get("model"), "mode": d.get("mode"), "sec": sec})
            return jid
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"   ⚠️ Spark 편집 {k + 1}/{tries} 실패: {str(e)[:160]}", flush=True)
            time.sleep(10 + 20 * k)
    raise SparkError(f"편집 실패: {last}")


def spark_video(src_job: str, prompt: str, path: str, timeout: int = 600, log: list | None = None) -> bool:
    """wan2.2 5B 이미지→영상(fast · 33프레임 ≈ 1.4초). 장식이라 한 번만 — 실패·초과면 False(정지 그림만 쓴다)."""
    body = {"type": "video", "from_job": src_job, "fast": True, "no_llm": True, "length": 33, "fps": 16, "mp4": True,
            "prompt": prompt}
    try:
        jid, d, sec = spark_job(body, timeout=timeout, poll=8.0)
        spark_fetch(jid, path)
        if log is not None:
            log.append({"what": "video", "model": d.get("model"), "sec": sec})
        return True
    except Exception as e:  # noqa: BLE001
        print(f"::warning title=5B 영상 건너뜀::{str(e)[:200]} — 정지 그림만 쓴다", flush=True)
        if log is not None:
            log.append({"what": "video", "failed": str(e)[:160]})
        return False


def mock_image(prompt: str, path: str, w: int, h: int) -> None:
    """Spark 없이(테스트) — 프롬프트로 정해지는 가짜 그림."""
    import random
    rnd = random.Random(prompt)
    im = Image.new("RGB", (w, h), tuple(rnd.randint(40, 120) for _ in range(3)))
    d = ImageDraw.Draw(im)
    for _ in range(9):
        x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(60, 260)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rnd.randint(60, 230) for _ in range(3)))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    im.save(path)


# ── 캡션 ──────────────────────────────────────────────
def caption(first: str, s: dict, e: dict, ai_note: str) -> str:
    """'<회차> · <한 줄>' + 열린 질문 + '출처: <catalog source_label>' + AI 표시 + 해시태그 5개까지."""
    hook = re.sub(r"\s{2,}", " ", K._TAG_RE.sub("", (s.get("caption") or "").strip())).strip()
    q = (s.get("question") or "").strip()
    tags = K.hashtags_of(s)
    body = f"{first} · {hook}" if first else hook
    body += (f"\n\n{q}" if q else "") + f"\n\n출처: {e.get('source_label', '')}\n{ai_note}"
    return body + ("\n\n" + " ".join(tags) if tags else "")
