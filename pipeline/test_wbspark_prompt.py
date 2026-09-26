#!/usr/bin/env python3
"""wbspark.strip_text_negatives 회귀 테스트.

    python pipeline/test_wbspark_prompt.py

'no text, no letters' 가 붙으면 게이트웨이가 z-image-turbo(80초) 대신 qwen-image(198초)로
보낸다(2026-09-27 tools/wbspark_route_check.py 실측). 그 부정형만 지우고 나머지는 지키는지 본다.
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wbspark as W  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


TEXT_WORDS = ("text", "letter", "watermark", "typography", "caption", "logo", "title", "word")

cover = ("A misty DMZ fence at dusk, no people, no faces, no text. modern editorial news key visual, "
         "9:16 vertical composition, poster key art, subject in upper two-thirds, highly detailed, "
         "no text, no letters, no watermark")
out = W.strip_text_negatives(cover)
ck("커버 접미사의 글자 낱말이 전부 빠진다", not any(w in out.lower() for w in TEXT_WORDS), out)
ck("글자와 무관한 부정형(no people, no faces)은 남는다", "no people" in out and "no faces" in out, out)
ck("장면 묘사는 그대로", out.startswith("A misty DMZ fence at dusk") and "highly detailed" in out, out)

hook = "golden rabbit emblem, no human face, no text, no letters, vertical 9:16 composition"
ck("루틴 thumbnail_hook 안의 no text 도 빠진다",
   W.strip_text_negatives(hook) == "golden rabbit emblem, no human face, vertical 9:16 composition",
   W.strip_text_negatives(hook))
ck("'no text in image' 형태도 빠진다",
   "text" not in W.strip_text_negatives("landmark; no text in image, no real person"))
ck("글자를 ★원하는 프롬프트는 건드리지 않는다",
   W.strip_text_negatives("a neon sign reading OPEN") == "a neon sign reading OPEN")
ck("빈 쉼표가 남지 않는다", ", ," not in out and not out.endswith(","), out)

os.environ["WBSPARK_KEEP_NEGATIVES"] = "1"
ck("WBSPARK_KEEP_NEGATIVES=1 이면 원문 그대로", W.strip_text_negatives(cover) == cover)
del os.environ["WBSPARK_KEEP_NEGATIVES"]

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
