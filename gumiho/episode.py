#!/usr/bin/env python3
"""대국 기록(match.json) → 영상 비트 목록. 진행 순서·자막·화면 상태를 코드가 정한다.

비트 = {"kind", "voice", "text"(읽을 말 · 없으면 무음), "min_sec", "screen": 화면 상태}
형식의 핵심은 '극적 아이러니'다: 시청자는 처음부터 여우가 누군지 알고, 모든 발언 옆에 그 모델의
속마음(thought)을 본다. 출연자끼리는 서로의 속마음을 모른다.

진행자 구미의 대사는 사건에서 뽑은 사실(누가·누구를·몇 표)로 채우고, 말투 후보는 seed 로 고른다.
나중에 Claude 가 쓴 대사(host_script)가 있으면 그걸 우선한다.
"""
from __future__ import annotations

import random

HOST_VOICE = "F2"

INTRO = [
    "Welcome to Gumiho Games. I'm Gumi. Six AIs just sat down at my table, and only some of them will leave it.",
    "Good evening, and welcome to Gumiho Games. I'm Gumi, your host. Six AIs, one table, and one very hungry fox.",
    "Welcome back to Gumiho Games. I'm Gumi. Tonight six AIs play a game where lying is not just allowed. It's required.",
]
RULES = ("Tonight's game is Fox Hunt. One player is secretly my fox. One is a shaman who can see the truth at night. "
         "Everyone else is a villager. Each day they talk and vote someone out. Each night, the fox strikes. "
         "Banish the fox and the village wins. Keep the fox alive until only two remain, and the fox wins.")
SECRET = [
    "Here's our little secret. Only you and I know it. The fox is {fox}. The shaman is {shaman}.",
    "Now, lean in. The others don't know this, but you will. The fox tonight is {fox}, and the shaman is {shaman}.",
]
THOUGHTS = "And you get something they don't. Next to every word they say, you'll see what they're really thinking."
HINT = ["Before we start, a little gift from me. My fox is one of these three: {a}. Let's see what they do with it.",
        "A hint, because I'm generous tonight. The fox is one of {a}."]
POLL = ["Nobody leaves on day one. But let's see who they suspect.", "Day one ends with a suspicion poll. No one goes home, yet."]
POLL_END = ["Nobody leaves today. But {top} now has {n} eyes on them.", "No banishment today, but {top} collected {n} votes of suspicion."]
DAY = ["Day {d}. {n} players remain. Let's hear them talk.", "Morning, day {d}. {n} of them are still at the table.",
       "Day {d} begins. {n} players left, and one of them is lying."]
VOTE = ["Time to vote. Who gets banished?", "Enough talk. Let's vote.", "The table goes quiet. Votes, please."]
BANISH = ["{who} is banished with {v} votes. And {who} was... the {role}.",
          "With {v} votes, {who} leaves the table. {who} was the {role}."]
TIE = ["A tie between {a}. Nobody leaves today.", "The vote is split between {a}. No one is banished."]
NIGHT = ["Night falls. The shaman looks for the truth, and my fox looks for dinner.",
         "Night. Everyone closes their eyes. Well, almost everyone."]
INSPECT = ["{who} the shaman looks into {target}'s heart. {target} is {res}.",
           "The shaman, {who}, peeks at {target}. The answer: {res}."]
KILL = ["And the fox chooses {target}. {target} was the {role}.",
        "My fox takes {target} tonight. {target} was the {role}."]
END_FOX = ["Only two left, and one of them is my fox. {fox} wins Fox Hunt!",
           "The fox survives. {fox} fooled the whole table. That's my fox."]
END_VILLAGE = ["The fox is caught! {fox} was banished, and the village wins.",
               "They found my fox. {fox} is out, and the village takes the win."]
INTERVIEW = ["Before you go, I have a few questions for my players.", "Now that the masks are off, let's hear from them."]
OUTRO ="Who played best tonight? Who would you never trust again? Tell me in the comments. See you at the next table."

ROLE_WORD = {"fox": "FOX", "shaman": "SHAMAN", "villager": "VILLAGER"}


def _pick(rng: random.Random, pool: list[str]) -> str:
    return rng.choice(pool)


