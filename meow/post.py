"""Meow Remix — 렌더한 고양이 쇼츠를 유튜브·인스타 릴스·쓰레드에 올린다.

    python meow/post.py text    <concepts.json>                    # 올라갈 글만 본다(오프라인)
    python meow/post.py youtube <concepts.json> [--gap-min 45]      # 비공개 + 예약 공개(편마다 gap 간격)
    python meow/post.py social  <concepts.json> [--gap-min 30]      # 인스타 릴스 + 쓰레드(편마다 gap 쉬고)

영상은 output/meow/<id>_<slug>.mp4 (render.py build). 유튜브 토큰은 YT_TOKEN_NOVEL 경로(워크플로가 시크릿을 파일로 쓴다),
인스타·쓰레드·Cloudinary 는 각 업로더가 환경변수에서 읽는다 — 여기서 토큰을 읽거나 찍지 않는다.
같은 편을 두 번 올리지 않게 유튜브는 설명의 표식(MARK)을, 인스타·쓰레드는 output/meow/posted.json 을 본다.
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
import render as R  # noqa: E402

CATEGORY = "15"            # Pets & Animals
POSTED = os.path.join(R.OUT, "posted.json")


def mark(doc: dict, c: dict) -> str:
    return f"Meow Remix · {doc['date']} {c['id']}"


def music_short(c: dict) -> str:
    t = R.tracks()[c["track"]]
    return f'🎵 "{t["title"]}" Kevin MacLeod (incompetech.com) · CC BY 4.0 creativecommons.org/licenses/by/4.0'


def yt_meta(doc: dict, c: dict) -> dict:
    en_tags = [h for h in c["hashtags"] if h.isascii() and "instagram" not in h]
    desc = "\n".join([c["en_line"], "", " ".join(en_tags + ["#shorts", "#aicat"]), "",
                      R.credit(c["track"]), "AI-generated video: the cats and scenes are not real footage.", "",
                      mark(doc, c)])
    return {"title": c["title"][:100], "description": desc, "tags": c["tags"][:15]}


def ig_caption(c: dict) -> str:
    return "\n".join([c["ko_line"], c["en_line"], "", " ".join(c["hashtags"]), "", music_short(c),
                      "AI로 만든 영상이에요."])


def threads_text(c: dict) -> str:
    t = R.tracks()[c["track"]]
    return "\n".join([c["ko_line"], c["en_line"], "", f'🎵 "{t["title"]}" Kevin MacLeod · CC BY 4.0', "AI로 만든 영상"])


def video_of(c: dict) -> dict:
    p = os.path.join(R.OUT, f"{R.stem(c)}_meta.json")
    if not os.path.exists(p):
        raise SystemExit(f"{R.stem(c)}: 렌더 없음(render.py build 먼저)")
    m = R.load(p)
    base = os.path.join(R.OUT, R.stem(c))        # meta 의 절대경로는 렌더한 PC 기준 — 여기서는 같은 폴더에서 찾는다
    return {"video": base + ".mp4", "cover": base + "_cover.jpg", "sec": m["sec"]}


def publish_times(n: int, gap_min: int, now: dt.datetime | None = None) -> list[str]:
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    first = (now + dt.timedelta(minutes=20)).replace(second=0, microsecond=0)
    return [(first + dt.timedelta(minutes=gap_min * k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(n)]


def _ledger() -> dict:
    return R.load(POSTED) if os.path.exists(POSTED) else {}


def _save(led: dict):
    os.makedirs(R.OUT, exist_ok=True)
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def youtube(doc: dict, gap_min: int) -> int:
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    sys.path.insert(0, os.path.join(ROOT, "gumiho", "tales"))
    import upload_tale as UT                # status_body: 비공개 + publishAt + containsSyntheticMedia
    import upload_youtube_novel as U
    from googleapiclient.http import MediaFileUpload
    yt = U.get_service()
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    print(f"채널: {ch['snippet']['title']}")
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    seen = " ".join(it["snippet"].get("description", "") for it in
                    yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute().get("items", []))
    led, fails = _ledger(), 0
    todo = [c for c in doc["concepts"] if mark(doc, c) not in seen]
    times = publish_times(len(todo), gap_min)
    for c, at in zip(todo, times):
        v, md = video_of(c), yt_meta(doc, c)
        body = {"snippet": {"title": md["title"], "description": md["description"], "tags": md["tags"],
                            "categoryId": CATEGORY, "defaultLanguage": "en", "defaultAudioLanguage": "zxx"},
                "status": UT.status_body("private", at)}
        try:
            req = yt.videos().insert(part="snippet,status", body=body,
                                     media_body=MediaFileUpload(v["video"], chunksize=-1, resumable=True))
            resp = None
            while resp is None:
                _, resp = req.next_chunk()
            vid = resp["id"]
            led.setdefault(R.stem(c), {})["youtube"] = {"url": f"https://youtu.be/{vid}", "publish_at": at}
            _save(led)
            print(f"✅ {R.stem(c)} https://youtu.be/{vid} · 공개 {at}", flush=True)
            # 썸네일은 안 바꾼다 — 쇼츠 피드는 썸네일을 안 쓰고, 쿼터(50 units)는 업로드와 같이 쓴다
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"::error::{R.stem(c)} 유튜브 업로드 실패: {str(e)[:300]}")
    print(f"유튜브: 새로 {len(todo) - fails}편 · 이미 있음 {len(doc['concepts']) - len(todo)}편 · 실패 {fails}")
    return 1 if fails else 0


def social(doc: dict, gap_min: int) -> int:
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import host_video as HV
    import upload_instagram as UI
    import upload_threads as UTH
    led, fails, first = _ledger(), 0, True
    for c in doc["concepts"]:
        st = R.stem(c)
        got = led.get(st, {})
        if got.get("ig") and got.get("threads"):
            print(f"⏭️ {st} 이미 올림")
            continue
        if not first and gap_min:
            print(f"   {gap_min}분 쉬고 다음 편", flush=True)
            time.sleep(gap_min * 60)
        first = False
        v = video_of(c)
        pid = f"meow_{doc['date']}_{c['id']}"
        url = HV.host(v["video"], pid)
        if not url:
            raise SystemExit("Cloudinary 호스팅 실패 — 자격증명 확인")
        cover = HV.host_image(v["cover"], pid + "_cover")
        if not got.get("ig"):
            try:
                got["ig"] = UI.publish_reel(url, ig_caption(c), cover_url=cover)
                print(f"✅ {st} 인스타 릴스 {got['ig']}", flush=True)
            except (Exception, SystemExit) as e:  # noqa: BLE001
                fails += 1
                print(f"::error::{st} 인스타 실패: {str(e)[:300]}")
        if not got.get("threads"):
            try:
                got["threads"] = UTH.publish_thread(url, threads_text(c), "고양이")
                print(f"✅ {st} 쓰레드 {got['threads']}", flush=True)
            except (Exception, SystemExit) as e:  # noqa: BLE001
                fails += 1
                print(f"::warning::{st} 쓰레드 실패: {str(e)[:300]}")
        led[st] = got
        _save(led)
        HV.cleanup(pid, resource_type="video")
        if cover:
            HV.cleanup(pid + "_cover", resource_type="image")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["text", "youtube", "social"])
    ap.add_argument("concepts")
    ap.add_argument("--gap-min", type=int, default=None)
    a = ap.parse_args()
    doc = R.load(a.concepts)
    errs = R.check(doc)
    if errs:
        print("❌ 검사 실패\n  " + "\n  ".join(errs))
        return 1
    if a.cmd == "text":
        for c in doc["concepts"]:
            md = yt_meta(doc, c)
            print(f"===== {R.stem(c)}\n[YT] {md['title']}\n{md['description']}\n[IG]\n{ig_caption(c)}\n[TH]\n{threads_text(c)}\n")
        return 0
    if a.cmd == "youtube":
        return youtube(doc, 45 if a.gap_min is None else a.gap_min)
    return social(doc, 30 if a.gap_min is None else a.gap_min)


if __name__ == "__main__":
    sys.exit(main())
