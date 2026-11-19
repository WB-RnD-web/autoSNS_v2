#!/usr/bin/env python3
"""'말년 지혜 표' 쇼츠 — 자식·부부·노후 돈·관계 이야기 다섯 줄을 한 장에(2026-11-17~11-30 2주 시험 · 매일 17:40 KST).

왜(2026-11-15 · 사용자 "말년 지혜 표 2주 시험 PR 올려줘 · 운세는 운세대로 하고 추가로 올리는 거야"):
  왕별이 시청자(55세 이상 87.6%)가 보는 '시니어 생활·공감' 쇼츠가 운세보다 크게 터진다.
  트렌드 레이더(data/trend-radar trends.json · 11/14 · 지난 21일, 채널 평소 대비 배수):
  - 오늘의 건강명언(구독 4.52만) 5초 카드 129만(27.8배) · 마음의 건강(1.44만) 부부 글귀 62만(31.8배)
  - 인생꿀팁(1.92만) 양념 보관법 47만(23.3배) · 같은 기간 운세 쪽 최고는 행운 충전소(12.8만) 64만(11.2배)
  - 태그별: 자식·관계 터짐 44%·편당 중앙 2.5만 · 명언·지혜 30%·1.5만 · 노후 돈 19%·1.2만
  - 그 채널들은 17:38~18:02 KST 에 올린다(11/15 공개 페이지 publishDate) → 우리도 17:40.
  반대 근거도 있다(10/10 조사): 운세 피드 채널에서 '좋은 글'만 있는 편은 가라앉았다(같은 채널 운세의 4%).
  그래서 2주 시험이다 — 판정은 채널 맥박(pulse_experiments 'wisdom-trial', 12/2).

우리 방식(★정책: 템플릿만 바꾼 대량 생산처럼 보이면 수익화 불가 — 편마다 내용이 다르다):
  편마다 주제 하나(부부 · 자식 · 손주 · 며느리·사위 · 노후 돈 · 이웃·친구 · 혼자 시간 · 서운할 때 …)에 다섯 줄.
  줄마다 큰 글자 한 줄 + 작은 글자 한 줄(화면) + 왜 그런지 한 문장(설명란). 문구는 아래 EPISODES 에 사람이 쓴 그대로 —
  해시·무작위로 고르지 않는다. 같은 줄은 시리즈에서 두 번 나오지 않는다(테스트가 본다).
  ★금지: 건강 장담·병 이름(의료 정책) · 돈 액수·투자 권유 · 종교 말 · 겁주는 말 · 게임 말투 · 명리 용어(theme_card.BANNED + 아래 NO_WORDS).
  운세 토픽이 아니다(topic 'wisdom') — 아침 운세 표·등급표 A/B·끝인사(outro)가 이 편을 건드리지 않는다.

편성: EPISODES 의 date 그대로(하루 한 편). 그 밖의 날 make 는 아무것도 안 쓴다(종료 코드 0 = 건너뜀).
  ★이어 가려면(판정이 '계속'일 때만) EPISODES 끝에 date 를 단 편을 붙인다 — 앞 편 날짜는 안 바뀐다.
  ★11/19 특별한 날(special — 동지·연말·송년·새해·설 연휴·설날)은 시험과 따로 그날에만 나간다. 판정은 TRIAL(14편)만 본다.

    python pipeline/wisdom_card.py show [--date 2026-11-17]
    python pipeline/wisdom_card.py make [--date …] --out <path>
    python pipeline/wisdom_card.py path [--date …]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pulli_card import HOOK_TAIL, kst_today  # noqa: E402

TOPIC = "wisdom"
ACCENT = "#2E7D6B"                    # 짙은 청록(먹·한지와 어울리는 차분한 색) — 운세 표(주황·분홍)와 갈린다
DONT = "#B4533C"                      # '아끼면 좋은 말'·'새는 습관' 편의 번호 색(붉은 흙빛)
BRAND = "왕별이 · 말년 지혜"
MARK = "말년 지혜"                    # ★유튜브 제목에 늘 들어간다 — 채널 맥박(pulse_formats 'wisdom')이 이걸로 센다. 바꾸지 않는다
PILL = "50·60·70대 공감 · 말년 지혜"
FOOT = "※ 어르신들 이야기를 모아 정리했어요 · 집집마다 사정은 다를 수 있어요"
STYLE = "hanji"                       # 배경 그림체 — cover_short.CARD_STYLE_PROMPT['hanji'](치비 띠 동물 아님)
MIN_TOTAL = 10.0                      # 다섯 줄을 다 읽을 시간(덕담표 10초와 같게)
JUDGE = dt.date(2026, 12, 2)          # 판정일(pulse_experiments 'wisdom-trial' 와 같다 — 테스트가 맞춰 본다)
COMMON_TAGS = ["#말년지혜", "#인생지혜", "#시니어공감", "#50대", "#60대", "#70대", "#shorts"]
YT_TAGS = ["말년지혜", "인생지혜", "시니어공감", "좋은글", "노후", "부부", "자식", "왕별이"]
# theme_card.BANNED 밖에서 이 표에만 더 막는 말(종교·겁주기·게임 말투·명리 용어)
NO_WORDS = ("부처", "하나님", "하느님", "아멘", "기도해", "기도드", "기도합", "축복", "천국", "지옥", "귀신",
            "큰일", "끔찍", "후회합니다", "절대", "레전드", "ㅋㅋ", "S급", "꿀팁",
            "사주", "팔자", "일진", "육합", "삼합", "원진", "십신", "역술")

# 편 — date 는 KST 공개일. l1·l2 = 화면 제목 두 줄(l2 는 청록) · say(있으면) = 제목·말에 쓰는 이름. items = (큰 글자, 작은 글자, 설명란 한 문장).
#   큰 글자는 한 줄(약 12자 안), 작은 글자는 약 20자 안 — 화면에서 한 크기로 맞춘다(motion_short.wisdom_layout).
EPISODES = [
    {"id": "couple_words", "date": "2026-11-17", "l1": "오래가는 부부가", "l2": "자주 하는 말", "tone": "do",
     "tags": ["#오래가는부부", "#부부공감", "#황혼부부"],
     "hook": "two warm teacups side by side on a low wooden table by a sunny hanok paper window, autumn light, calm mood, no people",
     "items": [
         ("\"고마워요\"", "작은 일에도 먼저 건네요", "밥상·설거지 같은 작은 일에 건넨 고맙다는 말이 쌓여 정이 돼요."),
         ("\"당신 덕분이야\"", "좋은 일은 공을 돌려요", "잘된 일의 공을 배우자에게 돌리면, 다음에도 서로 돕고 싶어져요."),
         ("\"밥은 먹었어요?\"", "짧은 안부가 곧 마음이에요", "오래 산 부부일수록 짧은 안부 한마디가 '당신을 생각한다'는 뜻이 돼요."),
         ("\"내가 미안해\"", "먼저 하는 쪽이 이겨요", "다툰 뒤 먼저 사과하는 건 지는 게 아니라 집안의 평화를 지키는 일이에요."),
         ("\"오늘 고생했어요\"", "하루 끝에 건네는 한마디", "하루를 마치며 서로의 수고를 알아주면 잠자리가 편해져요."),
     ]},
    {"id": "exam_grandchild", "date": "2026-11-18", "l1": "수능 보는 손주에게", "l2": "힘이 되는 한마디", "tone": "do",
     "tags": ["#수능응원", "#손주사랑", "#할머니할아버지"],
     "hook": "a warm lunch box wrapped in a soft cloth on a wooden table at dawn, a small thermos beside it, gentle hopeful light, no people",
     "items": [
         ("\"넌 이미 잘했어\"", "결과보다 애쓴 날들을 봐요", "점수 얘기 대신 그동안 애쓴 날들을 알아주면 마음이 놓여요."),
         ("\"떨리는 건 당연해\"", "떨리는 마음을 알아줘요", "괜찮다고 다그치기보다 떨리는 게 당연하다고 해 주면 오히려 차분해져요."),
         ("\"아는 것부터 차분히\"", "부담 대신 차분한 응원", "'꼭 잘 봐라'보다 '아는 것부터 차분히'가 시험장에서 떠오르는 말이에요."),
         ("\"끝나면 맛있는 거 먹자\"", "즐거운 약속 하나", "시험 뒤 즐거운 약속이 있으면 긴 하루를 버틸 힘이 돼요."),
         ("\"우린 늘 네 편이야\"", "든든한 내 편이 있어요", "어떤 결과든 네 편이라는 말은 손주가 오래 기억하는 한마디예요."),
     ]},
    {"id": "children_visit", "date": "2026-11-19", "l1": "자식이 자주 찾아오는", "l2": "부모의 말버릇", "tone": "do",
     "tags": ["#부모자식관계", "#자식연락", "#부모의지혜"],
     "hook": "a cozy Korean living room at golden hour, an open front door with shoes neatly arranged, warm welcoming light, no people",
     "items": [
         ("\"와 줘서 고맙다\"", "온 것만으로 반겨 줘요", "늦게 왔다는 말보다 와 줘서 고맙다는 말이 다음 걸음을 부르죠."),
         ("\"바쁘면 괜찮다\"", "미안한 마음을 덜어 줘요", "못 와서 미안한 자식에게 괜찮다고 하면, 오히려 더 자주 오고 싶어져요."),
         ("\"네 생각대로 해라\"", "다 큰 자식은 믿어 줘요", "결정을 믿어 주는 부모 앞에서 자식은 고민을 더 털어놓아요."),
         ("\"잘하고 있다\"", "칭찬은 나이 들어도 좋아요", "어른이 된 자식도 부모의 칭찬 한마디에 힘을 얻어요."),
         ("\"또 와라, 기다릴게\"", "문을 열어 두는 말", "헤어질 때 다음을 기다린다는 말이 다음 방문의 약속이 돼요."),
     ]},
    {"id": "people_gather", "date": "2026-11-20", "l1": "말년에 사람이", "l2": "모이는 사람", "tone": "do",
     "say": "말년에 사람이 모이는 사람의 습관",
     "tags": ["#인간관계", "#말년복", "#좋은사람"],
     "hook": "a quiet Korean village alley in autumn with a low stone wall and persimmon tree, warm afternoon sun, friendly mood, no people",
     "items": [
         ("먼저 웃으며 인사해요", "인사가 정의 시작이에요", "먼저 건네는 인사 한마디가 이웃과의 정을 여는 첫걸음이에요."),
         ("남의 말을 옮기지 않아요", "믿음이 차곡차곡 쌓여요", "들은 말을 옮기지 않는 사람에게는 사람들이 마음을 터놓아요."),
         ("작은 것도 나눠요", "귤 하나도 정이에요", "귤 하나, 떡 한 조각을 나누는 사람 곁에 사람이 모여요."),
         ("자랑보다 칭찬을 해요", "남을 높이면 내가 빛나요", "내 자랑보다 남을 칭찬하는 사람과 이야기하면 즐거워요."),
         ("약속 시간을 지켜요", "작은 약속이 큰 믿음", "시간을 지키는 사람은 나이 들수록 더 믿음직해 보여요."),
     ]},
    {"id": "money_leak", "date": "2026-11-21", "l1": "노후에 돈이", "l2": "새는 습관", "tone": "dont",
     "tags": ["#노후생활", "#노후자금", "#돈관리습관"],
     "hook": "an old cloth coin purse and a small notebook on warm hanji paper, a pair of reading glasses beside them, soft lamp light, no people",
     "items": [
         ("정에 끌려 서는 보증", "보증은 마음 대신 짐이 돼요", "정 때문에 선 보증이 노후 살림을 흔드는 일이 많아요. 마음은 다른 방법으로 전해요."),
         ("모르는 전화 속 이체", "끊고 가족에게 먼저 물어요", "급하다며 돈을 보내라는 전화는 일단 끊고, 가족에게 먼저 확인해요."),
         ("늦은 밤 홈쇼핑 주문", "하룻밤 자고 정해요", "밤에 본 물건은 아침에 다시 보면 꼭 필요하지 않은 때가 많아요."),
         ("체면 때문에 큰 부조", "마음만큼이면 충분해요", "부조는 체면보다 형편에 맞게 해도 마음은 충분히 전해져요."),
         ("'꼭 오른다'는 권유", "모르는 건 하지 않아요", "잘 모르는 일에 돈을 맡기라는 권유는 가족과 먼저 상의해요."),
     ]},
    {"id": "children_dont", "date": "2026-11-22", "l1": "자식에게", "l2": "아끼면 좋은 말", "tone": "dont",
     "tags": ["#부모자식관계", "#자식에게하지말아야할말", "#부모의지혜"],
     "hook": "a quiet Korean kitchen table with a steaming bowl of soup and two spoons, soft morning light through a window, no people",
     "items": [
         ("\"언제 결혼하니\"", "때가 되면 먼저 말해요", "결혼·자식 얘기는 묻지 않아도 자식이 먼저 꺼낼 때가 와요."),
         ("\"옆집 아이는…\"", "비교는 정을 깎아요", "남의 집 자식과 견주는 말은 칭찬 열 마디를 지워 버려요."),
         ("\"너 때문에 참았다\"", "지난 희생은 짐이 돼요", "부모의 희생 이야기는 고마움보다 무거운 짐으로 남기 쉬워요."),
         ("\"그러게 내가 뭐랬니\"", "지난 일은 덮어 줘요", "일이 틀어졌을 때는 따지기보다 다독여 주는 게 먼저예요."),
         ("\"벌이는 얼마나 되니\"", "형편은 기다려 줘요", "살림 형편은 자식이 먼저 말할 때까지 기다려 주면 편해해요."),
     ]},
    {"id": "inlaw_words", "date": "2026-11-23", "l1": "며느리·사위가", "l2": "편해하는 말", "tone": "do",
     "tags": ["#며느리", "#사위", "#시댁처가"],
     "hook": "a neatly set low dining table in a hanok room with side dishes under soft light, warm family mood, no people",
     "items": [
         ("\"편하게 쉬다 가라\"", "손님 아닌 식구로 대해요", "와서 일부터 하게 하기보다 쉬다 가라는 말이 마음을 열어요."),
         ("\"너희 방식대로 해라\"", "살림은 믿고 맡겨요", "아이 키우는 법·살림 방식은 그 집에 맡겨 주면 다툼이 줄어요."),
         ("\"고생했다, 고맙다\"", "수고를 알아줘요", "명절이나 집안일 뒤 고맙다는 한마디가 오래 남아요."),
         ("\"연락은 편할 때 해라\"", "부담을 덜어 줘요", "연락을 재촉하지 않으면 오히려 편하게 먼저 연락해요."),
         ("\"우리 걱정은 마라\"", "짐을 지우지 않아요", "부모가 잘 지낸다는 말이 자식 부부에게는 가장 큰 선물이에요."),
     ]},
    {"id": "home_laughter", "date": "2026-11-24", "l1": "집안에 웃음이", "l2": "많은 집의 습관", "tone": "do",
     "tags": ["#가족", "#화목한가정", "#집안분위기"],
     "hook": "a bright tidy Korean entrance hall with a small flower vase and warm light, calm cheerful home mood, no people",
     "items": [
         ("밥은 함께 먹어요", "한 상이 정을 이어요", "하루 한 끼라도 같이 먹으면 할 이야기가 저절로 생겨요."),
         ("TV보다 얘기해요", "오늘 있었던 일 나누기", "저녁에 TV를 잠시 끄고 하루 이야기를 나누면 집이 환해져요."),
         ("생일은 꼭 챙겨요", "작은 케이크도 기뻐요", "크게 차리지 않아도 생일을 기억해 주는 마음이 웃음을 만들어요."),
         ("'고마워'를 붙여요", "말끝마다 버릇처럼", "물 한 잔 건네받을 때도 고맙다고 하면 집안 말투가 고와져요."),
         ("현관을 환하게 둬요", "들어올 때 기분이 좋아요", "현관이 밝고 깔끔하면 집에 들어설 때마다 마음이 편해요."),
     ]},
    {"id": "kimjang_words", "date": "2026-11-25", "l1": "김장하는 날", "l2": "웃음 나는 한마디", "tone": "do",
     "tags": ["#김장", "#김장철", "#가족모임"],
     "hook": "a big basket of salted napa cabbage and red pepper paste in a sunny Korean courtyard in late autumn, warm mood, no people",
     "items": [
         ("\"같이 하니 금방이다\"", "힘든 일도 함께면 가벼워요", "김장은 고된 일이지만 같이 한다는 말에 힘이 나요."),
         ("\"올해 김치 맛있겠다\"", "수고에 기대를 얹어요", "맛있겠다는 말 한마디가 하루의 수고를 즐거움으로 바꿔요."),
         ("\"허리 펴고 쉬었다 해요\"", "서로를 챙겨 줘요", "오래 앉아 하는 일이니 쉬어 가자는 말이 서로를 챙기는 말이에요."),
         ("\"수육 삶아 놨다\"", "맛있는 쉼표 하나", "김장 날 수육 한 접시가 모두를 웃게 하는 쉼표가 돼요."),
         ("\"조금씩 싸 가거라\"", "나눔으로 마무리해요", "한 통씩 나눠 주며 끝내면 김장이 집안 잔치가 돼요."),
     ]},
    {"id": "alone_time", "date": "2026-11-26", "l1": "혼자 있는 시간이", "l2": "즐거운 사람의 습관", "tone": "do",
     "tags": ["#혼자의시간", "#노후생활", "#소소한행복"],
     "hook": "a sunny window seat in a Korean apartment with a potted plant, an open notebook and a cup of tea, peaceful mood, no people",
     "items": [
         ("아침 햇볕 쬐며 걸어요", "하루가 가볍게 열려요", "아침에 햇볕을 쬐며 동네를 한 바퀴 돌면 하루가 가볍게 시작돼요."),
         ("하루 한 사람 안부", "전화 한 통이 마음을 데워요", "하루 한 사람에게 안부를 전하면 혼자여도 외롭지 않아요."),
         ("좋아하는 노래 틀어요", "집 안에 생기가 돌아요", "좋아하는 노래 한 곡이 조용한 집에 생기를 불어넣어요."),
         ("화분 하나 가꿔요", "돌볼 것이 있으면 즐거워요", "물을 주고 새잎을 기다리는 재미가 하루에 작은 기쁨이 돼요."),
         ("일기 한 줄 써요", "하루가 차곡차곡 남아요", "한 줄만 적어도 지나고 보면 소중한 하루하루가 남아요."),
     ]},
    {"id": "hurt_feelings", "date": "2026-11-27", "l1": "서운할 때", "l2": "마음 편해지는 생각", "tone": "do",
     "tags": ["#마음공부", "#서운함", "#마음다스리기"],
     "hook": "a calm pond with fallen autumn leaves and a small wooden bench nearby, soft overcast light, peaceful mood, no people",
     "items": [
         ("\"사정이 있었겠지\"", "먼저 한 번 이해해 봐요", "서운한 일 뒤에는 내가 모르는 사정이 있을 때가 많아요."),
         ("\"하루 자고 생각하자\"", "밤 지나면 작아져요", "바로 말하기보다 하룻밤 지나 생각하면 서운함이 한결 작아져요."),
         ("\"부드럽게 말해 보자\"", "말 안 하면 몰라요", "꾹 참기보다 부드럽게 말하면 상대도 미처 몰랐다고 해요."),
         ("\"내 마음은 내가 챙기자\"", "좋아하는 일로 기분 전환", "서운할 때 좋아하는 일을 하면 마음이 먼저 풀려요."),
         ("\"좋았던 날도 많았지\"", "고마운 기억을 꺼내요", "서운한 한 번보다 고마웠던 여러 날을 떠올리면 마음이 넓어져요."),
     ]},
    {"id": "mouth_wallet", "date": "2026-11-28", "l1": "나이 들수록", "l2": "입은 닫고 지갑은 열고", "tone": "do",
     "say": "나이 들수록 지키면 좋은 습관",
     "tags": ["#어른의품격", "#인생명언", "#말조심"],
     "hook": "an old pine tree on a quiet Korean hillside at sunset, soft golden light, dignified calm mood, no people",
     "items": [
         ("잔소리는 한 번만", "두 번부턴 서운함이 돼요", "같은 말을 두 번 하면 걱정이 잔소리로 들리기 시작해요."),
         ("칭찬은 여러 번", "들을수록 힘이 나요", "칭찬은 여러 번 들어도 질리지 않고 힘이 돼요."),
         ("밥값은 가끔 먼저", "넉넉한 사람으로 남아요", "가끔 먼저 내는 밥값 한 번이 넉넉한 어른으로 기억되게 해요."),
         ("옛날 얘기는 짧게", "듣는 사람도 즐겁게", "지난 이야기는 짧고 재미있게 하면 다들 더 듣고 싶어 해요."),
         ("남의 흉은 못 들은 척", "말은 돌고 돌아요", "남의 흉에 맞장구치지 않으면 내 이야기도 함부로 돌지 않아요."),
     ]},
    {"id": "friends_last", "date": "2026-11-29", "l1": "친구·이웃과", "l2": "오래가는 사이", "tone": "do",
     "say": "친구·이웃과 오래가는 사이의 비결",
     "tags": ["#친구", "#이웃사촌", "#오랜인연"],
     "hook": "two wooden chairs on a quiet Korean garden porch at sunset with autumn leaves, warm friendly light, no people",
     "items": [
         ("빌린 건 꼭 돌려줘요", "작은 것부터 믿음이에요", "우산 하나, 그릇 하나도 제때 돌려주면 믿음이 쌓여요."),
         ("돈 거래는 하지 않아요", "정은 지키고 돈은 깔끔히", "돈이 오가면 오랜 정도 흔들리기 쉬워요. 마음은 다른 걸로 나눠요."),
         ("궂은일엔 먼저 가요", "힘들 때 곁이 기억돼요", "좋은 날보다 힘든 날 곁에 있어 준 사람이 오래 기억돼요."),
         ("비밀은 지켜 줘요", "털어놓을 수 있는 사람", "들은 비밀을 지켜 주면 그 사람에게 나는 믿을 친구가 돼요."),
         ("가끔 먼저 연락해요", "기다리지 말고 먼저", "연락을 기다리기보다 먼저 안부를 물으면 사이가 이어져요."),
     ]},
    {"id": "legacy", "date": "2026-11-30", "l1": "자식에게 물려주면", "l2": "좋은 것", "tone": "do",
     "tags": ["#물려줄것", "#가족사랑", "#노후준비"],
     "hook": "an old cloth-bound family album and a handwritten recipe card on a wooden table in warm afternoon light, nostalgic mood, no people",
     "items": [
         ("정리된 서류 한 묶음", "가족이 헤매지 않아요", "통장·보험·집 서류를 한곳에 정리해 두면 가족이 덜 헤매요."),
         ("가족 사진과 이야기", "우리 집 뿌리를 알게 해요", "사진 뒤에 얽힌 이야기를 들려주면 자식이 집안의 뿌리를 알게 돼요."),
         ("집안 음식 비법", "레시피 한 장이 추억이에요", "손맛을 적어 둔 레시피 한 장이 오래도록 집밥을 이어 줘요."),
         ("화목한 형제 사이", "무엇보다 큰 유산이에요", "형제가 사이좋게 지내도록 다독여 주는 것이 가장 큰 유산이에요."),
         ("고맙다는 편지 한 통", "오래 꺼내 읽는 선물", "고마웠다는 편지 한 통은 자식이 두고두고 꺼내 읽어요."),
     ]},
    # ★2026-11-19 특별한 날 달력(사용자 "수능날 같은 특별한 날에 위로·공감되는 것") — 시험(11/17~11/30)과 따로, 그날에만 17:40.
    #   special = 화면 알약에 쓰는 그날 이름. 동지 = 2026-12-22(KST 로 12/22 05:50 — 12/21 20:50 UTC) ·
    #   설날 = 2027-02-07(그믐 합삭이 2/6 15:56 UTC = 2/7 00:56 KST — 중국은 2/6) · 연휴 2/6~2/9.
    #   종교 말은 넣지 않는다(성탄 대신 '연말 가족 모임'). 판정(12/2)이 '접는다'여도 이 날들은 따로 정한다(빼려면 여기서 지운다).
    {"id": "dongji_porridge", "date": "2026-12-22", "special": "동지", "l1": "동짓날", "l2": "팥죽 나누며 하는 말", "tone": "do",
     "tags": ["#동지", "#동지팥죽", "#겨울나기"],
     "hook": "a steaming bowl of red bean porridge with small rice cake balls on a low wooden table in a warm hanok room, winter evening light, no people",
     "items": [
         ("\"한 그릇 같이 들자\"", "팥죽은 나눌수록 따뜻해요", "동지 팥죽은 이웃과 나눠 먹던 음식이라, 같이 먹자는 말에 정이 담겨요."),
         ("\"긴 밤 잘 보내요\"", "가장 긴 밤에 건네는 안부", "일 년 중 밤이 가장 긴 날이라, 잘 보내라는 안부 한마디가 따뜻하게 들려요."),
         ("\"이제 해가 길어진대\"", "내일부터 낮이 길어져요", "동지가 지나면 낮이 조금씩 길어져요. 좋은 날이 온다는 말로 들려 마음이 밝아져요."),
         ("\"새알심 나이만큼 먹어\"", "웃음 나는 옛말 한마디", "새알심을 나이만큼 먹는다는 옛말은 식구들을 한바탕 웃게 하는 이야기예요."),
         ("\"올해도 고생 많았어\"", "한 해 끝자락의 인사", "동지는 한 해 끝자락이라, 올 한 해 수고했다는 말이 잘 어울려요."),
     ]},
    {"id": "yearend_family", "date": "2026-12-24", "special": "연말", "l1": "연말 가족 모임에서", "l2": "듣고 싶은 말", "tone": "do",
     "tags": ["#연말모임", "#가족모임", "#연말인사"],
     "hook": "a cozy Korean living room with warm string lights and a small pine branch, a low table set with fruit and tea, winter evening, no people",
     "items": [
         ("\"와 줘서 반갑다\"", "모인 것만으로 고마워요", "바쁜 연말에 모인 것만으로도 고맙다는 말이 모임을 따뜻하게 열어요."),
         ("\"올해 제일 좋았던 일은?\"", "좋은 이야기부터 꺼내요", "좋았던 일부터 물으면 식탁에 웃음이 먼저 돌아요."),
         ("\"다들 별일 없어 다행이다\"", "무탈함에 감사해요", "별일 없이 한 해를 보낸 것만으로도 감사하다는 말이 서로를 다독여요."),
         ("\"내년엔 더 자주 보자\"", "다음 만남을 약속해요", "헤어질 때 다음을 약속하면 모임이 아쉬움 대신 기대로 끝나요."),
         ("\"사진 한 장 찍자\"", "오늘을 남겨요", "다 같이 찍은 사진 한 장이 오래도록 꺼내 보는 추억이 돼요."),
     ]},
    {"id": "yearend_self", "date": "2026-12-31", "special": "송년", "l1": "한 해를 보내며", "l2": "나에게 건네는 말", "tone": "do",
     "tags": ["#송년", "#한해마무리", "#나에게하는말"],
     "hook": "a quiet window view of a snowy Korean village at dusk on the last day of the year, a cup of tea on the sill, calm reflective mood, no people",
     "items": [
         ("\"올해도 잘 버텼다\"", "버틴 것도 장한 일이에요", "한 해를 무사히 지나온 것만으로도 스스로를 칭찬할 만해요."),
         ("\"고마운 사람이 많았네\"", "고마운 얼굴 떠올리기", "고마웠던 사람을 하나씩 떠올리면 한 해가 넉넉하게 느껴져요."),
         ("\"아쉬운 건 내려놓자\"", "새해엔 가볍게 시작해요", "아쉬운 일을 한 해 끝에 내려놓으면 새해를 가벼운 마음으로 맞을 수 있어요."),
         ("\"그래도 웃은 날이 많았지\"", "좋았던 날을 세어 봐요", "힘든 날보다 웃은 날을 세어 보면 한 해가 다르게 보여요."),
         ("\"내년에도 천천히 가자\"", "서두르지 않아도 돼요", "새해 목표보다 천천히 가자는 다짐이 마음을 편하게 해요."),
     ]},
    {"id": "newyear_blessing", "date": "2027-01-01", "special": "새해", "l1": "새해 첫날", "l2": "자식·손주에게 건네는 덕담", "tone": "do",
     "tags": ["#새해덕담", "#새해인사", "#덕담"],
     "hook": "the first sunrise of the new year over a calm sea with a small traditional Korean pavilion on a hill, warm golden light, hopeful mood, no people",
     "items": [
         ("\"올해도 네 편이야\"", "든든한 응원 한마디", "새해 첫날 들은 응원 한마디는 일 년 내내 힘이 돼요."),
         ("\"밥 잘 챙겨 먹어라\"", "가장 오래된 사랑 표현", "밥 챙기라는 당부는 어른이 건넬 수 있는 가장 따뜻한 걱정이에요."),
         ("\"하고 싶은 거 해 봐라\"", "도전을 믿어 줘요", "하고 싶은 일을 해 보라는 말은 자식·손주가 오래 기억하는 덕담이에요."),
         ("\"자주 웃으며 살자\"", "웃음이 복을 불러요", "새해 첫 덕담으로 웃자는 말이 가장 부담 없이 따뜻해요."),
         ("\"너희가 있어 행복하다\"", "마음을 그대로 전해요", "쑥스러워도 새해 첫날만큼은 마음을 그대로 말해 주면 좋아요."),
     ]},
    {"id": "seollal_dont", "date": "2027-02-06", "special": "설 연휴", "l1": "설에 모인 가족에게", "l2": "아끼면 좋은 말", "tone": "dont",
     "tags": ["#설날", "#명절잔소리", "#가족모임"],
     "hook": "a warm Korean family home during Lunar New Year with a low table of traditional dishes and rice cake soup, soft afternoon light, no people",
     "items": [
         ("\"취직은 했니\"", "물어보지 않아도 돼요", "일자리 이야기는 묻지 않아도 자식이 먼저 꺼낼 때가 와요."),
         ("\"살 좀 빼야겠다\"", "생김새 말은 아껴요", "명절에 들은 몸매 이야기는 오래 마음에 남아요."),
         ("\"누구네는 집 샀다더라\"", "견주는 말은 아껴요", "남의 집 소식과 견주는 말은 반가운 자리를 금세 식혀요."),
         ("\"용돈은 얼마 줄 거니\"", "돈 이야기는 조용히", "명절 용돈 이야기는 서로 부담이 되니 조용히 넘기는 게 좋아요."),
         ("\"너는 늘 그 모양이냐\"", "탓은 내려놓아요", "지난 일을 꺼내 탓하면 명절이 다툼으로 끝나기 쉬워요."),
     ]},
    {"id": "seollal_blessing", "date": "2027-02-07", "special": "설날", "l1": "설날 세배 받을 때", "l2": "건네면 좋은 덕담", "tone": "do",
     "tags": ["#세배", "#설날덕담", "#설날인사"],
     "hook": "a bright Korean hanok room on Lunar New Year morning with a folding screen and a low table with fruit and rice cakes, warm light, no people",
     "items": [
         ("\"쑥쑥 씩씩하게 크거라\"", "아이에게는 이 한마디", "아이에게는 공부 얘기보다 씩씩하게 크라는 덕담이 더 기억에 남아요."),
         ("\"하는 일 술술 풀려라\"", "일하는 자식에게", "일하는 자식에게는 잘 풀리라는 응원이 가장 반가운 덕담이에요."),
         ("\"둘이 서로 아껴라\"", "부부가 된 자식에게", "부부가 된 자식에게는 서로 아끼라는 말이 오래 남는 덕담이에요."),
         ("\"새해 복 많이 받아라\"", "모두에게 건네는 첫마디", "세배를 받으며 건네는 첫마디는 역시 복 많이 받으라는 말이에요."),
         ("\"얼굴 보니 좋구나\"", "만난 기쁨부터 말해요", "덕담보다 먼저, 얼굴 보니 좋다는 말이 세배 자리를 따뜻하게 해요."),
     ]},
]
TRIAL = [e for e in EPISODES if not e.get("special")]      # 2주 시험 14편(11/17~11/30) — 판정은 이것만 본다


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def episode_for(d: dt.date) -> dict | None:
    """그날 편(없으면 None = 건너뜀)."""
    return next((e for e in EPISODES if _d(e["date"]) == d), None)


def is_post_day(d: dt.date) -> bool:
    return episode_for(d) is not None


def first_day() -> dt.date:
    return min(_d(e["date"]) for e in EPISODES)


def last_day() -> dt.date:
    return max(_d(e["date"]) for e in EPISODES)


def headline(ep: dict) -> str:
    return f"{ep['l1']} {ep['l2']}"


def spoken(ep: dict) -> str:
    """제목·말·설명란 첫 줄에 쓰는 이름 — 화면 두 줄을 이으면 어색한 편은 say 로 바꾼다('…사람' → '…사람의 습관')."""
    return ep.get("say") or headline(ep)


def title(ep: dict) -> str:
    """'오래가는 부부가 자주 하는 말 5가지 | 말년 지혜 #오래가는부부 #부부공감' — 날짜 없이(오래 검색되게).
    run_pipeline 이 끝에 ' #shorts' 를 붙인다. 95자 안."""
    base = f"{spoken(ep)} {len(ep['items'])}가지 | {MARK}"
    for tag in ep["tags"]:
        if len(base) + 1 + len(tag) > 86:
            break
        base += f" {tag}"
    return base


def narration(ep: dict) -> str:
    return f"{spoken(ep)}, 다섯 가지예요. 몇 번이 제일 와닿으세요? 댓글로 번호를 남겨 주세요."


def description(ep: dict) -> str:
    """설명란 = 다섯 줄마다 왜 그런지(메타데이터도 심사가 본다 — 편마다 내용이 다르다)."""
    lines = [f"{spoken(ep)}, 다섯 가지를 한 장에 모았어요. 몇 번이 제일 와닿으세요? 댓글로 번호를 남겨 주세요 🙏", ""]
    lines += [f"{k}. {big.strip(chr(34))} — {why}" for k, (big, _small, why) in enumerate(ep["items"], 1)]
    lines += ["", "※ 왕별이가 어르신들 이야기를 모아 정리한 생활 지혜예요. 집집마다 사정은 다를 수 있어요.", "",
              " ".join(ep["tags"] + COMMON_TAGS)]
    return "\n".join(lines)


def scene(ep: dict) -> dict:
    pill = f"{ep['special']} · {MARK}" if ep.get("special") else PILL     # 특별한 날은 알약에 그날 이름
    return {"type": "wisdom", "pill": pill, "title": ep["l1"], "title2": ep["l2"], "tone": ep.get("tone", "do"),
            "items": [{"big": big, "small": small} for big, small, _why in ep["items"]],
            "foot": FOOT, "brand": BRAND, "narration": narration(ep)}


def storyboard(d: dt.date) -> dict:
    ep = episode_for(d)
    if ep is None:
        raise ValueError(f"{d}: 말년 지혜 표 편이 없는 날")
    t = title(ep)
    return {
        "date": d.isoformat(), "topic": TOPIC, "theme": f"wisdom:{ep['id']}", "privacy": "public",
        "accent": DONT if ep.get("tone") == "dont" else ACCENT, "_min_total": MIN_TOTAL,
        "hook_title": headline(ep), "headline": t,
        "thumbnail_hook": ep["hook"] + HOOK_TAIL, "thumbnail_style": STYLE,
        "scenes": [scene(ep)],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(ep)}},
        "notes": f"말년 지혜 표 · wisdom:{ep['id']} · wisdom_card.py 가 만든 스토리보드(11/17~11/30 2주 시험 · 17:40)",
    }


def is_wisdom(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    d = _d(str(sb.get("date"))[:10])
    eid = str(sb.get("theme") or "")[len("wisdom:"):]
    ep = next((e for e in EPISODES if e["id"] == eid), None) or episode_for(d)
    return {"title": title(ep)[:95], "description": description(ep), "tags": list(YT_TAGS)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="말년 지혜 표")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(os.path.relpath(path_for(d), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace("\\", "/"))
        return 0
    if not is_post_day(d):
        print(f"{d}: 말년 지혜 표 편성일이 아니다({first_day()}~{last_day()}) — 건너뜀")
        return 0
    sb = storyboard(d)
    if a.cmd == "show":
        print(f"{d} · {sb['theme']} · {sb['platforms']['youtube']['title']}")
        for k, it in enumerate(sb["scenes"][0]["items"], 1):
            print(f"  {k}. {it['big']}  — {it['small']}")
        print("  🎙️", sb["scenes"][0]["narration"])
        return 0
    out = a.out or path_for(d)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
