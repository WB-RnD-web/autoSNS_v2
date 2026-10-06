#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry_no_runner 검증 — 실제로 있었던 실패 모양으로 판정을 확인한다.

이 판정이 틀리면 두 방향 모두 사고다.
  · 너무 넓으면 → 업로드까지 끝난 실행을 다시 돌려 같은 영상이 두 번 올라간다
  · 너무 좁으면 → 실행기를 못 잡은 아침 운세가 또 반나절 비어 있는다(고치려던 문제 그대로)

실행: python tools/test_retry_no_runner.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import retry_no_runner as R  # noqa: E402

FAIL = []


def check(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got else ""))
    if not cond:
        FAIL.append(name)


# 2026-10-06 06:11 routine/fortune → shorts.yml 시도 1 (API 응답 그대로 줄임)
NO_RUNNER_1006 = {"name": "build-and-upload", "status": "completed", "conclusion": "cancelled",
                  "runner_id": 0, "runner_name": "", "runner_group_name": "", "steps": []}
# 2026-07-30 같은 모양 — 잡 결론이 failure 로 찍힌 경우
NO_RUNNER_0730 = {"name": "build-and-upload", "status": "completed", "conclusion": "failure",
                  "runner_id": 0, "runner_name": None, "steps": []}
# 2026-09-25 routine/politics — 실행기를 받아 17단계가 돌고 실패(코드·데이터 문제)
RAN_0925 = {"name": "build-and-upload", "status": "completed", "conclusion": "failure",
            "runner_id": 1000001986, "runner_name": "GitHub Actions 1000001986",
            "steps": [{"name": f"s{i}", "conclusion": "success"} for i in range(16)] + [{"name": "업로드", "conclusion": "failure"}]}
OK_JOB = {"name": "check", "conclusion": "success", "runner_id": 7, "runner_name": "x", "steps": [{"name": "a"}]}


def run(concl="failure", attempt=1):
    return {"id": 37374341428, "name": "뉴스 스토리보드 → HyperFrames 쇼츠 → 유튜브 업로드 (v2)",
            "conclusion": concl, "run_attempt": attempt, "head_branch": "routine/fortune"}


print("── 판정 ──")
ok, why = R.should_retry(run(), [NO_RUNNER_1006])
check("10/6 아침 운세(실행기 못 잡음 · 잡 cancelled) → 다시 돌린다", ok, why)
check("…두 번째 시도라고 적는다", "2번째" in why, why)
check("7/30 모양(잡 failure · runner 0 · 단계 0) → 다시 돌린다", R.should_retry(run(), [NO_RUNNER_0730])[0])
ok, why = R.should_retry(run(), [RAN_0925])
check("단계가 돈 실패(9/25 정치) → 안 돌린다(업로드됐을 수 있다)", not ok and "단계가 돈" in why, why)
check("실행기 못 잡은 잡 + 단계가 돈 실패 잡이 섞이면 → 안 돌린다",
      not R.should_retry(run(), [NO_RUNNER_1006, dict(RAN_0925, name="render")])[0])
check("성공한 잡은 판정에서 뺀다(나머지가 전부 실행기 없음이면 돌린다)",
      R.should_retry(run(), [OK_JOB, NO_RUNNER_1006])[0])
check("runner_id 는 0 인데 단계가 있으면 → 안 돌린다", not R.should_retry(run(), [dict(NO_RUNNER_1006, steps=[{"name": "a"}])])[0])
check("단계는 없는데 runner 이름이 있으면 → 안 돌린다", not R.should_retry(run(), [dict(NO_RUNNER_1006, runner_name="GitHub Actions 9")])[0])
ok, why = R.should_retry(run("cancelled"), [NO_RUNNER_1006])
check("사람이 누른 취소(실행 결론 cancelled) → 안 돌린다", not ok and "cancelled" in why, why)
check("성공한 실행 → 안 돌린다", not R.should_retry(run("success"), [OK_JOB])[0])
check("2번째 시도가 또 실행기를 못 잡으면 → 3번째로 한 번 더", R.should_retry(run(attempt=2), [NO_RUNNER_1006])[0])
ok, why = R.should_retry(run(attempt=3), [NO_RUNNER_1006])
check("3번째 시도까지 실패하면 → 멈춘다(상한)", not ok and "상한" in why, why)
check("잡 목록이 비면 → 안 돌린다", not R.should_retry(run(), [])[0])

