#!/usr/bin/env python3
"""M2: HyperFrames 베드 mp4 + 음성 + 자막 → 단일 shot 완성 mp4.

v1 pipeline/assemble.py 의 '비디오 에셋' 처리 경로(shot_clip_cmd, is_img=False)를
그대로 포팅한다. 바뀐 것은:
  - 베드 소스가 정적 이미지가 아니라 HyperFrames 애니메이션 mp4 (v2 핵심)
  - 자막 폰트를 NanumGothicBold → Pretendard-Bold 로 교체 (v2 브랜드 토큰)
나머지(자막 drawtext 파라미터, 화자색, 자막팝, 출처 워터마크, 코덱)는 v1과 동일.

상대경로로 실행(=Windows ffmpeg drawtext 경로 이슈 회피) → cwd 가 이 파일 위치여야 함.
"""
from __future__ import annotations
import os
import subprocess

FFMPEG = r"C:\Users\zxczx\tools\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
FONT = "fonts/Pretendard-Bold.otf"           # 상대경로
W, H, FPS = 1080, 1920, 30

# v1 assemble.py 와 동일
SPEAKER_COLOR = {"별하": "#FFD23F", "별이": "#5BC8FF"}
DEFAULT_COLOR = "white"


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


def speaker_of(speaker: str) -> str:
    for name in SPEAKER_COLOR:
        if name in speaker:
            return name
    return ""


def build_cmd(bed_mp4: str, dur: float, cap_file: str, credit_file: str,
              audio: str, out: str, speaker: str) -> list:
    """v1 shot_clip_cmd 의 video(is_img=False) 분기 포팅."""
    color = SPEAKER_COLOR.get(speaker, DEFAULT_COLOR)
    base_fs, pop_fs = 46, 56
    # v1 자막팝(동적 fontsize). Linux(apt ffmpeg)에선 정상 동작 = 프로덕션 경로.
    pop_expr = f"if(lt(t,0.25),{base_fs}+({pop_fs}-{base_fs})*(1-t/0.25),{base_fs})"
    # ⚠️ 로컬 Windows ffmpeg 8.1.1 static 빌드는 drawtext 동적 fontsize에서 크래시(0xC0000005).
    #    M2 로컬 증명에선 정적 fontsize 사용. CAPTION_POP=1 환경변수로 강제 활성화 가능.
    fs = pop_expr if os.environ.get("CAPTION_POP") == "1" else str(base_fs)
    draw = (f"drawtext=fontfile='{FONT}':textfile='{cap_file}':expansion=none:"
            f"fontcolor={color}:fontsize='{fs}':line_spacing=10:"
            f"box=1:boxcolor=black@0.5:boxborderw=20:"
            f"x=(w-text_w)/2:y=h-text_h-160")
    if credit_file:
        draw += (f",drawtext=fontfile='{FONT}':textfile='{credit_file}':expansion=none:"
                 f"fontcolor=white@0.85:fontsize=28:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
                 f"x=w-text_w-28:y=46")
    vchain = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},setsar=1,fps={FPS},{draw}")
    cmd = [FFMPEG, "-y", "-i", bed_mp4, "-i", audio,
           "-filter_complex", f"[0:v]{vchain}[v];[1:a]apad[a]",
           "-map", "[v]", "-map", "[a]",
           "-t", f"{dur:.2f}", "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
           "-r", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    return cmd


def main() -> int:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # economy storyboard shot #1
    speaker = "별하"
    caption = "별하: 야, 나 오늘 아침에 애플 뉴스 보고 진짜 손 떨렸잖아."
    credit = "출처 뉴스핌·이투데이·9to5Mac 등"
    bed = "bed/renders/bed.mp4"
    audio = "assets/voice_1.mp3"

    # 실제 음성 길이로 dur 재계산 (v1 방식: voice + 0.4)
    probe = subprocess.run(
        [FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
         "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", audio],
        capture_output=True, text=True, check=True)
    dur = round(float(probe.stdout.strip()) + 0.4, 2)

    os.makedirs("out", exist_ok=True)
    cap_file, credit_file = "out/cap1.txt", "out/credit.txt"
    with open(cap_file, "w", encoding="utf-8") as f:
        f.write(wrap(caption))
    with open(credit_file, "w", encoding="utf-8") as f:
        f.write(credit)

    out = "out/shot1_final.mp4"
    cmd = build_cmd(bed, dur, cap_file, credit_file, audio, out, speaker_of(speaker))
    print(f"# dur={dur}s speaker={speaker} color={SPEAKER_COLOR.get(speaker)}")
    subprocess.run(cmd, check=True)
    print(f"OK -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
