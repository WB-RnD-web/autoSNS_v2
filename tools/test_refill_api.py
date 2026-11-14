#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/refill_api.py 시험 — 네트워크·API 없이(가짜 클라이언트). 2026-11-14."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refill_api as RA  # noqa: E402
import refill_check as RC  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("✅ " if cond else "❌ ") + name + ("" if cond else f"\n     {str(detail)[:600]}"))
    if not cond:
        FAIL += 1


LF = RA.lf27_mod()
D = dt.date

print("── 고르기(runway) ──")
_rows = [{"id": "wb_lf27", "refillable": True, "days_left": 20, "last": "2026-12-07"},
         {"id": "insta_sci", "refillable": True, "days_left": 3, "last": "2026-11-17"},
         {"id": "wb_newyear_series", "refillable": False, "days_left": 5, "last": "2027-01-05"},
         {"id": "wb_gunghap", "refillable": True, "days_left": None, "last": "2026-11-17"}]
ck("남은 날이 21일보다 적은 API 줄기만(인스타 sci 는 API 줄기 아님 · 꺼진 줄기 X · 사람과 정하는 줄기 X)",
   RA.plan(_rows) == ["wb_lf27"], RA.plan(_rows))
ck("남은 날이 넉넉하면(23일) 아무것도 안 고른다 — 그날은 API 를 부르지 않는다",
   RA.plan([dict(_rows[0], days_left=23)]) == [])
ck("from = 마지막 편 다음 날 · 이미 바닥났으면 사흘 뒤(머지할 틈)",
   RA.from_for(_rows[0], D(2026, 11, 14)) == D(2026, 12, 8)
   and RA.from_for({"days_left": 0, "last": "2026-11-01"}, D(2026, 11, 14)) == D(2026, 11, 17))

print("── 출생연도 나누기 · 정규화(코드가 정하는 칸) ──")
_ys = LF.ddi_years("양")
ck("출생연도 장 1개 = 전부 · 2개 = 1960년대까지/1970년대부터 · 3개 = 빠짐없이 차례로",
   RA.split_years(_ys, 1) == [_ys] and RA.split_years(_ys, 2) == [[y for y in _ys if y < 1970], [y for y in _ys if y >= 1970]]
   and sum(RA.split_years(_ys, 3), []) == _ys and all(RA.split_years(_ys, 3)), RA.split_years(_ys, 3))


def _spec(ep_idx, title, **kw):
    e = LF.EPISODES[ep_idx]
    sp = {"animals": list(e["animals"]), "title": title, "thumb": dict(e["thumb"]),
          "angle": f"{e['animals'][0]}띠 한 주제만 깊게 — 앞 단독 편은 총운 전체, 이 편은 그중 하나를 달력처럼 짚는다",
          "qa_seeds": list(e["qa_seeds"])[:4],
          "chapters": [{k: c[k] for k in ("layout", "topic", "table", "animal", "title") if k in c} for c in e["chapters"]]}
    sp.update(kw)
    return sp


_n0 = len(LF.EPISODES)
_good = [_spec(4, "2027년 양띠 재물운 깊이 보기 | 돈이 도는 달과 지킬 것 · 출생연도별 풀이"),
         _spec(5, "2027년 말띠 건강운 깊이 보기 | 몸이 가벼운 달과 좋은 습관 · 출생연도별 풀이")]
_norm = RA.lf27_normalize({**_good[0], "id": "E99", "from": "2020-01-01"}, f"E{_n0 + 1:02d}", D(2026, 12, 8), LF)
_yc = [c for c in _norm["chapters"] if c["layout"] == "years"]
ck("정규화: id·from 은 코드가 정한다(모델 값 무시) · 장 id c01… · 출생연도 장 years 는 코드가 나눈다",
   _norm["id"] == f"E{_n0 + 1:02d}" and _norm["from"] == "2026-12-08"
   and [c["id"] for c in _norm["chapters"]] == [f"c{k + 1:02d}" for k in range(len(_norm["chapters"]))]
   and [c["years"] for c in _yc] == RA.split_years(_ys, 2), _norm["chapters"])
_specs = [RA.lf27_normalize(s, f"E{_n0 + 1 + i:02d}", D(2026, 12, 8), LF) for i, s in enumerate(_good)]
ck("맞는 명세 두 편은 검사(more_errs + 화면 규칙) 통과", all(not e for _, e in RA.lf27_errs(_specs, LF)), RA.lf27_errs(_specs, LF))
_mix = RA.lf27_normalize(_spec(4, "2027년 양띠·쥐띠 같이 보기 | 출생연도별 풀이", animals=["양", "쥐"]), "E99", D(2026, 12, 8), LF)
_m3 = RA.lf27_normalize(_spec(4, "2027년 양띠 달력 | 좋은 달", chapters=[dict(c, table="months3") if c.get("table") == "months1" else c
                                                                     for c in _good[0]["chapters"]]), "E99", D(2026, 12, 8), LF)
ck("막는 것: 다른 삼합 무리 섞기 · 한 띠 편에 세 띠 달 표 · 앞 편과 같은 제목",
   any("삼합 무리" in x for x in RA.lf27_extra_errs(_mix, LF, set()))
   and any("months3" in x for x in RA.lf27_extra_errs(_m3, LF, set()))
   and any("같다" in x for x in RA.lf27_extra_errs(_specs[0], LF, {_specs[0]["title"]})))


