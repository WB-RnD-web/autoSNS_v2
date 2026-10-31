#!/usr/bin/env python3
"""밤 편(c) '심해 직장인'(worker) · '위험한 진짜 이유'(danger) 테스트 — 편성·catalog·검사·캡션·mock 렌더 (2026-10-31).

    python insta/test_bc.py          # 네트워크·Spark 없이(렌더는 --mock 그림) · ffmpeg 필요
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bc_kit as B  # noqa: E402
import danger_reel as DR  # noqa: E402
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402
import pick_threads as T  # noqa: E402
import worker_reel as WR  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {str(detail)[:600]}"))
    if not cond:
        FAIL += 1


D = lambda m, d, y=2026: dt.date(y, m, d)  # noqa: E731
KST_AT = lambda d, h, mi=0: dt.datetime(d.year, d.month, d.day, h, mi, tzinfo=P.KST)  # noqa: E731
SW = json.load(open(os.path.join(HERE, "samples", "worker_monday-9am.json"), encoding="utf-8"))
SD = json.load(open(os.path.join(HERE, "samples", "danger_jellyfish-sleep.json"), encoding="utf-8"))
WE, DE = P.c_entries(P.WORKER), P.c_entries(P.DANGER)

print("── catalog ──")
ck("worker 14편 이상 · 번호 501 부터 빈틈없이 · slug 겹침 없음", len(WE) >= 14 and [e["n"] for e in WE] == list(range(501, 501 + len(WE)))
   and len({e["slug"] for e in WE}) == len(WE), [e.get("n") for e in WE])
ck("danger 14편 이상 · 번호 601 부터 빈틈없이 · slug 겹침 없음", len(DE) >= 14 and [e["n"] for e in DE] == list(range(601, 601 + len(DE)))
   and len({e["slug"] for e in DE}) == len(DE), [e.get("n") for e in DE])
ck("항목 검사(facts·src·evidence·https·careful·from·그림 묘사·숫자) 전부 통과",
   not [x for e in WE for x in WR.entry_errs(e)] and not [x for e in DE for x in DR.entry_errs(e)],
   [x for e in WE for x in WR.entry_errs(e)] + [x for e in DE for x in DR.entry_errs(e)])


def _nums(t: str) -> set:
    return {x.replace(",", "") for x in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}


def _fact_nums_in_evidence(e: dict) -> list:
    """fact 의 숫자는 원문 문장(evidence)에 있어야 한다 — '(… converted)'·'(… rounded)' 괄호 안 환산값은 뺀다."""
    bad = []
    for f in e["facts"]:
        core = re.sub(r"\([^()]*(?:converted|rounded)[^()]*\)", "", f["fact"])
        miss = _nums(core) - _nums(f["evidence"])
        if miss:
            bad.append((e["n"], sorted(miss), f["fact"][:80]))
    return bad


ck("facts 숫자는 evidence(원문 문장)에 있다(환산값은 'converted' 표시)", not [b for e in WE + DE for b in _fact_nums_in_evidence(e)],
   [b for e in WE + DE for b in _fact_nums_in_evidence(e)])
ck("캐릭터 고정 묘사: 기준 프롬프트·seed·편집 앞말 · 잔망루피 막는 말(fish·tail fin·instead of legs)",
   all(w in P.c_catalog(P.WORKER)["character"]["master_prompt"] for w in ("fish", "tail fin", "instead of legs", "necktie", "lanyard"))
   and isinstance(P.c_catalog(P.WORKER)["character"]["master_seed"], int)
   and P.c_catalog(P.WORKER)["character"]["keep_prefix"].startswith("Keep the exact same blobfish"))
ck("그림 한계 항목은 image_note 가 있다(해파리 601 — 화면은 일반 해파리)", "거꾸로해파리" in P.c_entry(601)["image_note"])
ck("카메오 동료는 심해 생물로 · look(영어) 있음", all(e["cameo"] is None or (e["cameo"]["look"] and e["cameo"]["animal_ko"]) for e in WE)
   and sum(1 for e in WE if e["cameo"]) >= 8)

print("── 편성: a·b 는 그대로 ──")
DAYS = [P.START + dt.timedelta(days=k) for k in range(130)]


def ab_table():
    return {d: tuple((sl, P.kind_for(d, sl), P.series_no(d, sl), P.sci_n(d) if P.kind_for(d, sl) == P.SCI else None,
                      P.bm_n(d) if P.kind_for(d, sl) in P.BM_KINDS else None) for sl in P.slots_on(d)) for d in DAYS}


base = ab_table()
with tempfile.TemporaryDirectory() as td:
    empty = os.path.join(td, "empty.json")
    json.dump({"entries": []}, open(empty, "w", encoding="utf-8"))
    with P.c_catalogs(worker=empty, danger=empty):
        ck("밤 편 catalog 가 비면 c 는 없다(day_slots = slots_on)", all(P.day_slots(d) == P.slots_on(d) for d in DAYS) and P.c_plan() == {})
        ck("★a·b 편성(꼴·회차·sci src_n·병맛 n)은 밤 편이 있든 없든 똑같다(10/08~2/14)", ab_table() == base)
ck("slots_on 은 그대로 a·b(밤 편은 day_slots 에만) · 11/07 까지 day_slots = slots_on",
   P.slots_on(D(11, 8)) == ("a", "b") and all(P.day_slots(d) == P.slots_on(d) for d in DAYS if d < P.C_FROM)
   and P.SLOTS == ("a", "b") and P.ALL_SLOTS == ("a", "b", "c"))
ck("쓰레드는 밤 편을 따라가지 않는다(threads_slot 은 a·b 중 골라보기만 · 밤 편 대본은 건너뛴다)",
   all(T.threads_slot(d) in (None, "a", "b") for d in DAYS)
   and any("밤 편" in w for w in T.skip_reasons(SD, D(11, 8), {"2026-11-08c": {"media_id": "X", "slug": SD["slug"]}}, env={})))

print("── 편성: 밤 편 c ──")
TABLE = [(D(11, 8), "danger", 601, 1), (D(11, 9), "worker", 501, 1), (D(11, 10), "danger", 602, 2), (D(11, 11), "worker", 502, 2),
         (D(11, 12), "danger", 603, 3), (D(11, 13), "worker", 503, 3), (D(11, 14), "danger", 604, 4), (D(11, 15), "worker", 504, 4),
         (D(11, 16), "danger", 605, 5), (D(11, 17), "worker", 505, 5), (D(11, 18), "danger", 606, 6), (D(11, 19), "worker", 506, 6),
         (D(11, 20), "danger", 607, 7), (D(11, 21), "worker", 507, 7)]
ck("11/08~11/21 편성표: 11/08 danger 601 #1 → 11/09 worker 501 1화 → … 하루씩 번갈아",
   [(d, P.c_kind(d), P.c_n(d), P.c_no(d)) for d, *_ in TABLE] == TABLE, [(d, P.c_kind(d), P.c_n(d), P.c_no(d)) for d, *_ in TABLE])
ck("밤 편 날: day_slots = a·b·c · kind_for(c) = 그 꼴 · slot_of 는 c · 회차 없음 · 골라보기 순번 없음",
   all(P.day_slots(d) == ("a", "b", "c") and P.kind_for(d, "c") == k and P.slot_of(d, k) == "c" and P.series_no(d, "c") is None
       for d, k, *_ in TABLE))
def raises(f) -> bool:
    try:
        f()
    except ValueError:
        return True
    return False


ck("11/07 에는 c 편이 없다(kind_for ValueError) · c_kind None · post_index(밤 편)도 ValueError(골라보기가 아니다)",
   raises(lambda: P.kind_for(D(11, 7), "c")) and P.c_kind(D(11, 7)) is None and raises(lambda: P.post_index(D(11, 8), "c")))
plan = P.c_plan()
ns = [n for _, n in plan.values()]
ck("항목은 한 번씩만 · catalog 전부 편성(worker 501~ · danger 601~) · 꼴은 날짜로 번갈아",
   len(ns) == len(set(ns)) == len(WE) + len(DE) and all(k == P.c_day_kind(d) for d, (k, _) in plan.items()))
ck("1화/1번은 첫 날 · 회차는 꼴마다 따로 센다(worker_no·danger_no)", P.worker_no(D(11, 9)) == 1 and P.danger_no(D(11, 8)) == 1
   and P.worker_no(D(11, 8)) is None and P.danger_no(D(11, 21)) is None and P.worker_no(D(11, 21)) == 7)


def stub(n: int, frm: str | None) -> dict:
    e = copy.deepcopy(P.c_entry(501 if n < 600 else 601))
    e["n"], e["slug"] = n, f"stub-{n}"
    if frm is None:
        e.pop("from", None)
    else:
        e["from"] = frm
    return e


with tempfile.TemporaryDirectory() as td:
    wp, dp = os.path.join(td, "w.json"), os.path.join(td, "d.json")
    json.dump({"character": P.c_catalog(P.WORKER)["character"], "entries": [stub(501, "2026-11-08"), stub(502, "2026-11-20"),
                                                                            stub(503, None)]}, open(wp, "w", encoding="utf-8"))
    json.dump({"entries": [stub(601, "2026-11-08"), stub(602, "2026-11-08")]}, open(dp, "w", encoding="utf-8"))
    with P.c_catalogs(worker=wp, danger=dp):
        p2 = P.c_plan()
        ck("from: 502 는 11/20 이후 첫 worker 날(11/21) · 그 사이 worker 날은 밤 편 없음 · from 없는 503 은 편성 안 함",
           p2 == {D(11, 8): ("danger", 601), D(11, 9): ("worker", 501), D(11, 10): ("danger", 602), D(11, 21): ("worker", 502)},
           sorted(p2.items()))
        ck("바닥난 꼴의 날은 밤 편이 없다(다른 꼴로 안 바꾼다) · day_slots 도 a·b", P.day_slots(D(11, 12)) == ("a", "b")
           and P.c_kind(D(11, 11)) is None)
        rw = {r["id"]: r for r in P.runway(D(11, 1))}
        ck("runway: worker 마지막 11/21 · 2편 · 채우는 번호 504~(from 없는 503 다음) · danger 마지막 11/10",
           (rw["insta_worker"]["last"], rw["insta_worker"]["left"], rw["insta_danger"]["last"]) == (D(11, 21), 2, D(11, 10))
           and "n 504~" in rw["insta_worker"]["refill"], rw)

print("── 차례·대상·장부 ──")
ck("due_slot: 11/08 21:30 → c · 19:00 → b · 11:00 → a · 11/07 21:30 → b(밤 편 없음)",
   (P.due_slot(D(11, 8), KST_AT(D(11, 8), 21, 30)), P.due_slot(D(11, 8), KST_AT(D(11, 8), 19)), P.due_slot(D(11, 8), KST_AT(D(11, 8), 11)),
    P.due_slot(D(11, 7), KST_AT(D(11, 7), 21, 30))) == ("c", "b", "a", "b"))
ck("ledger 열쇠: 밤 편 = 날짜+c(저녁 = 날짜 · 낮 = 날짜+a 그대로)",
   (P.ledger_key("2026-11-08", "c"), P.ledger_key("2026-11-08", "b"), P.ledger_key("2026-11-08", "a"))
   == ("2026-11-08c", "2026-11-08", "2026-11-08a"))
ck("파일 이름의 꼴: worker·danger 를 알아본다", P._kind_of_file("x/2026-11-09_worker_monday-9am.json") == "worker"
   and P._kind_of_file("x/2026-11-08_danger_jellyfish-sleep.json") == "danger")
with tempfile.TemporaryDirectory() as tmp:
    d8 = D(11, 8)
    ka, kb = P.kind_for(d8, "a"), P.kind_for(d8, "b")
    pa = os.path.join(tmp, f"2026-11-08_{ka}_x.json")
    pb = os.path.join(tmp, f"2026-11-08_{kb}_y.json")
    pc = os.path.join(tmp, "2026-11-08_danger_jellyfish-sleep.json")
    for p_ in (pa, pb):
        json.dump({"date": "2026-11-08"}, open(p_, "w", encoding="utf-8"))
    ck("targets: 밤 대본이 없으면 저녁 대본", P.latest_target(d8, tmp) == pb)
    json.dump(SD, open(pc, "w", encoding="utf-8"), ensure_ascii=False)
    ck("targets: 밤 대본이 오면 밤 대본(a < b < c — 앞 대본을 다시 집지 않는다)", P.latest_target(d8, tmp) == pc)
    ni = P.next_info(d8, tmp, slot="c")
    ck("next --slot c(11/08): danger · 601 entry 그대로 · card_no 1 · 견본·쓰는 법 · 이미 썼음 · JSON 으로 나간다",
       ni["due"] and ni["slot"] == "c" and ni["kind"] == "danger" and ni["src_n"] == 601 and ni["card_no"] == 1
       and ni["entry"] == P.c_entry(601) and ni["exemplar"] == "insta/samples/danger_jellyfish-sleep.json"
       and ni["writing"] == "insta/DANGER_WRITING.md" and ni["already_written"] and ni["file"].startswith("output/insta_pick/2026-11-08_danger_")
       and json.loads(json.dumps(ni, ensure_ascii=False)) == ni, {k: ni.get(k) for k in ("due", "kind", "src_n", "card_no")})
    ni9 = P.next_info(D(11, 9), tmp, slot="c")
    ck("next --slot c(11/09): worker · 501 · episode 1 · 캐릭터 묘사 · WORKER_WRITING · 아직 안 씀",
       ni9["kind"] == "worker" and ni9["src_n"] == 501 and ni9["episode"] == 1 and "블롭" in (ni9["character"] or "")
       and ni9["writing"] == "insta/WORKER_WRITING.md" and not ni9["already_written"])
    n7 = P.next_info(D(11, 7), tmp, slot="c")
    ck("next --slot c(11/07): 쓸 차례 아님(due false · 밤 편은 11/08 부터)", not n7["due"] and "밤 편" in n7["why"])
    ck("next(11/08 21:30, slot 없음) = 밤 편", P.next_info(d8, tmp, now=KST_AT(d8, 21, 30))["slot"] == "c")
    meta = {"video": pc, "seconds": 14.0}
    ck("게시 막기: 오늘 밤 대본 · 영상 있음 → 막는 것 없음 · 이미 올렸으면(날짜+c) 막는다",
       P.blockers(SD, meta, {}, d8) == [] and any("이미 올렸다" in b for b in P.blockers(SD, meta, {"2026-11-08c": {"media_id": "X"}}, d8))
       and not P.blockers(SD, meta, {"2026-11-08": {"media_id": "B"}}, d8), P.blockers(SD, meta, {}, d8))

print("── 대본 검사 ──")
ck("견본 둘 다 check ✅(pick_reel 이 worker_reel·danger_reel 로 넘긴다)", K.check(SW) == [] and K.check(SD) == [],
   K.check(SW) + K.check(SD))


def bad_w(mut) -> list:
    s = copy.deepcopy(SW)
    mut(s)
    return K.check(s)


def bad_d(mut) -> list:
    s = copy.deepcopy(SD)
    mut(s)
    return K.check(s)


CASES_W = [
    ("영어 자막 줄(line_en) 금지", lambda s: s.update(line_en="Monday 9AM. Face: melted."), "영어"),
    ("src_n 은 그날 항목", lambda s: s.update(src_n=502), "src_n"),
    ("회차(episode)는 코드가 센다", lambda s: s.update(episode=2), "episode"),
    ("날짜가 danger 날이면 막는다", lambda s: s.update(date="2026-11-10"), "꼴은 danger"),
    ("facts 에 없는 숫자", lambda s: s["fact"].update(body="수심 3,000m에선\n평범한 물고기 모습이에요."), "숫자"),
    ("시각 말고 숫자는 line 에 못 쓴다", lambda s: s.update(line="출근하면 얼굴이 3배 녹아요"), "숫자"),
    ("팔로우 부탁", lambda s: s.update(caption="블롭피시 얼굴 팔로우하고 보기"), "부탁"),
    ("유튜브 언급", lambda s: s.update(question="유튜브에서 더 볼래요?"), "유튜브"),
    ("장면에 sign", lambda s: s["shots"][0].update(scene=s["shots"][0]["scene"] + ", a big neon sign"), "sign"),
    ("장면에 한글", lambda s: s["shots"][1].update(scene="the blobfish 사무실 에서 at its desk in the morning light"), "영어"),
    ("장면에 phone", lambda s: s["shots"][1].update(scene=s["shots"][1]["scene"] + ", holding a phone"), "phone"),
    ("sources 는 그대로", lambda s: s.update(sources=s["sources"][:1]), "sources"),
    ("장면은 두 개", lambda s: s.update(shots=s["shots"][:1]), "shots"),
    ("hl 은 body 안 낱말", lambda s: s["fact"].update(hl=["없는 낱말"]), "hl"),
    ("line 이 두 줄을 넘으면", lambda s: s.update(line="출근만 하면 얼굴이 녹아요\n정말로 녹아요\n또 녹아요"), "line"),
    ("잔망루피(IP)", lambda s: s.update(caption="잔망루피 닮은 블롭피시"), "IP"),
]
for name, mut, word in CASES_W:
    er = bad_w(mut)
    ck(f"worker: {name}", any(word in x for x in er), er)
ck("worker: 시각('오전 9시')은 line·subtitle 에 써도 된다", bad_w(lambda s: s.update(subtitle="오전 9시 10분", line="오전 9시, 얼굴이 녹아요")) == [])
CASES_D = [
    ("title 은 catalog 그대로", lambda s: s.update(title=["해파리는 무서워", "진짜 이유"]), "title"),
    ("sticker 금지(위치를 모른다)", lambda s: s.update(sticker={"type": "circle", "x": 0.4, "y": 0.6}), "sticker"),
    ("tease 는 '?' 로 끝", lambda s: s.update(tease="독침 때문에"), "tease"),
    ("payoff 는 한 줄", lambda s: s.update(payoff="뇌가 없는데도 잠은 아주 꼬박꼬박 잘 잔다 정말로"), "payoff"),
    ("facts 에 없는 숫자", lambda s: s.update(aside="밤엔 박동이 10분의 1로 줄어듦"), "숫자"),
    ("card_no 는 코드가 센다", lambda s: s.update(card_no=3), "card_no"),
    ("그림에 logo", lambda s: s.update(image=s["image"] + ", brand logo in the corner"), "logo"),
    ("저장 부탁", lambda s: s.update(caption="저장해 두고 또 보기"), "부탁"),
    ("src_n 은 danger 항목", lambda s: s.update(src_n=501), "src_n"),
]
for name, mut, word in CASES_D:
    er = bad_d(mut)
    ck(f"danger: {name}", any(word in x for x in er), er)
ck("danger: aside 는 빼도 된다", bad_d(lambda s: s.pop("aside")) == [])

print("── 캡션 ──")
cw, cd = WR.caption_of(SW), DR.caption_of(SD)
ck("worker 캡션: '심해 직장인 1화 · 한 줄' · 열린 질문 · 출처(catalog source_label) · AI 표시 · 해시태그 5개",
   cw.startswith("심해 직장인 1화 · 블롭피시 얼굴") and SW["question"] in cw and f"출처: {P.c_entry(501)['source_label']}" in cw
   and "AI로 만든" in cw and cw.strip().splitlines()[-1].count("#") == 5, cw)
ck("danger 캡션: '위험한 진짜 이유 #1 · 한 줄' · image_note 를 AI 표시 줄에 밝힌다",
   cd.startswith("위험한 진짜 이유 #1 · ") and "(화면은 일반 해파리, 연구 대상은 거꾸로해파리)" in cd and "출처: " in cd, cd)
ck("캡션에 부탁 말·유튜브 없음", not any(w in cw + cd for w in ("팔로우", "댓글", "공유해", "저장해", "유튜브", "구독")))

print("── 화면 배치(안전 영역) ──")
from PIL import Image, ImageDraw  # noqa: E402
_d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
f, ls = B.fit_lines(_d, SW["line"], "head", 88, 64, 900, 2)
ck("worker 한 줄: 폭 900 안 · 아랫변 1440 안(두 줄이어도)", all(_d.textlength(x, font=f) <= 900 for x in ls)
   and WR.LINE_Y + 2 * (f.size + 14) <= B.Y_MAX)
fh, hls = B.fit_lines(_d, SW["fact"]["head"], "head", 76, 58, WR._text_w(P.c_entry(501)), 2)
ck("worker 사실 카드: 제목·본문이 오른쪽 960 안 · 출처 줄 1440 안",
   all(230 + _d.textlength(x, font=fh) <= B.X_MAX for x in hls)
   and all(230 + _d.textlength(x, font=WR.R.font("bold", 52)) <= B.X_MAX
           for x in B.wrap_lines(_d, SW["fact"]["body"], WR.R.font("bold", 52), WR._text_w(P.c_entry(501))))
   and 532 + 2 * (fh.size + 16) + 34 + 5 * 76 + 40 + B.SRC_PX + 8 <= B.Y_MAX)
ck("danger: 반전 줄 폭 880 안(x 74 → 954) · 출처 줄 아랫변 1440 안 · 출처 글씨 32px(폰에서 읽히게)",
   DR._one_line(SD["payoff"], "head", 72, 56) is not None and 1388 + B.SRC_PX + 8 <= B.Y_MAX and B.SRC_PX >= 32)

with tempfile.TemporaryDirectory() as td:
    ok_p, band_p, flat_p = (os.path.join(td, f"{k}.png") for k in ("ok", "band", "flat"))
    im = Image.new("RGB", (800, 1328), (10, 20, 60))           # 어두운 남색 바다 + 밝은 주인공(멀쩡)
    ImageDraw.Draw(im).ellipse((250, 400, 550, 900), fill=(220, 160, 200))
    im.save(ok_p)
    im2 = im.copy()
    ImageDraw.Draw(im2).rectangle((0, 870, 800, 1328), fill=(0, 0, 0))   # 아래 35% 검정(10/31 qwen 편집 실측)
    im2.save(band_p)
    Image.new("RGB", (800, 1328), (128, 128, 128)).save(flat_p)
    ck("망가진 그림 알아보기: 어두운 바다는 멀쩡 · 아래 검은 띠 34%·한 색은 망가짐(편집·그림을 다시 받는다)",
       B.broken_image(ok_p) is None and "검은 띠" in (B.broken_image(band_p) or "") and B.broken_image(flat_p) == "한 색",
       (B.broken_image(ok_p), B.broken_image(band_p), B.broken_image(flat_p)))

print("── mock 렌더(Spark 없이) ──")
with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as work:
    sp = os.path.join(out, "w.json")
    json.dump(SW, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    mw = K.render(sp, out, work, mock=True)
    dp_ = os.path.join(out, "d.json")
    json.dump(SD, open(dp_, "w", encoding="utf-8"), ensure_ascii=False)
    md = K.render(dp_, out, work, mock=True)
    ck("worker mock 렌더: mp4·커버·한눈에 보기·메타 · 16.4초(15~18) · 목소리 없음 · 캡션",
       all(os.path.exists(mw[k]) for k in ("video", "cover", "sheet")) and mw["seconds"] == 16.4
       and P.C_SEC["worker"][0] <= mw["seconds"] <= P.C_SEC["worker"][1] and mw["voice"] == "none" and mw["caption"] == cw, mw)
    ck("danger mock 렌더: 14초(13~15) · 메타 모양 같다(threads_images 빈 것)",
       os.path.exists(md["video"]) and md["seconds"] == 14.0 and md["threads_images"] == [] and md["caption"] == cd, md)
    info = B.clip_info(mw["video"])
    ck("영상: 1080×1920 · 30fps", info[:2] == (1080, 1920) and abs(info[2] - 30) < 0.5, info)
    led = os.path.join(out, "posted.json")
    os.environ["INSTA_PICK_PUBLISH"] = "0"
    rc = P.post(dp_, renders=out, ledger=led, today=D(11, 8))
    ck("post(dry-run): 11/08 밤 대본은 막는 것 없이 dry-run(0) · 다른 날이면 막는다(1)",
       rc == 0 and not os.path.exists(led) and P.post(dp_, renders=out, ledger=led, today=D(11, 9)) == 1)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
