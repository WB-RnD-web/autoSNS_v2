#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""콘텐츠 채우기(refill) — 클라우드 루틴 대신 Claude API 로 (.github/workflows/refill-api.yml · 2026-11-14).

왜: 11/13 사용자 "API 키로 도는 것만 켜고 루틴은 끄라" → 주간 채우기 루틴(trig_0112Nu…)도 같이 꺼졌다.
  11/14 사용자 '응 그렇게 바꿔줘' — 목록형 줄기가 바닥나기 전에 API 가 다음 편을 써서 PR 을 올린다.
  루틴이 하던 tools/REFILL.md 순서를 코드로 옮겼다: runway 로 고르고 → API 가 명세를 쓰고 → 번호·from·장 번호·
  출생연도 나누기는 코드가 정하고(결정론) → 검사가 통과할 때까지 오류를 붙여 다시 → 워크플로가 refill/<줄기>-<날짜> 로
  push(GH_PAT) → refill-pr.yml 이 채우기 검사·전체 테스트 뒤 PR. 머지는 사람이 한다.

    python tools/refill_api.py plan [--date D] [--lead 21]       # 채울 줄기 id(한 줄에 하나 · 없으면 빈 출력)
    python tools/refill_api.py fill wb_lf27 --env F --msg M [--date D] [--n 12] [--root DIR] [--base-root DIR]

지금 줄기: wb_lf27(왕별이 롱폼 '2027 정미년 깊이 보기' E17~). 사실(신살·삼재·달·행운·출생연도)은 코드가 띠마다
  계산한다(longform_2027.ddi_facts) — 모델은 '무엇을 어떤 순서로 다룰지'(제목·각도·장·질문 씨앗)만 쓴다. 웹 검색 없음.
