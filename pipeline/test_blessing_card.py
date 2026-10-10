#!/usr/bin/env python3
"""'띠별 아침 덕담표'(blessing_card · 풀이형 표 쉬는 날 10:40) 회귀 테스트.

    python pipeline/test_blessing_card.py
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import birth_basis            # noqa: E402
import blessing_card as B     # noqa: E402
import fortune_card as FC     # noqa: E402
import motion_short as M      # noqa: E402
import pulli_card as P        # noqa: E402
from theme_card import BANNED  # noqa: E402

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


D = dt.date
WANT = [D(2026, 10, 11), D(2026, 10, 13), D(2026, 10, 15), D(2026, 10, 17), D(2026, 10, 19), D(2026, 10, 21), D(2026, 10, 23)]

print("── 편성(10:40 풀이형 자리 · 10/11~10/24 격일)")
ck("덕담표 날 = 10/11·13·15·17·19·21·23 (7편)", B.bless_days() == WANT, B.bless_days())
span = [D(2026, 10, 1) + dt.timedelta(days=k) for k in range(60)]
ck("기간 안에서는 하루씩 번갈아 · 기간 밖(10/10 이전 · 10/24 · 10/25 이후)은 하루도 없다",
   [d for d in span if P.is_bless_day(d)] == WANT and not P.is_bless_day(D(2026, 10, 24))
   and not P.is_bless_day(D(2026, 10, 25)) and not P.is_bless_day(D(2026, 10, 10)))
same = all(P.storyboard(d) == P.pulli_storyboard(d) for d in span if not P.is_bless_day(d))
ck("덕담표 날이 아니면 풀이형 표 그대로(60일 — 10/24 · 10/25 뒤 포함)", same)
ck("덕담표 날이 아니면 theme 은 풀이형 테마", all(P.storyboard(d)["theme"] in {t["id"] for t in P.THEMES}
                                         for d in span if not P.is_bless_day(d)))
sbs = {d: P.storyboard(d) for d in WANT}
ck("덕담표 날은 덕담표 · 토픽은 풀이형 그대로(fortune_pulli — 렌더·업로드·재생목록 길 공유)",
   all(sb["theme"] == B.THEME and sb["topic"] == P.TOPIC and B.is_bless(sb) for sb in sbs.values()))
ck("파일 경로는 풀이형과 같다(루틴 path 명령 그대로)",
   P.path_for(D(2026, 10, 11), root="/r").replace("\\", "/") == "/r/output/news/2026-10-11_fortune_pulli_storyboard.json")
ck("끄기 스위치: BLESS_FROM = None 이면 하루도 없다", (lambda: (setattr(P, "BLESS_FROM", None),
   not any(P.is_bless_day(d) for d in WANT), setattr(P, "BLESS_FROM", D(2026, 10, 11)))[1])())
ck("풀이형 실험(tables-v2)의 판정일 10/22 은 풀이형 날", not P.is_bless_day(D(2026, 10, 22)))

print("── 문구(결정적 · 겹치지 않음)")
ck("같은 날짜면 같은 표", B.build_rows(D(2026, 10, 15)) == B.build_rows(D(2026, 10, 15))
   and P.storyboard(D(2026, 10, 15)) == P.storyboard(D(2026, 10, 15)))
lines = [r["line"] for d in WANT for r in B.build_rows(d)]
ck("7편 84칸 — 같은 문구가 한 번도 다시 나오지 않는다", len(lines) == 84 and len(set(lines)) == 84,
   sorted({x for x in lines if lines.count(x) > 1}))
need = {c: sum(len(B.order_in(d, c)) for d in WANT) for c in B.CATS}
ck("결마다 목록이 7편에 쓸 칸보다 많다", all(len(B.LINES[c]) >= need[c] for c in B.CATS), (need, {c: len(v) for c, v in B.LINES.items()}))
pool = [x for v in B.LINES.values() for x in v]
ck("목록 안에서도 겹치지 않는다(결 사이 포함)", len(pool) == len(set(pool)))
ck("한 줄 한글 9자 이내 · 숫자·영문 없음", all(hangul(x) <= 9 and not re.search(r"[0-9A-Za-z]", x) for x in pool),
   [x for x in pool if hangul(x) > 9])
ck("시험 기간 밖(견본)도 늘 같은 표 · 12칸 다 찬다", B.build_rows(D(2026, 11, 3)) == B.build_rows(D(2026, 11, 3))
   and all(r["line"] for r in B.build_rows(D(2026, 11, 3))))

print("── 근거(오늘 일진과 내 띠의 관계)")
ok = True
for d in WANT:
    g = P.ganzhi(d)
    for r in B.build_rows(d):
        rel, _ = P.relation(g["branch"], r["branch"])
        ok &= r["rel"] == rel and r["cat"] == B.CAT_OF[rel] and r["line"] in B.LINES[r["cat"]]
ck("7편 모든 칸: 관계 → 결 → 그 결의 문구", ok)
r11 = {r["animal"]: r for r in B.build_rows(D(2026, 10, 11))}
ck("손 계산 ① 10/11 무오일(말의 날): 양 = 오미 육합 → 합 첫 문구 · 개·호랑이 = 인오술 삼합 · 쥐 = 자오 충 · 소 = 축오 원진 · "
   "토끼 = 묘오 파 · 말 = 같은 띠(평온)",
   P.ganzhi(D(2026, 10, 11))["name"] == "무오"
   and (r11["양"]["rel"], r11["양"]["line"]) == ("육합", "반가운 소식이 와요")
   and (r11["개"]["rel"], r11["개"]["line"]) == ("삼합", "기다리던 전화가 와요")
   and (r11["호랑이"]["rel"], r11["호랑이"]["line"]) == ("삼합", "귀한 손님이 찾아와요")
   and (r11["쥐"]["rel"], r11["쥐"]["line"]) == ("충", "서두를 것 없어요")
   and (r11["소"]["rel"], r11["소"]["cat"]) == ("원진", "형파해") and (r11["토끼"]["rel"], r11["토끼"]["cat"]) == ("파", "형파해")
   and (r11["말"]["rel"], r11["말"]["cat"]) == ("같은 띠", "평온"),
   {a: (r["rel"], r["line"]) for a, r in r11.items()})
r17 = {r["animal"]: r for r in B.build_rows(D(2026, 10, 17))}
# 10/17 은 네 번째 덕담표 날 — 합 문구는 앞 세 편이 9칸, 충 문구는 3칸을 썼다 → 합 10번째 · 충 4번째
ck("손 계산 ② 10/17 갑자일(쥐의 날): 소 = 자축 육합 → 합 10번째 '든든한 내 편 생겨요' · 말 = 자오 충 → 충 4번째 "
   "'오늘은 쉬어 가세요' · 토끼 = 자묘 형 · 양 = 자미 원진 · 닭 = 자유 파 · 쥐 = 같은 띠",
   P.ganzhi(D(2026, 10, 17))["name"] == "갑자"
   and (r17["소"]["rel"], r17["소"]["line"]) == ("육합", "든든한 내 편 생겨요")
   and (r17["말"]["rel"], r17["말"]["line"]) == ("충", "오늘은 쉬어 가세요")
   and [r17[a]["rel"] for a in ("토끼", "양", "닭", "쥐")] == ["형", "원진", "파", "같은 띠"]
   and all(r17[a]["cat"] == "형파해" for a in ("토끼", "양", "닭")),
   {a: (r["rel"], r["line"]) for a, r in r17.items()})

print("── 금지어")
RELIGION = ("부처", "하나님", "하느님", "아멘", "나무아미타불", "기도", "축복", "주님", "예수", "성경", "불경", "염불", "교회",
            "성당", "절에", "찬송", "할렐루야", "관세음", "보살", "은총", "천국", "극락")
JARGON = ("육합", "삼합", "원진", "일진", "오행", "십신", "천간", "지지", "간지", "사주", "명리", "충·", "형·", "파·", "해·",
          "상충", "대길", "흉", "인성", "비겁", "식상", "재성", "관성")
GAME = ("레벨", "득템", "버프", "만렙", "최강", "역대급", "꿀팁", "등급", "순위", "1위", "점수", "S급", "A급", "급!")
SCARE = ("조심", "나쁜", "불운", "액운", "손해", "다툼", "싸움", "위험", "큰일", "재수", "꼴찌", "최악", "망")
HEALTH = ("건강해", "튼튼해", "낫는", "나아요", "나을", "병이", "오래 살", "장수", "회복", "완쾌")
MONEY = re.compile(r"\d[\d,]*\s*(원|만|억)|목돈|떼돈|돈이 들어")
screens = []
for d in WANT:
    sc = sbs[d]["scenes"][0]
    screens += [sc["title"], sc["pill"], sc["basis"]] + [r["line"] for r in sc["rows"]]
screens += pool
texts = screens + [B.title(d) for d in WANT] + [B.description(d) for d in WANT] + [sbs[d]["scenes"][0]["narration"] for d in WANT]
hit = lambda words, xs: sorted({w for w in words for t in xs if w in t})  # noqa: E731
ck("theme_card 금지어 없음(의료·투자·겁주기)", not hit(BANNED, texts), hit(BANNED, texts))
# 종교 말은 낱말 앞이 한글이 아닐 때만 잡는다 — '보기도'(입춘 안내)·'계절에' 같은 말까지 잡지 않게
rel_hit = sorted({w for w in RELIGION for t in texts if re.search(r"(?<![가-힣])" + w, t)})
ck("종교 말 없음(부처님·하나님·아멘·나무아미타불·기도·축복…) — 설명란·내레이션까지", not rel_hit, rel_hit)
ck("화면에 명리 용어 없음(합·충은 설명란에만)", not hit(JARGON, screens), hit(JARGON, screens))
ck("게임 말투·순위 말 없음 · 영문 등급 없음", not hit(GAME, screens + [B.title(d) for d in WANT]), hit(GAME, screens))
ck("겁주는 말·깎아내리는 말 없음", not hit(SCARE, screens), hit(SCARE, screens))
ck("건강 장담 없음", not hit(HEALTH, texts), hit(HEALTH, texts))
ck("돈 액수 없음", not any(MONEY.search(t) for t in screens + [sbs[d]["scenes"][0]["narration"] for d in WANT]))

print("── 제목·설명란")
titles = [B.title(d) for d in WANT]
ck("제목: 앞머리 '띠별 아침 덕담' 고정 · 날짜가 들어가 날마다 다르다 · #shorts 붙여 100자 이내",
   all(t.startswith(B.TITLE_PREFIX) and f"{d.month}월 {d.day}일" in t and len(t + " #shorts") <= 100 for t, d in zip(titles, WANT))
   and len(set(titles)) == 7, titles[:2])
ck("메타(pulli_card.meta)가 덕담표 제목·설명을 쓴다", P.meta(sbs[WANT[0]]) == B.meta(sbs[WANT[0]])
   and P.meta(sbs[WANT[0]])["title"] == titles[0])
ck("풀이형 메타는 그대로", P.meta(P.storyboard(D(2026, 10, 12)))["title"] == P.title(D(2026, 10, 12))[:95])
desc = B.description(WANT[0])
ck("설명란: 12띠마다 고른 이유(관계) · 입춘 안내 · '재미로 보세요' · 댓글 부탁",
   all(f"· {a}띠(" in desc for a in FC.ANIMALS) and "말의 날과 육합" in desc and "인오술 삼합" in desc
   and "마주 보는 충" in desc and birth_basis.ddi_note() in desc and "재미로 보세요" in desc and "댓글" in desc)
ck("설명란 한 줄: '· 양띠(55·67·79·91년생) — 말의 날과 육합 … → 반가운 소식이 와요'",
   "· 양띠(55·67·79·91년생) — 말의 날과 육합, 손발이 맞는 짝이라 반가운 일의 한마디 → '반가운 소식이 와요'" in desc,
   [x for x in desc.splitlines() if x.startswith("· 양띠")])

print("── 화면(bless)")
ok_lay, info = True, []
for d in WANT:
    sc = dict(sbs[d]["scenes"][0], start=0.0, clip=B.MIN_TOTAL)
    html = M.build_html([sc], B.MIN_TOTAL, sbs[d]["accent"], bg=True)
    cells = [tuple(map(float, m)) for m in re.findall(
        r'class="bcell"[^>]*left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px', html)]
    right = max(x + w for x, _, w, _ in cells)
    bottom = max(y + h for _, y, _, h in cells)
    lay = M.bless_layout([r["line"] for r in sc["rows"]])
    fits = all(lay["fl"] * M._bless_em(r["line"]) <= lay["cw"] - 2 * M.BLESS_PAD for r in sc["rows"])
    ok_lay &= len(cells) == 12 and right <= 960 and bottom <= 1500 and fits and lay["fl"] >= 36
    info.append((d.isoformat(), right, bottom, lay["fl"]))
ck("12칸이 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 · 덕담 한 줄이 칸 안에 들어간다(7편)", ok_lay, info)
card_px = {k: int(v) for k, v in re.findall(r"\.cell \.(nm|yr|ln)\{[^}]*?font-size:(\d+)px", M.CSS_CARD)}
lay = M.bless_layout(pool)                                  # 목록에서 가장 긴 줄도
ck(f"글자 크기: 띠 {M.BLESS_FN}px · 출생연도 {M.BLESS_FY}px · 덕담 36px 이상 — 지금 12칸 표({card_px}) 이상",
   M.BLESS_FN >= card_px["nm"] and M.BLESS_FY >= card_px["yr"] and lay["fl"] >= max(36, card_px["ln"]), (card_px, lay["fl"]))
# 폭은 theme_card 테스트와 같은 잣대(96px 한글 한 자 88px · 빈칸 26px) + 제목 칸 좌우 여백 26px
ck("화면 제목 96px 한 줄(제목 칸 900px 안)", hangul(B.SCREEN_TITLE) <= 9
   and sum(26 if c == " " else 88 for c in B.SCREEN_TITLE) + 52 <= 900 and "font-size:96px" in M.CSS_BLESS)
sc = dict(sbs[WANT[0]]["scenes"][0], start=0.0, clip=B.MIN_TOTAL)
html = M.build_html([sc], B.MIN_TOTAL, sbs[WANT[0]]["accent"], bg=False)
ck("제목 · '한마디' 분홍 · 기준 줄(입춘) · 꽃 바탕 · 순위 동그라미·점수 없음",
   '띠별로 드리는<em>한마디</em>' in html and birth_basis.SCREEN_DDI in html and 'class="bfloral"' in html
   and html.count('class="bfl"') >= 12 and 'class="rk"' not in html and "점</span>" not in html)
ck("꽃 그림이 있으면 어두운 막 대신 밝은 막 · CSS 꽃은 숨긴다", "#root #scrim{" in M.CSS_BLESS
   and "#scrim ~ .scene .bdeco{display:none;}" in M.CSS_BLESS)
pos = [int(x) for x in re.findall(r'class="basis"[^>]*top:(\d+)px', html)]
ck("기준 줄이 제목(아래 끝 304) 아래 · 첫 칸(360) 위", pos and 304 <= pos[0] and pos[0] + 34 <= M.BLESS_TOP, pos)
js = M.scene_js(0, sc, "#E0758A")
ck("0초부터 다 보인다(등장 애니메이션 없음) · 칸이 차례로 숨 쉰다", "tl.from(" not in js and js.count("-c") >= 12)
ck("진행자는 덕담표에 서지 않는다", '"bless"' in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1].splitlines()[0])
import cover_short as C  # noqa: E402
st = C._fields(sbs[WANT[0]])[2]
ck("배경 그림: 수채화 꽃(치비 띠 동물 아님) · 사람·글자 없음 꼬리", st == "flower"
   and C._style_prompt(st) == C.CARD_STYLE_PROMPT["flower"] and "chibi" not in C._style_prompt(st)
   and sbs[WANT[0]]["thumbnail_hook"].endswith(P.HOOK_TAIL) and "flower" in sbs[WANT[0]]["thumbnail_hook"]
   and "photo" not in sbs[WANT[0]]["thumbnail_hook"])

print("── 파이프라인 연결")
import ledger as L          # noqa: E402
import run_pipeline as R    # noqa: E402
import tier_card            # noqa: E402
sb = sbs[WANT[0]]
ck("아침 운세 표·등급표 A/B 가 덕담표를 덮어쓰지 않는다", not FC.use_card(sb) and not tier_card.use_ab(sb))
ck("ledger 키 = <날짜>_fortune_pulli(하루 한 편 그대로)", L.key_for(sb) == "2026-10-11_fortune_pulli", L.key_for(sb))
ck("재생목록·카테고리·AI 표시 = 풀이형과 같다", R.playlist_for(sb["topic"])[0] == R.PULLI_PLAYLIST
   and R.category_for(sb["topic"]) == "24" and R.synthetic_label(sb, {"_bg": "x.png"}) is False and not R.is_paused(sb))
ck("스토리보드에 장면이 실려 있다(CI 에서 LLM 안 씀) · 12칸 이상 머문다", [s["type"] for s in sb["scenes"]] == ["bless"]
   and len(sb["scenes"][0]["rows"]) == 12 and sb["_min_total"] >= 9)

print("── 채널 맥박 형식")
import pulse as PU  # noqa: E402
rules = PU.load_formats()["wb"]["rules"]
rec = {"title": titles[0] + " #shorts", "pub": "2026-10-11T01:40:00Z", "dur": 11}
ck("맥박이 덕담표를 '띠별 아침 덕담표'(bless)로 따로 센다", PU.classify(rec, rules) == "bless", PU.classify(rec, rules))
rec2 = {"title": P.title(D(2026, 10, 12)) + " #shorts", "pub": "2026-10-12T01:40:00Z", "dur": 14}
ck("풀이형 표는 그대로 '풀이형 표'(pulli)", PU.classify(rec2, rules) == "pulli", PU.classify(rec2, rules))
exs = {e["id"]: e for e in json.load(open(os.path.join(os.path.dirname(HERE), "tools", "pulse_experiments.json"),
                                          encoding="utf-8"))["experiments"]}
e = exs.get("blessing")
ck("실험 달력: blessing 10/11~10/25 · 덕담표 vs 풀이형·운세 표 · (내가 정함) · 50% 미만이면 접는다",
   e and e["start"] == "2026-10-11" and e["judge"] == "2026-10-25" and e["formats"][:2] == ["bless", "pulli"]
   and "(내가 정함)" in e["criterion"] and "50% 미만" in e["criterion"] and e["owner"] == "pulse", e)
t2 = exs.get("tables-v2")
ck("풀이형 실험(tables-v2)은 그대로(10/22 판정 · 형식 목록에 덕담표 없음)", t2 and t2["judge"] == "2026-10-22"
   and "bless" not in t2["formats"] and "pulli" in t2["formats"])

print("── make(루틴 명령 그대로)")
with tempfile.TemporaryDirectory() as tmp:
    p1, p2 = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
    P.main(["make", "--date", "2026-10-11", "--out", p1])
    P.main(["make", "--date", "2026-10-12", "--out", p2])
    a = json.load(open(p1, encoding="utf-8")) if os.path.exists(p1) else {}
    b = json.load(open(p2, encoding="utf-8")) if os.path.exists(p2) else {}
    ck("덕담표 날(10/11) make → 덕담표 파일", a.get("theme") == B.THEME and a == json.loads(json.dumps(P.storyboard(D(2026, 10, 11)))))
    ck("풀이형 날(10/12) make → 원래 풀이형 파일", b.get("theme") in {t["id"] for t in P.THEMES}
       and [s["type"] for s in b.get("scenes", [])] == ["card", "news"] and b == json.loads(json.dumps(P.pulli_storyboard(D(2026, 10, 12)))))
    # 루틴이 실제로 치는 명령 — path 로 경로를 받고 make --out 으로 쓴다(여기선 임시 폴더에)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, os.path.join(HERE, "pulli_card.py"), "path", "--date", "2026-10-13"],
                         capture_output=True, text=True, encoding="utf-8", env=env).stdout.strip()
    p3 = os.path.join(tmp, "c.json")
    subprocess.run([sys.executable, os.path.join(HERE, "pulli_card.py"), "make", "--date", "2026-10-13", "--out", p3],
                   capture_output=True, text=True, encoding="utf-8", env=env)
    c = json.load(open(p3, encoding="utf-8")) if os.path.exists(p3) else {}
    ck("명령줄 path·make: 경로는 풀이형 그대로 · 10/13 파일은 덕담표",
       out.replace("\\", "/").endswith("output/news/2026-10-13_fortune_pulli_storyboard.json") and c.get("theme") == B.THEME, (out, c.get("theme")))

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
