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
kinds = [k for _, _, k in seq if k != P.SCI]              # sci 편(10/15~)은 골라보기 로테이션에서 빠진다
ck("편 순서로 이어 붙이면 다섯 편마다 한 바퀴(이어지는 골라보기 다섯 편은 꼴이 전부 다르다)",
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
   and all(K.ASK[k] in wr for k in P.FORMATS) and "부탁 금지" in wr)
ck("쓰는 법: 하루 두 편 · due false 면 끝 · 한 번에 한 편", "하루 두 편" in wr and "due: false" in wr and "한 번에 한 편" in wr)

print("── sci 편성(10/15~10/28 · 하루 한 편 sci, 저녁·낮 번갈아) ──")
D = lambda m, d: dt.date(2026, m, d)  # noqa: E731
WIN = [P.SCI_FROM + dt.timedelta(days=k) for k in range(14)]
ck("기간 10/15~10/28(양끝 포함 14일) · 항목 14개", (P.SCI_FROM, P.SCI_TO) == (D(10, 15), D(10, 28))
   and (P.SCI_TO - P.SCI_FROM).days + 1 == 14 == len(P.SCI_ORDER))
ck("sci 편은 10/15 저녁(b) → 10/16 낮(a) → 10/17 저녁 … 번갈아", [P.sci_slot(d) for d in WIN] == ["b", "a"] * 7,
   [P.sci_slot(d) for d in WIN])
ck("기간 밖(10/14·10/29)엔 sci 없음", P.sci_slot(D(10, 14)) is None and P.sci_slot(D(10, 29)) is None
   and P.SCI not in [P.kind_for(d, sl) for d in (D(10, 14), D(10, 29)) for sl in P.slots_on(d)])
ck("기간 안 날마다 한 편은 sci · 한 편은 골라보기(꼴이 다르다)",
   all(sorted(P.kind_for(d, sl) == P.SCI for sl in P.slots_on(d)) == [False, True] for d in WIN))
TABLE = {  # 날짜: (낮 a, 저녁 b) — 보고·판정용으로 못 박는다
    D(10, 15): ("birth", "sci"), D(10, 16): ("sci", "pick"), D(10, 17): ("quiz", "sci"), D(10, 18): ("sci", "card"),
    D(10, 19): ("balance", "sci"), D(10, 20): ("sci", "birth"), D(10, 21): ("pick", "sci"), D(10, 22): ("sci", "quiz"),
    D(10, 23): ("card", "sci"), D(10, 24): ("sci", "balance"), D(10, 25): ("birth", "sci"), D(10, 26): ("sci", "pick"),
    D(10, 27): ("quiz", "sci"), D(10, 28): ("sci", "card"), D(10, 29): ("balance", "birth")}
got_t = {d: (P.kind_for(d, "a"), P.kind_for(d, "b")) for d in TABLE}
ck("10/15~10/29 편성표 그대로", got_t == TABLE, {d.isoformat(): v for d, v in got_t.items() if v != TABLE[d]})
PAST = [(D(10, 8), "b", "pick", 1), (D(10, 9), "b", "quiz", 2), (D(10, 10), "b", "card", 3), (D(10, 11), "b", "balance", 4),
        (D(10, 12), "b", "birth", 5), (D(10, 13), "a", "pick", 6), (D(10, 13), "b", "quiz", 7), (D(10, 14), "a", "card", 8),
        (D(10, 14), "b", "balance", 9)]
ck("10/14 까지 꼴·회차는 그대로(이미 올린 편이 안 바뀐다)",
   [(d, sl, P.kind_for(d, sl), P.series_no(d, sl)) for d, sl, _, _ in PAST] == PAST)
allp = [(d, sl, P.kind_for(d, sl)) for d in (P.START + dt.timedelta(days=k) for k in range(40)) for sl in P.slots_on(d)]
picks = [(d, sl, k) for d, sl, k in allp if k != P.SCI]
ck("골라보기 로테이션은 sci 를 건너뛰고 한 꼴씩 그대로(겹침·빠짐 없음 · 11/16 까지)",
   [k for _, _, k in picks] == [P.FORMATS[i % 5] for i in range(len(picks))])
