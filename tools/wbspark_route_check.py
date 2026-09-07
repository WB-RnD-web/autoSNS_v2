#!/usr/bin/env python3
"""wbSpark 라우팅 점검 — "no text" 접미사가 Qwen-Image 를 부르는지 확인한다.

배경
  게이트웨이의 needs_text() 는 프롬프트에 글자 관련 낱말(글자·간판·text·sign·
  title·word·logo…)이 있으면 Qwen-Image(30GB)로 보낸다. 기본 경로는 Z-Image(21GB).
  그런데 우리 파이프라인은 모든 이미지 프롬프트 끝에
  "no text, no letters, no watermark" 를 붙인다 — 부정형이지만 낱말은 들어 있다.
  이 검사가 부정형을 걸러내지 못한다면, 글자를 넣지 말라고 쓴 문장 때문에
  글자 특화 모델이 30GB 를 물고 도는 셈이 된다. 의도와 정반대다.

무엇을 하나
  같은 그림 프롬프트를 접미사만 빼고/붙여서 제출하고, 서버가 응답에 담아주는
  실제 model 을 비교한다. 모델이 갈리면 원인 확정.

  기본은 no_llm:true — LLM 재작성을 배제하고 원문만으로 needs_text 가 걸리는지 본다.
  --with-llm 을 주면 LLM 보정을 켠 실제 프로덕션 경로도 이어서 잰다
  (needs_text 는 LLM 이 만든 enhanced_prompt 도 검사하므로 결과가 다를 수 있다).

읽기 전용이다. POST /jobs 와 GET /jobs/{id} 만 부르고 서버 설정을 바꾸지 않는다.
산출물은 서버에 이미지 몇 장이 남을 뿐이고 게이트웨이가 1시간 뒤 정리한다.

실행 (Windows cmd)
    python tools\\wbspark_route_check.py
    tools\\check-wbspark-route.bat          ← 같은 것. 더블클릭도 된다.

실행 (bash)
    python3 tools/wbspark_route_check.py

표준 라이브러리만 쓴다 — pip install 없이 어디서나 돈다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://wangbyul.com/wbSpark"

# 접미사가 붙지 않은 순수 그림 프롬프트. 프로브(wbspark-probe.yml) 테스트 A 와 같은 문장이라
# 거기서 확인된 "이건 z-image 로 간다" 를 기준선으로 그대로 쓸 수 있다.
BASE_PROMPT = "a red apple on a white table, studio lighting"

# pipeline/thumbnail.py 의 TECH 꼬리. 아래 _read_suffix() 가 실제 소스에서 읽어오고,
# 못 읽었을 때만 이 값으로 떨어진다 — 소스가 바뀌면 점검도 따라간다.
FALLBACK_SUFFIX = ", no text, no letters, no watermark"

# 접미사를 붙이는 곳들. 판정이 ❌ 로 나오면 여기를 손봐야 한다.
CALL_SITES = (
    "pipeline/thumbnail.py:40        (TECH)",
    "pipeline/cover_short.py:37      (TECH)",
    "pipeline/scp_shorts_render.py:446",
    "pipeline/novel_render.py:245",
    "pipeline/story_render.py:509",
)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_suffix() -> tuple[str, str]:
    """pipeline/thumbnail.py 의 TECH 에서 'no text…' 꼬리를 실제로 읽어온다.

    반환 (접미사, 출처설명). 못 읽으면 FALLBACK_SUFFIX 를 쓴다.
    """
    path = os.path.join(_repo_root(), "pipeline", "thumbnail.py")
    try:
        with open(path, encoding="utf-8") as fp:
            src = fp.read()
    except OSError:
        return FALLBACK_SUFFIX, "소스를 못 읽어 기본값 사용"
    m = re.search(r'^TECH\s*=\s*"([^"]*)"', src, re.M)
    if not m:
        return FALLBACK_SUFFIX, "TECH 를 못 찾아 기본값 사용"
    tail = re.search(r"(,\s*no text.*)$", m.group(1))
    if not tail:
        return FALLBACK_SUFFIX, "TECH 에 'no text' 가 없어 기본값 사용"
    return tail.group(1), "pipeline/thumbnail.py 의 TECH 에서 읽음"


# ── 게이트웨이 호출 (stdlib 만) ──────────────────────────────────────────────
def _headers() -> dict:
    tok = os.environ.get("WBSPARK_TOKEN")
    h = {"Content-Type": "application/json; charset=utf-8"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def _post(url: str, body: dict, timeout: int = 40) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def run_case(base: str, label: str, prompt: str, no_llm: bool,
             timeout: int) -> dict | None:
    """한 건 제출 → 완료까지 폴링 → {'model','elapsed'} 반환. 실패하면 None."""
    body: dict = {"type": "image", "prompt": prompt}
    if no_llm:
        body["no_llm"] = True

    print(f"\n── {label}")
    print(f"   프롬프트: {prompt}")
    print(f"   no_llm={str(no_llm).lower()}")
    try:
        job = _post(f"{base}/jobs", body)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"   ❌ 제출 실패: {e}")
        return None
    job_id = job.get("job_id")
    if not job_id:
        print(f"   ❌ job_id 없음: {job}")
        return None
    print(f"   job_id={job_id}")

    t0, last = time.time(), ""
    while time.time() - t0 < timeout:
        time.sleep(5)
        try:
            s = _get(f"{base}/jobs/{job_id}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"   · 폴링 예외(계속): {e}")
            continue
        st = s.get("status", "?")
        if st != last:
            print(f"   [+{int(time.time() - t0)}s] status={st}")
            last = st
        if st == "done":
            model = s.get("model") or ""
            elapsed = s.get("elapsed")
            print(f"   ✅ 완료 — 서버측 {elapsed}초 / 모델 {model or '(서버가 안 알려줌)'}")
            return {"model": model, "elapsed": elapsed}
        if st in ("error", "failed"):
            print(f"   ❌ 생성 실패: {s}")
            return None
    print(f"   ⚠️ {timeout}초 내 완료 안 됨 (마지막 status={last or '무응답'})")
    return None


# ── 판정 ────────────────────────────────────────────────────────────────────
def verdict(plain: dict | None, suffixed: dict | None) -> int:
    """0=문제없음 / 1=확정 또는 요주의 / 2=판정불가."""
    print("\n" + "=" * 66)
    print("판정")
    print("=" * 66)
    if not plain or not suffixed:
        print("  ⚠️ 판정 불가 — 두 건 중 하나가 완료되지 않았습니다.")
        print("     게이트웨이가 살아 있는지 먼저 보세요:  curl -s <BASE>/health")
        return 2

    a, b = plain["model"], suffixed["model"]
    print(f"  접미사 없음 → {a or '?'}   ({plain['elapsed']}초)")
    print(f"  접미사 있음 → {b or '?'}   ({suffixed['elapsed']}초)")
    print("")

    if not a or not b:
        print("  ⚠️ 판정 불가 — 서버가 model 필드를 안 돌려줍니다.")
        print("     게이트웨이가 응답에 model 을 싣도록 해야 이 점검이 됩니다.")
        return 2

    if a != b:
        print(f"  ❌ 확정 — 접미사 때문에 모델이 '{a}' 에서 '{b}' 로 바뀝니다.")
        print("     글자를 넣지 말라고 쓴 문장이 글자 모델을 부르고 있습니다.")
        print("     → wbSpark 로 갈 때만 이 접미사를 빼거나 표현을 바꾸면 됩니다.")
        print("        (FLUX 는 이 접미사가 실제로 필요하므로 백엔드별로 갈라야 합니다)")
        print("     손볼 곳:")
        for s in CALL_SITES:
            print(f"       · {s}")
        return 1

    if "qwen" in a.lower():
        print("  ⚠️ 요주의 — 접미사와 무관하게 두 건 다 Qwen-Image 로 갑니다.")
        print("     접미사가 원인은 아니지만, 30GB 모델이 상시로 도는 건 그대로입니다.")
        print("     서버 기본 라우팅을 확인하세요.")
        return 1

    print("  ✅ 문제 없음 — 접미사가 붙어도 같은 모델로 갑니다.")
    print("     needs_text 가 부정형을 걸러내고 있습니다. 파이프라인 수정 불필요.")
    return 0


def main() -> int:
    suffix, origin = _read_suffix()
    ap = argparse.ArgumentParser(
        description="wbSpark 라우팅 점검 — 'no text' 접미사가 모델을 바꾸는지 확인",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=os.environ.get("WBSPARK_BASE", DEFAULT_BASE),
                    help=f"게이트웨이 주소 (기본 {DEFAULT_BASE})")
    ap.add_argument("--prompt", default=BASE_PROMPT, help="기준 그림 프롬프트")
    ap.add_argument("--suffix", default=suffix, help=f"검사할 접미사 (기본: {origin})")
    ap.add_argument("--timeout", type=int, default=300, help="건당 대기 상한 초 (기본 300)")
    ap.add_argument("--with-llm", action="store_true",
                    help="LLM 보정을 켠 실제 프로덕션 경로도 이어서 잰다")
    ap.add_argument("--dry-run", action="store_true",
                    help="서버를 부르지 않고 무엇을 보낼지만 출력")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    plain_p = args.prompt
    suffixed_p = args.prompt + args.suffix

    print("=" * 66)
    print("wbSpark 라우팅 점검")
    print("=" * 66)
    print(f"  게이트웨이 : {base}")
    print(f"  접미사     : {args.suffix!r}")
    print(f"               ({origin})")

    if args.dry_run:
        print("\n[dry-run] 아래 두 건을 보낼 예정입니다 (실제로는 안 보냄):\n")
        for lbl, p in (("접미사 없음", plain_p), ("접미사 있음", suffixed_p)):
            print(f"  {lbl}")
            print("   " + json.dumps({"type": "image", "prompt": p, "no_llm": True},
                                     ensure_ascii=False))
        if args.with_llm:
            print("\n  --with-llm: 위 두 건을 no_llm 없이 한 번 더 보냅니다.")
        return 0

    # 게이트웨이가 살아 있는지 먼저 — 죽어 있으면 뒤가 전부 의미 없다.
    try:
        h = _get(f"{base}/health", timeout=20)
        print(f"  /health    : {json.dumps(h, ensure_ascii=False)}")
        q = h.get("queued")
        if isinstance(q, int) and q > 0:
            print(f"  ⚠️ 대기열 {q}건 — GPU 직렬 레인에서 그 뒤에 줄을 섭니다.")
            print("     (시간만 길어질 뿐 어느 모델로 갔는지는 그대로 유효합니다)")
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"\n❌ 게이트웨이 무응답: {e}")
        print("   사내망/VPN 연결과 주소를 확인하세요.")
        return 2

    print("\n[1/2] " + "-" * 58)
    plain = run_case(base, "접미사 없음 (프로브와 같은 조건 = 기준선)",
                     plain_p, True, args.timeout)
    print("\n[2/2] " + "-" * 58)
    suffixed = run_case(base, "접미사 있음 (프로덕션과 같은 조건)",
                        suffixed_p, True, args.timeout)
    rc = verdict(plain, suffixed)

    if args.with_llm:
        print("\n" + "=" * 66)
        print("추가 — LLM 보정을 켠 실제 경로")
        print("=" * 66)
        print("  needs_text 는 LLM 이 재작성한 enhanced_prompt 도 검사한다.")
        print("  즉 원문이 깨끗해도 LLM 출력에 글자 낱말이 섞이면 Qwen 으로 샐 수 있다.")
        lp = run_case(base, "LLM 켬 · 접미사 없음", plain_p, False, args.timeout)
        ls = run_case(base, "LLM 켬 · 접미사 있음", suffixed_p, False, args.timeout)
        print("\n  요약")
        for lbl, r in (("LLM 켬 · 접미사 없음", lp), ("LLM 켬 · 접미사 있음", ls)):
            print(f"    {lbl} → {(r or {}).get('model') or '실패'}")
        print("\n  ※ 같은 조건을 여러 번 돌렸을 때 결과가 흔들리면 그 자체가 발견이다")
        print("     — LLM 출력에 따라 라우팅이 갈린다는 뜻이니까.")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
