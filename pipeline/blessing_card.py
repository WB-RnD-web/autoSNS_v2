#!/usr/bin/env python3
"""'띠별 아침 덕담표' 쇼츠 — 풀이형 표가 쉬는 날(2026-10-11~10-24 격일) 10:40 자리(pulli_card 가 부른다).

왜(2026-10-10 조사 — 운세·위로 채널 45곳):
  사장님이 '어르신은 운세만이 아니라 마음 편해지는 것도 본다'는 얘기를 들었다. 숫자로 보면:
  - 경전 쇼츠는 안 된다: 반야심경 쇼츠 중앙 365회 · 성경 구절 카드 226회(성경 번역은 대한성서공회 저작권도 있다).
  - 운세 피드 채널의 '좋은 글'만 있는 편은 가라앉는다: 한 채널의 좋은 글 중앙 3,669회 대 같은 채널 운세 쇼츠 90,911회.
  - '운세 틀 + 덕담'은 운세만큼 나간다: 가화만사성 이름 글자 시리즈 33.7만 · '말년에 부부가 함께 웃는 출생년도' 6.6만.
  - 운세 댓글의 44%는 시청자가 자기 띠·출생연도를 적는다 → 띠마다 칸이 있는 표가 맞다.
  → 우리 12띠 표 틀 그대로, 칸마다 따뜻한 한마디 한 줄 + 고운 꽃 배경.

우리 방식(★한마디를 아무렇게나 고르지 않는다 — 정책: 템플릿만 바꾼 대량 생산처럼 보이면 수익화 불가):
  오늘 일진의 띠와 내 띠의 관계(pulli_card.relation — 풀이형 표와 같은 계산)로 한마디의 결을 정한다.
    합(육합·삼합)        → 반가운 소식·손님·안부
    충                  → 서두를 것 없다·쉬는 것도 복
    형·파·해(원진 포함)  → 고운 말 한마디가 평안을 지킨다·몸 살피기
    그 밖(같은 띠 포함)   → 평온한 보통날이 복
  결마다 모아 둔 문구에서 '덕담표 날 순서 → 그날 일진의 띠부터 12지 순서'로 차례로 꺼낸다(해시 없음 · 같은 날짜면 늘 같은 표).
  시험 2주 7편(84칸)에 같은 문구가 두 번 나오지 않는다(테스트가 본다).
  화면엔 명리 용어를 쓰지 않는다(합·충은 설명란에만). 종교 말·돈 액수·건강 장담·겁주는 말·게임 말투 금지(테스트가 막는다).

    python pipeline/blessing_card.py show [--date 2026-10-11]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import birth_basis  # noqa: E402
import pulli_card as P  # noqa: E402
from fortune_card import ANIMALS, WEEKDAY, years_of  # noqa: E402

THEME = "bless:morning"               # 스토리보드 theme — pulli_card.meta 가 이걸 보고 이 파일로 넘긴다
ACCENT = "#E0758A"                    # 고운 분홍(꽃)
BRAND = "왕별이 · 띠별 아침 덕담"
TITLE_PREFIX = "띠별 아침 덕담"        # ★유튜브 제목 앞머리 — 채널 맥박(pulse_formats 'bless')이 이걸로 센다. 바꾸지 않는다
SCREEN_TITLE = "띠별로 드리는 한마디"   # 화면 제목(96px 한 줄) — '한마디'만 분홍
SCREEN_HL = "한마디"
MIN_TOTAL = 10.0                      # 12칸을 다 읽을 시간(나이 표 9초 · 등급표 9.6초와 비슷하게)

# 배경 키비주얼 — 사진이 아니라 생성 그림(저작권 걱정 없음). 그림체는 cover_short CARD_STYLE_PROMPT['flower'].
#   운세 토픽 기본 그림체(치비 띠 동물)를 쓰지 않도록 thumbnail_style 을 'flower' 로 준다.
HOOK = ("soft pastel watercolor painting of Korean flowers, pink cosmos, azaleas and plum blossoms gathered along the "
        "edges of warm cream hanji paper, gentle morning sunlight, calm soothing mood, open empty center, no people")

# 지지 관계 → 결. 원진은 '서운함·말 한마디'라 형·파·해와 같은 결로 본다. 같은 띠는 합도 충도 아닌 보통날로 본다.
CAT_OF = {"육합": "합", "삼합": "합", "충": "충", "형": "형파해", "파": "형파해", "해": "형파해", "원진": "형파해",
          "같은 띠": "평온", "": "평온"}
CATS = ("합", "충", "형파해", "평온")
CAT_LABEL = {"합": "합", "충": "충", "형파해": "형·파·해", "평온": "합도 충도 없는 날"}

# 칸 한 줄 — 어르신이 친구에게 건네는 말투(…요). 한글 9자 이내(96px 표의 칸 한 줄 · 36px 이상으로 들어간다).
# ★금지: 종교 말(부처님·하나님·아멘·기도·축복…) · 돈 액수 · 건강 장담 · 겁주는 말 · 게임 말투 · 명리 용어(테스트가 본다).
# 시험 7편에 결마다 쓰는 칸: 합 21 · 충 7 · 형파해 18 · 평온 38 — 목록은 그보다 넉넉히.
LINES = {
    "합": [  # 반가운 소식·손님·안부
        "반가운 소식이 와요", "기다리던 전화가 와요", "귀한 손님이 찾아와요", "좋은 소식 들려요", "웃을 일이 생겨요",
        "마음 맞는 사람 만나요", "옛 친구 연락 와요", "반가운 얼굴 봐요", "하는 일이 술술 풀려요", "든든한 내 편 생겨요",
        "칭찬 들을 일 있어요", "따뜻한 안부가 와요", "함께라서 든든해요", "멀리서 기쁜 소식 와요", "기쁜 일 함께 나눠요",
        "정이 오가는 하루예요", "복이 문 두드려요", "좋은 인연 이어져요", "웃음이 오래가요", "말이 척척 통해요",
        "고마운 손길 와요", "마음 선물 받아요", "기분 좋은 만남 있어요", "웃음꽃 피는 날이에요", "반가운 초대 받아요",
        "집안에 웃음 가득해요",
    ],
    "충": [  # 서두를 것 없다·쉬는 것도 복
        "서두를 것 없어요", "쉬는 것도 복이에요", "천천히 가도 괜찮아요", "오늘은 쉬어 가세요", "느긋하면 다 풀려요",
        "한숨 돌려도 돼요", "쉬엄쉬엄 가세요", "내일 해도 괜찮아요", "차 한잔하며 쉬세요", "쉬어 가면 더 좋아요",
        "마음 편히 쉬세요", "기다리면 때가 와요",
    ],
    "형파해": [  # 고운 말 한마디가 평안을 지킨다·몸 살피기
        "고운 말이 복이에요", "한마디 아끼면 편해요", "웃으며 넘기세요", "몸 살피며 천천히 가요", "따뜻한 밥 챙겨 드세요",
        "부드러운 말이 이겨요", "먼저 웃으면 편해요", "일찍 쉬면 좋아요", "물 한 잔 챙기세요", "고맙다 말해 보세요",
        "너그러우면 편해요", "몸 따뜻하게 하세요", "양보하면 웃어요", "좋은 말만 나눠요", "들어 주면 풀려요",
        "마음 넉넉히 가져요", "한 박자 쉬어 가요", "웃는 얼굴이 복이에요", "따뜻한 말 한마디", "무리 말고 쉬세요",
        "칭찬 한마디 건네요", "서운함은 흘려보내요", "미소가 정을 지켜요", "오늘 밤 푹 주무세요", "산책하며 숨 고르세요",
        "말은 천천히 해요", "다정한 말이 먼저예요", "한 걸음 물러나 봐요", "오늘은 들어 주세요", "가볍게 웃고 넘겨요",
    ],
    "평온": [  # 평온한 보통날이 복
        "평온한 날이 복이에요", "무탈한 게 제일이에요", "같은 하루가 고마워요", "편안한 하루예요", "잔잔하게 흘러가요",
        "소소한 기쁨 있어요", "차 한잔의 여유", "햇볕 쬐며 걸어요", "별일 없어 다행이에요", "마음이 넉넉해요",
        "고요해서 좋은 날", "밥맛 좋은 하루예요", "꽃 한 송이 보세요", "하늘 한번 보세요", "익숙한 길이 편해요",
        "이웃과 인사 나눠요", "창문 열고 바람 쐬요", "좋아하는 노래 들어요", "평소처럼 좋아요", "하루가 순하게 가요",
        "단잠 자는 날이에요", "오늘도 무사해요", "따뜻한 국 한 그릇", "사진첩 넘겨 보세요", "화분에 물 주세요",
        "고운 하루 보내세요", "웃으며 시작해요", "마음이 가벼워요", "여유롭게 걸어요", "손 편지 써 보세요",
        "좋아하는 반찬 드세요", "오랜 벗이 생각나요", "평범해서 고마워요", "볕 좋은 데 앉아요", "시장 구경 가 보세요",
        "정든 집이 편해요", "숨 한번 크게 쉬어요", "꽃향기 맡는 날", "오늘도 잘하고 있어요", "차분해서 좋아요",
        "소박한 밥상이 좋아요", "안부 한 통 건네요", "걷기 좋은 날이에요", "그대로도 충분해요", "오늘 하루 고마워요",
        "일상이 선물이에요", "편히 웃는 하루예요",
    ],
}


def bless_days() -> list[dt.date]:
    """시험 기간의 덕담표 날(pulli_card.is_bless_day) — 10/11·13·15·17·19·21·23."""
    if P.BLESS_FROM is None:
        return []
    n = (P.BLESS_TO - P.BLESS_FROM).days
    return [P.BLESS_FROM + dt.timedelta(days=k) for k in range(n + 1) if P.is_bless_day(P.BLESS_FROM + dt.timedelta(days=k))]


def relations(d: dt.date) -> list[tuple[int, str, str, str]]:
    """[(띠 번호, 관계, 삼합 이름, 결)] — 쥐부터 돼지까지. 관계는 풀이형 표와 같은 계산(pulli_card.relation)."""
    g = P.ganzhi(d)
    out = []
    for b in range(12):
        rel, grp = P.relation(g["branch"], b)
        out.append((b, rel, grp, CAT_OF[rel]))
    return out


def order_in(d: dt.date, cat: str) -> list[int]:
    """그날 그 결에 든 띠를 문구 목록에서 꺼내는 순서 — 오늘 일진의 띠부터 12지 순서로."""
    day_b = P.ganzhi(d)["branch"]
    return sorted((b for b, _, _, c in relations(d) if c == cat), key=lambda b: (b - day_b) % 12)


def offset(d: dt.date, cat: str) -> int:
    """이 날 이 결의 첫 문구 번호 = 앞선 덕담표 날들이 이 결에서 쓴 칸 수(시험 기간 안 — 겹치지 않는다).
    시험 기간 밖(견본·미리보기)은 날짜로 돌려 고른다(늘 같은 날짜면 같은 표)."""
    days = bless_days()
    if d in days:
        return sum(len(order_in(x, cat)) for x in days if x < d)
    return (d.toordinal() * 7) % len(LINES[cat])


def build_rows(d: dt.date) -> list[dict]:
    """12칸(쥐 → 돼지 순서 · 순위 없음). 칸마다 띠·출생연도·한 줄 + 근거(관계·결)."""
    picked = {}
    for cat in CATS:
        off = offset(d, cat)
        for j, b in enumerate(order_in(d, cat)):
            picked[b] = LINES[cat][(off + j) % len(LINES[cat])]
    return [{"animal": ANIMALS[b], "branch": b, "years": years_of(ANIMALS[b]), "rel": rel, "group": grp, "cat": cat,
             "line": picked[b]} for b, rel, grp, cat in relations(d)]


def day_word(g: dict) -> str:
    return f"{g['animal']}의 날"           # '말의 날' — 일진의 띠


# 설명란 근거 — 관계마다 앞말(왜 그 결인지) + 결마다 같은 끝말(어떤 한마디를 골랐는지). {dw} = '말의 날과'
REL_WHY = {"육합": "{dw} 육합, 손발이 맞는 짝이라", "삼합": "{dw} {grp} 삼합, 한 팀이 되는 날이라",
           "충": "{dw} 마주 보는 충, 서두르지 않아도 되는 날이라", "원진": "{dw} 원진, 말 한마디를 아끼면 좋은 날이라",
           "형": "{dw} 형, 서두르지 않는 게 좋은 날이라", "해": "{dw} 해, 한 박자 쉬어 가면 좋은 날이라",
           "파": "{dw} 파, 약속을 한 번 더 살피면 좋은 날이라", "같은 띠": "오늘과 같은 띠, 기운이 겹치는 보통날이라",
           "": "{dw} 합도 충도 없는 무난한 사이라"}
CAT_WHY = {"합": "반가운 일의 한마디", "충": "쉬어 가는 한마디", "형파해": "고운 말·몸 살피는 한마디",
           "평온": "평온한 하루의 한마디"}


def reason(r: dict, g: dict) -> str:
    """설명란 한 띠의 근거 — 어떤 관계라서 이 결의 한마디를 골랐는지."""
    dw = P.josa(day_word(g), "과", "와")
    return f"{REL_WHY[r['rel']].format(dw=dw, grp=r['group'])} {CAT_WHY[r['cat']]}"


def yrs_text(years: list[int]) -> str:
    return "·".join(f"{y % 100:02d}" for y in years) + "년생"


def title(d: dt.date) -> str:
    # 날짜를 넣어 제목이 겹치지 않게(재탕 제목 금지) · 앞머리는 TITLE_PREFIX 고정(형식 집계)
    return f"{TITLE_PREFIX} | 오늘 아침, 띠별로 드리는 한마디 · {d.month}월 {d.day}일 · 45~96년생 전부"


def description(d: dt.date) -> str:
    """설명란 = 12띠 전부의 근거(메타데이터도 심사가 본다 — 편마다 내용이 다르다)."""
    g = P.ganzhi(d)
    rows = build_rows(d)
    lines = [f"{TITLE_PREFIX} — {d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 아침, 띠별로 한마디씩 드려요. "
             "내 띠 칸을 찾아보세요 🙏",
             f"오늘은 {g['name']}일({g['hanja']}日), {day_word(g)}이에요.", "",
             "한마디는 이렇게 골랐어요: 오늘 일진의 띠와 내 띠가 합(육합·삼합)이면 반가운 일, 충이면 쉬어 가는 말, "
             "형·파·해·원진이면 고운 말과 몸 살피는 말, 그 밖이면 평온한 하루의 말을 골랐어요. "
             "같은 결의 덕담 중에서 날짜 순서대로 꺼내, 이 시리즈에서는 같은 말이 다시 나오지 않아요.", "",
             "띠별로 고른 이유:"]
    lines += [f"· {r['animal']}띠({yrs_text(r['years'])}) — {reason(r, g)} → '{r['line']}'" for r in rows]
    lines += ["", birth_basis.ddi_note(), "",
              "내 띠 한마디는 무엇이었나요? 댓글로 띠를 남겨 주세요 🙏", "",
              "※ 전통 일진 풀이로 골라 본 덕담이에요. 재미로 보세요.", "",
              "#덕담 #띠별덕담 #아침인사 #띠별운세 #오늘의한마디 #shorts"]
    return "\n".join(lines)


def narration(d: dt.date) -> str:
    return (f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 아침, 띠별로 드리는 한마디예요. "
            "오늘과 내 띠가 어울리는지 보고 골랐어요. 내 띠 칸을 찾아보시고, 댓글로 띠를 남겨 주세요.")


def scene(d: dt.date, rows: list[dict] | None = None) -> dict:
    rows = rows or build_rows(d)
    return {"type": "bless", "pill": f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 아침",
            "title": SCREEN_TITLE, "hl": SCREEN_HL,
            "rows": [{k: r[k] for k in ("animal", "years", "line")} for r in rows],
            "basis": birth_basis.SCREEN_DDI, "brand": BRAND, "narration": narration(d)}


def storyboard(d: dt.date, topic: str = P.TOPIC) -> dict:
    """topic 은 부르는 쪽(pulli_card)의 것을 그대로 쓴다 — 렌더·업로드·재생목록 길을 따로 만들지 않는다."""
    g = P.ganzhi(d)
    rows = build_rows(d)
    t = title(d)
    return {
        "date": d.isoformat(), "topic": topic, "theme": THEME, "ganzhi": g["name"], "privacy": "public",
        "accent": ACCENT, "_min_total": MIN_TOTAL,
        "hook_title": TITLE_PREFIX, "headline": t,
        "thumbnail_hook": HOOK + P.HOOK_TAIL, "thumbnail_style": "flower",
        "scenes": [scene(d, rows)],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d)}},
        "notes": f"띠별 아침 덕담표 · 일진 {g['name']} · blessing_card.py 가 만든 스토리보드(풀이형 쉬는 날 · 10/11~10/24 격일)",
    }


def is_bless(sb: dict) -> bool:
    return str(sb.get("theme") or "").startswith("bless:")


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(str(sb.get("date"))[:10])
    return {"title": title(d)[:95], "description": description(d)}


def show(d: dt.date) -> None:
    g = P.ganzhi(d)
    print(f"{d} {g['name']}일({g['hanja']}) · 덕담표 · {title(d)}")
    for r in build_rows(d):
        print(f"  {r['animal']:<4} {r['rel'] or '-':<4} ({CAT_LABEL[r['cat']]}) · {r['line']}")
    print("  🎙️", narration(d))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="띠별 아침 덕담표(보기 — 만들기는 pulli_card make 가 날짜를 보고 한다)")
    ap.add_argument("cmd", choices=["show", "json"])
    ap.add_argument("--date")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else P.kst_today()
    if a.cmd == "show":
        show(d)
    else:
        print(json.dumps(storyboard(d), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
