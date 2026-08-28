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
CRF = os.environ.get("SCP_CRF", "23")
XFADE = float(os.environ.get("SCP_XFADE", "1.2"))     # 장면 전환(초)
MAX_SCENES = int(os.environ.get("SCP_MAX_SCENES", "8"))
MIN_SCENE_SEC = float(os.environ.get("SCP_MIN_SCENE_SEC", "25"))

# ── 켄번즈(느린 줌·팬) ─────────────────────────────────────
# 정지 이미지 8장에 크로스페이드만 걸면 60초짜리 정지 화면이 이어진다.
# 참고 채널(4분 45초에 30컷 이상)과 비교하면 이 정적임이 제일 크게 체감되는 차이였다.
# 그림을 더 만들지 않고도 움직임을 만드는 가장 싼 방법이 켄번즈다.
KENBURNS = os.environ.get("SCP_KENBURNS", "1") != "0"
KB_AMP = float(os.environ.get("SCP_KB_AMP", "0.06"))    # 줌 폭(1.00 → 1.06)
KB_SRC_W = int(os.environ.get("SCP_KB_SRC_W", "2560"))  # zoompan 전 업스케일 폭
#   ★업스케일이 필요한 이유: zoompan 은 원본 해상도에서 정수 크롭을 하기 때문에
#   1920 폭 원본을 그대로 확대하면 프레임마다 1px 씩 튀는 지터가 보인다.

# ★프리셋은 켄번즈 여부에 따라 갈린다.
#   ultrafast 는 '정지 화면'을 전제로 고른 값이었다. 화면이 계속 움직이면
#   ultrafast 가 비트레이트를 폭증시킨다 — 실측(2분·8장면·10fps):
#       ultrafast  283.6MB (19Mbps)   ← 8분이면 1.1GB
#       veryfast    39.5MB (2.6Mbps)  ← 인코딩 시간은 +30% 뿐
#   그래서 켄번즈가 켜져 있으면 veryfast 를 기본으로 쓴다.
PRESET = os.environ.get("SCP_PRESET") or ("veryfast" if KENBURNS else "ultrafast")

# ── 오버레이(상단 라벨 · 강조 대형 텍스트) ─────────────────
TAG_MODE = os.environ.get("SCP_TAG_MODE", "intro")      # intro | always | off
TAG_SEC = float(os.environ.get("SCP_TAG_SEC", "10"))    # intro 모드에서 노출 시간
PUNCH_SEC = float(os.environ.get("SCP_PUNCH_SEC", "3.5"))
PUNCH_MAX = int(os.environ.get("SCP_PUNCH_MAX", "3"))   # 회차당 강조 컷 상한


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


# ── ASS 오버레이(상단 라벨 · 강조 대형 텍스트) ─────────
# 등급색. ★쇼츠(scp_shorts_render.CLASS_ACCENT)와 같은 값이다 — 바꾸면 양쪽 다 바꿀 것.
CLASS_HEX = {"safe": "#5FBF7A", "euclid": "#E0A93B", "keter": "#D9534F"}
CLASS_LABEL = {"safe": "SAFE", "euclid": "EUCLID", "keter": "KETER"}
DEFAULT_HEX = "#E0A93B"


def _ass_bgr(hexcolor: str) -> str:
    """#RRGGBB → ASS 의 &H00BBGGRR. ASS 는 ★BGR 순서다(RGB 아님)."""
    c = (hexcolor or "").strip().lstrip("#")
    if len(c) != 6:
        c = DEFAULT_HEX.lstrip("#")
    return f"&H00{c[4:6]}{c[2:4]}{c[0:2]}"


