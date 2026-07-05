#!/usr/bin/env python3
"""소설(novel) render-spec JSON 파서·검증.

루틴이 출력하는 에피소드 render-spec(Part A §3)을 읽어 안전하게 다룰 수 있도록 정규화한다.
쇼츠 스토리보드 스키마와 무관한 별도 스키마다.

검증 원칙(가드레일 일부를 렌더/업로드 전에 한 번 더 강제 — 과제 13):
  - 16:9 고정(background.aspect != "16:9" 여도 렌더러가 1920x1080 으로 정규화하므로 경고만).
  - segments 가 narration_full 을 사실상 덮는지(글자수 기준) 점검 — 누락 시 경고.
  - privacy 는 ★루틴 값 그대로 존중(오버라이드 없음). 미지정/비표준만 안전하게 private 폴백 + 경고.
  - 제목에 '#shorts' 가 있으면 제거(소설은 일반 동영상).

사용:
  python pipeline/novel_spec.py output/novel/<sid>/ep1_<date>.json   # 검증 + 요약 출력
"""
from __future__ import annotations
import argparse
import json
import sys

GENRES = {"로맨스", "잔혹동화", "판타지", "추리", "공포"}
RATINGS = {"all", "teen", "mature"}
PRIVACIES = {"public", "unlisted", "private"}

REQUIRED = ["series_id", "series_title", "episode_no", "narration_full", "segments",
            "background", "platforms"]


class SpecError(ValueError):
    """치명적 스키마 오류(렌더 불가)."""


