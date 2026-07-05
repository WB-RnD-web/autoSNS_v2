#!/usr/bin/env python3
"""소설 render-spec → 16:9 오디오소설 MP4 (신규 렌더러, 무료 스택).

쇼츠의 9:16 모션그래픽 렌더러(motion_short.py)와 ★완전히 별개다.

흐름:
  ① segments[].text → edge-tts 단일 내레이터 합성(세그먼트별) → 길이 측정
  ② 세그먼트 오디오 + 간격(무음) concat → 단일 내레이션 트랙(narration.m4a)
  ③ 세그먼트 길이로 자막(ASS) 타이밍 산출 → 번인
  ④ 정적 배경 1장(series_id 캐싱) + 켄번즈(회차별 크롭/줌 변형) + 자막 → H.264/yuv420p/AAC/+faststart
배경음은 없음(낭독만). 배경 이미지는 series 당 1회 생성·캐싱, 회차마다 줌/팬만 다르게(과제 7).

재활용: edge-tts(voice.py 와 동일 엔진), ffprobe 길이 측정 패턴(motion_short).
신규: 자막 번인(ASS/libass), 정적 배경 + zoompan 켄번즈, 16:9.

사용:
  python pipeline/novel_render.py --spec output/novel/<sid>/ep1_<date>.json \
      --out output/renders/<sid>_ep1.mp4
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys

import novel_spec

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1920, 1080, 30

# ── 단일 내레이터(낭독) ─ 전부 환경변수로 교체 가능 ──
NARRATOR = os.environ.get("NOVEL_VOICE", "ko-KR-HyunsuMultilingualNeural")
NARRATOR_FALLBACK = os.environ.get("NOVEL_VOICE_FALLBACK", "ko-KR-InJoonNeural")
VO_RATE = os.environ.get("NOVEL_RATE", "-3%")     # 낭독은 살짝 느리고 차분하게
VO_PITCH = os.environ.get("NOVEL_PITCH", "+0Hz")
SEG_GAP = float(os.environ.get("NOVEL_SEG_GAP", "0.28"))   # 세그먼트 사이 무음(자막 호흡)
LEAD_IN = float(os.environ.get("NOVEL_LEAD_IN", "0.6"))    # 시작 전 배경만
TAIL = float(os.environ.get("NOVEL_TAIL", "1.4"))          # 끝난 뒤 배경만

# ── 장르별 다크 배경 팔레트(잠들기 전 톤, 무료 절차적 생성용) ──
GENRE_BG = {
    "로맨스":   ("0x2a0e1a", "0x0a0306"),
    "잔혹동화": ("0x10201c", "0x03100b"),
    "판타지":   ("0x101a33", "0x05060f"),
    "추리":     ("0x141a1f", "0x05080b"),
    "공포":     ("0x1a0a0a", "0x020202"),
    "_default": ("0x141018", "0x050307"),
}


# ── ffmpeg/ffprobe 바이너리 해석(로컬 폴백 포함) ──
def _bin(name: str) -> str:
    p = shutil.which(name)
    if p:
        return p
    local = rf"C:\Users\zxczx\tools\ffmpeg-8.1.1-essentials_build\bin\{name}.exe"
    return local if os.path.exists(local) else name


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def sh(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {cmd if isinstance(cmd, str) else ' '.join(cmd)}\n"
                         f"{(e.stdout or '')[-1200:]}\n{(e.stderr or '')[-1800:]}\n")
        raise


def probe_dur(path: str) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ── 폰트 해석(자막 번인용) ──
def resolve_font(workdir: str) -> tuple[str | None, str]:
    """(fontsdir, font_family) 반환. 폰트 파일을 workdir 로 복사해 상대경로로 참조
    (Windows subtitles 필터의 경로 이스케이프 문제 회피)."""
    cand: list[tuple[str, str]] = []
    ef, en = os.environ.get("NOVEL_FONT_FILE"), os.environ.get("NOVEL_FONT_NAME")
    if ef:
        cand.append((ef, en or "Sans"))
    cand += [
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "NanumGothic"),
        ("/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf", "NanumBarunGothic"),
        (r"C:\Windows\Fonts\malgun.ttf", "Malgun Gothic"),
        (r"C:\Windows\Fonts\malgunsl.ttf", "Malgun Gothic"),
    ]
    for path, fam in cand:
        if path and os.path.exists(path):
            ext = os.path.splitext(path)[1] or ".ttf"
            dst = os.path.join(workdir, f"font{ext}")
            try:
                shutil.copyfile(path, dst)
            except OSError:
                return None, fam
            return ".", fam       # cwd=workdir 로 실행하므로 상대 "."
    return None, (en or "NanumGothic")


# ── ① TTS (세그먼트별, 단일 내레이터) ──
async def _synth(text: str, voice: str, out_mp3: str) -> None:
    import edge_tts  # type: ignore
    await edge_tts.Communicate(text, voice, rate=VO_RATE, pitch=VO_PITCH).save(out_mp3)


def synth_segment(text: str, out_mp3: str) -> None:
    """기본 보이스 → 실패 시 폴백 보이스 1회."""
    voices = [NARRATOR] + ([NARRATOR_FALLBACK] if NARRATOR_FALLBACK != NARRATOR else [])
    last: Exception | None = None
    for v in voices:
        try:
            asyncio.run(_synth(text, v, out_mp3))
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
                return
            last = RuntimeError("빈 음성 파일")
        except Exception as e:  # noqa: BLE001
            last = e
        if os.path.exists(out_mp3) and os.path.getsize(out_mp3) == 0:
            os.remove(out_mp3)
    raise last or RuntimeError("TTS 합성 실패")


def synth_all(segments: list[dict], workdir: str) -> list[float]:
    """각 세그먼트를 mp3 합성 → 44.1k 스테레오 wav 변환 → 길이 측정. 길이 리스트 반환."""
    durs: list[float] = []
    for i, seg in enumerate(segments):
        mp3 = os.path.join(workdir, f"seg_{i:03d}.mp3")
        wav = os.path.join(workdir, f"seg_{i:03d}.wav")
        synth_segment(seg["text"], mp3)
        sh([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
        d = probe_dur(wav)
        durs.append(d)
        print(f"  · seg{i:03d}  {d:5.1f}s  {seg['text'][:28]}…")
    return durs


# ── ② 오디오 concat (세그먼트 + 간격 무음) ──
def build_narration(n: int, durs: list[float], workdir: str, out_m4a: str) -> None:
    # 간격 무음 wav 1개 생성(재사용)
    gap_wav = os.path.join(workdir, "gap.wav")
    if SEG_GAP > 0:
        sh([FFMPEG, "-y", "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{SEG_GAP:.3f}", gap_wav])
    lines = []
    for i in range(n):
        lines.append(f"file 'seg_{i:03d}.wav'")
        if SEG_GAP > 0 and i < n - 1:
            lines.append("file 'gap.wav'")
    listf = os.path.join(workdir, "concat.txt")
    with open(listf, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    # concat demuxer(같은 포맷) → AAC
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-c:a", "aac", "-b:a", "192k", "narration.m4a"], cwd=workdir)
    if out_m4a != os.path.join(workdir, "narration.m4a"):
        shutil.copyfile(os.path.join(workdir, "narration.m4a"), out_m4a)


# ── ③ 자막(ASS) 생성 ──
def _ass_time(t: float) -> str:
    if t < 0:
        t = 0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_text(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N").strip()


def build_ass(segments: list[dict], durs: list[float], font_family: str, path: str) -> None:
    """세그먼트 길이로 자막 타이밍 산출(LEAD_IN 오프셋, 간격 반영)."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Novel,{font_family},54,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,2,2,260,260,96,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    t = LEAD_IN
    for i, seg in enumerate(segments):
        d = durs[i]
        start, end = t, t + d
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Novel,,0,0,0,,{_ass_text(seg['text'])}")
        t = end + (SEG_GAP if i < len(segments) - 1 else 0.0)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── 썸네일(무료 ffmpeg 텍스트 합성) — thumbnail_text 큰 글자, 크레딧 0 ──
