#!/usr/bin/env python3
"""렌더한 릴스·카드 → 인스타그램(+선택: 쓰레드) 게시. ★기본은 dry-run — 아무것도 올리지 않고, 무엇을 어떤 API 호출
순서로 올릴지만 보여 준다(가짜 전송 — 네트워크·토큰 없이).

    python insta/post_reel.py output/insta/2026-10-05_claude-routine-rules.json        # dry-run(호출 순서까지)
    INSTA_PUBLISH=1 python insta/post_reel.py <script.json>                            # 실제 게시

실제 게시는 환경변수 INSTA_PUBLISH=1 일 때만(워크플로: 레포 변수 INSTA_PUBLISH=1 + routine/insta push 일 때만 넘긴다).
쓰레드도 올리려면 INSTA_THREADS=1.

형식 — 매 편 릴스(render_reel)와 카드(render_cards)를 둘 다 만들고, 어디에 무엇을 올릴지는 코드가 날짜로 정한다
  (insta.publish_formats): 인스타 = 월·수·금 가이드 → 릴스, 일 성적표 → 카드 · 쓰레드 = 늘 카드.
  덮어쓰기: INSTA_IG_FORMAT = auto|reel|cards|both · INSTA_THREADS_FORMAT = auto|cards|reel
  정한 형식이 렌더되지 않았으면(렌더 실패) 있는 다른 형식으로 올리고 경고를 남긴다.

올리지 않는 경우(코드로 막는다)
  · 대본 검사 실패 · mock 렌더나 mock 숫자(가짜 목소리·그림·통계)
  · 이미 올린 편(ledger — Actions 캐시 · insta/posted.json — 레포 기록) · 같은 날짜에 이미 한 편 올림
  · 대본 날짜가 오늘(KST)이나 어제가 아님 — 옛 원고가 뒤늦게 밀려와(미아 복구 등) 엉뚱한 날 게시되는 것 방지
게시 경로: Cloudinary(pipeline/host_video)로 공개 URL(영상·커버·카드 JPEG) → 인스타(upload_instagram: 릴스 publish_reel,
  카드 publish_carousel) → [INSTA_THREADS=1] 쓰레드(upload_threads: publish_carousel | publish_thread, 주제 태그 하나)
  → 하나라도 성공하면 Cloudinary 원본 삭제 → 기록(ledger + insta/posted.json: 어느 곳에 어떤 형식으로 올렸나).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import insta as I  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
POSTED = os.path.join(HERE, "posted.json")
CARD_SIZE = (1080, 1350)
CARDS_RANGE = (2, 10)                              # 인스타 캐러셀 2~10장
KO = {"reel": "릴스", "cards": "카드"}


def _on(name: str) -> bool:
    return os.environ.get(name, "").strip() in ("1", "true", "True", "yes")


def _load(path: str) -> dict | None:
    return I.load(path) if os.path.exists(path) else None


def load_ledger(path: str, posted: str = POSTED) -> dict:
    led = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                led = json.load(f)
        except (OSError, json.JSONDecodeError):
            led = {}
    if os.path.exists(posted):                     # 로컬에서 손으로 올린 편 — 레포에 기록해 두고 다시 올리지 않는다
        with open(posted, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                led.setdefault(k, v)
    return led


def card_problems(cards: dict | None) -> list[str]:
    """카드 렌더가 게시할 수 있는 모양인가(2~10장 · 파일 있음 · 1080×1350 JPEG)."""
    if not cards:
        return ["렌더된 카드가 없다"]
    paths = cards.get("cards") or []
    why = []
    if not CARDS_RANGE[0] <= len(paths) <= CARDS_RANGE[1]:
        why.append(f"카드 {len(paths)}장 — {CARDS_RANGE[0]}~{CARDS_RANGE[1]}장")
    for p in paths:
        if not os.path.exists(p):
            why.append(f"카드 파일 없음: {os.path.basename(p)}")
            continue
        from PIL import Image
        with Image.open(p) as im:
            if im.format != "JPEG" or im.size != CARD_SIZE:
                why.append(f"카드 {os.path.basename(p)} 는 {CARD_SIZE[0]}×{CARD_SIZE[1]} JPEG 여야 한다({im.format} {im.size})")
    return why


def blockers(s: dict, path: str, meta: dict, led: dict, today: dt.date, cards: dict | None = None,
             need=("reel",)) -> list[str]:
    """게시하면 안 되는 이유(비었으면 게시 가능). meta = 릴스 메타, cards = 카드 메타, need = 올릴 형식들."""
    why = [f"대본 검사: {e}" for e in I.check(s, path)]
    stem = f"{s['date']}_{s['topic']}"
    if any(m and (m.get("mock") or m.get("stats_mock")) for m in (meta, cards)):
        why.append("mock 렌더/숫자 — 게시하지 않는다")
    if stem in led:
        why.append(f"이미 올린 편: {stem}")
    if any(k.startswith(s["date"] + "_") for k in led if k != stem):
        why.append(f"{s['date']} 에 이미 다른 편을 올렸다(하루 한 편)")
    d = I._date(s["date"])
    if not (today - dt.timedelta(days=1) <= d <= today):
        why.append(f"대본 날짜 {d} 가 오늘({today})·어제가 아니다 — 늦게 도착한 원고는 올리지 않는다")
    if "reel" in need and not os.path.exists((meta or {}).get("video", "")):
        why.append("렌더된 영상이 없다")
    if "cards" in need:
        why += card_problems(cards)
    return why


def route(plan: dict, have_reel: bool, have_cards: bool, threads_on: bool) -> dict:
    """정한 형식(plan) → 실제로 올릴 것 {"ig": [...], "threads": 형식|None, "notes": [...]}.
    정한 형식의 렌더가 없으면 있는 다른 형식으로(릴스·카드는 같은 대본이라 내용이 같다)."""
    have = {"reel": have_reel, "cards": have_cards}
    other = {"reel": "cards", "cards": "reel"}
    notes = []
    ig = [f for f in plan["ig"] if have[f]]
    for f in plan["ig"]:
        if not have[f]:
            notes.append(f"인스타 {KO[f]} 렌더 없음")
    if not ig:
        alt = next((other[f] for f in plan["ig"] if have[other[f]]), None)
        if alt:
            ig = [alt]
            notes.append(f"인스타는 {KO[alt]}로 대신")
    th = None
    if threads_on:
        th = plan["threads"]
        if not have[th]:
            alt = other[th] if have[other[th]] else None
            notes.append(f"쓰레드 {KO[th]} 렌더 없음" + (f" — {KO[alt]}로 대신" if alt else ""))
            th = alt
    return {"ig": ig, "threads": th, "notes": notes}


# ── 전송(실제 | dry-run) ───────────────────────────────
class LiveBackend:
    """실제: Cloudinary + requests(토큰은 각 업로더가 환경변수에서 읽는다 — 여기서 읽거나 찍지 않는다)."""
    dry = False

    def __init__(self):
        import host_video
        self.hv = host_video
        self.ig: dict = {}
        self.th: dict = {}

    def host_video(self, path: str, pid: str):
        return self.hv.host(path, pid)

    def host_image(self, path: str, pid: str):
        return self.hv.host_image(path, pid)

    def cleanup(self, pid: str, rtype: str):
        return self.hv.cleanup(pid, resource_type=rtype)


class _Resp:
    status_code = 200

    def __init__(self, body: dict):
        self._b = body
        self.text = json.dumps(body)

    def json(self) -> dict:
        return self._b

    def raise_for_status(self):
        return None


class DryHTTP:
    """가짜 전송 — 호출을 적어 두고 가짜 id·FINISHED 를 돌려준다(네트워크 없음)."""

    def __init__(self, calls: list):
        self.calls = calls
        self.n = 0

    def post(self, url, data=None, timeout=None):
        body = {k: v for k, v in (data or {}).items() if k != "access_token"}
        self.calls.append(("POST", url, body))
        self.n += 1
        return _Resp({"id": f"dry{self.n}"})

    def get(self, url, params=None, timeout=None):
        body = {k: v for k, v in (params or {}).items() if k != "access_token"}
        self.calls.append(("GET", url, body))
        return _Resp({"status_code": "FINISHED", "status": "FINISHED"})


class DryBackend:
    """dry-run: 공개 URL·API 호출을 흉내만 낸다. 호출 순서는 self.calls 에."""
    dry = True

    def __init__(self):
        self.calls: list = []
        http = DryHTTP(self.calls)
        nosleep = lambda _s: None  # noqa: E731
        self.ig = {"http": http, "sleep": nosleep, "user_id": "{IG_USER_ID}", "token": "DRY_RUN"}
        self.th = {"http": http, "sleep": nosleep, "user_id": "{THREADS_USER_ID}", "token": "DRY_RUN"}

    def host_video(self, path: str, pid: str):
        self.calls.append(("HOST", "video", {"public_id": pid, "file": os.path.basename(path)}))
        return f"https://dry-run.invalid/{pid}.mp4"

    def host_image(self, path: str, pid: str):
        self.calls.append(("HOST", "image", {"public_id": pid, "file": os.path.basename(path)}))
        return f"https://dry-run.invalid/{pid}.jpg"

    def cleanup(self, pid: str, rtype: str):
        self.calls.append(("CLEANUP", rtype, {"public_id": pid}))
        return True

    def lines(self) -> list[str]:
        """사람이 읽는 호출 순서 — 연달아 같은 모양의 호출(장마다 컨테이너·상태 확인·호스팅)은 한 줄로 ×N."""
        out: list[list] = []
        for m, url, body in self.calls:
            u = re.sub(r"/dry[0-9]+$", "/{id}", url)
            short = {}
            for k, v in body.items():
                if k in ("public_id", "file", "image_url") and isinstance(v, str):
                    v = re.sub(r"card[0-9]{2}", "card{NN}", v)
                if k == "file":
                    continue
                short[k] = v if len(str(v)) <= 70 else str(v)[:67] + "…"
            line = f"{m:7} {u}  {json.dumps(short, ensure_ascii=False)}"
            if out and out[-1][0] == line:
                out[-1][1] += 1
            else:
                out.append([line, 1])
        return [ln + (f"  ×{n}" if n > 1 else "") for ln, n in out]


def publish(rt: dict, reel: dict | None, cards: dict | None, s: dict, be) -> dict:
    """rt(route) 대로 올린다 → {"ig": {형식: id}, "threads": {형식: id}, "errors": {...}}.
    공개 URL 을 하나라도 못 만들면 아무것도 올리지 않고 멈춘다(반쯤 올라가는 일 없게)."""
    import upload_instagram as UI
    import upload_threads as UT
    stem = f"{s['date']}_{s['topic']}"
    out: dict = {"ig": {}, "threads": {}, "errors": {}}
    need_reel = "reel" in rt["ig"] or rt["threads"] == "reel"
    need_cards = "cards" in rt["ig"] or rt["threads"] == "cards"
    pid = f"insta_{stem}"
    hosted: list[tuple[str, str]] = []
    video_url = cover_url = None
    card_urls: list[str] = []

    def fail(msg: str):
        for hp, rtype in hosted:
            be.cleanup(hp, rtype)
        raise SystemExit(f"❌ {msg} — 공개 URL 을 만들 수 없어 게시 못 함(Cloudinary 자격증명·용량 확인)")

    if need_reel:
        video_url = be.host_video(reel["video"], pid)
        if not video_url:
            fail("영상")
        hosted.append((pid, "video"))
        if "reel" in rt["ig"] and reel.get("cover"):
            cover_url = be.host_image(reel["cover"], f"{pid}_cover")
            if cover_url:
                hosted.append((f"{pid}_cover", "image"))
    if need_cards:
        for k, p in enumerate(cards["cards"], 1):
            cpid = f"{pid}_card{k:02d}"
            u = be.host_image(p, cpid)
            if not u:
                fail(f"카드 {k}")
            hosted.append((cpid, "image"))
            card_urls.append(u)
    ok = False
    for f in rt["ig"]:
        try:
            if f == "reel":
                out["ig"]["reel"] = UI.publish_reel(video_url, reel["caption"], cover_url=cover_url, **be.ig)
            else:
                out["ig"]["cards"] = UI.publish_carousel(card_urls, cards["caption"], **be.ig)
            ok = True
        except (Exception, SystemExit) as e:  # noqa: BLE001
            out["errors"][f"ig_{f}"] = str(e)[:300]
            print(f"::error title=Instagram {KO[f]} 게시 실패::{str(e)[:300]}")
    if rt["threads"]:
        f = rt["threads"]
        tag = I.topic_tag(s)
        try:
            if f == "reel":
                out["threads"]["reel"] = UT.publish_thread(video_url, reel["threads"], tag, **be.th)
            else:
                out["threads"]["cards"] = UT.publish_carousel(card_urls, cards["threads"], tag, **be.th)
            ok = True
        except (Exception, SystemExit) as e:  # noqa: BLE001
            out["errors"][f"threads_{f}"] = str(e)[:300]
            print(f"::warning title=Threads {KO[f]} 게시 실패::{str(e)[:300]}")
    if ok:                                         # 인스타·쓰레드는 게시 때 복사해 간다 → 원본은 지워 무료 한도를 아낀다
        for hp, rtype in hosted:
            be.cleanup(hp, rtype)
    return out


def record(led: dict, s: dict, res: dict, ledger_path: str, posted_path: str | None = POSTED,
           now: float | None = None) -> dict:
    """어디에 어떤 형식으로 올렸나 — ledger(Actions 캐시) + insta/posted.json(로컬에서 올렸으면 커밋해 둔다).
    {"<date>_<slug>": {"uploaded_at", "video_id", "privacy", "formats": {"ig": [...], "threads": [...]}, "ids": {...}}}"""
    key = f"{s['date']}_{s['topic']}"
    ids = {f"ig_{k}": v for k, v in res["ig"].items()}
    ids.update({f"threads_{k}": v for k, v in res["threads"].items()})
    entry = {"uploaded_at": round(now if now is not None else time.time()),
             "video_id": next(iter(ids.values()), None), "privacy": "public",
             "formats": {"ig": sorted(res["ig"]), "threads": sorted(res["threads"])}, "ids": ids}
    led[key] = entry
    os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=2)
    if posted_path:
        posted = {}
        if os.path.exists(posted_path):
            try:
                with open(posted_path, encoding="utf-8") as f:
                    posted = json.load(f)
            except (OSError, json.JSONDecodeError):
                posted = {}
        posted[key] = entry
        with open(posted_path, "w", encoding="utf-8") as f:
            json.dump(posted, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return entry


def _summary(lines: list[str]):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="릴스·카드 게시(기본 dry-run)")
    ap.add_argument("script")
    ap.add_argument("--renders", default=os.path.join(ROOT, "output", "insta_render"))
    ap.add_argument("--ledger", default=os.path.join(ROOT, "output", "insta_render", "posted_ledger.json"))
    ap.add_argument("--posted", default=POSTED, help="레포 기록 파일(게시 성공 때 형식까지 적는다)")
    ap.add_argument("--today", help="오늘(KST) 덮어쓰기 — 테스트용")
    a = ap.parse_args()

    s = I.load(a.script)
    stem = f"{s['date']}_{s['topic']}"
    reel = _load(os.path.join(a.renders, f"{stem}_meta.json"))
    cards = _load(os.path.join(a.renders, f"{stem}_cards.json"))
    if not reel and not cards:
        print(f"::error::렌더 메타 없음: {stem}_meta.json(릴스)·{stem}_cards.json(카드) 둘 다 없다 — {a.renders}")
        return 2
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(KST).date()
    led = load_ledger(a.ledger, a.posted)
    plan = I.publish_formats(s["date"], s.get("format"))
    for w in plan["warn"]:
        print(f"::warning title=게시 형식::{w}")
    live = _on("INSTA_PUBLISH")
    threads = _on("INSTA_THREADS")
    rt = route(plan, bool(reel) and os.path.exists(reel.get("video", "")), not card_problems(cards), threads)
    need = tuple(dict.fromkeys(rt["ig"] + ([rt["threads"]] if rt["threads"] else [])))
    why = blockers(s, a.script, reel or {}, led, today, cards=cards, need=need)
    if not need:
        why.append("올릴 렌더가 없다(릴스·카드 둘 다 없음)")
    for n in rt["notes"]:
        print(f"::warning title=게시 형식::{n}")

    fmt_line = (f"인스타 {' + '.join(KO[f] for f in rt['ig']) or '없음'} · 쓰레드 "
                + (KO[rt["threads"]] if rt["threads"] else "끔(INSTA_THREADS)"))
    print(f"── {stem} · {plan['kind']} · {fmt_line}")
    if reel:
        print(f"   릴스 {reel.get('sec')}초 · 진행자 {reel.get('host')} · 목소리 {reel.get('voice')} · {reel.get('video')}")
    if cards:
        print(f"   카드 {cards.get('count')}장 · {' / '.join(cards.get('slides', []))}")
    for f in rt["ig"]:
        cap = (reel if f == "reel" else cards).get("caption", "")
        print(f"── 인스타 {KO[f]} 캡션({len(cap)}자) ──\n{cap}\n──────────")
    if rt["threads"]:
        src = reel if rt["threads"] == "reel" else cards
        txt = src.get("threads", "")
        print(f"── 쓰레드 {KO[rt['threads']]} 글({I.threads_len(txt)}/{I.THREADS_MAX}자 · 주제 태그 {I.topic_tag(s)}) ──\n"
              f"{txt}\n──────────")
    _summary([f"### 인스타 {stem}", f"- 형식: {fmt_line}"] + [f"- ⚠️ {n}" for n in rt["notes"]])
    if why:
        print("⛔ 게시 안 함:\n  " + "\n  ".join(why))
        _summary(["- ⛔ 게시 안 함: " + " · ".join(why)])
    if not live:
        if need and all((reel if f == "reel" else cards) for f in need):
            dry = DryBackend()
            with contextlib.redirect_stdout(io.StringIO()):     # 업로더의 '게시 완료' 출력은 가짜라 숨긴다
                publish(rt, reel, cards, s, dry)
            print("🧪 dry-run — 게시하지 않았다. 실제(INSTA_PUBLISH=1)라면 이 순서로 호출한다:")
            for ln in dry.lines():
                print("   " + ln)
        print(f"🧪 dry-run — 레포 변수 INSTA_PUBLISH=1 이면 게시({fmt_line})")
        _summary(["- 🧪 dry-run(게시 안 함)"])
        return 0
    if why:
        return 0 if any("이미" in w for w in why) else 1
    res = publish(rt, reel, cards, s, LiveBackend())
    if not res["ig"] and not res["threads"]:
        return 1
    rec = record(led, s, res, a.ledger, a.posted)
    print(f"✅ 게시: {json.dumps(rec, ensure_ascii=False)}")
    _summary([f"- ✅ 게시: 인스타 {', '.join(KO[f] for f in rec['formats']['ig']) or '-'}"
              f" · 쓰레드 {', '.join(KO[f] for f in rec['formats']['threads']) or '-'}"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
