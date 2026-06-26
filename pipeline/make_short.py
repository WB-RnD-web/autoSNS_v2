#!/usr/bin/env python3
"""스토리보드 JSON 1개 → 완성 쇼츠 mp4 (v2 단일 엔트리포인트).

흐름:
  ① generate_images.py (v1 재사용)  → output/assets/<date>_<topic>_twoshot.<ext>
  ② voice.py          (v1 재사용)  → output/assets/<date>_<topic>_voice_<n>.mp3
  ③ bed.render_bed    (v2 신규)    → output/assets/<date>_<topic>_twoshot_shot<n>.mp4 (샷별)
  ④ assemble          (v1 포팅)    → 샷별 자막 drawtext + 음성 → xfade 이어붙이기
                                     → output/renders/<date>_<topic>_final.mp4

v1 재사용: 이미지생성·음성·자막/타이밍/코덱/전환 로직. v2 신규: 샷별 모션 베드.
BGM: 기본 off (별도 오디오 트랙 없음 = notes "배경음 없음" 존중).

사용:
  python make_short.py --storyboard ../docs/samples/2026-06-26_economy_storyboard.json
  python make_short.py --storyboard <sb.json> --shots 2   # 앞 2샷만(검증)
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import config
import bed as bedmod

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
W, H, FPS = config.VIDEO_W, config.VIDEO_H, 30
XFADE = 0.3
FONT = os.path.join(HERE, "fonts", "Pretendard-Bold.otf")
BEDPROJ = os.path.join(HERE, "bedproj")
SPEAKER_COLOR = {"별하": "#FFD23F", "별이": "#5BC8FF"}
DEFAULT_COLOR = "white"


def _bin(name: str) -> str:
    """ffmpeg/ffprobe 경로 해결: PATH 우선, 없으면 로컬 tools 폴백."""
    p = shutil.which(name)
    if p:
        return p
    local = rf"C:\Users\zxczx\tools\ffmpeg-8.1.1-essentials_build\bin\{name}.exe"
    return local if os.path.exists(local) else name


FFMPEG = _bin("ffmpeg")
FFPROBE = _bin("ffprobe")


def sh(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {cmd}\n{(e.stdout or '')[-1200:]}\n{(e.stderr or '')[-1200:]}\n")
        raise


def probe_dur(path: str) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def speaker_of(s: str) -> str:
    for n in SPEAKER_COLOR:
        if n in s:
            return n
    return "별하"


def wrap(text: str, width: int = 16) -> str:
    """v1 assemble.wrap 동일."""
    out, cur = [], ""
    for w in text.split(" "):
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return "\n".join(out)


def find_asset(date: str, topic: str, asset_id: str, shot_n: int) -> str | None:
    """샷별 베드(<date>_<topic>_<asset>_shot<n>.mp4) 우선, 없으면 공용 에셋(v1 호환)."""
    tp = f"{topic}_" if topic else ""
    cands = [config.ASSETS_DIR / f"{date}_{tp}{asset_id}_shot{shot_n}.mp4"]
    for ext in ("mp4", "mov", "png", "jpg", "jpeg", "webp"):
        cands.append(config.ASSETS_DIR / f"{date}_{tp}{asset_id}.{ext}")
    for p in cands:
        if p.exists():
            return str(p)
    return None


def find_voice(date: str, topic: str, n: int) -> str | None:
    tp = f"{topic}_" if topic else ""
    p = config.ASSETS_DIR / f"{date}_{tp}voice_{n}.mp3"
    return str(p) if p.exists() else None


def shot_cmd(bed_mp4: str, dur: float, cap_file: str, credit_file: str | None,
             audio: str | None, out: str, speaker: str) -> list:
    """v1 assemble.shot_clip_cmd 의 video(is_img=False) 경로 포팅 + Pretendard + faststart."""
    color = SPEAKER_COLOR.get(speaker, DEFAULT_COLOR)
    base_fs, pop_fs = 46, 56
    # 자막팝(동적 fontsize): Linux apt ffmpeg는 정상(v1). 로컬 Windows static 빌드는 크래시 → 정적.
    fs = (f"if(lt(t,0.25),{base_fs}+({pop_fs}-{base_fs})*(1-t/0.25),{base_fs})"
          if os.environ.get("CAPTION_POP") == "1" else str(base_fs))
    # ffmpeg 필터그래프 내 경로: 슬래시화 + 드라이브 콜론 이스케이프(C\:/...) — 콜론은 옵션 구분자
    def _fp(p: str) -> str:
        return p.replace("\\", "/").replace(":", "\\:")
    font = _fp(FONT)
    cap = _fp(cap_file)
    draw = (f"drawtext=fontfile='{font}':textfile='{cap}':expansion=none:"
            f"fontcolor={color}:fontsize='{fs}':line_spacing=10:"
            f"box=1:boxcolor=black@0.5:boxborderw=20:x=(w-text_w)/2:y=h-text_h-160")
    if credit_file:
        cr = _fp(credit_file)
        draw += (f",drawtext=fontfile='{font}':textfile='{cr}':expansion=none:"
                 f"fontcolor=white@0.85:fontsize=28:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
                 f"x=w-text_w-28:y=46")
    vchain = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"setsar=1,fps={FPS},{draw}")
    cmd = [FFMPEG, "-y", "-i", bed_mp4]
    if audio:
        cmd += ["-i", audio, "-filter_complex", f"[0:v]{vchain}[v];[1:a]apad[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-filter_complex", f"[0:v]{vchain}[v]", "-map", "[v]", "-map", "1:a"]
    cmd += ["-t", f"{dur:.2f}", "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-r", str(FPS), "-pix_fmt", "yuv420p", out]
    return cmd


def concat_xfade(parts: list, durs: list, out: str, tmp: str) -> None:
    """v1 concat_xfade_cmd 포팅 (xfade+acrossfade), 단일 샷은 단순 copy."""
    if len(parts) == 1:
        sh([FFMPEG, "-y", "-i", parts[0], "-c", "copy", "-movflags", "+faststart", out])
        return
    cmd = [FFMPEG, "-y"]
    for p in parts:
        cmd += ["-i", p]
    fc, offset = [], 0.0
    vlab, alab = "[0:v]", "[0:a]"
    for i in range(1, len(parts)):
        offset += durs[i - 1] - XFADE
        nv, na = f"[v{i}]", f"[a{i}]"
        fc.append(f"{vlab}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.2f}{nv}")
        fc.append(f"{alab}[{i}:a]acrossfade=d={XFADE}{na}")
        vlab, alab = nv, na
    cmd += ["-filter_complex", ";".join(fc), "-map", vlab, "-map", alab,
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-r", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    sh(cmd)


def run_stage(script: str, sb_path: str) -> bool:
    return subprocess.run([PY, os.path.join(HERE, script), "--storyboard", sb_path]).returncode == 0


def make_short(sb_path: str, max_shots: int = 0, skip_bed: bool = False,
               quality: str = "standard") -> str:
    config.ensure_dirs()
    # render가 ffmpeg를 PATH에서 찾도록 보장
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + os.path.dirname(FFMPEG)

    with open(sb_path, encoding="utf-8") as f:
        sb = json.load(f)
    date, topic = sb["date"], sb.get("topic", "")
    shots = sb["shots"][:max_shots] if max_shots else sb["shots"]
    credit = sb.get("credit", "")

    # ① 이미지(투샷) — v1 재사용
    print("① generate_images")
    run_stage("generate_images.py", sb_path)
    # ② 음성 — v1 재사용
    print("② voice (edge-tts)")
    run_stage("voice.py", sb_path)

    # 투샷 이미지 확보 → bedproj
    tp = f"{topic}_" if topic else ""
    twoshot = None
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = config.ASSETS_DIR / f"{date}_{tp}twoshot.{ext}"
        if p.exists():
            twoshot = str(p); break
    if not twoshot:
        raise RuntimeError("투샷 이미지를 찾을 수 없음 (generate_images 실패?)")
    bedmod.ensure_twoshot(BEDPROJ, twoshot)

    tmp = tempfile.mkdtemp(prefix="autosns2_")
    credit_file = None
    if credit:
        credit_file = os.path.join(tmp, "credit.txt")
        open(credit_file, "w", encoding="utf-8").write(credit)

    parts, durs = [], []
    for s in shots:
        n = s["n"]
        sp = speaker_of(s.get("speaker", ""))
        voice = find_voice(date, topic, n)
        dur = round(probe_dur(voice) + 0.4, 2) if voice else float(s["duration"])
        # ③ 샷별 베드 — v2 신규
        bed_out = str(config.ASSETS_DIR / f"{date}_{tp}twoshot_shot{n}.mp4")
        if not (skip_bed and os.path.exists(bed_out)):
            print(f"③ bed shot{n} ({sp}, {dur}s)")
            bedmod.render_bed(bedmod.bed_html(dur, sp), BEDPROJ, bed_out, quality=quality)
        # ④ 샷 합성 — v1 포팅
        src = find_asset(date, topic, s["asset"], n)
        cap_file = os.path.join(tmp, f"cap{n}.txt")
        open(cap_file, "w", encoding="utf-8").write(wrap(s["caption"]))
        shot_out = os.path.join(tmp, f"shot{n}.mp4")
        sh(shot_cmd(src, dur, cap_file, credit_file, voice, shot_out, sp))
        parts.append(shot_out); durs.append(dur)

    suffix = f"_{topic}" if topic else ""
    out = str(config.RENDERS_DIR / f"{date}{suffix}_final.mp4")
    print(f"④ stitch {len(parts)} shots (~{round(sum(durs))}s, xfade={XFADE})")
    concat_xfade(parts, durs, out, tmp)
    print(f"✅ {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="스토리보드 1개 → 완성 쇼츠 mp4")
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--shots", type=int, default=0, help="앞 N샷만(0=전체)")
    ap.add_argument("--skip-bed", action="store_true")
    ap.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    args = ap.parse_args()
    config.load_dotenv()
    make_short(args.storyboard, args.shots, args.skip_bed, args.quality)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
