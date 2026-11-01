#!/usr/bin/env python3
"""Nine Tails 매일 트렌드 편 — Claude API + 웹 검색으로 '지금 뜨는 것'을 우리 꼴(얼굴 없는 3D 실화·what-if)로 쓴다(2026-11-01).

왜: 사용자 11/01 "대성하려면 매일 트렌드와 히트성을 찾아 따라 하는 형태가 최고". 미리 써 둔 카탈로그(월·수·금)는 그대로 두고,
  사이 날(화·목·토·일 21:30 KST)에 그날 뜨는 소재를 우리 꼴로 바꾼 편을 끼운다. tools/scout_api.py 와 같은 틀.
흐름: 레이더(Nine Tails 칸)·정찰(data/scout — fit 에 nt_story 가 있는 것 먼저)·이미 쓴 소재 → Opus 5.5 + web_search·web_fetch
  → story_catalog 스키마의 편 하나(또는 {"skip": 사유}) → 코드 검사(story.check_episode + 공개일·출처를 실제로 열었나) → 오류를 붙여
  최대 3번. 공개일은 코드가 정한다(story.trend_slot — 빈 자리가 없으면 API 를 부르지 않고 skip). 토큰·검색·달러는 <날짜>_api.json.

    python gumiho/tales/trend_api.py write --day 2026-11-01 --radar /tmp/radar --scout /tmp/scout --trend /tmp/nt-trend
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import story as ST  # noqa: E402

MODEL = os.environ.get("NT_TREND_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("NT_TREND_EFFORT", "high")
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력, 출력, 캐시 읽기(달러/100만)
SEARCH_USD = 0.01
MAX_SEARCH, MAX_FETCH = 15, 10
TRIES = 3
EXAMPLE_ID = 9                          # 스키마 예시로 보여 줄 카탈로그 편(인물 기준 그림·편집·재사용이 다 들어 있다)

WRITER = """You write one YouTube Short script per day for "Nine Tails Tales" (English, viewers 13-30): faceless 3D
reconstructions of short true survival stories and what-if science/disaster questions, 45-75 seconds.

Task: find something that is taking off right now (last 7-30 days) that fits that format, and turn it into one episode.
- Follow what makes the hit work (hook, structure, title pattern), but write every sentence yourself. Never copy narration,
  re-upload or buy anything.
- Every fact needs a source you actually opened with web_fetch in this conversation. Numbers exactly as the page says.
- Real people: public facts only, shown only as smooth featureless mannequins. No defamation, no fake true stories, no child
  horror, no gore, no politics, no health claims.
- Topics already used (user message) are off limits.
- If nothing current fits well, return {"skip": "<reason>"} instead of forcing it.