ck("회차(series_no)는 골라보기 편만 센다 — 1, 2, 3 … 빈틈 없이 · sci 는 None",
   [P.series_no(d, sl) for d, sl, _ in picks] == list(range(1, len(picks) + 1))
   and all(P.series_no(d, sl) is None for d, sl, k in allp if k == P.SCI))
ck("10/15 낮 태어난 달 #10 · 10/16 저녁 그림 고르기 #11 · 10/29 낮 밸런스 #24 · 저녁 #25",
   (P.series_no(D(10, 15), "a"), P.series_no(D(10, 16), "b"), P.series_no(D(10, 29), "a"), P.series_no(D(10, 29), "b"))
   == (10, 11, 24, 25))
ck("10/29 부터 다시 하루 골라보기 두 편", [P.kind_for(D(10, 30), sl) for sl in P.slots_on(D(10, 30))] == ["pick", "quiz"])
ck("slot_of 는 기간 안에서도 하나로 정해진다(sci ↔ sci 편 · 골라보기 꼴 ↔ 그 편)",
   all(P.slot_of(d, k) == sl for d, sl, k in allp) and all(P.slot_of(d, P.SCI) == P.sci_slot(d) for d in WIN))
try:
    P.post_index(D(10, 15), "b")
    raised = False
except ValueError:
    raised = True
ck("sci 편엔 골라보기 순번이 없다(post_index ValueError)", raised)
ck("sci 내용 순서 = SCI_ORDER(10/15 마리아나 101 · 10/16 심해 생물 201 · 10/28 남극 106)",
   [P.sci_n(d) for d in WIN] == list(P.SCI_ORDER) and P.sci_n(D(10, 14)) is None
   and P.SCI_ORDER == (101, 201, 107, 102, 203, 104, 202, 105, 206, 109, 205, 103, 207, 106))
ents = [P.sci_entry(n) for n in P.SCI_ORDER]
ck("SCI_ORDER 항목이 전부 shorts_catalog 에 있고 survival·compare · facts·sources 가 있다",
   all(e and e["format"] in ("survival", "compare") and e.get("facts") and e.get("sources") for e in ents)
   and [e["format"] for e in ents][:3] == ["survival", "compare", "survival"])
