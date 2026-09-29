#!/usr/bin/env python3
"""사연 오디오드라마 렌더 (2026-09-29 파일럿).

  ① 발화를 ~220자 조각으로 → Supertonic(DGX Spark) 여러 목소리 병렬 합성
  ② 조각 사이 쉼 + 장 사이 3초(장 제목 카드) → 한 줄 오디오 → 0.92배 속도(어르신 청취) · 음량 정규화
  ③ 장마다 그림 2~3장(Spark z-image, 실패 시 FLUX) → 1920×1080 정지화
  ④ 정지화 + 오디오 → mp4 (-tune stillimage, 10fps) · 자막(SRT) · 목차 · 썸네일

실측(2026-09-29): Supertonic 은 소리 1초에 약 1초(RTF≈1), 동시 6건이면 처리량 약 2.2배.
  → 100분이면 합성에 약 45분. 분당 ~450자로 읽는다.
"""
from __future__ import annotations
import concurrent.futures as cf
import os
import re
import shutil
import subprocess
import sys
import time
import wave

TEMPO = float(os.environ.get("DRAMA_TEMPO", "0.92"))
WORKERS = int(os.environ.get("DRAMA_TTS_WORKERS", "6"))
CHUNK_MAX = 220
GAP_SAME, GAP_SWITCH, GAP_CHAPTER = 0.35, 0.6, 3.0
SR = 44100
W, H = 1920, 1080
FPS = int(os.environ.get("DRAMA_FPS", "10"))
MAX_FALLBACK = 0.03          # Supertonic 실패 조각이 이 비율을 넘으면 목소리가 뒤섞이므로 중단
LOOK = ("soft painterly Korean drama illustration, warm muted colors, gentle window light, "
        "cinematic 16:9 composition, ordinary Korean people and homes, ")
EDGE_VOICE = {"F": ["ko-KR-SunHiNeural"], "M": ["ko-KR-InJoonNeural", "ko-KR-HyunsuMultilingualNeural"]}


def _bin(name):
    return shutil.which(name) or name


FFMPEG = _bin("ffmpeg")


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


