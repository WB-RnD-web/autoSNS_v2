#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이야기 뼈대 계약 검사 — 배정이 번호대로 걸렸는지, 사슬이 진짜 사슬인지.

2026-08-31. v9 프롬프트로 세 회차를 ★서로 못 보게 돌렸더니 자유 선택 4개가 전부 같았다.
(오프닝 무브 6개 · 클로징 5개 · 제목 공식 3개 · 남은 변칙 성질 3개 → 독립이면 0.4%)
목록을 주고 "골라라" 하면 제일 그럴듯한 하나로 몰린다는 뜻이라,
v10 부터는 ★SCP 번호에서 배정을 끌어낸다. 번호는 매 회 다르고 소재와 무관하다.

    끝 두 자리 n, 백의 자리 h
      뼈대        n % 3        0·1 = 연대기형 / 2 = 금기형
      번호 공개    n % 2        짝수 = 앞 / 홀수 = 뒤
      오프닝 무브  n % 6        과 (n%6+3)%6  ← 둘 중 하나
      클로징 무브  n % 5        과 (n%5+2)%5  ← 둘 중 하나
      닫기         h % 3        0 질문+구독 / 1 없음 / 2 가벼운 한마디
      원인(fault)  (n//10) % 4  0 재단 / 1·2 개체 / 3 제3자  → 재단 30% · 개체 50% · 제3자 20%

원작(origin)만 ★날짜로 정한다 — canon 회차는 9000대 번호를 안 쓰므로
번호가 정해지기 ★전에 판정해야 하기 때문이다:  date 의 일(day) % 3 == 0 → canon

★닫기에 백의 자리를 쓰는 이유: 두 자리 수는 ★자릿수 합과 3으로 나눈 나머지가 같다
   (10a+b ≡ a+b, mod 3). 그래서 끝 두 자리로 두 번 나누면 뼈대와 완전히 상관된다.
   실제로 9000~9999 전수 대조에서 카이제곱 0.00(완전 독립)을 확인하고 백의 자리로 잡았다.
   fault 는 십의 자리를 쓴다 — 뼈대와 카이제곱 1.06(자유도 6, 사실상 독립), 나머지와는 0.00.

★fault 도 배정으로 뺀 이유: v10 을 3편 돌렸더니 ★3편 전부 "재단" 이 나왔다.
   "3~4편에 한 번" 같은 비율 지시는 지켜지지 않는다.

여기엔 ★소재 키워드가 없다. 숫자와 필드값만 본다.
경고가 기본이고, 빨간불은 SCP_FAIL_ON_STRUCTURE=1.
"""
from __future__ import annotations

import os
import re

OPENING = ("증언으로 연다", "수치의 어긋남", "사람 한 명",
           "문서의 빈칸", "장면 하나", "화자의 고백")
CLOSING = ("기록이 아직 이어진다", "사람의 마지막 말", "재단의 판단 보류",
           "숫자 하나", "화자가 답을 안 한다")
STRUCTURE = {0: "연대기형", 1: "연대기형", 2: "금기형"}
ENDING = {0: "질문+구독", 1: "없음", 2: "가벼운 한마디"}
FAULT = {0: "재단", 1: "개체", 2: "개체", 3: "제3자"}

CHAIN_MIN = int(os.environ.get("SCP_CHAIN_MIN", "8"))          # 연대기형
CHAIN_MIN_TABOO = int(os.environ.get("SCP_CHAIN_MIN_TABOO", "6"))
EVENT_MIN = int(os.environ.get("SCP_EVENT_MIN", "15"))         # 마디 한 줄의 최소 길이

# ★"마디에 동사가 있는가"는 여기서 재지 않는다.
#   `…있었다` 로 끝나는 문장을 상태 서술로 보는 정규식을 넣었다가
#   "경계 반대편에서 뭔가를 조립하고 있었다"(멀쩡한 사건)를 잡아냈다.
#   한국어에서 이건 정규식으로 가릴 수 없다 — 오탐이 나는 검사는 경고를 무시하게 만든다.
#   그래서 ★기계가 확실히 아는 것만 본다: 마디 수 · because 유무 · 한 줄 길이.
#   "동사가 있는가"는 프롬프트(§C)와 Self-check 가 지킨다.


def digits(number: str) -> int:
    """`SCP-9421` · `9421-KO` → 9421. 못 읽으면 -1."""
    m = re.search(r"(\d{3,4})", str(number or ""))
    return int(m.group(1)) if m else -1


def assign(number: str) -> dict:
    """번호에서 배정을 끌어낸다. 번호를 못 읽으면 빈 dict."""
    num = digits(number)
    if num < 0:
        return {}
    n, h = num % 100, (num // 100) % 10
    return {
        "structure": STRUCTURE[n % 3],
        "number_reveal": "뒤" if n % 2 else "앞",
        "opening": (OPENING[n % 6], OPENING[(n % 6 + 3) % 6]),
        "closing": (CLOSING[n % 5], CLOSING[(n % 5 + 2) % 5]),
        "ending_mode": ENDING[h % 3],
        "fault": FAULT[(n // 10) % 4],
    }


def check_chain(chain: list[dict], structure: str) -> list[str]:
    """사슬이 목록이 아니라 사슬인지."""
    out: list[str] = []
    chain = chain or []
    need = CHAIN_MIN_TABOO if structure == "금기형" else CHAIN_MIN
    if len(chain) < need:
        out.append(f"chain 이 {len(chain)}마디뿐이다 — {structure}은 {need}마디 이상"
                   " (사건이 안 일어나면 분위기만 남는다)")
    missing = [i + 1 for i, c in enumerate(chain[1:], 1)
               if not str(c.get("because") or "").strip()]
    if missing:
        out.append(f"because 가 빈 마디: {missing} — 앞 마디의 ★결과가 아니면 사슬이 아니다")
    thin = [i + 1 for i, c in enumerate(chain)
            if len(str(c.get("event") or "").strip()) < EVENT_MIN]
    if thin:
        out.append(f"내용이 너무 짧은 마디: {thin} — 한 줄로도 ★무슨 일이 있었는지 알 수 있어야 한다")
    return out


def origin_for(date: str) -> str:
    """`2026-09-04` → 일(day) 4 % 3 = 1 → original. 0 이면 canon (3일에 한 번)."""
    m = re.search(r"\d{4}-\d{2}-(\d{2})", str(date or ""))
    if not m:
        return ""
    return "canon" if int(m.group(1)) % 3 == 0 else "original"


def check(spec: dict) -> list[str]:
    out: list[str] = []
    want_origin = origin_for(spec.get("date", ""))
    got_origin = str(spec.get("origin") or "").strip()
    if want_origin and got_origin and got_origin != want_origin:
        if want_origin == "canon" and not str(spec.get("origin_note") or "").strip():
            out.append(f"{spec.get('date')} 는 원작(canon) 차례인데 origin={got_origin} 이다 — "
                       "원문을 못 읽어 내려간 거라면 ★origin_note 에 이유를 적어라 "
                       "(안 적으면 매번 조용히 오리지널로 도망친다. 실제로 10편 내리 그랬다)")
        elif want_origin == "original":
            out.append(f"{spec.get('date')} 는 오리지널 차례인데 origin={got_origin} 이다")
    a = assign(spec.get("scp_number", ""))
    if not a:
        return ["scp_number 를 읽을 수 없다"]

    def head(v: str) -> str:
        """`뒤(맨 마지막)` · `없음 — 질문 안 붙임` → 앞의 값만. 주석이 붙어도 값이 맞으면 통과."""
        return re.split(r"[(（\[—·,:]| - ", str(v or "").strip())[0].strip()

    def cmp(field, want, label):
        got = head(spec.get(field))
        if not got:
            out.append(f"{label}({field})이 비어 있다 — 번호가 정한 값은 {want} 다")
        elif isinstance(want, tuple):
            if got not in want and not str(spec.get("opening_note") or "").strip():
                out.append(f"{label}이 배정 밖이다: {got!r} — 번호가 정한 건 {want[0]} 또는 {want[1]}."
                           " 둘 다 못 쓰겠으면 opening_note 에 이유를 적어라")
        elif got != want:
            out.append(f"{label}이 배정과 다르다: {got!r} ≠ {want!r} (번호 {spec.get('scp_number')})")

    cmp("structure", a["structure"], "뼈대")
    cmp("number_reveal", a["number_reveal"], "번호 공개 시점")
    cmp("ending_mode", a["ending_mode"], "닫기 방식")
    cmp("opening_move", a["opening"], "오프닝 무브")
    cmp("closing_move", a["closing"], "클로징 무브")
    cmp("fault", a["fault"], "원인")

    structure = str(spec.get("structure") or a["structure"]).strip()
    out += check_chain(spec.get("chain"), structure)

    procs = [p for p in (spec.get("procedures") or []) if str(p).strip()]
    if structure == "연대기형" and procs:
        out.append(f"연대기형인데 procedures 에 규칙이 {len(procs)}개 있다 — 빈 배열이어야 한다"
                   " (규칙을 만들면 매 회 같은 모양이 된다)")
    if structure == "금기형" and not (2 <= len(procs) <= 3):
        out.append(f"금기형인데 procedures 가 {len(procs)}개다 — 2~3개여야 한다")

    # 번호가 실제로 그 위치에서 처음 나오는가
    n = spec.get("narration_full") or ""
    num = digits(spec.get("scp_number", ""))
    if n and num > 0:
        hit = n.find(str(num))
        if hit < 0:
            out.append("낭독 본문에 번호가 한 번도 안 나온다")
        else:
            late = hit > len(n) * 0.85
            if a["number_reveal"] == "뒤" and not late:
                out.append(f"번호 공개가 '뒤' 인데 본문 {hit / len(n):.0%} 지점에서 이미 나왔다")
            if a["number_reveal"] == "앞" and late:
                out.append(f"번호 공개가 '앞' 인데 본문 {hit / len(n):.0%} 지점에서야 나온다")
    return out


def report(spec: dict) -> list[str]:
    a = assign(spec.get("scp_number", ""))
    problems = check(spec)
    chain = spec.get("chain") or []
    if a:
        print(f"   🧩 뼈대 {spec.get('structure','?')} · {len(chain)}마디 · "
              f"번호공개 {spec.get('number_reveal','?')} · 닫기 {spec.get('ending_mode','?')} · "
              f"fault {spec.get('fault','?')}  (번호 {spec.get('scp_number')} 배정: "
              f"{a['structure']}/{a['number_reveal']}/{a['ending_mode']})")
    if problems:
        print(f"   ⚠️  뼈대 점검({len(problems)}건)")
        for p in problems:
            print(f"      · {p}")
            print(f"::warning title=이야기 뼈대::{p}")
        if os.environ.get("SCP_FAIL_ON_STRUCTURE") == "1":
            raise SystemExit(f"[structure_rules] 뼈대 규칙 위반 {len(problems)}건 "
                             "(SCP_FAIL_ON_STRUCTURE=1)")
    else:
        print("   ✅ 이야기 뼈대 OK")
    return problems
