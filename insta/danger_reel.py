#!/usr/bin/env python3
"""인스타 밤 편(c) '위험한 진짜 이유' — 크림 카드형 반전 (2026-10-31).

벤치마크: 뭘보냥 '전기장판이 위험한 이유'(15초 · 이틀 585만 · 10/31 조사) — 크림/흰 카드 위 프로필 줄 + 굵은 제목, 가운데 동물,
  끝 무렵 한 줄 반전. 제목은 무섭고 끝은 귀엽다(진짜 위험이 아니라 '위험할 만큼 귀엽다').
편성: pick_plan.c_plan — 11/08 첫 장부터 이틀에 한 편(밤 편 c, 21:20). 무엇을 쓸지 = 그날 insta/danger_catalog.json 항목(src_n).
화면(1080×1920 · 14초 · 목소리 없음 · 코드로 만든 피아노):
  크림 바탕 위 흰 게시물 카드 — 동그란 프로필 + zerocrew.studio + '동물 상식 · 위험한 진짜 이유 #N' · 굵은 두 줄 제목(catalog title,
  '위험한' 만 빨강) · 동물 실사 그림(932×580, 5B 클립을 앞→뒤로 재생한 뒤 같은 구도의 고화질 그림으로 · 천천히 다가감 + 물결 흔들림)
  → 2.2초 회색 헛짚기('독침 때문에…?') → 7.4초 반전 한 줄(형광펜) → 9.6초 덧붙임 → 출처 줄(32px, catalog source_label).
  ★위치가 틀릴 수 있는 장식(그림 위 빨간 동그라미 등)은 없다 — 그림을 매번 새로 그려서 좌표를 미리 알 수 없다.
그림이 실제 종과 다를 수 있으면 catalog image_note 를 캡션 AI 표시 줄에 코드가 밝힌다(대본이 못 뺀다).
5B 영상(wan2.2 · 768×512 · 1.4초)은 장식 — 실패하면 정지 그림만(경고). 그림을 끝내 못 그리면 렌더가 멈춘다(다른 꼴과 같다).

    python insta/pick_reel.py check <danger 대본.json>
    python insta/pick_reel.py render <danger 대본.json> --out … [--mock]
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bc_kit as B  # noqa: E402
import pick_plan as P  # noqa: E402
import render_reel as R  # noqa: E402
import worker_reel as WR  # noqa: E402  (catalog facts 검사를 같이 쓴다)

KIND = P.DANGER
W, H = B.W, B.H
TOTAL, T_TEASE, T_PAYOFF, T_ASIDE = 14.0, 2.2, 7.4, 9.6
CREAM, PAPER = (238, 231, 216), (255, 253, 247)
INK, GRAY, RED, HL = (22, 22, 24), (118, 112, 102), (226, 64, 52), (255, 222, 89)
PROFILE = os.path.join(HERE, "assets", "profile.jpg")
CARD = (34, 196, 1046, 1462)                              # 흰 게시물 카드(크림 바탕 위)
VIS = (74, 586, 1006, 1166)                               # 동물 화면 932×580
VW, VH = VIS[2] - VIS[0], VIS[3] - VIS[1]
OVER = 1.12
BOB = (0.025, 3.6)                                        # 클립 뒤 정지 그림 물결(세로 비율 · 주기 초)
TEXT_X, TEXT_W = 74, 880
TEASE_MAX, PAYOFF_MAX, ASIDE_MAX = 18, 24, 30
STYLE = ", photorealistic wildlife photo, soft natural light, shallow depth of field, cute, sharp focus, high detail"
MOTION_DEFAULT = "the animal moves gently, soft natural motion, static camera, very subtle movement"


# ── 검사 ──────────────────────────────────────────────
def entry_errs(e: dict) -> list[str]:
    n = e.get("n")
    errs = []
    if P.c_kind_of_n(n) != KIND:
        errs.append(f"{n}: 번호는 {P.C_N0[KIND]}~{P.C_N0[KIND] + 99}")
    if not B._SLUG.fullmatch(e.get("slug") or ""):
        errs.append(f"{n}: slug 는 영어 소문자·하이픈")
    if P._date_or_none(e.get("from")) is None:
        errs.append(f"{n}: from(YYYY-MM-DD) 없음 — 없으면 편성되지 않는다")
    errs += WR._fact_errs(e)
    t = e.get("title")
    if not (isinstance(t, list) and len(t) == 2 and t[1] == "진짜 이유" and isinstance(t[0], str) and "위험한" in t[0]
            and (e.get("animal_ko") or "?") in t[0]):
        errs.append(f"{n}: title 은 ['<animal_ko>가 위험한', '진짜 이유']")
    for k in ("animal_ko", "tease_idea", "payoff_idea", "source_label"):
        if not isinstance(e.get(k), str) or not e[k].strip():
            errs.append(f"{n}: {k} 없음")
    if len(e.get("source_label") or "") > 40:
        errs.append(f"{n}: source_label 40자 이내")
    errs += B.img_errs(f"{n} image", e.get("image"), 30, 600)
    if not isinstance(e.get("motion"), str) or "static camera" not in e["motion"]:
        errs.append(f"{n}: motion 은 '… static camera, very subtle movement'")
    for k in ("payoff_idea", "aside_idea", "tease_idea"):
        bad = B.unbacked(e.get(k) or "", e)
        if bad:
            errs.append(f"{n}: {k} 에 facts 에 없는 숫자 {bad}")
    if not isinstance(e.get("image_note"), str):
        errs.append(f"{n}: image_note 는 글(그림이 실제와 다를 수 있으면 한 줄 · 아니면 빈 글)")
    return errs


def _one_line(text: str, kind: str, hi: int, lo: int) -> int | None:
    """한 줄(TEXT_W)에 들어가는 가장 큰 글자 크기 — 안 들어가면 None."""
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for size in range(hi, lo - 1, -2):
        if d.textlength(text, font=R.font(kind, size)) <= TEXT_W:
            return size
    return None


def check(s: dict) -> list[str]:
    errs, e, d = B.head_errs(s, KIND, P.c_n, P.danger_no, "card_no")
    if e is None:
        return errs
    if s.get("title") != e.get("title"):
        errs.append(f"title 은 catalog {e['n']} 그대로: {e.get('title')}")
    errs += B.img_errs("image", s.get("image"), 30, 600)
    if s.get("motion") is not None:
        errs += B.img_errs("motion", s.get("motion"), 10, 240)
    if "sticker" in s:
        errs.append("sticker 는 쓰지 않는다 — 그림을 매번 새로 그려서 위치가 맞는다는 보장이 없다")
    tease, payoff, aside = s.get("tease"), s.get("payoff"), s.get("aside")
    if not isinstance(tease, str) or not 2 <= len(tease) <= TEASE_MAX or not tease.rstrip().endswith("?"):
        errs.append(f"tease(헛짚기)는 2~{TEASE_MAX}자 · '?' 로 끝('독침 때문에…?')")
    elif _one_line(tease, "bold", 54, 54) is None:
        errs.append("tease 가 한 줄에 안 들어간다")
    if not isinstance(payoff, str) or not 4 <= len(payoff) <= PAYOFF_MAX or "\n" in payoff:
        errs.append(f"payoff(반전 한 줄)는 4~{PAYOFF_MAX}자 한 줄")
    elif _one_line(payoff, "head", 72, 56) is None:
        errs.append("payoff 가 한 줄(56px 이상)에 안 들어간다 — 줄일 것")
    if aside is not None and (not isinstance(aside, str) or not 0 < len(aside) <= ASIDE_MAX or "\n" in aside
                              or _one_line(aside, "reg", 36, 36) is None):
        errs.append(f"aside(덧붙임)는 한 줄 {ASIDE_MAX}자 이내 — 안 쓰면 필드를 빼요")
    for k, t in (("tease", tease), ("payoff", payoff), ("aside", aside)):
        if isinstance(t, str):
            bad = B.unbacked(t, e)
            if bad:
                errs.append(f"{k}: catalog {e['n']} facts 에 없는 숫자 {bad} — 숫자는 그 항목 facts 에서만")
    errs += B.caption_errs(s, e)
    texts = [t for t in (tease, payoff, aside, s.get("caption"), s.get("question")) if isinstance(t, str)]
    errs += B.word_errs(texts, [s.get("image") or "", s.get("motion") or ""])
    return errs


def warns(s: dict) -> list[str]:
    return []


# ── 그림 ──────────────────────────────────────────────
def image_prompt(s: dict) -> str:
    p = s["image"].rstrip(" .,")
    return p if "photo" in p.lower() else p + STYLE


def assets(s: dict, wd: str, mock: bool) -> dict:
    e = P.c_entry(s["src_n"]) or {}
    prompt = image_prompt(s)
    h = hashlib.sha1((prompt + str(mock)).encode()).hexdigest()[:10]
    still, clip, log = os.path.join(wd, f"still_{h}.png"), os.path.join(wd, f"clip_{h}.mp4"), []
    if mock:
        if not os.path.exists(still):
            B.mock_image(prompt, still, 1344, 896)
        return {"still": still, "clip": None, "spark": []}
    if os.path.exists(still) and os.path.getsize(still) > 5000 and not B.broken_image(still):   # 다시 돌릴 때 — 클립은 있으면 쓴다
        return {"still": still, "clip": clip if os.path.exists(clip) else None, "spark": []}
    jid = B.spark_image(prompt, still, 1344, 896, seed=e.get("n"), log=log)
    ok = B.spark_video(jid, s.get("motion") or e.get("motion") or MOTION_DEFAULT, clip, log=log)
    return {"still": still, "clip": clip if ok else None, "spark": log}


# ── 화면 ──────────────────────────────────────────────
class Card:
    def __init__(self, s: dict, a: dict):
        self.s = s
        self.e = P.c_entry(s["src_n"]) or {}
        self.still = B.cover(Image.open(a["still"]).convert("RGB"), int(VW * OVER), int(VH * OVER))
        self.clip, self.fps = B.load_clip(a["clip"], int(VW * OVER), int(VH * OVER)) if a.get("clip") else ([], 16.0)
        self.mask = B.rounded_mask(VW, VH, 30)
        self.payoff_f = R.font("head", _one_line(s["payoff"], "head", 72, 56) or 56)
        self.base = self._base()

    def _base(self) -> Image.Image:
        im = Image.new("RGB", (W, H), CREAM)
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).rounded_rectangle((CARD[0] + 6, CARD[1] + 16, CARD[2] - 6, CARD[3] + 20), 44, fill=60)
        im.paste(Image.new("RGB", (W, H), (160, 148, 128)), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)))
        ImageDraw.Draw(im).rounded_rectangle(CARD, 40, fill=PAPER)
        d = ImageDraw.Draw(im)
        S = 92
        try:
            pf = Image.open(PROFILE).convert("RGB").resize((S, S), B.LZ)
        except OSError:                                    # 프로필 그림이 없으면 남색 동그라미
            pf = Image.new("RGB", (S, S), (40, 52, 90))
        m = Image.new("L", (S * 4, S * 4), 0)
        ImageDraw.Draw(m).ellipse((0, 0, S * 4 - 1, S * 4 - 1), fill=255)
        im.paste(pf, (74, 232), m.resize((S, S), B.LZ))
        d.text((186, 240), "zerocrew.studio", font=R.font("bold", 40), fill=INK)
        d.text((186, 290), f"동물 상식 · {P.C_SERIES[KIND]} #{self.s['card_no']}", font=R.font("reg", 28), fill=GRAY)
        title = self.s["title"]
        size = next((z for z in range(90, 68, -2) if all(d.textlength(t, font=R.font("head", z)) <= TEXT_W for t in title)), 68)
        f = R.font("head", size)
        y = 362
        for ln in title:
            x = TEXT_X
            segs = [(ln, INK)]
            if "위험한" in ln:
                a_, b_ = ln.split("위험한", 1)
                segs = [(a_, INK), ("위험한", RED), (b_, INK)]
            for seg, col in segs:
                if seg:
                    d.text((x, y), seg, font=f, fill=col)
                    x += d.textlength(seg, font=f)
            y += 104
        return im

    def visual(self, t: float) -> Image.Image:
        z = 1.0 + 0.10 * B.ease(t / TOTAL)
        end = B.clip_span(self.clip, self.fps)
        cy = 0.5 + BOB[0] * B.ease((t - end) / 1.2) * math.sin(2 * math.pi * max(0.0, t - end) / BOB[1])
        fr = B.view(self.still, z, VW, VH, OVER, cy)
        v, a = B.pingpong(self.clip, self.fps, t)
        if v is not None:
            v = B.view(v, z, VW, VH, OVER)
            fr = Image.blend(v, fr, a) if a > 0 else v
        if t >= T_PAYOFF:                                  # 반전 순간 살짝 밝아졌다 돌아온다(위치 없는 강조)
            k = max(0.0, 1 - (t - T_PAYOFF) / 0.5)
            if k > 0:
                fr = Image.blend(fr, Image.new("RGB", fr.size, (255, 255, 255)), 0.35 * k)
        return fr

    def frame(self, t: float) -> Image.Image:
        im = self.base.copy()
        im.paste(self.visual(t), (VIS[0], VIS[1]), self.mask)
        d = ImageDraw.Draw(im, "RGBA")
        y0 = VIS[3] + 34
        s = self.s
        if T_TEASE <= t < T_PAYOFF:
            a = B.clamp((t - T_TEASE) / 0.35) * (1 - B.clamp((t - T_PAYOFF + 0.25) / 0.25))
            B.text_a(im, (TEXT_X, y0 + 12), s["tease"], R.font("bold", 54), GRAY, a)
        if t >= T_PAYOFF:
            p = B.clamp((t - T_PAYOFF) / 0.3)
            f = self.payoff_f
            yy = y0 + int((1 - B.ease(p)) * 20)
            w = d.textlength(s["payoff"], font=f)
            hw = B.ease((t - T_PAYOFF - 0.15) / 0.4)       # 형광펜이 왼쪽 → 오른쪽
            if hw > 0:
                d.rounded_rectangle((TEXT_X - 8, yy + f.size * 0.52, TEXT_X - 8 + (w + 16) * hw, yy + f.size * 1.12), 8,
                                    fill=HL + (235,))
            B.text_a(im, (TEXT_X, yy), s["payoff"], f, INK, p)
            if s.get("aside") and t >= T_ASIDE:
                B.text_a(im, (TEXT_X, yy + f.size + 26), s["aside"], R.font("reg", 36), GRAY, B.clamp((t - T_ASIDE) / 0.35))
            B.text_a(im, (TEXT_X, 1388), self.e.get("source_label", ""), R.font("reg", B.SRC_PX), (140, 134, 124), p)
        return im


# ── 캡션·렌더 ─────────────────────────────────────────
def caption_of(s: dict) -> str:
    e = P.c_entry(s.get("src_n")) or {}
    note = (e.get("image_note") or "").strip()
    ai = "AI로 만든 이미지·영상이에요" + (f"({note})" if note else "") + "."
    return B.caption(f"{P.C_SERIES[KIND]} #{s.get('card_no')}", s, e, ai)


def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    errs = check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    card = Card(s, a)
    wav = B.piano_bed(TOTAL, os.path.join(wd, "bed.wav"))
    out = os.path.join(out_dir, f"{stem}.mp4")
    B.mux(card.frame, TOTAL, wav, out, wd)
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    card.frame(0.5).save(cover, "JPEG", quality=90)          # 커버는 제목·동물(반전은 스포일러라 안 쓴다)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    B.contact_sheet(card.frame, [0.0, T_TEASE + 1.2, T_PAYOFF + 0.6, TOTAL - 0.3], sheet)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "src_n": s.get("src_n"), "video": out,
            "cover": cover, "sheet": sheet, "seconds": TOTAL, "voice": "none", "caption": caption_of(s),
            "threads_images": [], "spark": a["spark"], "clip": bool(a.get("clip"))}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta
