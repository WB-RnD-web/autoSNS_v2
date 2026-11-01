"""api-test/nt-trend 전용 — 비전 검수(story_qa)를 실제 API 로 한 번 확인(7화 첫 렌더의 틀린 그림 vs 고친 그림). 머지하지 않는다."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "gumiho", "tales"))
import anthropic  # noqa: E402
import story as ST  # noqa: E402
import story_qa as QA  # noqa: E402

ep = ST.find("7")
client = anthropic.Anthropic()
out = {}
for kind in ("bad", "good"):
    tok = {"input": 0, "output": 0, "calls": 0}
    r = QA.review(ep, {i: os.path.join(HERE, f"{kind}_{i:02d}.jpg") for i in (1, 5, 9, 13)}, client, tok)
    pi, po = QA.PRICE[QA.MODEL]
    out[kind] = {"result": {str(k): v for k, v in r.items()}, "tokens": tok,
                 "usd": round((tok["input"] * pi + tok["output"] * po) / 1e6, 4)}
txt = json.dumps(out, ensure_ascii=False, indent=1)
print(txt)
summ = os.environ.get("GITHUB_STEP_SUMMARY")
if summ:
    with open(summ, "a", encoding="utf-8") as f:
        f.write("```json\n" + txt + "\n```\n")
