#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이야기 뼈대 계약 회귀 테스트.

    python pipeline/test_structure_rules.py

2026-08-31. v9/v10 을 각각 3편씩 돌려 보고 드러난 것을 지킨다.
핵심은 ★배정이 번호에서 결정론적으로 나오고, 서로 상관되지 않는다는 것이다.
"""
from __future__ import annotations
import collections
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import structure_rules as S   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def spec(num="SCP-9421", **kw):
    a = S.assign(num)
    d = {"scp_number": num, "structure": a["structure"], "number_reveal": a["number_reveal"],
         "ending_mode": a["ending_mode"], "opening_move": a["opening"][0],
         "closing_move": a["closing"][0], "fault": a["fault"], "procedures": [],
         "chain": [{"when": f"{i}번째", "event": f"재단이 {i}번째 조치를 실행했다",
                    "because": "" if i == 0 else "앞 조치가 실패했기 때문이다",
                    "shot": f"{i}번 격리실 문 앞에 선 요원 둘"}
                   for i in range(10)],
         "cameos": [{"number": "SCP-682", "how": "옆 격리실에 같은 등급으로 있었다"}],
         # 번호는 ★배정된 위치에 놓는다(앞이면 앞, 뒤면 뒤) — 아니면 이 검사에 걸린다
         "narration_full": ("가" * 900 + f" 번호는 {num[-4:]} 입니다."
                            if a["number_reveal"] == "뒤"
                            else f"{num[-4:]} 이야기입니다. " + "가" * 900)}
    d.update(kw)
    return d


print("\n── 1. 배정이 번호에서 결정론적으로 나온다 ──")
a = S.assign("SCP-9421")
ck("뼈대 21%3=0 → 연대기형", a["structure"] == "연대기형", a["structure"])
ck("공개 21 홀수 → 뒤", a["number_reveal"] == "뒤")
ck("닫기 백의자리 4%3=1 → 없음", a["ending_mode"] == "없음")
ck("fault 십의자리 2%4=2 → 개체", a["fault"] == "개체")
ck("오프닝 후보 2개", len(a["opening"]) == 2 and a["opening"][0] != a["opening"][1])
ck("클로징 후보 2개", len(a["closing"]) == 2 and a["closing"][0] != a["closing"][1])
ck("같은 번호는 항상 같은 배정", S.assign("SCP-9421") == S.assign("9421"))
ck("지부 접미사도 읽는다", S.assign("SCP-9421-KO")["structure"] == a["structure"])
ck("번호를 못 읽으면 빈 dict", S.assign("SCP-") == {})

print("\n── 2. ★배정끼리 상관되지 않는다 (9000~9999 전수) ──")
rows = [S.assign(str(x)) for x in range(9000, 10000)]


def chi(k1, k2):
    c = collections.Counter((r[k1], r[k2]) for r in rows)
    tot = len(rows)
    R, C = collections.Counter(), collections.Counter()
    for (x, y), v in c.items():
        R[x] += v
        C[y] += v
    return sum((v - R[x] * C[y] / tot) ** 2 / (R[x] * C[y] / tot) for (x, y), v in c.items())


for k1, k2 in itertools.combinations(["structure", "number_reveal", "ending_mode", "fault"], 2):
    x = chi(k1, k2)
    ck(f"{k1} × {k2} 카이제곱 {x:.2f} < 2", x < 2.0)
# 끝 두 자리로 두 번 나누면 안 되는 이유(10a+b ≡ a+b, mod 3)를 못박아 둔다
bad = [x for x in range(9000, 10000) if (x % 100) % 3 != ((x % 100) // 10 + x % 10) % 3]
ck("두 자리 수는 자릿수 합과 %3 이 항상 같다(그래서 닫기는 백의 자리를 쓴다)", bad == [])
dist = collections.Counter(r["fault"] for r in rows)
ck("fault 분포 재단 30% · 개체 50% · 제3자 20%",
   (dist["재단"], dist["개체"], dist["제3자"]) == (300, 500, 200), str(dict(dist)))

print("\n── 3. 배정 위반을 잡는다 ──")
ck("정상 스펙은 통과", S.check(spec()) == [], str(S.check(spec())))
ck("뼈대가 다르면 잡는다", any("뼈대" in x for x in S.check(spec(structure="금기형"))))
ck("닫기가 다르면 잡는다", any("닫기" in x for x in S.check(spec(ending_mode="질문+구독"))))
ck("fault 가 다르면 잡는다", any("원인" in x for x in S.check(spec(fault="제3자"))))
ck("무브가 배정 밖이면 잡는다",
   any("배정 밖" in x for x in S.check(spec(opening_move="장면 하나"))))
ck("opening_note 를 적으면 무브 이탈을 허용한다",
   not any("배정 밖" in x for x in
           S.check(spec(opening_move="장면 하나", opening_note="증언 재료가 없었다"))))
ck("2순위 무브도 통과",
   S.check(spec(opening_move=S.assign("SCP-9421")["opening"][1])) == [])

print("\n── 4. 값 뒤에 설명이 붙어도 값이 맞으면 통과 ──")
for v in ("뒤", "뒤(맨 마지막)", "뒤 — 이야기를 다 하고", "뒤 · 마지막 한 줄"):
    ck(f"{v!r} 를 '뒤' 로 읽는다", not any("번호 공개" in x for x in S.check(spec(number_reveal=v))))
ck("'앞' 은 여전히 틀린 값으로 잡는다",
   any("번호 공개" in x for x in S.check(spec(number_reveal="앞(도입부)"))))

print("\n── 5. 사슬 ──")
ck("연대기형 8마디 미만이면 잡는다",
   any("마디뿐" in x for x in S.check(spec(chain=spec()["chain"][:5]))))
c = spec()["chain"]
c[3]["because"] = ""
ck("because 가 비면 잡는다", any("because" in x for x in S.check(spec(chain=c))))
c2 = spec()["chain"]
c2[2]["event"] = "이상함"
ck("마디가 너무 짧으면 잡는다", any("너무 짧은" in x for x in S.check(spec(chain=c2))))
ck("연대기형인데 규칙이 있으면 잡는다",
   any("연대기형인데" in x for x in S.check(spec(procedures=["a", "b"]))))
tb = spec("SCP-9286")
ck("금기형은 6마디면 통과", S.check(spec("SCP-9286", chain=tb["chain"][:6],
                                     procedures=["a", "b", "c"])) == [])
ck("금기형인데 규칙이 없으면 잡는다",
   any("금기형인데" in x for x in S.check(spec("SCP-9286", procedures=[]))))

print("\n── 5b. ★shot 과 카메오 (v13 — 그림에 요소가 없던 원인) ──")
noshot = spec()
for c in noshot["chain"]:
    c["shot"] = ""
ck("shot 이 없으면 잡는다", any("shot 이 채워진" in x for x in S.check(noshot)))
short = spec()
for c in short["chain"]:
    c["shot"] = "지하"
ck("shot 이 너무 짧으면 안 센다", any("shot 이 채워진" in x for x in S.check(short)))
ck("6개만 채워도 통과", S.check(spec(chain=[
    {**c, "shot": (c["shot"] if i < 6 else "")} for i, c in enumerate(spec()["chain"])])) == [])
ck("카메오가 없으면 잡는다", any("카메오" in x for x in S.check(spec(cameos=[]))))
ck("number 만 있고 how 가 비면 안 센다",
   any("카메오" in x for x in S.check(spec(cameos=[{"number": "SCP-173", "how": ""}]))))
ck("★231 은 카메오로도 막는다",
   any("금지 개체" in x for x in S.check(spec(cameos=[
       {"number": "SCP-682", "how": "옆방"}, {"number": "SCP-231", "how": "언급"}]))))
ck("숫자만 적어도 231 을 잡는다",
   any("금지 개체" in x for x in S.check(spec(cameos=[{"number": "231", "how": "언급"}]))))

print("\n── 6. 번호 공개 위치 ──")
ck("'뒤' 인데 앞에서 나오면 잡는다",
   any("이미 나왔다" in x for x in
       S.check(spec(narration_full="9421 로 시작합니다. " + "가" * 900))))
ck("'앞' 인데 끝에서야 나오면 잡는다",
   any("지점에서야" in x for x in
       S.check(spec("SCP-9286", procedures=["a", "b", "c"],
                    chain=spec("SCP-9286")["chain"][:7],
                    narration_full="가" * 900 + " 9286 입니다."))))

print("\n── 7. ★소재가 바뀌어도 안 꼬인다(하드코딩 없음) ──")
import ast   # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "structure_rules.py"), encoding="utf-8").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if ast.get_docstring(node) is not None:
            node.body = node.body[1:]
code = ast.unparse(tree)
for w in ("계곡", "위성", "검출기", "얼음", "심해", "도서관", "히말라야"):
    ck(f"코드에 소재 단어 없음: {w}", w not in code)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
