#!/usr/bin/env python3
"""SCP 쇼츠 렌더러 — 금요일 롱폼 스펙 → 토요일 9:16 세로 쇼츠(40~50초).

롱폼(scp_render)과 뭐가 다른가:
  ① 9:16(1080x1920). 상단 30%/하단 25%가 텍스트 자리.
  ② ★개체를 정면에 크게 보여준다 — 롱폼 §E '보여주지 않기'의 유일한 예외.
     세로 피드는 3초 안에 "저게 뭐야?"가 안 걸리면 스와이프된다.
  ③ ★LOOK 이 다르다. 롱폼의 빛바랜 35mm 필름룩은 손바닥만 한 화면에서 회색 덩어리로 보인다.
     쇼츠는 선명·고대비·강한 방향광(SHORTS_LOOK).
  ④ ★상단 큰 글자 2줄을 이미지에 번인한다(무음 시청 대비 — 사실상 썸네일).
     1줄=등급 라벨(등급색), 2줄=후킹. 등급색: 안전=초록 / 유클리드=황색 / 케테르=적색.
  ⑤ ★롱폼 오디오를 자르지 않고 shorts.script 로 TTS 를 새로 만든다.
     (싱크 맞추기가 사라지고, '잘라 붙인 티'도 안 난다)

스펙에 `shorts` 블록이 없으면 롱폼 필드로 폴백 합성한다(resolve_shorts) — v2 이전 스펙 대응.

TTS/내레이션/폰트/ffmpeg 래퍼는 story_render, xfade 식은 scp_render 재사용.
"""
from __future__ import annotations
import os
import re
import sys
import time as _time

import scp_render as SCP
import story_render as SR

FFMPEG = SR.FFMPEG
W, H = 1080, 1920
FPS = int(os.environ.get("SCP_SHORTS_FPS", "30"))
PRESET = os.environ.get("SCP_SHORTS_PRESET", "veryfast")
CRF = os.environ.get("SCP_SHORTS_CRF", "21")
XFADE = float(os.environ.get("SCP_SHORTS_XFADE", "0.6"))
MAX_SCENES = int(os.environ.get("SCP_SHORTS_MAX_SCENES", "3"))
MIN_SCENE_SEC = float(os.environ.get("SCP_SHORTS_MIN_SCENE_SEC", "12"))
# 자막 폭: 1080 - MarginL 45 - MarginR 150 = 885px(우측 여백은 쇼츠 버튼 열 회피).
# 한글 글자폭 ≈ 폰트크기 → 68px 이면 한 줄 ~13자, 24자면 2줄에 맞는다.
# (3줄 넘어가면 세로 화면에서 답답하고, 45~65세 타깃이라 더 줄이면 잘 안 보인다)
FONT_SIZE = int(os.environ.get("SCP_SHORTS_FONT_SIZE", "68"))
MAX_CAPTION_CHARS = int(os.environ.get("SCP_SHORTS_CAPTION_CHARS", "24"))
# 이미지 백엔드: qwen(자체 wbSpark) → flux 폴백. 반대로 쓰려면 SCP_SHORTS_IMG=flux.
IMG_BACKEND = os.environ.get("SCP_SHORTS_IMG", "qwen").strip().lower()

# 유튜브 쇼츠 상한 3분. 넘으면 일반 영상으로 취급돼 피드에 안 뜬다.
HARD_MAX_SEC = float(os.environ.get("SCP_SHORTS_MAX_SEC", "175"))

SHORTS_LOOK = ("sharp high-contrast product-still photography, single strong directional "
               "key light, deep black background, rich saturated color, crisp detail, "
               "dramatic rim light, photorealistic, 9:16 vertical composition")
SAFE_AREA = ("top 30% and bottom 25% of the frame are dark empty negative space for text")
NEG_PREFIX = "low contrast, washed out, faded, film grain, muted colors, "
NEG_BASE = ("text, letters, numbers, watermark, logo, caption, subtitles, cartoon, anime, "
            "illustration, painting, 3d render, cgi, gore, blood, corpse, face, human face, "
            "crowd, deformed hands, extra fingers, blurry, low resolution, jpeg artifacts")

