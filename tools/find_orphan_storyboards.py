#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""루틴 산출물이 ★엉뚱한 브랜치에 얹혀 있는지 찾는다.

2026-09-02. 미장·국장 루틴이 며칠째 발행이 안 됐는데 ★Actions 에 빨간불이 없었다.
파이프라인이 실패한 게 아니라 ★워크플로가 아예 안 떴기 때문이다.

  shorts.yml 은 `routine/**` 과 `main` push 에만 걸린다.
  그런데 루틴 세션에 "develop on claude/xxx" 브랜치 지시가 들어가면서
  스토리보드가 `claude/upbeat-brown-sjsoo5` 같은 곳으로 갔다.
  그 브랜치는 트리거에 안 걸리고, 아무도 실패하지 않았으므로 ★조용히 샌다.

이 검사기는 그 '미아' 를 찾는다. 판정은 아주 단순하다:

  루틴 산출물처럼 생긴 파일이 ★routine/* 도 main 도 아닌 브랜치에만 있으면 미아다.

★소재·토픽 이름을 하드코딩하지 않는다. 경로 모양만 본다 —
   토픽이 늘어나도 그대로 동작한다.

사용:
  python tools/find_orphan_storyboards.py              # 최근 3일치가 있으면 실패(rc=1)
  python tools/find_orphan_storyboards.py --max-age-days 7
  python tools/find_orphan_storyboards.py --all        # 오래된 것도 실패로 친다
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import re
import subprocess
import sys

# 루틴이 만들어 커밋하는 산출물의 경로 모양. ★토픽 이름은 안 쓴다.
WATCH = ("output/news/*_storyboard.json", "output/scp/*.json")
# 이 브랜치들에 있으면 정상이다(워크플로 트리거가 걸리는 곳).
HOME = ("main", "routine/*")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=False).stdout.strip()


def remote_branches() -> list[str]:
    out = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    names = []
    for line in out.splitlines():
        b = line.strip()
        if not b or b.endswith("/HEAD"):
            continue
        names.append(b[len("origin/"):] if b.startswith("origin/") else b)
    return names


def is_home(branch: str) -> bool:
    return any(fnmatch.fnmatch(branch, p) for p in HOME)


def outputs_on(branch: str) -> set[str]:
    out = git("ls-tree", "-r", "--name-only", f"origin/{branch}")
    return {f for f in out.splitlines()
            if any(fnmatch.fnmatch(f, p) for p in WATCH)}


def file_date(path: str) -> dt.date | None:
    m = DATE_RE.search(path)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def guess_topic(path: str) -> str:
    """경로에서 목적지 브랜치 이름을 짐작한다. ★토픽 목록을 두지 않는다 — 모양만 본다.

        output/news/2026-09-02_stock_us_storyboard.json → stock_us
        output/scp/scp-9245_2026-09-02.json             → scp
    """
    parts = path.split("/")
    name = parts[-1]
    if name.endswith("_storyboard.json"):
        stem = name[: -len("_storyboard.json")]
        stem = DATE_RE.sub("", stem).strip("_-")
        if stem:
            return stem
    return parts[1] if len(parts) > 2 else ""


def last_touch(branch: str, path: str) -> str:
    return git("log", "-1", "--format=%cd", "--date=format-local:%Y-%m-%d %H:%M",
               f"origin/{branch}", "--", path)


def find(max_age_days: int, count_all: bool) -> tuple[list[tuple], list[tuple]]:
    branches = remote_branches()
    safe: set[str] = set()
    for b in branches:
        if is_home(b):
            safe |= outputs_on(b)

    today = dt.date.today()
    fresh, stale = [], []
    for b in sorted(branches):
        if is_home(b):
            continue
        for f in sorted(outputs_on(b) - safe):
            d = file_date(f)
            age = (today - d).days if d else None
            row = (b, f, last_touch(b, f), age)
            if count_all or age is None or age <= max_age_days:
                fresh.append(row)
            else:
                stale.append(row)
    return fresh, stale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=3,
                    help="이보다 오래된 미아는 참고로만 알린다(기본 3)")
    ap.add_argument("--all", action="store_true", help="오래된 것도 실패로 친다")
    args = ap.parse_args()

    fresh, stale = find(args.max_age_days, args.all)

    if stale:
        print(f"\n참고 — {args.max_age_days}일보다 오래된 미아 {len(stale)}건(실패로 치지 않음)")
        for b, f, when, age in stale:
            print(f"   · {f}  ({b}, {when}, {age}일 전)")

    if not fresh:
        print("\n✅ 엉뚱한 브랜치에 얹힌 루틴 산출물 없음")
        return 0

    print(f"\n❌ 미아 산출물 {len(fresh)}건 — 이 브랜치는 워크플로 트리거에 걸리지 않는다")
    for b, f, when, age in fresh:
        print(f"\n   {f}")
        print(f"     브랜치 : {b}   (커밋 {when}"
              f"{f', 파일 날짜 {age}일 전' if age is not None else ''})")
        sha = git("log", "-1", "--format=%h", f"origin/{b}", "--", f)
        t = guess_topic(f) or "<토픽>"
        print(f"     복구   : git checkout -B _fix origin/routine/{t} "
              f"&& git cherry-pick {sha} && git push origin HEAD:routine/{t}")
        print(f"::warning title=미아 산출물::{f} 가 {b} 에만 있다 — "
              f"routine/{t} 로 옮겨야 발행된다")
    print("\n★원인은 대개 루틴 세션에 주입된 'develop on claude/…' 브랜치 지시가")
    print("  루틴 프롬프트의 routine/<토픽> push 지시를 덮어쓴 것이다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
