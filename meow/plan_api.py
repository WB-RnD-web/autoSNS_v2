#!/usr/bin/env python3
"""Meow Remix 매일 기획 — Claude API + 웹 검색으로 그날 한 편(5초 컷 2개)을 쓴다(2026-11-09).

왜: 11/09 사용자가 HD 견본 3편을 보고 "괜찮네 매일 쇼츠 PR 진행해줘". 고양이 AI 쇼츠는 '지금 뜨는 것'(밈·계절·음식)을
  우리 꼴로 바꾸는 게 핵심이라 매일 웹을 보고 쓴다. 루틴에 '~해라'라고 맡기지 않고 코드가 정한다:
  ① 꼴은 요일로(FORMAT_BY_WEEKDAY) ② 음악은 꼴에 맞는 곡 중에서(어제와 다르게) ③ 2컷째는 반드시 1컷 그림 edit(같은 고양이)
  ④ 검사(render.check_concept + 아래 check)를 못 넘으면 오류를 붙여 다시(최대 3번) — 그래도 안 되면 그날은 skip.
결과: <날짜>.json = {"date", "concepts": [편 하나]}(render.py·post.py 가 그대로 읽는 모양) 또는 {"date", "skip", "concepts": []}
      <날짜>_api.json = 모델·시도·토큰·검색·달러. 크레딧이 바닥나면 API 가 거절할 뿐 돈은 안 나간다(결제 수단 없음).
★11/13 하루 세 편(사용자 "빈도가 너무 낮다" → "ㄱㄱㄱ"): 편(slot) a·b·c — a = 매일 변신(견본 중 유일하게 846회 나온 꼴).
  파일은 a = <날짜>.json(예전 그대로) · b = <날짜>-b.json · c = <날짜>-c.json …
★11/14 하루 최대 12편(사용자 "API 크레딧 월 160~180달러 정도 쓰게"): 편 a~l. 실제 편 수는 워크플로 변수 MEOW_SLOTS.
  b 부터는 밈·춤·게임·변신을 요일로 돌린다. 꼴마다 곡이 3~10곡뿐이라 겹침 규칙은 오래된 것부터 풀고 바로 앞 편과는 끝까지 다르게.

    python meow/plan_api.py write --day 2026-11-10 --dir /tmp/data-meow [--slot b]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R  # noqa: E402
import analyst as AN  # noqa: E402 — 분석 담당(11/14): 새 채널 최근 쇼츠 성적

MODEL = os.environ.get("MEOW_PLAN_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("MEOW_PLAN_EFFORT", "high")
PRICE = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20)}   # 입력, 출력, 캐시 읽기(달러/100만)
SEARCH_USD = 0.01
MAX_SEARCH, MAX_FETCH = 6, 3
TRIES = 3

SLOTS = tuple("abcdefghijkl")          # 하루 최대 12편 — 실제로 쓰는 편은 워크플로 변수 MEOW_SLOTS(기본 12편)
# a 는 매일 변신(morph) — 고양이 AI 쇼츠의 간판이고 견본 중 혼자 846회(11/13). b 부터는 넷을 요일로 돌린다(월=0 … 일=6).
CYCLE = ("meme", "dance", "game", "morph")
USED_MAX = 300                           # 모델에게 보내는 '이미 쓴 소재' 줄 수(하루 12편이면 한 달이 360줄)
FORMAT_INFO = {
    "morph": "A food or object turns into a kitten. Shot 1: the food in a cosy real setting with only a small kitten hint "
             "(two tiny ears or a tail tip) on one piece. Shot 2 (edit of shot 1): that one piece is now a tiny kitten whose "
             "fur looks like the food, in the same spot, waking up. Add \"xfade\": 0.6 on shot 2.",
    "dance": "A cat dances on its hind legs to the beat in a fun setting (disco, kitchen, rooftop, festival). Shot 2 (edit of "
             "shot 1): the same cat in the same place doing the next move or a final pose.",
    "meme": "A relatable or trending meme moment acted out by a cat (work, school, cooking, gym, weather, holidays, the "
            "season). The caption is the meme line. Shot 2 (edit of shot 1): the same cat in the next beat or the punchline.",
    "game": "A cat in a game-like or arcade moment (claw machine, gaming chair, retro arcade, board game, carnival game) with "
            "no real game characters, brands or readable screens. Shot 2 (edit of shot 1): the same cat at the win/fail beat.",
}
MOODS_BY_FORMAT = {"morph": {"cute", "morph"}, "dance": {"dance", "cool"}, "meme": None,
                   "game": {"game", "silly", "chaos", "sneaky"}}
EXAMPLE = os.path.join(HERE, "example_daily.json")
CONCEPTS = os.path.join(HERE, "concepts")

WRITER = """You plan one of today's YouTube Shorts for "Meow Remix" (@MeowRemixCats): photorealistic AI cat videos with
music only (no voice, no script). Each Short is two 5-second shots (about 10 seconds): an image model draws shot 1, an
image-edit model makes shot 2 from the shot 1 picture (so it stays the same cat), and an image-to-video model animates each.

