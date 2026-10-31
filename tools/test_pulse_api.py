#!/usr/bin/env python3
"""채널 맥박 API 판 회귀 테스트 — 네트워크·키 없이(가짜 클라이언트).

    python tools/test_pulse_api.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pulse_api as PA  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


class FakeStream:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=self.text)],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200,
                                                     cache_creation_input_tokens=0, cache_read_input_tokens=500))


class FakeClient:
    """답을 차례로 돌려주고, 받은 messages 를 기록한다."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.answers.pop(0))


def mini_repo(td):
    """EDITABLE 파일 + 맥박 테스트 자리만 있는 작은 git 레포(테스트는 늘 통과하는 가짜)."""
    os.makedirs(os.path.join(td, "tools"))
    shutil.copy(os.path.join(ROOT, "tools", "PULSE.md"), os.path.join(td, "tools", "PULSE.md"))
    with open(os.path.join(td, "tools", "pulse_experiments.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write('{\n "experiments": [\n  {"id": "a", "status": "open"},\n  {"id": "b", "status": "open"}\n ]\n}\n')
    with open(os.path.join(td, "tools", "pulse_formats.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write('{"formats": []}\n')
    for t in ("test_pulse.py", "test_runway.py"):
        with open(os.path.join(td, "tools", t), "w", encoding="utf-8") as f:
            f.write("print('ok')\n")
    g = ["git", "-C", td, "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(g[:3] + ["init", "-q"], check=True)
    subprocess.run(g[:3] + ["config", "core.autocrlf", "false"], check=True)
    subprocess.run(g + ["add", "-A"], check=True)
    subprocess.run(g + ["commit", "-q", "-m", "init"], check=True)


print("\n── 1. 출력 읽기 ──")
ck("펜스·앞뒤 말이 붙어도 객체를 꺼낸다",
   PA.parse('좋아요\n```json\n{"fill": {"date": "x"}, "pr_edits": null}\n```')["fill"]["date"] == "x")
for bad in ("그냥 말", '{"date": "x"}', "[1, 2]"):
    try:
        PA.parse(bad)
        ck(f"잘못된 출력은 거절: {bad!r}", False)
    except ValueError:
        ck(f"잘못된 출력은 거절: {bad!r}", True)

print("\n── 2. PR 바꾸기는 정해진 파일·정확한 문자열만 ──")
with tempfile.TemporaryDirectory() as td:
    mini_repo(td)
    for p in (".github/workflows/shorts.yml", "tools/pulse.py", "tools/PULSE.md", "output/news/x.json", "../etc/passwd"):
        _, errs = PA.apply_edits([{"path": p, "old": "a", "new": "b"}], td)
        ck(f"{p} 는 못 고친다", errs and "고칠 수 없다" in errs[0], str(errs))
    _, errs = PA.apply_edits([{"path": "tools/pulse_experiments.json", "old": '"status": "open"', "new": "x"}], td)
    ck("두 번 나오는 old 는 거절(애매함)", errs and "2번" in errs[0], str(errs))
    _, errs = PA.apply_edits([{"path": "tools/pulse_experiments.json", "old": "없는 글", "new": "x"}], td)
    ck("없는 old 는 거절", errs and "0번" in errs[0], str(errs))
    _, errs = PA.apply_edits([{"path": "tools/pulse_experiments.json", "old": '{"id": "a", "status": "open"}',
                               "new": '{"id": "a", "status": "stopped"}'},
                              {"path": "tools/pulse.py", "old": "a", "new": "b"}], td)
    ck("하나라도 틀리면 아무것도 안 바꾼다", errs and '"a", "status": "open"' in PA._read(os.path.join(td, "tools", "pulse_experiments.json")))
    day_dir = os.path.join(td, "day")
    os.makedirs(day_dir)
    errs = PA.make_patch([{"path": "tools/pulse_experiments.json", "old": '{"id": "a", "status": "open"}',
                           "new": '{"id": "a", "status": "stopped"}'}], day_dir, td)
    pt = PA._read(os.path.join(day_dir, "pr.patch"))
    ck("make_patch: git diff 로 pr.patch 를 쓴다", not errs and pt.startswith("diff --git") and '"stopped"' in pt, str(errs))
    ck("make_patch: 작업 트리는 되돌린다", '"a", "status": "open"' in PA._read(os.path.join(td, "tools", "pulse_experiments.json")))
    errs = PA.make_patch([{"path": "tools/pulse_experiments.json", "old": ' ]\n}', "new": " ]"}], day_dir, td)
    ck("make_patch: JSON 을 깨는 바꾸기는 오류", errs and "깨진다" in errs[0], str(errs))

print("\n── 3. 검사 오류를 붙여 다시 묻고, 통과하면 멈춘다 ──")
with tempfile.TemporaryDirectory() as td:
    mini_repo(td)
    out_root = os.path.join(td, "output", "pulse")
    for d in ("2026-10-29", "2026-10-30", "2026-10-31"):
        os.makedirs(os.path.join(out_root, d))
        with open(os.path.join(out_root, d, "pulse.json"), "w", encoding="utf-8") as f:
            json.dump({"date": d, "radar_at": "t", "radar_age_h": 2, "flags": [{"id": f"F:{d}", "days": 1}]}, f)
        if d != "2026-10-31":
            with open(os.path.join(out_root, d, "fill.json"), "w", encoding="utf-8") as f:
                json.dump({"date": d, "summary": f"지난 요약 {d}"}, f, ensure_ascii=False)
    radar = os.path.join(td, "radar")
    os.makedirs(radar)
    with open(os.path.join(radar, "report.md"), "w", encoding="utf-8") as f:
        f.write("# 레이더 보고서 표시\n")
    seen = []

    def checker(day_dir):
        F = json.load(open(os.path.join(day_dir, "fill.json"), encoding="utf-8"))
        seen.append(F.get("summary"))
        return [] if F.get("summary") == "좋음" else ["summary 가 이상하다"]

    fc = FakeClient(['{"fill": {"summary": "나쁨", "pr": null}, "pr_edits": null}',
                     "펜스 없이 말만",
                     '{"fill": {"summary": "좋음", "pr": null}, "pr_edits": null}'])
    info = PA.write("2026-10-31", out_root, radar, client=fc, checker=checker, root=td)
    ck("세 번째 시도에서 통과", info["ok"] and info["tries"] == 3 and seen == ["나쁨", "좋음"], str((info, seen)))
    last = fc.calls[-1]["messages"]
    ck("다시 물을 때 앞 답과 검사 오류를 붙인다",
       len(last) == 5 and last[1]["role"] == "assistant" and "summary 가 이상하다" in last[2]["content"]
       and "읽을 수 없다" in last[4]["content"], json.dumps(last, ensure_ascii=False)[:400])
    first = fc.calls[0]
    ck("system = PULSE.md + API 절", "채널 맥박" in first["system"] and "이번 실행 방식(API)" in first["system"])
    blk = first["messages"][0]["content"][0]
    ck("자료 덩어리는 캐시에 올린다(다시 물을 때 싸게)", blk.get("cache_control") == {"type": "ephemeral"})
    um = blk["text"]
    ck("사용자 메시지: 오늘 pulse.json·레이더·지난 fill·실험 파일이 다 들어간다",
       "F:2026-10-31" in um and "레이더 보고서 표시" in um and "지난 요약 2026-10-30" in um and '"id": "a"' in um)
    with open(os.path.join(out_root, "2026-10-31", "api.json"), encoding="utf-8") as f:
        _j = json.load(f)
    ck("api.json: 토큰·달러·시도별 오류를 남긴다", _j["tokens"]["input"] == 3000 and _j["tokens"]["cache_read"] == 1500
       and _j["history"] == [["summary 가 이상하다"], ["출력을 읽을 수 없다: JSON 객체가 없다"], []], str(_j))
    fc = FakeClient(['{"fill": {"summary": "x", "pr": null}}'] * PA.TRIES)
    info = PA.write("2026-10-31", out_root, radar, client=fc, checker=lambda d: ["늘 실패"], root=td)
    ck("끝까지 실패하면 ok=False(워크플로가 실패로 끝난다)", not info["ok"] and info["tries"] == PA.TRIES)
    fc = FakeClient(['{"fill": {"summary": "좋음", "pr": {"slug": "s"}}, "pr_edits": null}',
                     '{"fill": {"summary": "좋음", "pr": null}, "pr_edits": null}'])
    info = PA.write("2026-10-31", out_root, radar, client=fc, checker=checker, root=td)
    ck("pr 이 있는데 pr_edits 가 없으면 오류로 돌려보낸다", info["ok"] and info["tries"] == 2
       and "pr_edits 가 비었다" in fc.calls[-1]["messages"][-1]["content"])

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
