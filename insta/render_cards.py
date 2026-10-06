#!/usr/bin/env python3
"""카드(캐러셀) 렌더 — 릴스와 같은 대본 JSON → 4:5 JPEG 슬라이드(1080×1350) · 한눈에 보기 · 메타(게시용 캡션).

    python insta/render_cards.py insta/samples/first-second.json --stats output/insta_render/stats.json
    python insta/render_cards.py <script> --mock        # Spark·네트워크 없이(가짜 그림·썸네일·숫자) — 테스트(게시 불가)

인스타·쓰레드에서 옆으로 넘겨 보는 카드. 릴스와 ★같은 대본·같은 글꼴·색·실물 화면(render_reel.Visuals)을 쓴다.
  1장   훅 — 위 두 줄 제목(headline)을 크게 + 첫 장면 화면. 격자 미리보기(3:4, 예전 1:1 가운데)에서도 제목이 읽히게
  2장~  장면 하나 = 한 장: 위에 그 장면 말(숫자 채운 화면 글자, 숫자는 노란색), 아래에 실물 화면(릴스 패널 그대로)
        · 연달아 같은 화면(단계 목록에서 강조만 바뀌는 것)은 한 장으로 합친다(말은 첫 장면 것)
        · 가운데 장이 8장을 넘으면 분위기 그림부터 뺀다(img → gumi → text → chat → …)
  끝장  저장·팔로우 + 두 채널(프로필 링크)
결정론: 같은 대본·같은 숫자 → 같은 슬라이드(무작위 없음 — mock 그림도 프롬프트로 시드).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import insta as I  # noqa: E402
import render_reel as R  # noqa: E402  (글꼴·색·그림·실물 화면을 그대로 쓴다)

W, H = 1080, 1350
MIN_SLIDES, MAX_SLIDES = 2, 10            # 인스타 캐러셀 2~10장(쓰레드는 20장까지)
POINTS_MAX = MAX_SLIDES - 2               # 훅·끝장을 뺀 가운데 장
QUALITY = 90

# ── 배치(1080×1350) ──
TOP_Y = 56                                # 위 한 줄: 계정 이름표 · 쪽수
TEXT_BOX = (60, 116, 1020, 496)           # 장면 말 — 짧으면 64px, 한 장면 최대(75자)도 들어가게 줄인다
TEXT_MAX, TEXT_MIN = 64, 38
PANEL_XY = (60, 520)                      # 실물 화면 = 릴스 패널 960×752 그대로 → 아래 끝 1272
PROG = (60, 1300, 1020, 1306)             # 넘긴 만큼 차는 줄(릴스 진행 줄과 같은 모양)
SQUARE = (0, 135, 1080, 1215)             # 예전 프로필 격자(1:1 가운데)
GRID34 = (34, 0, 1046, 1350)              # 지금 프로필 격자(3:4 가운데)
HOOK_TAG_Y = 150
HOOK_HEAD = (60, 236, 1020, 508)          # 훅 제목 — 1:1 안
HOOK_PANEL_Y = 536                        # 훅 화면 아래 끝 1183 — 1:1 안
HOOK_PANEL_SCALE = 0.86                   # 훅의 첫 장면 화면(826×647) — 1:1 안
DROP_ORDER = ("img", "gumi", "text", "chat", "flow", "thumb", "steps", "bars", "vs", "stat", "week")

BRAND = "AI 유튜브 운영 · 실제 기록"
DARK = (20, 20, 24)
CHANNEL_NOTE = {"wb": "한국어", "ntt": "영어 설화"}
CTA = {"guide": ["저장해 두고", "그대로 따라 해 보세요"], "report": ["다음 주에도", "숫자 그대로 올려요"]}
CTA_FOLLOW = "팔로우해 두면 월·수·금 가이드, 일요일 성적표"
CTA_LINK = "두 채널은 프로필 링크에서 볼 수 있어요"


# ── 계획(글꼴 없이 — 테스트 가능) ──────────────────────
def _same(a: dict, b: dict) -> bool:
    """강조(hi)만 다른 같은 화면인가."""
    return {k: v for k, v in a.items() if k != "hi"} == {k: v for k, v in b.items() if k != "hi"}


def card_plan(s: dict, ctx: dict | None = None) -> dict:
    """대본 → {"hook": 첫 장면, "points": 가운데 장들, "dropped": 뺀 장, "count": 전체 장 수}.
    ctx 가 있으면 장면 말(text)을 화면 글자로 채운다(없으면 자리표시자 그대로)."""
    items: list[dict] = []
    for i, x in enumerate(s["scenes"]):
        show = x.get("show") or {}
        kind = next((k for k in I.VISUALS if k in show), None)
        if kind is None:
            continue
        text = I.resolve(x.get("say", ""), ctx) if ctx is not None else x.get("say", "")
        if items and items[-1]["kind"] == kind and _same(items[-1]["show"], show):
            items[-1]["scenes"].append(i)
            continue
        items.append({"scenes": [i], "kind": kind, "show": show, "text": text})
    if not items:
        raise ValueError("화면이 있는 장면이 없다")
    hook, points, dropped = items[0], items[1:], []
    while len(points) > POINTS_MAX:                # 분위기 그림부터, 같은 종류면 뒤에서부터 뺀다
        k = min(range(len(points)), key=lambda j: (DROP_ORDER.index(points[j]["kind"]), -j))
        dropped.append(points.pop(k))
    return {"hook": hook, "points": points, "dropped": dropped, "count": len(points) + 2}


# ── 그리기 ────────────────────────────────────────────
class CardVisuals(R.Visuals):
    """릴스 실물 화면 그대로 — 단계 목록만 카드용(강조 한 줄 대신 번호 전부 켬 · hi=-1 이면 체크 표시)."""

    def v_steps(self, sh_, show, p, q, t):
        if int(show.get("hi", -1)) == -1:
            return super().v_steps(sh_, show, 1.0, 1.0, t)
        fr = self.bg.copy()
        d = ImageDraw.Draw(fr, "RGBA")
        steps = [self.S(x) for x in show["steps"]]
        n = len(steps)
        row = min(150, (R.PH - 80) / n)
        top = (R.PH - row * n) / 2
        f = R.fit(d, steps, "bold", 54, 36, R.PW - 220)
        fn = R.font("head", 44)
        for k, txt in enumerate(steps):
            cy = top + k * row + row / 2
            d.ellipse([96 - 36, cy - 36, 96 + 36, cy + 36], fill=R.ACCENT)
            num = str(k + 1)
            d.text((96 - R.tlen(d, num, fn) / 2, cy - fn.size * 0.62), num, font=fn, fill=DARK)
            d.text((160, cy - f.size * 0.62), txt, font=f, fill=R.INK)
        return fr


def background() -> Image.Image:
    """릴스 배경과 같은 남색 그라데이션 + 위쪽 호박색 빛(4:5)."""
    g = Image.linear_gradient("L").resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), R.BG_BOT), Image.new("RGB", (W, H), R.BG_TOP), g)
    glow = Image.radial_gradient("L").resize((W, W)).point(lambda v: int(max(0, 150 - v) * 0.35))
    bg.paste(Image.new("RGB", (W, W), (60, 52, 20)), (0, -W // 2 + 200), glow)
    return bg


def rich_line(d: ImageDraw.ImageDraw, x: float, y: float, line: str, f, base=R.INK):
    """낱말 단위로 — 숫자가 든 낱말은 노란색(릴스 자막과 같다)."""
    for w_ in line.split(" "):
        d.text((x, y), w_, font=f, fill=R.ACCENT if re.search(r"\d", w_) else base)
        x += R.tlen(d, w_ + " ", f)


def chip(d, x: float, y: float, text: str, f, fg=DARK, bg=R.ACCENT, pad=(22, 12)) -> float:
    """둥근 이름표 — 오른쪽 끝 x 를 돌려준다."""
    tw = R.tlen(d, text, f)
    bb = f.getbbox("가")
    d.rounded_rectangle([x, y, x + tw + pad[0] * 2, y + bb[3] + pad[1] * 2], 18, fill=bg)
    d.text((x + pad[0], y + pad[1] - bb[1] // 2), text, font=f, fill=fg)
    return x + tw + pad[0] * 2


def arrow(d, x: float, y: float, size: float, col):
    """오른쪽 화살표(글꼴에 기대지 않고 그린다)."""
    d.line([(x, y), (x + size, y)], fill=col, width=max(3, int(size / 9)))
    d.polygon([(x + size + 4, y), (x + size - size * 0.38, y - size * 0.32), (x + size - size * 0.38, y + size * 0.32)],
              fill=col)


def bookmark(d, cx: float, top: float, w: float, h: float, col):
    """인스타 '저장' 모양."""
    x0, x1 = cx - w / 2, cx + w / 2
    d.rounded_rectangle([x0, top, x1, top + h * 0.6], 10, fill=col)
    d.polygon([(x0, top + 20), (x1, top + 20), (x1, top + h), (cx, top + h * 0.72), (x0, top + h)], fill=col)


class Cards:
    def __init__(self, s: dict, ctx: dict, stats: dict | None, plan: dict):
        self.s, self.ctx, self.plan = s, ctx, plan
        self.n = plan["count"]
        self.vis = CardVisuals([], ctx, stats)
        self.mask = R.rounded_mask(R.PW, R.PH, 30)
        entry = I.topic_entry(s["topic"]) if s["format"] == "guide" else None
        self.tag = f"가이드 {entry['id']:02d}" if entry else "주간 성적표"

    def panel(self, it: dict) -> Image.Image:
        sh_ = {"kind": it["kind"], "show": it["show"], "dur": 10.0, "asset": it.get("asset")}
        t = 0.0 if it["kind"] in ("img", "gumi") else sh_["dur"]      # 그림은 확대 전, 나머지는 다 나온 뒤
        return self.vis.draw(sh_, t, settled=True)

    def _frame(self, k: int, top: bool = True) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        im = background()
        d = ImageDraw.Draw(im)
        if top:
            ft = R.font("bold", 28)
            d.text((60, TOP_Y), BRAND, font=ft, fill=R.MUTED)
            page = f"{k} / {self.n}"
            d.text((1020 - R.tlen(d, page, ft), TOP_Y), page, font=ft, fill=R.MUTED)
        d.rectangle(PROG, fill=(38, 42, 54))
        d.rectangle([PROG[0], PROG[1], PROG[0] + (PROG[2] - PROG[0]) * k / self.n, PROG[3]], fill=R.ACCENT)
        return im, d

    def hook(self) -> Image.Image:
        im, d = self._frame(1, top=False)
        ft = R.font("bold", 32)
        chip(d, 60, HOOK_TAG_Y, self.tag, ft)
        d.text((1020 - R.tlen(d, BRAND, R.font("bold", 30)), HOOK_TAG_Y + 12), BRAND, font=R.font("bold", 30),
               fill=R.MUTED)
        lines = [I.resolve(h, self.ctx) for h in self.s["headline"]]
        x0, y0, x1, y1 = HOOK_HEAD
        f = R.fit(d, lines, "head", 140, 60, x1 - x0)
        lh = f.size * 1.16
        y = y0 + ((y1 - y0) - lh * len(lines)) / 2
        for k, ln in enumerate(lines):
            col = R.INK if (k == 0 and len(lines) == 2) else R.ACCENT
            d.text((x0, y), ln, font=f, fill=col)
            y += lh
        pan = self.panel(self.plan["hook"])
        pw, ph = round(R.PW * HOOK_PANEL_SCALE), round(R.PH * HOOK_PANEL_SCALE)
        im.paste(pan.resize((pw, ph), Image.LANCZOS), ((W - pw) // 2, HOOK_PANEL_Y), R.rounded_mask(pw, ph, 26))
        fh = R.font("bold", 34)
        hint = "옆으로 넘겨 보세요"
        tw = R.tlen(d, hint, fh)
        x = (W - tw - 70) / 2
        d.text((x, 1226), hint, font=fh, fill=R.INK)
        arrow(d, x + tw + 18, 1226 + fh.size * 0.62, 44, R.ACCENT)
        return im

    def point(self, k: int, it: dict) -> Image.Image:
        im, d = self._frame(k)
        x0, y0, x1, y1 = TEXT_BOX
        for size in range(TEXT_MAX, TEXT_MIN - 1, -2):     # 상자 높이에 들어가는 가장 큰 글자(75자면 약 46px·5줄)
            f = R.font("bold", size)
            ls = R.wrap(d, it["text"], f, x1 - x0)
            if len(ls) * size * 1.3 <= y1 - y0:
                break
        ls = ls[: int((y1 - y0) // (f.size * 1.3))]         # 검사(SAY_MAX)를 넘은 글이 와도 아래 화면을 덮지 않게
        lh = f.size * 1.3
        y = y0 + ((y1 - y0) - lh * len(ls)) / 2
        for ln in ls:
            rich_line(d, x0, y, ln, f)
            y += lh
        im.paste(self.panel(it), PANEL_XY, self.mask)
        return im

    def cta(self, ai_art: bool) -> Image.Image:
        im, d = self._frame(self.n)
        bookmark(d, W / 2, 150, 92, 128, R.ACCENT)
        lines = CTA.get(self.s["format"], CTA["guide"])
        f = R.fit(d, lines, "head", 104, 60, 960)
        y = 320
        for k, ln in enumerate(lines):
            d.text(((W - R.tlen(d, ln, f)) / 2, y), ln, font=f, fill=R.ACCENT if k == len(lines) - 1 else R.INK)
            y += f.size * 1.18
        fo = R.fit(d, [CTA_FOLLOW], "bold", 42, 30, 960)
        d.text(((W - R.tlen(d, CTA_FOLLOW, fo)) / 2, y + 36), CTA_FOLLOW, font=fo, fill=R.MUTED)
        box = (60, 740, 1020, 1150)
        d.rounded_rectangle(box, 30, fill=(18, 21, 29), outline=R.LINE, width=2)
        fl = R.font("bold", 34)
        d.text((104, 782), CTA_LINK, font=fl, fill=R.MUTED)
        chans = I.catalog()["channels"]
        fn, fc = R.font("head", 58), R.font("bold", 32)
        for j, key in enumerate(("wb", "ntt")):
            cy = 900 + j * 138
            d.polygon([(108, cy - 26), (108, cy + 26), (150, cy)], fill=R.ACCENT)        # 재생 모양
            name = chans[key]["name"]
            d.text((180, cy - fn.size * 0.62), name, font=fn, fill=R.INK)
            note = CHANNEL_NOTE.get(key, chans[key].get("lang", ""))
            nw = R.tlen(d, note, fc) + 44
            chip(d, box[2] - 44 - nw, cy - 30, note, fc, fg=R.INK, bg=(38, 42, 54))
        foot = "숫자는 유튜브 실측" + (" · 일부 그림은 AI" if ai_art else "")
        fr = R.font("reg", 28)
        d.text(((W - R.tlen(d, foot, fr)) / 2, 1196), foot, font=fr, fill=R.DIM)
        return im


def sheet(paths: list[str], out: str, cols: int = 5):
    """사람 확인용 — 전체 장을 한 장에(1/5 크기)."""
    tw, th = W // 5, H // 5
    rows = (len(paths) + cols - 1) // cols
    sh = Image.new("RGB", (tw * cols, th * rows), (0, 0, 0))
    for k, p in enumerate(paths):
        sh.paste(Image.open(p).resize((tw, th), Image.LANCZOS), ((k % cols) * tw, (k // cols) * th))
    sh.save(out, "JPEG", quality=85)


def save(im: Image.Image, path: str, quality: int = QUALITY):
    # 4:4:4 — 노란 숫자·가는 글자 가장자리가 번지지 않게. optimize 는 결과가 늘 같다(결정론)
    im.convert("RGB").save(path, "JPEG", quality=quality, subsampling=0, optimize=True)


def render(path: str, out_dir: str, work: str, stats_path: str | None = None, mock: bool = False,
           quality: int = QUALITY) -> dict:
    s = I.load(path)
    errs = I.check(s, path)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stats = I.load(stats_path) if stats_path and os.path.exists(stats_path) else None
    if mock and stats is None:
        import stats as ST
        stats = ST.mock(I._date(s["date"]))
    entry = I.topic_entry(s["topic"]) if s["format"] == "guide" else None
    ctx = I.context(entry, stats, s["date"])
    stem = f"{s['date']}_{s['topic']}"
    t0 = time.time()
    try:                                              # 자리표시자를 못 채우면 여기서 멈춘다(그림 전)
        plan = card_plan(s, ctx)
        [I.resolve(h, ctx) for h in s["headline"]]
        ai_art = any(x["kind"] in ("img", "gumi") for x in [plan["hook"]] + plan["points"])
        caption = I.card_caption(s, ctx, ai_art)
        threads = I.threads_text(s, ctx)
        threads_post = I.threads_post_text(s, ctx)
    except I.Missing as e:
        raise SystemExit(f"❌ {e}")
    items = [plan["hook"]] + plan["points"]
    info = R.prepare_assets(s, items, entry, stats, os.path.join(work, stem, "img"), mock)   # 릴스와 같은 캐시
    os.makedirs(out_dir, exist_ok=True)
    cards = Cards(s, ctx, stats, plan)
    slides = [cards.hook()] + [cards.point(k, it) for k, it in enumerate(plan["points"], 2)] + [cards.cta(ai_art)]
    paths = []
    for k, im in enumerate(slides, 1):
        p = os.path.join(out_dir, f"{stem}_card{k:02d}.jpg")
        save(im, p, quality)
        paths.append(p)
    sheet_path = os.path.join(out_dir, f"{stem}_cards_sheet.jpg")
    sheet(paths, sheet_path)
    res = {"stem": stem, "date": s["date"], "format": s["format"], "topic": s["topic"], "cards": paths,
           "count": len(paths), "size": [W, H], "sheet": sheet_path, "mock": mock,
           "stats_mock": bool((stats or {}).get("mock")), "stats_at": (stats or {}).get("generated_at"),
           "ai_art": ai_art, "spark_images": info["spark_images"],
           "slides": ["hook:" + plan["hook"]["kind"]] + [f"{x['kind']}:{'+'.join(map(str, x['scenes']))}"
                                                           for x in plan["points"]] + ["cta"],
           "dropped": [x["scenes"] for x in plan["dropped"]],
           "caption": caption, "threads": threads, "threads_post": threads_post, "topic_tag": I.topic_tag(s)}
    with open(os.path.join(out_dir, f"{stem}_cards.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"✅ 카드 {len(paths)}장 · {stem} · {' / '.join(res['slides'])} · 그림 {info['spark_images']}"
          f" · {time.time() - t0:.1f}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타·쓰레드 카드(캐러셀) 렌더")
    ap.add_argument("script")
    ap.add_argument("--stats", default=os.path.join(ROOT, "output", "insta_render", "stats.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "insta_render"))
    ap.add_argument("--work", default=os.path.join(ROOT, "output", "insta_render", ".work"))
    ap.add_argument("--mock", action="store_true", help="Spark·네트워크 없이 — 테스트(게시 불가)")
    ap.add_argument("--quality", type=int, default=QUALITY, help="JPEG 품질(견본은 낮춰서 가볍게)")
    a = ap.parse_args()
    render(a.script, a.out, a.work, a.stats, a.mock, a.quality)
    return 0


if __name__ == "__main__":
    sys.exit(main())
