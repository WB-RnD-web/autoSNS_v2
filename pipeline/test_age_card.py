#!/usr/bin/env python3
"""'출생연도로 보는 ○○ 나이' 표(age_card · theme_card 쉬는 날) 회귀 테스트.

    python pipeline/test_age_card.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
import sys
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import age_card as A          # noqa: E402
import motion_short as M      # noqa: E402
import theme_card as T        # noqa: E402
from newyear_card import ten_god  # noqa: E402
from pulli_card import relation   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def hangul(s: str) -> int:
    return len(re.findall(r"[가-힣]", s))


print("── 나이 계산(해시가 아니라 십신·띠 관계)")
ck("테마 10개 · id 겹치지 않음 · 둘째 줄 11자 이내", len(A.THEMES) == 10 and len({t["id"] for t in A.THEMES}) == 10
   and all(hangul(t["l2"]) <= 11 for t in A.THEMES), [t["l2"] for t in A.THEMES if hangul(t["l2"]) > 11])
for th in A.THEMES:
    rs = A.rows(th)
    ok = [r["born"] for r in rs] == A.YEARS and all(r["year"] >= A.FROM_YEAR and r["age"] == r["year"] - r["born"] for r in rs)
    ok &= all(A.fits(th, r["born"], r["year"]) and not any(A.fits(th, r["born"], y) for y in range(A.FROM_YEAR, r["year"]))
              for r in rs)                                   # 그 기운이 '처음' 드는 해
    if "god" in th:
        ok &= all(ten_god(A.stem_of(r["born"]), A.stem_of(r["year"])) == th["god"]
                  and relation(A.branch_of(r["born"]), A.branch_of(r["year"]))[0] != "충" for r in rs)
    else:
        ok &= all(relation(A.branch_of(r["born"]), A.branch_of(r["year"]))[0] in th["rel"] for r in rs)
    ck(f"{th['id']}: 36칸 · 해마다 규칙대로 · 처음 드는 해", ok)
ck("손 계산: 1960 경자생 큰돈(편재 = 갑) → 2034 갑인년 74세",
   next(r for r in A.rows(next(t for t in A.THEMES if t["id"] == "bigmoney")) if r["born"] == 1960)["age"] == 74)
ck("손 계산: 1960 경자생 노후 편안(자축 육합) → 2033 계축년 73세",
   next(r for r in A.rows(next(t for t in A.THEMES if t["id"] == "comfort")) if r["born"] == 1960)["year"] == 2033)
ck("간지: 1960 경자 · 1984 갑자 · 2027 정미", A.ganji(1960) == "경자" and A.ganji(1984) == "갑자" and A.ganji(2027) == "정미")

print("── 편성(띠 테마 쉬는 날 낮 12시)")
days = [dt.date(2026, 10, 9) + dt.timedelta(days=k) for k in range(60)]
ck("10/9 쉬는 날은 아직 건너뜀(AGE_FROM 10/11) · 10/11부터 쉬는 날마다 나이 표 · 내는 날은 띠 테마",
   not T.is_age_day(dt.date(2026, 10, 9)) and T.is_age_day(dt.date(2026, 10, 11))
   and all(T.is_age_day(d) != T.is_post_day(d) for d in days if d >= T.AGE_FROM))
ck("첫 편은 가장 크게 터진 꼴 '노후가 편안해지는 나이'(경쟁 207만)",
   T.storyboard(dt.date(2026, 10, 11))["theme"] == "age:comfort")
age_days = [d for d in days if T.is_age_day(d)]
ids = [T.storyboard(d)["theme"] for d in age_days]
ck("같은 테마는 20일에 한 번(쉬는 날 열 번)", all(ids[i] != ids[j] for i in range(len(ids)) for j in range(i + 1, min(i + 10, len(ids)))), ids)
titles = [T.meta(T.storyboard(d))["title"] for d in age_days]
ck("제목이 날마다 다르다(재탕 제목 금지) · 95자 · 앞머리 '출생연도로 보는'(형식 집계)",
   len(set(titles)) == len(titles) and all(len(t) <= 95 and t.startswith("출생연도로 보는") for t in titles), titles[:2])
sb = T.storyboard(dt.date(2026, 10, 11))
txt = " ".join([sb["platforms"]["youtube"]["title"], sb["platforms"]["youtube"]["description"],
                sb["scenes"][0]["title"], sb["scenes"][0]["title2"], sb["scenes"][0]["narration"], sb["scenes"][0]["foot"]])
ck("금지어 없음(theme_card.BANNED)", not any(b in txt for b in T.BANNED), [b for b in T.BANNED if b in txt])
ck("토픽은 띠 테마 그대로(렌더·업로드·재생목록 길 공유) · 기준 줄 · 설명란에 해마다 근거와 입춘 안내",
   sb["topic"] == T.TOPIC and sb["scenes"][0]["basis"] == A.SCREEN_BASIS
   and "1960년생(경자생 쥐띠) → 2033년(계축년) 73세" in sb["platforms"]["youtube"]["description"]
   and "끝자리도 띠처럼" in sb["platforms"]["youtube"]["description"])
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "a.json")
    T.main(["make", "--date", "2026-10-11", "--out", p])
    ck("트리거 그대로(theme_card make) 쉬는 날 파일이 써진다", os.path.exists(p) and json.load(open(p, encoding="utf-8"))["theme"].startswith("age:"))
    p2 = os.path.join(tmp, "b.json")
    T.main(["make", "--date", "2026-10-09", "--out", p2])
    ck("AGE_FROM 전 쉬는 날은 그대로 건너뜀", not os.path.exists(p2))

print("── 화면(agetable)")
sc = dict(sb["scenes"][0], start=0, clip=9.0, _spk=0)
html = M.build_html([sc], 9.0, acc=sb["accent"], bg=False)
ck("36칸 · 12줄 · 제목 두 줄 · 기준 줄 · 각주", html.count('class="acell"') == 36 and html.count('class="arow') == 12
   and 'class="l2"' in html and 'class="basis"' in html and "afoot" in html)
lay = M.age_layout(36, 3)
right = max(x for x, _ in lay["xy"]) + lay["cw"]
bottom = max(y for _, y in lay["xy"]) + lay["rh"]
ck("표가 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 침범", right <= 961 and bottom <= 1500 and M.AGE_BOTTOM + 18 + 36 <= 1500,
   (right, bottom))
ck("글자 크기: 출생연도 34px · 나이 40px 이상(어르신 눈높이)", lay["fy"] >= 34 and lay["fa"] >= 40, (lay["fy"], lay["fa"]))
ck("한 칸에 '60년생 74세'가 들어간다",
   lay["fy"] * (0.56 * 2 + 2) + 10 + lay["fa"] * (0.56 * 2 + 1) <= lay["cw"] - 36 + 1)
ck("진행자는 나이 표에 서지 않는다", '"agetable")' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1][:260])

print("── 채널 맥박 형식")
import pulse as PU  # noqa: E402
rules = PU.load_formats()["wb"]["rules"]
rec = {"title": titles[0] + " #shorts", "pub": "2026-10-11T03:13:00Z", "dur": 9}
ck("맥박이 '출생연도 나이 표'로 따로 센다", PU.classify(rec, rules) == "age", PU.classify(rec, rules))
import name_card as N  # noqa: E402
rec2 = {"title": N.title(dt.date(2026, 10, 12), "lunar") + " #shorts", "pub": "2026-10-12T06:43:00Z", "dur": 10}
ck("맥박이 '음력 생일 끝자리 표'로 따로 센다", PU.classify(rec2, rules) == "lunar", PU.classify(rec2, rules))
rec3 = {"title": N.title(dt.date(2026, 10, 13), "am") + " #shorts", "pub": "2026-10-13T00:43:00Z", "dur": 10}
ck("이름 표 제목에 날짜를 넣어도 '이름 표'로 센다", PU.classify(rec3, rules) == "name", PU.classify(rec3, rules))

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
