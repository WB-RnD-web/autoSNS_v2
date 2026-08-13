#!/usr/bin/env python3
"""공용 낭독형 렌더러 — 사연(sayeon)/괴담(gwedam) 등 완결형 단편 오디오북.

소설(novel_render) 사상과 동일하되 ★시리즈/캐논 없음(매 회 완결). 배경은 이야기 전용 1장.

흐름:
  ① segments[].text → edge-tts 단일 내레이터 → mp3 → 44.1k wav → 길이 측정
  ② 세그먼트 + 간격(무음) concat → narration.m4a
  ③ 세그먼트 길이로 자막(ASS) 타이밍 산출 → 번인
  ④ 정적 배경(FLUX 이미지, 무키/실패 시 절차적) + 자막 번인 + 낭독 → 16:9 H.264/AAC/+faststart
  ⑤ 썸네일: FLUX 배경 + thumbnail_text 오버레이(소설 thumbnail 재사용)

배경음 없음(낭독만). 자막은 narration_full 을 segment 단위로.
"""
from __future__ import annotations
import asyncio
import os
import re
import shutil
import subprocess
import sys

import imagegen

W, H, FPS = 1920, 1080, 30

VOICE = os.environ.get("STORY_VOICE", "ko-KR-InJoonNeural")            # 차분한 라디오 낭독
VOICE_FALLBACK = os.environ.get("STORY_VOICE_FALLBACK", "ko-KR-HyunsuMultilingualNeural")
VO_RATE = os.environ.get("STORY_RATE", "-4%")                          # 사연/괴담은 살짝 느리게
VO_PITCH = os.environ.get("STORY_PITCH", "+0Hz")
SEG_GAP = float(os.environ.get("STORY_SEG_GAP", "0.32"))
LEAD_IN = float(os.environ.get("STORY_LEAD_IN", "0.6"))
TAIL = float(os.environ.get("STORY_TAIL", "1.8"))
FONT_SIZE = int(os.environ.get("STORY_FONT_SIZE", "56"))


def _bin(name):
    return shutil.which(name) or name


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def sh(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {' '.join(cmd) if isinstance(cmd, list) else cmd}\n"
                         f"{(e.stdout or '')[-800:]}\n{(e.stderr or '')[-1500:]}\n")
        raise


def probe_dur(path: str) -> float:
    if shutil.which("ffprobe"):
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


# ── 폰트(자막 번인) ──
def resolve_font(workdir: str) -> tuple[str | None, str]:
    cand = []
    ef, en = os.environ.get("STORY_FONT_FILE"), os.environ.get("STORY_FONT_NAME")
    if ef:
        cand.append((ef, en or "Sans"))
    cand += [
        ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "NanumGothic"),
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "NanumGothic"),
        (r"C:\Windows\Fonts\malgunbd.ttf", "Malgun Gothic"),
    ]
    for path, fam in cand:
        if path and os.path.exists(path):
            dst = os.path.join(workdir, "font" + (os.path.splitext(path)[1] or ".ttf"))
            try:
                shutil.copyfile(path, dst)
            except OSError:
                return None, fam
            return ".", fam
    return None, (en or "NanumGothic")


# ── ① TTS ──
async def _synth(text, voice, out_mp3):
    import edge_tts  # type: ignore
    await edge_tts.Communicate(text, voice, rate=VO_RATE, pitch=VO_PITCH).save(out_mp3)


def synth_segment(text: str, out_mp3: str) -> None:
    voices = [VOICE] + ([VOICE_FALLBACK] if VOICE_FALLBACK != VOICE else [])
    last = None
    for v in voices:
        try:
            asyncio.run(_synth(text, v, out_mp3))
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
                return
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or RuntimeError("TTS 합성 실패")


