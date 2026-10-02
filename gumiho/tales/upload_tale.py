#!/usr/bin/env python3
"""Nine Tails Tales 업로드 — 본편 + 쇼츠. ★기본은 비공개(private).

    python gumiho/tales/upload_tale.py <script.json> --renders output/gumiho/tales
    python gumiho/tales/upload_tale.py <script.json> --publish-at 2026-10-10T15:00:00Z   # 예약 공개(그때까지 비공개)

공개 방식은 레포 변수 TALES_PUBLISH 로 정한다(워크플로가 넘긴다):
  private   (기본) 비공개로만 올린다 — 사람이 스튜디오에서 보고 공개
  scheduled 비공개 + 예약 공개(다음 토요일 15:00 UTC = 미국 동부 오전 11시·한국 자정)
올리지 않는 경우(코드로 막는다): mock 렌더 · 이미 올린 편(ledger) · 대본 검사 실패.
토큰: YT_TOKEN_NOVEL 이 가리키는 파일(워크플로가 시크릿 YT_TOKEN_JSON_GUMIHO 로 만든다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import tales as T  # noqa: E402

# 현지화: 그 나라 사용자에게 그 나라 말 제목·설명이 뜬다(videos.update 50 units, 번역은 Spark gemma — 무료)
LANGS = [x.strip() for x in os.environ.get("TALES_LANGS", "es,pt,id,ja,ko,de,fr,vi").split(",") if x.strip()]
# ★이름을 바꾸면 ensure_playlist 가 못 찾고 새 목록을 만든다 — 스튜디오/API 에서 바꾼 이름과 같아야 한다(2026-09-30 변경).
PLAYLIST = "Every Tale: Korean Folklore, Myths & Ghost Stories | Nine Tails Tales"
PLAYLIST_DESC = ("Every tale Gumi, a 1,000-year-old gumiho (nine-tailed fox), has told so far, in order. "
                 "Korean folklore, Japanese and Chinese legends, monsters and ghost stories. A new tale every Saturday.")
URL_RE = re.compile(r"https?://\S+|youtu\.be/\S+")


def protect_urls(text: str) -> tuple[str, list[str]]:
    """번역 전에 링크를 ⟦0⟧ 같은 자리표시로 바꾼다 — Gemma 가 URL 을 고쳐 쓰다 깨뜨렸다(2026-09-30: youtu.beRhKw…)."""
    urls: list[str] = []

    def sub(m):
        urls.append(m.group(0))
        return f"⟦{len(urls) - 1}⟧"
    return URL_RE.sub(sub, text), urls


def restore_urls(text: str, urls: list[str]) -> str:
    """자리표시를 원래 링크로. 번역이 자리표시를 잃었으면 빠진 링크를 끝에 붙인다."""
    missing = []
    for i, u in enumerate(urls):
        if f"⟦{i}⟧" in text:
            text = text.replace(f"⟦{i}⟧", u)
        else:
            missing.append(u)
    text = re.sub(r"⟦\d+⟧", "", text)
    return text + ("\n\n" + "\n".join(missing) if missing else "")
CATEGORY = "24"          # Entertainment
UPLOADED = os.path.join(HERE, "uploaded.json")


def next_saturday_15utc(now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    d = now + dt.timedelta(days=(5 - now.weekday()) % 7)
    t = d.replace(hour=15, minute=0, second=0, microsecond=0)
    if t <= now + dt.timedelta(hours=6):          # 너무 가까우면 다음 주
        t += dt.timedelta(days=7)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sprint_times(day, now: dt.datetime | None = None) -> tuple[str, str]:
    """스프린트 편(1주 형식 실험): 본편 그날 15:00 UTC(미 동부 오전 11시) · 쇼츠 2시간 전.
    렌더가 늦어 시각이 지났거나 1시간 안이면 지금+2시간 정각으로 민다(쇼츠는 본편과 같은 시각까지)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    soon = (now + dt.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    long_at = dt.datetime(day.year, day.month, day.day, 15, tzinfo=dt.timezone.utc)
    if long_at < now + dt.timedelta(hours=1):
        long_at = soon
    short_at = long_at - dt.timedelta(hours=2)
    if short_at < now + dt.timedelta(hours=1):
        short_at = min(soon, long_at)
    f = "%Y-%m-%dT%H:%M:%SZ"
    return long_at.strftime(f), short_at.strftime(f)


def insert(yt, video: str, md: dict, privacy: str, publish_at: str | None) -> str:
    from googleapiclient.http import MediaFileUpload
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}
    if publish_at:
        status["publishAt"] = publish_at
    body = {"snippet": {"title": md["title"][:100], "description": md["description"][:4900], "tags": md["tags"],
                        "categoryId": CATEGORY, "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, chunksize=32 * 1024 * 1024, resumable=True))
    resp, last = None, -1
    while resp is None:
        st, resp = req.next_chunk()
        if st and int(st.progress() * 10) != last:
            last = int(st.progress() * 10)
            print(f"   업로드 {last * 10}%", flush=True)
    return resp["id"]


def localize(vid: str, title: str | None = None, description: str | None = None) -> list[str]:
    """제목·설명 현지화(best-effort — 실패해도 업로드는 끝났다). 원문은 영어.

    Gemma 는 8개 언어를 한 번에 JSON 으로 주면 설명이 길 때 출력이 잘린다(2026-09-30 실측: 4편 중 2편 파싱 실패)
    → 2개 언어씩 나눠 번역하고, 실패한 묶음은 한 번 더.
    """
    if not LANGS:
        return []
    os.environ["I18N_SOURCE_LANG"] = "en"
    # 이 채널 토큰만 쓰게 한다 — yt_i18n 은 forcessl → novel 순으로 토큰을 고른다(왕별이 토큰이 섞이지 않게)
    os.environ["YT_TOKEN_FORCESSL"] = os.environ.get("YT_TOKEN_NOVEL", "")
    try:
        import importlib
        import yt_i18n
        importlib.reload(yt_i18n)            # SOURCE_LANG 은 import 시점에 읽힌다
        if title is None:
            yt = yt_i18n._service(["forcessl", "novel"], [])
            sn = yt.videos().list(part="snippet", id=vid).execute()["items"][0]["snippet"]
            title, description = sn["title"], sn.get("description", "")
        loc = {}
        masked, urls = protect_urls(description or "")
        for k in range(0, len(LANGS), 2):
            group = LANGS[k:k + 2]
            for _ in range(2):
                got = yt_i18n.translate_meta(title, masked, group)
                if got:
                    for g in got.values():
                        g["description"] = restore_urls(g.get("description", ""), urls)
                    loc.update(got)
                    break
        if not loc:
            return []
        return yt_i18n.localize(vid, LANGS, localizations=loc)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 현지화 실패(업로드는 성공): {e}")
        return []


def captions(yt, vid: str, srt: str) -> bool:
    """영어 자막 트랙. force-ssl 스코프가 없으면 실패한다 — 그래도 유튜브 자동 자막이 있으니 건너뛴다."""
    from googleapiclient.http import MediaFileUpload
    try:
        yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English",
                                                               "isDraft": False}},
                             media_body=MediaFileUpload(srt, mimetype="application/octet-stream")).execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   ⏭️ 자막 트랙 건너뜀(자동 자막 사용): {str(e)[:140]}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "gumiho", "tales"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "gumiho", "tales_ledger.json"))
    ap.add_argument("--mode", default=os.environ.get("TALES_PUBLISH", "private"), choices=["private", "scheduled"])
    ap.add_argument("--publish-at", help="예약 공개 시각(UTC ISO) — 주면 mode 무시")
    ap.add_argument("--no-short", action="store_true")
    a = ap.parse_args()

    s = T.load(a.script)
    errs = T.check(s, a.script)
    if errs:
        print("::error::대본 검사 실패 — 올리지 않는다\n  " + "\n  ".join(errs))
        return 2
    stem = f"{s['id']:03d}_{s['slug']}"
    with open(os.path.join(a.renders, f"{stem}_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    if rm.get("mock"):
        print("::error::mock 렌더(가짜 그림·목소리)는 올리지 않는다")
        return 2
    led = {}
    if os.path.exists(a.ledger):
        with open(a.ledger, encoding="utf-8") as f:
            led = json.load(f)
    # Actions 캐시 밖에서(로컬에서) 올린 편 — 레포에 기록해 두고 다시 올리지 않는다
    with open(UPLOADED, encoding="utf-8") as f:
        for k, v in json.load(f).items():
            led.setdefault(k, v)
    done = led.get(stem, {})
    publish_at = a.publish_at or (next_saturday_15utc() if a.mode == "scheduled" else None)
    day = T.sprint_day(s["id"])
    short_at = None
    if day and a.mode == "scheduled" and not a.publish_at:
        publish_at, short_at = sprint_times(day)
        print(f"   스프린트 편({day}) — 본편 {publish_at} · 쇼츠 {short_at} · 추가 쇼츠 없음")
    # 앞서 올린 편(최신순 4개)을 설명에 링크 — 새 편이 옛 편을, 옛 편 검색 유입이 새 편을 끌어 준다
    more = [(v.get("title") or k, v["long"]) for k, v in sorted(led.items(), reverse=True)
            if k != stem and v.get("long")]
    md = T.meta(s, rm.get("starts"), more=more)

    import upload_youtube_novel as U
    yt = U.get_service()
    if not done.get("long"):
        vid = insert(yt, rm["video"], md, "private", publish_at)
        done["long"] = f"https://youtu.be/{vid}"
        done["title"] = md["title"]
        print(f"✅ 본편 {done['long']} · {'예약 ' + publish_at if publish_at else '비공개'}")
        done["thumb"] = bool(U.set_thumbnail(yt, vid, rm["thumb"]))
        if not done["thumb"]:
            print("   ⚠️ 썸네일 실패 — 채널 전화 인증(youtube.com/verify)이 안 됐으면 맞춤 썸네일이 막힌다")
        done["captions"] = captions(yt, vid, rm["srt"])
        done["langs"] = localize(vid, md["title"], md["description"])
        # 비공개로 올려도 넣는다 — 공개로 바뀌는 순간 재생목록에 이미 있어야 한다(목록은 공개 영상만 보여 준다).
        try:
            pid = U.ensure_playlist(yt, PLAYLIST, PLAYLIST_DESC, privacy="public")
            U.add_to_playlist(yt, pid, vid)
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 재생목록 실패(업로드는 성공): {e}")
        led[stem] = done
        _save(a.ledger, led)
    else:
        print(f"⏭️ 본편 이미 올림: {done['long']}")
    short = rm.get("short", {})
    if not a.no_short and short.get("video") and not done.get("short"):
        smd = T.meta(s, None, short_of=done["long"])["short"]
        s_at = short_at
        if publish_at and not s_at:                  # 쇼츠는 본편 하루 전에 풀어 본편으로 끌어온다
            s_at = (dt.datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%SZ") - dt.timedelta(days=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        sid = insert(yt, short["video"], smd, "private", s_at)
        done["short"] = f"https://youtu.be/{sid}"
        print(f"✅ 쇼츠 {done['short']}")
        localize(sid, smd["title"], smd["description"])
        led[stem] = done
        _save(a.ledger, led)
    # 추가 쇼츠(2026-10-01) — 본편이 공개된 ★뒤에 푼다(화·목 15:00 UTC). 관련 동영상 연결은 공개 영상만 고를 수 있다.
    smeta = T.meta(s, None, short_of=done.get("long"))["shorts_extra"]
    for k, ex in enumerate([] if day else (rm.get("shorts_extra") or []), start=2):
        key = f"short{k}"
        if a.no_short or not ex.get("video") or done.get(key) or k - 2 >= len(smeta):
            continue
        x_at = extra_short_at(publish_at, k)
        xid = insert(yt, ex["video"], smeta[k - 2], "private", x_at)
        done[key] = f"https://youtu.be/{xid}"
        print(f"✅ 쇼츠{k} {done[key]} · {'예약 ' + x_at if x_at else '비공개'}")
        localize(xid, smeta[k - 2]["title"], smeta[k - 2]["description"])
        led[stem] = done
        _save(a.ledger, led)
    print(json.dumps({stem: done}, ensure_ascii=False))
    return 0


EXTRA_SHORT_DAYS = {2: 3, 3: 5}     # 본편(토) 뒤 +3일(화) · +5일(목)


def extra_short_at(publish_at: str | None, k: int) -> str | None:
    """추가 쇼츠 k(2·3)의 예약 공개 시각. 본편이 비공개(예약 없음)면 None."""
    if not publish_at:
        return None
    t = dt.datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%SZ") + dt.timedelta(days=EXTRA_SHORT_DAYS.get(k, 3))
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _save(path: str, led: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.exit(main())
