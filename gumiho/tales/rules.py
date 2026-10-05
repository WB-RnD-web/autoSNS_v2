#!/usr/bin/env python3
"""Nine Tails RULES — 동아시아 규칙괴담 매일 쇼츠: 편성(날짜 → 한 편) · 대본 검사 · 메타.

    python gumiho/tales/rules.py next --date 2026-10-14     # 오늘 쓸 한 편(catalog 항목 + 저장 경로)
    python gumiho/tales/rules.py check output/tales_rules/R001_name-called-at-night.json

왜(2026-10-05): 사용자 "한복 차림에 설화 읽기로는 대박 힘들다 — 어린 친구·청년 타깃, 무조건 도파민·자극성·중독성".
  벤치마킹(https://claude.ai/artifact/A7cvXgPAzY8RfZbw29ScNo): 2026 신생 AI 쇼츠 채널은 하루 ~1편씩 올려 16–49번째에
  첫 100만. 터진 장치 = 첫 1초 2인칭 경고("If you see…") · 20–30초 · 끝이 처음으로 이어지는 루프 · 같은 캐릭터.
  Tung Tung Tung Sahur(민속+규칙+캐릭터)·Mandela 경고문이 같은 장치. 영어권에 규칙괴담 쇼츠 큰 채널은 아직 없다.
  ★반대로 이름만 바꾼 AI 템플릿 채널 16곳이 2026-01 삭제됐다 → 편마다 다른 전설·다른 규칙·실제 근거(catalog facts).
대본은 루틴이 WRITING_RULES.md 를 보고 쓴다. ★규칙 문장은 catalog facts 에서만 — 지어내지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import tales as T  # noqa: E402  (LOOKS · RULE_TITLE · BANNED · DATED 를 같이 쓴다)

CATALOG = os.path.join(HERE, "rules_catalog.json")
OUT_DIR = "output/tales_rules"
FORMATS = ("rules", "versus", "pov")
REACTS = ("shock", "smug", "scared", "laugh")       # 치비 구미 리액션(assets/tales/chibi_<react>.png)
WORDS = (45, 95)            # 20–35초(F2 ≈ 159 wpm × 템포 0.97 + 줄 사이 쉼)
LINES = (5, 9)
SAY_MAX = 22                # 한 줄(한 화면) 최대 단어 — 화면이 3–6초마다 바뀐다
TEXT_MAX = 48               # 화면 큰 글자(규칙 문장) 최대 글자 수
HOOK_WORDS, HOOK_CHARS = 7, 38
TITLE_MAX = 100
# 규칙형 제목: tales.RULE_TITLE 보다 넓게 — 'If Someone Calls…', 'If a Kappa…' 같은 조건문도 규칙이다
RULE_TITLE = re.compile(r"(?i)^\s*(never|don'?t|do not|if\b|always|you should never|why you should never)")
VS_TITLE = re.compile(r"(?i)\bvs\.?\b")
POV_TITLE = re.compile(r"(?i)^\s*pov\b")
SHOW_GUMI = re.compile(r"(?i)\b(gumi|fox girl|nine[- ]tailed fox girl|silver[- ]haired (girl|woman))\b")


def catalog(path: str = CATALOG) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assigned(date: dt.date, cat: dict | None = None) -> dict | None:
    """start 부터 하루 한 편, 목록 순서대로. 시작 전이거나 목록이 바닥나면 None."""
    cat = cat or catalog()
    k = (date - dt.date.fromisoformat(cat["start"])).days
    rs = cat["rules"]
    return rs[k] if 0 <= k < len(rs) else None


def file_for(e: dict) -> str:
    return f"{OUT_DIR}/R{e['n']:03d}_{e['slug']}.json"


def words(t: str) -> int:
    return len((t or "").split())


def check(s: dict, cat: dict | None = None) -> list[str]:
    cat = cat or catalog()
    errs: list[str] = []
    e = next((x for x in cat["rules"] if x["n"] == s.get("id")), None)
    if not e:
        return [f"id {s.get('id')!r} 가 rules_catalog 에 없다"]
    if s.get("slug") != e["slug"]:
        errs.append(f"slug {s.get('slug')!r} ≠ catalog {e['slug']!r}")
    fmt = s.get("format")
    if fmt != e["format"]:
        errs.append(f"format {fmt!r} ≠ catalog {e['format']!r}")
    if s.get("look") not in T.LOOKS:
        errs.append(f"look 필수 — {', '.join(T.LOOKS)} 중 하나")
    title = s.get("title", "")
    if not title.endswith("#shorts") or len(title) > TITLE_MAX:
        errs.append(f"title 은 {TITLE_MAX}자 이하, '#shorts' 로 끝난다")
    if fmt == "rules" and not RULE_TITLE.match(title):
        errs.append("rules 제목은 규칙형으로 시작(Never / Don't / If You / Always …)")
    if fmt == "versus" and not VS_TITLE.search(title):
        errs.append("versus 제목에 'vs' 가 있어야 한다")
    if fmt == "pov" and not POV_TITLE.match(title):
        errs.append("pov 제목은 'POV:' 로 시작")
    hook = s.get("hook", "")
    if not hook or words(hook) > HOOK_WORDS or len(hook) > HOOK_CHARS:
        errs.append(f"hook(화면 위 두 줄)은 2–{HOOK_WORDS}단어·{HOOK_CHARS}자 이하")
    ls = s.get("lines") or []
    if not LINES[0] <= len(ls) <= LINES[1]:
        errs.append(f"lines {len(ls)}개 — {LINES[0]}–{LINES[1]}개")
    total = sum(words(x.get("say", "")) for x in ls) + words((s.get("gumi") or {}).get("say", ""))
    if not WORDS[0] <= total <= WORDS[1]:
        errs.append(f"말 {total}단어 — {WORDS[0]}–{WORDS[1]}단어(20–35초)")
    rule_nos = []
    for i, x in enumerate(ls):
        if not x.get("say") or not x.get("img"):
            errs.append(f"줄 {i}: say·img 필수")
            continue
        if words(x["say"]) > SAY_MAX:
            errs.append(f"줄 {i}: {words(x['say'])}단어 > {SAY_MAX}")
        if x.get("text") and len(x["text"]) > TEXT_MAX:
            errs.append(f"줄 {i}: 화면 글자 {len(x['text'])}자 > {TEXT_MAX}")
        if SHOW_GUMI.search(x["img"]):
            errs.append(f"줄 {i}: 그림에 구미를 그리지 않는다(구미는 끝의 치비 리액션으로만 나온다)")
        if x.get("look") is not None and x["look"] not in T.LOOKS:
            errs.append(f"줄 {i}: look {x['look']!r}")
        if x.get("rule") is not None:
            rule_nos.append(x["rule"])
        for t_ in (x["say"], x.get("text", "")):
            if T.BANNED.search(t_ or ""):
                errs.append(f"줄 {i}: 금지어")
            m = T.DATED.search(t_ or "")
            if m:
                errs.append(f"줄 {i}: 날짜 타는 말 {m.group(0)!r}")
    if ls and not (ls[0].get("text") and ls[0].get("img")):
        errs.append("첫 줄은 그림 + 화면 큰 글자(경고문) — 첫 1초에 읽혀야 한다")
    if fmt == "rules":
        if len(rule_nos) < 4 or rule_nos != list(range(1, len(rule_nos) + 1)):
            errs.append(f"rules: 규칙 번호 1부터 차례로 4개 이상(rule: 1,2,3…) — 지금 {rule_nos}")
        if not s.get("loop_back"):
            errs.append("rules: loop_back 필수 — 마지막 규칙이 첫 줄과 어떻게 이어지는지(루프) 한 줄")
    if fmt == "versus" and not s.get("vote"):
        errs.append("versus: vote 필수 — 댓글로 묻는 한 줄")
    g = s.get("gumi") or {}
    if g.get("react") not in REACTS:
        errs.append(f"gumi.react — {', '.join(REACTS)} 중 하나(끝에 치비 구미)")
    if not g.get("say") or words(g["say"]) > 16:
        errs.append("gumi.say — 구미의 판정·한마디 16단어 이하")
    if not s.get("source") or len(s.get("source", "")) < 20:
        errs.append("source 필수 — 어느 전설·관습에서 온 규칙인지(설명란에 그대로 나간다)")
    tags = s.get("tags") or []
    if not 6 <= len(tags) <= 15:
        errs.append("tags 6–15개")
    return errs


DISCLOSURE = ("Illustrations and the narrator's voice are AI-generated. The rules come from real East Asian legends, "
              "superstitions and internet folklore — retold for fun, not instructions. 13+.")


def meta(s: dict, long_link: str | None = None) -> dict:
    lines = [s.get("description_hook") or s["hook"].capitalize() + ".", "",
             f"Where this comes from: {s['source']}"]
    if s.get("vote"):
        lines += ["", f"Vote in the comments: {s['vote']}"]
    if long_link:
        lines += ["", f"Full tales from Gumi: {long_link}"]
    lines += ["", DISCLOSURE, "",
              "#shorts #scary #horror #rules #creepy #folklore #" + {"rules": "scaryrules", "versus": "monsterbattle",
                                                                      "pov": "pov"}[s["format"]]]
    tags = list(dict.fromkeys((s.get("tags") or []) + ["scary rules", "horror shorts", "asian folklore", "nine tails tales"]))
    return {"title": s["title"][:TITLE_MAX], "description": "\n".join(lines)[:4900], "tags": tags[:15]}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("--date", default=dt.date.today().isoformat())
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    a = ap.parse_args()
    if a.cmd == "next":
        e = assigned(dt.date.fromisoformat(a.date))
        if not e:
            print(json.dumps({"none": True, "why": "시작 전이거나 목록이 바닥났다 — 오늘은 쓰지 않는다"}, ensure_ascii=False))
            return 0
        print(json.dumps({"file": file_for(e), **e}, ensure_ascii=False, indent=1))
        return 0
    bad = 0
    for f in a.files:
        with open(f, encoding="utf-8") as fh:
            errs = check(json.load(fh))
        print(("❌ " if errs else "✅ ") + f)
        for x in errs:
            print("   - " + x)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
