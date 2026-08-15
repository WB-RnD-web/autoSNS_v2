#!/usr/bin/env python3
"""Freesound API — 테마별 ASMR 소스 음원 검색·다운로드 (CC0 우선).

토큰(API 키)만으로 검색 + 미리듣기(mp3) 다운로드가 된다. 원본 고음질은 OAuth2 필요(선택).
수면 ASMR 앰비언트는 미리듣기(hq mp3, ≈128k)로 시작 가능.

env: FREESOUND_API_KEY

라이선스: 기본 CC0("Creative Commons 0")만 받아 출처표기 부담을 없앤다.
  FREESOUND_ALLOW_BY=1 이면 CC-BY 도 허용(그 경우 attribution 을 설명란에 넣어야 안전).
"""
from __future__ import annotations
import os
import sys

BASE = "https://freesound.org/apiv2"


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def _headers(key: str) -> dict:
    return {"Authorization": f"Token {key}"}


def _license_filter() -> str:
    # CC0 우선. CC-BY 허용 옵션(출처표기 필요).
    if os.environ.get("FREESOUND_ALLOW_BY", "0") == "1":
        return '(license:"Creative Commons 0" OR license:"Attribution")'
    return 'license:"Creative Commons 0"'


# 쿼리에서 '무엇의 소리인지'를 특정하지 못하는 수식어 — 관련성 판정에서 제외한다.
_STOPWORDS = {
    "asmr", "loop", "loops", "ambience", "ambient", "sound", "sounds", "noise",
    "white", "background", "soft", "gentle", "quiet", "calm", "relaxing", "cozy",
    "close", "mic", "night", "room", "tone", "no", "music", "talking", "speech",
    "and", "the", "with", "for", "long", "hour", "sleep", "sleeping",
}
# ASMR/백색소음에 음악 트랙이 섞이는 것을 막는다("keyboard"=건반악기 같은 동음이의어 방어).
_MUSICAL = {
    "music", "musical", "song", "melody", "chord", "chords", "harmony", "instrument",
    "synth", "synthesizer", "piano", "guitar", "drum", "drums", "bass", "beat", "beats",
    "reggae", "jazz", "techno", "edm", "house", "remix", "vocal", "vocals", "singing",
    "toolkit", "sample pack", "riff", "bpm", "melodic",
}


def _words(text: str) -> set:
    import re
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2}


def core_terms(query: str) -> set:
    """쿼리에서 핵심 명사만 남긴다. 예: 'mechanical keyboard typing asmr' → {mechanical,keyboard,typing}"""
    return _words(query) - _STOPWORDS


def _haystack(item: dict) -> set:
    tags = item.get("tags") or []
    return _words(item.get("name", "")) | {str(t).lower() for t in tags}


def relevance(item: dict, terms: set) -> int:
    """테마 핵심어가 음원 이름/태그에 몇 개나 걸리는지. 0이면 무관한 음원."""
    return len(terms & _haystack(item)) if terms else 1


def is_musical(item: dict) -> bool:
    """음악 트랙으로 보이면 True(ASMR 소스로 부적합)."""
    return bool(_haystack(item) & _MUSICAL)


def search(query: str, key: str, min_sec: int = 20, max_sec: int = 600,
           page_size: int = 30):
    """텍스트 검색 → 결과 리스트(dict: id,name,duration,previews,license,username,url,tags).

    duration 필터 + 라이선스 필터 + ★관련도(score) 정렬. 실패 시 [].

    ⚠️ 과거 downloads_desc(인기순)를 쓰다가 관련도가 통째로 버려져,
       'mechanical keyboard typing asmr' 검색에 'Crashing Starship' 같은 무관한
       인기 음원이 담기는 사고가 있었다(2026-07-17 keyboard-typing). 관련도 정렬 유지할 것.
    """
    requests = _requests()
    filt = f"{_license_filter()} duration:[{min_sec} TO {max_sec}]"
    params = {
        "query": query, "filter": filt,
        "fields": "id,name,duration,previews,license,username,url,tags",
        "sort": "score", "page_size": page_size,
    }
    try:
        r = requests.get(f"{BASE}/search/text/", params=params,
                         headers=_headers(key), timeout=40)
        if r.status_code != 200:
            sys.stderr.write(f"[warn] Freesound 검색 {r.status_code}: {r.text[:200]}\n")
            return []
        return r.json().get("results", []) or []
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] Freesound 검색 예외({query}): {e}\n")
        return []


