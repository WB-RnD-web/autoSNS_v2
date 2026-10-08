#!/usr/bin/env python3
"""띠·태어난 해·태어난 달 기준(birth_basis) 회귀 테스트 — 입춘 표 · 안내 문구 · 표마다 기준 줄이 붙었는지.

    python pipeline/test_birth_basis.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
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
# 천문연 발표(2020~2026)·천문연 역서 목록(그때 표준시 — 1955~61은 UTC+8:30)과 날짜 같음 · 시각 2분 안.
# ★자정 근처 해를 꼭 넣는다 — 이 해들이 '2월 5일 입춘' 목록과 띠를 가른다(10/8 사실 확인).
KASI = {1947: "02-05 00:51", 1951: "02-05 00:14", 1955: "02-04 22:48", 1959: "02-04 22:13", 1963: "02-04 22:08",
        1976: "02-05 01:40", 1980: "02-05 01:10", 1984: "02-05 00:19", 1988: "02-04 23:43",
        2020: "02-04 18:03", 2021: "02-03 23:59", 2022: "02-04 05:51", 2023: "02-04 11:43", 2024: "02-04 17:27",
        2025: "02-03 23:10", 2026: "02-04 05:02"}
for y, v in KASI.items():
    want = dt.datetime(y, int(v[:2]), int(v[3:5]), int(v[6:8]), int(v[9:]))
    ck(f"{y} 입춘 = 천문연 {v} (날짜 같음 · ±2분)", B.ipchun(y).date() == want.date()
       and abs((B.ipchun(y) - want).total_seconds()) <= 120, B.IPCHUN[y])
try:
    B.ipchun(1939)
    ck("표 밖의 해는 알아보기 쉬운 오류", False)
except ValueError:
    ck("표 밖의 해는 알아보기 쉬운 오류", True)

print("── 띠 정하기")
ck("1966-01-20 → 1965년 뱀띠(입춘 전)", B.ddi_year(dt.date(1966, 1, 20)) == 1965 and B.animal_of(1965) == "뱀")
ck("1966-02-10 → 1966년 말띠", B.ddi_year(dt.date(1966, 2, 10)) == 1966 and B.animal_of(1966) == "말")
ck("1984-02-04 → 1983년 돼지띠(그해 입춘 2월 5일)", B.ddi_year(dt.date(1984, 2, 4)) == 1983 and B.animal_of(1983) == "돼지")
ck("입춘 당일은 시각으로: 1996-02-04 10:00 → 1995 · 23:00 → 1996",
   B.ddi_year(dt.datetime(1996, 2, 4, 10)) == 1995 and B.ddi_year(dt.datetime(1996, 2, 4, 23)) == 1996)
ck("시간대 붙은 시각도 한국 시각으로: 1996-02-04 13:30 UTC(= 22:30 KST) → 1996",
   B.ddi_year(dt.datetime(1996, 2, 4, 13, 30, tzinfo=dt.timezone.utc)) == 1996)
k830 = dt.timezone(dt.timedelta(hours=8, minutes=30))
ck("1955~61 은 그때 표준시(UTC+8:30): 1958-02-04 16:00(+8:30) → 1957(입춘 16:19 전)",
   B.ddi_year(dt.datetime(1958, 2, 4, 16, 0, tzinfo=k830)) == 1957
   and B.ddi_year(dt.datetime(1958, 2, 4, 16, 30, tzinfo=k830)) == 1958)
ck("띠 이름 = fortune_card 와 같은 순서(1984 쥐)", B.ANIMALS == list(FC.ANIMALS) and B.animal_of(1984) == "쥐")
ck("2월 5일 입춘 해(45~96) = 47·48·51·52·56·60·64·68·72·76·80·84",
   B.odd_days(1945, 1996) == {5: [1947, 1948, 1951, 1952, 1956, 1960, 1964, 1968, 1972, 1976, 1980, 1984]},
   B.odd_days(1945, 1996))
ck("손주(08~25) 는 2월 3일 입춘 해 21·25", B.odd_days(2008, 2025) == {3: [2021, 2025]}, B.odd_days(2008, 2025))

print("── 안내 문구")
dn = B.ddi_note()
ck("띠: '사주·만세력에서는 입춘' · 설로 보는 분도 있다 · 양력 예시 · 음력 안내 · 당일 시각",
   "사주·만세력에서는" in dn and "음력 설로 보기도" in dn and "1965년생 뱀띠" in dn
   and "섣달 보름~정월 보름" in dn and "시각" in dn, dn)
ck("띠: '설이 아니라'처럼 설 기준을 틀렸다고 단정하지 않는다(10/8 사실 확인 — 설로 쓴 기사도 있다)",
   "설이 아니라" not in dn)
ck("띠: 2월 5일 입춘 해 목록이 들어간다", "47·48·51·52·56·60·64·68·72·76·80·84년" in dn)
ck("손주 띠 안내는 21·25년 2월 3일", "21·25년" in B.ddi_note(*B.GRAND))
gd = next(d for d in (dt.date(2026, 10, 9) + dt.timedelta(days=k) for k in range(120))
          if GC.theme_for(d)["years"] == "grand")
gdesc = GC.storyboard(gd)["platforms"]["youtube"]["description"]
ck(f"손주 궁합표({gd}): 어르신 줄도 있으니 2월 5일(47~84)·2월 3일(21·25) 둘 다 안내",
   "47·48·51·52·56·60·64·68·72·76·80·84년" in gdesc and "21·25년" in gdesc)
yn = B.year_note()
ck("끝자리: 입춘 기준 · 예시 1955-01-10 → '54년생, 끝자리 4'(출생연도처럼 읽히지 않게)",
   "입춘" in yn and "→ 54년생, 끝자리 4로 보세요" in yn, yn)
mn = B.month_note()
ck("태어난 달: 음력 생일 달 · 윤달 · 양력만 아는 분", "음력 생일 달" in mn and "윤4월생 → 4월생" in mn and "양력 생일만" in mn)
ck("좋은 달 표: 절기로 나눈 양력 달 · 음력 달과 어긋남 안내", "절기로 나눈 양력 달" in B.cal_month_note()
   and "음력 달" in B.cal_month_note())
ck("손주 궁합표 화면 줄은 '2월 4일쯤 전'(2021·2025 입춘이 2월 3일 밤)",
   GC.storyboard(gd)["scenes"][0]["basis"] == B.SCREEN_DDI_WIDE and "2월 3일" not in B.SCREEN_DDI_WIDE)
ck("화면 띠 줄: '양력'을 생일 쪽에(음력으로 생각하는 분이 헷갈리지 않게)", "양력 1월~2월 3일생" in B.SCREEN_DDI
   and "양력 1월~2월 3일생" in B.SCREEN_YEAR)
words = ("십신", "편인", "정관", "월건", "지지")         # 어르신 눈높이 — 화면 줄에 명리 용어 없이
for s in (B.SCREEN_DDI, B.SCREEN_DDI_WIDE, B.SCREEN_YEAR, B.SCREEN_MONTH, B.SCREEN_CAL_MONTH):
    em = sum(0.56 if c.isdigit() else 0.3 if c in "·., ()~" else 0.6 if c.isascii() else 1.0 for c in s)
    ck(f"화면 줄 28px 로 한 줄: '{s}' ({em:.1f}em)", em * 28 <= 900 - 96 and not any(w in s for w in words))

print("── 표마다 기준 줄·설명")
d = dt.date(2026, 10, 9)
daily = FC.build_spec({"date": d.isoformat(), "topic": "fortune", "notes": "", "scenes": []})
ck("매일 띠 운세 카드: 기준 줄 + 설명", daily["scenes"][0].get("basis") == B.SCREEN_DDI
   and "입춘" in FC.meta({"date": d.isoformat(), "topic": "fortune", "notes": ""})["description"])
for name, sb in (("띠 테마", T.storyboard(d)), ("등급표", TC.storyboard(d)), ("궁합표", GC.storyboard(d)),
                 ("풀이형", PC.storyboard(d))):
    ck(f"{name}: 첫 장 기준 줄 = 띠 · 설명에 입춘 안내", sb["scenes"][0].get("basis") in (B.SCREEN_DDI, B.SCREEN_DDI_WIDE)
       and B.ddi_note().splitlines()[0] in sb["platforms"]["youtube"]["description"])
for ep in NY.EPISODES:
    sb = NY.storyboard(d, ep)
    want = B.SCREEN_YEAR if ep["id"] == "digit" else B.SCREEN_DDI
    desc = sb["platforms"]["youtube"]["description"]
    ck(f"신년 {ep['id']}: 기준 줄 · 설명 안내", sb["scenes"][0].get("basis") == want
       and ("끝자리도 띠처럼" in desc if ep["id"] == "digit" else "사주·만세력에서는" in desc))
ny_m = NY.storyboard(d, NY.episode_by_id("months"))
ck("신년 좋은 달: 발밑 글 = SCREEN_CAL_MONTH · 설명에 절기로 나눈 양력 달", ny_m["scenes"][0]["foot"].startswith(B.SCREEN_CAL_MONTH)
   and "'좋은 달'은 절기로 나눈 양력 달" in ny_m["platforms"]["youtube"]["description"])
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

for name, sc0 in (("매일 카드", daily["scenes"][0]), ("궁합표", GC.storyboard(d)["scenes"][0]), ("태어난 달 표", sc)):
    h = M.build_html([dict(sc0, start=0, clip=6)], 6.0, "#C9A227", bg=False)
    ck(f"{name} HTML 에 기준 줄", 'class="basis"' in h and sc0["basis"] in h)


def top_of(html, cls):
    m = re.search(r'class="%s"[^>]*top:([\d.]+)px' % cls, html)
    return float(m.group(1)) if m else None


print("── 자리(10/8 화면 434가지 실측: 발밑 글이 쇼츠 제목 자리 y 1500~ 로 밀렸다 → 표를 줄여 원래 높이로)")
days = [dt.date(2026, 10, 9) + dt.timedelta(days=k) for k in range(60)]
worst_t = []
for dd in days:
    tsc = TC.storyboard(dd)["scenes"][0]
    h = M.build_html([dict(tsc, start=0, clip=6)], 6.0, "#C9A227", bg=False)
    lay = M.tier_layout(tsc["tiers"], M.TIER_BOTTOM - M.BASIS_H)
    worst_t.append((top_of(h, "tfoot"), top_of(h, "basis"), lay["fn"], min(lay["fy"], lay["fl"]), dd))
ck("등급표 60일: 발밑 글 top ≤ 1466(전과 같은 높이) · 기준 줄은 표와 발밑 글 사이",
   all(f <= 1466 and b < f for f, b, *_ in worst_t), max(worst_t))
ck("등급표 60일: 표를 줄여도 띠 이름 44px · 출생연도·이유 24px 이상",
   all(fn >= 44 and fs >= 24 for _, _, fn, fs, _ in worst_t), min(worst_t, key=lambda x: (x[2], x[3])))
worst_g = []
for dd in days:
    gsc = GC.storyboard(dd)["scenes"][0]
    h = M.build_html([dict(gsc, start=0, clip=6)], 6.0, "#C9A227", bg=False)
    lay = M.gunghap_layout(gsc["rows"], M.GH_BOTTOM - M.BASIS_H)
    worst_g.append((top_of(h, "ghfoot"), lay["fa"], lay["fg"], lay["fs"], dd))
ck("궁합표 60일: 발밑 글 top ≤ 1450(전과 같은 높이)", all(f <= 1450 for f, *_ in worst_g), max(worst_g))
ck("궁합표 60일: 표를 줄여도 띠 이름 36px · 짝 30px · 출생연도 20px 이상",
   all(fa >= 36 and fg >= 30 and fs >= 20 for _, fa, fg, fs, _ in worst_g), min(worst_g, key=lambda x: x[3]))
for slot in ("pm", "year"):
    gsc = N.storyboard(d, slot)["scenes"][0]
    h = M.build_html([dict(gsc, start=0, clip=6)], 6.0, "#C9A227", bg=False)
    plain = M.build_html([dict(gsc, start=0, clip=6, basis="")], 6.0, "#C9A227", bg=False)
    ck(f"내 것 찾기({slot}): 기준 줄은 제목 아래·칸 위(346~470) · 발밑 글 높이는 기준 줄 없을 때와 같음",
       350 <= top_of(h, "basis") <= M.GRID_TOP - 40 and top_of(h, "gfoot") == top_of(plain, "gfoot"))
cards = [f"{s} 띠별 운세 순위" for s in ("오늘", "이번 주", "이번 달")] + [t["card"] for t in T.THEMES] + [t["card"] for t in PC.THEMES]
cw = max((sum(0.3 if c == " " else 0.6 if c.isascii() else 0.9 for c in t) * 96 - 3 * len(t), t) for t in cards)
ck(f"띠 순위 카드 제목은 한 줄(96px · 960px 안) — 두 줄이면 기준 줄을 덮는다 · 가장 긴 것 '{cw[1]}' {cw[0]:.0f}px", cw[0] <= 940)

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
