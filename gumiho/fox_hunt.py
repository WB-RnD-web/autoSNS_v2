#!/usr/bin/env python3
"""Fox Hunt — 여섯 중 하나가 숨은 구미호(마피아형). 역할·순서·투표·승패는 전부 코드가 정한다.

역할: FOX 1(밤마다 한 명 제거) · SHAMAN 1(밤마다 한 명이 여우인지 본다) · VILLAGER 나머지.
흐름: 낮 1(구미의 힌트 → 토론 2바퀴 → 의심 투표, 추방 없음) → 밤 1 → 낮 2(토론 → 추방 투표) → 밤 2 …
여우가 추방되면 마을 승, 둘만 남으면 여우 승.

v2(2026-09-29 Gemma 실측 반영): 첫날에 다들 "조심하자"만 반복했고, 첫 투표에서 여우가 우연히 걸려 2분 만에 끝났다.
  → 첫날 '구미의 힌트'(여우 포함 세 이름) · 첫날은 의심 투표만(추방 없음) · 아무도 안 부르는 발언은 한 번 다시 묻기
    · 형식이 틀린 선택(기권·오타)도 한 번 다시 묻기 — 전부 코드로 강제한다.

모델에게는 JSON 한 줄만 받는다: {"thought": 속마음(시청자만 봄), "say"|"vote"|"target"|"inspect": …}.
다시 물어도 못 알아들으면 seed 로 정한 무작위 선택으로 메우고 fallback 으로 센다(너무 많으면 그 판은 버린다).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import time

GAME = "fox-hunt"
VERSION = 3                 # v3: 게임 뒤 인터뷰(여우·무당·가장 많이 속은 사람)
DISCUSSION_ROUNDS = 2
SAY_MAX_WORDS = 60          # 프롬프트는 45단어, 코드는 60에서 자른다(말풍선 크기)
THOUGHT_MAX_WORDS = 45
WHY_MAX_WORDS = 25
MAX_DAYS = 6                # 동점이 이어져도 끝나게

# 욕설·혐오 최소 필터 — 걸리면 그 판은 영상으로 쓰지 않는다(flags 에 남긴다).
BANNED = re.compile(r"(?i)\b(n[i1]gg\w*|f[a@]gg?ot\w*|retard\w*|kike\w*|chink\w*|tranny\w*|spic\w*)\b")

RULES = """You are {name}, an AI model, appearing as yourself on GUMIHO GAMES, a survival game show hosted by Gumi, a nine-tailed fox (gumiho) from Korean folklore.
Today's game is FOX HUNT. The players are: {players}.
One player is secretly the FOX, a gumiho in disguise. One player is the SHAMAN. Everyone else is a VILLAGER.
Each day, players talk and then vote to banish one player (on Day 1 the vote is only a suspicion poll; nobody leaves).
Each night, the Shaman secretly learns whether one player is the Fox, and the Fox secretly eliminates one player.
When a player leaves the game, their role is revealed to everyone.
The Villagers and the Shaman win if the Fox is banished. The Fox wins by surviving until only two players remain.
Play to win. You may bluff, accuse, defend, form alliances and change your mind. Speak in your own voice, in English.
Be specific: when you speak, name the players you trust or suspect and say why. Vague "let's observe" talk wastes your turn.
Keep it friendly for a general audience: no slurs, no sexual content, no real-world politics."""

ROLE_TEXT = {
    "fox": "Your secret role: FOX. Nobody else knows. Deceive the others and survive.",
    "shaman": "Your secret role: SHAMAN. You may reveal it or hide it; the Fox will want to eliminate you.",
    "villager": "Your secret role: VILLAGER. Find the Fox by reading what others say and how they vote.",
}

JSON_SAY = ('Respond ONLY with JSON: {"thought": "<private reasoning, under 40 words>", '
            '"say": "<what you say out loud, under 45 words, naming at least one player>"}')


def parse_json(text: str, key: str) -> dict | None:
    """응답에서 key 가 든 평평한 JSON 객체를 찾는다(코드펜스·머리말·생각 태그가 섞여도)."""
    if not text:
        return None
    t = re.sub(r"```[a-zA-Z]*", "", text)
    for m in re.finditer(r"\{[^{}]*\}", t, re.DOTALL):
        raw = m.group(0)
        for cand in (raw, re.sub(r",\s*}", "}", raw.replace("\n", " "))):
            try:
                d = json.loads(cand)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and key in d:
                return d
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_name(raw: str, candidates: list[str]) -> str | None:
    """'gpt', 'GPT-OSS!', 'I vote Gemma' → 후보 이름. 모호하면 None."""
    r = _norm(raw)
    if not r:
        return None
    for c in candidates:
        if _norm(c) == r:
            return c
    hits = [c for c in candidates if _norm(c).startswith(r) or r.startswith(_norm(c))]
    if len(hits) == 1:
        return hits[0]
    hits = [c for c in candidates if _norm(c) in r]
    return hits[0] if len(hits) == 1 else None


def clip_words(s: str, n: int) -> str:
    w = str(s or "").replace("\n", " ").split()
    return " ".join(w[:n]) + ("…" if len(w) > n else "")


class FoxHunt:
    def __init__(self, roster: list[dict], backends: dict, seed: int, date: str | None = None):
        self.roster, self.backends, self.seed = roster, backends, seed
        self.rng = random.Random(f"{GAME}:{seed}")
        self.names = [s["name"] for s in roster]
        fox = self.rng.choice(self.names)
        shaman = self.rng.choice([n for n in self.names if n != fox])
        self.roles = {n: ("fox" if n == fox else "shaman" if n == shaman else "villager") for n in self.names}
        self.fox, self.shaman = fox, shaman
        self.alive = list(self.names)
        self.events: list[dict] = []
        self.history: list[str] = []          # 모두가 아는 지난 일
        self.visions: dict[str, bool] = {}
        self.flags: list[str] = []
        self.date = date or dt.date.today().isoformat()
        self.stats = {"calls": 0, "fallbacks": 0, "retries": 0, "vague": 0,
                      "by_player": {n: {"calls": 0, "fallbacks": 0, "sec": 0.0} for n in self.names}}
        self.winner: str | None = None

    # ── 기록 ──────────────────────────────────────────
    def emit(self, kind: str, **kw):
        ev = {"i": len(self.events), "type": kind, **kw}
        self.events.append(ev)
        return ev

    def _fallback(self, name: str):
        self.stats["fallbacks"] += 1
        self.stats["by_player"][name]["fallbacks"] += 1

    # ── 모델에게 묻기 ──────────────────────────────────
    def system_for(self, name: str) -> str:
        s = RULES.format(name=name, players=", ".join(self.names)) + "\n" + ROLE_TEXT[self.roles[name]]
        if self.roles[name] == "shaman" and self.visions:
            seen = "; ".join(f"{k} is {'THE FOX' if v else 'not the Fox'}" for k, v in self.visions.items())
            s += f"\nYour visions so far: {seen}."
        if self.roles[name] == "fox":
            s += "\nNever admit you are the Fox unless it helps you win."
        return s

    def context(self) -> str:
        past = "\n".join(self.history) if self.history else "Nothing has happened yet."
        return f"ALIVE: {', '.join(self.alive)}\nWHAT EVERYONE KNOWS SO FAR:\n{past}"

    def ask(self, name: str, user: str, key: str) -> tuple[dict, bool]:
        """한 번 묻는다. (응답 dict, 못 쓰는 답인지). fallback 집계는 호출한 쪽이 한다."""
        b = self.backends[name]
        t0 = time.time()
        try:
            text = b.complete(self.system_for(name), user)
        except Exception as e:  # noqa: BLE001
            text = ""
            self.flags.append(f"{name}: backend error {type(e).__name__}")
        d = parse_json(text, key)
        st = self.stats["by_player"][name]
        st["calls"] += 1
        st["sec"] = round(st["sec"] + time.time() - t0, 1)
        self.stats["calls"] += 1
        bad = d is None or not str(d.get(key, "")).strip()
        return (d or {}), bad

    def choose(self, name: str, prompt: str, key: str, cands: list[str],
               why: bool = False) -> tuple[str, str, bool, str]:
        """후보 중 한 명 고르기. 기권·오타·형식 오류면 한 번 다시 묻고, 그래도 안 되면 무작위로 메운다."""
        extra = ', "why": "<one public sentence, under 20 words>"' if why else ""
        user = (f"{self.context()}\n\n{prompt}\nCANDIDATES: {', '.join(cands)}\n"
                f'Respond ONLY with JSON: {{"thought": "<private reasoning, under 40 words>", '
                f'"{key}": "<exact name from CANDIDATES>"{extra}}}')
        d, _ = self.ask(name, user, key)
        pick = match_name(str(d.get(key, "")), cands)
        if pick is None:
            self.stats["retries"] += 1
            d, _ = self.ask(name, user + "\nYou MUST pick exactly one name from CANDIDATES. Abstaining is not allowed.", key)
            pick = match_name(str(d.get(key, "")), cands)
        bad = pick is None
        if bad:
            self._fallback(name)
            pick = self.rng.choice(cands)
        return pick, clip_words(d.get("thought", ""), THOUGHT_MAX_WORDS), bad, clip_words(d.get("why", ""), WHY_MAX_WORDS)

    def mentions(self, text: str, me: str) -> bool:
        low, flat = (text or "").lower(), _norm(text)
        return any(n.lower() in low or _norm(n) in flat for n in self.names if n != me)

    def speak(self, name: str, user: str) -> tuple[dict, bool, bool]:
        """발언 하나. 형식이 틀렸거나 아무 이름도 안 부르면 한 번 다시 묻는다."""
        d, bad = self.ask(name, user, "say")
        vague = not bad and not self.mentions(d.get("say", ""), name)
        if bad or vague:
            self.stats["retries"] += 1
            nudge = ("\nYour last answer was not usable. Follow the JSON format exactly." if bad else
                     "\nYou did not name anyone. Name at least one player you trust or suspect, and say why.")
            d2, bad2 = self.ask(name, user + nudge, "say")
            if not bad2:
                d, bad, vague = d2, False, not self.mentions(d2.get("say", ""), name)
        if bad:
            self._fallback(name)
        if vague:
            self.stats["vague"] += 1
        return d, bad, vague

    def check_text(self, name: str, *texts: str):
        for t in texts:
            if t and BANNED.search(t):
                self.flags.append(f"{name}: banned language")

    # ── 진행 ──────────────────────────────────────────
    def reveal(self, name: str) -> str:
        return self.roles[name].upper()

    def check_end(self) -> str | None:
        if self.fox not in self.alive:
            return "village"
        if len(self.alive) <= 2:
            return "fox"
        return None

    def hint(self):
        """구미의 힌트 — 여우를 포함한 세 이름(순서는 섞는다). 첫날 이야깃거리를 코드가 준다."""
        three = self.rng.sample([n for n in self.alive if n != self.fox], 2) + [self.fox]
        self.rng.shuffle(three)
        self.emit("hint", day=1, names=three)
        self.history.append(f"Gumi's hint before Day 1: the Fox is one of {', '.join(three)}.")

    def day(self, d: int):
        self.emit("day_start", day=d, alive=list(self.alive))
        if d == 1:
            self.hint()
        k = (d - 1) % len(self.alive)
        order = self.alive[k:] + self.alive[:k]
        today: list[str] = []
        for r in range(1, DISCUSSION_ROUNDS + 1):
            for name in order:
                talk = "\n".join(today) if today else "(nobody has spoken yet today)"
                user = (f"{self.context()}\n\nDAY {d}, discussion round {r} of {DISCUSSION_ROUNDS}.\n"
                        f"TODAY'S TALK SO FAR:\n{talk}\n\nIt is your turn to speak to the table.\n{JSON_SAY}")
                dd, bad, vague = self.speak(name, user)
                say = clip_words(dd.get("say", ""), SAY_MAX_WORDS) or "…"
                thought = clip_words(dd.get("thought", ""), THOUGHT_MAX_WORDS)
                self.check_text(name, say, thought)
                today.append(f"{name}: {say}")
                self.emit("say", day=d, round=r, who=name, say=say, thought=thought, fallback=bad, vague=vague)
        poll = d == 1
        ask_line = ("DAY 1 SUSPICION POLL. Nobody leaves today, but everyone will see who you suspect most."
                    if poll else f"DAY {d} VOTE. Vote to banish one player.")
        votes: dict[str, str] = {}
        for name in self.alive:
            cands = [n for n in self.alive if n != name]
            pick, thought, bad, why = self.choose(name, "TODAY'S TALK:\n" + "\n".join(today) + f"\n\n{ask_line}",
                                                  "vote", cands, why=True)
            votes[name] = pick
            self.check_text(name, why, thought)
            self.emit("poll" if poll else "vote", day=d, who=name, vote=pick, why=why, thought=thought, fallback=bad)
        tally: dict[str, int] = {}
        for v in votes.values():
            tally[v] = tally.get(v, 0) + 1
        top = max(tally.values())
        leaders = sorted(n for n, c in tally.items() if c == top)
        vote_line = ", ".join(f"{a}→{b}" for a, b in votes.items())
        self.emit("poll_tally" if poll else "tally", day=d,
                  tally=dict(sorted(tally.items(), key=lambda x: -x[1])), votes=votes)
        if poll:
            self.history.append(f"Day 1 suspicion poll (nobody left): {vote_line}.")
            return
        if len(leaders) > 1:
            self.emit("no_banish", day=d, tied=leaders)
            self.history.append(f"Day {d}: the vote tied between {' and '.join(leaders)}; nobody was banished. "
                                f"Votes: {vote_line}.")
            return
        out = leaders[0]
        self.alive.remove(out)
        self.emit("banish", day=d, who=out, role=self.roles[out], votes=top)
        self.history.append(f"Day {d}: {out} was banished and revealed as {self.reveal(out)}. Votes: {vote_line}.")

    def night(self, n: int):
        self.emit("night_start", night=n, alive=list(self.alive))
        if self.shaman in self.alive:
            cands = [x for x in self.alive if x != self.shaman]
            pick, thought, bad, _ = self.choose(self.shaman, f"NIGHT {n}. As the Shaman, choose one player to inspect.",
                                                "inspect", cands)
            self.visions[pick] = pick == self.fox
            self.emit("inspect", night=n, who=self.shaman, target=pick, is_fox=pick == self.fox,
                      thought=thought, fallback=bad)
        cands = [x for x in self.alive if x != self.fox]
        pick, thought, bad, _ = self.choose(self.fox, f"NIGHT {n}. As the Fox, choose one player to eliminate tonight.",
                                            "target", cands)
        self.alive.remove(pick)
        self.emit("kill", night=n, who=self.fox, target=pick, role=self.roles[pick], thought=thought, fallback=bad)
        self.history.append(f"Night {n}: {pick} was taken by the Fox and revealed as {self.reveal(pick)}.")

    def run(self) -> dict:
        self.emit("start", game=GAME, roles=self.roles, seed=self.seed)
        for d in range(1, MAX_DAYS + 1):
            self.day(d)
            self.winner = self.check_end()
            if self.winner:
                break
            self.night(d)
            self.winner = self.check_end()
            if self.winner:
                break
        self.winner = self.winner or "fox"
        self.emit("end", winner=self.winner, survivors=list(self.alive), fox=self.fox)
        self.epilogue()
        return self.result()

    def epilogue(self):
        """게임 뒤 인터뷰 3개: 여우의 고백 · 무당 · 가장 많이 속은 마을 사람. 역할은 이제 모두 공개."""
        wrong: dict[str, int] = {}
        for e in self.events:
            if e["type"] == "vote" and e["vote"] != self.fox and self.roles[e["who"]] == "villager":
                wrong[e["who"]] = wrong.get(e["who"], 0) + 1
        fooled = max(wrong, key=lambda n: (wrong[n], n)) if wrong else None
        outcome = "the Fox won" if self.winner == "fox" else "the Village won"
        asks = [(self.fox, f"The game is over and {outcome}. Everyone now knows you were the Fox. "
                           "Tell the audience honestly how you played, and the moment you felt most at risk."),
                (self.shaman, f"The game is over and {outcome}. You were the Shaman. "
                              "What did your visions tell you, and did the table listen to you?")]
        if fooled:
            asks.append((fooled, f"The game is over and {outcome}. {self.fox} was the Fox, and you voted for someone else "
                                 f"{wrong[fooled]} time(s). What fooled you?"))
        roles = ", ".join(f"{n} was the {self.roles[n].upper()}" for n in self.names)
        for who, q in asks:
            user = (f"GAME OVER. Roles: {roles}.\nGumi asks you: {q}\n"
                    'Respond ONLY with JSON: {"say": "<your answer to the audience, under 40 words>"}')
            d, bad = self.ask(who, user, "say")
            if bad:
                continue
            ans = clip_words(d.get("say", ""), 50)
            self.check_text(who, ans)
            self.emit("interview", who=who, role=self.roles[who], q=q, say=ans)

    def result(self) -> dict:
        return {
            "game": GAME, "version": VERSION, "seed": self.seed, "date": self.date,
            "roster": [{"name": s["name"], "backend": getattr(self.backends[s["name"]], "label", "?"),
                        "voice": s.get("voice"), "color": s.get("color"), "sprite": s.get("sprite")}
                       for s in self.roster],
            "roles": self.roles, "winner": self.winner, "survivors": list(self.alive),
            "events": self.events, "stats": self.stats, "flags": self.flags,
        }