with tempfile.TemporaryDirectory() as tmp:
    ni = P.next_info(D(10, 15), tmp, now=KST_AT(D(10, 15), 19))
    ck("next 10/15 19시: sci · 저녁 편 · 101 마리아나 · 회차 없음 · SCI_WRITING · 견본 sci_mariana",
       (ni["kind"], ni["slot"], ni["src_n"], ni["format"], ni["series_no"], ni["writing"], ni["exemplar"], ni["file"])
       == ("sci", "b", 101, "survival", None, "insta/SCI_WRITING.md", "insta/samples/sci_mariana.json",
           "output/insta_pick/2026-10-15_sci_<slug>.json"), {k: ni.get(k) for k in ("kind", "slot", "src_n", "file")})
    e = ni["entry"]
    ck("next: catalog 항목(n·format·title_idea·facts·sources·look·careful·beat_ideas) 그대로",
       e["n"] == 101 and e["facts"] == P.sci_entry(101)["facts"] and e["sources"] == P.sci_entry(101)["sources"]
       and all(k in e for k in ("format", "title_idea", "look", "careful", "beat_ideas")))
    ni = P.next_info(D(10, 16), tmp, now=KST_AT(D(10, 16), 11))
    ck("next 10/16 11시: sci · 낮 편 · 201 compare · items_idea·unit 있음", (ni["kind"], ni["slot"], ni["src_n"], ni["format"])
       == ("sci", "a", 201, "compare") and "items_idea" in ni["entry"] and ni["entry"].get("unit") == "m", ni.get("src_n"))
    ni = P.next_info(D(10, 15), tmp, now=KST_AT(D(10, 15), 11))
    ck("next 10/15 11시: 낮 편은 골라보기(태어난 달 #10 · PICK_WRITING)", (ni["kind"], ni["slot"], ni["series_no"], ni["writing"])
       == ("birth", "a", 10, "insta/PICK_WRITING.md"), ni.get("kind"))
    SCI_S = json.load(open(os.path.join(HERE, "samples", "sci_mariana.json"), encoding="utf-8"))
    d16 = D(10, 16)
    pa_ = os.path.join(tmp, "2026-10-16_sci_deep-sea-size.json")
    json.dump(dict(SCI_S, date="2026-10-16", src_n=201), open(pa_, "w", encoding="utf-8"), ensure_ascii=False)
    ck("targets 10/16: 낮 sci 대본만 있으면 sci", P.latest_target(d16, tmp) == pa_)
    pb_ = os.path.join(tmp, "2026-10-16_pick_door.json")
    json.dump(dict(SAMPLES["pick"], date="2026-10-16"), open(pb_, "w", encoding="utf-8"), ensure_ascii=False)
    ck("targets 10/16: 저녁 골라보기가 오면 그것(낮 sci 를 다시 집지 않는다)", P.latest_target(d16, tmp) == pb_)
    ck("next 10/16 낮 sci: already_written", P.next_info(d16, tmp, now=KST_AT(d16, 11))["already_written"])
    vid = os.path.join(tmp, "v.mp4")
    open(vid, "wb").write(b"0")
    meta = {"video": vid, "seconds": 30.0}
    ck("게시: 10/15 sci 대본(저녁 편)은 막힘 없음 · 두 번은 막는다(날짜 열쇠)", P.blockers(SCI_S, meta, {}, D(10, 15)) == []
       and any("이미" in b for b in P.blockers(SCI_S, meta, {"2026-10-15": {"media_id": "S"}}, D(10, 15))))
    ck("게시: 10/15 낮 골라보기(태어난 달)를 올린 뒤에도 저녁 sci 는 올린다",
       P.blockers(SCI_S, meta, {"2026-10-15a": {"media_id": "A"}}, D(10, 15)) == [])
    ck("게시: sci 꼴이 아닌 날(10/14)의 sci 대본은 막는다", any("꼴" in b for b in P.blockers(dict(SCI_S, date="2026-10-14"), meta, {}, D(10, 14))))

print("── sci 대본 검사 ──")
SCI_S = json.load(open(os.path.join(HERE, "samples", "sci_mariana.json"), encoding="utf-8"))
E201 = P.sci_entry(201)
CMP = {"date": "2026-10-16", "kind": "sci", "src_n": 201, "slug": "deep-sea-size",
       "hook": ["심해 생물 크기 순위", "끝판왕은?"], "say_intro": "심해에서 제일 긴 동물은 과연 몇 미터일까요?",
       "beats": [{"big": "12cm", "sub": "심해아귀 암컷", "say": "심해아귀 암컷은 다 커도 12센티미터예요.", "src": 0, "value": 0.12,
                  "img": "a small deep sea anglerfish with a glowing lure in pitch-black water"},
                 {"big": "30cm", "sub": "흡혈오징어", "say": "흡혈오징어는 30센티미터, 수심 600에서 900미터에 살아요.", "src": 1,
                  "value": 0.3, "img": "a deep red vampire squid drifting in dark water"},
                 {"big": "46cm", "sub": "대왕구족충", "say": "쥐며느리 친척 대왕구족충은 46센티미터까지 자라요.", "src": 2,
                  "value": 0.46, "img": "a giant isopod crawling on the dark seafloor"},
                 {"big": "4.2m", "sub": "남극하트지느러미오징어", "say": "남극하트지느러미오징어 표본은 4.2미터였어요.", "src": 3,
                  "value": 4.2, "img": "a colossal squid with huge eyes in deep dark water"},
                 {"big": "6.4m", "sub": "그린란드상어", "say": "그린란드상어는 6.4미터까지 자라요.", "src": 4, "value": 6.4,
                  "img": "a large slow greenland shark gliding in icy dark water"},
                 {"big": "13m", "sub": "대왕오징어 암컷", "say": "대왕오징어 암컷은 긴 촉완까지 13미터예요.", "src": 5, "value": 13,
                  "img": "a giant squid with long tentacles in the deep ocean darkness"}],
       "verdict": {"big": "1위 거대관해파리", "say": "거대관해파리는 약 46미터로 추정돼요."},
       "caption": "심해 생물 크기 순위, 끝판왕은? 🦑", "hashtags": ["#심해", "#심해생물", "#크기비교"],
       "sources": E201["sources"], "bench": {"format": "크기 비교 순위"}}
