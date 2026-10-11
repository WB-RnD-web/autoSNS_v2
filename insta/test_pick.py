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
seq = [(d, sl, P.kind_for(d, sl)) for d in (P.START + dt.timedelta(days=k) for k in range(20)) for sl in P.slots_on(d)]
kinds = [k for _, _, k in seq]
ck("편 순서로 이어 붙이면 다섯 편마다 한 바퀴(이어지는 다섯 편은 꼴이 전부 다르다)",
   all(len(set(kinds[i:i + 5])) == 5 for i in range(len(kinds) - 4)))
ck("하루 두 편은 10/13부터 · 10/12까지는 저녁 편 하나", P.slots_on(dt.date(2026, 10, 12)) == ("b",)
   and P.slots_on(dt.date(2026, 10, 13)) == ("a", "b") and P.TWICE_FROM == dt.date(2026, 10, 13))
ck("10/13 낮 그림 고르기 · 저녁 상식 퀴즈 → 10/14 낮 타로 · 저녁 밸런스(로테이션이 끊기지 않는다)",
   [P.kind_for(dt.date(2026, 10, 13), "a"), P.kind_for(dt.date(2026, 10, 13), "b"),
    P.kind_for(dt.date(2026, 10, 14), "a"), P.kind_for(dt.date(2026, 10, 14), "b")] == ["pick", "quiz", "card", "balance"])
ck("꼴만 보면 그날 어느 편인지 하나로 정해진다(slot_of) · 그날 꼴이 아니면 None",
   all(P.slot_of(d, k) == sl for d, sl, k in seq) and P.slot_of(dt.date(2026, 10, 13), "card") is None)
ck("10/12 이전 꼴·회차는 그대로(견본·이미 올린 편이 안 바뀐다)",
   [P.kind_for(P.START + dt.timedelta(days=k)) for k in range(5)] == list(P.FORMATS)
   and [P.series_no(P.START + dt.timedelta(days=k)) for k in range(5)] == [1, 2, 3, 4, 5])
ck("회차는 편마다 하나씩: 10/13 낮 #6 · 저녁 #7 · 10/14 낮 #8",
   (P.series_no(dt.date(2026, 10, 13), "a"), P.series_no(dt.date(2026, 10, 13), "b"), P.series_no(dt.date(2026, 10, 14), "a"))
   == (6, 7, 8))
KST_AT = lambda d, h: dt.datetime(d.year, d.month, d.day, h, 0, tzinfo=P.KST)  # noqa: E731
ck("차례(due_slot): 16시 전 낮 편 · 뒤 저녁 편 · 10/12 낮엔 쓸 차례 아님(None)",
   (P.due_slot(dt.date(2026, 10, 13), KST_AT(dt.date(2026, 10, 13), 11)), P.due_slot(dt.date(2026, 10, 13), KST_AT(dt.date(2026, 10, 13), 19)),
    P.due_slot(dt.date(2026, 10, 12), KST_AT(dt.date(2026, 10, 12), 11)), P.due_slot(dt.date(2026, 10, 12), KST_AT(dt.date(2026, 10, 12), 19)))
   == ("a", "b", None, "b"))
ck("ledger 열쇠: 저녁 편 = 날짜 그대로(쓰레드가 보는 열쇠) · 낮 편 = 날짜+a",
   (P.ledger_key("2026-10-13", "b"), P.ledger_key("2026-10-13", "a")) == ("2026-10-13", "2026-10-13a"))
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
    # 커버(10/9) — 회차 라벨은 넣고, 아래 25%(y 1440~ · 인스타 캡션 자리)는 여전히 비운다
    for k, s in SAMPLES.items():
        a = K.assets(s, tmp, True)
        segs, _ = K.plan(s, {t: 1.0 for t in K.says_of(s)})
        pa = K.Painter(s, a, segs)
        cv = K.cover_of(pa, s)
        fr = pa.frame(0.5 if k != "birth" else 2.0)
        ref = fr if k == "birth" else base                  # birth 는 배경 그림이 깔려서 '라벨이 더한 것 없음'으로 본다
        low = max(abs(p - q) for p, q in zip(cv.crop((0, 1440, K.W, K.H)).resize((54, 24)).tobytes(),
                                               ref.crop((0, 1440, K.W, K.H)).resize((54, 24)).tobytes()))
        band = max(abs(p - q) for p, q in zip(cv.crop((300, 1384, 780, 1432)).tobytes(), fr.crop((300, 1384, 780, 1432)).tobytes()))
        ck(f"{k}: 커버 아래 25%(y 1440~)는 비어 있다 · 회차 라벨은 그 위에", cv.size == (K.W, K.H) and low < 8 and band > 60,
           (low, band))

