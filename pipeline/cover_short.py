#!/usr/bin/env python3
"""쇼츠(9:16) 커버 이미지 생성 — 인스타/쓰레드 미리보기(검은 화면) 대응.

배경: 모션그래픽 쇼츠 mp4는 첫 프레임이 검정(#0A0808 배경 + 첫 장면 페이드인)이라
      인스타 릴스/쓰레드가 그 프레임으로 미리보기를 만들어 '검은 화면'이 된다.
      (유튜브 쇼츠는 자체적으로 중간 프레임을 골라줘서 무관.)

해결: 소설 썸네일(thumbnail.py, 16:9)과 같은 방식으로 qwen-image 배경 + 후킹 문구를
      쇼츠 세로 규격(1080x1920)으로 합성한다. 그 커버를
        - 인스타: cover_url 로 지정
        - 쓰레드: 커버 API 가 없어 커버를 영상 '첫 프레임'으로 굽는다(prepend_cover)
      루틴이 thumbnail_hook 을 안 줬거나 qwen 이 느리면 → grab_frame 으로 영상 프레임 폴백
      (절대 검은 미리보기로 안 나가게).

루틴 명시 필드(스토리보드 top-level, 없으면 platforms.youtube 아래도 인식):
  thumbnail_hook  = 커버 배경으로 그릴 장면(영어 프롬프트). 없으면 build_cover→None(프레임 폴백)
  thumbnail_text  = 커버에 크게 얹을 후킹 문구. 없으면 hook_title → headline
  thumbnail_style = 강제 스타일 프리셋(비우면 news). news 외엔 thumbnail.py PRESETS 재사용

best-effort: 어떤 단계든 실패하면 None/False → 호출측(run_pipeline.do_social)이 폴백/스킵.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys

import wbspark

W, H = 1080, 1920  # 9:16 (config.VIDEO_W/H 와 동일)

# 뉴스/에디토리얼 프리셋 — 소설 art 프리셋(darkfantasy 등)은 뉴스에 안 맞아 별도.
NEWS_PRESET = ("modern editorial news key visual, bold cinematic photojournalism, "
               "dramatic high-contrast lighting, clean premium magazine-cover composition")

TECH = ("9:16 vertical composition, poster key art, subject in upper two-thirds, "
        "highly detailed, no text, no letters, no watermark")

CORAL = "#D97757"  # 브랜드 액센트(모션그래픽과 동일)


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _fields(sb: dict) -> tuple[str, str, str]:
    """스토리보드에서 커버 필드 추출(top-level 우선, platforms.youtube 폴백)."""
    yt = sb.get("platforms", {}).get("youtube", {}) if isinstance(sb.get("platforms"), dict) else {}

    def pick(k: str) -> str:
        return (sb.get(k) or (yt.get(k) if isinstance(yt, dict) else "") or "").strip()

    hook = pick("thumbnail_hook")
    text = (pick("thumbnail_text")
            or (sb.get("hook_title") or "").strip()
            or (sb.get("headline") or "").strip())
    style = pick("thumbnail_style").lower()
    return hook, text, style


def _style_prompt(style: str) -> str:
    if not style or style == "news":
        return NEWS_PRESET
    try:
        from thumbnail import PRESETS
        return PRESETS.get(style, NEWS_PRESET)
    except Exception:  # noqa: BLE001
        return NEWS_PRESET


def _overlay(bg_path: str, text: str, out_path: str) -> str:
    """9:16 배경에 후킹 문구를 또렷하게 오버레이(하단 스크림 + 자동 폰트축소)."""
    from PIL import Image, ImageDraw, ImageOps
    from thumbnail import _load_font, _wrap  # 폰트/줄바꿈 로직 재사용

    img = Image.open(bg_path).convert("RGB")
    img = ImageOps.fit(img, (W, H), Image.LANCZOS)  # cover-crop 중앙

    # 하단 스크림(가독성): 아래로 갈수록 어둡게. 상단도 살짝 톤다운.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    top = int(H * 0.50)
    for y in range(top, H):
        a = int(230 * (y - top) / (H - top))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, min(230, a)))
    tcap = int(H * 0.16)
    for y in range(0, tcap):
        a = int(90 * (1 - y / tcap))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, min(90, a)))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    draw = ImageDraw.Draw(img)
    if text:
        max_w = int(W * 0.86)
        for size in (128, 116, 104, 92, 80, 68, 60):
            font = _load_font(size)
            lines = _wrap(draw, text, font, max_w)
            if len(lines) <= 4:
                break
        line_h = int(size * 1.16)
        total_h = line_h * len(lines)
        y = int(H * 0.86) - total_h
        # 코랄 액센트 바(브랜드 식별)
        bar_w, bar_h = 132, 12
        draw.rounded_rectangle(
            [(W - bar_w) // 2, y - 44, (W + bar_w) // 2, y - 44 + bar_h],
            radius=6, fill=CORAL)
        stroke = max(5, size // 12)
        for ln in lines:
            w = draw.textlength(ln, font=font)
            x = (W - w) / 2
            draw.text((x, y), ln, font=font, fill=(255, 255, 255),
                      stroke_width=stroke, stroke_fill=(0, 0, 0))
            y += line_h

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=90)  # 1080x1920 JPEG → IG cover_url 8MB 제한 이내
    return out_path


def build_cover(sb: dict, out_path: str, workdir: str, timeout_sec: int = 300) -> str | None:
    """루틴이 준 thumbnail_hook 으로 9:16 커버 생성. hook 없거나 실패 시 None(→프레임 폴백)."""
    hook, text, style = _fields(sb)
    if not hook:
        print("   ⏭️  쇼츠 커버 스킵 — thumbnail_hook 없음(영상 프레임 폴백)")
        return None
    try:
        from PIL import Image  # noqa: F401 — 설치 확인
    except ImportError:
        sys.stderr.write("[warn] Pillow 미설치 — 커버 스킵(pip install pillow)\n")
        return None

    os.makedirs(workdir, exist_ok=True)
    raw = os.path.join(workdir, "cover_raw.png")
    prompt = f"{hook}. {_style_prompt(style)}, {TECH}"
    print(f"   🎨 쇼츠 커버 배경 생성(qwen-image)… (최대 {max(1, timeout_sec // 60)}분)")
    if not wbspark.generate_image(prompt, raw, timeout_sec=timeout_sec):
        print("   ⏭️  커버 배경 생성 실패/타임아웃(영상 프레임 폴백)")
        return None
    try:
        p = _overlay(raw, text, out_path)
        print(f"   🖼️  쇼츠 커버 완성: {os.path.basename(p)}")
        return p
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 커버 오버레이 실패 → 스킵: {e}\n")
        return None


def grab_frame(video_path: str, out_path: str, at_sec: float = 2.0) -> str | None:
    """폴백 커버 — 영상에서 프레임 1장 추출(후킹 문구 다 뜬 ~2s 지점 = 검은 프레임 회피)."""
    ff = _ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    try:
        r = subprocess.run(
            [ff, "-y", "-ss", f"{at_sec:.2f}", "-i", video_path,
             "-frames:v", "1", "-q:v", "2", out_path],
            capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"   🖼️  폴백 커버(영상 {at_sec:.0f}s 프레임): {os.path.basename(out_path)}")
            return out_path
        sys.stderr.write(f"[warn] 프레임 추출 실패: {(r.stderr or '')[-300:]}\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 프레임 추출 예외: {e}\n")
    return None


def prepend_cover(video_path: str, cover_img: str, out_path: str, hold_sec: float = 0.7) -> str | None:
    """커버를 영상 맨 앞 hold_sec 초 정지 프레임으로 붙임(쓰레드 미리보기용).

    쓰레드는 커버 API 가 없어 '첫 프레임'이 유일한 레버 → 굽는다. 재인코딩 발생(짧아서 무해).
    실패 시 None(→ 호출측이 원본 영상으로 진행, IG 는 cover_url 로 여전히 커버 표시).
    """
    ff = _ffmpeg()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"setsar=1,fps=30,format=yuv420p[cv];"
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[ca];"
        f"[2:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[mv];"
        f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo[ma];"
        f"[cv][ca][mv][ma]concat=n=2:v=1:a=1[outv][outa]"
    )
    cmd = [
        ff, "-y",
        "-loop", "1", "-t", f"{hold_sec:.2f}", "-i", cover_img,
        "-f", "lavfi", "-t", f"{hold_sec:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-i", video_path,
        "-filter_complex", fc,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"   🎬 커버 첫프레임 굽기 완료(+{hold_sec:.1f}s): {os.path.basename(out_path)}")
            return out_path
        sys.stderr.write(f"[warn] 커버 굽기 실패: {(r.stderr or '')[-400:]}\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 커버 굽기 예외: {e}\n")
    return None


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="쇼츠 9:16 커버 생성(테스트)")
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--out", default="cover.jpg")
    ap.add_argument("--workdir", default="_cover_work")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--grab-from", help="qwen 대신 이 영상에서 프레임 추출(폴백 테스트)")
    args = ap.parse_args()
    if args.grab_from:
        p = grab_frame(args.grab_from, args.out)
        return 0 if p else 1
    with open(args.storyboard, encoding="utf-8") as f:
        sb = json.load(f)
    p = build_cover(sb, args.out, args.workdir, timeout_sec=args.timeout)
    return 0 if p else 1


if __name__ == "__main__":
    raise SystemExit(main())
