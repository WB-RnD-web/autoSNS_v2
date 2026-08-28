#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""루틴 프롬프트 발행-주기 하드코딩 검사기.

    python check_prompt_schedule.py ROUTINE_SCP_v8_1.md [...]
    python check_prompt_schedule.py *.md

★프롬프트를 고칠 때마다 돌려라. 매일·평일 반복 실행에서 조용히 꼬이는 것만 잡는다.
'조용히'가 핵심이다 — 아래 것들은 ★에러를 내지 않는다. 그냥 영상이 안 만들어진다.

무엇을 보나
  1. 차단 분기      "이미 이번 주에 했으니 종료" → 평일 2회차부터 아무것도 안 나온다
  2. 메타데이터 오염  notes/description/태그에 박힌 요일·주기 → 스케줄 바뀌면 전부 거짓말
  3. 주차 기반 선택  포인터·주차로 소재를 고르면 주기가 바뀔 때 반복 간격도 같이 바뀐다
  4. 예시 번호       설명용 SCP 번호가 실제로 뽑히는 사고

반례(✗ 로 시작하거나 '예전에는'/'금지'가 붙은 줄)는 세지 않는다 — 그건 고치라고 적어둔 것이다.
"""
from __future__ import annotations
import glob
import os
import re
import sys

# (이름, 패턴, 왜 위험한가)
RULES = [
    ("차단 분기",
     r"(last_iso_week\s*==|이미\s*(이번\s*주|오늘).*?(종료|중단|스킵|만들지)|같은\s*주.*?(종료|중단))",
     "평일·매일 발행이면 2회차부터 아무것도 안 만들어진다"),
    ("메타데이터에 주기",
     r'"(notes|description|text|caption)"\s*:.*?(주\s*1회|매주|이번\s*주|[월화수목금토일]요일)',
     "산출물에 박제된다. 발행 요일이 바뀌면 전부 거짓말"),
    ("주차/요일 기반 소재 선택",
     r"(rotation_pointer|class_pointer)|((주차|요일)\s*(에\s*따라|기준으로)\s*(테마|소재|등급))",
     "주기가 바뀌면 반복 간격도 같이 바뀐다 — '최근 N개 회피'로 해야 한다"),
    ("고정 발행 요일 지시",
     r"[월화수목금토일]요일(에|에는)?\s*(발행|업로드|실행|만든다|올린다)",
     "스케줄이 바뀌면 지시가 틀려진다"),
]
# 반례·설명 줄은 건너뛴다
EXEMPT = re.compile(r"(^\s*[-*>|]?\s*✗|예전에는|금지|쓰지\s*마라|안 되는|넣으면 안|하지 않는다|없다\b)")


def audit(path: str) -> list[tuple[int, str, str, str]]:
    out = []
    for i, ln in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        if EXEMPT.search(ln):
            continue
        for name, pat, why in RULES:
            if re.search(pat, ln):
                out.append((i, name, why, ln.strip()[:100]))
                break
    return out


def main(argv: list[str]) -> int:
    pats = argv[1:] or ["*.md"]
    files: list[str] = []
    for p in pats:
        files += sorted(glob.glob(p))
    if not files:
        print("검사할 파일이 없다."); return 2
    total = 0
    for f in files:
        hits = audit(f)
        total += len(hits)
        mark = "✅" if not hits else "❌"
        print(f"\n{mark} {os.path.basename(f)} — {len(hits)}건")
        for i, name, why, ln in hits:
            print(f"   L{i:<5} [{name}]  {ln}")
            print(f"          → {why}")
    print(f"\n{'✅ 전부 통과' if not total else f'❌ 총 {total}건 — 고치고 다시 돌려라'}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
