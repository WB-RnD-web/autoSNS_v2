#!/usr/bin/env python3
"""ASMR 렌더러 — 정적 배경 1장 + Freesound 앰비언트(심리스 루프) + 낮은 나레이션 → 16:9 mp4.

소설(novel_render)과 사상 동일: 정적 이미지 + 오디오. 차이는 오디오가 낭독이 아니라
'테마 사운드를 ★3~4시간 이음새 없이 루프'한다는 점.

흐름:
  ① 클립들(mp3) → 48k 스테레오 wav 정규화
  ② 레이어별 '루프 단위' 생성(베드 12분 / 트리거 9분 / 배경음악 7분) — 전체 길이를 만들지 않는다
  ③ 최종 믹스에서 각 단위를 `-stream_loop -1` 로 무한 반복 + 겹쳐서 목표 길이에서 끊는다
  ④ 정적 이미지 + 오디오 → H.264/yuv420p/AAC/+faststart (정지영상이라 파일 아주 작음)
  ⑤ 썸네일: FLUX 배경 + 문구 오버레이(소설 thumbnail 재사용)

배경음/자막 없음(앰비언트 자체가 콘텐츠). 잘 때 듣는 용도 → 차분한 라우드니스(-20 LUFS).
"""
from __future__ import annotations
import os
import random
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
def build_unit(clips: list[str], out_wav: str, unit_sec: float, workdir: str,
               tag: str = "bed", loudness: int = -20) -> str:
    """클립들 → 크로스페이드 → ★배수로 늘려 unit_sec 짜리 '루프 단위'를 만든다.

    ★왜 전체 길이를 안 만드는가:
      3~4시간을 통째로 wav 로 만들면 한 레이어만 2.4GB 다(48k 스테레오 16bit).
      대신 12분짜리 단위 하나만 만들고, 최종 믹스에서 `-stream_loop -1` 로 무한 반복시킨다.
      디스크도 아끼고, 예전 `reps=min(...,60)` 상한 때문에 긴 영상이 조용해지던 버그도 사라진다.

    ★왜 배수(doubling)인가:
      예전엔 `_xfade_concat([base]*reps)` 로 ffmpeg 입력을 reps 개 넘겼다. 60개면 필터 그래프가
      60입력이라 무겁다. 2배씩 늘리면 입력 2개짜리 호출 log2(n)번이면 끝난다.
    """
    norm = [_norm_clip(c, os.path.join(workdir, f"{tag}_n{i:02d}.wav")) for i, c in enumerate(clips)]
    cur = _xfade_concat(norm, os.path.join(workdir, f"{tag}_base.wav"))
    base_dur = probe_dur(cur)
    if base_dur <= 0:
        raise RuntimeError(f"{tag} base 길이 측정 실패")
    step = 0
    while probe_dur(cur) < unit_sec - XFADE and step < 12:
        step += 1
        nxt = os.path.join(workdir, f"{tag}_x{step}.wav")
        _xfade_concat([cur, cur], nxt)
        if cur != os.path.join(workdir, f"{tag}_base.wav"):
            try:
                os.remove(cur)                    # 배수마다 2배씩 커진다 — 직전 것은 지운다
            except OSError:
                pass
        cur = nxt
    have = probe_dur(cur)
    unit = min(unit_sec, have)
    # 루프 이음새(단위 끝 → 단위 처음)의 클릭 방지용 아주 짧은 페이드. 앰비언트라 안 들린다.
    sh([FFMPEG, "-y", "-i", cur, "-af",
        f"atrim=0:{unit:.2f},afade=t=in:d=0.4,afade=t=out:st={max(0.0, unit - 0.4):.2f}:d=0.4,"
        f"loudnorm=I={loudness}:TP=-2:LRA=11",
        "-ar", "48000", "-ac", "2", out_wav])
    for p in [cur, os.path.join(workdir, f"{tag}_base.wav"), *norm]:
        if p != out_wav:
            try:
                os.remove(p)                      # 단위만 남기고 중간 wav 는 버린다
            except OSError:
                pass
    print(f"  · {tag} 루프 단위: 소스 {base_dur:.0f}s → 배수 {step}회 → {probe_dur(out_wav):.0f}s")
    return out_wav


