#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""왕별이 라디오 · 밤 편 '잠들기 전 복 받는 시간' — 사실(코드) · 대본 검사 · 구성 · 업로드 글 (2026-11-28).

왜(2026-11-28 사용자): "운전하면서·조깅하면서·자기 전에·집에서 라디오 듣는 것처럼 자연스럽게 보는 채널".
  견본(21분) 뒤 사용자: "F2로 하고 빗소리 30분으로 늘려서" → 말 15~19분 + 빗소리 30분 ≈ 45~50분.

나눠 맡는다:
  · 코드가 정한다 — 내일 띠 순위·생년·한 줄(fortune_card 와 같은 계산 = 다음 날 아침 표와 같다) · 행운의 색·좋은 시간
    · 옛날이야기·옛말 고르기(목록 순환) · 고정 진행 말(인사·띠 부르기·생년 호명·댓글 부탁·잘 자요·빗소리 신호).
  · API 가 쓴다(tools/radio_api.py) — 계절 안부 몇 줄 · 띠마다 내일 한마디·작은 실천·덧붙임·끝 인사
    · 옛날이야기 본문·생각해 볼 말 · 옛말 풀이 · 따라 하는 좋은 말 8줄.
  · 검사(check)가 막는다 — 금지어(의료·투자·겁주기·무속·종교·명리 용어·게임 말투) · 숫자·영어·한자 · 순위 말
    · 다른 띠 이름 · 길이 · 반복. 규칙은 코드에만 있다(부탁은 자주 무시된다).

    python pipeline/radio_night.py facts [--date 2026-11-28]       # API 에 줄 사실(사람이 보기)
    python pipeline/radio_night.py check <대본.json> [--date …]      # 검사만
    python pipeline/radio_night.py compose <대본.json> <plan.json>   # 렌더 계획으로
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import birth_basis  # noqa: E402
import fortune_card as FC  # noqa: E402
import weekly_fortune as WF  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
ANIMALS = FC.ANIMALS
SERIES = "잠들기 전 복 받는 시간"
PLAYLIST = os.environ.get("RADIO_PLAYLIST") or SERIES
PLAYLIST_DESC = ("잠들기 전에 라디오처럼 틀어 두세요. 내일 띠별 운세(생년 호명) · 옛날이야기 · 옛말 한 마디 · "
                 "따라 하는 좋은 말 · 빗소리. 매일 저녁 여덟 시에 올라와요.")
MARKER = "왕별이 라디오 · 밤 편"
CATEGORY = "24"
SYNTHETIC = os.environ.get("RADIO_SYNTHETIC", "0") == "1"   # 그림체 배경 — 채널 운세 관례대로 표시 안 함
PUBLISH_HHMM = os.environ.get("RADIO_PUBLISH_HHMM") or "20:00"
RAIN_MIN = float(os.environ.get("RADIO_RAIN_MIN", "30"))

# ══ 1. 말로 읽는 숫자 ═══════════════════════════════════════════════════════════════════
_D = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
MONTH_KO = {1: "일월", 2: "이월", 3: "삼월", 4: "사월", 5: "오월", 6: "유월", 7: "칠월", 8: "팔월", 9: "구월",
            10: "시월", 11: "십일월", 12: "십이월"}
WEEKDAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
DAYS_LEFT_KO = {0: "", 1: "하루", 2: "이틀", 3: "사흘", 4: "나흘", 5: "닷새", 6: "엿새", 7: "이레"}


def num_ko(n: int) -> str:
    """1~99 → 한자어 수(이십구). 0 은 ''."""
    t, o = divmod(int(n), 10)
    return (("" if t == 1 else _D[t]) + "십" if t else "") + _D[o]


def yy(year: int) -> str:
    """1948 → '사십팔' (어르신들이 말하는 대로 · 두 자리)."""
    return num_ko(year % 100) or "영"


def date_ko(d: dt.date) -> str:
    return f"{MONTH_KO[d.month]} {num_ko(d.day)}일"


def years_spoken(animal: str) -> str:
    return ", ".join(yy(y) + "년생" for y in FC.years_of(animal))


def years_screen(animal: str) -> str:
    return " · ".join(f"{y % 100:02d}" for y in FC.years_of(animal)) + "년생"


