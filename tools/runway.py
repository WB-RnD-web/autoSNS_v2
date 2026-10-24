#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""콘텐츠 재고(runway) — 줄기마다 '언제까지 쓸 게 있나'를 편성 코드에서 그대로 읽어 낸다 (2026-10-25).

왜: 사용자 10/24 "성과가 나오거나 쭉 유지해도 되는 루틴들은 단발성이나 몇회성으로 끝내지 말고 확실하게 계속 돌도록".
  줄기 몇 개는 목록(catalog)·끝 날짜(END/TO 상수)·정해진 편 수가 바닥나면 ★조용히 멈춘다 — 에러도 빨간불도 없다
  (그날 next 가 '쓸 편 없음'을 주고 루틴은 아무것도 안 쓴다). 그래서 줄기마다 한계 종류·마지막 날·남은 날·남은 편·
  채우는 곳을 한 번에 본다. ★날짜 셈은 각 모듈의 편성 함수를 그대로 부른다(pick_plan.runway · newyear_series.schedule ·
  rules.publish_date · gunghap_card.last_day …) — 편성 코드가 바뀌면 여기도 저절로 맞는다.
  채널 맥박(tools/pulse.py)이 WARN_DAYS(14)일 안에 바닥나는 줄기를 매일 신호(RUNWAY:<id>)로 띄운다.

한계 종류: 끝없음(날짜 순환·매일 루틴) · 목록(catalog — 채우면 이어진다) · 끝 날짜(코드 상수) · 시험(판정 뒤 정한다) · 꺼짐.
  '끝(대체)' = 일부러 끝낸 줄기(다른 줄기가 자리를 이어받았다) — 경고하지 않는다.

    python tools/runway.py [--date 2026-10-25] [--warn 14] [--json]
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in ("pipeline", os.path.join("gumiho", "tales"), "insta"):
    _d = os.path.join(ROOT, _p)
    if _d not in sys.path:
        sys.path.insert(0, _d)

KST = dt.timezone(dt.timedelta(hours=9))
WARN_DAYS = 14
LIMITS = {"open": "끝없음", "catalog": "목록", "end": "끝 날짜", "trial": "시험", "off": "꺼짐", "error": "확인 실패"}
CHANNELS = ("왕별이", "Nine Tails", "인스타")
WEEKDAY = "월화수목금토일"


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def _mod(name: str):
    return importlib.import_module(name)


