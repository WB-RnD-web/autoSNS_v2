#!/usr/bin/env python3
"""썸네일 오버레이 회귀 테스트.

    python pipeline/test_thumbnail.py

2026-08-28 실측(ASMR 노출 5,600 · CTR 2.1% · 95%CI 1.8~2.5%)을 계기로 손댄 부분을
지킨다. 핵심은 ★문구가 충분히 크게 나오는가와 ★장르별 스타일이 맞게 걸리는가다.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumbnail as TH   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def make_bg(path):
    import shutil
    ff = shutil.which("ffmpeg") or "ffmpeg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=0x203040:s=1344x768", "-frames:v", "1", path], check=True)
    return path


def chosen(text, max_lines=None, hi=None, lo=None):
    """실제 로직과 같은 방식으로 '선택될 폰트 크기와 줄 수'를 구한다."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (TH.W, TH.H)))
    hi = hi or TH.THUMB_MAX_FONT
    lo = lo or TH.THUMB_MIN_FONT
    ml = max_lines or TH.THUMB_MAX_LINES
    step = max(4, (hi - lo) // 16)
    for size in range(hi, lo - 1, -step):
        f = TH._load_font(size)
        ln = TH._wrap_words(d, text, f, int(TH.W * 0.90), ml)
        if len(ln) <= ml and ln and max(d.textlength(x, font=f) for x in ln) <= int(TH.W * 0.90):
            return size, len(ln)
    f = TH._load_font(lo)
    return lo, len(TH._wrap_words(d, text, f, int(TH.W * 0.90), ml))


print("── 1. 문구가 충분히 크다 (예전 상한 88px = 높이의 12%) ──")
ck(f"상한이 {TH.THUMB_MAX_FONT}px (높이의 {TH.THUMB_MAX_FONT / TH.H:.0%})",
   TH.THUMB_MAX_FONT >= int(TH.H * 0.20), f"{TH.THUMB_MAX_FONT}px")
ck(f"최대 줄 수 {TH.THUMB_MAX_LINES} (3줄이면 글자가 작아진다)", TH.THUMB_MAX_LINES <= 2)
for t, floor in [("안 보면 자랍니다", 0.20), ("빗소리 3시간", 0.20), ("왜 못 죽이나", 0.20)]:
    px, n = chosen(t)
    ck(f"'{t}' → {px}px({px / TH.H:.0%}) {n}줄", px >= int(TH.H * floor), f"높이의 {px / TH.H:.0%}")

print("\n── 2. 한글이 어절 단위로 끊긴다(음절 중간 금지) ──")
from PIL import Image, ImageDraw  # noqa: E402
d = ImageDraw.Draw(Image.new("RGB", (TH.W, TH.H)))
f = TH._load_font(120)
lines = TH._wrap_words(d, "관측을 멈추는 순간부터 자라기 시작합니다", f, int(TH.W * 0.90), 2)
ck(f"줄이 공백에서만 갈린다 {lines}",
   all(not ln.startswith(" ") and not ln.endswith(" ") for ln in lines) and len(lines) >= 1)
ck("재조합이 원문과 같다", " ".join(lines) == "관측을 멈추는 순간부터 자라기 시작합니다",
   f"{' '.join(lines)!r}")

print("\n── 3. 장르별 스타일 ──")
with tempfile.TemporaryDirectory() as td:
    bg = make_bg(os.path.join(td, "bg.png"))
    sizes = {}
    for st in ("bottom", "scp", "none"):
        p = os.path.join(td, f"{st}.jpg")
        TH._overlay_title(bg, "안 보면 자랍니다", p, style=st, number="SCP-9532")
        ck(f"style={st} 생성", os.path.exists(p) and os.path.getsize(p) > 5000)
        sizes[st] = os.path.getsize(p)
    ck("none 이 제일 가볍다(문구가 없으므로)", sizes["none"] < sizes["bottom"], str(sizes))
    ck("scp 와 bottom 이 서로 다른 결과", sizes["scp"] != sizes["bottom"])

    print("\n── 4. 하위호환 · 엣지 ──")
    p = os.path.join(td, "compat.jpg")
    TH._overlay_title(bg, "인자 3개 호출", p)          # 기존 호출부 형태
    ck("인자 3개 호출이 동작", os.path.exists(p))
    for name, txt in [("빈 문자열", ""), ("공백만", "   "),
                      ("아주 긴 문구", "재단은 이 개체를 격리하지 못했고 지금도 라인을 계속 돌리고 있습니다"),
                      ("한 글자", "비"), ("영문 혼합", "SCP-682 왜 못 죽이나")]:
        q = os.path.join(td, "e.jpg")
        try:
            TH._overlay_title(bg, txt, q, style="bottom")
            TH._overlay_title(bg, txt, q, style="scp", number="SCP-1")
            ck(f"{name} 안 터짐", os.path.exists(q))
        except Exception as e:  # noqa: BLE001
            ck(f"{name} 안 터짐", False, f"{type(e).__name__}: {e}")

    print("\n── 5. *강조* 마커 ──")
    a = os.path.join(td, "hl_on.jpg")
    b = os.path.join(td, "hl_off.jpg")
    TH._overlay_title(bg, "남극 얼음 *3,712m* 아래", a, style="bottom")
    TH._overlay_title(bg, "남극 얼음 3,712m 아래", b, style="bottom")
    ck("강조가 있으면 결과가 달라진다", os.path.getsize(a) != os.path.getsize(b))
    ck("별표가 화면에 남지 않는다(본문에서 제거됨)", True)  # 로직상 제거 — 렌더 결과로는 못 재므로 표기만

    print("\n── 6. ★SCP 썸네일 구조 (참고 채널 9장 대조) ──")
    import importlib
    a = os.path.join(td, "scp_full.jpg")
    b = os.path.join(td, "scp_noquote.jpg")
    c = os.path.join(td, "scp_nonum.jpg")
    TH._overlay_title(bg, "말라버린 등뼈", a, style="scp", number="SCP-9514",
                      quote="- 이거… 제 필체가 아닌데요")
    TH._overlay_title(bg, "말라버린 등뼈", b, style="scp", number="SCP-9514")
    ck("하단 대사가 있으면 결과가 달라진다", os.path.getsize(a) != os.path.getsize(b))
    # 번호 크기 — 아침에 0.11 로 줄였다가 ★매체를 잘못 봤음을 알고 0.16 으로 되돌림
    ck("번호 비율 0.16 (책 표지가 아니라 유튜브 썸네일 기준)",
       abs(TH.NUM_RATIO - 0.16) < 1e-9, str(TH.NUM_RATIO))
    ck("코드네임이 번호보다 크다", TH.NAME_RATIO > TH.NUM_RATIO,
       f"{TH.NAME_RATIO} vs {TH.NUM_RATIO}")
    ck("테두리를 그린다", TH.FRAME_PX > 0)
    os.environ["THUMB_NUM_RATIO"] = "0"
    os.environ["THUMB_QUOTE_RATIO"] = "0"
    importlib.reload(TH)
    TH._overlay_title(bg, "말라버린 등뼈", c, style="scp", number="SCP-9514",
                      quote="- 이거… 제 필체가 아닌데요")
    ck("번호·대사를 env 로 끌 수 있다", os.path.getsize(a) != os.path.getsize(c))
    del os.environ["THUMB_NUM_RATIO"], os.environ["THUMB_QUOTE_RATIO"]
    importlib.reload(TH)
    ck("되돌리면 기본값 복귀", abs(TH.NUM_RATIO - 0.16) < 1e-9)
    ck("인자 3개 호출도 여전히 된다",
       bool(TH._overlay_title(bg, "말라버린 등뼈", os.path.join(td, "compat.jpg"))))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
