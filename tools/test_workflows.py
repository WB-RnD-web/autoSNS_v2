#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""워크플로 전체 가드 — .github/workflows/*.yml 을 한꺼번에 본다(네트워크·자격증명 없이).

    python tools/test_workflows.py

2026-10-24: pipeline/test_ai_news.py 13절(워크플로 연결)에 있던 '모든 워크플로' 검사를 옮겼다
  (AI 소식 쇼츠를 접으며 test_ai_news.py 를 지웠다 — AI 소식 전용 검사는 같이 지웠다).
지키는 것:
  · 브랜치 필터 해석이 맞다(가드 자체 점검)
  · 누적 브랜치(routine/weekly_fortune·fortune_lf27)에 반응하는 push 워크플로는 그 주인 하나 —
    shorts.yml 의 routine/** 가 삼키면 지난 대본까지 다시 집어 같은 영상이 두 번 올라간다
  · 접은 누적 브랜치(routine/ai_am·ai_pm)도 shorts.yml 이 집지 않는다(대본이 쌓여 있다)
  · 데이터 브랜치(data/**)·맥박 PR 브랜치(pulse/**)에 반응하는 push 워크플로가 없다(업로드가 깨어나지 않게)
  · contents: write 는 WRITERS 에 적힌 워크플로에만 · 각자 자기 브랜치 하나로만 push(main·routine/* 아님)
  · 워크플로가 부르는 파일(uses: …/.github/workflows/X@main · python <파일>.py · bash <파일>.sh)이 레포에 있다
★새 데이터 워크플로를 만들면 WRITERS 에 함께 적는다(2026-10-01 #112: 트렌드 레이더를 더하면서 이 목록을 안 고쳐
  업로드가 하루 막혔다). 사람도 워크플로를 건드린 PR 전엔 tools/run_tests.sh 를 돌린다.
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WF = os.path.join(ROOT, ".github", "workflows")

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def push_branches(text):
    """워크플로의 on.push.branches (push 트리거가 없으면 None · 브랜치 필터가 없으면 ['**'] = 전부)."""
    pats, in_on, push_ind, br_ind = None, False, None, None
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip()
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        if ind == 0:
            in_on, push_ind, br_ind = s.startswith("on:"), None, None
            continue
        if not in_on:
            continue
        if push_ind is not None and ind <= push_ind:
            push_ind = br_ind = None
        if push_ind is None:
            if s == "push:" or s.startswith("push:"):
                push_ind, pats = ind, ["**"]
            continue
        if s.startswith("branches:"):
            br_ind, pats = ind, []
        elif br_ind is not None and s.startswith("- ") and ind >= br_ind:
            pats.append(s[2:].strip().strip("\"'"))
        elif br_ind is not None and ind <= br_ind:
            br_ind = None
    return pats


def gh_match(pats, ref):
    """GitHub 브랜치 필터: * = '/' 빼고 아무거나 · ** = 아무거나 · '!' = 빼기(뒤 규칙이 이긴다)."""
    hit = False
    for p in pats or []:
        neg = p.startswith("!")
        rx = re.escape(p[1:] if neg else p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(rx, ref):
            hit = not neg
    return hit


flows = {n: open(os.path.join(WF, n), encoding="utf-8").read() for n in sorted(os.listdir(WF)) if n.endswith(".yml")}
trig = {n: push_branches(t) for n, t in flows.items()}


def reacting(ref):
    """이 브랜치 push 에 깨는 워크플로(브랜치 필터 기준)."""
    return [n for n, p in trig.items() if p is not None and gh_match(p, ref)]


print("\n── 1. 브랜치 필터 해석(가드 점검) ──")
ck("shorts.yml 은 routine/날짜·routine/fortune O · routine/weekly_fortune·fortune_lf27·ai_am X",
   gh_match(trig["shorts.yml"], "routine/2026-06-26_politics") and gh_match(trig["shorts.yml"], "routine/fortune")
   and not gh_match(trig["shorts.yml"], "routine/weekly_fortune") and not gh_match(trig["shorts.yml"], "routine/fortune_lf27")
   and not gh_match(trig["shorts.yml"], "routine/ai_am"), str(trig["shorts.yml"]))
ck("fortune-lf27.yml 은 routine/fortune_lf27 O · routine/fortune X(06:13 매일 운세와 이름이 다르다)",
   gh_match(trig["fortune-lf27.yml"], "routine/fortune_lf27") and not gh_match(trig["fortune-lf27.yml"], "routine/fortune"),
   str(trig["fortune-lf27.yml"]))
ck("push 트리거가 없는 워크플로는 None(예약·호출 전용)",
   trig["orphan-check.yml"] is None and trig["retry-no-runner.yml"] is None and trig["weekly-fortune-run.yml"] is None)

print("\n── 2. 누적 브랜치는 주인 워크플로 하나만 ──")
# 누적 브랜치 = 대본이 계속 쌓이는 브랜치. 주인이 아닌 워크플로가 깨면 지난 대본까지 다시 집는다.
OWNERS = {"routine/weekly_fortune": "weekly-fortune.yml", "routine/fortune_lf27": "fortune-lf27.yml"}
for _br, _own in OWNERS.items():
    ck(f"{_br} 에 반응하는 push 워크플로는 {_own} 하나(shorts.yml 아님)", reacting(_br) == [_own], str(reacting(_br)))
# AI 소식(routine/ai_am·ai_pm)은 2026-10-07 에 접었지만 브랜치에 대본이 쌓여 있다 — shorts.yml 이 집으면 두 번 올라간다.
for _br in ("routine/ai_am", "routine/ai_pm"):
    ck(f"접은 누적 브랜치 {_br} 에 반응하는 push 워크플로가 없다", not reacting(_br), str(reacting(_br)))

print("\n── 3. 데이터·PR 브랜치 push 는 아무 워크플로도 깨우지 않는다 ──")
for _br in ("data/trend-radar", "data/ai-news-feed", "data/anything", "pulse/2026-10-24-sample"):
    ck(f"{_br} 에 반응하는 push 워크플로가 없다(업로드가 깨어나지 않게)", not reacting(_br), str(reacting(_br)))
# ★10/25 주간 채우기 루틴(tools/REFILL.md)은 refill/<줄기>-<날짜> 브랜치를 올린다 — 깨는 건 검사·PR(refill-pr.yml) 하나뿐,
#   업로드 워크플로가 깨면 안 된다. refill-pr.yml 은 읽기 권한 + PR 열기만(push·업로드·비밀 없음).
ck("refill/insta_sci-20261101 에 반응하는 push 워크플로는 refill-pr.yml 하나",
   reacting("refill/insta_sci-20261101") == ["refill-pr.yml"], str(reacting("refill/insta_sci-20261101")))
# 맥박 API 판 머지 전 시험 브랜치(api-test/pulse) — 깨는 건 pulse-api.yml 하나(업로드 워크플로 아님).
ck("api-test/pulse 에 반응하는 push 워크플로는 pulse-api.yml 하나",
   reacting("api-test/pulse") == ["pulse-api.yml"], str(reacting("api-test/pulse")))
ck("api-test/insta 에 반응하는 push 워크플로는 insta-api.yml 하나",
   reacting("api-test/insta") == ["insta-api.yml"], str(reacting("api-test/insta")))
_rp = flows.get("refill-pr.yml", "")
ck("refill-pr.yml: 읽기 권한 + PR 쓰기만 · secrets 안 씀 · 채우기 검사·전체 테스트 뒤에 PR",
   re.search(r"(?m)^\s*contents:\s*read", _rp) is not None and "pull-requests: write" in _rp and "secrets." not in _rp
   and _rp.find("tools/refill_check.py") < _rp.find("tools/run_tests.sh") < _rp.find("gh pr create"), "")

print("\n── 4. 쓰기 권한은 데이터 브랜치·맥박 PR 브랜치 워크플로에만 ──")
# 쓰기 권한은 '데이터 브랜치에 고아 커밋을 미는' 워크플로(트렌드 레이더, 2026-10-01 #112)와
#   채널 맥박(pulse.yml — 분석 루틴이 제안한 개선 PR 브랜치 pulse/<날짜>-<slug> 만 push, 2026-10-05)에만.
# 맥박 API 판(pulse-api.yml, 2026-10-31)은 비교 기간 동안 data/pulse-api 에만 쓴다.
# 인스타 대본 API 판(insta-api.yml, 2026-10-31)도 비교 기간 동안 data/insta-api 에만 쓴다.
WRITERS = {"trend-radar.yml": "data/trend-radar", "pulse.yml": "refs/heads/$BR", "pulse-api.yml": "data/pulse-api",
           "insta-api.yml": "data/insta-api"}
_w = sorted(n for n, t in flows.items() if re.search(r"(?m)^\s*contents:\s*write", t))
ck("contents: write 는 WRITERS(트렌드 레이더·맥박 PR 브랜치·맥박·인스타 API 판)에만", _w == sorted(WRITERS), str(_w))
for _wf, _br in WRITERS.items():
    _t = flows.get(_wf, "")
    _p = [ln for ln in _t.splitlines() if "git" in ln and " push" in ln and not ln.strip().startswith("#")]
    ck(f"…{_wf}: push 는 {_br} 하나로만(main·routine/* 아님)",
       len(_p) == 1 and _br in _t and "routine/" not in _p[0] and "main" not in _p[0], str(_p))
_others = [n for n, t in flows.items() if n not in WRITERS
           and [ln for ln in t.splitlines() if re.search(r"\bgit\b.*\spush\b", ln.split(" #")[0])
                and not ln.strip().startswith("#")]]
# orphan-rescue.yml 은 예외 — GITHUB_TOKEN 은 읽기 권한이고, 미아 산출물을 PAT 으로 routine/* 에 되돌린다(그게 할 일이다).
ck("그 밖에 git push 하는 워크플로는 orphan-rescue.yml(PAT · routine/* 되돌리기)뿐", _others == ["orphan-rescue.yml"], str(_others))

print("\n── 5. 워크플로가 부르는 파일이 레포에 있다 ──")
_miss = []
for n, t in flows.items():
    for ref in re.findall(r"uses:\s*\S+?/\.github/workflows/([\w.-]+\.ya?ml)@", t) + \
            re.findall(r"uses:\s*\./\.github/workflows/([\w.-]+\.ya?ml)", t):
        if ref not in flows:
            _miss.append(f"{n}: uses {ref}")
    # 레포 뿌리 또는 그 워크플로가 들어가는 폴더(cd pipeline · working-directory:) 기준
    wds = [""] + [w.strip("\"'") for w in re.findall(r"working-directory:\s*(\S+)", t) + re.findall(r"\bcd\s+([\w./-]+)", t)]
    for ln in t.splitlines():
        if ln.strip().startswith("#"):
            continue
        for f in re.findall(r"\b(?:python3?|bash|sh)\s+([\w./-]+\.(?:py|sh))\b", ln):
            if not any(os.path.exists(os.path.join(ROOT, w, f)) for w in wds):
                _miss.append(f"{n}: {f}")
ck("uses: …@main 의 워크플로 · python/bash 로 부르는 파일이 전부 있다", not _miss, str(_miss))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