Task: today's idea in the given format. Use web_search to see which cat or AI-cat Shorts, memes, seasonal moments or food
trends are taking off right now (last 7-30 days) and follow what makes them work (the hook, the transformation, the
relatable beat, the title pattern), but make it our own: never copy a video, character or brand. If nothing current fits,
use a strong evergreen idea (leave trend.evidence empty).

Writing
- Viewers: global (English title and caption) and Korean Instagram (ko_line). Cute, funny, cosy. No gore, no animals in
  danger or pain, no politics, no real people.
- caption: the on-screen hook, English, at most 40 characters.
- title: English, at most 70 characters, one or two emoji at the end, no hashtags.
- en_line: one English sentence for the description. ko_line: one short casual Korean line with one emoji.
- tags: 5-10 English keywords including "cat" and "ai cat". hashtags: 5-7, mixing Korean and English, including "#cat".
- track: one file from today's allowed list, different from yesterday's.

Shot 1 "image"
- Photorealistic, vertical composition, the cat fully in frame and clearly visible, one simple setting.
- Say what to draw, positively. Never ask for text, letters, signs, logos, screens with writing, phones, brands, real
  people, or game or film characters. No humans or human hands at all.
- Describe the cat precisely (breed or look, coat colour and pattern, eye colour) so the edit can keep it.

Shot 2 "edit" (made from the shot 1 picture)
- Start with "Keep exactly the same <the cat from shot 1> with the same fur pattern, face and eye color." then describe the
  change (the next pose or moment, or the same cat in a new place) and end with "Photorealistic, vertical composition."
- For morph, the edit turns the hinted piece into the tiny kitten in the same spot.

"motion" (both shots, for the image-to-video model)
- One simple continuous action that fits 5 seconds (blink, look around, paw tap, head tilt, sway to the beat, stretch,
  pounce in place). Background motion is welcome (steam, snow, lights, leaves).
- The action starts right away in the very first frame — no slow build-up or still opening (viewers swipe in 1 second).
- Keep the body shape: no yawning or wide-open mouth, no fast spins, no leaving the frame, nothing appearing from nowhere.
- Always say the cat stays fully in frame with four normal legs and end with "Photorealistic, smooth natural motion,
  static camera."

