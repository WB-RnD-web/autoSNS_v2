#!/usr/bin/env python3
"""띠·태어난 해·태어난 달 기준(birth_basis) 회귀 테스트 — 입춘 표 · 안내 문구 · 표마다 기준 줄이 붙었는지.

    python pipeline/test_birth_basis.py
"""
from __future__ import annotations
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import birth_basis as B       # noqa: E402
import fortune_card as FC     # noqa: E402
import gunghap_card as GC     # noqa: E402
import motion_short as M      # noqa: E402
import name_card as N         # noqa: E402
import newyear_card as NY     # noqa: E402
import pulli_card as PC       # noqa: E402
import theme_card as T        # noqa: E402
import tier_card as TC        # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


print("── 입춘 표")
ck("1940~2030 빠짐없이", sorted(B.IPCHUN) == list(range(1940, 2031)))
ck("입춘은 늘 양력 2월 3~5일", all(B.ipchun(y).month == 2 and 3 <= B.ipchun(y).day <= 5 for y in B.IPCHUN))
ck("45~96년생 입춘은 2월 4일 또는 5일(그래서 '1월 1일~2월 3일생 = 앞 해 띠'가 늘 맞다)",
   all(B.ipchun(y).day in (4, 5) for y in range(1945, 1997)))
# 천문연 발표 시각(KST)과 2분 안 — ephem 계산이 맞는지
KASI = {2020: "02-04 18:03", 2022: "02-04 05:51", 2023: "02-04 11:43", 2024: "02-04 17:27",
        2025: "02-03 23:10", 2026: "02-04 05:02"}
for y, s in KASI.items():
    want = dt.datetime(y, int(s[:2]), int(s[3:5]), int(s[6:8]), int(s[9:]))
    ck(f"{y} 입춘 = 천문연 {s} ±2분", abs((B.ipchun(y) - want).total_seconds()) <= 120, B.IPCHUN[y])

print("── 띠 정하기")
ck("1966-01-20 → 1965년 뱀띠(입춘 전)", B.ddi_year(dt.date(1966, 1, 20)) == 1965 and B.animal_of(1965) == "뱀")
ck("1966-02-10 → 1966년 말띠", B.ddi_year(dt.date(1966, 2, 10)) == 1966 and B.animal_of(1966) == "말")
ck("1984-02-04 → 1983년 돼지띠(그해 입춘 2월 5일)", B.ddi_year(dt.date(1984, 2, 4)) == 1983 and B.animal_of(1983) == "돼지")
ck("입춘 당일은 시각으로: 1996-02-04 10:00 → 1995 · 23:00 → 1996",
   B.ddi_year(dt.datetime(1996, 2, 4, 10)) == 1995 and B.ddi_year(dt.datetime(1996, 2, 4, 23)) == 1996)
ck("띠 이름 = fortune_card 와 같은 순서(1984 쥐)", B.ANIMALS == list(FC.ANIMALS) and B.animal_of(1984) == "쥐")
ck("2월 5일 입춘 해(45~96) = 47·48·51·52·56·60·64·68·72·76·80·84",
   B.odd_days(1945, 1996) == {5: [1947, 1948, 1951, 1952, 1956, 1960, 1964, 1968, 1972, 1976, 1980, 1984]},
   B.odd_days(1945, 1996))
ck("손주(08~25) 는 2월 3일 입춘 해 21·25", B.odd_days(2008, 2025) == {3: [2021, 2025]}, B.odd_days(2008, 2025))

print("── 안내 문구")
dn = B.ddi_note()
ck("띠: '설이 아니라 입춘' · 양력 예시 · 음력 안내(섣달 보름~정월 보름) · 당일 시각",
   "입춘" in dn and "음력 설이 아니라" in dn and "1965년생 뱀띠" in dn and "섣달 보름~정월 보름" in dn
   and "시각" in dn, dn)
