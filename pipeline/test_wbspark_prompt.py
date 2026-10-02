#!/usr/bin/env python3
"""wbspark.strip_text_negatives · image_body 회귀 테스트.

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

print("── 이미지 크기(no_llm 이면 서버가 aspect 를 무시한다)")
for asp, wide in (("9:16", False), ("16:9", True), ("1:1", None)):
    b = W.image_body("x", aspect=asp, no_llm=True)
    w, h = b.get("width"), b.get("height")
    ok = bool(w and h) and w % 64 == 0 and h % 64 == 0 and (w == h if wide is None else (w > h) == wide)
    ck(f"{asp}: 크기를 직접 보낸다({w}x{h})", ok and b["aspect"] == asp and b["no_llm"] is True, b)
ck("9:16 은 화면 비율(0.5625)에 가깝다", abs(768 / 1344 - 9 / 16) < 0.02)
b = W.image_body("a cat, no text, no letters")
ck("aspect 없으면 크기도 안 보낸다(서버 기본)", "width" not in b and "aspect" not in b and "no_llm" not in b, b)
ck("프롬프트는 글자 부정형을 뺀 채로 간다", b["prompt"] == "a cat", b)
ck("모델 고정은 그대로", W.image_body("x", model="z-image-turbo", aspect="9:16")["model"] == "z-image-turbo")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
