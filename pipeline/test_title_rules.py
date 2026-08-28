#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제목 계약 회귀 테스트.

    python pipeline/test_title_rules.py

2026-08-28. 제목 후보 10개를 놓고 공식 3개(A 기본 · B/C 로테이션)로 좁힌 결과를 지킨다.
★소재가 바뀌어도 안 깨지는지가 제일 중요하다 — 마지막 절이 그걸 본다.
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


A = "마리아나 해구 6,000m에서 발견된 심장 모양 암반의 정체 [SCP-9532]"
B = "「어제보다 커졌습니다」 심해 6,000m에서 자라는 암반 [SCP-9532]"
C = "구십 초만 눈을 떼면 자란다는 마리아나 해구의 암반 [SCP-9532]"

print("\n── 1. 채택된 공식 3개는 전부 통과 ──")
for name, t, f in (("A 장소+사건+번호", A, "A"), ("B 증언 인용", B, "B"), ("C 수치 강조", C, "C")):
    got = T.check(t, number="SCP-9532", form=f)
    ck(f"{name} 통과", got == [], str(got))

print("\n── 2. 번호 꼬리 ──")
ck("꼬리 없으면 잡는다",
   any("[SCP-####]" in x for x in T.check("심해에서 발견된 암반의 정체", number="9532", form="A")))
ck("번호 불일치를 잡는다",
   any("다르다" in x for x in T.check(A, number="SCP-9184", form="A")))
ck("지부 접미사(-KO)도 꼬리로 읽는다", T.tail_number("사라진 등대 [SCP-9532-KO]") == "9532-KO")
ck("normalize 가 꼬리를 보충한다",
   T.normalize("심해 6,000m에서 발견된 심장 모양 암반의 정체", "SCP-9532").endswith("[SCP-9532]"))
ck("이미 있으면 두 번 붙이지 않는다", T.normalize(A, "SCP-9532") == A)
ck("normalize 는 본문을 건드리지 않는다", T.strip_tail(T.normalize(A, "9532")) == T.strip_tail(A))
for raw in ("SCP-9532", "scp 9532", "9532", "  SCP_9532 "):
    ck(f"번호 표기 흡수: {raw!r}", T.norm_number(raw) == "9532")

print("\n── 3. 시리즈 접미사 / 길이 / 반응 요구 ──")
old = "안 보고 있으면, 자랍니다 | SCP 아카이브"
ck("`| SCP 아카이브` 를 잡는다", any("아카이브" in x for x in T.check(old, number="9532", form="A")))
ck("normalize 가 접미사를 떼고 번호를 붙인다",
   T.normalize(old, "9532") == "안 보고 있으면, 자랍니다 [SCP-9532]")
ck("60자 초과를 잡는다",
   any("잘라먹는다" in x for x in T.check("가" * 55 + " [SCP-9532]", number="9532", form="A")))
ck("너무 짧으면(장소 누락) 잡는다",
   any("장소" in x for x in T.check("안 보고 있으면, 자랍니다 [SCP-9532]", number="9532", form="A")))
ck("채택 후보 최단(33자)은 통과",
   T.check("당신이 보고 있는 동안에만 멈춰 있는 것 [SCP-9532]", number="9532", form="A") == [])
ck("길이 초과라고 잘라내지는 않는다", len(T.normalize("가" * 80, "9532")) > 60)
ck("`끔찍한`(내용 형용사)은 통과",
   T.check("심해 6,000m에서 발견된 끔찍한 심장 암반의 정체 [SCP-9532]",
           number="9532", form="A") == [])
ck("`역대급`(반응 요구)은 잡는다",
   any("반응" in x for x in T.check("역대급 심해 괴생명체의 정체를 파헤쳐본다 [SCP-9532]",
                                  number="9532", form="A")))
os.environ["SCP_TITLE_BANLIST"] = ""
ck("SCP_TITLE_BANLIST='' 면 검사 안 함", T.banlist() == ())
del os.environ["SCP_TITLE_BANLIST"]

