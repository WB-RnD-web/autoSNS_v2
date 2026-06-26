#!/usr/bin/env python3
"""스토리보드 → 무료 음성(TTS). 별이=남성, 별하=여성 (edge-tts, 키 불필요·고품질 한국어).

각 샷의 대사를 음성으로 합성한다. 한 샷 실패해도 나머지는 진행(해당 샷은 무음).
edge-tts 는 마이크로소프트 Edge 읽어주기 서비스를 쓰며 API 키가 필요 없다.

⚠️ '오늘(KST) 스토리보드'만 사용한다. 최신 파일로 폴백하지 않는다.

입력:  output/news/<오늘>_storyboard.json (shots[].line / speaker)
출력:  output/assets/<오늘>_voice_<n>.mp3

사용:
  python pipeline/voice.py            # 오늘 스토리보드 사용
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import os
import sys

import config

# 캐릭터별 무료 보이스 + 말투(edge-tts, 키 불필요). 전부 환경변수로 교체 가능.
# 자연스러움 튜닝: 인위적 rate/pitch 가중을 줄이고 신형 보이스 우선.
# 속도를 빠르게 하거나 피치를 올리면 더 기계적으로 들린다 → 0 근처로.
# 전부 환경변수로 덮어쓸 수 있으니, 들어보고 .env 에서 미세조정 가능.
VOICES = {
    "별이": {
        "voice": config.env("TTS_VOICE_BYEORI", "ko-KR-HyunsuMultilingualNeural"),  # 신형(자연스러움)
        "rate": config.env("TTS_RATE_BYEORI", "-2%"),    # 살짝 느리게 = 차분
        "pitch": config.env("TTS_PITCH_BYEORI", "+0Hz"),
        "fallback": "ko-KR-InJoonNeural",
    },
    "별하": {
        # 여성 보이스 유지(남성 별이와 구분돼야 함). 가속/피치 보정만 제거.
        "voice": config.env("TTS_VOICE_BYEOLHA", "ko-KR-SunHiNeural"),
        "rate": config.env("TTS_RATE_BYEOLHA", "+0%"),   # 가속 제거(기존 +10%가 딱딱함의 원인)
        "pitch": config.env("TTS_PITCH_BYEOLHA", "+0Hz"),  # 피치 보정 제거(기존 +6Hz)
        "fallback": "ko-KR-SunHiNeural",
    },
}


def settings_for(speaker: str) -> dict:
    for name, cfg in VOICES.items():
        if name in speaker:
            return cfg
    return VOICES["별하"]


def todays_storyboard() -> str | None:
    """오늘 날짜 스토리보드만(없으면 None)."""
    today = dt.datetime.now().strftime("%Y-%m-%d")
    p = config.NEWS_DIR / f"{today}_storyboard.json"
    return str(p) if p.exists() else None


async def _synth(text: str, voice: str, rate: str, pitch: str, out: str) -> None:
    import edge_tts  # type: ignore
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)


def synth(text: str, cfg: dict, out: str) -> str:
    """기본 보이스로 합성, 실패하면 안전 보이스로 1회 재시도. 성공한 보이스명 반환."""
    voices = [cfg["voice"]] + ([cfg["fallback"]] if cfg["fallback"] != cfg["voice"] else [])
    last: Exception | None = None
    for v in voices:
        try:
            asyncio.run(_synth(text, v, cfg["rate"], cfg["pitch"], out))
            if os.path.exists(out) and os.path.getsize(out) > 0:
                return v
            last = RuntimeError("빈 음성 파일")
        except Exception as e:  # noqa: BLE001
            last = e
        if os.path.exists(out) and os.path.getsize(out) == 0:
            os.remove(out)
    raise last or RuntimeError("음성 합성 실패")


def main() -> int:
    ap = argparse.ArgumentParser(description="스토리보드 → 무료 TTS 음성(별이=남/별하=여)")
    ap.add_argument("--storyboard", help="storyboard.json(기본: 오늘 것)")
    args = ap.parse_args()
    config.load_dotenv()
    config.ensure_dirs()

    path = args.storyboard or todays_storyboard()
    if not path or not os.path.exists(path):
        print("[error] 오늘 storyboard.json 없음 — 루틴이 커밋했는지 확인", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as f:
        sb = json.load(f)
    date = sb["date"]
    topic = sb.get("topic", "")
    tp = f"{topic}_" if topic else ""

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("[error] edge-tts 미설치 — 'pip install edge-tts' (없으면 영상은 무음 진행)", file=sys.stderr)
        return 1

    made, failed = [], []
    for s in sb.get("shots", []):
        text = (s.get("line") or "").strip()
        if not text:
            continue
        out = config.ASSETS_DIR / f"{date}_{tp}voice_{s['n']}.mp3"
        cfg = settings_for(s.get("speaker", ""))
        try:
            used = synth(text, cfg, str(out))
            made.append(out.name)
            print(f"  ✅ {out.name}  [{used}]  {text[:24]}…")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 샷{s['n']} 음성 실패: {e}", file=sys.stderr)
            failed.append(str(s["n"]))

    print(f"\n음성 {len(made)}개 생성" + (f" / 실패 샷 {failed}" if failed else ""))
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
