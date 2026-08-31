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
import math
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
SEG_GAP = float(os.environ.get("STORY_SEG_GAP", "0.32"))   # ★폴백 경로에서만 쓰인다
LEAD_IN = float(os.environ.get("STORY_LEAD_IN", "0.6"))
TAIL = float(os.environ.get("STORY_TAIL", "1.8"))
FONT_SIZE = int(os.environ.get("STORY_FONT_SIZE", "56"))

# ★통합 TTS — 세그먼트를 묶어 한 번에 합성한다(끊김 제거). 자세한 이유는 아래 ① 참고.
JOIN = os.environ.get("STORY_TTS_JOIN", "1") != "0"        # 0 = 옛 방식(세그먼트별)
JOIN_MAX_CHARS = int(os.environ.get("STORY_TTS_JOIN_CHARS", "700"))
GROUP_GAP = float(os.environ.get("STORY_GROUP_GAP", "0.35"))  # 그룹(문단) 사이 숨

# ── ★낭독 억양 변주 ──────────────────────────────────
# 2026-08-31. "목소리 톤·속도·높낮이가 전부 똑같아서 기계가 읽는 것 같다"는 지적.
# 실제로 그랬다 — rate/pitch 가 영상 전체에 ★단 하나의 값으로 걸려 있었다.
# 사람은 설명할 땐 조금 빠르고, 조여올수록 느려지고 낮아진다. 그 곡선을 흉내낸다.
#
# ★소재를 보지 않는다. 오직 ★이야기 진행률(묶음 위치)만 본다 — 어떤 이야기가 와도
#   같은 방식으로 동작하고, 키워드에 걸려 꼬일 여지가 없다.
# edge-tts 는 SSML 을 열어주지 않지만 rate/pitch 는 ★호출 단위로 줄 수 있다.
# 묶음(문단)마다 따로 합성하고 있으므로 거기에 얹으면 된다.
PROSODY = os.environ.get("STORY_PROSODY", "1") != "0"
PROSODY_RATE = float(os.environ.get("STORY_PROSODY_RATE", "5"))    # ±%p
PROSODY_PITCH = float(os.environ.get("STORY_PROSODY_PITCH", "3"))  # ±Hz
PROSODY_PEAK = float(os.environ.get("STORY_PROSODY_PEAK", "0.82")) # 가장 느려지는 지점(진행률)


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
# ★세그먼트마다 TTS 를 따로 돌리면 낭독이 매 문장 끊긴다.
#   edge-tts 는 한 번의 호출을 '완결된 발화' 로 읽기 때문에
#     ⓐ 끝 억양이 종결형으로 뚝 떨어지고
#     ⓑ mp3 앞뒤에 무음을 붙인다(합쳐서 0.4~0.7s 관측)
#   여기에 SEG_GAP 까지 더해져 경계마다 1초 가까이 비었다. 이어지는 이야기가 아니라
#   낱개 문장을 하나씩 읽어주는 소리로 들려서 2026-08-15 SCP 롱폼/쇼츠를 폐기했다.
#   → 세그먼트를 문단 크기로 묶어 ★한 번에 합성하고(연결 억양이 살아난다),
#     자막 타이밍은 WordBoundary 이벤트로 실제 오디오에서 되찾는다.
#     경계 무음이 아예 없어지고, 문장 사이 호흡은 TTS 가 스스로 넣는 자연스러운 양만 남는다.
def _num(s: str, unit: str) -> float:
    """`-4%` → -4.0 · `+0Hz` → 0.0. 못 읽으면 0."""
    try:
        return float(str(s).strip().rstrip(unit).rstrip("z").rstrip("H") or 0)
    except ValueError:
        return 0.0


def prosody_at(p: float) -> tuple[str, str]:
    """이야기 진행률 p(0~1) → 그 대목에서 쓸 (rate, pitch) 문자열.

    곡선은 하나다. 시작은 기준보다 조금 빠르고 높게(설명하는 톤),
    PROSODY_PEAK 까지 단조롭게 느려지고 낮아지고(조여드는 톤),
    그 뒤로는 ★조금만 되돌아온다 — 회복이 아니라 여운이다.
    """
    if not PROSODY:
        return VO_RATE, VO_PITCH
    p = 0.0 if p < 0 else (1.0 if p > 1 else p)
    peak = min(max(PROSODY_PEAK, 0.05), 0.999)
    if p <= peak:
        k = math.cos(math.pi * (p / peak))          # +1 → -1
    else:
        k = -1.0 + 0.45 * ((p - peak) / (1 - peak))  # -1 → -0.55
    rate = _num(VO_RATE, "%") + k * PROSODY_RATE
    pitch = _num(VO_PITCH, "Hz") + k * PROSODY_PITCH
    return f"{rate:+.0f}%", f"{pitch:+.0f}Hz"


async def _synth(text, voice, out_mp3, rate=None, pitch=None):
    import edge_tts  # type: ignore
    await edge_tts.Communicate(text, voice, rate=rate or VO_RATE,
                               pitch=pitch or VO_PITCH).save(out_mp3)


