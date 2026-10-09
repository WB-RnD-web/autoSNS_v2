#!/usr/bin/env python3
"""쓰레드 2주 시험(pick_threads·upload_threads 글/투표/스포일러/답글) 오프라인 테스트 — 가짜 전송만, 실제 API 호출 없음."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import insta as I  # noqa: E402
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402
import pick_threads as T  # noqa: E402
import upload_threads as UT  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


SAMPLES = {k: json.load(open(os.path.join(HERE, "samples", f"{v}.json"), encoding="utf-8")) for k, v in P.EXEMPLAR.items()}
DAY = dt.date(2026, 10, 13)                         # 시험 기간 안의 아무 날(대본 날짜를 이 날로 바꿔 쓴다)
NOSLEEP = lambda _s: None  # noqa: E731
CREDS = {"user_id": "{THREADS_USER_ID}", "token": "TEST"}


def today_of(s: dict, d: dt.date = DAY) -> dict:
    return dict(json.loads(json.dumps(s)), date=d.isoformat())


def unspoil(text: str, e: dict) -> str:
    u = text.encode("utf-16-le")
    return u[e["offset"] * 2:(e["offset"] + e["length"]) * 2].decode("utf-16-le")


def raises(f, *a) -> bool:
    """RuntimeError 로 막히나."""
    try:
        f(*a)
    except RuntimeError:
        return True
    return False


def raises_value(f, *a) -> bool:
    try:
        f(*a)
    except ValueError:
        return True
    return False


def blocked_before_send(f, text) -> bool:
    """보내기 전에(호출 0) RuntimeError 로 막히나."""
    h = T.FakeHTTP()
    try:
        f(text, None, http=h, sleep=NOSLEEP, **CREDS)
    except RuntimeError:
        return not h.calls
    return False


def publish_fails_with_body(h) -> bool:
    try:
        UT.publish_text("안녕", None, http=h, sleep=NOSLEEP, **CREDS)
    except RuntimeError as e:
        return "fake failure" in str(e)
    return False


print("── 기간(코드가 정한다) ──")
ck("10/11 ~ 10/24 KST(양끝 포함 14일)", (T.THREADS_FROM, T.THREADS_TO) == (dt.date(2026, 10, 11), dt.date(2026, 10, 24))
   and (T.THREADS_TO - T.THREADS_FROM).days + 1 == 14)
ck("10/10·10/25 는 밖 · 10/11·10/24 는 안", not T.in_window(dt.date(2026, 10, 10)) and T.in_window(dt.date(2026, 10, 11))
   and T.in_window(dt.date(2026, 10, 24)) and not T.in_window(dt.date(2026, 10, 25)))
src = open(os.path.join(HERE, "pick_threads.py"), encoding="utf-8").read()
ck("기간을 레포 변수로 늘리지 않는다(변수는 끄기 INSTA_PICK_THREADS=0 만)",
   not re.search(r"environ.*THREADS_(FROM|TO)|env\.get\(\"THREADS_(FROM|TO)", src) and "INSTA_PICK_THREADS" in src)

print("── 반말(대본 해요체 끝맺음) ──")
PAIRS = [("끌리는 문 하나 골라 봐요", "끌리는 문 하나 골라 봐"), ("문어의 심장은 몇 개일까요?", "문어의 심장은 몇 개일까?"),
         ("딱 좋은 주예요. 오늘 10분만 해 봐요.", "딱 좋은 주야. 오늘 10분만 해 봐."), ("푹 자는 게 답이에요.", "푹 자는 게 답이야."),
         ("인연이 가까워요", "인연이 가까워"), ("그렇죠?", "그렇지?"), ("좋네요!", "좋네!"), ("알려 주세요", "알려 주세요"),
         ("지금 용기가 필요", "지금 용기가 필요"), ("사람 몸에서 가장 큰 장기는?", "사람 몸에서 가장 큰 장기는?"),
         ("이번 주 나에게 올 일", "이번 주 나에게 올 일"), ("미뤄 둔 일이 있거든요", "미뤄 둔 일이 있거든")]
got = [(a, T.banmal(a)) for a, _ in PAIRS]
ck("확실한 꼴만 바꾸고 모르는 꼴(세요·필요·명사)은 그대로", all(T.banmal(a) == b for a, b in PAIRS),
   [g for g, (a, b) in zip(got, PAIRS) if g[1] != b])

print("── 꼴마다 글·투표·답글(견본) ──")
plans = {k: T.plan_of(today_of(s)) for k, s in SAMPLES.items()}
ck("모든 견본: 검사 통과", all(not T.problems(pl) for pl in plans.values()), {k: T.problems(pl) for k, pl in plans.items()})
ck("형식: pick·card 캐러셀 4장 · quiz·balance 글+투표 · birth 그림 한 장",
   [(plans[k]["post"]["type"], plans[k]["post"]["images"], bool(plans[k]["post"]["poll"])) for k in P.FORMATS]
   == [("carousel", 4, False), ("text", 0, True), ("carousel", 4, False), ("text", 0, True), ("image", 1, False)],
   {k: (pl["post"]["type"], pl["post"]["images"]) for k, pl in plans.items()})
ck("답글: pick·card·quiz 만(balance·birth 없음)", [bool(plans[k]["reply"]) for k in P.FORMATS] == [True, True, True, False, False])
for k in ("pick", "card"):
    s, pl = today_of(SAMPLES[k]), plans[k]
    lines = pl["post"]["text"].split("\n")
    ck(f"{k}: 글 = headline 두 줄(반말) + '난 N번' 한 줄", lines[:2] == [T.banmal(x) for x in s["headline"]]
       and re.fullmatch(r"난 [1-4]번( 카드)?", lines[2]) and len(lines) == 3, lines)
    cap = [ln for ln in K.caption_of(s).splitlines() if re.match(r"[1-4]번 ", ln)]
    rl = pl["reply"]["text"].split("\n")
    fmt = [f"{j}번 {o['name']} — {o['result']}: {o['lines']}" for j, o in enumerate(s["options"], 1)]
    ck(f"{k}: 답글 = caption_of 와 같은 꼴 'N번 name — result: lines'(끝맺음만 반말)", cap == fmt and rl[0] == T.RESULT_HEAD
       and rl[1:] == [f"{j}번 {o['name']} — {T.banmal(o['result'])}: {T.banmal(o['lines'])}" for j, o in enumerate(s["options"], 1)],
       (rl, cap))
    ents = pl["reply"]["spoilers"]
    ok = len(ents) == 4 and all(unspoil(pl["reply"]["text"], e) == rl[j + 1][3:] and rl[j + 1].startswith(f"{j + 1}번 ")
                                for j, e in enumerate(ents))
    ck(f"{k}: 스포일러 4개 — 번호는 보이고 그 뒤(결과)만 가린다", ok, ents)
    ck(f"{k}: 우리 번호는 다시 돌려도 같다", T.plan_of(s)["post"]["text"] == pl["post"]["text"])
q, pl = today_of(SAMPLES["quiz"]), plans["quiz"]
r0 = q["rounds"][0]
ck("quiz: 글 = rounds[0].q(반말) · 투표 = choices 4개 그대로", pl["post"]["text"] == T.banmal(r0["q"])
   and pl["post"]["poll"] == r0["choices"], pl["post"])
ans = r0["choices"][r0["answer"]]
ck("quiz: 답글 = 정답 + why · 정답부터 스포일러", pl["reply"]["text"].startswith("정답은 ")
   and unspoil(pl["reply"]["text"], pl["reply"]["spoilers"][0]).startswith(ans + " — ")
   and len(pl["reply"]["spoilers"]) == 1 and ans not in pl["reply"]["text"][:pl["reply"]["spoilers"][0]["offset"]], pl["reply"])
b, pl = today_of(SAMPLES["balance"]), plans["balance"]
ck("balance: 글 = rounds[0] a vs b + 한 줄 · 투표 = a·b label 둘", pl["post"]["poll"] == [b["rounds"][0]["a"]["label"],
   b["rounds"][0]["b"]["label"]] and pl["post"]["text"].split("\n")[0] == " vs ".join(pl["post"]["poll"])
   and pl["post"]["text"].split("\n")[1] in T.BALANCE_LINES, pl["post"])
pl = plans["birth"]
ck("birth: 글 = 제목 한 줄 + '난 N월생이라 …' 한 줄", re.fullmatch(r".+\n난 (1[0-2]|[1-9])월생이라 .+", pl["post"]["text"]), pl["post"])

print("── 금지 말·주제 태그 하나 ──")
for k, pl in plans.items():
    s = today_of(SAMPLES[k])
    texts = [pl["post"]["text"]] + ([pl["reply"]["text"]] if pl["reply"] else [])
    ck(f"{k}: 주제 태그 하나 = 해시태그 첫 개(# 없이) · 본문엔 # 없음", pl["topic_tag"] == I.topic_tag(s)
       == s["hashtags"][0].lstrip("#") and not any("#" in t for t in texts), pl["topic_tag"])
    banned = [I.CHANNELS_LINE, "유튜브", "댓글로 번호", "댓글", K.SHARE[k], K.REPLY[k], "http", "오늘의 골라보기"]
    ck(f"{k}: 채널 줄·유튜브·댓글 부탁·인스타 고정 문구 없음", not [w for t in texts for w in banned if w in t])
bad = T.plan_of(today_of(SAMPLES["pick"]))
bad["post"]["text"] += "\n" + I.CHANNELS_LINE
ck("채널 줄이 들어가면 막는다", any("금지" in e for e in T.problems(bad)))
bad = T.plan_of(today_of(SAMPLES["quiz"]))
bad["post"]["text"] += " 댓글로 번호 남겨 줘"
ck("'댓글로 번호 남겨 줘' 미끼는 막는다", any("금지" in e for e in T.problems(bad)))
bad = T.plan_of(today_of(SAMPLES["balance"]))
bad["post"]["text"] += " 유튜브에서 더 봐"
ck("유튜브 언급은 막는다", any("금지" in e for e in T.problems(bad)))
bad = T.plan_of(dict(today_of(SAMPLES["birth"]), hashtags=[]))
ck("주제 태그가 없으면 막는다", any("주제 태그" in e for e in T.problems(bad)))

print("── 투표 한도(공식 문서: 2~4개 · 한 개 1~25자 · 글에만) ──")
ck("보기 4개 → option_a~d", UT.poll_attachment(["가", "나", "다", "라"]) == {"option_a": "가", "option_b": "나", "option_c": "다",
                                                                       "option_d": "라"})
ck("보기 2개 → option_a·b 만", UT.poll_attachment(["가", "나"]) == {"option_a": "가", "option_b": "나"})
ck("보기 5개·1개는 막는다", raises(UT.poll_attachment, list("가나다라마")) and raises(UT.poll_attachment, ["가"]))
ck("보기 25자는 되고 26자는 막는다", not raises(UT.poll_attachment, ["가" * 25, "나"]) and raises(UT.poll_attachment, ["가" * 26, "나"]))
ck("빈 보기·겹친 보기는 막는다", raises(UT.poll_attachment, ["", "나"]) and raises(UT.poll_attachment, ["가", "가"]))
bad = T.plan_of(today_of(SAMPLES["quiz"]))
bad["post"]["poll"] = ["가" * 26, "나"]
ck("problems: 26자 보기를 막는다", any("25자" in e for e in T.problems(bad)))
bad = T.plan_of(today_of(SAMPLES["pick"]))
bad["post"]["poll"] = ["1번", "2번"]
ck("problems: 캐러셀에 투표는 막는다(글에만)", any("글(TEXT)에만" in e for e in T.problems(bad)))
ck("모든 견본 투표 보기 ≤ 25자", all(len(o) <= 25 for pl in plans.values() for o in pl["post"]["poll"] or []))

print("── 스포일러(text_entities · UTF-16) ──")
ck("앞에 이모지가 있으면 UTF-16 으로 센다(😀=2)", UT.spoiler("😀 정답 3개", "3개") == {"entity_type": "SPOILER", "offset": 6, "length": 2})
ck("가릴 말이 글에 없으면 ValueError", raises_value(UT.spoiler, "정답", "없는 말"))
ck("스포일러 11개는 막는다", raises(UT._check_spoilers, "가" * 30, [UT.spoiler("가" * 30, "가", i) for i in range(11)]))
ck("글 밖 범위는 막는다", raises(UT._check_spoilers, "가나", [{"entity_type": "SPOILER", "offset": 1, "length": 5}]))
bad = T.plan_of(today_of(SAMPLES["quiz"]))
bad["reply"]["text"] = "🎉 " + bad["reply"]["text"]
ck("답글에 이모지가 있으면 막는다(offset 밀림 방지)", any("이모지" in e for e in T.problems(bad)))
emo = today_of(SAMPLES["pick"])
emo["options"][0]["lines"] = "요즘 너무 달렸어요 🏃 이번 주엔 쉬어 봐요 ✨"
pl = T.plan_of(emo)
ck("대본 결과에 이모지가 있어도 답글에선 빼고 올린다(막히지 않게)", not T.problems(pl) and "🏃" not in pl["reply"]["text"]
   and "달렸어요 이번 주엔 쉬어 봐" in pl["reply"]["text"], pl["reply"]["text"].split("\n")[1])

print("── 게시(가짜 전송) — 호출 모양·reply_to_id·ledger ──")


def setup(tmp: str, kind: str, d: dt.date = DAY, ig: bool = True, images: int | None = None) -> tuple[str, dict]:
    s = today_of(SAMPLES[kind], d)
    sp = os.path.join(tmp, f"{s['date']}_{kind}_{s['slug']}.json")
    json.dump(s, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    rd = os.path.join(tmp, "render")
    os.makedirs(rd, exist_ok=True)
    stem = f"{s['date']}_{kind}_{s['slug']}"
    n = T.plan_of(s)["post"]["images"] if images is None else images
    imgs = []
    for k in range(1, n + 1):
        p = os.path.join(rd, f"{stem}_th{k}.jpg")
        open(p, "wb").write(b"jpg")
        imgs.append(p)
    json.dump({"threads_images": imgs}, open(os.path.join(rd, f"{stem}_meta.json"), "w", encoding="utf-8"))
    if ig:
        json.dump({s["date"]: {"media_id": "IG1", "kind": kind, "slug": s["slug"]}},
                  open(os.path.join(rd, "posted.json"), "w", encoding="utf-8"))
    return sp, {"renders": rd, "ledger": os.path.join(rd, "threads_posted.json"), "ig_ledger": os.path.join(rd, "posted.json")}


def run(sp, paths, http, cloud=None, env=None, d=DAY):
    return T.post(sp, paths["renders"], paths["ledger"], paths["ig_ledger"], d, env=env or {}, http=http,
                  cloud=cloud or T.FakeCloud(), sleep=NOSLEEP, **CREDS)


def posts(http):
    return [(u.rsplit("/", 1)[-1], b) for m, u, b in http.calls if m == "POST"]


for kind in P.FORMATS:
    with tempfile.TemporaryDirectory() as tmp:
        sp, paths = setup(tmp, kind)
        http, cloud = T.FakeHTTP(), T.FakeCloud()
        rc = run(sp, paths, http, cloud)
        pl = T.plan_of(json.load(open(sp, encoding="utf-8")))
        ps = posts(http)
        containers = [b for ep, b in ps if ep == "threads"]
        publishes = [b for ep, b in ps if ep == "threads_publish"]
        tags = [b["topic_tag"] for b in containers if "topic_tag" in b]
        ck(f"{kind}: 성공(0) · 주제 태그는 본 글 컨테이너 하나에만", rc == 0 and tags == [pl["topic_tag"]], (rc, tags))
        top = [b for b in containers if not b.get("is_carousel_item") and not b.get("reply_to_id")]
        ck(f"{kind}: 본 글 컨테이너 하나 · media_type={ {'carousel': 'CAROUSEL', 'image': 'IMAGE', 'text': 'TEXT'}[pl['post']['type']]}",
           len(top) == 1 and top[0]["media_type"] == {"carousel": "CAROUSEL", "image": "IMAGE", "text": "TEXT"}[pl["post"]["type"]]
           and top[0]["text"] == pl["post"]["text"], top)
        if pl["post"]["type"] == "carousel":
            kids = [b for b in containers if b.get("is_carousel_item") == "true"]
            ck(f"{kind}: 그림 4장 → IMAGE 자식 4개(is_carousel_item) → CAROUSEL children 4개",
               len(kids) == 4 and all(b["media_type"] == "IMAGE" and b["image_url"].startswith("https://") for b in kids)
               and len(top[0]["children"].split(",")) == 4 and "topic_tag" not in kids[0])
        if pl["post"]["type"] == "image":
            ck(f"{kind}: IMAGE 한 장(image_url)", top[0]["image_url"].startswith("https://") and "poll_attachment" not in top[0])
        if pl["post"]["poll"]:
            pa = json.loads(top[0]["poll_attachment"])
            ck(f"{kind}: poll_attachment = option_a… 보기 그대로", list(pa.values()) == pl["post"]["poll"]
               and list(pa) == list(UT.POLL_KEYS[:len(pl["post"]["poll"])]), pa)
        else:
            ck(f"{kind}: 투표 없음", "poll_attachment" not in top[0])
        replies = [b for b in containers if b.get("reply_to_id")]
        led = json.load(open(paths["ledger"], encoding="utf-8"))[DAY.isoformat()]
        if pl["reply"]:
            post_id = led["post_id"]
            ck(f"{kind}: 답글 TEXT 하나 · reply_to_id = 게시된 본 글 id · 주제 태그 없음",
               len(replies) == 1 and replies[0]["reply_to_id"] == post_id and replies[0]["media_type"] == "TEXT"
               and "topic_tag" not in replies[0] and "poll_attachment" not in replies[0], (replies, post_id))
            ck(f"{kind}: 답글 text_entities = 스포일러 그대로(JSON)", json.loads(replies[0]["text_entities"]) == pl["reply"]["spoilers"]
               and replies[0]["text"] == pl["reply"]["text"])
            ck(f"{kind}: 게시 두 번(본 글 → 답글) · ledger 에 post·reply id", len(publishes) == 2 and led.get("reply_id")
               and led["reply_id"] != post_id, led)
            seq = [ep + ("·reply" if b.get("reply_to_id") else "") for ep, b in ps]
            ck(f"{kind}: 순서 = 본 글 게시가 끝난 뒤 답글 컨테이너", seq.index("threads·reply") > seq.index("threads_publish"), seq)
        else:
            ck(f"{kind}: 답글 없음 · 게시 한 번", not replies and len(publishes) == 1 and "reply_id" not in led, led)
        hosts = [c for c in cloud.calls if c[0] == "HOST"]
        ck(f"{kind}: 그림 공개 URL {pl['post']['images']}장 → 게시 뒤 전부 지운다",
           len(hosts) == pl["post"]["images"] and len([c for c in cloud.calls if c[0] == "CLEANUP"]) == len(hosts))
        n = len(http.calls)
        rc2 = run(sp, paths, http, cloud)
        ck(f"{kind}: 다시 돌려도 두 번 안 올린다(호출 0 · 0 반환)", rc2 == 0 and len(http.calls) == n, http.calls[n:])

print("── 답글만 실패했다가 다시 돌리면 답글만 ──")
with tempfile.TemporaryDirectory() as tmp:
    sp, paths = setup(tmp, "quiz")
    http = T.FakeHTTP(fail_on=lambda url, data: bool(data.get("reply_to_id")))
    try:
        run(sp, paths, http)
        raised = False
    except RuntimeError:
        raised = True
    led = json.load(open(paths["ledger"], encoding="utf-8"))[DAY.isoformat()]
    ck("답글 실패 → 예외 · ledger 엔 본 글 id 만", raised and led.get("post_id") and not led.get("reply_id"), led)
    http2 = T.FakeHTTP()
    rc = run(sp, paths, http2)
    ps = posts(http2)
    led2 = json.load(open(paths["ledger"], encoding="utf-8"))[DAY.isoformat()]
    ck("다시 돌리면 본 글은 그대로 · 답글 하나만(reply_to_id = 그 본 글)", rc == 0 and led2["post_id"] == led["post_id"]
       and [b.get("reply_to_id") for ep, b in ps if ep == "threads"] == [led["post_id"]] and led2.get("reply_id"), ps)

with tempfile.TemporaryDirectory() as tmp:
    sp, paths = setup(tmp, "pick", images=0)                # 다시 돌릴 때 그림이 없어도 답글만이면 된다
    json.dump({DAY.isoformat(): {"post_id": "P9", "kind": "pick", "slug": "door"}}, open(paths["ledger"], "w", encoding="utf-8"))
    http, cloud = T.FakeHTTP(), T.FakeCloud()
    rc = run(sp, paths, http, cloud)
    ck("캐러셀 글은 올라갔고 답글만 남았으면 그림 없이 답글만(reply_to_id = P9)", rc == 0 and not cloud.calls
       and [b.get("reply_to_id") for ep, b in posts(http) if ep == "threads"] == ["P9"], posts(http))

print("── 건너뛰기(호출 0) ──")
CASES = [("기간 전(10/10)", dict(d=dt.date(2026, 10, 10)), {}), ("기간 뒤(10/25)", dict(d=dt.date(2026, 10, 25)), {}),
         ("INSTA_PICK_THREADS=0", {}, {"INSTA_PICK_THREADS": "0"}), ("수동 실행", {}, {"GITHUB_EVENT_NAME": "workflow_dispatch"}),
         ("인스타가 안 올라감", dict(ig=False), {})]
for name, kw, env in CASES:
    with tempfile.TemporaryDirectory() as tmp:
        d = kw.get("d", DAY)
        sp, paths = setup(tmp, "pick", d, ig=kw.get("ig", True))
        http = T.FakeHTTP()
        rc = run(sp, paths, http, env=env, d=d)
        ck(f"{name} → 올리지 않는다(0 · 호출 0 · ledger 없음)", rc == 0 and not http.calls and not os.path.exists(paths["ledger"]))
with tempfile.TemporaryDirectory() as tmp:
    sp, paths = setup(tmp, "pick")
    http = T.FakeHTTP()
    rc = run(sp, paths, http, d=DAY + dt.timedelta(days=1))
    ck("오늘 대본이 아니면 안 올린다", rc == 0 and not http.calls)
    json.dump({DAY.isoformat(): {"media_id": "IG1", "slug": "other"}}, open(paths["ig_ledger"], "w", encoding="utf-8"))
    rc = run(sp, paths, http)
    ck("인스타에 올라간 대본과 slug 가 다르면 안 올린다", rc == 0 and not http.calls)
with tempfile.TemporaryDirectory() as tmp:
    sp, paths = setup(tmp, "pick", images=0)
    http = T.FakeHTTP()
    rc = run(sp, paths, http)
    ck("쓰레드 그림이 없으면 막힘(1) · 호출 0", rc == 1 and not http.calls)

print("── upload_threads 글 함수 ──")
http = T.FakeHTTP()
tid = UT.publish_text("안녕", "심리테스트", poll=["가", "나"], http=http, sleep=NOSLEEP, **CREDS)
c = http.calls[0][2]
ck("publish_text: TEXT + topic_tag + poll_attachment → 상태 확인 → threads_publish", tid == "dry2" and c["media_type"] == "TEXT"
   and c["topic_tag"] == "심리테스트" and json.loads(c["poll_attachment"]) == {"option_a": "가", "option_b": "나"}
   and http.calls[1][0] == "GET" and http.calls[2][1].endswith("/threads_publish") and http.calls[2][2]["creation_id"] == "dry1")
ck("publish_text: 500자 넘으면 보내기 전에 막는다(호출 0)", blocked_before_send(UT.publish_text, "가" * 501))
ck("publish_text: 이모지는 UTF-8 바이트로 센다(🎉×125 = 500 OK · ×126 막힘)", not blocked_before_send(UT.publish_text, "🎉" * 125)
   and blocked_before_send(UT.publish_text, "🎉" * 126))
h = T.FakeHTTP()
UT.publish_reply("P1", "정답은 3개", spoilers=[UT.spoiler("정답은 3개", "3개")], http=h, sleep=NOSLEEP, **CREDS)
ck("publish_reply: reply_to_id·text_entities · 주제 태그 없음", h.calls[0][2]["reply_to_id"] == "P1"
   and json.loads(h.calls[0][2]["text_entities"]) == [{"entity_type": "SPOILER", "offset": 4, "length": 2}]
   and "topic_tag" not in h.calls[0][2])
ck("publish_reply: 부모 id 가 없으면 막는다", raises(UT.publish_reply, "", "x"))
ck("publish_text: 게시 실패(비200) → RuntimeError(메타 에러 본문 포함)", publish_fails_with_body(
   T.FakeHTTP(fail_on=lambda u, d: u.endswith("/threads_publish"))))
h = T.FakeHTTP()
UT.publish_image("https://x/1.jpg", "글", "타로", http=h, sleep=NOSLEEP, spoiler_media=True, **CREDS)
ck("publish_image: is_spoiler_media 를 줄 수 있다(기본은 안 보냄)", h.calls[0][2].get("is_spoiler_media") == "true")
h = T.FakeHTTP()
UT.publish_carousel(["https://x/1.jpg", "https://x/2.jpg"], "글", "타로", http=h, sleep=NOSLEEP, **CREDS)
ck("publish_carousel: 예전 호출 그대로(스포일러 안 보냄)", all("is_spoiler_media" not in c[2] and "text_entities" not in c[2]
                                                          for c in h.calls if c[0] == "POST"))

print("── 쓰레드 그림(렌더) ──")
with tempfile.TemporaryDirectory() as tmp:
    from PIL import Image
    for k in P.FORMATS:
        s = SAMPLES[k]
        a = K.assets(s, tmp, True)
        segs, _ = K.plan(s, {t: 1.0 for t in K.says_of(s)})
        pa = K.Painter(s, a, segs)
        files = K.threads_images(pa, s, tmp, f"x_{k}")
        sizes = [Image.open(f).size for f in files]
        want = {"pick": [(1080, 1080)] * 4, "card": [(1080, 1080)] * 4, "birth": [(1080, 1350)]}.get(k, [])
        ck(f"{k}: 쓰레드 그림 {len(want)}장 {want[:1]}", sizes == want, sizes)

print("── 워크플로 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "insta-pick.yml"), encoding="utf-8").read()
steps = re.split(r"(?m)^      - ", wf)
st = next((x for x in steps if "pick_threads.py post" in x), "")
ig = next((x for x in steps if "pick_plan.py post" in x), "")
ck("쓰레드 단계는 인스타 게시 단계 뒤", wf.index("pick_plan.py post") < wf.index("pick_threads.py post"))
ck("쓰레드 단계: push 때만 · 인스타 게시 성공 뒤 · continue-on-error",
   "github.event_name == 'push'" in st and "steps.post.outcome == 'success'" in st and "continue-on-error: true" in st
   and "id: post" in ig, st[:400])
ck("쓰레드 토큰은 쓰레드 단계에만(인스타 단계엔 없음)", "secrets.THREADS_ACCESS_TOKEN" in st and "secrets.THREADS_USER_ID" in st
   and "THREADS_ACCESS_TOKEN" not in ig)
ck("쓰레드 단계는 자기 테스트를 먼저 돈다(인스타 테스트 단계는 그대로)", "test_pick_threads.py" in st
   and st.index("test_pick_threads.py") < st.index("pick_threads.py post"))
ck("쓰레드 실패는 경고로 보인다(잡은 실패로 안 만든다)", "steps.threads.outcome == 'failure'" in wf and "::warning" in wf
   and "GITHUB_STEP_SUMMARY" in wf)
ck("쓰레드 ledger 는 따로 캐시(인스타 ledger 캐시는 그대로)", "output/insta_pick_render/threads_posted.json" in wf
   and "insta-pick-threads-ledger-" in wf and "key: insta-pick-ledger-${{ github.run_id }}" in wf)
code = "\n".join(ln for ln in wf.splitlines() if not ln.strip().startswith("#"))
ck("기간은 레포 변수가 아니라 코드(INSTA_THREADS 변수·날짜 조건에 기대지 않는다)", "vars.INSTA_THREADS " not in code
   and "vars.INSTA_THREADS}" not in code and not re.search(r"THREADS_(FROM|TO)|2026-10-(11|24)", code))

print(f"\n{'✅ 전부 통과' if not FAIL else f'❌ 실패 {FAIL}'}")
sys.exit(1 if FAIL else 0)