print("── 명령줄 ──")
with tempfile.TemporaryDirectory() as td:
    ev, jb, out = (os.path.join(td, n) for n in ("event.json", "jobs.json", "out.txt"))
    json.dump({"workflow_run": run()}, open(ev, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"total_count": 1, "jobs": [NO_RUNNER_1006]}, open(jb, "w", encoding="utf-8"))
    p = subprocess.run([sys.executable, os.path.join(HERE, "retry_no_runner.py"), "--event", ev, "--jobs", jb],
                       capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, GITHUB_OUTPUT=out))
    check("GITHUB_OUTPUT 에 retry=true", p.returncode == 0 and open(out, encoding="utf-8").read() == "retry=true\n", p.stderr[-300:])
    json.dump({"jobs": [RAN_0925]}, open(jb, "w", encoding="utf-8"))
    os.remove(out)
    p = subprocess.run([sys.executable, os.path.join(HERE, "retry_no_runner.py"), "--event", ev, "--jobs", jb],
                       capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, GITHUB_OUTPUT=out))
    check("…단계가 돈 실패면 retry=false · 종료 코드 0(빨간불 안 만든다)",
          p.returncode == 0 and open(out, encoding="utf-8").read() == "retry=false\n")

print("── 워크플로 연결 ──")
wfd = os.path.join(ROOT, ".github", "workflows")
flows = {n: open(os.path.join(wfd, n), encoding="utf-8").read() for n in sorted(os.listdir(wfd)) if n.endswith(".yml")}
me = flows["retry-no-runner.yml"]


def wf_name(text):
    m = re.search(r"^name:\s*(.+?)\s*$", text, re.M)
    return m.group(1).strip("\"'") if m else ""


def triggers(text):
    """on: 바로 아래 키들(push·schedule·workflow_dispatch …)."""
    keys, inside = set(), False
    for ln in text.splitlines():
        if re.match(r"^on:\s*$", ln):
            inside = True
            continue
        if inside:
            if ln and not ln[0].isspace() and not ln.startswith("#"):
                break
            m = re.match(r"^  ([a-z_]+):", ln)
            if m:
                keys.add(m.group(1))
    return keys


listed = re.findall(r'^\s{6}- "(.+)"\s*$', me.split("types:")[0], re.M)
names = {wf_name(t): n for n, t in flows.items()}
check("감시 목록의 이름이 전부 실제 워크플로 이름이다(틀리면 조용히 아무 일도 안 일어난다)",
      bool(listed) and all(x in names for x in listed), [x for x in listed if x not in names])
need = sorted(n for n, t in flows.items() if triggers(t) & {"push", "schedule"})
missing = [n for n in need if wf_name(flows[n]) not in listed]
check("push·schedule 로 도는 워크플로는 전부 감시한다", not missing, missing)
check("자기 자신은 감시하지 않는다(무한 반복 방지)", wf_name(me) not in listed)
check("workflow_run completed 로만 깬다(push·schedule 없음)",
      triggers(me) == {"workflow_run"} and "types: [completed]" in me)
check("권한: actions write · contents read 뿐", "actions: write" in me and "contents: read" in me and "contents: write" not in me)
check("실패 · 시도 3 미만일 때만 잡이 뜬다 · 레포 변수로 끈다",
      "conclusion == 'failure'" in me and "run_attempt < 3" in me and "(vars.RETRY_NO_RUNNER || '1') != '0'" in me)
check("…상한이 코드와 같다", R.MAX_ATTEMPT == 3)
body = me[re.search(r"^jobs:", me, re.M).start():]
check("그 시도의 잡을 읽고 → 판정 스크립트 → 성공한 잡은 놔두고 실패한 잡만 다시",
      "/attempts/$ATTEMPT/jobs" in body and "tools/retry_no_runner.py" in body and "/rerun-failed-jobs" in body
      and body.index("/attempts/$ATTEMPT/jobs") < body.index("tools/retry_no_runner.py") < body.index("/rerun-failed-jobs"))
check("판정이 true 일 때만 다시 돌린다", "if: steps.plan.outputs.retry == 'true'" in me)
check("이벤트 내용을 셸에 직접 끼우지 않는다(제목에 따옴표가 있어도 안전)",
      "toJson(github.event" not in me and "head_commit" not in me and "display_title" not in me)
check("코드는 main 에서", "ref: main" in me)

print()
if FAIL:
    print(f"❌ 실패 {len(FAIL)}개")
    sys.exit(1)
print("✅ 전부 통과")
