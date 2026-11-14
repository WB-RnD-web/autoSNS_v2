#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정리 노트 — 매일 '무엇이 먹히는지 · 무엇을 바꿨는지 · 결과가 어땠는지'를 한 장에 쌓는다 (2026-11-14).

왜: 11/14 사용자 "API 키로 분석하는 애를 만들고 내가 물어보면 그 정리된 걸 토대로 고치던가 유지하던가 결정" →
  추천안(틀 자동 조정 + 정리 노트)에 "응 그렇게 해줘". 알림·보고서는 보내지 않는다 — data/meow 의 notes/ 에 저장만.
  사용자가 물어보면 Claude(대화)가 이 노트를 읽고 '유지 / 고치자'를 답한다.

한 장 = 두 부분(근거와 추측을 나눈다):
  ① 근거 — 코드가 센 숫자(stats.json · mix.json). API 를 쓰지 않는다.
  ② 해석 — Claude API 가 ①과 지난 노트 세 장을 읽고 쓴 짧은 해석(추측은 추측이라고 적게 한다).
     2일 넘은 편이 없으면 부르지 않는다(돈 안 씀). 실패해도 ①은 남는다.

    python meow/notes.py write --dir <기획 폴더(data/meow)> --day 2026-11-15
      → <기획 폴더>/notes/<날짜>.md · notes/<날짜>_api.json(모델·토큰·달러)
하루 한 번(이미 있으면 건너뛴다). 비용: Opus 5.5 · effort medium · 하루 약 0.05~0.15달러.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyst as AN  # noqa: E402
import tuner as TU  # noqa: E402