# ── ②-b ★트리거 트랙(귀르가즘용 단발음 흩뿌리기) ──
# 왜 별도 트랙인가:
#   왁뿌볼(왁스 깨짐)·뽁뽁이·크런치 같은 트리거음은 ★1~3초짜리다. 앰비언트 베드에 섞으면
#   크로스페이드 루프가 뭉개지고, 그렇다고 20초 필터로 거르면 애초에 안 잡힌다.
#   그래서 '짧은 클립 + 무음 간격'을 번갈아 이어붙인 트랙을 따로 만들어 베드 위에 얹는다.
#   이게 실제로 잘 되는 트리거 ASMR 의 구조다 — 바탕은 조용하고, 소리는 띄엄띄엄 온다.
TRIG_GAP_MIN = float(os.environ.get("ASMR_TRIGGER_GAP_MIN", "3"))
TRIG_GAP_MAX = float(os.environ.get("ASMR_TRIGGER_GAP_MAX", "11"))


def build_triggers(clips: list[str], out_wav: str, target_sec: float, workdir: str,
                   seed: str = "", gap_min: float = TRIG_GAP_MIN,
                   gap_max: float = TRIG_GAP_MAX) -> str | None:
    """짧은 트리거 클립을 target_sec 동안 불규칙 간격으로 흩뿌린 트랙.

    seed 를 테마 이름으로 고정해 같은 테마면 같은 배치가 나오게 한다(재렌더 재현성).
    """
    clips = [c for c in clips if c and os.path.exists(c)]
    if not clips or target_sec <= 0:
        return None
    rnd = random.Random(seed or "asmr")

    norm, durs = [], []
    for i, c in enumerate(clips):
        p = _norm_clip(c, os.path.join(workdir, f"t{i:02d}.wav"))
        d = probe_dur(p)
        if d > 0.15:                       # 못 쓸 만큼 짧은 건 버린다
            norm.append(p)
            durs.append(d)
    if not norm:
        return None

    # 무음은 0.5초 단위로 반올림해 파일 수를 줄인다(같은 길이는 재사용)
    sil: dict[float, str] = {}

    def _silence(sec: float) -> str:
        key = max(0.5, round(sec * 2) / 2)
        if key not in sil:
            p = os.path.join(workdir, f"sil_{int(key * 10):04d}.wav")
            sh([FFMPEG, "-y", "-f", "lavfi", "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", f"{key:.2f}", p])
            sil[key] = p
        return sil[key]

    order, t, n = [], 0.0, 0
    while t < target_sec and n < 4000:     # 폭주 가드
        g = rnd.uniform(gap_min, gap_max)
        order.append(_silence(g))
        t += max(0.5, round(g * 2) / 2)
        k = rnd.randrange(len(norm))
        order.append(norm[k])
        t += durs[k]
        n += 1

    lst = os.path.join(workdir, "trig_concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in order:
            f.write(f"file '{os.path.abspath(p)}'\n")
    raw = os.path.join(workdir, "trig_raw.wav")
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", "-ac", "2", raw])
    # 이것도 '루프 단위'다(최종 믹스에서 무한 반복된다) → 이음새용 짧은 페이드만.
    sh([FFMPEG, "-y", "-i", raw, "-af",
        f"atrim=0:{target_sec:.2f},afade=t=in:d=0.4,"
        f"afade=t=out:st={max(0.0, target_sec - 0.4):.2f}:d=0.4,"
        f"loudnorm=I=-18:TP=-2:LRA=11", "-ar", "48000", "-ac", "2", out_wav])
    # 중간 산출물 정리 — raw 는 결과와 같은 크기고, 무음 조각도 쌓이면 100MB 단위가 된다.
    for p in [raw, *sil.values()]:
        try:
            os.remove(p)
        except OSError:
            pass
    print(f"  · 트리거 트랙: 소재 {len(norm)}종 × {n}회 배치 "
          f"(간격 {gap_min:.0f}~{gap_max:.0f}s) → {probe_dur(out_wav):.0f}s")
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


def mix_audio(layers: list[dict], out_m4a: str, total_sec: float,
              nar_wav: str | None = None, nar_gain: float = 0.35,
              nar_delay: float = 3.0) -> str:
    """루프 단위들을 ★무한 반복시켜 겹치고 total_sec 에서 끊는다 → AAC.

    layers: [{"path": wav, "gain": float}] — 각각 `-stream_loop -1` 로 무한 반복된다.
    단위 길이를 레이어마다 다르게 두면(베드 12분 / 트리거 9분 / 음악 7분) 조합 주기가
    아주 길어져서, 3~4시간을 들어도 "아까 그 패턴"이 잘 안 느껴진다.
    """
    use = [l for l in layers if l.get("path") and l.get("gain", 0) > 0]
    if not use:
        raise RuntimeError("믹스할 오디오 레이어가 없음")
    ins, fc, labels = [], [], []
    for i, l in enumerate(use):
        ins += ["-stream_loop", "-1", "-i", l["path"]]
        fc.append(f"[{i}:a]volume={l['gain']}[l{i}]")
        labels.append(f"[l{i}]")
    if nar_wav and nar_gain > 0:
        i = len(use)
        ins += ["-i", nar_wav]                      # ★나레이션은 반복하지 않는다(도입부 1회)
        fc.append(f"[{i}:a]adelay={int(nar_delay * 1000)}|{int(nar_delay * 1000)},"
                  f"volume={nar_gain}[l{i}]")
        labels.append(f"[l{i}]")
    st = max(0.0, total_sec - 8)
    if len(labels) == 1:
        fc.append(f"{labels[0]}afade=t=in:d=3,afade=t=out:st={st:.2f}:d=8[a]")
    else:
        fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                  f"afade=t=in:d=3,afade=t=out:st={st:.2f}:d=8[a]")
    sh([FFMPEG, "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[a]",
        "-t", f"{total_sec:.2f}", "-c:a", "aac", "-b:a", "192k", out_m4a])
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
        # ★ASMR 은 무텍스트가 관행이다 — 2026-08-28 상위 썸네일 6개 중 5개가 문구 없이
        #   '만지는 손·물건 클로즈업'만 있었다. 제목이 이미 다 설명하는 장르다.
        #   되돌리려면 ASMR_THUMB_STYLE=bottom.
        return _overlay_title(raw, (text or "").strip(), out_jpg,
                              style=os.environ.get("ASMR_THUMB_STYLE", "none"))
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 오버레이 실패 → 스킵: {e}\n")
        return None


