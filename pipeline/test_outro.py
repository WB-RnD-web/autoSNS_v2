#!/usr/bin/env python3
"""표 쇼츠 끝인사(outro.py · '오늘의 덕담 한마디' + '띠 남기시면 덕담 드려요') 회귀 테스트.

    python pipeline/test_outro.py
"""
from __future__ import annotations
import datetime as dt
import importlib
import json
import os
import re
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
os.environ["SHORTS_BG"] = "0"          # 통합 시험에서 배경 그림(Spark)을 부르지 않는다
import outro as O                # noqa: E402
import motion_short as M         # noqa: E402
import theme_card                # noqa: E402
import age_card                  # noqa: E402
import name_card                 # noqa: E402
import pulli_card                # noqa: E402
import blessing_card             # noqa: E402
import gunghap_card              # noqa: E402
import newyear_card              # noqa: E402
import newyear_series            # noqa: E402
import tier_card                 # noqa: E402
import fortune_card              # noqa: E402
import news_card                 # noqa: E402
import weekly_fortune            # noqa: E402
from theme_card import BANNED    # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


D = dt.date
AB0, AB1 = D(2026, 10, 26), D(2026, 11, 8)
AB = [AB0 + dt.timedelta(days=k) for k in range(14)]
ON = [d for d in AB if O.arm(d) == "on"]
OFF = [d for d in AB if O.arm(d) == "off"]

print("── A/B 날짜(10/26~11/8 · 그날 표 쇼츠 전부)")
ck("기간 = 10/26~11/8 · 7일 켬 / 7일 끔", O.OUTRO_AB == (AB0, AB1) and len(ON) == 7 and len(OFF) == 7, (ON, OFF))
ck("켜는 날 = 10/26·29 · 11/1·3·4·6·7", ON == [D(2026, 10, 26), D(2026, 10, 29), D(2026, 11, 1), D(2026, 11, 3), D(2026, 11, 4),
                                       D(2026, 11, 6), D(2026, 11, 7)], ON)
ck("두 쪽 모두 월~일이 한 번씩(요일 섞임이 같다)",
   sorted(d.weekday() for d in ON) == list(range(7)) and sorted(d.weekday() for d in OFF) == list(range(7)))
runs, cur = [], 1
for a, b in zip(AB, AB[1:]):
    cur = cur + 1 if O.arm(a) == O.arm(b) else 1
    runs.append(cur)
ck("같은 쪽은 많아야 이틀 연속(번갈아 가는 결)", max(runs) <= 2, runs)
th_on = sum(theme_card.is_post_day(d) for d in ON)
th_off = sum(theme_card.is_post_day(d) for d in OFF)
ck("낮 12시 띠 테마 표 ↔ 나이 표가 두 쪽에 4:3 으로 나뉜다(그냥 격일이면 7:0 — 형식 차이가 끝인사 효과로 보인다)",
   {th_on, th_off} == {3, 4} and all(theme_card.is_post_day(d) or theme_card.is_age_day(d) for d in AB), (th_on, th_off))
alt = [d for d in AB if (d - AB0).days % 2 == 0]
ck("…그냥 격일(짝수 날)이었다면 띠 테마 표가 한쪽에 몰린다(이 날짜표를 고른 이유)",
   sum(theme_card.is_post_day(d) for d in alt) in (0, 7))
ck("06:13 신년운세 시리즈(화·토)는 2:2", sum(newyear_series.is_slot_day(d) for d in ON) == 2
   and sum(newyear_series.is_slot_day(d) for d in OFF) == 2)
slots_on = sorted(str(name_card.slot_of_day(d)) for d in ON)
slots_off = sorted(str(name_card.slot_of_day(d)) for d in OFF)
ck("내 것 찾기 다섯 칸이 두 쪽에 고루(칸마다 한쪽에 몰리지 않음)",
   all(abs(slots_on.count(s) - slots_off.count(s)) <= 1 for s in set(slots_on + slots_off)), (slots_on, slots_off))
ck("기간 밖은 arm 없음(맥박이 A/B 로 세지 않는다)", O.arm(D(2026, 10, 25)) is None and O.arm(D(2026, 11, 9)) is None)
ck("10/25 이전은 끈다 · 기간 안은 날짜표대로", not O.is_on(D(2026, 10, 25)) and not O.is_on(D(2026, 10, 1))
   and all(O.is_on(d) for d in ON) and not any(O.is_on(d) for d in OFF))