ck("견본 sci_mariana 통과 · 날짜의 sci 편 · src_n = 그날 항목", K.check(SCI_S) == [] and P.kind_for(D(10, 15), "b") == "sci"
   and SCI_S["src_n"] == P.sci_n(D(10, 15)), K.check(SCI_S))
ck("compare(201) 대본 통과(작은 것 → 큰 것 · value)", K.check(CMP) == [], K.check(CMP))


def sci_bad(f, **kw):
    x = json.loads(json.dumps(kw.pop("base", SCI_S)))
    f(x)
    return K.check(x)


def _set(path, val):
    def f(x):
        o = x
        for k in path[:-1]:
            o = o[k]
        o[path[-1]] = val
    return f


errs = sci_bad(_set(["beats", 0, "big"], "11,000m"))
ck("facts 에 없는 숫자(11,000m)는 막는다", any("facts" in e and "11,000" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 2, "say"], "바닥의 물은 고작 3도예요."))
ck("말(say) 속 숫자도 facts 에서만(3도 → 막음 · 2.4도 는 통과)", any("3" in e and "facts" in e for e in errs), errs)
errs = sci_bad(_set(["verdict", "say"], "티타늄 마이크는 여기서 30일을 버텼어요."))
ck("판정 말의 숫자도 facts 에서만(30일 → 막음) · 확률(0%)만 예외", any("verdict.say" in e for e in errs)
   and not any("verdict.big" in e for e in K.check(SCI_S)), errs)
ck("콤마·단위 무시 · 만·억은 million·billion 과 맞춰 본다(430만 = 4.3 million · 54억 = 5.4 billion)",
   K.unbacked("430만 배 · 54억 배 · 4,300,000", K.fact_values(P.sci_entry(202))) == []
   and K.unbacked("431만", K.fact_values(P.sci_entry(202))) == ["431만"])
errs = sci_bad(_set(["beats", 1, "say"], "햇빛은 1,000미터 아래로 못 와요. 댓글로 남겨 줘요."))
ck("부탁 말(댓글로 남겨 줘)은 막는다", any("부탁" in e for e in errs), errs)
errs = sci_bad(_set(["src_n"], 102))
ck("src_n 이 그날 항목(101)이 아니면 막는다", any("src_n" in e for e in errs), errs)
errs = sci_bad(_set(["date"], "2026-10-14"))
ck("sci 날이 아니면(10/14) 막는다", any("sci 편이 없는 날" in e for e in errs), errs)
errs = sci_bad(lambda x: x["sources"].pop())
ck("sources 를 catalog 그대로 옮기지 않으면 막는다", any("sources" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 0, "src"], 9))
ck("src 번호가 sources 밖이면 막는다", any("src" in e for e in errs), errs)
errs = sci_bad(_set(["hook"], ["마리아나 해구 바닥에서 살아남기", "몇 분?"]))
ck("hook 줄 14자 넘으면 막는다", any("hook" in e for e in errs), errs)
errs = sci_bad(_set(["say_intro"], "안녕하세요, 오늘은 마리아나 해구예요."))
ck("say_intro 는 질문(?)으로 · 인사로 시작하면 막는다", sum("say_intro" in e for e in errs) == 2, errs)
errs = sci_bad(lambda x: x["beats"].__delitem__(slice(3, None)))
ck("박자 4개 미만은 막는다", any("beats" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 0, "img"], "a sign with text on the trench floor"))
ck("그림에 글자(sign·text)는 막는다", any("img" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 0, "img"], "a close-up portrait of a diver's face on the seafloor"))
ck("그림에 얼굴 클로즈업은 막는다", any("img" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 4, "say"], "압력에 몸이 피투성이가 돼요."))
ck("잔혹 묘사는 막는다", any("잔혹" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 0, "sub"], "타이타닉보다 깊은 곳"))
ck("프랜차이즈 이름은 막는다", any("프랜차이즈" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 0, "say"], "카메론이 내려간 수심 10,935미터예요."))
ck("실존 인물은 막는다", any("실존" in e for e in errs), errs)
errs = sci_bad(_set(["beats", 3, "value"], 0.2), base=CMP)
ck("compare: 작은 것 → 큰 것 순서가 아니면 막는다", any("순서" in e for e in errs), errs)
errs = sci_bad(lambda x: x["beats"][0].pop("value"), base=CMP)
ck("compare: value 가 없으면 막는다", any("value" in e for e in errs), errs)
errs = sci_bad(_set(["caption"], "마리아나 해구 바닥\n출처: NOAA"))
ck("caption 은 한 줄(출처·질문은 코드가)", any("caption" in e for e in errs), errs)

