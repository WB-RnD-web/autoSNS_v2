#!/usr/bin/env python3
"""렌더한 릴스 → 인스타그램(+선택: 쓰레드) 게시. ★기본은 dry-run — 아무것도 올리지 않고 무엇을 올릴지만 보여 준다.

    python insta/post_reel.py output/insta/2026-10-05_claude-routine-rules.json        # dry-run
    INSTA_PUBLISH=1 python insta/post_reel.py <script.json>                            # 실제 게시

실제 게시는 환경변수 INSTA_PUBLISH=1 일 때만(워크플로: 레포 변수 INSTA_PUBLISH=1 + routine/insta push 일 때만 넘긴다).
쓰레드도 올리려면 INSTA_THREADS=1.

올리지 않는 경우(코드로 막는다)
  · 대본 검사 실패 · mock 렌더나 mock 숫자(가짜 목소리·그림·통계)
  · 이미 올린 편(ledger — Actions 캐시 · insta/posted.json — 레포 기록) · 같은 날짜에 이미 한 편 올림
  · 대본 날짜가 오늘(KST)이나 어제가 아님 — 옛 원고가 뒤늦게 밀려와(미아 복구 등) 엉뚱한 날 게시되는 것 방지
게시 경로(왕별이 쇼츠가 쓰던 것 그대로): Cloudinary(pipeline/host_video)로 공개 URL → upload_instagram.publish_reel
  (커버 = 첫 프레임: 두 줄 제목이 보이는 화면) → [INSTA_THREADS=1] upload_threads.publish_thread → 성공하면 Cloudinary 원본 삭제.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import insta as I  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
POSTED = os.path.join(HERE, "posted.json")


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip() in ("1", "true", "True", "yes")


def load_ledger(path: str) -> dict:
    led = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                led = json.load(f)
        except (OSError, json.JSONDecodeError):
            led = {}
    if os.path.exists(POSTED):                     # 로컬에서 손으로 올린 편 — 레포에 기록해 두고 다시 올리지 않는다
        with open(POSTED, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                led.setdefault(k, v)
    return led


def blockers(s: dict, path: str, meta: dict, led: dict, today: dt.date) -> list[str]:
    """게시하면 안 되는 이유(비었으면 게시 가능)."""
    why = [f"대본 검사: {e}" for e in I.check(s, path)]
    stem = f"{s['date']}_{s['topic']}"
    if meta.get("mock") or meta.get("stats_mock"):
        why.append("mock 렌더/숫자 — 게시하지 않는다")
    if stem in led:
        why.append(f"이미 올린 편: {stem}")
    if any(k.startswith(s["date"] + "_") for k in led if k != stem):
        why.append(f"{s['date']} 에 이미 다른 편을 올렸다(하루 한 편)")
    d = I._date(s["date"])
    if not (today - dt.timedelta(days=1) <= d <= today):
        why.append(f"대본 날짜 {d} 가 오늘({today})·어제가 아니다 — 늦게 도착한 원고는 올리지 않는다")
    if not os.path.exists(meta.get("video", "")):
        why.append("렌더된 영상이 없다")
    return why


def publish(meta: dict, stem: str, threads: bool) -> dict:
    import host_video
    out = {}
    pid = f"insta_{stem}"
    url = host_video.host(meta["video"], pid)
    if not url:
        raise SystemExit("❌ Cloudinary 자격증명 없음 — 공개 URL 을 만들 수 없어 게시 못 함")
    cover_pid = f"{pid}_cover"
    cover_url = host_video.host_image(meta["cover"], cover_pid) if meta.get("cover") else None
    ok = False
    try:
        import upload_instagram
        out["ig"] = upload_instagram.publish_reel(url, meta["caption"], cover_url=cover_url)
        ok = True
    except (Exception, SystemExit) as e:  # noqa: BLE001
        out["ig_error"] = str(e)[:300]
        print(f"::error title=Instagram 게시 실패::{str(e)[:300]}")
    if threads:
        try:
            import upload_threads
            out["threads"] = upload_threads.publish_thread(url, meta["threads"])
            ok = True
        except (Exception, SystemExit) as e:  # noqa: BLE001
            out["threads_error"] = str(e)[:300]
            print(f"::warning title=Threads 게시 실패::{str(e)[:300]}")
    if ok:                                         # 인스타·쓰레드는 게시 때 복사해 간다 → 원본은 지워 무료 한도를 아낀다
        host_video.cleanup(pid)
        if cover_url:
            host_video.cleanup(cover_pid, resource_type="image")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="릴스 게시(기본 dry-run)")
    ap.add_argument("script")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "insta_render"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "insta_render", "posted_ledger.json"))
    ap.add_argument("--today", help="오늘(KST) 덮어쓰기 — 테스트용")
    a = ap.parse_args()

    s = I.load(a.script)
    stem = f"{s['date']}_{s['topic']}"
    meta_path = os.path.join(a.renders, f"{stem}_meta.json")
    if not os.path.exists(meta_path):
        print(f"::error::렌더 메타 없음: {meta_path}")
        return 2
    meta = I.load(meta_path)
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(KST).date()
    led = load_ledger(a.ledger)
    why = blockers(s, a.script, meta, led, today)
    live = _on("INSTA_PUBLISH")
    threads = _on("INSTA_THREADS")
    print(f"── {stem} · {meta.get('sec')}초 · 진행자 {meta.get('host')} · 목소리 {meta.get('voice')}")
    print(f"   영상 {meta.get('video')}\n   커버 {meta.get('cover')}")
    print("── 캡션 ──\n" + meta.get("caption", "") + "\n──────────")
    if why:
        print("⛔ 게시 안 함:\n  " + "\n  ".join(why))
        return 0 if not live else (0 if any("이미" in w for w in why) else 1)
    if not live:
        print(f"🧪 dry-run — 게시하지 않았다(레포 변수 INSTA_PUBLISH=1 이면 게시{' + 쓰레드' if threads else ''})")
        return 0
    res = publish(meta, stem, threads)
    if not res.get("ig") and not res.get("threads"):
        return 1
    import ledger as ledgermod
    ledgermod.mark(led, s, res.get("ig") or res.get("threads"), "public", time.time(), a.ledger)
    print(f"✅ 게시: {json.dumps(res, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
