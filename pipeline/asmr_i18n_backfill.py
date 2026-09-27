#!/usr/bin/env python3
"""이미 올라간 ASMR 롱폼에 영어 제목·설명(현지화)을 소급해 붙인다 — 1회성.

2026-09-27 스튜디오 실측: ASMR 영상 전부 '동영상 언어' 미설정·현지화 0개였다.
PR #68 부터 새 ASMR 은 자동으로 붙지만 기존 영상은 그대로라 이걸로 한 번 채운다.

하는 일 (영상 1편당 videos.list 1 + videos.update 50 units):
  ① 내 채널 업로드 목록에서 30분 이상 영상만 추린다
  ② 한국어 제목에서 테마 이름을 찾아(아래 KO_EN, 긴 것부터) 영어 이름으로 바꾼다 — 못 찾으면 건너뛴다
  ③ 이미 'en' 현지화가 있으면 건너뛴다(여러 번 돌려도 안전)
  ④ 기본 언어를 'ko' 로 두고 en 현지화를 추가한다(yt_i18n.localize — 제목·설명 원문은 그대로)

  python asmr_i18n_backfill.py            # 미리보기(바꾸지 않음)
  python asmr_i18n_backfill.py --apply    # 실제 적용
"""
from __future__ import annotations
import argparse
import re
import sys

import config
import run_asmr as R
import yt_i18n

# 한국어 제목 속 테마 → 영어 슬러그(english_name 이 'Calm Ocean Waves' 처럼 바꾼다). 긴 것부터 검사.
KO_EN = [
    ("잔잔한 파도", "calm-ocean-waves"), ("얼음 깨지는", "ice-cracking"),
    ("벽난로", "crackling-fireplace"), ("캠프파이어", "campfire-night"), ("모닥불", "campfire-night"),
    ("키보드", "keyboard-typing"), ("풀벌레", "summer-night-crickets"),
    ("시냇물", "babbling-brook"), ("계곡", "mountain-stream"), ("눈 오는 밤", "snowy-night"),
    ("도서관", "quiet-library-at-night"), ("미용실", "hair-salon"),
    ("창가 빗소리", "rain-on-the-window"), ("숲속 빗소리", "rain-in-the-forest"),
    ("빗소리", "rain-sounds"), ("파도", "ocean-waves"), ("종이", "paper-crumpling"),
]
_ISO = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso_sec(s: str) -> int:
    m = _ISO.fullmatch(s or "")
    if not m:
        return 0
    h, mi, se = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + se


def slug_for(title: str) -> str | None:
    for ko, slug in KO_EN:
        if ko in title:
            return slug
    return None


def english_for(title: str, seconds: int) -> dict | None:
    slug = slug_for(title)
    if not slug:
        return None
    # narration_text 를 비워 두지 않는다 — 예전 ASMR 은 낮은 나레이션이 있었을 수 있어
    # 'No talking' 을 약속하면 안 된다.
    spec = {"theme_id": slug, "narration_text": "?", "platforms": {"youtube": {"title": title}}}
    return R.english_localization(spec, seconds)


def uploads(yt) -> list[str]:
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    print(f"채널: {ch['snippet']['title']} ({ch['id']})")
    pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=pl, maxResults=50,
                                    pageToken=tok).execute()
        ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
        tok = r.get("nextPageToken")
        if not tok:
            return ids


def main() -> int:
    ap = argparse.ArgumentParser(description="ASMR 영어 제목 소급")
    ap.add_argument("--apply", action="store_true", help="실제로 적용(없으면 미리보기)")
    ap.add_argument("--min-min", type=int, default=30, help="이 분 이상 영상만")
    a = ap.parse_args()
    config.load_dotenv()
    yt = yt_i18n._service(["novel", "forcessl", "shorts"], [yt_i18n.SCOPE_MANAGE])
    if yt is None:
        print("[stop] 토큰 없음(token_novel.json)")
        return 1
    ids = uploads(yt)
    print(f"업로드 {len(ids)}편 검사 · {'적용' if a.apply else '미리보기'}\n")
    todo, skipped = [], []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,contentDetails,localizations",
                             id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            sec = iso_sec(v["contentDetails"].get("duration", ""))
            if sec < a.min_min * 60:
                continue
            title = v["snippet"]["title"]
            if "en" in (v.get("localizations") or {}):
                skipped.append((v["id"], title, "이미 en 있음"))
                continue
            en = english_for(title, sec)
            if not en:
                skipped.append((v["id"], title, "테마 매핑 없음"))
                continue
            todo.append((v["id"], title, en, sec))
    for vid, title, en, sec in todo:
        print(f"  {vid}  {sec // 3600}h{sec % 3600 // 60:02d}m  {title}\n      → {en['title']}")
    for vid, title, why in skipped:
        print(f"  건너뜀 {vid}  {title}  ({why})")
    print(f"\n대상 {len(todo)}편 · 건너뜀 {len(skipped)}편 · 예상 쿼터 {len(todo) * 51} units")
    if not a.apply:
        print("미리보기만 했다 — 적용하려면 --apply")
        return 0
    ok = 0
    for vid, title, en, _ in todo:
        done = yt_i18n.localize(vid, langs=["en"], localizations={"en": en})
        ok += bool(done)
    print(f"\n적용 {ok}/{len(todo)}")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