print("── sci 말·시간표·화면(가짜 그림) ──")
ck("말: 단위·분수·소수를 한글 읽기로(1/1,000 → 천 분의 일 · 2.4°C → 이 점 사도 · PSI)",
   K.sci_speech("1/1,000") == "천 분의 일" and K.sci_speech("2.4°C") == "이 점 사도"
   and "피에스아이" in K.sci_speech("16,000 PSI") and K.sci_speech("10,935m") == "만구백삼십오미터",
   [K.sci_speech(x) for x in ("1/1,000", "2.4°C", "16,000 PSI", "10,935m")])
ck("목소리 빠르기: sci 만 ×1.1(다른 꼴은 R.TEMPO 그대로)", K.SCI_TEMPO == 1.1 and R.TEMPO == float(os.environ.get("INSTA_TEMPO", "1.0"))
   and "tempo=SCI_TEMPO if sci else None" in open(os.path.join(HERE, "pick_reel.py"), encoding="utf-8").read())
from PIL import ImageChops  # noqa: E402
for name, s in (("survival(마리아나)", SCI_S), ("compare(심해 생물)", CMP)):
    says = K.says_of(s)
    dur = {t: 0.11 * len(t) for t in says}
    segs, _ = K.plan(s, dur)
    total = segs[-1]["start"] + segs[-1]["dur"]
    gaps = all(abs(a["start"] + a["dur"] - b["start"]) < 1e-6 for a, b in zip(segs, segs[1:]))
    said = {sg.get("say") for sg in segs} | {sg.get("say2") for sg in segs}
    ck(f"sci {name}: 18~40초 · 장면 빈틈 없음 · 질문 → 박자 {len(s['beats'])} → 판정 · 말이 전부 나온다(끝 질문 포함)",
       K.SCI_SEC[0] <= total <= K.SCI_SEC[1] and gaps and set(says) <= said
       and [sg["kind"] for sg in segs] == ["intro"] + ["beat"] * len(s["beats"]) + ["verdict"]
       and K.sci_speech(K.ask_of(s)) in said, (round(total, 1), gaps))
    short = K.plan(s, {t: 0.02 * len(t) for t in says})[0]
    ck(f"sci {name}: 말이 짧아도 18초 이상(끝 화면을 늘린다)", short[-1]["start"] + short[-1]["dur"] >= K.SCI_SEC[0] - 1e-6)
