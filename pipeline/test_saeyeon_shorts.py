#!/usr/bin/env python3
"""사연 쇼츠(saeyeon_shorts) 회귀 테스트 — 오프라인.

    python pipeline/test_saeyeon_shorts.py
"""
from __future__ import annotations
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import saeyeon_shorts as S  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


data = S.load()
print("── 대본")
bad = S.problems(data)
ck(f"14편 대본 검사 통과(제목·자막 길이·배역·목소리·영상 장면 ≤{S.MOVE_MAX}·폰 없음)", not bad, bad[:5])
ck("2주 분량(14편)", len(data["stories"]) == 14, len(data["stories"]))
for s in data["stories"]:
    p = [S.prompt(data, s, sc) for sc in s["scenes"]]
    if not all(x.startswith(data["style"]) for x in p):
        ck(f"[{s['id']}] 그림 지시는 공통 화풍으로 시작", False, p[0][:60])
ck("공통 화풍에 '폰'·'candid' 없음(폰 든 손이 생겼다)",
   not any(w in data["style"].lower() for w in ("phone", "candid")), data["style"])
broken = dict(data, stories=[dict(data["stories"][0], scenes=[dict(data["stories"][0]["scenes"][0],
                                                                      shot="{nobody} holding a phone")]
                                  + data["stories"][0]["scenes"][1:])])
ck("검사가 없는 배역·폰을 잡는다", any("배역" in b for b in S.problems(broken)))
broken2 = dict(data, stories=[dict(data["stories"][0], scenes=[dict(sc, move="camera pans fast")
                                                                for sc in data["stories"][0]["scenes"]])])
ck("검사가 영상 장면 수·흔들리는 지시를 잡는다",
   any("영상 장면" in b for b in S.problems(broken2)) and any("static camera" in b for b in S.problems(broken2)))

print("── 다음 편 고르기(두 번 안 올리기)")
ck("처음엔 1편", S.due(data, {}) == 1)
ck("ledger 에 1·2 → 3편", S.due(data, {"1": {}, "2": {}}) == 3)
ck("채널 표식도 본다(캐시가 날아가도)", S.due(data, {"1": {}}, {"사연 S002", "사연 S003"}) == 4)
ck("14편 다 올리면 할 일 없음(시험이 저절로 끝난다)",
   S.due(data, {str(i): {} for i in range(1, 15)}) is None)
ck("표식 형식", S.mark(7) == "사연 S007" and re.fullmatch(r"사연 S\d{3}", S.mark(14)))

print("── 메타")
for s in data["stories"]:
    m = S.meta(s)
    if not (len(m["title"]) <= 100 and S.mark(s["id"]) in m["description"] and "창작" in m["description"]
            and "AI" in m["description"]):
        ck(f"[{s['id']}] 제목 100자·설명에 표식·창작·AI 고지", False, m["title"])
ck("설명에 표식·창작·AI 고지(14편 전부)", True)
ck("업로드는 합성 콘텐츠 표시(synthetic=True)",
   "synthetic=True" in open(S.__file__, encoding="utf-8").read())

print("── 화면")
ck("늘이지 않는다(비율 유지 후 자르기)", "force_original_aspect_ratio=increase" in S._fit(W := S.W, S.H) and "crop" in S._fit(W, S.H))
vf = S.video_filter(4.0, S.VIDEO_CUT)
ck("영상 장면: 앞부분 → 마지막 프레임 줌 → 자막", "trim=0:1.9" in vf and "zoompan" in vf and "concat=n=2" in vf
   and vf.endswith("[v]"), vf)
ck("사진 장면: 줌 + 자막", "zoompan" in S.still_filter(3.0, True) and "overlay" in S.still_filter(3.0, False))
try:
    S.font(40)
    has_font = True
except SystemExit:
    has_font = False
if has_font:
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        p = S.overlay(data["stories"][0]["top"], data["stories"][0]["scenes"][2]["sub"], os.path.join(d, "o.png"))
        im = Image.open(p)
        a = im.getchannel("A")
        ck("오버레이 1080x1920", im.size == (S.W, S.H), im.size)
        ck("위 제목이 그려진다(위 560px 안)", a.crop((0, 150, S.W, 420)).getextrema()[1] == 255)
        ck("자막은 오른쪽 버튼 열(x>960)·아래 설명(y>1440)을 피한다",
           a.crop((962, 600, S.W, S.H)).getextrema()[1] == 0 and a.crop((0, 1440, S.W, S.H)).getextrema()[1] == 0)
        long = S.overlay(["가" * 12, "나" * 12], "가나다라마바사아자차카타파하 가나다라마", os.path.join(d, "l.png"))
        la = Image.open(long).getchannel("A")
        ck("긴 제목·자막도 화면 밖으로 안 나간다",
           la.crop((0, 0, 30, 560)).getextrema()[1] < 255 and la.crop((962, 600, S.W, S.H)).getextrema()[1] == 0)
else:
    print("  (글꼴 없음 — 오버레이 그림 검사 생략)")

print("── 워크플로")
wf = open(os.path.join(S.ROOT, ".github", "workflows", "saeyeon-shorts.yml"), encoding="utf-8").read()
ck("읽기 권한만 · 코드는 main 에서", "contents: read" in wf and "contents: write" not in wf and "ref: main" in wf)
ck("하루 한 번(13:07 KST) + 수동", re.findall(r'cron:\s*"([^"]+)"', wf) == ["7 4 * * *"] and "workflow_dispatch:" in wf)
ck("push 트리거 없음(루틴 브랜치에 깨지 않는다)", not re.search(r"(?m)^\s*push:", wf))
ck("ledger 는 잡이 실패해도 저장", "if: always() && hashFiles('output/saeyeon_shorts_ledger.json')" in wf)
ck("업로드 전에 오프라인 테스트", wf.index("test_saeyeon_shorts.py") < wf.index("saeyeon_shorts.py upload"))
ck("영상 끄는 스위치(레포 변수 SAEYEON_VIDEO)", "SAEYEON_VIDEO:" in wf and 'os.environ.get("SAEYEON_VIDEO", "1")' in
   open(S.__file__, encoding="utf-8").read())

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
