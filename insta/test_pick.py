#!/usr/bin/env python3
"""인스타 '오늘의 골라보기'·sci·병맛(pick_reel·pick_plan·bm_reel) 오프라인 테스트 — 편성·검사·시간표·화면·게시 막기·워크플로."""
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
kinds = [k for _, _, k in seq if P.is_pick(k)]           # sci 편(10/15~)·병맛 편(10/25~)은 골라보기 로테이션에서 빠진다
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

print("── sci 편성(10/15~11/07 · 하루 한 편 sci, 저녁·낮 번갈아 · ★10/20 연장) ──")
D = lambda m, d: dt.date(2026, m, d)  # noqa: E731
WIN = [P.SCI_FROM + dt.timedelta(days=k) for k in range(24)]
ck("기간 10/15~11/07(양끝 포함 24일) · 항목 24개", (P.SCI_FROM, P.SCI_TO) == (D(10, 15), D(11, 7))
   and (P.SCI_TO - P.SCI_FROM).days + 1 == 24 == len(P.SCI_ORDER))
ck("sci 편은 10/15 저녁(b) → 10/16 낮(a) → 10/17 저녁 … 번갈아(11/07 낮까지)", [P.sci_slot(d) for d in WIN] == ["b", "a"] * 12,
   [P.sci_slot(d) for d in WIN])
with P.only_order():                          # ★10/25 sci 는 11/08 뒤로도 이어진다(open_plan) — 여기는 '항목이 바닥난 뒤'를 못 박는다
    ck("기간 밖(10/14 · 항목이 바닥난 11/08)엔 sci 없음", P.sci_slot(D(10, 14)) is None and P.sci_slot(D(11, 8)) is None
       and P.SCI not in [P.kind_for(d, sl) for d in (D(10, 14), D(11, 8)) for sl in P.slots_on(d)])
ck("기간 안 날마다 한 편은 sci · 한 편은 골라보기(꼴이 다르다)",
   all(sorted(P.kind_for(d, sl) == P.SCI for sl in P.slots_on(d)) == [False, True] for d in WIN))
TABLE = {  # 날짜: (낮 a, 저녁 b) — 보고·판정용으로 못 박는다(10/24 까지는 이미 정해진 과거 · 바뀌면 안 된다)
    D(10, 15): ("birth", "sci"), D(10, 16): ("sci", "pick"), D(10, 17): ("quiz", "sci"), D(10, 18): ("sci", "card"),
    D(10, 19): ("balance", "sci"), D(10, 20): ("sci", "birth"), D(10, 21): ("pick", "sci"), D(10, 22): ("sci", "quiz"),
    D(10, 23): ("card", "sci"), D(10, 24): ("sci", "balance")}
got_t = {d: (P.kind_for(d, "a"), P.kind_for(d, "b")) for d in TABLE}
ck("10/15~10/24 편성표 그대로(과거)", got_t == TABLE, {d.isoformat(): v for d, v in got_t.items() if v != TABLE[d]})
PAST = [(D(10, 8), "b", "pick", 1), (D(10, 9), "b", "quiz", 2), (D(10, 10), "b", "card", 3), (D(10, 11), "b", "balance", 4),
        (D(10, 12), "b", "birth", 5), (D(10, 13), "a", "pick", 6), (D(10, 13), "b", "quiz", 7), (D(10, 14), "a", "card", 8),
        (D(10, 14), "b", "balance", 9)]
ck("10/14 까지 꼴·회차는 그대로(이미 올린 편이 안 바뀐다)",
   [(d, sl, P.kind_for(d, sl), P.series_no(d, sl)) for d, sl, _, _ in PAST] == PAST)
allp = [(d, sl, P.kind_for(d, sl)) for d in (P.START + dt.timedelta(days=k) for k in range(40)) for sl in P.slots_on(d)]
picks = [(d, sl, k) for d, sl, k in allp if P.is_pick(k)]
ck("골라보기 로테이션은 sci·병맛을 건너뛰고 한 꼴씩 그대로(겹침·빠짐 없음 · 11/16 까지)",
   [k for _, _, k in picks] == [P.FORMATS[i % 5] for i in range(len(picks))])
ck("회차(series_no)는 골라보기 편만 센다 — 1, 2, 3 … 빈틈 없이 · sci·병맛은 None",
   [P.series_no(d, sl) for d, sl, _ in picks] == list(range(1, len(picks) + 1))
   and all(P.series_no(d, sl) is None for d, sl, k in allp if not P.is_pick(k)))
with P.only_order():
    ck("10/15 낮 태어난 달 #10 · 10/16 저녁 그림 고르기 #11 · 10/24 저녁 밸런스 #19 · (항목이 바닥나면) 11/08 낮 #20 · 저녁 #21",
       (P.series_no(D(10, 15), "a"), P.series_no(D(10, 16), "b"), P.series_no(D(10, 24), "b"), P.series_no(D(11, 8), "a"),
        P.series_no(D(11, 8), "b")) == (10, 11, 19, 20, 21))
    ck("항목이 바닥나면 11/08 부터 다시 하루 골라보기 두 편 — 10/24 밸런스 다음 꼴(태어난 달)부터",
       [P.kind_for(D(11, 8), sl) for sl in P.slots_on(D(11, 8))] == ["birth", "pick"]
       and [P.kind_for(D(11, 9), sl) for sl in P.slots_on(D(11, 9))] == ["quiz", "card"])
ck("slot_of 는 기간 안에서도 하나로 정해진다(sci ↔ sci 편 · 골라보기 꼴 ↔ 그 편)",
   all(P.slot_of(d, k) == sl for d, sl, k in allp) and all(P.slot_of(d, P.SCI) == P.sci_slot(d) for d in WIN))
try:
    P.post_index(D(10, 15), "b")
    raised = False
except ValueError:
    raised = True
ck("sci 편엔 골라보기 순번이 없다(post_index ValueError)", raised)
ck("sci 내용 순서 = SCI_ORDER(10/15 마리아나 101 · 10/28 남극 106 그대로 → 10/29~ 안 쓴 catalog 7개 → 901~903)",
   [P.sci_n(d) for d in WIN] == list(P.SCI_ORDER) and P.sci_n(D(10, 14)) is None
   and (P.sci_n(D(11, 8)) is None or P.sci_n(D(11, 8)) not in P.SCI_ORDER)
   and P.SCI_ORDER[:14] == (101, 201, 107, 102, 203, 104, 202, 105, 206, 109, 205, 103, 207, 106)
   and P.SCI_ORDER[14:] == (108, 110, 111, 112, 113, 114, 204, 901, 902, 903))
ck("10/24 까지 sci 순서 그대로(이미 올린 편) · 10/25 205 · 10/29 108 · 11/07 903",
   [P.sci_n(D(10, 15) + dt.timedelta(days=k)) for k in range(10)] == [101, 201, 107, 102, 203, 104, 202, 105, 206, 109]
   and (P.sci_n(D(10, 25)), P.sci_n(D(10, 29)), P.sci_n(D(11, 7))) == (205, 108, 903))
ents = [P.sci_entry(n) for n in P.SCI_ORDER]
ck("SCI_ORDER 항목이 전부 있고(shorts_catalog · sci_extra) survival·compare · facts·sources 가 있다 · 겹침 없음",
   all(e and e["format"] in ("survival", "compare") and e.get("facts") and e.get("sources") for e in ents)
   and [e["format"] for e in ents][:3] == ["survival", "compare", "survival"] and len(set(P.SCI_ORDER)) == len(P.SCI_ORDER))
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

print("── sci 추가 주제(insta/sci_extra.json · 901~) ──")
EXTRA = json.load(open(os.path.join(HERE, "sci_extra.json"), encoding="utf-8"))
CAT = json.load(open(P.SHORTS, encoding="utf-8"))
xs = (EXTRA.get("survival") or []) + (EXTRA.get("compare") or [])
cat_ns = {e["n"] for e in (CAT.get("survival") or []) + (CAT.get("compare") or [])}
ck("sci_extra: n ≥ 901 · 901~903 = SCI_ORDER 끝 셋 · 새 항목은 904~950 · 번호 안 겹침(catalog·서로)",
   {901, 902, 903} <= {e["n"] for e in xs} and all(901 <= e["n"] <= 903 or P.SCI_OPEN_N0 <= e["n"] < P.TEARDOWN_N0 for e in xs)
   and not cat_ns & {e["n"] for e in xs} and len({e["n"] for e in xs}) == len(xs) and P.SCI_ORDER[-3:] == (901, 902, 903))


def _entry_ok(e: dict) -> bool:
    srcs = e.get("sources") or []
    ok = (e.get("format") in ("survival", "compare") and e.get("look") in K.SCI_LOOKS and e.get("title_idea")
          and srcs and all(u.startswith("https://") for u in srcs) and e.get("careful") and e.get("slug")
          and all(isinstance(f.get("fact"), str) and isinstance(f.get("src"), int) and 0 <= f["src"] < len(srcs) for f in e["facts"])
          and {f["src"] for f in e["facts"]} == set(range(len(srcs))))
    if e.get("format") == "compare":
        vals = [x["value"] for x in e.get("items_idea") or []]
        ok = ok and e.get("unit") and len(vals) >= 4 and vals == sorted(vals) \
            and all(K._backed(float(v), K.fact_values(e)) for v in vals)
    else:
        ok = ok and len(e.get("beat_ideas") or []) >= 4
    return bool(ok)


ck("sci_extra: catalog 와 같은 모양(format·look·title_idea·facts{fact,src}·sources 전부 쓰임·careful · compare 는 오름차순 값이 facts 에)",
   all(_entry_ok(e) for e in xs), [e["n"] for e in xs if not _entry_ok(e)])
ck("sci_extra: 내용 한계(잔혹·실존 인물·프랜차이즈 낱말이 facts 에 없다)",
   not any(w.lower() in f["fact"].lower() for e in xs for f in e["facts"] for w in K.SCI_GORE + K.SCI_PEOPLE + K.SCI_FRANCHISE))
ck("sci_entry 가 sci_extra 도 찾는다(901 회오리 · 903 compare m)", P.sci_entry(901)["slug"] == "inside-a-tornado"
   and P.sci_entry(903)["format"] == "compare" and P.sci_entry(903)["unit"] == "m" and P.sci_entry(999) is None)
