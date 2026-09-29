#!/usr/bin/env python3
"""Gumiho Games 출연 모델 연결 — Spark(Gemma) · Anthropic(Claude) · OpenAI 호환(공개 모델 API) · mock.

★Spark 는 회사 사람들이 같이 쓰는 공용 서버다(2026-09-29 작업이 몰려 한 번 멈췄다).
  그래서 SparkLLM 은 ① 한 번에 한 건만 보내고 ② /queue 의 대기 수가 많으면 보내기 전에 기다리고
  ③ 5xx·타임아웃이면 점점 길게 쉬었다가 다시 보낸다. 게임은 녹화용이라 느려도 된다.

★2026-09-29 실측: 게이트웨이 llm 작업은 model 값을 무시하고 늘 Gemma 4 가 답한다.
  그래서 다른 공개 모델은 OpenAI 호환 엔드포인트(GUMIHO_OPENAI_BASE)로 붙인다.

roster 한 칸 = {"name", "backend": spark|anthropic|openai|mock, "model", "voice", "color", "sprite"}
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

SPARK_BASE = (os.environ.get("WBSPARK_BASE") or "https://wangbyul.com/wbSpark").rstrip("/")


def _log(msg: str):
    sys.stderr.write(msg.rstrip() + "\n")


class Backend:
    label = "?"

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:  # pragma: no cover
        raise NotImplementedError


class SparkLLM(Backend):
    """Spark 게이트웨이 llm 작업(Gemma 4). 공용 서버 배려: 한 건씩 · 대기열 확인 · 점진 재시도."""

    def __init__(self, base: str = SPARK_BASE, timeout: int = 900,
                 max_waiting: int | None = None, poll: float = 2.5):
        self.base, self.timeout, self.poll = base, timeout, poll
        self.max_waiting = int(os.environ.get("GUMIHO_SPARK_MAX_WAITING", "6")) if max_waiting is None else max_waiting
        self.label = "spark:gemma-4"
        token = os.environ.get("WBSPARK_TOKEN")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def _get(self, path: str, timeout: int = 60):
        import requests
        return requests.get(f"{self.base}{path}", headers=self.headers, timeout=timeout)

    def _wait_turn(self, deadline: float):
        """남이 줄을 많이 세워 놨으면 끼어들지 않고 기다린다."""
        while time.monotonic() < deadline:
            try:
                q = self._get("/queue", 30).json()
                if int(q.get("waiting", 0)) <= self.max_waiting:
                    return
                _log(f"[spark] 대기열 {q.get('waiting')}건 — 20초 뒤 다시 확인")
            except Exception as e:  # noqa: BLE001
                _log(f"[spark] /queue 확인 실패({type(e).__name__}) — 20초 뒤 다시")
            time.sleep(20)

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        import requests
        deadline = time.monotonic() + self.timeout
        body = {"type": "llm", "prompt": f"{system}\n\n{user}"}
        wait = 10
        while time.monotonic() < deadline:
            self._wait_turn(deadline)
            try:
                r = requests.post(f"{self.base}/jobs", json=body, headers=self.headers, timeout=60)
                jid = r.json().get("job_id") if r.status_code == 200 else None
            except Exception as e:  # noqa: BLE001
                jid, r = None, None
                _log(f"[spark] 제출 예외 {type(e).__name__}")
            if not jid:
                _log(f"[spark] 제출 실패 {getattr(r, 'status_code', '?')} — {wait}초 쉼")
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            while time.monotonic() < deadline:
                time.sleep(self.poll)
                try:
                    d = self._get(f"/jobs/{jid}", 60).json()
                except Exception:  # noqa: BLE001
                    continue
                st = d.get("status")
                if st == "done":
                    return str(d.get("text") or "")
                if st in ("error", "failed"):
                    _log(f"[spark] 작업 실패: {str(d.get('error'))[:160]}")
                    break
            time.sleep(wait)
            wait = min(wait * 2, 120)
        raise TimeoutError("Spark LLM 시간 초과")


class Claude(Backend):
    def __init__(self, model: str = "claude-sonnet-5-5"):
        import anthropic  # noqa
        self.client = anthropic.Anthropic()
        self.model = model
        self.label = f"anthropic:{model}"

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        # Sonnet 5.5 는 기본으로 생각을 켜고 생각 토큰도 max_tokens 에 든다 → 넉넉히 준다.
        for attempt in range(4):
            try:
                msg = self.client.messages.create(
                    model=self.model, max_tokens=max(4000, max_tokens), system=system,
                    messages=[{"role": "user", "content": user}])
                return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            except Exception as e:  # noqa: BLE001
                _log(f"[claude] {type(e).__name__}: {str(e)[:120]} — 재시도 {attempt + 1}")
                time.sleep(5 * (attempt + 1))
        raise RuntimeError("Claude 호출 실패")


NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"


class OpenAICompat(Backend):
    """OpenAI 호환 chat/completions. 기본은 NVIDIA API 카탈로그 — 왕별이가 이미 쓰는 NVIDIA_API_KEY(무료)로 부른다.
    다른 곳(OpenRouter 등)을 쓰려면 GUMIHO_OPENAI_BASE / GUMIHO_OPENAI_KEY 로 바꾼다."""

    def __init__(self, model: str, base: str | None = None, key: str | None = None):
        self.model = model
        self.base = (base or os.environ.get("GUMIHO_OPENAI_BASE") or NVIDIA_BASE).rstrip("/")
        self.key = key or os.environ.get("GUMIHO_OPENAI_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
        if not self.key:
            raise SystemExit("[error] 공개 모델 API 키 없음 — NVIDIA_API_KEY(또는 GUMIHO_OPENAI_KEY)")
        self.label = f"openai:{model}"

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        import requests
        # 생각(reasoning)을 먼저 쓰는 모델이 많아 답이 잘리지 않게 넉넉히 준다.
        body = {"model": self.model, "max_tokens": max(2500, max_tokens), "temperature": 0.8,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        wait = 5
        for attempt in range(6):
            try:
                r = requests.post(f"{self.base}/chat/completions", json=body, headers=headers, timeout=180)
                if r.status_code == 200:
                    msg = r.json()["choices"][0]["message"]
                    return msg.get("content") or msg.get("reasoning_content") or ""
                _log(f"[openai] {self.model} {r.status_code}: {r.text[:120]}")
                if r.status_code < 500 and r.status_code != 429:
                    break
            except Exception as e:  # noqa: BLE001
                _log(f"[openai] {self.model} {type(e).__name__}")
            time.sleep(wait)
            wait = min(wait * 2, 90)
        raise RuntimeError(f"{self.model} 호출 실패")


class Mock(Backend):
    """오프라인 테스트용 — 규칙을 지키는 무작위 답. seed 로 재현된다."""

    def __init__(self, name: str, seed: int = 0, broken: bool = False):
        self.name, self.rng, self.broken = name, random.Random(f"{name}:{seed}"), broken
        self.label = "mock"

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        if self.broken:
            return "I refuse to answer in JSON."
        cands = []
        if "CANDIDATES:" in user:
            cands = [c.strip() for c in user.split("CANDIDATES:")[1].split("\n")[0].split(",") if c.strip()]
        elif "ALIVE:" in user:
            cands = [c.strip() for c in user.split("ALIVE:")[1].split("\n")[0].split(",")
                     if c.strip() and c.strip() != self.name]
        pick = self.rng.choice(cands) if cands else ""
        return json.dumps({"thought": f"{self.name} thinks about {pick or 'the table'}.",
                           "say": f"I am {self.name} and I have my eye on {pick or 'someone'}.",
                           "vote": pick, "target": pick, "inspect": pick})


def paid_allowed() -> bool:
    """★사용자 원칙(2026-09-29): 돈이 드는 호출은 없어야 한다. 무료 경로(Spark · NVIDIA 무료 키)만 기본 허용.
    유료 백엔드(Claude API · OpenRouter 등)는 GUMIHO_ALLOW_PAID=1 을 사람이 직접 켤 때만."""
    return os.environ.get("GUMIHO_ALLOW_PAID") == "1"


def make_backend(seat: dict, override: str | None = None, seed: int = 0) -> Backend:
    kind = override or seat.get("backend")
    if kind == "spark":
        return SparkLLM()
    if kind == "anthropic":
        if not paid_allowed():
            raise SystemExit(f"[error] {seat['name']}: Claude API 는 유료라 막혀 있다(GUMIHO_ALLOW_PAID)")
        return Claude(seat.get("model") or "claude-sonnet-5-5")
    if kind == "openai":
        if not seat.get("model") or seat["model"] == "TBD":
            raise SystemExit(f"[error] {seat['name']}: 공개 모델 ID 가 정해지지 않았다(roster)")
        base = (os.environ.get("GUMIHO_OPENAI_BASE") or NVIDIA_BASE).rstrip("/")
        if base != NVIDIA_BASE and not paid_allowed():
            raise SystemExit(f"[error] {seat['name']}: 무료 NVIDIA 주소가 아니다({base}) — 유료일 수 있어 막는다")
        return OpenAICompat(seat["model"], base=base)
    if kind == "mock":
        return Mock(seat["name"], seed)
    raise SystemExit(f"[error] 알 수 없는 backend: {kind}")


def load_roster(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        roster = json.load(f)
    names = [s["name"] for s in roster]
    if len(set(n.lower() for n in names)) != len(names):
        raise SystemExit("[error] roster 이름 중복")
    return roster
