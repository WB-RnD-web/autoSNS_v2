#!/usr/bin/env python3
"""SCP 아카이브 렌더러 — 다장면(멀티 씬) 배경 + 낭독 + 자막 번인 → 16:9 mp4.

사연/괴담(story_render)과의 차이:
  ① 배경이 1장이 아니라 ★여러 장면(scenes) — 이야기가 진행되며 크로스페이드로 전환돼 분위기를 만든다.
  ② 챕터 타임스탬프를 ★실제 TTS 길이로 재계산(루틴의 est_sec 는 추정치라 그대로 쓰면 밀린다).
  ③ 주 1회 발행(iso_week) — dedupe 키가 날짜가 아니라 주차.

TTS·자막(ASS)·폰트 로직은 story_render 를 그대로 재사용한다(중복 구현 금지).

렌더 비용 원칙(ASMR 운영 학습 반영):
  - 프레임 수 = 인코딩 시간. 정지 장면이라 낮은 fps 로 충분(기본 10fps).
    8분 @10fps = 4,800프레임 < ASMR 1시간 @2fps = 7,200프레임(프로덕션 실적).
  - 유튜브가 어차피 재인코딩 → preset ultrafast.
  - 크로스페이드 1.2s = 12프레임. 느린 분위기 전환엔 충분.
"""
from __future__ import annotations
import os
import re
import sys
import time as _time

import story_render as SR   # TTS / ASS / 폰트 / probe_dur 재사용
import imagegen

FFMPEG = SR.FFMPEG
W, H = 1920, 1080
FPS = int(os.environ.get("SCP_FPS", "10"))
PRESET = os.environ.get("SCP_PRESET", "ultrafast")
CRF = os.environ.get("SCP_CRF", "23")
XFADE = float(os.environ.get("SCP_XFADE", "1.2"))     # 장면 전환(초)
MAX_SCENES = int(os.environ.get("SCP_MAX_SCENES", "8"))
MIN_SCENE_SEC = float(os.environ.get("SCP_MIN_SCENE_SEC", "25"))


def _lap(t0, label):
    print(f"  ⏱ {label}: 누적 {_time.monotonic() - t0:.0f}s", flush=True)


# ── 장면 목록 결정 ──────────────────────────────────────
def resolve_scenes(spec: dict) -> list[dict]:
    """장면 프롬프트 목록. 우선순위:
      ① spec["scenes"] = [{"prompt":..., "negative_prompt":...}, ...]  ← 루틴이 주면 이걸 씀(권장)
      ② 폴백: background.prompt + thumbnail.hook + thumbnail.hook_alt[]
         (현재 SCP 스펙엔 scenes 가 없지만 이 4개가 모두 동일 스타일 접미사를 공유해 톤이 유지된다)
    """
    scenes: list[dict] = []
    raw = spec.get("scenes")
    if isinstance(raw, list) and raw:
        for s in raw:
            if isinstance(s, dict) and (s.get("prompt") or "").strip():
                scenes.append({"prompt": s["prompt"].strip(),
                               "negative_prompt": (s.get("negative_prompt") or "").strip()})
            elif isinstance(s, str) and s.strip():
                scenes.append({"prompt": s.strip(), "negative_prompt": ""})
        if scenes:
            print(f"  · 장면 소스: spec.scenes {len(scenes)}개")
            return scenes[:MAX_SCENES]

    bg = spec.get("background") or {}
    th = spec.get("thumbnail") or {}
    neg_bg = (bg.get("negative_prompt") or "").strip()
    neg_th = (th.get("negative_prompt") or "").strip()
    if (bg.get("prompt") or "").strip():
        scenes.append({"prompt": bg["prompt"].strip(), "negative_prompt": neg_bg})
    if (th.get("hook") or "").strip():
        scenes.append({"prompt": th["hook"].strip(), "negative_prompt": neg_th})
    for alt in (th.get("hook_alt") or []):
        if isinstance(alt, str) and alt.strip():
            scenes.append({"prompt": alt.strip(), "negative_prompt": neg_th})
    print(f"  · 장면 소스: background+thumbnail 폴백 {len(scenes)}개"
          f"{' (루틴이 scenes[] 를 주면 더 촘촘해짐)' if scenes else ''}")
    return scenes[:MAX_SCENES]