after = [D(2026, 11, 9) + dt.timedelta(days=k) for k in range(400)]
ck("11/9 부터는 OUTRO_DEFAULT(True) — 판정 없이도 조용히 꺼지지 않는다", O.OUTRO_DEFAULT is True and all(O.is_on(d) for d in after))
O.OUTRO_DEFAULT = False
ck("판정이 끄면(OUTRO_DEFAULT = False) 11/9 부터 끄고 A/B 날짜는 그대로",
   not any(O.is_on(d) for d in after) and all(O.is_on(d) for d in ON) and not any(O.is_on(d) for d in OFF))
O.OUTRO_DEFAULT = True
_ab = O.OUTRO_AB
O.OUTRO_AB = None
ck("A/B 를 없애면(None) OUTRO_FROM 부터 매일 기본값", all(O.is_on(d) for d in AB) and not O.is_on(D(2026, 10, 25))
   and O.arm(AB0) is None)
O.OUTRO_AB = _ab

sb26 = {"date": "2026-10-26", "topic": "fortune_theme", "scenes": [{"type": "card"}]}
k = dt.timezone(dt.timedelta(hours=9))
ck("정하는 날 = 스토리보드 날짜(견본을 미리 돌려도 그 날짜)",
   O.day_for(sb26, dt.datetime(2026, 10, 25, 10, 0, tzinfo=k)) == AB0
   and O.day_for(sb26, dt.datetime(2026, 10, 26, 23, 50, tzinfo=k)) == AB0)
ck("…자정 넘겨 늦게 돈 실행은 그날(게시일) — 맥박이 게시일로 나눈다",
   O.day_for(sb26, dt.datetime(2026, 10, 27, 0, 30, tzinfo=k)) == D(2026, 10, 27)
   and O.for_storyboard(sb26, now=dt.datetime(2026, 10, 27, 0, 30, tzinfo=k)) is None
   and O.for_storyboard(sb26, now=dt.datetime(2026, 10, 26, 6, 0, tzinfo=k)) is not None)

ex = {e["id"]: e for e in json.load(open(os.path.join(ROOT, "tools", "pulse_experiments.json"), encoding="utf-8"))["experiments"]}
e = ex.get("outro-blessing", {})
ck("실험 달력: outro-blessing · 10/26 시작 · 11/9 판정 · pulse · arms=outro", e.get("start") == "2026-10-26"
   and e.get("judge") == "2026-11-09" and e.get("owner") == "pulse" and e.get("arms") == "outro" and e.get("ch") == "wb", e)
ck("실험 달력의 날짜표 = outro.ab_calendar()", e.get("calendar") == O.ab_calendar(), e.get("calendar"))
crit = e.get("criterion", "")
ck("판정 기준(한국어): 댓글/1천 회 첫 48시간 +30% · 평균 시청 비율 5%p · 끄는 법", all(w in crit for w in (
    "48시간", "1천 회", "30%", "5%p", "평균 시청 비율", "OUTRO_DEFAULT = False")), crit[:80])
fm = json.load(open(os.path.join(ROOT, "tools", "pulse_formats.json"), encoding="utf-8"))["channels"]["wb"]["rules"]
keys = {r["key"] for r in fm}
ck("실험 형식 = 맥박 형식 키(표 쇼츠 전부 — 매일·주간·신년·테마·나이·풀이·덕담·내 것 찾기·등급·궁합)",
   set(e.get("formats", [])) <= keys and {"daily", "theme", "age", "pulli", "name", "month", "year", "surname", "lunar",
                                          "newyear_slot", "weekly_short"} <= set(e.get("formats", [])), e.get("formats"))
ck("다른 실험 판정일은 그대로", ex["newyear-slot"]["judge"] == "2026-11-25" and ex["blessing"]["judge"] == "2026-10-25")

