#!/usr/bin/env python3
"""쇼츠 화면 글자 맞춤 — 한국어 어절 줄바꿈 + 자동 크기 축소.

## 왜 필요한가

**① 브라우저는 한국어를 ★음절 단위로 자른다.**
   CSS 기본값(`word-break: normal`)에서 크롬은 한글을 CJK 로 취급해
   아무 글자 사이에서나 줄을 넘긴다.

       정부가 발표한 대책이        정부가 발표한 대책
       ─────────────────    →     이            ← 읽다가 걸린다

   정답은 `word-break: keep-all`(어절 단위) 이고 CSS 쪽에도 넣었다.
   다만 그것만으로는 ②가 안 풀린다.

**② 폰트 크기가 하드코딩돼 있다.**
   `.h1`=130px · `.statement`=116px · `.quote-text`=90px 인데 박스 폭은 920px 고정이다.
   한글은 130px 이면 한 줄에 7글자다. 대본 길이는 회차마다 다른데 크기는 안 변하니
   긴 문장은 그냥 3줄이 되거나 박스를 넘친다. → **글자 수에 맞춰 크기를 줄여야 한다.**

## 여기서 하는 일

1. 어절(공백) 단위 그리디 줄바꿈 — 음절 중간에서 끊기지 않는다
2. 목표 줄 수(`max_lines`) 안에 들어갈 때까지 폰트를 단계적으로 축소
3. 결과를 `<br/>` 로 박아서 ★브라우저 재줄바꿈에 맡기지 않는다(결정론적)
4. 하이라이트(`<span class="big">`)는 ★쪼개지지 않는 한 덩어리로 취급

## 폭 추정을 왜 파이썬에서 하나

헤드리스 브라우저에서 실측하려면 `document.fonts.ready` 를 기다려야 하는데,
그 비동기 대기가 HyperFrames 의 프레임 캡처 타이밍과 경합한다(폰트 로드 전에
캡처가 시작되면 측정값이 통째로 틀린다). 렌더 시작 전에 파이썬에서 끝내는 편이 안전하다.

Pretendard 는 한글이 고정 폭(1em)이라 추정이 잘 맞는다. 라틴/숫자에서 생기는
오차는 `SAFE`(기본 0.94) 여유로 흡수한다.
"""
from __future__ import annotations

import re
import unicodedata

# ── 문자 폭(em) ────────────────────────────────────────────
# Pretendard 실측 기준. 한글은 고정 폭이라 1.0 으로 정확하고,
# 라틴/숫자는 글자마다 다르지만 SAFE 여유 안에 들어온다.
W_HANGUL = 1.00
W_DIGIT = 0.58
W_UPPER = 0.68
W_LOWER = 0.55
W_SPACE = 0.28
W_THIN = 0.30      # . , ; : ! ? ' " ` |
W_MID = 0.42       # - ( ) [ ] { } / \ % + = < > * # ~ @ &
W_DEFAULT = 0.55

_THIN = set(".,;:!?'\"`|·’‘”“")
_MID = set("-()[]{}/\\%+=<>*#~@&_—–…")


def char_em(ch: str) -> float:
    """글자 하나의 폭(em)."""
    if ch == " " or ch == " ":
        return W_SPACE
    o = ord(ch)
    # 한글 음절/자모 · CJK · 전각 · CJK 구두점 → 전부 1em
    if (0xAC00 <= o <= 0xD7A3) or (0x1100 <= o <= 0x11FF) or (0x3130 <= o <= 0x318F) \
       or (0x4E00 <= o <= 0x9FFF) or (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFF60):
        return W_HANGUL
    if ch.isdigit():
        return W_DIGIT
    if ch in _THIN:
        return W_THIN
    if ch in _MID:
        return W_MID
    if "A" <= ch <= "Z":
        return W_UPPER
    if "a" <= ch <= "z":
        return W_LOWER
    # 결합 문자(조합형 한글의 종성 등)는 폭을 차지하지 않는다
    if unicodedata.combining(ch):
        return 0.0
    return W_DEFAULT


_TAG = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """`<b>`·`<br/>` 같은 마크업을 폭 계산에서 제외한다.

    kp·sub 필드에는 `<b>강조</b>` 가 그대로 들어온다. 태그를 글자로 세면
    "청문회 <b>이틀 전</b>" 이 실제보다 7글자쯤 넓다고 계산돼 폰트가 과하게 줄어든다.
    """
    return _TAG.sub("", text or "")


