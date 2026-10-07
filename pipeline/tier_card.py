#!/usr/bin/env python3
"""띠별 '운세 등급표'(S·A·B·C 티어표) 쇼츠 — 같은 근거, 다른 생김새 (2026-10-07).

왜: 같은 '1위~12위 표'만 반복하면 조회가 정체된다(사용자 10/7 — 10/6 하루 조회 −32%, 오후 표 두 편이 피드에서 멈춤).
  숏폼에서 잘 되는 '티어표'(항목을 S·A·B·C 칸에 넣는 형식 · 사용자가 10/6 보내 준 릴스)를 우리 방식으로 바꿨다.
  - 우리 강점은 그대로: 0초부터 답이 전부 보인다 · 출생연도 · 55세 이상 말투 · 전통 일진 근거(pulli_card 와 같은 계산).
  - 바뀌는 것: 순위 대신 네 칸으로 묶는다. 칸마다 들어가는 띠 수가 날마다 다르다(S는 늘 3, 나머지 1~6) —
    '서로 바꿔 끼워도 될 만큼 비슷한 영상'(수익화 정책)에서 한 걸음 더 멀어진다.

등급(오늘 일진의 띠와 내 띠의 관계 — pulli_card.relation · sipsin):
  S 대길 = 육합·삼합(손발이 맞는 짝)
  A 길   = 같은 띠, 또는 관계가 없고 나를 돕는 기운(인성)·같은 기운(비겁)
  B 보통 = 가벼운 엇갈림(해·파), 또는 관계가 없고 내보내는 기운(식상)·재물(재성)·일(관성)
  C 조심 = 충·원진·형
  칸 안 순서 = 관계 세기 → 십신 기본점 → 일진 띠부터의 순서.

시험(A/B, 2026-10-09~10-22): 06:13 '매일 운세 표'(fortune_card, 1~12위) 자리에서 하루씩 번갈아 등급표를 낸다.
  같은 시각·같은 시청자에서 두 형식을 비교한다. 루틴은 그대로 운세 대본을 올리고, 등급표 날엔 파이프라인이
  화면·제목·설명만 등급표로 바꾼다(날짜로 정한다 — 루틴 판단이 아니다). 월요일 '이번 주 운세'는 건드리지 않는다.
  판정 10/23(채널 맥박 tier-ab). 끄기: 레포 변수 FORTUNE_TIER=0 · 매일 등급표: FORTUNE_TIER=1

    python pipeline/tier_card.py show [--date 2026-10-08]     # 등급표 미리보기
    python pipeline/tier_card.py make [--date …] --out <path> # 스토리보드 JSON
    python pipeline/tier_card.py path [--date …]              # 오늘 파일 경로(output/news/…)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fortune_card import ANIMALS, WEEKDAY, years_of  # noqa: E402
from pulli_card import (CAT_BASE, EL_WORD, HOOK_TAIL, LINE_CAT, LINE_REL, REL,  # noqa: E402
                        ganzhi, josa, kst_today, reason, relation, sipsin)

TOPIC = "fortune_tier"
AB_START = dt.date(2026, 10, 9)       # 이날부터 짝수 번째 날(0·2·4…)이 등급표
AB_END = dt.date(2026, 10, 22)        # 2주 — 끝나면 기존 표로 돌아간다(판정 PR 이 바꾼다)
ACCENT = "#C9A227"
BRAND = "왕별이 · 오늘의 일진 등급표"

# 등급 — color 는 화면 칸 색(어두운 글자가 올라간다). id 는 코드 안 이름일 뿐, 화면·목소리·제목엔 label·stars 를 쓴다
# (2026-10-07 사용자: 왕별이는 어르신 채널 — 'S급·C급'·'에스급' 같은 게임 말투는 위화감이 있다).
TIERS = [
    {"id": "S", "label": "대길", "stars": "★★★★", "color": "#FF6B6B", "basis": "오늘 일진과 합(육합·삼합)"},
    {"id": "A", "label": "길", "stars": "★★★", "color": "#FFA94D", "basis": "같은 띠 · 나를 돕는 기운"},
    {"id": "B", "label": "보통", "stars": "★★", "color": "#FFD43B", "basis": "무난한 기운 · 가벼운 엇갈림(해·파)"},
    {"id": "C", "label": "조심", "stars": "★", "color": "#74C0FC", "basis": "충·원진·형"},
]
TIER_IDS = [t["id"] for t in TIERS]
# 배경 키비주얼 — 10/7 견본에서 '매듭 장식·축제' 를 넣었더니 중국 설날 그림(快乐 글자)이 나왔다. 한옥 방·감으로.
HOOK = ("a cozy Korean hanok room in warm autumn morning light, a low wooden table with a brass bowl of persimmons "
        "and a celadon teacup, paper sliding doors, calm and lucky mood, no people")


def tier_of(rel: str, cat: str) -> str:
    if rel in ("육합", "삼합"):
        return "S"
    if rel in ("충", "원진", "형"):
        return "C"
    if rel in ("해", "파"):
        return "B"
    if rel == "같은 띠" or cat in ("인성", "비겁"):
        return "A"
    return "B"


def build_tiers(d: dt.date) -> list[dict]:
    """[{id,label,color,basis,items:[{animal,years,line,rel,cat,branch}]}] — S→C, 빈 칸 없음은 보장하지 않는다."""
    g = ganzhi(d)
    items = []
    for b, a in enumerate(ANIMALS):
        rel, grp = relation(g["branch"], b)
        cat = sipsin(g["el"], b)
        line = LINE_REL[rel].format(d=g["animal"], g=grp) if rel else LINE_CAT[cat]
        items.append({"animal": a, "branch": b, "rel": rel, "group": grp, "cat": cat, "years": years_of(a),
                      "line": line, "tier": tier_of(rel, cat)})
    items.sort(key=lambda r: (REL[r["rel"]][1], -CAT_BASE[r["cat"]], (r["branch"] - g["branch"]) % 12))
    return [dict(t, items=[r for r in items if r["tier"] == t["id"]]) for t in TIERS]


def title(d: dt.date) -> str:
    return f"오늘 띠별 운세 등급표 대길~조심 | {d.month}월 {d.day}일 {ganzhi(d)['name']}일 · 45~96년생 전부"


def narration(d: dt.date) -> str:
    g, tiers = ganzhi(d), build_tiers(d)
    s, c = tiers[0]["items"], tiers[3]["items"]
    # ★우리말 등급(대길·조심) — 영문 등급은 어르신께 위화감(10/7). 조심 띠는 꾸짖지 않고 조언으로.
    # ★짧게(9초 안팎) — 표는 짧아야 다시 돈다(기존 표 8~10초). 날짜는 화면 위 알약에 있다.
    say = f"{g['name']}일 띠별 운세 등급표예요. 대길은 {', '.join(r['animal'] for r in s)}띠. "
    if c:
        say += f"{', '.join(r['animal'] for r in c)}띠는 오늘 한 박자 쉬어 가세요. "
    return say + "내 띠도 찾아보세요."


def description(d: dt.date) -> str:
    """설명란 = 12띠 전부의 등급과 이유(메타데이터도 심사가 본다 — 날마다 내용이 다르다)."""
    g, tiers = ganzhi(d), build_tiers(d)
    lines = [f"오늘 띠별 운세 등급표 — {d.month}월 {d.day}일은 {g['name']}일({g['hanja']}日), "
             f"{EL_WORD[g['el']]} 기운의 {g['animal']}날이에요.", ""]
    for t in tiers:
        lines.append(f"[{t['label']} {t['stars']}] {t['basis']}")
        lines += [f"· {r['animal']}띠({'·'.join(f'{y % 100:02d}' for y in r['years'])}년생) — {reason(r, g)}."
                  for r in t["items"]] or ["· 오늘은 없어요."]
        lines.append("")
    lines += [f"등급은 이렇게 정했어요: 오늘 일진의 띠({g['animal']})와 내 띠가 합(육합·삼합)이면 대길, "
              "충·원진·형이면 조심, 그 사이는 오늘 기운과 내 띠 오행의 관계로 길·보통을 나눴어요.",
              "내 띠는 어디에 있나요? 댓글로 남겨 주세요 🙏", "",
              "※ 전통 명리의 일진 풀이를 재미로 정리한 운세입니다.", "",
              f"#운세 #띠별운세 #오늘의일진 #{g['name']}일 #운세등급표 #shorts"]
    return "\n".join(lines)


def storyboard(d: dt.date) -> dict:
    g = ganzhi(d)
    tiers = build_tiers(d)
    pill = f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · {g['name']}일"
    t = title(d)
    scene_tiers = [{"id": x["id"], "label": x["label"], "big": x["label"], "small": x["stars"], "color": x["color"],
                    "items": [{k: r[k] for k in ("animal", "years", "line")} for r in x["items"]]} for x in tiers]
    return {
        "date": d.isoformat(), "topic": TOPIC, "ganzhi": g["name"], "privacy": "public",
        "accent": ACCENT, "_min_total": 9.0,
        "hook_title": "오늘 띠별 운세 등급표", "headline": t, "thumbnail_hook": HOOK + HOOK_TAIL,
        "scenes": [
            {"type": "tier", "pill": pill, "title": "오늘 띠별 운세 등급표", "tiers": scene_tiers,
             "foot": f"대길 = 합 · 조심 = 충·원진·형 — {g['name']}일 일진 풀이, 재미로 보세요",
             "brand": BRAND, "narration": narration(d)},
        ],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d)}},
        "notes": f"운세 등급표(티어표) · 일진 {g['name']} · tier_card.py 가 만든 스토리보드",
    }


def use_ab(sb: dict) -> bool:
    """06:13 매일 운세 스토리보드를 오늘 등급표로 바꿔 낼 날인가. 주간·테마·이름·풀이형 표는 건드리지 않는다."""
    from fortune_card import sb_date, scope_of
    mode = os.environ.get("FORTUNE_TIER", "ab").strip().lower()
    if mode in ("0", "false", "off"):
        return False
    t = str(sb.get("topic") or "").lower()
    if not t.startswith("fortune") or t.startswith(("fortune_theme", "fortune_name", "fortune_pulli", "fortune_tier", "fortune_gunghap",
                                                    "fortune_newyear")):
        return False
    if scope_of(sb) != "오늘":
        return False
    d = sb_date(sb)
    if not d or d < AB_START:
        return False
    if mode in ("1", "true", "on"):
        return True
    return d <= AB_END and (d - AB_START).days % 2 == 0


def build_spec(sb: dict) -> dict:
    """운세 스토리보드 날짜의 등급표 장면(렌더 스펙). 배경 그림은 루틴 대본의 것을 그대로 쓴다."""
    d = dt.date.fromisoformat(str(sb["date"])[:10])
    t = storyboard(d)
    return {"topic": t["topic"], "date": t["date"], "accent": t["accent"], "_min_total": t["_min_total"], "scenes": t["scenes"]}


def is_tier(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(sb["date"])
    return {"title": title(d)[:95], "description": description(d)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="운세 등급표(티어표)")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--out")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(path_for(d))
        return 0
    sb = storyboard(d)
    if a.cmd == "show":
        g = ganzhi(d)
        print(f"{d} {g['name']}일({g['hanja']}) · {sb['platforms']['youtube']['title']}")
        for t in build_tiers(d):
            print(f"  {t['id']} {t['label']:<3} " + " · ".join(f"{r['animal']}({r['line']})" for r in t["items"]))
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
