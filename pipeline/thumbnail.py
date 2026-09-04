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
import re
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


# ── 썸네일 문구 노브 ──────────────────────────────────────
# ★2026-08-28 실측: ASMR 노출 5,600 · CTR 2.1%(95%CI 1.8~2.5%) · SCP 도 2.1%.
#   두 토픽이 ★같은 이 함수를 쓴다 — 채널 전체 썸네일의 공통 병목이었다.
#   원인: 폰트 상한이 88px 인데 썸네일이 1280x720 이라 ★높이의 12% 밖에 안 됐다.
#   유튜브 썸네일 문구 관행은 높이의 20~30%(=144~216px). 절반도 안 쓰고 있었다.
THUMB_MAX_FONT = int(os.environ.get("THUMB_MAX_FONT", "200"))   # 높이의 28%
THUMB_MIN_FONT = int(os.environ.get("THUMB_MIN_FONT", "72"))
THUMB_MAX_LINES = int(os.environ.get("THUMB_MAX_LINES", "2"))   # 3줄이면 글자가 작아진다
THUMB_ACCENT = os.environ.get("THUMB_ACCENT", "#FF5A57")
# 문구 배치 스타일 — 장르마다 관행이 ★정반대다(2026-08-28 경쟁 채널 실측).
#   scp    : 번호를 ★상단에 초대형 + 제목. 조회수 상위 SCP 채널의 공통 형식
#   bottom : 하단 중앙 한 덩어리(기존 동작)
#   none   : ★문구를 아예 넣지 않는다. ASMR 상위 썸네일 6개 중 5개가 무텍스트였다
THUMB_STYLE = os.environ.get("THUMB_STYLE", "bottom")
THUMB_NUM_COLOR = os.environ.get("THUMB_NUM_COLOR", "#FFD54A")
# ★번호 크기 — 썸네일 높이 대비. 0 이면 안 그린다.
#   2026-09-04 아침: 0.24 → 0.11 로 줄였다. 근거는 "SCP 출판물 표지엔 번호가 없다" 였는데
#   ★매체를 잘못 봤다. 책 표지와 유튜브 썸네일은 다르다 —
#   같은 날 저녁 조회수 상위 SCP 채널의 ★썸네일을 놓고 보니 번호가 크다.
#   0.16 으로 되돌린다(24% 는 과했고 11% 는 모자랐다).
NUM_RATIO = float(os.environ.get("THUMB_NUM_RATIO", "0.16"))
NAME_RATIO = float(os.environ.get("THUMB_NAME_RATIO", "0.19"))   # 코드네임(흰 글자)
# 글자 자리만 어둡게. 상단은 번호+이름, 하단은 대사.
SCRIM_BAND = float(os.environ.get("THUMB_SCRIM_BAND", "0.44"))
SCRIM_ALPHA = int(os.environ.get("THUMB_SCRIM_ALPHA", "175"))
QUOTE_RATIO = float(os.environ.get("THUMB_QUOTE_RATIO", "0.062"))  # 하단 대사. 0 이면 끔
# 참고 채널이 전부 쓰는 바깥 테두리. 0 이면 안 그린다.
FRAME_PX = int(os.environ.get("THUMB_FRAME_PX", "10"))


def _hex_rgb(c: str, fallback=(255, 90, 87)) -> tuple:
    c = (c or "").strip().lstrip("#")
    if len(c) != 6:
        return fallback
    try:
        return tuple(int(c[k:k + 2], 16) for k in (0, 2, 4))
    except ValueError:
        return fallback


