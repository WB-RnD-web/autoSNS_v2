#!/usr/bin/env python3
"""띠별 운세 '12띠 한 장 표' 쇼츠 (2026-09-29).

왜: 경쟁 채널 실측(2026-09-29) — 5~9초짜리 한 장 표가 구독 1~10천 채널에서도 5만~40만 회가 나왔다
  (월하당 "오늘의 띠별 운세" 6.7만 · 가화만사성 "자식 덕 보는 나이 50~91년생 전부" 16.8만).
  우리 운세는 27~36초 내레이션형이고 편당 ~1,000회에서 멈춘다.
  → 격일로 두 형식을 번갈아 내보내 비교한다(A/B).

배정: ★2026-10-01 부터 매일 표(9/30 표 첫 편 5,700회·좋아요 101 — 기존 형식은 편당 ~800~1,000회에서 멈췄다).
  FORTUNE_CARD=ab 면 예전처럼 CARD_START 부터 짝수 날 = 표, 홀수 날 = 기존 형식. FORTUNE_CARD=0 이면 끈다.
  루틴 판단이 아니라 스토리보드 날짜로 정한다.
  ★2026-10-27부터 화·토(12/8부터 화·금·토) 06:13 은 '2027 신년운세 시리즈'(newyear_series.py)가 먼저 쓴다(run_pipeline 순서).
데이터: 루틴 스토리보드에는 1~3위만 있다 → 그대로 쓰고, 4~12위·점수·한 줄은 날짜 해시로 정한다
  (같은 날짜면 늘 같은 표). 재미로 보는 운세라는 고지는 설명란에 넣는다.

  ★2026-10-31부터 스토리보드도 코드가 쓴다(make — 1~3위 = 일진과 육합·삼합). 루틴은 실행 스위치만.

    python fortune_card.py <storyboard.json>     # 표 데이터 미리보기
    python fortune_card.py make [--date …] [--out …]   # 06:13 운세 스토리보드(output/news/<날짜>_fortune_storyboard.json)
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import sys

import birth_basis

CARD_START = dt.date(2026, 9, 30)

ANIMALS = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]
ALIAS = {"범": "호랑이"}
YEAR_MIN, YEAR_MAX = 1945, 1996      # 표에 적는 출생연도 범위(시청자 88%가 55세 이상)

# 한 줄은 9자 이내 — 한 칸에 한 줄로 들어가야 한다. 단정·겁주기 금지(엔터테인먼트 톤).
LINES = {
    "top": ["재물운 활짝", "귀인이 와요", "기쁜 소식", "하는 일 술술", "막힌 일 풀려요", "돈 들어와요"],
    "mid": ["작은 행운", "반가운 연락", "천천히 가면 이득", "소소한 기쁨", "관계가 순조", "건강 챙기면 굿"],
    "low": ["말 한마디 조심", "지갑 단속", "무리는 금물", "서두르면 손해", "약속 다시 확인", "마음 느긋하게"],
}
WEEKDAY = "월화수목금토일"
_RANK_RE = re.compile(r"([1-3])\s*위\s*(?:는|은)?\s*[·:—\-]?\s*(?:<b>)?\s*("
                      + "|".join(ANIMALS + list(ALIAS)) + r")띠")


def is_card_day(d: dt.date) -> bool:
    return d >= CARD_START and (d - CARD_START).days % 2 == 0


def sb_date(sb: dict) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(sb.get("date") or "")[:10])
    except ValueError:
        return None


def use_card(sb: dict) -> bool:
    """운세 스토리보드면 True(CARD_START 이후 매일). FORTUNE_CARD=ab 면 격일 A/B, =0 이면 끈다."""
    import os
    mode = os.environ.get("FORTUNE_CARD", "1").strip().lower()
    if mode in ("0", "false", "off"):
        return False
    t = str(sb.get("topic") or "").lower()
    # 낮 12시 테마 표는 theme_card, 09:40·15:40 '내 것 찾기' 표는 name_card, 10:40 풀이형 표는 pulli_card, 운세 등급표는 tier_card, 띠 궁합표는 gunghap_card, 2027 신년운세는 newyear_card 가 만든다
    if not t.startswith("fortune") or t.startswith(("fortune_theme", "fortune_name", "fortune_pulli", "fortune_tier", "fortune_gunghap",
                                                    "fortune_newyear")):
        return False
    d = sb_date(sb)
    if not d:
        return False
    if mode == "ab":
        return is_card_day(d)
    return d >= CARD_START


def _h(*parts) -> int:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest(), 16)


def years_of(animal: str) -> list[int]:
    k = ANIMALS.index(animal)
    return [y for y in range(YEAR_MIN, YEAR_MAX + 1) if (y - 1924) % 12 == k]


def _texts(sb: dict) -> list[str]:
    out = []
    for sc in sb.get("scenes") or []:
        for key in ("label", "sub", "narration", "text"):
            if sc.get(key):
                out.append(str(sc[key]))
        for key in ("points", "lines"):
            out += [str(x) for x in sc.get(key) or []]
    return out


def top_from_storyboard(sb: dict) -> tuple[list[str], int | None]:
    """스토리보드에서 1~3위 띠와 1위 점수를 뽑는다. 못 찾은 순위는 빈 채로 둔다."""
    ranks: dict[int, str] = {}
    for t in _texts(sb):
        for m in _RANK_RE.finditer(t):
            r, a = int(m.group(1)), ALIAS.get(m.group(2), m.group(2))
            if r not in ranks and a not in ranks.values():
                ranks[r] = a
    score = None
    first = ranks.get(1)
    for sc in sb.get("scenes") or []:
        if sc.get("type") == "stat" and first and first + "띠" in str(sc.get("label", "")):
            try:
                score = int(float(sc.get("to")))
            except (TypeError, ValueError):
                pass
    return [ranks[r] for r in sorted(ranks)], score


def scope_of(sb: dict) -> str:
    notes = str(sb.get("notes") or "")
    if "MODE=monthly" in notes:
        return "이번 달"
    if "MODE=weekly" in notes:
        return "이번 주"
    return "오늘"


def build_rows(sb: dict, key=None) -> list[dict]:
    """key: 해시 씨앗(기본 = 스토리보드 날짜). 주간 롱폼(weekly_fortune)은 '2026-W41' 같은 주 번호를 준다
    — 같은 방식으로 뽑되 월요일 하루 표와 똑같아지지 않게."""
    d = sb_date(sb) or dt.date.today()
    k = d if key is None else key
    top, s1 = top_from_storyboard(sb)
    rest = sorted((a for a in ANIMALS if a not in top), key=lambda a: _h(k, "order", a))
    order = top + rest
    score = max(80, min(99, s1 or 90 + _h(k, "s1") % 8))
    rows, used = [], {"top": set(), "mid": set(), "low": set()}
    for i, a in enumerate(order):
        if i:
            score -= 1 + _h(k, "gap", i) % 3
        score = max(score, 58)
        tier = "top" if i < 3 else ("mid" if i < 8 else "low")
        bank = [x for x in LINES[tier] if x not in used[tier]] or LINES[tier]
        line = bank[_h(k, "line", a) % len(bank)]
        used[tier].add(line)
        rows.append({"rank": i + 1, "animal": a, "years": years_of(a), "score": score, "line": line})
    return rows


def date_label(d: dt.date) -> str:
    return f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일"


def build_spec(sb: dict) -> dict:
    d = sb_date(sb) or dt.date.today()
    scope = scope_of(sb)
    brand = next((sc.get("brand") for sc in sb.get("scenes") or [] if sc.get("brand")), "일상공감뉴스 · 운세")
    return {
        "topic": sb.get("topic", "fortune"), "date": sb.get("date"),
        "accent": sb.get("accent") or "#C9A227",
        "_min_total": 7.0,       # 표를 읽을 시간 — 내레이션이 짧아도 7초는 머문다
        "scenes": [{
            "type": "card", "pill": date_label(d), "title": f"{scope} 띠별 운세 순위",
            "rows": build_rows(sb), "brand": brand, "basis": birth_basis.SCREEN_DDI,
            "narration": f"{scope} 띠별 운세 순위입니다. 내 띠는 몇 위인지 확인하고, 댓글로 남겨 주세요.",
        }],
    }


def meta(sb: dict) -> dict:
    """제목·설명 — 출생연도 범위를 제목에 넣는다(경쟁 채널 상위 제목의 공통점)."""
    d = sb_date(sb) or dt.date.today()
    scope = scope_of(sb)
    title = f"{scope} 띠별 운세 1위~12위 | {d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · 45~96년생 전부"
    desc = (f"{scope} 12띠 운세를 한 장에 모았어요. 내 띠는 몇 위인가요? 댓글로 남겨 주세요 🙏\n\n"
            f"{birth_basis.ddi_note()}\n\n"
            "※ 재미로 보는 운세입니다.\n\n"
            f"#운세 #띠별운세 #{scope.replace(' ', '')}운세 #오늘의운세 #shorts")
    return {"title": title[:95], "description": desc}


# ── 06:13 매일 운세 스토리보드를 코드로(2026-10-31) ─────────────────────────────────
# 왜: 운세 루틴이 매일 18KB 프롬프트로 7장면 대본·번역을 썼지만, 영상은 위 build_spec(1~3위 띠·1위 점수만 읽는다)·
#   newyear_series(화·토)가 만들고 대본 본문은 버려졌다 — 루틴이 구독 주간 한도만 썼다. 이제 다른 표처럼 코드가 쓰고
#   루틴은 실행 스위치만 한다(theme_card make 와 같은 꼴).
# 1~3위: 그날 일진의 띠와 육합 1 + 삼합 2(풀이형 표·등급표와 같은 계산 → 같은 날 표끼리 말이 엇갈리지 않는다), 순서·점수는 날짜 해시.
# 주간(월요일)·월간(1일)은 예전 루틴처럼 notes 의 MODE 로만 드러난다(scope_of) — 기준 날은 그 주 월요일·그달 1일의 일진.
ANIMAL_EN = ["rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "goat", "monkey", "rooster", "dog", "pig"]
BG_SHOTS = [   # 키비주얼·커버 배경(cover_short.build_bg) — 날마다 구도를 바꾼다(같은 구도 연달아 금지 · 예전 루틴 규칙)
    "a golden {a} emblem in front view, traditional Korean auspicious clouds, deep amethyst starry night",
    "close-up of a golden {a} emblem's glowing amber eye, fine engraved texture, soft bokeh, deep amethyst night",
    "silhouette of a golden {a} standing on auspicious clouds at dawn, warm light rays, calm majestic mood",
    "still life of gold coins and a red Korean lucky pouch beside a small golden {a} figurine, warm lamp light",
    "a golden {a} emblem over a quiet Korean hanok roof under a starry sky, soft moonlight, peaceful lucky mood",
    "a golden {a} constellation drawn in stars over misty mountains at dawn, serene auspicious mood",
]
MODE_PILL = {"daily": "오늘의 운세", "weekly": "이번 주 운세", "monthly": "이번 달 운세"}
MODE_GHOST = {"daily": "FORTUNE", "weekly": "WEEKLY", "monthly": "MONTHLY"}


def mode_of(d: dt.date) -> str:
    """예전 루틴 규칙 그대로: 1일 = 월간, (1일이 아닌) 월요일 = 주간, 그 밖 = 오늘."""
    return "monthly" if d.day == 1 else ("weekly" if d.weekday() == 0 else "daily")


def top3(d: dt.date) -> list[tuple[str, str]]:
    """[(띠, 이유)] 1위부터 — 일진의 띠와 육합 1 + 삼합 2."""
    import pulli_card as P
    g = P.ganzhi(d)
    b = g["branch"]
    mates = [(x, "육합") for p in P.YUKHAP if b in p for x in p if x != b]
    mates += [(x, f"{nm} 삼합") for grp, nm in P.SAMHAP if b in grp for x in grp if x != b]
    mates.sort(key=lambda m: _h(d, "top", m[0]))
    day = f"{g['name']}({g['hanja']})일 {g['animal']}의 날"
    return [(ANIMALS[x], f"{day}과 {rel}") for x, rel in mates[:3]]


def path_for(d: dt.date, root: str | None = None) -> str:
    import os
    root = root or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "news")
    return os.path.join(root, f"{d.isoformat()}_fortune_storyboard.json")


def make_storyboard(d: dt.date) -> dict:
    mode = mode_of(d)
    scope = {"daily": "오늘", "weekly": "이번 주", "monthly": "이번 달"}[mode]
    base = d if mode == "daily" else (d.replace(day=1) if mode == "monthly" else d - dt.timedelta(days=d.weekday()))
    (a1, why1), (a2, _), (a3, _) = top3(base)
    s1 = 88 + _h(d, "s1") % 10
    ys = [y for y in years_of(a1) if 1950 <= y <= 1990][-3:]
    brand = "일상공감뉴스 · 운세"
    hook = f"{scope} 1위는 {a1}띠"
    head = f"{d.month}월 {d.day}일 {scope} 띠별 운세 순위"
    return {
        "date": d.isoformat(), "topic": "fortune", "privacy": "public",
        "topic_keyword": f"{scope} 띠별 운세", "headline": head, "hook_title": hook, "accent": "#C9A24B",
        "thumbnail_hook": BG_SHOTS[_h(d, "bg") % len(BG_SHOTS)].format(a=ANIMAL_EN[ANIMALS.index(a1)])
        + ", no human face, no text in image",
        "thumbnail_text": f"{scope} 1위 {a1}띠",
        "scenes": [
            {"type": "hook", "pill": MODE_PILL[mode], "ghost": MODE_GHOST[mode], "lines": [scope, "딱 한 띠만", "운이 열려요"],
             "highlight": "딱 한 띠", "brand": brand, "narration": f"{scope}, 열두 띠 가운데 한 띠의 흐름이 유독 좋습니다."},
            {"type": "keypoint", "label": f"{scope} 운 좋은 띠 · 3위부터", "points": [f"3위 <b>{a3}띠</b>", f"2위 <b>{a2}띠</b>"],
             "brand": brand, "narration": f"3위는 {a3}띠, 2위는 {a2}띠입니다."},
            {"type": "stat", "label": f"행운 지수 1위 · {a1}띠", "prefix": "", "suffix": "점", "from": 0, "to": s1, "bar": True,
             "sub": " · ".join(map(str, ys)) + f"년생 <b>{a1}띠</b>", "brand": brand,
             "narration": f"1위는 {a1}띠, {why1}이라 지수가 {s1}점입니다."},
            {"type": "statement", "text": "내 띠는 몇 위였나요?", "highlight": "몇 위", "brand": brand,
             "narration": "내 띠는 몇 위였는지 확인해 보세요. 재미로 보는 운세였습니다."},
        ],
        "sources": ["전통 띠 운세(명리) — 일진과 띠의 육합·삼합"], "credit": f"재미로 보는 운세 · {why1}",
        "platforms": {"youtube": {"title": f"{hook} #shorts",
                                  "description": "\n".join([head, "※ 재미로 보는 운세입니다", "",
                                                            "#오늘의운세 #띠별운세 #운세 #shorts"])}},
        "notes": f"MODE={mode} · fortune_card.make 가 쓴 스토리보드(코드 · 1~3위 = {why1.split('과 ')[0]}과 육합·삼합) — 영상은 build_spec",
    }


def main(argv=None) -> int:
    import argparse
    import os
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] not in ("make", "path"):          # 예전 쓰임: fortune_card.py <storyboard.json> 미리보기
        with open(argv[0], encoding="utf-8") as f:
            _sb = json.load(f)
        print(json.dumps({"use_card": use_card(_sb), "meta": meta(_sb), "spec": build_spec(_sb)},
                         ensure_ascii=False, indent=1))
        return 0
    ap = argparse.ArgumentParser(description="06:13 매일 운세 스토리보드(코드)")
    ap.add_argument("cmd", choices=["make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    out = a.out or path_for(d)
    if a.cmd == "path":
        print(out)
        return 0
    sb = make_storyboard(d)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    top, s1 = top_from_storyboard(sb)
    print(f"{out} · {scope_of(sb)} · 1~3위 {top} · {s1}점")
    return 0


if __name__ == "__main__":
    sys.exit(main())