async def _synth_marks(text, voice, out_mp3, rate=None, pitch=None):
    """한 번의 호출로 합성하면서 단어 경계(초 단위)를 같이 받아온다."""
    import edge_tts  # type: ignore
    rate, pitch = rate or VO_RATE, pitch or VO_PITCH
    try:
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                    boundary="WordBoundary")
    except TypeError:                      # 구버전 edge-tts: 문장 경계만 나온다(그래도 쓸 만함)
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    marks = []
    with open(out_mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] in ("WordBoundary", "SentenceBoundary"):
                marks.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))
    return marks


def synth_group(text: str, out_mp3: str, rate=None, pitch=None) -> list[tuple[float, float, str]]:
    """묶음 하나를 합성. 실패하면 대체 보이스로, 그래도 안 되면 예외."""
    voices = [VOICE] + ([VOICE_FALLBACK] if VOICE_FALLBACK != VOICE else [])
    last = None
    for v in voices:
        for _ in range(2):                 # 네트워크 흔들림 1회 재시도
            try:
                marks = asyncio.run(_synth_marks(text, v, out_mp3, rate, pitch))
                if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
                    return marks
            except Exception as e:         # noqa: BLE001
                last = e
    raise last or RuntimeError("TTS 합성 실패")


def group_segments(segments, max_chars: int | None = None) -> list[list[int]]:
    """세그먼트를 문단 크기(JOIN_MAX_CHARS)로 묶는다 — 문장 중간은 절대 자르지 않는다.

    통째로 한 번에 합성하지 않는 이유: 15분짜리 롱폼을 웹소켓 하나로 받다 끊기면
    전부 날아간다. 묶음 단위면 재시도 비용이 문단 하나로 끝나고, 묶음 사이의
    GROUP_GAP(0.35s)은 문단 전환의 '숨'이라 오히려 있어야 자연스럽다.
    """
    max_chars = JOIN_MAX_CHARS if max_chars is None else max_chars
    groups: list[list[int]] = []
    cur: list[int] = []
    n = 0
    for i, seg in enumerate(segments):
        t = (seg.get("text") or "").strip()
        if cur and n + len(t) > max_chars:
            groups.append(cur)
            cur, n = [], 0
        cur.append(i)
        n += len(t) + 1
    if cur:
        groups.append(cur)
    return groups


def _spans_proportional(texts, dur) -> list[tuple[float, float]]:
    """단어 경계를 못 믿을 때 — 문자 수 비례로 나눈다.

    싱크 정밀도만 떨어질 뿐 ★낭독은 여전히 끊기지 않는다(오디오는 이미 한 덩어리).
    """
    w = [max(1, len(t)) for t in texts]
    tot = sum(w)
    out, t = [], 0.0
    for x in w:
        d = dur * x / tot
        out.append((t, t + d))
        t += d
    return out


def _spans_from_marks(texts, marks, dur) -> list[tuple[float, float]] | None:
    """단어 경계 → 세그먼트별 [start,end] (묶음 오디오 기준 초). 못 믿겠으면 None."""
    n = len(texts)
    joined = " ".join(texts)
    ranges, p = [], 0
    for t in texts:
        ranges.append((p, p + len(t)))
        p += len(t) + 1

    hits, cur = [], 0                      # 경계는 순서대로 오므로 커서를 전진만 시킨다
    for st, d, w in marks:
        w = (w or "").strip()
        if not w:
            continue
        pos = joined.find(w, cur)
        if pos < 0:
            continue                       # 구두점 등으로 못 찾으면 그 단어만 버린다
        cur = pos + len(w)
        hits.append((pos, st, st + d))

    starts: list[float | None] = [None] * n
    for i, (cs, ce) in enumerate(ranges):
        sel = [h for h in hits if cs <= h[0] < ce]
        if sel:
            starts[i] = sel[0][1]
    if sum(s is not None for s in starts) < max(1, int(n * 0.6)):
        return None

    # 첫 세그먼트는 오디오 시작에 고정 — 이후 빈 칸은 문자 수 비례로 보간
    starts[0] = 0.0
    cw = [0.0]
    for t in texts:
        cw.append(cw[-1] + max(1, len(t)))
    i = 1
    while i < n:
        if starts[i] is not None:
            i += 1
            continue
        a, b = i - 1, i
        while b < n and starts[b] is None:
            b += 1
        t0, t1 = starts[a], (starts[b] if b < n else dur)
        c0, c1 = cw[a], (cw[b] if b < n else cw[n])
        for k in range(a + 1, b):
            r = (cw[k] - c0) / (c1 - c0) if c1 > c0 else 0.0
            starts[k] = t0 + (t1 - t0) * r
        i = b

    # 끝 시각 = 다음 세그먼트 시작(마지막은 오디오 끝) — 자막이 깜빡이지 않고 이어진다
    return [(starts[i], starts[i + 1] if i + 1 < n else dur) for i in range(n)]


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


