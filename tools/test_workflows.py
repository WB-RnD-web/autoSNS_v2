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
ck("api-test/nt-trend 에 반응하는 push 워크플로는 nt-trend-api.yml 하나",
   reacting("api-test/nt-trend") == ["nt-trend-api.yml"], str(reacting("api-test/nt-trend")))
ck("data/nt-trend 에 반응하는 push 워크플로가 없다(트렌드 편이 올라가도 업로드가 바로 깨지 않는다)",
   not reacting("data/nt-trend"), str(reacting("data/nt-trend")))
ck("api-test/meow 에 반응하는 push 워크플로는 meow-daily.yml 하나(기획·렌더 시험 — 업로드 없음)",
   reacting("api-test/meow") == ["meow-daily.yml"], str(reacting("api-test/meow")))
for _br in ("data/meow", "data/meow-test"):
    ck(f"{_br} 에 반응하는 push 워크플로가 없다(기획이 올라가도 업로드가 바로 깨지 않는다)", not reacting(_br), str(reacting(_br)))
ck("api-test/scout 에 반응하는 push 워크플로는 scout-api.yml 하나",
   reacting("api-test/scout") == ["scout-api.yml"], str(reacting("api-test/scout")))
_rp = flows.get("refill-pr.yml", "")
ck("refill-pr.yml: 읽기 권한 + PR 쓰기만 · secrets 안 씀 · 채우기 검사·전체 테스트 뒤에 PR",
   re.search(r"(?m)^\s*contents:\s*read", _rp) is not None and "pull-requests: write" in _rp and "secrets." not in _rp
   and _rp.find("tools/refill_check.py") < _rp.find("tools/run_tests.sh") < _rp.find("gh pr create"), "")

print("\n── 4. 쓰기 권한은 데이터 브랜치·맥박 PR 브랜치 워크플로에만 ──")
# 쓰기 권한은 '데이터 브랜치에 고아 커밋을 미는' 워크플로(트렌드 레이더, 2026-10-01 #112)와
#   채널 맥박(pulse.yml — 분석 루틴이 제안한 개선 PR 브랜치 pulse/<날짜>-<slug> 만 push, 2026-10-05)에만.
# 맥박 API 판(pulse-api.yml, 2026-10-31)은 비교 기간 동안 data/pulse-api 에만 쓴다.
# 인스타 대본 API 판(insta-api.yml, 2026-10-31)도 비교 기간 동안 data/insta-api 에만 쓴다.
# 웹 정찰(scout-api.yml, 2026-10-31)은 data/scout 에만 쓴다.
# Nine Tails 트렌드 편(nt-trend-api.yml, 2026-11-01)은 data/nt-trend 에만 쓴다(nt-story.yml 은 읽기만).
# ★2026-11-09 Meow Remix 매일 쇼츠(meow-daily.yml)는 기획 잡만 data/meow(시험 data/meow-test)에 쓴다 — 렌더·업로드 잡은 읽기.
WRITERS = {"trend-radar.yml": "data/trend-radar", "pulse.yml": "refs/heads/$BR", "pulse-api.yml": "data/pulse-api",
           "insta-api.yml": "data/insta-api", "scout-api.yml": "data/scout", "nt-trend-api.yml": "data/nt-trend",
           "meow-daily.yml": "data/meow"}
_w = sorted(n for n, t in flows.items() if re.search(r"(?m)^\s*contents:\s*write", t))
ck("contents: write 는 WRITERS(트렌드 레이더·맥박 PR 브랜치·맥박·인스타 API 판·웹 정찰·NT 트렌드 편)에만", _w == sorted(WRITERS), str(_w))
for _wf, _br in WRITERS.items():
    _t = flows.get(_wf, "")
    _p = [ln for ln in _t.splitlines() if "git" in ln and " push" in ln and not ln.strip().startswith("#")]
    ck(f"…{_wf}: push 는 {_br} 하나로만(main·routine/* 아님)",
       len(_p) == 1 and _br in _t and "routine/" not in _p[0] and "main" not in _p[0], str(_p))
_others = [n for n, t in flows.items() if n not in WRITERS
           and [ln for ln in t.splitlines() if re.search(r"\bgit\b.*\spush\b", ln.split(" #")[0])
                and not ln.strip().startswith("#")]]
# orphan-rescue.yml 은 예외 — GITHUB_TOKEN 은 읽기 권한이고, 미아 산출물을 PAT 으로 routine/* 에 되돌린다(그게 할 일이다).
# ★2026-11-07 wb-triggers.yml · lf27-api.yml — 옛 클라우드 루틴이 하던 routine/* push 를 옮겼다(GITHUB_TOKEN 은 읽기, push 는 PAT).
PAT_PUSHERS = {"orphan-rescue.yml", "wb-triggers.yml", "lf27-api.yml"}
ck("그 밖에 git push 하는 워크플로는 PAT 으로 routine/* 에 미는 셋뿐(되돌리기·표 트리거·롱폼 API)",
   sorted(_others) == sorted(PAT_PUSHERS), str(_others))
