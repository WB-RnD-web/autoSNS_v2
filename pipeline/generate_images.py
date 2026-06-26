#!/usr/bin/env python3
"""스토리보드 → 이미지 준비.

기본(IMAGE_BACKEND=static): characters/refs/ 의 '고정 캐릭터 이미지'를 그대로 사용(무료·항상 동작).
  - 별이·별하 투샷을 characters/refs/twoshot.* 로 두면 앵커 컷에 사용.
  - 토픽 스틸 전용 이미지(still.*)가 없으면 투샷을 재사용.
선택(IMAGE_BACKEND=gemini): 유료 결제(빌링) 후 Google Gemini 2.5 Flash Image로 생성.

⚠️ '오늘(KST) 스토리보드'만 사용한다. 최신 파일로 폴백하지 않는다.

입력:  output/news/<오늘>_storyboard.json (assets_needed)
출력:  output/assets/<오늘>_<assetId>.<ext>

사용:
  python pipeline/generate_images.py                 # 기본=static(고정 이미지)
  python pipeline/generate_images.py --backend gemini # 결제 후 생성 모드
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import shutil
import sys

import config

REF_DIR = config.ROOT / "characters" / "refs"
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def todays_storyboard() -> str | None:
    """오늘 날짜 스토리보드만(없으면 None)."""
    today = dt.datetime.now().strftime("%Y-%m-%d")
    p = config.NEWS_DIR / f"{today}_storyboard.json"
    return str(p) if p.exists() else None


def ref_files() -> list:
    """characters/refs/ 의 이미지 파일 목록."""
    if not REF_DIR.exists():
        return []
    return [p for p in sorted(REF_DIR.iterdir()) if p.suffix.lower() in IMG_EXTS]


def pick_static(asset: dict, files: list):
    """asset에 맞는 고정 이미지 1개 선택(없으면 None)."""
    if not files:
        return None
    aid = asset["id"].lower()
    for p in files:
        s = p.stem.lower()
        if s == aid or aid in s or s in aid:
            return p
    for key in ("twoshot", "two", "anchor", "caster", "byeo", "별"):
        for p in files:
            if key in p.stem.lower():
                return p
    return files[0]


def run_static(sb: dict, date: str, files: list, topic: str = "") -> tuple[list, list]:
    tp = f"{topic}_" if topic else ""
    made, skipped = [], []
    for a in sb.get("assets_needed", []):
        src = pick_static(a, files)
        if src is None:
            skipped.append(f"{a['id']}(이미지 없음)")
            continue
        target = config.ASSETS_DIR / f"{date}_{tp}{a['id']}{src.suffix.lower()}"
        shutil.copyfile(src, target)
        made.append(target.name)
        print(f"  ✅ {target.name} ← characters/refs/{src.name}")
    return made, skipped


# ── (선택) Gemini 유료 백엔드 ─────────────────────────────
def _gemini_client(key: str):
    from google import genai  # type: ignore
    return genai.Client(api_key=key)


def _gemini_one(client, model: str, prompt: str, refs: list):
    from google.genai import types  # type: ignore
    contents: list = [prompt]
    for data, mime in refs:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime))
    resp = client.models.generate_content(model=model, contents=contents)
    for cand in (resp.candidates or []):
        for part in (cand.content.parts if getattr(cand, "content", None) else []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    return None


def run_gemini(sb: dict, date: str, topic: str = "") -> tuple[list, list]:
    tp = f"{topic}_" if topic else ""
    key = config.env("GEMINI_API_KEY") or config.env("GOOGLE_API_KEY")
    if not key:
        print("[error] IMAGE_BACKEND=gemini 인데 GEMINI_API_KEY 없음", file=sys.stderr)
        return [], ["키 없음"]
    model = config.env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    refs = [(p.read_bytes(),
             "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else f"image/{p.suffix.lower().lstrip('.')}")
            for p in ref_files()]
    client = _gemini_client(key)
    made, skipped = [], []
    for a in sb.get("assets_needed", []):
        target = config.ASSETS_DIR / f"{date}_{tp}{a['id']}.png"
        use_refs = refs if "twoshot" in a["id"] else []
        try:
            data = _gemini_one(client, model, a["prompt"], use_refs)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {a['id']} 생성 실패: {e}", file=sys.stderr)
            skipped.append(f"{a['id']}(실패)")
            continue
        if not data:
            skipped.append(f"{a['id']}(응답없음)")
            continue
        target.write_bytes(data)
        made.append(target.name)
        print(f"  ✅ {target.name}")
    return made, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="스토리보드 → 이미지 준비(고정/생성)")
    ap.add_argument("--storyboard", help="storyboard.json(기본: 오늘 것)")
    ap.add_argument("--backend", help="static(기본) | gemini")
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
    backend = (args.backend or config.env("IMAGE_BACKEND", "static")).lower()

    if backend == "gemini":
        print("# 이미지 백엔드: gemini(유료 결제 필요)")
        made, skipped = run_gemini(sb, date, topic)
    else:
        files = ref_files()
        print(f"# 이미지 백엔드: static(무료·고정 이미지) — characters/refs 이미지 {len(files)}장")
        if not files:
            print("[error] characters/refs/ 에 캐릭터 이미지가 없습니다.\n"
                  "        별이·별하 투샷을 characters/refs/twoshot.png 로 올려주세요.", file=sys.stderr)
            return 1
        made, skipped = run_static(sb, date, files, topic)

    print(f"\n준비 {len(made)}개: {', '.join(made) or '없음'}")
    if skipped:
        print(f"건너뜀: {', '.join(skipped)}")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
