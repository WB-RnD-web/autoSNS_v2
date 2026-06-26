#!/usr/bin/env python3
"""M3 — Path A 완성본: 실제 스토리보드 JSON → 완성 쇼츠 1편.

흐름(샷별):
  voice(edge-tts) → dur=voice+0.4 → bed HTML 생성 → HyperFrames render(mp4)
  → assemble(자막 drawtext + 음성, v1 포팅) → shot mp4
마지막: 모든 shot을 v1 concat_xfade_cmd 방식(xfade+acrossfade)으로 이어붙임 → 완성 mp4.

v1 재사용: voice 설정, assemble 비디오경로, xfade 이어붙이기 = 전부 v1 그대로.
v2 신규: 베드(HyperFrames 애니메이션) + 하단배너 크롭 + 샷별 화자 강조.

BGM: notes "배경음 없음" 존중 → 기본 off (별도 오디오 트랙 없음).

사용: python build.py            # 전체
      python build.py --shots 2  # 앞 2샷만(빠른 검증)
      python build.py --skip-bed # 베드 재렌더 생략(이미 있으면)
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = r"C:\Users\zxczx\tools\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
STORYBOARD = os.path.join(HERE, "..", "..", "docs", "samples",
                          "2026-06-26_economy_storyboard.json")
FONT = "fonts/Pretendard-Bold.otf"   # 상대경로(Windows drawtext 경로 회피)

W, H, FPS = 1080, 1920, 30
XFADE = 0.3
SPEAKER_COLOR = {"별하": "#FFD23F", "별이": "#5BC8FF"}

# v1 voice.py 설정 그대로
VOICES = {
    "별이": {"voice": "ko-KR-HyunsuMultilingualNeural", "rate": "-2%", "pitch": "+0Hz"},
    "별하": {"voice": "ko-KR-SunHiNeural", "rate": "+0%", "pitch": "+0Hz"},
}


# ── 베드 HTML 템플릿 (화자/길이 파라미터) ─────────────────────
BED_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { margin:0; width:1080px; height:1920px; overflow:hidden; background:#0A0808; }
#frame, #sway { position:absolute; inset:0; }
#sway { transform-origin:50% 60%; }
#kb {
  position:absolute; inset:0;
  background-image:url("assets/twoshot.png");
  background-size:cover; background-position:center top;
  transform-origin:__ORIGINX__% 12%;   /* 상단 기준 줌 → 하단 배너 크롭 + 화자 강조 */
  will-change:transform;
}
#spotlight {
  position:absolute; __SPOTSIDE__: 40px; top:560px;
  width:560px; height:760px; border-radius:50%;
  background:radial-gradient(circle, rgba(217,119,87,0.40) 0%, rgba(217,119,87,0) 62%);
  filter:blur(22px); mix-blend-mode:screen;
}
#grade {
  position:absolute; inset:0; pointer-events:none;
  background:
    radial-gradient(70% 50% at __SPOTX__% 50%, rgba(217,119,87,0.10) 0%, rgba(217,119,87,0) 60%),
    radial-gradient(120% 90% at 50% 42%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%);
}
/* 하단 잉크 밴드: 구워진 배너 완전 차단 + 자막 backing(브랜드 톤). 하단부는 완전 불투명. */
#lowerband {
  position:absolute; left:0; right:0; bottom:0; height:480px; pointer-events:none;
  background:linear-gradient(180deg, rgba(10,8,8,0) 0%, rgba(10,8,8,0.85) 40%, #0A0808 72%, #0A0808 100%);
}
#grain {
  position:absolute; inset:-50%; width:200%; height:200%; opacity:0.07; pointer-events:none;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1080" data-height="1920">
  <div id="frame" class="clip" data-start="0" data-duration="__DUR__" data-track-index="0">
    <div id="sway"><div id="kb"></div></div>
  </div>
  <div id="spotlight" class="clip" data-start="0" data-duration="__DUR__" data-track-index="1"></div>
  <div id="grade" class="clip" data-start="0" data-duration="__DUR__" data-track-index="2"></div>
  <div id="lowerband" class="clip" data-start="0" data-duration="__DUR__" data-track-index="3"></div>
  <div id="grain" class="clip" data-start="0" data-duration="__DUR__" data-track-index="4"></div>
</div>
<script>
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused:true });
const D = __DUR__;
// 켄번즈: base scale 크게(하단 배너 크롭) + 화자 쪽 드리프트
tl.fromTo("#kb", { scale:1.40, xPercent:__KBX0__, yPercent:0 },
                 { scale:1.54, xPercent:__KBX1__, yPercent:1.2, duration:D, ease:"none" }, 0);
// 미세 스웨이(회전만)
const swayCycle = 2.3;
tl.fromTo("#sway", { rotation:-0.4 },
  { rotation:0.4, duration:swayCycle/2, ease:"sine.inOut", yoyo:true,
    repeat: Math.max(0, Math.floor(D/swayCycle)-1) }, 0);
// 진입 페이드
tl.from("#frame", { opacity:0, duration:0.5, ease:"power2.out" }, 0);
// 화자 스포트라이트 호흡
tl.fromTo("#spotlight", { opacity:0 }, { opacity:0.85, duration:0.6, ease:"power2.out" }, 0.3);
const spotCycle = 1.5;
tl.to("#spotlight", { opacity:0.45, scale:1.06, duration:spotCycle/2, ease:"sine.inOut",
  yoyo:true, repeat: Math.max(0, Math.floor((D-0.9)/spotCycle)-1),
  transformOrigin:"__SPOTX__% 55%" }, 0.9);
window.__timelines["main"] = tl;
</script></body></html>
"""