# ── 고수준 렌더 ──
# 모드별 믹스 밸런스 — 수면용은 베드가 주인공, 트리거용은 트리거가 주인공.
#   music = 배경 피아노(선택). 소리를 가리면 안 되므로 어느 모드에서도 아주 낮게 깐다.
MODE_GAINS = {
    "sleep":   {"bed": 1.00, "trig": 0.00, "music": 0.22, "nar": 0.35},
    "mixed":   {"bed": 0.85, "trig": 0.60, "music": 0.20, "nar": 0.30},
    "trigger": {"bed": 0.35, "trig": 1.00, "music": 0.14, "nar": 0.00},
}

# ★길이 — 매 회 3~4시간 사이에서 랜덤. 유튜브 '장시간 ASMR' 은 길수록 잘 붙잡는다.
#   theme_id+date 를 seed 로 써서 같은 스펙을 다시 렌더해도 같은 길이가 나온다.
DUR_MIN_SEC = float(os.environ.get("ASMR_DUR_MIN_SEC", "10800"))   # 3시간
DUR_MAX_SEC = float(os.environ.get("ASMR_DUR_MAX_SEC", "14400"))   # 4시간
# 루프 단위 길이(초). 레이어마다 어긋나게 둬서 조합 주기를 길게 만든다.
UNIT_BED = float(os.environ.get("ASMR_UNIT_BED", "720"))     # 12분
UNIT_TRIG = float(os.environ.get("ASMR_UNIT_TRIG", "540"))   # 9분
UNIT_MUSIC = float(os.environ.get("ASMR_UNIT_MUSIC", "420"))  # 7분