with tempfile.TemporaryDirectory() as tmp:
    ni = P.next_info(D(11, 5), tmp, now=KST_AT(D(11, 5), 11))
    ck("next 11/05 11시: sci 낮 편 · 901 · entry 는 sci_extra 그대로", (ni["kind"], ni["slot"], ni["src_n"], ni["format"])
       == ("sci", "a", 901, "survival") and ni["entry"]["facts"] == P.sci_entry(901)["facts"], ni.get("src_n"))

print("── sci '속이 보이는 과학'(10/25 저녁~ · 투시·단면 + 원인 3단계) ──")
import sci_xray as X  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402
XS = json.load(open(os.path.join(HERE, "samples", "sci_xray_heaviest-life.json"), encoding="utf-8"))
ck("날짜로 갈린다: SCI_XRAY_FROM 10/25 · 10/24 까지 옛 모양 · 주제·편성(SCI_ORDER·sci_slot)은 그대로",
   P.SCI_XRAY_FROM == D(10, 25) and not P.sci_xray(D(10, 24)) and P.sci_xray(D(10, 25)) and P.sci_xray(D(11, 7))
   and P.sci_slot(D(10, 25)) == "b" and P.sci_n(D(10, 25)) == 205 and P.SCI_XRAY_VIEWS == ("xray", "cutaway", "scene"))
with tempfile.TemporaryDirectory() as tmp:
    ni = P.next_info(D(10, 25), tmp, now=KST_AT(D(10, 25), 19))
    ck("next 10/25 19시: sci 205 · 견본 sci_xray_heaviest-life · SCI_WRITING · 속이 보이는 과학 · 20~35초 · view 셋",
       (ni["kind"], ni["slot"], ni["src_n"], ni["exemplar"], ni["writing"], ni["series"], ni["length_sec"], ni["views"])
       == ("sci", "b", 205, P.SCI_XRAY_EXEMPLAR, "insta/SCI_WRITING.md", "속이 보이는 과학", [20.0, 35.0],
           ["xray", "cutaway", "scene"]) and P.SCI_XRAY_EXEMPLAR == "insta/samples/sci_xray_heaviest-life.json"
       and "why" in ni["structure"] and "3" in ni["structure"], {k: ni.get(k) for k in ("kind", "exemplar", "series")})
    ni = P.next_info(D(10, 26), tmp, now=KST_AT(D(10, 26), 11))
    ck("next 10/26 11시(103): 새 견본·새 모양 그대로", (ni["kind"], ni["src_n"], ni["exemplar"]) == ("sci", 103, P.SCI_XRAY_EXEMPLAR))
    ni = P.next_info(D(10, 24), tmp, now=KST_AT(D(10, 24), 11))
    ck("next 10/24 11시(옛 모양): 견본 sci_mariana · series 없음", (ni["kind"], ni["exemplar"], "series" in ni)
       == ("sci", "insta/samples/sci_mariana.json", False), ni.get("exemplar"))
ck("견본 = 10/25 저녁 sci 편 그대로(날짜·꼴·편·src_n·sources — 루틴이 그날 그대로 복사할 수 있다)",
   XS["date"] == "2026-10-25" and XS["kind"] == P.kind_for(D(10, 25), "b") == "sci" and P.slot_of(D(10, 25), "sci") == "b"
   and XS["src_n"] == P.sci_n(D(10, 25)) and XS["sources"] == P.sci_entry(205)["sources"])
ck("견본 통과 · '속이 보이는 과학'으로 검사된다(is_xray) · 경고 없음", K.check(XS) == [] and K.is_xray(XS) and K.warns(XS) == [],
   K.check(XS))
ck("견본 모양: 훅 → why → 박자 3(view 투시·단면) → 결과 · 이름표 셋 이상", len(XS["beats"]) == 3 and XS["why"]["view"] in X.VIEWS
   and all(b["view"] in ("xray", "cutaway") for b in XS["beats"]) and sum(bool(o.get("label")) for o in XS["beats"] + [XS["verdict"]]) >= 3
   and XS["hook"][1].endswith("?"))
SURV = {"date": "2026-10-28", "kind": "sci", "src_n": 106, "slug": "antarctic-night",
        "hook": ["영하 70도 남극 밤", "몸속에선 무슨 일?"], "say_intro": "지붕도 없이 남극 겨울밤에 서 있으면, 몸속에선 무슨 일이 생길까요?",
        "why": {"sub": "열이 빠져나가는 길이 셋", "say": "왜 못 버틸까요?", "view": "xray",
                "img": "a smooth featureless mannequin-like human figure standing on an icy plain in light snowfall"},
        "beats": [{"big": "영하 70도", "sub": "겨울 평균 기온", "say": "내륙의 겨울은 평균 영하 40도에서 70도예요.", "src": 2, "view": "cutaway",
                   "img": "a thick slab of Antarctic ice sheet sliced open like a cake, a tiny research hut on top"},
                  {"big": "5분", "sub": "드러난 피부가 얼어요", "say": "바람이 불면 드러난 피부는 5분 안에 얼 수 있어요.", "src": 3, "view": "xray",
                   "img": "a smooth featureless mannequin-like human hand with glowing finger bones in icy wind",
                   "label": "손가락뼈", "pin": [0.5, 0.45]},
                  {"big": "35°C", "sub": "이 아래면 저체온증", "say": "몸속 온도가 35도 아래로 내려가면 저체온증이에요.", "src": 4, "view": "xray",
                   "img": "a smooth featureless mannequin-like human figure with a softly glowing heart in the center of the chest",
                   "label": "심장", "pin": [0.5, 0.4]}],
        "verdict": {"big": "생존 확률 0%", "say": "해는 6개월 뒤에야 다시 떠요."},
        "caption": "영하 70도 남극 밤, 몸속에선? 🧊", "hashtags": ["#속이보이는과학", "#남극"],
        "sources": P.sci_entry(106)["sources"], "bench": {"format": "투명 피부 3D — 대조 훅 → 왜? → 원인 3단계 → 결과"}}
ck("survival(106 남극) 대본 통과 — 결과 그림이 없으면 3단계 그림을 잇는다 · 열린 질문은 생존 꼴", K.check(SURV) == []
   and K.ask_of(SURV) == K.ASK["sci"]["survival"] and X.plan(SURV, X.est_durations(SURV))[0][-1]["img"] == 2, K.check(SURV))


def xbad(f, base=None):
    x = json.loads(json.dumps(base or XS))
    f(x)
    return K.check(x)


CASES_X = [
    ("훅 둘째 줄이 질문(?)이 아니면 막는다", _set(["hook", 1], "이게 꼴찌다"), "hook 둘째 줄"),
    ("훅 줄 14자 넘으면 막는다", _set(["hook", 0], "기록상 제일 무거운 코끼리 10.9톤"), "hook 은 두 줄"),
    ("'왜?' 박자가 없으면 막는다", lambda x: x.pop("why"), "why("),
    ("why.say 에 '왜' 가 없으면 막는다", _set(["why", "say"], "더 무거운 게 셋이에요."), "why.say"),
    ("why.say 20자 넘으면 막는다", _set(["why", "say"], "왜냐고요? 코끼리보다 훨씬 더 무거운 게 셋이나 있어요."), "why.say"),
    ("박자가 2개면 막는다(정확히 3)", lambda x: x["beats"].pop(), "정확히 3개"),
    ("박자가 4개면 막는다(정확히 3)", lambda x: x["beats"].append(dict(x["beats"][2])), "정확히 3개"),
    ("view 가 없으면 막는다", lambda x: x["beats"][0].pop("view"), "view 는"),
    ("view 가 셋 밖이면 막는다", _set(["beats", 1, "view"], "photo"), "view 는"),
    ("scene 이 둘이면 막는다(속을 보여 줘야)", lambda x: [b.update(view="scene") for b in x["beats"][:2]], "scene"),
    ("이름표 10자 넘으면 막는다", _set(["beats", 0, "label"], "아주 긴 이름표 열한 글자"), "label"),
    ("pin 이 0.1~0.85 밖이면 막는다", _set(["beats", 0, "pin"], [0.5, 0.95]), "pin 은 [x, y]"),
    ("pin 이 두 수가 아니면 막는다", _set(["beats", 0, "pin"], [0.5]), "pin 은 [x, y]"),
    ("label 없이 pin 만 쓰면 막는다", lambda x: x["beats"][0].pop("label"), "pin 은 label 과 같이"),
    ("이름표 숫자도 facts 에서만(2,000톤 → 막음)", _set(["beats", 2, "label"], "2,000톤"), "facts"),
    ("why 숫자도 facts 에서만", _set(["why", "sub"], "더 무거운 게 7개"), "why.sub"),
    ("img 는 영어로(한글 → 막음)", _set(["beats", 0, "img"], "투명한 고래 몸속 갈비뼈가 보이는 모습"), "영어로"),
    ("그림에 글자(text)는 막는다", _set(["beats", 1, "img"], "a sequoia trunk cross-section with text on it"), "img 에"),
    ("why 그림의 잔혹 묘사(blood)도 막는다", _set(["why", "img"], "a huge elephant with blood vessels and organs inside"), "잔혹"),
    ("부탁 말(댓글)은 why 에서도 막는다", _set(["why", "sub"], "댓글로 남겨 줘요"), "부탁"),
    ("compare: 작은 것 → 큰 것이 아니면 막는다", _set(["beats", 2, "value"], 150), "순서"),
    ("결과가 없으면 막는다", lambda x: x.pop("verdict"), "verdict("),
    ("결과 img 를 쓰면 view 도", lambda x: x["verdict"].pop("view"), "verdict view"),
    ("src_n 이 그날 항목(205)이 아니면 막는다", _set(["src_n"], 103), "src_n"),
    ("sources 를 그대로 옮기지 않으면 막는다", lambda x: x["sources"].pop(), "sources"),
    ("말이 너무 길면 길이 어림이 막는다(35초)", lambda x: [b.update(say="가" * 45) for b in x["beats"]]
     and x.update(say_intro="나" * 49 + "?") or x["verdict"].update(say="다" * 40), "길이 어림"),
]
for name, f, want in CASES_X:
    errs = xbad(f)
    ck(name, any(want in e for e in errs), errs)
ck("날짜가 가른다: 옛 모양(마리아나 · 박자 6)을 10/25 로 쓰면 새 검사가 막는다(why·박자 3)",
   any("why(" in e for e in xbad(lambda x: x.update(date="2026-10-25", src_n=205), SCI_S))
   and any("정확히 3개" in e for e in xbad(lambda x: x.update(date="2026-10-25", src_n=205), SCI_S)))