# 등급 → (표시용 한글, 액센트색). 시청자가 색만 보고 위험도를 읽게 한다.
CLASS_KO = {"safe": "안전", "euclid": "유클리드", "keter": "케테르"}
CLASS_ACCENT = {"safe": "#5FBF7A", "euclid": "#E0A93B", "keter": "#D9534F"}
DEFAULT_ACCENT = "#E0A93B"


def _lap(t0, label):
    print(f"  ⏱ {label}: 누적 {_time.monotonic() - t0:.0f}s", flush=True)


def _hex(c: str, fallback: str = DEFAULT_ACCENT) -> tuple[int, int, int]:
    c = (c or "").strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", c):
        c = fallback
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


# ── shorts 블록 정규화(없으면 롱폼에서 폴백 합성) ──────────
def resolve_shorts(spec: dict) -> dict:
    """`shorts` 블록을 렌더러가 쓰는 형태로 정규화.

    루틴 프롬프트 v3 부터는 스펙에 `shorts` 가 들어온다. 그 이전 스펙(또는 루틴이 빠뜨린 경우)엔
    롱폼 필드로 합성한다 — 돌긴 돌지만 제목·후킹이 롱폼용이라 CTR 은 확실히 떨어진다(경고를 남긴다).
    """
    sh = spec.get("shorts") if isinstance(spec.get("shorts"), dict) else {}
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    th = spec.get("thumbnail") or {}
    cls = str(spec.get("object_class") or "").strip().lower()
    cls_ko = CLASS_KO.get(cls, spec.get("object_class") or "미분류")
    fallback = not sh

    # 제목: 후킹이 앞, 번호는 뒤(§2.6.1). 폴백은 롱폼 제목의 시리즈 접미사만 갈아끼운다.
    title = (sh.get("title") or "").strip()
    if not title:
        base = (yt.get("title") or spec.get("title") or "SCP").strip()
        base = re.sub(r"\s*\|\s*SCP\s*아카이브\s*$", "", base).strip()
        title = f"{base} | SCP"

    # 상단 2줄
    top = sh.get("overlay_top")
    if isinstance(top, str):
        top = [ln.strip() for ln in top.split("\n") if ln.strip()]
    if not isinstance(top, list) or not top:
        top = [f"등급 : {cls_ko}", (yt.get("thumbnail_text") or spec.get("title") or "").strip()]
    top = [str(t).strip() for t in top if str(t).strip()][:2]

    # 대본
    script = (sh.get("script") or "").strip()
    if not script:
        script = _fallback_script(spec)

    # 이미지 프롬프트: 세로 + 세이프영역 + SHORTS_LOOK 을 보장(루틴이 빠뜨렸어도 붙인다)
    subj = (sh.get("subject_prompt") or "").strip()
    if not subj:
        subj = (th.get("hook") or (spec.get("background") or {}).get("prompt") or "").strip()
        # 롱폼 hook 은 필름룩 접미사를 달고 있다 → 쇼츠에선 그게 독이라 잘라낸다.
        subj = re.split(r"\binstitutional archival photograph\b", subj)[0].strip().rstrip(",")
    if "9:16" not in subj:
        subj = f"{subj}, {SAFE_AREA}, {SHORTS_LOOK}"

    neg = (sh.get("negative_prompt") or th.get("negative_prompt") or NEG_BASE).strip()
    if not neg.lower().startswith("low contrast"):
        neg = NEG_PREFIX + neg

    # 폴백 설명은 ★logline 을 쓰지 않는다 — logline 은 반전을 요약한 문장이라 스포일러다.
    # 콜드오픈(hook_line)은 결과의 온도만 담고 있어 쇼츠 설명으로 안전하다.
    desc = ((sh.get("description") or "").strip()
            or (spec.get("hook_line") or "").strip()
            or (spec.get("cold_open") or "").strip())

    out = {
        "title": title[:100],
        "overlay_top": top,
        "script": script,
        "subject_prompt": subj,
        "negative_prompt": neg,
        "description": desc,
        "playlist": (sh.get("playlist") or "SCP 쇼츠").strip(),
        "accent": sh.get("accent") or CLASS_ACCENT.get(cls, DEFAULT_ACCENT),
        "fallback": fallback,
    }
    if fallback:
        sys.stderr.write("[warn] 스펙에 shorts 블록 없음 — 롱폼 필드로 폴백 합성했다. "
                         "루틴 프롬프트를 v3 로 올리면 제목/후킹이 쇼츠용으로 나온다.\n")
    print(f"  · 쇼츠 소스: {'폴백(롱폼 유래)' if fallback else 'spec.shorts'} | "
          f"title={out['title']!r} | 상단={out['overlay_top']}")
    return out


