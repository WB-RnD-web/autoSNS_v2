#!/usr/bin/env python3
"""SCP 롱폼 켄번즈 + 오버레이 회귀 테스트.

    python pipeline/test_scp_overlay.py

앞부분은 문자열/로직 검사라 ffmpeg 없이 돈다.
맨 끝 렌더 스모크는 zoompan·xfade·subtitles 필터가 있을 때만 실행한다.
"""
from __future__ import annotations
import importlib
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_render as SR   # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def load(**env):
    for k, v in env.items():
        os.environ[k] = v
    import scp_render
    return importlib.reload(scp_render)


print("── 1. 켄번즈 on/off 로 필터가 갈린다 ──")
R = load(SCP_KENBURNS="0")
vf = R.scene_vf(0, 300)
ck("off 면 zoompan 없음", "zoompan" not in vf and vf.startswith("fps="), vf)
ck("off 면 preset=ultrafast + stillimage", R.PRESET == "ultrafast" and R._tune() == ["-tune", "stillimage"],
   f"{R.PRESET} {R._tune()}")

R = load(SCP_KENBURNS="1")
ck("on 이면 preset=veryfast + 튠 없음", R.PRESET == "veryfast" and R._tune() == [],
   f"{R.PRESET} {R._tune()}")
ck("on 이면 업스케일 후 zoompan",
   all(t in R.scene_vf(0, 300) for t in (f"scale={R.KB_SRC_W}", "zoompan", "s=1920x1080")))
ck("프레임 1장이면 켄번즈 스킵(0 나눗셈 방지)", "zoompan" not in R.scene_vf(0, 1))

print("\n── 2. 4가지 움직임을 돌려 쓴다 ──")
vfs = [R.scene_vf(i, 300) for i in range(8)]
ck("0/4, 1/5 … 가 같다(주기 4)", vfs[0] == vfs[4] and vfs[1] == vfs[5])
ck("줌인/줌아웃이 섞인다", vfs[0] != vfs[1])
ck("팬 있는 것과 없는 것이 섞인다",
   ("iw*0.03" in vfs[2]) and ("iw*0.03" not in vfs[0]))
ck("팬 방향이 반대", ("+(iw*0.03)" in vfs[2]) and ("-(iw*0.03)" in vfs[3]))

print("\n── 3. 색 변환(ASS 는 BGR) ──")
for hexc, want in [("#D9534F", "&H004F53D9"), ("#5FBF7A", "&H007ABF5F"),
                   ("#E0A93B", "&H003BA9E0"), ("깨진값", "&H003BA9E0")]:
    got = R._ass_bgr(hexc)
    ck(f"{hexc} → {got}", got == want, f"기대 {want}")

print("\n── 4. augment_ass ──")
segs = [{"text": f"{i}번째 문장입니다."} for i in range(12)]
segs[3]["text"] = "절단면 조도는 0.2나노미터였습니다."
segs[9]["text"] = "반사면 폭은 1,140킬로미터였습니다."
spans = [(i * 10.0, i * 10.0 + 9.4) for i in range(12)]
spec = {"scp_number": "SCP-9412", "object_class": "Keter",
        "emphasis": ["0.2나노미터", "1,140킬로미터", "본문에없는말"]}

