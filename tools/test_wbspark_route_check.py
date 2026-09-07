#!/usr/bin/env python3
"""wbspark_route_check 검증 — 판정 분기와 접미사 읽기.

이 도구는 사람이 보고 판단을 내리는 물건이라, 판정이 틀리면 잘못된 곳을 고치게 된다.
네 갈래(확정 / 요주의 / 정상 / 판정불가)를 전부 눌러본다.

실행: python tools/test_wbspark_route_check.py
"""
import io
import os
import sys
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wbspark_route_check as W  # noqa: E402

FAIL = []


def check(name, cond, got=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {got}" if got else ""))
    if not cond:
        FAIL.append(name)


def verdict_of(plain, suffixed):
    """verdict() 를 조용히 돌려 (종료코드, 출력) 반환."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = W.verdict(plain, suffixed)
    return rc, buf.getvalue()


print("── ① 판정 분기 ──")

rc, out = verdict_of({"model": "z-image", "elapsed": 21},
                     {"model": "qwen-image", "elapsed": 79})
check("모델이 갈리면 확정(rc=1)", rc == 1, f"rc={rc}")
check("확정일 때 손볼 곳을 알려준다", "pipeline/thumbnail.py" in out)
check("확정일 때 FLUX 는 접미사가 필요하다고 경고", "FLUX" in out)

rc, out = verdict_of({"model": "qwen-image", "elapsed": 80},
                     {"model": "qwen-image", "elapsed": 79})
check("둘 다 qwen 이면 요주의(rc=1)", rc == 1, f"rc={rc}")
check("요주의는 접미사 탓이 아니라고 말한다", "접미사가 원인은 아니" in out)

rc, out = verdict_of({"model": "z-image", "elapsed": 21},
                     {"model": "z-image", "elapsed": 22})
check("둘 다 z-image 면 정상(rc=0)", rc == 0, f"rc={rc}")
check("정상이면 수정 불필요라고 말한다", "수정 불필요" in out)

rc, _ = verdict_of(None, {"model": "z-image", "elapsed": 22})
check("한 건이 실패하면 판정불가(rc=2)", rc == 2, f"rc={rc}")

rc, out = verdict_of({"model": "", "elapsed": 21}, {"model": "", "elapsed": 22})
check("model 이 비면 판정불가(rc=2)", rc == 2, f"rc={rc}")
check("판정불가 사유를 밝힌다", "model 필드를 안 돌려줍니다" in out)

# 판정은 '모르면 모른다' 고 말해야 한다 — 빈 값을 같다고 보고 ✅ 를 내면 최악이다.
check("빈 model 두 개를 '문제 없음' 으로 오판하지 않는다", rc != 0, f"rc={rc}")

print("\n── ② 접미사를 소스에서 읽는가 ──")
sfx, origin = W._read_suffix()
check("thumbnail.py 에서 읽어온다", "thumbnail.py" in origin, origin)
check("'no text' 로 시작하는 꼬리", sfx.lstrip(", ").startswith("no text"), repr(sfx))

# 진짜 TECH 와 글자까지 같아야 한다 — 여기가 어긋나면 엉뚱한 걸 재게 된다.
tech = ""
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "pipeline", "thumbnail.py"), encoding="utf-8") as fp:
    for line in fp:
        if line.startswith("TECH ="):
            tech = line
            break
check("실제 TECH 가 이 접미사로 끝난다", tech.rstrip().rstrip('"').endswith(sfx),
      repr(tech.strip()[:70]))

print("\n── ③ 호출 지점 목록이 실재하는가 ──")
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for site in W.CALL_SITES:
    path = site.split(":")[0].strip()
    check(f"{path} 있음", os.path.exists(os.path.join(root, path)))

print("\n── ④ dry-run 은 서버를 부르지 않는다 ──")


def _boom(*a, **k):
    raise AssertionError("dry-run 인데 네트워크를 불렀다")


W._post, W._get = _boom, _boom
argv = sys.argv[:]
sys.argv = ["x", "--dry-run"]
try:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = W.main()
    check("dry-run rc=0", rc == 0, f"rc={rc}")
    check("보낼 본문을 보여준다", '"no_llm": true' in buf.getvalue())
finally:
    sys.argv = argv

print("")
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: " + ", ".join(FAIL))
    raise SystemExit(1)
print("🎉 전부 통과")
