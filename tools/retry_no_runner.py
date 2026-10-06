#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실행기(runner)를 못 잡고 실패한 실행만 골라 '다시 돌려도 되는지' 판정한다.

git·API 호출은 하지 않는다(워크플로 retry-no-runner.yml 이 한다). 판단만 따로 테스트한다.

왜 필요한가 — 2026-10-06
  06:13 매일 운세(routine/fortune → shorts.yml)가 GitHub 실행기를 15분 동안 못 잡고 실패했다.
    실행 결론 failure · 잡 결론 cancelled · runner_id 0 · runner_name '' · 단계 0개
    (메시지: "The job was not acquired by Runner of type hosted even after multiple attempts")
  사람이 14:40 에 손으로 다시 돌릴 때까지 아침 자리가 비었고, 그날 06~10시 조회가 전날보다 36% 적었다.
  같은 모양의 실패가 7/28~7/31 에도 하루 여러 건 있었다(잡 결론 failure · runner_id 0 · 단계 0개).

언제 다시 돌리나 — ★셋 다 맞을 때만
  ① 실행 결론이 failure 다. 사람이 누른 취소(cancelled)는 건드리지 않는다.
  ② 성공하지 못한 잡이 ★전부 '실행기 없음'이다 — runner_id 가 0/없음이고, 단계가 하나도 안 돌았다.
     단계가 하나라도 돌았으면 건드리지 않는다. 업로드가 이미 됐을 수 있다(같은 영상이 두 번 올라간다).
  ③ 시도 횟수가 MAX_ATTEMPT 보다 작다 — 실행기 장애가 길어도 다시 돌리기는 두 번까지만.

사용:
  python tools/retry_no_runner.py --event "$GITHUB_EVENT_PATH" --jobs jobs.json
  jobs.json = GET /repos/{repo}/actions/runs/{id}/attempts/{n}/jobs 의 응답.
  GITHUB_OUTPUT 이 있으면 retry=true|false 를 쓴다. 이유는 stdout 에 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

MAX_ATTEMPT = 3          # 첫 시도 + 다시 돌리기 두 번
DONE_OK = ("success", "skipped", "neutral")


def no_runner(job: dict) -> bool:
    """실행기를 받은 적이 없는 잡 — 단계가 하나도 안 돌았다."""
    return not (job.get("runner_id") or 0) and not (job.get("runner_name") or "") and not (job.get("steps") or [])


def should_retry(run: dict, jobs: list[dict]) -> tuple[bool, str]:
    concl = run.get("conclusion")
    if concl != "failure":
        return False, f"결론이 {concl} — failure 만 본다(사람이 누른 취소는 그대로 둔다)"
    attempt = int(run.get("run_attempt") or 1)
    if attempt >= MAX_ATTEMPT:
        return False, f"이미 {attempt}번째 시도 — 더 돌리지 않는다(상한 {MAX_ATTEMPT})"
    bad = [j for j in jobs if j.get("conclusion") not in DONE_OK]
    if not bad:
        return False, "성공 못 한 잡이 없다 — 잡 목록이 비었거나 다른 이유의 실패"
    ran = [j.get("name", "?") for j in bad if not no_runner(j)]
    if ran:
        return False, f"단계가 돈 잡이 있다({', '.join(ran)}) — 업로드가 됐을 수 있어 다시 돌리지 않는다"
    return True, f"실행기를 못 잡은 잡 {len(bad)}개({', '.join(j.get('name', '?') for j in bad)}) — {attempt + 1}번째 시도로 다시 돌린다"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True, help="GITHUB_EVENT_PATH (workflow_run 이벤트)")
    ap.add_argument("--jobs", required=True, help="그 시도의 잡 목록(API 응답 JSON)")
    a = ap.parse_args(argv)
    run = json.load(open(a.event, encoding="utf-8")).get("workflow_run") or {}
    jobs = json.load(open(a.jobs, encoding="utf-8")).get("jobs") or []
    ok, why = should_retry(run, jobs)
    print(f"{run.get('name', '?')} #{run.get('id', '?')} 시도 {run.get('run_attempt', '?')} ({run.get('head_branch', '?')}): {why}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"retry={'true' if ok else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
