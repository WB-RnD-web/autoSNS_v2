"""2027 정미년 깊이 보기 롱폼 대본 — 루틴 대신 Claude API 로 쓴다(.github/workflows/lf27-api.yml).

    python tools/lf27_api.py write --env <파일> [--date ISO]   # next → (견본 복사 | API 로 쓰기) → check → FILE 로 복사

옛 루틴(trig_01HtELyY…)이 하던 일 그대로: pipeline/longform_2027.py next 가 편·사실·뼈대를 주고, 글쓰기 안내
(pipeline/LONGFORM_2027_WRITING.md)와 견본(E01)을 읽어 쓰고, longform_2027.py check 가 통과할 때까지 고친다.
push 는 워크플로가 한다(GH_PAT — fortune-lf27.yml 이 깨어나야 한다). 루틴은 구독 주간 한도를 썼고 여기는 API 크레딧을 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.environ.get("LF27_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("LF27_EFFORT", "high")
TRIES = 4
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}
WRITING = os.path.join(ROOT, "pipeline", "LONGFORM_2027_WRITING.md")
SAMPLE = os.path.join(ROOT, "docs", "samples", "longform_2027_E01.json")

# 옛 루틴 프롬프트의 규칙 — 그대로 옮겼다
RULES = """너는 왕별이(55세 이상 어르신 시청자) 롱폼 '2027 정미년 깊이 보기' 대본 작가다.
- 아래 '글쓰기 안내'를 전부 따르고, 사용자 메시지(next 출력)가 준 각도·질문 씨앗·사실·뼈대로 대본 JSON 하나를 쓴다.
- 사실(신살·삼재·출생연도·달 범위)은 next 가 준 그대로 쓴다. 바꾸거나 지어내지 않는다.
- 견본(E01)은 형식과 말투만 참고한다. 견본 문장을 옮기지 않는다.
- 어르신께 드리는 조언형 말투로 쓴다. 살·삼재는 '꼭 지킬 3가지'·'잘 넘기는 법' 같은 조언 틀에서만 쓴다. 겁주는 말을 쓰지 않는다.
- 실제로 누가 물은 것처럼 쓰지 않는다(질문은 '이런 걸 많이 궁금해하세요' 같은 틀). 지어낸 통계·사연·실존 인물 금지.
- 출력은 ```json 블록 하나에 대본 JSON 전체만. 다른 말은 쓰지 않는다."""


def run_next(date: str | None = None) -> str:
    args = [sys.executable, "pipeline/longform_2027.py", "next"] + (["--date", date] if date else [])
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit("next 실패:\n" + r.stdout + r.stderr)
    return r.stdout


def parse_next(text: str) -> dict:
    """머리의 KEY=VALUE 줄들(빈 줄 전까지)."""
    out = {}
    for line in text.splitlines():
        if not line.strip():
            break
        m = re.match(r"([A-Z_]+)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def check(path: str, date: str | None = None) -> list[str]:
    args = [sys.executable, "pipeline/longform_2027.py", "check", path] + (["--date", date] if date else [])
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        return []
    lines = [ln.strip() for ln in (r.stdout + r.stderr).splitlines() if ln.strip()]
    errs = [ln for ln in lines if ln.startswith(("❌", "-", "•")) or "오류" in ln]
    return errs or lines[-20:]


def extract_json(text: str) -> dict:
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def system_prompt() -> str:
    with open(WRITING, encoding="utf-8") as f:
        writing = f.read()
    with open(SAMPLE, encoding="utf-8") as f:
        sample = f.read()
    return f"{RULES}\n\n# 글쓰기 안내(pipeline/LONGFORM_2027_WRITING.md)\n\n{writing}\n\n# 견본 E01(형식·말투만 — 문장은 옮기지 않는다)\n\n{sample}"


def ask(client, system: str, messages: list[dict]):
    with client.messages.stream(model=MODEL, max_tokens=32000, system=system, messages=messages,
                                extra_body={"output_config": {"effort": EFFORT}}) as s:
        msg = s.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("모델이 답을 거절했다(refusal)")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("출력이 max_tokens 에서 잘렸다")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), msg.usage


def write_script(next_text: str, write_to: str, client=None, checker=check) -> dict:
    """API 로 쓰고 check 가 통과할 때까지 다시 묻는다(최대 TRIES). {ok, tries, usd, errors}."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    system = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": next_text + "\n\n위 편의 대본 JSON 전체를 ```json 블록 하나로 내라."}]
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    errs: list[str] = []
    n = 0
    for n in range(1, TRIES + 1):
        text, usage = ask(client, system, messages)
        for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                     ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
            tok[k] += getattr(usage, f, 0) or 0
        try:
            data = extract_json(text)
            os.makedirs(os.path.dirname(write_to), exist_ok=True)
            with open(write_to, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            errs = checker(write_to)
        except (ValueError, KeyError) as e:
            errs = [f"JSON 을 읽을 수 없다: {e}"]
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"), flush=True)
        if not errs:
            break
        for x in errs[:30]:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "코드 검사(longform_2027.py check)에서 오류가 났다. 고쳐서 대본 JSON 전체를 다시 내라.\n"
                                                 + "\n".join(f"- {x}" for x in errs[:30])}]
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6
    return {"ok": not errs, "tries": n, "usd": round(usd, 3), "tokens": tok, "errors": errs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["write"])
    ap.add_argument("--env", required=True, help="워크플로가 읽을 EPISODE·FILE·MORE")
    ap.add_argument("--date", default=None, help="기준 시각(KST) — 시험용")
    a = ap.parse_args()
    nt = run_next(a.date)
    head = parse_next(nt)
    res = {"EPISODE": head.get("EPISODE", "NONE"), "FILE": "", "MORE": head.get("MORE", "0")}
    if res["EPISODE"] == "NONE":
        print(nt.strip().splitlines()[-1])
    else:
        write_to, file_ = head["WRITE_TO"], head["FILE"].replace("\\", "/")
        ready = head.get("READY", "").split()[0] if head.get("READY") else ""
        if ready:
            shutil.copyfile(os.path.join(ROOT, ready), write_to)
            errs = check(write_to, a.date)
            info = {"ok": not errs, "tries": 0, "usd": 0, "errors": errs}
        else:
            info = write_script(nt, write_to, checker=lambda p: check(p, a.date))
        print(f"🧾 {res['EPISODE']} · {MODEL} · 시도 {info['tries']} · 약 {info['usd']}달러")
        if not info["ok"]:
            print("::error::검사를 끝내 통과하지 못했다 — push 하지 않는다\n  " + "\n  ".join(info["errors"][:20]))
            return 1
        os.makedirs(os.path.join(ROOT, os.path.dirname(file_)), exist_ok=True)
        shutil.copyfile(write_to, os.path.join(ROOT, file_))
        res["FILE"] = file_
    with open(a.env, "w", encoding="utf-8") as f:
        for k, v in res.items():
            f.write(f"{k}={shlex.quote(v)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