MODEL = os.environ.get("MEOW_NOTE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("MEOW_NOTE_EFFORT", "medium")
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력, 출력, 캐시 읽기(달러/100만)
NOTES = "notes"
KEEP_PREV = 3
SPLIT = "\n## 해석"

SYSTEM = """너는 고양이 AI 쇼츠 채널(Meow Remix TV · 영어권 · 하루 최대 12편 자동 업로드)의 분석 담당이다.
아래 '근거'(코드가 센 숫자)와 지난 노트를 읽고, 사람이 나중에 '유지할지 고칠지' 정할 때 볼 짧은 해석을 한국어로 쓴다.

규칙:
- 숫자에 있는 것만 사실로 쓴다. 숫자로 확인 안 되는 생각은 문장 끝에 '(추측)'을 붙인다.
- 편 수가 적으면(꼴마다 3편 안 되거나 2일 넘은 편이 8편 안 되면) 결론을 내지 말고 '아직 이르다'고 쓴다.
- 지난 노트에서 바꾼 것(꼴 비율·미리 보기)이 그 뒤 숫자에 어떻게 나타났는지 한 줄로 이어 본다(아직 모르면 모른다고).
- 짧게. 보고서 말투·장황한 나열 금지. 제안은 최대 2개.

형식(마크다운, 이 제목 그대로):
## 해석(AI · 추측 포함)
- 3~5줄
## 유지 · 고칠 후보
- 최대 2개 · 각 줄에 근거 숫자
## 다음에 볼 것
- 1~2줄"""


def _med(xs: list[float]) -> float | str:
    return round(statistics.median(xs), 1) if xs else "-"


def _mean(xs: list[float]) -> float | str:
    return round(sum(xs) / len(xs), 1) if xs else "-"


def facts(stats: dict | None, mix: dict | None, day: dt.date, now: dt.datetime) -> tuple[str, int]:
    """① 근거(한국어 마크다운) · 2일 넘은 편 수."""
    vids = (stats or {}).get("videos") or []
    old = [v for v in vids if AN._age_h(v, now) >= AN.JUDGE_AGE_H]
    rows = {r["video"]: r for r in TU.scored(stats, now)}
    L = [f"# 고양이 쇼츠 정리 노트 — {day.isoformat()}", "", "## 근거(숫자 · 코드가 셈)"]
    if not vids:
        L.append("- 성적 없음(stats.json 없음 또는 공개 쇼츠 0편)")
    else:
        L.append(f"- 성적 기준 {(stats or {}).get('at', '?')} · 공개 쇼츠 {len(vids)}편(2일 넘은 편 {len(old)}편) · "
                 f"조회수 합 {sum(v.get('views', 0) for v in vids):,}")
        if old:
            L.append(f"- 2일 넘은 편: 조회수 중앙값 {_med([v.get('views', 0) for v in old])} · "
                     f"평균 시청 % 중앙값 {_med([v.get('avg_pct', 0) for v in old])} · "
                     f"쇼츠 피드 비중 중앙값 {_med([100 * v.get('feed_share', 0) for v in old])}% · "
                     f"피드가 안 받아 준 편(20회 안 됨) {sum(v.get('views', 0) < AN.JUDGE_MIN_VIEWS for v in old)}편")
            L += ["", "| 꼴 | 편 | 조회수 평균 | 평균 시청 % | 피드 % | 점수(0~1) |", "|---|---|---|---|---|---|"]
            fs = TU.format_scores(list(rows.values()))
            for f in TU.FORMATS:
                g = [v for v in old if v.get("format") == f]
                L.append(f"| {f} | {len(g)} | {_mean([v.get('views', 0) for v in g])} | {_mean([v.get('avg_pct', 0) for v in g])} | "
                         f"{_mean([100 * v.get('feed_share', 0) for v in g])} | {fs[f]['score'] if fs[f]['score'] is not None else '-'} |")
            arms = TU.tease_arms(list(rows.values()))
            L.append("")
            sc = lambda x: "-" if x is None else x  # noqa: E731
            L.append(f"- 결말 미리 보기 A/B(2일 넘은 편 · A/B 뒤 편만): 켬 {arms['on']['n']}편 점수 {sc(arms['on']['score'])} · "
                     f"끔 {arms['off']['n']}편 점수 {sc(arms['off']['score'])}")
            rk = sorted([v for v in old if v["video"] in rows], key=lambda v: rows[v["video"]]["s"], reverse=True)
            if len(rk) >= 6:
                for name, part in (("가장 잘 된 3편", rk[:3]), ("가장 안 된 3편", rk[-3:])):
                    L.append(f"- {name}: " + " / ".join(
                        f"{v.get('format')} \"{v.get('caption', '')}\" {v.get('views', 0)}회·{v.get('avg_pct', 0)}%" for v in part))
    if mix:
        L.append(f"- 오늘 틀(자동 조정): 꼴 " + " · ".join(f"{f} {round(100 * mix['weights'].get(f, 0))}%" for f in TU.FORMATS)
                 + f" · 미리 보기 끄는 편 {round(100 * mix.get('tease_off', 0))}%")
        for w in mix.get("why") or []:
            L.append(f"  - {w}")
        log = (mix.get("log") or [])[-8:-1]
        if log:
            L.append("- 지난 틀: " + " / ".join(
                f"{x['date'][5:]} " + "·".join(f"{f[:2]}{round(100 * x['weights'].get(f, 0))}" for f in TU.FORMATS)
                + f" 끔{round(100 * x.get('tease_off', 0))}" for x in log))
    return "\n".join(L), len(old)


def previous(note_dir: str, day: dt.date, k: int = KEEP_PREV) -> list[str]:
    ps = sorted(p for p in glob.glob(os.path.join(note_dir, "20??-??-??.md")) if os.path.basename(p)[:10] < day.isoformat())
    out = []
    for p in ps[-k:]:
        with open(p, encoding="utf-8") as f:
            out.append(f.read())
    return out


def _rows_for_model(stats: dict | None, now: dt.datetime) -> str:
    keep = ("published", "format", "caption", "title", "views", "avg_pct", "avg_sec", "likes", "subs", "feed_share", "tease")
    vids = (stats or {}).get("videos") or []
    return "\n".join(json.dumps({k: v.get(k) for k in keep} | {"age_h": round(AN._age_h(v, now))}, ensure_ascii=False)
                     for v in vids[:100])


def interpret(client, fact_md: str, stats: dict | None, prev: list[str], now: dt.datetime) -> tuple[str, dict]:
    user = "\n\n".join([
        "# 근거(오늘)", fact_md,
        "# 편별 숫자(새것부터 · age_h = 공개 뒤 시간)", _rows_for_model(stats, now),
        "# 지난 노트(오래된 것부터)", *(prev or ["(없음 — 첫 노트)"]),
    ])
    with client.messages.stream(model=MODEL, max_tokens=8000, system=SYSTEM,
                                messages=[{"role": "user", "content": user}],
                                extra_body={"output_config": {"effort": EFFORT}}) as st:
        msg = st.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    u = msg.usage
    tok = {"input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0,
           "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = round((tok["input"] * pi + tok["cache_read"] * pc + tok["output"] * po) / 1e6, 4)
    return text, {"model": MODEL, "effort": EFFORT, "tokens": tok, "usd": usd}


def write(data_dir: str, day: dt.date, client=None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    nd = os.path.join(data_dir, NOTES)
    os.makedirs(nd, exist_ok=True)
    path = os.path.join(nd, day.isoformat() + ".md")
    if os.path.exists(path):
        return {"kept": True, "path": path}
    stats = AN.load(data_dir)
    fact_md, n_old = facts(stats, TU.load(data_dir), day, now)
    info: dict = {"date": day.isoformat(), "old": n_old, "api": None}
    if n_old == 0:
        body = "## 해석(AI · 추측 포함)\n- 아직 2일 넘은 편이 없어 해석은 건너뜀(API 안 씀)"
    else:
        try:
            if client is None:
                import anthropic
                client = anthropic.Anthropic()
            body, info["api"] = interpret(client, fact_md, stats, previous(nd, day), now)
            if not body.startswith("## 해석"):
                body = "## 해석(AI · 추측 포함)\n" + body
        except Exception as e:  # noqa: BLE001 — 해석이 실패해도 근거는 남긴다
            body = f"## 해석(AI · 추측 포함)\n- 해석 실패({type(e).__name__}: {str(e)[:200]}) — 근거만 남김"
            info["error"] = str(e)[:300]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fact_md + "\n\n" + body + "\n")
    with open(os.path.join(nd, day.isoformat() + "_api.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return {**info, "path": path}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="정리 노트 — 근거(숫자) + 해석(API) 한 장 · 저장만")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--dir", required=True)
    w.add_argument("--day", required=True)
    a = ap.parse_args(argv)
    r = write(a.dir, dt.date.fromisoformat(a.day))
    if r.get("kept"):
        print(f"📝 {a.day} 노트는 이미 있다 — 건너뜀")
        return 0
    api = r.get("api") or {}
    print(f"📝 {a.day} 노트 · 2일 넘은 편 {r['old']}편 · " + (f"해석 {api['model']} 약 {api['usd']}달러" if api else "해석 없음(API 안 씀)")
          + (f" · 실패: {r['error'][:120]}" if r.get("error") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
