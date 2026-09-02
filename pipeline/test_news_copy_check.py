#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뉴스 카피 검사 회귀 테스트.

    python pipeline/test_news_copy_check.py

2026-09-02. 실제 발행분 4편(주식 3 · 정치 1)에서 갈린 지점을 그대로 지킨다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import news_copy_check as C   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


# 실제 2026-09-02 미장 회차를 줄인 것 — 화면엔 숫자, 말엔 없음
FLAT = {
    "hook_title": "애플만 웃었다, 나스닥은 울었다",
    "scenes": [
        {"type": "hook", "lines": ["뉴욕이", "다시", "출렁였다"], "pill": "중동 재충돌",
         "narration": "중동에서 다시 포성이 커지자, 뉴욕 장이 열리자마자 출렁였습니다."},
        {"type": "trend", "label": "나스닥", "to": -1.03, "sub": "애플만 나홀로 <b>+2.6%</b>",
         "narration": "나스닥은 어젯밤 하루 만에 일 퍼센트 넘게 밀려 마감했습니다."},
        {"type": "keypoint", "points": ["국채금리 <b>4.8%대</b>, 2025년 1월 이후 최고",
                                        "유가는 <b>90달러</b> 넘게 급등"],
         "narration": "미국과 이란이 다시 부딪혔고 금리와 유가가 함께 뛰었습니다."},
    ],
}
# 같은 재료를 규칙대로 다시 쓴 것
PUNCHY = {
    "hook_title": "국채금리 4.8%, 1월 이후 최고",
    "scenes": [
        {"type": "hook", "lines": ["국채금리", "4.8%", "1월 이후 최고"], "pill": "중동 재충돌",
         "narration": "국채금리가 사 점 팔 퍼센트, 올해 1월 이후 최고까지 올랐습니다."},
        {"type": "trend", "label": "나스닥", "to": -1.03, "sub": "애플만 나홀로 <b>+2.6%</b>",
         "narration": "나스닥은 일 점 영삼 퍼센트 밀렸는데, 애플만 이 점 육 퍼센트 올랐습니다."},
        {"type": "keypoint", "points": ["유가 <b>90달러</b> 돌파"],
         "narration": "유가는 구십 달러를 넘겼습니다."},
    ],
}

print("\n── 1. 밋밋한 회차를 잡는다 ──")
p = C.check(FLAT)
ck("화면↔말 숫자 격차를 잡는다", any("소리로 들으면" in x for x in p))
ck("hook 에 수치가 없는 걸 잡는다", any("숫자가 곧 후킹" in x for x in p))
ck("hook_title 과 hook.lines 가 따로 노는 걸 잡는다",
   any("겹치는 말이 하나도 없다" in x for x in p))

print("\n── 2. 고쳐 쓴 회차는 통과 ──")
ck("경고 0건", C.check(PUNCHY) == [], str(C.check(PUNCHY)))
m = C.measure(PUNCHY)
ck("내레이션 숫자 비율이 오른다", m["num_ratio"] >= 0.6, f"{m['num_ratio']:.0%}")
ck("hook 수치를 센다", m["hook_nums"] > 0)

print("\n── 3. 측정 ──")
ck("HTML 태그를 벗겨서 센다", "<b>" not in C.screen_text(FLAT["scenes"][1]))
ck("한글 수사도 숫자로 센다", C.count_num("일 퍼센트 넘게 밀렸다") == 1)
ck("아라비아 숫자를 센다", C.count_num("4.8%대, 2025년") == 2)
ck("빈 스토리보드를 잡는다", C.check({"scenes": []}) == ["scenes 가 비어 있다"])
ck("내레이션 빈 장면을 잡는다",
   any("내레이션이 빈" in x for x in C.check({"scenes": [{"type": "hook", "lines": ["1개"],
                                                        "narration": ""}]})))

print("\n── 4. 짧은 hook 줄은 ★잡지 않는다 (문체지 결함이 아니다) ──")
short = {"hook_title": "세금 29일", "scenes": [
    {"type": "hook", "lines": ["세금이", "29일 만에", "사라졌다?"],
     "narration": "종부세 기준이 29일 만에 되돌아갔습니다."}]}
ck("짧은 줄에 경고가 안 뜬다", not any("깨진다" in x for x in C.check(short)))
long_line = {"hook_title": "x", "scenes": [
    {"type": "hook", "lines": ["아홉글자가넘는줄입니다"], "narration": "1개"}]}
ck("8자 초과는 잡는다", any("깨진다" in x for x in C.check(long_line)))

print("\n── 5. 반응 요구 단어 ──")
ck("`역대급` 을 잡는다",
   any("사실의 강도" in x for x in C.check({"hook_title": "역대급 폭락",
                                          "scenes": [{"type": "hook", "lines": ["1개"],
                                                      "narration": "1개"}]})))
ck("`최고`(사실 서술)는 통과", not any("사실의 강도" in x for x in C.check(PUNCHY)))
os.environ["NEWS_COPY_BANLIST"] = ""
ck("NEWS_COPY_BANLIST='' 면 검사 안 함", C.banlist() == ())
del os.environ["NEWS_COPY_BANLIST"]

print("\n── 6. ★소재가 바뀌어도 안 꼬인다(하드코딩 없음) ──")
import ast   # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "news_copy_check.py"), encoding="utf-8").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if ast.get_docstring(node) is not None:
            node.body = node.body[1:]
code = ast.unparse(tree)
for w in ("나스닥", "코스피", "애플", "국채", "종부세", "다우", "유가"):
    ck(f"코드에 소재 단어 없음: {w}", w not in code)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
