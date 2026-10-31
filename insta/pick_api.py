#!/usr/bin/env python3
"""인스타 대본을 루틴 대신 Claude API 로 쓴다(2026-10-31) — 지금은 루틴과 나란히 비교(data/insta-api).

왜: 인스타 대본 루틴(하루 두 번 · Sonnet)은 구독의 ★주간 한도를 쓴다(바닥나면 업로드 루틴도 같이 멈춘다).
  Max 계정에 따로 붙는 월 200달러 API 크레딧으로 옮긴다(결제 수단 없음 · 넘으면 거절될 뿐 돈 안 나감).
  쓰는 규칙은 이미 공개 레포에 있다: 편·꼴·항목은 pick_plan.next_info, 쓰는 법은 next 의 writing 파일, 모양은 exemplar,
  검사는 pick_reel.check — 루틴이 하던 그대로를 API 한 번(+검사 오류 때 다시)으로 한다.
흐름: next_info(그날·그 편) → 오늘 날짜 견본(insta/samples)이 있으면 그대로(사람이 본 견본 · API 안 씀)
  → 없으면 system = 작가 규칙 + writing 파일, user = next 출력 + exemplar → 대본 JSON → pick_reel.check
  → 오류가 나면 오류를 붙여 다시(최대 3번). 실제 토큰·달러·시도별 오류를 api.json 에 남긴다.
비용(추정): Opus 5.5 입력 약 1.5만·출력 약 1만 토큰 → 편당 0.25달러 안팎.

    python insta/pick_api.py write --date 2026-10-31 --slot b --scripts output/insta_pick --out <폴더>
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402

MODEL = os.environ.get("INSTA_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("INSTA_EFFORT", "high")
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력, 출력, 캐시 읽기(달러/100만)
TRIES = 3
SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

WRITER = """너는 한국 인스타 계정(@zerocrew.studio, 이름 '소름과학 | 심해·우주·생존')의 대본 작가다. 보는 사람은 한국의 10~20대다.
계정 목표는 인스타 팔로워를 키우는 것 하나다. 유튜브 홍보는 하지 않는다(링크·채널 이름·'유튜브에서' 같은 말 금지).

규칙(어기면 검사에서 떨어진다):
- 편(slot)·꼴(kind)·항목(src_n·entry)은 코드가 정했다(사용자 메시지의 next). 바꾸지 않는다.
- 너는 웹을 못 본다. 사실·숫자는 next 가 준 것(sci: entry.facts · 병맛: entry.facts)만 쓴다. 지어내지 않는다. careful 을 지킨다.
  sources 는 entry 것을 그대로 옮기고, src_n 은 next 값 그대로.
- 병맛: entry 만 쓴다. src_n(= bm_n)·sources·topic(B 는 animal·animal_ko 도)을 entry 에서 그대로. 재미는 정색한 말투와 마지막 한 줄
  (펀치라인)에서 나온다. 내레이션에 'ㅋㅋ'·'킹받' 같은 말을 쓰지 않는다.
- 골라보기: recent 와 겹치지 않는 새 주제. 퀴즈는 사실만. bench.seen 은 비워 두고 bench.format 만.
- 그림 묘사(img)는 영어로. 실존 인물·브랜드·글자가 없는 장면. 병맛 B 는 같은 동물 묘사를 모든 장면에 복사하고 사람은 그리지 않는다.
- 화면 글과 목소리에 댓글·남겨 줘·보내 줘·공유해·태그해·저장해·팔로우 같은 부탁을 쓰지 않는다. 금지어와 문구 규칙은 아래 writing 을 따른다.
- 아래 '쓰는 법(writing)'이 이 꼴의 자세한 규칙이다. exemplar(견본)와 ★같은 모양(필드·타입)으로 쓴다. 견본 문구를 베끼지 않는다.