print("── 오늘의 덕담(날짜로 · 같은 날짜면 늘 같은 줄)")
span = [D(2026, 10, 1) + dt.timedelta(days=k) for k in range(460)]          # 2027년 끝까지
seq = [O.blessing(d) for d in span]
O._SEQ.clear()
back = [O.blessing(d) for d in reversed(span)][::-1]                        # 뒤에서부터 물어도 같다
O._SEQ.clear()
O2 = importlib.reload(O)
ck("결정적: 다시 불러도 · 거꾸로 물어도 같은 줄", seq == back == [O2.blessing(d) for d in span])
O = O2
rep = [(span[i], seq[i]) for i in range(1, len(seq)) if seq[i] == seq[i - 1]]
ck("어제와 같은 줄이 다음 날 나오지 않는다(15개월)", not rep, rep[:3])
near = [(span[i], seq[i]) for i in range(len(seq)) if seq[i] in seq[max(0, i - O.REPEAT_GAP):i]]
ck(f"앞선 {O.REPEAT_GAP}일 안에 나온 줄은 다시 안 나온다(2주 A/B 안에서 겹치지 않음)", not near, near[:3])
ck("A/B 14일 덕담이 전부 다르다", len({O.blessing(d) for d in AB}) == 14)
ck("절기 날은 그 절기 줄(입동 11/7 · 동지 12/22 · 입춘 2027-02-04)",
   O.blessing(D(2026, 11, 7)).startswith("입동") and O.blessing(D(2026, 12, 22)).startswith("동지")
   and O.blessing(D(2027, 2, 4)).startswith("입춘") and all(O.blessing(d) == x for d, (_, x) in O.JEOLGI.items()))
ck("절기 표: 2026 입동 11/7 · 소설 11/22 · 대설 12/7 · 동지 12/22 · 2027 입춘 2/4(newyear_series 12절과 같다)",
   all(D(2026, m, dd) in O.JEOLGI for m, dd in ((11, 7), (11, 22), (12, 7), (12, 22)))
   and all(D(2027, m, newyear_series.JEOLGI[m][0]) in O.JEOLGI and O.JEOLGI[D(2027, m, newyear_series.JEOLGI[m][0])][0]
           == newyear_series.JEOLGI[m][1] for m in range(1, 13)))
season_bad = [(d, x) for d, x in zip(span, seq) if d not in O.JEOLGI
              and any(x in v and x not in O.SEASON[O.SEASON_OF[d.month]] and x not in O.ALWAYS
                      and x not in sum(O.WEEKDAY_LINES.values(), []) for v in O.SEASON.values())]
ck("계절 줄은 그 계절에만(여름에 '장갑'·겨울에 '수박' 없음)", not season_bad, season_bad[:3])
wd_bad = [(d, x) for d, x in zip(span, seq) for w, v in O.WEEKDAY_LINES.items() if x in v and d.weekday() != w
          and x not in O.ALWAYS and not any(x in s for s in O.SEASON.values())]
ck("요일 줄은 그 요일에만", not wd_bad, wd_bad[:3])
mon = [x for d, x in zip(span, seq) if d.weekday() == 0 and d not in O.JEOLGI]
ck("월요일은 대부분 한 주 시작 인사", sum(x in O.WEEKDAY_LINES[0] for x in mon) >= len(mon) * 0.6,
   f"{sum(x in O.WEEKDAY_LINES[0] for x in mon)}/{len(mon)}")
tue = [x for d, x in zip(span, seq) if d.weekday() == 1 and d not in O.JEOLGI]
ck("화요일은 대부분 계절 줄", sum(any(x in v for v in O.SEASON.values()) for x in tue) >= len(tue) * 0.6)

print("── 덕담 글(화면 큰 글자 = 목소리)")
lines = O.all_lines()
long_ = [(x, O.hangul(x), len(x)) for x in lines if O.hangul(x) > O.LINE_MAX_HANGUL or len(x) > O.LINE_MAX_CHARS]
ck(f"덕담은 한글 {O.LINE_MAX_HANGUL}자 · 화면 {O.LINE_MAX_CHARS}자 이내(목소리 2.5초에 초대까지 들어가게)", not long_, long_)
ck("화면 둘째 줄 '띠 남기시면 덕담 드려요' 14자 이내 · 이모지 없음(글꼴에 없다)",
   O.INVITE_SCREEN == "띠 남기시면 덕담 드려요" and len(O.INVITE_SCREEN) <= 14 and all(ord(c) < 0x2000 or "가" <= c <= "힣"
                                                                              for c in O.INVITE_SCREEN))
ck("목소리 = 덕담 + 초대 두 문장", O.build(AB0)["vo"] == [O.blessing(AB0) + ".", "띠 남기시면 덕담 드려요."])
ck("목소리는 쉼표 없이(절기 이름 뒤 쉼이 길다) · 화면엔 쉼표 그대로", O.build(D(2026, 11, 7))["vo"][0] == "입동 든든히 드세요."
   and O.build(D(2026, 11, 7))["line1"] == "입동, 든든히 드세요")
