#!/usr/bin/env python3
"""인스타 '오늘의 골라보기' → 쓰레드(@feeldragon3802) 2주 시험 — 같은 대본으로 글 하나 + 내 답글 하나 (2026-10-10).

왜: 10/6 진단 — 쓰레드 편당 11~55회·반응 0(인스타 캐러셀을 그대로 옮긴 글). 한국 쓰레드는 반말·짧은 글·답글이 퍼진다
  (조사 https://claude.ai/artifact/SAWS7fA8fSnh7hwodLg5P7). 사용자 승인(10/10): 2주 동안 매일 릴스가 올라간 뒤
  같은 대본으로 쓰레드 글 하나 + 내 답글 하나. 끝나면 인사이트로 판정한다.
★기간은 코드가 정한다(THREADS_FROM~THREADS_TO, KST, 양끝 포함) — 레포 변수·루틴 지시는 안 지켜질 수 있다.

꼴마다(대본 필드 그대로 — pick_plan.FORMATS):
  pick·card  글 = headline 두 줄 + '난 N번'(우리 고른 것) · 고르기 그림 4장 캐러셀(번호 배지)
             답글 = 번호별 결과 — 'N번 name — result: lines'(caption_of 와 같은 꼴) · 번호 뒤를 스포일러로 가린다
  quiz       글 = rounds[0].q + 투표(choices 4개) · 답글 = 정답 + why(스포일러)
  balance    글 = rounds[0] a vs b + 한 줄 · 투표(a·b label) · 답글 없음
  birth      글 = headline + '난 N월생이라 …' 한 줄 · 표 한 장 · 답글 없음
말투: 대본의 해요체 끝맺음을 반말로(banmal — 확실한 꼴만 바꾸고 모르는 꼴은 그대로 둔다).
지키는 것: 주제 태그 하나(insta.topic_tag = 해시태그 첫 개) · 본문 '#'·채널 줄(CHANNELS_LINE)·유튜브·링크 없음 ·
  '댓글로 번호 남겨 줘' 같은 미끼 없음(Meta 는 참여 유도 미끼를 덜 퍼뜨린다 — 투표가 그 자리를 대신한다) ·
  투표 보기 2~4개·한 개 25자 · 글 500자 · 스포일러 10개까지(답글엔 이모지 없이 — offset 단위가 문서에 없다).
순서: 인스타 ledger 에 오늘 media_id 가 있어야(= 인스타가 실제로 올라간 뒤) → 글 → ledger 기록 → 답글 → ledger 기록.
  다시 돌려도 두 번 올리지 않는다(ledger: output/insta_pick_render/threads_posted.json · Actions 캐시).
  쓰레드가 실패해도 인스타는 그대로다(워크플로 continue-on-error + 경고).
끄기: 레포 변수 INSTA_PICK_THREADS=0 (끄기만 된다 — 기간 밖은 켤 수 없다).

    python insta/pick_threads.py show <script.json> [--date 2026-10-11]   # 보낼 글·투표·답글·호출 순서(가짜 전송)
    python insta/pick_threads.py post <script.json>                       # 워크플로가 쓴다
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import insta as I  # noqa: E402  (topic_tag · CHANNELS_LINE · 미끼·홍보 정규식)
import pick_plan as P  # noqa: E402
import upload_threads as UT  # noqa: E402

THREADS_FROM = dt.date(2026, 10, 11)     # 2주 시험 첫날(KST)
THREADS_TO = dt.date(2026, 10, 24)       # 마지막 날(KST, 포함) — 판정 뒤 늘리려면 코드로(PR)
LEDGER = os.path.join(P.RENDERS, "threads_posted.json")
REPLY_GAP = 10                           # 본 글 게시 뒤 답글까지 잠깐 쉰다(게시가 퍼지기 전에 답글을 붙이지 않게 — 넉넉히)
RESULT_HEAD = "결과는 여기"
BALANCE_LINES = ("둘 중 하나만 고른다면?", "이거 진짜 못 고르겠어", "하나만 골라야 하면 뭐 고를래?")
# 쓰레드 글에 들어가면 안 되는 말 — 인스타 캡션 고정 문구(보내기·숫자 댓글)·채널 줄·유튜브·댓글 부탁
BANNED = (I.CHANNELS_LINE, "기록 중인 채널", "유튜브", "YouTube", "Youtube", "youtube", "댓글", "팔로우", "구독", "#",
          "오늘의 골라보기")
_EMOJI = re.compile("[\U0001F000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D\u20E3]")


# ── 말투 ──────────────────────────────────────────────
def _final_jamo(ch: str) -> int:
    """한글 음절의 받침 번호(0 = 받침 없음, -1 = 한글 아님)."""
    o = ord(ch) - 0xAC00
    return o % 28 if 0 <= o < 11172 else -1


_END = re.compile(r"^(.*?)([가-힣])(요|죠)([\s.!?~…]*)$", re.S)


def _banmal1(sent: str) -> str:
    m = _END.match(sent)
    if not m:
        return sent
    head, prev, yo, tail = m.groups()
    if yo == "죠":                                   # 그렇죠 → 그렇지
        return head + prev + "지" + tail
    if prev in "에예":                               # 이에요·예요·아니에요 → 이야·야·아니야
        return head + "야" + tail
    if prev == "세":                                 # 보세요 → (확실한 반말이 없어) 그대로
        return sent
    if _final_jamo(prev) == 0 or prev in "군든걸":    # 봐요·와요·까요·있어요·군요·거든요 → 요만 뺀다
        return head + prev + tail
    return sent                                      # 필요·중요 같은 낱말 끝은 그대로


def banmal(text: str) -> str:
    """해요체 끝맺음 → 반말(문장마다). 확실한 꼴만 바꾼다: '골라 봐요'→'골라 봐' · '일까요?'→'일까?' · '주예요'→'주야'."""
    out = []
    for line in str(text).split("\n"):
        out.append(" ".join(_banmal1(x) for x in re.split(r"(?<=[.!?])\s+", line.strip())))
    return "\n".join(out)


def _plain(text: str) -> str:
    """스포일러 답글용 — 이모지를 빼고 빈칸을 하나로(이모지가 있으면 offset 단위에 따라 가림 자리가 밀릴 수 있다)."""
    return re.sub(r"[ \t]{2,}", " ", _EMOJI.sub("", text)).strip()


# ── 무엇을 올리나 ─────────────────────────────────────
def in_window(d: dt.date) -> bool:
    return THREADS_FROM <= d <= THREADS_TO


def _pick_no(s: dict, n: int) -> int:
    """우리 고른 번호(1~n) — 날짜·slug 로 정해서 다시 돌려도 같다."""
    return int(hashlib.sha1(f"{s.get('date')}_{s.get('slug')}".encode()).hexdigest(), 16) % n + 1


def plan_of(s: dict) -> dict:
    """대본 → {"kind", "topic_tag", "post": {"type": carousel|image|text, "text", "poll", "images"(장 수)},
    "reply": {"text", "spoilers"} | None}."""
    kind = s["kind"]
    tag = I.topic_tag(s)
    post: dict = {"type": "text", "text": "", "poll": None, "images": 0}
    reply = None
    if kind in ("pick", "card"):
        n = _pick_no(s, len(s["options"]))
        mine = f"난 {n}번" + (" 카드" if kind == "card" else "")
        post.update(type="carousel", images=len(s["options"]),
                    text="\n".join(banmal(x) for x in s["headline"]) + f"\n{mine}")
        lines, hidden = [RESULT_HEAD], []
        for k, o in enumerate(s["options"], 1):          # caption_of 와 같은 꼴: 'N번 name — result: lines'
            rest = f"{_plain(o['name'])} — {banmal(_plain(o['result']))}: {banmal(_plain(o['lines']))}"
            lines.append(f"{k}번 {rest}")
            hidden.append(rest)
        reply = {"text": "\n".join(lines), "hidden": hidden}
    elif kind == "quiz":
        r = s["rounds"][0]
        post.update(text=banmal(r["q"]), poll=list(r["choices"]))
        ans = _plain(r["choices"][r["answer"]]) + (f" — {banmal(_plain(r['why']))}" if r.get("why") else "")
        reply = {"text": f"정답은 {ans}", "hidden": [ans]}
    elif kind == "balance":
        r = s["rounds"][0]
        a, b = r["a"]["label"], r["b"]["label"]
        post.update(text=f"{a} vs {b}\n{BALANCE_LINES[_pick_no(s, len(BALANCE_LINES)) - 1]}", poll=[a, b])
    elif kind == "birth":
        m = _pick_no(s, 12)
        cell = next(c for c in s["cells"] if c.get("m") == m)
        post.update(type="image", images=1,
                    text=banmal(" ".join(s["headline"])) + f"\n난 {m}월생이라 {banmal(cell['text'])}")
    if reply:                                            # 스포일러 = 가릴 말마다 하나(앞에서부터 차례로 찾는다)
        ents, at = [], 0
        for part in reply.pop("hidden"):
            e = UT.spoiler(reply["text"], part, at)
            ents.append(e)
            at = reply["text"].find(part, at) + len(part)
        reply["spoilers"] = ents
    return {"kind": kind, "topic_tag": tag, "post": post, "reply": reply}


def problems(pl: dict) -> list[str]:
    """보내기 전에 막는다 — 길이·투표·스포일러·주제 태그 하나·금지 말(채널 줄·유튜브·댓글 부탁·해시태그)."""
    bad = []
    post, reply = pl["post"], pl.get("reply")
    texts = [("글", post["text"])] + ([("답글", reply["text"])] if reply else [])
    for where, t in texts:
        if not t or UT.text_len(t) > UT.TEXT_MAX:
            bad.append(f"{where} 1~{UT.TEXT_MAX}자 — 지금 {UT.text_len(t)}자")
        hit = [w for w in BANNED if w in t]
        if hit or I.BAIT.search(t) or I.PROMO.search(t):
            bad.append(f"{where}에 금지 말: {hit or [x.group(0) for x in (I.BAIT.search(t), I.PROMO.search(t)) if x]}")
    tag = pl.get("topic_tag")
    if not tag or not 1 <= len(tag) <= 50 or re.search(r"[.&#\s]", tag):
        bad.append(f"주제 태그 하나(1~50자, 마침표·& 없이)가 필요하다: {tag!r}")
    if post.get("poll"):
        if post["type"] != "text":
            bad.append("투표는 글(TEXT)에만 붙는다")
        try:
            UT.poll_attachment(post["poll"])
        except RuntimeError as e:
            bad.append(str(e))
    if post["type"] == "carousel" and not 2 <= post["images"] <= 20:
        bad.append(f"캐러셀은 2~20장 — {post['images']}장")
    if reply:
        if _EMOJI.search(reply["text"]):
            bad.append("스포일러 답글에 이모지 — offset 이 밀릴 수 있어 넣지 않는다")
        try:
            UT._check_spoilers(reply["text"], reply.get("spoilers"))
        except RuntimeError as e:
            bad.append(str(e))
        if not reply.get("spoilers"):
            bad.append("답글 스포일러가 없다")
    return bad


# ── 게시 ──────────────────────────────────────────────
def skip_reasons(s: dict, today: dt.date, ig_led: dict, env=None) -> list[str]:
    """올리지 않는 까닭(있으면 조용히 건너뛴다 — 실패가 아니다)."""
    env = os.environ if env is None else env
    why = []
    if not in_window(today):
        why.append(f"2주 시험 기간({THREADS_FROM}~{THREADS_TO}) 밖: {today}")
    if (env.get("INSTA_PICK_THREADS") or "1").strip() == "0":
        why.append("레포 변수 INSTA_PICK_THREADS=0 — 쓰레드 끔")
    if env.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        why.append("수동 실행(렌더만)")
    if s.get("date") != today.isoformat():
        why.append(f"오늘({today}) 대본이 아니다: {s.get('date')}")
    ig = ig_led.get(s.get("date") or "", {})
    if not ig.get("media_id"):
        why.append("인스타가 아직 안 올라갔다(인스타 ledger 에 오늘 media_id 없음)")
    elif ig.get("slug") and ig.get("slug") != s.get("slug"):
        why.append(f"인스타에 올라간 대본({ig.get('slug')})과 다르다: {s.get('slug')}")
    return why


class Cloud:
    """그림 공개 URL(Cloudinary 무료) — 테스트는 같은 모양의 가짜를 넣는다."""

    def host_image(self, path: str, pid: str) -> str | None:
        import host_video
        return host_video.host_image(path, pid)

    def cleanup(self, pid: str) -> None:
        import host_video
        host_video.cleanup(pid, "image")


def _save(led: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def _now() -> str:
    return dt.datetime.now(P.KST).isoformat(timespec="seconds")


def post(path: str, renders: str = P.RENDERS, ledger: str = LEDGER, ig_ledger: str = P.LEDGER,
         today: dt.date | None = None, *, env=None, http=None, cloud=None, sleep=time.sleep,
         user_id: str | None = None, token: str | None = None) -> int:
    """오늘 대본 → 쓰레드 글 + 답글. 0 = 올렸다/이미 올렸다/건너뜀 · 1 = 막힘·실패(워크플로가 경고로 띄운다)."""
    s = json.load(open(path, encoding="utf-8"))
    today = today or P.kst_today()
    why = skip_reasons(s, today, P.load_ledger(ig_ledger), env)
    if why:
        print("⏭️ 쓰레드 안 올림:\n  " + "\n  ".join(why))
        return 0
    pl = plan_of(s)
    led = P.load_ledger(ledger)
    entry = led.get(s["date"]) or {}
    if entry.get("post_id") and (entry.get("reply_id") or not pl["reply"]):
        print(f"⏭️ 쓰레드 {s['date']} 는 이미 올렸다: post={entry['post_id']} reply={entry.get('reply_id') or '-'}")
        return 0
    bad = problems(pl)
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    imgs: list[str] = []
    if pl["post"]["images"] and not entry.get("post_id"):  # 글이 이미 올라갔으면(답글만 남음) 그림은 필요 없다
        mp = os.path.join(renders, f"{stem}_meta.json")
        meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        imgs = [p for p in meta.get("threads_images") or [] if os.path.exists(p)]
        if len(imgs) != pl["post"]["images"]:
            bad.append(f"쓰레드 그림 {pl['post']['images']}장이 필요한데 {len(imgs)}장(렌더 메타 threads_images)")
    if bad:
        print("::error title=쓰레드 막힘::" + " · ".join(bad))
        return 1
    kw = {"http": http, "sleep": sleep, "user_id": user_id, "token": token}
    tag = pl["topic_tag"]
    if not entry.get("post_id"):
        cloud = cloud or Cloud()
        hosted, urls = [], []
        try:
            for k, p in enumerate(imgs, 1):
                pid = f"insta_pick_th_{stem}_{k}"
                u = cloud.host_image(p, pid)
                if not u:
                    raise RuntimeError(f"그림 {k} 공개 URL 실패(Cloudinary)")
                hosted.append(pid)
                urls.append(u)
            kind = pl["post"]["type"]
            if kind == "carousel":
                pid_ = UT.publish_carousel(urls, pl["post"]["text"], tag, **kw)
            elif kind == "image":
                pid_ = UT.publish_image(urls[0], pl["post"]["text"], tag, **kw)
            else:
                pid_ = UT.publish_text(pl["post"]["text"], tag, poll=pl["post"]["poll"], **kw)
        finally:                                          # 쓰레드는 컨테이너를 만들 때 그림을 가져간다 → 원본은 지운다
            for pid in hosted:
                cloud.cleanup(pid)
        entry = {"kind": s["kind"], "slug": s["slug"], "type": pl["post"]["type"], "post_id": pid_,
                 "topic_tag": tag, "at": _now()}
        led[s["date"]] = entry
        _save(led, ledger)                                # 답글이 실패해도 글은 다시 올리지 않게 바로 적는다
        if pl["reply"]:
            sleep(REPLY_GAP)
    if pl["reply"] and not entry.get("reply_id"):
        rid = UT.publish_reply(entry["post_id"], pl["reply"]["text"], spoilers=pl["reply"]["spoilers"], **kw)
        entry.update(reply_id=rid, reply_at=_now())
        led[s["date"]] = entry
        _save(led, ledger)
    print(f"✅ 쓰레드 '오늘의 골라보기' {stem}: post={entry['post_id']} reply={entry.get('reply_id') or '-'} · 주제 태그 {tag}")
    return 0


# ── 가짜 전송(show · 테스트) ───────────────────────────
class _Resp:
    def __init__(self, data: dict):
        self.status_code, self._d, self.text = 200, data, json.dumps(data)

    def json(self) -> dict:
        return self._d


class FakeHTTP:
    """Threads API 흉내 — 보낸 것을 calls 에 쌓고 id 를 차례로 준다(dry-run · 테스트)."""

    def __init__(self, fail_on=None):
        self.calls: list[tuple[str, str, dict]] = []
        self.n = 0
        self.fail_on = fail_on                           # fail_on(url, data) 가 참인 POST 는 400(답글 실패 흉내 등)

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, dict(data or {})))
        if self.fail_on and self.fail_on(url, data or {}):
            r = _Resp({"error": {"message": "fake failure", "code": 1}})
            r.status_code = 400
            return r
        self.n += 1
        return _Resp({"id": f"dry{self.n}"})

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, dict(params or {})))
        return _Resp({"status": "FINISHED"})


class FakeCloud:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def host_image(self, path, pid):
        self.calls.append(("HOST", pid))
        return f"https://dry-run.invalid/{pid}.jpg"

    def cleanup(self, pid):
        self.calls.append(("CLEANUP", pid))


def show(s: dict) -> str:
    """사람이 읽는 미리보기(markdown) — 글·투표·답글(스포일러는 [[ ]])·주제 태그·검사 결과·호출 순서."""
    pl = plan_of(s)
    bad = problems(pl)
    p, r = pl["post"], pl["reply"]
    out = [f"### {s['date']} · {s['kind']} · {s['slug']}", "",
           f"- 형식: {p['type']}" + (f" (그림 {p['images']}장)" if p["images"] else "") + f" · 주제 태그: `{pl['topic_tag']}`",
           "- 글:", "", "```", p["text"], "```"]
    if p.get("poll"):
        out += ["", "- 투표: " + " / ".join(f"`{o}`({len(o)}자)" for o in p["poll"])]
    if r:
        t, marked, last = r["text"], [], 0
        u16 = t.encode("utf-16-le")
        for e in r["spoilers"]:
            a, b = e["offset"] * 2, (e["offset"] + e["length"]) * 2
            marked += [u16[last:a].decode("utf-16-le"), "[[", u16[a:b].decode("utf-16-le"), "]]"]
            last = b
        marked.append(u16[last:].decode("utf-16-le"))
        out += ["", "- 내 답글(reply_to_id = 위 글 · [[ ]] = 스포일러):", "", "```", "".join(marked), "```",
                "", "- 스포일러 entities: `" + json.dumps(r["spoilers"]) + "`"]
    else:
        out += ["", "- 내 답글: 없음"]
    out += ["", "- 검사: " + ("✅ 통과" if not bad else "❌ " + " · ".join(bad))]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 '오늘의 골라보기' → 쓰레드 2주 시험")
    ap.add_argument("cmd", choices=["show", "post"])
    ap.add_argument("script")
    ap.add_argument("--date", help="show: 대본 날짜를 이 날로 바꿔 본다")
    a = ap.parse_args()
    if a.cmd == "show":
        s = json.load(open(a.script, encoding="utf-8"))
        if a.date:
            s["date"] = a.date
        print(show(s))
        return 0
    try:
        return post(a.script)
    except (Exception, SystemExit) as e:  # noqa: BLE001  (쓰레드 실패는 경고로 — 인스타는 이미 올라갔다)
        print(f"::warning title=쓰레드 게시 실패::{str(e)[:300]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
