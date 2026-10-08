#!/usr/bin/env python3
"""띠 궁합표 쇼츠 — 내 띠를 찾으면 찰떡 짝과 조심할 띠가 바로 보이는 표 (2026-10-07).

왜: 왕별이를 운세 전문 채널로 좁히면서(10/7) 운세 안에서 주제를 넓힌다. 지난 30일 유튜브 수요(10/7 실측):
  '띠 궁합' 상위 20편 중앙값 7.6만 회(가화만사성 '부부 띠 궁합 순위' 17만 · '띠별 찰떡궁합 짝꿍' 17만).
  - 우리 강점 그대로: 0초부터 답이 전부 보인다 · 출생연도 · 근거(전통 지지 관계 — pulli_card 와 같은 표).
  - 같은 짝을 매번 순위로 세우면 늘 비슷한 영상이 된다 → '묶음'(부부·친구·사돈·손주)을 돌려 가며,
    묶음마다 보는 관계가 다르다(부부 = 육합·충, 친구 = 삼합·원진, 사돈 = 합 둘·부딪힘 둘, 손주 = 아이 띠).

근거(전통 명리의 지지 관계 — 재미로 보는 운세라는 고지는 그대로):
  육합(손발이 맞는 짝) · 삼합(한 팀이 되는 셋) · 충(정면으로 부딪힘) · 원진(서로 서운함이 쌓임).
  같은 등급 안에서는 두 띠의 오행이 서로 살리는(상생) 짝을 앞에 둔다.

편성: 화·금 18:13 KST(GUNGHAP_DAYS) — 날짜로 묶음을 정한다(루틴 판단이 아니다).
  ★6편 시리즈로 끝난다(묶음마다 한 번 — 같은 표를 다시 올리지 않는다). 그 뒤는 성적을 보고 새 묶음을 PR 로 채운다.

    python pipeline/gunghap_card.py show [--date 2026-10-09]
    python pipeline/gunghap_card.py make [--date …] --out <path>   # 편성일이 아니면 아무것도 안 쓴다(종료 코드 0)
    python pipeline/gunghap_card.py path [--date …]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fortune_card import ANIMALS, years_of  # noqa: E402
import birth_basis  # noqa: E402
from pulli_card import (BRANCH_EL, CTL, EL_WORD, GEN, HOOK_TAIL, SAMHAP, WONJIN, YUKHAP, josa,  # noqa: E402
                        kst_today)

TOPIC = "fortune_gunghap"
ACCENT = "#E8657A"
BRAND = "왕별이 · 띠 궁합표"
START = dt.date(2026, 10, 9)          # 첫 편(금) — 묶음 순환의 0번
GUNGHAP_DAYS = (1, 4)                 # 화·금(월=0)
GRAND_YEARS = (2008, 2025)            # 손주 출생연도 범위


def pair_of(rel_pairs: list, b: int) -> int:
    return next(y if x == b else x for x, y in rel_pairs if b in (x, y))


def samhap_mates(b: int) -> tuple[list[int], str]:
    grp, nm = next((g, n) for g, n in SAMHAP if b in g)
    return [x for x in grp if x != b], nm


def chung(b: int) -> int:
    return (b + 6) % 12


def sangsaeng(a: int, b: int) -> bool:
    ea, eb = BRANCH_EL[a], BRANCH_EL[b]
    return GEN[ea] == eb or GEN[eb] == ea


def el_note(a: int, b: int) -> str:
    """두 띠 오행의 관계 한 줄 — '물이 나무를 살려요'. 서로 다른 기운이면 빈 문자열."""
    ea, eb = BRANCH_EL[a], BRANCH_EL[b]
    if ea == eb:
        return f"둘 다 {EL_WORD[ea]} 기운"
    if GEN[ea] == eb:
        return f"{josa(EL_WORD[ea], '이', '가')} {josa(EL_WORD[eb], '을', '를')} 살려요"
    if GEN[eb] == ea:
        return f"{josa(EL_WORD[eb], '이', '가')} {josa(EL_WORD[ea], '을', '를')} 살려요"
    return ""


def grand_years(b: int) -> list[int]:
    return [y for y in range(GRAND_YEARS[0], GRAND_YEARS[1] + 1) if (y - 1924) % 12 == b]


# 묶음 — good/bad 는 (띠 번호) → [(짝 띠, 관계 이름)] · card = 화면 제목 · cols = 표 머리
def _couple(b):
    return [(pair_of(YUKHAP, b), "육합")], [(chung(b), "충")]


def _friends(b):
    mates, nm = samhap_mates(b)
    mates.sort(key=lambda x: (not sangsaeng(b, x), x))
    return [(x, f"{nm} 삼합") for x in mates], [(pair_of(WONJIN, b), "원진")]


def _inlaw(b):
    mates, nm = samhap_mates(b)
    good = [(pair_of(YUKHAP, b), "육합")] + [(x, f"{nm} 삼합") for x in mates]
    good.sort(key=lambda g: (g[1] != "육합" and not sangsaeng(b, g[0]), g[1] != "육합", g[0]))
    return good[:2], [(chung(b), "충"), (pair_of(WONJIN, b), "원진")]


def _grand(b):
    g, bad = _inlaw(b)
    return g, bad[:1]


def _by_el(el: str, b: int) -> list[int]:
    return [x for x in range(12) if BRANCH_EL[x] == el and x != b]


def _money(b):
    """재물 궁합 — 내가 다스리는 오행(재성)의 띠가 재물을 불러온다 · 정면으로 부딪히는 충은 돈 다툼."""
    me = BRANCH_EL[b]
    c = chung(b)
    money = _by_el(CTL[me], b)
    # 충인 띠가 재성이기도 하면(쥐↔말·돼지↔뱀·원숭이↔호랑이·닭↔토끼) 재물 쪽에서 빼고 '재물 다툼'으로 둔다
    return [(x, "재성") for x in money if x != c], [(c, "충(재물)" if c in money else "충")]


def _helper(b):
    """귀인 궁합 — 나를 살리는 오행(인성)의 띠가 귀인 · 나를 누르는 오행(관성)의 띠는 기가 눌린다."""
    me = BRANCH_EL[b]
    gen_me = next(e for e, t in GEN.items() if t == me)
    ctl_me = next(e for e, t in CTL.items() if t == me)
    return [(x, "인성") for x in _by_el(gen_me, b)], [(x, "관성") for x in _by_el(ctl_me, b)]


THEMES = [
    {"id": "couple", "card": "부부 띠 궁합표", "yt": "부부 띠 궁합표", "cols": ("찰떡 짝", "조심할 띠"),
     "fn": _couple, "years": "self",
     "why": "부부는 육합(손발이 맞는 짝)을 가장 좋게, 정면으로 부딪히는 충을 조심할 짝으로 봤어요",
     "hook": "a warm Korean living room at golden hour with two teacups on a low wooden table and a pair of "
             "embroidered cushions side by side, soft and loving mood, no people"},
    {"id": "friends", "card": "친구·동업 궁합표", "yt": "친구·동업 띠 궁합표", "cols": ("한 팀 되는 띠", "서운해지는 띠"),
     "fn": _friends, "years": "self",
     "why": "친구·동업은 셋이 한 팀이 되는 삼합을 좋게, 서운함이 쌓이는 원진을 조심할 짝으로 봤어요",
     "hook": "a cozy Korean traditional tea house corner with three cups of tea and a plate of rice cakes on a "
             "wooden table, warm afternoon light, friendly mood, no people"},
    {"id": "money", "card": "재물 궁합표", "yt": "돈을 불러오는 띠 궁합표", "cols": ("재물 부르는 띠", "돈 다툼 띠"),
     "fn": _money, "years": "self",
     "why": "내 띠의 오행이 다스리는 기운(재성)이 재물이라, 그 오행의 띠를 재물 부르는 띠로, 정면으로 부딪히는 충을 돈 다툼 띠로 봤어요",
     "hook": "a traditional Korean wooden chest with brass fittings slightly open showing silk coin pouches, "
             "persimmons on a tray beside it, warm golden light, lucky mood, no people"},
    {"id": "helper", "card": "귀인 궁합표", "yt": "나를 돕는 귀인 띠 궁합표", "cols": ("나를 돕는 띠", "기 눌리는 띠"),
     "fn": _helper, "years": "self",
     "why": "내 띠의 오행을 살려 주는 기운(인성)의 띠를 귀인으로, 나를 누르는 기운(관성)의 띠를 기 눌리는 띠로 봤어요",
     "hook": "a Korean hanok gate slightly open onto a sunlit courtyard with a ginkgo tree in autumn colors, "
             "welcoming and hopeful mood, no people"},
    {"id": "inlaw", "card": "사돈·며느리 궁합표", "yt": "사돈·며느리·사위 띠 궁합표", "cols": ("잘 맞는 띠", "부딪히는 띠"),
     "fn": _inlaw, "years": "self",
     "why": "가족이 되는 사이는 육합·삼합 가운데 오행이 서로 살리는 띠를 앞에, 충·원진을 조심할 띠로 봤어요",
     "hook": "a festive Korean family dining table with many side dishes and a pot of stew under warm lamp "
             "light, hanok windows behind, welcoming family mood, no people"},
    {"id": "grand", "card": "손주와 잘 맞는 띠", "yt": "할머니·할아버지와 손주 띠 궁합표", "cols": ("잘 맞는 손주 띠", "부딪히는 손주 띠"),
     "fn": _grand, "years": "grand",
     "why": "내 띠와 육합·삼합인 아이 띠를 잘 맞는 손주로, 충인 띠를 부딪히는 손주로 봤어요",
     "hook": "a sunny Korean apartment living room with a small pair of children's shoes and a knitted blanket "
             "on a sofa, toys on the floor, warm grandparent mood, no people"},
]

# 표 한 줄 이유(10자 이내)
ONE = {"육합": "육합·찰떡 짝", "충": "충·정면 충돌", "원진": "원진·서운함", "재성": "재성·재물 기운",
       "인성": "인성·돕는 기운", "관성": "관성·누르는 기운", "충(재물)": "충·재물 다툼"}


def is_post_day(d: dt.date) -> bool:
    """화·금 · START 부터 · 6편 시리즈 안(목록이 바닥나면 쓰지 않는다 — 채워 넣을 때까지)."""
    return d >= START and d.weekday() in GUNGHAP_DAYS and post_index(d) < len(THEMES)


def post_index(d: dt.date) -> int:
    """START 부터 몇 번째 편인가(편성일만 센다)."""
    return sum(1 for k in range((d - START).days) if (START + dt.timedelta(days=k)).weekday() in GUNGHAP_DAYS)


def theme_for(d: dt.date) -> dict:
    """그날의 묶음. 편성일이 아닌 날(견본)은 가장 가까운 다음 편성일의 묶음, 시리즈가 끝났으면 마지막 묶음."""
    return THEMES[min(post_index(d), len(THEMES) - 1)]


def build_rows(d: dt.date, th: dict | None = None) -> list[dict]:
    th = th or theme_for(d)
    rows = []
    for b, a in enumerate(ANIMALS):
        good, bad = th["fn"](b)
        who = (lambda x: grand_years(x)) if th["years"] == "grand" else (lambda x: years_of(ANIMALS[x]))
        rows.append({
            "animal": a, "branch": b, "years": years_of(a),
            "good": [{"animal": ANIMALS[x], "rel": r, "years": who(x), "note": el_note(b, x)} for x, r in good],
            "bad": [{"animal": ANIMALS[x], "rel": r, "years": who(x)} for x, r in bad],
        })
    return rows


def cell_text(items: list[dict]) -> str:
    return "·".join(i["animal"] for i in items) + "띠"


def cell_line(items: list[dict]) -> str:
    """'육합·찰떡 짝' · '신자진 삼합' · '육합·삼합' · '충·원진'."""
    rels = list(dict.fromkeys(i["rel"] for i in items))
    if len(rels) == 1:
        return ONE.get(rels[0], rels[0])
    return "·".join(dict.fromkeys("삼합" if "삼합" in r else r for r in rels))


def title(d: dt.date, th: dict | None = None) -> str:
    th = th or theme_for(d)
    tail = "2008~2025년생 손주" if th["years"] == "grand" else "45~96년생 전부"
    return f"{th['yt']} | 내 띠의 {th['cols'][0]}·{th['cols'][1]} · {tail}"


def narration(d: dt.date, th: dict | None = None) -> str:
    th = th or theme_for(d)
    rows = build_rows(d, th)
    a, b = rows[0], rows[2]           # 쥐띠·호랑이띠 — 첫 줄과 셋째 줄을 예로
    ga, gb = cell_text(a["good"]), cell_text(b["good"])
    return (f"{th['card']}예요. 쥐띠의 {josa(th['cols'][0], '은', '는')} {ga}, 호랑이띠는 {josa(gb, '이에요', '예요')}. "
            f"내 띠도 찾아보세요.")


def description(d: dt.date) -> str:
    th = theme_for(d)
    rows = build_rows(d, th)
    lines = [f"{th['yt']} — 내 띠를 찾으면 {th['cols'][0]}와 {th['cols'][1]}가 바로 보여요.", "",
             birth_basis.ddi_note(birth_basis.ADULT[0],
                                  birth_basis.GRAND[1] if th["years"] == "grand" else birth_basis.ADULT[1]), ""]
    for r in rows:
        g = " · ".join(f"{x['animal']}띠({x['rel']}{', ' + x['note'] if x.get('note') else ''})" for x in r["good"])
        bd = " · ".join(f"{x['animal']}띠({x['rel']})" for x in r["bad"])
        yrs = "·".join(f"{y % 100:02d}" for y in r["years"])
        lines.append(f"· {r['animal']}띠({yrs}년생) — {th['cols'][0]}: {g} / {th['cols'][1]}: {bd}")
    if th["years"] == "grand":
        lines += ["", "손주 띠 출생연도: " + " · ".join(
            f"{a}띠 {'·'.join(str(y) for y in grand_years(k))}" for k, a in enumerate(ANIMALS))]
    lines += ["", f"궁합은 이렇게 봤어요: {th['why']}. 두 띠의 오행이 서로 살리는 짝은 앞에 뒀어요.",
              "우리 집은 몇 쌍이 찰떡인가요? 댓글로 남겨 주세요 🙏", "",
              "※ 전통 명리의 띠 궁합(지지 관계)을 재미로 정리한 운세입니다. 사람 사이는 띠보다 마음이 먼저예요.", "",
              f"#띠궁합 #궁합 #띠별운세 #{th['card'].replace(' ', '').replace('·', '')} #운세 #shorts"]
    return "\n".join(lines)


def storyboard(d: dt.date) -> dict:
    th = theme_for(d)
    rows = build_rows(d, th)
    t = title(d, th)
    scene_rows = [{"animal": r["animal"], "years": r["years"],
                   "good": cell_text(r["good"]), "good_line": cell_line(r["good"]),
                   "bad": cell_text(r["bad"]), "bad_line": cell_line(r["bad"])} for r in rows]
    foot = ("손주 띠 = 2008~2025년생 · " if th["years"] == "grand" else "") + "육합·삼합·충·원진 — 전통 띠 궁합, 재미로 보세요"
    return {
        "date": d.isoformat(), "topic": TOPIC, "theme": th["id"], "privacy": "public",
        "accent": ACCENT, "_min_total": 9.0,
        "hook_title": th["yt"], "headline": t, "thumbnail_hook": th["hook"] + HOOK_TAIL,
        "scenes": [{"type": "gunghap", "pill": ("12띠 전부 · 손주 08~25년생" if th["years"] == "grand" else "12띠 전부 · 45~96년생"), "title": th["card"],
                    "cols": list(th["cols"]), "rows": scene_rows, "foot": foot,
                    "basis": birth_basis.SCREEN_DDI_WIDE if th["years"] == "grand" else birth_basis.SCREEN_DDI,
                    "brand": BRAND,
                    "narration": narration(d, th)}],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d)}},
        "notes": f"띠 궁합표 · theme={th['id']} · gunghap_card.py 가 만든 스토리보드",
    }


def is_gunghap(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(sb["date"])
    return {"title": title(d)[:95], "description": description(d)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="띠 궁합표")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true", help="편성일이 아니어도 만든다(견본용)")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(path_for(d))
        return 0
    if a.cmd == "make" and not (a.force or is_post_day(d)):
        print(f"{d}: 궁합표 편성일이 아니다(화·금, {START} 부터) — 건너뜀")
        return 0
    sb = storyboard(d)
    if a.cmd == "show":
        print(f"{d} · {sb['theme']} · {sb['platforms']['youtube']['title']}")
        for r in sb["scenes"][0]["rows"]:
            print(f"  {r['animal']:<4} {r['good']:<10} ({r['good_line']}) | {r['bad']:<8} ({r['bad_line']})")
        print("  🎙️", sb["scenes"][0]["narration"])
        return 0
    out = a.out or path_for(d)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