ck("한글·빈칸·쉼표만(영어·숫자·이모지·게임 말투 없음)", all(re.fullmatch(r"[가-힣 ,]+", x) for x in lines + [O.INVITE_SCREEN]),
   [x for x in lines if not re.fullmatch(r"[가-힣 ,]+", x)])
texts = lines + [O.INVITE_SCREEN, O.INVITE_VO, O.LABEL, O.DESC_LINE]
hit = lambda words, xs: sorted({w for w in words for t in xs if w in t})  # noqa: E731
ck("theme_card 금지어 없음(의료·투자·겁주기·자극)", not hit(BANNED, texts), hit(BANNED, texts))
wf = [w for v in weekly_fortune.BAN.values() for w in v]
ck("주간 운세 금지어 없음(자극·겁주기·의료·투자·장담·무속)", not hit(wf, texts), hit(wf, texts))
RELIGION = ("부처", "하나님", "하느님", "아멘", "나무아미타불", "기도", "축복", "주님", "예수", "성경", "불경", "염불", "교회",
            "성당", "절에", "찬송", "할렐루야", "관세음", "보살", "은총", "천국", "극락", "조상님", "신령", "고사")
ck("종교 말 없음", not hit(RELIGION, texts), hit(RELIGION, texts))
SCARE = ("조심", "나쁜", "불운", "액운", "손해", "다툼", "싸움", "위험", "큰일", "재수", "최악", "망해", "망한", "망할", "망쳐", "주의",
         "경고", "아프", "쓰러")                  # '망종'(절기)은 괜찮다
ck("겁주는 말 없음", not hit(SCARE, texts), hit(SCARE, texts))
HEALTH = ("건강해", "튼튼해", "낫는", "나아요", "나을", "병", "오래 살", "장수", "회복", "완쾌", "면역", "혈압", "관절", "다이어트",
          "약", "효과", "좋아져", "예방")
ck("건강 장담·의료 조언 없음(따뜻하게 입기·물 한 잔·천천히 걷기 같은 생활 말까지만)", not hit(HEALTH, texts), hit(HEALTH, texts))
MONEY = ("돈", "재물", "부자", "횡재", "당첨", "로또", "복권", "대박", "목돈", "용돈", "만원", "억")
ck("돈·로또 약속 없음", not hit(MONEY, texts), hit(MONEY, texts))
BAIT = ("복 받", "복이 와", "복이 들어", "행운이 와", "소원 이뤄", "소원이 이뤄", "구독", "좋아요 눌러", "좋아요와", "알림", "공유",
        "꼭 남기")
ck("'댓글 달면 복 받는다' 같은 미끼 없음 — 약속은 '덕담 드려요'뿐(사장님이 실제로 답글을 단다)",
   not hit(BAIT, texts) and "덕담 드려요" in O.INVITE_SCREEN and "덕담 드려요" in O.DESC_LINE, hit(BAIT, texts))
GAME = ("레벨", "득템", "버프", "만렙", "최강", "꿀팁", "갓", "킹", "ㅋ", "ㅎㅎ", "인생템", "레전드")
ck("게임·인터넷 말투 없음", not hit(GAME, texts), hit(GAME, texts))

print("── 설명란 한 줄")
desc = theme_card.meta(theme_card.storyboard(AB0))["description"]
nd = O.with_line(desc)
ck("첫 문단 바로 아래에 '댓글에 띠를 남겨 주시면 왕별이가 덕담 드려요 🙏'",
   nd.split("\n\n")[1] == "댓글에 띠를 남겨 주시면 왕별이가 덕담 드려요 🙏" and nd.split("\n\n")[0] == desc.split("\n\n")[0])
ck("나머지 글은 그대로(그 한 줄만 빼면 원래 설명)", nd.replace("\n\n" + O.DESC_LINE, "", 1) == desc)
ck("두 번 넣지 않는다 · 문단이 하나뿐이어도 · 빈 설명도", O.with_line(nd) == nd
   and O.with_line("한 줄") == "한 줄\n\n" + O.DESC_LINE and O.with_line("") == O.DESC_LINE)
