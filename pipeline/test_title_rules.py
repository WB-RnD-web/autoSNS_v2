#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제목 계약 회귀 테스트.

    python pipeline/test_title_rules.py

2026-09-04. 발행 4편의 제목이 ★4편 모두 `~의 정체` 로 끝난 것을 계기로
공식을 4개로 나누고 번호(n%4)로 배정하게 바꿨다. 그 계약을 지킨다.
★마지막 절이 제일 중요하다 — 소재가 바뀌어도 안 꼬여야 한다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import title_rules as T   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


# 번호 끝 두 자리 % 4 가 공식을 정한다: 32→0 사건 / 01→1 피해 / 14→2 증언 / 43→3 정체
CASES = [
    ("사건형", "SCP-9532", "심해 6,000m의 암반이 관측을 멈춘 순간 자라기 시작했다 [SCP-9532]"),
    ("피해형", "SCP-9601", "마리아나 해구 관측조 열한 명이 같은 날 명단에서 사라졌다 [SCP-9601]"),
    ("증언형", "SCP-9414", "「어제보다 커졌습니다」 심해 6,000m에서 자라는 암반 [SCP-9414]"),
    ("정체형", "SCP-9443", "마리아나 해구 6,000m에서 발견된 심장 모양 암반의 정체 [SCP-9443]"),
]

print("\n── 1. 공식 4개 — 번호가 정한다 ──")
for form, num, title in CASES:
    ck(f"{num} → {form}", T.form_for(num) == form, T.form_for(num))
    got = T.check(title, number=num, form=form)
    ck(f"{form} 통과", got == [], str(got))
ck("번호를 못 읽으면 빈 문자열", T.form_for("SCP-") == "")

print("\n── 2. ★`~의 정체` 를 끊는다 (4편 중 4편이 그랬다) ──")
je = "마리아나 해구 6,000m에서 발견된 심장 모양 암반의 정체 [SCP-9532]"
ck("사건형인데 `~의 정체` 로 끝나면 잡는다",
   any("의 정체" in x for x in T.check_form(je, "사건형")))
ck("정체형이면 통과", T.check_form(je, "정체형", "SCP-9443") == [])
ck("정체형인데 `~의 정체` 가 아니면 잡는다",
   any("정체" in x for x in T.check_form(CASES[0][2], "정체형")))
ck("문장 중간의 '정체'는 안 잡는다",
   not any("의 정체" in x for x in
           T.check_form("정체를 숨긴 관측조가 기지를 떠났다 [SCP-9532]", "사건형")))

print("\n── 3. 배정 위반 · 구조 ──")
ck("번호 배정과 다른 공식을 잡는다",
   any("번호 배정" in x for x in T.check_form(CASES[0][2], "정체형", "SCP-9532")))
ck("증언형인데 따옴표로 안 열면 잡는다",
   any("따옴표" in x for x in T.check_form(CASES[0][2], "증언형")))
ck("공식 선언이 없으면 잡는다", any("title_form" in x for x in T.check_form(CASES[0][2], "")))
ck("옛 이름(A/B/C)은 이제 틀린 값이다",
   any("title_form" in x for x in T.check_form(CASES[0][2], "A")))

print("\n── 4. 번호 꼬리 ──")
ck("꼬리 없으면 잡는다",
   any("[SCP-####]" in x for x in T.check("심해에서 발견된 암반이 자랐다", number="9532",
                                          form="사건형")))
ck("번호 불일치를 잡는다",
   any("다르다" in x for x in T.check(CASES[0][2], number="SCP-9184", form="사건형")))
ck("지부 접미사(-KO)도 꼬리로 읽는다", T.tail_number("사라진 등대 [SCP-9532-KO]") == "9532-KO")
ck("normalize 가 꼬리를 보충한다",
   T.normalize("심해 6,000m의 암반이 자라기 시작했다", "SCP-9532").endswith("[SCP-9532]"))
ck("이미 있으면 두 번 안 붙인다", T.normalize(CASES[0][2], "SCP-9532") == CASES[0][2])
ck("normalize 는 본문을 안 건드린다",
   T.strip_tail(T.normalize(CASES[0][2], "9532")) == T.strip_tail(CASES[0][2]))
for raw in ("SCP-9532", "scp 9532", "9532", "  SCP_9532 "):
    ck(f"번호 표기 흡수: {raw!r}", T.norm_number(raw) == "9532")

