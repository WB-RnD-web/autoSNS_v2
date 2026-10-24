#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""'2027 정미년 깊이 보기'(longform_2027 · longform_2027_render · run_longform_2027 · sal_frame) 회귀 테스트.

네트워크 없이 돈다(워크플로가 렌더 전에 돌린다). ffmpeg 가 있으면 1초짜리 조각 하나를 실제로 만든다.

    python pipeline/test_longform_2027.py
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ.setdefault("LF27_MOCK", "1")
import birth_basis as BB  # noqa: E402
import longform_2027 as LF  # noqa: E402
import sal_frame as SF  # noqa: E402
import theme_card  # noqa: E402
import weekly_fortune as WF  # noqa: E402
from fortune_card import ANIMALS  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


KST = LF.KST


def at(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=KST)


with open(LF.SAMPLE, encoding="utf-8") as f:
    SAMPLE = json.load(f)
SAT = at("2026-10-31T10:00")          # E01 을 쓰는 루틴 회차(토 10시)


def errs_of(sc, now=SAT, history=None, strict=True, path=""):
    return LF.check(sc, path, now=now, history=history or [], strict=strict)[0]


def chap(sc, cid):
    return next(c for c in sc["chapters"] if c["id"] == cid)


print("── 1. 십이신살·삼재·방위(표준 표와 대조) ──")
B = "자축인묘진사오미신유술해"
# 표준 십이신살 표: 그룹마다 겁살부터 화개살까지의 지지(삼합 지살 기준)
STD = {"신자진": "사오미신유술해자축인묘진", "인오술": "해자축인묘진사오미신유술",
       "사유축": "인묘진사오미신유술해자축", "해묘미": "신유술해자축인묘진사오미"}
ok = True
for grp, seq in STD.items():
    for k, ch_ in enumerate(seq):
        for a in LF.GROUP_ORDER[grp]:
            if LF.sinsal_of(ANIMALS.index(a), B.index(ch_)) != LF.SINSAL[k]:
                ok = False
ck("12띠 × 12지지 신살이 표준 표(삼합 지살 기준 겁살~화개살)와 같다", ok)
want27 = {"신자진": "천살", "인오술": "반안살", "사유축": "월살", "해묘미": "화개살"}
ck("2027 정미년(未): 신자진 천살 · 인오술 반안살 · 사유축 월살 · 해묘미 화개살",
   all(LF.sinsal_of(ANIMALS.index(a)) == s for g, s in want27.items() for a in LF.GROUP_ORDER[g]))
ck("…원숭이·쥐·용 / 호랑이·말·개 / 뱀·닭·소 / 돼지·토끼·양", LF.GROUP_ORDER == {
    "신자진": ("원숭이", "쥐", "용"), "인오술": ("호랑이", "말", "개"), "사유축": ("뱀", "닭", "소"),
    "해묘미": ("돼지", "토끼", "양")})
ck("삼재 2027: 해묘미만 날삼재(들 2025 · 눌 2026) · 다른 그룹은 없음",
   [a for a in ANIMALS if LF.samjae_stage(ANIMALS.index(a)) == "날삼재"] == ["토끼", "양", "돼지"]
   and not [a for a in ANIMALS if LF.samjae_stage(ANIMALS.index(a)) in ("들삼재", "눌삼재")]
   and LF.samjae_stage(3, LF.year_branch(2025)) == "들삼재" and LF.samjae_stage(3, LF.year_branch(2026)) == "눌삼재")
ck("삼재 해: 신자진 2022~24(지남) · 인오술 2028~30(다음) · 사유축 2031~33 · 해묘미 2025~27(지금)",
   LF.samjae_years(0) == {"last": [2022, 2023, 2024], "next": [2034, 2035, 2036]}
   and LF.samjae_years(2)["next"] == [2028, 2029, 2030] and LF.samjae_years(5)["next"] == [2031, 2032, 2033]
   and LF.samjae_years(7)["now"] == [2025, 2026, 2027], [LF.samjae_years(b) for b in (0, 2, 5, 7)])
ck("대장군: 사오미년 동쪽(2027) · 인묘진년 북 · 신유술년 남 · 해자축년 서",
   LF.daejanggun() == "동쪽" and LF.daejanggun(LF.year_branch(2024)) == "북쪽"
   and LF.daejanggun(LF.year_branch(2028)) == "남쪽" and LF.daejanggun(LF.year_branch(2031)) == "서쪽")
ck("삼살: 해묘미년 서쪽(2027) · 인오술년 북(2026) · 신자진년 남(2024) · 사유축년 동(2029)",
   LF.samsal() == "서쪽" and LF.samsal(LF.year_branch(2026)) == "북쪽" and LF.samsal(LF.year_branch(2024)) == "남쪽"
   and LF.samsal(LF.year_branch(2029)) == "동쪽")