ck("해시태그 문단은 맨 끝 그대로", nd.rstrip().split("\n")[-1] == desc.rstrip().split("\n")[-1])

print("── 어느 쇼츠에 붙나(왕별이 표 쇼츠 전부 · 그 밖은 안 붙는다)")
nyd = next(d for d in (D(2026, 10, 27) + dt.timedelta(days=k) for k in range(30)) if newyear_series.is_slot_day(d))
routine = {"date": AB0.isoformat(), "topic": "fortune", "privacy": "public", "hook_title": "오늘 1위 쥐띠",
           "scenes": [{"type": "hook", "lines": ["1위는 쥐띠"], "narration": "오늘 1위는 쥐띠"}],
           "platforms": {"youtube": {"title": "x #shorts", "description": "x"}}, "notes": "MODE=daily"}
tables = {
    "매일 운세 표(fortune_card)": (routine, fortune_card.build_spec(routine)),
    "띠 테마 표": (theme_card.storyboard(AB0), None),
    "나이 표(age_card)": (age_card.storyboard(AB0, theme_card.TOPIC), None),
    "내 것 찾기(grid)": (name_card.storyboard(AB0, "am"), None),
    "풀이형 표(card + 풀이)": (pulli_card.storyboard(AB0), None),
    "덕담표(bless)": (blessing_card.storyboard(AB0), None),
    "띠 궁합표": (gunghap_card.storyboard(AB0), None),
    "신년 표(newyear_card)": (newyear_card.storyboard(AB0), None),
    "운세 등급표": (tier_card.storyboard(AB0), None),
}
_nsb = dict(routine, date=nyd.isoformat())
tables["2027 신년 시리즈(06:13)"] = (_nsb, newyear_series.build_spec(_nsb))
for name, (sb, spec) in tables.items():
    sb = dict(sb, date=AB0.isoformat()) if spec is None else sb
    on = O.for_storyboard(sb, spec, now=dt.datetime(2026, 10, 1, tzinfo=k))
    off = O.for_storyboard(dict(sb, date="2026-10-27"), spec, now=dt.datetime(2026, 10, 1, tzinfo=k))
    if sb.get("date") != AB0.isoformat():           # 신년 시리즈는 그날(화·토)만 — 켜는 날에 맞춰 본다
        on = O.for_storyboard(sb, spec, now=dt.datetime(2026, 10, 1, tzinfo=k)) if O.is_on(O.sb_date(sb)) else "skip"
        off = None
    ck(f"{name}: 켜는 날 붙고 끄는 날 안 붙는다", O.is_table(sb, spec) and on and off is None, (O.is_table(sb, spec), on, off))
not_tables = {
    "옛 운세 형식(hook·stat)": routine,
    "정치 한 장(news)": {"date": AB0.isoformat(), "topic": "politics", "scenes": [{"type": "news"}]},
    "AI 소식": {"date": AB0.isoformat(), "topic": "ai", "scenes": [{"type": "card"}]},
}
for name, sb in not_tables.items():
    ck(f"{name}: 안 붙는다", O.for_storyboard(sb, now=dt.datetime(2026, 10, 1, tzinfo=k)) is None)

print("── 렌더러(motion_short)")
tempo, vo, dur = M.outro_timing([1.05, 1.22])                       # Supertonic F1 실측(10/25) 중간값 — 덕담 + 초대
ck("보통 덕담 + 초대(실측 1.05 + 1.22초) → 2.5초 안 · 빠르기 거의 그대로(1.02배 이하)", dur <= M.OUTRO_MAX and tempo <= 1.02,
   (tempo, vo, dur))
tempo, vo, dur = M.outro_timing([1.22, 1.42])                       # 실측 최악(가장 긴 덕담 + 가장 길게 나온 초대)
ck("가장 길게 나와도(1.22 + 1.42초) 2.5초 안 · 빠르기 1.18배 이하", dur <= M.OUTRO_MAX and tempo <= M.OUTRO_TEMPO_MAX <= 1.18,
   (tempo, vo, dur))
tempo, vo, dur = M.outro_timing([0.5, 1.0])
ck("짧으면 빠르기 그대로 · 최소 2.0초", tempo == 1.0 and dur == M.OUTRO_MIN, (tempo, vo, dur))
tempo, vo, dur = M.outro_timing([2.4, 1.37])
ck("너무 길면 1.18배까지만 빠르게 하고 그만큼 길어진다(목소리를 자르지 않는다)",
   tempo == M.OUTRO_TEMPO_MAX and dur > M.OUTRO_MAX, (tempo, vo, dur))
