#!/usr/bin/env python3
"""Nine Tails Tales 3D 실화·what-if 쇼츠 렌더(2026-11 재개) — story_catalog.json 한 편 → 1080×1920 H.264 + AAC.

    python gumiho/tales/story_reel.py 1                 # 편 id(또는 slug) — Spark 그림 + edge-tts
    python gumiho/tales/story_reel.py 1 --mock          # 테스트: 가짜 그림·가짜 목소리(네트워크 없음)

2차 견본(C:\\wbtmp\\nt_samples_v2, 10/31 사용자 '현 상태로도 괜찮다')을 옮긴 것이다. 지키는 것:
  ★깨짐 0 이 먼저다 — 5B 영상 클립은 쓰지 않는다(제작 중에 깨짐을 자동으로 못 거른다). 정지 그림 + 느린 밀기·패닝뿐,
    회전·손떨림·2.5D 패럴랙스도 없다(가장자리가 찢어지고 세부가 떨린다).
  ★얼굴 없는 3D 마네킹 — 실존 인물 얼굴을 그리지 않는다. 인물 컷은 기준 그림(seed 고정) 한 장에서 qwen-image-edit
    (from_job)로 이어 그려 옷·체형이 컷마다 같다(편집 결과 752×1392 → 서버 x2 업스케일 1504×2784).
  · 목소리 edge-tts en-US-AndrewNeural(단어 시각이 나와 카라오케 자막이 말에 맞는다) — 막히면 Supertonic M3.
  · 자막: 2~3단어씩, 화면 아래 20 %·오른쪽 140px(쇼츠 버튼) 밖. 첫 프레임부터 자막이 있다.
  · 소리: 내레이션 + 코드로 만든 배경음·효과음(저작권 없음) → -15 LUFS.
  · Spark 는 공용: 한 건씩, ★05:45~08:00 KST(아침 업로드 루틴)에는 잡을 내지 않는다 → QuietHours(종료 코드 75) —
    받은 그림은 work 폴더에 남아 다음 예비 실행이 이어 받는다.
OpenCV 없이 PIL·numpy 만 쓴다(맥박·채우기 PR 의 테스트 환경에 OpenCV 가 없다).
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import datetime as dt
import glob
import hashlib
import json
import math
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import story as ST  # noqa: E402

W, H, FPS, SR = 1080, 1920, 30, 44100
IMG_W, IMG_H = 1152, 2048
LUFS = -15
CAP_Y = 1330            # 자막 가운데 — 아래 끝 ~1400 < 1536(아래 20 %)
CAP_CX = 530            # 가운데보다 조금 왼쪽 — 오른쪽 끝 < 940(오른쪽 140px)
CAP_MAXW = 780
YELLOW = (255, 214, 64)
VOICE = {"engine": "edge", "name": "en-US-AndrewNeural", "rate": "+4%"}
FALLBACK_VOICE = {"engine": "supertonic", "name": "M3", "tempo": 0.9}
STYLE = ("cinematic 3D animated documentary reconstruction, Unreal Engine 5 render, detailed realistic environment, "
         "dramatic cinematic lighting, volumetric light, shallow depth of field, ")
EDIT_PREFIX = "Keep exactly the same faceless mannequin figure, the same outfit and the same cinematic 3D render style. "
REF_TTL = 45 * 60       # 게이트웨이는 결과를 1시간 뒤 지운다 — 편집의 기준(from_job)은 45분마다 새로
FONTS = [r"C:\Windows\Fonts\seguibl.ttf", r"C:\Windows\Fonts\ariblk.ttf",
         "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf", "/usr/share/fonts/truetype/noto/NotoSans-ExtraBold.ttf",
         "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_AFFINE = getattr(Image, "Transform", Image).AFFINE
_BICUBIC = getattr(Image, "Resampling", Image).BICUBIC
_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS


class QuietHours(RuntimeError):
    """05:45~08:00 KST — Spark 를 쓰지 않는다(다음 예비 실행이 이어 받는다)."""


def h16(*parts) -> str:
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:12]


def log(msg: str):
    print(f"[{dt.datetime.now(ST.KST):%H:%M:%S}] {msg}", flush=True)


def ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    for p in ("C:/wbtmp/ffbin/ffmpeg.exe",):
        if os.path.exists(p):
            return p
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def sh(cmd: list):
    subprocess.run(cmd, check=True)


_FONT = {}


def font(size: int):
    if size not in _FONT:
        for p in FONTS:
            if os.path.exists(p):
                _FONT[size] = ImageFont.truetype(p, size)
                break
        else:
            raise RuntimeError(f"자막 글꼴 없음 — {FONTS[2:]} (fonts-noto-extra 설치 확인)")
    return _FONT[size]


# ── Spark ───────────────────────────────────────────────
def _spark():
    import requests
    import wbspark
    return wbspark, requests


def spark_job(payload: dict, timeout: int = 1200, poll: float = 4.0):
    if ST.quiet(dt.datetime.now(dt.timezone.utc)):
        raise QuietHours("05:45~08:00 KST — Spark 를 쓰지 않는다")
    wbspark, requests = _spark()
    B = wbspark._base()
    for _ in range(90):                               # 공용 서버 — 대기열이 길면 기다린다(최대 30분)
        try:
            q = requests.get(f"{B}/queue", timeout=15).json()
            if int(q.get("waiting", 0)) <= 6:
                break
        except Exception:  # noqa: BLE001
            break
        time.sleep(20)
    r = requests.post(f"{B}/jobs", json=payload, headers=wbspark._headers(), timeout=40)
    jid = r.json().get("job_id")
    if not jid:
        return None, {"status": "error", "error": r.text[:200]}, 0.0
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            d = requests.get(f"{B}/jobs/{jid}", headers=wbspark._headers(), timeout=60).json()
        except Exception as e:  # noqa: BLE001
            log(f"  폴링 오류 {str(e)[:80]}")
            continue
        if d.get("status") in ("done", "error", "failed"):
            return jid, d, round(time.time() - t0, 1)
    return jid, {"status": "timeout"}, round(time.time() - t0, 1)


def spark_fetch(jid: str, path: str) -> bool:
    wbspark, requests = _spark()
    f = requests.get(f"{wbspark._base()}/jobs/{jid}/file", headers=wbspark._headers(), timeout=300)
    if f.status_code == 200 and f.content:
        with open(path, "wb") as fp:
            fp.write(f.content)
        return True
    return False


# ── 목소리 ──────────────────────────────────────────────
TOKEN_RE = re.compile(r"\{([^|}]*)\|([^}]*)\}|(\S+)")


def parse_tokens(shots: list) -> tuple:
    """'{보이는 글|읽는 말}' → 토큰 [{disp, a, b, shot}] + 읽는 문장. a/b = 읽는 문장 안의 글자 위치."""
    toks, spoken = [], ""
    for si, sh_ in enumerate(shots):
        for m in TOKEN_RE.finditer(sh_["say"]):
            disp, spk = (m.group(1), m.group(2)) if m.group(3) is None else (m.group(3), m.group(3))
            if spoken:
                spoken += " "
            a = len(spoken)
            spoken += spk
            toks.append({"disp": disp, "a": a, "b": len(spoken), "shot": si})
    return toks, spoken


def _norm_map(s: str):
    chars, idx = [], []
    for i, c in enumerate(s.lower()):
        if c.isalnum():
            chars.append(c)
            idx.append(i)
    return "".join(chars), idx


def align(words: list, toks: list, spoken: str):
    """TTS 단어 시각 → 토큰마다 t0/t1(글자 순서대로 찾는다)."""
    norm, idx = _norm_map(spoken)
    starts = [t["a"] for t in toks]
    cur = 0
    for w in words:
        wn, _ = _norm_map(w["w"])
        if not wn:
            continue
        k = norm.find(wn, cur)
        if k < 0 or k - cur > 40:
            continue
        cur = k + len(wn)
        ti = max(0, bisect.bisect_right(starts, idx[k]) - 1)
        t = toks[ti]
        t["t0"] = min(t.get("t0", 1e9), w["t0"])
        t["t1"] = max(t.get("t1", 0), w["t1"])
    for i, t in enumerate(toks):
        if "t0" not in t:
            prev = next((toks[j]["t1"] for j in range(i - 1, -1, -1) if "t1" in toks[j]), 0.0)
            t["t0"], t["t1"] = prev, prev + 0.2


async def _edge(text: str, voice: str, rate: str, mp3: str) -> list:
    import edge_tts
    c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"w": ch["text"], "t0": ch["offset"] / 1e7, "t1": (ch["offset"] + ch["duration"]) / 1e7})
    return words


def wav_read(p: str):
    with wave.open(p) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768.0
    return sr, (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x)


def wav_write(p: str, sr: int, x):
    y = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(p, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())


def _line(sh_: dict) -> str:
    return " ".join(m.group(2) if m.group(3) is None else m.group(3) for m in TOKEN_RE.finditer(sh_["say"]))


def _voice_edge(ep, v, spoken, wav):
    mp3 = wav[:-4] + ".mp3"
    words = None
    for attempt in range(4):
        try:
            words = asyncio.run(_edge(spoken, v["name"], v.get("rate", "+0%"), mp3))
            if words:
                break
        except Exception as e:  # noqa: BLE001
            log(f"edge-tts 오류 {e} — 다시")
        time.sleep(5 + 10 * attempt)
    if not words:
        return None
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", mp3, "-af",
        "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=90,equalizer=f=3200:t=q:w=1.2:g=2",
        "-ar", str(SR), "-ac", "1", wav])
    return words


def _voice_lines(ep, v, wd, wav, mock: bool):
    """Supertonic(또는 mock): 줄마다 합성 · 단어 시각은 글자 비율로."""
    words, cursor, chunks = [], 0.0, []
    if not mock:
        wbspark, _ = _spark()
    for sh_ in ep["shots"]:
        line = _line(sh_)
        if mock:
            d = max(0.5, len(line.split()) / 2.7)
            t = np.arange(int(d * SR)) / SR
            x = (0.08 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
        else:
            raw = os.path.join(wd, f"st_{h16(v['name'], line)}.wav")
            if not os.path.exists(raw):
                for attempt in range(4):
                    if wbspark.tts(line, raw, v["name"], timeout_sec=600):
                        break
                    time.sleep(5 + 10 * attempt)
                else:
                    raise RuntimeError(f"목소리 실패: {line[:40]}")
            fixed = raw[:-4] + "_44k.wav"
            tempo = f"atempo={v['tempo']}," if v.get("tempo") else ""
            sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af",
                tempo + "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                "silenceremove=start_periods=1:start_threshold=-50dB,areverse", "-ar", str(SR), "-ac", "1", fixed])
            _, x = wav_read(fixed)
            d = len(x) / SR
        ws = line.split()
        tot = sum(len(w) + 1 for w in ws)
        acc = 0
        for w in ws:
            a0 = cursor + d * acc / tot
            acc += len(w) + 1
            words.append({"w": w, "t0": a0, "t1": cursor + d * acc / tot})
        chunks.append(x.astype(np.float32))
        gap = 0.22 if sh_["say"].rstrip()[-1:] in ".?!:" else 0.08
        chunks.append(np.zeros(int(gap * SR), np.float32))
        cursor += d + gap
    y = np.concatenate(chunks)
    wav_write(wav, SR, y / max(1e-6, float(np.abs(y).max())) * 0.9)
    return words


def make_voice(ep: dict, wd: str, mock: bool = False) -> dict:
    toks, spoken = parse_tokens(ep["shots"])
    v = {"engine": "mock"} if mock else VOICE
    key = h16(json.dumps(v, sort_keys=True), spoken)
    out_json = os.path.join(wd, f"voice_{key}.json")
    if os.path.exists(out_json):
        return json.load(open(out_json, encoding="utf-8"))
    wav = os.path.join(wd, f"voice_{key}.wav")
    words = None if mock else _voice_edge(ep, v, spoken, wav)
    if words is None:
        if not mock:
            log("edge-tts 실패 → Supertonic M3")
        words = _voice_lines(ep, {"engine": "mock"} if mock else FALLBACK_VOICE, wd, wav, mock)
    lead = max(0.0, words[0]["t0"] - 0.05)               # 첫 말이 50ms 에 나오게(훅은 바로 말한다)
    trimmed = wav[:-4] + "_t.wav"
    sh([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{lead:.3f}", "-i", wav, "-ar", str(SR), "-ac", "1", trimmed])
    for w in words:
        w["t0"] -= lead
        w["t1"] -= lead
    align(words, toks, spoken)
    with wave.open(trimmed) as w:
        dur = w.getnframes() / float(w.getframerate())
    res = {"wav": trimmed, "dur": dur, "tokens": toks, "spoken": spoken, "mock": mock}
    json.dump(res, open(out_json, "w", encoding="utf-8"), indent=1)
    return res


# ── 그림 ────────────────────────────────────────────────
def shot_prompt(ep: dict, sh_: dict) -> str:
    return STYLE + sh_["prompt"] + sh_.get("tail", ep.get("style_tail", ""))


def _mock_image(path: str, seed: int):
    r = np.random.RandomState(seed)
    c0, c1 = r.randint(20, 200, 3), r.randint(20, 200, 3)
    g = np.linspace(0, 1, 512)[:, None, None]
    a = (c0 * (1 - g) + c1 * g).astype(np.uint8)
    Image.fromarray(np.repeat(a, 288, axis=1)).save(path)


def make_assets(ep: dict, wd: str, mock: bool = False) -> dict:
    """편의 그림 전부(캐시: work 폴더 — 중간에 멈춰도 다음 실행이 받은 그림부터 잇는다)."""
    path = os.path.join(wd, "assets.json")
    A = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"img": {}, "spark": []}
    ref = {"jid": None, "t": 0.0}

    def save():
        json.dump(A, open(path, "w", encoding="utf-8"), indent=1)

    def ref_job():
        if ref["jid"] and time.time() - ref["t"] < REF_TTL:
            return ref["jid"]
        ch = ep["character"]
        p = STYLE + ch["prompt"] + ep.get("style_tail", "")
        for _ in range(3):
            jid, d, t = spark_job({"type": "image", "prompt": p, "width": IMG_W, "height": IMG_H, "no_llm": True,
                                   "model": "z-image-turbo", "seed": ch["seed"]}, timeout=900)
            if d.get("status") == "done":
                A["spark"].append({"shot": "ref", "type": "image", "server_s": d.get("elapsed")})
                ref.update(jid=jid, t=time.time())
                return jid
            time.sleep(20)
        raise RuntimeError("기준 그림 실패")

    A.setdefault("override", {})
    for i, sh_ in enumerate(ep["shots"]):
        if "reuse" in sh_:
            continue
        ov = A["override"].get(str(i))
        if ov and os.path.exists(ov):              # 검수가 다시 그린 그림(이어 받기에도 유지)
            A["img"][str(i)] = ov
            continue
        if sh_.get("edit"):
            key = h16("edit", ep["character"]["prompt"], ep["character"]["seed"], sh_["edit"])
        else:
            key = h16(shot_prompt(ep, sh_), IMG_W, IMG_H, sh_.get("seed"))
        png = os.path.join(wd, f"img_{i:02d}_{key}{'_mock' if mock else ''}.png")
        if os.path.exists(png):
            A["img"][str(i)] = png
            continue
        if mock:
            _mock_image(png, int(key[:6], 16))
            A["img"][str(i)] = png
            continue
        seed = int(sh_.get("seed", int(key[:8], 16) % 2147483647))
        for attempt in range(3):
            if sh_.get("edit"):
                body = {"type": "image", "from_job": ref_job(), "edit": EDIT_PREFIX + sh_["edit"], "prompt": sh_["edit"],
                        "upscale": "x2", "no_llm": True}
            else:
                body = {"type": "image", "prompt": shot_prompt(ep, sh_), "width": IMG_W, "height": IMG_H,
                        "no_llm": True, "model": "z-image-turbo", "seed": seed}
            jid, d, t = spark_job(body)
            if d.get("status") == "done" and spark_fetch(jid, png):
                A["spark"].append({"shot": i, "type": "edit" if sh_.get("edit") else "image",
                                   "server_s": d.get("elapsed"), "size": f"{d.get('width')}x{d.get('height')}"})
                log(f"{ep['id']:03d} 그림 {i:02d} {d.get('model')} {d.get('width')}x{d.get('height')} · {t}s")
                break
            log(f"{ep['id']:03d} 그림 {i:02d} 실패 {d.get('status')} {str(d.get('error'))[:120]}")
            if sh_.get("edit"):
                ref["jid"] = None                          # 기준 그림이 지워졌을 수 있다
            time.sleep(20)
        else:
            raise RuntimeError(f"그림 {i} 실패")
        A["img"][str(i)] = png
        save()
    save()
    A["_ref"] = ref
    return A


def redraw_fn(ep: dict, A: dict, wd: str):
    """검수가 고친 프롬프트로 한 컷을 다시 그린다(편집 컷은 기준 그림에서 편집) → 새 그림 경로 · 실패면 None."""
    def redraw(i: int, text: str) -> str | None:
        sh_ = ep["shots"][i]
        png = os.path.join(wd, f"img_{i:02d}_qa_{h16(text)}.png")
        if not os.path.exists(png):
            if sh_.get("edit"):
                ch = ep["character"]
                jid, d, _ = spark_job({"type": "image", "prompt": STYLE + ch["prompt"] + ep.get("style_tail", ""),
                                       "width": IMG_W, "height": IMG_H, "no_llm": True, "model": "z-image-turbo",
                                       "seed": ch["seed"]}, timeout=900)
                if d.get("status") != "done":
                    return None
                body = {"type": "image", "from_job": jid, "edit": EDIT_PREFIX + text, "prompt": text, "upscale": "x2",
                        "no_llm": True}
            else:
                body = {"type": "image", "prompt": STYLE + text + sh_.get("tail", ep.get("style_tail", "")),
                        "width": IMG_W, "height": IMG_H, "no_llm": True, "model": "z-image-turbo",
                        "seed": int(h16(text)[:8], 16) % 2147483647}
            jid, d, t = spark_job(body)
            if d.get("status") != "done" or not spark_fetch(jid, png):
                return None
            A["spark"].append({"shot": i, "type": "qa_redraw", "server_s": d.get("elapsed")})
            log(f"{ep['id']} 검수 다시 그림 {i:02d} · {t}s")
        A["override"][str(i)] = png
        json.dump({k: v for k, v in A.items() if not k.startswith("_")},
                  open(os.path.join(wd, "assets.json"), "w", encoding="utf-8"), indent=1)
        return png
    return redraw


# ── 시간표·자막 ─────────────────────────────────────────
def build_timeline(ep: dict, V: dict) -> dict:
    toks = V["tokens"]
    n = len(ep["shots"])
    starts = [0.0] * n
    for si in range(1, n):
        first = next(t for t in toks if t["shot"] == si)
        starts[si] = max(starts[si - 1] + 0.4, first["t0"] - 0.06)
    total = min(max(t["t1"] for t in toks) + 0.35, V["dur"] + 0.35)
    ends = starts[1:] + [total]
    phrases, cur = [], []
    for t in toks:
        disp = re.sub(r'^["“]+|["”.,;:…]+$', "", t["disp"]).replace("...", "").strip().rstrip('"”').strip()
        if not disp or disp in ("—", "-"):
            continue
        if cur and (t["shot"] != cur[-1]["shot"] or t["t0"] - cur[-1]["t1"] > 0.3):
            phrases.append(cur)
            cur = []
        cur.append({"d": disp, "t0": t["t0"], "t1": t["t1"], "shot": t["shot"]})
        if re.search(r"[.?!:;,…—]\"?$", t["disp"]):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    chunks = []
    for ph in phrases:                                # 2~3단어씩 고르게(끝에 한 단어만 남지 않게)
        m = len(ph)
        chars = sum(len(w["d"]) + 1 for w in ph)
        k = min(m, max(math.ceil(m / 3), math.ceil(chars / 18)))
        pos = 0
        for q in range(k):
            sz = m // k + (1 if q < m % k else 0)
            part = ph[pos:pos + sz]
            pos += sz
            chunks.append({"words": part, "t0": part[0]["t0"]})
    chunks[0]["t0"] = 0.0
    for k, c in enumerate(chunks):
        last = c["words"][-1]["t1"]
        nxt = chunks[k + 1]["t0"] if k + 1 < len(chunks) else total
        c["t1"] = nxt if nxt - last < 0.6 else last + 0.3
    return {"starts": starts, "ends": ends, "total": total, "chunks": chunks}


def srt(T: dict, out: str):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    with open(out, "w", encoding="utf-8") as f:
        for k, c in enumerate(T["chunks"], 1):
            f.write(f"{k}\n{ts(c['t0'])} --> {ts(c['t1'])}\n{' '.join(w['d'] for w in c['words'])}\n\n")


# ── 화면 ────────────────────────────────────────────────
def ease_io(p):
    return 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, p)))


def ease_out(p):
    p = min(1, max(0, p))
    return 1 - (1 - p) ** 3


MOVES = ("hook", "push_in", "pull_out", "pan_left", "pan_right", "drift_left", "drift_right", "tilt_up", "punch",
         "shake", "orbit", "loop_end")


def cam_params(move: str, p: float, lt: float, dur: float, focus=None):
    """→ 확대, 중심 x·y(그림 0~1). 밀기·당기기·패닝만(회전·흔들림 없음 — 세부가 떨리고 가장자리가 찢어진다).
    shake·orbit 은 옛 대본 호환으로 push_in 과 같다."""
    e = ease_io(p)
    lin = 0.35 * p + 0.65 * e
    z, cx, cy = 1.06, 0.5, 0.5
    if move == "hook":
        z = 1.0 + 0.14 * ease_out(lt / max(dur, 1.8))
    elif move in ("push_in", "shake", "orbit"):
        z = 1.04 + 0.09 * lin
    elif move == "pull_out":
        z = 1.14 - 0.09 * lin
    elif move in ("pan_right", "pan_left"):
        z = 1.14
        d = 0.045 * (1 if move == "pan_right" else -1)
        cx = 0.5 - d + 2 * d * lin
    elif move in ("drift_right", "drift_left"):
        z = 1.07 + 0.04 * lin
        d = 0.025 * (1 if move == "drift_right" else -1)
        cx = 0.5 - d + 2 * d * lin
    elif move == "tilt_up":
        z = 1.14
        cy = 0.55 - 0.1 * lin
    elif move == "punch":
        z = 1.16 - 0.1 * ease_out(min(1, lt / 0.4)) + 0.03 * p
    elif move == "loop_end":
        z = 1.0 + 0.14 * (1 - ease_io(p))
    if focus:
        cx += focus[0] - 0.5
        cy += focus[1] - 0.5
        z *= focus[2] if len(focus) > 2 else 1.0
    return z, cx, cy


def warp(src: Image.Image, z: float, cx: float, cy: float) -> Image.Image:
    ws, hs = src.size
    s = max(W / ws, H / hs) * z
    hx, hy = (W / 2) / s, (H / 2) / s
    px = min(max(cx * ws, hx), ws - hx)
    py = min(max(cy * hs, hy), hs - hy)
    a = 1.0 / s
    return src.transform((W, H), _AFFINE, (a, 0, px - a * W / 2, 0, a, py - a * H / 2), resample=_BICUBIC)


class Particles:
    """먼지·비·불티 등 입자(3겹 깊이) — 정지 그림 위에서 살아 있는 느낌을 준다."""

    def __init__(self, kind: str, seed: int):
        self.kind = kind
        r = np.random.RandomState(seed)
        n = {"float": 40, "dust": 50, "rain": 140, "embers": 45, "smoke": 24, "snow": 70, "spray": 60,
             "debris": 22}.get(kind, 0)
        self.n = n
        self.x, self.y = r.rand(n) * W, r.rand(n) * H
        self.z = r.choice([0.35, 0.65, 1.0], size=n, p=[0.5, 0.33, 0.17])
        self.ph, self.sz = r.rand(n) * 6.28, r.rand(n)
        v = {"float": ((r.rand(n) - 0.5) * 30, (r.rand(n) - 0.5) * 30),
             "dust": ((r.rand(n) - 0.5) * 24, -8 - r.rand(n) * 16),
             "rain": (-260 * np.ones(n), 1500 + r.rand(n) * 500),
             "embers": ((r.rand(n) - 0.5) * 60, -90 - r.rand(n) * 120),
             "smoke": ((r.rand(n) - 0.3) * 30, -30 - r.rand(n) * 20),
             "snow": ((r.rand(n) - 0.5) * 40, 60 + r.rand(n) * 60),
             "spray": (120 + r.rand(n) * 160, (r.rand(n) - 0.6) * 60),
             "debris": (900 + r.rand(n) * 900, (r.rand(n) - 0.5) * 500)}.get(kind, (np.zeros(n), np.zeros(n)))
        self.vx, self.vy = v
        self.sprites = {}

    def sprite(self, rad: int, col: tuple, blur: float, aq: int):
        k = (rad, col, blur, aq)
        if k not in self.sprites:
            s = rad * 2 + int(blur * 3) * 2 + 2
            im = Image.new("RGBA", (s, s), col + (0,))
            c = s // 2
            ImageDraw.Draw(im).ellipse([c - rad, c - rad, c + rad, c + rad], fill=col + (255,))
            if blur:
                im = im.filter(ImageFilter.GaussianBlur(blur))
            if aq < 10:
                im.putalpha(im.getchannel("A").point(lambda v: int(v * aq / 10)))
            self.sprites[k] = im
        return self.sprites[k]

    def draw(self, img: Image.Image, lt: float, zoom: float):
        if not self.n:
            return
        d = ImageDraw.Draw(img, "RGBA")
        for i in range(self.n):
            z = self.z[i]
            x = (self.x[i] + self.vx[i] * z * lt) % (W + 200) - 100
            y = (self.y[i] + self.vy[i] * z * lt) % (H + 200) - 100
            k = zoom ** (1.5 * z)
            x, y = W / 2 + (x - W / 2) * k, H / 2 + (y - H / 2) * k
            if self.kind == "rain":
                ln = 30 + 70 * z
                d.line([(x, y), (x + 0.17 * ln, y - ln)], fill=(200, 215, 230, int(40 + 90 * z)), width=max(1, int(2 * z)))
                continue
            if self.kind == "debris":
                s = 4 + 10 * z
                ang = self.ph[i] + lt * 9
                d.polygon([(x + s * math.cos(ang + q), y + 0.6 * s * math.sin(ang + q)) for q in (0, 1.6, 3.14, 4.7)],
                          fill=(235, 235, 228, 200))
                continue
            if self.kind in ("float", "snow", "spray"):
                col, base = (225, 240, 255), 2 + 6 * self.sz[i]
            elif self.kind == "embers":
                col, base = (255, 150 + int(70 * self.sz[i]), 60), 2 + 3 * self.sz[i]
            elif self.kind == "smoke":
                col, base = (120, 120, 125), 30 + 50 * self.sz[i]
            else:
                col, base = (255, 236, 205), 1.5 + 3 * self.sz[i]
            rad = max(1, int(base * (0.5 + z)))
            blur = 12 if self.kind == "smoke" else (0 if z < 0.5 else (1.5 if z < 0.9 else 4.0))
            fl = 0.6 + 0.4 * math.sin(lt * 3 + self.ph[i]) if self.kind in ("embers", "dust", "float") else 1
            a = (0.25 + 0.55 * z) * fl * (0.35 if self.kind == "smoke" else 1)
            if a <= 0.02:
                continue
            sp = self.sprite(rad, col, blur, min(10, int(a * 10 + 0.5)))
            img.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)


def caption_img(words: list, active: int) -> Image.Image:
    size = 96
    while True:
        f = font(size)
        sp = f.getlength(" ")
        widths = [f.getlength(w) for w in words]
        tw = sum(widths) + sp * (len(words) - 1)
        if tw <= CAP_MAXW or size <= 54:
            break
        size -= 4
    st = max(6, size // 10)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (int(tw) + 4 * st + 20, asc + desc + 4 * st + 16), (0, 0, 0, 0))
    shd = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(shd)
    x = 2 * st + 10
    for w, wd_ in zip(words, widths):
        ds.text((x + 4, 2 * st + 12), w, font=f, fill=(0, 0, 0, 170), stroke_width=st, stroke_fill=(0, 0, 0, 170))
        x += wd_ + sp
    im.alpha_composite(shd.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im)
    x = 2 * st + 10
    for k, (w, wd_) in enumerate(zip(words, widths)):
        d.text((x, 2 * st + 6), w, font=f, fill=YELLOW if k == active else (255, 255, 255), stroke_width=st,
               stroke_fill=(0, 0, 0))
        x += wd_ + sp
    return im


class Renderer:
    def __init__(self, ep: dict, T: dict, A: dict):
        self.ep, self.T, self.shots = ep, T, ep["shots"]
        self.src = {}
        for i, sh_ in enumerate(self.shots):
            j = sh_.get("reuse", i)
            if j not in self.src:
                self.src[j] = Image.open(A["img"][str(j)]).convert("RGB")
        self.parts = {i: Particles(sh_.get("fx", "none"), 1000 + i) for i, sh_ in enumerate(self.shots)}
        g = ep.get("grade", {})
        c = g.get("contrast", 1.06)
        self.sat = g.get("saturation", 1.0)
        tint = g.get("tint", [1, 1, 1])
        self.lut = [min(255, max(0, int(((v - 118) * c + 118) * tint[ch]))) for ch in range(3) for v in range(256)]
        self.tint_lut = {}
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
        vig = np.clip(1.0 - 0.42 * np.clip(rr - 0.45, 0, None) ** 1.6, 0.45, 1.0)
        self.vig = Image.fromarray((np.repeat(vig[..., None], 3, 2) * 255).astype(np.uint8))
        r = np.random.RandomState(5)
        self.grain = []
        for _ in range(4):
            gr = np.repeat(np.repeat(r.randn(H // 2, W // 2) * 4.0, 2, 0), 2, 1)[..., None].repeat(3, 2)
            self.grain.append((Image.fromarray(np.clip(gr, 0, 255).astype(np.uint8)),
                               Image.fromarray(np.clip(-gr, 0, 255).astype(np.uint8))))
        self.caps = {}

    def frame(self, n: int) -> bytes:
        T = self.T
        t = n / FPS
        i = max(0, bisect.bisect_right(T["starts"], t) - 1)
        sh_ = self.shots[i]
        st, en = T["starts"][i], T["ends"][i]
        dur, lt = en - st, t - st
        p = lt / dur
        move = sh_.get("move", "push_in")
        z, cx, cy = cam_params(move, p, lt, dur, sh_.get("focus"))
        if move not in ("loop_end", "hook") and i > 0:
            z *= 1 + 0.025 * math.exp(-lt / 0.12)          # 컷마다 아주 작은 밀림
        im = warp(self.src[sh_.get("reuse", i)], z, cx, cy)
        if self.sat != 1.0:
            im = ImageEnhance.Color(im).enhance(self.sat)
        im = im.point(self.lut)
        if sh_.get("tint"):
            key = tuple(sh_["tint"])
            if key not in self.tint_lut:
                self.tint_lut[key] = [min(255, int(v * key[ch])) for ch in range(3) for v in range(256)]
            im = im.point(self.tint_lut[key])
        fl = 0.0
        for ft in sh_.get("flash", []):                   # 번개·충격: 0.1초짜리 짧은 빛 한 번
            if lt >= ft:
                fl = max(fl, 0.7 * math.exp(-(lt - ft) / 0.05))
        if fl > 0.01:
            im = Image.blend(im, Image.new("RGB", (W, H), (255, 255, 255)), min(0.85, fl))
        im = ImageChops.multiply(im, self.vig)
        gp, gn = self.grain[n % len(self.grain)]
        im = ImageChops.subtract(ImageChops.add(im, gp), gn)
        z0 = cam_params(move, 0, 0, dur, sh_.get("focus"))[0]
        self.parts[i].draw(im, lt, z / z0)
        ch = next(((k, c) for k, c in enumerate(T["chunks"]) if c["t0"] - 0.02 <= t < c["t1"]), None)
        if ch is not None:
            k, c = ch
            act = max([wi for wi, w in enumerate(c["words"]) if t >= w["t0"] - 0.03] or [0])
            if (k, act) not in self.caps:
                self.caps[(k, act)] = caption_img([w["d"] for w in c["words"]], act)
            cim = self.caps[(k, act)]
            age = t - c["t0"]
            if age < 0.09 and k > 0:
                s = 0.86 + 0.14 * (age / 0.09)
                cim = cim.resize((max(1, int(cim.width * s)), max(1, int(cim.height * s))))
            im.paste(cim, (int(CAP_CX - cim.width / 2), int(CAP_Y - cim.height / 2)), cim)
        return im.tobytes()


def _render_part(args):
    ep, T, A, a, b, out = args
    R = Renderer(ep, T, A)
    p = subprocess.Popen([ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for n in range(a, b):
        p.stdin.write(R.frame(n))
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg 실패 {out}")
    return out


def render_video(ep, T, A, wd, out, procs):
    nfr = int(round(T["total"] * FPS))
    step = math.ceil(nfr / procs)
    jobs = [(ep, T, A, k, min(nfr, k + step), os.path.join(wd, f"part_{k // step:02d}.mp4")) for k in range(0, nfr, step)]
    if len(jobs) == 1:
        parts = [_render_part(jobs[0])]
    else:
        with mp.Pool(len(jobs)) as pool:
            parts = pool.map(_render_part, jobs)
    lst = os.path.join(wd, "parts.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    sh([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])


# ── 소리 ────────────────────────────────────────────────
def _filt(x, lo=None, hi=None, order=2):
    """주파수 영역 버터워스 크기 필터(scipy 없이)."""
    x = np.asarray(x, np.float64)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    g = np.ones_like(f)
    if hi:
        g /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g /= np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    return np.fft.irfft(X * g, len(x))


def _lp(x, fc):
    return _filt(x, hi=fc)


def _hp(x, fc):
    return _filt(x, lo=fc)


def _bp(x, lo, hi):
    return _filt(x, lo=lo, hi=hi)


def movavg(x, win: int):
    c = np.cumsum(np.concatenate([[0.0], x]))
    h = win // 2
    idx = np.arange(len(x))
    a, b = np.clip(idx - h, 0, len(x)), np.clip(idx + h + 1, 0, len(x))
    return (c[b] - c[a]) / np.maximum(1, b - a)


SFX = ("hit", "boom", "thud", "whoosh", "suck", "thunder", "zap", "fire", "drip", "water", "alarm", "radio", "hiss",
       "rumble", "wind", "siren", "heartbeat", "fizz", "crash")


def sfx(name: str, r: np.random.RandomState) -> np.ndarray:
    def noise(sec):
        return r.randn(int(sec * SR))

    def t(sec):
        return np.arange(int(sec * SR)) / SR
    if name == "hit":
        tt = t(1.2)
        y = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-tt * 3) + 38) / SR) * np.exp(-tt * 3.5)
        return 0.9 * (y + 0.4 * _lp(noise(1.2), 2500) * np.exp(-tt * 30))
    if name in ("boom", "thud"):
        tt = t(2.5 if name == "boom" else 0.7)
        y = np.sin(2 * np.pi * np.cumsum(45 * np.exp(-tt * 1.5) + 30) / SR) * np.exp(-tt * (1.6 if name == "boom" else 6))
        return 0.9 * (y + 0.5 * _lp(noise(len(tt) / SR), 300) * np.exp(-tt * 4))
    if name in ("whoosh", "suck"):
        n_, tt = noise(0.8), t(0.8)
        y = np.zeros_like(n_)
        for k, (lo, hi) in enumerate([(300, 900), (700, 2000), (1500, 4500)]):
            y += _bp(n_, lo, hi) * np.sin(np.pi * np.clip(tt / 0.8 * 3 - k, 0, 1)) ** 2
        y *= np.sin(np.pi * tt / 0.8) ** 2
        return 1.2 * (y[::-1] if name == "suck" else y)
    if name == "thunder":
        tt = t(3.5)
        return 0.8 * _hp(noise(3.5), 1500) * np.exp(-tt * 9) + 2.2 * _lp(noise(3.5), 180) * (1 - np.exp(-tt * 8)) * np.exp(-tt * 0.9)
    if name == "zap":
        tt = t(0.6)
        return 0.9 * (np.sign(np.sin(2 * np.pi * 120 * tt)) * 0.3 + _hp(noise(0.6), 2000) * (r.rand(len(tt)) > 0.97)) * np.exp(-tt * 5)
    if name == "fire":
        tt = t(1.5)
        return 0.6 * (_hp(noise(1.5), 1200) * (r.rand(len(tt)) > 0.985) * 3 + 0.3 * _lp(noise(1.5), 600)) * np.sin(np.pi * tt / 1.5)
    if name == "drip":
        tt = t(0.35)
        return 0.5 * np.sin(2 * np.pi * np.cumsum(1400 * np.exp(-tt * 12) + 500) / SR) * np.exp(-tt * 14)
    if name == "water":
        y = np.zeros(int(1.4 * SR))
        for _ in range(9):
            s = r.randint(0, len(y) - 8000)
            tt = np.arange(6000) / SR
            y[s:s + 6000] += 0.5 * np.sin(2 * np.pi * np.cumsum((300 + r.rand() * 500) * (1 + 2 * tt)) / SR) * np.exp(-tt * 30)
        return _lp(y + 0.15 * _lp(r.randn(len(y)), 500), 2200)
    if name == "alarm":
        tt = t(1.5)
        return 0.18 * np.sin(2 * np.pi * np.where((tt % 0.5) < 0.25, 880, 660) * tt) * ((tt % 0.5) < 0.42)
    if name == "radio":
        n_ = _bp(noise(0.9), 900, 3500)
        return 0.5 * n_ * (0.5 + 0.5 * (r.rand(len(n_)) > 0.6)) * np.sin(np.pi * np.arange(len(n_)) / len(n_))
    if name == "hiss":
        return 0.4 * _hp(noise(1.2), 3000) * np.sin(np.pi * t(1.2) / 1.2)
    if name == "rumble":
        return 2.5 * _lp(noise(2.5), 120) * np.sin(np.pi * t(2.5) / 2.5)
    if name == "wind":
        n_ = noise(2.2)
        return 1.1 * (_bp(n_, 250, 1200) + 0.5 * _bp(n_, 1200, 3000)) * np.sin(np.pi * t(2.2) / 2.2) ** 1.5
    if name == "siren":
        tt = t(1.8)
        return 0.12 * np.sin(2 * np.pi * np.cumsum(700 + 250 * np.sin(2 * np.pi * 1.5 * tt)) / SR) * np.sin(np.pi * tt / 1.8)
    if name == "heartbeat":
        y = np.zeros(int(1.8 * SR))
        for s in (0.0, 0.28, 0.9, 1.18):
            tt = np.arange(int(0.25 * SR)) / SR
            k = int(s * SR)
            y[k:k + len(tt)] += np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 18)
        return 0.9 * y
    if name == "fizz":
        tt = t(1.4)
        return 0.8 * _hp(noise(1.4), 4000) * (r.rand(len(tt)) > 0.9) * np.sin(np.pi * tt / 1.4)
    if name == "crash":
        tt = t(3.0)
        y = 1.4 * _lp(noise(3.0), 1800) * (1 - np.exp(-tt * 30)) * np.exp(-tt * 1.3)
        b = sfx("boom", r)[:len(tt)]
        y[:len(b)] += 0.8 * b
        return y
    return np.zeros(1)


MOODS = {"space": (73.42, 62), "storm": (65.41, 76), "tension": (69.3, 92), "ocean": (61.74, 70)}


def music_bed(mood: str, total: float, seed: int) -> np.ndarray:
    r = np.random.RandomState(seed)
    n = int(total * SR) + SR
    tt = np.arange(n) / SR
    root, bpm = MOODS.get(mood, MOODS["tension"])
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.07 * tt)
    y = 0.22 * (np.sin(2 * np.pi * root * tt) + 0.5 * np.sin(2 * np.pi * root * 1.5 * tt + 1)
                + 0.35 * np.sin(2 * np.pi * root * 2.003 * tt) + 0.2 * np.sin(2 * np.pi * root * 3.01 * tt)) * lfo
    y += 0.05 * _lp(r.randn(n), 900) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * tt))
    for k, mult in enumerate([4, 4.757, 6]):
        y += 0.03 * np.sin(2 * np.pi * root * mult * tt + k) * (0.5 + 0.5 * np.sin(2 * np.pi * (0.03 + 0.01 * k) * tt))
    beat = 60.0 / bpm
    for k in range(int(total / beat) + 2):
        s, ln = int(k * beat * SR), int(0.35 * SR)
        if s + ln > n:
            break
        u = np.arange(ln) / SR
        y[s:s + ln] += 0.33 * np.sin(2 * np.pi * (50 + 40 * np.exp(-u * 25)) * u) * np.exp(-u * 9)
    if mood == "storm":
        y += 0.12 * _lp(_hp(r.randn(n), 400), 5000)
    if mood == "ocean":
        y += 0.16 * _lp(r.randn(n), 700) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * tt)) ** 2
    if mood == "space":
        y += 0.025 * np.sin(2 * np.pi * root * 8 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * tt))
    return y


def build_audio(ep, T, V, wd, out_m4a):
    _, v = wav_read(V["wav"])
    n = int(T["total"] * SR)
    voice = np.zeros(n, np.float32)
    voice[:min(n, len(v))] = v[:n]
    bed = music_bed(ep.get("music", "tension"), T["total"], ep["id"])[:n]
    bed = bed / (np.sqrt(np.mean(bed ** 2)) + 1e-9) * 0.05
    env = movavg(np.sqrt(movavg(voice.astype(np.float64) ** 2, 2205)), 4410)
    duck = 1.0 - 0.45 * np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
    fx = np.zeros(n, np.float32)
    r = np.random.RandomState(7)
    for i, sh_ in enumerate(ep["shots"]):
        if sh_.get("sfx"):
            s = sfx(sh_["sfx"], r).astype(np.float32)
            s = s / (np.abs(s).max() + 1e-9) * 0.5
            k = int(T["starts"][i] * SR)
            e = min(n, k + len(s))
            fx[k:e] += s[:e - k]
    mix = voice + bed * duck + fx * 0.55
    mix = mix / max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    wav_write(raw, SR, mix)
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=11",
        "-ar", str(SR), "-ac", "2", "-c:a", "aac", "-b:a", "192k", out_m4a])


# ── 확인용 그림 ─────────────────────────────────────────
def first2s(mp4: str, out: str):
    tiles = []
    with tempfile.TemporaryDirectory() as td:
        for k, ts in enumerate((0.0, 0.5, 1.0, 1.5, 2.0)):
            f = os.path.join(td, f"{k}.png")
            sh([ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{ts:.2f}", "-i", mp4, "-frames:v", "1", f])
            im = Image.open(f).convert("RGB").resize((360, 640), _LANCZOS)
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 92, 40], fill=(0, 0, 0))
            d.text((10, 6), f"{ts:.1f}s", font=font(26), fill=(255, 255, 255))
            tiles.append(im)
    sheet = Image.new("RGB", (5 * 368 - 8, 640), (20, 20, 20))
    for k, im in enumerate(tiles):
        sheet.paste(im, (k * 368, 0))
    sheet.save(out, quality=90)


def sheet_1s(mp4: str, out: str, cols: int = 11):
    """영상 전체를 1초에 한 장씩 — 깨진 곳을 사람이(또는 다음 검수가) 한눈에 본다."""
    with tempfile.TemporaryDirectory() as td:
        sh([ffmpeg(), "-y", "-loglevel", "error", "-i", mp4, "-vf", "fps=1,scale=270:480", os.path.join(td, "f_%03d.png")])
        fs = sorted(glob.glob(os.path.join(td, "f_*.png")))
        rows = max(1, math.ceil(len(fs) / cols))
        sheet = Image.new("RGB", (cols * 270, rows * 480), (0, 0, 0))
        for k, f in enumerate(fs):
            im = Image.open(f).convert("RGB")
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 64, 30], fill=(0, 0, 0))
            d.text((6, 3), f"{k}s", font=font(22), fill=(255, 255, 0))
            sheet.paste(im, ((k % cols) * 270, (k // cols) * 480))
    sheet.save(out, quality=88)


# ── 한 편 ───────────────────────────────────────────────
def render(ep: dict, out_dir: str = ST.OUT, work: str = ST.WORK, mock: bool = False, procs: int | None = None,
           limit_shots: int | None = None) -> dict:
    """한 편을 렌더 → {video, srt, sheet, first2s, meta, sec, spark}. limit_shots = 테스트용(앞 몇 장면만)."""
    t0 = time.time()
    if limit_shots:
        ep = dict(ep, shots=ep["shots"][:limit_shots])
    st = ST.stem(ep) + ("_mock" if mock else "")
    wd = os.path.join(work, st)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    V = make_voice(ep, wd, mock)
    log(f"{st} 목소리 {V['dur']:.1f}s")
    A = make_assets(ep, wd, mock)
    A.pop("_ref", None)
    qa = {"skipped": "mock"} if mock else None
    if not mock:
        import story_qa
        qa = story_qa.run(ep, A, redraw_fn(ep, A, wd))
        log(f"{st} 그림 검수: " + (qa.get("skipped") or f"걸림 {list(qa['flagged'])} · 고침 {qa['fixed']} · 남음 {qa['failed']}"
                                  f"{' · 막음(트렌드)' if qa['block'] else ''} · {qa['usd']}달러"))
    T = build_timeline(ep, V)
    base = os.path.join(out_dir, st)
    silent, m4a = os.path.join(wd, "silent.mp4"), os.path.join(wd, "audio.m4a")
    render_video(ep, T, A, wd, silent, procs or max(1, min(10, (os.cpu_count() or 2))))
    build_audio(ep, T, V, wd, m4a)
    sh([ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-map", "0:v", "-map", "1:a", "-c", "copy",
        "-shortest", "-movflags", "+faststart", base + ".mp4"])
    srt(T, base + ".srt")
    first2s(base + ".mp4", base + "_first2s.jpg")
    sheet_1s(base + ".mp4", base + "_sheet.jpg")
    sp = A.get("spark", [])
    with open(base + "_qa.json", "w", encoding="utf-8") as f:
        json.dump(qa, f, ensure_ascii=False, indent=1)
    res = {"id": ep["id"], "slug": ep["slug"], "video": base + ".mp4", "srt": base + ".srt",
           "sheet": base + "_sheet.jpg", "first2s": base + "_first2s.jpg", "sec": round(T["total"], 2), "mock": mock,
           "spark_server_s": round(sum(x.get("server_s") or 0 for x in sp)), "images": len(A["img"]),
           "edits": sum(1 for x in sp if x.get("type") == "edit"), "render_s": round(time.time() - t0),
           "kind": ep.get("kind", "catalog"), "qa": base + "_qa.json", "qa_block": bool(qa.get("block")),
           "qa_failed": qa.get("failed", []), "qa_fixed": qa.get("fixed", []), "qa_usd": qa.get("usd", 0)}
    with open(base + "_meta.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    log(f"✅ {base}.mp4 · {res['sec']}s · Spark {res['spark_server_s']}s · {res['render_s']}s")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Nine Tails 3D 실화·what-if 쇼츠 렌더")
    ap.add_argument("episode", help="카탈로그 id·slug 또는 편 키(트렌드 편: trend_<쓴 날>_<slug>)")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=ST.OUT)
    ap.add_argument("--work", default=ST.WORK)
    ap.add_argument("--procs", type=int)
    a = ap.parse_args()
    ep = ST.find(a.episode, trends=ST.load_trends())
    errs = ST.check_episode(ep)
    if errs:
        print("::error::카탈로그 검사 실패 — 렌더하지 않는다\n  " + "\n  ".join(errs))
        return 2
    try:
        render(ep, a.out, a.work, a.mock, a.procs)
    except QuietHours as e:
        print(f"⏸️ {e} — 받은 그림은 work 에 남았다. 다음 예비 실행이 잇는다.")
        return 75
    return 0


if __name__ == "__main__":
    sys.exit(main())
