#!/usr/bin/env python3
"""소식 '10초 한 장'(news_card) 회귀 테스트 — 오프라인.

    python pipeline/test_news_card.py
"""
from __future__ import annotations
import copy
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("NEWS_CARD", None)
import news_card as N       # noqa: E402
import motion_short as M    # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# 10/3 루틴 대본(실제 내용) — 정치·미장·AI
POL = {"date": "2026-10-03", "topic": "politics", "hook_title": "78년 만에 검찰청이 문을 닫았습니다", "scenes": [
    {"type": "hook", "lines": ["오늘부터", "검찰청이", "없습니다"], "narration": "어제부터 우리나라에서 검찰청이라는 이름의 기관이 사라졌습니다."},
    {"type": "stat", "label": "검찰청 존속", "from": 0, "to": 78, "sub": "1948년 설립, <b>78년</b> 만에 폐지", "narration": "1948년 설립된 검찰청이 칠십팔 년 만에 폐지됐습니다."},
    {"type": "keypoint", "label": "달라진 역할", "points": ["수사 — <b>중수청</b>이 중대범죄 담당", "기소 — <b>공소청</b>이 공소 유지 전담"], "narration": "."},
    {"type": "stat", "label": "중수청 정원", "from": 0, "to": 2874, "sub": "개청 전 지원자 <b>1,962명</b>으로 집계", "narration": "."},
    {"type": "keypoint", "label": "여야 반응", "points": ["여당 — <b>\"형사사법체계 새 역사\"</b>", "야당 — <b>\"치안 지옥문 열려\"</b>"], "narration": "."},
    {"type": "statement", "text": "내 일상 치안, 달라질까?", "narration": "."}]}
US = {"date": "2026-10-03", "topic": "stock_us", "hook_title": "일자리 2.9만, 내 주식은 웃었다", "accent": "#2E9E5B", "scenes": [
    {"type": "hook", "lines": ["일자리 2.9만", "내 주식은", "웃었다"], "narration": "나쁜 소식이 나왔는데 뉴욕은 오히려 웃었습니다."},
    {"type": "trend", "label": "나스닥", "from": 0, "to": 1.2, "sub": "일자리는 <b>쇼크</b>, 증시는 환호", "narration": "."},
    {"type": "keypoint", "label": "왜 올랐나", "points": ["일자리 <b>2.9만</b>, 예상 크게 밑돌아", "금리 <b>인상 기대</b> 후퇴", "전날 10년물 금리 <b>2002년 이후</b> 최고"], "narration": "."},
    {"type": "statement", "text": "내 계좌엔 숨통, 일자리엔 경고등", "narration": "."},
    {"type": "keypoint", "label": "다음 주 지켜볼 것", "points": ["월요일 밤 <b>10시 30분</b> 뉴욕장 개장", "실업률 <b>4.2%</b>, 더 오르나"], "narration": "."}]}
AI = {"date": "2026-10-03", "topic": "ai_am", "hook_title": "하나은행 89명 정보 유출, AI 추정", "slot": "am", "scenes": [
    {"type": "hook", "lines": ["은행 정보가", "줄줄이 유출"], "narration": "여러 은행에서 고객 정보가 빠져나갔습니다."},
    {"type": "stat", "label": "하나은행 유출 고객", "to": 89, "suffix": "명", "sub": "KB국민은행 <b>119명</b>", "narration": "."},
    {"type": "statement", "text": "송금 시스템과는 별개", "narration": "."},
    {"type": "keypoint", "label": "오늘 해 볼 3가지", "points": ["은행 <b>공식 앱·번호</b>로 확인", "모르는 링크는 <b>누르지 않기</b>", "비밀번호 <b>바꿔 두기</b>"], "narration": "."}]}
NOON = {"date": "2026-10-03", "topic": "politics_noon", "hook_title": "846곳 감사, 25일 시작합니다", "scenes": [
    {"type": "stat", "label": "감사 대상 기관", "to": 846, "suffix": "곳", "sub": "<b>10월 6일</b>부터 25일간", "narration": "국정감사가 시작됩니다."},
    {"type": "keypoint", "label": "생활과 맞닿은 곳", "points": ["배달 수수료 — 내 <b>주문 가격</b>", "새벽배송 — 내 <b>택배 시간</b>"], "narration": "."},
    {"type": "statement", "text": "이번 국감, 무엇을 봐야 할까?", "narration": "."}]}

print("── 어느 대본에 쓰나")
ck("정치·주식·AI 는 한 장으로", all(N.use(x) for x in (POL, US, AI, NOON)))
ck("운세·띠 표·이름 표는 건드리지 않는다",
   not any(N.use({"topic": t, "scenes": [{"type": "hook"}]}) for t in ("fortune", "fortune_theme", "fortune_name", "drama")))
os.environ["NEWS_CARD"] = "0"
ck("NEWS_CARD=0 이면 예전 40초 형식", not N.use(POL))
os.environ.pop("NEWS_CARD")