# ══ 2. 고르기 목록(옛날이야기·옛말) ══════════════════════════════════════════════════════
# 잠자리에 맞게 따뜻하거나 웃긴 전래 이야기만(무서운 장면·희생·학대가 큰 것은 뺐다). 줄거리는 전래 그대로, 문장은 새로 쓴다.
# scene = 그 이야기 배경 그림(사람 없이 — Spark z-image · 실패하면 assets/radio/story.jpg).
STORIES = [
    {"title": "의좋은 형제", "gist": "형제가 서로 걱정해 밤마다 몰래 볏단을 상대 논에 옮기다가, 보름달 아래 논둑에서 마주쳐 끌어안는다.",
     "scene": "harvested rice fields under a bright full moon at night, stacked rice sheaves, a small thatched-roof Korean village in the distance"},
    {"title": "금도끼 은도끼", "gist": "정직한 나무꾼이 연못에 쇠도끼를 빠뜨리자 산신령이 금도끼·은도끼를 내민다. 내 것은 쇠도끼라 말해 셋 다 받는다. 욕심낸 이웃은 쇠도끼마저 잃는다.",
     "scene": "a calm mountain pond surrounded by pine trees in soft morning mist, an old wooden axe resting on a rock"},
    {"title": "혹부리 영감", "gist": "노래 잘하는 혹부리 영감이 빈집에서 노래하다 도깨비들에게 혹을 떼어 주고 보물을 받는다. 흉내 낸 욕심쟁이 영감은 혹을 하나 더 붙인다(웃음으로 끝낸다).",
     "scene": "an old empty thatched hut deep in a moonlit mountain forest, small warm floating lights among the trees"},
    {"title": "흥부와 놀부", "gist": "착한 흥부가 다친 제비 다리를 고쳐 주고, 이듬해 제비가 물어 온 박씨에서 보물이 나온다. 놀부는 혼이 나고 뉘우쳐 형제가 다시 사이좋게 산다.",
     "scene": "large ripe gourds on a thatched roof under an autumn moon, swallows resting on the eaves"},
    {"title": "은혜 갚은 까치", "gist": "길 가던 선비가 까치 새끼를 구해 준다. 그날 밤 선비가 위험에 처하자 까치들이 산속 절의 종을 울려 선비를 살린다(무섭지 않게, 고마움에 무게).",
     "scene": "an old Korean mountain temple bell pavilion under a full moon, pine trees, magpies on a branch"},
    {"title": "우렁각시", "gist": "가난한 총각이 논에서 우렁이를 주워 물독에 넣는다. 날마다 누군가 밥상을 차려 두는데, 알고 보니 우렁이 속에서 나온 각시였다. 둘은 오래오래 행복하게 산다.",
     "scene": "a cozy thatched cottage kitchen at night with a steaming iron rice pot and a big clay water jar, warm lamplight"},
    {"title": "젊어지는 샘물", "gist": "나무하던 착한 할아버지가 산속 샘물을 마시고 젊어지고, 할머니도 마셔 젊어진다. 욕심쟁이 영감은 너무 많이 마셔 아기가 되고, 착한 부부가 아기를 키운다.",
     "scene": "a clear spring in a deep mountain forest with morning mist and soft sunlight, mossy rocks"},
    {"title": "방귀쟁이 며느리", "gist": "방귀를 참다 얼굴이 노래진 며느리가 시댁 허락에 방귀를 뀌자 집이 흔들린다. 친정 가는 길에 그 방귀로 배나무 배를 떨어뜨려 장사꾼들을 돕고, 복덩이 며느리가 된다.",
     "scene": "a big pear tree full of ripe pears beside a quiet country road, rolling hills, warm late afternoon light"},
    {"title": "도깨비 방망이", "gist": "효심 깊은 나무꾼이 부모님 드릴 개암을 줍고 빈집에서 쉬다 도깨비들을 만난다. 개암 깨무는 소리에 도깨비들이 달아나 방망이를 얻는다. 흉내 낸 욕심쟁이는 혼이 난다.",
     "scene": "an old wooden house in an autumn forest at night, hazelnut branches, a soft glowing moon"},
    {"title": "견우와 직녀", "gist": "하늘나라 견우와 직녀가 일을 게을리해 은하수 양쪽으로 헤어진다. 해마다 칠월 칠석이면 까치와 까마귀가 다리를 놓아 둘이 만난다. 그날 내리는 비는 반가움의 눈물이다.",
     "scene": "the milky way over a quiet river at night, a flock of magpies flying across the starry sky, soft glow"},
    {"title": "토끼와 자라", "gist": "용왕님 병에 토끼 간이 약이라 자라가 토끼를 꾀어 바닷속으로 데려간다. 토끼는 간을 바위에 말려 두고 왔다고 꾀를 내어 무사히 돌아온다.",
     "scene": "seaside rocks under a full moon, calm sea with gentle waves, a small sandy shore and pine trees"},
    {"title": "호랑이와 곶감", "gist": "우는 아이 집 앞에 온 호랑이가 '곶감 줄게' 하자 울음을 뚝 그치는 걸 듣고, 곶감이 저보다 무서운 줄 안다. 소도둑이 등에 올라타자 곶감인 줄 알고 줄행랑친다.",
     "scene": "a snowy thatched cottage at night with strings of dried persimmons hanging under the eaves, warm light from the paper window"},
    {"title": "팥죽 할멈과 호랑이", "gist": "팥밭 매던 할머니가 호랑이에게 팥죽 쑤어 먹고 보자고 꾀를 낸다. 할머니 팥죽을 얻어먹은 알밤·자라·쇠똥·멍석·지게가 힘을 모아 할머니를 지켜 준다(우스꽝스럽게).",
     "scene": "a traditional Korean kitchen with a big pot of red bean porridge steaming, winter night, warm firelight"},
    {"title": "소가 된 게으름뱅이", "gist": "일하기 싫은 게으름뱅이가 이상한 탈을 쓰자 소가 되어 고된 일을 한다. 무를 먹으면 사람으로 돌아온다는 말을 듣고 무를 먹어 돌아오고, 부지런한 사람이 된다.",
     "scene": "a peaceful countryside field with a brown ox resting under a willow tree, radish field, soft evening light"},
    {"title": "개와 고양이", "gist": "착한 노부부가 잉어를 살려 주고 받은 구슬을 욕심쟁이가 훔쳐 간다. 기르던 개와 고양이가 강을 건너 구슬을 찾아오고, 집안에 다시 복이 든다.",
     "scene": "a riverside village in winter moonlight, a frozen river, a small thatched house with warm light"},
    {"title": "호랑이 형님", "gist": "산에서 호랑이를 만난 나무꾼이 '형님, 어머니가 늘 찾으셨어요' 하고 꾀를 낸다. 호랑이는 정말 형인 줄 알고 날마다 어머니께 산짐승을 갖다 드리는 효자가 된다.",
     "scene": "a mountain pass with tall pine trees under a big moon, an old thatched cottage at the foot of the mountain"},
    {"title": "반쪽이", "gist": "몸이 반쪽으로 태어난 반쪽이는 형들에게 놀림을 받지만, 씩씩하고 지혜롭게 큰일을 해내고 모두에게 인정받는다.",
     "scene": "a mountain village path at dawn, terraced fields, soft fog over the hills"},
    {"title": "나무 그늘을 산 총각", "gist": "욕심쟁이 부자가 느티나무 그늘을 혼자 쓰자, 총각이 그늘을 돈 주고 산다. 해가 기울며 그늘이 부잣집 마당·대청까지 들어가고, 부자는 결국 마을에 그늘을 내놓는다.",
     "scene": "a huge old zelkova tree in a Korean village square on a summer evening, long shadows on a tiled-roof house"},
    {"title": "짧아진 바지", "gist": "할아버지 새 바지가 조금 길어서, 할머니·큰며느리·작은며느리가 저마다 몰래 한 뼘씩 줄인다. 다음 날 바지는 깡총해졌지만, 식구들 마음에 온 집이 웃는다.",
     "scene": "a hanok courtyard at night with a laundry line and a folded traditional garment on a wooden floor, warm lamplight"},
    {"title": "요술 맷돌", "gist": "말만 하면 무엇이든 나오는 맷돌을 훔친 도둑이 배 위에서 '소금 나와라' 하다 멈추는 법을 몰라 배째 바다에 가라앉는다. 그래서 바닷물이 짜다고 한다.",
     "scene": "a calm moonlit sea with a small wooden boat in the distance, gentle waves, soft clouds"},
    {"title": "훈장님의 꿀단지", "gist": "훈장님이 꿀단지를 '어른만 먹는 쓴 약'이라 숨겨 두자, 꾀 많은 아이가 그 꿀을 먹고 훈장님 벼루를 일부러 깨뜨린 척 '죄송해서 약을 먹었다'고 한다. 훈장님도 웃고 만다.",
     "scene": "an old Korean village schoolhouse at dusk, low writing desks and an ink stone on the wooden floor, warm light"},
    {"title": "냄새 맡은 값", "gist": "구두쇠 주인이 고기 굽는 냄새를 맡은 값을 내라 하자, 원님 앞에서 가난한 선비가 엽전 꾸러미를 흔들어 '소리로 냄새 값을 치렀다'고 한다. 모두 크게 웃는다.",
     "scene": "an old Korean market street at dusk with paper lanterns, wooden stalls and a small inn"},
    {"title": "오성과 한음", "gist": "어린 오성은 옆집 대감 댁으로 넘어간 감나무 가지의 감을 두고, 그 집 방문 창호지에 주먹을 쑥 넣고 '이 팔은 누구 팔입니까' 묻는다. 대감은 그 슬기에 웃으며 감을 돌려준다.",
     "scene": "a persimmon tree with orange persimmons leaning over an old stone wall between two hanok houses, autumn sky"},
    {"title": "황희 정승과 누렁소", "gist": "젊은 황희가 들에서 농부에게 '두 소 가운데 어느 소가 일을 더 잘하오' 묻자, 농부가 다가와 귓속말로 답한다. 짐승도 제 흉을 들으면 서운해한다는 말에 황희는 말조심을 평생 새긴다.",
     "scene": "two oxen plowing a field at sunset, a straw-roofed farmhouse, gentle hills"},
    {"title": "자린고비", "gist": "아끼고 아끼는 자린고비가 굴비 한 마리를 천장에 매달아 두고 밥 한 숟가락에 한 번씩 쳐다본다. 아들이 두 번 쳐다보자 '짜다' 한다. 그렇게 모은 재산을 흉년에 마을에 나눈다.",
     "scene": "the inside of an old Korean farmhouse with a dried fish hanging from a wooden beam, a small low table, warm lamplight"},
    {"title": "바보 온달과 평강 공주", "gist": "울보 평강 공주는 '바보 온달에게 시집보낸다'는 말을 듣고 자란다. 커서 정말 온달을 찾아가 글과 무예를 가르치고, 온달은 나라의 훌륭한 장수가 된다.",
     "scene": "an ancient mountain fortress wall and a small village below under a soft moon, autumn trees"},
]