print("── 캡션 고정 문구·해시태그·회차(10/9) ──")
TAG = re.compile(r"(?<!\S)#(?!\d+(?:\s|$))\S+")              # 숫자만인 '#5' 는 회차 — 해시태그로 세지 않는다
for k, s in SAMPLES.items():
    cap = K.caption_of(s)
    ck(f"{k}: 끝에 열린 질문 한 줄(코드가 붙인다 · 해시태그 앞)", K.ASK[k] in cap and K.ASK[k].endswith("?")
       and cap.index(K.ASK[k]) < cap.index(K.hashtags_of(s)[0]), cap[-160:])
    ck(f"{k}: 캡션에 댓글·보내기·친구 부탁 없음(인스타 2024-06-02: 특정 숫자로 댓글 부탁 = 추천 안 함)",
       not any(w in cap for w in ("댓글", "보내서", "친구한테", "숫자만", "세 글자만")), cap[-160:])
dup = json.loads(json.dumps(SAMPLES["pick"]))
dup["caption"] += "\n몇 번 골랐는지 댓글로 남겨 줘요!\n친구 태그해서 같이 해 봐요"
cap = K.caption_of(dup)
ck("대본 caption 에 댓글·친구 부탁 줄이 있어도 빼고 올린다(경고만)", "댓글" not in cap and "친구" not in cap
   and any("caption" in w for w in K.warns(dup)), cap)
loud = json.loads(json.dumps(SAMPLES["balance"]))
loud["say_outro"] = "고른 거 댓글로 남겨 줘요."
ck("목소리·화면 글에 댓글 부탁이 있으면 check 가 막는다(10/11)", any("부탁" in e for e in K.check(loud)), K.check(loud))
ck("밸런스 끝 화면에 '댓글로' 글자가 없다(코드 고정 문구)", "댓글로 세 글자만" not in open(os.path.join(HERE, "pick_reel.py"), encoding="utf-8").read())
many = dict(SAMPLES["pick"], hashtags=[f"#태그{c}" for c in "가나다라마바사아"])
cap = K.caption_of(many)
ck("해시태그 8개 → 캡션엔 앞 5개만 · check 는 막지 않고 경고만", TAG.findall(cap) == [f"#태그{c}" for c in "가나다라마"]
   and not K.check(many) and any("hashtags" in w for w in K.warns(many)), (TAG.findall(cap), K.check(many), K.warns(many)))
inline = dict(SAMPLES["quiz"], caption="3초 퀴즈 #상식 #두뇌 🧠 다 맞혀 봐요")
ck("캡션 본문 해시태그도 빼서 전체 5개 이하", len(TAG.findall(K.caption_of(inline))) <= 5 and "#두뇌 " not in K.caption_of(inline))
ck("모든 견본 캡션 해시태그 ≤ 5", all(len(TAG.findall(K.caption_of(s))) <= 5 for s in SAMPLES.values()))
ck("회차 번호: 10/8 = #1 · 10/12 = #5 · 10/13 = #6", (P.series_no(dt.date(2026, 10, 8)), P.series_no(dt.date(2026, 10, 12)),
                                                    P.series_no(dt.date(2026, 10, 13))) == (1, 5, 6))
two = dict(SAMPLES["quiz"], date="2026-10-13")             # 10/13 저녁 편 = 상식 퀴즈 → #7
ck("10/13부터 캡션 회차는 편 순서대로(10/13 저녁 퀴즈 = #7)", K.caption_of(two).startswith("오늘의 골라보기 #7 · "), K.caption_of(two)[:30])
firsts = {k: K.caption_of(s).splitlines()[0] for k, s in SAMPLES.items()}
ck("캡션 첫 줄 앞에 '오늘의 골라보기 #N'(날짜대로)", firsts["pick"].startswith("오늘의 골라보기 #1 · 끌리는")
   and firsts["birth"].startswith("오늘의 골라보기 #5 · ") and firsts["quiz"].startswith("오늘의 골라보기 #2 · "), firsts)
again = dict(SAMPLES["quiz"], caption="오늘의 골라보기 #9 · " + SAMPLES["quiz"]["caption"])
ck("작가가 회차를 써도 한 번만(날짜 번호로)", K.caption_of(again).count("오늘의 골라보기") == 1
   and K.caption_of(again).startswith("오늘의 골라보기 #2 · 3초"))
ck("날짜가 시작일(10/8) 전이면 막는다(#0 방지)", any("date" in e for e in K.check(dict(SAMPLES["pick"], date="2026-10-07"))))