def build(match: dict) -> list[dict]:
    rng = random.Random(f"host:{match['seed']}")
    roles, ev = match["roles"], match["events"]
    names = [s["name"] for s in match["roster"]]
    voice = {s["name"]: s.get("voice") or "M1" for s in match["roster"]}
    fox = next(n for n, r in roles.items() if r == "fox")
    shaman = next(n for n, r in roles.items() if r == "shaman")
    alive, dead = list(names), {}
    phase = {"label": "FOX HUNT", "night": False}
    known = {"roles": False}
    beats: list[dict] = []

    def screen(**kw):
        s = {"alive": list(alive), "dead": dict(dead), "phase": dict(phase), "fox": fox, "shaman": shaman,
             "roles_known": known["roles"]}
        s.update(kw)
        return s

    def host(text, **kw):
        beats.append({"kind": "host", "voice": HOST_VOICE, "text": text, "min_sec": 2.0, "screen": screen(host=True, **kw)})

    # 콜드 오픈 — 여우의 속마음 한 줄(누군지는 아직 말하지 않는다)
    fox_thoughts = [e for e in ev if e.get("who") == fox and e.get("thought") and e["type"] in ("say", "vote", "kill")]
    hook = max(fox_thoughts, key=lambda e: len(e["thought"]), default=None)
    if hook:
        beats.append({"kind": "hook", "voice": HOST_VOICE,
                      "text": "One of these six AIs is lying to everyone else. This is what it was thinking.",
                      "min_sec": 4.0, "screen": screen(quote=hook["thought"])})
    host(_pick(rng, INTRO), title=True)
    for n in names:
        beats.append({"kind": "roll", "voice": voice[n], "text": f"{n}.", "min_sec": 1.1, "screen": screen(highlight=n)})
    host(RULES, rules=True)
    known["roles"] = True
    host(_pick(rng, SECRET).format(fox=fox, shaman=shaman), reveal_roles=True)
    host(THOUGHTS)

    for e in ev:
        t = e["type"]
        if t == "day_start":
            phase.update(label=f"DAY {e['day']}", night=False)
            host(_pick(rng, DAY).format(d=e["day"], n=len(alive)), card=f"DAY {e['day']}")
        elif t == "hint":
            host(_pick(rng, HINT).format(a=", ".join(e["names"][:-1]) + " or " + e["names"][-1]), hint=e["names"])
        elif t == "say":
            beats.append({"kind": "say", "voice": voice[e["who"]], "text": e["say"], "min_sec": 2.5,
                          "screen": screen(highlight=e["who"], say=e["say"], thought=e.get("thought", ""))})
        elif t in ("vote", "poll"):
            if not beats or beats[-1]["kind"] != "vote":
                host(_pick(rng, POLL if t == "poll" else VOTE), votes=[])
            prev = [b for b in beats if b["kind"] == "vote" and b["screen"]["phase"]["label"] == phase["label"]]
            rows = (prev[-1]["screen"]["votes"] if prev else []) + [[e["who"], e["vote"]]]
            lead = f"I suspect {e['vote']}." if t == "poll" else f"I vote {e['vote']}."
            spoken = f"{lead} {e.get('why', '')}".strip()
            beats.append({"kind": "vote", "voice": voice[e["who"]], "text": spoken, "min_sec": 1.6,
                          "screen": screen(highlight=e["who"], votes=rows, say=spoken, thought=e.get("thought", ""),
                                           poll=t == "poll")})
        elif t == "poll_tally":
            beats.append({"kind": "tally", "voice": None, "text": None, "min_sec": 2.4,
                          "screen": screen(tally=e["tally"], poll=True)})
            top = next(iter(e["tally"]))
            host(_pick(rng, POLL_END).format(top=top, n=e["tally"][top]), highlight=top)
        elif t == "tally":
            beats.append({"kind": "tally", "voice": None, "text": None, "min_sec": 2.4,
                          "screen": screen(tally=e["tally"])})
        elif t == "no_banish":
            host(_pick(rng, TIE).format(a=" and ".join(e["tied"])), tally_keep=True)
        elif t == "banish":
            alive.remove(e["who"])
            dead[e["who"]] = {"role": e["role"], "how": "banished"}
            host(_pick(rng, BANISH).format(who=e["who"], v=e["votes"], role=ROLE_WORD[e["role"]]),
                 highlight=e["who"], reveal=e["who"])
        elif t == "night_start":
            phase.update(label=f"NIGHT {e['night']}", night=True)
            host(_pick(rng, NIGHT), card=f"NIGHT {e['night']}")
        elif t == "inspect":
            res = "THE FOX" if e["is_fox"] else "not the fox"
            beats.append({"kind": "thought", "voice": None, "text": None, "min_sec": 3.5,
                          "screen": screen(highlight=e["who"], thought=e.get("thought", ""), secret=True)})
            host(_pick(rng, INSPECT).format(who=e["who"], target=e["target"], res=res), highlight=e["target"])
        elif t == "kill":
            beats.append({"kind": "thought", "voice": None, "text": None, "min_sec": 3.5,
                          "screen": screen(highlight=e["who"], thought=e.get("thought", ""), secret=True)})
            alive.remove(e["target"])
            dead[e["target"]] = {"role": e["role"], "how": "taken"}
            host(_pick(rng, KILL).format(target=e["target"], role=ROLE_WORD[e["role"]]),
                 highlight=e["target"], reveal=e["target"])
        elif t == "end":
            phase.update(label="RESULT", night=False)
            pool = END_FOX if e["winner"] == "fox" else END_VILLAGE
            host(_pick(rng, pool).format(fox=fox), highlight=fox, winner=e["winner"], reveal_all=True)
        elif t == "interview":
            if not beats or beats[-1]["kind"] != "interview":
                host(_pick(rng, INTERVIEW), reveal_all=True)
            beats.append({"kind": "interview", "voice": voice[e["who"]], "text": e["say"], "min_sec": 2.5,
                          "screen": screen(highlight=e["who"], say=e["say"], reveal_all=True,
                                           label=f"{e['who']} · {ROLE_WORD[e['role']]}")})
    if any(b["kind"] in ("interview",) or b["screen"].get("winner") for b in beats):
        host(OUTRO, reveal_all=True)
    for i, b in enumerate(beats):
        b["i"] = i
    return beats


def chapters(beats: list[dict]) -> list[tuple[int, str]]:
    """(비트 번호, 이름) — 유튜브 챕터용. 영상 시각은 렌더러가 붙인다."""
    out = [(0, "Cold open")]
    for b in beats:
        c = b["screen"].get("card")
        if c:
            out.append((b["i"], c.title()))
        elif b["screen"].get("rules"):
            out.append((b["i"], "The rules"))
        elif b["screen"].get("winner"):
            out.append((b["i"], "Result"))
    return out
