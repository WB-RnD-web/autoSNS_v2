#!/usr/bin/env python3
"""띠별 '테마 순위' 한 장 표 쇼츠 — 매일 낮 12시 (2026-10-01).

왜: 매일 06시 '12띠 한 장 표'(fortune_card)가 첫 편 5,944회 — 같은 기간 다른 쇼츠는 편당 ~1,000회에서 멈췄다.
  경쟁 채널은 같은 표에 ★테마를 바꿔 하루 여러 편을 올린다
  (가화만사성 "자식 덕 보는 나이 50~91년생 전부" 168,249 · "조상이 돕는 성씨 순위" 403,000).
  → 06시 표는 그대로 두고, 낮 12시에 테마 표를 한 편 더 낸다.

전부 코드가 정한다(루틴은 실행 스위치만): 테마 = 날짜 순환(THEMES), 순위·점수·한 줄 = 날짜+테마 해시.
  같은 날짜면 늘 같은 표. 문구는 아래 목록에서만 나온다 — 의료·투자·겁주는 말이 끼어들 틈이 없다(테스트가 막는다).
  렌더는 fortune_card 와 같은 'card' 장면(motion_short) — 스토리보드에 장면을 직접 싣는다(CI 에서 LLM 안 씀).

    python pipeline/theme_card.py show [--date 2026-10-02]          # 미리보기
    python pipeline/theme_card.py make [--date …] --out <path>      # 스토리보드 JSON 쓰기
    python pipeline/theme_card.py path [--date …]                   # 오늘 파일 경로(output/news/…)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fortune_card import ANIMALS, WEEKDAY, _h, years_of  # noqa: E402

TOPIC = "fortune_theme"
EPOCH = dt.date(2026, 10, 2)          # 첫 편 — 테마 순환의 0번
# ★2026-10-08부터 이틀에 한 번(짝수 번째 날만) — 10/7 진단: 같은 꼴 표를 매일 내면 피드가 덜 퍼뜨린다
#   (name_card.ROTATION 과 같은 이유). 테마는 그대로 날짜 순환(11개 · 이틀 간격이어도 전부 돈다). 되돌리기 = None.
ALT_FROM: dt.date | None = dt.date(2026, 10, 8)
KST = dt.timezone(dt.timedelta(hours=9))
ACCENT = "#C9A227"
BRAND = "왕별이 · 띠별 순위"

# card = 화면 제목(한 줄 · 한글 9자 이내 — 96px 한 줄에 들어가야 한다)
# yt   = 유튜브 제목 앞부분 · 내레이션. {m} = 달
# 한 줄(top 3 · mid 5 · low 4칸)은 9자 이내, 단정·겁주기·의료·투자 금지(테스트가 검사한다)
THEMES = [
    {"id": "money", "card": "돈 들어오는 띠", "yt": "{m}월 돈 들어오는 띠 순위",
     "top": ["목돈 들어와요", "밀린 돈 받아요", "지갑이 두둑", "뜻밖의 용돈"],
     "mid": ["알뜰하면 이득", "작은 수입", "씀씀이 조절", "모으는 재미", "공과금 정리", "비상금 챙기기"],
     "low": ["지갑 단속", "충동구매 조심", "빌려주기 금물", "새는 돈 막기", "영수증 챙기기"],
     "hook": "warm golden morning light on a traditional Korean wooden table with a silk coin pouch and "
             "persimmons, soft bokeh, cozy and lucky mood, no people, no text"},
    {"id": "children", "card": "자식 덕 보는 띠", "yt": "자식 덕 보는 띠 순위",
     "top": ["자식 효도 받아요", "기쁜 소식 와요", "자식 자랑할 일", "든든한 지원군"],
     "mid": ["안부 전화 와요", "함께 밥 한 끼", "소소한 선물", "마음이 통해요", "웃음 나는 대화", "사진 한 장"],
     "low": ["먼저 연락하기", "잔소리는 쉬어요", "서운함 내려놓기", "기다려 주기", "칭찬 한마디"],
     "hook": "cozy Korean living room at golden hour, framed family photos on a wooden shelf, warm tea on a "
             "low table, soft bokeh, no faces, no text"},
    {"id": "lateluck", "card": "말년 복 있는 띠", "yt": "말년 복 있는 띠 순위",
     "top": ["편안한 노후", "복이 쌓여요", "웃을 일 많아요", "든든한 곳간"],
     "mid": ["꾸준함이 복", "건강이 재산", "작은 행복", "차곡차곡 쌓여요", "여유가 생겨요", "취미가 복"],
     "low": ["욕심 내려놓기", "무리는 금물", "생활비 점검", "천천히 가요", "마음 느긋하게"],
     "hook": "peaceful Korean hanok courtyard in autumn afternoon, persimmon tree, warm sunlight, calm and "
             "abundant mood, no people, no text"},
    {"id": "helper", "card": "귀인 만나는 띠", "yt": "{m}월 귀인 만나는 띠 순위",
     "top": ["귀인이 와요", "좋은 인연", "도움 받아요", "반가운 만남"],
     "mid": ["옛 친구 연락", "이웃과 정 나눔", "모임에 복", "말벗이 생겨요", "좋은 소개", "고마운 손길"],
     "low": ["말 한마디 조심", "약속 다시 확인", "오해 풀기", "먼저 인사하기", "부탁은 신중히"],
     "hook": "two warm cups of Korean tea on a wooden table by a sunny window, autumn leaves outside, "
             "friendly welcoming mood, no people, no text"},
    {"id": "couple", "card": "부부 금슬 좋은 띠", "yt": "부부 금슬 좋은 띠 순위",
     "top": ["금슬 최고", "함께 웃어요", "손잡고 산책", "다정한 하루"],
     "mid": ["고운 말 한마디", "같이 장보기", "추억 이야기", "차 한잔 데이트", "서로 칭찬", "함께 산책"],
     "low": ["잔소리 줄이기", "먼저 양보", "서운함 풀기", "말투 부드럽게", "고맙다 말하기"],
     "hook": "two pairs of traditional Korean rubber shoes side by side on a hanok porch in warm evening light, "
             "gentle romantic mood, no people, no text"},
    {"id": "grandkids", "card": "손주 복 있는 띠", "yt": "손주 복 있는 띠 순위",
     "top": ["손주 재롱 가득", "기쁜 소식", "손주 자랑", "웃음꽃 활짝"],
     "mid": ["영상통화 와요", "선물 고르는 재미", "소소한 기쁨", "사진 한 장", "동화책 읽기", "함께 나들이"],
     "low": ["용돈은 적당히", "돌봄은 적당히", "기다려 주기", "먼저 안부", "몸 먼저 챙기기"],
     "hook": "colorful children's toys and a picture book on a warm Korean floor cushion in soft afternoon "
             "light, joyful cozy mood, no people, no text"},
    {"id": "doublejoy", "card": "겹경사 생기는 띠", "yt": "{m}월 겹경사 생기는 띠 순위",
     "top": ["겹경사 와요", "기쁜 소식 둘", "좋은 일 연달아", "축하받을 일"],
     "mid": ["작은 경사", "반가운 소식", "잔치 초대", "웃을 일 생겨요", "선물 받아요", "좋은 기별"],
     "low": ["준비는 미리", "지출 계획 세우기", "몸 먼저 챙기기", "서두르면 손해", "일정 다시 확인"],
     "hook": "festive Korean table with rice cakes, fruit and red and gold silk ribbons, warm celebratory light, "
             "no people, no text"},
    {"id": "light", "card": "몸이 가벼운 띠", "yt": "{m}월 몸이 가벼운 띠 순위",
     "top": ["몸이 가벼워요", "잠이 달아요", "기운이 펄펄", "걷기 좋은 때"],
     "mid": ["물 자주 마시기", "스트레칭 굿", "제때 식사", "가벼운 산책", "일찍 자기", "햇볕 쬐기"],
     "low": ["무리는 금물", "밤잠 챙기기", "찬바람 조심", "과식은 쉬어요", "천천히 움직이기"],
     "hook": "quiet Korean park path in crisp autumn morning sunlight, golden ginkgo leaves, fresh and "
             "energetic mood, no people, no text"},
    {"id": "openluck", "card": "운이 트이는 띠", "yt": "{m}월 운이 트이는 띠 순위",
     "top": ["막힌 일 풀려요", "운이 활짝", "하는 일 술술", "기회가 와요"],
     "mid": ["천천히 가면 이득", "꾸준함이 답", "작은 행운", "차근차근", "준비하면 굿", "좋은 흐름"],
     "low": ["서두르면 손해", "한 템포 쉬기", "확인 또 확인", "마음 느긋하게", "약속 다시 확인"],
     "hook": "sunrise over layered Korean mountains with soft mist, golden light breaking through clouds, "
             "hopeful mood, no people, no text"},
    {"id": "friends", "card": "친구 복 많은 띠", "yt": "친구 복 많은 띠 순위",
     "top": ["친구가 찾아와요", "반가운 연락", "모임에 웃음", "든든한 벗"],
     "mid": ["안부 한 통", "차 한잔 약속", "옛 추억", "정 나누기", "동창 소식", "함께 나들이"],
     "low": ["말 한마디 조심", "돈거래 금물", "약속 지키기", "먼저 연락", "험담은 쉬어요"],
     "hook": "a cozy Korean tea house table set for friends with several teacups and sweets, warm lantern light, "
             "friendly mood, no people, no text"},
    {"id": "home", "card": "집안이 편한 띠", "yt": "{m}월 집안이 편한 띠 순위",
     "top": ["집안이 화목", "웃음꽃 활짝", "평안한 집", "가족이 한마음"],
     "mid": ["정리하면 복", "가족 식사", "대청소 운", "화분 하나", "따뜻한 저녁", "소소한 대화"],
     "low": ["큰소리 금물", "살림 점검", "문단속 꼼꼼", "지출 정리", "서운함 풀기"],
     "hook": "warm Korean home kitchen in the evening with a pot of stew and rice bowls on the table, soft "
             "lamp light, peaceful family mood, no people, no text"},
]
TIERS = (("top", 3), ("mid", 5), ("low", 4))   # 1~3위 · 4~8위 · 9~12위

# 테스트가 문구 전체에서 찾는 금지어(fortune·weekly 규칙과 같은 결)
BANNED = ("치료", "완치", "처방", "복용", "수술", "진단", "약 ", "보약", "한약", "영양제", "암", "당뇨", "고혈압",
          "주식", "코인", "로또", "복권", "대출", "빚", "투자", "부동산", "수익률", "종목",
          "죽음", "사망", "파산", "망한", "재앙", "저주", "삼재", "사고", "이혼", "사기", "배신",
          "충격", "경악", "역대급", "대박", "무조건", "떼돈", "부적", "굿판", "굿을", "점집")


def is_post_day(d: dt.date) -> bool:
    return ALT_FROM is None or d < ALT_FROM or (d - ALT_FROM).days % 2 == 0


def theme_for(d: dt.date) -> dict:
    return THEMES[(d - EPOCH).days % len(THEMES)]


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def build_rows(d: dt.date, th: dict) -> list[dict]:
    k = f"{d.isoformat()}|{th['id']}"
    order = sorted(ANIMALS, key=lambda a: _h(k, "order", a))
    score = 90 + _h(k, "s1") % 9                  # 1위 90~98점
    rows, i = [], 0
    for tier, n in TIERS:
        bank = sorted(th[tier], key=lambda x: _h(k, "line", tier, x))
        for j in range(n):
            a = order[i]
            if i:
                score -= 1 + _h(k, "gap", i) % 3
            rows.append({"rank": i + 1, "animal": a, "years": years_of(a), "score": max(score, 58),
                         "line": bank[j % len(bank)]})
            i += 1
    return rows


def yt_phrase(d: dt.date, th: dict) -> str:
    return th["yt"].format(m=d.month)


def title(d: dt.date, th: dict) -> str:
    return f"{yt_phrase(d, th)} 1위~12위 | {d.month}월 {d.day}일 · 45~96년생 전부"


def description(d: dt.date, th: dict) -> str:
    tag = th["card"].replace(" ", "")
    return (f"{yt_phrase(d, th)} — 12띠를 한 장에 모았어요. 내 띠는 몇 위인가요? 댓글로 남겨 주세요 🙏\n"
            f"매일 아침 6시엔 '오늘 띠별 운세', 낮 12시엔 '띠별 순위 특집'이 올라와요.\n\n"
            "※ 재미로 보는 운세입니다.\n\n"
            f"#운세 #띠별운세 #{tag} #띠별순위 #shorts")


def storyboard(d: dt.date) -> dict:
    th = theme_for(d)
    pill = f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일 · 특집"
    narr = f"{yt_phrase(d, th)}입니다. 내 띠는 몇 위인지 확인하고, 댓글로 남겨 주세요."
    t = title(d, th)
    return {
        "date": d.isoformat(), "topic": TOPIC, "theme": th["id"], "privacy": "public",
        "accent": ACCENT, "_min_total": 7.0,
        "hook_title": yt_phrase(d, th), "headline": t,
        "thumbnail_hook": th["hook"],
        "scenes": [{"type": "card", "pill": pill, "title": th["card"], "rows": build_rows(d, th),
                    "brand": BRAND, "narration": narr}],
        "platforms": {"youtube": {"title": f"{t} #shorts", "description": description(d, th)}},
        "notes": f"띠별 테마 순위 표 · theme={th['id']} · theme_card.py 가 만든 스토리보드(루틴은 실행 스위치만)",
    }


def is_theme(sb: dict) -> bool:
    return str(sb.get("topic") or "").strip().lower() == TOPIC


def meta(sb: dict) -> dict:
    d = dt.date.fromisoformat(str(sb.get("date"))[:10])
    th = next((x for x in THEMES if x["id"] == sb.get("theme")), None) or theme_for(d)
    return {"title": title(d, th)[:95], "description": description(d, th)}


def path_for(d: dt.date, root: str | None = None) -> str:
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "output", "news", f"{d.isoformat()}_{TOPIC}_storyboard.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="띠별 테마 순위 표 스토리보드")
    ap.add_argument("cmd", choices=["show", "make", "path"])
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    ap.add_argument("--out", help="make: 쓸 경로(기본: output/news/<날짜>_fortune_theme_storyboard.json)")
    ap.add_argument("--force", action="store_true", help="쉬는 날이어도 만든다(견본용)")
    a = ap.parse_args(argv)
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "path":
        print(os.path.relpath(path_for(d)))
        return 0
    if a.cmd == "make" and not (a.force or is_post_day(d)):
        print(f"{d}: 띠 테마 표 쉬는 날(이틀에 한 번, {ALT_FROM} 부터 짝수 번째 날) — 건너뜀")
        return 0
    sb = storyboard(d)
    if a.cmd == "show":
        print(json.dumps(sb, ensure_ascii=False, indent=1))
        return 0
    out = a.out or path_for(d)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)
    print(f"THEME={sb['theme']} · {sb['scenes'][0]['title']} · {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