print("\n── 4. 선언한 공식과 구조가 맞는가 ──")
ck("B 인데 따옴표로 안 열면 잡는다", any("따옴표" in x for x in T.check_form(A, "B")))
ck("C 인데 수치가 없으면 잡는다",
   any("수치" in x for x in T.check_form("사라진 등대의 정체 [SCP-9532]", "C")))
ck("C 는 한글 수사도 수치로 본다", T.check_form(C, "C") == [])
ck("A 는 따옴표·수치 어느 쪽도 강요하지 않는다", T.check_form("사라진 등대의 정체 [SCP-9532]", "A") == [])
ck("공식 선언이 없으면 잡는다", any("title_form" in x for x in T.check_form(A, "")))
ck("infer: 따옴표로 열면 B", T.infer_form(B) == "B")
ck("infer: 숫자가 있어도 기본은 A", T.infer_form(A) == "A")

print("\n── 5. 제목 ≠ thumbnail_text ──")
ck("썸네일 문구를 그대로 품으면 잡는다",
   any("thumbnail_text" in x for x in
       T.check("「가라앉은 심장」 마리아나 해구에서 발견된 이상현상 [SCP-9532]",
               number="9532", form="B", thumbnail_text="가라앉은 심장")))
ck("다르면 통과", T.check(A, number="9532", form="A", thumbnail_text="가라앉은 심장") == [])

print("\n── 6. 쇼츠는 계약이 다르다 ──")
sh = "이 밥솥은 죽을 사람을 알고 있었다 | SCP"
ck("쇼츠 정상 통과", T.check(sh, profile="shorts") == [])
ck("쇼츠에 번호 꼬리가 붙으면 잡는다",
   any("[SCP-####]" in x for x in T.check("사라진 등대의 정체 [SCP-9532]", profile="shorts")))
ck("` | SCP` 로 안 끝나면 잡는다",
   any("SCP` 로 끝나지" in x for x in T.check("이 밥솥은 죽을 사람을 알고 있었다", profile="shorts")))
ck("`#shorts` 직접 쓰면 잡는다",
   any("#shorts" in x for x in T.check("이 밥솥은 죽을 사람을 알고 있었다 #shorts | SCP", profile="shorts")))
ck("report(shorts) 는 번호를 붙이지 않는다", T.report(sh, number="9532", profile="shorts") == sh)

print("\n── 7. ★소재가 바뀌어도 안 꼬인다(하드코딩 없음) ──")
# 심해/해구 같은 이번 회차 소재 단어에 규칙이 묶여 있으면 여기서 터진다.
others = [
    ("A", "체르노빌 4호기 지하에서 발견된 발광 균사체의 정체 [SCP-9601]", "9601"),
    ("A", "달 뒷면 착륙선 잔해에서 회수된 금속 손의 정체 [SCP-9733]", "9733"),
    ("B", "「문을 세 번 세지 마세요」 사이트-19 복도 관측 기록 [SCP-9288]", "9288"),
    ("B", "「그 아이는 명단에 없었습니다」 남극 기지 인원 대조 [SCP-9455]", "9455"),
    ("C", "칠 분마다 한 층씩 늘어난다는 부쿠레슈티의 계단 [SCP-9120]", "9120"),
    ("C", "41명이 사라진 뒤에야 열린 시추공 아래의 문 [SCP-9412]", "9412"),
]
for f, t, n in others:
    got = T.check(t, number=n, form=f)
    ck(f"{f} · {t[:18]}…", got == [], str(got))
# 규칙부(코드)에 이번 회차 소재 단어가 섞이면 다음 회차에서 오작동한다.
# 설명(주석·독스트링)에 예시로 적히는 건 괜찮다 — ★동작하는 코드만 본다.
import ast   # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_rules.py"),
           encoding="utf-8").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if ast.get_docstring(node) is not None:
            node.body = node.body[1:]
code = ast.unparse(tree)
for w in ("심해", "해구", "마리아나", "암반", "밥솥", "등대"):
    ck(f"코드에 소재 단어 없음: {w}", w not in code)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
