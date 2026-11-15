#!/usr/bin/env python3
"""'말년 지혜 표'(wisdom_card · 2026-11-17~11-30 2주 시험 · 17:40) 회귀 테스트.

    python pipeline/test_wisdom_card.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import motion_short as M      # noqa: E402
import wisdom_card as W       # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


D = dt.date
DAYS = [D(2026, 11, 17) + dt.timedelta(days=k) for k in range(14)]

print("── 편성(날짜 그대로 · 2주 14편)")
dates = [W._d(e["date"]) for e in W.EPISODES]
ck("14편 · 11/17~11/30 하루 한 편 · 날짜 겹침 없음", dates == DAYS, dates)
ck("first_day·last_day·JUDGE(11/30 뒤 · 12/02)", W.first_day() == DAYS[0] and W.last_day() == DAYS[-1] and W.JUDGE == D(2026, 12, 2))
ck("그 밖의 날은 편성일이 아니다(11/16 · 12/01)", not W.is_post_day(D(2026, 11, 16)) and not W.is_post_day(D(2026, 12, 1)))
ck("id 겹침 없음", len({e["id"] for e in W.EPISODES}) == len(W.EPISODES))
ck("수능 응원 편은 수능(11/19) 전날 17:40 — 시험 끝난 뒤에 나가지 않는다",
   next(e for e in W.EPISODES if e["id"] == "exam_grandchild")["date"] == "2026-11-18")

print("── 글(편마다 다르게 · 금지어)")
items = [it for e in W.EPISODES for it in e["items"]]
ck("편마다 다섯 줄 · 줄마다 (큰 글자, 작은 글자, 설명란 한 문장)",
   all(len(e["items"]) == 5 and all(len(it) == 3 and all(str(x).strip() for x in it) for it in e["items"]) for e in W.EPISODES))
bigs = [it[0] for it in items]
smalls = [it[1] for it in items]
ck("큰 글자 줄·작은 글자 줄이 시리즈에서 두 번 나오지 않는다(재탕 X)", len(set(bigs)) == len(bigs) and len(set(smalls)) == len(smalls),
   [b for b in bigs if bigs.count(b) > 1] + [s for s in smalls if smalls.count(s) > 1])
whys = [it[2] for it in items]
ck("설명란 한 문장도 겹치지 않고 마침표로 끝난다", len(set(whys)) == len(whys) and all(w.endswith(("요.", "다.", "죠.")) for w in whys),
   [w for w in whys if not w.endswith(("요.", "다.", "죠."))])
every = " ".join([W.title(e) + W.description(e) + W.narration(e) + e["l1"] + e["l2"] + " ".join(x for it in e["items"] for x in it)
                  for e in W.EPISODES])
bad = [w for w in BANNED + W.NO_WORDS if w in every]
ck("금지어 없음(건강 장담·병 이름·돈 액수·투자·종교·겁주기·게임 말투·명리 용어)", not bad, bad)
ck("돈 액수(숫자+원·만 원) 없음", not re.search(r"\d+\s*(만\s*)?원", every))
ck("말투: 큰 글자·작은 글자에 반말 명령('~해라' 단독)·느낌표 남발 없음", all(s.count("!") == 0 for s in smalls + bigs))
ck("편마다 태그 셋 · 전부 # 로 시작 · 빈칸 없음", all(len(e["tags"]) == 3 and all(t.startswith("#") and " " not in t for t in e["tags"])
                                                 for e in W.EPISODES))
ck("배경 그림: 사람·글자 없음 꼬리 · 사진 아님", all(W.storyboard(W._d(e["date"]))["thumbnail_hook"].endswith(", no text, no letters, no signage, no logos")
                                         and "no people" in e["hook"] and "photo" not in e["hook"] for e in W.EPISODES))

print("── 스토리보드(CI 에서 LLM 안 씀)")
sbs = {d: W.storyboard(d) for d in DAYS}
sb = sbs[DAYS[0]]
ck("토픽 wisdom · 장면 하나(wisdom) · 다섯 줄 · 10초 이상 머문다 · 공개",
   sb["topic"] == "wisdom" and [s["type"] for s in sb["scenes"]] == ["wisdom"] and len(sb["scenes"][0]["items"]) == 5
   and sb["_min_total"] >= 10 and sb["privacy"] == "public")
ck("제목: '| 말년 지혜' 가 늘 들어간다 · 95자 안 · 날짜 없음(오래 검색되게) · 편마다 다르다",
   all("| 말년 지혜" in W.title(e) and len(W.title(e) + " #shorts") <= 100 and not re.search(r"\d+월 \d+일", W.title(e))
       for e in W.EPISODES) and len({W.title(e) for e in W.EPISODES}) == 14, [W.title(e) for e in W.EPISODES])
ck("설명란: 다섯 줄 전부 '번호. 큰 글자 — 왜' · 댓글 부탁 · 고지 · 공통 태그",
   all(all(f"{k}. " in W.description(e) and it[2] in W.description(e) for k, it in enumerate(e["items"], 1))
       and "댓글로 번호" in W.description(e) and "집집마다" in W.description(e) and "#말년지혜" in W.description(e)
       for e in W.EPISODES))
ck("말(내레이션): 제목 + '다섯 가지예요' + 댓글 부탁 · 짧다(말이 길면 첫 화면에서 넘긴다)",
   all(W.narration(e).startswith(W.spoken(e)) and "다섯 가지예요" in W.narration(e) and len(W.narration(e)) <= 80 for e in W.EPISODES),
   [len(W.narration(e)) for e in W.EPISODES])
dont = [e for e in W.EPISODES if e["tone"] == "dont"]
ck("'아끼면 좋은 말'·'새는 습관' 편은 번호 색이 다르다(tone dont → 붉은 흙빛)",
   {e["id"] for e in dont} == {"money_leak", "children_dont"} and all(sbs[W._d(e["date"])]["accent"] == W.DONT for e in dont)
   and all(sbs[W._d(e["date"])]["accent"] == W.ACCENT for e in W.EPISODES if e["tone"] == "do"))
m = W.meta(sb)
ck("meta: 제목·설명·태그(뉴스 기본 태그 아님)", m["title"] == W.title(W.EPISODES[0]) and m["description"] == W.description(W.EPISODES[0])
   and "뉴스" not in m["tags"] and "말년지혜" in m["tags"])

print("── 화면(wisdom)")
ok, info = True, []
for d in DAYS:
    sc = dict(sbs[d]["scenes"][0], start=0.0, clip=W.MIN_TOTAL)
    lay = M.wisdom_layout(sc["items"], sc["title"], sc["title2"])
    html = M.build_html([sc], W.MIN_TOTAL, sbs[d]["accent"], bg=True)
    boxes = [tuple(map(float, x)) for x in re.findall(
        r'class="witem"[^>]*left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px', html)]
    right = max(x + w for x, _, w, _ in boxes)
    bottom = max(y + h for _, y, _, h in boxes)
    fits = all(lay["fb"] * M._wis_em(it["big"]) <= lay["room"] and lay["fs"] * M._wis_em(it["small"]) <= lay["room"] for it in sc["items"])
    tfit = lay["f1"] * M._wis_em(sc["title"]) <= M.WIS_W - 52 and lay["f2"] * M._wis_em(sc["title2"]) <= M.WIS_W - 52
    title_bottom = M.WIS_TOP - 30          # 제목 칸(176 + 안쪽 여백 + 두 줄)이 첫 칸 위에서 끝난다
    tb = 176 + 20 + 24 + lay["f1"] * 1.12 + lay["f2"] * 1.1
    ok &= (len(boxes) == 5 and right <= 960 and bottom <= 1420 and fits and tfit and lay["fb"] >= 56 and lay["fs"] >= 32
           and lay["f2"] >= 64 and tb <= M.WIS_TOP - 8)
    info.append((d.isoformat(), right, bottom, lay["fb"], lay["fs"], lay["f1"], lay["f2"], round(tb)))
ck("다섯 칸이 오른쪽 버튼 열(x 960)·아래 쇼츠 제목 자리(y 1420) 안 · 글자가 칸 안 · 큰 글자 56px 이상 · 제목 칸이 첫 칸 위(14편)", ok, info)
sc = dict(sb["scenes"][0], start=0.0, clip=W.MIN_TOTAL)
html = M.build_html([sc], W.MIN_TOTAL, sb["accent"], bg=False)
ck("제목 두 줄 · 번호 1~5 · 한지 바탕 · 발밑 고지 · 순위·점수·띠 없음",
   'class="l1"' in html and 'class="l2"' in html and all(f">{k}</div>" in html for k in range(1, 6)) and 'class="wpaper"' in html
   and W.FOOT in html and 'class="rk"' not in html and "띠</div>" not in html)
ck("배경 그림이 깔리면 어두운 막 대신 밝은 막", "#root #scrim{" in M.CSS_WISDOM and "#scrim ~ .scene .wpaper{" in M.CSS_WISDOM)
js = M.scene_js(0, sc, W.ACCENT)
ck("0초부터 다 보인다(등장 애니메이션 없음) · 번호가 차례로 톡", "tl.from(" not in js and all(f"-c{k}" in js for k in range(5)))
ck("진행자는 말년 지혜 표에 서지 않는다", '"wisdom"' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1].splitlines()[0])
import cover_short as C  # noqa: E402
st = C._fields(sb)[2]
ck("배경 그림체: 한지 수묵(치비 띠 동물 아님)", st == "hanji" and C._style_prompt(st) == C.CARD_STYLE_PROMPT["hanji"]
   and "chibi" not in C._style_prompt(st))

print("── 파이프라인 연결")
import fortune_card as FC   # noqa: E402
import ledger as L          # noqa: E402
import outro                # noqa: E402
import run_pipeline as R    # noqa: E402
import tier_card            # noqa: E402
import newyear_series       # noqa: E402
ck("운세 표·등급표 A/B·신년 시리즈·끝인사가 이 편을 건드리지 않는다(운세 토픽이 아니다)",
   not FC.use_card(sb) and not tier_card.use_ab(sb) and not newyear_series.use_slot(sb) and not outro.is_table(sb))
ck("ledger 키 = <날짜>_wisdom(하루 한 편)", L.key_for(sb) == "2026-11-17_wisdom", L.key_for(sb))
ck("재생목록 '말년 지혜' · 카테고리 22(인물·블로그) · 그림 배경이라 AI 표시 대상 아님 · 일시정지 아님",
   R.playlist_for("wisdom") == (R.WISDOM_PLAYLIST, R.WISDOM_PLAYLIST_DESC) and R.category_for("wisdom") == "22"
   and R.synthetic_label(sb, {"_bg": "x.png"}) is False and not R.is_paused(sb))
ck("운세 재생목록·카테고리는 그대로(fortune → 24 · 매일 운세 목록)", R.category_for("fortune") == "24"
   and R.playlist_for("fortune")[0] == R.FORTUNE_PLAYLIST)
src = open(R.__file__, encoding="utf-8").read()
ck("업로드 메타: wisdom_card.meta 로 제목·설명·태그를 바꾼다 · 번역 안 넣음",
   "wm = wisdom_card.meta(sb)" in src and 'meta["tags"] = wm["tags"]' in src)

print("── 채널 맥박 형식 · 실험")
import pulse as PU  # noqa: E402
rules = PU.load_formats()["wb"]["rules"]
for e in W.EPISODES[:3]:
    rec = {"title": W.title(e) + " #shorts", "pub": e["date"] + "T08:40:00Z", "dur": 11}
    ck(f"맥박이 '{W.title(e)[:16]}…'를 말년 지혜 표(wisdom)로 센다", PU.classify(rec, rules) == "wisdom", PU.classify(rec, rules))
others = ["오늘 띠별 운세 1위~12위 | 11월 17일 화요일 · 45~96년생 전부 #shorts",
          "출생연도로 보는 노후가 편안해지는 나이 | 50~85년생 전부 · 11월 17일 #shorts",
          "말년 복 있는 띠 순위 1위~12위 | 11월 17일 · 45~96년생 전부 #shorts"]
ck("다른 표 제목은 wisdom 으로 안 센다('말년 복' 띠 순위 포함)", all(PU.classify({"title": t, "pub": "2026-11-17T03:00:00Z", "dur": 11}, rules) != "wisdom"
                                                     for t in others), [PU.classify({"title": t, "pub": "2026-11-17T03:00:00Z", "dur": 11}, rules) for t in others])
exs = {e["id"]: e for e in json.load(open(os.path.join(ROOT, "tools", "pulse_experiments.json"), encoding="utf-8"))["experiments"]}
e = exs.get("wisdom-trial")
ck("실험 달력: wisdom-trial 11/17~12/02 · 판정 = wisdom_card.JUDGE · (내가 정함) · 0.5배 미만이면 접는다 · 운세 표와 비교",
   e and e["start"] == "2026-11-17" and e["judge"] == W.JUDGE.isoformat() and e["formats"][0] == "wisdom"
   and "daily" in e["formats"] and "(내가 정함)" in e["criterion"] and "0.5배 미만" in e["criterion"] and e["owner"] == "pulse"
   and e["status"] == "scheduled", e)

print("── make·path(트리거가 치는 명령 그대로)")
import wb_trigger as T  # noqa: E402
with tempfile.TemporaryDirectory() as tmp:
    p1, p2 = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
    W.main(["make", "--date", "2026-11-17", "--out", p1])
    W.main(["make", "--date", "2026-11-16", "--out", p2])
    a = json.load(open(p1, encoding="utf-8")) if os.path.exists(p1) else {}
    ck("편성일(11/17) make → 그날 스토리보드", a == json.loads(json.dumps(W.storyboard(D(2026, 11, 17)))))
    ck("편성일이 아닌 날(11/16) make → 아무것도 안 쓴다(트리거가 건너뜀)", not os.path.exists(p2))
ck("path = output/news/<날짜>_wisdom_storyboard.json(쇼츠 워크플로가 집는 곳)",
   os.path.relpath(W.path_for(D(2026, 11, 17)), ROOT).replace("\\", "/") == "output/news/2026-11-17_wisdom_storyboard.json")
ck("트리거 SPECS: routine/wisdom · 내 것 찾기 칸 없음", T.SPECS["wisdom"][0] == "routine/wisdom" and T.SPECS["wisdom"][3] is None)

print("\n" + ("✅ 전부 통과" if not FAIL else f"❌ 실패 {FAIL}개"))
sys.exit(1 if FAIL else 0)
