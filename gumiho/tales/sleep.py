#!/usr/bin/env python3
"""Nine Tails Tales — 수면판(Sleep Edition): 지난 편 몇 개를 ★다시 지어★ 한 시간짜리 '잠들 때 듣는' 영상으로.

    python gumiho/tales/sleep.py check                          # gumiho/tales/sleep/*.json 검사
    python gumiho/tales/sleep.py due --today 2026-10-18          # 오늘 만들 수면판(경로를 한 줄씩)
    python gumiho/tales/sleep.py render gumiho/tales/sleep/001_rainy-night.json [--mock] [--fps 15]
    python gumiho/tales/sleep.py upload gumiho/tales/sleep/001_rainy-night.json

왜(2026-10-01 전수조사 C:\\wbtmp\\gumiho_survey): 차분한 내레이션의 긴 영상은 '잠들며 틀어 두는' 시청 시간이 크다.
  같은 영상을 이어 붙여 다시 올리면 '재사용 콘텐츠'가 된다(2025-07 YPP 예시: 겉만 다른 이야기 반복) — 그래서
  ① 새로 쓴 연결 내레이션(인트로·편 사이·아웃트로) ② 새로 그린 그림(같은 프롬프트라도 새로 생성)
  ③ 느린 목소리(0.92)·긴 전환·어두운 화면 ④ 빗소리 앰비언스와 끝 10분 비 화면 으로 ★새 작품★으로 짓는다.

편에서 가져오는 범위(코드가 자른다 — spec 에 적지 않아도 된다):
  · 시작: 'TALE 00N' 카드부터(콜드 오픈 훅·채널 인사는 버린다 — 연결 내레이션이 대신한다)
  · 끝: 마지막 카드 뒤 처음 나오는 '댓글/구독/다음 편' 줄 앞까지
  · 가운데: 로마 숫자 장 카드·화면 주석은 버린다(잠을 깨우는 글자·효과음), '댓글·다음 편·지난 편' 말은 뺀다
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import render_tale as R  # noqa: E402
import tales as T        # noqa: E402

SLEEP_DIR = os.path.join(HERE, "sleep")
OUT = os.path.join(ROOT, "output", "gumiho", "tales")
WORK = os.path.join(ROOT, "output", "gumiho", ".work")
LEDGER = os.path.join(ROOT, "output", "gumiho", "sleep_ledger.json")

TEMPO = 0.92          # 본편 0.97 보다 느리게
GAP = 1.4             # 말 끝나고 다음 장면까지(본편 0.5)
CARD_SEC = 5.0        # 'TALE 00N' 카드 — 효과음 대신 부드러운 현 소리
XF = 1.6              # 교차 전환(본편 0.5)
DIM = 0.8             # 화면 밝기(잠자리에서 눈부시지 않게)
FPS = 15              # 움직임이 느려서 충분하다 — 한 시간 분량 프레임을 Actions 시간 안에
FADE_OUT = 30.0       # 끝 30초 동안 천천히 검게
LUFS = -16            # 본편 -14 보다 조용히(유튜브는 큰 소리만 줄이고 작은 소리는 키우지 않는다)
TAIL_BOOST = 2.5      # 끝 '비만' 구간은 빗소리를 +8dB(10/1 샘플 실측: 말 -15.6 LUFS · 비 -31.9 LUFS 로 너무 작았다)
TAIL_MIN = (0, 20)    # 끝 비 화면(분)
TALES_N = (2, 6)
SCENE_MAX_WORDS = 70
KEEP_MIN = 15         # 편에서 남은 장면이 이보다 적으면 자르기가 잘못된 것
CTA = re.compile(r"(?i)\b(comments?|subscrib\w*|like (this|the) video|the bell|next time|next week|last time|"
                 r"see you|until then|tale number)\b")
FX_CALM = {"embers": "dust"}          # 튀어 오르는 불티는 잠을 깨운다
PLAYLIST = "Sleep Edition: Korean Folklore to Fall Asleep To | Nine Tails Tales"
PLAYLIST_DESC = ("Long, slow, dimly lit editions of Gumi's tales with soft rain — Korean folklore, fox spirits and "
                 "ghost stories to fall asleep to. A new Sleep Edition every month.")
EXTRA_TAGS = ["sleep stories", "stories to fall asleep to", "bedtime stories for adults", "rain sounds for sleeping",
              "korean folklore", "nine tails tales"]


def marker(spec: dict) -> str:
    """설명란 표식 — 유튜브에 이미 있는지(중복 업로드)를 이걸로 찾는다."""
    return f"Sleep Edition {spec['id']:03d}"


def stem(spec: dict) -> str:
    return f"sleep_{spec['id']:03d}_{spec['slug']}"


# ── 편 가져오기 ─────────────────────────────────────────
def tale_path(name: str) -> str | None:
    """'001_gumiho' → 대본 경로(사람 견본 scripts/ 또는 루틴 output/tales/)."""
    for d in (T.SCRIPTS, T.ROUTINE_DIR):
        p = os.path.join(d, f"{name}.json")
        if os.path.exists(p):
            return p
    return None


def trim(s: dict) -> tuple[list[dict], list[str]]:
    """편 하나에서 수면판에 쓸 장면(복사본)과 버린 이유 목록."""
    sc = s["scenes"]
    start = next((i for i, x in enumerate(sc) if str(x.get("card", "")).startswith("TALE")), 0)
    last_card = max((i for i, x in enumerate(sc) if x.get("card")), default=start)
    end = next((i for i in range(last_card + 1, len(sc)) if CTA.search(sc[i].get("say", ""))), len(sc))
    kept, dropped = [], [f"앞 {start}장면(콜드 오픈·인사)", f"뒤 {len(sc) - end}장면(댓글·다음 편)"]
    for i in range(start, end):
        x = sc[i]
        if x.get("card"):
            if i != start:
                dropped.append(f"{i}: 장 카드 {x['card']!r}")
                continue
        elif CTA.search(x.get("say", "")):
            dropped.append(f"{i}: {x['say'][:50]!r}")
            continue
        y = {k: v for k, v in x.items() if k != "note"}
        if y.get("fx") in FX_CALM:
            y["fx"] = FX_CALM[y["fx"]]
        kept.append(y)
    return kept, dropped


# ── 검사 ────────────────────────────────────────────────
def _scene_errs(x: dict, lab: str) -> list[str]:
    errs = []
    src = [k for k in ("img", "gumi") if x.get(k)]
    if len(src) != 1:
        errs.append(f"{lab}: img·gumi 중 정확히 하나")
    if not x.get("say"):
        errs.append(f"{lab}: say 없음")
    if T.words(x.get("say", "")) > SCENE_MAX_WORDS:
        errs.append(f"{lab}: {T.words(x['say'])}단어 > {SCENE_MAX_WORDS}")
    if x.get("gumi") and x["gumi"] not in T.GUMI:
        errs.append(f"{lab}: gumi 는 {T.GUMI}")
    if x.get("fx", "dust") not in T.FX:
        errs.append(f"{lab}: fx {x.get('fx')!r} ∉ {T.FX}")
    if x.get("move", "in") not in T.MOVES:
        errs.append(f"{lab}: move {x.get('move')!r} ∉ {T.MOVES}")
    for f in ("say", "img"):
        if T.BANNED.search(x.get(f, "")):
            errs.append(f"{lab}: 금지어 {T.BANNED.search(x[f]).group(0)!r}")
    m = CTA.search(x.get("say", ""))
    if m:
        errs.append(f"{lab}: 수면판에 '{m.group(0)}' 같은 말은 넣지 않는다(잠을 깨운다·다음 편 예고 없음)")
    m = T.DATED.search(x.get("say", ""))
    if m:
        errs.append(f"{lab}: 날짜를 타는 표현 {m.group(0)!r}")
    return errs


def check(spec: dict, path: str | None = None) -> list[str]:
    errs = []
    for k in ("id", "slug", "title", "thumb", "hook", "tags", "intro", "tales", "outro", "tail", "render_from",
              "publish_at"):
        if not spec.get(k):
            errs.append(f"'{k}' 없음")
    if errs:
        return errs
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", spec["slug"]):
        errs.append(f"slug 형식: {spec['slug']!r}")
    if path and os.path.basename(path) != f"{spec['id']:03d}_{spec['slug']}.json":
        errs.append(f"파일 이름은 {spec['id']:03d}_{spec['slug']}.json")
    if len(spec["title"]) > T.TITLE_SEARCH_MAX:
        errs.append(f"제목 {len(spec['title'])}자 > {T.TITLE_SEARCH_MAX}")
    th = spec["thumb"]
    if not th.get("text") or T.words(th["text"]) > T.THUMB_MAX_WORDS or len(th["text"]) > 22 or not th.get("img"):
        errs.append("thumb: text(4단어·22자 이하)·img 필요")
    try:
        rf = dt.date.fromisoformat(spec["render_from"])
        pa = dt.datetime.strptime(spec["publish_at"], "%Y-%m-%dT%H:%M:%SZ")
        if (pa.date() - rf).days < 2:
            errs.append("publish_at 은 render_from 보다 이틀 이상 뒤(렌더 3~5시간 + 실패 시 다음 날 재시도)")
    except ValueError as e:
        errs.append(f"날짜 형식(render_from YYYY-MM-DD · publish_at YYYY-MM-DDTHH:MM:SSZ): {e}")
    tail = spec["tail"]
    if not (TAIL_MIN[0] <= float(tail.get("min", -1)) <= TAIL_MIN[1]) or not tail.get("img"):
        errs.append(f"tail: min {TAIL_MIN}·img 필요")
    tl = spec["tales"]
    if not TALES_N[0] <= len(tl) <= TALES_N[1]:
        errs.append(f"편 {len(tl)}개 — {TALES_N}")
    if len({t.get("file") for t in tl}) != len(tl):
        errs.append("같은 편이 두 번 들어 있다")
    for k, x in enumerate(spec["intro"]):
        errs += _scene_errs(x, f"intro {k}")
    for k, x in enumerate(spec["outro"]):
        errs += _scene_errs(x, f"outro {k}")
    for j, t in enumerate(tl):
        if not re.fullmatch(r"\d{3}_[a-z0-9-]+", t.get("file", "")):
            errs.append(f"tales {j}: file 은 '001_gumiho' 꼴")
        if not t.get("chapter"):
            errs.append(f"tales {j}: chapter(설명란 챕터 이름) 없음")
        if not t.get("link"):
            errs.append(f"tales {j}: link(그 편으로 넘어가는 새 내레이션) 없음 — 이어 붙이기만 하면 재사용 콘텐츠다")
        for k, x in enumerate(t.get("link") or []):
            errs += _scene_errs(x, f"tales {j} link {k}")
    new_words = sum(T.words(x["say"]) for x in spec["intro"] + spec["outro"] + [y for t in tl for y in t.get("link") or []])
    if new_words < 120:
        errs.append(f"새 내레이션 {new_words}단어 — 120단어 이상(인트로·편 사이·아웃트로)")
    if len(",".join(spec["tags"] + EXTRA_TAGS)) > 480:
        errs.append("태그 합계 480자 이하")
    return errs


def load_tales(spec: dict) -> tuple[list[dict], list[str]]:
    """(대본들, 없는 편 이름들)."""
    got, missing = [], []
    for t in spec["tales"]:
        p = tale_path(t["file"])
        if p:
            got.append(T.load(p))
        else:
            missing.append(t["file"])
    return got, missing


# ── 언제 만드나 ─────────────────────────────────────────
def load_ledger(path: str = LEDGER) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def due(spec: dict, today: dt.date, led: dict) -> tuple[bool, str]:
    if led.get(stem(spec), {}).get("long"):
        return False, f"이미 올림 {led[stem(spec)]['long']}"
    rf = dt.date.fromisoformat(spec["render_from"])
    if today < rf:
        return False, f"{rf} 부터"
    _, missing = load_tales(spec)
    if missing:
        return False, f"대본 없음 {missing} — 루틴이 그 편을 쓴 뒤에 만든다"
    return True, "만든다"


def publish_time(spec: dict, mode: str, now: dt.datetime | None = None) -> str | None:
    """scheduled: spec 시각(늦었으면 지금+1시간 정각) · private: 예약 없음(비공개로만)."""
    if mode != "scheduled":
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    want = dt.datetime.strptime(spec["publish_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if want < now + dt.timedelta(hours=1):
        want = (now + dt.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    return want.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 장면·시간 ───────────────────────────────────────────
def build_scenes(spec: dict, scripts: list[dict]) -> tuple[list[dict], dict]:
    """수면판 장면 목록(챕터 표시 포함)과 편별 자르기 보고."""
    out, report = [], {}
    for k, x in enumerate(spec["intro"]):
        out.append(dict(x, chapter="Settle in" if k == 0 else None))
    for t, s in zip(spec["tales"], scripts):
        for k, x in enumerate(t["link"]):
            out.append(dict(x, chapter=t["chapter"] if k == 0 else None))
        kept, dropped = trim(s)
        report[t["file"]] = {"kept": len(kept), "dropped": dropped}
        out += [dict(x, chapter=None) for x in kept]
    for k, x in enumerate(spec["outro"]):
        out.append(dict(x, chapter="Goodnight" if k == 0 else None))
    tail = spec["tail"]
    if float(tail["min"]) > 0:
        out.append({"img": tail["img"], "fx": tail.get("fx", "rain"), "move": "in", "say": "", "tail": True,
                    "chapter": "Rain only"})
    return out, report


def plan(scenes: list[dict]) -> list[dict]:
    shots = R.plan({"scenes": scenes})
    for x, sc in zip(shots, scenes):
        x["chapter"] = sc.get("chapter")
        x["tail"] = bool(sc.get("tail"))
        x["note"] = ""
        if x["fx"] in FX_CALM:
            x["fx"] = FX_CALM[x["fx"]]
    return shots


def timeline(shots: list[dict], voices: dict, tail_sec: float) -> float:
    t = 0.0
    for x in shots:
        x["start"] = round(t, 3)
        if x["tail"]:
            x["dur"] = round(tail_sec, 3)
        elif x["kind"] == "card":
            x["dur"] = CARD_SEC
        else:
            x["wav"] = voices[x["say"]]
            x["vdur"] = R.wav_dur(x["wav"])
            x["dur"] = round(R.LEAD + x["vdur"] + GAP + x["hold"], 3)
        t += x["dur"]
    return round(t, 3)


# ── 소리: 빗소리 앰비언스(블록 단위 — 한 시간을 메모리에 다 올리지 않는다) ──
class Ambience:
    """빗소리(23초 원형) + 바람(30초 원형) + 낮은 드론. 원형 잡음이라 블록을 이어도 이음새가 없다."""

    def __init__(self, seed: int):
        import numpy as np
        rng = np.random.default_rng(seed)
        SR = R.SR

        def loop(sec, shape):
            L = int(SR * sec)
            spec = np.fft.rfft(rng.standard_normal(L))
            fr = np.fft.rfftfreq(L, 1 / SR)
            y = np.fft.irfft(spec * shape(fr), L).astype("float32")
            return y / (float(np.sqrt(np.mean(y ** 2))) + 1e-9)

        self.wind = loop(30, lambda f: 1 / (1 + (f / 260) ** 2))
        # 비: 400Hz~7kHz 를 1/√f 로(분홍빛) — 쏴아 하는 소리
        self.rain = loop(23, lambda f: ((f / 400) ** 2 / (1 + (f / 400) ** 2)) / (1 + (f / 7000) ** 2)
                         * np.sqrt(1000 / np.maximum(f, 50)))
        # 빗방울: 짧게 사라지는 톡 소리를 원형 고리 안에 흩뿌린다
        L = len(self.rain)
        drops = np.zeros(L, dtype="float32")
        n = int(SR * 0.012)
        env = np.exp(-np.arange(n) / (SR * 0.0025)).astype("float32")
        for _ in range(23 * 14):
            a = int(rng.integers(L))
            burst = rng.standard_normal(n).astype("float32")
            burst = np.diff(burst, prepend=0).astype("float32") * env * float(rng.uniform(0.3, 1.0))
            idx = (a + np.arange(n)) % L
            drops[idx] += burst
        drops /= float(np.sqrt(np.mean(drops ** 2))) + 1e-9
        self.rain = self.rain + 0.35 * drops
        self.ph = rng.uniform(0, 6.28, 3)

    def block(self, a: int, n: int):
        """샘플 a 부터 n 개(정규화 전 — rms 약 1)."""
        import numpy as np
        SR = R.SR
        t = (np.arange(a, a + n) / SR).astype("float64")
        drone = (0.5 * np.sin(2 * np.pi * 73.42 * t + self.ph[0]) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.031 * t))
                 + 0.3 * np.sin(2 * np.pi * 110.0 * t + self.ph[1]) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.023 * t + 1))
                 ).astype("float32")
        wi = np.take(self.wind, np.arange(a, a + n) % len(self.wind))
        ra = np.take(self.rain, np.arange(a, a + n) % len(self.rain))
        sway = (0.8 + 0.2 * np.sin(2 * np.pi * 0.013 * t)).astype("float32")
        return (0.9 * ra * sway + 0.35 * wi + 0.5 * drone).astype("float32")


def chime(rng):
    """'TALE' 카드 — 본편의 쿵 대신 낮은 현 두 줄."""
    return R._pluck(146.83, 4.0, rng) * 0.5 + R._pluck(220.0, 4.0, rng) * 0.3


def _loudnorm(raw: str, out_m4a: str):
    """2패스 loudnorm(linear) — 끝 10분 빗소리를 키우지 않게(1패스는 조용한 구간을 끌어올린다)."""
    ff = R.ffmpeg()
    target = f"I={LUFS}:TP=-2:LRA=11"
    r = subprocess.run([ff, "-hide_banner", "-i", raw, "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    af = f"loudnorm={target}"
    if m:
        j = json.loads(m.group(0))
        af += (f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
               f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    R.sh([ff, "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ar", str(R.SR), "-c:a", "aac", "-b:a", "160k", out_m4a])


def build_audio(shots: list[dict], total: float, out_m4a: str, wd: str, seed: int = 1, block_sec: int = 30):
    import numpy as np
    import wave
    SR = R.SR
    n_all = int(total * SR)
    # 목소리 크기·봉우리(전체) — 블록마다 같은 기준으로 섞으려고 먼저 잰다
    peak, ss, cnt = 1e-6, 0.0, 0
    for x in shots:
        if x.get("wav"):
            v = R.wav_read(x["wav"])
            peak = max(peak, float(np.abs(v).max()))
            act = v[np.abs(v) > 1e-4]
            ss += float(np.sum(act.astype("float64") ** 2))
            cnt += len(act)
    g = 0.7 / peak                                   # 목소리 봉우리 0.7 — 빗소리를 더해도 깎이지 않게
    vr = g * math.sqrt(ss / max(1, cnt)) if cnt else 0.1
    amb = Ambience(seed)
    amb_gain = vr * 0.16                              # 말 사이 약 -16dB
    rng = np.random.default_rng(seed + 1)
    events = []                                       # (시작 샘플, 길이, 종류, wav 경로|배열)
    for x in shots:
        if x.get("wav"):
            with wave.open(x["wav"]) as wf:
                ln = wf.getnframes()
            events.append((int((x["start"] + R.LEAD) * SR), ln, "wav", x["wav"]))
        elif x["kind"] == "card":
            c = chime(rng) * vr * 1.6
            events.append((int(x["start"] * SR), len(c), "arr", c))
    cache: dict = {}

    def get(kind, v):
        if kind == "arr":
            return v
        if v not in cache:
            if len(cache) > 8:
                cache.pop(next(iter(cache)))
            cache[v] = R.wav_read(v) * g
        return cache[v]

    tail_s = next((int(x["start"] * SR) for x in shots if x.get("tail")), n_all)
    pad = int(SR * 0.5)
    win = int(SR * 0.25)
    raw = os.path.join(wd, "mix.wav")
    fin, fout = int(SR * 3), int(SR * FADE_OUT)
    with wave.open(raw, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for a in range(0, n_all, SR * block_sec):
            n = min(SR * block_sec, n_all - a)
            a0, n0 = max(0, a - pad), min(n_all, a + n + pad) - max(0, a - pad)
            voice = np.zeros(n0, dtype="float32")
            fxs = np.zeros(n0, dtype="float32")
            for s0, ln, kind, v in events:
                if s0 >= a0 + n0 or s0 + ln <= a0:
                    continue
                arr = get(kind, v)
                lo, hi = max(s0, a0), min(s0 + len(arr), a0 + n0)
                (voice if kind == "wav" else fxs)[lo - a0:hi - a0] += arr[lo - s0:hi - s0]
            env = R.movavg(np.abs(voice), win)
            duck = R.movavg(1 - 0.3 * np.clip(env / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
            bed = amb.block(a0, n0) * amb_gain
            if a0 + n0 > tail_s:                      # 끝 비 구간: 8초에 걸쳐 빗소리를 키운다
                ramp = np.clip((np.arange(a0, a0 + n0) - tail_s) / (SR * 8.0), 0, 1).astype("float32")
                bed *= 1 + (TAIL_BOOST - 1) * ramp
            mix = (voice + bed * duck + fxs)[a - a0:a - a0 + n]
            idx = np.arange(a, a + n)
            fade = np.minimum(1.0, np.minimum(idx / fin, np.maximum(0.0, (n_all - idx) / fout))).astype("float32")
            mix *= fade
            w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    _loudnorm(raw, out_m4a)
    os.remove(raw)


# ── 썸네일·한눈에 보기 ──────────────────────────────────
def thumbnail(spec: dict, raw: str, out: str, minutes: float):
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
    tw_, th_ = 1280, 720
    img = ImageOps.fit(Image.open(raw).convert("RGB"), (tw_, th_), Image.LANCZOS, centering=(0.6, 0.45))
    img = ImageEnhance.Brightness(img).enhance(0.72)
    blue = Image.new("RGB", (tw_, th_), (10, 18, 44))
    img = Image.blend(img, blue, 0.28)
    grad = Image.linear_gradient("L").rotate(90, expand=True).resize((tw_, th_))      # 왼쪽 255 → 오른쪽 0
    img = Image.composite(Image.new("RGB", (tw_, th_), (6, 8, 20)), img, grad.point(lambda v: int(max(0, v - 90))))
    d = ImageDraw.Draw(img)
    words_ = spec["thumb"]["text"].upper().split()
    mid = max(1, (len(words_) + 1) // 2)
    lines = [ln for ln in (" ".join(words_[:mid]), " ".join(words_[mid:])) if ln]
    size = 150
    while size > 70:
        f = R.font("sans", size)
        if max(d.textlength(ln, font=f) for ln in lines) <= 680 and len(lines) * size * 1.02 <= 430:
            break
        size -= 6
    f = R.font("sans", size)
    y = (th_ - len(lines) * size * 1.02) / 2 + 30
    for k, ln in enumerate(lines):
        col = (236, 240, 255) if k < len(lines) - 1 else (255, 206, 120)
        d.text((56, y), ln, font=f, fill=col, stroke_width=max(5, size // 20), stroke_fill=(0, 0, 0))
        y += size * 1.02
    hrs = "1 HOUR" if 55 <= minutes < 75 else (f"{minutes / 60:.1f} HOURS" if minutes >= 75 else f"{round(minutes)} MIN")
    tag = f"SLEEP EDITION · {hrs} · RAIN"
    ft = R.font("sans_bold", 34)
    tl = d.textlength(tag, font=ft)
    d.rounded_rectangle([50, 44, 50 + tl + 40, 100], 12, fill=(36, 52, 112))
    d.text((70, 50), tag, font=ft, fill=(255, 255, 255))
    img.save(out, "JPEG", quality=92)
    return out


def contact_sheet(P: dict, out: str, n: int = 36, cols: int = 6):
    from PIL import Image, ImageDraw
    pa = R.Painter(P)
    shots = P["shots"]
    pick = sorted({round(k * (len(shots) - 1) / max(1, n - 1)) for k in range(n)})
    tw_, th_ = 400, 225
    rows = int(math.ceil(len(pick) / cols))
    sheet = Image.new("RGB", (cols * tw_, rows * th_), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for j, k in enumerate(pick):
        x = shots[k]
        fr = pa.frame(x["start"] + min(x["dur"] / 2, 20)).resize((tw_, th_))
        sheet.paste(fr, ((j % cols) * tw_, (j // cols) * th_))
        d.text(((j % cols) * tw_ + 8, (j // cols) * th_ + 6), f"{k} · {T.ts(x['start'])}", fill=(255, 255, 0))
    sheet.save(out, "JPEG", quality=80)


# ── 메타데이터 ──────────────────────────────────────────
def chapters(shots: list[dict]) -> str:
    rows, last = [], -99.0
    for x in shots:
        if x.get("chapter") and (x["start"] - last >= 10 or not rows):
            rows.append(f"{T.ts(x['start'])} {x['chapter']}")
            last = x["start"]
    return "\n".join(rows)


def about_len(minutes: float) -> str:
    if 50 <= minutes < 75:
        return "about an hour"
    if minutes >= 75:
        return f"about {minutes / 60:.1f} hours"
    return f"about {round(minutes)} minutes"


def meta(spec: dict, scripts: list[dict], chap: str, minutes: float,
         full: list[tuple[str, str]] | None = None) -> dict:
    tags = list(dict.fromkeys(spec["tags"] + EXTRA_TAGS))
    srcs = list(dict.fromkeys(x for s in scripts for x in s.get("sources", [])))[:12]
    n = len(spec["tales"])
    tail = float(spec["tail"]["min"])
    desc = (f"{spec['hook']}\n\n"
            f"{marker(spec)} — {n} of Gumi's tales, retold slowly over soft rain, {about_len(minutes)} long. "
            f"The screen stays dim{f', and the last {tail:g} minutes are only rain' if tail else ''}. "
            "No ads in the middle of a story, no sudden sounds.\n\n"
            f"{chap}\n\n"
            + ("Watch the full episodes:\n" + "\n".join(f"▶ {t} — {u}" for t, u in full) + "\n\n" if full else "")
            + (("Sources & further reading:\n" + "\n".join(f"• {x}" for x in srcs) + "\n\n") if srcs else "")
            + f"{T.ABOUT}\n\n{T.AI_NOTE}\n\n#sleepstories #koreanfolklore #gumiho")
    return {"title": spec["title"][:100], "description": desc[:4900], "tags": tags}


# ── 렌더 ────────────────────────────────────────────────
def render(path: str, out_dir: str = OUT, work: str = WORK, mock: bool = False, fps: int = FPS,
           procs: int | None = None, tail_min: float | None = None) -> dict:
    spec = T.load(path)
    errs = check(spec, path)
    if errs:
        raise SystemExit("수면판 검사 실패:\n  " + "\n  ".join(errs))
    scripts, missing = load_tales(spec)
    if missing:
        raise SystemExit(f"대본 없음: {missing}")
    st = stem(spec)
    wd = os.path.join(work, st)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    scenes, report = build_scenes(spec, scripts)
    for f, r in report.items():
        print(f"   ✂️ {f}: {r['kept']}장면 · 버림 {r['dropped'][:6]}", flush=True)
        if r["kept"] < KEEP_MIN:
            raise SystemExit(f"{f}: 남은 장면 {r['kept']} < {KEEP_MIN} — 자르기가 잘못됐다")
    shots = plan(scenes)
    R.TEMPO = TEMPO                                  # synth 가 부를 때 읽는다(캐시 키에도 들어간다)
    voices = R.synth([x["say"] for x in shots if x["say"]], os.path.join(wd, "tts"), mock)
    tail = float(spec["tail"]["min"] if tail_min is None else tail_min)
    total = timeline(shots, voices, tail * 60)
    print(f"   ⏱️ 수면판 {total / 60:.1f}분 · 장면 {len(shots)}", flush=True)
    im = R.make_images(spec, shots, os.path.join(wd, "img"), mock)
    P = {"shots": shots, "total": total, "xf": XF, "dim": DIM, "fade_out": FADE_OUT}
    base = os.path.join(out_dir, st)
    contact_sheet(P, base + "_sheet.jpg")
    os.environ["TALES_FPS"] = str(fps)                # 구간 인코딩 프로세스(spawn)는 render_tale 을 새로 읽는다
    R.FPS = fps
    silent = os.path.join(wd, "silent.mp4")
    R.render_video(P, wd, silent, procs)
    audio = os.path.join(wd, "audio.m4a")
    build_audio(shots, total, audio, wd, seed=spec["id"])
    R.mux(silent, audio, base + ".mp4")
    n_cues = R.build_srt(shots, base + ".srt")
    minutes = round(total / 60, 2)
    thumbnail(spec, im["thumb_raw"], base + "_thumb.jpg", minutes)
    chap = chapters(shots)
    res = {"stem": st, "video": base + ".mp4", "thumb": base + "_thumb.jpg", "srt": base + ".srt",
           "sheet": base + "_sheet.jpg", "minutes": minutes, "cues": n_cues, "images": im["images"],
           "mock": mock, "fps": fps, "chapters": chap, "trim": report,
           **meta(spec, scripts, chap, minutes)}
    with open(base + "_meta.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"✅ {base}.mp4 · {minutes}분 · 그림 {im['images']} · 자막 {n_cues} · {time.time() - t0:.0f}s")
    return res


# ── 업로드 ──────────────────────────────────────────────
def on_youtube(yt, mark: str) -> str | None:
    """채널 최근 업로드 50개에서 표식을 찾는다(캐시가 날아가도 두 번 올리지 않게). 2 units."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute().get("items", [])
    for it in items:
        sn = it["snippet"]
        if mark in sn.get("description", "") or mark in sn.get("title", ""):
            return f"https://youtu.be/{sn['resourceId']['videoId']}"
    return None