print("── 정치: 찬반 한 장")
p = N.build_scene(POL)
ck("양쪽 말이 있으면 찬반(debate)", p["layout"] == "debate" and [x["h"] for x in p["sides"]] == ["여당", "야당"], p.get("sides"))
ck("따옴표·굵게는 벗긴다", p["sides"][0]["q"] == "형사사법체계 새 역사", p["sides"][0]["q"])
ck("마지막 물음표 문장이 부제", p["title2"] == "내 일상 치안, 달라질까?")
ck("⭕/❌ 한 표 + 핵심 숫자(단위는 같은 장면 글에서)", p["ox"] == ["맞다", "아니다"] and p["big"]["num"] == "78"
   and p["big"]["unit"] == "년", p["big"])
n = N.build_scene(NOON)
ck("'배달 수수료 — 내 주문 가격' 같은 설명 줄은 찬반으로 보지 않는다(요점 카드로)", n["layout"] == "bullets", n.get("sides"))

print("── 주식: 성적표")
u = N.build_scene(US)
ck("숫자 줄이 둘 이상이면 성적표(board)", u["layout"] == "board" and len(u["rows"]) >= 2, u.get("rows"))
ck("나스닥 오름 = up(빨강 ▲는 렌더가 도형으로)", u["rows"][0] == {"k": "나스닥", "s": "일자리는 쇼크, 증시는 환호", "v": "1.2%", "dir": "up"},
   u["rows"][0])
ck("숫자 아닌 굵은 말('인상 기대'·'2002년 이후')은 표에 싣지 않는다",
   not any(r["v"] in ("인상 기대", "2002년 이후") for r in u["rows"]), u["rows"])
ck("한 줄 정리 = 첫 단정 문장 · 투자 권유 아님", u["verdict"] == "내 계좌엔 숨통, 일자리엔 경고등" and "투자 권유" in u["foot"])
ck("미장/국장 이름", u["title"] == ["간밤 미국장 성적표"] and N.build_scene(dict(US, topic="stock"))["title"] == ["오늘 국장 성적표"])

print("── AI: 체크리스트")
a = N.build_scene(AI)
ck("'해 볼 3가지' 요점이면 체크리스트", a["layout"] == "check" and a["items"][0] == "은행 공식 앱·번호로 확인", a.get("items"))
ck("공유 부탁 · 숫자 89명", "공유" in a["share"] and a["big"]["num"] == "89" and a["big"]["unit"] == "명")

print("── 새 사실을 만들지 않는다")
for sb in (POL, US, AI, NOON):
    src = re.sub(r"<[^>]+>", "", str(sb))
    sc = N.build_scene(sb)
    nums = re.findall(r"\d[\d,.]*", " ".join(str(v) for v in (sc.get("big") or {}).values())
                      + " ".join(str(r.get("v")) for r in sc.get("rows") or []))
    bad = [x for x in nums if x.replace(",", "") not in src.replace(",", "")]
    if bad:
        ck(f"{sb['topic']}: 숫자는 대본에 있던 것만", False, bad)
ck("카드의 숫자는 전부 대본에 있던 것", True)

print("── 화면")
for sb in (POL, US, AI, NOON):
    sp = N.build_spec(sb)
    sc = dict(sp["scenes"][0], start=0, clip=11.0, _spk=0)
    html = M.build_html([sc], 11.0, acc=sp["accent"], bg=False)
    html = html if isinstance(html, str) else html[0]
    ck(f"{sb['topic']}: 한 장(news) · 11초 붙잡기 · 진행자 없음",
       'class="nwrap"' in html and sp["_min_total"] >= 10 and "CSS_NEWS" not in html and ".nwrap{" in html)
    ck(f"{sb['topic']}: 이모지·특수 화살표 글자 없음(리눅스 글꼴에서 네모)",
       not re.search(r"[←-⇿■-◿☀-➿\U0001F300-\U0001FAFF]", re.sub(r"<(style|script).*?</(style|script)>", "", html, flags=re.S)))
ck("진행자는 한 장 화면에 서지 않는다", '"news"' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1][:200])

print("── 파이프라인 연결")
import run_pipeline as RP  # noqa: E402
src = open(RP.__file__, encoding="utf-8").read()
ck("run_pipeline 이 한 장으로 바꾼다", "news_card.use(sb)" in src and "news_card.build_spec(sb)" in src)
import ai_news as A  # noqa: E402
ck("AI 길이 검사: 한 장(11초)은 통과 · 60초는 탈락", A.check_duration(11.2) is None and A.check_duration(60.2))
wf = {n: open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".github", "workflows", n), encoding="utf-8").read()
      for n in ("shorts.yml", "ai-news-run.yml")}
ck("워크플로가 레포 변수 NEWS_CARD 를 넘긴다(끄기 스위치)", all("NEWS_CARD: ${{ vars.NEWS_CARD" in t for t in wf.values()))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
