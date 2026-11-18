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
ck("cron 줄이 전부 case 에 있다(옛 시각 줄은 머지 전에 깬 실행용으로 더 있다)", set(crons) <= set(mapped), f"{crons} vs {mapped}")
legacy = {c: w for c, w in mapped.items() if c not in crons}
ck("옛 시각 줄 = 11/18 전 cron 8개 그대로(늦게 도착한 실행도 '어느 트리거인지 모름'으로 안 죽는다)",
   legacy == {"0 21 * * *": "fortune", "40 22 * * *": "name_year", "40 0 * * *": "name_am", "40 1 * * *": "pulli",
              "0 3 * * *": "theme", "40 4 * * *": "name_surname", "40 6 * * *": "name_pm", "40 8 * * *": "wisdom"}, legacy)
mapped = {c: w for c, w in mapped.items() if c in crons}
ck("case 가 고른 이름이 전부 SPECS 에 있다", set(mapped.values()) <= set(T.SPECS), str(set(mapped.values()) - set(T.SPECS)))
ck("SPECS 가 전부 어느 cron 에 걸린다", set(T.SPECS) == set(mapped.values()))
ck("수동 실행 선택지 = SPECS", set(re.search(r"options: \[([^\]]+)\]", wf).group(1).replace(" ", "").split(",")) == set(T.SPECS))
ck("공개 시각은 옛 루틴 시각 그대로(운세 06:00 · 풀이형 10:40 · 테마 12:00 · 말년 지혜 17:40 KST)",
   T.SLOT_KST["fortune"] == "06:00" and T.SLOT_KST["pulli"] == "10:40" and T.SLOT_KST["theme"] == "12:00"
   and T.SLOT_KST["wisdom"] == "17:40" and set(T.SLOT_KST) == set(T.SPECS))


def _lead_min(cron: str, which: str) -> int:
    """cron(UTC) 이 공개 시각(KST)보다 몇 분 먼저 깨우나."""
    mm, hh = (int(x) for x in cron.split()[:2])
    fire = (hh * 60 + mm + 9 * 60) % 1440
    sh, sm = (int(x) for x in T.SLOT_KST[which].split(":"))
    return (sh * 60 + sm - fire) % 1440


leads = {w: _lead_min(c, w) for c, w in mapped.items()}
ck("★11/18 cron 은 공개 시각보다 12시간 먼저 깨운다(정각 편만 7분 늦게 — 11시간 53분)",
   all(T.LEAD_H * 60 - 10 <= m <= T.LEAD_H * 60 for m in leads.values()) and T.LEAD_H == 12, leads)
ck("말년 지혜 표: 05:40 KST 에 깨워 17:40 KST 공개 → routine/wisdom · wisdom_card",
   mapped.get("40 20 * * *") == "wisdom" and T.SPECS["wisdom"][:3] == ("routine/wisdom", "wisdom-trigger", "pipeline/wisdom_card.py"))

import datetime as _dt  # noqa: E402
K = T.KST
at = lambda y, mo, d, h, mi: _dt.datetime(y, mo, d, h, mi, tzinfo=K)  # noqa: E731
ck("target: 제때(전날 18:07) 깨면 다음 날 06:00 운세", T.target("fortune", at(2026, 11, 18, 18, 7)) == at(2026, 11, 19, 6, 0))
ck("target: 10시간 늦게(새벽 04:00) 돌아도 같은 편 — 날짜가 안 밀린다",
   T.target("fortune", at(2026, 11, 19, 4, 0)) == at(2026, 11, 19, 6, 0))
ck("target: 공개 시각을 넘겨(07:30) 돌면 그 편(이미 지남 → 바로 공개)", T.target("fortune", at(2026, 11, 19, 7, 30)) == at(2026, 11, 19, 6, 0))
ck("target: 말년 지혜 05:40 → 그날 17:40 · 21시간 늦은 새벽 02:50 에도 그날(11/17) 편 — 11/17 실제로 하루 밀렸던 경우",
   T.target("wisdom", at(2026, 11, 17, 5, 40)) == at(2026, 11, 17, 17, 40)
   and T.target("wisdom", at(2026, 11, 18, 2, 50)) == at(2026, 11, 17, 17, 40))
ck("target: 테마(12:00) 00:07 에 깨면 그날 12:00", T.target("theme", at(2026, 11, 19, 0, 7)) == at(2026, 11, 19, 12, 0))
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as _td:
    _p = os.path.join(_td, "x.json")
    json.dump({"date": "2026-11-19", "topic": "fortune", "headline": "오늘 띠별 운세"}, open(_p, "w", encoding="utf-8"),
              ensure_ascii=False)
    T.stamp(_p, at(2026, 11, 19, 6, 0))
    _sb = json.load(open(_p, encoding="utf-8"))
ck("stamp: 스토리보드에 publish_at(KST) 을 적고 나머지는 그대로", _sb.get("publish_at") == "2026-11-19T06:00+09:00"
   and _sb["headline"] == "오늘 띠별 운세" and _sb["date"] == "2026-11-19", _sb)
_src = read("tools/wb_trigger.py")
ck("make 가 만든 파일에 공개 시각을 적는다 · 손으로 --date 를 주면 그날 공개 시각",
   "stamp(full, publish_at)" in _src and "when = slot_dt(a.which, dt.date.fromisoformat(a.date))" in _src
   and "when = target(a.which, dt.datetime.now(KST))" in _src)
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
