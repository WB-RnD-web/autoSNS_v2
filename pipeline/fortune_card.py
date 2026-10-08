#!/usr/bin/env python3
"""띠별 운세 '12띠 한 장 표' 쇼츠 (2026-09-29).

왜: 경쟁 채널 실측(2026-09-29) — 5~9초짜리 한 장 표가 구독 1~10천 채널에서도 5만~40만 회가 나왔다
  (월하당 "오늘의 띠별 운세" 6.7만 · 가화만사성 "자식 덕 보는 나이 50~91년생 전부" 16.8만).
  우리 운세는 27~36초 내레이션형이고 편당 ~1,000회에서 멈춘다.
  → 격일로 두 형식을 번갈아 내보내 비교한다(A/B).

배정: ★2026-10-01 부터 매일 표(9/30 표 첫 편 5,700회·좋아요 101 — 기존 형식은 편당 ~800~1,000회에서 멈췄다).
  FORTUNE_CARD=ab 면 예전처럼 CARD_START 부터 짝수 날 = 표, 홀수 날 = 기존 형식. FORTUNE_CARD=0 이면 끈다.
  루틴 판단이 아니라 스토리보드 날짜로 정한다.
데이터: 루틴 스토리보드에는 1~3위만 있다 → 그대로 쓰고, 4~12위·점수·한 줄은 날짜 해시로 정한다
  (같은 날짜면 늘 같은 표). 재미로 보는 운세라는 고지는 설명란에 넣는다.

    python fortune_card.py <storyboard.json>     # 표 데이터 미리보기
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


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        _sb = json.load(f)
    print(json.dumps({"use_card": use_card(_sb), "meta": meta(_sb), "spec": build_spec(_sb)},
                     ensure_ascii=False, indent=1))
