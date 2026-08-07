#!/usr/bin/env python3
"""ASMR 렌더러 — 정적 배경 1장 + Freesound 앰비언트(심리스 루프) + 낮은 나레이션 → 16:9 mp4.

소설(novel_render)과 사상 동일: 정적 이미지 + 오디오. 차이는 오디오가 낭독이 아니라
'테마 앰비언트(가위질/빗소리/…)를 1시간으로 이음새 없이 루프'한다는 점.

흐름:
  ① 클립들(mp3) → 48k 스테레오 wav 정규화
  ② 크로스페이드로 이어 'base' 생성 → base 를 크로스페이드 루프해 목표 길이 채움 → loudnorm + 페이드
  ③ (선택) 나레이션(edge-tts) 을 앰비언트보다 낮게 시작부에 믹스
  ④ 정적 이미지 + 오디오 → H.264/yuv420p/AAC/+faststart (정지영상이라 파일 아주 작음)
  ⑤ 썸네일: FLUX 배경 + 문구 오버레이(소설 thumbnail 재사용)

배경음/자막 없음(앰비언트 자체가 콘텐츠). 잘 때 듣는 용도 → 차분한 라우드니스(-20 LUFS).
"""
from __future__ import annotations
import math
import os
import re
import shutil
import subprocess
import sys

W, H = 1920, 1080  # 16:9
# 정지영상이라 fps 는 최소로(프레임 수 = 인코딩 시간). 2fps → 10fps 대비 프레임 1/5.
FPS = int(os.environ.get("ASMR_FPS", "2"))
# 유튜브가 재인코딩하므로 프리셋 품질 차이는 최종 화질에 사실상 무의미 → 최속 프리셋.
PRESET = os.environ.get("ASMR_PRESET", "ultrafast")
XFADE = float(os.environ.get("ASMR_XFADE", "2.5"))  # 크로스페이드 길이(초)