def _concat_to_m4a(names: list[str], gap: float, workdir: str, out_m4a: str) -> None:
    lines = []
    if gap > 0 and len(names) > 1:
        sh([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{gap:.3f}", os.path.join(workdir, "gap.wav")])
    for i, nm in enumerate(names):
        lines.append(f"file '{nm}'")
        if gap > 0 and i < len(names) - 1:
            lines.append("file 'gap.wav'")
    with open(os.path.join(workdir, "concat.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-c:a", "aac", "-b:a", "192k", "narration.m4a"], cwd=workdir)
    if out_m4a != os.path.join(workdir, "narration.m4a"):
        shutil.copyfile(os.path.join(workdir, "narration.m4a"), out_m4a)


def spans_from_durs(durs) -> list[tuple[float, float]]:
    """옛 방식(세그먼트별 합성)의 타이밍 — 폴백 경로 전용."""
    out, t = [], LEAD_IN
    for i, d in enumerate(durs):
        out.append((t, t + d))
        t += d + (SEG_GAP if i < len(durs) - 1 else 0)
    return out


def total_from_spans(spans) -> float:
    return (spans[-1][1] if spans else LEAD_IN) + TAIL


def _synth_joined(segments, workdir, out_m4a) -> list[tuple[float, float]]:
    groups = group_segments(segments)
    spans: list[tuple[float, float] | None] = [None] * len(segments)
    names, base, guessed = [], LEAD_IN, 0
    for gi, idxs in enumerate(groups):
        texts = [(segments[i].get("text") or "").strip() for i in idxs]
        mp3 = os.path.join(workdir, f"grp_{gi:03d}.mp3")
        wav = os.path.join(workdir, f"grp_{gi:03d}.wav")
        # 묶음이 하나뿐이면 진행률이 0 으로 고정돼 곡선이 의미가 없다 → 기준값 그대로.
        p = (gi / (len(groups) - 1)) if len(groups) > 1 else None
        rate, pitch = prosody_at(p) if p is not None else (VO_RATE, VO_PITCH)
        marks = synth_group(" ".join(texts), mp3, rate, pitch)
        sh([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
        d = probe_dur(wav)
        local = _spans_from_marks(texts, marks, d)
        if local is None:
            local = _spans_proportional(texts, d)
            guessed += 1
        for k, i in enumerate(idxs):
            spans[i] = (base + local[k][0], base + local[k][1])
        names.append(os.path.basename(wav))
        base += d + GROUP_GAP
    _concat_to_m4a(names, GROUP_GAP, workdir, out_m4a)
    # 묶음 경계의 GROUP_GAP 동안 자막이 사라져 깜빡이지 않도록, 각 자막을 다음 자막
    # 시작까지 늘인다(마지막은 오디오 끝 그대로).
    if any(s is None for s in spans):     # 있을 수 없지만, 어긋난 채 내보내면 자막이 밀린다
        raise RuntimeError("세그먼트 타이밍 누락")
    out = [(spans[i][0], spans[i + 1][0] if i + 1 < len(spans) else spans[i][1])
           for i in range(len(spans))]
    audio = base - GROUP_GAP - LEAD_IN
    note = f", {guessed}묶음은 문자수 비례 추정" if guessed else ""
    print(f"  · TTS {len(segments)} segments → ★{len(groups)}묶음 통합 합성"
          f"(총 {audio:.0f}s 낭독{note}) — 끊김 지점 {len(groups) - 1}곳"
          f"(옛 방식 {len(segments) - 1}곳)")
    return out


def synth_narration(segments, workdir, out_m4a) -> list[tuple[float, float]]:
    """낭독 오디오를 만들고 세그먼트별 (start, end) 를 돌려준다.

    통합 합성이 어떤 이유로든 실패하면 ★옛 방식(세그먼트별)으로 조용히 내려간다.
    최악의 경우가 '예전 품질'이지 '실패한 런'이 아니게 하려는 것.
    """
    if JOIN:
        try:
            return _synth_joined(segments, workdir, out_m4a)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 통합 TTS 실패 → 세그먼트별 합성으로 폴백: {e}\n")
    durs = synth_all(segments, workdir)
    build_narration(len(segments), durs, workdir, out_m4a)
    return spans_from_durs(durs)


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


def build_srt(segments, spans, path, key="text") -> str | None:
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
    lines = []
    for i, seg in enumerate(segments):
        start, end = spans[i]
        # 특정 세그먼트만 번역이 비면 한국어로 메운다(자막이 통째로 사라지는 것보다 낫다)
        text = (seg.get(key) or seg.get("text") or "").strip()
        lines.append(f"{i + 1}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def build_ass(segments, spans, font_family, path):
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
    for i, seg in enumerate(segments):
        start, end = spans[i]
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Story,,0,0,0,,{_ass_text(seg['text'])}")
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
    narration = os.path.join(workdir, "narration.m4a")
    spans = synth_narration(segments, workdir, narration)
    total = total_from_spans(spans)
    ass_path = os.path.join(workdir, "captions.ass")
    build_ass(segments, spans, font_family, ass_path)
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