rels = {a: LF.all_relations(7, ANIMALS.index(a)) for a in ANIMALS}
ck("未와의 관계: 쥐 원진·해 · 소 충·형 · 말 육합 · 토끼·돼지 삼합 · 개 형·파 · 양 같은 띠 · 호랑이·용·뱀·원숭이·닭 없음",
   rels["쥐"] == ["원진", "해"] and rels["소"] == ["충", "형"] and rels["말"] == ["육합"] and rels["토끼"] == ["삼합"]
   and rels["돼지"] == ["삼합"] and rels["개"] == ["형", "파"] and rels["양"] == ["같은 띠"]
   and all(not rels[a] for a in ("호랑이", "용", "뱀", "원숭이", "닭")), rels)
ys = LF.ddi_years("양")
ck("출생연도 1930~2009: 양띠 31·43·55·67·79·91·03 · 67년생 환갑(정미생 → 정미년)",
   ys == [1931, 1943, 1955, 1967, 1979, 1991, 2003]
   and [r["year"] for r in LF.ddi_facts("양")["years"] if r["hwangap"]] == [1967])
ck("…모든 띠가 1930년대~2000년대를 빠짐없이(6~7개) · 띠가 맞다(입춘 기준 해의 띠)",
   all(6 <= len(LF.ddi_years(a)) <= 7 and all(BB.animal_of(y) == a for y in LF.ddi_years(a)) for a in ANIMALS)
   and sorted(y for a in ANIMALS for y in LF.ddi_years(a)) == list(range(1930, 2010)))
f32 = {r["year"]: r for r in LF.ddi_facts("원숭이")["years"]}
ck("출생연도 천간: 32·92년생(임) = 정임합 · 쥐띠 72년생(임) = 정임합 · 계 해는 정계충",
   "정임" in f32[1932]["stem_note"] and "정임" in f32[1992]["stem_note"]
   and "정계" in {r["year"]: r for r in LF.ddi_facts("닭")["years"]}[1933]["stem_note"])

print("── 2. 편성(월·수·금 20:00 · 날짜로 정한다) ──")
E = LF.EPISODES
E16 = E[:LF.FIRST_N]                                      # ★10/25 채우기: E17~ 이 longform_2027_more.json 으로 붙을 수 있다
ck("첫 16편 · 첫 편 2026-11-02(월) · E16 12-07(월)", len(E16) == 16 and E[0]["publish"] == "2026-11-02"
   and E16[-1]["publish"] == "2026-12-07" and E16[-1]["id"] == "E16", [e["publish"] for e in E16])
ck("…모두 월·수·금 · 날짜가 겹치지 않고 첫 16편은 하루도 건너뛰지 않는다 · 이어 가는 편은 from 이후·앞 편 뒤",
   all(dt.date.fromisoformat(e["publish"]).weekday() in (0, 2, 4) for e in E)
   and [e["publish"] for e in E16] == [d.isoformat() for d in LF._schedule_dates(16)]
   and [e["publish"] for e in E] == sorted({e["publish"] for e in E}) and all(e["publish"] >= e["from"] for e in E[16:])
   and [e["id"] for e in E] == [f"E{k:02d}" for k in range(1, len(E) + 1)])
ck("A 묶음 4편: 천살(신자진) → 화개살·날삼재(해묘미) → 반안살(인오술) → 월살(사유축)",
   [(e["group"], e["sinsal"]) for e in E[:4]] == [("신자진", "천살"), ("해묘미", "화개살"), ("인오술", "반안살"),
                                                   ("사유축", "월살")] and E[1]["samjae"] == "날삼재")
ck("B 띠 단독 12편: 양띠부터 · 12띠 한 번씩", [e["animals"][0] for e in E16[4:]][0] == "양"
   and sorted(e["animals"][0] for e in E16[4:]) == sorted(ANIMALS) and all(e["kind"] == "single" for e in E16[4:]))
ck("공개 시각 = 그날 20:00 KST(11:00Z) · 이미 지났으면 None(바로 공개)",
   LF.publish_at(E[0], at("2026-10-31T10:00")) == "2026-11-02T11:00:00Z"
   and LF.publish_at(E[0], at("2026-11-02T19:55")) is None)
ck("파일 이름 = E01_2026-11-02.json", LF.file_name(E[0]) == "E01_2026-11-02.json")

print("── 2b. 이어 가는 편(E17~ · longform_2027_more.json · from) — 앞 16편 날짜는 그대로 ──")
_specs = LF.more_specs()
ck("지금 이어 가는 편 명세는 전부 검사 통과(틀리면 편성에서 빠진다) · 편성된 수 = 명세 수",
   all(not LF.more_errs(sp, [f"E{k:02d}" for k in range(1, 17 + i)]) for i, sp in enumerate(_specs))
   and len(E) == 16 + len(_specs), [LF.more_errs(sp, [e["id"] for e in E[:16 + i]]) for i, sp in enumerate(_specs)])
_e5 = E16[4]
_last = dt.date.fromisoformat(E[-1]["publish"])
_sp = {"id": f"E{len(E) + 1:02d}", "from": (_last + dt.timedelta(days=12)).isoformat(), "animals": _e5["animals"],
       "title": "2027년 양띠 재물운 깊이 보기 | 돈이 도는 달과 지킬 것 · 출생연도별 풀이",
       "thumb": {"big": "2027 양띠", "sub": "재물운", "pill": "돈이 도는 달"},
       "angle": "양띠 재물만 깊게 — 앞 편(총운)과 달리 돈 흐름·달별 재물·지킬 것을 차근차근",
       "chapters": _e5["chapters"], "qa_seeds": _e5["qa_seeds"][:3]}
