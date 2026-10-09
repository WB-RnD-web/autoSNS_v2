#!/usr/bin/env python3
"""'내 것 찾기' 표(name_card) 회귀 테스트.

    python pipeline/test_name_card.py
"""
from __future__ import annotations
import datetime as dt
import json
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
        elif slot == "year":
            ok = [c["big"] for c in cells] == [f"{n}년생" for n in range(10)]
            ok &= sorted(int(c["small"][:-1]) for c in cells) == list(range(1, 11))
            ok &= sum(c["hi"] for c in cells) == 3 and all(int(c["small"][:-1]) <= 3 for c in cells if c["hi"])
        elif slot == "lunar":
            ok = [c["big"] for c in cells] == [N.lunar_days(n) for n in N.LUNAR_DIGITS] and len(cells) == 10
            ok &= sorted(int(c["small"][:-1]) for c in cells) == list(range(1, 11))
            ok &= sum(c["hi"] for c in cells) == 3 and all(int(c["small"][:-1]) <= 3 for c in cells if c["hi"])
            ok &= "31" not in " ".join(c["big"] for c in cells)          # 음력엔 31일이 없다
        elif slot == "surname":
            ok = [c["big"] for c in cells] == sorted(f"{x}씨" for x in N.SURNAMES) and len(cells) == 20
            ok &= sorted(int(c["small"][:-1]) for c in cells) == list(range(1, 21))
            ok &= sum(c["hi"] for c in cells) == 3 and all(int(c["small"][:-1]) <= 3 for c in cells if c["hi"])
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
ck("하루 네 표(해 끝자리·성씨·태어난 달·12시 띠)의 주제가 전부 다르다(60일)",
   all(len({N.year_theme(x)["id"], N.surname_theme(x)["id"], N.month_theme(x)["id"], T.theme_for(x)["id"]}) == 4
       for x in (d0 + dt.timedelta(days=i) for i in range(60))))
ck("천간: 1984 갑 · 1990 경 · 1955 을 · 1963 계(끝자리 → 천간)",
   dict((n, g) for n, g, _ in N.STEMS)[4] == "갑" and dict((n, g) for n, g, _ in N.STEMS)[0] == "경"
   and dict((n, g) for n, g, _ in N.STEMS)[5] == "을" and dict((n, g) for n, g, _ in N.STEMS)[3] == "계")
ck("성씨 20개 · 겹치지 않음", len(N.SURNAMES) == 20 and len(set(N.SURNAMES)) == 20)

print("── 메타·경로·파이프라인 연결")
sb = N.storyboard(d0, "am")
ck("topic·slot·_min_total", sb["topic"] == N.TOPIC and sb["slot"] == "am" and sb["_min_total"] >= 8)
ck("ledger 키에 슬롯(하루 두 편이 서로 막지 않게)",
   N.path_for(d0, "am").endswith("2026-10-02_fortune_name_am_storyboard.json")
   and N.path_for(d0, "pm").endswith("2026-10-02_fortune_name_pm_storyboard.json"))
m = N.meta(sb)
ck("meta 제목 95자 이내·설명에 '재미로'", len(m["title"]) <= 95 and "재미로" in m["description"])
ck("fortune_card 아침 표가 이 토픽을 가로채지 않는다", not FC.use_card(sb))
ck("슬롯 자동: 7:40 year · 9:40 am · 13:40 surname · 15:40 pm",
   [N.slot_now(dt.datetime(2026, 10, 2, h, 40, tzinfo=N.KST)) for h in (7, 9, 13, 15)]
   == ["year", "am", "surname", "pm"])
ck("다섯 칸 저장 경로가 서로 다르다(서로 막지 않게)",
   len({N.path_for(d0, sl) for sl in N.SLOTS}) == len(N.SLOTS) == 5)
import run_pipeline as RP  # noqa: E402
ck("재생목록 '내 것 찾기'", RP.playlist_for(N.TOPIC) == (RP.NAME_PLAYLIST, RP.NAME_PLAYLIST_DESC))
ck("카테고리 24(엔터테인먼트)", RP.category_for(N.TOPIC) == "24")

print("── 화면(grid 장면)")
for slot, n in (("am", N.NAME_CELLS), ("pm", 12), ("year", 10), ("surname", 20), ("lunar", 10)):
    s = N.storyboard(d0, slot)
    sc = dict(s["scenes"][0], start=0, clip=9.0, _spk=0)
    html = M.build_html([sc], 9.0, acc=s["accent"], bg=False)
    html = html if isinstance(html, str) else html[0]
    ck(f"{slot}: 칸 {n}개 · 제목 두 줄 · 각주", html.count('class="gcell') == n and 'class="l2"' in html
       and "gfoot" in html, html.count('class="gcell'))
    cw, ch, xy = M.grid_layout(n, sc["cols"])
    ck(f"{slot}: 표가 오른쪽 버튼 열(x 960)·아래 22%(y 1500) 안 침범",
       max(x for x, _ in xy) + cw <= 961 and max(y for _, y in xy) + ch <= 1500, (cw, ch))
    fns = [int(m) for m in re.findall(r'class="gn" style="bottom:\d+px;font-size:(\d+)px"', html)]
    longest = max(sum(0.6 if c_.isascii() else 1.0 for c_ in x["note"]) for x in sc["cells"])
    ck(f"{slot}: 한 줄 글자가 칸 안에 든다(…로 안 잘림)", fns and fns[0] * longest <= cw - 30, (fns[:1], longest, cw))
