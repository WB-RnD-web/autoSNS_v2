#!/usr/bin/env python3
"""풀이형 표(pulli_card) 오프라인 테스트 — 일진 계산·지지 관계·순위·문구·연결."""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fortune_card as FC  # noqa: E402
import pulli_card as P  # noqa: E402
from theme_card import BANNED  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


print("── 일진(60갑자) ──")
for d, want in [("1949-10-01", "갑자"), ("2000-01-01", "무오"), ("2026-09-24", "신축"), ("2026-10-08", "을묘")]:
    got = P.ganzhi(dt.date.fromisoformat(d))["name"]
    ck(f"{d} = {want}일", got == want, got)
ck("하루 지나면 다음 갑자", all((P.ganzhi_index(dt.date(2026, 1, 1) + dt.timedelta(days=k + 1)) - P.ganzhi_index(dt.date(2026, 1, 1) + dt.timedelta(days=k))) % 60 == 1
                          for k in range(70)))

print("── 지지 관계 ──")
ck("충: 띠마다 정확히 하나(6칸 건너편)", all(sum(P.relation(a, b)[0] == "충" for b in range(12)) == 1 for a in range(12)))
ck("육합: 띠마다 짝 하나", all(sum(any({a, b} == set(p) for p in P.YUKHAP) for b in range(12)) == 1 for a in range(12)))
ck("삼합: 네 무리가 12띠를 나눈다", sorted(x for g, _ in P.SAMHAP for x in g) == list(range(12)))
ck("같은 띠 = '같은 띠'", all(P.relation(a, a)[0] == "같은 띠" for a in range(12)))
ck("관계는 대칭", all(P.relation(a, b)[0] == P.relation(b, a)[0] for a in range(12) for b in range(12)))
ck("겹치면 센 쪽: 인해(육합·파) → 육합 · 자미(해·원진) → 원진", P.relation(2, 11)[0] == "육합" and P.relation(0, 7)[0] == "원진")
ck("십신: 갑(목)일에 쥐(수) = 식상·말(화) = 인성·소(토) = 관성·원숭이(금) = 재성·호랑이(목) = 비겁",
   [P.sipsin("목", b) for b in (0, 6, 1, 8, 2)] == ["식상", "인성", "관성", "재성", "비겁"],
   [P.sipsin("목", b) for b in (0, 6, 1, 8, 2)])

print("── 표 60일 ──")
days = [dt.date(2026, 10, 8) + dt.timedelta(days=k) for k in range(60)]
bad = []
texts = []
combos = set()
for d in days:
    rows = P.build_rows(d)
    sb = P.pulli_storyboard(d)          # 덕담표 날(10/11~10/23 격일)에도 풀이형 표 자체는 늘 만들 수 있어야 한다
    if sorted(r["animal"] for r in rows) != sorted(FC.ANIMALS) or [r["rank"] for r in rows] != list(range(1, 13)):
        bad.append((d, "띠·순위"))
    if any(a["score"] <= b["score"] for a, b in zip(rows, rows[1:])):
        bad.append((d, "점수가 순위대로 줄지 않음"))
    if any(len(r["line"]) > 9 for r in rows):
        bad.append((d, [r["line"] for r in rows if len(r["line"]) > 9]))
    if len(sb["scenes"][1]["narration"]) > 110:
        bad.append((d, "풀이 내레이션이 길다", len(sb["scenes"][1]["narration"])))
    if len(P.title(d)) > 95:
        bad.append((d, "제목 95자 넘음"))
    texts += [r["line"] for r in rows] + sb["scenes"][1]["items"] + [sc["narration"] for sc in sb["scenes"]]
    texts += [P.title(d), P.description(d), sb["scenes"][1]["verdict"]]
    combos.add((sb["theme"], tuple(r["animal"] for r in rows[:3])))
ck("12띠·1~12위·점수 내림차순·한 줄 9자·제목 95자·풀이 내레이션 110자", not bad, bad[:3])
hits = sorted({w for w in BANNED for t in texts if w in t})
ck("금지어 없음(의료·투자·겁주기)", not hits, hits)
ck("60일 표가 서로 다르다(테마·1~3위 조합 50가지 이상 — '서로 바꿔 끼울 수 있는 영상'이 아니다)", len(combos) >= 50, len(combos))
ck("같은 날짜면 같은 표", P.storyboard(days[0]) == P.storyboard(days[0]))

print("── 덕담표 날(10/11~10/24 격일, blessing_card) ──")
bless = [d for d in days if P.is_bless_day(d)]
ck("덕담표 날 7편 · 그 밖의 날은 storyboard = 풀이형 표 그대로", len(bless) == 7
   and all(P.storyboard(d) == P.pulli_storyboard(d) for d in days if d not in bless), bless)
ck("덕담표 날은 같은 토픽·같은 파일 경로로 덕담표", all(P.storyboard(d)["topic"] == P.TOPIC
   and P.storyboard(d)["theme"].startswith("bless:") for d in bless))

print("── 덕담표 기간 풀이형 테마(격일이어도 6개가 다 돈다) ──")
win = [dt.date(2026, 10, 12) + dt.timedelta(days=2 * k) for k in range(7)]      # 10/12·14·…·24 = 기간 안 풀이형 날
ck("기간 안 풀이형 날 = 10/12·14·16·18·20·22·24", [d for d in (dt.date(2026, 10, 11) + dt.timedelta(days=k) for k in range(14))
                                           if not P.is_bless_day(d)] == win)
seq = [P.storyboard(d)["theme"] for d in win]
ck("기간 안 풀이형 날에 테마 6개가 전부 나온다(날짜 순환이면 집안·귀인·자식 셋뿐이었다)",
   set(seq) == {t["id"] for t in P.THEMES}, seq)
ck("기간 안 풀이형 날 연속 6편마다 테마가 겹치지 않는다", all(len(set(seq[i:i + 6])) == 6 for i in range(len(seq) - 5)), seq)
ck("기간 첫 풀이형 날이 직전 순환을 이어받는다(10/10 자식 → 10/12 몸 → 10/14 집안 → 10/16 돈)",
   seq[:3] == ["body", "home", "money"], seq)
# main(855aa8c, 덕담표 전) 의 theme_for 결과를 그대로 박아 둔다 — 기간 밖은 한 날짜도 바뀌면 안 된다
MAIN_1001 = ["money", "helper", "work", "children", "body", "home", "money", "helper", "work", "children"]  # 10/1~10/10
MAIN_1025 = ["money", "helper", "work", "children", "body", "home"] * 5                                   # 10/25~11/23
ck("기간 밖 테마 = main 그대로(10/1~10/10)",
   [P.theme_for(dt.date(2026, 10, 1) + dt.timedelta(days=k))["id"] for k in range(10)] == MAIN_1001)
ck("기간 밖 테마 = main 그대로(10/25~11/23)",
   [P.theme_for(dt.date(2026, 10, 25) + dt.timedelta(days=k))["id"] for k in range(30)] == MAIN_1025)
ck("기간 밖 제목 = main 그대로(10/10 · 10/25 · 11/30)",
   [P.title(dt.date(2026, 10, 10)), P.title(dt.date(2026, 10, 25)), P.title(dt.date(2026, 11, 30))] ==
   ["오늘 자식 덕 보는 띠 순위 1위~12위 | 10월 10일 정사일 풀이 · 45~96년생 전부",
    "오늘 돈 들어오는 띠 순위 1위~12위 | 10월 25일 임신일 풀이 · 45~96년생 전부",
    "오늘 돈 들어오는 띠 순위 1위~12위 | 11월 30일 무신일 풀이 · 45~96년생 전부"])
ck("기간 밖은 날짜 순환 공식 그대로(10/25~12/31)", all(P.theme_for(d) is P.THEMES[(d - P.EPOCH).days % 6]
   for d in (dt.date(2026, 10, 25) + dt.timedelta(days=k) for k in range(68))))