def augment_ass(ass_path: str, spec: dict, segments: list, spans: list, font: str) -> int:
    """자막 ASS 에 ① 상단 번호·등급 라벨 ② 강조 대형 텍스트를 얹는다.

    별도 렌더 패스를 만들지 않는다 — 이미 자막을 번인하고 있으므로 ★같은 필터에
    이벤트만 더 넣으면 인코딩 비용이 사실상 0이다.

    강조는 `spec["emphasis"]`(문자열 배열)로 받는다. 각 문자열이 ★어느 세그먼트 본문에
    들어 있는지 찾아서 그 세그먼트가 시작할 때 띄운다. 쇼츠의 `highlight` 와 같은 방식이라
    루틴이 이미 아는 규칙이다(본문에 글자 그대로 있어야 한다).
    """
    if not os.path.exists(ass_path):
        return 0
    total = SR.total_from_spans(spans) if spans else 0.0
    cls = str(spec.get("object_class") or "").strip().lower()
    hexc = CLASS_HEX.get(cls, DEFAULT_HEX)
    num = str(spec.get("scp_number") or "SCP-????").strip()
    label = CLASS_LABEL.get(cls, (spec.get("object_class") or "").upper() or "UNKNOWN")

    styles = [
        # 상단 라벨 — BorderStyle=3(불투명 박스) · Alignment=7(좌상단)
        #   ★Outline 이 곧 박스 여백이다. 0 이면 글자 딱 맞게 붙어 박스가 안 보인다.
        #   ★박스는 ★불투명(알파 00)이어야 한다. 반투명이면 색 변경(\\c) 지점에서
        #   박스가 두 번 그려져 겹치는 부분만 진해진다(실측으로 확인).
        f"Style: Tag,{font},44,&H00F5EEE8,&H000000FF,&H00120E0A,&H00000000,"
        f"-1,0,0,0,100,100,2,0,3,10,0,7,60,60,50,1",
        # 강조 — Alignment=5(중앙) · 두꺼운 외곽선
        f"Style: Punch,{font},150,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,6,3,5,120,120,0,1",
    ]
    events = []

    # ① 상단 라벨
    if TAG_MODE != "off" and total > 0:
        end = total if TAG_MODE == "always" else min(TAG_SEC, total)
        txt = (f"{SR._ass_text(num)}   "
               f"{{\\c{_ass_bgr(hexc)}}}{SR._ass_text(label)}")
        events.append(f"Dialogue: 1,{SR._ass_time(0)},{SR._ass_time(end)},Tag,,0,0,0,,"
                      f"{{\\fad(0,320)}}{txt}")

    # ② 강조 대형 텍스트
    #   두 가지 표기를 다 받는다.
    #     ㉠ segments[i]["emphasis"]  ← 스펙 스키마에 원래 있던 자리. ★정확하다(매칭 불필요)
    #     ㉡ spec["emphasis"] = [문자열]  ← 본문에서 그 문자열이 든 세그먼트를 찾는다
    #   ㉠을 먼저 채우고 ㉡으로 보충한다. 같은 세그먼트를 두 번 쓰지 않는다.
    cand: list[tuple[int, str]] = []
    for i, sg in enumerate(segments):
        key = str(sg.get("emphasis") or "").strip()
        if key:
            cand.append((i, key))
    seen_idx = {i for i, _ in cand}
    for raw in (spec.get("emphasis") or [])[:PUNCH_MAX * 4]:
        key = str(raw or "").strip()
        if not key:
            continue
        idx = next((i for i, sg in enumerate(segments)
                    if i not in seen_idx and key in str(sg.get("text") or "")), None)
        if idx is None:
            sys.stderr.write(f"[warn] emphasis 매칭 실패(본문에 없음): {key!r}\n")
            continue
        cand.append((idx, key))
        seen_idx.add(idx)

    picked, last_t = [], -99.0
    for idx, key in sorted(cand):
        if len(picked) >= PUNCH_MAX or idx >= len(spans):
            continue
        st = spans[idx][0] + 0.25
        if st - last_t < 20.0:       # 너무 몰리면 산만하다 — 최소 20초 간격
            continue
        picked.append((st, key))
        last_t = st
    for st, key in picked:
        en = min(st + PUNCH_SEC, total) if total else st + PUNCH_SEC
        events.append(
            f"Dialogue: 1,{SR._ass_time(st)},{SR._ass_time(en)},Punch,,0,0,0,,"
            f"{{\\an5\\pos(960,430)\\fscx62\\fscy62"
            f"\\t(0,240,\\fscx100\\fscy100)\\fad(140,300)}}{SR._ass_text(key)}")

    if not events:
        return 0
    body = open(ass_path, encoding="utf-8").read()
    body = body.replace("\n[Events]", "\n" + "\n".join(styles) + "\n\n[Events]", 1)
    open(ass_path, "w", encoding="utf-8").write(body.rstrip("\n") + "\n" + "\n".join(events) + "\n")
    print(f"  · 오버레이: 상단 라벨 {'on' if TAG_MODE != 'off' else 'off'}"
          f"({TAG_MODE}) · 강조 컷 {len(picked)}개")
    return len(events)


