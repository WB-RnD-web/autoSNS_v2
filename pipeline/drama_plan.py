#!/usr/bin/env python3
"""시니어 사연 오디오드라마(90~110분) — 회차 배정 · 대본 조립 · 검사 (2026-09-29 파일럿).

왜: 국내 AI 자동화 채널 중 가장 확실히 되는 유형이 55세 이상 대상 사연 오디오드라마였다
  (사연그리다 구독 10.3만·영상 15개·최고 213만, 코리아인생사연 8.57만 · 2026-09-29 실측).
  이 채널 시청자 88%가 55세 이상이고, 롱폼이라 수익화 시간에 그대로 쌓인다.
  우리 사연라디오(7~8월, 6~20분·문학형 제목)는 편당 0~15회였다 → 길이·제목·구성이 다르다.

루틴(Sonnet 5.5)은 ★글만 쓴다. 어떤 이야기 유형·화자 성별로 쓸지는 코드가 날짜로 정하고(assign),
분량·구성·화자 표기는 코드가 검사한다(check). 검사를 통과하지 못하면 업로드하지 않는다.

폴더 한 편 = output/drama/<DATE>_<slug>/
  meta.json            제목·설명·썸네일 문구·등장인물·그림 프롬프트 (루틴이 씀)
  ch01.txt ~ chNN.txt  장별 대본 (루틴이 씀)
  spec.json            build 가 만든다 — 파이프라인 입력

대본 형식 (한 줄 = 한 사람의 한 발화):
  # 1장. 대문 앞에서
  [화자] 그날 아침, 저는 아들 내외가 사는 집 대문 앞에 서 있었습니다.
  [며느리] 어머님, 여기서 뭐 하세요?

    python drama_plan.py assign --date 2026-10-02
    python drama_plan.py count  output/drama/2026-10-02_mother-house
    python drama_plan.py build  output/drama/2026-10-02_mother-house
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import sys

START = dt.date(2026, 10, 2)          # 첫 회(금) — 주 1편
NARRATOR = "화자"

# 이야기 유형 — 줄거리는 루틴이 짓는다. 같은 유형이 연달아 나오지 않게 날짜로 돌린다.
# narrator: 화자 성별(F/M). hook: 첫 30초에 던질 가장 극적인 장면의 씨앗.
ARCHETYPES = [
    {"key": "mother-house", "narrator": "F",
     "hook": "평생 일군 집을 아들 내외에게 넘겨준 뒤 그 집에서 밀려난 어머니"},
    {"key": "father-will", "narrator": "M",
     "hook": "아버지 장례식 날 공개된 유언장, 막내에게만 남긴 낡은 열쇠 하나"},
    {"key": "first-love", "narrator": "F",
     "hook": "사십 년 만에 요양병원 같은 병실에서 다시 만난 첫사랑"},
    {"key": "secret-daughter", "narrator": "F",
     "hook": "환갑 잔칫날 알게 된 사실 — 키운 딸이 내 배로 낳은 딸이 아니었다"},
    {"key": "eldest-son", "narrator": "M",
     "hook": "사업 자금을 대준 큰아들이 연락을 끊고, 삼 년 뒤 문을 두드린 건 손녀였다"},
    {"key": "daughter-in-law", "narrator": "F",
     "hook": "십 년을 구박한 며느리가 쓰러진 나를 끝까지 지킨 진짜 이유"},
    {"key": "late-divorce", "narrator": "F",
     "hook": "황혼 이혼 서류를 내민 날, 남편이 장롱 밑에서 꺼낸 오래된 통장"},
    {"key": "scam-letter", "narrator": "F",
     "hook": "노후 자금을 사기당한 남편이 끝까지 숨긴 편지 한 통"},
    {"key": "lunchbox-friend", "narrator": "M",
     "hook": "가난하던 시절 도시락을 나눠 준 친구를 삼십 년 만에 찾아간 날"},
    {"key": "waiting-mother", "narrator": "F",
     "hook": "치매 어머니가 매일 밤 대문 앞에서 기다리던 사람의 정체"},
    {"key": "guarantor-sister", "narrator": "F",
     "hook": "동생 보증을 섰다가 모든 것을 잃은 언니에게 이십 년 뒤 날아온 등기"},
    {"key": "adopted-son", "narrator": "F",
     "hook": "형편이 안 돼 입양 보낸 아들이 사십 년 뒤 회사 대표가 되어 찾아오다"},
    {"key": "hometown-return", "narrator": "M",
     "hook": "도시에서 밀려나 고향 빈집으로 내려간 노부부에게 생긴 일"},
    {"key": "wedding-snub", "narrator": "F",
     "hook": "아들 결혼식장에서 사돈에게 무시당한 어머니, 일 년 뒤의 반전"},
    {"key": "hidden-lottery", "narrator": "F",
     "hook": "복권 당첨을 숨긴 할머니 앞에서 드러난 자식들의 진짜 얼굴"},
    {"key": "late-letter", "narrator": "F",
     "hook": "세상을 떠난 줄 알았던 약혼자의 편지가 오십 년 만에 도착하다"},
]

# Supertonic 프리셋. F3·F4 는 숫자를 잘못 읽어(2026-09-27 실측 '1위'→'2비') 쓰지 않는다.
NARRATOR_VOICE = {"F": os.environ.get("DRAMA_NARRATOR_F", "F2"),
                  "M": os.environ.get("DRAMA_NARRATOR_M", "M2")}
CAST_VOICES = {"F": ["F1", "F5", "F2"], "M": ["M1", "M3", "M4", "M5", "M2"]}

# 분량: Supertonic 은 분당 ~450자를 읽는다(2026-09-29 실측). 파이프라인이 0.92배로 늦춰 읽히므로
# 34,000~42,000자 ≈ 85~105분(발화 사이 쉼 포함).
MIN_CHARS, MAX_CHARS = 34000, 46000
MIN_CH, MAX_CH = 8, 14
MIN_CH_CHARS = 1800
MAX_CAST = 6
MIN_NARRATOR_SHARE = 0.55
TITLE_MAX = 60
IMG_PER_CH = (2, 3)

LINE_RE = re.compile(r"^\[([^\]\n]{1,12})\]\s*(.+)$")
HEAD_RE = re.compile(r"^#\s*(\d+)\s*장[.\s·:-]*(.*)$")


# ── 배정 ──────────────────────────────────────────────────────
def episode_of(d: dt.date) -> int:
    """START 부터 몇 번째 회차인지(1부터). START 이전이면 0."""
    return 0 if d < START else (d - START).days // 7 + 1


def assign(d: dt.date) -> dict:
    ep = max(1, episode_of(d))
    a = ARCHETYPES[(ep - 1) % len(ARCHETYPES)]
    return {"date": d.isoformat(), "episode": ep, "archetype": a["key"], "hook_seed": a["hook"],
            "narrator_gender": a["narrator"], "narrator_voice": NARRATOR_VOICE[a["narrator"]],
            "folder": f"output/drama/{d.isoformat()}_{a['key']}",
            "target_chars": [MIN_CHARS, MAX_CHARS - 4000], "chapters": [10, 12]}


# ── 대본 파싱 ─────────────────────────────────────────────────
def parse_chapter(text: str, index: int) -> dict:
    title, lines, bad = "", [], []
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        m = HEAD_RE.match(s)
        if m:
            title = m.group(2).strip() or title
            continue
        m = LINE_RE.match(s)
        if not m:
            bad.append(f"{index}장 {n}번째 줄: [이름] 표기가 없다 → {s[:30]}")
            continue
        spk, body = m.group(1).strip(), m.group(2).strip()
        body = body.strip().strip('"“”').strip()
        if body:
            lines.append({"spk": spk, "text": body})
    return {"index": index, "title": title or f"{index}장", "lines": lines, "_bad": bad}


def chapter_files(folder: str) -> list[str]:
    return sorted(f for f in os.listdir(folder) if re.fullmatch(r"ch\d{2}\.txt", f))


def load_meta(folder: str) -> dict:
    with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def cast_voices(meta: dict, narrator_gender: str) -> dict:
    """등장인물마다 목소리 배정 — 성별별 목록을 차례로. 화자 목소리와 겹치지 않게."""
    nv = NARRATOR_VOICE[narrator_gender]
    voices = {NARRATOR: nv}
    used = {"F": 0, "M": 0}
    for c in meta.get("characters") or []:
        g = "M" if str(c.get("gender", "F")).upper().startswith("M") else "F"
        pool = [v for v in CAST_VOICES[g] if v != nv] or CAST_VOICES[g]
        voices[c["name"]] = pool[used[g] % len(pool)]
        used[g] += 1
    return voices


def build(folder: str) -> dict:
    meta = load_meta(folder)
    d = dt.date.fromisoformat(str(meta.get("date"))[:10])
    a = assign(d)
    chapters = []
    for i, fn in enumerate(chapter_files(folder), 1):
        with open(os.path.join(folder, fn), encoding="utf-8") as f:
            chapters.append(parse_chapter(f.read(), i))
    voices = cast_voices(meta, a["narrator_gender"])
    spec = {
        "topic": "drama", "date": d.isoformat(), "episode": a["episode"],
        "story_id": meta.get("story_id") or f"drama-{d.isoformat()}",
        "archetype": a["archetype"], "narrator_gender": a["narrator_gender"],
        "title": meta.get("title", ""), "description": meta.get("description", ""),
        "thumbnail_text": meta.get("thumbnail_text", ""), "thumbnail_prompt": meta.get("thumbnail_prompt", ""),
        "characters": meta.get("characters") or [], "images": meta.get("images") or [],
        "tags": meta.get("tags") or [], "voices": voices,
        "chapters": [{k: v for k, v in c.items() if k != "_bad"} for c in chapters],
        "_parse_errors": [e for c in chapters for e in c["_bad"]],
    }
    spec["stats"] = stats(spec)
    return spec


def stats(spec: dict) -> dict:
    lines = [ln for c in spec["chapters"] for ln in c["lines"]]
    chars = sum(len(ln["text"]) for ln in lines)
    nar = sum(len(ln["text"]) for ln in lines if ln["spk"] == NARRATOR)
    return {"chars": chars, "lines": len(lines), "chapters": len(spec["chapters"]),
            "narrator_share": round(nar / chars, 3) if chars else 0.0,
            "est_min": round(chars / 450 / 0.92 + len(lines) * 0.45 / 60, 1)}


# ── 검사(게이트) ──────────────────────────────────────────────
def check(spec: dict, allow_short: bool = False) -> list[str]:
    """문제 목록. 비어 있어야 업로드한다."""
    p = list(spec.get("_parse_errors") or [])[:10]
    st = spec.get("stats") or stats(spec)
    if not allow_short:
        if st["chars"] < MIN_CHARS:
            p.append(f"분량 부족: {st['chars']:,}자 (최소 {MIN_CHARS:,}자 ≈ 85분)")
        if not MIN_CH <= st["chapters"] <= MAX_CH:
            p.append(f"장 수 {st['chapters']} (허용 {MIN_CH}~{MAX_CH})")
        for c in spec["chapters"]:
            n = sum(len(ln["text"]) for ln in c["lines"])
            if n < MIN_CH_CHARS:
                p.append(f"{c['index']}장 분량 {n:,}자 (최소 {MIN_CH_CHARS:,}자)")
    if st["chars"] > MAX_CHARS:
        p.append(f"분량 초과: {st['chars']:,}자 (최대 {MAX_CHARS:,}자)")
    declared = {c.get("name") for c in spec.get("characters") or []}
    if len(declared) > MAX_CAST:
        p.append(f"등장인물 {len(declared)}명 (최대 {MAX_CAST}명 — 목소리가 모자라다)")
    unknown = sorted({ln["spk"] for c in spec["chapters"] for ln in c["lines"]} - declared - {NARRATOR})
    if unknown:
        p.append(f"meta.characters 에 없는 이름: {', '.join(unknown)}")
    if st["narrator_share"] < MIN_NARRATOR_SHARE:
        p.append(f"화자 비중 {st['narrator_share']:.0%} (최소 {MIN_NARRATOR_SHARE:.0%} — 대사만 이어지면 따라가기 어렵다)")
    t = spec.get("title", "")
    if not t or len(t) > TITLE_MAX:
        p.append(f"제목 길이 {len(t)}자 (1~{TITLE_MAX}자)")
    if not (spec.get("thumbnail_text") or "").strip():
        p.append("thumbnail_text 없음")
    if not (spec.get("description") or "").strip():
        p.append("description 없음")
    by_ch = {}
    for im in spec.get("images") or []:
        by_ch[int(im.get("chapter", 0))] = by_ch.get(int(im.get("chapter", 0)), 0) + 1
    for c in spec["chapters"]:
        if by_ch.get(c["index"], 0) < 1:
            p.append(f"{c['index']}장 그림 프롬프트 없음 (장마다 {IMG_PER_CH[0]}~{IMG_PER_CH[1]}개)")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="사연 드라마 배정·조립·검사")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assign")
    a.add_argument("--date", required=True)
    for name in ("count", "build"):
        s = sub.add_parser(name)
        s.add_argument("folder")
        s.add_argument("--allow-short", action="store_true")
    args = ap.parse_args()
    if args.cmd == "assign":
        print(json.dumps(assign(dt.date.fromisoformat(args.date)), ensure_ascii=False, indent=2))
        return 0
    spec = build(args.folder)
    probs = check(spec, allow_short=args.allow_short)
    st = spec["stats"]
    print(f"분량 {st['chars']:,}자 · {st['chapters']}장 · {st['lines']}줄 · 화자 {st['narrator_share']:.0%} · 예상 {st['est_min']}분")
    for c in spec["chapters"]:
        print(f"  {c['index']:>2}장 {sum(len(x['text']) for x in c['lines']):>6,}자  {c['title']}")
    if args.cmd == "build":
        out = os.path.join(args.folder, "spec.json")
        spec.pop("_parse_errors", None)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        print(f"→ {out}")
    if probs:
        print("\n❌ 고칠 것:")
        for x in probs:
            print("  - " + x)
        return 1
    print("✅ 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
