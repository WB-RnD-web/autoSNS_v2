#!/usr/bin/env python3
"""Gumiho Games 렌더 — 비트 → 화면(PIL 1920×1080) + 목소리(Spark Supertonic 영어) → mp4·자막·챕터·썸네일.

    python gumiho/render.py output/gumiho/matches/2026-10-01_fox-hunt_s2026100102.json --frames-only   # 화면만(ffmpeg 없이)
    python gumiho/render.py <match.json>                                                                 # 영상까지

★Spark 는 공용 서버라 목소리 합성은 동시 2건(GUMIHO_TTS_WORKERS)만 보낸다. 같은 문장은 캐시해 다시 안 만든다.
화면은 비트마다 한 장(정지 화면)이고, 길이는 목소리 길이(+여백) 또는 속마음을 읽을 시간 중 긴 쪽이다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import wave

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import episode  # noqa: E402

A = os.path.join(HERE, "assets")
W, H = 1920, 1080
SR = 44100
GAP = 0.45                 # 말 사이 쉼
READ_WPS = 3.4             # 속마음 읽는 속도(단어/초)
WORKERS = int(os.environ.get("GUMIHO_TTS_WORKERS", "2"))
GOLD, RED, INK, PAPER = (242, 200, 110), (226, 58, 44), (22, 16, 26), (250, 247, 242)
ROLE_COLOR = {"fox": (226, 58, 44), "shaman": (170, 120, 255), "villager": (150, 150, 160)}

# 굵기별 파일(fonts-noto-core). 없는 굵기는 가장 가까운 것을 쓴다 — 2026-09-29 Actions 에서 800 이 없어 멈췄다.
NOTO_DIR = "/usr/share/fonts/truetype/noto"
NOTO = {400: "NotoSans-Regular.ttf", 600: "NotoSans-SemiBold.ttf", 700: "NotoSans-Bold.ttf",
        800: "NotoSans-ExtraBold.ttf", 900: "NotoSans-Black.ttf"}
VF = [r"C:\Windows\Fonts\NotoSansKR-VF.ttf", f"{NOTO_DIR}/NotoSans-VF.ttf"]
NANUM = {400: "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
         700: "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
         800: "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf"}
_fc: dict = {}


def _by_nearest(table: dict, weight: int) -> list[str]:
    return [table[k] for k in sorted(table, key=lambda k: (abs(k - weight), -k))]


def font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    k = (size, weight)
    if k in _fc:
        return _fc[k]
    f = None
    for name in _by_nearest(NOTO, weight):
        p = os.path.join(NOTO_DIR, name)
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            break
    if f is None:
        for p in VF:
            if os.path.exists(p):
                f = ImageFont.truetype(p, size)
                try:
                    f.set_variation_by_axes([weight])
                except Exception:  # noqa: BLE001
                    pass
                break
    if f is None:
        for p in _by_nearest(NANUM, weight):
            if os.path.exists(p):
                f = ImageFont.truetype(p, size)
                break
    _fc[k] = f or ImageFont.load_default()
    return _fc[k]


def wrap(text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for w in str(text).split():
        t = f"{cur} {w}".strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(text: str, box_w: int, box_h: int, size: int, weight: int, min_size: int = 26, lh: float = 1.25):
    while size >= min_size:
        f = font(size, weight)
        ls = wrap(text, f, box_w)
        if len(ls) * size * lh <= box_h:
            return f, ls, size
        size -= 2
    f = font(min_size, weight)
    ls = wrap(text, f, box_w)
    keep = max(1, int(box_h / (min_size * lh)))
    if len(ls) > keep:
        ls = ls[:keep]
        ls[-1] = ls[-1].rstrip(".,") + "…"
    return f, ls, min_size


def hexrgb(h: str | None, default=(230, 230, 230)):
    try:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:  # noqa: BLE001
        return default


# ── 재료 ──────────────────────────────────────────────
class Kit:
    def __init__(self, match: dict):
        self.roster = {s["name"]: s for s in match["roster"]}
        self.names = [s["name"] for s in match["roster"]]
        self.roles = match["roles"]
        stage = Image.open(os.path.join(A, "stage.jpg")).convert("RGB").resize((W, H))
        self.day = ImageEnhance.Brightness(stage).enhance(0.55)
        night = ImageEnhance.Brightness(stage).enhance(0.32)
        self.night = Image.blend(night, Image.new("RGB", (W, H), (10, 18, 60)), 0.35)
        self.gumi = {k: Image.open(os.path.join(A, f"gumi_{k}.jpg")).convert("RGB") for k in ("front", "side", "wink")}
        self.sprites = {}
        for n in self.names:
            key = self.roster[n].get("sprite") or n.lower()
            p = os.path.join(A, "sprites", f"{key}.png")
            sp = Image.open(p).convert("RGBA") if os.path.exists(p) else Image.new("RGBA", (64, 64), (200, 200, 200, 255))
            self.sprites[n] = sp

    def color(self, n: str):
        return hexrgb(self.roster.get(n, {}).get("color"))

    def sprite(self, n: str, h: int, grey: bool = False) -> Image.Image:
        sp = self.sprites[n]
        s = sp.resize((max(1, round(sp.width * h / sp.height)), h), Image.NEAREST)
        if grey:
            g = s.convert("LA").convert("RGBA")
            g.putalpha(s.getchannel("A").point(lambda a: a * 0.45))
            s = g
        return s


def rounded(d: ImageDraw.ImageDraw, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def overlay(img: Image.Image, box, fill, r=18):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(box, r, fill=fill)
    img.alpha_composite(lay)


SEAT_X = [250 + i * 284 for i in range(6)]
SEAT_BASE = 905


def seat_x(kit: Kit, n: str) -> int:
    return SEAT_X[kit.names.index(n)] if n in kit.names else W // 2


def draw_seats(img: Image.Image, kit: Kit, sc: dict):
    d = ImageDraw.Draw(img)
    hl = sc.get("highlight")
    for n in kit.names:
        x = seat_x(kit, n)
        dead = sc["dead"].get(n)
        up = 22 if n == hl and not dead else 0
        col = kit.color(n)
        if n == hl and not dead:
            glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse([x - 110, SEAT_BASE - 40, x + 110, SEAT_BASE + 10], fill=col + (150,))
            img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
        sp = kit.sprite(n, 150, grey=bool(dead))
        img.alpha_composite(sp, (x - sp.width // 2, SEAT_BASE - sp.height - up))
        f = font(26, 800 if n == hl else 700)
        tw = f.getlength(n)
        plate = [x - tw / 2 - 16, SEAT_BASE + 12, x + tw / 2 + 16, SEAT_BASE + 52]
        if n == hl and not dead:
            rounded(d, plate, 12, fill=col)
            d.text((x - tw / 2, SEAT_BASE + 15), n, font=f, fill=INK if sum(col) > 380 else PAPER)
        else:
            rounded(d, plate, 12, fill=(16, 12, 20), outline=col if not dead else (80, 80, 90), width=2)
            d.text((x - tw / 2, SEAT_BASE + 15), n, font=f, fill=(120, 120, 128) if dead else PAPER)
        tag = None
        if dead:
            tag = (f"{'OUT' if dead['how'] == 'banished' else 'TAKEN'} · {dead['role'].upper()}", ROLE_COLOR[dead["role"]])
        elif sc.get("roles_known") or sc.get("reveal_all"):
            r = kit.roles[n]
            if r != "villager" or sc.get("reveal_all"):
                tag = (r.upper(), ROLE_COLOR[r])
        if tag:
            ft = font(19, 800)
            tl = ft.getlength(tag[0])
            rounded(d, [x - tl / 2 - 10, SEAT_BASE + 60, x + tl / 2 + 10, SEAT_BASE + 90], 10, fill=tag[1])
            d.text((x - tl / 2, SEAT_BASE + 62), tag[0], font=ft, fill=PAPER)


def draw_top(img: Image.Image, sc: dict):
    d = ImageDraw.Draw(img)
    d.text((56, 36), "GUMIHO GAMES", font=font(30, 900), fill=GOLD)
    lab = sc["phase"]["label"]
    f = font(24, 800)
    tw = f.getlength(lab)
    rounded(d, [330, 38, 330 + tw + 28, 74], 16, fill=(40, 60, 140) if sc["phase"]["night"] else RED)
    d.text((344, 41), lab, font=f, fill=PAPER)
    al = f"ALIVE {len(sc['alive'])}/6"
    d.text((W - 56 - font(24, 700).getlength(al), 42), al, font=font(24, 700), fill=(220, 214, 206))


def draw_bubble(img: Image.Image, kit: Kit, who: str, text: str, box, label: str | None = None):
    x0, y0, x1, y1 = box
    col = kit.color(who) if who in kit.names else GOLD
    overlay(img, box, PAPER + (246,), r=26)
    d = ImageDraw.Draw(img)
    sx = min(max(seat_x(kit, who), x0 + 60), x1 - 60)
    d.polygon([(sx - 22, y1 - 2), (sx + 22, y1 - 2), (sx, y1 + 34)], fill=PAPER)
    name = label or who
    fn = font(26, 900)
    rounded(d, [x0 + 28, y0 - 20, x0 + 56 + fn.getlength(name), y0 + 20], 14, fill=col)
    d.text((x0 + 42, y0 - 17), name, font=fn, fill=INK if sum(col) > 380 else PAPER)
    f, ls, size = fit(f"“{text}”", x1 - x0 - 80, y1 - y0 - 60, 46, 700, 28)
    y = y0 + 34
    for ln in ls:
        d.text((x0 + 40, y), ln, font=f, fill=INK)
        y += int(size * 1.25)


def draw_thought(img: Image.Image, kit: Kit, who: str, text: str, box, secret: bool = False):
    if not text:
        return
    x0, y0, x1, y1 = box
    fox = kit.roles.get(who) == "fox"
    overlay(img, box, (18, 10, 22, 225), r=20)
    d = ImageDraw.Draw(img)
    edge = RED if fox else (kit.color(who) if who in kit.names else GOLD)
    d.rounded_rectangle(box, 20, outline=edge, width=3)
    lab = f"WHAT {who.upper()} IS REALLY THINKING" + ("  ·  SECRET" if secret else "")
    d.text((x0 + 28, y0 + 16), lab, font=font(22, 800), fill=(236, 150, 140) if fox else (205, 190, 225))
    f, ls, size = fit(text, x1 - x0 - 60, y1 - y0 - 70, 36, 400, 24)
    y = y0 + 54
    for ln in ls:
        d.text((x0 + 30, y), ln, font=f, fill=(244, 234, 236))
        y += int(size * 1.28)


def draw_host(img: Image.Image, kit: Kit, text: str, sc: dict, face: str = "front"):
    d = ImageDraw.Draw(img)
    pf = kit.gumi[face].resize((470, 470), Image.LANCZOS)
    m = Image.new("L", pf.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, 469, 469], 36, fill=255)
    px, py = 90, 150
    ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle([px - 8, py - 8, px + 478, py + 478], 42, fill=RED + (255,))
    img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(10)))
    img.paste(pf, (px, py), m)
    d.rounded_rectangle([px, py + 400, px + 150, py + 450], 14, fill=(16, 10, 18))
    d.text((px + 22, py + 406), "GUMI", font=font(30, 900), fill=GOLD)
    x0, y0, x1, ymax = 620, 190, 1830, 600
    f, ls, size = fit(text, x1 - x0 - 90, ymax - y0 - 70, 50, 700, 30)
    box = (x0, y0, x1, max(y0 + 190, min(ymax, y0 + int(len(ls) * size * 1.3) + 76)))  # 글 길이만큼만
    overlay(img, box, (16, 10, 20, 228), r=26)
    d.rounded_rectangle(box, 26, outline=GOLD, width=2)
    y = box[1] + 38
    for ln in ls:
        d.text((box[0] + 46, y), ln, font=f, fill=PAPER)
        y += int(size * 1.3)


def draw_card(img: Image.Image, label: str):
    d = ImageDraw.Draw(img)
    f = font(84, 900)
    tw = f.getlength(label)
    d.text(((W - tw) / 2 + 4, 64 + 4), label, font=f, fill=(0, 0, 0))
    d.text(((W - tw) / 2, 64), label, font=f, fill=GOLD)


def draw_votes(img: Image.Image, kit: Kit, rows: list, poll: bool):
    box = (1330, 130, 1860, 700)
    overlay(img, box, (14, 10, 18, 230), r=22)
    d = ImageDraw.Draw(img)
    d.text((box[0] + 26, box[1] + 18), "SUSPICION POLL" if poll else "VOTES", font=font(26, 900), fill=GOLD)
    y = box[1] + 70
    for i, (a, b) in enumerate(rows):
        last = i == len(rows) - 1
        fa, fb = font(28, 800 if last else 600), font(28, 800 if last else 600)
        d.text((box[0] + 26, y), a, font=fa, fill=kit.color(a))
        d.text((box[0] + 26 + fa.getlength(a) + 14, y), "→", font=fa, fill=(200, 190, 180))
        d.text((box[0] + 26 + fa.getlength(a) + 58, y), b, font=fb, fill=kit.color(b))
        y += 52


def draw_tally(img: Image.Image, kit: Kit, tally: dict, poll: bool):
    box = (420, 170, 1500, 690)
    overlay(img, box, (14, 10, 18, 236), r=26)
    d = ImageDraw.Draw(img)
    d.text((box[0] + 40, box[1] + 26), "WHO THEY SUSPECT" if poll else "THE VOTE", font=font(34, 900), fill=GOLD)
    mx = max(tally.values())
    y = box[1] + 100
    for n, c in tally.items():
        d.text((box[0] + 40, y), n, font=font(32, 800), fill=kit.color(n))
        bw = int((box[2] - box[0] - 360) * c / mx)
        d.rounded_rectangle([box[0] + 260, y + 6, box[0] + 260 + bw, y + 40], 10, fill=kit.color(n))
        d.text((box[0] + 280 + bw, y + 2), str(c), font=font(32, 900), fill=PAPER)
        y += 64


def draw_center_banner(img: Image.Image, text: str, color):
    """진행자 자막 칸(아래 끝 ≈ 640)과 자리(위 끝 ≈ 740) 사이 띠에 한 줄."""
    d = ImageDraw.Draw(img)
    f, ls, size = fit(text, 1600, 96, 80, 900, 40)
    y = 690 - size * 1.2 / 2 - 8
    for ln in ls[:1]:
        tw = f.getlength(ln)
        d.text(((W - tw) / 2 + 4, y + 4), ln, font=f, fill=(0, 0, 0))
        d.text(((W - tw) / 2, y), ln, font=f, fill=color)
        y += size * 1.2


def draw_rules(img: Image.Image):
    box = (620, 620, 1830, 690)
    d = ImageDraw.Draw(img)
    items = [("FOX ×1", RED), ("SHAMAN ×1", ROLE_COLOR["shaman"]), ("VILLAGERS ×4", (200, 200, 210))]
    x = box[0]
    for t, c in items:
        f = font(28, 900)
        tw = f.getlength(t)
        rounded(d, [x, box[1], x + tw + 36, box[3]], 20, fill=c)
        d.text((x + 18, box[1] + 16), t, font=f, fill=PAPER)
        x += tw + 60


def draw_hint(img: Image.Image, kit: Kit, names: list):
    d = ImageDraw.Draw(img)
    d.text((620, 630), "THE FOX IS ONE OF:  " + "  ·  ".join(names), font=font(34, 900), fill=GOLD)


def frame(kit: Kit, b: dict) -> Image.Image:
    sc = b["screen"]
    img = (kit.night if sc["phase"]["night"] else kit.day).convert("RGBA")
    k = b["kind"]
    if k == "hook":
        img = Image.blend(img.convert("RGB"), Image.new("RGB", (W, H), (6, 4, 8)), 0.72).convert("RGBA")
        d = ImageDraw.Draw(img)
        f, ls, size = fit(f"“{sc['quote']}”", 1400, 420, 60, 700, 34, lh=1.3)
        y = 220
        for ln in ls:
            d.text(((W - f.getlength(ln)) / 2, y), ln, font=f, fill=PAPER)
            y += int(size * 1.3)
        s = "— one of these six AIs"
        d.text(((W - font(34, 400).getlength(s)) / 2, y + 30), s, font=font(34, 400), fill=(236, 150, 140))
        for i, n in enumerate(kit.names):
            sp = kit.sprite(n, 110)
            img.alpha_composite(sp, (SEAT_X[i] - sp.width // 2, 930 - sp.height))
        return img.convert("RGB")
    draw_top(img, sc)
    draw_seats(img, kit, sc)
    if k == "host":
        face = "wink" if sc.get("reveal_roles") or sc.get("winner") == "fox" else ("side" if sc["phase"]["night"] else "front")
        draw_host(img, kit, b["text"], sc, face)
        if sc.get("card"):
            draw_card(img, sc["card"])
        if sc.get("title"):
            draw_card(img, "FOX HUNT")
        if sc.get("rules"):
            draw_rules(img)
        if sc.get("hint"):
            draw_hint(img, kit, sc["hint"])
        if sc.get("reveal") and sc["reveal"] in sc["dead"]:
            r = sc["dead"][sc["reveal"]]["role"]
            draw_center_banner(img, f"{sc['reveal'].upper()} WAS THE {r.upper()}", ROLE_COLOR[r])
        if sc.get("winner"):
            draw_center_banner(img, "THE FOX WINS" if sc["winner"] == "fox" else "THE VILLAGE WINS",
                               RED if sc["winner"] == "fox" else GOLD)
    elif k == "say":
        who = sc["highlight"]
        draw_bubble(img, kit, who, sc["say"], (150, 120, 1770, 430))
        draw_thought(img, kit, who, sc.get("thought", ""), (330, 470, 1590, 690))
    elif k == "vote":
        who = sc["highlight"]
        draw_bubble(img, kit, who, sc.get("say", ""), (80, 120, 1290, 360))
        draw_thought(img, kit, who, sc.get("thought", ""), (80, 400, 1290, 690))
        draw_votes(img, kit, sc.get("votes", []), sc.get("poll", False))
    elif k == "tally":
        draw_tally(img, kit, sc["tally"], sc.get("poll", False))
    elif k == "thought":
        draw_thought(img, kit, sc["highlight"], sc.get("thought", ""), (330, 200, 1590, 560), secret=True)
    elif k == "interview":
        draw_bubble(img, kit, sc["highlight"], sc["say"], (150, 150, 1770, 560), label=sc.get("label"))
    elif k == "roll":
        n = sc["highlight"]
        draw_center_banner(img, n.upper(), kit.color(n))
    return img.convert("RGB")


# ── 목소리 ────────────────────────────────────────────
def wav_info(p: str) -> tuple[float, int, int, int]:
    with wave.open(p) as w:
        return w.getnframes() / w.getframerate(), w.getframerate(), w.getnchannels(), w.getsampwidth()


def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def normalize(p: str):
    _, sr, ch, sw = wav_info(p)
    if (sr, ch, sw) == (SR, 1, 2):
        return
    ff = ffmpeg()
    if not ff:
        raise RuntimeError(f"{p}: {sr}Hz/{ch}ch/{sw * 8}bit — ffmpeg 없이 변환 불가")
    tmp = p + ".n.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", p, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", tmp], check=True)
    os.replace(tmp, p)


def synth(beats: list[dict], wd: str, tts=None) -> dict:
    """목소리가 있는 비트마다 wav. 캐시: (목소리, 문장) 해시."""
    if tts is None:
        import wbspark
        tts = lambda text, out, voice: wbspark.tts(text, out, voice, timeout_sec=900)  # noqa: E731
    os.makedirs(wd, exist_ok=True)
    todo = [b for b in beats if b.get("text") and b.get("voice")]

    def one(b):
        h = hashlib.sha1(f"{b['voice']}|{b['text']}".encode()).hexdigest()[:16]
        out = os.path.join(wd, f"v_{h}.wav")
        if not (os.path.exists(out) and os.path.getsize(out) > 1000):
            ok = False
            for attempt in range(4):
                if tts(b["text"], out, b["voice"]):
                    ok = True
                    break
                time.sleep(5 + attempt * 10)
            if not ok:
                return b["i"], None
        return b["i"], out

    t0, failed = time.time(), []
    by_i = {}
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for n, (i, out) in enumerate(ex.map(one, todo), 1):
            by_i[i] = out
            if out is None:
                failed.append(i)
            if n % 20 == 0 or n == len(todo):
                print(f"   🎙️ 목소리 {n}/{len(todo)} · 실패 {len(failed)} · {time.time() - t0:.0f}s", flush=True)
    if failed:
        raise RuntimeError(f"목소리 합성 실패 {len(failed)}건 — 비트 {failed[:8]}")
    for b in beats:
        if b["i"] in by_i:
            b["wav"] = by_i[b["i"]]
            normalize(b["wav"])
            b["dur"] = wav_info(b["wav"])[0]
    return {"voiced": len(todo), "tts_sec": round(time.time() - t0)}


def timeline(beats: list[dict]) -> float:
    t = 0.0
    for b in beats:
        need = b.get("min_sec", 1.5)
        if b.get("dur"):
            need = max(need, b["dur"] + GAP)
        th = b["screen"].get("thought")
        if th and b["kind"] in ("say", "vote", "thought"):
            need = max(need, len(th.split()) / READ_WPS + 1.2)
        b["start"], b["sec"] = round(t, 3), round(need, 3)
        t = round(t + b["sec"], 3)       # 영상·소리·자막이 같은 반올림 값을 쓰게
    return t


def build_audio(beats: list[dict], out: str):
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for b in beats:
            total = int(round(b["sec"] * SR))
            written = 0
            if b.get("wav"):
                with wave.open(b["wav"]) as r:
                    data = r.readframes(min(r.getnframes(), total))
                w.writeframes(data)
                written = len(data) // 2
            if total > written:
                w.writeframes(b"\x00\x00" * (total - written))


def ts(sec: float, srt: bool = True) -> str:
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), sec % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    return f"{h}:{m:02d}:{int(s):02d}" if h else f"{m:02d}:{int(s):02d}"


def build_srt(beats: list[dict], out: str) -> int:
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for b in beats:
            if not b.get("text") or not b.get("dur"):
                continue
            who = "Gumi" if b["voice"] == episode.HOST_VOICE and b["kind"] in ("host", "hook") else b["screen"].get("highlight", "")
            n += 1
            f.write(f"{n}\n{ts(b['start'])} --> {ts(b['start'] + b['dur'])}\n{who}: {b['text']}\n\n")
    return n


def chapters_text(beats: list[dict]) -> str:
    lines, seen = [], set()
    for i, name in episode.chapters(beats):
        t = 0.0 if i == 0 else beats[i]["start"]
        if name in seen:
            continue
        seen.add(name)
        lines.append(f"{ts(t, srt=False)} {name}")
    return "\n".join(lines)


def build_video(beats: list[dict], frames_dir: str, audio: str, out: str):
    ff = ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg 없음")
    lst = os.path.join(frames_dir, "frames.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for b in beats:
            f.write(f"file '{os.path.abspath(b['frame'])}'\nduration {b['sec']:.3f}\n")
        f.write(f"file '{os.path.abspath(beats[-1]['frame'])}'\n")
    cmd = [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
           "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "21",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)


# ── 썸네일 · 메타 ──────────────────────────────────────
def thumbnail(kit: Kit, match: dict, out: str):
    img = kit.night.resize((1280, 720)).convert("RGBA")
    img = Image.blend(img.convert("RGB"), Image.new("RGB", (1280, 720), (8, 4, 10)), 0.35).convert("RGBA")
    g = kit.gumi["wink"].resize((560, 560), Image.LANCZOS)
    m = Image.new("L", g.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, 559, 559], fill=255)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([690, 90, 1270, 670], fill=RED + (255,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(26)))
    img.paste(g, (700, 100), m)
    d = ImageDraw.Draw(img)
    for i, (t, c) in enumerate([("WHO IS", PAPER), ("THE FOX?", GOLD)]):
        f = font(118, 900)
        d.text((52 + 5, 70 + i * 132 + 5), t, font=f, fill=(0, 0, 0))
        d.text((52, 70 + i * 132), t, font=f, fill=c)
    d.text((58, 350), "6 AIs  ·  1 LIAR", font=font(46, 900), fill=(236, 120, 100))
    for i, n in enumerate(kit.names):
        sp = kit.sprite(n, 118)
        img.alpha_composite(sp, (60 + i * 108 - sp.width // 2 + 44, 640 - sp.height))
    img.convert("RGB").save(out, quality=92)


TITLES_FOX = ["6 AIs Played a Korean Fox-Hunting Game. {fox} Lied to Everyone.",
              "{fox} Fooled 5 Other AIs in Fox Hunt",
              "I Made 6 AIs Hunt a Fox. The Fox Was {fox}."]
TITLES_VILLAGE = ["6 AIs Played a Korean Fox-Hunting Game. Could They Catch the Liar?",
                  "5 AIs vs 1 Liar: Who Is the Fox?",
                  "I Made 6 AIs Hunt a Fox Among Them"]


def meta(match: dict, chapters: str) -> dict:
    rng = random.Random(f"title:{match['seed']}")
    fox = next(n for n, r in match["roles"].items() if r == "fox")
    title = rng.choice(TITLES_FOX if match["winner"] == "fox" else TITLES_VILLAGE).format(fox=fox)
    cast = ", ".join(f"{s['name']} ({s['backend'].split(':', 1)[-1]})" for s in match["roster"])
    desc = (f"Six AI models sit at Gumi's table for FOX HUNT. One of them is secretly a gumiho, a nine-tailed fox "
            f"from Korean folklore. The others have to find it before it's too late.\n\n"
            f"Cast: {cast}\n\n"
            f"Every line the players say and every vote they cast came from the models themselves in a real, unscripted "
            f"match. The \"really thinking\" panels show the private reasoning each model wrote before it spoke. "
            f"Host lines and the hint were written by us.\n\n⏱ Chapters\n{chapters}\n\n"
            f"Host art, voices and visuals are AI-generated. Made in Seoul.\n\n#AI #LLM #FoxHunt #Mafia #GumihoGames")
    return {"title": title[:95], "description": desc[:4900],
            "tags": ["AI", "LLM", "AI plays games", "mafia game", "werewolf", "social deduction", "Claude", "Gemma",
                     "gumiho", "Korean folklore", "AI vs AI"]}


def render(match_path: str, out_dir: str, frames_only: bool = False, tts=None) -> dict:
    with open(match_path, encoding="utf-8") as f:
        match = json.load(f)
    stem = os.path.splitext(os.path.basename(match_path))[0]
    wd = os.path.join(out_dir, f"_{stem}")
    fd = os.path.join(wd, "frames")
    os.makedirs(fd, exist_ok=True)
    kit = Kit(match)
    beats = episode.build(match)
    for b in beats:
        b["frame"] = os.path.join(fd, f"f{b['i']:04d}.jpg")
        frame(kit, b).save(b["frame"], quality=90)
    print(f"   🖼️ 화면 {len(beats)}장", flush=True)
    thumb = os.path.join(out_dir, f"{stem}_thumb.jpg")
    thumbnail(kit, match, thumb)
    if frames_only:
        timeline(beats)
        return {"beats": len(beats), "frames": fd, "thumb": thumb}
    st = synth(beats, os.path.join(wd, "voice"), tts)
    total = timeline(beats)
    audio = os.path.join(wd, "audio.wav")
    build_audio(beats, audio)
    srt = os.path.join(out_dir, f"{stem}.srt")
    n_srt = build_srt(beats, srt)
    chap = chapters_text(beats)
    video = os.path.join(out_dir, f"{stem}.mp4")
    build_video(beats, fd, audio, video)
    md = meta(match, chap)
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(md, f, ensure_ascii=False, indent=1)
    print(f"✅ {video} · {total / 60:.1f}분 · 비트 {len(beats)} · 자막 {n_srt} · 목소리 {st['tts_sec']}초", flush=True)
    return {"video": video, "thumb": thumb, "srt": srt, "meta": md, "minutes": round(total / 60, 1), **st}


def main() -> int:
    ap = argparse.ArgumentParser(description="Gumiho Games 렌더")
    ap.add_argument("match")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "gumiho", "renders"))
    ap.add_argument("--frames-only", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    render(args.match, args.out, args.frames_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