ck("진행자는 표 화면에 서지 않는다(grid)", "grid" in M.build_motion.__code__.co_consts
   or "grid" in open(M.__file__, encoding="utf-8").read().split("pr_on = presenter_on", 1)[1][:200])

print("── 하루 한 칸 순환(10/8~, 10/7 진단) ──")
import datetime as _dt  # noqa: E402
import tempfile as _tf  # noqa: E402
_d0 = _dt.date(2026, 10, 8)
_week = [N.slot_of_day(_d0 + _dt.timedelta(days=k)) for k in range(10)]
ck("10/8 이름 · 10/9 태어난 달 · 10/10 해 끝자리 · 10/11 성씨 · 10/12 음력 생일 끝자리 · 5일마다 반복",
   _week == ["am", "pm", "year", "surname", "lunar"] * 2, _week)
ck("10/7 까지는 네 칸 모두(순환 전)", N.slot_of_day(_dt.date(2026, 10, 7)) is None
   and all(N.is_slot_day(_dt.date(2026, 10, 7), s) for s in N.SLOTS))
ck("하루에 정확히 한 칸만", all(sum(N.is_slot_day(_d0 + _dt.timedelta(days=k), s) for s in N.SLOTS) == 1 for k in range(28)))
_seen = {s: [N.storyboard(_d0 + _dt.timedelta(days=k), s)["theme"] for k in range(40) if N.slot_of_day(_d0 + _dt.timedelta(days=k)) == s]
         for s in N.SLOTS}
ck("칸마다 다음 차례엔 다른 테마(같은 표가 연달아 안 나온다)", all(a != b for v in _seen.values() for a, b in zip(v, v[1:])), _seen)
with _tf.TemporaryDirectory() as _tmp:
    _p = os.path.join(_tmp, "x.json")
    N.main(["make", "--date", "2026-10-08", "--slot", "year", "--out", _p])
    _skip = not os.path.exists(_p)
    N.main(["make", "--date", "2026-10-08", "--slot", "am", "--out", _p])
    ck("그날 칸이 아니면 make 가 안 쓰고, 그날 칸이면 쓴다(트리거는 '파일 없음 = 건너뜀')", _skip and os.path.exists(_p))
    _p2 = os.path.join(_tmp, "y.json")
    N.main(["make", "--date", "2026-10-08", "--slot", "year", "--out", _p2, "--force"])
    ck("--force 면 그날 칸이 아니어도 쓴다(견본용)", os.path.exists(_p2))

print("── 음력 생일 끝자리(10/9 시장 조사 · 15:40 트리거를 그날만 빌려 쓴다) ──")
ck("음력 끝자리 날엔 15:40(pm) 트리거가 lunar 를 낸다 · 다른 날엔 그대로",
   N.resolve_slot(_dt.date(2026, 10, 12), "pm") == "lunar" and N.resolve_slot(_dt.date(2026, 10, 13), "pm") == "pm"
   and N.resolve_slot(_dt.date(2026, 10, 12), "am") == "am")
with _tf.TemporaryDirectory() as _tmp:
    _p = os.path.join(_tmp, "l.json")
    N.main(["make", "--date", "2026-10-12", "--slot", "pm", "--out", _p])
    _sb = json.load(open(_p, encoding="utf-8")) if os.path.exists(_p) else {}
    ck("트리거 그대로(--slot pm) 10/12 엔 음력 끝자리 표가 써진다", _sb.get("slot") == "lunar"
       and _sb["scenes"][0]["title"] == "음력 생일 끝자리로 보는", _sb.get("slot"))
    ck("path 도 같은 칸을 가리킨다(트리거 'test -f' 가 맞는 파일을 본다)",
       N.path_for(_dt.date(2026, 10, 12), N.resolve_slot(_dt.date(2026, 10, 12), "pm")).endswith("2026-10-12_fortune_name_lunar_storyboard.json"))
_l = N.storyboard(_dt.date(2026, 10, 12), "lunar")
ck("음력 끝자리 표: 기준 줄 · 설명란 안내 · 제목 앞머리(형식 집계)",
   _l["scenes"][0].get("basis") and "음력에는 31일이 없어요" in _l["platforms"]["youtube"]["description"]
   and N.title(_dt.date(2026, 10, 12), "lunar").startswith("음력 생일 끝자리로 보는"))
ck("모든 칸 제목에 날짜(같은 테마가 돌아와도 제목이 똑같지 않게 — 재탕 편이 꺼졌다)",
   all("10월 12일" in N.title(_dt.date(2026, 10, 12), sl) for sl in N.SLOTS))


print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