_sp2 = dict(_sp, id=f"E{len(E) + 2:02d}", title=_sp["title"].replace("재물운", "건강운"), **{"from": E[0]["publish"]})
_bad = dict(_sp, id="E99", chapters=_e5["chapters"][:3], title="양띠 이야기")
_tmp = tempfile.mkdtemp()
_mp = os.path.join(_tmp, "more.json")
with open(_mp, "w", encoding="utf-8") as f:
    json.dump({"episodes": _specs + [_sp, _sp2, _bad]}, f, ensure_ascii=False)
_real_more = LF.MORE_PATH
LF.MORE_PATH = _mp
_eps = LF.episodes()
LF.MORE_PATH = _real_more


def _next_post(d):
    while d.weekday() not in LF.POST_DAYS:
        d += dt.timedelta(days=1)
    return d


_d17 = _next_post(_last + dt.timedelta(days=12))
ck("붙인 편: from 이후 첫 월·수·금 · 다음 편은 from 이 일러도 앞 편 다음 월·수·금 · 앞 편들 날짜·id 그대로 · 사이가 비어도 된다",
   [(e["id"], e["publish"]) for e in _eps[:len(E)]] == [(e["id"], e["publish"]) for e in E]
   and [(e["id"], e["publish"]) for e in _eps[len(E):]] == [(_sp["id"], _d17.isoformat()),
                                                            (_sp2["id"], _next_post(_d17 + dt.timedelta(days=1)).isoformat())],
   [(e["id"], e["publish"]) for e in _eps[len(E) - 1:]])
ck("붙인 편: 앞 마지막 편 → 다음 편 고리 · 출생연도 장 채움 · 장마다 배경 · kind single(띠 하나)",
   _eps[len(E) - 1]["next"] == _sp["id"] and _eps[-1]["next"] is None and _eps[len(E)]["kind"] == "single"
   and len(_eps[len(E)]["scenes"]) == len(_eps[len(E)]["chapters"]) and _eps[len(E)]["from"] == _sp["from"])
ck("틀린 명세(번호·장 3개·제목)는 편성하지 않고 더 이상 붙지 않는다 · more_errs 가 이유를 낸다",
   len(_eps) == len(E) + 2 and any("id 는" in x for x in LF.more_errs(_bad, [e["id"] for e in _eps]))
   and any("chapters" in x for x in LF.more_errs(_bad, [e["id"] for e in _eps]))
   and any("title" in x for x in LF.more_errs(_bad, [e["id"] for e in _eps])))
ck("명세 검사: 출생연도 장이 띠의 해를 다 덮지 않으면 · from 없으면 · 없는 표면 막는다",
   any("출생연도" in x for x in LF.more_errs(dict(_sp, chapters=[c for c in _e5["chapters"] if c["layout"] != "years"]),
                                            [e["id"] for e in E]))
   and any("from" in x for x in LF.more_errs({k: v for k, v in _sp.items() if k != "from"}, [e["id"] for e in E]))
   and any("table" in x for x in LF.more_errs(dict(_sp, chapters=_e5["chapters"][:-1] + [dict(_e5["chapters"][-1], layout="table",
                                                                                         table="x")]), [e["id"] for e in E])))

print("── 3. 카탈로그 ──")
with open(LF.CATALOG_PATH, encoding="utf-8") as f:
    committed = f.read()
ck("커밋된 longform_2027_catalog.json = 코드가 만든 것(손으로 고치지 않는다 — catalog --write)",
   committed == LF.catalog_json())
cat = json.loads(committed)
need = {"id", "publish", "kind", "group", "animals", "sinsal", "title", "search", "thumb", "angle", "qa_seeds",
        "chapters", "facts", "next"}
ck("편마다 필요한 칸이 다 있다", all(need <= set(e) for e in cat["episodes"]), [need - set(e) for e in cat["episodes"]][:2])
fact_keys = {"sinsal_2027", "samjae_2027", "samjae_years", "relations_with_2027", "tier_total", "tier_money",
             "months_good", "months_caution", "lucky", "health", "years"}
ck("띠마다 사실: 신살·삼재·未 관계·등급·좋은/조심할 달·행운(색·숫자·방향)·건강·출생연도",
   all(fact_keys <= set(f_) for e in cat["episodes"] for f_ in e["facts"].values())
   and all(set(f_["lucky"]) >= {"colors", "numbers", "direction"} for e in cat["episodes"] for f_ in e["facts"].values()))
ck("장 10개 이상 · 출생연도 장이 그 편 띠의 1930~2009년생을 빠짐없이",
   all(len(e["chapters"]) >= LF.SPEC.chapters_min for e in E)
   and all(sorted(y for c in e["chapters"] if c["layout"] == "years" for y in c["years"])
           == sorted(y for a in e["animals"] for y in LF.ddi_years(a)) for e in E))
