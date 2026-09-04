#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""낭독 문체 검사 회귀 테스트.

    python pipeline/test_narration_check.py

2026-08-31. 발행된 4편에서 실제로 걸린 결함을 그대로 재현해 둔다.
★마지막 절이 제일 중요하다 — 소재가 바뀌어도 안 꼬여야 한다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narration_check as N   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


# 실제 4편에서 걸린 것과 같은 결함을 가진 대본
BAD = ("SCP-9758은 북유럽 지하의 처분장입니다. 도면에 없는 층이 나왔습니다. "
       "이 이야기를 시작하기 전에 하나만 짚고 갈게요. 확보. 격리. 보호. "
       "재단은 번호를 붙였습니다. 객체 등급, 세이프. 격리 방법은 이미 나와 있다는 뜻입니다. "
       "통에 찍힌 날짜가 이상했습니다. 아직 오지 않은 날짜였습니다. "
       "댓글로 한번 들려주세요. 다음 이야기에서 뵙겠습니다.")

# 같은 사건을 리듬 있게 쓴 것
GOOD = ("도면에는 열두 층까지밖에 없었습니다. 그런데 엘리베이터 버튼은 열세 개였죠. "
        "「눌러도 되나요?」 「눌러보세요.」 그 대화가 기록의 전부입니다. "
        "문이 열렸고… 통이 여섯 개 있었어요. 이미 봉인이 끝난 채로요. "
        "여기까진 그럴 수 있습니다. 문제는 날짜였거든요. "
        "「이거 잘못 찍힌 거 아닙니까?」 아무도 대답을 못 했습니다. "
        "아직 오지 않은 날짜였으니까요 — 그것도 여섯 개 전부. "
        "이상하죠? 저도 처음엔 오타인 줄 알았어요. "
        "「그럼 우리가 언젠가 여기다 뭘 넣는다는 거네요.」 "
        "그 말을 한 사람은 사흘 뒤에 사직서를 냈습니다. "
        "「누가 넣는지가 문제가 아니라…」 그 뒤는 녹취가 끊겨 있고요. "
        "그래서 지금은 어떻게 됐냐고요? 층은 아직 거기 있습니다.")

print("\n── 1. 프롬프트 예문 복붙 ──")
p = N.check(BAD)
ck("의례 문구를 잡는다", any("프롬프트 예문" in x for x in p))
ck("여러 개를 한 줄로 모은다", any("확보. 격리. 보호" in x and "다음 이야기에서" in x for x in p))
os.environ["SCP_RITUAL_BANLIST"] = ""
ck("SCP_RITUAL_BANLIST='' 면 검사 안 함", N.rituals() == ())
os.environ["SCP_RITUAL_BANLIST"] = "확보. 격리. 보호|다른 문구"
ck("파이프(|)로 목록을 갈아끼운다", N.rituals() == ("확보. 격리. 보호", "다른 문구"))
del os.environ["SCP_RITUAL_BANLIST"]

print("\n── 2. 첫 문장 ──")
ck("`SCP-####는 …입니다` 를 잡는다", any("첫 문장" in x for x in N.check(BAD)))
ck("다른 방식으로 열면 통과", not any("첫 문장" in x for x in N.check(GOOD)))
ck("지부 접미사도 같은 형식으로 본다",
   any("첫 문장" in x for x in N.check("SCP-9758-KO는 지하 처분장입니다. 그렇습니다.")))

print("\n── 3. 리듬 ──")
m = N.measure(GOOD)
ck("호흡 부호를 센다", m["breath_per_k"] > 0, str(m["breath_per_k"]))
ck("물음표를 센다", m["questions_per_k"] > 0, str(m["questions_per_k"]))
ck("직접 인용 쌍을 센다", m["quotes"] == 5, str(m["quotes"]))
ck("인용은 밀도로 잰다(짧은 대본이 억울하게 안 걸리게)",
   N.measure("「짧게.」 그렇습니다.")["quotes_per_k"] > N.MIN_QUOTES_K)
ck("인용이 아예 없으면 잡는다",
   any("직접 인용" in x for x in N.check("그랬습니다. " * 20 + "왜죠? 음… 그렇군요.")))
ck("리듬 있는 대본은 호흡·물음표로 안 걸린다",
   not any(("호흡" in x or "묻는 문장" in x) for x in N.check(GOOD)))
flat = "그랬습니다. " * 40
ck("어미가 한쪽으로 쏠리면 잡는다", any("종결어미" in x for x in N.check(flat)))
ck("최빈어미 비율을 계산한다", N.measure(flat)["top_ending_share"] > 0.9)

