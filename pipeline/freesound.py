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


def search(query: str, key: str, min_sec: int = 20, max_sec: int = 600,
           page_size: int = 15):
    """텍스트 검색 → 결과 리스트(dict: id,name,duration,previews,license,username,url).

    duration 필터 + 라이선스 필터 + 다운로드/평점 순 정렬(품질 우선). 실패 시 []."""
    requests = _requests()
    filt = f"{_license_filter()} duration:[{min_sec} TO {max_sec}]"
    params = {
        "query": query, "filter": filt,
        "fields": "id,name,duration,previews,license,username,url",
        "sort": "downloads_desc", "page_size": page_size,
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
    files, attrs, seen = [], [], set()
    total = 0.0

    def _collect(qs: list[str]):
        nonlocal total
        for q in qs:
            if total >= want_sec or len(files) >= max_clips:
                break
            for it in search(q, key):
                if total >= want_sec or len(files) >= max_clips:
                    break
                fid = it.get("id")
                if fid in seen:
                    continue
                dur = float(it.get("duration") or 0)
                if dur <= 0:
                    continue
                dst = os.path.join(out_dir, f"fs_{fid}.mp3")
                if _download_preview(it, dst):
                    seen.add(fid)
                    files.append(dst)
                    total += dur
                    attrs.append({"name": it.get("name"), "username": it.get("username"),
                                  "url": it.get("url"), "license": it.get("license")})
                    print(f"   · Freesound 다운로드: {it.get('name','?')[:36]} ({dur:.0f}s, by {it.get('username')})")

    _collect(queries)
    # 0건 폴백: 루틴이 주는 자연어 쿼리(단어 5~6개)는 전부 AND 매칭이라
    # CC0+duration 필터와 겹치면 결과 0이 되기 쉽다(2026-07-18 quiet-cafe 관측).
    # 앞 2단어 → 앞 1단어로 점진 완화해 재시도한다(라이선스 정책은 그대로).
    for n in (2, 1):
        if files:
            break
        relaxed = []
        for q in queries:
            rq = " ".join((q or "").split()[:n])
            if rq and rq not in relaxed:
                relaxed.append(rq)
        if relaxed:
            print(f"   ↺ 검색 0건 → 쿼리 완화(앞 {n}단어) 재시도: {relaxed}")
            _collect(relaxed)
    print(f"   → Freesound 클립 {len(files)}개, 합계 {total:.0f}s (목표 {want_sec}s)")
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