# 롱폼 `procedures` 는 '문서 조항' 문체(`~하지 않는다`)로 적혀 있다. 그대로 읽히면
# v2 가 고쳤던 그 평평한 낭독이 쇼츠에서 되살아난다 → 폴백 경로에서만 구어로 바꾼다.
_SOFTEN = [(r"않는다(?=[.!?]|$)", "않습니다"), (r"않았다(?=[.!?]|$)", "않았습니다"),
           (r"한다(?=[.!?]|$)", "합니다"), (r"된다(?=[.!?]|$)", "됩니다"),
           (r"있다(?=[.!?]|$)", "있습니다"), (r"없다(?=[.!?]|$)", "없습니다"),
           (r"이다(?=[.!?]|$)", "입니다"), (r"아니다(?=[.!?]|$)", "아닙니다"),
           (r"^대상이\b", "밥솥이"), (r"\b본 대상\b", "그 물건")]


def _soften(s: str) -> str:
    for pat, rep in _SOFTEN:
        s = re.sub(pat, rep, s)
    return s


def _fallback_script(spec: dict) -> str:
    """롱폼 필드로 40~50초 대본 합성 — 콜드오픈 + 규칙 + 미끼(반전은 절대 안 넣는다)."""
    hook = (spec.get("hook_line") or spec.get("logline") or "").strip()
    procs = [str(p).strip() for p in (spec.get("procedures") or []) if str(p).strip()][:3]
    parts = [hook] if hook else []
    if procs:
        parts.append(f"지켜야 할 게 {['한', '두', '세'][len(procs) - 1]} 가지 있었습니다.")
        parts += [_soften(p) for p in procs]
    parts.append("어기면 어떻게 되는지는, 어디에도 적혀 있지 않습니다.")
    parts.append("무슨 일이 있었는지는 전편에서 말씀드릴게요.")
    return " ".join(p if p.endswith((".", "!", "?", "…")) else p + "." for p in parts)