ck("띠: 2월 5일 입춘 해 목록이 들어간다", "47·48·51·52·56·60·64·68·72·76·80·84년" in dn)
ck("손주 띠 안내는 21·25년 2월 3일", "21·25년" in B.ddi_note(*B.GRAND))
yn = B.year_note()
ck("끝자리: 입춘 기준 · 예시 1955-01-10 → 4년생", "입춘" in yn and "→ 4년생" in yn, yn)
mn = B.month_note()
ck("태어난 달: 음력 생일 달 · 윤달 · 양력만 아는 분", "음력 생일 달" in mn and "윤4월생 → 4월생" in mn and "양력 생일만" in mn)
ck("좋은 달 표: 양력 · 절기", "양력" in B.cal_month_note() and "절기" in B.cal_month_note())
words = ("십신", "편인", "정관", "월건", "지지")         # 어르신 눈높이 — 화면 줄에 명리 용어 없이
for s in (B.SCREEN_DDI, B.SCREEN_YEAR, B.SCREEN_MONTH, B.SCREEN_CAL_MONTH):
    em = sum(0.56 if c.isdigit() else 0.3 if c in "·., ()~" else 0.6 if c.isascii() else 1.0 for c in s)
    ck(f"화면 줄 28px 로 한 줄: '{s}' ({em:.1f}em)", em * 28 <= 900 - 96 and not any(w in s for w in words))

print("── 표마다 기준 줄·설명")
d = dt.date(2026, 10, 9)
daily = FC.build_spec({"date": d.isoformat(), "topic": "fortune", "notes": "", "scenes": []})
ck("매일 띠 운세 카드: 기준 줄 + 설명", daily["scenes"][0].get("basis") == B.SCREEN_DDI
   and "입춘" in FC.meta({"date": d.isoformat(), "topic": "fortune", "notes": ""})["description"])
for name, sb in (("띠 테마", T.storyboard(d)), ("등급표", TC.storyboard(d)), ("궁합표", GC.storyboard(d)),
                 ("풀이형", PC.storyboard(d))):
    ck(f"{name}: 첫 장 기준 줄 = 띠 · 설명에 입춘 안내", sb["scenes"][0].get("basis") == B.SCREEN_DDI
       and B.ddi_note().splitlines()[0] in sb["platforms"]["youtube"]["description"])
for ep in NY.EPISODES:
    sb = NY.storyboard(d, ep)
    want = B.SCREEN_YEAR if ep["id"] == "digit" else B.SCREEN_DDI
    desc = sb["platforms"]["youtube"]["description"]
    ck(f"신년 {ep['id']}: 기준 줄 · 설명 안내", sb["scenes"][0].get("basis") == want
       and ("끝자리도 띠처럼" in desc if ep["id"] == "digit" else "음력 설이 아니라" in desc))
ny_m = NY.storyboard(d, NY.episode_by_id("months"))
ck("신년 좋은 달: 발밑 글 '달은 양력' · 설명에 양력 달", "양력" in ny_m["scenes"][0]["foot"]
   and "'좋은 달'의 달은 양력" in ny_m["platforms"]["youtube"]["description"])
pm = N.storyboard(d, "pm")
sc = pm["scenes"][0]
ck("태어난 달 표: 화면 제목 '음력 생일 달로 보는' · 기준 줄 · 목소리 '음력 생일 달'",
   sc["title"] == "음력 생일 달로 보는" and sc.get("basis") == B.SCREEN_MONTH and "음력 생일 달" in sc["narration"])
ck("태어난 달 표: 유튜브 제목 앞머리는 그대로(형식 집계) + '음력 1월생'",
   N.title(d, "pm").startswith("태어난 달로 보는") and "음력 1월생~12월생" in N.title(d, "pm"))
ck("태어난 달 표: 설명에 음력 안내", "'태어난 달'은 음력 생일 달" in N.description(d, "pm"))
yr = N.storyboard(d, "year")
ck("해 끝자리 표: 기준 줄 · 설명에 입춘 안내", yr["scenes"][0].get("basis") == B.SCREEN_YEAR
   and "끝자리도 띠처럼" in N.description(d, "year"))
ck("이름·성씨 표엔 기준 줄 없음", not N.storyboard(d, "am")["scenes"][0].get("basis")
   and not N.storyboard(d, "surname")["scenes"][0].get("basis") and "입춘" not in N.description(d, "am"))

print("── 화면(HTML)")
html = M.build_html([dict(TC.storyboard(d)["scenes"][0], start=0, clip=6)], 6.0, "#C9A227", bg=False)
ck("기준 줄: '기준' 딱지 + 문구 · 스타일", 'class="basis"' in html and "<b>기준</b>" in html
   and B.SCREEN_DDI in html and ".basis{" in html)
html2 = M.build_html([dict(N.storyboard(d, "am")["scenes"][0], start=0, clip=6)], 6.0, "#C9A227", bg=False)
ck("기준 없는 표엔 기준 줄·스타일 없음", 'class="basis"' not in html2 and ".basis{" not in html2)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
