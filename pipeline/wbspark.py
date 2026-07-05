#!/usr/bin/env python3
"""wbSpark(qwen-image) 게이트웨이 클라이언트 — 비동기 잡큐.

사내 Spark 서버의 qwen-image 를 회사 도메인 게이트웨이로 노출한 것.
외부 공인(211.168.38.218, split-horizon DNS)이라 GitHub Actions 러너에서도 호출된다.

API:
  POST {BASE}/jobs   {"type":"image","prompt":"..."} → {"job_id","status":"queued"}
  GET  {BASE}/jobs/{id}                               → {"status":"queued|...|done|error|failed"}
  GET  {BASE}/jobs/{id}/file                          → PNG 바이너리

환경변수:
  WBSPARK_BASE   기본 https://wangbyul.com/wbSpark
  WBSPARK_TOKEN  (선택) 있으면 Authorization: Bearer 로 전송

썸네일은 best-effort — 실패해도 예외 대신 False 를 반환해 파이프라인을 막지 않는다.
"""
from __future__ import annotations
import os
import sys
import time

DEFAULT_BASE = "https://wangbyul.com/wbSpark"


def _requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        raise SystemExit("[error] pip install requests (pipeline/requirements.txt)")


def _base() -> str:
    return (os.environ.get("WBSPARK_BASE") or DEFAULT_BASE).rstrip("/")


def _headers() -> dict:
    tok = os.environ.get("WBSPARK_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def generate_image(prompt: str, out_path: str,
                   timeout_sec: int = 720, poll_sec: float = 4.0) -> bool:
    """프롬프트로 이미지 1장 생성 → out_path 에 PNG 저장. 성공 시 True.

    생성이 5~10분 걸릴 수 있어 timeout_sec 기본 12분. 실패는 경고 후 False.
    """
    requests = _requests()
    base, headers = _base(), _headers()
    try:
        r = requests.post(f"{base}/jobs", json={"type": "image", "prompt": prompt},
                          headers=headers, timeout=40)
        if r.status_code != 200:
            sys.stderr.write(f"[warn] wbSpark 제출 실패 {r.status_code}: {r.text[:200]}\n")
            return False
        job_id = r.json().get("job_id")
        if not job_id:
            sys.stderr.write(f"[warn] wbSpark job_id 없음: {r.text[:200]}\n")
            return False
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] wbSpark 제출 예외: {e}\n")
        return False

    deadline = time.monotonic() + timeout_sec
    status = "?"
    while time.monotonic() < deadline:
        time.sleep(poll_sec)
        try:
            s = requests.get(f"{base}/jobs/{job_id}", headers=headers, timeout=30)
            status = (s.json() or {}).get("status", "?")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] wbSpark 폴링 예외(계속): {e}\n")
            continue
        if status == "done":
            break
        if status in ("error", "failed"):
            sys.stderr.write(f"[warn] wbSpark 생성 실패: {s.text[:200]}\n")
            return False
    else:
        sys.stderr.write(f"[warn] wbSpark 타임아웃({timeout_sec}s, 마지막 status={status})\n")
        return False

    try:
        f = requests.get(f"{base}/jobs/{job_id}/file", headers=headers, timeout=60)
        if f.status_code != 200 or not f.content:
            sys.stderr.write(f"[warn] wbSpark 파일 수신 실패 {f.status_code}\n")
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "wb") as fp:
            fp.write(f.content)
        return True
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] wbSpark 다운로드 예외: {e}\n")
        return False


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="wbSpark 이미지 생성(테스트)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", default="wbspark_out.png")
    ap.add_argument("--timeout", type=int, default=720)
    args = ap.parse_args()
    ok = generate_image(args.prompt, args.out, timeout_sec=args.timeout)
    print(("✅ 저장: " + args.out) if ok else "❌ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
