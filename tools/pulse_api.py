#!/usr/bin/env python3
"""채널 맥박 — 해석(fill.json)을 루틴 대신 Claude API 한 번으로 쓴다(2026-10-31).

왜: 분석 루틴(Opus, 매일 07:30)은 구독의 ★주간 한도를 쓴다. 한도가 바닥나면 업로드 루틴까지 같이 멈춘다.
  Max 계정에 따로 붙는 월 200달러 API 크레딧(결제 수단 없음 · 조직 월 한도 200달러 → 넘으면 멈출 뿐 돈이 안 나간다)으로 옮긴다.
  숫자는 그대로 tools/pulse.py build 가 내고, 여기서는 해석만 받는다. 규칙은 tools/PULSE.md 그대로, 검사기도 같다(pulse.py check).
흐름: PULSE.md + 오늘 pulse.json + 레이더 report.md + 지난 3일 fill.json·플래그 + 최근 커밋 → Claude → fill.json
  (+ pr_edits → pr.patch). 검사 오류가 나면 그 오류를 붙여 다시 묻는다(최대 3번).
PR: 지난 맥박 PR 4개(#154·#159·#164·#167)가 전부 tools/pulse_experiments.json 만 고쳤다 → 고칠 수 있는 파일을 EDITABLE 로
  묶고, 파일을 통째로 보여 준 뒤 '정확한 문자열 바꾸기'만 받는다. 테스트는 여기서 돌린다(루틴이 하던 '직접 돌려 통과').
비용: 10/31 첫 시험 = 자료 약 7.4만 토큰 × 2번(검사 오류로 한 번 더) + 출력 1.9만 → 0.97달러. 그 뒤 자료를 캐시에 올려
  다시 묻는 값을 줄였다. 실제 토큰·달러·시도별 오류는 <날짜>/api.json 에 남는다.

    python tools/pulse_api.py write --day 2026-10-31 --dir output/pulse --radar /tmp/radar
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pulse as PU  # noqa: E402

MODEL = os.environ.get("PULSE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("PULSE_EFFORT", "high")
# 달러 / 100만 토큰(입력, 출력, 캐시 읽기) — 캐시 쓰기는 입력의 1.25배
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}
EDITABLE = ("tools/pulse_experiments.json", "tools/pulse_formats.json")
TRIES = 3
PREV_DAYS = 3

API_NOTE = """

---

## 이번 실행 방식(API) — 위 안내서보다 이 절이 앞선다

너는 도구 없이 한 번에 답한다. 필요한 자료(오늘 pulse.json, 레이더 report.md, 지난 며칠 fill.json·플래그, 실험·형식 파일,
최근 커밋)는 사용자 메시지에 전부 붙어 있다. 거기 없는 숫자는 쓰지 않는다.

출력은 ★JSON 객체 하나만(코드펜스·설명 없이):
{"fill": <fill.json 객체 — 위 '모양' 그대로>, "pr_edits": null}