# 옛말 — 어르신이 아는 따뜻한 말만(남 흉·돈 자랑·종교 문구 없음). sub = 화면 둘째 줄(한글만 · 한자 금지).
SAYINGS = [
    {"line": "웃는 집에 복이 온다", "sub": "소문만복래"},
    {"line": "가는 말이 고와야\n오는 말이 곱다", "sub": ""},
    {"line": "말 한마디로\n천 냥 빚을 갚는다", "sub": ""},
    {"line": "고생 끝에 낙이 온다", "sub": "고진감래"},
    {"line": "백지장도 맞들면 낫다", "sub": ""},
    {"line": "천 리 길도 한 걸음부터", "sub": ""},
    {"line": "티끌 모아 태산", "sub": ""},
    {"line": "집안이 화목하면\n모든 일이 잘 풀린다", "sub": "가화만사성"},
    {"line": "쥐구멍에도 볕 들 날 있다", "sub": ""},
    {"line": "비 온 뒤에 땅이 굳어진다", "sub": ""},
    {"line": "가는 정이 있어야\n오는 정이 있다", "sub": ""},
    {"line": "낙숫물이 댓돌을 뚫는다", "sub": ""},
    {"line": "공든 탑이 무너지랴", "sub": ""},
    {"line": "먼 친척보다\n가까운 이웃이 낫다", "sub": "이웃사촌"},
    {"line": "첫술에 배부르랴", "sub": ""},
    {"line": "시작이 반이다", "sub": ""},
    {"line": "한 번 웃으면 한 번 젊어진다", "sub": "일소일소"},
    {"line": "세월이 약이다", "sub": ""},
    {"line": "등잔 밑이 어둡다", "sub": ""},
    {"line": "돌다리도 두들겨 보고 건너라", "sub": ""},
    {"line": "아는 길도 물어 가라", "sub": ""},
    {"line": "콩 심은 데 콩 나고\n팥 심은 데 팥 난다", "sub": ""},
    {"line": "길고 짧은 건\n대 봐야 안다", "sub": ""},
    {"line": "열 번 찍어\n안 넘어가는 나무 없다", "sub": ""},
    {"line": "꿩 먹고 알 먹고", "sub": ""},
    {"line": "늦게 배운 재미가\n더 무섭다", "sub": ""},
    {"line": "정성이 지극하면\n돌 위에도 풀이 난다", "sub": ""},
]

COLORS = ["하늘색", "초록색", "노란색", "분홍색", "남색", "보라색", "빨간색", "베이지색", "주황색", "금색", "갈색", "연두색"]
TIMES = [("오전 여덟 시", "오전 8시"), ("오전 아홉 시", "오전 9시"), ("오전 열 시", "오전 10시"), ("오전 열한 시", "오전 11시"),
         ("점심 무렵", "점심 무렵"), ("오후 한 시", "오후 1시"), ("오후 두 시", "오후 2시"), ("오후 세 시", "오후 3시"),
         ("오후 네 시", "오후 4시"), ("오후 다섯 시", "오후 5시"), ("저녁 여섯 시", "저녁 6시"), ("저녁 일곱 시", "저녁 7시")]
SEASON = {1: "한겨울 · 해가 짧고 밤이 길다", 2: "늦겨울 · 입춘 무렵, 봄을 기다린다", 3: "이른 봄 · 꽃샘추위",
          4: "봄 · 꽃 피는 때", 5: "늦봄 · 가정의 달", 6: "초여름", 7: "한여름 · 장마와 더위", 8: "늦여름 · 무더위",
          9: "초가을 · 선선한 바람", 10: "가을 · 단풍", 11: "늦가을 · 밤공기가 차가워진다, 김장철",
          12: "초겨울 · 한 해를 마무리하는 때, 동지"}


# ══ 3. 사실(코드가 정한다) ═══════════════════════════════════════════════════════════════
def tonight(now: dt.datetime | None = None) -> dt.date:
    return (now or dt.datetime.now(KST)).astimezone(KST).date()


BASE = dt.date(2026, 11, 28)          # 견본 날 — 이야기·옛말 순환의 0번


