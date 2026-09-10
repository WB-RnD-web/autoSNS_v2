#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""올라와야 할 산출물이 ★아예 만들어지지 않은 것을 찾는다.

find_orphan_storyboards.py 와 방향이 반대다.

  미아 감지기 : 잘못된 브랜치에 ★있는 파일을 찾는다
  이 검사기   : 어디에도 ★없는 산출물을 찾는다

왜 갈라놨나 — 2026-09-10.
  별자리 루틴이 정상 발화(SUCCEEDED)했는데 산출물이 아무 브랜치에도 없었다.
  세션은 `claude/vibrant-babbage-pkzyvi` 를 받았지만 push 를 아예 하지 않았다.
  파일이 어디에도 없으니 미아 감지기에는 ★보이지 않는다 — 잘못 놓인 파일을 찾는 도구니까.
  자동 복구(orphan-rescue.yml)도 옮길 게 없어 손을 못 댄다.
  즉 이 고장은 완전히 조용했다. 그걸 시끄럽게 만드는 게 이 파일이다.

★무엇이 올라와야 하는지를 하드코딩하지 않는다
  토픽 목록도, 스케줄도 적지 않는다. 루틴은 레포 밖(Claude Routines)에 있고 사용자가
  수시로 켜고 끈다 — 표를 만들면 반드시 어긋난다.
  대신 ★과거 발행 이력에서 리듬을 배운다. 그래서 토픽이 늘거나 줄어도 따라간다.

배우는 것 두 가지 (둘 다 이력에서 나온다)
  ① 요일 확률 — 이 토픽이 이 요일에 발행될 확률. 평일만/매일/주1회가 저절로 갈린다.
  ② 발행 시각 — 중앙값. 아침 루틴(07시)과 미장 루틴(22:30)을 구별하려면 필요하다.

②가 있어야 판정 시점을 옳게 고른다. 11시에 검사할 때
  아침 07시 루틴 → 오늘 것을 봐야 하고
  밤 22:30 루틴 → 오늘 건 아직 시간 전이니 ★어제 것을 봐야 한다.
그래서 '기대 시각이 이미 지난 가장 최근 날짜' 를 검사 대상으로 삼는다.