# ── 켄번즈 필터 ────────────────────────────────────────
def scene_vf(i: int, nf: int) -> str:
    """장면 하나의 비디오 필터 체인. KENBURNS 가 꺼져 있으면 예전과 완전히 동일하다.

    zoompan 은 ★입력 해상도에서 정수 크롭을 하므로, 1920 원본을 그대로 쓰면
    프레임마다 1px 씩 흔들리는 지터가 보인다. 먼저 KB_SRC_W 로 올린 뒤 크롭한다
    (2560 → 1920 이라 결과는 항상 축소 = 선명하다).

    4가지 움직임을 돌려 쓴다. 같은 방향만 이어지면 그것대로 단조롭다.
      0 줌인·고정 / 1 줌아웃·고정 / 2 줌인·오른쪽으로 / 3 줌아웃·왼쪽으로
    """
    base = f"fps={FPS}"
    if not KENBURNS or nf < 2:
        return f"{base},format=yuv420p,setsar=1"
    mode = i % 4
    zin = mode in (0, 2)
    dx = {0: 0, 1: 0, 2: 1, 3: -1}[mode]
    prog = f"on/{nf - 1}"
    z = (f"1+{KB_AMP:.4f}*({prog})" if zin
         else f"{1 + KB_AMP:.4f}-{KB_AMP:.4f}*({prog})")
    x = "iw/2-(iw/zoom/2)"
    if dx:
        x += f"{'+' if dx > 0 else '-'}(iw*0.03)*(({prog})-0.5)"
    y = "ih/2-(ih/zoom/2)"
    return (f"{base},scale={KB_SRC_W}:-2,"
            f"zoompan=z='{z}':d=1:x='{x}':y='{y}':s={W}x{H}:fps={FPS},"
            f"format=yuv420p,setsar=1")


# ── 챕터 타임스탬프 재계산 ─────────────────────────────
def recompute_chapters(spec: dict, spans: list[tuple[float, float]]) -> list[str]:
    """루틴 챕터(est_sec 기준) → 실제 TTS 길이 기준으로 재매핑.

    루틴의 est_sec 합계와 실제 낭독 길이가 크게 다를 수 있어(관측: 310s vs ~480s),
    그대로 두면 유튜브 챕터가 전부 어긋난다. est 시간축의 위치를 세그먼트 인덱스로 옮긴 뒤
    그 세그먼트의 '실제 시작 시각'을 쓴다. 첫 챕터는 반드시 0:00(유튜브 요구사항).
    """
    yt = (spec.get("platforms") or {}).get("youtube") or {}
    chapters = yt.get("chapters") or []
    segs = spec.get("segments") or []
    if not chapters or not segs or len(spans) != len(segs):
        return list(chapters)

    # est 누적 / 실제 시작 시각
    est_cum, t = [], 0.0
    for s in segs:
        t += float(s.get("est_sec", 0) or 0)
        est_cum.append(t)
    act_start = [s for s, _ in spans]

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


