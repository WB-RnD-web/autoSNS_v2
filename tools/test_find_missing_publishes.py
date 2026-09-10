#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find_missing_publishes 검증 — 리듬 학습과 누락 판정.

이 검사기는 ★사람을 깨우는 물건이다. 그래서 두 방향을 모두 봐야 한다.

  못 잡으면  → 고치려던 조용한 고장이 그대로 남는다
  오탐하면   → 매일 빨간불이 되고, 그러면 아무도 안 본다
              (원래 미아 감지기가 7일 연속 빨간불이라 무시된 게 이 프로젝트의 실제 사고다)

기준 시각을 --now 로 주입할 수 있게 만들어서 요일·시각 경계를 그대로 눌러본다.
2026-09-10 은 목요일이다.

실행: python tools/find_missing_publishes.py 가 아니라
      python tools/test_find_missing_publishes.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_missing_publishes as M  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 10, 11, 0, tzinfo=KST)      # 목요일 오전 11시
FAIL = []


def check(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got else ""))
    if not cond:
        FAIL.append(name)


def runs(topic, days_ago_list, hh, mm=0, event="push", prefix="routine/", base=None):
    """(기준일로부터 N일 전) 목록으로 Actions 실행 기록을 만든다. 시각은 KST 로 준다.

    ★base 를 반드시 검사 기준 시각과 맞춰야 한다. 여기가 NOW 로 고정돼 있어서
    토요일 검사 테스트의 픽스처가 이틀 밀렸고, 테스트가 ★엉뚱한 이유로 통과했다.
    """
    ref = base or NOW
    out = []
    for n in days_ago_list:
        when_kst = (ref - dt.timedelta(days=n)).replace(hour=hh, minute=mm,
                                                        second=0, microsecond=0)
        out.append({"event": event, "head_branch": f"{prefix}{topic}",
                    "run_started_at": when_kst.astimezone(dt.timezone.utc)
                                              .strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def verdict(payload, now=NOW, **kw):
    hist = M.parse_runs({"workflow_runs": payload})
    learned = M.learn(hist, now, kw.pop("days", 28))
    return M.judge(learned, now, **kw)


DAILY = list(range(1, 15))            # 어제부터 14일 전까지 매일
print("── ① 매일 도는 루틴이 오늘 빠졌다 → 누락")
miss, held = verdict(runs("horoscope", DAILY, 7, 37))
check("1건 잡는다", len(miss) == 1, f"{len(miss)}건")
if miss:
    check("오늘(09-10)을 지목한다", str(miss[0]["target"]) == "2026-09-10",
          str(miss[0]["target"]))

print("\n── ② 오늘 올라왔으면 조용하다")
miss2, _ = verdict(runs("horoscope", [0] + DAILY, 7, 37))
check("아무 말 없음", len(miss2) == 0, f"{len(miss2)}건")

print("\n── ③ 평일만 도는 루틴 · 토요일에 검사 → 기대하지 않는 날")
# 09-11(금)까지 정상 발행된 평일 루틴을 09-12(토) 에 본다.
# 검사 대상은 '기대 시각이 지난 가장 최근 날' = 09-12(토) 이고, 토요일엔 원래 안 돈다.
sat = dt.datetime(2026, 9, 12, 12, 0, tzinfo=KST)      # 토요일 정오(09:24+2h 지남)
weekdays = [n for n in range(0, 30)
            if (sat - dt.timedelta(days=n)).weekday() < 5]
fx3 = runs("scp", weekdays, 9, 24, base=sat)
check("픽스처가 금요일까지 채워져 있다",
      any(r["run_started_at"].startswith("2026-09-11") for r in fx3),
      f"{len(fx3)}건")
miss3, held3 = verdict(fx3, now=sat)
check("누락으로 안 잡는다", len(miss3) == 0, f"{len(miss3)}건")
check("토요일을 '기대하지 않는 날' 로 본다",
      any("기대하지 않는" in h["why"] and "2026-09-12" in h["why"] for h in held3),
      "; ".join(h["why"] for h in held3)[:70])

print("\n── ③-b 같은 평일 루틴이 ★금요일을 빠뜨렸으면 금요일에 잡는다")
fri = dt.datetime(2026, 9, 11, 12, 0, tzinfo=KST)      # 금요일 정오
wd_gap = [n for n in range(1, 30)
          if (fri - dt.timedelta(days=n)).weekday() < 5]
miss3b, _ = verdict(runs("scp", wd_gap, 9, 24, base=fri), now=fri)
check("금요일을 지목한다",
      len(miss3b) == 1 and str(miss3b[0]["target"]) == "2026-09-11",
      str(miss3b[0]["target"]) if miss3b else "0건")

print("\n── ④ 밤 22:30 루틴을 아침 11시에 검사 → ★어제를 본다")
# 오늘 22:30 은 아직 오지 않았다. '오늘 안 올라왔다' 고 잡으면 매일 오탐이다.
night_ok = runs("stock_us", DAILY, 22, 30)
miss4, _ = verdict(night_ok)
check("어제까지 있으면 조용하다", len(miss4) == 0, f"{len(miss4)}건")

print("\n── ⑤ 그 밤 루틴이 ★어제 빠졌으면 잡는다")
night_gap = runs("stock_us", [n for n in DAILY if n != 1], 22, 30, base=NOW)
miss5, _ = verdict(night_gap)
check("1건 잡는다", len(miss5) == 1, f"{len(miss5)}건")
if miss5:
    check("어제(09-09)를 지목한다", str(miss5[0]["target"]) == "2026-09-09",
          str(miss5[0]["target"]))

print("\n── ⑥ 이력이 적으면 판단하지 않는다 (모르면 모른다고 한다)")
miss6, held6 = verdict(runs("newtopic", [1, 2], 8, 0))
check("누락으로 안 잡는다", len(miss6) == 0, f"{len(miss6)}건")
check("보류 이유를 밝힌다", any("보류" in h["why"] for h in held6),
      "; ".join(h["why"] for h in held6)[:60])

print("\n── ⑦ push 아닌 실행은 리듬으로 배우지 않는다")
# 수동 재실행(dispatch)·스케줄을 발행으로 세면 리듬이 오염된다.
mixed = (runs("horoscope", DAILY, 7, 37, event="workflow_dispatch")
         + runs("horoscope", DAILY, 7, 37, event="schedule"))
check("이력 0건이 된다", len(M.parse_runs({"workflow_runs": mixed})) == 0,
      f"{len(M.parse_runs({'workflow_runs': mixed}))}건")

print("\n── ⑧ routine/* 이 아닌 브랜치는 무시한다")
other = runs("shorts-thumb", DAILY, 7, 37, prefix="claude/")
check("이력 0건", len(M.parse_runs({"workflow_runs": other})) == 0)
main_runs = runs("", DAILY, 7, 37, prefix="main")
check("main push 도 안 센다", len(M.parse_runs({"workflow_runs": main_runs})) == 0)

print("\n── ⑨ 회귀: 검사 대상 날짜가 자기 확률의 분모에 들어가지 않는다")
# 2026-09-10 별자리에서 실제로 이랬다. 목요일 표본이 그 하루뿐이고 그날이 바로
# 빠진 날이라, 확률 0% 가 되어 '기대하지 않는 날' 로 넘어갔다 — 놓친 걸 못 잡았다.
short = runs("horoscope", [1, 2, 3, 4, 5, 6], 7, 37)   # 09-04~09-09, 목요일 없음
miss9, held9 = verdict(short)
check("짧은 이력에서도 잡는다", len(miss9) == 1, f"{len(miss9)}건")
if miss9:
    check("전체 발행률로 물러섰다고 밝힌다", "전체 발행률" in miss9[0]["basis"],
          miss9[0]["basis"])

print("\n── ⑩ 회귀: 학습 창보다 이력이 짧아도 눈이 멀지 않는다")
# 분모를 창 전체(28일)로 잡으면 매일 도는 루틴도 요일 확률이 1/4 로 깎여 전부 보류된다.
learned10 = M.learn(M.parse_runs({"workflow_runs": runs("fortune", DAILY, 7, 9)}),
                    NOW, 28)
p10, _ = M.expect_p(learned10["fortune"], NOW.date())
check("매일 루틴의 기대가 높게 나온다", p10 >= 0.9, f"{p10:.0%}")

print("\n── ⑪ 주 1회 루틴은 다른 요일에 조용하다")
mondays = [n for n in range(1, 30) if (NOW - dt.timedelta(days=n)).weekday() == 0]
miss11, held11 = verdict(runs("asmr", mondays, 23, 0))
check("목요일엔 안 잡는다", len(miss11) == 0, f"{len(miss11)}건")

print("")
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: " + ", ".join(FAIL))
    raise SystemExit(1)
print("🎉 전부 통과")