def _hms(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600}시간 {s % 3600 // 60}분 {s % 60}초"


def pick_duration(spec: dict) -> float:
    """스펙이 정한 길이 > 레거시 duration_min > ★3~4시간 랜덤."""
    if spec.get("duration_sec"):
        return float(spec["duration_sec"])
    if spec.get("duration_min"):
        return float(spec["duration_min"]) * 60.0
    seed = f"{spec.get('theme_id', '')}|{spec.get('date', '')}"
    return round(random.Random(seed).uniform(DUR_MIN_SEC, DUR_MAX_SEC))


def render(spec: dict, clips: list[str], out_mp4: str, workdir: str,
           trigger_clips: list[str] | None = None,
           music_clips: list[str] | None = None) -> dict:
    import time as _time
    t0 = _time.monotonic()

    def _lap(label: str):
        # 단계별 소요시간 — Actions 로그가 스텝 단위로 버퍼링돼 타임스탬프로는
        # 내부 병목을 알 수 없어(2026-07 관측) 직접 찍는다.
        print(f"  ⏱ {label}: 누적 {_time.monotonic() - t0:.0f}s", flush=True)

    os.makedirs(workdir, exist_ok=True)
    if not clips:
        raise RuntimeError("오디오 클립 없음(Freesound 실패) — ASMR 렌더 중단")
    target = pick_duration(spec)
    mode = str(spec.get("mode") or "sleep").strip().lower()
    g = MODE_GAINS.get(mode) or MODE_GAINS["sleep"]
    print(f"  · 모드 {mode} · ★길이 {_hms(target)} ({target:.0f}s)")
    print(f"    믹스 베드 {g['bed']} / 트리거 {g['trig']} / 음악 {g['music']} / 나레이션 {g['nar']}")

    layers = [{"path": build_unit(clips, os.path.join(workdir, "bed.wav"),
                                  UNIT_BED, workdir, "bed"), "gain": g["bed"]}]
    _lap("앰비언트 루프 단위")

    if g["trig"] > 0 and trigger_clips:
        layers.append({"path": build_triggers(trigger_clips, os.path.join(workdir, "trig.wav"),
                                              UNIT_TRIG, workdir,
                                              seed=str(spec.get("theme_id") or spec.get("date") or "")),
                       "gain": g["trig"]})
        _lap("트리거 루프 단위")
    elif g["trig"] > 0:
        print("  ⚠️ 트리거 모드인데 트리거 소재가 없다 — 베드만으로 진행")

    if g["music"] > 0 and music_clips:
        layers.append({"path": build_unit(music_clips, os.path.join(workdir, "music.wav"),
                                          UNIT_MUSIC, workdir, "music", loudness=-26),
                       "gain": g["music"]})
        _lap("배경 음악 루프 단위")
    yt = (spec.get("platforms") or {}).get("youtube") or {}

    # 나레이션(선택): 여/남 보이스는 spec.narration_voice 로 결정
    voice_f = os.environ.get("ASMR_VOICE_FEMALE", "ko-KR-SunHiNeural")
    voice_m = os.environ.get("ASMR_VOICE_MALE", "ko-KR-InJoonNeural")
    voice = voice_m if (spec.get("narration_voice") == "male") else voice_f
    nar = (synth_narration(spec.get("narration_text", ""), voice,
                           os.path.join(workdir, "nar.wav"), workdir)
           if g["nar"] > 0 else None)
    gain = float(os.environ.get("ASMR_NARRATION_GAIN", str(g["nar"])))
    audio = mix_audio(layers, os.path.join(workdir, "mix.m4a"), target,
                      nar_wav=nar, nar_gain=gain)
    _lap(f"믹스({len(layers)}레이어 무한루프 → {_hms(target)})")

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