sizes = {x: M.outro_split(x) for x in lines}
small = {x: v for x, v in sizes.items() if v[1] < 100 or len(v[0]) > 2}
ck("큰 글자: 덕담 전부 100px 이상 · 두 줄 이내(어르신 눈높이 — 표 제목 96px 보다 크게)", not small, small)
splits = {x: " / ".join(M.outro_split(x)[0]) for x in ("입동, 든든히 드세요", "따끈한 차 드세요", "꽃구경 가 보세요",
                                                    "안부 전화 해 봐요", "하늘 한번 보세요", "한 주 힘내세요")}
ck("두 줄로 나눌 때 뜻이 갈리지 않는 곳에서(쉼표 뒤 · 끝 말 앞 · '가 보세요'는 한 덩어리) · 짧으면 한 줄",
   splits == {"입동, 든든히 드세요": "입동, / 든든히 드세요", "따끈한 차 드세요": "따끈한 차 / 드세요",
              "꽃구경 가 보세요": "꽃구경 / 가 보세요", "안부 전화 해 봐요": "안부 전화 / 해 봐요",
              "하늘 한번 보세요": "하늘 한번 / 보세요", "한 주 힘내세요": "한 주 힘내세요"}, splits)
ck("둘째 줄 72px", int(min(M.OUTRO_F2, M.OUTRO_BOX / M._outro_em(O.INVITE_SCREEN))) >= 70)
sc = dict(theme_card.storyboard(AB0)["scenes"][0], start=0.0, clip=9.4)
ob = dict(O.build(AB0), start=7.0, dur=2.4, t2=1.1, tempo=1.0)
html = M.build_html([sc], 9.4, "#C9A227", bg=True, outro=ob)
ck("HTML: 끝인사 판 · 알약 '오늘의 덕담 한마디' · 덕담 · 초대 · 7.0초에 나타난다",
   'id="outro"' in html and ">오늘의 덕담 한마디<" in html and ">띠 남기시면 덕담 드려요<" in html
   and all(f"<span>{x}</span>" in html for x in M.outro_split(O.blessing(AB0))[0])
   and 'tl.fromTo("#outro",{opacity:0},{opacity:1,duration:0.22,ease:"power1.out"},7.00);' in html)
ck("끝인사 없으면 HTML 에 흔적 없음(기존 화면 그대로)", 'id="outro"' not in M.build_html([sc], 9.4, "#C9A227", bg=True)
   and "#outro" not in M.build_html([sc], 9.4, "#C9A227", bg=True))
tops = []
for x in lines:
    h = M.outro_html(dict(ob, line1=x))
    top = int(re.search(r'class="opanel" style="top:(\d+)px"', h).group(1))
    lns, f1 = M.outro_split(x)
    tops.append((x, top, top + 52 + 58 + 70 + 34 + len(lns) * f1 * 1.14 + 38 + 72 * 1.15))
bad = [t for t in tops if t[1] < 500 or t[2] > 1300]
ck("판 자리: x 60~960(오른쪽 버튼 열 비움) · y 500~1300(위 검색 줄·아래 제목 자리 1460~ 비움)",
   not bad and "#outro .opanel{position:absolute;left:60px;width:900px;" in M.CSS_OUTRO, bad[:3])
bh = M.build_html([dict(blessing_card.scene(AB0), start=0.0, clip=10.0)], 12.4, blessing_card.ACCENT, outro=ob)
ck("덕담표(밝은 꽃 바탕) 뒤엔 밝은 판", 'id="outro" class="light"' in bh and 'id="outro" class="dark"' in html)
src = open(os.path.join(HERE, "motion_short.py"), encoding="utf-8").read()
bm = src[src.index("def build_motion("):]
ck("build_motion: 최소 길이로 머문 뒤에 끝인사 · 표(마지막 장면)는 끝인사 밑에 그대로 · 목소리 실패면 끝인사 없이",
   bm.index('if total < min_total:') < bm.index('outro_audio(spec["_outro"], workdir)')
   and 'scenes[-1]["clip"] = round(total - scenes[-1]["start"], 2)' in bm and 'spec["_outro_applied"] = outro' in bm
   and "끝인사 없이" in bm and 'ms = int((outro["start"] + OUTRO_LEAD) * 1000)' in bm)

