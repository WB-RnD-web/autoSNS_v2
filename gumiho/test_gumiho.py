#!/usr/bin/env python3
"""Gumiho Games 회귀 테스트 — 네트워크 없이(mock 백엔드).

    python gumiho/test_gumiho.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fox_hunt as F   # noqa: E402
import players as P    # noqa: E402
import run_match as R  # noqa: E402

FAIL = 0
CANDS = P.load_roster(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roster.json"))
ROSTER = P.default_cast(CANDS)          # 점검 없이 앞에서부터 6명(mock 테스트용)
NAMES = [s["name"] for s in ROSTER]


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


print("── 응답 읽기 ──")
ck("평범한 JSON", F.parse_json('{"thought": "x", "vote": "Gemma"}', "vote") == {"thought": "x", "vote": "Gemma"})
ck("코드펜스·머리말", F.parse_json('Sure!\n```json\n{"thought":"t","say":"hi"}\n```', "say")["say"] == "hi")
ck("끝 쉼표", F.parse_json('{"thought":"t","target":"Qwen",}', "target")["target"] == "Qwen")
ck("키가 없으면 None", F.parse_json('{"thought":"t"}', "vote") is None)
ck("두 객체 중 키 있는 쪽", F.parse_json('{"a":1} then {"vote":"Llama"}', "vote")["vote"] == "Llama")
ck("이름 맞추기: gpt → GPT-OSS", F.match_name("gpt", NAMES) == "GPT-OSS")
ck("이름 맞추기: 문장 속 이름", F.match_name("I vote for Gemma.", NAMES) == "Gemma")
ck("이름 맞추기: 없는 이름은 None", F.match_name("Grok", NAMES) is None)
ck("이름 맞추기: 빈 값 None", F.match_name("", NAMES) is None)
ck("단어 자르기", F.clip_words("a " * 80, 60).count("a") == 60)

print("── mock 으로 게임 30판 ──")
bad = []
for seed in range(30):
    m = R.run("fox-hunt", ROSTER, seed, "mock", "2026-10-01")
    roles = list(m["roles"].values())
    ev = m["events"]
    if roles.count("fox") != 1 or roles.count("shaman") != 1:
        bad.append((seed, "역할 수"))
    if m["winner"] not in ("fox", "village"):
        bad.append((seed, "승자"))
    fox = next(n for n, r in m["roles"].items() if r == "fox")
    if m["winner"] == "village" and fox in m["survivors"]:
        bad.append((seed, "마을 승인데 여우 생존"))
    if m["winner"] == "fox" and (fox not in m["survivors"] or len(m["survivors"]) > 2):
        bad.append((seed, "여우 승 조건"))
    d1 = {e["who"] for e in ev if e["type"] == "say" and e["day"] == 1}
    if d1 != set(NAMES):
        bad.append((seed, "첫날 전원 발언"))
    if any(e["type"] in ("vote", "poll") and e["who"] == e["vote"] for e in ev):
        bad.append((seed, "자기 투표"))
    hint = next((e for e in ev if e["type"] == "hint"), None)
    if not hint or fox not in hint["names"] or len(set(hint["names"])) != 3:
        bad.append((seed, "힌트에 여우 포함 3명"))
    if any(e["type"] == "banish" and e["day"] == 1 for e in ev) or any(e["type"] == "vote" and e["day"] == 1 for e in ev):
        bad.append((seed, "첫날은 추방 없음"))
    if sum(1 for e in ev if e["type"] == "poll") != 6:
        bad.append((seed, "첫날 의심 투표 6표"))
    if not any(e["type"] == "night_start" for e in ev):
        bad.append((seed, "최소 밤 1번"))
    if any(e["type"] == "say" and e.get("vague") for e in ev):
        bad.append((seed, "mock 발언이 이름을 안 부름"))
    tail = [e["type"] for e in ev[next(i for i, e in enumerate(ev) if e["type"] == "end"):]]
    if tail[0] != "end" or any(t != "interview" for t in tail[1:]) or len(tail) < 3:
        bad.append((seed, "끝 → 인터뷰만"))
    dead = set()
    for e in ev:
        if e["type"] in ("say", "vote") and e["who"] in dead:
            bad.append((seed, f"탈락자 {e['who']} 발언"))
        if e["type"] == "banish":
            dead.add(e["who"])
        if e["type"] == "kill":
            dead.add(e["target"])
    if m["drama"]["fallback_ratio"] != 0:
        bad.append((seed, "mock 인데 메움"))
ck("30판 규칙 위반 없음", not bad, str(bad[:5]))
a = R.run("fox-hunt", ROSTER, 11, "mock", "2026-10-01")
b = R.run("fox-hunt", ROSTER, 11, "mock", "2026-10-01")
ck("같은 seed → 같은 역할·같은 진행", a["roles"] == b["roles"] and a["events"] == b["events"])
wins = {R.run("fox-hunt", ROSTER, s, "mock", "2026-10-01")["winner"] for s in range(30)}
ck("여우 승·마을 승 둘 다 나온다", wins == {"fox", "village"}, str(wins))

print("── 망가진 모델 ──")
g = F.FoxHunt(ROSTER, {n: P.Mock(n, 0, broken=True) for n in NAMES}, 3)
m = g.run()
ck("JSON 을 못 줘도 게임은 끝난다", m["events"][-1]["type"] == "end")
ck("전부 메웠으면 사용 불가", R.drama_score(m)["usable"] is False)
g = F.FoxHunt(ROSTER, {n: P.Mock(n, 0) for n in NAMES}, 5)
g.check_text("Gemma", "you are a retard")
ck("욕설 필터가 걸면 flags", g.flags and "banned" in g.flags[0])

print("── 영상 비트 · 화면 ──")
import tempfile  # noqa: E402
import episode   # noqa: E402
import render    # noqa: E402
m = R.run("fox-hunt", ROSTER, 7, "mock", "2026-10-01")
bs = episode.build(m)
says = [e for e in m["events"] if e["type"] == "say"]
ck("발언마다 비트 하나", sum(1 for b in bs if b["kind"] == "say") == len(says))
ck("투표·의심 투표마다 비트", sum(1 for b in bs if b["kind"] == "vote") ==
   sum(1 for e in m["events"] if e["type"] in ("vote", "poll")))
ck("시청자에게 역할 공개 뒤로만 FOX 표시", not bs[1]["screen"]["roles_known"] and bs[-1]["screen"]["roles_known"])
ck("첫 비트는 콜드 오픈", bs[0]["kind"] == "hook")
ck("마지막은 진행자 인사", bs[-1]["kind"] == "host" and "comments" in bs[-1]["text"])
render.timeline(bs)
ck("비트 시간이 이어진다", all(abs(a["start"] + a["sec"] - b["start"]) < 1e-6 for a, b in zip(bs, bs[1:])))
ck("속마음이 길면 읽을 시간만큼 머문다",
   all(b["sec"] >= len(b["screen"]["thought"].split()) / render.READ_WPS for b in bs if b["kind"] == "say"))
kit = render.Kit(m)
with tempfile.TemporaryDirectory() as td:
    kinds = {}
    for b in bs:
        kinds.setdefault(b["kind"], b)
    for k, b in kinds.items():
        im = render.frame(kit, b)
        ok = im.size == (1920, 1080)
        if not ok:
            break
    ck(f"비트 종류 {len(kinds)}개 화면 1920×1080", ok)
    render.thumbnail(kit, m, os.path.join(td, "t.jpg"))
    ck("썸네일 생성", os.path.getsize(os.path.join(td, "t.jpg")) > 20000)
md = render.meta(m, "00:00 Cold open")
ck("제목 95자 이내 · 설명에 AI 고지", len(md["title"]) <= 95 and "AI-generated" in md["description"])

print("── roster ──")
ck("시즌 1 출연 6", len(ROSTER) == 6)
ck("목소리 겹침 없음·F3/F4 안 씀", len({s['voice'] for s in ROSTER}) == 6 and not {s['voice'] for s in ROSTER} & {"F3", "F4"})
try:
    P.make_backend({"name": "X", "backend": "openai", "model": "TBD"})
    ck("모델 미정이면 멈춘다", False)
except SystemExit:
    ck("모델 미정이면 멈춘다", True)
os.environ.pop("GUMIHO_ALLOW_PAID", None)
try:
    P.make_backend({"name": "X", "backend": "anthropic", "model": "claude-sonnet-5-5"})
    ck("유료(Claude API)는 기본으로 막힌다", False)
except SystemExit:
    ck("유료(Claude API)는 기본으로 막힌다", True)
os.environ["GUMIHO_OPENAI_BASE"] = "https://openrouter.ai/api/v1"
try:
    P.make_backend({"name": "X", "backend": "openai", "model": "openai/gpt-oss-20b"})
    ck("NVIDIA 무료 주소가 아니면 막힌다", False)
except SystemExit:
    ck("NVIDIA 무료 주소가 아니면 막힌다", True)
os.environ.pop("GUMIHO_OPENAI_BASE", None)
ck("후보 전원이 무료 경로(spark·openai→NVIDIA)", all(s["backend"] in ("spark", "openai") for s in CANDS))

print("── 출연 전 점검 ──")
dead = {"deepseek-ai/deepseek-v4.1-flash", "mistralai/mistral-large-2-instruct", "moonshotai/kimi-k3"}
cast, rep = P.select_cast(CANDS, probe_fn=lambda c: (c["model"] not in dead, "fake"))
names = [c["name"] for c in cast]
ck("떨어진 모델 대신 대기 명단이 채운다", len(cast) == 6 and "DeepSeek" not in names and "GLM" in names, str(names))
ck("같은 이름 대체 모델(Kimi k3 → k2.6)", any(c["name"] == "Kimi" and c["model"] == "moonshotai/kimi-k2.6" for c in cast))
ck("이름 중복 없음", len(set(names)) == 6)
ck("목소리 6개 모두 다름·진행자(F2)와 안 겹침", len({c['voice'] for c in cast}) == 6 and "F2" not in {c['voice'] for c in cast})
ck("점검 기록이 남는다", any(r.startswith("✗ DeepSeek") for r in rep))
cast2, _ = P.select_cast(CANDS, probe_fn=lambda c: (c["backend"] == "spark", "fake"))
ck("6명이 안 되면 모자란 채로 돌려준다(실행은 run_match 가 막음)", len(cast2) == 1)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
