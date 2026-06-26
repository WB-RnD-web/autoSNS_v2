#!/usr/bin/env python3
"""업로드 dedupe ledger — 이미 처리/업로드한 스토리보드 재처리 방지.

⚠️ main 브랜치에 쓰지 않는다(자기 재트리거 루프 방지).
   ledger 파일은 .gitignore 처리되며, Actions 에선 actions/cache 로 런 간 영속한다.
   (강한 보장이 필요하면 별도 ledger 브랜치로 확장 — 현재는 cache + git diff 조합으로 충분.)

키: "<date>_<topic>"  (스토리보드 파일명 규칙과 일치)
값: {"uploaded_at": <epoch>, "video_id": <str|null>, "privacy": <str>}
"""
from __future__ import annotations
import json
import os

import config

DEFAULT_PATH = str(config.OUTPUT / "ledger.json")


def key_for(sb: dict) -> str:
    return f"{sb.get('date','')}_{sb.get('topic','')}"


def load(path: str = DEFAULT_PATH) -> dict:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def is_done(led: dict, sb: dict) -> bool:
    return key_for(sb) in led


def mark(led: dict, sb: dict, video_id: str | None, privacy: str,
         now: float, path: str = DEFAULT_PATH) -> None:
    led[key_for(sb)] = {"uploaded_at": now, "video_id": video_id, "privacy": privacy}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=2)