# ── ① 조각 나누기 ─────────────────────────────────────────────
def split_text(text: str, limit: int = CHUNK_MAX) -> list[str]:
    """문장 끝에서 끊어 limit 이하 조각으로. 문장 하나가 너무 길면 쉼표에서 한 번 더."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text] if text else []
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    out, cur = [], ""
    for s in sents:
        if len(s) > limit:
            parts = [p.strip() for p in re.split(r"(?<=,)\s+", s) if p.strip()]
        else:
            parts = [s]
        for p in parts:
            while len(p) > limit:            # 쉼표도 없는 긴 문장 — 공백에서 자른다
                cut = p.rfind(" ", 0, limit)
                cut = cut if cut > limit // 2 else limit
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(p[:cut].strip())
                p = p[cut:].strip()
            if cur and len(cur) + 1 + len(p) > limit:
                out.append(cur)
                cur = p
            else:
                cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


def plan_chunks(spec: dict) -> list[dict]:
    chunks = []
    for c in spec["chapters"]:
        for li, ln in enumerate(c["lines"]):
            for piece in split_text(ln["text"]):
                chunks.append({"ch": c["index"], "line": li, "spk": ln["spk"], "text": piece,
                               "voice": spec["voices"].get(ln["spk"], spec["voices"]["화자"])})
    for i, ck in enumerate(chunks):
        ck["i"] = i
    return chunks


# ── ② 합성 ────────────────────────────────────────────────────
def wav_dur(path: str) -> float:
    with wave.open(path) as w:
        return w.getnframes() / float(w.getframerate())


def write_silence(path: str, sec: float):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"\x00\x00" * int(SR * sec))


def _gender_of(spec: dict, spk: str) -> str:
    if spk == "화자":
        return spec.get("narrator_gender", "F")
    for c in spec.get("characters") or []:
        if c.get("name") == spk:
            return "M" if str(c.get("gender", "F")).upper().startswith("M") else "F"
    return "F"


def _edge(text: str, wav_out: str, voice: str):
    mp3 = wav_out[:-4] + ".mp3"
    sh([sys.executable, "-m", "edge_tts", "--voice", voice, "--text", text, "--write-media", mp3])
    sh([FFMPEG, "-y", "-v", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", wav_out])


def _normalize_wav(path: str):
    """Supertonic 출력이 44.1kHz 모노 16bit 가 아니면 맞춘다(concat 은 형식이 같아야 한다)."""
    with wave.open(path) as w:
        ok = (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (SR, 1, 2)
    if not ok:
        tmp = path[:-4] + "_n.wav"
        sh([FFMPEG, "-y", "-v", "error", "-i", path, "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", tmp])
        os.replace(tmp, path)


def synth_all(spec: dict, chunks: list[dict], wd: str, tts=None) -> dict:
    """모든 조각을 합성해 ck['wav'], ck['dur'] 를 채운다. 반환: 통계."""
    if tts is None:
        import wbspark
        tts = wbspark.tts
    os.makedirs(wd, exist_ok=True)

    def one(ck):
        out = os.path.join(wd, f"c{ck['i']:04d}.wav")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return ck["i"], True                     # 재실행 시 이어 하기
        for attempt in range(3):
            if tts(ck["text"], out, ck["voice"]):
                return ck["i"], True
            time.sleep(3 + attempt * 5)
        return ck["i"], False

    t0 = time.time()
    failed = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for n, (i, ok) in enumerate(ex.map(one, chunks), 1):
            if not ok:
                failed.append(i)
            if n % 25 == 0 or n == len(chunks):
                print(f"   🎙️ 합성 {n}/{len(chunks)} · 실패 {len(failed)} · {time.time() - t0:.0f}s", flush=True)
    if len(failed) > max(3, int(len(chunks) * MAX_FALLBACK)):
        raise RuntimeError(f"Supertonic 실패 {len(failed)}/{len(chunks)} — 목소리가 섞이므로 중단")
    for i in failed:                                  # 소수만 edge-tts 로 메운다
        ck = chunks[i]
        pool = EDGE_VOICE[_gender_of(spec, ck["spk"])]
        _edge(ck["text"], os.path.join(wd, f"c{i:04d}.wav"), pool[0])
        print(f"   ⚠️ 조각 {i} edge-tts 로 대체")
    for ck in chunks:
        ck["wav"] = os.path.join(wd, f"c{ck['i']:04d}.wav")
        _normalize_wav(ck["wav"])
        ck["dur"] = wav_dur(ck["wav"])
    return {"chunks": len(chunks), "fallback": len(failed), "tts_sec": round(time.time() - t0)}


# ── 타임라인 ──────────────────────────────────────────────────
def timeline(chunks: list[dict]) -> tuple[list[dict], float]:
    """원본 속도 기준 시각을 매긴다. 2장부터는 장 앞에 GAP_CHAPTER(장 제목 카드).
    반환: (장별 [{ch, card_start, start}], 전체 길이) — 모두 ★최종(TEMPO 적용) 시각."""
    t, prev, chaps = 0.0, None, []
    for ck in chunks:
        if prev is None or ck["ch"] != prev["ch"]:
            card = t
            if prev is not None:
                t += GAP_CHAPTER
            chaps.append({"ch": ck["ch"], "card_start": card, "start": t})
        elif prev is not None:
            t += GAP_SAME if (ck["spk"] == prev["spk"]) else GAP_SWITCH
        ck["gap_before"] = t - (prev["t0"] + prev["dur"]) if prev is not None else 0.0
        ck["t0"] = t
        t += ck["dur"]
        prev = ck
    total = t + 1.5
    for ck in chunks:
        ck["start"], ck["end"] = ck["t0"] / TEMPO, (ck["t0"] + ck["dur"]) / TEMPO
    for c in chaps:
        c["card_start"] /= TEMPO
        c["start"] /= TEMPO
    return chaps, total / TEMPO


def build_audio(chunks: list[dict], wd: str, out_m4a: str):
    sil = {}

    def silence(sec):
        key = round(sec, 2)
        if key not in sil:
            p = os.path.join(wd, f"sil_{key:.2f}.wav")
            write_silence(p, key)
            sil[key] = p
        return sil[key]

    lst = os.path.join(wd, "audio_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for ck in chunks:
            if ck["gap_before"] > 0.01:
                f.write(f"file '{os.path.abspath(silence(ck['gap_before']))}'\n")
            f.write(f"file '{os.path.abspath(ck['wav'])}'\n")
        f.write(f"file '{os.path.abspath(silence(1.5))}'\n")
    sh([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
        "-af", f"atempo={TEMPO},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "1",
        "-c:a", "aac", "-b:a", "128k", out_m4a])


# ── 자막 · 목차 ───────────────────────────────────────────────
def _ts(sec: float, srt: bool = True) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{int(h)}:{int(m):02d}:{int(s):02d}" if h >= 1 else f"{int(m):02d}:{int(s):02d}"


def build_srt(chunks: list[dict], out: str):
    """조각을 문장으로 나눠 글자 수 비례로 시간을 나눈다. 대사는 앞에 (이름)."""
    cues = []
    for ck in chunks:
        sents = [s for s in re.split(r"(?<=[.!?…])\s+", ck["text"]) if s.strip()] or [ck["text"]]
        total = sum(len(s) for s in sents) or 1
        t = ck["start"]
        span = ck["end"] - ck["start"]
        for s in sents:
            d = span * len(s) / total
            txt = s if ck["spk"] == "화자" else f"({ck['spk']}) {s}"
            cues.append((t, t + d, txt))
            t += d
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for n, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{n}\n{_ts(a)} --> {_ts(b)}\n{txt}\n\n")
    return len(cues)


def chapters_text(spec: dict, chaps: list[dict]) -> str:
    titles = {c["index"]: c["title"] for c in spec["chapters"]}
    lines = []
    for n, c in enumerate(chaps):
        t = 0.0 if n == 0 else c["card_start"]
        lines.append(f"{_ts(t, srt=False)} {c['ch']}장 · {titles.get(c['ch'], '')}".rstrip(" ·"))
    return "\n".join(lines)


# ── ③ 그림 ────────────────────────────────────────────────────
def _cover(src: str, dst: str):
    from PIL import Image, ImageOps
    img = ImageOps.fit(Image.open(src).convert("RGB"), (W, H), Image.LANCZOS)
    img.save(dst, "JPEG", quality=90)


def gen_image(prompt: str, out_jpg: str, seed: int = 0) -> bool:
    raw = out_jpg[:-4] + "_raw.png"
    ok = False
    try:
        import wbspark
        ok = wbspark.generate_image(LOOK + prompt, raw, aspect="16:9", no_llm=True)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ Spark 그림 예외: {e}")
    if not ok:
        try:
            import imagegen
            ok = bool(imagegen.flux_image(LOOK + prompt, raw, 1344, 768, seed=seed))
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ FLUX 예외: {e}")
    if ok and os.path.exists(raw):
        _cover(raw, out_jpg)
        return True
    return False


def chapter_card(bg_jpg: str | None, n: int, title: str, out: str):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    import thumbnail as TH
    if bg_jpg and os.path.exists(bg_jpg):
        img = Image.open(bg_jpg).convert("RGB").filter(ImageFilter.GaussianBlur(14))
        img = ImageEnhance.Brightness(img).enhance(0.35)
    else:
        img = Image.new("RGB", (W, H), (18, 16, 20))
    d = ImageDraw.Draw(img)
    f1, f2 = TH._load_font(64), TH._load_font(112)
    a = f"{n}장"
    d.text(((W - d.textlength(a, font=f1)) / 2, 380), a, font=f1, fill=(255, 212, 59))
    for k, ln in enumerate(TH._wrap(d, title, f2, W - 240)[:2]):
        d.text(((W - d.textlength(ln, font=f2)) / 2, 480 + k * 140), ln, font=f2, fill=(255, 255, 255))
    img.save(out, "JPEG", quality=90)


def make_images(spec: dict, wd: str) -> dict:
    """장 번호 → 그림 경로 목록. 실패한 그림은 같은 장(없으면 앞 장) 그림으로 메운다."""
    os.makedirs(wd, exist_ok=True)
    by_ch: dict[int, list[str]] = {}
    for k, im in enumerate(spec.get("images") or []):
        out = os.path.join(wd, f"img_{k:02d}.jpg")
        if os.path.exists(out) or gen_image(im.get("prompt", ""), out, seed=k):
            by_ch.setdefault(int(im.get("chapter", 1)), []).append(out)
        print(f"   🖼️ 그림 {k + 1}/{len(spec.get('images') or [])} {'✓' if os.path.exists(out) else '✗'}", flush=True)
    last = None
    for c in spec["chapters"]:
        if not by_ch.get(c["index"]) and last:
            by_ch[c["index"]] = [last]
        if by_ch.get(c["index"]):
            last = by_ch[c["index"]][-1]
    return by_ch


# ── ④ 영상 ────────────────────────────────────────────────────
def video_segments(spec: dict, chaps: list[dict], total: float, imgs: dict, wd: str) -> list[tuple]:
    """(그림, 시작, 끝) 목록. 2장부터 장 앞 GAP_CHAPTER 동안 장 제목 카드."""
    titles = {c["index"]: c["title"] for c in spec["chapters"]}
    segs = []
    blank = os.path.join(wd, "blank.jpg")
    for n, c in enumerate(chaps):
        end = chaps[n + 1]["card_start"] if n + 1 < len(chaps) else total
        pics = imgs.get(c["ch"]) or []
        if n > 0:
            card = os.path.join(wd, f"card_{c['ch']:02d}.jpg")
            chapter_card(pics[0] if pics else None, c["ch"], titles.get(c["ch"], ""), card)
            segs.append((card, c["card_start"], c["start"]))
        if not pics:
            if not os.path.exists(blank):
                chapter_card(None, c["ch"], "", blank)
            pics = [blank]
        span = (end - c["start"]) / len(pics)
        for k, p in enumerate(pics):
            segs.append((p, c["start"] + k * span, c["start"] + (k + 1) * span))
    return segs


def build_video(segs: list[tuple], audio: str, out_mp4: str, wd: str):
    lst = os.path.join(wd, "video_list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p, a, b in segs:
            f.write(f"file '{os.path.abspath(p)}'\nduration {max(0.1, b - a):.3f}\n")
        f.write(f"file '{os.path.abspath(segs[-1][0])}'\n")        # concat 은 마지막 항목을 한 번 더
    sh([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", audio,
        "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "25",
        "-c:a", "copy", "-shortest", "-movflags", "+faststart", out_mp4])


def thumbnail_for(spec: dict, imgs: dict, wd: str, out: str) -> str | None:
    import thumbnail as TH
    bg = os.path.join(wd, "thumb_bg.jpg")
    if not (spec.get("thumbnail_prompt") and gen_image(spec["thumbnail_prompt"], bg, seed=99)):
        first = next((p for c in sorted(imgs) for p in imgs[c]), None)
        if not first:
            return None
        shutil.copy(first, bg)
    try:
        return TH._overlay_title(bg, spec.get("thumbnail_text", ""), out, accent="#FFD43B")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 썸네일 문구 실패 → 그림만: {e}")
        shutil.copy(bg, out)
        return out


def render(spec: dict, out_dir: str, wd: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(wd, exist_ok=True)
    base = os.path.join(out_dir, f"{spec['date']}_drama")
    chunks = plan_chunks(spec)
    print(f"   📜 {spec['stats']['chars']:,}자 → 조각 {len(chunks)}개 · 목소리 {spec['voices']}")
    tts_stat = synth_all(spec, chunks, os.path.join(wd, "tts"))
    chaps, total = timeline(chunks)
    audio = base + "_audio.m4a"
    build_audio(chunks, os.path.join(wd, "tts"), audio)
    imgs = make_images(spec, os.path.join(wd, "img"))
    segs = video_segments(spec, chaps, total, imgs, os.path.join(wd, "img"))
    video = base + ".mp4"
    build_video(segs, audio, video, os.path.join(wd, "img"))
    srt = base + ".srt"
    n_cues = build_srt(chunks, srt)
    thumb = thumbnail_for(spec, imgs, os.path.join(wd, "img"), base + "_thumb.jpg")
    res = {"video": video, "thumb": thumb, "srt": srt, "chapters": chapters_text(spec, chaps),
           "duration_min": round(total / 60, 1), "cues": n_cues, "images": sum(len(v) for v in imgs.values()),
           **tts_stat}
    print(f"✅ {video} · {res['duration_min']}분 · 그림 {res['images']}장 · 자막 {n_cues}개 · 합성 {tts_stat['tts_sec']}초")
    return res