def _const(path: str, name: str):
    """모듈을 실행하지 않고 상수만 읽는다(sleep.py 는 렌더러(PIL)를 끌고 와서 — 맥박·루틴 환경엔 없을 수 있다)."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name and node.value:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def _row(ch: str, id_: str, name: str, limit: str, last: dt.date | None = None, left: int | None = None,
         refill: str = "", note: str = "", judge: dt.date | None = None, ended: str = "") -> dict:
    return {"ch": ch, "id": id_, "name": name, "limit": limit, "last": last, "left": left, "refill": refill,
            "note": note, "judge": judge, "ended": ended}


# ── 왕별이 ──────────────────────────────────────────────
def wangbyul(today: dt.date) -> list[dict]:
    th, ag, nm, pu = _mod("theme_card"), _mod("age_card"), _mod("name_card"), _mod("pulli_card")
    gh, nc, ns, lf, wf = _mod("gunghap_card"), _mod("newyear_card"), _mod("newyear_series"), _mod("longform_2027"), _mod("weekly_fortune")
    ch = "왕별이"
    out = [
        _row(ch, "wb_daily", "06:13 매일 운세(routine/fortune → run_pipeline · 월 = 이번 주 운세)", "open",
             refill="없음 — 매일 루틴이 그날 대본을 쓴다",
             note="신년운세 시리즈 날(화·토 · 12/8~ 화·금·토)은 그 편이 자리를 쓴다(newyear_series)"),
        _row(ch, "wb_theme", f"12:00 띠 테마 표(격일 · 테마 {len(th.THEMES)}개 순환) + 쉬는 날 출생연도 나이 표(테마 {len(ag.THEMES)}개)",
             "open", refill="없음 — 날짜 순환(theme_card · age_card)"),
        _row(ch, "wb_name", f"'내 것 찾기' 표(name_card · 하루 한 칸 {len(nm.ROTATION)}일 순환)", "open",
             refill="없음 — 날짜 순환"),
        _row(ch, "wb_pulli", f"10:40 풀이형 표(pulli_card · 일진 · 테마 {len(pu.THEMES)}개 순환)", "open",
             refill="없음 — 날짜 순환", note=f"덕담표(blessing_card)는 {pu.BLESS_TO:%m/%d} 로 끝"),
    ]
    g_last = gh.last_day()
    out.append(_row(ch, "wb_gunghap", f"띠 궁합표(화·금 18:13 · {len(gh.THEMES)}편 시리즈)", "catalog", g_last,
                    _count(today, g_last, gh.is_post_day),
                    refill="pipeline/gunghap_card.py THEMES 끝에 새 묶음(성적 보고 PR — 같은 표 다시 안 올린다)"))
    n_last = nc.last_day()
    out.append(_row(ch, "wb_newyear_card", f"2027 신년운세 1차 묶음(월·목 · {len(nc.EPISODES)}편)", "catalog", n_last,
                    _count(today, n_last, nc.is_post_day), ended="06:13 신년운세 시리즈(newyear_series)가 이어받음"))
    sched = ns.schedule((ns.last_day() or today) + dt.timedelta(days=1)) if ns.SERIES_FROM else []
    out.append(_row(ch, "wb_newyear_series", f"06:13 2027 신년운세 시리즈(화·토 → 12/8~ 화·금·토 · {len(ns.EPISODES)}편)",
                    "catalog" if ns.SERIES_FROM else "off", ns.last_day(), sum(d >= today for d, _ in sched),
                    refill="pipeline/newyear_series.py EPISODES 끝에 새 편(같은 꼴 연달아 X) — 바닥나면 06:13 은 매일 운세로",
                    note="판정 pulse_experiments 'newyear-slot'"))
    eps = [dt.date.fromisoformat(e["publish"]) for e in lf.EPISODES]
    out.append(_row(ch, "wb_lf27", f"롱폼 '2027 정미년 깊이 보기'(월·수·금 20:00 · {len(eps)}편 고정)", "catalog", lf.last_day(),
                    sum(d >= today for d in eps),
                    refill="뒤를 이을 롱폼 편성이 없다 — 새 시리즈(또는 주간 롱폼 weekly_fortune.STOP_FROM 되돌리기)를 PR 로",
                    note="이게 끝나면 왕별이 롱폼 0편(주간 롱폼은 11/02 부터 꺼짐)"))
    w_last = wf.last_day()
    out.append(_row(ch, "wb_weekly_lf", "주간 띠별 운세 롱폼(일 08:00)", "end" if w_last else "open", w_last,
                    int(bool(w_last and w_last >= today)) if w_last else None,
                    ended="11/02 부터 '2027 정미년 깊이 보기'(longform_2027)가 대신" if w_last else "",
                    refill="다시 켜기 = pipeline/weekly_fortune.py STOP_FROM 을 None"))
    return out


def _count(today: dt.date, last: dt.date | None, is_day) -> int:
    """today~last 중 그 줄기 편성일 수(모듈의 is_post_day 그대로)."""
    if not last or last < today:
        return 0
    return sum(1 for k in range((last - today).days + 1) if is_day(today + dt.timedelta(days=k)))


# ── Nine Tails ──────────────────────────────────────────
def nine_tails(today: dt.date) -> list[dict]:
    R, T = _mod("rules"), _mod("tales")
    ch = "Nine Tails"
    sc = R.shorts()
    lasts = R.last_publish(sc)
    pub = [R.publish_date(e, sc) for f in R.NEW_FORMATS for e in sc.get(f) or []]
    judge = dt.date.fromisoformat(sc["judge"]) if sc.get("judge") else None
    detail = " · ".join(f"{f} {d:%m/%d}" for f, d in lasts.items() if d)
    out = [_row(ch, "nt_shorts", "영어 쇼츠(survival 매일 · compare/liminal 격일 — shorts_catalog)", "trial",
                max((d for d in lasts.values() if d), default=None), sum(d >= today for d in pub), judge=judge,
                refill="gumiho/tales/shorts_catalog.json 형식별 목록 끝에 — 공개일은 목록 위치로 first_publish 부터 센다"
                       "(rules.publish_date) · 바닥난 뒤 붙이면 지난 날짜가 되니 마지막 날 전에 붙이거나 first_publish·offset 을 옮길 것",
                note=f"마지막 공개 {detail} · 쓰는 날은 하루 전")]
    cat = T.load(T.CATALOG)
    dated = [dt.date.fromisoformat(e["date"]) for e in cat["tales"] if e.get("date") and not e.get("retired")]
    backlog = cat.get("backlog") or []
    out.append(_row(ch, "nt_longform", "해설 롱폼(주 1편 일 14:00 UTC — catalog.json tales)", "catalog", T.last_date(),
                    sum(d >= today for d in dated),
                    refill="gumiho/tales/catalog.json tales 에 편 추가(date = 일요일 · facts·sources·careful)",
                    note=f"backlog 제목 {len(backlog)}개(제목만 — 사실·출처를 채워야 편성된다)" if backlog else ""))
    enabled = _const(os.path.join(ROOT, "gumiho", "tales", "sleep.py"), "ENABLED")
    out.append(_row(ch, "nt_sleep", "수면판 Sleep Edition(지난 편을 다시 지은 1시간)", "open" if enabled else "off",
                    ended="" if enabled else "10/09 설화 금지로 꺼짐(sleep.ENABLED) — 켜려면 설화 아닌 편으로 spec 을 새로",
                    refill="gumiho/tales/sleep/*.json spec + sleep.py ENABLED = True"))
    return out


# ── 인스타 ──────────────────────────────────────────────
def instagram(today: dt.date) -> list[dict]:
    P = _mod("pick_plan")
    return [_row("인스타", r["id"], r["name"], r["limit"], r.get("last"), r.get("left"), r.get("refill", ""),
                 r.get("note", ""), r.get("judge")) for r in P.runway(today)]


SOURCES = (("왕별이", wangbyul), ("Nine Tails", nine_tails), ("인스타", instagram))


def collect(today: dt.date) -> list[dict]:
    """줄기 전부 + days_left(끝없음·꺼짐은 None · 그 밖은 마지막 날까지 남은 날, 지났으면 0).
    한 모듈이 깨져도 나머지는 낸다(그 줄기는 limit 'error')."""
    rows = []
    for ch, fn in SOURCES:
        try:
            rows += fn(today)
        except Exception as e:  # noqa: BLE001 — 맥박이 이것 때문에 멈추면 안 된다
            rows.append(_row(ch, f"{ch}_error", f"{ch} 편성 읽기", "error", note=f"{type(e).__name__}: {e}"[:200]))
    for r in rows:
        r["today"] = today
        if r["limit"] in ("open", "off", "error"):
            r["days_left"] = None
        else:
            r["days_left"] = max(0, (r["last"] - today).days) if r["last"] else 0
    return rows


def low(rows: list[dict], warn: int = WARN_DAYS) -> list[dict]:
    """warn 일 안에 바닥나는 줄기 — 목록·끝 날짜·시험 중 일부러 끝낸 것(ended)이 아닌 것."""
    return [r for r in rows if r["days_left"] is not None and r["days_left"] < warn and not r["ended"]]


def _d(d: dt.date | None) -> str:
    return f"{d:%m/%d}({WEEKDAY[d.weekday()]})" if d else "—"


def line(r: dict) -> str:
    """한 줄 요약(맥박 신호 문구에도 쓴다)."""
    if r["limit"] == "open":
        return f"{r['name']} — 끝없음"
    if r["limit"] == "off":
        return f"{r['name']} — 꺼짐"
    if r["limit"] == "error":
        return f"{r['name']} — 확인 실패: {r['note']}"
    s = f"{r['name']} — {LIMITS[r['limit']]} · 마지막 {_d(r['last'])}"
    if not r["last"]:
        s += " · 쓸 항목 없음"
    elif r["days_left"]:
        s += f" · {r['days_left']}일 남음"
    else:
        s += " · 오늘이 마지막" if r["last"] == r.get("today") else " · 끝남"
    if r["left"] is not None:
        s += f" · {r['left']}편 남음"
    if r.get("judge"):
        s += f" · 판정 {_d(r['judge'])}"
    return s


def text(rows: list[dict], today: dt.date, warn: int = WARN_DAYS) -> str:
    lows = {r["id"] for r in low(rows, warn)}
    o = [f"📦 콘텐츠 재고(runway) — {today.isoformat()}({WEEKDAY[today.weekday()]}) KST 기준 · 경고 {warn}일 안", ""]
    for ch in CHANNELS:
        o.append(f"[{ch}]")
        for r in (x for x in rows if x["ch"] == ch):
            mark = "⚠️" if r["id"] in lows else "✓" if r["limit"] == "open" else "–" if (r["ended"] or r["limit"] == "off") else "·"
            o.append(f"  {mark} {line(r)}")
            if r["ended"]:
                o.append(f"       끝(대체): {r['ended']}")
            elif r["limit"] not in ("open",) and r["refill"]:
                o.append(f"       채우기: {r['refill']}")
            if r["note"] and r["limit"] != "error":
                o.append(f"       참고: {r['note']}")
        o.append("")
    lw = low(rows, warn)
    if lw:
        o.append(f"⚠️ {warn}일 안에 바닥나는 줄기 {len(lw)}개: " + " · ".join(f"{r['id']}({r['days_left']}일)" for r in lw))
    else:
        o.append(f"✅ {warn}일 안에 바닥나는 줄기 없음")
    return "\n".join(o)


def as_json(rows: list[dict], today: dt.date, warn: int = WARN_DAYS) -> dict:
    def j(r):
        return {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in r.items() if k != "today"}
    return {"date": today.isoformat(), "warn": warn, "streams": [j(r) for r in rows], "low": [r["id"] for r in low(rows, warn)]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="콘텐츠 재고(runway) — 줄기마다 마지막 날·남은 날·채우는 곳")
    ap.add_argument("--date", help="기준 날짜 YYYY-MM-DD(기본: 오늘 KST)")
    ap.add_argument("--warn", type=int, default=WARN_DAYS, help=f"이 날 수 안에 바닥나면 경고(기본 {WARN_DAYS})")
    ap.add_argument("--json", action="store_true", help="JSON 으로")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.date) if a.date else kst_today()
    rows = collect(today)
    if a.json:
        print(json.dumps(as_json(rows, today, a.warn), ensure_ascii=False, indent=1))
    else:
        print(text(rows, today, a.warn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
