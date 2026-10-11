#!/usr/bin/env python3
"""인스타 '오늘의 골라보기' 편성·게시 — 날짜·편(slot)으로 꼴을 정하고(로테이션), 편마다 한 번만 올린다 (2026-10-07).

편성(코드가 정한다 — 쓰는 쪽이 고르지 않는다):
  FORMATS 를 START 부터 한 편씩 돌린다: 10/8 그림 고르기 → 10/9 상식 퀴즈 → 10/10 타로 카드 → 10/11 밸런스 게임
  → 10/12 태어난 달 표 (여기까지 하루 한 편 = 저녁 편 b · 같은 꼴 연달아 금지 — 왕별이 10/7 교훈)
  ★10/11 사용자 "하루 2편 이상" → TWICE_FROM(10/13)부터 하루 두 편: 낮 편 a(12시대) · 저녁 편 b(7~8시대, 예전 그 자리).
    로테이션은 끊기지 않고 이어진다: 10/13 a 그림 고르기 · b 상식 퀴즈 → 10/14 a 타로 · b 밸런스 → 10/15 a 태어난 달 · b 그림 …
    (같은 날 두 편은 늘 다른 꼴 · 이어지는 두 편도 늘 다른 꼴 — 그래서 꼴만 보면 그날 어느 편인지 하나로 정해진다: slot_of)
  회차 번호도 편 순서대로: 10/8 = '오늘의 골라보기 #1' · 10/12 = #5 · 10/13 낮 = #6 · 10/13 저녁 = #7 (series_no)
  어느 편 차례인지(due_slot)도 코드가 정한다: KST NOON_UNTIL(16)시 전이면 낮 편, 뒤면 저녁 편.
  쓰레드(pick_threads)는 저녁 편만 따라간다 — 쓰레드 2주 시험(10/11~10/24) 조건을 그대로 두려고.
흐름:
  ① 대본 작가 — 클라우드 루틴(11:50 낮 편 · 19:50 저녁 편 대타) 또는 로컬 예약 작업(insta-pick-daily, 19:20 저녁 편, 크롬 서칭)이
     `next` 가 알려 준 편·꼴로 대본 JSON 을 쓴다 → `pick_reel.py check` → routine/insta_pick 에 push
  ② insta-pick.yml(Actions) — 코드는 main, 대본은 routine/insta_pick 의 오늘 파일 중 가장 늦은 편 → 렌더 → `post` 로 인스타 릴스 게시
게시 막기: 레포 변수 INSTA_PICK_PUBLISH=0 (기본: push 로 온 오늘 대본은 올린다 — 사용자 10/8 "매일 올려줘")

    python insta/pick_plan.py next [--date 2026-10-13] [--slot a|b]   # 지금 차례인 편·꼴·파일 이름·견본·최근 주제
    python insta/pick_plan.py targets [--date …]             # 오늘 대본 중 가장 늦은 편 하나(워크플로가 쓴다)
    python insta/pick_plan.py post <script.json>             # 렌더 결과를 게시(INSTA_PICK_PUBLISH=1 일 때만 실제로)
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

FORMATS = ("pick", "quiz", "card", "balance", "birth")
START = dt.date(2026, 10, 8)
TWICE_FROM = dt.date(2026, 10, 13)       # 10/11 사용자 "하루 2편 이상" — 이날부터 낮(a)·저녁(b) 두 편
SLOTS = ("a", "b")
SLOT_LABEL = {"a": "낮 편(12시대)", "b": "저녁 편(7~8시대)"}
NOON_UNTIL = 16                          # KST 이 시각 전에 부르면 낮 편 차례, 뒤면 저녁 편 차례
KST = dt.timezone(dt.timedelta(hours=9))
SCRIPTS = os.path.join(ROOT, "output", "insta_pick")
RENDERS = os.path.join(ROOT, "output", "insta_pick_render")
LEDGER = os.path.join(RENDERS, "posted.json")
EXEMPLAR = {"pick": "pick_door", "card": "pick_card", "quiz": "pick_quiz", "balance": "pick_balance", "birth": "pick_birth"}
LABEL = {"pick": "그림 고르기 심리테스트", "card": "타로 카드 고르기", "quiz": "상식 퀴즈", "balance": "밸런스 게임",
         "birth": "태어난 달 표"}
# 그날 꼴의 서칭 키워드(로컬 크롬 · 인스타 검색 상위 조회수) — 쓰는 쪽이 참고만 한다
KEYWORDS = {"pick": ["심리테스트", "성격테스트", "그림 고르기"], "card": ["타로", "타로 골라보세요", "오늘의 타로"],
            "quiz": ["상식 퀴즈", "넌센스 퀴즈", "퀴즈"], "balance": ["밸런스 게임", "둘 중 하나"],
            "birth": ["태어난 달", "생일 운세", "탄생월"]}


def kst_today() -> dt.date:
    return dt.datetime.now(KST).date()


def slots_on(d: dt.date) -> tuple[str, ...]:
    """그날 편들 — TWICE_FROM 전에는 저녁 편 하나(b), 뒤로는 낮·저녁 두 편."""
    return SLOTS if d >= TWICE_FROM else ("b",)


def _slot(d: dt.date, slot: str | None) -> str:
    sl = slot or slots_on(d)[0]
    if sl not in slots_on(d):
        raise ValueError(f"{d} 에는 {sl} 편이 없다(그날 편: {slots_on(d)})")
    return sl


def post_index(d: dt.date, slot: str | None = None) -> int:
    """START 부터 몇 번째 편인가(0부터) — 하루 한 편이던 날들 뒤로 하루 두 편이 끊김 없이 이어진다."""
    sl = _slot(d, slot)
    if d < TWICE_FROM:
        return (d - START).days
    return (TWICE_FROM - START).days + 2 * (d - TWICE_FROM).days + SLOTS.index(sl)


def kind_for(d: dt.date, slot: str | None = None) -> str:
    """그날 그 편의 꼴. slot 을 안 주면 그날 첫 편."""
    return FORMATS[post_index(d, slot) % len(FORMATS)]


def series_no(d: dt.date, slot: str | None = None) -> int:
    """'오늘의 골라보기 #N' — 10/8 이 #1, 편마다 하나씩 는다. 10/9: 매일 이어지는 시리즈로 보이게(캡션 첫 줄·커버 라벨)."""
    return post_index(d, slot) + 1


