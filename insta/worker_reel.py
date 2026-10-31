#!/usr/bin/env python3
"""인스타 밤 편(c) '심해 직장인' — 블롭피시 회사원 캐릭터 + 직장 공감 한 줄 + 끝 '진짜 과학' 한 장 (2026-10-31).

벤치마크: 꾸이꾸이 김꾸이 '꿈꾸던 어른이 되었나요?'(AI 기니피그 · 밤 버스 · 한 줄 · 55초 · 1,700만, 10/31 조사) — 캐릭터 하나를
  계속 쓰고, 큰 한국어 한 줄 + 잔잔한 피아노, 대놓고 팔지 않는다. 우리 판은 짧게(약 16초) + 끝에 진짜 과학 한 장(믿을 만한 계정).
  ★작은 영어 자막 줄은 없다(10/31 결론: 인스타 영어 자막은 비추천).
편성: pick_plan.c_plan — 11/09 1화부터 이틀에 한 편(밤 편 c, 21:20). 무엇을 쓸지 = 그날 insta/worker_catalog.json 항목(src_n).
화면(1080×1920 · 약 16.4초 · 목소리 없음):
  0~6.2초 장면 1(천천히 다가감) → 6.2~10.8초 장면 2(천천히 물러남 · 카메오 동료) — 내내 위에 '심해 직장인 N화' 칩 + 상황 칩,
  아래(y 1196~, 캡션 자리 위)에 큰 한 줄(첫 프레임부터 보인다 — 첫 1초)
  → 마지막 5.6초 심해 남색 '진짜 과학' 카드(제목 · 본문 · 강조 낱말 노랑 · 수심 게이지(catalog gauge 가 있을 때만) · 출처 줄 32px).
캐릭터 일관성: catalog character.master_prompt + master_seed 로 기준 그림(z-image-turbo, 늘 같은 그림) → 장면마다 그 잡을
  from_job 으로 넘겨 qwen-image-edit 가 같은 캐릭터를 새 장면에(keep_prefix + 대본 scene). 편집이 실패하면 같은 캐릭터 묘사 +
  같은 seed 로 새로 그린다(덜 닮지만 올라간다 · 경고). 그것도 실패하면 렌더가 멈춘다(다른 꼴과 같다 — 게시 안 됨).
5B 영상은 쓰지 않는다 — 480×800 을 전체 화면으로 2.6배 키우면 흐리고 얼굴이 뭉개진다(10/31 견본). 대신 켄 번스.

    python insta/pick_reel.py check <worker 대본.json>       # pick_reel 이 이 모듈로 넘긴다
    python insta/pick_reel.py render <worker 대본.json> --out … [--mock]
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bc_kit as B  # noqa: E402
import pick_plan as P  # noqa: E402
import render_reel as R  # noqa: E402

KIND = P.WORKER
W, H = B.W, B.H
SHOT_DUR = (6.2, 4.6)                                     # 장면 1 · 장면 2(초)
FACT_DUR = 5.6                                            # 진짜 과학 카드
XF = 0.45                                                 # 장면 교차
OVER = 1.14                                               # 켄 번스 여유
LINE_Y = 1196                                             # 큰 한 줄 윗변(아래 25% 캡션 자리 위)
LINE_MAX, SUB_MAX, HEAD_MAX, BODY_MAX = 30, 12, 24, 90
FOCUS = {"left": -0.05, "center": 0.0, "right": 0.05}
YEL, NAVY = (255, 214, 102), (10, 14, 28)


# ── 검사 ──────────────────────────────────────────────
def entry_errs(e: dict) -> list[str]:
    """worker_catalog 항목 검사(테스트가 전부 돌린다)."""
    n = e.get("n")
    errs = []
    if P.c_kind_of_n(n) != KIND:
        errs.append(f"{n}: 번호는 {P.C_N0[KIND]}~{P.C_N0[KIND] + 99}")
    if not B._SLUG.fullmatch(e.get("slug") or ""):
        errs.append(f"{n}: slug 는 영어 소문자·하이픈")
    if P._date_or_none(e.get("from")) is None:
        errs.append(f"{n}: from(YYYY-MM-DD) 없음 — 없으면 편성되지 않는다")
    errs += _fact_errs(e)
    for k in ("title_idea", "subtitle_idea", "situation", "line_idea", "fact_topic", "source_label"):
        if not isinstance(e.get(k), str) or not e[k].strip():
            errs.append(f"{n}: {k} 없음")
    if len(e.get("subtitle_idea") or "") > SUB_MAX or len((e.get("line_idea") or "").replace("\n", "")) > LINE_MAX:
        errs.append(f"{n}: subtitle_idea {SUB_MAX}자 · line_idea {LINE_MAX}자 이내")
    if len(e.get("source_label") or "") > 40:
        errs.append(f"{n}: source_label 40자 이내")
    sc = e.get("scene_ideas")
    if not (isinstance(sc, list) and len(sc) == 2):
        errs.append(f"{n}: scene_ideas 는 두 장면")
    else:
        for i, x in enumerate(sc):
            errs += B.img_errs(f"{n} scene_ideas[{i}]", x, 30, 600)
    cm = e.get("cameo")
    if cm is not None:
        if not (isinstance(cm, dict) and all(isinstance(cm.get(k), str) and cm[k] for k in ("animal_ko", "animal_en", "look"))):
            errs.append(f"{n}: cameo 는 null 또는 animal_ko·animal_en·look")
        else:
            errs += B.img_errs(f"{n} cameo.look", cm["look"], 20, 400)
    fi = e.get("fact_idea") or {}
    if not (isinstance(fi.get("head"), str) and isinstance(fi.get("body"), str)):
        errs.append(f"{n}: fact_idea.head·body 없음")
    else:
        for k in ("head", "body"):
            bad = B.unbacked(fi[k], e)
            if bad:
                errs.append(f"{n}: fact_idea.{k} 에 facts 에 없는 숫자 {bad}")
    g = e.get("gauge")
    if g is not None and not (isinstance(g, list) and len(g) == 2 and all(isinstance(x, int) for x in g) and 0 < g[0] < g[1] <= 1500
                              and not B.unbacked(f"{g[0]} {g[1]}", e)):
        errs.append(f"{n}: gauge 는 [얕은 m, 깊은 m](1,500m 이내 · 두 수 모두 facts 에)")
    return errs


def _fact_errs(e: dict) -> list[str]:
    """facts{fact, src, evidence} · https 출처 전부 쓰임 · careful — danger_reel 도 쓴다."""
    n = e.get("n")
    errs = []
    srcs = e.get("sources")
    if not (isinstance(srcs, list) and srcs and all(isinstance(u, str) and u.startswith("https://") for u in srcs)):
        return [f"{n}: sources 는 https URL 목록"]
    if any("wikipedia.org" in u for u in srcs):
        errs.append(f"{n}: 위키백과는 출처로 쓰지 않는다")
    facts = e.get("facts")
    if not (isinstance(facts, list) and facts):
        return errs + [f"{n}: facts 없음"]
    used = set()
    for k, f in enumerate(facts):
        if not (isinstance(f, dict) and isinstance(f.get("fact"), str) and f["fact"].strip()):
            errs.append(f"{n}: facts[{k}].fact 없음")
            continue
        src = f.get("src")
        if not (isinstance(src, int) and not isinstance(src, bool) and 0 <= src < len(srcs)):
            errs.append(f"{n}: facts[{k}].src 는 sources 번호")
        else:
            used.add(src)
        if not isinstance(f.get("evidence"), str) or len(f["evidence"].strip()) < 10:
            errs.append(f"{n}: facts[{k}].evidence(원문 문장) 없음")
    if set(range(len(srcs))) - used:
        errs.append(f"{n}: 안 쓰는 출처 {sorted(set(range(len(srcs))) - used)}")
    if not (isinstance(e.get("careful"), list) and e["careful"]):
        errs.append(f"{n}: careful 없음")
    return errs


def _texts(s: dict) -> list[str]:
    f = s.get("fact") if isinstance(s.get("fact"), dict) else {}
    out = [s.get("subtitle"), s.get("line"), f.get("head"), f.get("body"), s.get("caption"), s.get("question")]
    return [t for t in out if isinstance(t, str)]


def check(s: dict) -> list[str]:
    errs, e, d = B.head_errs(s, KIND, P.c_n, P.worker_no, "episode")
    if e is None:
        return errs
    dr = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    if "line_en" in s or "line_ja" in s:
        errs.append("영어·일본어 작은 자막 줄은 쓰지 않는다(10/31 — 인스타 영어 자막 비추천) · line_en 을 빼요")
    sub = s.get("subtitle")
    if not isinstance(sub, str) or not 0 < len(sub) <= SUB_MAX or "\n" in sub:
        errs.append(f"subtitle(상황 칩 — '월요일 아침 9시')은 한 줄 1~{SUB_MAX}자")
    line = s.get("line")
    if not isinstance(line, str) or not 2 <= len(line.replace("\n", "")) <= LINE_MAX or line.count("\n") > 1:
        errs.append(f"line(공감 한 줄)은 2~{LINE_MAX}자 · 줄바꿈은 많아야 한 번")
    else:
        f, ls = B.fit_lines(dr, line, "head", 88, 64, 900, 2)
        if len(ls) > 2 or f.size < 64:
            errs.append("line 이 화면 두 줄(64px 이상)에 안 들어간다 — 줄이거나 줄바꿈(\\n) 자리를 바꿀 것")
    for where, t in (("subtitle", sub), ("line", line)):
        if isinstance(t, str):
            if B._LATIN3.search(t):
                errs.append(f"{where}: 영어 낱말은 쓰지 않는다(한국어만)")
            bad = B.unbacked(t, e, allow_time=True)
            if bad:
                errs.append(f"{where}: 시각('9시') 말고는 facts 에 있는 숫자만 — {bad}")
    shots = s.get("shots")
    if not (isinstance(shots, list) and len(shots) == 2 and all(isinstance(x, dict) for x in shots)):
        errs.append("shots 는 장면 두 개(객체) — {scene, move?, focus?}")
        shots = []
    for i, x in enumerate(shots):
        errs += B.img_errs(f"shots[{i}].scene", x.get("scene"), 30, 600)
        if x.get("move", "in") not in ("in", "out"):
            errs.append(f"shots[{i}].move 는 in|out")
        if x.get("focus", "center") not in FOCUS:
            errs.append(f"shots[{i}].focus 는 left|center|right")
    fct = s.get("fact")
    if not isinstance(fct, dict):
        errs.append("fact{head, body, hl} 없음")
        fct = {}
    head, body, hl = fct.get("head"), fct.get("body"), fct.get("hl", [])
    if not isinstance(head, str) or not 2 <= len(head.replace("\n", "")) <= HEAD_MAX or head.count("\n") > 1:
        errs.append(f"fact.head 는 2~{HEAD_MAX}자 · 두 줄까지")
    if not isinstance(body, str) or not 10 <= len(body.replace("\n", "")) <= BODY_MAX:
        errs.append(f"fact.body 는 10~{BODY_MAX}자")
    elif len(B.wrap_lines(dr, body, R.font("bold", 52), _text_w(e))) > 5:
        errs.append("fact.body 가 화면 다섯 줄을 넘는다 — 줄일 것")
    if not (isinstance(hl, list) and all(isinstance(h, str) and h and isinstance(body, str) and h in body for h in hl)):
        errs.append("fact.hl 은 body 안에 그대로 있는 낱말 목록(줄바꿈을 걸치지 않게)")
    for k, t in (("fact.head", head), ("fact.body", body)):
        if isinstance(t, str):
            bad = B.unbacked(t, e)
            if bad:
                errs.append(f"{k}: catalog {e['n']} facts 에 없는 숫자 {bad} — 숫자는 그 항목 facts 에서만")
    errs += B.caption_errs(s, e)
    errs += B.word_errs(_texts(s), [x.get("scene") or "" for x in shots])
    return errs


def warns(s: dict) -> list[str]:
    e = P.c_entry(s.get("src_n")) or {}
    cm = e.get("cameo")
    scenes = " ".join(x.get("scene") or "" for x in s.get("shots") or [] if isinstance(x, dict))
    word = ((cm or {}).get("animal_en") or "").split()[-1:]
    if cm and word and word[0].lower() not in scenes.lower():
        return [f"카메오({cm.get('animal_ko')})가 장면 묘사에 없다 — 사실 카드가 그 동료 이야기면 장면 2에 cameo.look 을 넣어요"]
    return []


def _text_w(e: dict) -> int:
    return 720 if e.get("gauge") else 860


# ── 그림 ──────────────────────────────────────────────
def assets(s: dict, wd: str, mock: bool) -> dict:
    """장면 그림 두 장 — 기준 그림(seed 고정) → from_job 편집. 같은 장면 묘사면 다시 그리지 않는다(작업 폴더 캐시)."""
    ch = P.c_catalog(KIND).get("character") or {}
    paths, log = [], []
    todo = []
    for i, x in enumerate(s["shots"]):
        h = hashlib.sha1((ch.get("keep_prefix", "") + x["scene"] + str(mock)).encode()).hexdigest()[:10]
        p = os.path.join(wd, f"shot{i}_{h}.png")
        paths.append(p)
        if not (os.path.exists(p) and os.path.getsize(p) > 5000 and not B.broken_image(p)):
            todo.append((i, x, p))
    if mock:
        for i, x, p in todo:
            B.mock_image(x["scene"], p, 800, 1328)
        return {"shots": paths, "spark": []}
    mj = None
    for i, x, p in todo:
        if not B.spark_alive(mj):
            mj = B.spark_image(ch["master_prompt"], os.path.join(wd, "master.png"), *ch["master_size"],
                               seed=ch["master_seed"], log=log)
        try:
            B.spark_edit(mj, ch["keep_prefix"] + "Change only the scene: " + x["scene"] + ch["style_tail"], p, log=log)
        except B.SparkError as e:
            print(f"::warning title=캐릭터 편집 실패 — 묘사로 새로 그림::{str(e)[:200]}", flush=True)
            B.spark_image(ch["fallback_prefix"] + x["scene"] + ch["style_tail"], p, 768, 1344, seed=ch["master_seed"], log=log)
            log.append({"what": "fallback", "shot": i})
    return {"shots": paths, "spark": log}


# ── 화면 ──────────────────────────────────────────────
class Episode:
    def __init__(self, s: dict, a: dict):
        self.s = s
        self.e = P.c_entry(s["src_n"]) or {}
        t = 0.0
        self.shots = []
        for i, x in enumerate(s["shots"]):
            im = Image.open(a["shots"][i]).convert("RGB")
            self.shots.append({**x, "start": t, "dur": SHOT_DUR[i], "img": B.cover(im, int(W * OVER), int(H * OVER))})
            t += SHOT_DUR[i]
        self.fact_start = t
        self.total = round(t + FACT_DUR, 3)
        self.fact_bg = B.vgrad((W, H), (16, 40, 74), (3, 8, 20))
        rng = random.Random(7)
        self.bubbles = [(rng.uniform(40, 1040), rng.uniform(0, 1920), rng.uniform(3, 11), rng.uniform(40, 120)) for _ in range(46)]
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        self.line_f, self.line_ls = B.fit_lines(d, s["line"], "head", 88, 64, 900, 2)
        tw = _text_w(self.e)
        f = s["fact"]
        self.head_f, self.head_ls = B.fit_lines(d, f["head"], "head", 76, 58, tw, 2)
        self.body_f = R.font("bold", 52)
        self.body_ls = B.wrap_lines(d, f["body"], self.body_f, tw)

    def shot_frame(self, x: dict, t: float) -> Image.Image:
        lt = t - x["start"]
        p = B.clamp(lt / (x["dur"] + XF))
        z = 1.0 + 0.12 * (B.ease(p) if x.get("move", "in") == "in" else 1 - B.ease(p))
        return B.view(x["img"], z, W, H, OVER, 0.47, 0.0, FOCUS.get(x.get("focus", "center"), 0.0))

    def scene(self, t: float) -> Image.Image:
        x = [y for y in self.shots if y["start"] <= t][-1]
        fr = self.shot_frame(x, t)
        i = self.shots.index(x)
        if i > 0 and t - x["start"] < XF:
            fr = Image.blend(self.shot_frame(self.shots[i - 1], t), fr, B.ease((t - x["start"]) / XF))
        return fr

    def fact_frame(self, t: float) -> Image.Image:
        f, e = self.s["fact"], self.e
        lt = t - self.fact_start
        im = self.fact_bg.copy()
        d = ImageDraw.Draw(im, "RGBA")
        for (x, y0, r, sp) in self.bubbles:                # 올라가는 마린 스노
            y = (y0 - sp * t) % 1920
            d.ellipse((x - r / 2, y - r / 2, x + r / 2, y + r / 2), fill=(170, 210, 255, 46))
        a = B.clamp(lt / 0.4)
        x0 = 90
        g = e.get("gauge")
        if g:                                              # 수심 게이지(catalog gauge 가 있을 때만 — 사실 숫자)
            gx, gy0, gy1 = 92, 420, 1330
            d.line((gx, gy0, gx, gy1), fill=(120, 160, 210, int(160 * a)), width=4)
            for m in range(0, 1501, 300):
                yy = gy0 + (gy1 - gy0) * m / 1500
                d.line((gx - 12, yy, gx + 12, yy), fill=(120, 160, 210, int(200 * a)), width=3)
                B.text_a(im, (gx + 22, yy - 14), f"{m:,}m", R.font("reg", 24), (140, 175, 220), a)
            band = B.clamp((lt - 0.3) / 0.8)
            y_lo, y_hi = (gy0 + (gy1 - gy0) * g[0] / 1500, gy0 + (gy1 - gy0) * g[1] / 1500)
            d.rounded_rectangle((gx - 10, y_lo, gx + 10, y_lo + (y_hi - y_lo) * band), 8, fill=(255, 196, 92, int(230 * a)))
            x0 = 230
        B.text_a(im, (x0, 470), "진짜 과학", R.font("bold", 38), (255, 196, 92), a)
        y = 532
        for ln in self.head_ls:
            B.text_a(im, (x0, y), ln, self.head_f, (245, 247, 252), a)
            y += self.head_f.size + 16
        y += 34
        b = B.clamp((lt - 0.45) / 0.5)
        for ln in self.body_ls:
            B.rich_line(im, (x0, y), ln, self.body_f, (214, 224, 240), (255, 196, 92), f.get("hl", []), b)
            y += 76
        B.text_a(im, (x0, max(y + 40, 1250)), e.get("source_label", ""), R.font("reg", B.SRC_PX), (160, 180, 210), b)
        return im

    def overlay(self, im: Image.Image, t: float) -> Image.Image:
        s = self.s
        d = ImageDraw.Draw(im, "RGBA")
        chip = f"{P.C_SERIES[KIND]} {s['episode']}화"
        f1 = R.font("head", 46)
        w1 = d.textlength(chip, font=f1)
        d.rounded_rectangle((60, 232, 60 + w1 + 48, 308), 38, fill=NAVY + (200,))
        d.text((84, 243), chip, font=f1, fill=YEL)
        f2 = R.font("bold", 38)
        w2 = d.textlength(s["subtitle"], font=f2)
        d.rounded_rectangle((60, 322, 60 + w2 + 40, 384), 31, fill=NAVY + (150,))
        d.text((80, 331), s["subtitle"], font=f2, fill=(255, 255, 255))
        if t >= self.fact_start:
            return im
        pop = B.clamp(t / 0.18)                            # 첫 프레임부터 보인다(살짝 튀어 오름)
        B.shade_band(im, LINE_Y - 90, LINE_Y + 260, 165)
        y = LINE_Y
        for ln in self.line_ls:
            w = d.textlength(ln, font=self.line_f)
            B.text_stroke(im, (60 + (900 - w) / 2, y + (1 - pop) * 10), ln, self.line_f, (255, 255, 255), (0, 0, 0), 7)
            y += self.line_f.size + 14
        return im

    def frame(self, t: float) -> Image.Image:
        if t < self.fact_start:
            im = self.scene(t)
        else:
            im = self.fact_frame(t)
            dt_ = t - self.fact_start
            if dt_ < 0.5:                                  # 장면 → 사실 카드(가라앉는 느낌)
                prev = self.scene(self.fact_start - 0.01).filter(ImageFilter.GaussianBlur(6 * dt_ / 0.5))
                im = Image.blend(prev, im, B.ease(dt_ / 0.5))
        return self.overlay(im, t)


# ── 캡션·렌더 ─────────────────────────────────────────
def caption_of(s: dict) -> str:
    e = P.c_entry(s.get("src_n")) or {}
    return B.caption(f"{P.C_SERIES[KIND]} {s.get('episode')}화", s, e, "AI로 만든 캐릭터 영상이에요.")


def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    errs = check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    for w_ in warns(s):
        print(f"⚠️ {w_}")
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    ep = Episode(s, a)
    wav = B.piano_bed(ep.total, os.path.join(wd, "bed.wav"))
    out = os.path.join(out_dir, f"{stem}.mp4")
    B.mux(ep.frame, ep.total, wav, out, wd)
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    ep.frame(0.4).save(cover, "JPEG", quality=90)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    B.contact_sheet(ep.frame, [0.0, 2.5, ep.shots[1]["start"] + 1.2, ep.fact_start + 2.8], sheet)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "src_n": s.get("src_n"), "video": out,
            "cover": cover, "sheet": sheet, "seconds": ep.total, "voice": "none", "caption": caption_of(s),
            "threads_images": [], "spark": a["spark"]}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta
