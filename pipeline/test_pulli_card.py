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
    sb = P.storyboard(d)
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