lays = {e["id"]: {c["layout"] for c in e["chapters"]} for e in E}
ck("편마다 꼴 4가지 이상(표·카드·출생연도·질문·행운)", all(len(v) >= 4 for v in lays.values()), lays)
titles = [e["title"] for e in E]
ck("제목: 검색어가 앞('2027년 …띠') · 100자 이내 · 서로 다르다 · 한자 없음",
   all(t.startswith("2027년 ") and "띠" in t.split(" | ")[0] and len(t) <= 100 for t in titles)
   and len(set(titles)) == len(E) and not any(LF.HANJA.search(t) for t in titles), titles)
ck("제목의 살·삼재는 조언 틀 안에서만(sal_frame)", not [v for t in titles for v in SF.violations(t, unit="whole")],
   [v for t in titles for v in SF.violations(t, unit="whole")][:2])
ck("제목·썸네일에 금지어·영문 등급 없음", not [h for e in E for x in (e["title"], *e["thumb"].values())
                                        for h in LF.ban_hits(x)])
ck("다음 편 고리: E01→E02 … 마지막 편은 끝(이어 가는 편이 있으면 E16→E17)",
   [e["next"] for e in E] == [f"E{k:02d}" for k in range(2, len(E) + 1)] + [None])
ck("배경 장면: 장마다 하나 · 사람·글자·축제 없는 장면(긍정형 묘사)",
   all(len(e["scenes"]) == len(e["chapters"]) for e in E) and "no people" in LF.STYLE
   and not any(re.search(r"(?i)festival|new year|lantern|lucky|text|letter|sign", s) for s in LF.SCENES + (LF.LAMB,)))

def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


code_txt = list(_strings([LF.table_sinsal12(), LF.table_months(ANIMALS), [LF.table_people12(a) for a in ANIMALS],
                          [e["facts"] for e in cat["episodes"]], [e["thumb"] for e in E], [c["title"] for e in E for c in e["chapters"]]]))
ck("코드가 만든 화면·사실 글(표·장 제목·썸네일·사실 JSON)에 금지어 없음('큰일'도)",
   not [(t, h) for t in code_txt for h in LF.ban_hits(t)], [(t, h) for t in code_txt for h in LF.ban_hits(t)][:3])
rows_txt = [f"{r['animal']}띠 {r['sinsal']} {r['samjae']} {r['advice']}" for r in LF.table_sinsal12()] +     [c["title"] for e in E for c in e["chapters"]] + [" ".join(e["thumb"].values()) for e in E]
ck("…살 이름이 든 표 한 줄·장 제목·썸네일은 그 줄 안에 조언 틀", not [v for t in rows_txt for v in SF.violations(t, unit="whole")],
   [v for t in rows_txt for v in SF.violations(t, unit="whole")][:3])

print("── 4. 살·삼재 조언 틀(sal_frame) — 쇼츠·롱폼 공통 ──")
ck("허용: 꼭 지킬 3가지 · 잘 넘기는 법 · 복삼재로 바꾸는 법 · 조심할 달 · …하세요",
   all(SF.ok(x, unit="whole") for x in ("2027년 천살 드는 띠 꼭 지킬 3가지", "날삼재 잘 넘기는 법",
                                       "날삼재 복삼재로 바꾸는 법", "월살 조심할 달", "삼재라도 차분히 지내세요")))
ck("막음: 조언 틀 없이 '삼재입니다'·'천살이 들었습니다'",
   not SF.ok("올해는 삼재입니다.") and not SF.ok("원숭이띠는 천살이 들었습니다."))
ck("막음: 겁주는 말과 같이(큰일·망한다·죽는다·재앙) — 조언이 있어도",
   all(not SF.ok(x) for x in ("삼재가 들면 큰일 납니다, 조심하세요.", "천살이면 망한다고 하니 지키세요.",
                                "삼재에 재앙이 오니 준비하세요.", "날삼재에 죽는다는 말, 대비하세요.")))
ck("문장 단위: 다른 문장의 조언은 이 문장을 덮지 않는다",
   not SF.ok("올해는 삼재입니다. 건강을 챙기세요.") and SF.ok("올해는 삼재지만 건강을 챙기세요."))
ck("시청자 질문은 답이 조언 틀 — 겁주는 말만 본다",
   SF.ok("천살이 든 해에는 이사를 미뤄야 하나요?", question=True)
   and not SF.ok("삼재라 큰일 나는 건 아닌가요?", question=True))
ck("살다·살림·몇 살 같은 말은 살 이름이 아니다",
   SF.sal_words("같이 살아요. 살림이 넉넉해요. 열 살 손주") == [] and SF.sal_words("천살과 반안살, 날삼재") ==
   ["천살", "반안살", "날삼재"])
ck("쇼츠 금지어(theme_card.BANNED)에서 '삼재'를 뺐다 — 대신 sal_frame 을 쇼츠 테스트가 같이 돈다",
   "삼재" not in theme_card.BANNED and "재앙" in theme_card.BANNED and "망한" in theme_card.BANNED
   and all("sal_frame" in open(os.path.join(HERE, n), encoding="utf-8").read()
           for n in ("test_newyear_card.py", "test_newyear_series.py")))