PR 을 낼 때만(위 PR 조건을 전부 만족할 때) fill.pr 를 채우고 pr_edits 에 바꿀 곳을 적는다:
"pr_edits": [{"path": "tools/pulse_experiments.json", "old": "<파일에 정확히 한 번 나오는 원문>", "new": "<바꿀 글>"}]
- path 는 tools/pulse_experiments.json · tools/pulse_formats.json 만. 그 밖의 변경은 actions 에 local 로 적는다.
- old 는 붙어 있는 파일 내용을 글자 그대로(들여쓰기 포함) 옮긴다. 테스트·pr.patch 만들기는 코드가 한다.
- 코드가 돌린 검사에서 오류가 나면 오류 목록을 보내 줄 테니, 고쳐서 ★JSON 전체를 다시 낸다.
"""


def _read(path: str, limit: int | None = None) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            t = f.read()
    except OSError:
        return "(없음)"
    return t if limit is None or len(t) <= limit else t[:limit] + "\n…(뒤 생략)"


def _git_log(root: str) -> str:
    try:
        return subprocess.run(["git", "-C", root, "log", "--since=4 days ago", "--format=%h %ad %s", "--date=short"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip() or "(없음)"
    except (OSError, subprocess.SubprocessError):
        return "(git log 실패)"


def system_prompt(root: str = ROOT) -> str:
    return _read(os.path.join(root, "tools", "PULSE.md")) + API_NOTE


def user_message(day: str, out_root: str, radar_dir: str, root: str = ROOT) -> str:
    day_dir = os.path.join(out_root, day)
    P = PU.load(os.path.join(day_dir, "pulse.json")) or {}
    parts = [f"# 오늘(KST) {day}",
             f"레이더 데이터 시각 {P.get('radar_at', '?')} · {P.get('radar_age_h', '?')}시간 전"
             + (" — ★오래된 데이터(DATA_STALE)" if (P.get("radar_age_h") or 0) > 12 else ""),
             "\n## 오늘 pulse.json\n```json\n" + json.dumps(P, ensure_ascii=False) + "\n```",
             "\n## 레이더 report.md(data/trend-radar)\n" + _read(os.path.join(radar_dir, "report.md"), 30000)]
    for d in PU.prev_dirs(out_root, day, PREV_DAYS):
        F = PU.load(os.path.join(d, "fill.json"))
        Q = PU.load(os.path.join(d, "pulse.json")) or {}
        parts.append(f"\n## {os.path.basename(d)} — 그날 fill.json · 플래그")
        parts.append("```json\n" + json.dumps({"fill": F, "flags": Q.get("flags"), "pred_scored": Q.get("pred_scored")},
                                              ensure_ascii=False) + "\n```")
    for p in EDITABLE:
        parts.append(f"\n## {p}(PR 로 고칠 수 있는 파일 — 원문 그대로)\n```\n" + _read(os.path.join(root, p)) + "\n```")
    parts.append("\n## 최근 4일 커밋(main)\n" + _git_log(root))
    return "\n".join(parts)


def parse(text: str) -> dict:
    """모델이 펜스나 말을 붙여도 바깥 JSON 객체 하나만 꺼낸다."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("JSON 객체가 없다")
    out = json.loads(t[a:b + 1])
    if not isinstance(out, dict) or not isinstance(out.get("fill"), dict):
        raise ValueError('최상위가 {"fill": {...}, "pr_edits": ...} 모양이 아니다')
    return out


def apply_edits(edits, root: str = ROOT) -> tuple[list[str], list[str]]:
    """정확한 문자열 바꾸기. (바꾼 파일, 오류). 오류가 하나라도 있으면 아무것도 바꾸지 않는다."""
    errs, new_text = [], {}
    if not isinstance(edits, list) or not edits:
        return [], ["pr_edits 가 비었다(PR 을 낼 거면 바꿀 곳을 적고, 아니면 fill.pr 을 null 로)"]
    for i, e in enumerate(edits, 1):
        p = str((e or {}).get("path", "")).replace("\\", "/")
        if p not in EDITABLE:
            errs.append(f"pr_edits[{i}]: {p or '(경로 없음)'} 는 고칠 수 없다 — {', '.join(EDITABLE)} 만")
            continue
        old, new = (e or {}).get("old"), (e or {}).get("new")
        if not isinstance(old, str) or not old or not isinstance(new, str):
            errs.append(f"pr_edits[{i}]: old·new 가 글자가 아니다")
            continue
        cur = new_text.get(p)
        if cur is None:
            cur = _read(os.path.join(root, p))
        n = cur.count(old)
        if n != 1:
            errs.append(f"pr_edits[{i}]: old 가 {p} 에 {n}번 나온다(정확히 한 번이어야 한다 — 원문 그대로 옮길 것)")
            continue
        new_text[p] = cur.replace(old, new)
    if errs:
        return [], errs
    for p, t in new_text.items():
        with open(os.path.join(root, p), "w", encoding="utf-8", newline="\n") as f:
            f.write(t)
    return sorted(new_text), []


