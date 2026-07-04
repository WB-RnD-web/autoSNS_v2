#!/usr/bin/env python3
"""IG/Threads 장기토큰 자동 갱신 → GitHub Secret 재기록.

Meta 장기토큰(60일)은 만료 전(≥24h 경과) 갱신하면 갱신 시점부터 다시 60일 연장된다.
주 1회 실행하면 사실상 무기한 유지된다. 앱 시크릿 불필요 — 현재 토큰만 있으면 됨.

갱신된 새 토큰을 gh CLI 로 같은 이름의 GitHub Secret 에 덮어써서, 다음 파이프라인
실행이 항상 유효한 토큰을 읽게 한다(토큰은 프로세스 메모리에만 두고 로그/파일로 노출 안 함).

요구 환경(워크플로에서 주입):
  - THREADS_ACCESS_TOKEN, IG_ACCESS_TOKEN : 현재(갱신 대상) 토큰. 없으면 해당 플랫폼 스킵.
  - GH_TOKEN         : Secrets write 권한 PAT (gh secret set 용)
  - GITHUB_REPOSITORY: owner/repo (GitHub 러너 기본 제공, 예: WB-RnD-web/autoSNS_v2)

각 플랫폼은 독립 — 하나 실패해도 나머지는 진행한다. 하나라도 실패하면 exit 1.

참고: IG 토큰이 '구' Facebook 로그인 그래프 토큰이면 아래 ig_refresh_token 엔드포인트가
아니라 fb_exchange_token(앱 시크릿 필요) 방식이라 실패한다. 그 경우 에러 메시지를 보고
IG_REFRESH_URL/IG_REFRESH_GRANT 를 교체하거나 별도 처리한다(현재 앱은 Instagram 로그인
유즈케이스라 ig_refresh_token 이 맞음).
"""
from __future__ import annotations
import os
import subprocess
import sys

# (secret 이름, 갱신 엔드포인트, grant_type)
TARGETS = [
    ("THREADS_ACCESS_TOKEN",
     "https://graph.threads.net/refresh_access_token", "th_refresh_token"),
    ("IG_ACCESS_TOKEN",
     "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
]


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def refresh(url: str, grant: str, token: str) -> tuple[str, int]:
    """장기토큰 갱신 → (새 토큰, 만료까지 초). 실패 시 예외."""
    requests = _requests()
    r = requests.get(url, params={"grant_type": grant, "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    new = data.get("access_token")
    if not new:
        raise RuntimeError(f"응답에 access_token 없음: {data}")
    return new, int(data.get("expires_in", 0))


def set_secret(name: str, value: str, repo: str) -> None:
    """gh CLI 로 리포지토리 Secret 덮어쓰기(값은 stdin 으로만 전달)."""
    subprocess.run(
        ["gh", "secret", "set", name, "--repo", repo],
        input=value, text=True, check=True,
        capture_output=True,  # 혹시 모를 값 노출 방지
    )


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("[error] GITHUB_REPOSITORY 필요(owner/repo)", file=sys.stderr)
        return 1
    if not os.environ.get("GH_TOKEN"):
        print("[error] GH_TOKEN(PAT) 필요 — Secrets write 권한", file=sys.stderr)
        return 1

    failed = False
    for name, url, grant in TARGETS:
        cur = os.environ.get(name)
        if not cur:
            print(f"[skip] {name} 미설정 — 건너뜀")
            continue
        try:
            new, exp = refresh(url, grant, cur)
            set_secret(name, new, repo)
            days = exp // 86400 if exp else "?"
            same = "(변화 없음)" if new == cur else ""
            print(f"[ok] {name} 갱신·기록 완료 — 만료 {days}일 후 {same}")
        except subprocess.CalledProcessError as e:
            failed = True
            print(f"[fail] {name} Secret 기록 실패: gh 오류 {e.returncode}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            failed = True
            print(f"[fail] {name} 갱신 실패: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