ck("주간 롱폼 금지어도 같은 규칙(삼재는 틀 안에서만)", "삼재" not in sum(WF.BAN.values(), ())
   and not WF.ban_hits("날삼재는 마무리를 잘하면 복삼재로 바꿀 수 있어요.") and WF.ban_hits("올해는 삼재입니다."))
ck("2027 롱폼 금지어: 큰일(통째로) · 한 해 깎아내리기 · 게임 말투 · 요일 약속",
   all(LF.ban_hits(x) for x in ("큰일은 미루세요.", "최악의 한 해예요.", "꿀팁 알려 드릴게요.", "월요일에 만나요.",
                                 "S급 운이에요.")))

print("── 5. 대본 검사(check) ──")
e0 = errs_of(SAMPLE)
ck("견본 E01(실제 첫 편): 검사 통과", not e0, e0[:4])
st = LF.compose(SAMPLE)["stats"]
ck(f"…예상 {st['est_min']}분 · {st['chars']:,}자 · 파트 {st['parts']}(시작 + 장 11 + 예고)",
   12 <= st["est_min"] <= 15 and st["parts"] == 13)
ck("…10/20 기준이면 '8일 넘게 남았다'(엄격) · 느슨하면 경고만",
   any("8일" in e for e in errs_of(SAMPLE, now=at("2026-10-20T10:00")))
   and not errs_of(SAMPLE, now=at("2026-10-20T10:00"), strict=False))


def mut(fn):
    sc = copy.deepcopy(SAMPLE)
    fn(sc)
    return errs_of(sc)


def has(errs, word):
    return any(word in e for e in errs)


ck("틀 없는 삼재 문장 → 오류", has(mut(lambda s: chap(s, "c02")["say"].append("원숭이띠는 올해 삼재가 아닙니다.")),
                               "조언 틀"))
ck("겁주는 말 → 오류", has(mut(lambda s: chap(s, "c06")["say"].__setitem__(0, chap(s, "c06")["say"][0] + " 안 지키면 큰일 나요.")),
                       "금지어"))
ck("말에 숫자 → 오류(연도는 코드가 읽는다)", has(mut(lambda s: chap(s, "c09")["say"].__setitem__(0, "3월이 좋아요. 사월도 좋고요. 차분히 지내세요.")),
                                    "쓸 수 없는 글자"))
ck("영문 등급·한자 → 오류", has(mut(lambda s: chap(s, "c02")["points"].__setitem__(0, "S급 해")), "영문 등급")
   and has(mut(lambda s: chap(s, "c02")["points"].__setitem__(0, "天殺 잘 넘기기")), "쓸 수 없는 글자"))
ck("요일 약속 → 오류", has(mut(lambda s: s.__setitem__("teaser", "다음 편은 수요일 저녁에 만나요. 돼지띠, 토끼띠, 양띠가 마무리 잘하는 법을 들려 드릴게요.")),
                         "요일"))
ck("한 해 깎아내리기·게임 말투 → 오류", has(mut(lambda s: chap(s, "c02")["say"].append("쥐띠에게는 최악의 한 해라 꿀팁이 필요해요.")),
                                    "한 해 깎아내리기"))
ck("사실 오류: '쥐띠는 반안살' → 오류", has(mut(lambda s: chap(s, "c06")["say"].append("쥐띠는 반안살이라 자리를 다지면 좋아요.")),
                                     "사실 오류"))
ck("사실 오류: '용띠 날삼재' → 오류", has(mut(lambda s: chap(s, "c07")["say"].append("용띠는 날삼재라 마무리를 잘하세요.")),
                                   "사실 오류"))
ck("장 순서·개수 → 오류", has(mut(lambda s: s["chapters"].pop(3)), "id 순서"))
ck("출생연도 빠짐 → 오류", has(mut(lambda s: chap(s, "c03")["years"].pop()), "출생연도는 코드가 정한다"))
ck("예고에 '다음 편' 없음 → 오류", has(mut(lambda s: s.__setitem__("teaser", "돼지띠, 토끼띠, 양띠가 날삼재를 잘 넘기는 법도 곧 들려 드릴게요.")),
                                  "다음 편"))
ck("질문은 물음표로", has(mut(lambda s: s.__setitem__("question", "내년에 천살이 든다는데 원숭이띠인 저는 괜찮을지 궁금해요.")), "물음표"))
ck("같은 대본 안에서 복사 → 오류", has(mut(lambda s: chap(s, "c04")["years"][1].__setitem__("say", chap(s, "c04")["years"][0]["say"])),
                                "거의 같다"))
ck("짧으면 길이 오류(장·전체)", has(mut(lambda s: [chap(s, c)["say"].__setitem__(slice(1, None), []) for c in ("c06", "c07", "c08", "c02")]),
                               "예상 길이") or has(mut(lambda s: [chap(s, c)["say"].__setitem__(slice(1, None), []) for c in ("c06", "c07", "c08")]), "장이"))
other = copy.deepcopy(SAMPLE)
other.update(episode="E02", publish="2026-11-04")
ck("다른 편이 견본을 옮겨 쓰면 → 오류(이력 대조)",
   has(LF.check(other, "", now=at("2026-11-02T10:00"), history=[{**SAMPLE, "_sample": True}], strict=False)[0], "견본"))
