#!/usr/bin/env python3
"""인스타 '오늘의 골라보기' 편성·게시 — 날짜로 꼴을 정하고(로테이션), 하루 한 편만 올린다 (2026-10-07).

편성(코드가 정한다 — 쓰는 쪽이 고르지 않는다):
  FORMATS 를 START 부터 하루씩 돌린다: 10/8 그림 고르기 → 10/9 상식 퀴즈 → 10/10 타로 카드 → 10/11 밸런스 게임
  → 10/12 태어난 달 표 → 10/13 그림 고르기 …  (같은 꼴은 5일에 한 번 — 왕별이 10/7 교훈: 같은 꼴 매일은 피드가 덜 퍼뜨린다)
흐름:
  ① 로컬 예약 작업(insta-pick-daily, 매일 저녁) — 로컬 크롬으로 그 꼴의 요즘 뜨는 릴스를 몇 개 보고(하루 10건 안쪽),
     `next` 가 알려 준 꼴로 대본 JSON 을 새로 쓴다 → `pick_reel.py check` → routine/insta_pick 에 push
  ② insta-pick.yml(Actions) — 코드는 main, 대본은 routine/insta_pick 의 오늘 파일 → 렌더 → `post` 로 인스타 릴스 게시
게시 막기: 레포 변수 INSTA_PICK_PUBLISH=0 (기본: push 로 온 오늘 대본은 올린다 — 사용자 10/8 "매일 올려줘")

    python insta/pick_plan.py next [--date 2026-10-09]       # 오늘 꼴·파일 이름·견본·최근 주제(겹치지 않게)
    python insta/pick_plan.py targets [--date …]             # output/insta_pick 의 오늘 대본(워크플로가 쓴다)
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


def kind_for(d: dt.date) -> str:
    return FORMATS[(d - START).days % len(FORMATS)]


def scripts_on(d: dt.date, root: str = SCRIPTS) -> list[str]:
    return sorted(glob.glob(os.path.join(root, f"{d.isoformat()}_*.json")))


def recent(d: dt.date, root: str = SCRIPTS, n: int = 40) -> list[dict]:
    """지난 대본(오늘 전) — 같은 주제·같은 문제를 다시 쓰지 않게."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "*.json")), reverse=True):
        name = os.path.basename(p)
        if name[:10] >= d.isoformat():
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


def next_info(d: dt.date, root: str = SCRIPTS) -> dict:
    k = kind_for(d)
    return {"date": d.isoformat(), "kind": k, "label": LABEL[k], "file": f"output/insta_pick/{d.isoformat()}_{k}_<slug>.json",
            "exemplar": f"insta/samples/{EXEMPLAR[k]}.json", "writing": "insta/PICK_WRITING.md",
            "keywords": KEYWORDS[k], "already_written": bool(scripts_on(d, root)), "recent": recent(d, root)}


# ── 게시 ──────────────────────────────────────────────
def load_ledger(path: str = LEDGER) -> dict:
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def blockers(s: dict, meta: dict | None, led: dict, today: dt.date) -> list[str]:
    bad = []
    if s.get("date") != today.isoformat():
        bad.append(f"오늘({today}) 대본이 아니다: {s.get('date')}")
    else:
        d = dt.date.fromisoformat(s["date"])
        if s.get("kind") != kind_for(d):
            bad.append(f"오늘 꼴은 {kind_for(d)} — 대본은 {s.get('kind')}")
    if s.get("date") in led:
        bad.append(f"{s.get('date')} 는 이미 올렸다: {led[s['date']].get('media_id')}")
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
    led[s["date"]] = {"media_id": mid, "kind": s["kind"], "slug": s["slug"], "seconds": meta["seconds"],
                      "at": dt.datetime.now(KST).isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    json.dump(led, open(ledger, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ 인스타 '오늘의 골라보기' 게시: {stem} · media_id={mid}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 '오늘의 골라보기' 편성·게시")
    ap.add_argument("cmd", choices=["next", "targets", "post"])
    ap.add_argument("script", nargs="?")
    ap.add_argument("--date")
    ap.add_argument("--root", default=SCRIPTS)
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.cmd == "next":
        print(json.dumps(next_info(d, a.root), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "targets":
        print(" ".join(os.path.relpath(p, ROOT).replace("\\", "/") for p in scripts_on(d, a.root)[:1]))
        return 0
    if not a.script:
        ap.error("post 는 대본 경로가 필요하다")
    return post(a.script)


if __name__ == "__main__":
    sys.exit(main())