def measure(text: str, size_px: float, big: str = "", big_ratio: float = 1.0) -> float:
    """문자열 폭(px). `big` 부분만 `big_ratio` 배 크게 잡는다. HTML 태그는 무시."""
    if not text:
        return 0.0
    plain = strip_tags(text)
    mult = _big_mask(plain, strip_tags(big), big_ratio)
    return sum(char_em(c) * m for c, m in zip(plain, mult)) * size_px


def _big_mask(text: str, big: str, big_ratio: float) -> list[float]:
    """`big` 이 걸린 구간만 big_ratio, 나머지는 1.0 인 배열."""
    mult = [1.0] * len(text)
    if big and big_ratio != 1.0:
        start = text.find(big)
        if start >= 0:
            for k in range(start, start + len(big)):
                mult[k] = big_ratio
    return mult


# ── 어절 단위 줄바꿈 ───────────────────────────────────────
def _split_sp(text: str) -> list[tuple[str, bool]]:
    """공백으로 자르고 (어절, 뒤에 공백이 있었나) 로 만든다."""
    if not text:
        return []
    words = text.split(" ")
    out = []
    for j, w in enumerate(words):
        if not w:
            continue
        out.append((w, j < len(words) - 1))
    return out


def tokens(text: str, big: str = "") -> list[tuple[str, bool]]:
    """(어절, 뒤에 공백이 있었나) 목록. 하이라이트는 ★쪼개지지 않게 묶는다.

    하이라이트가 공백을 품고 있으면("여성 총리") 한 덩어리로 다뤄야 한다.
    줄을 넘어 쪼개지면 `<span class="big">` 이 두 줄에 걸쳐 어색해지고 치환도 실패한다.

    ★주의: 하이라이트가 어절 경계에 딱 안 맞을 수 있다.
        "오늘 몇 번째였나요?" 에서 big="몇 번째" 면 뒤에 "였나요?" 가 남는다.
        여기서 공백을 새로 끼워 넣으면 ★원문에 없던 띄어쓰기가 생긴다
        ("몇 번째 였나요?"). 그래서 붙어 있던 조각은 붙은 채로 묶는다.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if big and " " in big and big in text:
        i = text.find(big)
        head, tail = text[:i], text[i + len(big):]
        tail_sp = tail.startswith(" ")
        out = _split_sp(head)
        if out and not head.endswith(" "):
            t, _ = out[-1]                      # 하이라이트가 어절 중간에서 시작
            out[-1] = (t + big, tail_sp)
        else:
            out.append((big, tail_sp))
        rest = _split_sp(tail.lstrip(" ") if tail_sp else tail)
        if rest and not tail_sp:
            t0, sp0 = rest[0]                   # 하이라이트가 어절 중간에서 끝
            lt, _ = out[-1]
            out[-1] = (lt + t0, sp0)
            rest = rest[1:]
        out += rest
        return _glue_punct(out)
    return _glue_punct(_split_sp(text))


_PUNCT_ONLY = re.compile(r"^[\s.,;:!?)\]}%’”·…]+$")


def _glue_punct(toks: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """문장부호만 남은 토큰을 앞 어절에 붙인다.

    하이라이트를 통째로 떼어내면 뒤에 붙어 있던 쉼표가 홀로 남을 수 있다.
    그대로 두면 ★줄이 쉼표로 시작한다.
    """
    out: list[tuple[str, bool]] = []
    for t, sp in toks:
        if out and _PUNCT_ONLY.match(t):
            pt, _ = out[-1]
            out[-1] = (pt + t, sp)
        else:
            out.append((t, sp))
    return out


def join(toks: list[tuple[str, bool]]) -> str:
    """(어절, 공백) 목록을 원문 그대로 되돌린다."""
    return "".join(t + (" " if sp else "") for t, sp in toks).rstrip()


def wrap(text: str, size_px: float, box_px: float,
         big: str = "", big_ratio: float = 1.0) -> list[str]:
    """어절 그리디 줄바꿈. 한 어절이 통째로 박스보다 길면 그 줄만 넘친다(축소로 해결)."""
    toks = tokens(text, big)
    if not toks:
        return []
    lines: list[str] = []
    cur: list[tuple[str, bool]] = []
    for tok in toks:
        cand = cur + [tok]
        if cur and measure(join(cand), size_px, big, big_ratio) > box_px:
            lines.append(join(cur))
            cur = [tok]
        else:
            cur = cand
    if cur:
        lines.append(join(cur))
    return lines


def fit(text: str, box_px: float, base_px: float, *,
        min_px: float | None = None, max_lines: int = 2,
        big: str = "", big_ratio: float = 1.0,
        safe: float = 0.94, step: float = 0.96,
        prefer_fewer: float = 0.75) -> tuple[int, list[str]]:
    """`max_lines` 줄 안에 들어가는 (폰트 크기, 줄 목록)을 돌려준다.

    base_px 부터 시작해 step 배씩 줄이며, min_px 까지 내려가도 안 맞으면
    ★min_px 로 최선을 다한 결과를 준다(글자를 잘라내지는 않는다 — 잘린 자막이
    작은 자막보다 훨씬 나쁘다).

    `prefer_fewer`: 그 비율까지 줄여서 ★줄 수를 더 줄일 수 있으면 그쪽을 택한다.
      쇼츠에서는 한 줄로 들어오는 쪽이 크기보다 낫다 — 다만 무한정 줄이면 안 읽히므로
      원래 크기의 이 비율(기본 75%)까지만 양보한다. 0 이면 끈다.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return int(base_px), []
    if min_px is None:
        min_px = base_px * 0.55
    usable = box_px * safe
    size = float(base_px)
    while True:
        lines = wrap(text, size, usable, big, big_ratio)
        widest = max((measure(ln, size, big, big_ratio) for ln in lines), default=0.0)
        if (len(lines) <= max_lines and widest <= usable) or size <= min_px:
            size, lines = _fewer(text, size, usable, lines, min_px,
                                 big, big_ratio, step, prefer_fewer)
            return int(round(size)), balance(text, size, usable, len(lines), big, big_ratio)
        size = max(min_px, size * step)