def slot_of(d: dt.date, kind: str) -> str | None:
    """그날 그 꼴은 어느 편인가 — 같은 날 두 편은 꼴이 늘 달라서 하나로 정해진다. 그날 꼴이 아니면 None."""
    return next((sl for sl in slots_on(d) if kind_for(d, sl) == kind), None)


def due_slot(d: dt.date, now: dt.datetime | None = None) -> str | None:
    """지금 쓸 차례인 편 — NOON_UNTIL 시 전이면 낮 편(없는 날이면 None = 쓸 차례 아님), 뒤면 저녁 편."""
    now = now or dt.datetime.now(KST)
    if now.astimezone(KST).hour < NOON_UNTIL:
        return "a" if "a" in slots_on(d) else None
    return "b"


def ledger_key(date: str, slot: str) -> str:
    """게시 ledger 열쇠 — 저녁 편은 예전처럼 날짜 그대로(쓰레드가 이 열쇠만 본다), 낮 편은 날짜+'a'."""
    return date if slot == "b" else f"{date}{slot}"


def _kind_of_file(p: str) -> str:
    parts = os.path.basename(p).split("_")
    return parts[1] if len(parts) >= 3 else ""


def scripts_on(d: dt.date, root: str = SCRIPTS) -> list[str]:
    return sorted(glob.glob(os.path.join(root, f"{d.isoformat()}_*.json")))


def script_for(d: dt.date, slot: str, root: str = SCRIPTS) -> str | None:
    """그날 그 편의 대본 파일(파일 이름의 꼴로 찾는다) — 없으면 None."""
    k = kind_for(d, slot)
    return next((p for p in scripts_on(d, root) if _kind_of_file(p) == k), None)


def latest_target(d: dt.date, root: str = SCRIPTS) -> str | None:
    """워크플로가 처리할 오늘 대본 — 있는 편 중 가장 늦은 편(저녁 push 때 낮 대본을 다시 집지 않게)."""
    for sl in reversed(slots_on(d)):
        p = script_for(d, sl, root)
        if p:
            return p
    return None