def sh(cmd, **kw):
    """실패 시 캡처된 stdout/stderr를 출력하고 재발생."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {cmd}\n")
        if e.stdout:
            sys.stderr.write(f"--- stdout ---\n{e.stdout[-2000:]}\n")
        if e.stderr:
            sys.stderr.write(f"--- stderr ---\n{e.stderr[-2000:]}\n")
        raise


def probe_dur(path: str) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def speaker_name(s: str) -> str:
    for n in SPEAKER_COLOR:
        if n in s:
            return n
    return "별하"


def wrap(text: str, width: int = 16) -> str:
    out, cur = [], ""
    for w in text.split(" "):
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return "\n".join(out)


def gen_voice(line: str, speaker: str, out_mp3: str) -> None:
    cfg = VOICES[speaker]
    sh([sys.executable, "-m", "edge_tts", "--voice", cfg["voice"],
        f"--rate={cfg['rate']}", f"--pitch={cfg['pitch']}",
        "--text", line, "--write-media", out_mp3],
       capture_output=True, text=True)


def gen_bed_html(dur: float, speaker: str) -> str:
    right = (speaker == "별하")
    html = BED_TEMPLATE
    repl = {
        "__DUR__": f"{dur:.2f}",
        "__ORIGINX__": "68" if right else "32",
        "__SPOTSIDE__": "right" if right else "left",
        "__SPOTX__": "75" if right else "25",
        "__KBX0__": "1.5" if right else "-1.5",
        "__KBX1__": "-2.5" if right else "2.5",
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    return html


def render_bed(html: str, bedproj: str, out_mp4: str) -> None:
    with open(os.path.join(bedproj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    # PATH는 main()에서 os.environ에 ffmpeg 추가 완료 → env= 전달 안 함(node 경로 상속 유지)
    sh(f'npx --yes hyperframes render --output "{out_mp4}"', cwd=bedproj, shell=True)


def assemble_shot(bed_mp4: str, audio: str, caption: str, credit: str,
                  speaker: str, dur: float, out_mp4: str, tmpdir: str) -> None:
    color = SPEAKER_COLOR.get(speaker, "white")
    cap_file = os.path.join(tmpdir, "cap.txt").replace("\\", "/")
    cr_file = os.path.join(tmpdir, "credit.txt").replace("\\", "/")
    with open(cap_file, "w", encoding="utf-8") as f:
        f.write(wrap(caption))
    with open(cr_file, "w", encoding="utf-8") as f:
        f.write(credit)
    # 자막팝(동적 fontsize)은 Linux 전용(로컬 Windows ffmpeg 크래시) → CAPTION_POP=1 시 활성
    fs = ("if(lt(t,0.25),46+(56-46)*(1-t/0.25),46)"
          if os.environ.get("CAPTION_POP") == "1" else "46")
    draw = (f"drawtext=fontfile='{FONT}':textfile='{cap_file}':expansion=none:"
            f"fontcolor={color}:fontsize='{fs}':line_spacing=10:"
            f"box=1:boxcolor=black@0.5:boxborderw=20:x=(w-text_w)/2:y=h-text_h-160")
    draw += (f",drawtext=fontfile='{FONT}':textfile='{cr_file}':expansion=none:"
             f"fontcolor=white@0.85:fontsize=28:shadowcolor=black@0.7:shadowx=2:shadowy=2:"
             f"x=w-text_w-28:y=46")
    vchain = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"setsar=1,fps={FPS},{draw}")
    sh([FFMPEG, "-y", "-i", bed_mp4, "-i", audio,
        "-filter_complex", f"[0:v]{vchain}[v];[1:a]apad[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
        "-r", str(FPS), "-pix_fmt", "yuv420p", out_mp4],
       capture_output=True, text=True)


def concat_xfade(parts: list, durs: list, out_mp4: str) -> None:
    """v1 concat_xfade_cmd 포팅 (xfade+acrossfade)."""
    if len(parts) == 1:
        sh([FFMPEG, "-y", "-i", parts[0], "-c", "copy", out_mp4],
           capture_output=True, text=True)
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
            "-r", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_mp4]
    sh(cmd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=int, default=0, help="앞 N샷만(0=전체)")
    ap.add_argument("--skip-bed", action="store_true", help="베드 재렌더 생략")
    args = ap.parse_args()
    os.chdir(HERE)
    # hyperframes render가 ffmpeg를 PATH에서 찾으므로 추가(키 케이스 안전하게 PATH 사용)
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + os.path.dirname(FFMPEG)

    for d in ("beds", "voices", "shots", "out", "tmp"):
        os.makedirs(d, exist_ok=True)
    bedproj = os.path.join(HERE, "bedproj")

    with open(STORYBOARD, encoding="utf-8") as f:
        sb = json.load(f)
    shots = sb["shots"]
    if args.shots:
        shots = shots[:args.shots]

    parts, durs = [], []
    for s in shots:
        n = s["n"]
        sp = speaker_name(s.get("speaker", ""))
        line = s["line"]
        print(f"[shot {n}] {sp}: {line[:24]}…")
        # 1) voice
        voice = f"voices/voice_{n}.mp3"
        gen_voice(line, sp, voice)
        dur = round(probe_dur(voice) + 0.4, 2)
        # 2) bed
        bed = os.path.join(HERE, "beds", f"bed_{n}.mp4")
        if not (args.skip_bed and os.path.exists(bed)):
            render_bed(gen_bed_html(dur, sp), bedproj, bed)
        # 3) assemble shot
        shot = f"shots/shot_{n}.mp4"
        assemble_shot(bed, voice, s["caption"], sb.get("credit", ""), sp, dur, shot, "tmp")
        parts.append(os.path.join(HERE, "shots", f"shot_{n}.mp4"))
        durs.append(dur)
        print(f"   dur={dur}s -> {shot}")

    # 4) stitch
    out = os.path.join(HERE, "out", f"{sb['date']}_{sb['topic']}_final.mp4")
    print(f"\n[stitch] {len(parts)} shots, total ~{round(sum(durs))}s, xfade={XFADE}")
    concat_xfade(parts, durs, out)
    print(f"OK -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
