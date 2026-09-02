#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뉴스 스토리보드 카피가 ★밋밋한지 잰다 (주식·정치·경제 공용).

2026-09-02. "좀 자극적이게" 라는 요청을 받고 최근 스토리보드를 재봤더니
재료는 센데 ★카피가 그걸 안 쓰고 있었다.

  파일                        화면 숫자   말 숫자
  2026-09-02_stock_us              5        1
  2026-08-31_stock_us              6        2
  2026-09-01_stock                 6        3
  2026-09-02_politics              4        8   ← 정치만 말로 읽는다

화면에는 `국채금리 4.8%대, 2025년 1월 이후 최고` 가 떠 있는데
내레이션은 "금리와 유가가 함께 뛰었습니다" 였다. ★소리로 들으면 아무것도 안 남는다.

그리고 hook_title 에 좋은 카피를 써놓고 1번 장면이 그걸 안 쓴다:

  hook_title  "애플만 웃었다, 나스닥은 울었다"   ← 대비가 있고 세다
  hook.lines  ["뉴욕이","다시","출렁였다"]        ← 아무 정보가 없다

원인은 프롬프트의 `R2 오픈 루프`("hook 은 숫자와 결론을 숨기고 감정만") 였다.
6초짜리 세로 쇼츠에서 첫 장면에 정보가 없으면 그냥 스와이프된다 —
★이 포맷에서는 숫자가 곧 후킹이다.