def _wrap_words(draw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    """★어절 단위 줄바꿈. 폭은 PIL 로 ★실측한다.

    기존 `_wrap` 은 글자 단위 폴백이라 한글이 ★음절 중간에서 잘렸다
    ("직결된 / 다"). 쇼츠 자막에서 같은 문제를 textfit.py 로 고쳤으므로
    어절 분해만 그쪽을 재사용하고, 측정은 여기서 실제 폰트로 한다.
    """
    try:
        import textfit
        toks = [t for t, _ in textfit.tokens(text)]
    except Exception:  # noqa: BLE001
        toks = [w for w in (text or "").split() if w]
    if not toks:
        return []
    lines, cur = [], ""
    for tok in toks:
        cand = tok if not cur else cur + " " + tok
        if cur and draw.textlength(cand, font=font) > max_w:
            lines.append(cur)
            cur = tok
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _fit_line(draw, text: str, max_w: int, hi: int, lo: int):
    """한 줄이 max_w 안에 들어가는 가장 큰 폰트를 찾는다."""
    step = max(4, (hi - lo) // 20)
    for size in range(hi, lo - 1, -step):
        f = _load_font(size)
        if draw.textlength(text, font=f) <= max_w:
            return size, f
    return lo, _load_font(lo)


def _stroked(draw, xy, text, font, fill, stroke_w, stroke_fill=(0, 0, 0)):
    draw.text(xy, text, font=font, fill=fill,
              stroke_width=stroke_w, stroke_fill=stroke_fill)


def _overlay_scp(img, title: str, number: str, accent, out_path: str, quote: str = "") -> str:
    """조회수 상위 SCP 채널의 썸네일 구조를 그대로 따른다.

        [상단]  번호      — 초대형, 노랑, 검은 외곽선
        [상단]  코드네임  — 초대형, 흰색
        [전체]  개체 그림 — 프롬프트가 화면을 채운다(§2.5.2)
        [하단]  대사 한 줄 — "- 왜.. 왜 이러세요!!!" 류
        [가장자리] 얇은 강조색 테두리

    2026-09-04 정정 2회. 아침엔 번호를 24%→11% 로 줄였는데, 근거로 삼은 게
    ★SCP 출판물 '책 표지' 였다. 저녁에 같은 채널의 ★유튜브 썸네일을 보니
    번호가 크다. 매체가 다르면 규칙도 다르다 — 0.16 으로 되돌렸다.

    하단 대사는 참고 채널이 예외 없이 쓴다. 무서운 그림 + 사람 말 한 줄의
    조합이 "무슨 일이 벌어지는 중" 이라는 신호를 준다.
    """
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(img)
    max_w = int(W * 0.92)
    num = (number or "").strip() if NUM_RATIO > 0 else ""
    body = (title or "").strip()
    q = (quote or "").strip() if QUOTE_RATIO > 0 else ""

    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    band = int(H * SCRIM_BAND)
    for y in range(band):
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, int(SCRIM_ALPHA * (1 - y / band) ** 0.6)))
    if q:                                   # 하단에도 얕게 — 대사가 앉을 자리
        qb = int(H * 0.22)
        for y in range(qb):
            a = int(150 * (y / qb) ** 1.4)
            sd.line([(0, H - qb + y), (W, H - qb + y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    draw = ImageDraw.Draw(img)

    y = int(H * 0.035)
    if num:
        ns, nf = _fit_line(draw, num, max_w, int(H * NUM_RATIO), int(H * NUM_RATIO * 0.55))
        nw = draw.textlength(num, font=nf)
        _stroked(draw, ((W - nw) / 2, y), num, nf,
                 _hex_rgb(THUMB_NUM_COLOR, (255, 213, 74)), max(7, ns // 7))
        y += int(ns * 1.02)

    lines, tf, ts = None, None, None
    for size in range(int(H * NAME_RATIO), int(H * 0.09), -6):
        f = _load_font(size)
        cand = _wrap_words(draw, body, f, max_w, 2)
        if len(cand) <= 2 and cand and max(draw.textlength(x, font=f) for x in cand) <= max_w:
            lines, tf, ts = cand, f, size
            break
    if lines is None:
        ts = int(H * 0.09)
        tf = _load_font(ts)
        lines = _wrap_words(draw, body, tf, max_w, 2) or [body]
    for ln in lines:
        w = draw.textlength(ln, font=tf)
        _stroked(draw, ((W - w) / 2, y), ln, tf, (255, 255, 255), max(7, ts // 8))
        y += int(ts * 1.06)

    if q:
        qs, qf = _fit_line(draw, q, int(W * 0.90), int(H * QUOTE_RATIO), int(H * 0.036))
        qw = draw.textlength(q, font=qf)
        _stroked(draw, ((W - qw) / 2, H - int(H * 0.115)), q, qf,
                 (255, 240, 214), max(4, qs // 6))

    if FRAME_PX > 0:
        fc = _hex_rgb(accent or THUMB_ACCENT, (229, 72, 77))
        ImageDraw.Draw(img).rectangle([0, 0, W - 1, H - 1], outline=fc, width=FRAME_PX)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    img.save(out_path, "JPEG", quality=88)
    return out_path


def _overlay_title(bg_path: str, title: str, out_path: str,
                   accent: str | None = None, style: str | None = None,
                   number: str = "", quote: str = "") -> str:
    """배경 + 문구. `*강조*` 로 감싼 부분은 accent 색으로 칠한다.

    style:
      "bottom" 하단 중앙 한 덩어리(기존 동작 · 기본값)
      "scp"    번호 + 코드네임 + 하단 대사. `number` · `quote` 를 함께 넘긴다
      "none"   ★문구 없음. 배경 그대로 저장(ASMR 처럼 무텍스트가 관행인 장르)

    ★하위호환: 인자 3개 호출부(story_render·asmr_render·scp_render)는 그대로 동작한다.
    """
    from PIL import Image, ImageDraw, ImageOps

    img = Image.open(bg_path).convert("RGB")
    img = ImageOps.fit(img, (W, H), Image.LANCZOS)  # cover-crop 중앙

    st = (style or THUMB_STYLE or "bottom").strip().lower()
    if st == "none" or not (title or "").strip():
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        img.save(out_path, "JPEG", quality=88)
        return out_path
    if st == "scp":
        return _overlay_scp(img, title, number, accent, out_path, quote)

    raw = (title or "").strip()
    acc = _hex_rgb(accent or THUMB_ACCENT)
    # *강조* 마커 → 위치만 기억하고 본문에서는 제거
    hl = ""
    m = re.search(r"\*([^*]{1,20})\*", raw)
    if m:
        hl = m.group(1)
        raw = raw[:m.start()] + hl + raw[m.end():]

    draw = ImageDraw.Draw(img)
    max_w = int(W * 0.90)
    size, lines = THUMB_MIN_FONT, []
    # ★큰 것부터 내려온다 — 예전엔 88 이 상한이라 항상 작았다
    step = max(4, (THUMB_MAX_FONT - THUMB_MIN_FONT) // 16)
    for size in range(THUMB_MAX_FONT, THUMB_MIN_FONT - 1, -step):
        font = _load_font(size)
        lines = _wrap_words(draw, raw, font, max_w, THUMB_MAX_LINES)
        if len(lines) <= THUMB_MAX_LINES and lines and \
                max(draw.textlength(x, font=font) for x in lines) <= max_w:
            break
    font = _load_font(size)
    if not lines:
        lines = _wrap_words(draw, raw, font, max_w, THUMB_MAX_LINES) or [raw]

    line_h = int(size * 1.14)
    total_h = line_h * len(lines)
    y0 = H - int(H * 0.07) - total_h

    # 스크림: ★텍스트 블록 위쪽부터만 어둡게 한다.
    #   예전엔 높이 42% 지점부터 215/255 까지 깔아 이미지 절반이 죽었다.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    top = max(0, y0 - int(size * 0.7))
    for y in range(top, H):
        a = int(200 * (y - top) / max(1, H - top))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, min(200, a)))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    draw = ImageDraw.Draw(img)

    stroke = max(5, size // 12)
    y = y0
    for ln in lines:
        w = draw.textlength(ln, font=font)
        x = (W - w) / 2
        if hl and hl in ln:
            # 강조 부분만 색을 바꿔 세 조각으로 그린다
            a, _, b = ln.partition(hl)
            for piece, col in ((a, (255, 255, 255)), (hl, acc), (b, (255, 255, 255))):
                if not piece:
                    continue
                draw.text((x, y), piece, font=font, fill=col,
                          stroke_width=stroke, stroke_fill=(0, 0, 0))
                x += draw.textlength(piece, font=font)
        else:
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
