#!/usr/bin/env python3
"""'내 것 찾기' 표(name_card) 회귀 테스트.

    python pipeline/test_name_card.py
"""
from __future__ import annotations
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHORTS_PAUSED_TOPICS", "")
import name_card as N         # noqa: E402
import theme_card as T        # noqa: E402
import fortune_card as FC     # noqa: E402
import motion_short as M      # noqa: E402

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


print("── 이름 글자 테마")
ids = [t["id"] for t in N.NAME_THEMES]
ck("테마 id 겹치지 않음", len(ids) == len(set(ids)), ids)
for th in N.NAME_THEMES:
    syl = [b[0] for b in th["bank"]]
    ck(f"[{th['id']}] 은행 {len(syl)}자 ≥ {N.NAME_CELLS}", len(syl) >= N.NAME_CELLS)
    ck(f"[{th['id']}] 한 테마 안에서 글자 안 겹침", len(syl) == len(set(syl)), [s for s in syl if syl.count(s) > 1])
    ck(f"[{th['id']}] 글자는 한글 한 자 · 한자 한 자 · 훈은 한글",
       all(len(s) == 1 and hangul(s) == 1 and len(h) == 1 and "一" <= h <= "鿿" and hangul(n) == len(n)
           for s, h, n in th["bank"]), th["bank"][:3])
    ck(f"[{th['id']}] 화면 제목 두 줄 각 {N.LINE_MAX}자 이내", hangul(th["l1"]) <= N.LINE_MAX and hangul(th["l2"]) <= N.LINE_MAX,
       (th["l1"], th["l2"]))
    text = " ".join([th["l1"], th["l2"], th["yt"]] + [n for _, _, n in th["bank"]])
    ck(f"[{th['id']}] 금지어 없음", not any(b in text for b in T.BANNED), [b for b in T.BANNED if b in text])

print("── 태어난 달 테마")
for th in T.THEMES:
    ck(f"[{th['id']}] 달 표 이름표 있음", th["id"] in N.MONTH_LABEL)
    lab = N.month_label(dt.date(2026, 10, 2), th)
    ck(f"[{th['id']}] 두 번째 줄 '{lab} 순위' {N.LINE_MAX}자 이내", hangul(lab + "순위") <= N.LINE_MAX, lab)

print("── 40일 표")
d0 = dt.date(2026, 10, 2)
seen_am, prev = set(), None
for i in range(40):
    d = d0 + dt.timedelta(days=i)
    for slot in N.SLOTS:
        sb = N.storyboard(d, slot)
        sc = sb["scenes"][0]
        cells = sc["cells"]
        if slot == "am":
            ok = len(cells) == N.NAME_CELLS and len({c["big"] for c in cells}) == N.NAME_CELLS
            ok &= [c["big"] for c in cells] == sorted(c["big"] for c in cells)
            seen_am.add(tuple(c["big"] for c in cells))
        else:
            ok = [c["big"] for c in cells] == [f"{m}월생" for m in range(1, 13)]
            ok &= sorted(int(c["small"][:-1]) for c in cells) == list(range(1, 13))
            ok &= sum(c["hi"] for c in cells) == 3 and all(int(c["small"][:-1]) <= 3 for c in cells if c["hi"])
        if not ok:
            ck(f"{d} {slot} 표 모양", False, cells[:3])
        text = " ".join([sc["title"], sc["title2"], sc["narration"], sb["platforms"]["youtube"]["title"],
                         sb["platforms"]["youtube"]["description"]] + [c["note"] for c in cells])
        if any(b in text for b in T.BANNED):
            ck(f"{d} {slot} 금지어", False, [b for b in T.BANNED if b in text])
        if len(sb["platforms"]["youtube"]["title"]) > 100:
            ck(f"{d} {slot} 제목 100자", False, sb["platforms"]["youtube"]["title"])
    if i == 0:
        prev = N.storyboard(d, "am")
ck("40일 오전 표 모두 정상(칸 24·글자 안 겹침·가나다순)", True)
ck("같은 테마라도 날마다 고르는 글자가 달라진다(같은 표 되풀이 방지)", len(seen_am) >= 35, len(seen_am))
ck("같은 날짜·슬롯이면 늘 같은 표", N.storyboard(d0, "am") == prev)
ck("오후 달 표 테마는 같은 날 12시 띠 표와 다르다",
   all(N.month_theme(d0 + dt.timedelta(days=i))["id"] != T.theme_for(d0 + dt.timedelta(days=i))["id"] for i in range(30)))

print("── 메타·경로·파이프라인 연결")
sb = N.storyboard(d0, "am")
ck("topic·slot·_min_total", sb["topic"] == N.TOPIC and sb["slot"] == "am" and sb["_min_total"] >= 8)
ck("ledger 키에 슬롯(하루 두 편이 서로 막지 않게)",
   N.path_for(d0, "am").endswith("2026-10-02_fortune_name_am_storyboard.json")
   and N.path_for(d0, "pm").endswith("2026-10-02_fortune_name_pm_storyboard.json"))
m = N.meta(sb)
ck("meta 제목 95자 이내·설명에 '재미로'", len(m["title"]) <= 95 and "재미로" in m["description"])
ck("fortune_card 아침 표가 이 토픽을 가로채지 않는다", not FC.use_card(sb))
ck("슬롯 자동: 9시 40분 am · 15시 40분 pm",
   N.slot_now(dt.datetime(2026, 10, 2, 9, 40, tzinfo=N.KST)) == "am"
   and N.slot_now(dt.datetime(2026, 10, 2, 15, 40, tzinfo=N.KST)) == "pm")
import run_pipeline as RP  # noqa: E402
ck("재생목록 '내 것 찾기'", RP.playlist_for(N.TOPIC) == (RP.NAME_PLAYLIST, RP.NAME_PLAYLIST_DESC))
ck("카테고리 24(엔터테인먼트)", RP.category_for(N.TOPIC) == "24")

print("── 화면(grid 장면)")
for slot, n in (("am", N.NAME_CELLS), ("pm", 12)):
    s = N.storyboard(d0, slot)
    sc = dict(s["scenes"][0], start=0, clip=9.0, _spk=0)
    html = M.build_html([sc], 9.0, acc=s["accent"], bg=False)
    html = html if isinstance(html, str) else html[0]
    ck(f"{slot}: 칸 {n}개 · 제목 두 줄 · 각주", html.count('class="gcell') == n and 'class="l2"' in html
       and "gfoot" in html, html.count('class="gcell'))
    cw, ch, xy = M.grid_layout(n, sc["cols"])
    ck(f"{slot}: 표가 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 침범",
       max(x for x, _ in xy) + cw <= 961 and max(y for _, y in xy) + ch <= 1500, (cw, ch))
ck("진행자는 표 화면에 서지 않는다(grid)", "grid" in M.build_motion.__code__.co_consts
   or "grid" in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1][:200])

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