def _tune() -> list[str]:
    """`-tune stillimage` 는 ★정지 화면 전제다. 켄번즈로 화면이 계속 움직이면
    오히려 블록 노이즈가 생긴다 → 켄번즈가 켜져 있으면 튠을 뺀다."""
    return [] if KENBURNS else ["-tune", "stillimage"]


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
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
              + scene_vf(0, max(1, int(round(total * FPS)))) + f",{sub}")
        cmd = [FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.abspath(images[0]),
               "-i", os.path.abspath(narration_m4a), "-vf", vf,
               "-c:v", "libx264", *_tune(), "-preset", PRESET, "-crf", CRF,
               "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
               "-movflags", "+faststart", os.path.abspath(out_mp4)]
        SR.sh(cmd, cwd=wd)
        return out_mp4

    ins, d, x = xfade_chain(images, total, FPS, XFADE)
    ins += ["-i", os.path.abspath(narration_m4a)]

    fc, cur = [], None
    nf = max(1, int(round(d * FPS)))       # 장면당 프레임 수
    for i in range(n):
        fc.append(f"[{i}:v]{scene_vf(i, nf)}[s{i}]")
    cur = "[s0]"
    for i in range(1, n):
        off = d * i - x * i          # 누적 오프셋
        lbl = f"[x{i}]"
        fc.append(f"{cur}[s{i}]xfade=transition=fade:duration={x:.3f}:offset={off:.3f}{lbl}")
        cur = lbl
    fc.append(f"{cur}{sub}[v]")

    cmd = [FFMPEG, "-y", *ins, "-filter_complex", ";".join(fc),
           "-map", "[v]", "-map", f"{n}:a",
           "-c:v", "libx264", *_tune(), "-preset", PRESET, "-crf", CRF,
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "copy", "-t", f"{total:.2f}",
           "-movflags", "+faststart", os.path.abspath(out_mp4)]
    print(f"  · 장면 {n}개 × {d:.0f}s (전환 {x:.1f}s), {FPS}fps → 총 {total:.0f}s"
          + (f" · 켄번즈 ±{KB_AMP:.0%}" if KENBURNS else " · 켄번즈 off"))
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
    narration = os.path.join(workdir, "narration.m4a")
    spans = SR.synth_narration(segments, workdir, narration)
    _lap(t0, f"TTS {len(segments)}세그먼트")

    total = SR.total_from_spans(spans)
    ass_path = os.path.join(workdir, "captions.ass")
    SR.build_ass(segments, spans, font_family, ass_path)
    augment_ass(ass_path, spec, segments, spans, font_family)
    srt_path = SR.build_srt(segments, spans, os.path.join(workdir, "captions.srt"))
    # ★루틴이 segments[i]["text_en"] 등을 써줬다면 같은 타이밍으로 번역 자막도 만든다.
    #   번역 API 를 쓰지 않으므로 비용 0이고, 타이밍이 한국어와 동일해 싱크가 어긋날 수 없다.
    srts = {}
    for _lang in [l.strip() for l in os.environ.get("I18N_LANGS", "en,ja,zh-Hant").split(",") if l.strip()]:
        _p = SR.build_srt(segments, spans,
                          os.path.join(workdir, f"captions_{_lang.replace('-', '_')}.srt"),
                          key=f"text_{_lang.replace('-', '_')}")
        if _p:
            srts[_lang] = _p
    if srts:
        print(f"  · 루틴 번역 자막 {len(srts)}개 언어: {', '.join(srts)}")
    _lap(t0, "내레이션+자막")

    images = gen_scene_images(resolve_scenes(spec), workdir)
    _lap(t0, f"장면 이미지 {len(images)}장")

    render_video(images, narration, ass_path, fontsdir, out_mp4, total)
    _lap(t0, "영상 인코딩")

    dur = SR.probe_dur(out_mp4)
    size_mb = os.path.getsize(out_mp4) / 1e6
    chapters = recompute_chapters(spec, spans)
    print(f"✅ {out_mp4}  ({dur:.0f}s, {size_mb:.1f}MB, 장면 {len(images)}개, {len(segments)} segments)")
    return {"out": out_mp4, "duration_sec": round(dur, 1), "size_mb": round(size_mb, 1),
            "scenes": len(images), "chapters": chapters, "srt": srt_path, "srts": srts}


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