def _download_preview(item: dict, out_path: str) -> bool:
    """미리듣기(hq mp3 우선) 다운로드. 성공 시 True."""
    requests = _requests()
    prev = item.get("previews") or {}
    src = prev.get("preview-hq-mp3") or prev.get("preview-lq-mp3") \
        or prev.get("preview-hq-ogg") or prev.get("preview-lq-ogg")
    if not src:
        return False
    try:
        r = requests.get(src, timeout=60)
        if r.status_code != 200 or not r.content:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)
        return os.path.getsize(out_path) > 0
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] Freesound 다운로드 예외({item.get('id')}): {e}\n")
        return False


def fetch_triggers(queries: list[str], out_dir: str, want_n: int = 14,
                   min_sec: float = 0.3, max_sec: float = 8.0, key: str | None = None):
    """★단발 트리거음 수집 — fetch_theme 과 달리 ★짧은 클립을 노린다.

    앰비언트 수집은 duration:[20 TO 600] 로 거른다. 루프를 만들려면 그래야 하지만,
    왁뿌볼(왁스 깨짐)·뽁뽁이·크런치 같은 트리거음은 ★1~3초짜리라 그 필터에서 통째로
    사라진다. 그래서 짧은 쪽만 따로 긁는 경로를 둔다.

    반환: (files[str], attributions[dict]) — fetch_theme 과 같은 모양.
    비어도 렌더는 계속된다(트리거 없이 베드만).
    """
    key = key or os.environ.get("FREESOUND_API_KEY")
    if not key or not queries:
        return [], []
    os.makedirs(out_dir, exist_ok=True)
    files, attrs, seen = [], [], set()
    for q in queries:
        if len(files) >= want_n:
            break
        terms = core_terms(q)
        for it in search(q, key, min_sec=int(min_sec), max_sec=int(max_sec), page_size=30):
            if len(files) >= want_n:
                break
            if it["id"] in seen or is_musical(it):
                continue
            d = float(it.get("duration") or 0)
            if not (min_sec <= d <= max_sec):     # API 는 초 단위 반올림이라 한 번 더 본다
                continue
            if relevance(it, terms) < 1:
                continue
            dst = os.path.join(out_dir, f"trg_{it['id']}.mp3")
            if not _download_preview(it, dst):
                continue
            seen.add(it["id"])
            files.append(dst)
            attrs.append({"name": it.get("name"), "username": it.get("username"),
                          "url": it.get("url"), "license": it.get("license")})
    print(f"   → 트리거 클립 {len(files)}개 (목표 {want_n}개, {min_sec:.0f}~{max_sec:.0f}s)")
    return files, attrs