ck("파일 이름·편성 날짜는 코드가 정한다", has(errs_of(SAMPLE, path="/x/E01_2026-11-03.json"), "파일 이름")
   and has(mut(lambda s: s.__setitem__("publish", "2026-11-03")), "편성"))
ck("코드 고정 문구(인사·입춘·행운·마무리)도 금지어·조언 틀·읽기 글자를 지킨다", all(
    not LF.ban_hits(x) and SF.ok(x) and not [c for c in x if not LF.SPOKEN_OK.fullmatch(c)]
    for x in [LF.OPEN_TAIL, LF.OUTRO_FIXED, LF.LUCKY_FIXED, LF.IPCHUN_SPOKEN] + [LF.lucky_spoken(a) for a in ANIMALS]))
ck("입춘 기준 줄: 첫 출생연도 장의 첫 말 · 화면 · 설명란",
   LF.compose(SAMPLE)["parts"][3]["chunks"][0]["text"] == LF.IPCHUN_SPOKEN
   and "입춘" in LF.IPCHUN_SPOKEN and "이월 삼일" in LF.IPCHUN_SPOKEN)

print("── 6. next — 루틴이 쓸 편 ──")


def nxt(when, last=None):
    p = LF.pending(at(when), last)
    return [e["id"] for e in p]


ck("10/29(목) = 아직 없음 · 10/31(토) = E01 · 11/2(월) E01 올린 뒤 = E02 · 11/4(수) = E03 · 11/7(토) = E04",
   nxt("2026-10-29T10:00") == [] and nxt("2026-10-31T10:00") == ["E01"] and nxt("2026-11-02T10:00", "E01") == ["E02"]
   and nxt("2026-11-04T10:00", "E02") == ["E03"] and nxt("2026-11-07T10:00", "E03") == ["E04"])
ck("…한 번 놓치면 다음 회차에 둘(MORE=1): 토 회차를 놓친 월 10시 = E01·E02",
   nxt("2026-11-02T10:00") == ["E01", "E02"])
ck("…공개 3시간 안이면 쓰지 않는다 · 마지막 편 뒤엔 없음",
   nxt("2026-11-02T18:00") == ["E02"] and all(x > "E16" for x in nxt("2026-12-07T10:00", "E16")))
txt = LF.next_text(at("2026-10-31T10:00"), root=tempfile.mkdtemp())
ck("next 출력: EPISODE·PUBLISH·FILE·WRITE_TO·READY(견본)·사실·뼈대",
   all(k in txt for k in ("EPISODE=E01", "PUBLISH=2026-11-02 20:00 KST", "FILE=output/fortune_lf27/E01_2026-11-02.json",
                          "WRITE_TO=", "READY=", '"sinsal_2027": "천살"', '"kind": "longform_2027"')))
ck("…쓸 편이 없으면 EPISODE=NONE", "EPISODE=NONE" in LF.next_text(at("2026-10-28T10:00"), root=tempfile.mkdtemp()))

print("── 7. 렌더 계획 · 화면 꼴마다 그리기(모의) ──")
import longform_2027_render as R  # noqa: E402
import weekly_fortune_render as WR  # noqa: E402


def fake_script(ep: dict) -> dict:
    sk = LF.skeleton(ep)
    sk["question"] = f"{ep['animals'][0]}띠인데 내년 운이 궁금해요?"
    sk["cold_open"] = "안녕하세요. 오늘은 차근차근 풀어 드릴게요. " * 4
    for k, c in enumerate(sk["chapters"]):
        lay = c["_layout"]
        if lay == "card":
            c["say"] = [f"{k}번째 장의 첫 단락이에요. 천천히 들어 보세요.", f"{k}번째 장의 둘째 단락이에요. 마음 편히 지내세요."]
            c["points"] = ["첫째 요점", "둘째 요점", "셋째 요점"]
        elif lay in ("table", "lucky"):
            c["say"] = [f"{k}번째 장 표를 짚어 드릴게요. 좋은 달에 일을 잡으세요."]
        elif lay == "years":
            c["intro"] = ""
            for x in c["years"]:
                x["say"] = f"{x['year']} 해에 태어난 분께 드리는 말이에요. 건강을 챙기세요."
                x["point"] = "건강 챙기기"
        elif lay == "qa":
            c["qa"] = [{"q": "이사해도 괜찮을까요?", "a": "좋은 달을 골라 천천히 정하시면 돼요. " * 3, "point": "좋은 달에 천천히"},
                       {"q": "모임은 언제가 좋나요?", "a": "좋은 달에 가족 모임을 잡아 보세요. " * 3, "point": "좋은 달에 모임"}]
    sk["teaser"] = "다음 편에서 또 만나요. 차근차근 풀어 드릴게요."
    sk["closing"] = "고맙습니다."
    return sk


shot = {}
okall = True
for ep in E:
    plan = LF.compose(fake_script(ep))
    if [p["id"] for p in plan["parts"]] != ["open"] + [c["id"] for c in ep["chapters"]] + ["outro"]:
        okall = False
    for p in plan["parts"]:
        for c in p["chunks"]:
            sp = c["slide"]
            key = (sp["kind"], sp.get("table"), sp.get("focus") is None, sp.get("answer"), sp.get("compass"),
                   sp.get("step"), sp.get("hwangap"), len(ep["animals"]), ep["next"] is None)
            if key not in shot:
                shot[key] = (plan, sp)