def full_links(yt, scripts: list[dict]) -> list[tuple[str, str]]:
    """각 편 본편 링크 — uploaded.json 먼저, 없으면 채널 업로드에서 제목으로 찾는다."""
    with open(os.path.join(HERE, "uploaded.json"), encoding="utf-8") as f:
        known = json.load(f)
    by_title = {}
    if yt is not None:
        try:
            ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
            up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            for it in yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute().get("items", []):
                sn = it["snippet"]
                by_title.setdefault(sn["title"].strip().lower(), f"https://youtu.be/{sn['resourceId']['videoId']}")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 본편 링크 조회 실패(설명란 링크 일부 생략): {e}")
    out = []
    for s in scripts:
        k = f"{s['id']:03d}_{s['slug']}"
        url = (known.get(k) or {}).get("long") or by_title.get(s["title"][:100].strip().lower())
        if url:
            out.append((s["title"].split(" | ")[0], url))
    return out


def upload(path: str, out_dir: str = OUT, ledger: str = LEDGER, mode: str = "private") -> int:
    import upload_tale as UT
    spec = T.load(path)
    errs = check(spec, path)
    if errs:
        print("::error::수면판 검사 실패 — 올리지 않는다\n  " + "\n  ".join(errs))
        return 2
    st = stem(spec)
    with open(os.path.join(out_dir, f"{st}_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    if rm.get("mock"):
        print("::error::mock 렌더(가짜 그림·목소리)는 올리지 않는다")
        return 2
    led = load_ledger(ledger)
    done = led.get(st, {})
    if done.get("long"):
        print(f"⏭️ 이미 올림: {done['long']}")
        return 0
    import upload_youtube_novel as U
    yt = U.get_service()
    dup = on_youtube(yt, marker(spec))
    if dup:
        print(f"⏭️ 유튜브에 이미 있다(표식 '{marker(spec)}'): {dup} — ledger 에만 적는다")
        led[st] = {"long": dup, "title": spec["title"]}
        UT._save(ledger, led)
        return 0
    scripts, _ = load_tales(spec)
    md = meta(spec, scripts, rm["chapters"], rm["minutes"], full_links(yt, scripts))
    at = publish_time(spec, mode)
    vid = UT.insert(yt, rm["video"], md, "private", at)
    done = {"long": f"https://youtu.be/{vid}", "title": md["title"], "publish_at": at}
    led[st] = done
    UT._save(ledger, led)
    print(f"✅ 수면판 {done['long']} · {'예약 ' + at if at else '비공개'}")
    done["thumb"] = bool(U.set_thumbnail(yt, vid, rm["thumb"]))
    done["captions"] = UT.captions(yt, vid, rm["srt"])
    done["langs"] = UT.localize(vid, md["title"], md["description"])
    try:
        pid = U.ensure_playlist(yt, PLAYLIST, PLAYLIST_DESC, privacy="public")
        U.add_to_playlist(yt, pid, vid)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 재생목록 실패(업로드는 성공): {e}")
    led[st] = done
    UT._save(ledger, led)
    print(json.dumps({st: done}, ensure_ascii=False))
    return 0


# ── CLI ─────────────────────────────────────────────────
def specs() -> list[str]:
    return sorted(glob.glob(os.path.join(SLEEP_DIR, "*.json")))


def main() -> int:
    ap = argparse.ArgumentParser(description="Nine Tails Tales 수면판")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="*")
    d = sub.add_parser("due")
    d.add_argument("--today")
    d.add_argument("--ledger", default=LEDGER)
    r = sub.add_parser("render")
    r.add_argument("path")
    r.add_argument("--out", default=OUT)
    r.add_argument("--work", default=WORK)
    r.add_argument("--mock", action="store_true")
    r.add_argument("--fps", type=int, default=FPS)
    r.add_argument("--procs", type=int)
    r.add_argument("--tail-min", type=float)
    u = sub.add_parser("upload")
    u.add_argument("path")
    u.add_argument("--out", default=OUT)
    u.add_argument("--ledger", default=LEDGER)
    u.add_argument("--mode", default=os.environ.get("TALES_PUBLISH", "private"), choices=["private", "scheduled"])
    sn = sub.add_parser("seen", help="유튜브에 이미 있으면 0(ledger 에 적는다) — 세 시간 렌더 전에 확인")
    sn.add_argument("path")
    sn.add_argument("--ledger", default=LEDGER)
    a = ap.parse_args()

    if a.cmd == "seen":
        import upload_tale as UT
        import upload_youtube_novel as U
        spec = T.load(a.path)
        url = on_youtube(U.get_service(), marker(spec))
        if not url:
            print(f"   유튜브에 '{marker(spec)}' 없음 — 만든다")
            return 1
        led = load_ledger(a.ledger)
        led[stem(spec)] = {"long": url, "title": spec["title"]}
        UT._save(a.ledger, led)
        print(f"⏭️ 이미 올라가 있다: {url}")
        return 0

    if a.cmd == "check":
        bad = 0
        for p in a.paths or specs():
            spec = T.load(p)
            errs = check(spec, p)
            scripts, missing = load_tales(spec) if not errs else ([], [])
            print(f"{'✅' if not errs else '❌'} {os.path.basename(p)} · 편 {len(spec.get('tales', []))}"
                  f"{' · 아직 없는 대본 ' + str(missing) if missing else ''}")
            for e in errs:
                print(f"   ✗ {e}")
            bad += bool(errs)
        return 1 if bad else 0
    if a.cmd == "due":
        today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
        led = load_ledger(a.ledger)
        for p in specs():
            spec = T.load(p)
            if check(spec, p):
                print(f"   ✗ {os.path.basename(p)}: 검사 실패 — 건너뜀", file=sys.stderr)
                continue
            ok, why = due(spec, today, led)
            print(f"   {'▶' if ok else '·'} {os.path.basename(p)}: {why}", file=sys.stderr)
            if ok:
                print(os.path.relpath(p, ROOT).replace(os.sep, "/"))
        return 0
    if a.cmd == "render":
        render(a.path, a.out, a.work, a.mock, a.fps, a.procs, a.tail_min)
        return 0
    return upload(a.path, a.out, a.ledger, a.mode)


if __name__ == "__main__":
    sys.exit(main())
