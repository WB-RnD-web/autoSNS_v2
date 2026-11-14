"""Meow Remix — 렌더한 고양이 쇼츠를 유튜브·인스타 릴스·쓰레드에 올린다.

    python meow/post.py text    <concepts.json>                    # 올라갈 글만 본다(오프라인)
    python meow/post.py youtube <concepts.json> [--gap-min 45]      # 비공개 + 예약 공개(편마다 gap 간격)
    python meow/post.py youtube <날짜>.json --slot-kst 10:00         # 매일판: 그 날짜 10:00 KST 공개(지났으면 20분 뒤)
    python meow/post.py seen    <날짜>.json                          # 이미 다 올라갔으면 0 · 남았으면 10
    python meow/post.py social  <concepts.json> [--gap-min 30]      # 인스타 릴스 + 쓰레드(편마다 gap 쉬고)
    python meow/post.py pick    <data/meow 폴더> [--days 3 --min-gap-h 3]   # 인스타·쓰레드에 올릴 편 하나(경로) — 없으면 빈 줄

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
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import render as R  # noqa: E402

CATEGORY = "15"            # Pets & Animals
NOT_YET = 10               # seen: 아직 안 올라감(오류 1 과 구별 — 다른 채널 토큰이면 렌더 전에 멈춘다)
CHANNEL_HANDLE = os.environ.get("MEOW_CHANNEL_HANDLE", "@meowremixcats").lower()
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


def slot_at(day: str, hhmm: str) -> dt.datetime:
    """기획 날짜 + 'HH:MM'(KST) → UTC 시각(매일판 공개 시각). 하루 12편이면 끝 편은 다음 날 새벽 — '32:00' = 다음 날 08:00."""
    h, m = (int(x) for x in hhmm.split(":"))
    base = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(0, 0), R.KST)
    return (base + dt.timedelta(hours=h, minutes=m)).astimezone(dt.timezone.utc)


def publish_times(n: int, gap_min: int, now: dt.datetime | None = None, first_at: dt.datetime | None = None) -> list[str]:
    """첫 편 = first_at(매일판 공개 시각) — 이미 지났거나 없으면 20분 뒤 · 그다음은 gap 간격."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    first = now + dt.timedelta(minutes=20)
    if first_at is not None and first_at > first:
        first = first_at.astimezone(dt.timezone.utc)
    first = first.replace(second=0, microsecond=0)
    return [(first + dt.timedelta(minutes=gap_min * k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(n)]


def uploaded_text(yt) -> str:
    """채널 최근 업로드 50편의 설명(비공개·예약 포함 — 주인 토큰) — 표식(MARK)으로 두 번 올리기를 막는다.
    ★토큰 파일이 없으면 업로더가 왕별이 토큰으로 넘어간다 — 핸들이 고양이 채널이 아니면 멈춘다."""
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    handle, title = str(ch["snippet"].get("customUrl", "")).lower(), ch["snippet"]["title"]
    print(f"채널: {title} ({handle})")
    if handle != CHANNEL_HANDLE and title not in ("Meow Remix", "Nine Tails Tales"):   # 이름 바꾸기 전·후
        raise SystemExit(f"❌ 다른 채널 토큰({title} {handle}) — 고양이 채널({CHANNEL_HANDLE})에만 올린다")
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    return " ".join(it["snippet"].get("description", "") for it in
                    yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute().get("items", []))


def seen(doc: dict) -> int:
    """기획의 편이 전부 이미 올라가 있으면 0(렌더하지 않아도 된다) · 남았으면 10 · 오류(다른 채널 등)는 1."""
    if not doc.get("concepts"):
        return 0
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import upload_youtube_novel as U
    text = uploaded_text(U.get_service())
    left = [R.stem(c) for c in doc["concepts"] if mark(doc, c) not in text]
    print(f"이미 올라감: {len(doc['concepts']) - len(left)}편 · 남음: {left or '없음'}")
    return NOT_YET if left else 0


def _ledger() -> dict:
    return R.load(POSTED) if os.path.exists(POSTED) else {}


def _save(led: dict):
    os.makedirs(R.OUT, exist_ok=True)
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def youtube(doc: dict, gap_min: int, slot_kst: str | None = None) -> int:
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    sys.path.insert(0, os.path.join(ROOT, "gumiho", "tales"))
    import upload_tale as UT                # status_body: 비공개 + publishAt + containsSyntheticMedia
    import upload_youtube_novel as U
    from googleapiclient.http import MediaFileUpload
    yt = U.get_service()
    seen_text = uploaded_text(yt)
    led, fails = _ledger(), 0
    todo = [c for c in doc["concepts"] if mark(doc, c) not in seen_text]
    times = publish_times(len(todo), gap_min, first_at=slot_at(doc["date"], slot_kst) if slot_kst else None)
    for c, at in zip(todo, times):
        v, md = video_of(c), yt_meta(doc, c)
        body = {"snippet": {"title": md["title"], "description": md["description"], "tags": md["tags"],
                            "categoryId": CATEGORY, "defaultLanguage": "en"},
                # 오디오 언어는 넣지 않는다 — 말소리 없는 영상이라고 'zxx' 를 넣으면 400 INVALID_REQUEST_METADATA(10/01·11/07 두 번)
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
        if got.get("ig") or got.get("threads"):
            got.setdefault("at", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        led[st] = got
        _save(led)
        HV.cleanup(pid, resource_type="video")
        if cover:
            HV.cleanup(pid + "_cover", resource_type="image")
    return 1 if fails else 0


def pick(plans: str, led: dict, days: int = 3, min_gap_h: float = 3, now: dt.datetime | None = None,
         has_out=lambda stem: True) -> tuple[str | None, str]:
    """인스타·쓰레드에 올릴 편 하나 → (기획 파일 경로 | None, 까닭).
    ★11/11~13 0편 사고: 18:00 예약이 8시간 늦게(다음 날 새벽) 돌아 '오늘' 기획만 보다가 아무것도 안 올렸다.
    → 날짜를 '오늘'로 묶지 않는다: 최근 days 일의 편 a(<날짜>.json · 매일 변신) 중 완성본(캐시)이 있고 아직 안 올린 것,
      새것부터. 인스타는 하루 1편 꼴로 — 마지막 게시 뒤 min_gap_h 시간 안이면 쉰다(놓친 편 따라잡기도 몰아 올리지 않게)."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    last = [dt.datetime.fromisoformat(v["at"].replace("Z", "+00:00")) for v in led.values()
            if isinstance(v, dict) and v.get("at")]
    if last and now - max(last) < dt.timedelta(hours=min_gap_h):
        return None, f"마지막 게시({max(last):%m-%d %H:%M} UTC) 뒤 {min_gap_h}시간이 안 됐다"
    today = now.astimezone(R.KST).date()
    for k in range(days):
        p = os.path.join(plans, f"{today - dt.timedelta(days=k)}.json")
        if not os.path.exists(p):
            continue
        cs = R.load(p).get("concepts") or []
        if not cs:
            continue
        st = R.stem(cs[0])
        got = led.get(st, {})
        if got.get("ig") and got.get("threads"):
            continue
        if not has_out(st):
            continue
        return p, f"{st} (인스타 {'✓' if got.get('ig') else '·'} 쓰레드 {'✓' if got.get('threads') else '·'})"
    return None, f"최근 {days}일 편 a 중 올릴 것 없음(다 올렸거나 완성본이 아직 없다)"


def out_cache_exists(stem: str) -> bool:
    """meow-daily 가 저장한 완성본 캐시(meow-out-<stem>-)가 있나 — GitHub API(GITHUB_TOKEN · actions: read).
    토큰이 없으면(로컬) 있다고 본다."""
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo:
        return True
    q = urllib.parse.urlencode({"key": f"meow-out-{stem}-", "per_page": 1})
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/caches?{q}",
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("total_count", 0) > 0
    except Exception as e:  # noqa: BLE001 — 못 보면 있다고 치고 넘긴다(캐시 받기에서 없으면 경고로 끝난다)
        print(f"(캐시 목록을 못 봤다: {str(e)[:120]})", file=sys.stderr)
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["text", "youtube", "social", "seen", "pick"])
    ap.add_argument("concepts", help="기획 파일(pick 은 data/meow 폴더)")
    ap.add_argument("--gap-min", type=int, default=None)
    ap.add_argument("--slot-kst", default=None, help="매일판: 기획 날짜의 이 시각(KST HH:MM)에 공개 — 지났으면 20분 뒤")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--min-gap-h", type=float, default=3)
    a = ap.parse_args()
    if a.cmd == "pick":
        p, why = pick(a.concepts, _ledger(), a.days, a.min_gap_h, has_out=out_cache_exists)
        print(why, file=sys.stderr)
        print(p or "")
        return 0
    doc = R.load(a.concepts)
    doc.setdefault("concepts", [])
    errs = R.check(doc)
    if errs:
        print("❌ 검사 실패\n  " + "\n  ".join(errs))
        return 1
    if a.cmd == "seen":
        return seen(doc)
    if a.cmd == "text":
        for c in doc["concepts"]:
            md = yt_meta(doc, c)
            print(f"===== {R.stem(c)}\n[YT] {md['title']}\n{md['description']}\n[IG]\n{ig_caption(c)}\n[TH]\n{threads_text(c)}\n")
        return 0
    if a.cmd == "youtube":
        return youtube(doc, 45 if a.gap_min is None else a.gap_min, a.slot_kst)
    return social(doc, 30 if a.gap_min is None else a.gap_min)


if __name__ == "__main__":
    sys.exit(main())