출력: 대본 JSON 객체 하나만(코드펜스·설명 없이). slug 는 영어 소문자·숫자·하이픈.
코드가 검사(pick_reel check)에서 오류를 보내면 고쳐서 ★JSON 전체를 다시 낸다.
"""


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return "(없음)"


def writings(info: dict, root: str = ROOT) -> list[str]:
    w = info.get("writing") or []
    return [w] if isinstance(w, str) else list(w)


def system_prompt(info: dict, root: str = ROOT) -> str:
    parts = [WRITER]
    for w in writings(info, root):
        parts.append(f"\n---\n## 쓰는 법(writing) — {w}\n\n" + _read(os.path.join(root, w)))
    return "\n".join(parts)


def user_message(info: dict, root: str = ROOT) -> str:
    ex = info.get("exemplar") or ""
    return "\n".join([f"# 오늘(KST) {info['date']} · {info.get('slot_label') or info.get('slot')} · 꼴 {info.get('kind')}",
                      "\n## next(코드가 정한 편·꼴·항목·최근 대본)\n```json\n" + json.dumps(info, ensure_ascii=False, indent=1) + "\n```",
                      f"\n## exemplar(견본 — 이 모양으로) {ex}\n```json\n" + _read(os.path.join(root, ex)) + "\n```"])


def same_day_sample(info: dict, root: str = ROOT) -> str | None:
    """insta/samples 에 오늘 날짜·같은 꼴 견본이 있으면 그 경로 — 사람이 이미 본 견본이라 새로 쓰지 않는다(루틴 2번 규칙)."""
    for p in sorted(glob.glob(os.path.join(root, "insta", "samples", "*.json"))):
        try:
            s = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(s, dict) and s.get("date") == info["date"] and s.get("kind") == info.get("kind"):
            return p
    return None


def parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("JSON 객체가 없다")
    s = json.loads(t[a:b + 1])
    if not isinstance(s, dict):
        raise ValueError("최상위가 객체가 아니다")
    return s


def file_for(info: dict, s: dict) -> str:
    slug = str(s.get("slug") or "")
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"slug '{slug}' — 영어 소문자·숫자·하이픈만")
    return info["file"].replace("<slug>", slug)


def default_checker(s: dict) -> list[str]:
    import pick_reel
    return pick_reel.check(s)


def ask(client, system: str, messages: list[dict]):
    with client.messages.stream(model=MODEL, max_tokens=24000, system=system, messages=messages,
                                extra_body={"output_config": {"effort": EFFORT}}) as st:
        msg = st.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), msg.usage


def write(info: dict, out_dir: str, client=None, checker=None, root: str = ROOT) -> dict:
    """대본 하나를 out_dir 에 쓴다(파일 이름 = next 의 file). 결과 요약(api.json 내용)을 낸다."""
    os.makedirs(out_dir, exist_ok=True)
    base = {"date": info["date"], "slot": info.get("slot"), "kind": info.get("kind"), "model": MODEL}
    sample = same_day_sample(info, root)
    if sample:
        s = json.load(open(sample, encoding="utf-8"))
        name = os.path.basename(file_for(info, s))
        shutil.copy(sample, os.path.join(out_dir, name))
        return {**base, "ok": True, "file": name, "sample": os.path.relpath(sample, root).replace("\\", "/"), "tries": 0,
                "usd": 0.0, "errors": [], "history": []}
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    checker = checker or default_checker
    system = system_prompt(info, root)
    messages = [{"role": "user", "content": [{"type": "text", "text": user_message(info, root),
                                              "cache_control": {"type": "ephemeral"}}]}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    errs: list[str] = []
    history: list[list[str]] = []
    name = None
    for n in range(1, TRIES + 1):
        text, usage = ask(client, system, messages)
        for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            tok[k] += getattr(usage, f, 0) or 0
        try:
            s = parse(text)
            name = os.path.basename(file_for(info, s))
            errs = list(checker(s))
            for k_ in ("date", "kind"):
                if s.get(k_) != info.get(k_):
                    errs.append(f"{k_} 가 next 와 다르다: {s.get(k_)!r} ≠ {info.get(k_)!r}")
            if info.get("src_n") is not None and s.get("src_n") != info.get("src_n"):
                errs.append(f"src_n 이 next 와 다르다: {s.get('src_n')!r} ≠ {info.get('src_n')!r}")
            with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
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
                     {"role": "user", "content": "코드가 돌린 검사(pick_reel check)에서 오류가 났다. 고쳐서 JSON 전체를 다시 내라.\n"
                                                 + "\n".join(f"- {x}" for x in errs)}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6
    return {**base, "ok": not errs, "file": name, "sample": None, "effort": EFFORT, "tries": n, "tokens": tok,
            "usd": round(usd, 3), "errors": errs, "history": history}


def target_slot(d: dt.date, scripts: str) -> tuple[str | None, str | None]:
    """오늘 대본 중 가장 늦은 편(워크플로가 막 렌더한 것)의 (편, 파일) — 비교 기간에 같은 편을 API 로 다시 쓴다."""
    p = P.latest_target(d, scripts)
    return (P.slot_of(d, P._kind_of_file(p)), p) if p else (None, None)


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 대본을 API 로 쓴다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--date", required=True)
    w.add_argument("--slot", help="비우면 오늘 대본 중 가장 늦은 편(비교 기간 — 그 편 파일은 빼고 다시 쓴다)")
    w.add_argument("--scripts", default=P.SCRIPTS, help="지난 대본 폴더(recent·already_written 판단)")
    w.add_argument("--out", required=True)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date)
    slot, routine_file = (a.slot, None) if a.slot else target_slot(d, a.scripts)
    if not slot:
        print("오늘 대본이 없다 — 쓸 편을 모른다")
        return 0
    if routine_file:                                   # 루틴 판은 비교용으로 옆에 두고, 판단(already_written·recent)에서는 뺀다
        os.makedirs(a.out, exist_ok=True)
        shutil.copy(routine_file, os.path.join(a.out, "routine_" + os.path.basename(routine_file)))
        os.remove(routine_file)
    info = P.next_info(d, a.scripts, slot=slot)
    if not info.get("due"):
        print(f"쓸 차례 아님: {info.get('why')}")
        return 0
    res = write(info, a.out)
    with open(os.path.join(a.out, f"api_{slot}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    t = res.get("tokens") or {}
    print(f"🧾 {res['kind']} · {res.get('file')} · 시도 {res['tries']} · 출력 {t.get('output', 0):,} 토큰 · 약 {res['usd']}달러"
          + (f" · 견본 {res['sample']}" if res.get("sample") else ""))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