def _procedural(out_png: str) -> str:
    SR.sh([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x0d0b10:s={W}x{H}",
           "-frames:v", "1", "-vf", "vignette=PI/5,noise=alls=8:allf=t,format=rgb24", out_png])
    return out_png


def gen_scene_images(scenes: list[dict], workdir: str) -> list[str]:
    """장면별 이미지 생성 → WxH 정규화. 개별 실패는 건너뛰고, 전부 실패면 절차적 1장."""
    out: list[str] = []
    for i, sc in enumerate(scenes):
        raw = None
        try:
            raw = imagegen.flux_image(sc["prompt"], os.path.join(workdir, f"scene{i}_raw.png"),
                                      1344, 768, seed=i)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 장면{i} 생성 예외: {e}\n")
        if not raw:
            sys.stderr.write(f"[warn] 장면{i} 이미지 없음 — 건너뜀\n")
            continue
        norm = os.path.join(workdir, f"scene{i}.png")
        SR.sh([FFMPEG, "-y", "-i", raw, "-vf",
               f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
               f"eq=brightness=-0.05:saturation=1.02,vignette=PI/5", "-frames:v", "1", norm])
        out.append(norm)
    if not out:
        out.append(_procedural(os.path.join(workdir, "scene_proc.png")))
        print("  · ⚠️ FLUX 전부 실패 → 절차적 배경 1장")
    print(f"  · 장면 이미지 {len(out)}장 확보")
    return out


def xfade_chain(images: list[str], total: float, fps: int, xfade: float) -> tuple[list[str], float, float]:
    """xfade 체인용 (입력 인자, 장면길이 d, 전환길이 x) 계산.

    최종 길이 = Σd - (n-1)*x  →  d = (total + (n-1)*x)/n.
    쇼츠 렌더러(scp_shorts_render)도 이 식을 그대로 쓴다 — 한 곳에서만 유지한다.
    """
    n = len(images)
    x = min(xfade, max(0.4, total / n / 4))
    d = (total + (n - 1) * x) / n
    ins: list[str] = []
    for img in images:
        ins += ["-loop", "1", "-t", f"{d:.3f}", "-framerate", str(fps), "-i", os.path.abspath(img)]
    return ins, d, x


# ── 챕터 타임스탬프 재계산 ─────────────────────────────
def recompute_chapters(spec: dict, seg_durs: list[float]) -> list[str]:
    """루틴 챕터(est_sec 기준) → 실제 TTS 길이 기준으로 재매핑.

    루틴의 est_sec 합계와 실제 낭독 길이가 크게 다를 수 있어(관측: 310s vs ~480s),
    그대로 두면 유튜브 챕터가 전부 어긋난다. est 시간축의 위치를 세그먼트 인덱스로 옮긴 뒤
    그 세그먼트의 '실제 시작 시각'을 쓴다. 첫 챕터는 반드시 0:00(유튜브 요구사항).
    """
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    chapters = yt.get("chapters") or []
    segs = spec.get("segments") or []
    if not chapters or not segs or len(seg_durs) != len(segs):
        return list(chapters)

    # est 누적 / 실제 누적
    est_cum, t = [], 0.0
    for s in segs:
        t += float(s.get("est_sec", 0) or 0)
        est_cum.append(t)
    act_start, t = [], SR.LEAD_IN
    for d in seg_durs:
        act_start.append(t)
        t += d + SR.SEG_GAP

    out = []
    for idx, c in enumerate(chapters):
        m = re.match(r"\s*(\d+):(\d{2})\s+(.*)", str(c))
        if not m:
            out.append(str(c))
            continue
        est_sec = int(m.group(1)) * 60 + int(m.group(2))
        title = m.group(3).strip()
        if idx == 0:
            real = 0.0
        else:
            si = next((i for i, e in enumerate(est_cum) if e >= est_sec), len(segs) - 1)
            real = act_start[si]
        out.append(f"{int(real // 60):02d}:{int(real % 60):02d} {title}")
    print(f"  · 챕터 {len(out)}개 실제 시각으로 재계산(마지막 {out[-1].split()[0] if out else '-'})")
    return out


