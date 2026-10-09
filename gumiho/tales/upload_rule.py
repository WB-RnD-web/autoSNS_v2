#!/usr/bin/env python3
"""Nine Tails 쇼츠 업로드(옛 RULES + 새 라인업 survival·compare·liminal). ★기본은 비공개(private).

    python gumiho/tales/upload_rule.py output/tales_rules/R101_mariana-trench-floor.json
    python gumiho/tales/upload_rule.py <script.json> --publish-at 2026-10-13T20:00:00Z

새 라인업(2026-10-13~, rules.py 머리말): 공개 시각은 편마다 — A survival 20:00 UTC(16:00 ET) · B compare/liminal 23:30 UTC
  (19:30 ET), 배정일(=쓰는 날) 다음 날. 재생목록도 편마다(How Long Would You Last? · Ranked: Biggest, Heaviest, Fastest ·
  Liminal Rules).
  실사 그림이라 'altered or synthetic content' 표시 — upload_tale.status_body 가 containsSyntheticMedia=true 를 넣는다
  (그 함수는 롱폼과 같이 쓴다 — 여기서 고치지 않는다). madeForKids=false 도 거기서.

공개 방식(레포 변수 RULES_PUBLISH, 없으면 TALES_PUBLISH 를 따른다 — 워크플로가 넘긴다):
  private   비공개로만 올린다
  scheduled 비공개 + 예약 공개(배정일 다음 날 13:00 UTC = 한국 22:00 · 미 동부 오전 9시 — publish_time)
    2026-10-09: 21:00 UTC(06:00 KST) 공개 첫 편 FBrojHee6tA 가 5시간 반 0회, 13:00 UTC 공개 쇼츠는 수백~2천 회
    → 비교가 되게 다른 쇼츠와 같은 13:00 UTC 로 맞춘다(공개 시각이 결정적이라는 공식 근거는 없다).
올리지 않는 경우(코드로 막는다): mock 렌더 · 대본 검사 실패 · 이미 올린 편(ledger) · ★채널에 같은 제목이 이미 있음.
  (Actions 캐시는 브랜치마다 따로라 ledger 만 믿으면 두 번 올라간다 — 2026-10-03 제주 파도 영상 중복의 교훈)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import rules as RU  # noqa: E402

PLAYLIST = "Nine Tails RULES — East Asian Rule Horror (Don't Break Them)"
PLAYLIST_DESC = ("Korean, Japanese and Chinese legends turned into rules you must follow. A new rule horror Short every day, "
                 "judged by Gumi, a 1,000-year-old nine-tailed fox. 13+.")
CHANNEL_URL = "https://www.youtube.com/@NineTailsTales"


def publish_time(now: dt.datetime | None = None, hhmm: str | None = None, day: dt.date | None = None) -> str:
    """예약 공개 시각(UTC, 카탈로그 publish_utc = 13:00).

    day(그 편 배정일)를 주면 그다음 날 hhmm. 루틴 12:00 UTC → 업로드 12:20 무렵(10/8·10/9 실측 12:20·12:22)이라
      그날 13:00 은 40분 여유뿐 — Spark 대기열이 길면 넘겨 하루씩 밀리고 다음 편과 겹친다 → 늘 다음 날(편마다 한 칸).
    그 칸이 지났거나 1시간 안이면(재실행·아주 늦은 렌더) 지금 + 1시간(15분 단위 올림) — ★다음 날로 미루지 않는다.
      (10/10 검수: 다음 날 같은 시각으로 미루면 다음 편 칸에 겹친다. 같은 날 늦게 나가야 'TOMORROW' 예고도 대충 맞다)
    day 없이(옛 수동 경로)는 지금 기준 다음 hhmm.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    h, m = (int(x) for x in (hhmm or RU.catalog().get("publish_utc", "13:00")).split(":"))
    if day:
        t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        if t >= now + dt.timedelta(hours=1):
            return t.strftime("%Y-%m-%dT%H:%M:%SZ")
        late = now + dt.timedelta(hours=1)
        day0 = late.replace(hour=0, minute=0, second=0, microsecond=0)
        q = math.ceil((late - day0).total_seconds() / 900) * 900          # 15분 단위로 올림
        return (day0 + dt.timedelta(seconds=q)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t < now + dt.timedelta(hours=1):
        t += dt.timedelta(days=1)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def when(s: dict, now: dt.datetime | None = None, allow_retired: bool = False) -> str:
    """대본 → 예약 공개 시각. 새 형식은 슬롯(A 20:00 · B 23:30 UTC), 옛 RULES 는 13:00 UTC — 둘 다 배정일 다음 날.
    옛 설화 RULES 는 10/9 로 끝났다 — allow_retired 없이는 시각을 주지 않는다(올리지 않는다)."""
    if s.get("format") in RU.NEW_FORMATS:
        sc = RU.shorts()
        e = RU.entry(s["id"], sc)
        return publish_time(now, hhmm=RU.slot_of(e, sc)[1], day=RU.assign_date(e, sc))
    if not allow_retired and RU.retired((now or dt.datetime.now(dt.timezone.utc)).date()):
        raise RuntimeError(RU.RETIRED_MSG)
    return publish_time(now, day=RU.day_of(s["id"]))


def on_channel(yt, title: str) -> str | None:
    """채널 최근 업로드 50개 중 같은 제목이 있으면 그 영상 id(비공개·예약 포함 — 내 토큰이라 보인다)."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    r = yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute()
    for it in r.get("items", []):
        if it["snippet"]["title"].strip().lower() == title.strip().lower():
            return it["snippet"]["resourceId"]["videoId"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "gumiho", "rules"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "gumiho", "rules_ledger.json"))
    ap.add_argument("--mode", default=os.environ.get("RULES_PUBLISH") or os.environ.get("TALES_PUBLISH") or "private",
                    choices=["private", "scheduled"])
    ap.add_argument("--publish-at")
    ap.add_argument("--allow-retired", action="store_true", help="옛 설화 RULES(10/9 끝)를 일부러 올릴 때만 — 워크플로는 쓰지 않는다")
    a = ap.parse_args()

    with open(a.script, encoding="utf-8") as f:
        s = json.load(f)
    errs = RU.check(s, allow_retired=a.allow_retired)
    if errs:
        print("::error::대본 검사 실패 — 올리지 않는다\n  " + "\n  ".join(errs))
        return 2
    stem = RU.stem_of(s)
    with open(os.path.join(a.renders, f"{stem}_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    if rm.get("mock"):
        print("::error::mock 렌더(가짜 그림·목소리)는 올리지 않는다")
        return 2
    led = {}
    if os.path.exists(a.ledger):
        with open(a.ledger, encoding="utf-8") as f:
            led = json.load(f)
    if led.get(stem, {}).get("short"):
        print(f"⏭️ 이미 올림(ledger): {led[stem]['short']}")
        return 0
    md = RU.meta(s, CHANNEL_URL)
    import upload_tale as UT
    import upload_youtube_novel as U
    yt = U.get_service()
    dup = on_channel(yt, md["title"])
    if dup:
        print(f"⏭️ 채널에 같은 제목이 이미 있다 — 올리지 않는다: https://youtu.be/{dup}")
        led[stem] = {"short": f"https://youtu.be/{dup}", "title": md["title"], "found": True}
        _save(a.ledger, led)
        return 0
    at = a.publish_at or (when(s, allow_retired=a.allow_retired) if a.mode == "scheduled" else None)
    facts = UT.shorts_facts(rm["video"])
    vid = UT.insert(yt, rm["video"], md, "private", at)
    # 0회 점검용: 공개 시각 + 쇼츠 판정 조건(세로·3분 이하·madeForKids=false)을 ledger 에 남긴다(2026-10-09)
    done = {"short": f"https://youtu.be/{vid}", "title": md["title"], "publish_at": at, "shorts": facts,
            "format": s.get("format")}
    print(f"✅ 쇼츠 {done['short']} · {'예약 ' + at if at else '비공개'} · {UT.facts_line(facts)}")
    led[stem] = done
    _save(a.ledger, led)
    done["langs"] = UT.localize(vid, md["title"], md["description"])
    try:
        name, desc = RU.playlist_for(s) or (PLAYLIST, PLAYLIST_DESC)     # 새 형식은 시리즈별 재생목록
        pid = U.ensure_playlist(yt, name, desc, privacy="public")
        U.add_to_playlist(yt, pid, vid)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 재생목록 실패(업로드는 성공): {e}")
    led[stem] = done
    _save(a.ledger, led)
    print(json.dumps({stem: done}, ensure_ascii=False))
    return 0


def _save(path: str, led: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