ck("모든 편(이어 가는 편 포함) 뼈대를 채우면 렌더 계획이 만들어진다(시작 · 장 · 예고)", okall)
kinds = {k[0] for k in shot}
tables = {k[1] for k in shot if k[0] == "table"}
ck("화면 꼴: 시작·카드·표·출생연도·질문·행운·다음 편 — 표 4가지(신살 12띠·세 띠 달·한 띠 달력·사람)",
   kinds == {"open", "card", "table", "years", "qa", "lucky", "outro"} and tables == {"sinsal12", "months3", "months1", "people12"},
   (kinds, tables))
bad = []
for key, (plan, sp) in shot.items():
    try:
        im = R.draw_slide(plan, sp)
        ex = im.getextrema()
        if im.size != (1920, 1080) or im.mode != "RGBA" or ex[3][1] < 200:
            bad.append((key, im.size, im.mode))
    except Exception as e:  # noqa: BLE001
        bad.append((key, repr(e)[:120]))
ck(f"모의 렌더: 꼴 {len(shot)}가지 화면을 모두 그린다(1920×1080 투명 판 · 글자가 보인다)", not bad, bad[:3])
th_bad = []
for ep in (E[0], E[4], E[-1]):
    im = R.draw_thumbnail(LF.compose(fake_script(ep)))
    if im.size != (1280, 720):
        th_bad.append(ep["id"])
ck("썸네일(묶음·단독·마지막 편) 1280×720", not th_bad, th_bad)
plan = LF.compose(SAMPLE)
durs = {c["text"]: len(c["text"]) / (LF.SPEC.cpm / 60.0) for p in plan["parts"] for c in p["chunks"]}
items, parts, total = WR.timeline(plan, durs, cfg=LF.SPEC)
chs = WR.chapters_text(parts).splitlines()
ck("타임라인(시리즈 길이 설정): 목차 13줄 · 00:00 시작 · 챕터마다 10초 이상 · 예상 길이와 같다",
   len(chs) == 13 and chs[0].startswith("00:00") and all(b["card"] - a["card"] >= 10 for a, b in zip(parts, parts[1:]))
   and abs(total - plan["stats"]["est_sec"]) < 2, (chs[:2], total, plan["stats"]["est_sec"]))
ck("주간 운세 렌더러는 기본값 그대로(cfg 없음 = 주간 설정)",
   WR.timeline({"parts": [{"id": "a", "title": "a", "chunks": [{"text": "x", "slide": {}}]}]}, {"x": 1.0})[2]
   == (WF.LEAD + 1.0 + WF.TAIL) / WF.TEMPO)
ck("TTS 조각: 190자 넘으면 문장에서 나눈다 · 빈 글 없음",
   all(len(c["text"]) <= 200 and c["text"].strip() for p in plan["parts"] for c in p["chunks"])
   and len(LF.split_chunks("가나다라. " * 60)) > 1)
ck("켄 번스: 장마다 방향이 바뀐다(다가가기·물러나기 번갈아)", len(set(R.MOVES)) >= 4 and R.ZOOM > 0)
if shutil.which(os.environ.get("FFMPEG") or "ffmpeg") or os.path.exists(R.R.FFMPEG):
    td = tempfile.mkdtemp()
    try:
        bg = R.ensure_bg(LF.SCENES[0], td)                 # 모의 → 그라데이션
        ov = os.path.join(td, "ov.png")
        R.draw_slide(plan, plan["parts"][2]["chunks"][0]["slide"]).save(ov)
        out = os.path.join(td, "p.mp4")
        R.part_clip(bg, [(ov, 0.5), (ov, 0.5)], 24, out, 1)
        ck("ffmpeg: 배경 켄 번스 + 판 → 1초 조각", os.path.getsize(out) > 5000)
    except Exception as e:  # noqa: BLE001
        ck("ffmpeg: 배경 켄 번스 + 판 → 1초 조각", False, repr(e)[:200])
    finally:
        shutil.rmtree(td, ignore_errors=True)
else:
    print("  (ffmpeg 없음 — 조각 렌더 건너뜀)")

print("── 8. 업로드 메타 ──")
desc = LF.description_for(plan, WR.chapters_text(parts), SAMPLE)
ck("설명란: 목차(00:00) · 출생연도 줄 · 질문·답 · 행운 · 다음 편 · 2028 미리 보기 · 입춘 안내 · 재미로 · 표식",
   "⏱ 목차\n00:00" in desc and "32·44·56·68·80·92·04년생" in desc and "Q. " in desc and "🍀" in desc
   and "📌 다음 편: 2027년 날삼재 드는 띠" in desc and "2028년" in desc and "입춘" in desc and "재미로" in desc
   and desc.rstrip().endswith("2027 정미년 깊이 보기 E01") and len(desc) <= 4900)
