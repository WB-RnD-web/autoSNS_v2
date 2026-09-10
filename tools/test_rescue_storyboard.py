#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rescue_storyboard 검증 — 진짜 git 저장소를 만들어서 판단을 확인한다.

이 판단이 틀리면 두 방향 모두 사고다.
  · 너무 넓으면 → 사람의 개발 브랜치 커밋을 운영 브랜치로 밀어넣고 영상이 올라간다
  · 너무 좁으면 → 미아를 못 살리고 조용히 샌다(고치려던 문제 그대로)

그래서 목(mock) 대신 실제 저장소를 만들어 돌린다. git 동작을 흉내내면
정작 검증하려는 부분이 안 검증된다.

실행: python tools/test_rescue_storyboard.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAIL = []


def check(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got else ""))
    if not cond:
        FAIL.append(name)


def sh(*args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}\n{r.stderr}")
    return r.stdout.strip()


def write(root, path, body="{}"):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fp:
        fp.write(body)


def commit(root, paths, msg):
    for p in paths:
        sh("git", "add", p, cwd=root)
    sh("git", "commit", "-q", "-m", msg, cwd=root)
    return sh("git", "rev-parse", "HEAD", cwd=root)


def build_repo(tmp):
    """origin(베어) + 작업본. routine/stock 에는 어제 파일이 이미 있다."""
    bare = os.path.join(tmp, "origin.git")
    work = os.path.join(tmp, "work")
    sh("git", "init", "-q", "--bare", "-b", "main", bare)
    sh("git", "init", "-q", "-b", "main", work)
    sh("git", "-C", work, "config", "user.email", "t@t")
    sh("git", "-C", work, "config", "user.name", "t")
    sh("git", "-C", work, "remote", "add", "origin", bare)

    write(work, "README.md", "x")
    commit(work, ["README.md"], "init")
    sh("git", "-C", work, "push", "-q", "origin", "main")

    # routine/stock — 어제 산출물이 이미 발행된 상태
    sh("git", "-C", work, "checkout", "-q", "-B", "routine/stock")
    write(work, "output/news/2026-09-09_stock_storyboard.json")
    commit(work, ["output/news/2026-09-09_stock_storyboard.json"],
           "chore: 오늘 스토리보드(루틴) stock")
    sh("git", "-C", work, "push", "-q", "origin", "routine/stock")
    sh("git", "-C", work, "checkout", "-q", "main")
    sh("git", "-C", work, "fetch", "-q", "origin",
       "+refs/heads/*:refs/remotes/origin/*")
    return work


def run_plan(work, before, after, branch):
    """cwd 를 저장소로 바꾼 뒤 plan() 을 호출한다(git 이 cwd 를 본다)."""
    import importlib
    cur = os.getcwd()
    os.chdir(work)
    try:
        mod = importlib.import_module("rescue_storyboard")
        importlib.reload(mod)
        return mod.plan(before, after, branch)
    finally:
        os.chdir(cur)