def _ord(d: dt.date) -> int:
    return (d - BASE).days


def pick_story(d: dt.date) -> dict:
    return STORIES[_ord(d) % len(STORIES)]


def pick_saying(d: dt.date) -> dict:
    return SAYINGS[(_ord(d) * 7) % len(SAYINGS)]


def tone_of(rank: int) -> str:
    if rank <= 3:
        return "밝게 — 기운이 아주 좋은 세 띠 가운데 하나. 반가운 소식 위주로"
    if rank <= 8:
        return "차분하게 — 무난하고 소소한 기쁨"
    return "다정하게 — 조심할 점 하나를 부드러운 조언으로(겁주지 않는다)"


def facts(d: dt.date) -> dict:
    """오늘 밤(d) 방송의 사실 — 내일(d+1) 띠 순위는 다음 날 아침 표와 같은 계산."""
    tm = d + dt.timedelta(days=1)
    rows = {r["animal"]: r for r in FC.build_rows(FC.make_storyboard(tm))}
    rnd = random.Random(f"radio|{d.isoformat()}")
    colors, times = COLORS[:], TIMES[:]
    rnd.shuffle(colors)
    rnd.shuffle(times)
    top = [r["animal"] for r in sorted(rows.values(), key=lambda r: r["rank"])[:3]]
    nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    ddi = {}
    for i, a in enumerate(ANIMALS):
        r = rows[a]
        ddi[a] = {"rank": r["rank"], "key": r["line"], "years": r["years"], "top": a in top, "tone": tone_of(r["rank"]),
                  "color": colors[i], "time_say": times[i][0], "time_show": times[i][1]}
    return {"date": d.isoformat(), "for_date": tm.isoformat(), "weekday": WEEKDAY_KO[d.weekday()],
            "for_weekday": WEEKDAY_KO[tm.weekday()], "date_ko": date_ko(d), "for_date_ko": date_ko(tm),
            "days_left": (nxt - d).days - 1, "season": SEASON[d.month], "top": top, "ddi": ddi,
            "story": pick_story(d), "saying": pick_saying(d)}


# ══ 4. API 에 주는 글 ════════════════════════════════════════════════════════════════════
LIMITS = {"hello": (2, 5, 8, 60), "msg": (28, 110), "tip": (28, 110), "more": (18, 90), "bye": (12, 55),
          "story_lines": (16, 36, 6, 75), "story_chars": (650, 1500), "think": (3, 6, 6, 55),
          "card": (2, 16), "saying_lines": (4, 8, 6, 75), "wish": (8, 6, 26), "night": (0, 2, 6, 50),
          "plan_chars": (4600, 7800)}


def brief(d: dt.date) -> str:
    f = facts(d)
    L = LIMITS
    rows = []
    for a in ANIMALS:
        x = f["ddi"][a]
        rows.append(f"- {a}띠({years_screen(a)}) · 내일 순위 {x['rank']}위(말하지 말 것) · 화면 한 줄 '{x['key']}'"
                    f" · 말투: {x['tone']}")
    st, sy = f["story"], f["saying"]
    left = f"이번 달 남은 날: {DAYS_LEFT_KO.get(f['days_left'], str(f['days_left']) + '일')}" if f["days_left"] else "오늘이 이달 마지막 날"
    return f"""# 오늘 밤 방송 사실(코드가 정했다 — 바꾸지 않는다)
- 오늘 밤: {f['date']} {f['weekday']} ({f['date_ko']}) · {left} · 계절: {f['season']}
- 내일: {f['for_date']} {f['for_weekday']} ({f['for_date_ko']})
- 내일 기운이 특히 좋은 세 띠(코드가 소개한다): {', '.join(a + '띠' for a in f['top'])}
- 띠별(쥐→돼지 순서로 방송한다. 생년 호명·행운의 색·좋은 시간은 코드가 붙인다):
{chr(10).join(rows)}
- 오늘 옛날이야기: '{st['title']}' — 줄거리(전래 그대로, 문장은 새로): {st['gist']}
- 오늘 옛말: '{sy['line'].replace(chr(10), ' ')}'{(' · ' + sy['sub']) if sy['sub'] else ''}

# 낼 것: 아래 모양의 JSON 하나(```json 블록). 모든 글은 소리 내어 읽는다 — 한글·문장부호만(숫자·영어·한자 금지).
{{
 "date": "{f['date']}",
 "hello": [ {L['hello'][0]}~{L['hello'][1]}문장 — '안녕하세요' 다음에 이어질 계절·하루 위로. 오늘 날씨를 단정하지 않는다 ],
 "ddi": {{
   "쥐": {{"msg": "내일 한마디 {L['msg'][0]}~{L['msg'][1]}자(화면 한 줄과 같은 뜻으로)", "tip": "작은 실천 {L['tip'][0]}~{L['tip'][1]}자",
          "more": "덧붙이는 다정한 말 {L['more'][0]}~{L['more'][1]}자", "bye": "'쥐띠 분들,'로 시작하는 끝 인사 {L['bye'][0]}~{L['bye'][1]}자"}},
   … 열두 띠 모두(쥐 소 호랑이 토끼 용 뱀 말 양 원숭이 닭 개 돼지) …
 }},
 "story": {{"title": "{st['title']}", "lines": [ {L['story_lines'][0]}~{L['story_lines'][1]}문장, 합쳐서 {L['story_chars'][0]}~{L['story_chars'][1]}자. 이야기 본문만(소개 말은 코드가 한다) ],
           "think": [ {L['think'][0]}~{L['think'][1]}문장 — 이야기에서 우리 집·식구 이야기로 ],
           "card": "화면에 띄울 한 줄(줄바꿈 \\n 으로 두 줄까지, 줄마다 {L['card'][1]}자 이하)"}},
 "saying": {{"lines": [ {L['saying_lines'][0]}~{L['saying_lines'][1]}문장 — 옛말을 한 번 그대로 말하고, 뜻과 내일 해 볼 작은 일로 ] }},
 "wish": [ 딱 {L['wish'][0]}줄 — 따라 하는 좋은 말. 줄마다 {L['wish'][1]}~{L['wish'][2]}자, '~니다.'로 끝 ],
 "night": [ {L['night'][0]}~{L['night'][1]}문장(없어도 된다) — 잠들기 전 포근한 한마디 ]
}}"""