print("\n── 5. 접미사 · 길이 · 반응 요구 ──")
old = "안 보고 있으면, 자랍니다 | SCP 아카이브"
ck("`| SCP 아카이브` 를 잡는다",
   any("아카이브" in x for x in T.check(old, number="9532", form="사건형")))
ck("normalize 가 접미사를 떼고 번호를 붙인다",
   T.normalize(old, "9532") == "안 보고 있으면, 자랍니다 [SCP-9532]")
ck("60자 초과를 잡는다",
   any("잘라먹는다" in x for x in T.check("가" * 55 + " [SCP-9532]", number="9532",
                                       form="사건형")))
ck("너무 짧으면(장소 누락) 잡는다",
   any("장소" in x for x in T.check("암반이 자랐다 [SCP-9532]", number="9532", form="사건형")))
ck("길이 초과라고 잘라내지는 않는다", len(T.normalize("가" * 80, "9532")) > 60)
ck("`끔찍한`(내용 형용사)은 통과",
   T.check("심해 6,000m의 끔찍한 암반이 관측을 멈춘 순간 자랐다 [SCP-9532]",
           number="9532", form="사건형") == [])
ck("`역대급`(반응 요구)은 잡는다",
   any("반응" in x for x in T.check("역대급 심해 괴생명체가 관측조를 덮쳤다 [SCP-9532]",
                                  number="9532", form="사건형")))
os.environ["SCP_TITLE_BANLIST"] = ""
ck("SCP_TITLE_BANLIST='' 면 검사 안 함", T.banlist() == ())
del os.environ["SCP_TITLE_BANLIST"]

print("\n── 6. 제목 ≠ thumbnail_text ──")
ck("썸네일 문구를 그대로 품으면 잡는다",
   any("thumbnail_text" in x for x in
       T.check("「가라앉은 심장」이 관측을 멈춘 순간 자랐다 [SCP-9414]",
               number="9414", form="증언형", thumbnail_text="가라앉은 심장")))
ck("다르면 통과",
   T.check(CASES[0][2], number="9532", form="사건형", thumbnail_text="가라앉은 심장") == [])

print("\n── 7. 쇼츠는 계약이 다르다 ──")
sh = "이 밥솥은 죽을 사람을 알고 있었다 | SCP"
ck("쇼츠 정상 통과", T.check(sh, profile="shorts") == [])
ck("쇼츠에 번호 꼬리가 붙으면 잡는다",
   any("[SCP-####]" in x for x in T.check("사라진 등대의 정체 [SCP-9532]", profile="shorts")))
ck("` | SCP` 로 안 끝나면 잡는다",
   any("SCP` 로 끝나지" in x for x in T.check("이 밥솥은 죽을 사람을 알고 있었다",
                                            profile="shorts")))
ck("`#shorts` 직접 쓰면 잡는다",
   any("#shorts" in x for x in T.check("이 밥솥은 죽을 사람을 알고 있었다 #shorts | SCP",
                                       profile="shorts")))
ck("report(shorts) 는 번호를 안 붙인다", T.report(sh, number="9532", profile="shorts") == sh)

print("\n── 8. ★소재가 바뀌어도 안 꼬인다(하드코딩 없음) ──")
others = [
    ("사건형", "SCP-9128", "체르노빌 4호기 지하의 균사체가 관측탑을 통째로 삼켰다 [SCP-9128]"),
    ("피재형_오타확인", "SCP-9317", "달 뒷면 착륙선에 남은 승무원 아홉이 이름을 잃었다 [SCP-9317]"),
    ("증언형", "SCP-9286", "「문을 세 번 세지 마세요」 사이트-19 복도 관측 기록 [SCP-9286]"),
    ("정체형", "SCP-9331", "부쿠레슈티 지하에서 칠 분마다 늘어나는 계단의 정체 [SCP-9331]"),
]
for label, num, title in others:
    f = T.form_for(num)
    got = T.check(title, number=num, form=f)
    ck(f"{f} · {title[:20]}…", got == [], str(got))
import ast   # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_rules.py"),
           encoding="utf-8").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if ast.get_docstring(node) is not None:
            node.body = node.body[1:]
code = ast.unparse(tree)
for w in ("심해", "해구", "마리아나", "암반", "밥솥", "등대", "체르노빌"):
    ck(f"코드에 소재 단어 없음: {w}", w not in code)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
