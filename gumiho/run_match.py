#!/usr/bin/env python3
"""Gumiho Games 대국 실행 — 같은 게임을 N판 돌려 기록하고, 가장 극적인 판을 코드 점수로 고른다.

    python gumiho/run_match.py --matches 5                      # 시즌 roster, 오늘 날짜 seed
    python gumiho/run_match.py --matches 1 --backend spark      # 모든 자리를 Spark Gemma 로(엔진 점검용 — 공개 금지)
    python gumiho/run_match.py --matches 3 --backend mock       # 오프라인

seed = 날짜(YYYYMMDD)*100 + 판 번호 → 같은 날 다시 돌리면 같은 역할 배정.
판은 한 번에 하나씩 돈다(Spark 는 공용 서버라 병렬로 두드리지 않는다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fox_hunt  # noqa: E402
import players   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES = {"fox-hunt": fox_hunt.FoxHunt}
MAX_FALLBACK = 0.15   # 모델 답을 이 비율 넘게 메웠으면 영상으로 쓰지 않는다


def drama_score(m: dict) -> dict:
    """코드로 매기는 '볼 만한 판' 점수. 사람이 볼 후보를 좁히는 용도 — 최종 선택은 사람이 확인한다."""
    ev, roles = m["events"], m["roles"]
    fox = next(n for n, r in roles.items() if r == "fox")
    s, why = 0.0, []
    if m["winner"] == "fox":
        s += 3; why.append("여우 승리")
    wrong = [e for e in ev if e["type"] == "banish" and e["role"] != "fox"]
    s += 2 * len(wrong)
    if wrong:
        why.append(f"엉뚱한 추방 {len(wrong)}")
    days = max([e["day"] for e in ev if e["type"] == "day_start"] or [1])
    s += days
    found = [e for e in ev if e["type"] == "inspect" and e["is_fox"]]
    if found:
        s += 2; why.append("무당이 여우를 봄")
        n = found[0]["night"]
        if any(e["type"] == "day_start" and e["day"] == n + 1 for e in ev) and \
                not any(e["type"] == "banish" and e["day"] == n + 1 and e["who"] == fox for e in ev):
            s += 2; why.append("보고도 못 잡음")
    if any(e["type"] == "kill" and e["role"] == "shaman" for e in ev):
        s += 1; why.append("무당 제거")
    for e in ev:
        if e["type"] == "tally":
            c = sorted(e["tally"].values(), reverse=True)
            if len(c) > 1 and c[0] - c[1] <= 1:
                s += 1
        if e["type"] == "no_banish":
            why.append("동점")
    accused = sum(1 for e in ev if e["type"] == "say" and e["who"] != fox and fox.lower() in e["say"].lower())
    if accused >= 3 and m["winner"] == "fox":
        s += 2; why.append(f"여우가 {accused}번 지목되고도 생존")
    calls = max(1, m["stats"]["calls"])
    fb = m["stats"]["fallbacks"] / calls
    s -= 10 * fb
    ok = fb <= MAX_FALLBACK and not m["flags"]
    return {"score": round(s, 2), "why": why, "fallback_ratio": round(fb, 3), "usable": ok}


def run(game: str, roster: list[dict], seed: int, backend: str | None, date: str) -> dict:
    backends = {s["name"]: players.make_backend(s, backend, seed) for s in roster}
    t0 = time.time()
    m = GAMES[game](roster, backends, seed, date=date).run()
    m["sec"] = round(time.time() - t0)
    m["test_backend"] = backend      # 한 백엔드로 모든 자리를 채운 판은 공개용이 아니다
    m["drama"] = drama_score(m)
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description="Gumiho Games 대국 실행")
    ap.add_argument("--game", default="fox-hunt", choices=sorted(GAMES))
    ap.add_argument("--roster", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "roster.json"))
    ap.add_argument("--matches", type=int, default=5)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--backend", choices=["spark", "mock", "anthropic"], help="모든 자리를 이 백엔드로(점검용)")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "gumiho", "matches"))
    args = ap.parse_args()
    cands = players.load_roster(args.roster)
    if args.backend:          # 점검용: 모든 자리를 한 백엔드로 — 모델 점검 없이 앞에서부터 6명
        roster = players.default_cast(cands)
    else:                     # 실제 출연: 우선순위대로 점검해 통과한 6명(떨어지면 대기 명단에서 자동 교체)
        roster, report = players.select_cast(cands)
        print("🎟️ 출연 전 점검\n   " + "\n   ".join(report), flush=True)
        if len(roster) < players.SEATS:
            print(f"::error::출연 가능 모델이 {len(roster)}개뿐이다(필요 {players.SEATS})")
            return 1
        print("   → 출연: " + ", ".join(f"{s['name']}({s['model']})" for s in roster), flush=True)
    os.makedirs(args.out, exist_ok=True)
    base = int(args.date.replace("-", "")) * 100
    best = None
    for k in range(args.matches):
        seed = base + k
        m = run(args.game, roster, seed, args.backend, args.date)
        path = os.path.join(args.out, f"{args.date}_{args.game}_s{seed}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        dm = m["drama"]
        print(f"▶ 판 {k + 1}/{args.matches} seed {seed}: 승자 {m['winner']} · 여우 {m['roles'] and next(n for n, r in m['roles'].items() if r == 'fox')}"
              f" · 점수 {dm['score']} {dm['why']} · 메움 {dm['fallback_ratio']:.0%} · {m['sec']}초"
              f"{'' if dm['usable'] else ' · ✗ 사용 불가'}", flush=True)
        if dm["usable"] and (best is None or dm["score"] > best[0]):
            best = (dm["score"], path)
    if best:
        print(f"✅ 추천 판: {best[1]} (점수 {best[0]})")
        with open(os.path.join(args.out, f"{args.date}_{args.game}_best.txt"), "w", encoding="utf-8") as f:
            f.write(best[1] + "\n")
        return 0
    print("::error::쓸 수 있는 판이 없다(메움 비율·필터)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