ck("…설명란 모든 줄이 살 조언 틀·금지어를 지킨다",
   not [v for ln in desc.splitlines() if not ln.startswith(("Q. ", "#")) for v in SF.violations(ln, unit="whole")]
   and not [h for ln in desc.splitlines() for h in LF.ban_hits(ln) if "요일" not in h],
   [v for ln in desc.splitlines() if not ln.startswith(("Q. ", "#")) for v in SF.violations(ln, unit="whole")][:2])
tags = LF.tags_for(E[0])
ck("태그: '68년생 운세' 같은 출생연도 태그 · '2027년 쥐띠 운세' · 500자 안",
   "68년생 운세" in tags and "2027년 쥐띠 운세" in tags and sum(len(t) + 1 for t in tags) <= 500, tags)
ck("유튜브 중복 표식: E01 은 E01 만(E010 같은 것과 헷갈리지 않게)",
   LF.already_uploaded([{"video_id": "v1", "description": "…\n2027 정미년 깊이 보기 E01"}], "E01") == "v1"
   and LF.already_uploaded([{"video_id": "v1", "description": "2027 정미년 깊이 보기 E012"}], "E01") is None)
ck("쇼츠 설명란 링크: 첫 편 공개(11/2 20:00) 뒤부터 이 시리즈로", not LF.link_series(at("2026-11-02T19:00"))
   and LF.link_series(at("2026-11-02T20:30")) and LF.append_link("설명", "V9").endswith("youtu.be/V9")
   and LF.append_link(LF.append_link("설명", "V9"), "V9").count("V9") == 1)
src = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
ck("run_pipeline.add_weekly_link: 시리즈 공개 편이 있으면 그 링크 · 없으면 주간 롱폼(예전대로)",
   "LF.link_series()" in src and "title=LF.PLAYLIST" in src and src.index("title=LF.PLAYLIST") < src.index(
       "vid = weekly_fortune.latest_public_video(yt)"))
run_src = open(os.path.join(HERE, "run_longform_2027.py"), encoding="utf-8").read()
ck("업로드 길: 주간 롱폼과 같은 publish(재생목록·썸네일·예약·카테고리 24·ko)",
   "N.publish(" in run_src and "playlist_title=LF.PLAYLIST" in run_src and "publish_at=at" in run_src
   and "category_id=LF.CATEGORY" in run_src and LF.CATEGORY == "24")

print("── 9. 워크플로 연결(가드) ──")
wf = os.path.join(ROOT, ".github", "workflows")
flows = {n: open(os.path.join(wf, n), encoding="utf-8").read() for n in sorted(os.listdir(wf)) if n.endswith(".yml")}
tramp, run = flows["fortune-lf27.yml"], flows["fortune-lf27-run.yml"]
ck("fortune-lf27.yml: routine/fortune_lf27 의 output/fortune_lf27/** push 만 · @main 실행 파일 · 수동 기본 = 견본·업로드 없음",
   '- "routine/fortune_lf27"' in tramp and '- "output/fortune_lf27/**"' in tramp
   and "fortune-lf27-run.yml@main" in tramp and 'default: "docs/samples/longform_2027_E01.json"' in tramp)
ck("run: 코드는 main · 새로 추가된 대본만 · 테스트 먼저 · ledger 접두 lf27-ledger- · 읽기 권한만",
   "ref: main" in run and "--diff-filter=A" in run
   and run.index("pipeline/test_longform_2027.py") < run.index("python run_longform_2027.py")
   and "key: lf27-ledger-" in run and "restore-keys: lf27-ledger-" in run
   and not re.search(r"(?m)^\s*contents:\s*write", run + tramp))
others = [re.search(r"restore-keys:\s*(\S+)", t).group(1) for n, t in flows.items()
          if n != "fortune-lf27-run.yml" and re.search(r"restore-keys:\s*(\S+)", t)]
ck("…다른 워크플로의 restore-keys 접두가 우리 키를 집어 가지 않는다",
   not any("lf27-ledger-x".startswith(o) for o in others), others)
ck("shorts.yml 은 routine/fortune_lf27 을 뺀다(06:13 routine/fortune 은 그대로)",
   '- "!routine/fortune_lf27"' in flows["shorts.yml"] and '- "routine/**"' in flows["shorts.yml"])
ck("retry-no-runner 감시 목록에 들어 있다", "2027 정미년 깊이 보기 롱폼 (routine/fortune_lf27 push" in flows["retry-no-runner.yml"]
   and re.search(r"^name:\s*2027 정미년 깊이 보기 롱폼 \(routine/fortune_lf27 push", tramp, re.M))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import find_orphan_storyboards as FO  # noqa: E402
ck("미아 감시·복구: output/fortune_lf27 → routine/fortune_lf27",
   "output/fortune_lf27/*.json" in FO.WATCH and FO.guess_topic("output/fortune_lf27/E01_2026-11-02.json") == "fortune_lf27"
   and '"output/fortune_lf27/**.json"' in flows["orphan-rescue.yml"])
ck("ledger·로그는 커밋하지 않는다", all(x in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
                                  for x in ("/output/lf27_ledger.json", "/output/lf27_log.json")))
ck("글쓰기 안내서가 있다(구조·분량·금지)", os.path.exists(os.path.join(HERE, "LONGFORM_2027_WRITING.md")))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