with tempfile.TemporaryDirectory() as tmp:
    for name, s in (("survival", SCI_S), ("compare", CMP)):
        a = K.assets(s, tmp, True)
        segs, _ = K.plan(s, {t: 0.11 * len(t) for t in K.says_of(s)})
        pa = K.Painter(s, a, segs)
        times = [0.0] + [sg["start"] + sg["dur"] * f for sg in segs for f in (0.01, 0.05, 0.5, 0.97)]
        sizes, low, top, bars = True, [], [], []
        for t in times:
            fr, bg_ = pa.frame(t), pa.sci_bg(t).convert("RGB")
            sizes &= fr.size == (K.W, K.H)
            bb = ImageChops.difference(fr, bg_).getbbox()
            low.append(bb[3] if bb else 0)                      # 그린 것의 아랫변
            top.append(bool(ImageChops.difference(fr.crop((0, 230, K.W, 430)), bg_.crop((0, 230, K.W, 430))).getbbox()))
            sg = pa.seg_at(t)
            if sg["kind"] == "beat":
                bars.append(bool(ImageChops.difference(fr.crop((0, 1196, K.W, 1440)), bg_.crop((0, 1196, K.W, 1440))).getbbox()))
        ck(f"sci {name}: 장면 전부(질문·박자·판정 {len(times)}장) 1080×1920", sizes)
        ck(f"sci {name}: 아래 25%(y 1440~)엔 아무것도 그리지 않는다(바탕 그림 그대로)", max(low) <= 1440, max(low))
        ck(f"sci {name}: 훅 두 줄은 처음부터 끝까지 위에", all(top))
        ck(f"sci {name}: 막대 띠는 compare 만(박자마다 y 1196~1440 사이에)", all(bars) if name == "compare" else not any(bars), bars)
        cv = K.cover_of(pa, s)
        ck(f"sci {name}: 커버 = 첫 프레임(회차 라벨 없음)", cv.size == (K.W, K.H)
           and not ImageChops.difference(cv, pa.frame(0.0)).getbbox())
cap = K.caption_of(SCI_S)
lines = cap.split("\n")
ck("sci 캡션: 훅 한 줄 → 출처(기관 이름) → 열린 질문 → 해시태그 · 회차 없음",
   lines[0] == SCI_S["caption"] and "출처: NOAA · RMG" in cap and K.ASK["sci"]["survival"] in cap
   and cap.index("출처:") < cap.index(K.ASK["sci"]["survival"]) < cap.index("#심해") and "오늘의 골라보기" not in cap, cap)
ck("sci 캡션: 해시태그 ≤ 5 · 댓글·보내기 부탁 없음", len(TAG.findall(cap)) <= 5 and not any(w in cap for w in ("댓글", "보내서", "저장")))
ck("sci 열린 질문은 형식마다(survival · compare)", K.ask_of(SCI_S) == "너라면 몇 초 버틸 것 같아요?"
   and K.ask_of(CMP) == "제일 놀라운 건 뭐였어요?" and K.ASK["sci"]["compare"] in K.caption_of(CMP))
ck("출처 이름: 도메인 → 기관(noaa.gov → NOAA · rmg.co.uk → RMG · 겹친 것 한 번)",
   K.source_names(["https://oceanservice.noaa.gov/x", "https://www.noaa.gov/y", "https://www.rmg.co.uk/z"]) == ["NOAA", "RMG"]
   and K.source_host("https://nssdc.gsfc.nasa.gov/a") == "nasa.gov")
wr2 = open(os.path.join(HERE, "SCI_WRITING.md"), encoding="utf-8").read()
ck("SCI_WRITING: 질문 먼저 · 숫자는 facts 에서만 · 부탁·잔혹·실존 인물·프랜차이즈 금지 · 열린 질문 두 개",
   "질문" in wr2 and "facts" in wr2 and "부탁 금지" in wr2 and "잔혹" in wr2 and "실존 인물" in wr2 and "영화" in wr2
   and K.ASK["sci"]["survival"] in wr2 and K.ASK["sci"]["compare"] in wr2 and "sci_mariana" in wr2)
ck("PICK_WRITING: sci 날은 SCI_WRITING 을 따른다", "SCI_WRITING.md" in wr and "sci" in wr)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
