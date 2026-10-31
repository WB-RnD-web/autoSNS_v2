#!/usr/bin/env python3
"""매일 바깥 흐름 찾기(scout) — Claude API + 웹 검색으로 지금 뜨는 주제·소재 후보를 모은다(2026-10-31).

왜: 사용자 10/31 "api key 로 매일매일 새로운 아이디어, 최신 유행, 최신 컨텐츠, 지금 핫한 소스를 찾아서 매일 돌면 어때?".
  트렌드 레이더(trend_radar.py)는 참고 유튜브 채널의 ★숫자만 본다. 그 밖(기사·커뮤니티·검색 흐름)은 아무도 안 봤다.
  보고서를 하나 더 늘리지 않는다(10/11 '점검·정기 보고 불필요'): 결과는 data/scout 에 쌓이고 ★맥박(pulse_api)이 읽어
  trends·actions 에 반영한다. 소재 후보는 사실마다 출처 링크가 있는 것만 남긴다(2단계에서 카탈로그 PR 로 옮긴다).
흐름: 우리 채널·꼴 요약 + 레이더 report.md + 재고(runway) + 이미 쓴 소재 목록 → Opus 5.5 + web_search·web_fetch
  → JSON(hot·candidates) → 검사(링크·개수·꼴 이름) → 오류면 붙여 다시(최대 3번). 실제 토큰·검색 횟수·달러를 api 에 남긴다.
비용: 10/31 첫 시험 = 검색 12번·읽기 2번·출력 1.1만 토큰 → 0.61달러. 검색을 20번으로 늘려 하루 0.7~1달러 추정. 결제 수단이 없어 크레딧이 바닥나면 거절될 뿐이다.

    python tools/scout_api.py write --day 2026-10-31 --radar /tmp/radar --out /tmp/scout
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
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MODEL = os.environ.get("SCOUT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("SCOUT_EFFORT", "high")
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력, 출력, 캐시 읽기(달러/100만)
SEARCH_USD = 0.01                       # 웹 검색 한 번
MAX_SEARCH, MAX_FETCH = 20, 8        # 10/31 첫 시험: 12번은 영어 쪽에서 다 써서 한국 쪽을 거의 못 봤다 → 20번 · 한국 먼저
TRIES = 3
# 후보가 들어갈 줄기 — 카탈로그 이름과 같게(2단계에서 이 줄기의 catalog 로 옮긴다)
LINES = {
    "insta_sci": "인스타 '속이 보이는 과학'(심해·우주·극한 생존 — 몸·기계 속을 열어 보는 20~35초)",
    "insta_teardown": "인스타 '과학으로 뜯어보는 물건'(생활 물건을 단면으로)",
    "insta_danger": "인스타 '위험한 진짜 이유'(무서운 제목 → 귀여운 진짜 사실 · 동물)",
    "insta_worker": "인스타 '심해 직장인'(블롭피시 캐릭터 직장 공감 + 진짜 심해 과학 한 장 · 동료 심해 생물)",
    "wb_table": "왕별이 운세 표 쇼츠(55세 이상 · 띠·출생연도·태어난 달·이름 · 명리 근거)",
    "nt_story": "Nine Tails(영어권 13~30세) — 얼굴 없는 3D 짧은 실화·what-if(쉬는 중 · 재개 검토)",
}
CHANNELS = """우리 채널(시청자·지금 꼴):
- 왕별이(유튜브, 한국 55세 이상): 매일 운세 12띠 표·풀이형 표·띠 테마 표·출생연도 나이 표·2027 신년운세 시리즈·롱폼 '2027 정미년 깊이 보기'.
  어르신 말투(등급·게임 말투·겁주기 금지). 목표: 2027-01-31 전 수익화(YPP).
- 인스타 @zerocrew.studio('소름과학 | 심해·우주·생존', 한국 10~20대): 낮·저녁 = sci(속이 보이는 과학)·뜯어보기·골라보기,
  밤(11/08~) = '위험한 진짜 이유' 카드 ↔ '심해 직장인' 블롭피시. 유튜브 홍보·참여 구걸(댓글·저장·팔로우 부탁) 금지.