Output: one JSON object only, no code fences, in the episode schema shown in the user message (same keys as the example),
plus "trend": {"why_now": "...", "pattern": "which hit's hook/structure/title you followed", "evidence": [{"title": "...",
"url": "https://...", "date": "YYYY-MM-DD"}]} (1-3 links showing it is hot now). Do not set id, from, written or kind.
Script rules: open on the decisive moment; one line per shot; the last shot loops to the first (reuse 0, move loop_end);
110-200 spoken words; write numbers as "{display|spoken}". Image prompts describe what to draw positively (no negations),
never ask for text, logos or signs, and every person is "a smooth featureless matte white mannequin". Use "character" + "edit"
only for one recurring person. Facts reference sources by index. If the code returns errors, fix them and return the whole JSON.
"""


def _read(path: str, limit: int | None = None) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            t = f.read()
    except OSError:
        return "(없음)"
    return t if limit is None or len(t) <= limit else t[:limit] + "\n…"


def radar_nt(radar_dir: str, limit: int = 9000) -> str:
    """레이더 report.md 에서 Nine Tails 칸만."""
    t = _read(os.path.join(radar_dir, "report.md"))
    parts = re.split(r"(?m)^## ", t)
    keep = ["## " + p for p in parts[1:] if "Nine Tails" in p.splitlines()[0]]
    return ("\n".join(keep) or "(없음)")[:limit]


def scout_brief(scout_dir: str, day: dt.date, limit: int = 7000) -> str:
    """오늘(없으면 가장 최근) 정찰 — nt_story 에 맞는 것 먼저, 그다음 나머지 영어권 hot."""
    fs = sorted(glob.glob(os.path.join(scout_dir, "20??-??-??.json")))
    fs = [f for f in fs if os.path.basename(f)[:10] <= day.isoformat()]
    if not fs:
        return "(없음)"
    try:
        s = json.load(open(fs[-1], encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "(읽기 실패)"
    hot = s.get("hot") or []
    hot = sorted(hot, key=lambda h: ("nt_story" not in (h.get("fit") or []), h.get("market") != "us"))
    lines = [f"(scout {s.get('date')})"]
    for h in hot:
        ev = "; ".join(e.get("url", "") for e in h.get("evidence") or [])
        lines.append(f"- [{h.get('market')}|{','.join(h.get('fit') or [])}] {h.get('topic')} — {h.get('why_now', '')} ({ev})")
    for c in s.get("candidates") or []:
        if c.get("line") == "nt_story":
            fs_ = "; ".join(f"{f.get('fact')} <{f.get('source_url')}>" for f in c.get("facts") or [])
            lines.append(f"- candidate nt_story: {c.get('title_idea')} | {fs_}")
    return "\n".join(lines)[:limit]


def used(trend_dir: str) -> list[str]:
    out = [f"{e['slug']} / {e['title']}" for e in ST.episodes()]
    for p in sorted(glob.glob(os.path.join(trend_dir, "20??-??-??.json"))):
        try:
            e = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(e, dict) and e.get("slug"):
            out.append(f"{e['slug']} / {e.get('title', '')}")
    return out


def example() -> str:
    e = ST.find(str(EXAMPLE_ID))
    return json.dumps({k: v for k, v in e.items() if k not in ("id", "from")}, ensure_ascii=False)


def user_message(day: dt.date, slot: dt.date, radar_dir: str, scout_dir: str, trend_dir: str) -> str:
    return "\n".join([
        f"# Today (KST) {day.isoformat()} — this episode publishes {slot.isoformat()} 21:30 KST", "",
        "## Allowed values", f"format: {list(ST.FORMATS)} · music: {list(ST.MUSIC)} · move: {list(ST.MOVES)}",
        f"fx: {list(ST.FX)} · sfx: {list(ST.SFX)} · shots {ST.SHOTS[0]}-{ST.SHOTS[1]} · flash only within 0.6 s of a shot start",
        "\n## Example episode (schema — copy the keys, not the content)\n" + example(),
        "\n## Trend radar — Nine Tails niches (reference channels, view multiples)\n" + radar_nt(radar_dir),
        "\n## Today's web scout (data/scout)\n" + scout_brief(scout_dir, day),
        "\n## Used topics (off limits)\n" + "\n".join(used(trend_dir))[:6000],
    ])


def parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("JSON 객체가 없다")
    out = json.loads(t[a:b + 1])
    if not isinstance(out, dict):
        raise ValueError("최상위가 객체가 아니다")
    return out


def norm(u: str) -> str:
    u = (u or "").strip().split("#")[0].rstrip("/")
    return re.sub(r"^http://", "https://", u).lower()


def finalize(ep: dict, day: dt.date, slot: dt.date) -> dict:
    """코드가 정하는 칸(모델이 넣어도 덮어쓴다)."""
    ep = dict(ep)
    ep.update({"id": int(day.strftime("%Y%m%d")), "kind": "trend", "written": day.isoformat(), "from": slot.isoformat()})
    return ep


def check(ep: dict, day: dt.date, slot: dt.date, used_list: list[str], fetched: set, seen: set) -> list[str]:
    if "skip" in ep:
        return [] if str(ep["skip"]).strip() else ["skip 사유가 비었다"]
    errs = ST.check_episode(ep)
    if ep.get("from") != slot.isoformat():
        errs.append(f"from 은 {slot}")
    for s in ep.get("sources") or []:
        if norm(s.get("url", "")) not in fetched:
            errs.append(f"출처 {s.get('url')} 는 이 대화에서 web_fetch 로 연 페이지가 아니다 — 열어 보고 쓰거나 빼라")
    for x in (ep.get("trend") or {}).get("evidence") or []:
        if norm(x.get("url", "")) not in fetched | seen:
            errs.append(f"trend.evidence {x.get('url')} 는 검색 결과·열어 본 페이지에 없다")
    taken = {u.split(" / ")[0] for u in used_list} | {u.split(" / ", 1)[-1].lower() for u in used_list}
    if ep.get("slug") in taken or str(ep.get("title", "")).lower() in taken:
        errs.append("이미 쓴 소재·제목이다")
    return errs


def _walk_urls(obj, out: set, depth: int = 0):
    if depth > 6 or obj is None:
        return
    if isinstance(obj, dict):
        items = obj.items()
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            _walk_urls(x, out, depth + 1)
        return
    else:
        items = ((k, getattr(obj, k)) for k in ("url", "content", "source") if hasattr(obj, k))
    for k, v in items:
        if k == "url" and isinstance(v, str):
            out.add(norm(v))
        elif isinstance(v, (dict, list, tuple)) or hasattr(v, "__dict__"):
            _walk_urls(v, out, depth + 1)


def tool_urls(content, fetched: set, seen: set):
    """서버 도구 결과에서 연 페이지(web_fetch)·검색에 나온 페이지(web_search) 주소를 모은다."""
    for b in content or []:
        t = getattr(b, "type", "") if not isinstance(b, dict) else b.get("type", "")
        c = b.get("content") if isinstance(b, dict) else getattr(b, "content", None)
        if t == "web_fetch_tool_result":           # 실패한 읽기(web_fetch_tool_error)에는 url 이 없다 → 센다 = 실제로 열었다
            _walk_urls(c, fetched)
        elif t == "web_search_tool_result":
            _walk_urls(c, seen)


def _usage_add(tok: dict, usage) -> None:
    for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                 ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
        tok[k] += getattr(usage, f, 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        tok["web_search"] += getattr(stu, "web_search_requests", 0) or 0
        tok["web_fetch"] += getattr(stu, "web_fetch_requests", 0) or 0


def ask(client, messages: list[dict], tok: dict, fetched: set, seen: set, max_pauses: int = 8) -> str:
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCH},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_FETCH}]
    msgs = list(messages)
    for _ in range(max_pauses + 1):
        with client.messages.stream(model=MODEL, max_tokens=32000, system=WRITER, messages=msgs, tools=tools,
                                    extra_body={"output_config": {"effort": EFFORT}}) as st:
            msg = st.get_final_message()
        _usage_add(tok, msg.usage)
        tool_urls(msg.content, fetched, seen)
        if msg.stop_reason == "pause_turn":
            msgs = msgs + [{"role": "assistant", "content": msg.content}]
            continue
        if msg.stop_reason == "refusal":
            raise RuntimeError("모델이 답을 거절했다(refusal)")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("출력이 max_tokens 에서 잘렸다")
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raise RuntimeError(f"pause_turn 이 {max_pauses}번 넘게 이어졌다")


def _save(path: str, obj: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def write(day: dt.date, radar_dir: str, scout_dir: str, trend_dir: str, client=None) -> dict:
    os.makedirs(trend_dir, exist_ok=True)
    out = os.path.join(trend_dir, f"{day.isoformat()}.json")
    taken = {dt.date.fromisoformat(e["from"]) for e in ST.load_trends(trend_dir, quiet_errors=True)}
    slot = ST.trend_slot(day, taken)
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "web_search": 0, "web_fetch": 0}
    info = {"date": day.isoformat(), "model": MODEL, "effort": EFFORT, "tokens": tok, "usd": 0.0}
    if slot is None:                                   # API 를 부르지 않는다(비용 0)
        _save(out, {"date": day.isoformat(), "skip": f"트렌드 자리 없음 — {ST.TREND_AHEAD}일 안 화·목·토·일이 다 찼다"})
        _save(os.path.join(trend_dir, f"{day.isoformat()}_api.json"), dict(info, ok=True, tries=0, slot=None))
        return dict(info, ok=True, tries=0, slot=None, skip=True)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    used_list = used(trend_dir)
    messages = [{"role": "user", "content": [{"type": "text", "text": user_message(day, slot, radar_dir, scout_dir, trend_dir),
                                              "cache_control": {"type": "ephemeral"}}]}]
    fetched, seen = set(), set()
    errs: list[str] = []
    history: list[list[str]] = []
    result = None
    for n in range(1, TRIES + 1):
        text = ask(client, messages, tok, fetched, seen)
        try:
            raw = parse(text)
            ep = raw if "skip" in raw else finalize(raw, day, slot)
            errs = check(ep, day, slot, used_list, fetched, seen)
            result = {"date": day.isoformat(), "skip": str(raw["skip"])[:500]} if "skip" in raw else ep
        except (ValueError, KeyError, TypeError) as e:
            errs = [f"출력을 읽을 수 없다: {e}"]
        history.append(errs)
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"))
        if not errs:
            break
        for x in errs:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The code checks failed. Fix these (fetch pages if needed) and return the whole "
                                                 "JSON again:\n" + "\n".join(f"- {x}" for x in errs)}]
    if errs:                                            # 세 번 다 못 넘으면 그날은 건너뛴다(틀린 편을 올리지 않는다)
        result = {"date": day.isoformat(), "skip": "검사 실패: " + " | ".join(errs)[:800]}
    _save(out, result)
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6 \
        + tok["web_search"] * SEARCH_USD
    info.update({"ok": not errs, "tries": n, "slot": slot.isoformat(), "usd": round(usd, 3), "errors": errs,
                 "history": history, "fetched": len(fetched), "skip": "skip" in result})
    _save(os.path.join(trend_dir, f"{day.isoformat()}_api.json"), info)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Nine Tails 매일 트렌드 편(Claude API)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--day", required=True)
    w.add_argument("--radar", required=True)
    w.add_argument("--scout", required=True)
    w.add_argument("--trend", required=True)
    a = ap.parse_args()
    info = write(dt.date.fromisoformat(a.day), a.radar, a.scout, a.trend)
    t = info["tokens"]
    print(f"🎬 {info['model']} · 공개 {info.get('slot')} · 시도 {info['tries']} · 검색 {t['web_search']} · 읽기 {t['web_fetch']}"
          f" · 출력 {t['output']:,} 토큰 · 약 {info['usd']}달러{' · 건너뜀' if info.get('skip') else ''}")
    return 0                       # 검사 실패도 그날 skip 으로 남겼다 — 같은 날 다시 돌며 돈을 쓰지 않게 올리기까지 간다


if __name__ == "__main__":
    sys.exit(main())