# ── 다장면 영상 조립(단일 패스: xfade 체인 + 자막 번인 + 오디오 mux) ──
def render_video(images: list[str], narration_m4a: str, ass_path: str,
                 fontsdir: str | None, out_mp4: str, total: float) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    wd = os.path.dirname(os.path.abspath(ass_path))
    sub = f"subtitles={os.path.basename(ass_path)}" + (f":fontsdir={fontsdir}" if fontsdir else "")

    n = len(images)
    # 장면이 너무 잦으면 산만 + 인코딩 낭비 → 최소 길이 보장
    if n > 1 and total / n < MIN_SCENE_SEC:
        n = max(1, int(total // MIN_SCENE_SEC))
        images = images[:n]
    if n == 1:
        cmd = [FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.abspath(images[0]),
               "-i", os.path.abspath(narration_m4a),
               "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,{sub}",
               "-c:v", "libx264", "-tune", "stillimage", "-preset", PRESET, "-crf", CRF,
               "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
               "-movflags", "+faststart", os.path.abspath(out_mp4)]
        SR.sh(cmd, cwd=wd)
        return out_mp4

    ins, d, x = xfade_chain(images, total, FPS, XFADE)
    ins += ["-i", os.path.abspath(narration_m4a)]

    fc, cur = [], None
    for i in range(n):
        fc.append(f"[{i}:v]fps={FPS},format=yuv420p,setsar=1[s{i}]")
    cur = "[s0]"
    for i in range(1, n):
        off = d * i - x * i          # 누적 오프셋
        lbl = f"[x{i}]"
        fc.append(f"{cur}[s{i}]xfade=transition=fade:duration={x:.3f}:offset={off:.3f}{lbl}")
        cur = lbl
    fc.append(f"{cur}{sub}[v]")

    cmd = [FFMPEG, "-y", *ins, "-filter_complex", ";".join(fc),
           "-map", "[v]", "-map", f"{n}:a",
           "-c:v", "libx264", "-tune", "stillimage", "-preset", PRESET, "-crf", CRF,
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
           "-movflags", "+faststart", os.path.abspath(out_mp4)]
    print(f"  · 장면 {n}개 × {d:.0f}s (전환 {x:.1f}s), {FPS}fps → 총 {total:.0f}s")
    SR.sh(cmd, cwd=wd)
    return out_mp4


# ── 썸네일 ─────────────────────────────────────────────
def build_thumbnail(spec: dict, out_jpg: str, workdir: str) -> str | None:
    th = spec.get("thumbnail") or {}
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    hook = (th.get("hook") or "").strip()
    text = (yt.get("thumbnail_text") or spec.get("title") or "").strip()
    if not hook:
        return None
    raw = imagegen.flux_image(hook, os.path.join(workdir, "thumb_raw.png"), 1344, 768)
    if not raw:
        return None
    try:
        from thumbnail import _overlay_title
        return _overlay_title(raw, text, out_jpg)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 오버레이 실패 → 스킵: {e}\n")
        return None


# ── 고수준 렌더 ────────────────────────────────────────
def render(spec: dict, out_mp4: str, workdir: str) -> dict:
    t0 = _time.monotonic()
    os.makedirs(workdir, exist_ok=True)
    segments = spec.get("segments") or []
    if not segments:
        raise RuntimeError("segments 없음")

    fontsdir, font_family = SR.resolve_font(workdir)
    durs = SR.synth_all(segments, workdir)
    _lap(t0, f"TTS {len(segments)}세그먼트")

    total = SR.LEAD_IN + sum(durs) + SR.SEG_GAP * (len(segments) - 1) + SR.TAIL
    narration = os.path.join(workdir, "narration.m4a")
    SR.build_narration(len(segments), durs, workdir, narration)
    ass_path = os.path.join(workdir, "captions.ass")
    SR.build_ass(segments, durs, font_family, ass_path)
    _lap(t0, "내레이션+자막")

    images = gen_scene_images(resolve_scenes(spec), workdir)
    _lap(t0, f"장면 이미지 {len(images)}장")

    render_video(images, narration, ass_path, fontsdir, out_mp4, total)
    _lap(t0, "영상 인코딩")

    dur = SR.probe_dur(out_mp4)
    size_mb = os.path.getsize(out_mp4) / 1e6
    chapters = recompute_chapters(spec, durs)
    print(f"✅ {out_mp4}  ({dur:.0f}s, {size_mb:.1f}MB, 장면 {len(images)}개, {len(segments)} segments)")
    return {"out": out_mp4, "duration_sec": round(dur, 1), "size_mb": round(size_mb, 1),
            "scenes": len(images), "chapters": chapters}


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="SCP 다장면 렌더(테스트)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="_scp_work")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    info = render(spec, args.out, args.workdir)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