THUMB_W, THUMB_H = 1280, 720


def _thumb_ass(text: str, font_family: str, path: str) -> None:
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {THUMB_W}
PlayResY: {THUMB_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Thumb,{font_family},108,&H00FFFFFF,&H000000FF,&H00101018,&H00000000,1,0,0,0,100,100,2,0,1,8,4,5,120,120,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:10.00,Thumb,,0,0,0,,{_ass_text(text)}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(head)


# ── (선택) NVIDIA FLUX.2 klein-4b 장면 이미지 — 있으면 썸네일 베이스로 ──
def _extract_img_b64(body) -> str | None:
    """응답에서 base64 이미지 추출(모델별 응답 키 편차 대비 방어적)."""
    def clean(s):
        return s.split(",", 1)[1] if isinstance(s, str) and s.startswith("data:") else s
    cands = []
    try:
        art = body["artifacts"][0]
        cands += [art.get("b64_json"), art.get("base64"), art.get("image")]
    except Exception:  # noqa: BLE001
        pass
    for k in ("image", "b64_json"):
        if isinstance(body, dict) and isinstance(body.get(k), str):
            cands.append(body[k])
    try:
        cands.append(body["data"][0].get("b64_json"))
    except Exception:  # noqa: BLE001
        pass
    for c in cands:
        if isinstance(c, str) and len(c) > 100:
            return clean(c)
    return None


def flux_image(prompt: str, out_png: str, w: int = 1344, h: int = 768) -> str | None:
    """NVIDIA_API_KEY 있으면 FLUX.2 klein-4b(호스팅·Apache-2.0 상업OK)로 장면 이미지 생성.
    ★무키/오프/4xx/형식불일치 → None(무료 폴백). 429·5xx·타임아웃·네트워크는 짧게 재시도.
    NOVEL_THUMB_FLUX=0 으로 끌 수 있음. (모델/타임아웃/재시도는 env 로 조정 가능)"""
    if os.environ.get("NOVEL_THUMB_FLUX", "1") != "1":
        return None
    key = os.environ.get("NVIDIA_API_KEY")
    if not key or not (prompt or "").strip():
        return None
    import urllib.request
    import urllib.error
    import base64 as _b64
    import time as _time
    url = os.environ.get("NOVEL_FLUX_URL",
                         "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b")
    payload = json.dumps({"prompt": prompt[:9000], "width": w, "height": h,
                          "seed": int(os.environ.get("NOVEL_FLUX_SEED", "0")), "steps": 4}).encode()
    timeout = int(os.environ.get("NOVEL_FLUX_TIMEOUT", "150"))
    retries = int(os.environ.get("NOVEL_FLUX_RETRIES", "2"))
    for attempt in range(1, retries + 2):
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "curl/8.4.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:           # 혼잡/서버 → 재시도
                sys.stderr.write(f"[warn] FLUX {e.code}(혼잡/서버) {attempt}/{retries + 1} — 재시도\n")
                _time.sleep(min(2 ** attempt, 20)); continue
            body_txt = ""
            try:
                body_txt = (e.read() or b"")[:300].decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            sys.stderr.write(f"[warn] FLUX {e.code} 요청오류 → 무료 폴백: {body_txt}\n")
            return None                                  # 400/404/422 → 재시도 무의미
        except Exception as e:  # noqa: BLE001               # 타임아웃/네트워크 → 재시도
            sys.stderr.write(f"[warn] FLUX 네트워크/타임아웃 {attempt}/{retries + 1} → {e}\n")
            _time.sleep(min(2 ** attempt, 20)); continue
        b64 = _extract_img_b64(data)
        if not b64:
            keys = list(data.keys()) if isinstance(data, dict) else type(data)
            sys.stderr.write(f"[warn] FLUX 200인데 이미지 필드 못 찾음 → 폴백. keys={keys}\n")
            return None
        try:
            with open(out_png, "wb") as f:
                f.write(_b64.b64decode(b64))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] FLUX 디코드 실패 → 폴백: {e}\n")
            return None
        print(f"  · FLUX(klein-4b) 장면 이미지 생성 OK: {os.path.basename(out_png)}")
        return out_png
    sys.stderr.write("[warn] FLUX 재시도 소진(혼잡) → 무료 폴백\n")
    return None


