#!/usr/bin/env python3
"""띠별 '풀이형 표' 쇼츠 — 순위에 근거가 있는 표 (2026-10-06, tables-v2 실험).

왜: 수익화 심사(YPP)는 조회수 최다·최신 영상을 본다. 유튜브 정책(고객센터 1311392)은 '템플릿으로 만든 듯한
  이미지 슬라이드·해설이나 교육적 가치가 거의 없는 것·서로 바꿔 끼워도 될 만큼 비슷한 영상'을 수익 창출에서 뺀다.
  기존 표(theme_card·name_card·fortune_card 4~12위)는 순위가 날짜 해시, 한 줄이 짧은 목록에서 고른 문구라
  이 문구에 가깝다. → 표 모양은 그대로 두고, ★순위를 전통 일진(日辰) 풀이로 정하고 칸마다 이유를 적는다.
  날마다 일진이 바뀌니 순위·이유·풀이가 날마다 다르다(같은 날짜면 늘 같은 표).

근거(전통 명리의 일진 풀이 — 재미로 보는 운세라는 고지는 그대로):
  - 오늘의 일진 = 60갑자. 일진 번호 = (율리우스일 − 11) mod 60 — 1949-10-01 갑자·2000-01-01 무오로 검증.
  - 띠(지지)와 오늘 일진의 지지 관계: 육합·삼합(좋은 짝) · 같은 띠 · 충·원진·형·해·파(조심).
  - 띠 오행과 오늘 천간 오행의 관계(십신): 인성(나를 돕는 기운)·비겁(같은 기운)·식상(내가 내보내는 기운)·
    재성(내가 다스리는 기운 = 재물)·관성(나를 다잡는 기운 = 일). 테마마다 맞는 십신에 가산점.
  점수 = 지지 관계 점수 × 테마 가중치 + 테마 십신 가산 + 십신 기본점. 동점은 관계 세기 → 일진 띠부터의 순서.

    python pipeline/pulli_card.py show [--date 2026-10-07]     # 표·풀이 미리보기
    python pipeline/pulli_card.py make [--date …] --out <path> # 스토리보드 JSON
    python pipeline/pulli_card.py path [--date …]              # 오늘 파일 경로(output/news/…)

★2026-10-11~10-24 이틀에 한 번(짝수 번째 날)은 같은 10:40 자리에 '띠별 아침 덕담표'(blessing_card)가 나간다.
  루틴 명령은 그대로(path·make) — 날짜를 보고 이 파일이 blessing_card 로 넘긴다(theme_card → age_card 와 같은 방식).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import birth_basis  # noqa: E402
from fortune_card import ANIMALS, WEEKDAY, years_of  # noqa: E402

TOPIC = "fortune_pulli"
EPOCH = dt.date(2026, 10, 7)          # 첫 편 — 테마 순환의 0번
KST = dt.timezone(dt.timedelta(hours=9))
ACCENT = "#C9A227"
BRAND = "왕별이 · 오늘의 일진 풀이"
# ★덕담표 2주 시험(2026-10-10 사용자 승인) — BLESS_FROM 부터 BLESS_TO 까지 짝수 번째 날(10/11·13·15·17·19·21·23, 7편)은
#   풀이형 대신 '띠별 아침 덕담표'(blessing_card)가 같은 10:40 자리·같은 토픽으로 나간다. 하루 편수는 그대로.
#   왜: 45개 채널 조사 — 경전·좋은 글만 있는 쇼츠는 가라앉고(반야심경 중앙 365회 · 성경 구절 226회 · 운세 채널의 좋은 글
#   3,669 대 운세 90,911), '운세 틀 + 덕담'은 운세만큼 나간다(가화만사성 이름 글자 33.7만 · 말년 부부 출생년도 6.6만).
#   판정 10/25(pulse_experiments 'blessing'). 끄기 = BLESS_FROM 을 None 으로(그날부터 매일 풀이형).
BLESS_FROM: dt.date | None = dt.date(2026, 10, 11)
BLESS_TO = dt.date(2026, 10, 24)

STEMS = "갑을병정무기경신임계"
STEMS_HJ = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "자축인묘진사오미신유술해"
BRANCHES_HJ = "子丑寅卯辰巳午未申酉戌亥"
STEM_EL = "목목화화토토금금수수"                    # 천간 오행
BRANCH_EL = "수토목목토화화토금금토수"              # 지지 오행(띠의 오행)
EL_WORD = {"목": "나무", "화": "불", "토": "흙", "금": "쇠", "수": "물"}
GEN = {"목": "화", "화": "토", "토": "금", "금": "수", "수": "목"}     # 생: 목→화→토→금→수→목
CTL = {"목": "토", "토": "수", "수": "화", "화": "금", "금": "목"}     # 극: 목→토→수→화→금→목

# 지지 관계(번호 = BRANCHES 인덱스, 0 = 자/쥐)
YUKHAP = [(0, 1), (2, 11), (3, 10), (4, 9), (5, 8), (6, 7)]
SAMHAP = [((8, 0, 4), "신자진"), ((11, 3, 7), "해묘미"), ((2, 6, 10), "인오술"), ((5, 9, 1), "사유축")]
HYEONG = [{2, 5, 8}, {1, 10, 7}, {0, 3}]                 # 인사신·축술미·자묘 (같은 지지 자형은 '같은 띠'로 본다)
HAE = [(0, 7), (1, 6), (2, 5), (3, 4), (8, 11), (9, 10)]
WONJIN = [(0, 7), (1, 6), (2, 9), (3, 8), (4, 11), (5, 10)]
PA = [(0, 9), (1, 4), (2, 11), (3, 6), (5, 8), (7, 10)]
# 관계 → (점수, 세기 순서 — 작을수록 먼저 보여 준다)
REL = {"육합": (3.0, 0), "삼합": (2.0, 1), "같은 띠": (1.0, 2), "충": (-3.0, 3), "원진": (-2.0, 4),
       "형": (-2.0, 5), "해": (-1.0, 6), "파": (-1.0, 7), "": (0.0, 9)}
# 십신 기본점 — 나를 돕는 기운이 가장 편하고, 나를 다잡는 기운이 가장 빡빡하다
CAT_BASE = {"인성": 0.5, "비겁": 0.3, "식상": 0.2, "재성": 0.2, "관성": -0.3}

# 테마 — card = 화면 제목(9자 이내) · yt = 유튜브 제목 앞부분 · cat = 가산점(bonus)을 받는 십신 · w = 지지 관계 가중치
#   돈·일·자식은 십신이 주인공(bonus 3, 관계 0.8) · 귀인·몸은 반반 · 집안은 관계가 주인공(관계 1.6, bonus 1)
# hook = 배경 키비주얼(사람·글자 없음)
THEMES = [
    {"id": "money", "card": "돈 들어오는 띠", "yt": "오늘 돈 들어오는 띠 순위", "cat": "재성", "w": 0.8, "bonus": 3.0,
     "why": "재물 기운 = 내 띠가 다스리는 오행(재성)",
     "hook": "warm golden morning light on a traditional Korean wooden table with a silk coin pouch and "
             "persimmons, soft bokeh, cozy and lucky mood, no people, no text"},
    {"id": "helper", "card": "귀인 만나는 띠", "yt": "오늘 귀인 만나는 띠 순위", "cat": "인성", "w": 1.3, "bonus": 2.0,
     "why": "귀인 = 일진과 합이 되는 띠 + 나를 돕는 오행(인성)",
     "hook": "a Korean hanok courtyard in warm autumn afternoon light, a wooden gate slightly open, fallen ginkgo "
             "leaves on stone steps, welcoming calm mood, no people"},
    {"id": "work", "card": "일 잘 풀리는 띠", "yt": "오늘 일 잘 풀리는 띠 순위", "cat": "관성", "w": 0.8, "bonus": 3.0,
     "why": "일 = 나를 다잡는 오행(관성)이 들어오는 날",
     "hook": "neat Korean study desk with a brush, ink stone and an open notebook in soft morning light, "
             "calm focused mood, no people, no text"},
    {"id": "children", "card": "자식 덕 보는 띠", "yt": "오늘 자식 덕 보는 띠 순위", "cat": "식상", "w": 0.8, "bonus": 3.0,
     "why": "자식·손주 = 내 띠가 낳는 오행(식상)",
     "hook": "cozy Korean living room at golden hour, framed family photos on a wooden shelf, warm tea on a "
             "low table, soft bokeh, no faces, no text"},
    {"id": "body", "card": "몸이 가벼운 띠", "yt": "오늘 몸이 가벼운 띠 순위", "cat": "비겁", "w": 1.2, "bonus": 2.0,
     "why": "힘 = 내 띠와 같은 오행(비겁) · 충이 없는 날",
     "hook": "a quiet Korean mountain walking trail in early autumn morning, soft sunlight through trees, "
             "fresh and light mood, no people, no text"},
    {"id": "home", "card": "집안이 편한 띠", "yt": "오늘 집안이 편한 띠 순위", "cat": "인성", "w": 1.6, "bonus": 1.0,
     "why": "집안 = 일진과 합·충(관계)을 가장 크게 본다",
     "hook": "warm Korean home kitchen in the evening with a pot of stew and rice bowls on the table, soft "
             "lamp light, peaceful family mood, no people, no text"},
]

# 칸 한 줄(9자 이내) — 관계가 있으면 관계, 없으면 십신
LINE_REL = {"육합": "{d}날과 육합", "삼합": "{g} 삼합", "같은 띠": "같은 띠의 날", "충": "{d}날과 충",
            "원진": "원진·말 아끼기", "형": "형·천천히", "해": "해·한 박자 쉬기", "파": "파·다시 확인"}
LINE_CAT = {"인성": "도움 받는 날", "비겁": "기운이 같은 날", "식상": "베푸는 날", "재성": "재물 기운 날",
            "관성": "맡은 일 꼼꼼히"}
# 풀이(화면·내레이션) — {d} = 일진 띠(조사 붙음)
SAY_REL = {"육합": "{dw} 육합, 손발이 맞는 짝이에요", "삼합": "{g} 삼합, 한 팀이 되는 날이에요",
           "같은 띠": "오늘과 같은 띠, 기운이 겹치는 날이에요", "충": "{dw} 정면으로 부딪히는 충, 큰 결정은 내일로 미루세요",
           "원진": "{dw} 원진, 말 한마디를 아끼세요", "형": "{dw} 형, 서두르지 않는 게 좋아요",
           "해": "{dw} 해, 한 박자 쉬어 가세요", "파": "{dw} 파, 약속은 다시 확인하세요"}
CAT_WORD = {"인성": "돕는 기운", "비겁": "같은 기운", "식상": "자식·베풂 기운", "재성": "재물 기운", "관성": "일 기운"}
SAY_CAT = {"인성": "나를 돕는 기운이 들어오는 날이에요", "비겁": "같은 기운이라 힘이 나는 날이에요",
           "식상": "내 기운이 밖으로 나가요, 베풀수록 좋은 날이에요", "재성": "내 띠가 다스리는 기운, 재물 기운이에요",
           "관성": "나를 다잡는 기운, 맡은 일은 꼼꼼히 챙기세요"}


# ── 일진 ────────────────────────────────────────────────
def ganzhi_index(d: dt.date) -> int:
    """60갑자 번호(0 = 갑자). 율리우스일 − 11 의 60 나머지."""
    return (d.toordinal() + 1721425 - 11) % 60


def ganzhi(d: dt.date) -> dict:
    i = ganzhi_index(d)
    s, b = i % 10, i % 12
    return {"index": i, "stem": s, "branch": b, "name": STEMS[s] + BRANCHES[b], "hanja": STEMS_HJ[s] + BRANCHES_HJ[b],
            "el": STEM_EL[s], "animal": ANIMALS[b]}


def josa(word: str, a: str, b: str) -> str:
    """받침 있으면 a, 없으면 b — '과/와'."""
    c = word[-1]
    return word + (a if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else b)


def relation(day_b: int, b: int) -> tuple[str, str]:
    """(관계 이름, 삼합 이름). 여러 관계가 겹치면 세기 순서가 앞선 하나(예: 인해 = 육합·파 → 육합)."""
    found = []
    pair = {day_b, b}
    if b == day_b:
        found.append(("같은 띠", ""))
    if any(pair == set(p) for p in YUKHAP):
        found.append(("육합", ""))
    for grp, nm in SAMHAP:
        if day_b in grp and b in grp and b != day_b:
            found.append(("삼합", nm))
    if (b - day_b) % 12 == 6:
        found.append(("충", ""))
    if any(pair == set(p) for p in WONJIN):
        found.append(("원진", ""))
    if b != day_b and any(pair <= g for g in HYEONG):
        found.append(("형", ""))
    if any(pair == set(p) for p in HAE):
        found.append(("해", ""))
    if any(pair == set(p) for p in PA):
        found.append(("파", ""))
    if not found:
        return "", ""
    return min(found, key=lambda x: REL[x[0]][1])


def sipsin(day_el: str, b: int) -> str:
    """띠(지지) 오행 = 나, 오늘 천간 오행 = 들어오는 기운."""
    me = BRANCH_EL[b]
    if day_el == me:
        return "비겁"
    if GEN[day_el] == me:
        return "인성"
    if GEN[me] == day_el:
        return "식상"
    if CTL[me] == day_el:
        return "재성"
    return "관성"


def is_bless_day(d: dt.date) -> bool:
    """덕담표 날 — BLESS_FROM ≤ d ≤ BLESS_TO 이고 BLESS_FROM 부터 짝수 번째 날. 그 밖은 늘 풀이형."""
    return BLESS_FROM is not None and BLESS_FROM <= d <= BLESS_TO and (d - BLESS_FROM).days % 2 == 0


def theme_for(d: dt.date) -> dict:
    """테마 = 날짜 순환. ★덕담표 기간 안(BLESS_FROM~BLESS_TO)만 '풀이형이 나간 날 수'로 돈다 —
    격일이면 날짜 순환(6개)이 짝수 칸만 밟아 집안·귀인·자식 셋만 나온다(tables-v2 판정 10/22 이 기운다).
    기간 첫 풀이형 날이 기간 직전까지의 순환을 이어받는다(10/10 자식 → 10/12 몸 → 10/14 집안 → 10/16 돈 …).
    기간 밖은 예전 그대로(날짜)."""
    if BLESS_FROM is not None and BLESS_FROM <= d <= BLESS_TO:
        k = (BLESS_FROM - EPOCH).days + sum(not is_bless_day(BLESS_FROM + dt.timedelta(days=j))
                                            for j in range((d - BLESS_FROM).days))
        return THEMES[k % len(THEMES)]
    return THEMES[(d - EPOCH).days % len(THEMES)]


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def build_rows(d: dt.date, th: dict | None = None) -> list[dict]:
    th = th or theme_for(d)
    g = ganzhi(d)
    rows = []
    for b, a in enumerate(ANIMALS):
        rel, grp = relation(g["branch"], b)
        cat = sipsin(g["el"], b)
        pts = REL[rel][0] * th["w"] + (th["bonus"] if cat == th["cat"] else 0.0) + CAT_BASE[cat]
        rows.append({"animal": a, "branch": b, "rel": rel, "group": grp, "cat": cat, "points": round(pts, 2)})
    rows.sort(key=lambda r: (-r["points"], REL[r["rel"]][1], (r["branch"] - g["branch"]) % 12))
    prev = None
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["years"] = years_of(r["animal"])
        sc = max(58, min(98, round(80 + r["points"] * 4)))
        if prev is not None and sc >= prev:
            sc = prev - 1
        r["score"] = prev = max(sc, 50)
        if r["rel"]:
            r["line"] = LINE_REL[r["rel"]].format(d=g["animal"], g=r["group"])
        else:
            r["line"] = LINE_CAT[r["cat"]]
    return rows


def reason(r: dict, g: dict, th: dict | None = None) -> str:
    """한 띠의 이유. 테마 십신이 겹치면 '…에 재물 기운까지' 를 붙인다."""
    dw = josa(g["animal"], "과", "와")
    if not r["rel"]:
        return SAY_CAT[r["cat"]]
    base = SAY_REL[r["rel"]].format(dw=dw, g=r["group"])
    if th and r["cat"] == th["cat"] and REL[r["rel"]][0] > 0:
        base = base.split(",")[0] + f"에 {CAT_WORD[r['cat']]}까지 겹쳤어요"
    return base


def cat_note(rows: list[dict], g: dict, th: dict) -> tuple[str, str]:
    """테마 십신(예: 재물 기운)이 닿는 띠들과 그 순위 — (화면 한 줄, 내레이션 한 문장).
    합·충 때문에 밀린 띠는 이유를 붙인다: '원숭이띠 11위(충)'."""
    cs = sorted((r for r in rows if r["cat"] == th["cat"]), key=lambda r: r["rank"])
    word = CAT_WORD[th["cat"]]
    if not cs:
        return (f"<b>{word}</b> · 오늘은 직접 닿는 띠가 없어 합·충으로 갈렸어요",
                f"{word}이 직접 닿는 띠는 없어서, 오늘은 합과 충으로 순위가 갈렸어요")
    shown = " · ".join(f"{r['animal']}띠 {r['rank']}위" + (f"({r['rel']})" if REL[r["rel"]][0] < 0 else "") for r in cs)
    names = "·".join(r["animal"] for r in cs)
    say = f"{josa(word, '은', '는')} {names}띠에 들어와요"
    neg = [r for r in cs if REL[r["rel"]][0] < 0]
    if neg:
        r = max(neg, key=lambda x: x["rank"])
        say = (f"{josa(word, '은', '는')} {names}띠에 들어오는데, {r['animal']}띠는 "
               f"{josa(g['animal'], '과', '와')} {r['rel']}이라 {r['rank']}위예요")
    return f"<b>{word}</b> · {shown}", say


def short(r: dict, g: dict) -> str:
    """내레이션용 짧은 이유: '호랑이와 육합' · '재물 기운'."""
    return f"{josa(g['animal'], '과', '와')} {r['rel']}" if r["rel"] else CAT_WORD[r["cat"]]


def explain(d: dt.date) -> dict:
    """풀이 장면(화면 4줄 · 내레이션) — 1위·2~3위·꼴찌의 이유."""
    th, g = theme_for(d), ganzhi(d)
    rows = build_rows(d, th)
    a, z = rows[0], rows[-1]
    note, note_say = cat_note(rows, g, th)
    items = [f"오늘은 <b>{g['name']}일</b>({g['hanja']}日) — {EL_WORD[g['el']]} 기운의 {g['animal']}날",
             f"<b>1위 {a['animal']}띠</b> · {reason(a, g, th)}",
             note,
             f"<b>12위 {z['animal']}띠</b> · {reason(z, g, th)}"]
    # ★짧게(12초 안팎) — 12띠 이유를 다 읽으면 40초가 넘는다. 전부는 화면·설명란에 있다.
    zs = short(z, g)
    say = (f"왜 이런 순위일까요? 오늘은 {g['name']}일, {g['animal']}날이에요. "
           f"1위 {a['animal']}띠는 {short(a, g)}, 12위 {z['animal']}띠는 {josa(zs, '이에요', '예요')}. "
           f"내 띠 풀이는 설명란에 있어요.")
    return {"items": items, "narration": say, "why": th["why"]}


def title(d: dt.date, th: dict | None = None) -> str:
    th = th or theme_for(d)
    return f"{th['yt']} 1위~12위 | {d.month}월 {d.day}일 {ganzhi(d)['name']}일 풀이 · 45~96년생 전부"


def description(d: dt.date) -> str:
    """설명란 = 12띠 전부의 이유(메타데이터도 심사가 본다 — 편마다 내용이 다르다)."""
    th, g = theme_for(d), ganzhi(d)
    rows = build_rows(d, th)
    lines = [f"{th['yt']} — {d.month}월 {d.day}일은 {g['name']}일({g['hanja']}日), "
             f"{EL_WORD[g['el']]} 기운의 {g['animal']}날이에요.", "",
             birth_basis.ddi_note(), "",
             "띠별 풀이(오늘 일진과의 관계):"]
    lines += [f"{r['rank']}위 {r['animal']}띠({r['score']}점) — {reason(r, g, th)}." for r in rows]
    lines += ["", f"순위는 이렇게 정했어요: 오늘 일진의 띠와 내 띠가 합(육합·삼합)인지 충·원진·형·해·파인지, "
                  f"그리고 오늘 기운과 내 띠 오행의 관계를 봤어요. {th['why']}.",
              "내 띠는 몇 위인가요? 댓글로 남겨 주세요 🙏", "",
              "※ 전통 명리의 일진 풀이를 재미로 정리한 운세입니다.", "",
              f"#운세 #띠별운세 #오늘의일진 #{g['name']}일 #{th['card'].replace(' ', '')} #shorts"]
    return "\n".join(lines)


# 배경 그림에 글자·간판이 끼면(2026-10-06 견본: 찻잔 그림에 '奇茶' 간판) 표가 지저분해진다 — 모든 hook 뒤에 붙인다.
#   그림체(치비 띠 동물 마스코트)는 cover_short 가 fortune 토픽에 고정으로 붙인다 — 기존 표와 같은 결.
HOOK_TAIL = ", no text, no letters, no signage, no logos"


def storyboard(d: dt.date) -> dict:
    """그날 10:40 스토리보드 — 덕담표 날이면 blessing_card, 아니면 풀이형 표."""
    if is_bless_day(d):
        import blessing_card  # 늦게 부른다 — blessing_card 가 이 파일의 일진·지지 관계를 쓴다(순환 import 방지)
        return blessing_card.storyboard(d, TOPIC)
    return pulli_storyboard(d)


def pulli_storyboard(d: dt.date) -> dict:
    """풀이형 표(tables-v2) — 덕담표 날에도 날짜만 주면 만든다(테스트·견본용)."""
    th, g = theme_for(d), ganzhi(d)
    rows = build_rows(d, th)
    ex = explain(d)
    pill = f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · {g['name']}일"
    say1 = (f"{d.month}월 {d.day}일 {g['name']}일, {th['card']} 순위입니다. "
            f"1위 {rows[0]['animal']}띠, 2위 {rows[1]['animal']}띠, 3위 {rows[2]['animal']}띠.")
    t = title(d, th)
    card_rows = [{k: r[k] for k in ("rank", "animal", "years", "score", "line")} for r in rows]
    return {
        "date": d.isoformat(), "topic": TOPIC, "theme": th["id"], "ganzhi": g["name"], "privacy": "public",
        "accent": ACCENT, "_min_total": 14.0,
        "hook_title": th["yt"], "headline": t, "thumbnail_hook": th["hook"] + HOOK_TAIL,
        "scenes": [
            {"type": "card", "pill": pill, "title": th["card"], "rows": card_rows, "basis": birth_basis.SCREEN_DDI,
             "brand": BRAND, "narration": say1},
            {"type": "news", "layout": "bullets", "pill": f"{g['name']}일 풀이", "title": ["왜 이 순위일까?"],
             "items": ex["items"], "verdict": ex["why"], "foot": "전통 일진 풀이 · 재미로 보는 운세예요",
             "brand": BRAND, "narration": ex["narration"]},
        ],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d)}},
        "notes": f"풀이형 표(tables-v2) · theme={th['id']} · 일진 {g['name']} · pulli_card.py 가 만든 스토리보드",
    }


def is_pulli(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    import blessing_card
    if blessing_card.is_bless(sb):
        return blessing_card.meta(sb)
    d = dt.date.fromisoformat(sb["date"])
    return {"title": title(d)[:95], "description": description(d)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="풀이형 표(덕담표 날엔 덕담표)")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(path_for(d))
        return 0
    sb = storyboard(d)
    if a.cmd == "show" and is_bless_day(d):
        import blessing_card
        blessing_card.show(d)
        return 0
    if a.cmd == "show":
        g = ganzhi(d)
        print(f"{d} {g['name']}일({g['hanja']}) · 테마 {sb['theme']} · {sb['platforms']['youtube']['title']}")
        for r in build_rows(d):
            print(f"  {r['rank']:>2}위 {r['animal']:<4} {r['score']}점 · {r['line']:<10} ({r['rel'] or '-'} / {r['cat']} / {r['points']})")
        for x in sb["scenes"][1]["items"]:
            print("  ·", x)
        print("  🎙️", sb["scenes"][0]["narration"])
        print("  🎙️", sb["scenes"][1]["narration"])
        return 0
    out = a.out or path_for(d)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