with tempfile.TemporaryDirectory() as td:
    fontsdir, font = SR.resolve_font(td)
    ass = os.path.join(td, "c.ass")
    SR.build_ass(segs, spans, font, ass)
    n = R.augment_ass(ass, spec, segs, spans, font)
    body = open(ass, encoding="utf-8").read()
    ck("이벤트 3개(라벨1 + 강조2)", n == 3, f"n={n}")
    ck("Tag·Punch 스타일 추가", "Style: Tag," in body and "Style: Punch," in body)
    ck("스타일이 [Events] ★앞에 있다",
       body.index("Style: Punch,") < body.index("[Events]"))
    ck("라벨에 번호+등급", "SCP-9412" in body and "KETER" in body)
    ck("등급색이 케테르 적색", R._ass_bgr("#D9534F") in body)
    ck("박스가 불투명(알파 00)", "&H00120E0A" in body, "반투명이면 색 전환부가 겹쳐 진해진다")
    ck("강조가 해당 세그먼트 시각에", "0:00:30.25" in body and "0:01:30.25" in body)
    ck("본문에 없는 강조는 버린다", "본문에없는말" not in body)

    # 강조가 몰리면 걸러낸다 — 채택된 것들은 ★항상 20초 이상 떨어져 있어야 한다
    spec2 = dict(spec, emphasis=[f"{i}번째" for i in range(12)])
    ass2 = os.path.join(td, "c2.ass")
    SR.build_ass(segs, spans, font, ass2)
    R.augment_ass(ass2, spec2, segs, spans, font)
    b2 = open(ass2, encoding="utf-8").read()
    import re as _re
    ts = [_re.match(r"Dialogue: \d+,(\d):(\d\d):(\d\d)\.(\d\d)", ln).groups()
          for ln in b2.splitlines() if ",Punch," in ln]
    secs = [int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100 for h, m, s, cs in ts]
    gaps = [round(secs[i] - secs[i - 1], 2) for i in range(1, len(secs))]
    ck(f"상한 {R.PUNCH_MAX}개 이하로 채택({len(secs)}개)", len(secs) <= R.PUNCH_MAX)
    ck(f"채택분 간격이 전부 20초 이상 {gaps}", all(g >= 20.0 for g in gaps))

    # TAG_MODE
    R2 = load(SCP_KENBURNS="1", SCP_TAG_MODE="off")
    ass3 = os.path.join(td, "c3.ass")
    SR.build_ass(segs, spans, font, ass3)
    R2.augment_ass(ass3, {"scp_number": "X", "object_class": "Safe"}, segs, spans, font)
    ck("TAG_MODE=off 면 라벨 없음", ",Tag," not in open(ass3, encoding="utf-8").read())

print("\n── 5. 렌더 스모크(ffmpeg 필터 있을 때만) ──")
R = load(SCP_KENBURNS="1", SCP_TAG_MODE="intro", SCP_MIN_SCENE_SEC="4", SCP_FPS="10")
try:
    have = subprocess.run([SR.FFMPEG, "-hide_banner", "-filters"],
                          capture_output=True, text=True, timeout=30).stdout
except Exception:  # noqa: BLE001
    have = ""
need = ("zoompan", "xfade", "subtitles")
if not all(f" {f} " in have for f in need):
    print(f"  · 스킵 — {need} 중 없는 필터가 있다")
else:
    with tempfile.TemporaryDirectory() as td:
        imgs = []
        for i in range(3):
            p = os.path.join(td, f"i{i}.png")
            SR.sh([SR.FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=0x{30 + i * 40:02x}3040:s=1920x1080",
                   "-vf", "drawgrid=w=60:h=60:t=2:c=white@0.5", "-frames:v", "1", p])
            imgs.append(p)
        aud = os.path.join(td, "a.m4a")
        SR.sh([SR.FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
               "-t", "15", "-c:a", "aac", "-b:a", "64k", aud])
        fontsdir, font = SR.resolve_font(td)
        ass = os.path.join(td, "c.ass")
        sg = [{"text": f"문장 {i}. 0.2나노미터."} for i in range(3)]
        sp = [(i * 5.0, i * 5.0 + 4.6) for i in range(3)]
        SR.build_ass(sg, sp, font, ass)
        R.augment_ass(ass, {"scp_number": "SCP-1", "object_class": "Safe",
                            "emphasis": ["0.2나노미터"]}, sg, sp, font)
        out = os.path.join(td, "o.mp4")
        R.render_video(imgs, aud, ass, fontsdir, out, 15.0)
        ck("mp4 생성", os.path.exists(out) and os.path.getsize(out) > 20_000)
        # 실제로 움직이는가 — 연속 프레임 차이
        raw = os.path.join(td, "f%02d.png")
        SR.sh([SR.FFMPEG, "-y", "-i", out, "-vf",
               "select='between(n,10,13)',scale=320:-1", "-vsync", "0", raw])
        try:
            from PIL import Image
            import numpy as np
            fr = [np.asarray(Image.open(os.path.join(td, f"f{i:02d}.png")).convert("L"), dtype=float)
                  for i in range(1, 5)]
            diffs = [abs(fr[i] - fr[i - 1]).mean() for i in range(1, len(fr))]
            ck(f"연속 프레임이 실제로 변한다(평균차 {max(diffs):.2f})", max(diffs) > 0.5,
               "0 이면 켄번즈가 안 걸린 것")
        except ImportError:
            print("  · 픽셀 비교 스킵 — PIL/numpy 없음")

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
