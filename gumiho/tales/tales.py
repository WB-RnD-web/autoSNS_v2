#!/usr/bin/env python3
"""Nine Tails Tales — 대본 규칙·검사·메타데이터(제목·설명·챕터·태그).

한 편 = NNN_slug.json 한 파일(사람이 쓴 견본은 gumiho/tales/scripts/, 루틴이 쓴 건 routine/tales 의 output/tales/). 구미(천 년 묵은 구미호)가 한국 설화 하나를 영어로 들려준다.
대본을 누가 썼든(사람·루틴) ★이 검사를 통과해야 렌더·업로드한다 — 루틴에게 한 '지시'는 안 지켜질 수 있어서
분량·장면 수·필드는 코드가 강제한다.

    python gumiho/tales/tales.py check gumiho/tales/scripts/001_gumiho.json
    python gumiho/tales/tales.py next --date 2026-10-08   # 그 주에 쓸 설화(날짜로 결정론적 배정) — 루틴은 이것만 쓴다

scene 한 칸:
  {"say": "내레이션(영어)", "img": "그림 프롬프트(영어)", "fx": "fog", "move": "in", "hold": 0.8, "note": "화면 주석", "key": "짧은 이름"}
  {"say": "...", "gumi": "front|bead|wink"}       # 구미 본인 그림(assets/tales)
  {"card": "II", "sub": "The Fox Bead"}            # 장 제목 카드(말 없음) — sub 가 있는 카드가 유튜브 챕터가 된다
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
ROUTINE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "output", "tales")
CATALOG = os.path.join(HERE, "catalog.json")

CHANNEL = "Nine Tails Tales"
VOICE = os.environ.get("TALES_VOICE", "F2")          # 구미 목소리(Supertonic). F3·F4 는 쓰지 않는다(발음 실측)
WPM = 159                                            # F2 실측(2026-09-29) — 분량 추정용
GUMI = ("front", "bead", "wink")
FX = ("none", "dust", "fog", "embers", "snow", "rain", "fireflies")
MOVES = ("in", "out", "left", "right", "up", "down")
FORMATS = ("tale", "urban", "list", "versus")   # catalog.format — 같은 틀이 연속되지 않게 섞는다(WRITING.md)

# 분량: 8분이 넘어야 중간 광고가 붙는다. 너무 길면 한 주 안에 Spark 그림이 부담.
WORDS_MIN, WORDS_MAX = 1200, 2600
SCENES_MIN, SCENES_MAX = 30, 90
SAY_MAX_WORDS = 70          # 한 그림에 26초 넘게 머물지 않게
HOOK_MAX_WORDS = 45         # 첫 장면(콜드 오픈) — 첫 15초가 이탈을 가른다
SHORT_WORDS = (60, 150)     # 쇼츠 30~55초
SHORT_LINES = (4, 9)
THUMB_MAX_WORDS = 4
# 몇 달 뒤에도 통해야 한다(역주행) — 날짜를 타는 말은 금지. 사실로 적는 연도(1994년 영화 등)는 괜찮다
DATED = re.compile(r"(?i)\b(this (year|week|month|halloween|summer|winter|season)|last (week|month|year)|recently|"
                   r"right now|these days|currently|trending|as of today)\b")
BANNED = re.compile(r"(?i)\b(fuck|shit|rape|porn|nude|naked|gore|dismember|suicide|decapitat)\w*")

AI_NOTE = ("Illustrations and the narrator's voice are AI-generated. Stories are researched from Korean folklore "
           "and retold by Nine Tails Tales; details vary between regional versions.")
ABOUT = ("Nine Tails Tales: Korean and East Asian myths, monsters and ghost stories, told by Gumi, "
         "a 1,000-year-old nine-tailed fox. A new tale every week.")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def words(t: str) -> int:
    return len((t or "").split())


def stats(s: dict) -> dict:
    sc = s.get("scenes") or []
    w = sum(words(x.get("say", "")) for x in sc)
    return {"scenes": len(sc), "words": w, "est_min": round(w / WPM + 0.6 * len(sc) / 60, 1),
            "images": len({x["img"] for x in sc if x.get("img")}),
            "chapters": sum(1 for x in sc if x.get("card") and x.get("sub"))}


def check(s: dict, path: str | None = None) -> list[str]:
    """문제 목록(비었으면 통과)."""
    errs = []
    need = ("id", "slug", "title", "thumb", "scenes", "short", "tags", "sources", "hook")
    for k in need:
        if not s.get(k):
            errs.append(f"'{k}' 없음")
    if errs:
        return errs
    if not isinstance(s["id"], int) or s["id"] < 1:
        errs.append("id 는 1 이상 정수")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s["slug"]):
        errs.append(f"slug 형식: {s['slug']!r}")
    if path:
        base = os.path.basename(path)
        want = f"{s['id']:03d}_{s['slug']}.json"
        if base != want:
            errs.append(f"파일 이름은 {want} 여야 한다(지금 {base})")
    if len(s["title"]) > 100:
        errs.append(f"제목 {len(s['title'])}자 > 100")
    th = s["thumb"]
    if not th.get("text") or words(th["text"]) > THUMB_MAX_WORDS or len(th["text"]) > 22:
        errs.append(f"썸네일 문구는 {THUMB_MAX_WORDS}단어·22자 이하: {th.get('text')!r}")
    if not th.get("img"):
        errs.append("thumb.img(썸네일 그림 프롬프트) 없음")
    sc = s["scenes"]
    st = stats(s)
    if not SCENES_MIN <= st["scenes"] <= SCENES_MAX:
        errs.append(f"장면 {st['scenes']}개 — {SCENES_MIN}~{SCENES_MAX}")
    if not WORDS_MIN <= st["words"] <= WORDS_MAX:
        errs.append(f"내레이션 {st['words']}단어 — {WORDS_MIN}~{WORDS_MAX}(약 8~16분)")
    if st["chapters"] < 3:
        errs.append(f"챕터 카드(sub 있는 card) {st['chapters']}개 — 3개 이상(유튜브 챕터 조건)")
    keys = set()
    for i, x in enumerate(sc):
        kinds = [k for k in ("img", "gumi", "card") if x.get(k)]
        if len(kinds) != 1:
            errs.append(f"장면 {i}: img·gumi·card 중 정확히 하나 ({kinds})")
            continue
        if x.get("card"):
            if x.get("say"):
                errs.append(f"장면 {i}: 카드에는 say 를 넣지 않는다")
        elif not x.get("say"):
            errs.append(f"장면 {i}: say 없음")
        if words(x.get("say", "")) > SAY_MAX_WORDS:
            errs.append(f"장면 {i}: {words(x['say'])}단어 > {SAY_MAX_WORDS} — 둘로 나눌 것")
        if x.get("gumi") and x["gumi"] not in GUMI:
            errs.append(f"장면 {i}: gumi 는 {GUMI}")
        if x.get("fx", "dust") not in FX:
            errs.append(f"장면 {i}: fx {x.get('fx')!r} ∉ {FX}")
        if x.get("move", "in") not in MOVES:
            errs.append(f"장면 {i}: move {x.get('move')!r} ∉ {MOVES}")
        if len(x.get("note", "")) > 60:
            errs.append(f"장면 {i}: note 60자 이하")
        if not 0 <= float(x.get("hold", 0)) <= 3:
            errs.append(f"장면 {i}: hold 0~3초")
        if x.get("key"):
            keys.add(x["key"])
        for f in ("say", "img", "note"):
            if BANNED.search(x.get(f, "")):
                errs.append(f"장면 {i}: 금지어 {BANNED.search(x[f]).group(0)!r}")
    for i in range(1, len(sc)):
        if sc[i].get("card") and sc[i - 1].get("card"):
            errs.append(f"장면 {i - 1}·{i}: 카드가 연달아 나온다 — 글자 화면만 5초 넘게 이어지면 이탈한다(TALE 카드가 1장을 겸한다)")
    for i, x in enumerate(sc):
        m = DATED.search(x.get("say", ""))
        if m:
            errs.append(f"장면 {i}: 날짜를 타는 표현 {m.group(0)!r} — 몇 달 뒤에 보는 사람에게도 맞게 쓴다")
    if not any(t.lower() in s["title"].lower() for t in s["tags"][:3]):
        errs.append("제목에 검색어가 없다 — 태그 앞 3개 중 하나(예: gumiho)를 제목에 넣는다(검색 유입이 오래 간다)")
    first = sc[0] if sc else {}
    if not (first.get("img") and first.get("say")):
        errs.append("첫 장면은 그림+내레이션(콜드 오픈)이어야 한다")
    elif words(first["say"]) > HOOK_MAX_WORDS:
        errs.append(f"첫 장면 {words(first['say'])}단어 > {HOOK_MAX_WORDS}")
    sh = s["short"]
    lines = sh.get("lines") or []
    sw = sum(words(ln.get("say", "")) for ln in lines)
    if not SHORT_LINES[0] <= len(lines) <= SHORT_LINES[1]:
        errs.append(f"쇼츠 줄 {len(lines)} — {SHORT_LINES}")
    if not SHORT_WORDS[0] <= sw <= SHORT_WORDS[1]:
        errs.append(f"쇼츠 {sw}단어 — {SHORT_WORDS}(30~55초)")
    if not sh.get("title") or len(sh["title"]) > 100:
        errs.append("쇼츠 제목 1~100자")
    for j, ln in enumerate(lines):
        src = [k for k in ("scene", "gumi", "img") if ln.get(k)]
        if len(src) != 1:
            errs.append(f"쇼츠 {j}: scene·gumi·img 중 하나")
        elif ln.get("scene") and ln["scene"] not in keys:
            errs.append(f"쇼츠 {j}: scene key {ln['scene']!r} 가 본편에 없다")
        if ln.get("gumi") and ln["gumi"] not in GUMI:
            errs.append(f"쇼츠 {j}: gumi 는 {GUMI}")
    if len(",".join(s["tags"])) > 480:
        errs.append("태그 합계 480자 이하")
    return errs


# ── 메타데이터 ──────────────────────────────────────────
def ts(sec: float) -> str:
    sec = int(round(max(0.0, sec)))
    h, rem = divmod(sec, 3600)
    m, s_ = divmod(rem, 60)
    return f"{h}:{m:02d}:{s_:02d}" if h else f"{m:02d}:{s_:02d}"


def chapters(s: dict, starts: list[float]) -> str:
    """유튜브 챕터: 0:00 부터, sub 있는 카드마다. starts = 장면별 시작 초."""
    rows = [("00:00", "Cold open")]
    for x, t in zip(s["scenes"], starts):
        if x.get("card") and x.get("sub"):
            # 'TALE 001' 카드는 본편 시작, 로마 숫자 카드는 장 제목
            label = f"Tale: {x['sub']}" if x["card"].startswith("TALE") else f"{x['card']}. {x['sub']}"
            rows.append((ts(t), label))
    # 유튜브 규칙: 첫 챕터 0:00, 각 10초 이상 — 너무 붙은 항목은 뺀다
    out, last = [], -99
    for stamp, label in rows:
        sec = sum(int(p) * 60 ** k for k, p in enumerate(reversed(stamp.split(":"))))
        if sec - last >= 10 or not out:
            out.append(f"{stamp} {label}")
            last = sec
    return "\n".join(out)


def meta(s: dict, starts: list[float] | None = None, short_of: str | None = None,
         more: list[tuple[str, str]] | None = None) -> dict:
    tags = list(dict.fromkeys(s["tags"] + ["nine tails tales", "korean folklore", "korean mythology"]))
    src = "\n".join(f"• {x}" for x in s["sources"])
    chap = chapters(s, starts) if starts else ""
    # 앞서 올린 편 링크 — 새 편이 옛 편을, 옛 편의 검색 유입이 새 편을 끌어 준다(역주행)
    more_txt = ("More tales from Gumi:\n" + "\n".join(f"▶ {t} — {u}" for t, u in more[:4]) + "\n\n") if more else ""
    desc = (f"{s['hook']}\n\n"
            f"Tale {s['id']:03d} of 1,000 — told by Gumi, a 1,000-year-old gumiho.\n\n"
            + (f"{chap}\n\n" if chap else "")
            + more_txt
            + f"Sources & further reading:\n{src}\n\n{ABOUT}\n\n{AI_NOTE}\n\n"
            + "#gumiho #koreanfolklore #koreanmythology")
    out = {"title": s["title"][:100], "description": desc[:4900], "tags": tags}
    sh = s["short"]
    sdesc = (f"{s['hook']}\n\n"
             + (f"Full tale: {short_of}\n\n" if short_of else "Full tale on the channel.\n\n")
             + f"{AI_NOTE}\n\n#shorts #gumiho #koreanfolklore #koreanlegend")
    out["short"] = {"title": sh["title"][:100], "description": sdesc, "tags": tags[:15]}
    return out


# ── 다음 편 ──────────────────────────────────────────────
def assigned_id(date: str) -> int:
    """날짜 → 편 번호. catalog.start(루틴 첫 실행일, 수요일)부터 7일 안이 2편, 그 뒤 7일마다 +1(루틴이 한 주 빠져도 번호는 밀리지 않는다)."""
    import datetime as dt
    start = dt.date.fromisoformat(load(CATALOG)["start"])
    d = dt.date.fromisoformat(date)
    return 2 + max(0, (d - start).days // 7)


def entry(tale_id: int) -> dict | None:
    return next((e for e in load(CATALOG)["tales"] if e["id"] == tale_id), None)


def written_ids() -> set[int]:
    ids = set()
    for d in (SCRIPTS, ROUTINE_DIR):
        for p in glob.glob(os.path.join(d, "*.json")):
            m = re.match(r"(\d{3})_", os.path.basename(p))
            if m:
                ids.add(int(m.group(1)))
    return ids


def next_entry(date: str | None = None) -> dict | None:
    """date 가 있으면 그 주의 편(결정론적). 없으면 catalog 에서 대본이 없는 가장 앞 번호."""
    if date:
        return entry(assigned_id(date))
    done = written_ids()
    return next((e for e in load(CATALOG)["tales"] if e["id"] not in done and not e.get("done")), None)


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for p in sys.argv[2:]:
            s = load(p)
            errs = check(s, p)
            st = stats(s)
            print(f"{'✅' if not errs else '❌'} {os.path.basename(p)} · 장면 {st['scenes']} · {st['words']}단어"
                  f" · 약 {st['est_min']}분 · 그림 {st['images']} · 챕터 {st['chapters']}")
            for e in errs:
                print(f"   ✗ {e}")
            bad += bool(errs)
        return 1 if bad else 0
    if len(sys.argv) >= 2 and sys.argv[1] == "next":
        date = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[2] == "--date" else None
        e = next_entry(date)
        if not e:
            print("catalog 끝 — 새 항목을 추가할 것")
            return 1
        e = dict(e, file=f"{e['id']:03d}_{e['slug']}.json", already_written=e["id"] in written_ids())
        print(json.dumps(e, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