# ── 대본 → 자막 세그먼트 ────────────────────────────────
def _split_sentence(p: str, max_chars: int) -> list[str]:
    """긴 문장을 ★균등하게 나눈다.

    앞에서부터 max_chars 씩 잘라내면 꼬리가 `않았습니다.` 같은 한 조각으로 남는다.
    자막도 흉하지만 세그먼트마다 TTS 를 따로 돌리는 구조라 **낭독이 거기서 끊긴다.**
    그래서 필요한 조각 수를 먼저 정하고, 각 경계를 쉼표(우선)·공백에서 고른다.
    """
    if len(p) <= max_chars:
        return [p]
    n = -(-len(p) // max_chars)                       # 올림 나눗셈
    target = len(p) / n
    cands = [(m.end(), 0) for m in re.finditer(r",\s", p)]      # 쉼표 뒤 선호
    cands += [(m.end(), 1) for m in re.finditer(r"\s", p)]
    out, start = [], 0
    for k in range(1, n):
        pool = [c for c in cands if start + 4 < c[0] < len(p) - 4]
        if not pool:
            break
        pos = min(pool, key=lambda c: abs(c[0] - target * k) + c[1] * 3)[0]
        out.append(p[start:pos].strip())
        start = pos
    out.append(p[start:].strip())
    return [s for s in out if s]


def split_script(text: str, max_chars: int = MAX_CAPTION_CHARS) -> list[dict]:
    """대본 문자열을 자막 한 장 분량으로 자른다(문장 단위 → 균등 분할 → 최후 강제)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    out: list[str] = []
    for sent in re.split(r"(?<=[.!?…])\s+", t):
        p = sent.strip()
        if not p:
            continue
        for piece in _split_sentence(p, max_chars):
            while len(piece) > max_chars * 1.6:       # 공백조차 없는 극단 케이스
                out.append(piece[:max_chars])
                piece = piece[max_chars:].strip()
            if piece:
                out.append(piece)
    return [{"text": s} for s in out]


# ── 이미지 ─────────────────────────────────────────────
def _gen_raw(prompt: str, out_png: str, seed: int) -> str | None:
    """qwen(wbSpark) ↔ FLUX 중 설정된 쪽 먼저, 실패하면 다른 쪽. 둘 다 실패면 None."""
    order = ["qwen", "flux"] if IMG_BACKEND != "flux" else ["flux", "qwen"]
    for backend in order:
        try:
            if backend == "qwen":
                import wbspark
                to = int(os.environ.get("SCP_SHORTS_QWEN_TIMEOUT", "420"))
                print(f"  · 이미지{seed} qwen-image 생성 시도(최대 {to // 60}분)…", flush=True)
                if wbspark.generate_image(prompt, out_png, timeout_sec=to):
                    print(f"  · qwen-image OK: {os.path.basename(out_png)}")
                    return out_png
            else:
                import imagegen
                # 9:16 → FLUX 는 64 배수 요구. 832x1216 ≈ 0.684(9:16=0.5625 보다 완만하지만
                # 아래 crop 으로 세로를 맞춘다). 세로 생성이 가로보다 구도가 훨씬 잘 나온다.
                if imagegen.flux_image(prompt, out_png, 832, 1216, seed=seed):
                    return out_png
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 이미지{seed} {backend} 예외: {e}\n")
    return None


def _procedural(out_png: str) -> str:
    SR.sh([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x0d0b10:s={W}x{H}",
           "-frames:v", "1", "-vf", "vignette=PI/5,noise=alls=8:allf=t,format=rgb24", out_png])
    return out_png


def gen_images(prompt: str, n: int, workdir: str) -> list[str]:
    """같은 개체를 seed 만 바꿔 n 장. 구도가 조금씩 달라져 크로스페이드가 '살아있는' 느낌을 준다."""
    out: list[str] = []
    for i in range(max(1, n)):
        raw = _gen_raw(prompt, os.path.join(workdir, f"sh{i}_raw.png"), seed=i)
        if not raw:
            continue
        norm = os.path.join(workdir, f"sh{i}_norm.png")
        SR.sh([FFMPEG, "-y", "-i", raw, "-vf",
               f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
               f"eq=contrast=1.06:saturation=1.08", "-frames:v", "1", norm])
        out.append(norm)
    if not out:
        out.append(_procedural(os.path.join(workdir, "sh_proc.png")))
        print("  · ⚠️ 이미지 생성 전부 실패 → 절차적 배경 1장")
    return out


# ── 상단 큰 글자 번인 ───────────────────────────────────
def burn_top(img_path: str, lines: list[str], out_path: str, accent: str) -> str:
    """상단 2줄(등급 라벨 + 후킹)을 이미지에 굽는다. 무음으로 넘기는 시청자용 '썸네일'."""
    from PIL import Image, ImageDraw, ImageOps
    from thumbnail import _load_font, _wrap

    img = ImageOps.fit(Image.open(img_path).convert("RGB"), (W, H), Image.LANCZOS)
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    tcap = int(H * 0.34)                                  # 상단 스크림(글자 가독성)
    for y in range(tcap):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, int(205 * (1 - y / tcap))))
    bstart = int(H * 0.66)                                # 하단 스크림(자막 가독성)
    for y in range(bstart, H):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, min(190, int(190 * (y - bstart) / (H - bstart)))))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    draw = ImageDraw.Draw(img)
    max_w = int(W * 0.88)
    y = int(H * 0.055)
    rgb = _hex(accent)
    for idx, raw in enumerate(lines[:2]):
        txt = str(raw).strip()
        if not txt:
            continue
        limit = 1 if idx == 0 else 2                      # 라벨 1줄, 후킹 2줄까지
        for size in ((60, 54, 48, 42) if idx == 0 else (104, 92, 82, 72, 64, 56)):
            font = _load_font(size)
            wrapped = _wrap(draw, txt, font, max_w)
            if len(wrapped) <= limit:
                break
        wrapped = wrapped[:limit]
        stroke = max(4, size // 11)
        fill = rgb if idx == 0 else (255, 255, 255)
        for ln in wrapped:
            x = (W - draw.textlength(ln, font=font)) / 2
            draw.text((x, y), ln, font=font, fill=fill,
                      stroke_width=stroke, stroke_fill=(0, 0, 0))
            y += int(size * 1.18)
        if idx == 0:                                      # 라벨 밑 액센트 바
            draw.rounded_rectangle([(W - 150) // 2, y + 10, (W + 150) // 2, y + 20],
                                   radius=5, fill=rgb)
            y += 46
    img.save(out_path, "PNG")
    return out_path


# ── 자막(ASS) — 9:16 + 쇼츠 UI 회피 ─────────────────────
def build_ass(segments: list[dict], durs: list[float], font_family: str, path: str) -> None:
    """쇼츠 자막. 하단 UI(제목/채널 ~290px)와 우측 버튼 열(~x>940)을 피해 배치한다."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sh,{font_family},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,2,2,45,150,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    t = SR.LEAD_IN
    for i, seg in enumerate(segments):
        d = durs[i]
        lines.append(f"Dialogue: 0,{SR._ass_time(t)},{SR._ass_time(t + d)},Sh,,0,0,0,,"
                     f"{SR._ass_text(seg['text'])}")
        t += d + (SR.SEG_GAP if i < len(segments) - 1 else 0)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── 영상 조립 ───────────────────────────────────────────
def render_video(images: list[str], narration_m4a: str, ass_path: str,
                 fontsdir: str | None, out_mp4: str, total: float) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)) or ".", exist_ok=True)
    wd = os.path.dirname(os.path.abspath(ass_path))
    sub = f"subtitles={os.path.basename(ass_path)}" + (f":fontsdir={fontsdir}" if fontsdir else "")

    n = len(images)
    if n > 1 and total / n < MIN_SCENE_SEC:
        n = max(1, int(total // MIN_SCENE_SEC))
        images = images[:n]
    if n == 1:
        SR.sh([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.abspath(images[0]),
               "-i", os.path.abspath(narration_m4a),
               "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,{sub}",
               "-c:v", "libx264", "-tune", "stillimage", "-preset", PRESET, "-crf", CRF,
               "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
               "-movflags", "+faststart", os.path.abspath(out_mp4)], cwd=wd)
        print(f"  · 장면 1개, {FPS}fps → 총 {total:.0f}s")
        return out_mp4

    ins, d, x = SCP.xfade_chain(images, total, FPS, XFADE)
    ins += ["-i", os.path.abspath(narration_m4a)]
    fc = [f"[{i}:v]fps={FPS},format=yuv420p,setsar=1[s{i}]" for i in range(n)]
    cur = "[s0]"
    for i in range(1, n):
        fc.append(f"{cur}[s{i}]xfade=transition=fade:duration={x:.3f}:offset={d * i - x * i:.3f}[x{i}]")
        cur = f"[x{i}]"
    fc.append(f"{cur}{sub}[v]")
    SR.sh([FFMPEG, "-y", *ins, "-filter_complex", ";".join(fc),
           "-map", "[v]", "-map", f"{n}:a",
           "-c:v", "libx264", "-tune", "stillimage", "-preset", PRESET, "-crf", CRF,
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
           "-movflags", "+faststart", os.path.abspath(out_mp4)], cwd=wd)
    print(f"  · 장면 {n}개 × {d:.0f}s (전환 {x:.1f}s), {FPS}fps → 총 {total:.0f}s")
    return out_mp4


# ── 고수준 렌더 ────────────────────────────────────────
def render(spec: dict, out_mp4: str, workdir: str) -> dict:
    t0 = _time.monotonic()
    os.makedirs(workdir, exist_ok=True)
    sh = resolve_shorts(spec)

    segments = split_script(sh["script"])
    if not segments:
        raise RuntimeError("shorts.script 가 비어 있음 — 대본 없이는 렌더 불가")
    print(f"  · 대본 {len(sh['script'])}자 → 자막 {len(segments)}장")

    fontsdir, font_family = SR.resolve_font(workdir)
    durs = SR.synth_all(segments, workdir)
    _lap(t0, f"TTS {len(segments)}세그먼트")

    total = SR.LEAD_IN + sum(durs) + SR.SEG_GAP * (len(segments) - 1) + SR.TAIL
    if total > HARD_MAX_SEC:
        sys.stderr.write(f"[warn] 쇼츠 길이 {total:.0f}s > {HARD_MAX_SEC:.0f}s — 유튜브가 "
                         f"쇼츠로 취급하지 않을 수 있다(대본을 줄여라).\n")

    narration = os.path.join(workdir, "narration.m4a")
    SR.build_narration(len(segments), durs, workdir, narration)
    ass_path = os.path.join(workdir, "captions.ass")
    build_ass(segments, durs, font_family, ass_path)
    srt_path = SR.build_srt(segments, durs, os.path.join(workdir, "captions.srt"))
    # ★루틴이 segments[i]["text_en"] 등을 써줬다면 같은 타이밍으로 번역 자막도 만든다.
    #   번역 API 를 쓰지 않으므로 비용 0이고, 타이밍이 한국어와 동일해 싱크가 어긋날 수 없다.
    srts = {}
    for _lang in [l.strip() for l in os.environ.get("I18N_LANGS", "en,ja,zh-Hant").split(",") if l.strip()]:
        _p = SR.build_srt(segments, durs,
                          os.path.join(workdir, f"captions_{_lang.replace('-', '_')}.srt"),
                          key=f"text_{_lang.replace('-', '_')}")
        if _p:
            srts[_lang] = _p
    if srts:
        print(f"  · 루틴 번역 자막 {len(srts)}개 언어: {', '.join(srts)}")
    _lap(t0, "내레이션+자막")

    want = max(1, min(MAX_SCENES, int(total // MIN_SCENE_SEC) or 1))
    # 두 백엔드 모두 negative_prompt 파라미터가 없다 → 스펙의 네거티브는 보관용이고,
    # 실제로는 다른 파이프라인과 같은 방식으로 짧은 금지 문구만 프롬프트에 덧붙인다.
    raws = gen_images(f"{sh['subject_prompt']}, no text, no letters, no watermark, no human face",
                      want, workdir)
    images = [burn_top(p, sh["overlay_top"], os.path.join(workdir, f"sh{i}.png"), sh["accent"])
              for i, p in enumerate(raws)]
    _lap(t0, f"이미지 {len(images)}장(+상단 문구 번인)")

    render_video(images, narration, ass_path, fontsdir, out_mp4, total)
    _lap(t0, "영상 인코딩")

    dur = SR.probe_dur(out_mp4)
    size_mb = os.path.getsize(out_mp4) / 1e6
    # 쇼츠 썸네일 = 첫 장면(상단 문구 포함) 그대로. 이미 9:16 이라 추가 생성 비용 0.
    thumb = os.path.splitext(out_mp4)[0] + "_thumb.jpg"
    try:
        from PIL import Image
        Image.open(images[0]).convert("RGB").save(thumb, "JPEG", quality=88)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 쇼츠 썸네일 저장 실패 → 스킵: {e}\n")
        thumb = None
    print(f"✅ {out_mp4}  ({dur:.0f}s, {size_mb:.1f}MB, 장면 {len(images)}개, 자막 {len(segments)}장)")
    return {"out": out_mp4, "duration_sec": round(dur, 1), "size_mb": round(size_mb, 1),
            "scenes": len(images), "captions": len(segments), "thumbnail": thumb,
            "srt": srt_path, "srts": srts, "shorts": sh}


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="SCP 쇼츠(9:16) 렌더(테스트)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="_scp_shorts_work")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    info = render(spec, args.out, args.workdir)
    info.pop("shorts", None)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
