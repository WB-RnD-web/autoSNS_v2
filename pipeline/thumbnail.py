#!/usr/bin/env python3
"""소설 회차별 커스텀 썸네일 생성.

흐름: 대본 한줄요약(spec.thumbnail_hook) → 장르맞춤 스타일 프리셋으로 qwen-image 배경 생성
      → 제목을 또렷한 폰트로 오버레이(글자 안 깨짐) → 1280x720 JPEG.

하드코딩 금지: 내용은 hook, 스타일은 장르(또는 spec.thumbnail_style), 제목은 회차에서.
hook 없으면 None 반환(썸네일 스킵 — YouTube 자동 프레임 사용).

best-effort: 어떤 단계든 실패하면 None 반환, 파이프라인은 계속 진행.
"""
from __future__ import annotations
import os
import sys

import wbspark

W, H = 1280, 720  # YouTube 썸네일 권장(16:9)

# ── 스타일 프리셋(아트 톤). thumbnail_lab.ps1 과 동일 계열. ──
PRESETS = {
    "darkfantasy": "dark fantasy anime key visual, moody atmospheric anime illustration, dramatic chiaroscuro cinematic lighting, ominous tense mood, highly detailed",
    "lightnovel":  "Japanese light novel cover illustration, glossy vibrant anime art, soft rim lighting, character-forward, sparkling delicate details, bright appealing",
    "webtoon":     "Korean webtoon style illustration, clean bold lineart, vivid saturated colors, crisp dramatic lighting, modern polished",
    "ghibli":      "Studio Ghibli style soft painterly anime, warm whimsical storybook mood, gentle natural light, nostalgic cozy",
    "epicfantasy": "epic fantasy anime concept art, luminous magical atmosphere, grand cinematic scale, vibrant glowing colors, highly detailed",
}

# ── 장르 → 대표 스타일(주제 맞춤 — 항상 다크 아님) ──
GENRE_STYLE = {
    "로맨스": "lightnovel",
    "판타지": "epicfantasy",
    "잔혹동화": "darkfantasy",
    "추리": "darkfantasy",
    "공포": "darkfantasy",
}
DEFAULT_STYLE = "lightnovel"

TECH = "16:9 wide cinematic composition, poster key art, highly detailed, no text, no letters, no watermark"

FONT_CANDIDATES = [
    os.environ.get("THUMB_FONT_FILE", ""),
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
]


def _pick_style(spec: dict) -> str:
    st = (spec.get("thumbnail_style") or "").strip().lower()
    if st in PRESETS:
        return st
    return GENRE_STYLE.get(spec.get("genre", ""), DEFAULT_STYLE)


def _font_path() -> str | None:
    for p in FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


def _load_font(size: int):
    from PIL import ImageFont
    fp = _font_path()
    if fp:
        return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    """폭 기준 줄바꿈(한글은 공백 없을 수 있어 글자 단위 폴백)."""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        elif " " in cur.strip():
            idx = cur.rfind(" ")
            lines.append(cur[:idx].rstrip())
            cur = cur[idx + 1:] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def _overlay_title(bg_path: str, title: str, out_path: str) -> str:
    from PIL import Image, ImageDraw, ImageOps

    img = Image.open(bg_path).convert("RGB")
    img = ImageOps.fit(img, (W, H), Image.LANCZOS)  # cover-crop 중앙

    # 하단 스크림(가독성): 아래로 갈수록 어둡게
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    top = int(H * 0.42)
    for y in range(top, H):
        a = int(215 * (y - top) / (H - top))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, min(215, a)))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    draw = ImageDraw.Draw(img)
    max_w = int(W * 0.88)
    # 3줄 이내에 들어오도록 폰트 크기 자동 축소
    for size in (88, 80, 72, 64, 56, 48):
        font = _load_font(size)
        lines = _wrap(draw, title, font, max_w)
        if len(lines) <= 3:
            break
    line_h = int(size * 1.18)
    total_h = line_h * len(lines)
    y = H - 64 - total_h
    stroke = max(4, size // 14)
    for ln in lines:
        w = draw.textlength(ln, font=font)
        x = (W - w) / 2
        draw.text((x, y), ln, font=font, fill=(255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += line_h

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=88)  # 1280x720 JPEG → 2MB 이내
    return out_path


def build_thumbnail(spec: dict, out_path: str, workdir: str) -> str | None:
    """spec 으로 커스텀 썸네일 생성. hook 없거나 실패 시 None."""
    hook = (spec.get("thumbnail_hook") or "").strip()
    if not hook:
        print("   ⏭️  썸네일 스킵 — thumbnail_hook 없음")
        return None
    try:
        from PIL import Image  # noqa: F401 — 설치 확인
    except ImportError:
        sys.stderr.write("[warn] Pillow 미설치 — 썸네일 스킵(pip install pillow)\n")
        return None

    style = _pick_style(spec)
    prompt = f"{hook}. {PRESETS[style]}, {TECH}"
    os.makedirs(workdir, exist_ok=True)
    raw = os.path.join(workdir, "thumb_raw.png")
    print(f"   🎨 썸네일 배경 생성(style={style})… (최대 12분)")
    if not wbspark.generate_image(prompt, raw):
        print("   ⏭️  썸네일 스킵 — 배경 생성 실패")
        return None

    # 썸네일에 얹을 문구: thumbnail_text(초강력 후킹 문구) 우선, 없으면 제목.
    overlay_text = (spec.get("thumbnail_text")
                    or spec.get("platforms", {}).get("youtube", {}).get("title")
                    or spec.get("series_title", "")).strip()
    try:
        path = _overlay_title(raw, overlay_text, out_path)
        print(f"   🖼️  썸네일 완성: {path}")
        return path
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 썸네일 오버레이 실패 → 스킵: {e}\n")
        return None


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="소설 썸네일 생성(테스트)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="thumb.jpg")
    ap.add_argument("--workdir", default="_thumb_work")
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    p = build_thumbnail(spec, args.out, args.workdir)
    return 0 if p else 1


if __name__ == "__main__":
    raise SystemExit(main())