# ══ 5. 검사 ══════════════════════════════════════════════════════════════════════════════
BAN = {k: v for k, v in WF.BAN.items()}
# '큰일'·'무서운'·'꽝' 은 뺐다 — 이야기(호랑이와 곶감)·안부(꽝꽝 언)·'큰일보다 작은 일' 에 자연스럽게 나온다
BAN["겁주는 말"] = BAN["겁주는 말"] + ("흉하", "흉한", "불길", "액운", "횡액", "끔찍", "피할 수 없",
                                     "화를 입", "화를 당", "불행", "최악", "되는 일이 없", "운이 없", "불운")
BAN["게임·젊은 말투"] = ("레벨", "만렙", "버프", "너프", "꿀팁", "개꿀", "레전드", "끝판왕", "치트키", "존버", "떡상", "떡락",
                    "인생템", "핵이득", "ㅋㅋ", "ㅎㅎ", "등급", "티어", "에스급", "에이급")
BAN["지어낸 사연"] = ("질문 주신", "보내 주신", "보내주신", "사연 주신", "사연을 보내", "댓글로 물어", "댓글 주신", "어느 시청자",
                  "한 시청자", "시청자분이")
# '주님'(공주님)·'사주'(사 주다)·'세운'(세운 계획)·'편인'(편인데)·'정인'·'일 등'(집안일 등) 은 낱말 안에 숨어 있어 뺐다
BAN["종교 말"] = ("기도", "하나님", "하느님", "부처님", "예수", "아멘", "할렐루야", "나무아미타불", "관세음보살", "성경",
               "불경", "경전", "찬송", "염불", "교회", "성당", "법당")
BAN["명리 용어"] = ("육합", "삼합", "일진", "천간", "오행", "상생", "상극", "용신", "십신", "대운", "편재", "정재",
                 "식신", "겁재", "비견", "편관", "정관", "역마", "도화", "원진", "사주팔자")
BAN["순위 말"] = ("순위", "등수", "꼴찌", "꼴등", "번째로 좋", "번째로 낮", "가장 낮", "제일 낮", "가장 나쁜",
               "제일 나쁜", "가장 안 좋", "제일 안 좋")
# '삼 위예요'·'일위입니다' — '이 위에 얹어'·'아궁이 위에' 는 걸리지 않게 뒤 말을 좁혔다
RANK_RE = re.compile(r"(?<![가-힣])(?:[일이삼사오육칠팔구]|십[일이]?|열두|열한)\s?위(?:예요|에요|입니다|이에요|를 차지|권|로 올라|에 올라)")
HANJA = re.compile(r"[一-鿿㐀-䶿]")
SPOKEN_OK = WF.SPOKEN_OK
SCREEN_OK = re.compile(r"[가-힣\s.,!?~…'\"“”‘’()\-:·]")
ANIMAL_RE = re.compile(r"(" + "|".join(sorted(ANIMALS + ["범"], key=len, reverse=True)) + r")띠")


def _s(v) -> str:
    return re.sub(r"[ \t]+", " ", v).strip() if isinstance(v, str) else ""


def _lines(v) -> list[str]:
    return [_s(x) for x in v] if isinstance(v, list) else []


# 음식 '죽'(팥죽을 쑤어 — '죽을' 이 겁주는 말에 걸린다)·숨소리 '헉헉' 은 검사 전에 지운다
_FOOD_JUK = re.compile(r"(?:팥|호박|전복|흰|녹두|잣|깨|야채|채소)죽|죽(?=을 (?:쑤|끓|먹|드|한 그릇|퍼))")


def _for_ban(text: str) -> str:
    return _FOOD_JUK.sub(lambda m: m.group(0)[:-1] + "국", text).replace("헉헉", "")


def ban_list_text() -> str:
    """글쓰기 안내에 붙이는 금지어 목록(코드 검사와 같은 것)."""
    rows = [f"- {g}: {', '.join(ws)}" for g, ws in BAN.items()]
    rows.append("- 순위 말: '삼 위예요'·'일위입니다' 처럼 순위를 숫자로 말하기")
    rows.append("- 살·삼재 낱말: 쓰지 않는다(이 방송은 조언 틀이 없다)")
    return "\n".join(rows)


def ban_hits(text: str) -> list[str]:
    import sal_frame
    text = _for_ban(text)
    out = []
    for group, words in BAN.items():
        hit = [w for w in words if w in text]
        if group == "의료 조언" and WF.CANCER_RE.search(text):
            hit.append("암")
        if hit:
            out.append(f"{group}: {', '.join(hit)}")
    if RANK_RE.search(text):
        out.append(f"순위 말: '{RANK_RE.search(text).group(0).strip()}'")
    out += [f"살·삼재: {v}" for v in sal_frame.violations(text)]
    return out


def bad_chars(text: str, ok=SPOKEN_OK) -> list[str]:
    return sorted({c for c in text if c != "\n" and not ok.fullmatch(c)})


def spoken_texts(sc: dict) -> list[tuple[str, str]]:
    """(자리, 글) — 대본에서 소리 내어 읽는 모든 칸."""
    out = [(f"hello[{i}]", x) for i, x in enumerate(_lines(sc.get("hello")))]
    for a in ANIMALS:
        x = (sc.get("ddi") or {}).get(a) or {}
        out += [(f"ddi.{a}.{k}", _s(x.get(k))) for k in ("msg", "tip", "more", "bye")]
    st = sc.get("story") or {}
    out += [(f"story.lines[{i}]", x) for i, x in enumerate(_lines(st.get("lines")))]
    out += [(f"story.think[{i}]", x) for i, x in enumerate(_lines(st.get("think")))]
    out += [(f"saying.lines[{i}]", x) for i, x in enumerate(_lines((sc.get("saying") or {}).get("lines")))]
    out += [(f"wish[{i}]", x) for i, x in enumerate(_lines(sc.get("wish")))]
    out += [(f"night[{i}]", x) for i, x in enumerate(_lines(sc.get("night")))]
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^가-힣]", "", s or "")