def _warn(msgs: list, m: str) -> None:
    msgs.append(m)


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(spec: dict) -> tuple[dict, list[str]]:
    """spec 을 검증·정규화하고 (정규화본, 경고목록)을 반환. 치명 오류는 SpecError."""
    warns: list[str] = []
    s = dict(spec)  # 얕은 복사

    # ── 필수 필드 ──
    missing = [k for k in REQUIRED if not s.get(k)]
    if missing:
        raise SpecError(f"필수 필드 누락: {missing}")

    if s.get("topic", "novel") != "novel":
        _warn(warns, f"topic 이 'novel' 아님: {s.get('topic')!r}")

    # ── 장르 ──
    genre = s.get("genre", "")
    if genre and genre not in GENRES:
        _warn(warns, f"알 수 없는 장르: {genre!r} (허용: {sorted(GENRES)})")

    # ── 회차 번호 ──
    try:
        s["episode_no"] = int(s["episode_no"])
    except (TypeError, ValueError):
        raise SpecError(f"episode_no 정수 아님: {s.get('episode_no')!r}")
    s["total_episodes"] = int(s.get("total_episodes") or 0)
    s["is_finale"] = bool(s.get("is_finale", False))

    # ── segments ──
    segs = s.get("segments") or []
    if not isinstance(segs, list) or not segs:
        raise SpecError("segments 비어있음 — 자막/타이밍 단위 필요")
    norm_segs = []
    for i, seg in enumerate(segs):
        if isinstance(seg, str):
            seg = {"text": seg}
        text = (seg.get("text") or "").strip()
        if not text:
            _warn(warns, f"segments[{i}] 빈 텍스트 — 건너뜀")
            continue
        norm_segs.append({"text": text, "est_sec": float(seg.get("est_sec") or 0)})
    if not norm_segs:
        raise SpecError("유효한 segment 가 하나도 없음")
    s["segments"] = norm_segs

    # ── narration_full vs segments 커버리지 ──
    nf = (s.get("narration_full") or "").strip()
    s["narration_full"] = nf
    seg_chars = sum(len(x["text"]) for x in norm_segs)
    nf_chars = len(nf)
    if nf_chars:
        ratio = seg_chars / max(1, nf_chars)
        if ratio < 0.85:
            _warn(warns, f"segments 가 narration_full 의 {ratio:.0%} 만 덮음 "
                         f"(자막 누락 가능). seg={seg_chars}자 / full={nf_chars}자")
    # 분량(≈10분 = 3,000~3,800자) 점검 — 경고만
    body_chars = nf_chars or seg_chars
    if body_chars < 1200:
        _warn(warns, f"본문 {body_chars}자 — 10분 목표(3,000~3,800자)보다 매우 짧음(테스트면 무시)")
    elif body_chars > 4500:
        _warn(warns, f"본문 {body_chars}자 — 10분 목표보다 김(TTS 길어짐)")

    # ── background ──
    bg = dict(s.get("background") or {})
    if not bg.get("prompt"):
        _warn(warns, "background.prompt 비어있음 — 장르 기본 배경으로 렌더")
    if bg.get("aspect") and bg["aspect"] != "16:9":
        _warn(warns, f"background.aspect={bg.get('aspect')!r} — 렌더러가 16:9 로 정규화")
    bg.setdefault("id", f"{s['series_id']}_bg")
    bg.setdefault("reuse", True)
    s["background"] = bg

    # ── thumbnail (선택): 루틴이 대본 한줄요약을 thumbnail_hook 으로 제공 ──
    #    있으면 CI 가 qwen-image 로 회차별 썸네일 생성(장르맞춤 스타일)+제목 오버레이+YT 지정.
    #    없으면 썸네일 스킵(YouTube 자동 프레임) — 파이프라인은 정상 진행.
    s["thumbnail_hook"] = (s.get("thumbnail_hook") or "").strip()
    s["thumbnail_style"] = (s.get("thumbnail_style") or "").strip().lower()
    if not s["thumbnail_hook"]:
        _warn(warns, "thumbnail_hook 없음 — 커스텀 썸네일 스킵(YT 자동 프레임)")

    # ── content_rating ──
    rating = (s.get("content_rating") or "all").lower()
    if rating not in RATINGS:
        _warn(warns, f"content_rating={rating!r} 비표준 → all 취급")
        rating = "all"
    s["content_rating"] = rating

    # ── privacy: ★루틴이 정한 값을 그대로 존중(파이프라인은 오버라이드하지 않음) ──
    #    공개/부분공개/비공개는 '루틴'이 결정한다. 파이프라인은 강등/강요하지 않는다.
    #    미지정·비표준 값일 때만 사고 방지로 private 폴백 + 경고(이건 '결정'이 아니라 안전 폴백).
    raw = s.get("privacy")
    privacy = (raw or "").lower()
    if not raw:
        _warn(warns, "privacy 미지정 → 안전하게 private 폴백(루틴 JSON 에 명시 권장)")
        privacy = "private"
    elif privacy not in PRIVACIES:
        _warn(warns, f"privacy={raw!r} 비표준(허용: public|unlisted|private) → 안전하게 private 폴백")
        privacy = "private"
    # mature 회차는 보통 unlisted 가 안전하지만, 공개도는 ★루틴이 결정한다 → 강등 없이 경고만.
    if rating == "mature" and privacy == "public":
        _warn(warns, "content_rating=mature 인데 privacy=public — 루틴 의도면 그대로 진행(파이프라인 강등 없음)")
    s["privacy"] = privacy

    # ── platforms.youtube ──
    yt = dict((s.get("platforms") or {}).get("youtube") or {})
    title = (yt.get("title") or f"{s['series_title']} EP{s['episode_no']}").strip()
    # 소설은 일반 동영상 — #shorts 금지
    low = title.lower()
    if "#shorts" in low or "#short" in low:
        title = title.replace("#Shorts", "").replace("#shorts", "").replace("#Short", "").replace("#short", "").strip()
        _warn(warns, "제목의 #shorts 제거(소설은 일반 동영상)")
    yt["title"] = title[:100]
    if not yt.get("description"):
        _warn(warns, "youtube.description 비어있음")
        yt["description"] = s.get("logline", "")
    if "#shorts" in (yt.get("description") or "").lower():
        yt["description"] = yt["description"].replace("#shorts", "").replace("#Shorts", "")
        _warn(warns, "설명의 #shorts 제거")
    yt.setdefault("playlist", s.get("series_title", ""))
    s["platforms"] = {**s.get("platforms", {}), "youtube": yt}

    return s, warns


def main() -> int:
    ap = argparse.ArgumentParser(description="소설 render-spec 검증")
    ap.add_argument("spec", help="에피소드 render-spec JSON 경로")
    ap.add_argument("--json", action="store_true", help="정규화본을 JSON 으로 출력")
    args = ap.parse_args()
    try:
        spec = load(args.spec)
        norm, warns = normalize(spec)
    except (SpecError, json.JSONDecodeError, OSError) as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(norm, ensure_ascii=False, indent=2))
        return 0

    print("──── 소설 render-spec 검증 ────")
    print(f"  series   : {norm['series_id']}  ({norm.get('genre','?')})")
    print(f"  title    : {norm['series_title']}  EP{norm['episode_no']}/{norm['total_episodes']}"
          + ("  [완결]" if norm["is_finale"] else ""))
    print(f"  본문     : {len(norm['narration_full'])}자  ·  segments {len(norm['segments'])}개")
    print(f"  rating   : {norm['content_rating']}  ·  privacy: {norm['privacy']}")
    print(f"  playlist : {norm['platforms']['youtube']['playlist']!r}")
    print(f"  yt title : {norm['platforms']['youtube']['title']!r}")
    if warns:
        print("  ⚠️ 경고:")
        for w in warns:
            print(f"     - {w}")
    else:
        print("  ✅ 경고 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