def synth_all(segments, workdir) -> list[float]:
    durs = []
    for i, seg in enumerate(segments):
        mp3 = os.path.join(workdir, f"seg_{i:03d}.mp3")
        wav = os.path.join(workdir, f"seg_{i:03d}.wav")
        synth_segment(seg["text"], mp3)
        sh([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
        d = probe_dur(wav)
        durs.append(d)
    print(f"  · TTS {len(segments)} segments 합성 완료(총 {sum(durs):.0f}s 낭독)")
    return durs


# ── ② 내레이션 concat ──
def build_narration(n, durs, workdir, out_m4a) -> None:
    gap = os.path.join(workdir, "gap.wav")
    if SEG_GAP > 0:
        sh([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{SEG_GAP:.3f}", gap])
    lines = []
    for i in range(n):
        lines.append(f"file 'seg_{i:03d}.wav'")
        if SEG_GAP > 0 and i < n - 1:
            lines.append("file 'gap.wav'")
    with open(os.path.join(workdir, "concat.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-c:a", "aac", "-b:a", "192k", "narration.m4a"], cwd=workdir)
    if out_m4a != os.path.join(workdir, "narration.m4a"):
        shutil.copyfile(os.path.join(workdir, "narration.m4a"), out_m4a)


# ── ③ 자막(ASS) ──
def _ass_time(t):
    if t < 0:
        t = 0
    cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_text(s):
    return (s or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N").strip()


def _srt_time(t):
    if t < 0:
        t = 0
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments, durs, path, key="text") -> str | None:
    """번인 자막과 ★같은 타이밍의 SRT — 유튜브 자막 트랙의 원본이 된다.

    ffmpeg 로 ASS→SRT 변환하면 `<font face=… size=…>` 태그가 딸려 나와 지저분해진다.
    타이밍 계산은 build_ass 와 동일하므로 여기서 바로 만든다.

    ★key 로 번역 자막도 같은 함수로 만든다: 루틴이 segments[i]["text_en"] 을 써주면
    key="text_en" 으로 부르면 된다. 타이밍은 한국어와 ★완전히 동일하므로 싱크가 어긋날
    수 없다(번역 API 로 SRT 를 통째로 옮길 때 생기던 개수 불일치 문제가 원천적으로 없다).
    해당 key 가 하나도 없으면 None — 호출측이 그 언어를 스킵한다.
    """
    if not any((seg.get(key) or "").strip() for seg in segments):
        return None
    lines, t = [], LEAD_IN
    for i, seg in enumerate(segments):
        d = durs[i]
        # 특정 세그먼트만 번역이 비면 한국어로 메운다(자막이 통째로 사라지는 것보다 낫다)
        text = (seg.get(key) or seg.get("text") or "").strip()
        lines.append(f"{i + 1}\n{_srt_time(t)} --> {_srt_time(t + d)}\n{text}\n")
        t += d + (SEG_GAP if i < len(segments) - 1 else 0)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def build_ass(segments, durs, font_family, path):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Story,{font_family},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,3,2,2,220,220,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    t = LEAD_IN
    for i, seg in enumerate(segments):
        d = durs[i]
        start, end = t, t + d
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Story,,0,0,0,,{_ass_text(seg['text'])}")
        t = end + (SEG_GAP if i < len(segments) - 1 else 0)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── ④ 배경 ──
def ensure_background(prompt: str, out_png: str, workdir: str) -> str:
    raw = imagegen.flux_image(prompt, os.path.join(workdir, "bg_raw.png"), 1344, 768)
    src = raw or _procedural_bg(os.path.join(workdir, "bg_proc.png"))
    sh([FFMPEG, "-y", "-i", src, "-vf",
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
        f"eq=brightness=-0.06:saturation=1.03,vignette=PI/5", "-frames:v", "1", out_png])
    return out_png


def _procedural_bg(out_png: str) -> str:
    sh([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x0d0b10:s={W}x{H}",
        "-frames:v", "1", "-vf", "vignette=PI/5,noise=alls=8:allf=t,format=rgb24", out_png])
    return out_png


# ── 영상 조립(정적 배경 + 자막 번인 + 낭독) ──
def render_video(bg_png: str, narration_m4a: str, ass_path: str, fontsdir: str | None,
                 out_mp4: str, total: float) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    wd = os.path.dirname(os.path.abspath(ass_path))
    ass_rel = os.path.basename(ass_path)
    sub = f"subtitles={ass_rel}" + (f":fontsdir={fontsdir}" if fontsdir else "")
    sh([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.abspath(bg_png),
        "-i", os.path.abspath(narration_m4a),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,{sub}",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}", "-movflags", "+faststart",
        os.path.abspath(out_mp4)], cwd=wd)
    return out_mp4


# ── ⑤ 썸네일(FLUX + 문구 오버레이) ──
def build_thumbnail(hook: str, text: str, out_jpg: str, workdir: str) -> str | None:
    if not (hook or "").strip():
        return None
    raw = imagegen.flux_image(hook + ", cinematic movie-poster illustration, dramatic lighting, "
                                     "atmospheric, highly detailed, no text, no letters, no watermark",
                              os.path.join(workdir, "thumb_raw.png"), 1344, 768)
    if not raw:
        return None
    try:
        from thumbnail import _overlay_title
        return _overlay_title(raw, (text or "").strip(), out_jpg)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 오버레이 실패 → 스킵: {e}\n")
        return None


# ── 고수준 렌더 ──
def render(spec: dict, out_mp4: str, workdir: str) -> dict:
    os.makedirs(workdir, exist_ok=True)
    segments = spec.get("segments") or []
    if not segments:
        raise RuntimeError("segments 없음")
    fontsdir, font_family = resolve_font(workdir)
    durs = synth_all(segments, workdir)
    total = LEAD_IN + sum(durs) + SEG_GAP * (len(segments) - 1) + TAIL
    narration = os.path.join(workdir, "narration.m4a")
    build_narration(len(segments), durs, workdir, narration)
    ass_path = os.path.join(workdir, "captions.ass")
    build_ass(segments, durs, font_family, ass_path)
    bg = ensure_background((spec.get("background") or {}).get("prompt", ""),
                           os.path.join(workdir, "bg.png"), workdir)
    render_video(bg, narration, ass_path, fontsdir, out_mp4, total)
    dur = probe_dur(out_mp4)
    size_mb = os.path.getsize(out_mp4) / 1e6
    print(f"✅ {out_mp4}  ({dur:.0f}s, {size_mb:.1f}MB, {len(segments)} segments)")
    return {"out": out_mp4, "duration_sec": round(dur, 1), "size_mb": round(size_mb, 1)}


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="낭독형 스토리 렌더(테스트)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="_story_work")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    render(spec, args.out, args.workdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