ck("날짜가 가른다: 새 모양을 10/24 로 쓰면 옛 검사(박자 4~6)로 막힌다 · is_xray False",
   any("beats 는 4~6개" in e for e in xbad(lambda x: x.update(date="2026-10-24", src_n=109)))
   and not K.is_xray(dict(XS, date="2026-10-24")) and not K.is_xray(dict(XS, date="x")))
ck("옛 견본(10/15 마리아나)은 그대로 통과(옛 날짜는 옛 규칙)", K.check(SCI_S) == [] and not K.is_xray(SCI_S))

says = X.says_of(XS)
segs, ticks = X.plan(XS, {t: 0.11 * len(t) for t in says})
total = segs[-1]["start"] + segs[-1]["dur"]
said = {sg.get("say") for sg in segs} | {sg.get("say2") for sg in segs}
ck("시간표: 훅(0.0초부터 말) → 왜? → 1/3·2/3·3/3 → 결과 · 빈틈 없음 · 말 전부(끝 질문 포함) · 20~35초",
   [sg["kind"] for sg in segs] == ["intro", "why", "step", "step", "step", "verdict"] and segs[0]["at"] == 0.0
   and all(abs(a["start"] + a["dur"] - b["start"]) < 1e-6 for a, b in zip(segs, segs[1:])) and set(says) <= said
   and K.sci_speech(K.ask_of(XS)) in said and X.SEC[0] <= total <= X.SEC[1] and len(ticks) == 5, round(total, 1))
ck("훅과 '왜?' 는 한 그림(why) · 박자마다 제 그림 · 결과는 결과 그림", [sg["img"] for sg in segs] == ["why", "why", 0, 1, 2, "verdict"]
   and segs[0]["img_g"] == segs[1]["img_g"])
short = X.plan(XS, {t: 0.02 * len(t) for t in says})[0]
ck("말이 짧아도 20초 이상(끝 화면을 늘린다)", short[-1]["start"] + short[-1]["dur"] >= X.SEC[0] - 1e-6)
est = X.plan(XS, X.est_durations(XS))[0]
ck("길이 어림(CPS) 20~35초 · 훅은 0~6초 안쪽", X.SEC[0] <= est[-1]["start"] + est[-1]["dur"] <= X.SEC[1] and est[1]["start"] <= 6.5,
   (round(est[-1]["start"] + est[-1]["dur"], 1), est[1]["start"]))
ck("그림 화풍: view 마다 코드가 앞뒤를 붙인다(단면 · 투시 '유리처럼' · 밝은 단색 배경) · 정사각",
   X.prompt_of(XS["beats"][1]).startswith("clean 3D cutaway cross-section illustration, ")
   and "outer shell cut open" in X.prompt_of(XS["beats"][1]) and "clear like glass" in X.prompt_of(XS["why"])
   and all("plain light grey-blue gradient background" in X.prompt_of({"img": "x" * 20, "view": v}) for v in X.VIEWS)
   and X.ASPECT == "1:1" and not any(K.SCI_IMG_BAN.search(h + t) for h, t in X.VIEW_STYLE.values()))
with tempfile.TemporaryDirectory() as tmp:
    a = X.assets(XS, tmp, True)
    ck("그림: why · 박자 셋 · 결과 = 5장(가짜)", sorted(map(str, a["imgs"])) == ["0", "1", "2", "verdict", "why"])
    segs, _ = X.plan(XS, {t: 0.11 * len(t) for t in X.says_of(XS)})
    pa = X.Painter(XS, a, segs)
    times = [0.0] + [sg["start"] + sg["dur"] * f for sg in segs for f in (0.02, 0.5, 0.97)]
    sizes, low, top = True, [], []
    for t in times:
        fr, bg_ = pa.frame(t), pa.bg_at(t).convert("RGB")
        sizes &= fr.size == (K.W, K.H)
        bb = ImageChops.difference(fr, bg_).getbbox()
        low.append(bb[3] if bb else 0)
        top.append(bool(ImageChops.difference(fr.crop((0, 150, K.W, 300)), bg_.crop((0, 150, K.W, 300))).getbbox()))
    ck(f"화면 전부({len(times)}장) 1080×1920 · 아래 25%(y 1440~)엔 아무것도 그리지 않는다 · 훅은 처음부터 끝까지 위에",
       sizes and max(low) <= 1440 and all(top), max(low))

    def drawn(t, box):
        return bool(ImageChops.difference(pa.frame(t).crop(box), pa.bg_at(t).convert("RGB").crop(box)).getbbox())
    mid = {sg["kind"] + str(sg.get("k", "")): sg["start"] + sg["dur"] * 0.8 for sg in segs}
    seen = {}
    _prog, _badge = pa._progress, pa._badge
    pa._progress = lambda d, cur, done: seen.setdefault(pa.cur, []).append(("prog", cur, done)) or _prog(d, cur, done)
    pa._badge = lambda d, text: seen.setdefault(pa.cur, []).append(("badge", text)) or _badge(d, text)
    for k_, t_ in mid.items():
        pa.cur = k_
        pa.frame(t_)
    pa._progress, pa._badge = _prog, _badge
    ck("단계 배지(1/3·2/3·3/3 · 결과)는 박자·결과에만 · 1→2→3 진행 표시(지금 단계·지난 단계)는 왜?·박자·결과에(첫 장면엔 없음)",
       seen == {"why": [("prog", None, 0)], "step0": [("prog", 0, 0), ("badge", "1/3")], "step1": [("prog", 1, 1), ("badge", "2/3")],
                "step2": [("prog", 2, 2), ("badge", "3/3")], "verdict": [("prog", None, 3), ("badge", "결과")]}
       and all(drawn(mid[k], X.BADGE_BOX) for k in ("step0", "verdict")) and not drawn(mid["why"], X.BADGE_BOX), seen)
    sg0 = segs[2]
    t_on = sg0["start"] + X.LABEL_AT + X.LABEL_IN + 0.05
    px, py = pa.pin_xy(sg0, t_on, XS["beats"][0]["pin"])
    box = (int(px) - 10, int(py) - 10, int(px) + 10, int(py) + 10)
    ck("이름표: 박자 시작엔 없고(LABEL_AT 뒤) 선이 pin 자리를 가리킨다 · 칩은 오른쪽 버튼 열(x 960~) 앞",
       not drawn(sg0["start"] + 0.1, box) and drawn(t_on, box) and not drawn(t_on, (962, 600, K.W, 1440)))
    dark = Image.new("RGB", (64, 64), (40, 40, 50))
    ck("첫 화면이 밝다(평균 밝기 ≥ 110 — 10/14 어두운 sci 교훈) · 어두운 그림은 끌어올린다",
       X.first_frame_brightness(pa) >= 110 and sum(ImageOps.grayscale(X.brighten(dark)).getdata()) / 4096 >= X.BRIGHT_MIN - 12,
       round(X.first_frame_brightness(pa), 1))
    st = X.sheet_times(segs)
    ck("확인용 프레임: 첫 프레임 + 장면마다(결과는 열린 질문 뒤)", st[0] == 0.0 and len(st) == len(segs) + 1
       and st[-1] > segs[-1]["start"] + segs[-1]["ask_at"])
cap = K.caption_of(XS)
ck("캡션: 훅 한 줄 → 출처(기관) → 열린 질문(compare) → 해시태그 ≤ 5 · 부탁 없음", cap.split("\n")[0] == XS["caption"]
   and "출처: San Diego Zoo · NOAA · NPS · USU 외" in cap and K.ASK["sci"]["compare"] in cap and len(TAG.findall(cap)) <= 5
   and not any(w in cap for w in ("댓글", "보내서", "저장")), cap)
src_ = open(os.path.join(HERE, "pick_reel.py"), encoding="utf-8").read()
ck("pick_reel 이 날짜로 넘긴다(check·render 둘 다 is_xray → sci_xray)", "_xray().check(s) if is_xray(s) else check_sci(s)" in src_
   and "if is_xray(s):" in src_ and "return _xray().render(path, out_dir, work, mock)" in src_)
wx = open(os.path.join(HERE, "SCI_WRITING.md"), encoding="utf-8").read()
ck("SCI_WRITING: 속이 보이는 과학 · 훅 → 왜? → 3단계 → 결과 · view 셋 · label·pin · 새 견본 · 10/25 복사 · 숫자는 facts",
   all(w in wx for w in ("속이 보이는 과학", "왜", "정확히 3개", "1/3", "xray", "cutaway", "scene", "label", "pin",
                         "sci_xray_heaviest-life.json", "10/25", "facts", "check", "due: false", "부탁 금지")))

print("── 병맛 편성(10/25~11/07 · 골라보기 자리 · A/B 번갈아) ──")
import bm_reel as B  # noqa: E402
BMWIN = [P.BM_FROM + dt.timedelta(days=k) for k in range(14)]
ck("기간 10/25~11/07(양끝 포함 14일) · 꼴 둘", (P.BM_FROM, P.BM_TO) == (D(10, 25), D(11, 7))
   and (P.BM_TO - P.BM_FROM).days + 1 == 14 and P.BM_KINDS == ("bm_paper", "bm_animal"))
ck("꼴: 10/25 부터 ABBA ABBA ABBA AB(i%4 가 0·3 이면 A) → 7편씩",
   "".join("A" if P.bm_kind(d) == "bm_paper" else "B" for d in BMWIN) == "ABBAABBAABBAAB"
   and [P.kind_for(d, sl) for d in BMWIN for sl in P.slots_on(d)].count("bm_paper") == 7
   and [P.kind_for(d, sl) for d in BMWIN for sl in P.slots_on(d)].count("bm_animal") == 7)
split = {(k, sl): sum(1 for d in BMWIN if P.bm_kind(d) == k and P.bm_slot(d) == sl) for k in P.BM_KINDS for sl in P.SLOTS}
ck("시간대가 꼴에 몰리지 않는다: A 낮 4·저녁 3 · B 낮 3·저녁 4", split == {("bm_paper", "a"): 4, ("bm_paper", "b"): 3,
                                                          ("bm_animal", "a"): 3, ("bm_animal", "b"): 4}, split)