Output: one JSON object only (no code fences) with the keys of the example: slug, track, caption, title, en_line, ko_line,
tags, hashtags, shots (exactly 2), cover_shot (1 or 2), trend {"why_now", "pattern", "evidence": [{"title", "url"}]} with
URLs only from your searches. Do not set id, format, engine or seed. If the code returns errors, fix them and return the
whole JSON again."""


def fmt_of(day: dt.date, slot: str = "a") -> str:
    i = SLOTS.index(slot)
    return "morph" if i == 0 else CYCLE[(day.weekday() + i - 1) % len(CYCLE)]


def doc_name(day: dt.date, slot: str = "a") -> str:
    """편 a 는 예전 이름(<날짜>.json) 그대로 — post.py·인스타·지난 기록이 그대로 읽는다."""
    return day.isoformat() + ("" if slot == "a" else f"-{slot}")


def tracks_for(fmt: str) -> list[str]:
    want = MOODS_BY_FORMAT[fmt]
    return [f for f, t in R.tracks().items() if want is None or want & set(t.get("moods", []))]


def concept_id(day: dt.date, slot: str = "a") -> str:
    return "m" + day.strftime("%y%m%d") + ("" if slot == "a" else slot)


def seed_of(day: dt.date, slot: str = "a") -> int:
    key = day.isoformat() if slot == "a" else f"{day.isoformat()}-{slot}"
    return int(hashlib.sha1(key.encode()).hexdigest()[:6], 16) % 90000 + 10000


def history(data_dir: str) -> list[dict]:
    """지금까지 쓴 편(data/meow 의 날짜 파일 + 레포의 견본 기획) — 오래된 것부터."""
    rows = []
    days = glob.glob(os.path.join(data_dir, "20??-??-??.json")) + glob.glob(os.path.join(data_dir, "20??-??-??-?.json"))
    for p in sorted(glob.glob(os.path.join(CONCEPTS, "*.json"))) + sorted(days):
        try:
            d = R.load(p)
        except Exception:  # noqa: BLE001
            continue
        for c in d.get("concepts") or []:
            rows.append({"date": d.get("date", ""), "slug": c.get("slug", ""), "title": c.get("title", ""),
                         "format": c.get("format", ""), "track": c.get("track", ""),
                         "cat": (c.get("shots") or [{}])[0].get("image", "")[:110]})
    return rows


def _track_of(data_dir: str, name: str) -> str | None:
    try:
        cs = R.load(os.path.join(data_dir, name + ".json")).get("concepts") or []
    except Exception:  # noqa: BLE001
        return None
    return cs[0].get("track") if cs else None


def avoid_tracks(data_dir: str, day: dt.date, slot: str = "a") -> list[str]:
    """쓰면 안 되는 곡 = 어제 같은 편의 곡 + 오늘 앞 편들의 곡(같은 음악이 이어지지 않게).
    하루 편이 많으면 그 꼴 곡(3~10곡)이 동난다 → 오래된 것부터 풀어 한 곡은 남긴다(바로 앞 편 곡은 끝까지 피한다)."""
    names = [doc_name(day - dt.timedelta(days=1), slot)] + [doc_name(day, s) for s in SLOTS[:SLOTS.index(slot)]]
    raw = [t for t in (_track_of(data_dir, n) for n in names) if t]
    out = list(dict.fromkeys(reversed(raw)))[::-1]        # 겹치면 가장 최근 자리만 남긴다(오래된 → 최근)
    allowed = set(tracks_for(fmt_of(day, slot)))
    while len(out) > 1 and not (allowed - set(out)):
        out.pop(0)
    return out


def user_message(day: dt.date, data_dir: str, slot: str = "a") -> str:
    fmt = fmt_of(day, slot)
    hist = history(data_dir)
    recent = [h for h in hist if h["date"] and h["date"] < day.isoformat()][-10:]
    today = [h for h in hist if h["date"] == day.isoformat()]
    tr = R.tracks()
    av = avoid_tracks(data_dir, day, slot)
    return "\n".join([
        f"# Today (KST) {day.isoformat()} ({day.strftime('%A')}) — Short #{SLOTS.index(slot) + 1} of the day — format: {fmt}",
        FORMAT_INFO[fmt], "",
        "## Allowed tracks today (file — title — moods)",
        *[f"- {f} — {tr[f]['title']} — {', '.join(tr[f].get('moods', []))}" for f in tracks_for(fmt)],
        f"Tracks already used (do not use): {', '.join(av) or '(none)'}",
        "\n## Example (schema: copy the keys, not the idea)\n" + json.dumps(R.load(EXAMPLE)["concept"], ensure_ascii=False),
        "\n## Today's other Shorts (make this one clearly different: another cat, setting and idea)",
        *([f"- {h['format']} · {h['title']} · {h['track']} · {h['cat']}" for h in today] or ["- (none yet)"]),
        "\n## Recent days (vary the cat, the setting and the music)",
        *[f"- {h['date']} {h['format']} · {h['title']} · {h['track']} · {h['cat']}" for h in recent],
        "\n## Used ideas (off limits: slug / title)",
        *[f"- {h['slug']} / {h['title']}" for h in hist[-USED_MAX:]],
        *AN.lessons(AN.load(data_dir)),          # ★11/14 분석 담당 — 새 채널 최근 쇼츠 성적(stats.json 이 있을 때만)
    ])


def parse(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.S)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise ValueError("JSON 객체가 없다")
    out = json.loads(t[a:b + 1])
    if not isinstance(out, dict):
        raise ValueError("최상위가 객체가 아니다")
    return out


def norm(u: str) -> str:
    u = (u or "").strip().split("#")[0].rstrip("/")
    return re.sub(r"^http://", "https://", u).lower()


def finalize(c: dict, day: dt.date, slot: str = "a") -> dict:
    """코드가 정하는 칸(모델이 넣어도 덮어쓴다)."""
    c = dict(c)
    c.update({"id": concept_id(day, slot), "format": fmt_of(day, slot), "engine": "14b", "seed": seed_of(day, slot)})
    return c


def check(c: dict, day: dt.date, data_dir: str, seen: set, slot: str = "a") -> list[str]:
    errs = R.check_concept(c)
    if errs:
        return errs
    fmt, sh = fmt_of(day, slot), c["shots"]
    if len(sh) != 2:
        errs.append("컷은 정확히 2개(5초 + 5초)")
    else:
        if not sh[0].get("image"):
            errs.append("shots[0] 은 image")
        e2 = sh[1].get("edit") or ""
        if not e2 or int(sh[1].get("from", 1)) != 1:
            errs.append("shots[1] 은 shot 1 그림의 edit(같은 고양이) — image 를 쓰지 않는다")
        elif not e2.startswith("Keep exactly the same"):
            errs.append("shots[1].edit 는 'Keep exactly the same …' 로 시작")
        if fmt == "morph" and not sh[1].get("xfade"):
            errs.append("morph 는 shots[1] 에 xfade(0.6)")
    if c["track"] not in tracks_for(fmt):
        errs.append(f"track 은 오늘({fmt}) 허용 곡 중 하나: {tracks_for(fmt)}")
    if c["track"] in avoid_tracks(data_dir, day, slot):
        errs.append("track 이 어제 같은 편이나 오늘 앞 편과 같다")
    if len(c["caption"]) > 40:
        errs.append(f"caption {len(c['caption'])}자 > 40")
    if len(c["title"]) > 70 or "#" in c["title"]:
        errs.append("title 은 70자 안·해시태그 없이")
    if not re.search(r"[가-힣]", c.get("ko_line", "")):
        errs.append("ko_line 은 한국어")
    tags, hs = c.get("tags") or [], c.get("hashtags") or []
    if not (5 <= len(tags) <= 15) or not all(isinstance(t, str) and t for t in tags):
        errs.append("tags 5~15개")
    if not (4 <= len(hs) <= 8) or not all(isinstance(h, str) and h.startswith("#") and " " not in h for h in hs) \
            or "#cat" not in [h.lower() for h in hs]:
        errs.append("hashtags 4~8개 · # 로 시작 · 띄어쓰기 없이 · #cat 포함")
    if c.get("cover_shot") not in (1, 2):
        errs.append("cover_shot 은 1 또는 2")
    taken = {h["slug"] for h in history(data_dir)} | {h["title"].lower() for h in history(data_dir)}
    if c["slug"] in taken or c["title"].lower() in taken:
        errs.append("이미 쓴 slug·제목이다")
    for x in (c.get("trend") or {}).get("evidence") or []:
        if norm(x.get("url", "")) not in seen:
            errs.append(f"trend.evidence {x.get('url')} 는 이 대화의 검색·읽기 결과에 없다")
    return errs


def _walk_urls(obj, out: set, depth: int = 0):
    if depth > 6 or obj is None:
        return
    if isinstance(obj, (list, tuple)):
        for x in obj:
            _walk_urls(x, out, depth + 1)
        return
    items = obj.items() if isinstance(obj, dict) else (
        (k, getattr(obj, k)) for k in ("url", "content", "source") if hasattr(obj, k))
    for k, v in items:
        if k == "url" and isinstance(v, str):
            out.add(norm(v))
        elif isinstance(v, (dict, list, tuple)) or hasattr(v, "__dict__"):
            _walk_urls(v, out, depth + 1)


def tool_urls(content, seen: set) -> None:
    for b in content or []:
        t = b.get("type", "") if isinstance(b, dict) else getattr(b, "type", "")
        if t in ("web_search_tool_result", "web_fetch_tool_result"):
            _walk_urls(b.get("content") if isinstance(b, dict) else getattr(b, "content", None), seen)


def _usage_add(tok: dict, usage) -> None:
    for k, f in (("input", "input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                 ("cache_read", "cache_read_input_tokens"), ("output", "output_tokens")):
        tok[k] += getattr(usage, f, 0) or 0
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        tok["web_search"] += getattr(stu, "web_search_requests", 0) or 0
        tok["web_fetch"] += getattr(stu, "web_fetch_requests", 0) or 0


def ask(client, messages: list[dict], tok: dict, seen: set, max_pauses: int = 8) -> str:
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCH},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_FETCH}]
    msgs = list(messages)
    for _ in range(max_pauses + 1):
        with client.messages.stream(model=MODEL, max_tokens=16000, system=WRITER, messages=msgs, tools=tools,
                                    extra_body={"output_config": {"effort": EFFORT}}) as st:
            msg = st.get_final_message()
        _usage_add(tok, msg.usage)
        tool_urls(msg.content, seen)
        if msg.stop_reason == "pause_turn":
            msgs = msgs + [{"role": "assistant", "content": msg.content}]
            continue
        if msg.stop_reason == "refusal":
            raise RuntimeError("모델이 답을 거절했다(refusal)")
        if msg.stop_reason == "max_tokens":
            raise RuntimeError("출력이 max_tokens 에서 잘렸다")
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    raise RuntimeError(f"pause_turn 이 {max_pauses}번 넘게 이어졌다")


def _save(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def write(day: dt.date, data_dir: str, client=None, slot: str = "a") -> dict:
    os.makedirs(data_dir, exist_ok=True)
    tok = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "web_search": 0, "web_fetch": 0}
    info = {"date": day.isoformat(), "slot": slot, "format": fmt_of(day, slot), "model": MODEL, "effort": EFFORT,
            "tokens": tok}
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    messages = [{"role": "user", "content": [{"type": "text", "text": user_message(day, data_dir, slot),
                                              "cache_control": {"type": "ephemeral"}}]}]
    seen: set = set()
    errs: list[str] = []
    history_: list[list[str]] = []
    concept = None
    n = 0
    for n in range(1, TRIES + 1):
        text = ask(client, messages, tok, seen)
        try:
            concept = finalize(parse(text), day, slot)
            errs = check(concept, day, data_dir, seen, slot)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            errs = [f"출력을 읽을 수 없다: {e}"]
        history_.append(errs)
        print(f"   시도 {n}: " + ("✅ 통과" if not errs else f"오류 {len(errs)}개"))
        if not errs:
            break
        for x in errs:
            print(f"     - {x[:300]}")
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The code checks failed. Fix these and return the whole JSON again:\n"
                                                 + "\n".join(f"- {x}" for x in errs)}]
    if errs:                                       # 세 번 다 못 넘으면 그날은 건너뛴다(틀린 편을 만들지 않는다)
        doc = {"date": day.isoformat(), "skip": "검사 실패: " + " | ".join(errs)[:800], "concepts": []}
    else:
        doc = {"date": day.isoformat(), "concepts": [concept]}
    _save(os.path.join(data_dir, doc_name(day, slot) + ".json"), doc)
    pi, po, pc = PRICE.get(MODEL, PRICE["claude-opus-5-5"])
    usd = (tok["input"] * pi + tok["cache_write"] * pi * 1.25 + tok["cache_read"] * pc + tok["output"] * po) / 1e6 \
        + tok["web_search"] * SEARCH_USD
    info.update({"ok": not errs, "tries": n, "usd": round(usd, 3), "errors": errs, "history": history_,
                 "slug": (concept or {}).get("slug") if not errs else None})
    _save(os.path.join(data_dir, doc_name(day, slot) + "_api.json"), info)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Meow Remix 매일 기획(Claude API)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--day", required=True)
    w.add_argument("--dir", required=True)
    w.add_argument("--slot", default="a", choices=SLOTS)
    p = sub.add_parser("prompt")                      # API 없이 모델에게 갈 글만 본다
    p.add_argument("--day", required=True)
    p.add_argument("--dir", required=True)
    p.add_argument("--slot", default="a", choices=SLOTS)
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.day)
    if a.cmd == "prompt":
        print(WRITER + "\n\n=====\n" + user_message(day, a.dir, a.slot))
        return 0
    info = write(day, a.dir, slot=a.slot)
    t = info["tokens"]
    print(f"🐱 {info['model']} · {info['date']} 편 {a.slot} {info['format']} · 시도 {info['tries']} · 검색 {t['web_search']} · "
          f"읽기 {t['web_fetch']} · 출력 {t['output']:,} 토큰 · 약 {info['usd']}달러 · {info.get('slug') or '건너뜀'}")
    return 0                       # 검사 실패도 그날 skip 으로 남겼다 — 같은 날 다시 돌며 돈을 쓰지 않게 올리기까지 간다


if __name__ == "__main__":
    sys.exit(main())