- Nine Tails Tales(유튜브, 영어권 13~30세): 10/28 쉬는 중. 재개 후보 = 얼굴 없는 3D 짧은 실화·what-if(45~75초).
"""

WRITER = """너는 세 채널의 '바깥 흐름 정찰병'이다. 매일 웹을 검색해 ★지금(최근 7~30일) 뜨는 주제와 그 이유를 찾고,
우리 꼴에 바로 쓸 수 있는 소재 후보를 사실·출처와 함께 고른다. 읽는 쪽은 사람보다 ★코드와 다음 분석(맥박)이다.

규칙:
- 근거 없는 '유행'은 쓰지 않는다. hot 마다 실제로 열어 본(검색 결과·fetch) 페이지 링크 1~3개(evidence)와 날짜를 단다.
- 날짜가 오래된 것(30일 넘은 것)은 '지금 뜨는' 근거가 아니다. 상시 인기 주제는 why_now 에 그렇다고 솔직히 적는다.
- 소재 후보(candidates)는 사실(facts)마다 그 사실이 실제로 적힌 페이지 링크(source_url)를 단다. 숫자는 페이지에 있는 그대로.
  확신이 없으면 후보로 넣지 않는다(0개여도 된다). 이미 쓴 소재(사용자 메시지의 used)와 겹치면 넣지 않는다.
- 정책: 실존 인물 명예훼손·가짜 실화·아동 공포·건강 단정·금전 보장·정치 진영은 넣지 않는다. 경쟁 채널 영상을 베끼자는 제안 금지
  (꼴·구조를 참고하는 건 된다).
- 우리 시청자와 안 맞는 흐름(예: 55세 이상 채널에 10대 밈)은 hot 에 넣지 않는다.
- ★검색 순서·예산: 한국 쪽 먼저(검색 약 10번 — 왕별이·인스타 시청자), 그다음 영어 쪽(약 7번), 남은 몇 번은 사실 확인용으로 아낀다.
  검색은 한국어·영어 둘 다. 한국 쪽은 '요즘 유행 쇼츠', '릴스 유행', 운세·띠 관련 화제, 동물·심해·우주 뉴스. 영어 쪽은 viral true story,
  what if, science news. 인스타·틱톡 안쪽은 검색에 잘 안 잡히니 기사·커뮤니티·유튜브에 퍼진 흔적으로 본다.

출력: JSON 객체 하나만(코드펜스·설명 없이):
{"date": "<오늘>",
 "hot": [{"topic": "한 줄", "market": "kr|us", "where": "어디서 뜨나(유튜브 쇼츠·기사·커뮤니티 등)",
          "evidence": [{"title": "...", "url": "https://...", "date": "YYYY-MM-DD 또는 ''"}],
          "why_now": "왜 지금", "fit": ["줄기 키"], "idea": "우리 꼴로 하면 한 줄"}],
 "candidates": [{"line": "줄기 키", "title_idea": "제목 아이디어", "facts": [{"fact": "한국어 한 문장", "source_url": "https://..."}],
                 "careful": "주의(단정 금지 등) 또는 ''"}],
 "note": "오늘 찾기 총평 한두 문장"}
hot 3~8개, candidates 0~6개. 줄기 키는 사용자 메시지의 lines 에 있는 것만.
코드가 검사 오류를 보내면 고쳐서 JSON 전체를 다시 낸다.
"""


def _read(path: str, limit: int | None = None) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            t = f.read()
    except OSError:
        return "(없음)"
    return t if limit is None or len(t) <= limit else t[:limit] + "\n…(뒤 생략)"


def used_topics(root: str = ROOT) -> list[str]:
    """이미 쓴(쓸) 소재 — 카탈로그의 slug·제목 아이디어. 같은 걸 다시 후보로 내지 않게."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "insta", "*catalog*.json")) + [os.path.join(root, "insta", "sci_extra.json"),
                                                                              os.path.join(root, "gumiho", "tales", "shorts_catalog.json")]):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        items = d.get("entries") or d.get("items") or d.get("catalog") or (d if isinstance(d, list) else [])
        for e in items if isinstance(items, list) else []:
            if isinstance(e, dict):
                t = e.get("slug") or e.get("title_idea") or e.get("topic") or e.get("title")
                if t:
                    out.append(str(t)[:60])
    return sorted(set(out))