def _fewer(text, size, usable, lines, min_px, big, big_ratio, step, ratio):
    """조금만 줄여서 줄 수가 주는 지점이 있으면 거기로 간다.

    "당신의 / 별자리는 오늘 / 몇 번째였나요?" 3줄(116px) 보다
    "당신의 별자리는 / 오늘 몇 번째였나요?" 2줄(90px) 이 쇼츠에선 낫다.
    ★단 한없이 줄이면 안 읽히므로 원래 크기의 `ratio` 배까지만 양보한다.
    """
    if not ratio or len(lines) <= 1:
        return size, lines
    floor = max(min_px, size * ratio)
    best_size, best_lines = size, lines
    t = size
    while t > floor:
        t = max(floor, t * step)
        cand = wrap(text, t, usable, big, big_ratio)
        if len(cand) < len(best_lines):     # 아래로 훑으므로 ★첫 개선이 가장 큰 크기
            best_size, best_lines = t, cand
        if t <= floor:
            break
    return best_size, best_lines


def balance(text: str, size_px: float, box_px: float, n_lines: int,
            big: str = "", big_ratio: float = 1.0) -> list[str]:
    """줄 수를 유지하면서 각 줄 길이를 고르게 만든다.

    그리디 줄바꿈은 앞줄을 꽉 채우고 뒷줄에 찌꺼기를 남긴다.

        어제 코스피가 장중 3% 넘게        어제 코스피가 장중 3% 넘게
        빠졌습니다                   →    빠졌습니다              ← 이게 그리디
                                          어제 코스피가 장중         ← 이게 균형
                                          3% 넘게 빠졌습니다

    CSS `text-wrap: balance` 가 같은 일을 하지만, 우리는 `<br/>` 를 직접 박기 때문에
    브라우저가 손댈 여지가 없다 → 여기서 직접 한다.
    같은 줄 수가 나오는 ★가장 좁은 폭을 이분 탐색해서 다시 감는다.
    """
    if n_lines <= 1:
        return wrap(text, size_px, box_px, big, big_ratio)
    lo, hi = 0.0, box_px
    best = wrap(text, size_px, box_px, big, big_ratio)
    for _ in range(18):
        mid = (lo + hi) / 2
        cand = wrap(text, size_px, mid, big, big_ratio)
        if len(cand) <= n_lines and mid > 0:
            best, hi = cand, mid
        else:
            lo = mid
    return best


def fit_html(text: str, box_px: float, base_px: float, *,
             esc=None, max_lines: int = 2, min_px: float | None = None,
             big: str = "", big_ratio: float = 1.0, big_html: str = "",
             safe: float = 0.94) -> tuple[int, str]:
    """fit() 결과를 `<br/>` 로 이어 붙인 HTML 로.

    `big_html` 을 주면 하이라이트 구간을 그 문자열로 감싼다.
    (`{}` 자리에 이스케이프된 하이라이트 텍스트가 들어간다)
    """
    size, lines = fit(text, box_px, base_px, min_px=min_px, max_lines=max_lines,
                      big=big, big_ratio=big_ratio, safe=safe)
    e = esc or (lambda s: s)
    out = []
    used_big = False
    for ln in lines:
        s = e(ln)
        if big and big_html and not used_big and big in ln:
            s = s.replace(e(big), big_html.format(e(big)), 1)
            used_big = True
        out.append(s)
    return size, "<br/>".join(out)
