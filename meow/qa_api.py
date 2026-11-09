#!/usr/bin/env python3
"""Meow Remix 검수(비전) — 그림을 다 받은 뒤(영상 만들기 전)와 영상을 다 받은 뒤(올리기 전) Claude 에게 보여 준다(2026-11-09).

왜: 11/07 5B 견본은 '버벅이고 깨지고 일그러져' 불합격했다. 매일판은 만드는 동안 사람이 볼 수 없으니
  ① 그림: 다리·눈·꼬리 개수, 녹은 몸, 글자·워터마크, 사람(손 포함), 2컷째 고양이가 1컷과 다른 고양이
  ② 영상(클립마다 6장 띠): 몸이 녹거나 늘어남, 다리가 생기거나 사라짐, 얼굴 깨짐, 다른 고양이로 바뀜, 글자·사람이 나타남
  을 찾게 한다. 고치는 규칙은 daily.py(그림은 한 번 다시 그림 · 영상은 한 번 다시 만들고 그래도 걸리면 그날은 안 올림).
★키가 없거나 API 가 실패하면 None — 검수 없이 간다(검수 때문에 매일 편이 멈추지 않게). 토큰·달러는 결과에 남긴다.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R  # noqa: E402

MODEL = os.environ.get("MEOW_QA_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("MEOW_QA_EFFORT", "medium")
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}     # 입력·출력(달러/100만 토큰)

STILLS = """You review the start frames of a photorealistic AI cat YouTube Short before each frame is animated into a
5-second clip. Each shot comes with its image prompt (or the edit instruction that made it from an earlier shot).
Flag a shot (ok=false) only for problems a viewer would clearly notice:
- anatomy: extra or missing legs, paws, tails, ears or eyes; fused, melted or broken bodies or faces
- text: readable letters, numbers, logos or watermarks
- people: any human or human body part (hands, arms, faces)
- mismatch: the frame clearly does not show the main thing the prompt asks for
- different_cat: a later shot shows a clearly different cat (coat colour or pattern) from the cat in shot 1. Skip this when
  shot 1 shows food or an object that only hints at a kitten (format "morph").
Small oddities, style and composition choices are fine. For each flagged shot write "fix": the full corrected English
prompt for that shot in the same kind as given (an image prompt, or an edit instruction that starts with "Keep exactly the
same ..."); describe positively what to show, no negations.
Return only JSON: {"shots": [{"shot": <number>, "ok": true|false, "issues": ["anatomy: ..."], "fix": "..."}]}"""

CLIPS = """You review AI-generated 5-second video clips of a photorealistic cat YouTube Short before upload. Each clip is
shown as one strip of 6 frames, left to right in time, with the motion it should show.
Flag a clip (ok=false) only for problems a viewer would clearly notice in motion:
- the body melts, stretches, merges with objects or changes shape
- legs, paws, tails, ears or eyes appear, disappear or multiply
- the face breaks or smears
- the cat turns into a different cat (coat colour or pattern) during the clip
- text, a watermark, or a human or human hand appears
- frames blow out to white or turn to noise
Motion blur, small softness and a pose that differs from the prompt are fine.
Return only JSON: {"clips": [{"clip": <number>, "ok": true|false, "issues": ["melting: ..."]}]}"""


def jpeg_b64(src: str, out: str, vf: str) -> str:
    subprocess.run([R.ffmpeg(), "-v", "error", "-y", "-i", src, "-vf", vf, "-frames:v", "1", "-q:v", "4", out], check=True)
    with open(out, "rb") as f:
        return base64.b64encode(f.read()).decode()


def still_b64(png: str) -> str:
    return jpeg_b64(png, png[:-4] + "_qa.jpg", "scale=384:-2")


def strip_b64(clip: str, n: int = 6) -> str:
    """클립 5초에서 고르게 n 장 → 가로 띠 한 장."""
    return jpeg_b64(clip, clip[:-4] + "_qa.jpg", f"fps={n / 5.2:.3f},scale=240:-2,tile={n}x1")


def client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def parse(text: str, key: str, asked: set) -> list[dict]:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("검수 답에 JSON 이 없다")
    one = key[:-1]
    rows = []
    for r in json.loads(t[a:b + 1]).get(key, []):
        try:
            n = int(r.get(one))
        except (TypeError, ValueError):
            continue
        if n in asked:
            rows.append({one: n, "ok": bool(r.get("ok", True)), "issues": [str(x)[:200] for x in r.get("issues") or []],
                         "fix": str(r.get("fix") or "")[:1500]})
    missing = asked - {r[one] for r in rows}
    if missing:
        raise ValueError(f"검수 답에 {sorted(missing)} 이 없다")
    return rows


def ask(cl, system: str, content: list, key: str, asked: set) -> dict:
    msg = cl.messages.create(model=MODEL, max_tokens=4000, system=system, messages=[{"role": "user", "content": content}],
                             extra_body={"output_config": {"effort": EFFORT}})
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    pi, po = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    u = msg.usage
    usd = ((getattr(u, "input_tokens", 0) or 0) * pi + (getattr(u, "output_tokens", 0) or 0) * po) / 1e6
    return {key: parse(text, key, asked), "model": MODEL, "usd": round(usd, 4)}


def _what(c: dict, i: int) -> str:
    s = c["shots"][i - 1]
    if s.get("edit"):
        return f"edit of shot {s.get('from', 1)}: {s['edit']}"
    return f"image prompt: {s['image']}"


def review_stills(c: dict, cl=None) -> dict | None:
    """컷 그림 전부 → {"shots": [...], "usd"} · 키 없음·실패면 None."""
    cl = cl or client()
    if cl is None:
        return None
    content = [{"type": "text", "text": f"Short: {c['title']}\nFormat: {c['format']}\nShots: {len(c['shots'])}"}]
    for i in range(1, len(c["shots"]) + 1):
        content.append({"type": "text", "text": f"Shot {i} — {_what(c, i)}\nIt will be animated as: {c['shots'][i - 1]['motion']}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": still_b64(R.shot_png(c, i))}})
    try:
        return ask(cl, STILLS, content, "shots", set(range(1, len(c["shots"]) + 1)))
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 그림 검수 실패(검수 없이 간다): {str(e)[:200]}")
        return None


def review_clips(c: dict, which: list[int] | None = None, cl=None) -> dict | None:
    """클립(1부터 · 없으면 전부) → {"clips": [...], "usd"} · 키 없음·실패면 None."""
    cl = cl or client()
    if cl is None:
        return None
    which = which or list(range(1, len(c["shots"]) + 1))
    content = [{"type": "text", "text": f"Short: {c['title']}\nFormat: {c['format']}\nClips to review: {which}"}]
    for i in which:
        content.append({"type": "text", "text": f"Clip {i} — motion: {c['shots'][i - 1]['motion']}"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": strip_b64(R.clip_path(c, i))}})
    try:
        return ask(cl, CLIPS, content, "clips", set(which))
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 영상 검수 실패(검수 없이 간다): {str(e)[:200]}")
        return None


def flagged(res: dict | None, key: str) -> list[dict]:
    return [r for r in (res or {}).get(key, []) if not r["ok"]]