def check(sc, d: dt.date | None = None) -> list[str]:
    """대본 검사 — 오류 목록(비면 통과)."""
    if not isinstance(sc, dict):
        return ["대본이 JSON 객체가 아니다"]
    errs: list[str] = []
    L = LIMITS
    if d is not None and _s(sc.get("date")) != d.isoformat():
        errs.append(f"date 는 '{d.isoformat()}' 여야 한다(지금 '{_s(sc.get('date'))}')")
    d = d or (dt.date.fromisoformat(_s(sc.get("date"))) if re.fullmatch(r"\d{4}-\d\d-\d\d", _s(sc.get("date"))) else None)
    f = facts(d) if d else None

    def count(name, xs, lo, hi):
        if not lo <= len(xs) <= hi:
            errs.append(f"{name}: {lo}~{hi}개여야 한다(지금 {len(xs)}개)")

    def length(where, s, lo, hi):
        n = len(s)
        if not lo <= n <= hi:
            errs.append(f"{where}: {lo}~{hi}자여야 한다(지금 {n}자) — '{s[:40]}'")

    hello = _lines(sc.get("hello"))
    count("hello", hello, L["hello"][0], L["hello"][1])
    for i, x in enumerate(hello):
        length(f"hello[{i}]", x, L["hello"][2], L["hello"][3])
    ddi = sc.get("ddi") if isinstance(sc.get("ddi"), dict) else {}
    extra = sorted(set(ddi) - set(ANIMALS))
    if extra:
        errs.append(f"ddi: 모르는 띠 {extra}")
    msgs = {}
    for a in ANIMALS:
        x = ddi.get(a)
        if not isinstance(x, dict):
            errs.append(f"ddi.{a}: 없다")
            continue
        for k in ("msg", "tip", "more", "bye"):
            length(f"ddi.{a}.{k}", _s(x.get(k)), *L[k])
        if not _s(x.get("bye")).startswith(f"{a}띠 분들"):
            errs.append(f"ddi.{a}.bye: '{a}띠 분들,'로 시작해야 한다 — '{_s(x.get('bye'))[:30]}'")
        others = {m.group(1) for k in ("msg", "tip", "more", "bye") for m in ANIMAL_RE.finditer(_s(x.get(k)))} - {a}
        if others:
            errs.append(f"ddi.{a}: 다른 띠 이름이 나온다 {sorted(others)}")
        msgs[a] = _s(x.get("msg"))
    names = list(msgs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sim = WF.similarity(msgs[a], msgs[b])
            if sim > 0.5:
                errs.append(f"ddi.{a}.msg 와 ddi.{b}.msg 가 너무 비슷하다({sim:.2f}) — 띠마다 다르게")
    st = sc.get("story") if isinstance(sc.get("story"), dict) else {}
    if f and _s(st.get("title")) != f["story"]["title"]:
        errs.append(f"story.title 은 '{f['story']['title']}' 여야 한다(지금 '{_s(st.get('title'))}')")
    sl = _lines(st.get("lines"))
    count("story.lines", sl, L["story_lines"][0], L["story_lines"][1])
    for i, x in enumerate(sl):
        length(f"story.lines[{i}]", x, L["story_lines"][2], L["story_lines"][3])
    n = sum(len(x) for x in sl)
    if not L["story_chars"][0] <= n <= L["story_chars"][1]:
        errs.append(f"story.lines: 합쳐서 {L['story_chars'][0]}~{L['story_chars'][1]}자여야 한다(지금 {n}자)")
    th = _lines(st.get("think"))
    count("story.think", th, L["think"][0], L["think"][1])
    for i, x in enumerate(th):
        length(f"story.think[{i}]", x, L["think"][2], L["think"][3])
    card = st.get("card") if isinstance(st.get("card"), str) else ""
    cl = [c.strip() for c in card.split("\n") if c.strip()]
    if not 1 <= len(cl) <= L["card"][0] or any(len(c) > L["card"][1] for c in cl):
        errs.append(f"story.card: 한두 줄, 줄마다 {L['card'][1]}자 이하(지금 {[len(c) for c in cl]})")
    if bad_chars(card, SCREEN_OK):
        errs.append(f"story.card: 화면에 못 쓰는 글자 {bad_chars(card, SCREEN_OK)}")
    sy = _lines((sc.get("saying") or {}).get("lines") if isinstance(sc.get("saying"), dict) else None)
    count("saying.lines", sy, L["saying_lines"][0], L["saying_lines"][1])
    for i, x in enumerate(sy):
        length(f"saying.lines[{i}]", x, L["saying_lines"][2], L["saying_lines"][3])
    if f and _norm(f["saying"]["line"]) not in _norm(" ".join(sy)):
        errs.append(f"saying.lines: 옛말 '{f['saying']['line'].replace(chr(10), ' ')}'을 한 번은 그대로 말해야 한다")
    wish = _lines(sc.get("wish"))
    if len(wish) != L["wish"][0]:
        errs.append(f"wish: 딱 {L['wish'][0]}줄(지금 {len(wish)}줄)")
    for i, x in enumerate(wish):
        length(f"wish[{i}]", x, L["wish"][1], L["wish"][2])
        if not x.endswith("니다."):
            errs.append(f"wish[{i}]: '~니다.'로 끝나야 한다 — '{x}'")
    if len(set(_norm(x) for x in wish)) != len(wish):
        errs.append("wish: 같은 줄이 두 번 나온다")
    night = _lines(sc.get("night"))
    count("night", night, L["night"][0], L["night"][1])
    for i, x in enumerate(night):
        length(f"night[{i}]", x, L["night"][2], L["night"][3])
    for where, text in spoken_texts(sc):
        for h in ban_hits(text):
            errs.append(f"{where}: 금지어 {h} — '{text[:40]}'")
        bc = bad_chars(text)
        if bc:
            errs.append(f"{where}: 소리 내어 읽기 어려운 글자 {bc}(숫자·영어·한자 금지 — 한글로) — '{text[:40]}'")
    for h in ban_hits(card):
        errs.append(f"story.card: 금지어 {h}")
    if not errs and d is not None:
        n = stats(compose(sc, d))["chars"]
        lo, hi = L["plan_chars"]
        if not lo <= n <= hi:
            errs.append(f"전체 글자 {n}자 — {lo}~{hi}자(말 15~20분)여야 한다. 띠·이야기 글을 {'늘려' if n < lo else '줄여'} 달라")
    return errs


# ══ 6. 구성(렌더 계획) ═══════════════════════════════════════════════════════════════════
def _c(text: str, slide: dict, pause: float | None = None) -> dict:
    d = {"text": _s(text), "slide": slide}
    if pause is not None:
        d["pause"] = pause
    return d


def split_sentences(s: str) -> list[str]:
    """두 문장짜리 글 → 문장 하나씩(목소리 조각을 짧게)."""
    out, cur = [], ""
    for ch in _s(s):
        cur += ch
        if ch in ".?!" and cur.strip():
            out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


CALLS = ["{a}띠입니다. {Y} {a}띠 분들.", "다음은 {a}띠예요. {Y} {a}띠 분들.", "{a}띠 차례예요. {Y} {a}띠 분들, 잘 들어 보세요."]


def compose(sc: dict, d: dt.date) -> dict:
    """대본(API) + 사실(코드) → 렌더 계획 {date, parts:[{id,title,bg,chunks:[{text,slide,pause?}]}]}."""
    f = facts(d)
    k = _ord(d)
    open_s = {"kind": "open", "date": f"{d.month}월 {d.day}일 {f['weekday']} 밤"}
    hello = [_c("안녕하세요. 잠들기 전 복 받는 시간입니다.", open_s)]
    hello += [_c(x, open_s) for x in _lines(sc.get("hello"))]
    hello += [_c(x, open_s) for x in (
        "이 시간에는 내일 띠별 운세를 쥐띠부터 돼지띠까지 차례로 들려 드리고요.",
        "옛날이야기 한 토막 들려 드린 다음에, 마음 편해지는 좋은 말을 같이 따라 해 볼 거예요.",
        ("화면은 안 보셔도 괜찮아요. 라디오처럼 틀어 두시고, 눈 감고 들으세요.",
         "설거지하시면서, 누워서 쉬시면서, 그냥 라디오처럼 틀어 두세요.")[k % 2],
        "내 띠 차례가 오면, 제가 생년을 하나하나 불러 드릴게요.",
        "끝 무렵에는 빗소리를 조용히 깔아 드릴게요.",
        "자, 그럼 내일 운세부터 들어 볼까요.")]
    parts = [{"id": "hello", "title": "안부 인사", "bg": "hello", "chunks": hello}]
    tm = dt.date.fromisoformat(f["for_date"])
    top = f["top"]
    intro_s = {"kind": "ddi_intro", "date": f"{tm.month}월 {tm.day}일 {f['for_weekday']}", "top": top}
    parts.append({"id": "ddi_intro", "title": "내일 띠별 운세", "bg": "ddi", "chunks": [
        _c(f"내일은 {f['for_date_ko']}, {f['for_weekday']}이에요.", intro_s),
        _c(f"내일 기운이 특히 좋은 띠는 {top[0]}띠, {top[1]}띠, {top[2]}띠예요.", intro_s),
        _c("이 세 띠는 내일 마음먹은 일을 시작해 보셔도 좋겠어요.", intro_s),
        _c("띠는 입춘을 기준으로 봐요. 양력으로 일월이나 이월 초, 입춘 전에 태어나신 분은 앞 해 띠로 보세요.", intro_s),
        _c("그럼 쥐띠부터 시작할게요.", intro_s)]})
    for i, a in enumerate(ANIMALS):
        x, fx = sc["ddi"][a], f["ddi"][a]
        s = {"kind": "ddi", "animal": a, "years": fx["years"], "key": fx["key"], "color": fx["color"],
             "time": fx["time_show"], "top": fx["top"]}
        if i == 0:
            call = "쥐띠부터 볼게요. {Y} 쥐띠 분들."
        elif i == len(ANIMALS) - 1:
            call = "마지막으로 {a}띠예요. {Y} {a}띠 분들."
        else:
            call = CALLS[(k + i) % len(CALLS)]
        call = call.format(a=a, Y=years_spoken(a)) + (" 반가운 말씀 드릴게요." if fx["top"] else "")
        t = fx["time_say"]
        lucky = f"행운의 색은 {fx['color']}, 좋은 시간은 " + (f"{t}이에요." if t.endswith("무렵") else f"{t}쯤이에요.")
        ys = fx["years"]
        chunks = [_c(call, s)]
        for key in ("msg", "tip", "more"):
            chunks += [_c(y, s) for y in split_sentences(x[key])]
        chunks += [_c(lucky, s), _c(f"{yy(ys[0])}년생부터 {yy(ys[-1])}년생까지, " + _s(x["bye"]), s)]
        parts.append({"id": f"ddi_{a}", "title": f"{a}띠 ({'·'.join(f'{y % 100:02d}' for y in ys)}년생)", "bg": "ddi",
                      "chunks": chunks})
    outro_s = {"kind": "ddi_outro"}
    parts[-1]["chunks"] += [
        _c("열두 띠 운세, 모두 들려 드렸어요. 식구들 띠도 같이 들으셨죠?", outro_s),
        _c("댓글에 내 띠랑 식구들 띠를 적어 두세요. 적어 두기만 해도 마음이 든든해지실 거예요.", outro_s)]
    st = sc["story"]
    title = f["story"]["title"]
    st_s = {"kind": "story", "title": title}
    think_s = {"kind": "story_think", "line": "\n".join(c.strip() for c in st["card"].split("\n") if c.strip())}
    parts.append({"id": "story", "title": f"옛날이야기 · {title}", "bg": "story", "chunks":
                  [_c("이제 옛날이야기 한 토막 들려 드릴게요.", st_s), _c(f"오늘 이야기는 {title} 이야기예요.", st_s)]
                  + [_c(x, st_s) for x in _lines(st["lines"])] + [_c(x, think_s) for x in _lines(st["think"])]})
    sy = f["saying"]
    ow = {"kind": "saying", "line": sy["line"], "sub": sy["sub"]}
    parts.append({"id": "saying", "title": f"옛말 한 마디 · {sy['line'].replace(chr(10), ' ')}", "bg": "story",
                  "chunks": [_c("옛말 한 마디 들려 드릴게요.", ow)] + [_c(x, ow) for x in _lines(sc["saying"]["lines"])]})
    wi = {"kind": "wish_intro"}
    wishes = _lines(sc["wish"])
    wch = [_c("이제 마음 편해지는 좋은 말을 같이 따라 해 볼게요.", wi),
           _c("제가 먼저 한 줄 읽으면, 마음속으로든 작은 목소리로든 천천히 따라 해 보세요.", wi),
           _c("숨을 한번 크게 들이쉬고, 천천히 내쉬고.", wi, pause=3.0),
           _c("시작할게요.", wi)]
    wch += [_c(w, {"kind": "wish", "line": w, "n": i + 1, "of": len(wishes)}, pause=5.5) for i, w in enumerate(wishes)]
    fam = {"kind": "wish_family"}
    wch += [_c("잘하셨어요.", fam),
            _c("이번에는 사랑하는 식구들 얼굴을 한 사람씩 떠올려 보세요.", fam),
            _c("이름을 마음속으로 한 번씩, 천천히 불러 주세요.", fam, pause=10.0),
            _c("그 이름 하나하나에, 오늘 밤 좋은 기운이 포근하게 내려앉기를 바랄게요.", fam),
            _c("내 띠랑 식구들 띠, 그리고 마음에 담은 좋은 말 한 줄을 댓글로 남겨 주세요.", fam),
            _c("적어 두면, 그 말이 내 마음에 한 번 더 새겨져요.", fam)]
    parts.append({"id": "wish", "title": "따라 하는 좋은 말", "bg": "wish", "chunks": wch})
    ns = {"kind": "night"}
    night = [_c("오늘 밤도 잠들기 전 복 받는 시간과 함께해 주셔서 고맙습니다.", ns),
             _c("내일 운세는 재미로 들으시고, 좋은 말만 마음에 담아 두세요.", ns)]
    night += [_c(x, ns) for x in _lines(sc.get("night"))]
    night += [_c("이제 불 끄시고, 이불 포근하게 덮으세요.", ns),
              _c("지금부터는 조용한 빗소리를 깔아 드릴게요. 빗소리 들으면서 편안히 주무세요.", ns),
              _c("내일 밤에도 이 시간에 다시 찾아올게요.", ns),
              _c("안녕히 주무세요.", ns)]
    parts.append({"id": "night", "title": "잘 자요", "bg": "night", "chunks": night})
    return {"date": d.isoformat(), "for_date": f["for_date"], "title": SERIES, "story": title,
            "story_scene": f["story"]["scene"], "saying": sy["line"].replace("\n", " "), "top": top,
            "for_label": f"{tm.month}월 {tm.day}일 {f['for_weekday']}", "parts": parts}


def stats(plan: dict) -> dict:
    texts = [c["text"] for p in plan["parts"] for c in p["chunks"]]
    chars = sum(len(t) for t in texts)
    # 실측(11/28 견본 · F2 · 0.9배): 5,945자 → 말 16.2분(쉼 포함) ≈ 367자/분
    return {"chars": chars, "chunks": len(texts), "parts": len(plan["parts"]), "est_min": round(chars / 367, 1)}


# ══ 7. 업로드 글 ═════════════════════════════════════════════════════════════════════════
MUSIC_CREDIT = ("🎹 피아노: \"Gymnopedie No 1\" Kevin MacLeod (incompetech.com)\n"
                "Licensed under Creative Commons: By Attribution 4.0 License\nhttp://creativecommons.org/licenses/by/4.0/")
CREDIT = "🎙️ 목소리: Supertonic (Supertone · OpenRAIL-M) · 🎨 그림: AI 생성 · 🌧️ 빗소리: 직접 합성"
DISCLAIMER = "※ 재미로 보는 운세예요. 건강·돈 문제는 꼭 전문가와 상의하세요."
HASHTAGS = "#띠별운세 #내일운세 #잠잘때듣는 #수면라디오 #옛날이야기 #빗소리 #왕별이"


def marker(d: dt.date | str) -> str:
    return f"{MARKER} {d if isinstance(d, str) else d.isoformat()}"


def title_for(plan: dict) -> str:
    rain = int(RAIN_MIN)
    t = (f"🌙 잠들기 전 복 받는 시간 | 내일 띠별 운세({plan['for_label']}) · {plan['story']} · "
         f"따라 하는 좋은 말 · 빗소리 {rain}분")
    if len(t) > 100:
        t = f"🌙 잠들기 전 복 받는 시간 | 내일 띠별 운세({plan['for_label']}) · {plan['story']} · 빗소리 {rain}분"
    return t[:100]


def description_for(plan: dict, chapters: str) -> str:
    desc = (f"오늘 하루도 애쓰셨어요. 불 끄고 누워서 라디오처럼 들으세요.\n"
            f"내일({plan['for_label']}) 띠별 운세 — 쥐띠부터 돼지띠까지 생년을 하나하나 불러 드려요(45~96년생).\n"
            f"옛날이야기 '{plan['story']}' · 옛말 한 마디 '{plan['saying']}' · 따라 하는 좋은 말 · 빗소리 {int(RAIN_MIN)}분\n\n"
            f"⏱ 목차\n{chapters}\n\n{birth_basis.ddi_note().replace('이 표는', '이 방송은')}\n\n"
            "💬 댓글에 내 띠와 식구들 띠를 적어 두세요.\n🌙 매일 저녁 8시에 올라와요.\n\n"
            f"{DISCLAIMER}\n{CREDIT}\n{MUSIC_CREDIT}\n\n{HASHTAGS}\n\n{marker(plan['date'])}")
    return desc[:4900]


def tags_for(plan: dict) -> list[str]:
    return ["띠별운세", "내일운세", "잠잘때듣는", "수면라디오", "옛날이야기", plan["story"], "빗소리", "운세", "왕별이",
            "잠들기 전 복 받는 시간"]


def publish_at(d: dt.date, now: dt.datetime | None = None) -> str | None:
    """그날 20:00 KST(UTC RFC3339). 이미 지났거나 10분 안이면 None(바로 공개)."""
    try:
        h, m = (int(x) for x in PUBLISH_HHMM.split(":"))
    except ValueError:
        h, m = 20, 0
    when = dt.datetime.combine(d, dt.time(h, m), tzinfo=KST)
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    if when <= now + dt.timedelta(minutes=10):
        return None
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def already_uploaded(uploads: list[dict], d: dt.date | str) -> str | None:
    mk = marker(d)
    for u in uploads or []:
        if mk in (u.get("description") or ""):
            return u.get("video_id") or "?"
    return None


# ══ 8. 명령 ══════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="왕별이 라디오 밤 편 — 사실·검사·구성")
    ap.add_argument("cmd", choices=["facts", "brief", "check", "compose"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--date", default=None, help="오늘 밤 날짜(기본: 지금 KST)")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else tonight()
    if a.cmd == "facts":
        print(json.dumps(facts(d), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "brief":
        print(brief(d))
        return 0
    with open(a.paths[0], encoding="utf-8") as fh:
        sc = json.load(fh)
    if not a.date and re.fullmatch(r"\d{4}-\d\d-\d\d", _s(sc.get("date"))):
        d = dt.date.fromisoformat(sc["date"])
    errs = check(sc, d)
    if errs:
        print(f"❌ 검사 실패 {len(errs)}건")
        for e in errs:
            print(f"- {e}")
        return 1
    plan = compose(sc, d)
    print(f"✅ 통과 · {json.dumps(stats(plan), ensure_ascii=False)}")
    if a.cmd == "compose":
        with open(a.paths[1], "w", encoding="utf-8") as fh:
            json.dump(plan, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