print("── 파이프라인 연결(run_pipeline.process — 렌더·업로드는 가짜로)")
import run_pipeline as R  # noqa: E402
got = {}


def fake_build(spec, out_mp4, wd, quality="standard"):
    got["spec"] = spec
    spec["_outro_applied"] = dict(spec["_outro"], dur=2.4) if spec.get("_outro") else None
    return out_mp4


def fake_upload(video, meta, retries=2):
    got["meta"] = meta
    return "VIDEO_ID"


R.motion_short.build_motion = fake_build
R.upload_with_retry = fake_upload
R.has_credentials = lambda: True
R.add_weekly_link = lambda meta, topic: None
R.add_playlist = lambda *a, **kw: None
# ★시계를 대본 날 아침으로 고정한다 — day_for 는 max(대본 날, 오늘)이라, 실제 시계로 돌리면
#   10/27 부터 10/26 대본도 '오늘(끄는 날)'로 잡혀 테스트가 깨졌다(전체 테스트를 거치는 채우기·맥박 PR 이 막힘).
_for_sb = O.for_storyboard
O.for_storyboard = lambda sb, spec=None, now=None: _for_sb(
    sb, spec, now or dt.datetime.fromisoformat(sb["date"] + "T05:00:00").replace(tzinfo=k))
with tempfile.TemporaryDirectory() as tmp:
    led_path = os.path.join(tmp, "ledger.json")
    for d in (AB0, D(2026, 10, 27)):
        sb = theme_card.storyboard(d)
        p = os.path.join(tmp, f"{d}_{sb['topic']}_storyboard.json")
        json.dump(sb, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        args = SimpleNamespace(include_paused=False, spec=None, quality="draft", no_upload=False, dry_run_upload=False,
                               force_private=True, no_social=True, ai_lenient=False, ledger_path=led_path)
        got.clear()
        led = {}
        res = R.process(p, args, led)
        if d == AB0:
            ck("켜는 날(10/26 띠 테마 표): 끝인사 스펙 → 렌더 · 설명란에 초대 한 줄 · ledger outro=True",
               got["spec"].get("_outro", {}).get("line1") == O.blessing(d) and res.get("outro") is True
               and O.DESC_LINE in got["meta"]["description"] and led[f"{d}_{sb['topic']}"].get("outro") is True,
               (res, got.get("meta", {}).get("description", "")[:80]))
            ck("…설명란의 나머지는 theme_card 설명 그대로", O.with_line(theme_card.meta(sb)["description"])
               in got["meta"]["description"])
        else:
            ck("끄는 날(10/27 나이 표): 끝인사 없음 · 설명란 손대지 않음 · ledger outro=False",
               "_outro" not in got["spec"] and res.get("outro") is False and O.DESC_LINE not in got["meta"]["description"]
               and led[f"{d}_{sb['topic']}"].get("outro") is False, res)
O.for_storyboard = _for_sb
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
proc = rp[rp.index("def process("):]
ck("run_pipeline: 장면을 정한 뒤 · 렌더 전에 끝인사 · 설명란 한 줄은 표별 제목/설명을 다 정한 뒤",
   proc.index("news_card.build_spec(sb)") < proc.index("outro.for_storyboard(sb, spec)") < proc.index("motion_short.build_motion(")
   and proc.index("name_card.meta(sb)") < proc.index("outro.with_line(meta[\"description\"])") < proc.index("add_weekly_link(meta"))

print("── 채널 맥박(게시일로 끝인사 있는 날 / 없는 날)")
import pulse as PU      # noqa: E402
import trend_radar as TR  # noqa: E402
UTC = dt.timezone.utc
spec = PU.load_formats()["wb"]


def rec(title, d, views, cmts):
    pub = dt.datetime(d.year, d.month, d.day, 6, 14, tzinfo=k).astimezone(UTC)
    vs, cs = {}, {}
    for n in range(0, 6):
        t = dt.datetime(d.year, d.month, d.day, 0, tzinfo=UTC) + dt.timedelta(days=n + 1)
        age = (t - pub).total_seconds() / 86400
        vs[t.strftime("%Y-%m-%dT%H")] = int(views * age)
        cs[t.strftime("%Y-%m-%dT%H")] = int(cmts * age)
    last = max(vs)
    return {"ch": spec["id"], "niche": "own_wb", "title": title, "pub": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "dur": 9,
            "views": vs, "cmts": cs, "comments": cs[last], "likes": 0}


reg = {}
for d in AB:
    on = O.arm(d) == "on"
    reg[f"d{d}"] = rec(f"오늘 띠별 운세 1위~12위 | {d.month}월 {d.day}일 · 45~96년생 전부 #shorts", d, 10000, 40 if on else 20)
    reg[f"x{d}"] = rec(f"국회 소식 {d}", d, 10000, 500)               # 표 쇼츠가 아닌 영상은 세지 않는다
reg["late"] = rec("오늘 띠별 운세 1위~12위 | 11월 9일", D(2026, 11, 9), 10000, 99)   # 기간 밖
at = dt.datetime(2026, 11, 15, 0, tzinfo=UTC)
c = PU.analyze_channel("wb", spec, reg, {}, at)
rows, _ = PU.exp_status(D(2026, 11, 9), {"wb": c})
arms = next(r for r in rows if r["id"] == "outro-blessing").get("arms", {})
ck("pulse.json experiments[].arms: 표 쇼츠만 · 기간 안만 7편 / 7편", arms.get("on", {}).get("n") == 7
   and arms.get("off", {}).get("n") == 7 and arms["on"]["fmts"] == {"daily": 7}, arms)
ck("첫 48시간 댓글 ÷ 조회 1천 회 ≈ 4.0 vs 2.0 · 비율 ≈ 2.0", abs(arms["on"]["c1k48"] - 4.0) < 0.1
   and abs(arms["off"]["c1k48"] - 2.0) < 0.1 and abs(arms.get("c1k48_ratio", 0) - 2.0) < 0.05 and arms["on"]["n48"] == 7, arms)
ck("첫 48시간 조회 중앙값 · 지금까지 댓글/1천 회도 낸다", arms["on"]["med48"] == arms["off"]["med48"] and arms["on"]["c1k_now"])
ck("다른 실험 줄에는 arms 가 없다", all("arms" not in r for r in rows if r["id"] != "outro-blessing"))
ck("arms 이름은 정해 둔 것만(실험 달력이 아무 모듈이나 못 부른다)", PU.arm_split({"arms": "run_pipeline", "formats": ["daily"]}, c) == {})
nocm = {v: dict(r, cmts={}) for v, r in reg.items()}
a2 = PU.arm_split(next(x for x in json.load(open(PU.EXPERIMENTS, encoding="utf-8"))["experiments"] if x["id"] == "outro-blessing"),
                  PU.analyze_channel("wb", spec, nocm, {}, at))
ck("댓글 스냅숏이 없던 편(레이더 변경 전)은 c1k48 없음 · c1k_now 로", a2["on"]["c1k48"] is None and a2["on"]["c1k_now"] > 0, a2)


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class _YT:
    def channels(self):
        return SimpleNamespace(list=lambda **kw: _Req({"items": [{"id": i, "contentDetails": {"relatedPlaylists": {"uploads": "UU" + i}}}
                                                                  for i in kw["id"].split(",")]}))

    def playlistItems(self):
        return SimpleNamespace(list=lambda **kw: _Req({"items": [{"contentDetails": {"videoId": "v1"}}]}))

    def videos(self):
        return SimpleNamespace(list=lambda **kw: _Req({"items": [{"id": "v1", "snippet": {
            "title": "t", "publishedAt": "2026-10-26T00:00:00Z", "channelId": "UCw"},
            "statistics": {"viewCount": "100", "likeCount": "3", "commentCount": "7"}, "contentDetails": {"duration": "PT9S"}}]}))


treg = {}
try:
    TR.collect(treg, {"own_wb": {"own": True, "channels": {"UCw": "W"}}}, _YT(), dt.datetime(2026, 10, 27, 0, tzinfo=UTC))
    ck("트렌드 레이더: 댓글 수도 스냅숏(cmts)으로 남긴다", treg.get("v1", {}).get("cmts") == {"2026-10-27T00": 7}, treg.get("v1"))
except Exception as ex_:  # noqa: BLE001
    trs = open(os.path.join(ROOT, "tools", "trend_radar.py"), encoding="utf-8").read()
    ck("트렌드 레이더: 댓글 수도 스냅숏(cmts)으로 남긴다(소스)", 'r.setdefault("cmts", {})[key] = d["comments"]' in trs, ex_)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