_bf = P.BLESS_FROM
P.BLESS_FROM = None
ck("덕담표를 끄면(BLESS_FROM = None) 기간 안도 날짜 순환", [P.theme_for(d)["id"] for d in win]
   == [P.THEMES[(d - P.EPOCH).days % 6]["id"] for d in win])
P.BLESS_FROM = _bf

print("── 스토리보드·메타 ──")
sb = P.storyboard(dt.date(2026, 10, 8))
ck("토픽 fortune_pulli · 장면 = 표 + 풀이", sb["topic"] == "fortune_pulli" and [s["type"] for s in sb["scenes"]] == ["card", "news"])
ck("표 장면: 12칸(순위·띠·출생연도·점수·한 줄)", len(sb["scenes"][0]["rows"]) == 12
   and set(sb["scenes"][0]["rows"][0]) == {"rank", "animal", "years", "score", "line"})
ck("풀이 장면: 4줄 · 한 줄 정리 · 재미 고지", len(sb["scenes"][1]["items"]) == 4 and sb["scenes"][1]["verdict"]
   and "재미" in sb["scenes"][1]["foot"])
desc = P.description(dt.date(2026, 10, 8))
ck("설명란: 12띠 이유 전부 · 순위 정한 방법 · 재미 고지", all(f"{a}띠(" in desc for a in FC.ANIMALS)
   and "순위는 이렇게 정했어요" in desc and "재미로" in desc)
ck("제목: 일진 이름 + 45~96년생", "을묘일 풀이" in P.title(dt.date(2026, 10, 8)) and P.title(dt.date(2026, 10, 8)).endswith("45~96년생 전부"))
ck("배경 그림: 글자·간판 금지 꼬리", sb["thumbnail_hook"].endswith(P.HOOK_TAIL))
ck("받침 조사: 용과·쥐와·호랑이와", P.josa("용", "과", "와") == "용과" and P.josa("쥐", "과", "와") == "쥐와" and P.josa("호랑이", "과", "와") == "호랑이와")

print("── 화면 배치(쇼츠 버튼 열 x 960 · 제목 자리 y 1500) ──")
import motion_short as M  # noqa: E402
sc0 = dict(P.pulli_storyboard(dt.date(2026, 10, 12))["scenes"][0], start=0.0, clip=7.0)
html0 = M.scene_html(0, sc0, P.ACCENT)
boxes = [tuple(map(float, b)) for b in re.findall(
    r'class="cell[^"]*"[^>]*left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px', html0)]
ck("표 12칸 · 오른쪽 끝 960 이하 · 아래 끝 1500 이하", len(boxes) == 12 and max(x + w for x, _, w, _ in boxes) <= 960
   and max(y + h for _, y, _, h in boxes) <= 1500, (max(x + w for x, _, w, _ in boxes), max(y + h for _, y, _, h in boxes)))
fpx = {k: int(v) for k, v in re.findall(r"\.cell \.(rk|nm|sc|yr|ln)\{[^}]*?font-size:(\d+)px", M.CSS_CARD)}
ck("글자 크기는 그대로(띠 58 · 점수 44 · 출생연도 30 · 한 줄 34 · 순위 36)",
   fpx == {"rk": 36, "nm": 58, "sc": 44, "yr": 30, "ln": 34}, fpx)

print("── 파이프라인 연결 ──")
ck("아침 운세 표(fortune_card)가 풀이형 표를 덮어쓰지 않는다", not FC.use_card(sb))
rp = open(os.path.join(HERE, "run_pipeline.py"), encoding="utf-8").read()
ck("run_pipeline: 재생목록·카피 점검 제외·제목/설명", "PULLI_PLAYLIST" in rp and "pulli_card.is_pulli(sb)" in rp and "pulli_card.meta(sb)" in rp)
path = P.path_for(dt.date(2026, 10, 8), root="/repo")
ck("파일 경로 = output/news/<날짜>_fortune_pulli_storyboard.json (shorts.yml 이 집는다)",
   path.replace("\\", "/").endswith("output/news/2026-10-08_fortune_pulli_storyboard.json") and re.search(r"_storyboard\.json$", path))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