이력의 출처는 GitHub Actions 실행 목록이다. routine/* 브랜치는 매번 main 에서
리셋되므로 브랜치 커밋 이력에는 최신 1건만 남는다 — 리듬을 배울 수 없다.
Actions 실행 기록은 push 마다 남아 온전하다.

사용:
  python tools/find_missing_publishes.py --runs runs.json
  python tools/find_missing_publishes.py --runs runs.json --now 2026-09-10T11:00+09:00
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
from collections import defaultdict

KST = dt.timezone(dt.timedelta(hours=9))

WINDOW_DAYS = 28        # 리듬을 배우는 창. 짧으면 못 배우고 길면 옛 리듬을 붙잡는다
MIN_SAMPLES = 4         # 이보다 적으면 판단하지 않는다 — 모르면 모른다고 한다
DOW_THRESHOLD = 0.6     # 이 요일 발행 확률이 이 이상이면 '오늘 올라와야 한다' 로 본다
GRACE_HOURS = 2.0       # 기대 시각 + 이만큼은 기다려준다(루틴 지연·렌더 시간)
DOW_KO = ("월", "화", "수", "목", "금", "토", "일")


def parse_runs(payload: dict | list) -> list[tuple[str, dt.datetime]]:
    """Actions 실행 목록 → [(토픽, 발행시각KST)]. push 로 뜬 routine/* 만 센다.

    push 가 아닌 것(schedule·workflow_dispatch)은 루틴 발행이 아니므로 제외한다 —
    수동 재실행을 리듬으로 배우면 안 된다.
    """
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else payload
    out = []
    for r in runs:
        if r.get("event") != "push":
            continue
        br = r.get("head_branch") or ""
        if not br.startswith("routine/"):
            continue
        topic = br[len("routine/"):]
        stamp = r.get("run_started_at") or r.get("created_at") or ""
        try:
            when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append((topic, when.astimezone(KST)))
    return out


def learn(history: list[tuple[str, dt.datetime]], now: dt.datetime,
          window_days: int) -> dict[str, dict]:
    """토픽별 리듬을 배운다 — 요일 확률과 발행 시각 중앙값."""
    start = (now - dt.timedelta(days=window_days)).date()
    by_topic: dict[str, list[dt.datetime]] = defaultdict(list)
    for topic, when in history:
        if when.date() >= start:
            by_topic[topic].append(when)

    # ★분모는 '이력이 실제로 있는 구간' 으로 좁힌다.
    #   창을 28일로 잡고 기록이 7일치뿐이면, 매일 도는 루틴도 요일 확률이 1/4 로 깎여
    #   전부 '기대하지 않는 날' 이 되어버린다 — 감시가 통째로 잠든다.
    #   그래서 창 시작과 가장 오래된 기록 중 ★늦은 쪽부터 센다.
    seen = [w.date() for _, w in history if w.date() >= start]
    if seen:
        start = max(start, min(seen))

    # 그 구간에 각 요일이 몇 번 있었나 — 확률의 분모다
    dow_total = defaultdict(int)
    d = start
    while d <= now.date():
        dow_total[d.weekday()] += 1
        d += dt.timedelta(days=1)

    span = [start + dt.timedelta(days=i)
            for i in range((now.date() - start).days + 1)]

    learned = {}
    for topic, times in by_topic.items():
        days = sorted({t.date() for t in times})
        # 발행 시각은 '하루 중 몇 분' 의 중앙값으로 본다
        minutes = sorted(t.hour * 60 + t.minute for t in times)
        learned[topic] = {
            "days": days,
            "count": len(days),
            "last": days[-1] if days else None,
            "span": span,                 # 확률의 분모가 되는 날짜들
            "dow_total": dict(dow_total),
            "at_min": int(statistics.median(minutes)) if minutes else 0,
        }
    return learned


def expect_p(info: dict, target: dt.date, min_dow: int = 2) -> tuple[float, str]:
    """target 날짜에 발행이 기대되는 정도. ★target 자신은 분모에서 뺀다.

    검사하려는 날짜를 분모에 넣으면 자기 확률을 스스로 깎는다. 관측 창이 짧을 때
    그 요일의 유일한 표본이 바로 '빠진 그 날' 이 되어, 놓친 것을 놓쳤다고 말할 수
    없게 된다(2026-09-10 별자리에서 실제로 그랬다).

    그 요일 표본이 min_dow 미만이면 요일로 판단하지 않고 ★전체 발행률로 물러선다.
    매일 도는 루틴은 그것만으로도 잡히고, 주 1회 루틴은 낮은 값이 나와 보류된다.
    """
    others = [d for d in info["span"] if d != target]
    same_dow = [d for d in others if d.weekday() == target.weekday()]
    hits = set(info["days"])
    if len(same_dow) >= min_dow:
        return (sum(d in hits for d in same_dow) / len(same_dow),
                f"{DOW_KO[target.weekday()]}요일 표본 {len(same_dow)}일")
    if not others:
        return 0.0, "표본 없음"
    return (sum(d in hits for d in others) / len(others),
            f"{DOW_KO[target.weekday()]}요일 표본 {len(same_dow)}일뿐 → 전체 발행률로 대체")


def judge(learned: dict[str, dict], now: dt.datetime, *,
          min_samples: int = MIN_SAMPLES, dow_threshold: float = DOW_THRESHOLD,
          grace_hours: float = GRACE_HOURS) -> tuple[list[dict], list[dict]]:
    """(누락, 보류) 반환.

    검사 대상 날짜는 ★기대 시각이 이미 지난 가장 최근 날짜다. 밤에 발행되는 토픽을
    아침에 '오늘 안 올라왔다' 고 잡으면 매일 오탐이 난다.
    """
    missing, held = [], []
    for topic, info in sorted(learned.items()):
        if info["count"] < min_samples:
            held.append({"topic": topic, "why":
                         f"이력 {info['count']}회 — {min_samples}회 미만이라 판단 보류"})
            continue

        due = (now.replace(hour=0, minute=0, second=0, microsecond=0)
               + dt.timedelta(minutes=info["at_min"], hours=grace_hours))
        target = now.date() if now >= due else now.date() - dt.timedelta(days=1)

        p, basis = expect_p(info, target)
        if p < dow_threshold:
            held.append({"topic": topic, "why":
                         f"{target} 발행 기대 {p:.0%} ({basis}) — 기대하지 않는 날"})
            continue

        if target in info["days"]:
            continue        # 정상

        missing.append({
            "topic": topic, "target": target, "p": p, "basis": basis,
            "at": f"{info['at_min'] // 60:02d}:{info['at_min'] % 60:02d}",
            "last": info["last"],
            "gap": (target - info["last"]).days if info["last"] else None,
        })
    return missing, held


def main() -> int:
    ap = argparse.ArgumentParser(
        description="올라와야 할 산출물이 아예 만들어지지 않은 것을 찾는다")
    ap.add_argument("--runs", required=True, nargs="+",
                    help="GitHub Actions 실행 목록 JSON. 여러 개(페이지) 주면 합친다. '-' 는 표준입력")
    ap.add_argument("--now", help="기준 시각(ISO, 기본 지금). 테스트용")
    ap.add_argument("--days", type=int, default=WINDOW_DAYS, help="리듬 학습 창(일)")
    ap.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    ap.add_argument("--dow-threshold", type=float, default=DOW_THRESHOLD)
    ap.add_argument("--grace-hours", type=float, default=GRACE_HOURS)
    ap.add_argument("--quiet-held", action="store_true", help="보류 목록을 숨긴다")
    args = ap.parse_args()

    history: list[tuple[str, dt.datetime]] = []
    for src in args.runs:
        raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
        history += parse_runs(json.loads(raw))
    # 같은 실행이 페이지 경계에서 중복될 수 있다 — (토픽, 시각) 으로 접는다
    history = sorted(set(history))

    now = (dt.datetime.fromisoformat(args.now).astimezone(KST) if args.now
           else dt.datetime.now(KST))
    learned = learn(history, now, args.days)
    missing, held = judge(learned, now, min_samples=args.min_samples,
                          dow_threshold=args.dow_threshold,
                          grace_hours=args.grace_hours)

    print(f"기준 {now:%Y-%m-%d %H:%M} KST · 최근 {args.days}일 · 발행기록 {len(history)}건")
    print("")
    if learned:
        print("배운 리듬")
        for topic, i in sorted(learned.items()):
            ref = now.date()
            dows = "".join(
                DOW_KO[w] if expect_p(i, ref + dt.timedelta(
                    days=(w - ref.weekday()) % 7 - 7))[0] >= args.dow_threshold else "·"
                for w in range(7))
            print(f"   {topic:<12} {dows}  {i['at_min'] // 60:02d}:{i['at_min'] % 60:02d}경"
                  f"  {i['count']}회  마지막 {i['last']}")
        print("")

    if held and not args.quiet_held:
        print("판단 보류")
        for h in held:
            print(f"   · {h['topic']}: {h['why']}")
        print("")

    if not missing:
        print("✅ 빠진 발행 없음.")
        return 0

    print(f"❌ 발행 누락 {len(missing)}건 — 루틴은 돌았는데 산출물이 어디에도 없다")
    print("")
    for m in missing:
        print(f"   {m['topic']}  ({m['target']} {DOW_KO[m['target'].weekday()]})")
        print(f"     기대   : {m['p']:.0%} ({m['basis']}) · 보통 {m['at']}경")
        print(f"     마지막 : {m['last']}  ({m['gap']}일 전)")
    print("")
    print("★확인 순서")
    print("  1. 루틴이 발화했나 — Routines 의 마지막 실행 상태")
    print("     SUCCEEDED 는 '세션에 전달됐다' 는 뜻이고 작업 성공과 무관하다.")
    print("  2. 세션이 어느 브랜치를 받았나 — claude/* 면 push 를 안 한 것이다.")
    print("     산출물이 브랜치에 남아 있다면 orphan-rescue.yml 이 이미 옮겼을 것이다.")
    print("  3. 둘 다 아니면 산출물은 사라졌다 — 루틴을 다시 돌리는 수밖에 없다.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