print("── 편성 정보·게시 막기 ──")
with tempfile.TemporaryDirectory() as tmp:
    d = dt.date(2026, 10, 9)
    ni = P.next_info(d, tmp, now=KST_AT(d, 19))
    ck("next: 오늘 꼴·견본·키워드 · 아직 안 씀", ni["kind"] == "quiz" and ni["exemplar"].endswith("pick_quiz.json")
       and ni["keywords"] and not ni["already_written"] and ni["due"] and ni["slot"] == "b")
    json.dump(SAMPLES["pick"], open(os.path.join(tmp, "2026-10-08_pick_door.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(SAMPLES["quiz"], open(os.path.join(tmp, "2026-10-09_quiz_body-animal.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ni = P.next_info(d, tmp, now=KST_AT(d, 19))
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

print("── 하루 두 편 — 쓰기·고르기·게시 막기(10/13~) ──")
with tempfile.TemporaryDirectory() as tmp:
    d2 = dt.date(2026, 10, 13)
    ni = P.next_info(d2, tmp, now=KST_AT(d2, 11))
    ck("next 11시: 낮 편 · 그림 고르기 · #6 · 아직 안 씀", (ni["due"], ni["slot"], ni["kind"], ni["series_no"], ni["already_written"])
       == (True, "a", "pick", 6, False), ni)
    ni = P.next_info(dt.date(2026, 10, 12), tmp, now=KST_AT(dt.date(2026, 10, 12), 11))
    ck("next 10/12 11시: 쓸 차례 아님(due false) — 낮 편은 10/13부터", ni["due"] is False and "why" in ni, ni)
    pa = os.path.join(tmp, "2026-10-13_pick_door.json")
    json.dump(dict(SAMPLES["pick"], date="2026-10-13"), open(pa, "w", encoding="utf-8"), ensure_ascii=False)
    ck("낮 대본을 쓴 뒤 next 11시 = already_written · 19시 = 저녁 편(퀴즈) 아직", P.next_info(d2, tmp, now=KST_AT(d2, 11))["already_written"]
       and not P.next_info(d2, tmp, now=KST_AT(d2, 19))["already_written"] and P.next_info(d2, tmp, now=KST_AT(d2, 19))["kind"] == "quiz")
    ck("저녁 편 recent 에 오늘 낮 편이 들어간다(같은 날 주제 겹침 방지)",
       [r["slug"] for r in P.next_info(d2, tmp, now=KST_AT(d2, 19))["recent"]][:1] == ["door"])
    ck("targets: 낮 대본만 있으면 낮 대본", P.latest_target(d2, tmp) == pa)
    pb = os.path.join(tmp, "2026-10-13_quiz_body-animal.json")
    json.dump(dict(SAMPLES["quiz"], date="2026-10-13"), open(pb, "w", encoding="utf-8"), ensure_ascii=False)
    ck("targets: 저녁 대본이 오면 저녁 대본(낮 것을 다시 집지 않는다)", P.latest_target(d2, tmp) == pb)
    vid = os.path.join(tmp, "v.mp4")
    open(vid, "wb").write(b"0")
    meta = {"video": vid, "seconds": 22.0}
    sa, sb = dict(SAMPLES["pick"], date="2026-10-13"), dict(SAMPLES["quiz"], date="2026-10-13")
    ck("게시: 낮·저녁 편 둘 다 그날 꼴이라 막힘 없음", P.blockers(sa, meta, {}, d2) == [] and P.blockers(sb, meta, {}, d2) == [])
    ck("게시: 낮 편을 올린 뒤에도 저녁 편은 올린다(편마다 한 번)", P.blockers(sb, meta, {"2026-10-13a": {"media_id": "A"}}, d2) == [])
    ck("게시: 낮 편 두 번은 막는다", any("이미" in b for b in P.blockers(sa, meta, {"2026-10-13a": {"media_id": "A"}}, d2)))
    ck("게시: 저녁 편 두 번은 막는다(날짜 열쇠)", any("이미" in b for b in P.blockers(sb, meta, {"2026-10-13": {"media_id": "B"}}, d2)))
    ck("게시: 그날 편에 없는 꼴(10/13 타로)은 막는다", any("꼴" in b for b in P.blockers(dict(SAMPLES["card"], date="2026-10-13"), meta, {}, d2)))

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
ck("쓰는 법: 회차·열린 질문·해시태그 5개는 코드가 붙인다 · 작가는 같은 말 쓰지 않기 · 부탁 금지",
   "코드가 붙이는 것" in wr and "오늘의 골라보기 #N" in wr and "5개까지" in wr and "쓰지 않아요" in wr
   and all(K.ASK[k] in wr for k in K.ASK) and "부탁 금지" in wr)
ck("쓰는 법: 하루 두 편 · due false 면 끝 · 한 번에 한 편", "하루 두 편" in wr and "due: false" in wr and "한 번에 한 편" in wr)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