def build_thumbnail(spec: dict, bg_png: str, workdir: str, out_thumb: str,
                    fontsdir: str | None, font_family: str) -> str | None:
    """1280x720 썸네일(배경 어둡게 + thumbnail_text 큰 글자). 텍스트 없으면 None.
    호출부에서 예외를 무시하므로, 실패해도 업로드 파이프라인은 진행된다."""
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    text = (yt.get("thumbnail_text") or spec.get("hook_line")
            or spec.get("series_title") or "").strip()
    if not text:
        return None
    # 썸네일 베이스: FLUX 장면 생성 시도 → 실패 시 series 배경.
    #   ★회차별 장면 우선: thumbnail_prompt/thumbnail_hook(루틴이 회차마다 써주는 필드)이 있으면 그걸 쓴다.
    #   없을 때만 series 공통 background.prompt 로 폴백(그렇지 않으면 회차 썸네일이 다 똑같아짐).
    scene = (yt.get("thumbnail_prompt")
             or yt.get("thumbnail_hook")
             or spec.get("thumbnail_hook")
             or (spec.get("background") or {}).get("prompt") or "").strip()
    base = None
    if scene:
        scene_full = scene + (", cinematic movie-poster illustration, dramatic lighting, "
                              "atmospheric, highly detailed, no text, no watermark")
        base = flux_image(scene_full, os.path.join(workdir, "thumb_flux.png"), 1344, 768)
    base = base or bg_png       # ★FLUX 실패/무키 → series 배경으로 폴백
    _thumb_ass(text, font_family, os.path.join(workdir, "thumb.ass"))
    sub = "subtitles=thumb.ass" + (f":fontsdir={fontsdir}" if fontsdir else "")
    # FLUX 장면이면 덜 어둡게(장면 살리기), 절차적 배경이면 더 어둡게(글자 대비)
    dark = "-0.10" if base != bg_png else "-0.15"
    vf = (f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=increase,"
          f"crop={THUMB_W}:{THUMB_H},setsar=1,eq=brightness={dark}:saturation=1.12,"
          f"vignette=PI/4,{sub}")
    sh([FFMPEG, "-y", "-i", os.path.abspath(base), "-vf", vf,
        "-frames:v", "1", "-q:v", "2", "thumb.jpg"], cwd=workdir)
    made = os.path.join(workdir, "thumb.jpg")
    out_abs = os.path.abspath(out_thumb)
    if out_abs != os.path.abspath(made):
        shutil.copyfile(made, out_abs)
    print(f"  · 썸네일 생성: {os.path.basename(out_abs)}  ({text[:20]}…)")
    return out_abs