BMTABLE = {  # 날짜: (낮 a, 저녁 b) — 보고·판정용
    D(10, 25): ("bm_paper", "sci"), D(10, 26): ("sci", "bm_animal"), D(10, 27): ("bm_animal", "sci"),
    D(10, 28): ("sci", "bm_paper"), D(10, 29): ("bm_paper", "sci"), D(10, 30): ("sci", "bm_animal"),
    D(10, 31): ("bm_animal", "sci"), D(11, 1): ("sci", "bm_paper"), D(11, 2): ("bm_paper", "sci"),
    D(11, 3): ("sci", "bm_animal"), D(11, 4): ("bm_animal", "sci"), D(11, 5): ("sci", "bm_paper"),
    D(11, 6): ("bm_paper", "sci"), D(11, 7): ("sci", "bm_animal"), D(11, 8): ("birth", "pick")}
with P.only_order():                          # 11/08 은 sci 항목이 바닥났을 때 — 열린 항목이 있으면 그날 한 편은 sci(따로 본다)
    got_b = {d: (P.kind_for(d, "a"), P.kind_for(d, "b")) for d in BMTABLE}
ck("10/25~11/08 편성표 그대로(병맛 = sci 가 아닌 편 · 항목이 바닥나면 11/08 골라보기 두 편)", got_b == BMTABLE,
   {d.isoformat(): v for d, v in got_b.items() if v != BMTABLE[d]})
ck("기간 밖(10/24·11/08)엔 병맛 없음 · 10/24 이전 꼴은 골라보기·sci 뿐", P.bm_kind(D(10, 24)) is None and P.bm_kind(D(11, 8)) is None
   and all(P.kind_for(d, sl) in P.FORMATS + (P.SCI,) for d, sl, _ in allp if d <= D(10, 24)))
ck("기간 안 날마다 sci 한 편 + 병맛 한 편(골라보기 없음 · 회차 None · slot_of 하나로)",
   all(sorted(P.kind_for(d, sl) for sl in P.slots_on(d)) == sorted([P.SCI, P.bm_kind(d)]) for d in BMWIN)
   and all(P.series_no(d, sl) is None for d in BMWIN for sl in P.slots_on(d))
   and all(P.slot_of(d, P.bm_kind(d)) == P.bm_slot(d) != P.sci_slot(d) for d in BMWIN))
try:
    P.post_index(D(10, 25), "a")
    raised = False
except ValueError:
    raised = True
ck("병맛 편엔 골라보기 순번이 없다(post_index ValueError)", raised)
ck("10/24 까지 꼴·회차·sci 순서는 그대로(병맛이 과거를 바꾸지 않는다)",
   [(d, sl, P.kind_for(d, sl), P.series_no(d, sl)) for d, sl, _, _ in PAST] == PAST and got_t == TABLE)
ck("파일 이름의 꼴: bm_paper·bm_animal(밑줄 든 꼴)도 알아본다", P._kind_of_file("x/2026-10-25_bm_paper_wombat-cube-poo.json")
   == "bm_paper" and P._kind_of_file("2026-10-26_bm_animal_penguin-subway.json") == "bm_animal"
   and P._kind_of_file("2026-10-16_sci_deep-sea-size.json") == "sci" and P._kind_of_file("2026-10-08_pick_door.json") == "pick")
BM_A = json.load(open(os.path.join(HERE, "samples", "bm_paper_wombat.json"), encoding="utf-8"))
BM_B = json.load(open(os.path.join(HERE, "samples", "bm_animal_penguin.json"), encoding="utf-8"))
with tempfile.TemporaryDirectory() as tmp:
    ni = P.next_info(D(10, 25), tmp, now=KST_AT(D(10, 25), 11))
    ck("next 10/25 11시: 병맛 A · 낮 편 · BM_WRITING · 견본 bm_paper_wombat · 회차 없음 · 1/14 · 18~23초",
       (ni["kind"], ni["slot"], ni["writing"], ni["exemplar"], ni["series_no"], ni["format"], ni["bm_no"], ni["bm_total"],
        ni["length_sec"], ni["file"]) == ("bm_paper", "a", "insta/BM_WRITING.md", "insta/samples/bm_paper_wombat.json", None,
                                          "A", 1, 14, [18.0, 23.0], "output/insta_pick/2026-10-25_bm_paper_<slug>.json"), ni)
    ni = P.next_info(D(10, 26), tmp, now=KST_AT(D(10, 26), 19))
    ck("next 10/26 19시: 병맛 B · 저녁 편 · 견본 bm_animal_penguin · 2/14 · 18~22초",
       (ni["kind"], ni["slot"], ni["writing"], ni["exemplar"], ni["format"], ni["bm_no"], ni["length_sec"])
       == ("bm_animal", "b", "insta/BM_WRITING.md", "insta/samples/bm_animal_penguin.json", "B", 2, [18.0, 22.0]), ni)
    e401 = P.bm_entry(401)
    ck("next 병맛: 그날 catalog 항목(bm_n·src_n 401 · facts·sources·careful·premise 그대로)",
       (ni_a := P.next_info(D(10, 25), tmp, now=KST_AT(D(10, 25), 11)))["bm_n"] == ni_a["src_n"] == 401
       and ni_a["entry"]["facts"] == e401["facts"] and ni_a["entry"]["sources"] == e401["sources"]
       and all(k in ni_a["entry"] for k in ("careful", "premise", "punch_idea", "stamp_idea", "topic", "slug")), ni_a.get("bm_n"))
    ni_b = P.next_info(D(11, 7), tmp, now=KST_AT(D(11, 7), 19))
    ck("next 11/07 19시: 병맛 B 414 갯가재 · animal·quote_idea 가 entry 에", (ni_b["kind"], ni_b["slot"], ni_b["bm_n"])
       == ("bm_animal", "b", 414) and ni_b["entry"]["animal_ko"] == "갯가재" and "quote_idea" in ni_b["entry"], ni_b.get("bm_n"))
    ck("next 10/26 11시: 그날 낮 편은 sci(103)", (P.next_info(D(10, 26), tmp, now=KST_AT(D(10, 26), 11))["kind"],
                                             P.next_info(D(10, 26), tmp, now=KST_AT(D(10, 26), 11))["src_n"]) == ("sci", 103))
    ck("견본 날짜의 꼴 = 견본 꼴(10/25 A · 10/26 B — 클라우드 루틴이 그대로 복사할 수 있다)",
       P.kind_for(D(10, 25), P.bm_slot(D(10, 25))) == BM_A["kind"] == "bm_paper" and BM_A["date"] == "2026-10-25"
       and P.kind_for(D(10, 26), P.bm_slot(D(10, 26))) == BM_B["kind"] == "bm_animal" and BM_B["date"] == "2026-10-26")
    pa_ = os.path.join(tmp, "2026-10-25_bm_paper_wombat-cube-poo.json")
    json.dump(BM_A, open(pa_, "w", encoding="utf-8"), ensure_ascii=False)
    ck("병맛 대본을 쓰면 already_written · targets 가 집는다", P.next_info(D(10, 25), tmp, now=KST_AT(D(10, 25), 11))["already_written"]
       and P.latest_target(D(10, 25), tmp) == pa_)
    pb_ = os.path.join(tmp, "2026-10-25_sci_cheetah.json")
    json.dump(dict(SCI_S, date="2026-10-25", src_n=205), open(pb_, "w", encoding="utf-8"), ensure_ascii=False)
    ck("targets 10/25: 저녁 sci 가 오면 그것(낮 병맛을 다시 집지 않는다)", P.latest_target(D(10, 25), tmp) == pb_)
    rec = P.next_info(D(10, 27), tmp, now=KST_AT(D(10, 27), 11))["recent"]
    ck("recent 에 병맛 topic 이 보인다(같은 소재 다시 쓰지 않게)", any(r.get("topic") == BM_A["topic"] for r in rec), rec[:2])
    vid = os.path.join(tmp, "v.mp4")
    open(vid, "wb").write(b"0")
    meta = {"video": vid, "seconds": 20.0}
    ck("게시: 10/25 병맛 A(낮 편)는 막힘 없음 · 두 번은 막는다(낮 열쇠 '2026-10-25a')", P.blockers(BM_A, meta, {}, D(10, 25)) == []
       and any("이미" in b for b in P.blockers(BM_A, meta, {"2026-10-25a": {"media_id": "A"}}, D(10, 25))))
    ck("게시: 병맛 꼴이 그날 꼴과 다르면 막는다(10/26 에 A)", any("꼴" in b for b in P.blockers(dict(BM_A, date="2026-10-26"), meta, {}, D(10, 26))))

print("── 병맛 소재 catalog(insta/bm_catalog.json — 14편 · 출처 미리 확인) ──")
BMCAT = json.load(open(os.path.join(HERE, "bm_catalog.json"), encoding="utf-8"))["entries"]
ck("catalog 14편 · n = BM_ORDER(401~414) 순서 그대로", [e["n"] for e in BMCAT] == list(P.BM_ORDER) == list(range(401, 415)))
ck("날마다 편성 꼴 = 그날 항목 format(ABBA: paper 7 · animal 7)",
   all(P.BM_FMT_KIND[P.bm_entry(P.bm_n(d))["format"]] == P.bm_kind(d) for d in BMWIN)
   and [e["format"] for e in BMCAT].count("paper") == 7 and [e["format"] for e in BMCAT].count("animal") == 7)
ck("catalog 항목 검사 전부 통과(facts{fact,src}·https 출처 전부 쓰임·careful·premise·punch_idea·꼴별 필드)",
   all(not B.entry_errs(e) for e in BMCAT), {e["n"]: B.entry_errs(e) for e in BMCAT if B.entry_errs(e)})
anim = [e["animal_ko"] for e in BMCAT if e["format"] == "animal"]
ck("B 동물은 모두 다르다 · 햄스터 없음 · 소재(topic·slug) 겹침 없음", len(set(anim)) == len(anim) == 7 and "햄스터" not in anim
   and len({e["topic"] for e in BMCAT}) == len({e["slug"] for e in BMCAT}) == 14, anim)
ck("10/25 웜뱃(401)·10/26 펭귄(402) = 견본과 같은 sources·topic·animal", P.bm_n(D(10, 25)) == 401 and P.bm_n(D(10, 26)) == 402
   and BMCAT[0]["sources"] == json.load(open(os.path.join(HERE, "samples", "bm_paper_wombat.json"), encoding="utf-8"))["sources"]
   and BMCAT[1]["animal"] == json.load(open(os.path.join(HERE, "samples", "bm_animal_penguin.json"), encoding="utf-8"))["animal"])