★종목·지수·정당 이름 같은 소재 단어를 하나도 쓰지 않는다. 숫자·길이·구조만 본다.
경고가 기본이고, 빨간불은 NEWS_FAIL_ON_COPY=1.
"""
from __future__ import annotations

import json
import os
import re

# 숫자 — 아라비아 숫자 또는 한글 수사 + 단위.
NUM = re.compile(r"\d+(?:[.,]\d+)?")
KOR_NUM = re.compile(r"[영일이삼사오육칠팔구십백천만억]\s*(?:퍼센트|프로|달러|원|포인트|배|년|월|일|시)")
# 화면 텍스트가 들어가는 필드들. 렌더러(motion_short)가 실제로 그리는 것만.
SCREEN_KEYS = ("lines", "points", "text", "sub", "label", "pill")
TAG = re.compile(r"</?[a-zA-Z][^>]*>")

# 반응을 요구하는 말. 사실을 세게 쓰는 건 얼마든지 좋다(§자극의 방향).
DEFAULT_BANLIST = ("충격", "경악", "역대급", "미쳤", "소름", "헉", "대박", "패닉", "폭망")

MIN_NARRATION_NUM_RATIO = float(os.environ.get("NEWS_MIN_NUM_RATIO", "0.6"))
# lines 한 줄의 ★상한만 본다. 프롬프트 표는 "권장 5~7자 / 최대 8자" 인데,
# 짧은 줄("다시")은 렌더링 문제가 아니라 ★문체다 — 짧게 끊는 게 오히려 셀 때가 많다.
# 하한까지 잡았더니 정치(잘 나온 회차)까지 걸려서, 실제 깨지는 조건만 남겼다.
MAX_HOOK_LEN = int(os.environ.get("NEWS_MAX_HOOK_LINE", "8"))


def banlist() -> tuple[str, ...]:
    raw = os.environ.get("NEWS_COPY_BANLIST")
    if raw is None:
        return DEFAULT_BANLIST
    return tuple(w.strip() for w in raw.split(",") if w.strip())


def strip_tags(s: str) -> str:
    return TAG.sub("", s or "")


def _flat(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return " ".join(_flat(x) for x in v)
    return ""


def screen_text(scene: dict) -> str:
    return strip_tags(" ".join(_flat(scene.get(k)) for k in SCREEN_KEYS if scene.get(k)))


def count_num(s: str) -> int:
    return len(NUM.findall(s or "")) + len(KOR_NUM.findall(s or ""))


def measure(spec: dict) -> dict:
    scenes = spec.get("scenes") or []
    screen = " ".join(screen_text(s) for s in scenes)
    narr = " ".join(s.get("narration", "") for s in scenes)
    hook = scenes[0] if scenes else {}
    lines = [strip_tags(x) for x in (hook.get("lines") or []) if isinstance(x, str)]
    ns, nn = count_num(screen), count_num(narr)
    return {
        "scenes": len(scenes),
        "screen_nums": ns,
        "narration_nums": nn,
        "num_ratio": (nn / ns) if ns else 0.0,
        "hook_lines": lines,
        "hook_nums": count_num(" ".join(lines) + " " + strip_tags(_flat(hook.get("pill")))),
        "hook_title": strip_tags(spec.get("hook_title") or ""),
        "narration_chars": len(narr),
    }


def _tokens(s: str) -> set[str]:
    """비교용 토큰 — 숫자와 2자 이상 한글 덩어리."""
    return set(re.findall(r"\d+(?:[.,]\d+)?|[가-힣]{2,}", s or ""))


def check(spec: dict) -> list[str]:
    scenes = spec.get("scenes") or []
    if not scenes:
        return ["scenes 가 비어 있다"]
    m = measure(spec)
    out: list[str] = []

    if m["screen_nums"] and m["num_ratio"] < MIN_NARRATION_NUM_RATIO:
        out.append(f"화면엔 숫자가 {m['screen_nums']}개인데 내레이션엔 {m['narration_nums']}개다 "
                   f"(비율 {m['num_ratio']:.0%}, 권장 {MIN_NARRATION_NUM_RATIO:.0%}+). "
                   "소리로 들으면 아무것도 안 남는다 — ★화면에 쓴 수치는 말로도 읽어라")

    if not m["hook_nums"]:
        out.append("1번 hook 장면에 수치가 하나도 없다 — 이 포맷에선 ★숫자가 곧 후킹이다. "
                   "6초 안에 정보가 없으면 스와이프된다")

    if m["hook_title"] and m["hook_lines"]:
        shared = _tokens(m["hook_title"]) & _tokens(" ".join(m["hook_lines"]))
        if not shared:
            out.append(f"hook_title({m['hook_title']!r})과 hook.lines({m['hook_lines']})가 "
                       "겹치는 말이 하나도 없다 — 제목의 카피를 화면 첫 장면이 안 쓰고 있다")

    for i, l in enumerate(m["hook_lines"]):
        if len(l) > MAX_HOOK_LEN:
            out.append(f"hook.lines[{i}] {l!r} 가 {len(l)}자 — {MAX_HOOK_LEN}자를 넘으면 "
                       "화면에서 깨진다")

    body = " ".join([m["hook_title"]] + [screen_text(s) for s in scenes]
                    + [s.get("narration", "") for s in scenes])
    hit = [w for w in banlist() if w in body]
    if hit:
        out.append("반응을 요구하는 말이 들어 있다: " + ", ".join(hit)
                   + " — 자극은 ★사실의 강도로 낸다(`2025년 1월 이후 최고` 가 `역대급` 보다 세다)")

    empty = [i + 1 for i, s in enumerate(scenes) if not (s.get("narration") or "").strip()]
    if empty:
        out.append(f"내레이션이 빈 장면: {empty}")
    return out


def report(spec: dict) -> list[str]:
    m = measure(spec)
    problems = check(spec)
    print(f"   📰 장면 {m['scenes']} · 화면 숫자 {m['screen_nums']} · 내레이션 숫자 "
          f"{m['narration_nums']} ({m['num_ratio']:.0%}) · hook 수치 {m['hook_nums']}개")
    if problems:
        print(f"   ⚠️  카피 점검({len(problems)}건)")
        for p in problems:
            print(f"      · {p}")
            print(f"::warning title=카피 밋밋함::{p}")
        if os.environ.get("NEWS_FAIL_ON_COPY") == "1":
            raise SystemExit(f"[news_copy_check] 카피 규칙 위반 {len(problems)}건 "
                             "(NEWS_FAIL_ON_COPY=1)")
    else:
        print("   ✅ 카피 OK")
    return problems


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    bad = 0
    for p in args.paths:
        print(f"\n── {os.path.basename(p)}")
        with open(p, encoding="utf-8") as f:
            bad += len(report(json.load(f)))
    return 1 if (bad and os.environ.get("NEWS_FAIL_ON_COPY") == "1") else 0


if __name__ == "__main__":
    raise SystemExit(main())
