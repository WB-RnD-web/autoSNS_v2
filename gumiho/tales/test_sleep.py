#!/usr/bin/env python3
"""수면판(sleep.py) 회귀 테스트 — 네트워크 없이(가짜 그림·가짜 목소리). 작은 가짜 편 두 개로 끝까지 렌더한다.

    python gumiho/tales/test_sleep.py
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_tale as R  # noqa: E402
import sleep as S        # noqa: E402
import tales as T        # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


SPEC_PATH = S.specs()[0]
SPEC = T.load(SPEC_PATH)
EP1 = T.load(os.path.join(HERE, "scripts", "001_gumiho.json"))

print("── 수면판 spec 검사 ──")
for p in S.specs():
    ck(f"{os.path.basename(p)} 통과", not S.check(T.load(p), p), str(S.check(T.load(p), p)[:3]))
bad = copy.deepcopy(SPEC)
bad["tales"][0]["link"][0]["say"] = "Before you sleep, tell me in the comments which tale you liked."
ck("연결 내레이션에 '댓글' → 막힌다", any("comments" in e for e in S.check(bad)))
bad = copy.deepcopy(SPEC)
bad["tales"][1]["link"] = []
ck("연결 내레이션 없는 편 → 막힌다(이어 붙이기만은 재사용 콘텐츠)", any("link" in e for e in S.check(bad)))
bad = copy.deepcopy(SPEC)
bad["publish_at"] = bad["render_from"] + "T12:00:00Z"
ck("공개가 렌더 시작과 이틀이 안 되면 막힌다", any("이틀" in e for e in S.check(bad)))
bad = copy.deepcopy(SPEC)
bad["tales"].append(copy.deepcopy(bad["tales"][0]))
ck("같은 편 두 번 → 막힌다", any("두 번" in e for e in S.check(bad)))
bad = copy.deepcopy(SPEC)
bad["tail"]["min"] = 45
ck("끝 비 화면 20분 초과 → 막힌다", any("tail" in e for e in S.check(bad)))
ck("파일 이름이 id_slug 와 다르면 막힌다", any("파일 이름" in e for e in S.check(SPEC, "/x/002_other.json")))

print("── 편 자르기(1화 실제 대본) ──")
kept, dropped = S.trim(EP1)
ck("TALE 카드부터 시작", str(kept[0].get("card", "")).startswith("TALE"), str(kept[0])[:80])
ck("댓글·다음 편·지난 편 말이 남지 않는다", not any(S.CTA.search(x.get("say", "")) for x in kept))
ck("장 카드는 TALE 하나만", sum(1 for x in kept if x.get("card")) == 1)
ck("화면 주석·불티 없음", not any(x.get("note") for x in kept) and not any(x.get("fx") == "embers" for x in kept))
ck(f"이야기 본문은 남는다({len(kept)}장면 ≥ {S.KEEP_MIN})", len(kept) >= S.KEEP_MIN)
ck("구미의 '정답' 맺음말은 남긴다", any("collecting a thousand" in x.get("say", "") for x in kept))
mid = copy.deepcopy(EP1)
k = next(i for i, x in enumerate(mid["scenes"]) if x.get("say") and i > 25)
mid["scenes"][k]["say"] = "Last time I told you about this. Anyway."
kept2, _ = S.trim(mid)
ck("이야기 가운데 '지난 편' 말은 그 줄만 뺀다(뒤를 통째로 자르지 않는다)", len(kept2) == len(kept) - 1)

print("── 언제 만드나·언제 공개하나 ──")
rf = dt.date.fromisoformat(SPEC["render_from"])
ok, why = S.due(SPEC, rf - dt.timedelta(days=1), {})
ck("render_from 전에는 만들지 않는다", not ok, why)
real_tp = S.tale_path
S.tale_path = lambda name: os.path.join(HERE, "scripts", "001_gumiho.json")      # 모든 편이 있는 척
ok, why = S.due(SPEC, rf, {})
ck("render_from 이후·대본이 다 있으면 만든다", ok, why)
ok, why = S.due(SPEC, rf, {S.stem(SPEC): {"long": "https://youtu.be/X"}})
ck("ledger 에 올린 기록이 있으면 다시 만들지 않는다", not ok, why)
S.tale_path = lambda name: None if name.startswith("004") else os.path.join(HERE, "scripts", "001_gumiho.json")
ok, why = S.due(SPEC, rf, {})
ck("대본이 하나라도 없으면 기다린다", not ok and "004" in why, why)
S.tale_path = real_tp
now = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
ck("private 이면 예약 없음", S.publish_time(SPEC, "private", now) is None)
ck("scheduled 면 spec 시각", S.publish_time(SPEC, "scheduled", now) == SPEC["publish_at"])
late = S.publish_time(SPEC, "scheduled", dt.datetime(2026, 10, 27, 3, 20, tzinfo=dt.timezone.utc))
ck("늦었으면 지금+2시간 정각", late == "2026-10-27T05:00:00Z", str(late))

print("── 메타데이터 ──")
shots = [{"start": 0.0, "chapter": "Settle in"}, {"start": 50.0, "chapter": "The Gumiho"},
         {"start": 55.0, "chapter": "Too Close"}, {"start": 900.0, "chapter": "The Fox Sister"},
         {"start": 3000.0, "chapter": "Goodnight"}, {"start": 3100.0, "chapter": "Rain only"}]
chap = S.chapters(shots)
ck("챕터 00:00 부터·10초 안 붙은 항목은 뺀다", chap.splitlines()[0].startswith("00:00") and "Too Close" not in chap, chap)
md = S.meta(SPEC, [EP1], chap, 62.4, [("The Gumiho Legend", "https://youtu.be/RhKwrpHRLeY")])
ck("설명에 표식(중복 업로드 판정용)", S.marker(SPEC) in md["description"])
ck("설명에 본편 링크·출처·AI 고지", "youtu.be/RhKwrpHRLeY" in md["description"] and "Sources" in md["description"]
   and "AI-generated" in md["description"])
ck("'about an hour'", "about an hour" in md["description"])
ck("제목 70자 이내·태그 480자 이내", len(md["title"]) <= 70 and len(",".join(md["tags"])) <= 480)

print("── 소리 ──")
import numpy as np  # noqa: E402
amb = S.Ambience(3)
n = R.SR * 2
whole = amb.block(0, 2 * n)
ck("빗소리 블록을 이어도 이음새가 없다", np.allclose(whole, np.concatenate([amb.block(0, n), amb.block(n, n)]), atol=1e-4))
ck("앰비언스 크기 정상(rms 0.3~3)", 0.3 < float(np.sqrt(np.mean(whole ** 2))) < 3)

print("── 가짜 편 두 개로 끝까지 렌더 ──")


def fake_tale(i: int) -> dict:
    sc = [{"img": f"cold open {i}", "say": "A cold open line that teases the ending.", "fx": "fog"},
          {"gumi": "front", "say": f"Hello, dear human. This is Tale Number {i}."},
          {"card": f"TALE {900 + i}", "sub": f"Fake Tale {i}"}]
    sc += [{"img": f"tale {i} scene {k}", "say": f"Scene {k} of the fake tale, told slowly.", "fx": "embers",
            "note": "a note"} for k in range(4)]
    sc += [{"card": "I", "sub": "Middle"}, {"img": f"tale {i} end", "say": "And that was the end of it."},
           {"gumi": "wink", "say": "Tell me in the comments what you would do."},
           {"img": f"tale {i} next", "say": "Next time, another tale."}]
    return {"id": 900 + i, "slug": f"fake-{i}", "title": f"Fake Tale {i}", "sources": [f"Source {i}"], "scenes": sc}


with tempfile.TemporaryDirectory() as td:
    tales = {f"{900 + i}_fake-{i}": fake_tale(i) for i in (1, 2)}
    for k, s in tales.items():
        with open(os.path.join(td, k + ".json"), "w", encoding="utf-8") as f:
            json.dump(s, f)
    spec = copy.deepcopy(SPEC)
    spec.update({"id": 99, "slug": "test-night"})
    spec["tales"] = [dict(SPEC["tales"][0], file="901_fake-1"), dict(SPEC["tales"][1], file="902_fake-2")]
    spec["tail"]["min"] = 0.1
    sp = os.path.join(td, "099_test-night.json")
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    S.tale_path = lambda name: os.path.join(td, f"{name}.json") if name in tales else None
    S.KEEP_MIN, keep_min = 3, S.KEEP_MIN
    out, work = os.path.join(td, "out"), os.path.join(td, "work")
    # procs=1: spawn 자식은 이 테스트 파일을 다시 실행한다(__main__ 가드가 없어서) — 한 프로세스로 그린다
    res = S.render(sp, out, work, mock=True, fps=4, procs=1)
    S.KEEP_MIN = keep_min
    ck("영상·썸네일·자막·한눈에 보기·메타", all(os.path.exists(res[k]) for k in ("video", "thumb", "srt", "sheet")))
    ck("썸네일 1280×720", R.Image.open(res["thumb"]).size == (1280, 720))
    with open(os.path.join(out, "sleep_099_test-night_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    ck("mock 표시(올리지 않게)", rm["mock"] is True)
    ck("편마다 4+1장면(TALE 카드+본문 4, 맺음 1)만 남았다",
       all(r["kept"] == 6 for r in rm["trim"].values()), str({k: v["kept"] for k, v in rm["trim"].items()}))
    chap_lines = rm["chapters"].splitlines()
    ck("챕터: 인사·편 둘·잘 자·비", [ln.split(" ", 1)[1] for ln in chap_lines]
       == ["Settle in", "The Gumiho", "The Fox Sister", "Goodnight", "Rain only"], str(chap_lines))
    r = subprocess.run([R.ffmpeg(), "-hide_banner", "-i", res["video"]], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else -1
    ck("영상 길이 = 계획 길이(±1.5초)", abs(dur - rm["minutes"] * 60) < 1.5, f"{dur} vs {rm['minutes'] * 60}")
    ck("소리 트랙 있음", "Audio:" in r.stderr)
    srt = open(res["srt"], encoding="utf-8").read()
    ck("자막에 새 연결 내레이션", "Gumi" in srt and "comments" not in srt)
    ck("mock 은 업로드 거부", S.upload(sp, out, os.path.join(td, "led.json"), "scheduled") == 2)
    S.tale_path = real_tp

    shots_ = [{"i": 0, "kind": "img", "prep": res["thumb"], "move": "in", "fx": "none", "start": 0.0, "dur": 10.0}]
    a = np.asarray(R.Painter({"shots": shots_, "total": 10.0}).frame(5.0)).mean()
    b = np.asarray(R.Painter({"shots": shots_, "total": 10.0, "dim": S.DIM}).frame(5.0)).mean()
    ck("수면판 화면은 본편보다 어둡다(dim)", b < a * 0.9, f"{b:.1f} vs {a:.1f}")

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