low_cat = json.dumps(BMCAT, ensure_ascii=False).lower()
ck("catalog 에 금지 소재 낱말 없음(브레인롯·캐릭터 IP·실존 인물·성적·외모 비하)",
   not B._hits(B.BRAINROT + B.CHARACTERS + B.CELEBS + B.SEXUAL + B.BODY, [low_cat]), B._hits(B.BRAINROT + B.CHARACTERS + B.CELEBS
                                                                                      + B.SEXUAL + B.BODY, [low_cat]))

print("── 병맛 대본 검사 ──")
ck("견본 A(웜뱃)·B(펭귄) 통과 · pick_reel.check 가 넘긴다", K.check(BM_A) == [] and K.check(BM_B) == [] and B.check(BM_A) == [],
   (K.check(BM_A), K.check(BM_B)))
ck("pick_reel KINDS 에 병맛 두 꼴", set(P.BM_KINDS) <= set(K.KINDS))


def bm_bad(base, f):
    x = json.loads(json.dumps(base))
    f(x)
    return K.check(x)


def _line(i, key, val):
    def f(x):
        x["lines"][i][key] = val
    return f


CASES_BM = [
    ("facts 에 없는 숫자(하루 200개)는 막는다", BM_A, _line(3, "say", "하루 최대 200개. 한 개 2센티쯤."), "facts 에 없는 숫자"),
    ("만·억도 facts 와 맞춰 본다(100만 개 → 막음)", BM_A, _line(3, "big", "100만 개"), "facts 에 없는 숫자"),
    ("캡션 숫자도 facts 에서만", BM_A, lambda x: x.update(caption="웜뱃 하루 300개ㅋㅋ"), "caption: catalog"),
    ("첫 줄이 hook 이 아니면 막는다", BM_A, _line(0, "type", "beat"), "hook"),
    ("펀치라인이 없으면 막는다", BM_A, _line(5, "type", "beat"), "펀치라인"),
    ("도장(stamp)이 없으면 막는다", BM_A, _line(1, "type", "beat"), "도장"),
    ("숫자 든 줄에 src 가 없으면 막는다", BM_A, lambda x: x["lines"][3].pop("src"), "src"),
    ("sources 를 catalog 그대로 옮기지 않으면 막는다(하나 더함)", BM_A, lambda x: x["sources"].append("https://example.org/x"),
     "그대로"),
    ("sources 순서가 다르면 막는다", BM_A, lambda x: x["sources"].reverse(), "그대로"),
    ("src_n 이 그날 항목(401)이 아니면 막는다", BM_A, lambda x: x.update(src_n=404), "src_n"),
    ("src_n 이 catalog 에 없으면 막는다", BM_A, lambda x: x.update(src_n=999), "bm_catalog"),
    ("숫자는 catalog facts 에서만(대본에 facts 를 써도 소용없다)", BM_A, lambda x: x.update(
        facts=[{"fact": "about 500 cubes", "src": 0}]) or x["lines"][3].update(big="하루 500개"), "facts 에 없는 숫자"),
    ("topic 을 catalog 와 다르게 쓰면 막는다", BM_A, lambda x: x.update(topic="웜뱃 똥 이야기"), "topic"),
    ("B animal 을 catalog 와 다르게 쓰면 막는다", BM_B, lambda x: x.update(animal_ko="황제펭귄"), "animal"),
    ("TTS 가 'ㅋㅋ'를 읽지 않게(say 에 ㅋㅋ → 막음)", BM_A, _line(0, "say", "네모난 똥 싸는 동물 진짜 있음ㅋㅋ"), "ㅋㅋ"),
    ("TTS 가 '킹받'을 읽지 않게", BM_A, _line(5, "say", "결론. 웜뱃 킹받네."), "킹받"),
    ("say 에 '띠용'(효과음 이름)도 막는다", BM_A, _line(5, "say", "결론. 띠용."), "띠용"),
    ("숫자를 한글로(스물한 마리) 쓰면 막는다", BM_B, _line(1, "say", "펭귄은 모이면 1제곱미터에 약 스물한 마리."), "아라비아"),
    ("say 에 영어가 남으면 막는다", BM_A, _line(2, "say", "장 속에 balloon 넣고 불어 봄."), "영어"),
    ("캡션에 댓글 부탁 → 막는다(ASK_BAN)", BM_A, lambda x: x.update(caption="웜뱃 진짜 이럼ㅋㅋ 출처 댓글에 둠"), "부탁"),
    ("화면 글에 팔로우 부탁 → 막는다", BM_B, lambda x: x.update(end="팔로우하면 다음 편"), "부탁"),
    ("해시태그 6개는 막는다", BM_A, lambda x: x.update(hashtags=[f"#태그{c}" for c in "가나다라마바"]), "hashtags"),
    ("캡션에 '#'·'출처' 를 쓰면 막는다(코드가 붙인다)", BM_A, lambda x: x.update(caption="웜뱃 #웜뱃"), "caption"),
    ("브레인롯(퉁퉁퉁 사후르)은 막는다", BM_A, _line(5, "sub", "결론: 퉁퉁퉁 사후르 등장"), "브레인롯"),
    ("치이카와·펭수 같은 캐릭터 IP 는 막는다", BM_B, lambda x: x.update(topic="펭수 지하철"), "IP"),
    ("영화 장면 패러디는 막는다", BM_B, _line(3, "sub", "그 영화 명장면 패러디"), "IP"),
    ("실존 인물(아이유)은 막는다", BM_A, _line(2, "sub", "아이유도 놀람"), "실존 인물"),
    ("잔혹 묘사는 막는다", BM_A, _line(2, "img", "a wombat with a bloody wound on a rock"), "잔혹"),
    ("성적인 말은 막는다", BM_B, _line(3, "sub", "섹시한 펭귄"), "성적인"),
    ("외모 비하는 막는다", BM_B, _line(3, "sub", "뚱뚱해서 안 움직임"), "외모"),
    ("따라 하면 위험한 것(집에서 해 봐)은 막는다", BM_A, _line(2, "sub", "집에서 해 보면 앎"), "위험"),
    ("지하철 노선 이름은 막는다", BM_B, _line(0, "sub", "2호선 펭귄들의 출근"), "노선"),
    ("그림에 글자(sign)는 막는다", BM_B, _line(0, "img", BM_B["lines"][0]["img"] + ", a station sign"), "img"),
    ("B 그림에 사람(passengers)은 막는다", BM_B, _line(3, "img", BM_B["lines"][3]["img"] + ", human passengers behind"), "사람"),
    ("B 그림에 같은 동물 묘사가 없으면 막는다", BM_B, _line(5, "img", "a penguin sitting alone in an empty bright subway car"), "animal"),
    ("B 동물 한마디는 사건 바로 다음(순서 어기면 막음)", BM_B, lambda x: x["lines"].insert(4, x["lines"].pop(3)), "바로 다음"),
    ("B 한마디 빠르기 -10~-35 밖이면 막는다", BM_B, _line(4, "rate", -50), "rate"),
    ("B 진짜 동물 사실(fact)이 없으면 막는다", BM_B, lambda x: [ln.update(type="beat") for ln in x["lines"] if ln["type"] == "fact"], "fact"),
    ("병맛 날이 아니면(10/24) 막는다", BM_A, lambda x: x.update(date="2026-10-24"), "병맛 편이 없는 날"),
    ("그날 꼴이 아니면(10/26 에 A) 막는다", BM_A, lambda x: x.update(date="2026-10-26"), "병맛 꼴은"),
    ("햄스터 + 사무실·출근(김햄찌와 겹침)은 막는다", BM_B, lambda x: x.update(animal_ko="햄스터"), "햄스터"),
]
for name, base, f, want in CASES_BM:
    errs = bm_bad(base, f)
    ck(name, any(want in e for e in errs), errs)
ck("만·억이 붙은 수는 곱한 값으로만 맞춰 본다(병맛: 100만 ≠ 100 · 21마리 = 21)", B.unbacked("100만 개 · 21마리", [100.0, 21.0]) == ["100만"]
   and B.unbacked("430만", [4.3e6]) == [])
long_a = json.loads(json.dumps(BM_A))
for ln in long_a["lines"]:                                 # 줄마다 30자 가까이 — 어림 25초+
    ln["say"] = (ln["say"].rstrip(".") + " 그리고 이건 아주 진지한 이야기임.")[:32]
ck("길이 어림이 23초를 크게 넘으면 막는다", any("길이 어림" in e for e in K.check(long_a)), K.check(long_a))
short_b = json.loads(json.dumps(BM_B))
for ln in short_b["lines"]:
    ln["say"] = {"hook": "월요일.", "fact": "21마리.", "incident": "안 움직임.", "quote": "…네.", "punch": "종점."}.get(ln["type"], ln["say"])
short_b["lines"][2]["say"] = "30초, 60초."
ck("길이 어림이 너무 짧으면 막는다(18초 - 3)", any("길이 어림" in e for e in K.check(short_b)), K.check(short_b))

