#!/usr/bin/env python3
"""인스타 '오늘의 골라보기'(pick_reel·pick_plan) 오프라인 테스트 — 편성·검사·시간표·화면·게시 막기·워크플로."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402
import render_reel as R  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


SAMPLES = {k: json.load(open(os.path.join(HERE, "samples", f"{v}.json"), encoding="utf-8")) for k, v in P.EXEMPLAR.items()}

print("── 편성(날짜로 돈다) ──")
week = [P.kind_for(P.START + dt.timedelta(days=k)) for k in range(6)]
ck("10/8 그림 고르기 → 퀴즈 → 타로 → 밸런스 → 태어난 달 → 다시 그림", week == ["pick", "quiz", "card", "balance", "birth", "pick"], week)
ck("같은 꼴은 5일에 한 번", all(P.kind_for(P.START + dt.timedelta(days=k)) != P.kind_for(P.START + dt.timedelta(days=k + j))
                              for k in range(10) for j in range(1, 5)))
ck("견본 날짜의 꼴 = 견본 꼴(첫 닷새 그대로 올릴 수 있다)",
   all(P.kind_for(dt.date.fromisoformat(s["date"])) == s["kind"] for s in SAMPLES.values()),
   {k: (s["date"], P.kind_for(dt.date.fromisoformat(s["date"]))) for k, s in SAMPLES.items()})

print("── 대본 검사 ──")
ck("견본 다섯 개 모두 통과", all(not K.check(s) for s in SAMPLES.values()), {k: K.check(s) for k, s in SAMPLES.items()})
bad = json.loads(json.dumps(SAMPLES["quiz"]))
bad["rounds"][0]["say_a"] = "정답은 이거예요."
ck("퀴즈: 정답 낱말이 say_a 에 없으면 막는다", any("say_a" in e for e in K.check(bad)))
bad = json.loads(json.dumps(SAMPLES["pick"]))
bad["caption"] += " 팔로우하면 결과 보내 드려요"
ck("금지어(팔로우 유도) 막는다", any("금지어" in e for e in K.check(bad)))
bad = json.loads(json.dumps(SAMPLES["birth"]))
bad["cells"] = bad["cells"][:11]
ck("태어난 달 표: 12칸이 아니면 막는다", any("12칸" in e for e in K.check(bad)))
bad = json.loads(json.dumps(SAMPLES["card"]))
del bad["options"][0]["reveal_img"]
ck("타로: 앞면 그림이 없으면 막는다", any("reveal_img" in e for e in K.check(bad)))
bad = json.loads(json.dumps(SAMPLES["pick"]))
bad.pop("bench")
ck("어떤 바이럴 꼴을 빌렸는지(bench.format)가 없으면 막는다", any("bench" in e for e in K.check(bad)))

print("── 시간표 ──")
for k, s in SAMPLES.items():
    says = K.says_of(s)
    dur = {t: 0.11 * len(t) for t in says}            # 대략 한 글자 0.11초
    segs, ticks = K.plan(s, dur)
    total = segs[-1]["start"] + segs[-1]["dur"]
    gaps = all(abs(a["start"] + a["dur"] - b["start"]) < 1e-6 for a, b in zip(segs, segs[1:]))
    said = {sg.get("say") for sg in segs} | {sg.get("say2") for sg in segs}
    ck(f"{k}: 8~40초 · 장면이 빈틈없이 이어진다 · 말이 전부 나온다", 8 <= total <= 40 and gaps and set(says) <= said,
       (round(total, 1), gaps, set(says) - said))

print("── 화면(가짜 그림) ──")
with tempfile.TemporaryDirectory() as tmp:
    for k, s in SAMPLES.items():
        a = K.assets(s, tmp, True)
        says = K.says_of(s)
        segs, _ = K.plan(s, {t: 0.11 * len(t) for t in says})
        pa = K.Painter(s, a, segs)
        times = [0.2] + [sg["start"] + sg["dur"] * f for sg in segs for f in (0.1, 0.6, 0.97)]
        ok = all(pa.frame(t).size == (K.W, K.H) for t in times)
        ck(f"{k}: 모든 장면이 1080×1920 으로 그려진다({len(times)}장)", ok)
    # 아래 25%(인스타 캡션 자리)는 비어 있다 — 배경 그라데이션 말고 그린 것이 없다
    s = SAMPLES["pick"]
    a = K.assets(s, tmp, True)
    segs, _ = K.plan(s, {t: 1.0 for t in K.says_of(s)})
    pa = K.Painter(s, a, segs)
    base = K.bg().convert("RGB")
    fr = pa.frame(segs[1]["start"] + 0.5)
    diff = max(abs(p - q) for p, q in zip(fr.crop((0, 1560, K.W, K.H)).resize((54, 18)).tobytes(),
                                           base.crop((0, 1560, K.W, K.H)).resize((54, 18)).tobytes()))
    ck("결과 화면 아래 25%(y 1560~)는 비운다(인스타 캡션·버튼 자리)", diff < 8, diff)
    cap = K.caption_of(SAMPLES["quiz"])
    ck("캡션에 정답·해시태그가 들어간다(멈춰서 다시 보는 사람용)", "1번 문제 정답: 3개" in cap and "#상식퀴즈" in cap)

print("── 편성 정보·게시 막기 ──")
with tempfile.TemporaryDirectory() as tmp:
    d = dt.date(2026, 10, 9)
    ni = P.next_info(d, tmp)
    ck("next: 오늘 꼴·견본·키워드 · 아직 안 씀", ni["kind"] == "quiz" and ni["exemplar"].endswith("pick_quiz.json")
       and ni["keywords"] and not ni["already_written"])
    json.dump(SAMPLES["pick"], open(os.path.join(tmp, "2026-10-08_pick_door.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(SAMPLES["quiz"], open(os.path.join(tmp, "2026-10-09_quiz_body-animal.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ni = P.next_info(d, tmp)
    ck("next: 오늘 파일이 있으면 already_written · recent 에는 지난 것만", ni["already_written"]
       and [r["slug"] for r in ni["recent"]] == ["door"])
    ck("targets: 오늘 대본 하나만", len(P.scripts_on(d, tmp)) == 1)
    s = SAMPLES["quiz"]
    vid = os.path.join(tmp, "v.mp4")
    open(vid, "wb").write(b"0")
    meta = {"video": vid, "seconds": 22.0}
    ck("게시: 오늘·맞는 꼴·영상 있음 → 막힘 없음", P.blockers(s, meta, {}, d) == [])
    ck("게시: 날짜가 오늘이 아니면 막는다", P.blockers(s, meta, {}, d + dt.timedelta(days=1)))
    ck("게시: 같은 날 두 번 안 올린다", any("이미" in b for b in P.blockers(s, meta, {"2026-10-09": {"media_id": "1"}}, d)))
    wrong = dict(s, kind="pick")
    ck("게시: 꼴이 날짜와 다르면 막는다", any("꼴" in b for b in P.blockers(wrong, meta, {}, d)))
    ck("게시: 영상이 없으면 막는다", P.blockers(s, None, {}, d))
    os.environ.pop("INSTA_PICK_PUBLISH", None)
    rd = os.path.join(tmp, "r")
    os.makedirs(rd)
    json.dump(dict(meta, caption="x", cover=""), open(os.path.join(rd, "2026-10-09_quiz_body-animal_meta.json"), "w", encoding="utf-8"))
    sp = os.path.join(tmp, "2026-10-09_quiz_body-animal.json")
    ck("게시: INSTA_PICK_PUBLISH=1 이 아니면 dry-run(올리지 않고 0)", P.post(sp, rd, os.path.join(rd, "led.json"), d) == 0
       and not os.path.exists(os.path.join(rd, "led.json")))

print("── 워크플로·문서 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "insta-pick.yml"), encoding="utf-8").read()
ck("코드는 main · 대본은 routine/insta_pick · contents: read", "ref: main" in wf and "routine/insta_pick" in wf
   and re.search(r"(?m)^\s*contents:\s*read", wf) and not re.search(r"(?m)^\s*contents:\s*write", wf))
ck("검사 → 렌더 → 게시 순서 · 게시는 push 때만 · 막기 변수", wf.index("pick_reel.py check") < wf.index("pick_reel.py render")
   < wf.index("pick_plan.py post") and "github.event_name == 'push'" in wf and "INSTA_PICK_PUBLISH" in wf)
name = re.search(r"(?m)^name:\s*(.+)$", wf).group(1).strip()
rt = open(os.path.join(ROOT, ".github", "workflows", "retry-no-runner.yml"), encoding="utf-8").read()
ck("실행기 못 잡으면 다시 돌리기 목록에 있다(retry-no-runner)", f'"{name}"' in rt)
wr = open(os.path.join(HERE, "PICK_WRITING.md"), encoding="utf-8").read()
ck("쓰는 법: 유튜브 홍보 금지 · 꼴은 코드가 · 사실만(퀴즈) · 베끼지 않기", "유튜브" in wr and "홍보" in wr
   and "코드가 정해요" in wr and "사실만" in wr and "새로 만들어요" in wr)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
