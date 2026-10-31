#!/usr/bin/env python3
"""인스타 대본 API 판 회귀 테스트 — 네트워크·키 없이(가짜 클라이언트).

    python insta/test_pick_api.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pick_api as A  # noqa: E402
import pick_plan as P  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


class FakeClient:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        text = self.answers.pop(0)

        class S:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def get_final_message(s):
                return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)],
                                       usage=SimpleNamespace(input_tokens=100, output_tokens=50,
                                                             cache_creation_input_tokens=1000, cache_read_input_tokens=0))
        return S()


def fake_root(td):
    os.makedirs(os.path.join(td, "insta", "samples"))
    with open(os.path.join(td, "insta", "SCI_WRITING.md"), "w", encoding="utf-8") as f:
        f.write("# 쓰는 법 표시\n")
    with open(os.path.join(td, "insta", "samples", "ex.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": "sci", "slug": "exemplar-mark"}, f)


INFO = {"date": "2026-10-31", "due": True, "slot": "b", "slot_label": "저녁 편", "kind": "sci", "src_n": 111,
        "file": "output/insta_pick/2026-10-31_sci_<slug>.json", "exemplar": "insta/samples/ex.json",
        "writing": "insta/SCI_WRITING.md", "entry": {"n": 111, "facts": [{"fact": "사실 표시"}]}}

print("\n── 1. 출력·파일 이름 ──")
ck("펜스가 붙어도 객체를 꺼낸다", A.parse('```json\n{"slug": "a-b"}\n```')["slug"] == "a-b")
ck("파일 이름 = next 의 file 에 slug", A.file_for(INFO, {"slug": "titan-no-suit"}) == "output/insta_pick/2026-10-31_sci_titan-no-suit.json")
for bad in ("Titan", "a_b", "../x", ""):
    try:
        A.file_for(INFO, {"slug": bad})
        ck(f"이상한 slug 거절: {bad!r}", False)
    except ValueError:
        ck(f"이상한 slug 거절: {bad!r}", True)

print("\n── 2. 다시 묻기 고리 ──")
with tempfile.TemporaryDirectory() as td:
    fake_root(td)
    out = os.path.join(td, "out")
    good = {"date": "2026-10-31", "kind": "sci", "src_n": 111, "slug": "titan-no-suit", "ok": True}
    fc = FakeClient([json.dumps({**good, "ok": False}), json.dumps({**good, "src_n": 999}), json.dumps(good)])
    res = A.write(INFO, out, client=fc, checker=lambda s: [] if s.get("ok") else ["hook 이 이상하다"], root=td)
    ck("세 번째에 통과 · 파일을 쓴다", res["ok"] and res["tries"] == 3 and os.path.exists(os.path.join(out, "2026-10-31_sci_titan-no-suit.json")),
       str(res))
    ck("검사 오류 · next 와 다른 src_n 을 돌려보낸다", res["history"][0] == ["hook 이 이상하다"]
       and any("src_n" in x for x in res["history"][1]) and res["history"][2] == [], str(res["history"]))
    last = fc.calls[-1]["messages"]
    ck("다시 물을 때 앞 답 + 오류", last[1]["role"] == "assistant" and "src_n" in last[-1]["content"])
    first = fc.calls[0]
    ck("system = 작가 규칙 + writing 파일", "대본 작가" in first["system"] and "쓰는 법 표시" in first["system"])
    blk = first["messages"][0]["content"][0]
    ck("user = next + exemplar · 캐시에 올린다", "사실 표시" in blk["text"] and "exemplar-mark" in blk["text"]
       and blk.get("cache_control") == {"type": "ephemeral"})
    ck("토큰·달러를 센다", res["tokens"]["cache_write"] == 3000 and res["usd"] > 0)
    fc = FakeClient([json.dumps({**good, "kind": "bm_paper"})] * A.TRIES)
    res = A.write(INFO, out, client=fc, checker=lambda s: [], root=td)
    ck("꼴이 next 와 다르면 끝까지 실패(ok=False)", not res["ok"] and any("kind" in x for x in res["errors"]))

print("\n── 3. 오늘 날짜 견본이면 API 를 안 쓴다 ──")
with tempfile.TemporaryDirectory() as td:
    fake_root(td)
    with open(os.path.join(td, "insta", "samples", "today.json"), "w", encoding="utf-8") as f:
        json.dump({"date": "2026-10-31", "kind": "sci", "slug": "today-sample"}, f)
    fc = FakeClient([])
    res = A.write(INFO, os.path.join(td, "out"), client=fc, root=td)
    ck("견본 복사 · 호출 0번 · 0달러", res["ok"] and res["sample"] == "insta/samples/today.json" and not fc.calls and res["usd"] == 0
       and os.path.exists(os.path.join(td, "out", "2026-10-31_sci_today-sample.json")), str(res))

print("\n── 4. 비교 기간: 막 렌더한 편(오늘 가장 늦은 편)을 고른다 ──")
with tempfile.TemporaryDirectory() as td:
    d = dt.date(2026, 10, 31)
    for sl in P.slots_on(d):
        with open(os.path.join(td, f"2026-10-31_{P.kind_for(d, sl)}_x-{sl}.json"), "w", encoding="utf-8") as f:
            json.dump({"date": "2026-10-31"}, f)
    sl, p = A.target_slot(d, td)
    ck("10/31: 저녁 편(b) 파일", sl == "b" and p.endswith(f"_{P.kind_for(d, 'b')}_x-b.json"), str((sl, p)))
    os.remove(p)
    sl, p = A.target_slot(d, td)
    ck("저녁 편이 없으면 낮 편(a)", sl == "a", str((sl, p)))
    ck("대본이 없으면 (None, None)", A.target_slot(dt.date(2026, 10, 1), td) == (None, None))

print("\n── 5. 실제 writing·견본 파일이 있다(꼴마다) ──")
_miss = []
for _k in range(40):
    _d = dt.date(2026, 10, 25) + dt.timedelta(days=_k)
    for _sl in P.slots_on(_d):
        _i = P.next_info(_d, tempfile.gettempdir(), slot=_sl)
        if _i.get("due"):
            _miss += [p for p in A.writings(_i) + [_i["exemplar"]] if not os.path.exists(os.path.join(ROOT, p))]
ck("next 가 가리키는 writing·exemplar 가 레포에 있다(10/25부터 40일)", not _miss, str(sorted(set(_miss))))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