print("── 병맛 시간표·소리(0초 말 · 멈춤·무음 · 띠용 · 목소리 바꾸기) ──")
for name, s in (("A 웜뱃", BM_A), ("B 펭귄", BM_B)):
    segs, ev = B.plan(s, B.est_durations(s))
    total = B.total_of(segs)
    lo, hi = P.BM_SEC[s["kind"]]
    gaps = all(abs(a["start"] + a["dur"] - b["start"]) < 1e-6 for a, b in zip(segs, segs[1:]))
    ck(f"{name}: 첫 말 0.0초(hook) · 장면 빈틈 없음 · 길이 {lo:g}~{hi:g}초 · 줄마다 말 하나", ev["voices"][0]["at"] == 0.0
       and ev["voices"][0]["k"] == 0 and segs[0]["start"] == 0.0 and gaps and lo <= total <= hi
       and [v["k"] for v in ev["voices"]] == list(range(len(s["lines"]))), (total, gaps))
    names = [n for n, _ in ev["sfx"]]
    ck(f"{name}: 0초 펑(펀치 줌) · 끝 띠용 + 흔들림", ("pop", 0.0) in ev["sfx"] and names.count("boing") == 1
       and ev["shake"] == [t for n, t in ev["sfx"] if n == "boing"])
    off = ev["bed_off"][0][0]
    ck(f"{name}: 배경음은 무음 구간부터 끈다 · 그 뒤 말은 펀치·한마디뿐", len(ev["bed_off"]) == 1
       and all(v["k"] >= len(s["lines"]) - (1 if s["kind"] == "bm_paper" else 2) for v in ev["voices"] if v["at"] >= off))
    if s["kind"] == "bm_paper":
        fz = next(x for x in segs if x["kind"] == "freeze")
        bo = next(x for x in segs if x["kind"] == "boing")
        st = next(x for x in segs if x["kind"] == "stamp")
        quiet = [v for v in ev["voices"] if v["at"] < fz["start"] + fz["dur"] and v["at"] + v["dur"] > fz["start"] + 1e-6]
        ck("A: 펀치 뒤 0.4초 멈춤(그림 고정 hold)·무음(말·효과음 없음) → 띠용", abs(fz["dur"] - 0.4) < 1e-9 and fz["hold"] is not None
           and not quiet and not [t for _, t in ev["sfx"] if fz["start"] <= t < fz["start"] + fz["dur"]]
           and bo["start"] == round(fz["start"] + fz["dur"], 3) and ("boing", bo["start"]) in ev["sfx"]
           and off == fz["start"])
        ck("A: 도장 — 쿵(thump)과 하얀 번쩍이 같은 시각 · 말은 그 뒤", [t for n, t in ev["sfx"] if n == "thump"] == ev["flash"]
           and len(ev["flash"]) == 1 and st["start"] < ev["flash"][0] < ev["voices"][st["k"]]["at"])
        ck("A: 목소리는 전부 F1(정색 여자 목소리 하나)", {v["who"] for v in ev["voices"]} == {"f1"})
    else:
        sl = next(x for x in segs if x["kind"] == "silence")
        q = next(v for v in ev["voices"] if v["who"] == "quote")
        quiet = [v for v in ev["voices"] if v["at"] < sl["start"] + sl["dur"] and v["at"] + v["dur"] > sl["start"] + 1e-6]
        ck("B: 사건 뒤 0.5초 무음(말 없음·배경음 끔·그림 고정) → 동물 한마디", abs(sl["dur"] - 0.5) < 1e-9 and not quiet
           and sl["hold"] is not None and q["at"] >= sl["start"] + sl["dur"] and off == sl["start"])
        ck("B: 목소리 바꾸기 — 한마디만 'quote'(edge InJoon, 느리게) · 나머지 F1", [v["who"] for v in ev["voices"]].count("quote") == 1
           and q["rate"] == -25 and B.QUOTE_VOICE == "ko-KR-InJoonNeural" and B.QUOTE_RATE == (-35, -10)
           and all(v["who"] == "f1" for v in ev["voices"] if v is not q))
        ck("B: 끝 카드에서 띠용", segs[-1]["kind"] == "end" and ("boing", segs[-1]["start"]) in ev["sfx"])
ck("소리는 코드로 만든다(펑·쿵·띠용 — 길이·크기)", all(0.1 < len(B.SFX[n]()) / R.SR < 1.0 and float(abs(B.SFX[n]()).max()) > 0.1
                                          for n in ("pop", "thump", "boing")))
src = open(os.path.join(HERE, "bm_reel.py"), encoding="utf-8").read()
ck("한마디 목소리: edge-tts InJoon --rate · 막히면 Supertonic M1(다른 목소리 유지) · 내레이션은 R.synth F1", "--rate=" in src
   and "QUOTE_FALLBACK = \"M1\"" in src and "R.synth(f1, wd, False, tempo=TEMPO)" in src)

