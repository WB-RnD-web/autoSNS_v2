#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""엉뚱한 브랜치로 간 루틴 산출물을 ★어디로 되돌릴지 계산한다.

find_orphan_storyboards.py 는 "이미 샌 것을 찾는다". 이 스크립트는 "방금 샌 것을
어디로 되돌릴지" 만 계산한다 — git 조작은 하지 않는다(워크플로가 한다).
그래서 판단 로직만 따로 테스트할 수 있다.

왜 필요한가 — 2026-09-10 확인
  루틴 세션에는 `claude/…` 브랜치에서 개발하라는 지시가 자동으로 주입된다. 그게 루틴
  프롬프트의 `routine/<토픽>` push 지시와 충돌하고, ★어느 쪽이 이기는지가 회차마다 다르다.
  루틴 7개의 설정(outcome_branch)은 전부 동일한데도 같은 루틴이 어제는 맞고 오늘은 틀린다.

    주식(국장)  09-08 ✅  09-09 ✅  09-10 ❌
    별자리      09-09 ✅            09-10 ❌   ← 09-10 에 처음 걸렸다

  09-02 에 프롬프트를 고쳐봤지만 09-07·09-09·09-10 또 터졌다. 지시로는 못 고친다.
  그래서 지시에 기대지 않고 결정론적으로 되돌린다.

무엇을 옮기나 — ★세 겹으로 좁힌다. 사람의 개발 브랜치를 건드리면 안 되기 때문이다.
  ① 경로가 루틴 산출물 모양이다 (find_orphan 의 WATCH 를 그대로 쓴다)
  ② 그 커밋이 ★산출물만 담고 있다 — 코드가 한 줄이라도 섞이면 사람 커밋으로 보고 건드리지 않는다
  ③ 새로 ★추가된(A) 파일이다. 수정은 옮기지 않는다 (cherry-pick 이 충돌할 수 있고,
     이미 발행된 것을 덮어쓸 수 있다)
  ④ 목적지 routine/<토픽> 에 이미 같은 파일이 있으면 건너뛴다

②가 핵심이다. 토픽 이름을 하드코딩하지 않으면서 사람 커밋을 걸러낸다 —
루틴은 산출물 하나만 커밋하고, 사람은 코드를 함께 만진다.

사용:
  python tools/rescue_storyboard.py --after <sha> [--before <sha>] [--branch <name>]
                                    [--out plan.tsv]
출력(TSV, stdout 또는 --out): <원본커밋sha>\t<파일경로>\t<목적지브랜치>
사람이 읽는 설명은 stderr 로 나간다 — 파이프로 받아도 섞이지 않는다.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_orphan_storyboards import WATCH, git, guess_topic, is_home  # noqa: E402


def _ok(*args: str) -> bool:
    """git 명령이 성공했나만 본다(출력은 안 쓴다)."""
    return subprocess.run(["git", *args], capture_output=True).returncode == 0


def has_file(branch: str, path: str) -> bool:
    return _ok("cat-file", "-e", f"origin/{branch}:{path}")


def has_branch(branch: str) -> bool:
    return _ok("rev-parse", "--verify", "-q", f"origin/{branch}")


def is_output(path: str) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in WATCH)


def commits_in(before: str | None, after: str) -> list[str]:
    """이번 push 에 담긴 커밋들(오래된 것부터).

    새 브랜치를 만든 push 는 before 가 0000… 으로 온다. 그럴 때 before..after 를 쓰면
    브랜치 전체 역사가 잡히므로, 그 커밋 하나만 본다.
    """
    if not before or set(before) <= {"0"}:
        rng = f"{after}~1..{after}"
    else:
        rng = f"{before}..{after}"
    return [l for l in git("rev-list", "--reverse", rng).splitlines() if l.strip()]


def touched(sha: str) -> list[str]:
    return [l.strip() for l in git("show", "--name-only", "--format=", sha).splitlines()
            if l.strip()]


def added(sha: str) -> set[str]:
    out = git("show", "--name-status", "--format=", sha)
    res = set()
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].startswith("A"):
            res.add(parts[-1])
    return res


def plan(before: str | None, after: str,
         branch: str = "") -> tuple[list[tuple[str, str, str]], list[str]]:
    """(옮길 것들, 사람이 읽을 메모들) 반환. 옮길 것이 없으면 빈 목록."""
    notes: list[str] = []
    if branch and is_home(branch):
        return [], [f"'{branch}' 는 이미 트리거가 걸리는 브랜치다 — 할 일 없음"]

    moves: list[tuple[str, str, str]] = []
    for sha in commits_in(before, after):
        files = touched(sha)
        outs = [f for f in files if is_output(f)]
        if not outs:
            continue
        if len(outs) != len(files):
            extra = [f for f in files if not is_output(f)]
            notes.append(f"{sha[:7]} 건너뜀 — 산출물 외 파일이 섞였다(사람 커밋으로 본다): "
                         + ", ".join(extra[:3]))
            continue
        new = added(sha)
        for f in outs:
            if f not in new:
                notes.append(f"{sha[:7]} {f} 건너뜀 — 새로 추가된 파일이 아니다")
                continue
            topic = guess_topic(f)
            if not topic:
                notes.append(f"{sha[:7]} {f} 건너뜀 — 경로에서 목적지를 짐작할 수 없다")
                continue
            target = f"routine/{topic}"
            if has_branch(target) and has_file(target, f):
                notes.append(f"{sha[:7]} {f} 건너뜀 — 이미 {target} 에 있다")
                continue
            if not has_branch(target):
                notes.append(f"{target} 가 아직 없다 — push 가 새로 만든다")
            moves.append((sha, f, target))
    return moves, notes


def main() -> int:
    ap = argparse.ArgumentParser(
        description="엉뚱한 브랜치로 간 루틴 산출물의 복구 계획을 계산")
    ap.add_argument("--after", required=True, help="push 후 커밋 sha (github.sha)")
    ap.add_argument("--before", default="", help="push 전 커밋 sha (github.event.before)")
    ap.add_argument("--branch", default="", help="push 된 브랜치 이름 (github.ref_name)")
    ap.add_argument("--out", help="TSV 를 이 파일로 (기본 stdout)")
    args = ap.parse_args()

    moves, notes = plan(args.before, args.after, args.branch)

    for n in notes:
        print(f"   · {n}", file=sys.stderr)
    if not moves:
        print("옮길 산출물 없음.", file=sys.stderr)
    else:
        print(f"옮길 산출물 {len(moves)}건:", file=sys.stderr)
        for sha, f, target in moves:
            print(f"   {f}  →  {target}   (원본 {sha[:7]})", file=sys.stderr)

    lines = "".join(f"{s}\t{f}\t{t}\n" for s, f, t in moves)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fp:
            fp.write(lines)
    else:
        sys.stdout.write(lines)
    return 0        # 옮길 게 없는 건 정상이다 — 실패로 치지 않는다


if __name__ == "__main__":
    raise SystemExit(main())