def _bin(name):
    return shutil.which(name) or name


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def sh(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {' '.join(cmd)}\n{(e.stdout or '')[-800:]}\n{(e.stderr or '')[-1500:]}\n")
        raise


def probe_dur(path: str) -> float:
    """길이(초). ffprobe 있으면 그걸로, 없으면 ffmpeg -i stderr 파싱."""
    if shutil.which("ffprobe"):
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


# ── ① 정규화 ──
def _norm_clip(src: str, dst: str) -> str:
    sh([FFMPEG, "-y", "-i", src, "-vn", "-ar", "48000", "-ac", "2", dst])
    return dst


# ── 크로스페이드 체인(여러 입력을 하나로) ──
def _xfade_concat(inputs: list[str], out_wav: str, d: float = XFADE) -> str:
    if len(inputs) == 1:
        shutil.copyfile(inputs[0], out_wav)
        return out_wav
    ins = []
    for p in inputs:
        ins += ["-i", p]
    fc, cur = [], "[0]"
    for i in range(1, len(inputs)):
        lbl = f"[x{i}]"
        fc.append(f"{cur}[{i}]acrossfade=d={d}:c1=tri:c2=tri{lbl}")
        cur = lbl
    sh([FFMPEG, "-y", *ins, "-filter_complex", ";".join(fc), "-map", cur, out_wav])
    return out_wav


# ── ② 앰비언트 베드(심리스 루프) ──
def build_bed(clips: list[str], out_wav: str, target_sec: float, workdir: str) -> str:
    """클립들 → 크로스페이드 base → 루프해 target_sec 채움 → loudnorm + 페이드인/아웃."""
    norm = [_norm_clip(c, os.path.join(workdir, f"n{i:02d}.wav")) for i, c in enumerate(clips)]
    base = _xfade_concat(norm, os.path.join(workdir, "base.wav"))
    base_dur = probe_dur(base)
    if base_dur <= 0:
        raise RuntimeError("base 길이 측정 실패")
    reps = max(1, math.ceil(target_sec / max(1.0, base_dur - XFADE)))
    reps = min(reps, 60)  # 폭주 가드
    long_ = base if reps == 1 else _xfade_concat([base] * reps, os.path.join(workdir, "long.wav"))
    st = max(0.0, target_sec - 6)
    sh([FFMPEG, "-y", "-i", long_, "-af",
        f"atrim=0:{target_sec:.2f},afade=t=in:d=2,afade=t=out:st={st:.2f}:d=6,"
        f"loudnorm=I=-20:TP=-2:LRA=11",
        "-ar", "48000", "-ac", "2", out_wav])
    print(f"  · 앰비언트 베드: base {base_dur:.0f}s ×{reps} → {probe_dur(out_wav):.0f}s")
    return out_wav


# ── ③ 나레이션(edge-tts) + 낮은 믹스 ──
def synth_narration(text: str, voice: str, out_wav: str, workdir: str) -> str | None:
    if not (text or "").strip():
        return None
    mp3 = os.path.join(workdir, "nar.mp3")
    try:
        sh([sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text, "--write-media", mp3])
        sh([FFMPEG, "-y", "-i", mp3, "-ar", "48000", "-ac", "2", out_wav])
        return out_wav
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 나레이션 합성 실패 → 무나레이션: {e}\n")
        return None


def mix_audio(bed_wav: str, nar_wav: str | None, out_m4a: str,
              gain: float = 0.35, delay: float = 3.0) -> str:
    if nar_wav:
        ms = int(delay * 1000)
        fc = (f"[1:a]adelay={ms}|{ms},volume={gain}[nar];"
              f"[0:a][nar]amix=inputs=2:duration=first:normalize=0[a]")
        sh([FFMPEG, "-y", "-i", bed_wav, "-i", nar_wav, "-filter_complex", fc,
            "-map", "[a]", "-c:a", "aac", "-b:a", "192k", out_m4a])
    else:
        sh([FFMPEG, "-y", "-i", bed_wav, "-c:a", "aac", "-b:a", "192k", out_m4a])
    return out_m4a


# ── 배경 이미지(FLUX → 실패 시 절차적 다크) ──
def ensure_background(prompt: str, out_png: str, workdir: str) -> str:
    import imagegen
    raw = imagegen.flux_image(prompt, os.path.join(workdir, "bg_raw.png"), 1344, 768)
    src = raw or _procedural_bg(os.path.join(workdir, "bg_proc.png"))
    sh([FFMPEG, "-y", "-i", src, "-vf",
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
        f"eq=brightness=-0.06:saturation=1.03,vignette=PI/5", "-frames:v", "1", out_png])
    return out_png


def _procedural_bg(out_png: str) -> str:
    sh([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x0e1020:s={W}x{H}",
        "-frames:v", "1", "-vf", "vignette=PI/5,noise=alls=8:allf=t,format=rgb24", out_png])
    return out_png


# ── ④ 정적 영상 조립 ──
def render_video(image: str, audio_m4a: str, out_mp4: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    adur = probe_dur(audio_m4a)          # 오디오 길이에 정확히 맞춰 자른다(-t)
    sh([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", image, "-i", audio_m4a,
        "-c:v", "libx264", "-tune", "stillimage", "-preset", PRESET, "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
        "-r", str(FPS), "-c:a", "copy", "-t", f"{adur:.2f}", "-movflags", "+faststart", out_mp4])
    return out_mp4


# ── ⑤ 썸네일(FLUX 배경 + 문구 오버레이, 소설 thumbnail 재사용) ──
def build_thumbnail(hook: str, text: str, out_jpg: str, workdir: str) -> str | None:
    import imagegen
    prompt = (hook or "").strip()
    if not prompt:
        return None
    raw = imagegen.flux_image(prompt + ", cozy calm nighttime mood, soft warm light, no text, no letters",
                              os.path.join(workdir, "thumb_raw.png"), 1344, 768)
    if not raw:
        return None
    try:
        from thumbnail import _overlay_title  # 16:9 제목 오버레이 재사용
        return _overlay_title(raw, (text or "").strip(), out_jpg)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 오버레이 실패 → 스킵: {e}\n")
        return None


# ── 고수준 렌더 ──
def render(spec: dict, clips: list[str], out_mp4: str, workdir: str) -> dict:
    import time as _time
    t0 = _time.monotonic()

    def _lap(label: str):
        # 단계별 소요시간 — Actions 로그가 스텝 단위로 버퍼링돼 타임스탬프로는
        # 내부 병목을 알 수 없어(2026-07 관측) 직접 찍는다.
        print(f"  ⏱ {label}: 누적 {_time.monotonic() - t0:.0f}s", flush=True)

    os.makedirs(workdir, exist_ok=True)
    if not clips:
        raise RuntimeError("오디오 클립 없음(Freesound 실패) — ASMR 렌더 중단")
    target = float(spec.get("duration_min", 60)) * 60.0
    want_bed = max(target * 0.9, 60)  # 소스가 target 에 못 미치면 루프로 채움

    bed = build_bed(clips, os.path.join(workdir, "bed.wav"), target, workdir)
    _lap("앰비언트 베드(정규화+루프+loudnorm)")
    yt = (spec.get("platforms") or {}).get("youtube") or {}

    # 나레이션(선택): 여/남 보이스는 spec.narration_voice 로 결정
    voice_f = os.environ.get("ASMR_VOICE_FEMALE", "ko-KR-SunHiNeural")
    voice_m = os.environ.get("ASMR_VOICE_MALE", "ko-KR-InJoonNeural")
    voice = voice_m if (spec.get("narration_voice") == "male") else voice_f
    nar = synth_narration(spec.get("narration_text", ""), voice,
                          os.path.join(workdir, "nar.wav"), workdir)
    gain = float(os.environ.get("ASMR_NARRATION_GAIN", "0.35"))
    audio = mix_audio(bed, nar, os.path.join(workdir, "mix.m4a"), gain=gain)
    _lap("나레이션+믹스(AAC)")

    bg = ensure_background((spec.get("background") or {}).get("prompt", ""),
                           os.path.join(workdir, "bg.png"), workdir)
    _lap("배경 이미지(FLUX)")
    render_video(bg, audio, out_mp4)
    _lap(f"영상 인코딩({FPS}fps/{PRESET})")
    dur = probe_dur(out_mp4)
    size_mb = os.path.getsize(out_mp4) / 1e6
    print(f"✅ {out_mp4}  ({dur:.0f}s, {size_mb:.1f}MB, voice={'남' if voice==voice_m else '여'}, "
          f"나레이션={'있음' if nar else '없음'})")
    return {"out": out_mp4, "duration_sec": round(dur, 1), "size_mb": round(size_mb, 1)}


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="ASMR 렌더(테스트) — 클립 직접 지정")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--clip", action="append", default=[], help="오디오 클립(여러 번)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="_asmr_work")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    render(spec, args.clip, args.out, args.workdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