def fetch_theme(queries: list[str], out_dir: str, want_sec: int = 1800,
                max_clips: int = 12, key: str | None = None):
    """테마 쿼리들로 CC0 클립을 want_sec(합계 길이) 이상 모을 때까지 다운로드.

    반환: (files[str], attributions[dict:name,username,url,license]).
    files 가 비면 호출측이 렌더를 중단해야 한다(오디오 없이는 ASMR 불가)."""
    key = key or os.environ.get("FREESOUND_API_KEY")
    if not key:
        sys.stderr.write("[error] FREESOUND_API_KEY 없음 — ASMR 오디오 소스 불가\n")
        return [], []
    os.makedirs(out_dir, exist_ok=True)
    terms = set()
    for q in queries:
        terms |= core_terms(q)

    def _candidates(qs: list[str], min_rel: int) -> list[dict]:
        """검색만 수행해 후보를 모으고, 관련도 min_rel 이상 + 비음악 만 남겨 정렬."""
        pool = {}
        for q in qs:
            for it in search(q, key):
                fid = it.get("id")
                # taken: 이전 라운드에서 이미 받은 음원(라운드 간 중복 방지)
                if not fid or fid in pool or fid in taken or float(it.get("duration") or 0) <= 0:
                    continue
                if is_musical(it):
                    continue
                rel = relevance(it, terms)
                if rel < min_rel:
                    continue
                it["_rel"] = rel
                pool[fid] = it
        # 관련도 높은 순 → 같으면 긴 클립 우선(루프 이음새가 적어 자연스럽다)
        return sorted(pool.values(), key=lambda x: (-x["_rel"], -float(x.get("duration") or 0)))

    def _download(cands: list[dict]):
        for it in cands:
            if total[0] >= want_sec or len(files) >= max_clips:
                break
            dur = float(it.get("duration") or 0)
            dst = os.path.join(out_dir, f"fs_{it['id']}.mp3")
            if _download_preview(it, dst):
                taken.add(it["id"])
                files.append(dst)
                total[0] += dur
                attrs.append({"name": it.get("name"), "username": it.get("username"),
                              "url": it.get("url"), "license": it.get("license")})
                print(f"   · Freesound 다운로드: {it.get('name','?')[:36]} "
                      f"({dur:.0f}s, 관련도 {it['_rel']}, by {it.get('username')})")

    files, attrs, total, taken = [], [], [0.0], set()

    # 1차: 원본 쿼리 + 관련도 1 이상(테마 핵심어가 이름/태그에 최소 1개)
    _download(_candidates(queries, min_rel=1))

    # 2차: 소스가 부족하면 쿼리를 점진 완화해 ★온-토픽 소재를 더 모은다.
    #   - 0건 사례(2026-07-18 quiet-cafe, 2026-08-06 library): 자연어 쿼리가
    #     CC0+duration 필터와 겹쳐 아무것도 안 걸리는 경우
    #   - 부족 사례: 엄격 필터 통과분이 짧아 1시간을 짧은 루프로 때우게 되는 경우
    #   어느 쪽이든 관련도 기준(1 이상)은 유지한다 — 무관한 음원을 채우느니 반복이 낫다.
    for n in (2, 1):
        if total[0] >= want_sec or len(files) >= max_clips:
            break
        relaxed = []
        for q in queries:
            rq = " ".join((q or "").split()[:n])
            if rq and rq not in relaxed:
                relaxed.append(rq)
        if relaxed:
            print(f"   ↺ 소스 부족({total[0]:.0f}/{want_sec}s) → 쿼리 완화(앞 {n}단어): {relaxed}")
            _download(_candidates(relaxed, min_rel=1))

    # 3차 폴백: 그래도 0건이면 관련도 조건을 풀어 최소한의 소스라도 확보한다
    # (무음 실패보다는 낫다. 단 음악 트랙 제외는 유지).
    if not files:
        print("   ↺ 여전히 0건 → 관련도 조건 해제(음악 제외는 유지)")
        _download(_candidates(queries, min_rel=0))

    print(f"   → Freesound 클립 {len(files)}개, 합계 {total[0]:.0f}s (목표 {want_sec}s)")
    return files, attrs


def attribution_block(attrs: list[dict]) -> str:
    """CC-BY 사용 시 유튜브 설명란에 넣을 출처 문단. CC0만이면 빈 문자열."""
    by = [a for a in attrs if a.get("license") and "creativecommons.org/publicdomain/zero" not in (a.get("license") or "")]
    if not by:
        return ""
    lines = ["음원 출처(Freesound):"]
    for a in by:
        lines.append(f"· {a.get('name')} — {a.get('username')} ({a.get('url')})")
    return "\n".join(lines)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Freesound 테마 음원 수집(테스트)")
    ap.add_argument("--query", action="append", required=True, help="검색어(여러 번 가능)")
    ap.add_argument("--out", default="_fs_work")
    ap.add_argument("--want-sec", type=int, default=300)
    args = ap.parse_args()
    files, attrs = fetch_theme(args.query, args.out, want_sec=args.want_sec)
    print(f"\n다운로드 {len(files)}개")
    print(attribution_block(attrs) or "(CC0만 — 출처표기 불필요)")
    return 0 if files else 1


if __name__ == "__main__":
    raise SystemExit(main())