print("── 병맛 화면(가짜 그림) — 1080×1920 · 아래 25% 비움 · 첫 화면 밝게 ──")
A_NEXT = dict(json.loads(json.dumps(BM_A)), next="고양이 액체설")
from PIL import ImageChops, ImageOps  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    for name, s in (("A 웜뱃", BM_A), ("A 웜뱃 + 다음 카드", A_NEXT), ("B 펭귄", BM_B)):
        a = B.assets(s, tmp, True)
        segs, ev = B.plan(s, B.est_durations(s))
        B.pad_to(segs, P.BM_SEC[s["kind"]][0])
        pa = B.Painter(s, a, segs, ev)
        kinds = sorted({x["kind"] for x in segs})
        times = [0.0] + [x["start"] + x["dur"] * f for x in segs for f in (0.02, 0.3, 0.97)] + ev["flash"] + \
            [t + 0.05 for t in ev["shake"]]
        sizes, low, top = True, [], []
        for t in times:
            fr, bg_ = pa.frame(t), pa.bg_at(t)
            sizes &= fr.size == (K.W, K.H)
            bb = ImageChops.difference(fr, bg_).getbbox()
            low.append(bb[3] if bb else 0)
            top.append(bool(ImageChops.difference(fr.crop((0, 120, K.W, 420)), bg_.crop((0, 120, K.W, 420))).getbbox()))
        ck(f"{name}: 장면 전부({', '.join(kinds)} · {len(times)}장) 1080×1920", sizes)
        ck(f"{name}: 아래 25%(y 1440~)엔 아무것도 그리지 않는다(흔들림·번쩍 때도)", max(low) <= 1440, max(low))
        ck(f"{name}: 제목은 처음부터 끝까지 위에(끝 카드 빼고)", all(tp for tp, t in zip(top, times) if pa.seg_at(t)["kind"] != "end"))
        f0 = pa.frame(0.0)
        ck(f"{name}: 첫 프레임(0.0초)에 큰 제목이 이미 있다", bool(ImageChops.difference(f0.crop((0, 250, K.W, 560)),
                                                                        pa.bg_at(0.0).crop((0, 250, K.W, 560))).getbbox()))
        if "next" in s:
            en = next(x for x in segs if x["kind"] == "end")
            ck(f"{name}: '다음 편' 끝 카드가 그려진다", bool(ImageChops.difference(pa.frame(en["start"] + 0.6), pa.bg_at(en["start"] + 0.6)).getbbox()))
        cv = B.cover_of(pa)
        ck(f"{name}: 커버 = 첫 장면(제목 자리 잡은 뒤) 1080×1920", cv.size == (K.W, K.H)
           and not ImageChops.difference(cv, pa.frame(B.COVER_T)).getbbox())
        sheet = os.path.join(tmp, f"sheet_{s['kind']}.jpg")
        B.contact_sheet(pa, segs, sheet)
        ck(f"{name}: 한눈에 보기(첫 프레임 + 장면마다)", os.path.getsize(sheet) > 10000 and len(B.sheet_times(segs)) >= 8)
    from PIL import Image as _I  # noqa: E402
    im = _I.new("RGB", (64, 112), (40, 40, 40))
    for y in range(112):
        for x in range(64):
            im.putpixel((x, y), (20 + x, 18 + y // 2, 30))
    g0 = sum(ImageOps.grayscale(im).getdata()) / (64 * 112)
    g1 = sum(ImageOps.grayscale(B.brighten(im)).getdata()) / (64 * 112)
    ck("어두운 그림은 밝게 끌어올린다(10/14 sci 교훈: 평균 밝기 128 근처로)", g0 < 70 and 115 <= g1 <= 150, (round(g0), round(g1)))

print("── 병맛 캡션·문서 ──")
for s in (BM_A, BM_B):
    cap = K.caption_of(s)
    ls_ = cap.split("\n")
    ck(f"{s['kind']}: 캡션 = 한 줄 → 출처: 도메인 → 해시태그(≤5) · 회차·열린 질문·부탁 없음",
       ls_[0] == s["caption"] and cap.count("출처: ") == 1 and all(h in cap for h in B.source_hosts(s))
       and len(TAG.findall(cap)) <= 5 and "오늘의 골라보기" not in cap and not any(w in cap for w in ("댓글", "공유", "저장", "팔로우"))
       and cap.index("출처:") < cap.index("#"), cap)
ck("A 캡션 출처: labonline.com.au · physicsworld.com · smithsonianmag.com", "출처: labonline.com.au · physicsworld.com · smithsonianmag.com"
   in K.caption_of(BM_A), K.caption_of(BM_A))
wb = open(os.path.join(HERE, "BM_WRITING.md"), encoding="utf-8").read()
ck("BM_WRITING: 두 꼴·견본·facts·부탁 금지·브레인롯·animal 복사·띠용·0.5초 무음",
   all(w in wb for w in ("bm_paper", "bm_animal", "bm_paper_wombat", "bm_catalog.json", "src_n", "facts", "부탁", "브레인롯", "animal", "띠용", "0.5초",
                         "check", "due: false")))
ck("PICK_WRITING: 병맛 날은 BM_WRITING 을 따른다 · next 의 writing", "BM_WRITING.md" in wr and "writing" in wr)

print("── sci 끝없이(open_plan · 11/08~) · 뜯어보기(11/10~ 화·금) ──")
import contextlib  # noqa: E402
import copy  # noqa: E402

EXTRA_REAL = json.load(open(P.SCI_EXTRA, encoding="utf-8"))
SHORTS_REAL = json.load(open(P.SHORTS, encoding="utf-8"))


def stub(n, frm, series=None, slug=None):
    """시험용 가짜 항목(파일에 안 남는다) — entry_errs 를 통과하는 모양 · 숫자는 facts 에."""
    e = {"n": n, "slug": slug or f"stub-{n}", "format": "survival", "look": "earth", "title_idea": f"Stub {n}",
         "situation": "STUB", "teaser": "STUB", "sources": [f"https://example.org/stub-{n}-a", f"https://example.org/stub-{n}-b"],
         "facts": [{"fact": "Stub: the magnetron makes waves at 2.45 GHz.", "src": 0, "evidence": "stub 2.45 GHz"},
                   {"fact": "Stub: the waves bounce off the metal walls.", "src": 0, "evidence": "stub walls"},
                   {"fact": "Stub: the turntable turns about 5 times a minute.", "src": 1, "evidence": "stub 5 times"}],
         "beat_ideas": [{"t": "--:--", "what": "waves at 2.45 GHz", "fact": 0, "view": "cutaway"},
                        {"t": "--:--", "what": "waves bounce off the walls", "fact": 1, "view": "cutaway"},
                        {"t": "--:--", "what": "turntable turns 5 times a minute", "fact": 2, "view": "cutaway"}],
         "odds_idea": None, "careful": ["stub — 시험용"]}
    if frm:
        e["from"] = frm
    if series:
        e["series"] = series
    return e


@contextlib.contextmanager
def pools(extra=(), teardown=None, shorts=()):
    """열린 항목만 바꿔 끼운다 — extra(sci_extra 에 더할 것) · teardown(뜯어보기 catalog, None = 파일 없음) · shorts(insta_from 단 것)."""
    with tempfile.TemporaryDirectory() as td:
        ex = copy.deepcopy(EXTRA_REAL)
        ex["survival"] = [e for e in ex["survival"] if e["n"] in P.SCI_ORDER] + list(extra)
        ex["compare"] = [e for e in ex["compare"] if e["n"] in P.SCI_ORDER]
        sh = copy.deepcopy(SHORTS_REAL)
        sh["survival"] = [e for e in sh["survival"] if e["n"] in P.SCI_ORDER] + list(shorts)
        sh["compare"] = [e for e in sh["compare"] if e["n"] in P.SCI_ORDER]
        paths = {"extra": os.path.join(td, "x.json"), "shorts": os.path.join(td, "s.json"), "teardown": os.path.join(td, "t.json")}
        json.dump(ex, open(paths["extra"], "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(sh, open(paths["shorts"], "w", encoding="utf-8"), ensure_ascii=False)
        if teardown is not None:
            json.dump({"about": "stub", "survival": list(teardown)}, open(paths["teardown"], "w", encoding="utf-8"), ensure_ascii=False)
        with P.catalogs(**paths):
            yield


DAYS = [P.SCI_FROM + dt.timedelta(days=k) for k in range(90)]          # 10/15 ~ 1/12


def table():
    return {d: tuple(P.kind_for(d, sl) for sl in P.slots_on(d)) for d in DAYS}


def picks_ok():
    """골라보기 로테이션·회차가 끊기지도 겹치지도 않는다(sci 가 끊겼다 이어져도)."""
    pk = [(d, sl, P.kind_for(d, sl)) for d in (P.START + dt.timedelta(days=k) for k in range(120)) for sl in P.slots_on(d)]
    pk = [(d, sl, k) for d, sl, k in pk if P.is_pick(k)]
    return ([k for _, _, k in pk] == [P.FORMATS[i % 5] for i in range(len(pk))]
            and [P.series_no(d, sl) for d, sl, _ in pk] == list(range(1, len(pk) + 1)))


def sci_ns():
    return [P.sci_n(d) for d in DAYS if P.sci_n(d) is not None]


ck("SCI_TO 는 끝이 아니다: 열린 편성은 SCI_OPEN_FROM(11/08)부터 · 뜯어보기는 11/09 주 화·금 · 번호 904~ · 951~",
   P.SCI_OPEN_FROM == D(11, 8) and P.TEARDOWN_FROM == D(11, 9) and P.TEARDOWN_DAYS == (1, 4)
   and P.SCI_OPEN_N0 == 904 and P.TEARDOWN_N0 == 951 and P.TEARDOWN_SERIES == "과학으로 뜯어보는 물건")
with pools():
    base = table()
    ck("열린 항목이 없으면: 11/08 부터 sci 없음 = 예전 SCI_TO 뒤 그대로(골라보기 두 편) · open_plan 빈 것",
       P.open_plan() == {} and all(P.SCI not in base[d] and len(base[d]) == 2 for d in DAYS if d > P.SCI_TO)
       and base[D(11, 8)] == ("birth", "pick"), base[D(11, 8)])
    rw = {r["id"]: r for r in P.runway(D(10, 25))}
    ck("runway(10/25): sci 마지막 11/07 · 14편(오늘 포함) · 뜯어보기 0 · 병맛 시험 11/07(판정 11/08) · 골라보기 끝없음",
       (rw["insta_sci"]["last"], rw["insta_sci"]["left"], rw["insta_teardown"]["last"], rw["insta_teardown"]["left"],
        rw["insta_bm"]["last"], rw["insta_bm"]["judge"], rw["insta_pick"]["limit"])
       == (D(11, 7), 14, None, 0, D(11, 7), D(11, 8), "open"), rw)
    ck("runway(11/20 · 바닥난 뒤): sci 남은 0 · 채우는 곳 sci_extra.json · from 은 다음 날 이후",
       P.runway(D(11, 20))[1]["left"] == 0 and "sci_extra.json" in P.runway(D(11, 20))[1]["refill"]
       and "2026-11-21" in P.runway(D(11, 20))[1]["refill"])
with pools(extra=[stub(904, "2026-10-26"), stub(905, "2026-11-01"), stub(906, "2026-11-20")]):
    t = table()
    ck("열린 항목 셋: 11/08 904(저녁) · 11/09 905(낮) · 906 은 from 11/20 부터(그 사이는 골라보기 두 편)",
       [(d, P.sci_n(d), P.sci_slot(d)) for d in P.open_plan()] == [(D(11, 8), 904, "b"), (D(11, 9), 905, "a"), (D(11, 20), 906, "b")]
       and all(P.SCI not in t[d] for d in DAYS if D(11, 10) <= d <= D(11, 19)), sorted(P.open_plan().items()))
    ck("sci 자리는 날짜로 번갈아(끊겼다 이어져도) · 하루 sci 는 많아야 한 편 · slot_of 는 하나로",
       all(P.sci_slot(d) == ("b" if (d - P.SCI_FROM).days % 2 == 0 else "a") for d in P.open_plan())
       and all(t[d].count(P.SCI) <= 1 for d in DAYS) and all(P.slot_of(d, k) == sl for d in DAYS
                                                             for sl, k in zip(P.slots_on(d), t[d])))
    ck("src_n 은 한 번씩만(SCI_ORDER 24 + 열린 3 · 겹침 없음) · sci_no 는 이어 센다(11/08 = 25번째)",
       len(sci_ns()) == len(set(sci_ns())) == 27 and P.sci_index(D(11, 8)) == 24 and P.sci_index(D(11, 20)) == 26)
    ck("골라보기 로테이션·회차는 sci 가 끊겼다 이어져도 빈틈·겹침 없음(1/12 까지)", picks_ok())
    ck("11/07 까지(SCI_ORDER · 병맛 · 회차)는 열린 항목이 있어도 그대로", all(t[d] == base[d] for d in DAYS if d <= P.SCI_TO))
    rw = {r["id"]: r for r in P.runway(D(10, 25))}
    ck("runway: sci 마지막 = 열린 항목 마지막 날(11/20) · 17편", (rw["insta_sci"]["last"], rw["insta_sci"]["left"]) == (D(11, 20), 17), rw["insta_sci"])
    ck("바닥나면(11/21~) 다시 골라보기 두 편 · runway 0", all(P.SCI not in t[d] for d in DAYS if d > D(11, 20))
       and P.runway(D(11, 21))[1]["left"] == 0)
    with tempfile.TemporaryDirectory() as tmp:
        ni = P.next_info(D(11, 8), tmp, now=KST_AT(D(11, 8), 19))
        ck("next 11/08 19시: sci 904 · entry 그대로 · sci_no 25 · 속이 보이는 과학(xray 견본) · 회차 없음",
           (ni["kind"], ni["slot"], ni["src_n"], ni["sci_no"], ni["series"], ni["exemplar"], ni["series_no"])
           == ("sci", "b", 904, 25, "속이 보이는 과학", P.SCI_XRAY_EXEMPLAR, None) and ni["entry"]["facts"] == stub(904, "")["facts"], ni)
        ni = P.next_info(D(11, 8), tmp, now=KST_AT(D(11, 8), 11))
        ck("next 11/08 11시: 낮 편은 골라보기(태어난 달 #20)", (ni["kind"], ni["series_no"]) == ("birth", 20), ni.get("kind"))
before = None
with pools(extra=[stub(904, "2026-10-26"), stub(905, "2026-11-01")]):
    before = table()
with pools(extra=[stub(904, "2026-10-26"), stub(905, "2026-11-01"), stub(906, "2026-11-25")]):
    after = table()
ck("지난 편성은 안 바뀐다: 바닥난 뒤(11/10~) 붙인 항목이 from(11/25)을 달면 그 전 날 편성·회차는 그대로 · 11/25 부터 sci",
   all(before[d] == after[d] for d in DAYS if d < D(11, 25)) and P.SCI in after[D(11, 25)] and P.SCI not in before[D(11, 25)])
with pools(extra=[stub(904, None), stub(905, "2026-11-08")], shorts=[dict(stub(115, None), insta_from="2026-11-09"),
                                                                   stub(116, None)]):
    un = P.open_pools()["unscheduled"]
    ck("from 없는 항목(904)은 편성 안 함 · shorts_catalog 는 insta_from 단 것(115)만 · 안 단 것(116)은 '안 씀'으로 남는다",
       [P.open_plan()[d][1] for d in sorted(P.open_plan())] == [905, 115] and un == {"no_from": [904], "shorts_unused": [116]}, un)
    ck("runway 가 알린다: from 없는 항목 · shorts 안 쓴 항목", "904" in P.runway(D(10, 25))[1]["note"]
       and "insta_from" in P.runway(D(10, 25))[1]["note"], P.runway(D(10, 25))[1]["note"])
    ck("SCI_ORDER 항목은 from 을 달아도 다시 안 쓴다(반복 없음)", 101 not in [n for _, n in P.open_plan().values()])

TD = [stub(951, "2026-11-09", "teardown", "microwave-inside"), stub(952, "2026-11-09", "teardown", "fridge-inside")]
with pools(teardown=TD):
    plan = P.open_plan()
    ck("뜯어보기만(보통 sci 없음): 11/10(화) 951 저녁 · 11/13(금) 952 낮 — 화·금만 · 다른 날은 골라보기 두 편",
       sorted((d, x, P.sci_slot(d)) for d, x in plan.items()) == [(D(11, 10), ("teardown", 951), "b"), (D(11, 13), ("teardown", 952), "a")]
       and P.is_teardown_day(D(11, 10)) and P.is_teardown_day(D(11, 13)) and not P.is_teardown_day(D(11, 9))
       and not P.is_teardown_day(D(11, 6)), plan)
    ck("뜯어보기 편도 kind sci · series teardown · teardown_index 0·1 · sci_entry 가 teardown_catalog 도 찾는다",
       P.kind_for(D(11, 10), "b") == P.SCI and P.sci_series(D(11, 10)) == P.TEARDOWN and P.teardown_index(D(11, 13)) == 1
       and P.sci_entry(951)["slug"] == "microwave-inside" and P.is_teardown_entry(P.sci_entry(951)))
    ck("뜯어보기가 바닥나면(11/17 화) 그날도 보통 sci → 그것도 없으면 골라보기 두 편",
       P.sci_slot(D(11, 17)) is None and len(table()[D(11, 17)]) == 2)
    with tempfile.TemporaryDirectory() as tmp:
        ni = P.next_info(D(11, 10), tmp, now=KST_AT(D(11, 10), 19))
        ck("next 11/10 19시: sci 951 · series '과학으로 뜯어보는 물건' · series_id teardown · 1번째 · entry.series · SCI_WRITING · xray 견본",
           (ni["kind"], ni["src_n"], ni["series"], ni["series_id"], ni["teardown_no"], ni["entry"].get("series"), ni["writing"],
            ni["exemplar"]) == ("sci", 951, "과학으로 뜯어보는 물건", "teardown", 1, "teardown", "insta/SCI_WRITING.md",
                                P.SCI_XRAY_EXEMPLAR) and "cutaway" in ni["views_hint"] and ni["keywords"] == list(P.TEARDOWN_KEYWORDS), ni)
    rw = {r["id"]: r for r in P.runway(D(10, 25))}
    ck("runway: 뜯어보기 마지막 11/13 · 2편 · 보통 sci 는 11/07", (rw["insta_teardown"]["last"], rw["insta_teardown"]["left"],
                                                     rw["insta_sci"]["last"]) == (D(11, 13), 2, D(11, 7)), rw["insta_teardown"])
REG = [stub(n, "2026-11-08") for n in range(904, 910)]
with pools(extra=REG, teardown=TD[:1]):
    seq = [(d, P.open_plan()[d]) for d in sorted(P.open_plan())]
    ck("보통 sci + 뜯어보기: 11/08 904 · 11/09 905 · 11/10(화) 뜯어보기 951 · 11/11 906 · 11/12 907 · 11/13(금 · 뜯어보기 바닥) 보통 908 · 11/14 909",
       seq == [(D(11, 8), ("sci", 904)), (D(11, 9), ("sci", 905)), (D(11, 10), ("teardown", 951)), (D(11, 11), ("sci", 906)),
               (D(11, 12), ("sci", 907)), (D(11, 13), ("sci", 908)), (D(11, 14), ("sci", 909))], seq)
    ck("뜯어보기는 화·금에만 · 보통 sci 는 다른 날(뜯어보기가 있을 때) · 반복 없음 · 골라보기 빈틈 없음",
       all(d.weekday() in P.TEARDOWN_DAYS for d, (k, _) in seq if k == "teardown") and len(sci_ns()) == len(set(sci_ns())) and picks_ok())
with pools(extra=REG[:3]):
    ck("뜯어보기 catalog 가 없으면(파일 없음) 화·금도 보통 sci — 11/10 은 906", P.sci_series(D(11, 10)) == P.SCI and P.sci_n(D(11, 10)) == 906
       and P.open_pools()[P.TEARDOWN] == [])
bm_ref = {d: (P.bm_kind(d), P.bm_slot(d), P.bm_n(d)) for d in BMWIN}
with pools(extra=REG, teardown=TD):
    bm_t = {d: (P.bm_kind(d), P.bm_slot(d), P.bm_n(d)) for d in BMWIN}
    ck("병맛 시험은 그대로(10/25~11/07 · ABBA · 401~414 · 11/08 끝)", bm_t == bm_ref
       and "".join("A" if P.bm_kind(d) == "bm_paper" else "B" for d in BMWIN) == "ABBAABBAABBAAB"
       and [P.bm_n(d) for d in BMWIN] == list(P.BM_ORDER) and P.bm_kind(D(11, 8)) is None and P.BM_TO == D(11, 7))
    ck("SCI_XRAY_FROM 그대로(10/25~ 속이 보이는 과학 · 뜯어보기도 그 모양)", P.SCI_XRAY_FROM == D(10, 25) and P.sci_xray(D(11, 10)))

print("── 뜯어보기 대본 검사(속이 보이는 과학 모양 + 상표·따라 하기·안전 단정 금지) ──")
TDS = {"date": "2026-11-10", "kind": "sci", "src_n": 951, "slug": "microwave-inside",
       "hook": ["전자레인지 속", "뭐가 돌아갈까?"], "say_intro": "전자레인지 문을 닫으면, 안에선 무슨 일이 생길까요?",
       "why": {"sub": "부품 셋이 같이 일해요", "say": "왜 데워질까요?", "view": "cutaway",
               "img": "a kitchen microwave oven with the outer shell cut open to reveal the inner parts"},
       "beats": [{"big": "2.45GHz", "sub": "전파를 만드는 곳", "say": "마그네트론이 2.45기가헤르츠 전파를 만들어요.", "src": 0,
                  "view": "cutaway", "img": "a microwave oven cut open showing a small cylindrical magnetron at the side",
                  "label": "마그네트론", "pin": [0.5, 0.45]},
                 {"big": "반사", "sub": "금속 벽", "say": "전파는 금속 벽에 부딪히며 안을 돌아요.", "src": 0, "view": "cutaway",
                  "img": "a microwave oven sliced open like a cake showing glowing waves bouncing between metal walls"},
                 {"big": "분당 5바퀴", "sub": "돌림판", "say": "돌림판은 분당 5바퀴쯤 돌아요.", "src": 1, "view": "cutaway",
                  "img": "a microwave oven cut open showing a round glass turntable with a bowl in the center",
                  "label": "돌림판", "pin": [0.5, 0.6]}],
       "verdict": {"big": "골고루 데움", "say": "그래서 음식이 골고루 데워져요."},
       "caption": "전자레인지 속, 뭐가 돌아갈까? 🔬", "hashtags": ["#과학으로뜯어보는물건", "#작동원리"],
       "sources": TD[0]["sources"], "bench": {"format": "3D 단면 해설 — 대조 훅 → 왜? → 원인 3단계 → 결과"}}
with pools(teardown=TD):
    ck("뜯어보기 대본(11/10 · 951) 통과 · 첫 장면 칩은 '과학으로 뜯어보는 물건' · 끝 질문은 부품", K.check(TDS) == []
       and X.series_of(TDS) == P.TEARDOWN_SERIES and K.ask_of(TDS) == K.ASK["sci"]["teardown"] == "어느 부품이 제일 의외였어요?"
       and K.ASK["sci"]["teardown"] in K.caption_of(TDS) and X.series_of(XS) == X.SERIES, K.check(TDS))
    for name, f, want in [
        ("상표 이름(한글)은 막는다", _set(["say_intro"], "삼성 전자레인지 문을 닫으면, 안에선 무슨 일이 생길까요?"), "상표"),
        ("상표 이름(그림 묘사 · 영어)도 막는다", _set(["why", "img"], "a samsung microwave oven with the outer shell cut open"), "상표"),
        ("'직접 열어 보세요'는 막는다", _set(["verdict", "say"], "궁금하면 직접 열어 보세요."), "따라 하게"),
        ("안전·건강 단정은 막는다", _set(["verdict", "say"], "그래서 전자레인지는 안전해요."), "안전"),
        ("숫자는 그 항목 facts 에서만(3GHz → 막음)", _set(["beats", 0, "big"], "3GHz"), "facts"),
        ("src_n 이 그날 뜯어보기 항목이 아니면 막는다", _set(["src_n"], 952), "src_n")]:
        x = json.loads(json.dumps(TDS))
        f(x)
        errs = K.check(x)
        ck(name, any(want in e for e in errs), errs)
    ck("'파인애플'의 애플은 상표가 아니다 · 보통 sci 대본엔 뜯어보기 금지를 안 건다", K.brand_hits(["파인애플 단면"]) == []
       and K.brand_hits(["애플 이어폰", "a Dyson fan"]) == ["dyson", "애플"]
       and not any("뜯어보기" in e for e in xbad(_set(["verdict", "say"], "그래서 안전해요."))))
ck("catalog 항목 검사(entry_errs): 시험용 항목 통과 · from 없음 · evidence 없음 · 상표 · facts 에 없는 숫자 · series 없음을 잡는다",
   K.entry_errs(TD[0]) == [] and any("from" in e for e in K.entry_errs(stub(951, None, "teardown")))
   and any("evidence" in e for e in K.entry_errs(dict(TD[0], facts=[{k: v for k, v in f.items() if k != "evidence"}
                                                                    for f in TD[0]["facts"]])))
   and any("상표" in e for e in K.entry_errs(dict(TD[0], title_idea="Inside a Dyson Fan")))
   and any("facts 에 없다" in e for e in K.entry_errs(dict(TD[0], beat_ideas=[dict(TD[0]["beat_ideas"][0], what="9 GHz")] * 3)))
   and any("series" in e for e in K.entry_errs({k: v for k, v in TD[0].items() if k != "series"} | {"n": 960})))

print("── 지금 catalog(sci_extra 904~ · teardown_catalog) — 모양·출처·from·반복 없음 ──")
OPEN_X = [e for e in P.catalog_entries(EXTRA_REAL) if e["n"] not in P.SCI_ORDER]
TD_REAL = P.catalog_entries(P._read(P.TEARDOWN_CATALOG))
ck("sci_extra 의 새 항목(904~)은 전부 catalog 검사 통과(from 포함)", all(K.entry_errs(e) == [] for e in OPEN_X),
   {e["n"]: K.entry_errs(e) for e in OPEN_X if K.entry_errs(e)})
ck("teardown_catalog(없어도 된다): 항목마다 검사 통과 · n 951~ · series teardown · from ≥ 11/09 · slug·n 겹침 없음",
   all(K.entry_errs(e) == [] and P._date_or_none(e.get("from")) >= P.TEARDOWN_FROM for e in TD_REAL)
   and len({e["n"] for e in TD_REAL}) == len({e["slug"] for e in TD_REAL}) == len(TD_REAL),
   {e.get("n"): K.entry_errs(e) for e in TD_REAL if K.entry_errs(e)})
live = [P.sci_n(d) for d in (P.SCI_FROM + dt.timedelta(days=k) for k in range(400)) if P.sci_n(d) is not None]
ck("지금 catalog 로 400일: src_n 반복 없음 · 편성 안 된 항목 없음(from 빠짐) · 골라보기 빈틈 없음",
   len(live) == len(set(live)) and P.open_pools()["unscheduled"]["no_from"] == [] and picks_ok(),
   P.open_pools()["unscheduled"])
wsci = open(os.path.join(HERE, "SCI_WRITING.md"), encoding="utf-8").read()
ck("SCI_WRITING: 뜯어보기 — 상표·모델 금지 · 직접 열어 보세요 금지 · 안전·건강 단정 금지 · 숫자는 facts · label 은 부품 · from",
   all(w in wsci for w in ("과학으로 뜯어보는 물건", "teardown_catalog.json", "상표·모델 이름 금지", "직접 열어 보세요", "안전·건강 단정 금지",
                           "facts", "부품 이름", "cutaway", "from")))

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
