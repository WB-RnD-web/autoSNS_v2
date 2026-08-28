#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제목 계약 검사 — 규칙은 프롬프트가 정하고, 기계로 확인 가능한 것만 여기서 본다.

2026-08-28. 조회수 상위 SCP 채널을 훑어보고 제목 공식을 3개로 좁혔다.
루틴이 어떤 공식으로 썼는지 `platforms.youtube.title_form` 에 ★스스로 적어 보내고,
여기서는 그 선언이 실제 문장 구조와 맞는지만 확인한다.

    A  장소+사건+번호   기본. 매 회 쓸 수 있다.       마리아나 해구 6,000m에서 발견된 … [SCP-9532]
    B  증언 인용형      따옴표로 연다.               「어제보다 커졌습니다」 심해 … [SCP-9532]
    C  수치 강조형      수치가 후킹이다.              구십 초만 눈을 떼면 자란다는 … [SCP-9532]

★여기에 소재·주제 키워드는 한 글자도 없다.
   "장소가 들어있나" 같은 건 기계가 판정할 수 없어서 ★프롬프트 쪽 규칙으로 남겼다.
   이 파일이 보는 건 괄호·따옴표·숫자·길이 같은 ★구조뿐이다 — 소재가 뭐로 바뀌든 안 꼬인다.