다른 목록 줄기(인스타 sci·뜯어보기·밤 편 · NT 쇼츠)는 11/07 고양이 전환 뒤 안 돈다 — 다시 켜면 STREAMS 에 더한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KST = dt.timezone(dt.timedelta(hours=9))
MODEL = os.environ.get("REFILL_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("REFILL_EFFORT", "high")
TRIES = 3
LEAD = 21            # 남은 날이 이보다 적으면 채운다 — runway 경고(14일)보다 일주일 먼저(사람이 머지할 틈)
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력·출력·캐시 읽기($/M)
STREAMS = {
    "wb_lf27": {"name": "2027 정미년 깊이 보기 롱폼", "n": 12, "min_keep": 4,
                "files": ["pipeline/longform_2027_more.json", "pipeline/longform_2027_catalog.json"]},
}


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


# ── 고르기 ─────────────────────────────────────────────
def runway_rows(date: str | None = None, root: str = ROOT) -> list[dict]:
    r = subprocess.run([sys.executable, os.path.join("tools", "runway.py"), "--json"] + (["--date", date] if date else []),
                       cwd=root, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        raise SystemExit("runway 실패:\n" + r.stdout[-800:] + r.stderr[-800:])
    data = json.loads(r.stdout)
    return data["streams"] if isinstance(data, dict) else data


def plan(rows: list[dict], lead: int = LEAD) -> list[str]:
    """API 로 채우는 줄기 중 refillable 이고 남은 날이 lead 보다 적은 것 — 남은 날이 적은 것부터."""
    pick = [r for r in rows if r.get("id") in STREAMS and r.get("refillable")
            and isinstance(r.get("days_left"), int) and r["days_left"] < lead]
    return [r["id"] for r in sorted(pick, key=lambda r: r["days_left"])]


def from_for(row: dict, today: dt.date) -> dt.date:
    """새 편 from = 마지막 편 다음 날(내일보다 이르면 내일). 이미 바닥났으면 사흘 뒤(머지할 틈 — REFILL.md 공통 규칙)."""
    last = row.get("last")
    if row.get("days_left") and last:
        return max(dt.date.fromisoformat(last) + dt.timedelta(days=1), today + dt.timedelta(days=1))
    return today + dt.timedelta(days=3)


# ── 2027 깊이 보기(wb_lf27) ─────────────────────────────
def lf27_mod():
    p = os.path.join(ROOT, "pipeline")
    if p not in sys.path:
        sys.path.insert(0, p)
    import longform_2027 as LF
    return LF


def split_years(years: list[int], k: int) -> list[list[int]]:
    """한 띠의 출생연도 장이 k개면 코드가 나눈다 — 1개 = 전부 · 2개 = 1960년대까지 / 1970년대부터(단독 편과 같다) ·
    3개 이상 = 차례로 고르게."""
    if k <= 1:
        return [list(years)]
    if k == 2:
        old, new = [y for y in years if y < 1970], [y for y in years if y >= 1970]
        if old and new:
            return [old, new]
    n = len(years)
    return [years[i * n // k:(i + 1) * n // k] for i in range(k)]


CH_KEYS = ("layout", "topic", "table", "animal", "title")


def lf27_normalize(sp: dict, eid: str, from_: dt.date, LF) -> dict:
    """모델 명세 → 코드가 정하는 칸을 채운 명세: id·from(결정론) · 장 id c01… · 출생연도 장 years(split_years)."""
    out = {"id": eid, "from": from_.isoformat()}
    for k in ("animals", "title", "thumb", "angle", "qa_seeds"):
        if k in sp:
            out[k] = sp[k]
    raw = [c for c in sp.get("chapters") or [] if isinstance(c, dict)]
    count: dict[str, int] = {}
    for c in raw:
        if c.get("layout") == "years" and c.get("animal") in LF.ANIMALS:
            count[c["animal"]] = count.get(c["animal"], 0) + 1
    parts = {a: split_years(LF.ddi_years(a), n) for a, n in count.items()}
    used: dict[str, int] = {}
    chs = []
    for k, c in enumerate(raw):
        c2 = {"id": f"c{k + 1:02d}", **{x: c[x] for x in CH_KEYS if x in c}}
        if c2.get("layout") == "years" and c2.get("animal") in parts:
            i = used.get(c2["animal"], 0)
            used[c2["animal"]] = i + 1
            c2["years"] = parts[c2["animal"]][i]
        chs.append(c2)
    out["chapters"] = chs
    return out


def lf27_extra_errs(sp: dict, LF, titles: set[str]) -> list[str]:
    """more_errs 밖에서 화면이 깨지거나 겹치는 것 — 띠 1~3 · 여러 띠는 같은 삼합 무리(신살이 같다) · 표와 띠 수 ·
    띠마다 출생연도 장 3개까지 · 앞 편과 같은 제목 X."""
    errs = []
    an = sp.get("animals") if isinstance(sp.get("animals"), list) else []
    an = [a for a in an if a in LF.ANIMALS]
    if not 1 <= len(an) <= 3:
        errs.append("animals 는 1~3띠")
    if len(an) > 1 and len({LF.ddi_facts(a)["group"] for a in an}) > 1:
        errs.append("여러 띠 편은 같은 삼합 무리(신자진·해묘미·인오술·사유축)만 — 편의 신살이 하나여야 한다")
    for c in sp.get("chapters") or []:
        t = c.get("table") if isinstance(c, dict) and c.get("layout") == "table" else None
        if t == "months3" and len(an) < 2:
            errs.append(f"chapters {c.get('id')}: months3(세 띠 달) 표는 2~3띠 편에만 — 한 띠는 months1")
        if t in ("months1", "people12") and len(an) != 1:
            errs.append(f"chapters {c.get('id')}: {t} 표는 한 띠 편에만(첫 띠만 그려진다)")
    for a in an:
        n = sum(1 for c in sp.get("chapters") or [] if isinstance(c, dict) and c.get("layout") == "years" and c.get("animal") == a)
        if n > 3:
            errs.append(f"{a}띠 출생연도 장은 3개까지")
    if sp.get("title") in titles:
        errs.append("title 이 앞 편과 같다 — 편마다 새 주제로")
    return errs


def lf27_errs(specs: list[dict], LF) -> list[tuple[str, list[str]]]:
    """[(id, 오류들)] — 앞 편이 틀려도 뒤 편을 계속 본다(모델에게 한 번에 다 알려 준다)."""
    before = [e["id"] for e in LF.EPISODES]
    titles = {e["title"] for e in LF.EPISODES}
    out = []
    for sp in specs:
        es = LF.more_errs(sp, before) + lf27_extra_errs(sp, LF, titles)
        out.append((sp.get("id"), es))
        before.append(sp.get("id"))
        titles.add(sp.get("title"))
    return out


RULES_LF27 = """너는 왕별이(55세 이상 어르신이 보는 운세 채널) 롱폼 '2027 정미년 깊이 보기'의 편성 작가다.
지금까지 나간·정해진 편(episodes_so_far) 뒤에 이어 갈 편의 '명세'만 쓴다(대본은 나중에 다른 단계가 쓴다).

꼭 지킬 것:
- 사실(신살·삼재·합충·좋은 달·조심할 달·행운·출생연도)은 facts_by_animal 에 있는 것만 바탕으로 각도를 잡는다. 지어내지 않는다.
- 같은 띠를 다시 다룰 땐 주제를 좁힌다(재물·건강·가족·자녀·이사·달력·환갑·2028 준비 …). 앞 편과 같은 제목·같은 판박이 구성 X —
  angle 에 '앞 편들과 무엇이 다른지'를 분명히 적는다. 한 띠 편과 같은 삼합 무리(2~3띠) 편을 섞어도 된다.
- 여러 띠 편은 같은 삼합 무리 안에서만(신자진: 원숭이·쥐·용 · 해묘미: 돼지·토끼·양 · 인오술: 호랑이·말·개 · 사유축: 뱀·닭·소).
- 제목: '2027년 ○○띠 …'로 시작 · 100자 안 · 한자·영어 등급·의료·투자·겁주는 말 X. 살·삼재 낱말은 '잘 넘기는 법'·'꼭 지킬 3가지'
  같은 조언 틀 안에서만. 한 해를 깎아내리지 않는다(조언형).
- thumb: big(10자 안팎, 예 '2027 양띠') · sub · pill(짧은 조언 한 줄).
- chapters 10~12개, 꼴 4가지 이상. 꼴: card(topic 에 다룰 거리 한 낱말·영어 소문자, 예 money) · table(table: sinsal12 | months3 | months1 |
  people12 — months3 은 2~3띠 편, months1·people12 는 한 띠 편) · years(animal: 그 편의 띠 — 띠마다 1~3장, 출생연도는 코드가 나눈다:
  2장이면 ① 1930~60년대생 ② 1970년대생부터) · qa · lucky. 편의 띠마다 years 장이 꼭 있어야 한다.
- qa_seeds 3~5개: 어르신이 할 법한 질문(끝은 ?). 실제로 누가 물은 것처럼 쓰지 않는다.
- id·from·장 id 는 코드가 붙인다 — 적지 않아도 된다.
- 출력은 ```json 블록 하나: {"episodes": [명세, …]} — 다른 말은 쓰지 않는다."""


def _section(path: str, anchor: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            t = f.read()
    except FileNotFoundError:
        return ""
    m = re.search(r'<a id="%s"></a>(.*?)(?=<a id=|\n---\n|\Z)' % re.escape(anchor), t, re.S)
    return m.group(1).strip() if m else ""


def lf27_system() -> str:
    with open(os.path.join(ROOT, "pipeline", "LONGFORM_2027_WRITING.md"), encoding="utf-8") as f:
        writing = f.read()
    return (f"{RULES_LF27}\n\n# 채우기 안내(tools/REFILL.md#wb_lf27)\n\n{_section(os.path.join(ROOT, 'tools', 'REFILL.md'), 'wb_lf27')}"
            f"\n\n# 대본 글쓰기 안내(참고 — 장 꼴이 화면에서 어떻게 쓰이는지)\n\n{writing}")


def _ch_line(c: dict) -> str:
    tag = c.get("topic") or c.get("table") or c.get("animal") or ""
    return f"{c['layout']}{':' + str(tag) if tag else ''} {c['title']}"


def lf27_user(LF, n: int, from_: dt.date) -> str:
    eps = [{"id": e["id"], "publish": e["publish"], "animals": e["animals"], "title": e["title"], "angle": e["angle"],
            "chapters": [_ch_line(c) for c in e["chapters"]]} for e in LF.EPISODES]
    facts = {}
    for a in LF.ANIMALS:
        f = {k: v for k, v in LF.ddi_facts(a).items() if k != "years"}
        f["birth_years"] = LF.ddi_years(a)
        facts[a] = f
    ex = next((e for e in LF.EPISODES if e.get("kind") == "single"), LF.EPISODES[0])
    example = {k: ex[k] for k in ("animals", "title", "thumb", "angle", "qa_seeds")}
    example["chapters"] = [{x: c[x] for x in CH_KEYS if x in c} for c in ex["chapters"]]
    ctx = {"year": LF.year_facts(), "episodes_so_far": eps, "facts_by_animal": facts}
    return (f"# 자료(JSON)\n{json.dumps(ctx, ensure_ascii=False, default=str)}\n\n"
            f"# 명세 모양(지난 편 하나 — 모양만 참고, 주제·제목은 새로)\n```json\n{json.dumps(example, ensure_ascii=False)}\n```\n\n"
            f"# 할 일\n{eps[-1]['id']} 뒤에 이어 갈 {n}편의 명세를 순서대로 써라(첫 편은 {from_.isoformat()} 이후 첫 월·수·금에 나간다 · "
            f"월·수·금 주 3편). 띠를 고르게 돌리고, 같은 띠가 연달아 나오지 않게.")


def extract_json(text: str):
    m = re.search(r"```json\s*(\{.*\}|\[.*\])\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def ask(client, system, messages):
    with client.messages.stream(model=MODEL, max_tokens=32000, system=system, messages=messages,
                                extra_body={"output_config": {"effort": EFFORT}}) as s:
        msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), msg.usage


def write_specs(LF, n: int, from_: dt.date, client=None, min_keep: int = 4) -> dict:
    """API 로 명세 n편 → 코드가 정규화 → 검사 → 오류를 붙여 다시(최대 TRIES). 끝까지 틀리면 앞에서부터 맞는 편만
    (min_keep 편 이상일 때). {ok, specs, tries, usd, errors}."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    system = [{"type": "text", "text": lf27_system(), "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": lf27_user(LF, n, from_)}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    n0 = len(LF.EPISODES)
    specs: list[dict] = []
    bad: list[tuple[str, list[str]]] = []
    tries = 0
    for tries in range(1, TRIES + 1):
        text, usage = ask(client, system, messages)
        for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            tok[k] += getattr(usage, f, 0) or 0
        try:
            data = extract_json(text)
            raw = data.get("episodes") if isinstance(data, dict) else data
            if not isinstance(raw, list) or not raw:
                raise ValueError("episodes 목록이 없다")
            specs = [lf27_normalize(sp if isinstance(sp, dict) else {}, f"E{n0 + 1 + i:02d}", from_, LF)
                     for i, sp in enumerate(raw[:n])]
            res = lf27_errs(specs, LF)
            bad = [(i, e) for i, e in res if e]
            if len(raw) < n:
                bad.append(("전체", [f"{n}편이 필요한데 {len(raw)}편"]))
        except (ValueError, KeyError, TypeError) as e:
            specs, bad = [], [("전체", [f"JSON 을 읽을 수 없다: {e}"])]
        print(f"   시도 {tries}: " + ("✅ 통과" if not bad else f"오류 {sum(len(e) for _, e in bad)}개"), flush=True)
        if not bad:
            break
        lines = [f"- {i}: {x}" for i, es in bad for x in es][:40]
        print("\n".join("     " + x[:300] for x in lines))
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "코드 검사에서 오류가 났다. 고쳐서 명세 전체({\"episodes\": […]})를 다시 내라.\n"
                                                 + "\n".join(lines)}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6
    errors = [f"{i}: {x}" for i, es in bad for x in es]
    if bad and specs:
        first_bad = next((k for k, (i, es) in enumerate(lf27_errs(specs, LF)) if es), len(specs))
        if first_bad >= min_keep:
            print(f"   ⚠️ 끝까지 틀린 편이 있어 앞 {first_bad}편만 붙인다")
            specs, bad = specs[:first_bad], []
    return {"ok": not bad and bool(specs), "specs": specs if not bad else [], "tries": tries,
            "usd": round(usd, 3), "tokens": tok, "errors": errors}


def lf27_append(specs: list[dict], root: str = ROOT) -> None:
    """끝에만 붙이고(REFILL.md 공통 규칙) 카탈로그를 코드 출력과 맞춘다(catalog --write)."""
    p = os.path.join(root, "pipeline", "longform_2027_more.json")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data["episodes"] = list(data.get("episodes") or []) + specs
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    r = subprocess.run([sys.executable, os.path.join("pipeline", "longform_2027.py"), "catalog", "--write"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        raise RuntimeError("catalog --write 실패: " + (r.stdout + r.stderr)[-600:])


def lf27_dates(ids: list[str], root: str = ROOT) -> dict[str, str]:
    r = subprocess.run([sys.executable, os.path.join("pipeline", "longform_2027.py"), "schedule"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    got = dict(re.findall(r"^(E\d+)\s+(\d{4}-\d{2}-\d{2})", r.stdout, re.M))
    return {i: got.get(i, "?") for i in ids}


def refill_check(today: dt.date, root: str = ROOT, base_root: str | None = None) -> tuple[bool, str]:
    args = [sys.executable, os.path.join(ROOT, "tools", "refill_check.py"), "--date", today.isoformat(), "--root", root]
    if base_root:
        args += ["--base-root", base_root]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def commit_message(stream: str, specs: list[dict], dates: dict[str, str], check_out: str, info: dict) -> str:
    st = STREAMS[stream]
    first, last = dates[specs[0]["id"]], dates[specs[-1]["id"]]
    md = lambda s: s[5:].replace("-", "/") if len(s) == 10 else s  # noqa: E731
    rows = "\n".join(f"- {sp['id']} {dates[sp['id']]} · {'·'.join(sp['animals'])}띠 — {sp['title']}" for sp in specs)
    return f"""채우기: {st['name']} {len(specs)}편({md(first)}~{md(last)})

## 무엇을 붙였나
- 줄기: {stream} — {st['files'][0]}
- 항목: {specs[0]['id']}~{specs[-1]['id']}({len(specs)}편) · from {specs[0]['from']}
- 편성: {first} ~ {last}(월·수·금 20:00)

{rows}

## 출처
- 웹 숫자 없음 — 신살·삼재·좋은 달·행운·출생연도는 코드(longform_2027.ddi_facts)가 띠마다 계산한다

## 검사
- python tools/refill_check.py ✅
```
{check_out[-1500:]}
```
- 전체 테스트는 refill-pr.yml 이 PR 을 열기 전에 다시 돌렸다

## 머지
- from({specs[0]['from']}) 전에 머지해야 첫 편부터 나간다
- 쓴 곳: Claude API({MODEL}) · 시도 {info['tries']} · 약 {info['usd']}달러 — .github/workflows/refill-api.yml

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""


def fill(stream: str, today: dt.date, n: int | None = None, client=None, root: str = ROOT,
         base_root: str | None = None, rows: list[dict] | None = None) -> dict:
    if stream not in STREAMS:
        raise SystemExit(f"API 로 채우는 줄기가 아니다: {stream} (있는 것: {', '.join(STREAMS)})")
    st = STREAMS[stream]
    rows = rows if rows is not None else runway_rows(today.isoformat(), root)
    row = next((r for r in rows if r.get("id") == stream), {})
    from_ = from_for(row, today)
    LF = lf27_mod()
    info = write_specs(LF, n or st["n"], from_, client=client, min_keep=st["min_keep"])
    print(f"🧾 {stream} · {MODEL} · 시도 {info['tries']} · 약 {info['usd']}달러 · 붙일 편 {len(info['specs'])}")
    if not info["ok"]:
        return {**info, "ok": False, "why": "명세 검사를 끝내 통과하지 못했다"}
    lf27_append(info["specs"], root)
    ok, out = refill_check(today, root, base_root)
    print(out)
    if not ok:
        return {**info, "ok": False, "why": "refill_check 실패", "check": out}
    dates = lf27_dates([sp["id"] for sp in info["specs"]], root)
    msg = commit_message(stream, info["specs"], dates, out, info)
    return {**info, "ok": True, "message": msg, "branch": f"refill/{stream}-{today.strftime('%Y%m%d')}",
            "files": st["files"], "dates": dates}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="콘텐츠 채우기(API) — 목록형 줄기가 바닥나기 전에 다음 편 명세를 쓴다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--date")
    p.add_argument("--lead", type=int, default=LEAD)
    f = sub.add_parser("fill")
    f.add_argument("stream")
    f.add_argument("--env", required=True, help="워크플로가 읽을 BRANCH·COUNT·FILES")
    f.add_argument("--msg", required=True, help="커밋 글(제목 줄 = PR 제목 · 본문 = PR 본문)")
    f.add_argument("--date")
    f.add_argument("--n", type=int)
    f.add_argument("--root", default=ROOT)
    f.add_argument("--base-root")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "plan":
        for s in plan(runway_rows(today.isoformat()), a.lead):
            print(s)
        return 0
    res = fill(a.stream, today, a.n, root=a.root, base_root=a.base_root)
    if not res["ok"]:
        print(f"::error::{res.get('why')} — push 하지 않는다\n  " + "\n  ".join(res.get("errors", [])[:20]))
        return 1
    with open(a.msg, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(res["message"])
    with open(a.env, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"BRANCH={shlex.quote(res['branch'])}\nCOUNT={len(res['specs'])}\nFILES={shlex.quote(' '.join(res['files']))}\n")
    print(f"✅ {res['branch']} · {len(res['specs'])}편 · {min(res['dates'].values())} ~ {max(res['dates'].values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