def make_patch(edits, day_dir: str, root: str = ROOT) -> list[str]:
    """main 작업 트리에 바꾸기를 얹고 → 관련 테스트 → git diff 를 pr.patch 로 → 되돌린다. 오류 목록을 낸다."""
    files, errs = apply_edits(edits, root)
    if errs:
        return errs
    try:
        for p in files:
            json.loads(_read(os.path.join(root, p)))       # 고친 JSON 이 깨지지 않았나
        for t in ("tools/test_pulse.py", "tools/test_runway.py"):
            if os.path.exists(os.path.join(root, t)):
                r = subprocess.run([sys.executable, t], cwd=root, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=600)
                if r.returncode:
                    return [f"PR 을 얹으면 {t} 가 실패한다: " + (r.stdout + r.stderr)[-1500:]]
        diff = subprocess.run(["git", "-C", root, "diff", "--", *files], capture_output=True, text=True,
                              encoding="utf-8").stdout
        with open(os.path.join(day_dir, "pr.patch"), "w", encoding="utf-8", newline="\n") as f:
            f.write(diff)
        return []
    except ValueError as e:
        return [f"PR 을 얹은 JSON 이 깨진다: {e}"]
    finally:
        subprocess.run(["git", "-C", root, "checkout", "--", *files], capture_output=True)


def ask(client, system: str, messages: list[dict]):
    """스트리밍으로 받는다(긴 출력에서 타임아웃 방지). (글, usage)."""
    with client.messages.stream(model=MODEL, max_tokens=32000, system=system, messages=messages,
                                extra_body={"output_config": {"effort": EFFORT}}) as s:
        msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    return text, msg.usage


def write(day: str, out_root: str, radar_dir: str, client=None, checker=None, root: str = ROOT) -> dict:
    """fill.json(+pr.patch)을 쓰고 검사 통과까지 다시 묻는다. 결과 요약(api.json 내용)을 낸다."""
    day_dir = os.path.join(out_root, day)
    if not os.path.exists(os.path.join(day_dir, "pulse.json")):
        raise SystemExit(f"{day_dir}/pulse.json 이 없다 — 먼저 pulse.py build")
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    checker = checker or PU.check
    system = system_prompt(root)
    # 자료 덩어리(7만 토큰 안팎)를 캐시에 올린다 — 검사 오류로 다시 물을 때 같은 자료를 1/20 값에 다시 읽는다
    messages = [{"role": "user", "content": [{"type": "text", "text": user_message(day, out_root, radar_dir, root),
                                              "cache_control": {"type": "ephemeral"}}]}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    errs: list[str] = []
    history: list[list[str]] = []
    for n in range(1, TRIES + 1):
        text, usage = ask(client, system, messages)
        for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            tok[k] += getattr(usage, f, 0) or 0
        patch = os.path.join(day_dir, "pr.patch")
        if os.path.exists(patch):
            os.remove(patch)
        try:
            out = parse(text)
            with open(os.path.join(day_dir, "fill.json"), "w", encoding="utf-8") as f:
                json.dump(out["fill"], f, ensure_ascii=False, indent=1)
            errs = make_patch(out.get("pr_edits"), day_dir, root) if out["fill"].get("pr") else []
            errs = errs or checker(day_dir)
        except (ValueError, KeyError) as e:
            errs = [f"출력을 읽을 수 없다: {e}"]
        history.append(errs)
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"))
        if not errs:
            break
        for x in errs:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "코드가 돌린 검사에서 오류가 났다. 고쳐서 JSON 전체를 다시 내라.\n"
                                                 + "\n".join(f"- {x}" for x in errs)}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6
    # history = 시도마다 검사 오류(다시 묻게 만든 이유 — 자주 나는 오류는 API_NOTE 에 미리 적어 시도를 줄인다)
    info = {"model": MODEL, "effort": EFFORT, "tries": n, "ok": not errs, "tokens": tok, "usd": round(usd, 3),
            "errors": errs, "history": history}
    with open(os.path.join(day_dir, "api.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="채널 맥박 해석을 API 로 쓴다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--day", required=True)
    w.add_argument("--dir", default=os.path.join("output", "pulse"))
    w.add_argument("--radar", required=True)
    a = ap.parse_args()
    info = write(a.day, a.dir, a.radar)
    t = info["tokens"]
    print(f"🧾 {info['model']} · 시도 {info['tries']} · 입력 {t['input']:,}(캐시 쓰기 {t['cache_write']:,} · 읽기 {t['cache_read']:,})"
          f" · 출력 {t['output']:,} 토큰 · 약 {info['usd']}달러")
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