def runway_text(day: dt.date) -> str:
    try:
        import runway
        rows = runway.collect(day)
        return runway.text(rows, day)
    except Exception as e:  # noqa: BLE001 — 재고표가 없어도 정찰은 돈다
        return f"(재고표 실패: {e})"


def user_message(day: dt.date, radar_dir: str, root: str = ROOT) -> str:
    return "\n".join([
        f"# 오늘(KST) {day.isoformat()}", "", CHANNELS,
        "## lines(후보 줄기 키)\n" + "\n".join(f"- {k}: {v}" for k, v in LINES.items()),
        "\n## 트렌드 레이더(참고 유튜브 채널 숫자 — data/trend-radar report.md)\n" + _read(os.path.join(radar_dir, "report.md"), 15000),
        "\n## 콘텐츠 재고(runway — 바닥나 가는 줄기가 후보 우선)\n" + runway_text(day)[:6000],
        "\n## used(이미 쓴 소재 — 겹치지 않게)\n" + ", ".join(used_topics(root))[:8000],
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


def _url(u) -> bool:
    return isinstance(u, str) and re.match(r"https?://[^\s]+\.[^\s]+", u) is not None


def check(s: dict, day: dt.date) -> list[str]:
    errs = []
    if s.get("date") != day.isoformat():
        errs.append(f"date 는 {day.isoformat()}")
    hot = s.get("hot")
    if not isinstance(hot, list) or not 3 <= len(hot) <= 8:
        errs.append("hot: 3~8개")
        hot = hot if isinstance(hot, list) else []
    for i, h in enumerate(hot, 1):
        if not isinstance(h, dict) or not str(h.get("topic") or "").strip():
            errs.append(f"hot[{i}]: topic 없음")
            continue
        ev = h.get("evidence")
        if not isinstance(ev, list) or not 1 <= len(ev) <= 3 or not all(isinstance(e, dict) and _url(e.get("url")) for e in ev):
            errs.append(f"hot[{i}] '{h['topic'][:20]}': evidence 1~3개, 각 url(https://…) 필수")
        if h.get("market") not in ("kr", "us"):
            errs.append(f"hot[{i}]: market 은 kr|us")
        bad = [f for f in (h.get("fit") or []) if f not in LINES]
        if bad or not h.get("fit"):
            errs.append(f"hot[{i}]: fit 은 lines 키 1개 이상({bad})")
    cands = s.get("candidates")
    if not isinstance(cands, list) or len(cands) > 6:
        errs.append("candidates: 0~6개 목록")
        cands = cands if isinstance(cands, list) else []
    for i, c in enumerate(cands, 1):
        if not isinstance(c, dict) or c.get("line") not in LINES:
            errs.append(f"candidates[{i}]: line 은 lines 키")
            continue
        fs = c.get("facts")
        if not isinstance(fs, list) or not fs or not all(isinstance(f, dict) and str(f.get("fact") or "").strip()
                                                        and _url(f.get("source_url")) for f in fs):
            errs.append(f"candidates[{i}] '{str(c.get('title_idea'))[:20]}': facts 마다 fact + source_url(https://…)")
    return errs


def _usage_add(tok: dict, usage) -> None:
    for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                 ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
        tok[k] += getattr(usage, f, 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        tok["web_search"] += getattr(stu, "web_search_requests", 0) or 0
        tok["web_fetch"] += getattr(stu, "web_fetch_requests", 0) or 0


def ask(client, system: str, messages: list[dict], tok: dict, max_pauses: int = 6) -> str:
    """서버 도구(검색·읽기)가 도는 동안 pause_turn 이 나면 그 턴을 붙여 이어 간다. 마지막 글을 낸다."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCH},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_FETCH}]
    msgs = list(messages)
    for _ in range(max_pauses + 1):
        with client.messages.stream(model=MODEL, max_tokens=32000, system=system, messages=msgs, tools=tools,
                                    extra_body={"output_config": {"effort": EFFORT}}) as st:
            msg = st.get_final_message()
        _usage_add(tok, msg.usage)
        if msg.stop_reason == "pause_turn":
            msgs = msgs + [{"role": "assistant", "content": msg.content}]
            continue
        if msg.stop_reason == "refusal":
            raise RuntimeError("모델이 답을 거절했다(refusal)")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("출력이 max_tokens 에서 잘렸다")
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raise RuntimeError(f"pause_turn 이 {max_pauses}번 넘게 이어졌다")


def write(day: dt.date, radar_dir: str, out_dir: str, client=None, root: str = ROOT) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    messages = [{"role": "user", "content": [{"type": "text", "text": user_message(day, radar_dir, root),
                                              "cache_control": {"type": "ephemeral"}}]}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "web_search": 0, "web_fetch": 0}
    errs: list[str] = []
    history: list[list[str]] = []
    for n in range(1, TRIES + 1):
        text = ask(client, WRITER, messages, tok)
        try:
            s = parse(text)
            errs = check(s, day)
            with open(os.path.join(out_dir, f"{day.isoformat()}.json"), "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=1)
        except (ValueError, KeyError) as e:
            errs = [f"출력을 읽을 수 없다: {e}"]
        history.append(errs)
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"))
        if not errs:
            break
        for x in errs:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "코드가 돌린 검사에서 오류가 났다. 필요하면 더 검색해서 고치고, JSON 전체를 다시 내라.\n"
                                                 + "\n".join(f"- {x}" for x in errs)}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6 \
        + tok["web_search"] * SEARCH_USD
    info = {"date": day.isoformat(), "model": MODEL, "effort": EFFORT, "ok": not errs, "tries": n, "tokens": tok,
            "usd": round(usd, 3), "errors": errs, "history": history}
    with open(os.path.join(out_dir, f"{day.isoformat()}_api.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


def brief(path: str, limit: int = 8000) -> str:
    """맥박(pulse_api)이 읽을 요약 — hot·candidates 의 줄만(링크 포함)."""
    try:
        s = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    lines = [f"(웹 정찰 {s.get('date')}) {s.get('note', '')}"]
    for h in s.get("hot") or []:
        ev = "; ".join(f"{e.get('title', '')[:40]} {e.get('url', '')}" for e in h.get("evidence") or [])
        lines.append(f"- [{h.get('market')}] {h.get('topic')} — {h.get('why_now', '')} → {','.join(h.get('fit') or [])}: {h.get('idea', '')} ({ev})")
    for c in s.get("candidates") or []:
        lines.append(f"- 후보 {c.get('line')}: {c.get('title_idea')} (사실 {len(c.get('facts') or [])}개)")
    return "\n".join(lines)[:limit]


def latest(dir_: str) -> str | None:
    fs = sorted(p for p in glob.glob(os.path.join(dir_, "20??-??-??.json")))
    return fs[-1] if fs else None


def main() -> int:
    ap = argparse.ArgumentParser(description="매일 바깥 흐름 찾기(웹 검색)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--day", required=True)
    w.add_argument("--radar", required=True)
    w.add_argument("--out", required=True)
    a = ap.parse_args()
    info = write(dt.date.fromisoformat(a.day), a.radar, a.out)
    t = info["tokens"]
    print(f"🧭 {info['model']} · 시도 {info['tries']} · 검색 {t['web_search']} · 읽기 {t['web_fetch']} · 출력 {t['output']:,} 토큰"
          f" · 약 {info['usd']}달러")
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