def recent(d: dt.date, root: str = SCRIPTS, n: int = 40, kind: str | None = None) -> list[dict]:
    """지난 대본(오늘 전 + 오늘의 다른 편) — 같은 주제·같은 문제를 다시 쓰지 않게."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "*.json")), reverse=True):
        name = os.path.basename(p)
        if name[:10] > d.isoformat() or (name[:10] == d.isoformat() and (kind is None or _kind_of_file(p) == kind)):
            continue
        try:
            s = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        item = {"date": s.get("date"), "kind": s.get("kind"), "slug": s.get("slug"), "headline": " / ".join(s.get("headline", []))}
        if s.get("kind") == "quiz":
            item["questions"] = [r.get("q") for r in s.get("rounds", [])]
        out.append(item)
        if len(out) >= n:
            break
    return out


def next_info(d: dt.date, root: str = SCRIPTS, slot: str | None = None, now: dt.datetime | None = None) -> dict:
    """지금 쓸 편 — slot 을 안 주면 due_slot(시각)으로. 쓸 차례가 아니면 due: false(아무것도 쓰지 않는다)."""
    sl = slot or due_slot(d, now)
    if sl is None or sl not in slots_on(d):
        return {"date": d.isoformat(), "due": False, "slot": sl, "already_written": False,
                "why": f"{d} 에는 낮 편이 없다 — 하루 두 편은 {TWICE_FROM} 부터(그 전엔 저녁 편 하나)"}
    k = kind_for(d, sl)
    return {"date": d.isoformat(), "due": True, "slot": sl, "slot_label": SLOT_LABEL[sl], "series_no": series_no(d, sl),
            "kind": k, "label": LABEL[k], "file": f"output/insta_pick/{d.isoformat()}_{k}_<slug>.json",
            "exemplar": f"insta/samples/{EXEMPLAR[k]}.json", "writing": "insta/PICK_WRITING.md",
            "keywords": KEYWORDS[k], "already_written": bool(script_for(d, sl, root)), "recent": recent(d, root, kind=k)}


# ── 게시 ──────────────────────────────────────────────
def load_ledger(path: str = LEDGER) -> dict:
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def blockers(s: dict, meta: dict | None, led: dict, today: dt.date) -> list[str]:
    bad = []
    sl = None
    if s.get("date") != today.isoformat():
        bad.append(f"오늘({today}) 대본이 아니다: {s.get('date')}")
    else:
        d = dt.date.fromisoformat(s["date"])
        sl = slot_of(d, s.get("kind", ""))
        if sl is None:
            bad.append(f"오늘 꼴은 {[kind_for(d, x) for x in slots_on(d)]} — 대본은 {s.get('kind')}")
    key = ledger_key(s.get("date", ""), sl or "b")
    if sl and key in led:
        bad.append(f"{s.get('date')} {SLOT_LABEL[sl]}은 이미 올렸다: {led[key].get('media_id')}")
    if not meta or not os.path.exists(meta.get("video", "")):
        bad.append("렌더 결과(영상)가 없다")
    elif not 8 <= float(meta.get("seconds", 0)) <= 60:
        bad.append(f"길이가 이상하다: {meta.get('seconds')}초")
    return bad


def post(path: str, renders: str = RENDERS, ledger: str = LEDGER, today: dt.date | None = None) -> int:
    s = json.load(open(path, encoding="utf-8"))
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    mp = os.path.join(renders, f"{stem}_meta.json")
    meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else None
    led = load_ledger(ledger)
    today = today or kst_today()
    bad = blockers(s, meta, led, today)
    if bad:
        print("⏭️ 게시 안 함:\n  " + "\n  ".join(bad))
        return 0 if any("이미 올렸다" in b for b in bad) else 1
    caption = meta["caption"][:2150]
    if os.environ.get("INSTA_PICK_PUBLISH", "0").strip() != "1":
        print(f"🔸 dry-run — INSTA_PICK_PUBLISH=1 이 아니라 올리지 않는다 · {stem} · {meta['seconds']}초\n{caption[:300]}…")
        return 0
    import host_video
    import upload_instagram as UI
    pid = f"insta_pick_{stem}"
    url = host_video.host(meta["video"], pid)
    cover = host_video.host_image(meta["cover"], pid + "_cover") if meta.get("cover") else None
    if not url:
        print("❌ 영상 공개 URL 실패(Cloudinary)")
        return 1
    try:
        mid = UI.publish_reel(url, caption, cover_url=cover)
    finally:
        host_video.cleanup(pid)
        if cover:
            host_video.cleanup(pid + "_cover", "image")
    sl = slot_of(dt.date.fromisoformat(s["date"]), s["kind"])
    led[ledger_key(s["date"], sl)] = {"media_id": mid, "kind": s["kind"], "slug": s["slug"], "slot": sl,
                                      "seconds": meta["seconds"], "at": dt.datetime.now(KST).isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    json.dump(led, open(ledger, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 인스타 '오늘의 골라보기' 게시: {stem} · media_id={mid}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 '오늘의 골라보기' 편성·게시")
    ap.add_argument("cmd", choices=["next", "targets", "post"])
    ap.add_argument("script", nargs="?")
    ap.add_argument("--date")
    ap.add_argument("--slot", choices=SLOTS, help="next: 이 편으로(안 주면 지금 시각으로 정한다)")
    ap.add_argument("--root", default=SCRIPTS)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "next":
        print(json.dumps(next_info(d, a.root, a.slot), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "targets":
        t = latest_target(d, a.root)
        print(os.path.relpath(t, ROOT).replace("\\", "/") if t else "")
        return 0
    if not a.script:
        ap.error("post 는 대본 경로가 필요하다")
    return post(a.script)


if __name__ == "__main__":
    sys.exit(main())