# ── ④ 배경(series 캐싱 + 정규화) ──
def _normalize_to_169(src: str, out_png: str) -> None:
    sh([FFMPEG, "-y", "-i", src, "-vf",
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
        "-frames:v", "1", out_png])


def _gen_procedural(genre: str, out_png: str) -> None:
    c0, c1 = GENRE_BG.get(genre, GENRE_BG["_default"])
    # 1순위: 세로 그라데이션 + 비네팅 + 미세 노이즈
    grad = (f"gradients=s={W}x{H}:c0={c0}:c1={c1}:type=linear:nb_colors=2:"
            f"x0=0:y0=0:x1=0:y1={H}:duration=1:speed=0")
    try:
        sh([FFMPEG, "-y", "-f", "lavfi", "-i", grad, "-frames:v", "1",
            "-vf", "vignette=PI/5,noise=alls=8:allf=t,format=rgb24", out_png])
        return
    except subprocess.CalledProcessError:
        pass
    # 폴백: 단색 + 비네팅 + 노이즈
    sh([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c={c0}:s={W}x{H}",
        "-frames:v", "1", "-vf", "vignette=PI/5,noise=alls=10:allf=t,format=rgb24", out_png])


def _gemini_bg(prompt: str, out_png: str, workdir: str) -> bool:
    """(선택·유료) Gemini 이미지 백엔드. 성공 시 True. 키 없으면 False."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False
    try:
        from google import genai  # type: ignore
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
        client = genai.Client(api_key=key)
        full = f"{prompt}\n\n16:9 cinematic horizontal wide shot, no text, no watermark, atmospheric, dark mood."
        resp = client.models.generate_content(model=model, contents=[full])
        for cand in (resp.candidates or []):
            for part in (cand.content.parts if getattr(cand, "content", None) else []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    raw = os.path.join(workdir, "bg_raw.png")
                    with open(raw, "wb") as f:
                        f.write(inline.data)
                    _normalize_to_169(raw, out_png)
                    return True
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] Gemini 배경 생성 실패 → 절차적 배경 사용: {e}\n")
    return False


def _flux_bg(prompt: str, out_png: str, workdir: str) -> bool:
    """FLUX.2 klein-4b(무료 호스팅)로 시리즈 배경 생성 → 1920x1080 정규화.
    자막 가독성을 위해 살짝 어둡게 + 비네팅(10분 내내 깔리는 배경이라 차분하게)."""
    raw = flux_image(prompt + ", cinematic wide establishing shot, atmospheric, "
                              "highly detailed, no text, no watermark",
                     os.path.join(workdir, "bg_flux_raw.png"), 1344, 768)
    if not raw:
        return False
    try:
        sh([FFMPEG, "-y", "-i", raw, "-vf",
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
            f"eq=brightness=-0.08:saturation=1.05,vignette=PI/5",
            "-frames:v", "1", out_png])
        return os.path.exists(out_png) and os.path.getsize(out_png) > 0
    except subprocess.CalledProcessError:
        return False


def ensure_background(spec: dict, cache_dir: str, workdir: str) -> str:
    """series_id 로 캐싱된 1920x1080 기본 배경 경로 반환(없으면 생성).
    우선순위: ★FLUX(klein-4b·무료) → Gemini(유료·키 있으면) → 절차적(무료 최후 폴백).
    절차적 폴백으로 만들어진 시리즈는 marker 를 남겨, 다음 회차에서 FLUX 업그레이드를 재시도한다."""
    os.makedirs(cache_dir, exist_ok=True)
    sid = spec["series_id"]
    cache = os.path.join(cache_dir, f"{sid}.png")
    marker = cache + ".procedural"      # '절차적 폴백이었음' 표시(업그레이드 재시도용)
    prompt = (spec.get("background") or {}).get("prompt", "")
    backend = os.environ.get("NOVEL_BG_BACKEND", "auto").lower()  # auto|flux|gemini|procedural

    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        if os.path.exists(marker) and backend in ("auto", "flux") and prompt:
            # 지난 회차에 절차적으로 폴백했던 시리즈 → FLUX 업그레이드 재시도
            if _flux_bg(prompt, cache, workdir):
                os.remove(marker)
                print("  · 배경 업그레이드: 절차적 → FLUX 장면(시리즈 캐시 교체)")
                return cache
        print(f"  · 배경 캐시 재사용: {cache}")
        return cache

    made = False
    if backend in ("auto", "flux") and prompt:
        made = _flux_bg(prompt, cache, workdir)
        if made:
            print("  · FLUX(klein-4b) 시리즈 배경 생성 ✅")
    if not made and backend in ("auto", "gemini") and prompt:
        made = _gemini_bg(prompt, cache, workdir)
    if not made:
        print(f"  · 절차적 배경 생성(장르={spec.get('genre','?')}) — 다음 회차에 FLUX 재시도")
        _gen_procedural(spec.get("genre", ""), cache)
        with open(marker, "w") as f:
            f.write("procedural")
    return cache


# ── 켄번즈(회차별 변형) zoompan 표현식 ──
def kenburns_filter(total_frames: int, episode_no: int) -> str:
    n = max(1, total_frames)
    mode = (max(1, episode_no) - 1) % 4
    sup = f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},setsar=1"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if mode == 0:      # 줌인, 중앙
        z, x, y = f"1.0+0.10*on/{n}", cx, cy
    elif mode == 1:    # 줌아웃, 중앙
        z, x, y = f"1.10-0.10*on/{n}", cx, cy
    elif mode == 2:    # 줌인 + 좌→우 팬
        z, x, y = f"1.0+0.08*on/{n}", f"(iw-iw/zoom)*on/{n}", cy
    else:              # 줌인 + 상→하 팬
        z, x, y = f"1.0+0.08*on/{n}", cx, f"(ih-ih/zoom)*on/{n}"
    zp = (f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}")
    return f"{sup},{zp},format=yuv420p"


# ── 최종 합성 ──
def build_video(bg_png: str, narration: str, ass_rel: str, total: float,
                episode_no: int, fontsdir: str | None, out_mp4: str, workdir: str) -> None:
    total_frames = int(round(total * FPS))
    lead_ms = int(round(LEAD_IN * 1000))
    sub = f"subtitles={ass_rel}" + (f":fontsdir={fontsdir}" if fontsdir else "")
    vf = f"[0:v]{kenburns_filter(total_frames, episode_no)},{sub}[v]"
    af = f"[1:a]adelay={lead_ms}:all=1,apad[a]"
    fc = f"{vf};{af}"
    out_abs = os.path.abspath(out_mp4)
    os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
    sh([FFMPEG, "-y", "-loop", "1", "-i", os.path.abspath(bg_png),
        "-i", os.path.abspath(narration),
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
        "-t", f"{total:.3f}", "-r", str(FPS),
        "-c:v", "libx264", "-preset", os.environ.get("NOVEL_X264_PRESET", "medium"),
        "-tune", "stillimage", "-crf", os.environ.get("NOVEL_CRF", "20"),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_abs],
       cwd=workdir)


def render(spec_path: str, out_mp4: str, workdir: str, cache_dir: str) -> dict:
    spec, warns = novel_spec.normalize(novel_spec.load(spec_path))
    for w in warns:
        print(f"  ⚠️ {w}")
    os.makedirs(workdir, exist_ok=True)
    segments = spec["segments"]
    print(f"# 렌더 시작: {spec['series_id']} EP{spec['episode_no']}  ({len(segments)} segments)")

    # 폰트
    fontsdir, font_family = resolve_font(workdir)
    print(f"  · 자막 폰트: {font_family}" + (" (workdir 복사)" if fontsdir else " (시스템)"))

    # ① TTS
    durs = synth_all(segments, workdir)
    # ② concat
    narration = os.path.join(workdir, "narration.m4a")
    build_narration(len(segments), durs, workdir, narration)
    audio_dur = probe_dur(narration)
    total = round(LEAD_IN + audio_dur + TAIL, 3)
    # ③ ASS
    ass_path = os.path.join(workdir, "ep.ass")
    build_ass(segments, durs, font_family, ass_path)
    # ④ 배경 + 합성
    bg = ensure_background(spec, cache_dir, workdir)
    build_video(bg, narration, "ep.ass", total, spec["episode_no"], fontsdir, out_mp4, workdir)

    # ⑤ 썸네일(무료 · thumbnail_text 큰 글자) — ★실패해도 렌더/업로드는 계속(폴백)
    thumb_out = os.path.splitext(out_mp4)[0] + "_thumb.jpg"
    try:
        thumbnail = build_thumbnail(spec, bg, workdir, thumb_out, fontsdir, font_family)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 생성 실패(무시하고 진행): {e}\n")
        thumbnail = None

    info = {"out": out_mp4, "duration_sec": round(total, 1),
            "audio_sec": round(audio_dur, 1), "segments": len(segments),
            "thumbnail": thumbnail,
            "narration_chars": len(spec["narration_full"]) or sum(len(s["text"]) for s in segments)}
    print(f"✅ {out_mp4}  ({total:.1f}s, 낭독 {audio_dur:.1f}s, {len(segments)} segments)"
          + (f"  + 썸네일" if thumbnail else ""))
    return info


def main() -> int:
    import config
    ap = argparse.ArgumentParser(description="소설 render-spec → 16:9 오디오소설 MP4")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="")
    ap.add_argument("--cache-dir", default=str(config.OUTPUT / "_work" / "novel_bg"))
    args = ap.parse_args()
    config.load_dotenv()
    config.ensure_dirs()
    wd = args.workdir or str(config.OUTPUT / "_work" / "novel" /
                             os.path.splitext(os.path.basename(args.spec))[0])
    info = render(args.spec, args.out, wd, args.cache_dir)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
