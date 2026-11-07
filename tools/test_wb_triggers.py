"""루틴 → Actions 옮기기(wb-triggers.yml · lf27-api.yml) 오프라인 검사. 네트워크·API 없이 돈다.

    python tools/test_wb_triggers.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lf27_api as L  # noqa: E402
import wb_trigger as T  # noqa: E402

fails = 0


def ck(name: str, ok: bool, extra: str = ""):
    global fails
    print(("✅ " if ok else "❌ ") + name + (f" — {extra}" if extra and not ok else ""))
    fails += 0 if ok else 1


def read(p: str) -> str:
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


# ── wb-triggers.yml ↔ wb_trigger.py ──
wf = read(".github/workflows/wb-triggers.yml")
crons = re.findall(r'- cron: "([^"]+)"', wf)
mapped = dict(re.findall(r'"([0-9* ,]+)"\)\s+W=(\w+)', wf))
ck("cron 7줄이 전부 case 에 있다", sorted(crons) == sorted(mapped), f"{crons} vs {mapped}")
ck("case 가 고른 이름이 전부 SPECS 에 있다", set(mapped.values()) <= set(T.SPECS), str(set(mapped.values()) - set(T.SPECS)))
ck("SPECS 7개가 전부 어느 cron 에 걸린다", set(T.SPECS) == set(mapped.values()))
ck("수동 실행 선택지 = SPECS", set(re.search(r"options: \[([^\]]+)\]", wf).group(1).replace(" ", "").split(",")) == set(T.SPECS))
ck("옛 루틴 시각 그대로(운세 21:00 · 풀이형 01:40 · 테마 03:00 UTC)",
   mapped.get("0 21 * * *") == "fortune" and mapped.get("40 1 * * *") == "pulli" and mapped.get("0 3 * * *") == "theme")
ck("push 는 GH_PAT(GITHUB_TOKEN 이면 쇼츠가 안 깨어난다)", "token: ${{ secrets.GH_PAT" in wf)
ck("강제 push 없음", not re.search(r"push\s+(-f|--force)", wf))
ck("이미 원격에 있으면 다시 push 하지 않는다", "git cat-file -e" in wf)
ck("브랜치는 전부 routine/*", all(s[0].startswith("routine/") for s in T.SPECS.values()))

# ── lf27-api.yml ──
lw = read(".github/workflows/lf27-api.yml")
ck("롱폼: 옛 루틴 시각(월·수·토 01:07 UTC)", '"7 1 * * 1,3,6"' in lw)
ck("롱폼: GH_PAT 로 push · 강제 push 없음", "secrets.GH_PAT" in lw and not re.search(r"push\s+(-f|--force)", lw))
ck("롱폼: 끄기 변수 LF27_API", "vars.LF27_API" in lw)

# ── lf27_api: next 머리 읽기 · JSON 꺼내기 · 다시 묻기 ──
head = L.parse_next("NOW=2026-11-08 10:07 KST\nEPISODE=E05\nFILE=output/fortune_lf27/E05_2026-11-11.json\n"
                    "WRITE_TO=/tmp/x/E05.json\nMORE=0\n\n── 이 편 ──\nKEY=무시")
ck("next 머리만 읽는다", head.get("EPISODE") == "E05" and "KEY" not in head and head["MORE"] == "0")
ck("```json 블록에서 꺼낸다", L.extract_json('앞말\n```json\n{"a": 1}\n```\n뒷말') == {"a": 1})
ck("블록이 없어도 { … } 를 꺼낸다", L.extract_json('{"b": [1, 2]}') == {"b": [1, 2]})


class _U:
    input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens = 1000, 0, 0, 500


class _B:
    type = "text"

    def __init__(self, t):
        self.text = t


class _M:
    stop_reason = "end_turn"
    usage = _U()

    def __init__(self, t):
        self.content = [_B(t)]


class _S:
    def __init__(self, t):
        self.t = t

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return _M(self.t)


class FakeClient:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    @property
    def messages(self):
        return self

    def stream(self, **kw):
        self.calls.append(kw)
        return _S(self.answers.pop(0))


sample = read("docs/samples/longform_2027_E01.json")
d = tempfile.mkdtemp()
seen = []


def checker(p):
    seen.append(p)
    return ["장 3 say 가 짧다"] if len(seen) == 1 else []


fc = FakeClient(["```json\n" + sample + "\n```", "```json\n" + sample + "\n```"])
info = L.write_script("EPISODE=E05\n", os.path.join(d, "E05.json"), client=fc, checker=checker)
ck("검사 오류면 오류를 붙여 다시 묻고, 통과하면 멈춘다", info["ok"] and info["tries"] == 2 and len(fc.calls) == 2)
ck("다시 물을 때 오류 문구가 들어간다", "장 3 say 가 짧다" in json.dumps(fc.calls[1]["messages"], ensure_ascii=False))
ck("글쓰기 안내·견본이 system 에 들어간다(캐시)", "LONGFORM_2027_WRITING" in fc.calls[0]["system"][0]["text"]
   and fc.calls[0]["system"][0].get("cache_control"))
ck("쓴 파일이 JSON", json.load(open(os.path.join(d, "E05.json"), encoding="utf-8")) == json.loads(sample))

print(f"\n{'❌ 실패 ' + str(fails) + '개' if fails else '✅ 전부 통과'}")
sys.exit(1 if fails else 0)
