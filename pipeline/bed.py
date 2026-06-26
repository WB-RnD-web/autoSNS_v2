#!/usr/bin/env python3
"""HyperFrames 모션 베드 생성·렌더 (v2 신규 = 비주얼 레이어).

투샷 이미지 1장을 받아 샷별로 애니메이션 mp4(자막·음성 없는 순수 베드)를 렌더한다.
화자(별하=우/별이=좌)에 따라 켄번즈 기준점·드리프트·스포트라이트를 분기하고,
하단의 구워진 배너는 상단기준 줌 + 잉크 lower-third 밴드로 차단한다.

자막/음성은 베드에 넣지 않는다(assemble.py가 v1 방식대로 얹음).
"""
from __future__ import annotations
import os
import shutil
import subprocess

# 화자/길이 파라미터 베드 템플릿 (토큰 치환)
BED_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
html, body { margin:0; width:1080px; height:1920px; overflow:hidden; background:#0A0808; }
#frame, #sway { position:absolute; inset:0; }
#sway { transform-origin:50% 60%; }
#kb {
  position:absolute; inset:0;
  background-image:url("assets/twoshot.png");
  background-size:cover; background-position:center top;
  transform-origin:__ORIGINX__% 12%;
  will-change:transform;
}
#spotlight {
  position:absolute; __SPOTSIDE__: 40px; top:560px;
  width:560px; height:760px; border-radius:50%;
  background:radial-gradient(circle, rgba(217,119,87,0.40) 0%, rgba(217,119,87,0) 62%);
  filter:blur(22px); mix-blend-mode:screen;
}
#grade {
  position:absolute; inset:0; pointer-events:none;
  background:
    radial-gradient(70% 50% at __SPOTX__% 50%, rgba(217,119,87,0.10) 0%, rgba(217,119,87,0) 60%),
    radial-gradient(120% 90% at 50% 42%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%);
}
#lowerband {
  position:absolute; left:0; right:0; bottom:0; height:480px; pointer-events:none;
  background:linear-gradient(180deg, rgba(10,8,8,0) 0%, rgba(10,8,8,0.85) 40%, #0A0808 72%, #0A0808 100%);
}
#grain {
  position:absolute; inset:-50%; width:200%; height:200%; opacity:0.07; pointer-events:none;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="__DUR__" data-width="1080" data-height="1920">
  <div id="frame" class="clip" data-start="0" data-duration="__DUR__" data-track-index="0">
    <div id="sway"><div id="kb"></div></div>
  </div>
  <div id="spotlight" class="clip" data-start="0" data-duration="__DUR__" data-track-index="1"></div>
  <div id="grade" class="clip" data-start="0" data-duration="__DUR__" data-track-index="2"></div>
  <div id="lowerband" class="clip" data-start="0" data-duration="__DUR__" data-track-index="3"></div>
  <div id="grain" class="clip" data-start="0" data-duration="__DUR__" data-track-index="4"></div>
</div>
<script>
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused:true });
const D = __DUR__;
tl.fromTo("#kb", { scale:1.40, xPercent:__KBX0__, yPercent:0 },
                 { scale:1.54, xPercent:__KBX1__, yPercent:1.2, duration:D, ease:"none" }, 0);
const swayCycle = 2.3;
tl.fromTo("#sway", { rotation:-0.4 },
  { rotation:0.4, duration:swayCycle/2, ease:"sine.inOut", yoyo:true,
    repeat: Math.max(0, Math.floor(D/swayCycle)-1) }, 0);
tl.from("#frame", { opacity:0, duration:0.5, ease:"power2.out" }, 0);
tl.fromTo("#spotlight", { opacity:0 }, { opacity:0.85, duration:0.6, ease:"power2.out" }, 0.3);
const spotCycle = 1.5;
tl.to("#spotlight", { opacity:0.45, scale:1.06, duration:spotCycle/2, ease:"sine.inOut",
  yoyo:true, repeat: Math.max(0, Math.floor((D-0.9)/spotCycle)-1),
  transformOrigin:"__SPOTX__% 55%" }, 0.9);
window.__timelines["main"] = tl;
</script></body></html>
"""


def bed_html(dur: float, speaker: str) -> str:
    """화자/길이에 맞춘 베드 HTML 생성."""
    right = (speaker == "별하")
    repl = {
        "__DUR__": f"{dur:.2f}",
        "__ORIGINX__": "68" if right else "32",
        "__SPOTSIDE__": "right" if right else "left",
        "__SPOTX__": "75" if right else "25",
        "__KBX0__": "1.5" if right else "-1.5",
        "__KBX1__": "-2.5" if right else "2.5",
    }
    html = BED_TEMPLATE
    for k, v in repl.items():
        html = html.replace(k, v)
    return html


def render_bed(html: str, bedproj: str, out_mp4: str, quality: str = "standard") -> None:
    """베드 HTML을 bedproj/index.html로 쓰고 hyperframes render로 mp4 생성."""
    with open(os.path.join(bedproj, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
    # npx는 shell 경유(Windows npx.cmd 해석). PATH는 호출측에서 ffmpeg 포함 보장.
    cmd = f'npx --yes hyperframes@0.7.9 render --quality {quality} --output "{out_mp4}"'
    r = subprocess.run(cmd, cwd=bedproj, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"bed render 실패 (rc={r.returncode})\n"
                           f"{(r.stdout or '')[-1500:]}\n{(r.stderr or '')[-1500:]}")


def ensure_twoshot(bedproj: str, twoshot_src: str) -> None:
    """투샷 이미지를 bedproj/assets/twoshot.png 로 배치."""
    dst_dir = os.path.join(bedproj, "assets")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copyfile(twoshot_src, os.path.join(dst_dir, "twoshot.png"))