print("\n── 4. 빈 입력 ──")
ck("빈 대본을 잡는다", N.check("") == ["narration_full 이 비어 있다"])
ck("측정은 터지지 않는다", N.measure("")["sentences"] == 0)

print("\n── 4b. ★재단 어휘 (v12 — 09-04 회차에 '격리' 가 0회였다) ──")
bare = ("어느 소금호수가 마르고 있었습니다. 능선 하나가 드러났고요… "
        "「이거 어제도 이랬나요?」 아무도 답을 못 했습니다 — 그게 전부였죠. "
        "이상하죠? 저도 처음엔 착시인 줄 알았어요. 「다시 재보겠습니다.」 "
        "「그만두세요.」 그 뒤로 기록이 없습니다. 「누가 재고 있었던 걸까요?」")
p2 = N.check(bare)
ck("`격리` 가 없으면 잡는다", any("격리" in x and "회뿐" in x for x in p2))
ck("재단 용어 밀도가 낮으면 잡는다", any("재단 용어가" in x for x in p2))
ck("격리 횟수를 센다", N.measure("격리 격리 격리")["contain"] == 3)
ck("재단 어휘 밀도를 잰다", N.measure("재단 격리 사이트" * 20)["canon_per_k"] > 8)
os.environ["SCP_MIN_CANON_K"] = "0"
os.environ["SCP_MIN_CONTAIN"] = "0"
import importlib
importlib.reload(N)
ck("환경변수로 끌 수 있다", not any(("격리" in x and "회뿐" in x) or "재단 용어가" in x
                                for x in N.check(bare)))
del os.environ["SCP_MIN_CANON_K"], os.environ["SCP_MIN_CONTAIN"]
importlib.reload(N)

print("\n── 5. ★소재가 바뀌어도 안 꼬인다(하드코딩 없음) ──")
# 규칙부(동작하는 코드)에 이번 회차 소재 단어가 섞이면 다음 회차에서 오작동한다.
import ast   # noqa: E402
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "narration_check.py"), encoding="utf-8").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if ast.get_docstring(node) is not None:
            node.body = node.body[1:]
code = ast.unparse(tree)
# ★CANON_TERMS(재단·격리·사이트…)는 소재가 아니라 ★장르 어휘라 여기서 제외한다 —
# 어떤 개체가 와도 재단은 격리를 한다. 아래는 '이번 회차 소재' 단어들이다.
for w in ("처분장", "북유럽", "해구", "심해", "밥솥", "이발", "통화"):
    ck(f"코드에 소재 단어 없음: {w}", w not in code)
# 다른 소재의 리듬 있는 대본은 전부 통과해야 한다
others = [
    "「불빛이 하나 더 있어요.」 관측 일지엔 그렇게만 적혀 있습니다. "
    "전파망원경 접시가 열두 개인데… 열세 번째 그림자가 잡혔거든요. "
    "이상하죠? 저도 장비 결함인 줄 알았습니다. "
    "재단은 사이트 하나를 통째로 붙였고, 격리는 접시를 세지 않는 것으로 시작됐습니다. "
    "「접시를 세어보겠습니다.」 「세지 마세요.」 그 무전이 마지막이었어요 — "
    "기동특무부대가 들어갔지만 재수용은 실패했고, 격리 절차만 두 번 고쳐 썼습니다. "
    "그래서 지금 몇 개냐고요? 아무도 안 셉니다. 기억소거도 사흘을 못 갔고요. "
    "「세면 늘어나니까요.」 그렇게들 말하더군요. 격리는 지금도 진행 중입니다.",
    "「저 아이는 명단에 없습니다.」 남극 기지 인원 대조에서 나온 말입니다. "
    "스물넷이 들어갔는데 스물다섯이 앉아 있었죠. "
    "여기까진 착오일 수 있어요. 그런데 사진이 남아 있거든요… "
    "재단은 그 에어리어를 봉쇄하고 격리 절차를 새로 썼습니다. D계급 두 명이 들어갔고요. "
    "「다시 세어보겠습니다.」 「그만 세요.」 인지위해 차단도 소용이 없었습니다. "
    "다시 세면 스물여섯이 됩니다. 이상하지 않나요? 객체 등급은 그날 바뀌었습니다. "
    "「그럼 처음부터 스물넷이 아니었던 거 아닙니까?」 그 질문에 답한 사람은 없습니다. "
    "격리는 지금도 사이트 안에서 이어집니다. 재수용 계획은 아직 격리 등급 심사에 올라가 있고요.",
]
for i, t in enumerate(others, 1):
    got = N.check(t)
    ck(f"다른 소재 대본 {i} 통과", got == [], str(got))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