# ── 가짜 클라이언트 ──
class _Usage:
    input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens = 20000, 0, 0, 8000


class _Msg:
    def __init__(self, text):
        self.stop_reason = "end_turn"
        self.content = [type("B", (), {"type": "text", "text": text})()]
        self.usage = _Usage()


class _Stream:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return _Msg(self.text)


class _Client:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = self

    def stream(self, **kw):
        self.calls.append(copy.deepcopy(kw))
        return _Stream(self.replies.pop(0))


def _reply(specs):
    return "```json\n" + json.dumps({"episodes": specs}, ensure_ascii=False) + "\n```"


print("── API 쓰기(가짜) ──")
_bad = copy.deepcopy(_good)
_bad[1]["chapters"] = [c for c in _bad[1]["chapters"] if c["layout"] != "years"]     # 출생연도 장 빠짐
fc = _Client([_reply(_bad), _reply(_good)])
info = RA.write_specs(LF, 2, D(2026, 12, 8), client=fc)
ck("틀린 편이 있으면 오류를 붙여 다시 → 두 번째에 통과 · 비용 셈",
   info["ok"] and info["tries"] == 2 and len(info["specs"]) == 2 and "코드 검사에서 오류" in fc.calls[1]["messages"][-1]["content"]
   and "출생연도" in fc.calls[1]["messages"][-1]["content"] and info["usd"] > 0, info)
ck("모델에게 가는 글 = 지난 편 목록·띠마다 사실·명세 모양 · 시스템은 캐시",
   all(e["id"] in fc.calls[0]["messages"][0]["content"] for e in LF.EPISODES)
   and "facts_by_animal" in fc.calls[0]["messages"][0]["content"]
   and fc.calls[0]["system"][0].get("cache_control") == {"type": "ephemeral"})
fc = _Client([_reply(_good + _bad[1:])] * 3)
_g3 = RA.TRIES
info = RA.write_specs(LF, 3, D(2026, 12, 8), client=fc, min_keep=2)
ck("끝까지 틀리면 앞에서부터 맞는 편만(min_keep 이상일 때) — 틀린 편 뒤로는 붙이지 않는다",
   info["ok"] and len(info["specs"]) == 2 and info["tries"] == _g3, info)
fc = _Client(["not json"] * 3)
ck("끝까지 못 읽으면 실패(아무것도 안 붙인다)", not RA.write_specs(LF, 2, D(2026, 12, 8), client=fc)["ok"])

print("── 끝까지(가짜 API → 붙이기 → catalog → refill_check → 커밋 글) ──")
base = RC.base_tree("HEAD")
cur = tempfile.mkdtemp(prefix="refill_api_cur_")
shutil.copytree(base, cur, dirs_exist_ok=True)
try:
    res = RA.fill("wb_lf27", D(2026, 11, 14), n=2, client=_Client([_reply(_good)]), root=cur, base_root=base,
                  rows=[{"id": "wb_lf27", "refillable": True, "days_left": 23, "last": "2026-12-07"}])
    with open(os.path.join(cur, "pipeline", "longform_2027_more.json"), encoding="utf-8") as f:
        _more = json.load(f)["episodes"]
    with open(os.path.join(cur, "pipeline", "longform_2027_catalog.json"), encoding="utf-8") as f:
        _cat = f.read()
    # 첫 새 편 = max(from 12/08, 지금 마지막 편 다음 날) 이후 첫 월·수·금 — 목록이 늘어도 맞게 계산한다(끝 번호·날짜를 박지 않는다)
    _d = max(D(2026, 12, 8), D.fromisoformat(LF.EPISODES[-1]["publish"]) + dt.timedelta(days=1))
    while _d.weekday() not in LF.POST_DAYS:
        _d += dt.timedelta(days=1)
    _ds = [res.get("dates", {}).get(_specs[k]["id"], "") for k in (0, 1)]
    ck("붙이기 → catalog --write → refill_check ✅ → 브랜치 refill/wb_lf27-20261114 · 첫 편은 마지막 편 뒤 첫 월·수·금",
       res["ok"] and res["branch"] == "refill/wb_lf27-20261114" and [s["id"] for s in _more][-2:] == [_specs[0]["id"], _specs[1]["id"]]
       and _specs[0]["title"] in _cat and _ds[0] == _d.isoformat() and _ds[1] > _ds[0],
       {k: res.get(k) for k in ("ok", "why", "check", "dates")})
    ck("커밋 글 첫 줄 = PR 제목 '채우기: … 2편(첫 날~마지막 날)' · 본문에 검사·from·비용",
       res["message"].splitlines()[0] == f"채우기: 2027 정미년 깊이 보기 롱폼 2편({_ds[0][5:].replace('-', '/')}~{_ds[1][5:].replace('-', '/')})"
       and "from 2026-12-08" in res["message"] and "refill_check" in res["message"] and "달러" in res["message"],
       res["message"][:400])
finally:
    shutil.rmtree(cur, ignore_errors=True)
    shutil.rmtree(base, ignore_errors=True)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