with tempfile.TemporaryDirectory() as tmp:
    work = build_repo(tmp)

    print("── ① 루틴이 claude/* 에 산출물만 커밋 → 옮긴다")
    sh("git", "-C", work, "checkout", "-q", "-B", "claude/dazzling-fermat-1o3nyq",
       "origin/main")
    base = sh("git", "-C", work, "rev-parse", "HEAD")
    write(work, "output/news/2026-09-10_stock_storyboard.json")
    sha = commit(work, ["output/news/2026-09-10_stock_storyboard.json"],
                 "chore: 오늘 스토리보드(루틴) stock")
    moves, notes = run_plan(work, base, sha, "claude/dazzling-fermat-1o3nyq")
    check("1건을 옮긴다", len(moves) == 1, f"{len(moves)}건")
    if moves:
        check("목적지가 routine/stock", moves[0][2] == "routine/stock", moves[0][2])
        check("파일이 오늘 것", "2026-09-10" in moves[0][1], moves[0][1])

    print("\n── ② 코드가 섞인 커밋 → 사람 커밋으로 보고 건드리지 않는다")
    sh("git", "-C", work, "checkout", "-q", "-B", "claude/my-dev-work", "origin/main")
    base2 = sh("git", "-C", work, "rev-parse", "HEAD")
    write(work, "output/news/2026-09-10_love_storyboard.json")
    write(work, "pipeline/thing.py", "print(1)\n")
    sha2 = commit(work, ["output/news/2026-09-10_love_storyboard.json",
                         "pipeline/thing.py"], "feat: 뭔가 만들다가 샘플도 같이")
    moves2, notes2 = run_plan(work, base2, sha2, "claude/my-dev-work")
    check("아무것도 옮기지 않는다", len(moves2) == 0, f"{len(moves2)}건")
    check("이유를 남긴다", any("섞였다" in n for n in notes2),
          "; ".join(notes2)[:60])

    print("\n── ③ 목적지에 이미 있는 파일 → 건너뛴다(재발행 방지)")
    sh("git", "-C", work, "checkout", "-q", "-B", "claude/dup", "origin/main")
    base3 = sh("git", "-C", work, "rev-parse", "HEAD")
    write(work, "output/news/2026-09-09_stock_storyboard.json")   # 어제 것 = 이미 발행됨
    sha3 = commit(work, ["output/news/2026-09-09_stock_storyboard.json"],
                  "chore: 오늘 스토리보드(루틴) stock")
    moves3, notes3 = run_plan(work, base3, sha3, "claude/dup")
    check("옮기지 않는다", len(moves3) == 0, f"{len(moves3)}건")
    check("이미 있다고 말한다", any("이미" in n for n in notes3),
          "; ".join(notes3)[:60])

    print("\n── ④ 정상 브랜치로의 push → 할 일 없음")
    m4, n4 = run_plan(work, base, sha, "routine/stock")
    check("routine/* 는 건드리지 않는다", len(m4) == 0, f"{len(m4)}건")
    m4b, _ = run_plan(work, base, sha, "main")
    check("main 도 건드리지 않는다", len(m4b) == 0, f"{len(m4b)}건")

    print("\n── ⑤ 새 브랜치 push (before=0000…) 도 처리한다")
    zero = "0" * 40
    moves5, _ = run_plan(work, zero, sha, "claude/dazzling-fermat-1o3nyq")
    check("그 커밋 하나만 본다", len(moves5) == 1, f"{len(moves5)}건")

    print("\n── ⑥ SCP 산출물도 옮긴다 (경로 모양이 다르다)")
    sh("git", "-C", work, "checkout", "-q", "-B", "claude/scp-orphan", "origin/main")
    base6 = sh("git", "-C", work, "rev-parse", "HEAD")
    write(work, "output/scp/scp-9683_2026-09-10.json")
    sha6 = commit(work, ["output/scp/scp-9683_2026-09-10.json"],
                  "scp: SCP-9683 어쩌고")
    moves6, _ = run_plan(work, base6, sha6, "claude/scp-orphan")
    check("routine/scp 로 보낸다",
          len(moves6) == 1 and moves6[0][2] == "routine/scp",
          moves6[0][2] if moves6 else "0건")

    print("\n── ⑦ 산출물이 없는 push → 조용히 통과")
    sh("git", "-C", work, "checkout", "-q", "-B", "claude/code-only", "origin/main")
    base7 = sh("git", "-C", work, "rev-parse", "HEAD")
    write(work, "pipeline/other.py", "x=1\n")
    sha7 = commit(work, ["pipeline/other.py"], "chore: 코드만")
    moves7, _ = run_plan(work, base7, sha7, "claude/code-only")
    check("옮길 것 없음", len(moves7) == 0, f"{len(moves7)}건")

print("")
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: " + ", ".join(FAIL))
    raise SystemExit(1)
print("🎉 전부 통과")
