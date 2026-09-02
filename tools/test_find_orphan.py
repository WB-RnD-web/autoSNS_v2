#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""미아 감지기 회귀 테스트.

    python tools/test_find_orphan.py

진짜 git 저장소를 임시로 만들어서 브랜치 구조를 재현한다 — 판정 로직이
'어느 브랜치에 있느냐' 하나에 달려 있어서, 그걸 흉내내면 검사가 의미가 없다.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_orphan_storyboards as F   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def sh(*a, cwd=None):
    subprocess.run(a, cwd=cwd, check=True, capture_output=True)


print("\n── 1. 토픽 추정 (★토픽 목록 하드코딩 없이) ──")
for path, want in [
    ("output/news/2026-09-02_stock_us_storyboard.json", "stock_us"),
    ("output/news/2026-09-02_stock_storyboard.json", "stock"),
    ("output/news/2026-08-21_horoscope_storyboard.json", "horoscope"),
    ("output/scp/scp-9245_2026-09-02.json", "scp"),
    ("output/asmr/2026-08-31_keyboard.json", "asmr"),
]:
    ck(f"{path.split('/')[-1]} → {want}", F.guess_topic(path) == want, F.guess_topic(path))

print("\n── 2. 어느 브랜치가 '집' 인가 ──")
for b, home in [("main", True), ("routine/stock", True), ("routine/scp", True),
                ("claude/upbeat-brown-sjsoo5", False), ("dev", False),
                ("routine-ish", False)]:
    ck(f"{b} → {'집' if home else '미아 후보'}", F.is_home(b) == home)

print("\n── 3. 실제 git 저장소로 판정 ──")
with tempfile.TemporaryDirectory() as td:
    up, wk = os.path.join(td, "up.git"), os.path.join(td, "wk")
    sh("git", "init", "--bare", "-q", "-b", "main", up)
    sh("git", "init", "-q", "-b", "main", wk)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        sh("git", "config", k, v, cwd=wk)
    sh("git", "remote", "add", "origin", up, cwd=wk)
    os.makedirs(os.path.join(wk, "output/news"))
    open(os.path.join(wk, "README.md"), "w").write("x")
    sh("git", "add", "-A", cwd=wk)
    sh("git", "commit", "-qm", "init", cwd=wk)
    sh("git", "push", "-q", "origin", "main", cwd=wk)

    def add(branch, path):
        sh("git", "checkout", "-qB", branch, "main", cwd=wk)
        full = os.path.join(wk, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w").write("{}")
        sh("git", "add", "-A", cwd=wk)
        sh("git", "commit", "-qm", f"add {path}", cwd=wk)
        sh("git", "push", "-q", "origin", branch, cwd=wk)

    add("routine/stock", "output/news/2026-09-02_stock_storyboard.json")
    add("claude/stray-1", "output/news/2026-09-02_stock_us_storyboard.json")
    add("claude/stray-2", "output/scp/scp-9999_2026-09-02.json")
    add("claude/normal-code", "pipeline/foo.py")

    cwd0 = os.getcwd()
    os.chdir(wk)
    try:
        sh("git", "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
        fresh, stale = F.find(max_age_days=3650, count_all=True)
        got = {(b, f) for b, f, _, _ in fresh}
        ck("미아 2건을 찾는다", len(got) == 2, str(got))
        ck("claude/stray-1 의 스토리보드", ("claude/stray-1",
            "output/news/2026-09-02_stock_us_storyboard.json") in got)
        ck("claude/stray-2 의 SCP 스펙", ("claude/stray-2",
            "output/scp/scp-9999_2026-09-02.json") in got)
        ck("routine/* 에 있는 건 미아가 아니다",
           not any("stock_storyboard" in f and "us" not in f for _, f in got))
        ck("코드만 바꾼 브랜치는 안 잡는다", not any(b == "claude/normal-code" for b, _ in got))

        # 같은 파일이 routine/* 에도 생기면 미아가 아니게 된다
        add("routine/stock_us", "output/news/2026-09-02_stock_us_storyboard.json")
        sh("git", "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
        fresh2, _ = F.find(max_age_days=3650, count_all=True)
        ck("routine/* 로 옮기면 미아에서 빠진다",
           not any("stock_us" in f for _, f, _, _ in fresh2), str(fresh2))

        # 오래된 것은 참고로만
        add("claude/stray-old", "output/news/2020-01-01_old_storyboard.json")
        sh("git", "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
        fr, st = F.find(max_age_days=3, count_all=False)
        ck("오래된 미아는 실패로 치지 않는다",
           any("2020-01-01" in f for _, f, _, _ in st)
           and not any("2020-01-01" in f for _, f, _, _ in fr))
        ck("--all 이면 오래된 것도 실패로 친다",
           any("2020-01-01" in f for _, f, _, _ in F.find(3, True)[0]))
    finally:
        os.chdir(cwd0)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