for _wf in ("wb-triggers.yml", "lf27-api.yml"):
    _t = flows.get(_wf, "")
    _p = [ln for ln in _t.splitlines() if re.search(r"\bgit\b.*\spush\b", ln.split(" #")[0]) and not ln.strip().startswith("#")]
    ck(f"…{_wf}: 읽기 권한 · push 는 PAT · main 이 아니라 routine/* 로만 · 강제 push 없음",
       re.search(r"(?m)^\s*contents:\s*read", _t) is not None and "secrets.GH_PAT" in _t
       and all("main" not in ln and "-f" not in ln.split() and "--force" not in ln for ln in _p)
       and ("routine/" in _t), str(_p))

# ★2026-11 Nine Tails Story(nt-story.yml): 예약으로만 깨고(push 없음) 읽기 권한 — 업로드 ledger 는 Actions 캐시.
_ns = flows.get("nt-story.yml", "")
ck("nt-story.yml: push 트리거 없음(예약·수동) · 읽기 권한 · 할 일은 story.py due · 5B 영상 잡 없음",
   trig.get("nt-story.yml") is None and re.search(r"(?m)^\s*contents:\s*read", _ns) is not None
   and "gumiho/tales/story.py due" in _ns and '"type": "video"' not in _ns, "")

# ★2026-11-09 Meow Remix 매일 쇼츠: 업로드는 예약 실행(또는 수동 upload 켬)만 · api-test/meow 시험은 렌더만 ·
#   쓰기 권한은 기획 잡에만(맨 위는 읽기) · 렌더 잡은 기획을 읽기만 · 유튜브 토큰은 Meow Remix(옛 Nine Tails) 것.
_mw = flows.get("meow-daily.yml", "")
_render = _mw.split("\n  render:", 1)[-1]
ck("meow-daily.yml: 맨 위 읽기 · 쓰기는 기획 잡만 · 업로드는 예약/수동 upload 만 · 고양이 채널 토큰 · 조용한 시간·검수 막힘은 실패 아님",
   re.search(r"(?m)^permissions:\n  contents: read", _mw) is not None and "contents: write" not in _render
   and "UPLOAD: ${{ github.event_name == 'schedule' || github.event.inputs.upload == 'true' }}" in _mw
   and "env.UPLOAD == 'true'" in _render and "YT_TOKEN_JSON_GUMIHO" in _render and "YT_TOKEN_JSON_NOVEL" not in _mw
   and "rc -eq 75" in _render and "rc -eq 3" in _render
   and not [ln for ln in _render.splitlines() if re.search(r"\bgit\b.*\spush\b", ln)], "")

# ★2026-11-09 사용자 "인스타·쓰레드에도 올려줘" — meow-social.yml 은 예약·수동으로만 깨고 읽기 권한 · 완성본은
#   meow-daily 의 캐시에서 꺼낸다(actions/cache 는 경로 목록이 같아야 열린다 — 두 파일의 목록이 똑같은지 본다).
_ms = flows.get("meow-social.yml", "")


def _out_paths(t):
    m = re.search(r"path: \|\n((?:\s+output/meow/\$\{\{ steps\.pick\.outputs\.stem \}\}[^\n]*\n)+)", t)
    return [x.strip() for x in m.group(1).splitlines()] if m else None


ck("meow-social.yml: push 트리거 없음 · 읽기 권한 · post.py social 하나 · 게시 ledger 캐시 · 유튜브 토큰 안 씀",
   trig.get("meow-social.yml") is None and re.search(r"(?m)^permissions:\n  contents: read", _ms) is not None
   and "contents: write" not in _ms and "python meow/post.py social" in _ms and "meow-posted-" in _ms
   and "YT_TOKEN" not in _ms, "")
ck("완성본 캐시 경로가 meow-daily(저장)와 meow-social(받기)에서 똑같다 · 열쇠 앞머리 meow-out-",
   _out_paths(_mw) is not None and _out_paths(_mw) == _out_paths(_ms) and len(_out_paths(_ms)) == 3
   and "key: meow-out-${{ steps.pick.outputs.stem }}-${{ github.run_id }}" in _mw
   and "restore-keys: meow-out-${{ steps.pick.outputs.stem }}-" in _ms, f"{_out_paths(_mw)} vs {_out_paths(_ms)}")

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
