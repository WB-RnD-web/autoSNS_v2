#!/usr/bin/env python3
"""오디오 언어 되돌리기(1회성) — 한국어 음성인데 '영어(en-US)'로 바뀐 영상을 'ko' 로.

    python pipeline/fix_audio_lang.py              # 미리보기(바꾸지 않음)
    python pipeline/fix_audio_lang.py --apply      # 실제 수정(videos.update 50 units/편)

2026-09-30 확인: yt_i18n.localize 가 snippet 을 덮어쓰며 defaultAudioLanguage 를 빼먹어
한국어 음성 쇼츠·SCP 가 en-US 가 됐다. 그 기간 쇼츠는 0~183회, ko 로 돌아온 9/30 운세는 6시간 1,285회.

고르는 규칙(코드로 고정):
  - 제목에 한글이 있고, 소리 영상(ASMR·빗소리 등 말소리 없는 것)이 아니면 → 'ko'
  - 소리 영상·영어 제목 영상은 건드리지 않는다.
제목·설명·태그·카테고리·기본 언어는 읽은 그대로 다시 싣는다(현지화는 part 에 없어서 그대로 남는다).
"""
from __future__ import annotations

import argparse
import re
import sys

import yt_i18n

HANGUL = re.compile(r"[가-힣]")
SOUND = re.compile(r"ASMR|백색소음|빗소리|Sleep Sounds|White Noise", re.I)


def target(sn: dict) -> str | None:
    t = sn.get("title", "")
    if SOUND.search(t) or not HANGUL.search(t):
        return None
    return "ko"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200, help="최근 몇 편까지 볼지(쿼터: 수정 1편 50 units)")
    a = ap.parse_args()
    yt = yt_i18n._service(["novel", "forcessl"], [yt_i18n.SCOPE_MANAGE])
    if yt is None:
        print("::error::토큰 없음")
        return 1
    ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()["items"][0]
    print(f"채널: {ch['snippet']['title']}")
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while len(ids) < a.limit:
        kw = {"part": "contentDetails", "playlistId": up, "maxResults": 50}
        if tok:
            kw["pageToken"] = tok
        r = yt.playlistItems().list(**kw).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    ids = ids[: a.limit]
    todo = []
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[k:k + 50])).execute()["items"]:
            sn = v["snippet"]
            want = target(sn)
            if want and sn.get("defaultAudioLanguage") != want:
                todo.append((v["id"], sn, want))
    print(f"본 영상 {len(ids)}편 · 고칠 영상 {len(todo)}편 · 쿼터 약 {len(todo) * 50} units")
    done = 0
    for vid, sn, want in todo:
        print(f"  {vid} {sn.get('defaultAudioLanguage')} → {want} | {sn['title'][:50]}")
        if not a.apply:
            continue
        body = yt_i18n.snippet_for_update(sn)
        body["defaultAudioLanguage"] = want
        try:
            yt.videos().update(part="snippet", body={"id": vid, "snippet": body}).execute()
            done += 1
        except Exception as e:  # noqa: BLE001
            print(f"    ⚠️ 실패: {str(e)[:160]}")
    print(f"{'✅ 수정' if a.apply else '미리보기 — 수정 안 함'}: {done if a.apply else len(todo)}편")
    return 0


if __name__ == "__main__":
    sys.exit(main())
