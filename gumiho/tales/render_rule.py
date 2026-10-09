#!/usr/bin/env python3
"""Nine Tails RULES 쇼츠 렌더 — 대본(JSON) → 목소리(Spark Supertonic) · 세로 그림(Spark) → 1080x1920 mp4.

    python gumiho/tales/render_rule.py output/tales_rules/R001_name-called-at-night.json
    python gumiho/tales/render_rule.py gumiho/tales/rules_scripts/R001_name-called-at-night.json --mock   # 가짜 그림·목소리

화면(2026-10-05 벤치마킹 — 첫 1초·루프·한 방):
  · 위: 시리즈 표시 + 끝까지 떠 있는 두 줄 hook(소리 없이 넘기는 사람도 첫 프레임에 읽는다)
  · 가운데 아래: 규칙 카드 — 'RULE 3' + 큰 글자. 줄이 바뀔 때마다 튀어나오고(0.18초), 하얗게 번쩍하고, 살짝 흔들린다
  · 아래: 지금 말하는 조각(3단어)
  · 끝: 치비 구미 스티커가 튀어나와 한마디 → 마지막 0.4초는 첫 장면으로 섞여 들어간다(쇼츠가 다시 돌 때 이음새가 없게)
    (본편 링크 끝맺음은 넣지 않는다(2026-10-09) — 본편이 없고, 끝→첫 장면 루프가 이 형식의 핵심 장치다.
     "More rules tomorrow" 같은 다음 편 고리도 루프를 끊는다. 이야기 쇼츠의 끝맺음은 render_tale.CTA_*)
소리: 목소리 + 낮은 드론 + 첫 '쿵' + 규칙마다 작은 '쿵'. 전부 코드로 만든다(저작권 없음). -14 LUFS.
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
POP = 0.18                     # 규칙 카드 튀어나오는 시간
LOOP = 0.4                     # 끝 → 첫 장면 섞기
MAX_SEC = 40.0
OUT = os.path.join(ROOT, "output", "gumiho", "rules")
ASSETS = R.ASSETS
SERIES = "NINE TAILS RULES"
YELLOW = (255, 214, 64)


def gen_vertical(prompt: str, out: str, look: str, mock: bool) -> bool:
    if mock:
        return R.gen_image(prompt, out, mock=True)
    import wbspark
    for attempt in range(3):
        R.spark_wait()
        if wbspark.generate_image(R.look_prefix(look) + prompt, out, aspect="9:16", no_llm=True,
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
    """치비 구미 스티커(흰 바탕) → 가장자리에서 이어진 흰 배경만 투명하게."""
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


def plan(s: dict, voices: dict, raws: list[str]) -> dict:
    rows, t = [], 0.0
    for i, ln in enumerate(s["lines"]):
        d = R.wav_dur(voices[ln["say"]])
        rows.append({"i": i, "say": ln["say"], "text": (ln.get("text") or "").upper(), "rule": ln.get("rule"),
                     "raw": raws[i], "wav": voices[ln["say"]], "start": round(t, 3), "vdur": d,
                     "dur": round(d + GAP, 3)})
        t += d + GAP
    g = s["gumi"]
    gd = R.wav_dur(voices[g["say"]])
    gumi = {"say": g["say"], "react": g["react"], "wav": voices[g["say"]], "start": round(t + 0.1, 3), "vdur": gd}
    total = round(gumi["start"] + gd + 0.35 + LOOP, 3)
    rows[-1]["dur"] = round(total - rows[-1]["start"], 3)       # 마지막 그림이 구미 대사 동안 남는다
    return {"rows": rows, "gumi": gumi, "total": total}


class Painter:
    def __init__(self, P: dict, s: dict):
        self.P, self.s = P, s
        self.rows = P["rows"]
        self.starts = [r["start"] for r in self.rows]
        self.imgs = {r["raw"]: Image.open(r["raw"]).convert("RGB") for r in self.rows}
        self.fx = R.FX(SW, SH, seed=11)
        self.vig = R.vignette(SW, SH)
        self.ftop = R.font("sans_bold", 34)
        self.fcap = R.font("sans", 64)
        self.frule = R.font("sans_bold", 40)
        self.hook_lines, self.fhook = self._fit(s["hook"].upper(), (118, 106, 96, 86, 76, 68), SW - 110)
        self.gumi = chibi(P["gumi"]["react"])
        for r in self.rows:
            r["chunks"] = R.caption_chunks(r["say"])
            r["tlines"], r["ftext"] = self._fit(r["text"], (104, 94, 84, 76, 68, 60), SW - 120) if r["text"] else ([], None)

    def _fit(self, text: str, sizes, width) -> tuple[list[str], object]:
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        ws = text.split()
        for size in sizes:
            f = R.font("sans", size)
            cands = [[text]] if len(ws) < 3 else []
            cands += [[" ".join(ws[:k]), " ".join(ws[k:])] for k in range(1, len(ws))]
            best = min(cands, key=lambda ls: max(d.textlength(x, font=f) for x in ls)) if cands else [text]
            if max(d.textlength(x, font=f) for x in best) <= width:
                return best, f
        f = R.font("sans", sizes[-1])
        return R.wrap(d, text, f, width)[:3], f

    def base(self, r: dict, t: float) -> Image.Image:
        im = self.imgs[r["raw"]]
        p = R.ease((t - r["start"]) / max(0.5, r["dur"]))
        z = 1.0 + 0.06 * p                                     # 천천히 다가간다
        cw, ch = im.width / z, im.height / z
        cx, cy = im.width / 2, im.height / 2
        crop = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
        return crop.resize((SW, SH), Image.Resampling.BILINEAR)

    @staticmethod
    def stroke_text(d, xy, text, f, fill, sw=9):
        d.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0))

    def frame(self, t: float) -> Image.Image:
        P = self.P
        k = max(0, min(len(self.rows) - 1, R.bisect.bisect_right(self.starts, t) - 1))
        r = self.rows[k]
        fr = self.base(r, t)
        lt = t - r["start"]
        if k > 0 and lt < 0.12:                                 # 빠른 컷(섞지 않고 번쩍)
            pass
        # 끝 → 첫 장면(루프)
        if t > P["total"] - LOOP:
            q = (t - (P["total"] - LOOP)) / LOOP
            fr = Image.blend(fr, self.base(self.rows[0], 0.0), min(1.0, q))
        fr = self.fx.draw(fr, "embers", t)
        fr = ImageChops.multiply(fr, self.vig)
        # 규칙이 바뀌는 순간: 흔들림 + 번쩍
        if r["text"] and lt < 0.1:
            dx = int(10 * math.sin(lt * 90))
            fr = ImageChops.offset(fr, dx, 0)
        if r["text"] and lt < 0.09 and k > 0:
            fr = Image.blend(fr, Image.new("RGB", (SW, SH), (255, 255, 255)), 0.35 * (1 - lt / 0.09))
        d = ImageDraw.Draw(fr)
        # 위: 시리즈 표시 + hook
        tl = d.textlength(SERIES, font=self.ftop)
        d.rounded_rectangle([(SW - tl) / 2 - 24, 150, (SW + tl) / 2 + 24, 206], 12, fill=R.RED)
        d.text(((SW - tl) / 2, 157), SERIES, font=self.ftop, fill=(255, 255, 255))
        y = 232
        lh = int(self.fhook.size * 1.12)
        for ln in self.hook_lines:
            w_ = d.textlength(ln, font=self.fhook)
            self.stroke_text(d, ((SW - w_) / 2, y), ln, self.fhook, (255, 255, 255), 10)
            y += lh
        in_loop = t > P["total"] - LOOP
        # 규칙 카드(가운데 아래) — 구미가 나오면 비킨다(10/5 실렌더: 치비가 마지막 규칙 글자를 가렸다)
        gumi_on = t >= P["gumi"]["start"] - 0.05
        if r["text"] and not in_loop and not gumi_on:
            s_ = min(1.0, lt / POP) if lt >= 0 else 1.0
            s_ = 1.0 + 0.25 * (1 - s_) ** 2 if s_ < 1 else 1.0          # 크게 → 제자리(튀어나옴)
            card = Image.new("RGBA", (SW, 520), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            yy = 20
            if r["rule"]:
                lab = f"RULE {r['rule']}"
                lw = cd.textlength(lab, font=self.frule)
                cd.rounded_rectangle([(SW - lw) / 2 - 22, yy, (SW + lw) / 2 + 22, yy + 62], 14, fill=(12, 8, 12, 230),
                                     outline=YELLOW + (255,), width=3)
                cd.text(((SW - lw) / 2, yy + 9), lab, font=self.frule, fill=YELLOW)
                yy += 86
            lh2 = int(r["ftext"].size * 1.1)
            for ln in r["tlines"]:
                w_ = cd.textlength(ln, font=r["ftext"])
                cd.text(((SW - w_) / 2, yy), ln, font=r["ftext"], fill=(255, 255, 255), stroke_width=11,
                        stroke_fill=(0, 0, 0))
                yy += lh2
            if s_ != 1.0:
                cw_, ch_ = int(SW * s_), int(520 * s_)
                card = card.resize((cw_, ch_), Image.Resampling.BILINEAR).crop(((cw_ - SW) // 2, (ch_ - 520) // 2,
                                                                    (cw_ - SW) // 2 + SW, (ch_ - 520) // 2 + 520))
            fr.paste(card, (0, 1020), card)
        # 아래: 말하는 조각
        g = P["gumi"]
        speaking = None
        if 0 <= lt <= r["vdur"] + 0.15 and t < g["start"]:
            speaking = (r, lt)
        elif g["start"] <= t <= g["start"] + g["vdur"] + 0.15:
            speaking = ({"chunks": R.caption_chunks(g["say"]), "vdur": g["vdur"]}, t - g["start"])
        if speaking and not in_loop:
            rr, ll = speaking
            tot = sum(len(c) for c in rr["chunks"]) or 1
            acc, cur = 0.0, rr["chunks"][-1]
            for c in rr["chunks"]:
                acc += rr["vdur"] * len(c) / tot
                if ll < acc:
                    cur = c
                    break
            w_ = d.textlength(cur, font=self.fcap)
            self.stroke_text(d, ((SW - w_) / 2, 1585), cur, self.fcap, YELLOW if t >= g["start"] else (255, 255, 255), 8)
        # 끝: 치비 구미(통통 튀며 등장)
        if t >= g["start"] - 0.05 and not in_loop:
            q = min(1.0, (t - g["start"] + 0.05) / 0.3)
            sc = 0.3 + 0.7 * q + 0.12 * math.sin(q * math.pi)
            gi = self.gumi.resize((max(8, int(self.gumi.width * sc)), max(8, int(self.gumi.height * sc))), Image.Resampling.BILINEAR)
            gx, gy = (SW - gi.width) // 2, 1540 - gi.height          # 가운데, 자막(1585) 바로 위
            fr.paste(gi, (gx, gy), gi)
        if in_loop:   # 첫 장면으로 섞이는 동안 hook 만 남긴다(첫 프레임과 같게)
            pass
        return fr


def render(path: str, out_dir: str = OUT, work: str | None = None, mock: bool = False) -> dict:
    import numpy as np
    s = RU.load(path) if hasattr(RU, "load") else json.load(open(path, encoding="utf-8"))
    errs = RU.check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stem = f"R{s['id']:03d}_{s['slug']}"
    wd = work or os.path.join(ROOT, "work", "rules", stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    texts = [ln["say"] for ln in s["lines"]] + [s["gumi"]["say"]]
    voices = R.synth(texts, os.path.join(wd, "voice"), mock)
    raws = []
    for i, ln in enumerate(s["lines"]):
        look = ln.get("look") or s.get("look")
        raw = os.path.join(wd, f"raw_{R.h16(R.look_prefix(look), ln['img'], mock, 'v')}.png")
        if not (os.path.exists(raw) and os.path.getsize(raw) > 10000):
            if not gen_vertical(ln["img"], raw, look, mock):
                raise RuntimeError(f"그림 실패: {ln['img'][:60]}")
        prep = raw[:-4] + "_v.jpg"
        if not os.path.exists(prep):
            fit_vertical(raw, prep)
        raws.append(prep)
        print(f"   🖼️ 그림 {i + 1}/{len(s['lines'])}", flush=True)
    P = plan(s, voices, raws)
    if P["total"] > MAX_SEC:
        raise RuntimeError(f"{P['total']}초 > {MAX_SEC}")
    pa = Painter(P, s)
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
    for r in P["rows"][1:]:
        if r["text"]:
            hit = R.boom(rng)[: int(SR * 0.6)] * vr * 0.9
            a = int(r["start"] * SR)
            mix[a:a + len(hit)] += hit[: max(0, n - a)]
    mix = mix[: int(P["total"] * SR)]
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    R.wav_write(raw, mix)
    aud = os.path.join(wd, "audio.m4a")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
          "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", aud])
    video = os.path.join(out_dir, f"{stem}.mp4")
    R.mux(silent, aud, video)
    # 첫 프레임(썸네일 겸 확인용)
    first = os.path.join(out_dir, f"{stem}_first.jpg")
    pa.frame(0.05).save(first, quality=88)
    meta = {"video": video, "first": first, "sec": P["total"], "lines": len(P["rows"]), "mock": mock, "stem": stem}
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
    a = ap.parse_args()
    render(a.script, a.out, a.work, a.mock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