검사 결과는 경고다. 제목이 조금 어긋났다고 이미 렌더까지 끝난 영상을 버리는 건 손해라,
기본은 `::warning::` 만 띄우고 계속 간다. 빨간불로 세우려면 SCP_FAIL_ON_TITLE=1.
"""
from __future__ import annotations

import os
import re

# ── 구조 패턴 ──────────────────────────────────────────
# 끝에 붙는 번호 꼬리. `-KO` 같은 지부 접미사도 받는다.
TAIL_RE = re.compile(r"\s*\[SCP-(\d{3,4}(?:-[A-Z]{2})?)\]\s*$")
# 여는 따옴표 — 증언 인용형(B)의 신호.
OPEN_QUOTE = "「『\"'“‘《〈"
# 수치 — 아라비아 숫자 또는 한글 수사(C).
NUM_RE = re.compile(r"\d|[영일이삼사오육칠팔구십백천만억]\s*(?:초|분|시간|일|주|개월|년|명|번|회|층|미터|킬로|번째)")
# 시리즈 접미사 — 번호가 그 역할을 하므로 중복이다.
SERIES_SUFFIX_RE = re.compile(r"\|\s*SCP\s*아카이브\s*$")
# 쇼츠 꼬리 — 롱폼과 계약이 다르다(§2.6.1: 번호를 앞세우지 않는다).
SHORTS_TAIL_RE = re.compile(r"\|\s*SCP\s*$")

# 반응을 요구하는 말. 내용 형용사(끔찍한·잔혹한·기이한)는 ★막지 않는다 —
# 참고 채널이 실제로 쓰고 있고, 영상이 그러하면 그건 사실이기 때문이다.
DEFAULT_BANLIST = ("충격", "경악", "역대급", "미쳤다", "미친", "소름주의",
                   "실화냐", "레전드", "대박", "클릭")

# 채택 후보 10개의 실측 길이는 33~46자였다. 아래는 그 바깥에 여유를 둔 값이다.
LONG_MIN, LONG_MAX = 28, 60
SHORT_MIN, SHORT_MAX = 18, 34


def banlist() -> tuple[str, ...]:
    """SCP_TITLE_BANLIST 로 갈아끼울 수 있다(쉼표 구분). 빈 문자열이면 검사 안 함."""
    raw = os.environ.get("SCP_TITLE_BANLIST")
    if raw is None:
        return DEFAULT_BANLIST
    return tuple(w.strip() for w in raw.split(",") if w.strip())


def tail_number(title: str) -> str:
    """끝의 `[SCP-9532]` 에서 번호만. 없으면 빈 문자열."""
    m = TAIL_RE.search(title or "")
    return m.group(1) if m else ""


def strip_tail(title: str) -> str:
    """번호 꼬리를 뗀 본문."""
    return TAIL_RE.sub("", title or "").strip()


def norm_number(number: str) -> str:
    """`SCP-9532` · `scp 9532` · `9532` → `9532`. 지부 접미사는 살린다."""
    s = str(number or "").strip().upper()
    s = re.sub(r"^SCP[\s\-_]*", "", s)
    return s.strip()


def infer_form(title: str) -> str:
    """구조만 보고 짐작한다 — 선언이 없을 때의 폴백이다.

    ★A 와 C 는 구조가 겹친다(A 예시에도 `6,000m` 이 있다).
      그래서 '숫자가 있으면 C' 로 단정하지 않고, 선언이 없으면 A(기본)로 본다.
      선언이 있으면 infer 를 믿지 않고 §check_form 의 ★필요조건만 확인한다.
    """
    body = strip_tail(title)
    if body[:1] in OPEN_QUOTE:
        return "B"
    return "A"


def check_form(title: str, form: str) -> list[str]:
    """선언한 공식이 문장 구조와 모순되지 않는지 — ★필요조건만 본다."""
    form = (form or "").strip().upper()
    body = strip_tail(title)
    out: list[str] = []
    if form not in ("A", "B", "C"):
        out.append(f"title_form 이 A/B/C 가 아니다: {form or '(없음)'}")
        return out
    if form == "B" and body[:1] not in OPEN_QUOTE:
        out.append("title_form=B(증언 인용형)인데 제목이 따옴표로 시작하지 않는다")
    if form == "C" and not NUM_RE.search(body):
        out.append("title_form=C(수치 강조형)인데 제목에 수치가 없다")
    return out


def check(title: str, *, number: str = "", form: str = "",
          thumbnail_text: str = "", profile: str = "long") -> list[str]:
    """어긋난 점을 사람이 읽는 문장으로 돌려준다. 빈 리스트면 통과."""
    t = (title or "").strip()
    out: list[str] = []
    if not t:
        return ["제목이 비어 있다"]

    if profile == "shorts":
        if TAIL_RE.search(t):
            out.append("쇼츠 제목에 `[SCP-####]` 꼬리가 붙었다 — 오리지널 번호는 검색 수요가 0이다(§2.6.1)")
        if not SHORTS_TAIL_RE.search(t):
            out.append("쇼츠 제목이 ` | SCP` 로 끝나지 않는다")
        if "#shorts" in t.lower():
            out.append("`#shorts` 는 파이프라인이 붙인다 — 제목에 직접 쓰지 마라")
        if not (SHORT_MIN <= len(t) <= SHORT_MAX):
            out.append(f"쇼츠 제목 길이 {len(t)}자 — {SHORT_MIN}~{SHORT_MAX}자 권장")
    else:
        tail = tail_number(t)
        if not tail:
            out.append("끝에 `[SCP-####]` 가 없다 — 검색으로 들어오는 장르라 번호가 곧 검색어다")
        elif number and norm_number(number) != tail:
            out.append(f"제목의 번호(SCP-{tail})와 스펙의 scp_number({number})가 다르다")
        if SERIES_SUFFIX_RE.search(t):
            out.append("`| SCP 아카이브` 접미사는 쓰지 않는다 — 번호가 그 역할을 한다")
        if len(t) > LONG_MAX:
            out.append(f"제목 길이 {len(t)}자 — {LONG_MAX}자를 넘으면 유튜브 검색결과가 잘라먹는다")
        elif len(t) < LONG_MIN:
            out.append(f"제목 길이 {len(t)}자 — {LONG_MIN}자 미만이면 "
                       "★장소나 사건이 빠졌을 가능성이 높다(§2-H2)")
        out += check_form(t, form)

    hit = [w for w in banlist() if w in t]
    if hit:
        out.append("반응을 요구하는 말이 들어 있다: " + ", ".join(hit)
                   + " — 내용 형용사(끔찍한·잔혹한·기이한)는 괜찮다")

    tx = (thumbnail_text or "").strip()
    if tx and tx in t:
        out.append(f"제목이 thumbnail_text({tx!r})를 그대로 품고 있다 — 제목은 사건, 썸네일은 이름이다")
    return out


def normalize(title: str, number: str = "") -> str:
    """기계적으로 되돌릴 수 있는 것만 고친다 — ★문장에는 손대지 않는다.

    ① 시리즈 접미사 제거  ② 번호 꼬리 보충. 길이 초과는 ★자르지 않는다(어절이 깨진다).
    """
    t = (title or "").strip()
    if not t:
        return t
    t = SERIES_SUFFIX_RE.sub("", t).strip()
    n = norm_number(number)
    if n and not tail_number(t):
        t = f"{t} [SCP-{n}]"
    return t


def report(title: str, *, number: str = "", form: str = "",
           thumbnail_text: str = "", profile: str = "long", fix: bool = True) -> str:
    """검사 + (원하면) 기계적 보정. 보정된 제목을 돌려주고 경고는 stdout 으로."""
    fixed = normalize(title, number) if (fix and profile != "shorts") else (title or "").strip()
    problems = check(fixed, number=number, form=form,
                     thumbnail_text=thumbnail_text, profile=profile)
    tag = "쇼츠" if profile == "shorts" else "롱폼"
    shown = form.strip().upper() or infer_form(fixed)
    if fixed != (title or "").strip():
        print(f"   ✏️  제목 보정: {title!r} → {fixed!r}")
    if problems:
        print(f"   ⚠️  {tag} 제목 점검({len(problems)}건) — 공식 {shown}")
        for p in problems:
            print(f"      · {p}")
            print(f"::warning title=제목 규칙::{p}")
        if os.environ.get("SCP_FAIL_ON_TITLE") == "1":
            raise SystemExit(f"[title_rules] {tag} 제목 규칙 위반 {len(problems)}건 (SCP_FAIL_ON_TITLE=1)")
    else:
        print(f"   ✅ {tag} 제목 OK — 공식 {shown} · {len(fixed)}자")
    return fixed
