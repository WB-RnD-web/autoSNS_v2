#!/usr/bin/env python3
"""장면 스펙(JSON) → 모션그래픽 뉴스 쇼츠 mp4 (v2 핵심 렌더러).

흐름:
  ① 장면별 내레이션 → edge-tts(단일 내레이터) → 길이 측정
  ② 길이에 맞춰 장면 타이밍 산출
  ③ 타입별 템플릿(hook/stat/gauge/trend)으로 HyperFrames HTML 생성
  ④ hyperframes render → 무음 mp4
  ⑤ VO 트랙(장면 시작 정렬) 합성 → mux → 최종 mp4

장면 스펙 예: docs/samples/scene_spec_economy.json
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "motion")
W, H, FPS = 1080, 1920, 30
NARRATOR = os.environ.get("VO_VOICE", "ko-KR-SunHiNeural")
VO_RATE = os.environ.get("VO_RATE", "+6%")
PAD = 0.6        # 내레이션 뒤 여유
OVERLAP = 0.4    # 장면 전환 겹침
BRAND = {"ink": "#0A0808", "cream": "#EDD9BC", "coral": "#D97757", "red": "#E5484D"}


def _bin(name):
    p = shutil.which(name)
    if p:
        return p
    local = rf"C:\Users\zxczx\tools\ffmpeg-8.1.1-essentials_build\bin\{name}.exe"
    return local if os.path.exists(local) else name


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def sh(cmd, **kw):
    kw.setdefault("capture_output", True); kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"\n[cmd failed] {cmd}\n{(e.stdout or '')[-1000:]}\n{(e.stderr or '')[-1500:]}\n")
        raise


def probe_dur(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ── CSS (공통) ────────────────────────────────────────────
CSS = """
@font-face{font-family:"Pretendard";font-weight:400;src:url("assets/fonts/Pretendard-Regular.woff2") format("woff2");}
@font-face{font-family:"Pretendard";font-weight:700;src:url("assets/fonts/Pretendard-Bold.woff2") format("woff2");}
@font-face{font-family:"Pretendard";font-weight:800;src:url("assets/fonts/Pretendard-ExtraBold.woff2") format("woff2");}
*{margin:0;padding:0;box-sizing:border-box;}
html,body{width:1080px;height:1920px;overflow:hidden;background:#0A0808;font-family:"Pretendard",sans-serif;}
.scene{position:absolute;inset:0;overflow:hidden;background:#0A0808;}
.glow{position:absolute;border-radius:50%;filter:blur(90px);pointer-events:none;}
.grain{position:absolute;inset:-50%;width:200%;height:200%;opacity:.06;pointer-events:none;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");}
.ghost{position:absolute;font-weight:800;color:rgba(217,119,87,.07);font-size:520px;letter-spacing:-10px;white-space:nowrap;pointer-events:none;left:-60px;top:1040px;}
.pill{display:inline-flex;align-items:center;gap:16px;background:#D97757;color:#0A0808;font-weight:800;font-size:42px;letter-spacing:2px;padding:14px 34px;border-radius:999px;}
.pill .dot{width:18px;height:18px;border-radius:50%;background:#0A0808;}
.brand{position:absolute;bottom:70px;left:60px;color:rgba(237,217,188,.5);font-weight:700;font-size:36px;letter-spacing:3px;}
.wrap{position:absolute;left:80px;top:440px;width:920px;}
.label{color:#D97757;font-weight:800;font-size:48px;letter-spacing:1px;}
.sub{color:rgba(237,217,188,.7);font-weight:500;font-size:48px;margin-top:14px;}
.sub b{color:#EDD9BC;}
.h1{color:#EDD9BC;font-weight:800;font-size:130px;line-height:1.05;letter-spacing:-3px;}
.h1 .big{color:#D97757;font-size:230px;display:inline-block;}
.pillrow{position:absolute;left:80px;top:300px;}
.num{font-weight:800;font-size:300px;line-height:1;letter-spacing:-8px;color:#D97757;}
.barbase{position:absolute;right:120px;bottom:430px;width:120px;height:700px;border-radius:18px;background:rgba(237,217,188,.08);}
.bar{position:absolute;right:120px;bottom:430px;width:120px;height:0;border-radius:18px;background:linear-gradient(180deg,#D97757,#b85a3e);}
.track{position:absolute;left:80px;bottom:560px;width:920px;height:40px;border-radius:20px;background:rgba(237,217,188,.08);}
.fill{position:absolute;left:80px;bottom:560px;width:230px;height:40px;border-radius:20px;background:#D97757;transform-origin:left center;}
.trend svg{position:absolute;left:80px;bottom:500px;width:920px;height:360px;}
.closer{position:absolute;left:80px;bottom:300px;width:920px;color:#EDD9BC;font-weight:800;font-size:72px;line-height:1.1;opacity:0;}
.quote-mark{font-family:Georgia,serif;font-size:300px;color:#D97757;line-height:0.55;font-weight:800;}
.quote-text{color:#EDD9BC;font-weight:800;font-size:90px;line-height:1.25;margin-top:-20px;}
.quote-attr{color:rgba(237,217,188,.6);font-weight:600;font-size:44px;margin-top:34px;}
.kp{color:#EDD9BC;font-weight:700;font-size:68px;line-height:1.25;display:flex;align-items:flex-start;gap:26px;margin-top:30px;}
.kp .b{color:#D97757;font-weight:800;min-width:58px;}
.statement{color:#EDD9BC;font-weight:800;font-size:116px;line-height:1.12;letter-spacing:-2px;}
.statement .big{color:#D97757;}
#fade{position:absolute;inset:0;background:#0A0808;opacity:0;z-index:50;pointer-events:none;}
"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _allow_b(s):
    # <b>..</b> 만 허용
    return esc(s).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;br/&gt;", "<br/>")


# ── 장면 HTML ─────────────────────────────────────────────
def scene_html(i, sc):
    t = sc["type"]
    gid = f"s{i}"
    glow = f'<div class="glow" id="{gid}-glow" style="width:760px;height:760px;left:-160px;top:280px;background:radial-gradient(circle,{BRAND["coral"]},rgba(217,119,87,0));opacity:.45;"></div>'
    grain = '<div class="grain"></div>'
    brand = f'<div class="brand">{esc(sc.get("brand","일상공감뉴스"))}</div>'
    body = ""
    if t == "hook":
        lines = sc.get("lines", [])
        hl = sc.get("highlight", "")
        ghost = f'<div class="ghost" id="{gid}-ghost">{esc(sc.get("ghost",""))}</div>' if sc.get("ghost") else ""
        pill = f'<div class="pillrow"><span class="pill"><span class="dot"></span>{esc(sc.get("pill","BREAKING"))}</span></div>'
        lhtml = []
        for j, ln in enumerate(lines):
            txt = esc(ln)
            if hl and hl in ln:
                txt = txt.replace(esc(hl), f'<span class="big" id="{gid}-hl">{esc(hl)}</span>')
            lhtml.append(f'<div class="h1" id="{gid}-l{j}">{txt}</div>')
        body = ghost + pill + '<div class="wrap" style="top:560px">' + "".join(lhtml) + "</div>"
    elif t == "stat":
        bar = (f'<div class="barbase"></div><div class="bar" id="{gid}-bar"></div>') if sc.get("bar") else ""
        body = (bar + '<div class="wrap">'
                + f'<div class="label" id="{gid}-label">{esc(sc.get("label",""))}</div>'
                + f'<div class="num" id="{gid}-num" style="margin-top:18px;">{esc(sc.get("prefix",""))}0{esc(sc.get("suffix",""))}</div>'
                + f'<div class="sub" id="{gid}-sub">{_allow_b(sc.get("sub",""))}</div></div>')
    elif t == "gauge":
        body = (f'<div class="track"></div><div class="fill" id="{gid}-fill"></div>'
                + '<div class="wrap">'
                + f'<div class="label" id="{gid}-label">{esc(sc.get("label",""))}</div>'
                + f'<div style="margin-top:10px;"><span class="num" id="{gid}-num">{int(sc.get("from",1))}</span><span class="num" style="font-size:200px;">{esc(sc.get("unit","배"))}</span></div>'
                + f'<div class="sub" id="{gid}-sub">{_allow_b(sc.get("sub",""))}</div></div>')
    elif t == "trend":
        down = sc.get("dir", "down") == "down"
        col = BRAND["red"] if down else "#3FB950"
        path = "M0,40 L230,70 L460,55 L690,150 L920,320" if down else "M0,320 L230,250 L460,270 L690,120 L920,40"
        closer = f'<div class="closer" id="{gid}-closer">{_allow_b(sc.get("closer",""))}</div>' if sc.get("closer") else ""
        glow = glow.replace(BRAND["coral"], col).replace('opacity:.45', 'opacity:0').replace(f'id="{gid}-glow"', f'id="{gid}-glow" data-col="{col}"')
        body = ('<div class="wrap">'
                + f'<div class="label" id="{gid}-label" style="color:{col}">{esc(sc.get("label",""))}</div>'
                + f'<div class="num" id="{gid}-num" style="color:{col};margin-top:10px;">0{esc(sc.get("suffix","%"))}</div>'
                + f'<div class="sub" id="{gid}-sub">{_allow_b(sc.get("sub",""))}</div></div>'
                + f'<svg viewBox="0 0 920 360" preserveAspectRatio="none"><path id="{gid}-line" d="{path}" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                + closer)
    elif t == "quote":
        body = ('<div class="wrap" style="top:520px">'
                + f'<div class="quote-mark" id="{gid}-qm">&ldquo;</div>'
                + f'<div class="quote-text" id="{gid}-qt">{_allow_b(sc.get("text",""))}</div>'
                + f'<div class="quote-attr" id="{gid}-qa">{esc(sc.get("attr",""))}</div></div>')
    elif t == "keypoint":
        pts = "".join(f'<div class="kp" id="{gid}-kp{j}"><span class="b">{j+1}</span><span>{_allow_b(p)}</span></div>'
                      for j, p in enumerate(sc.get("points", [])))
        body = ('<div class="wrap" style="top:480px">'
                + f'<div class="label" id="{gid}-label">{esc(sc.get("label",""))}</div>'
                + pts + "</div>")
    elif t == "statement":
        txt = esc(sc.get("text", ""))
        hl = sc.get("highlight", "")
        if hl and hl in sc.get("text", ""):
            txt = txt.replace(esc(hl), f'<span class="big" id="{gid}-hl">{esc(hl)}</span>')
        body = (f'<div class="wrap" style="top:560px"><div class="statement" id="{gid}-st">{txt}</div></div>')
    cls = "scene clip trend" if t == "trend" else "scene clip"
    return (f'<div id="{gid}" class="{cls}" data-start="{sc["start"]:.2f}" '
            f'data-duration="{sc["clip"]:.2f}" data-track-index="{i}" style="z-index:{i+1}">'
            + glow + grain + body + brand + "</div>")


# ── 장면 JS(GSAP) ─────────────────────────────────────────
TRANSITIONS = ["fade", "pushup", "slideleft", "zoom"]


def scene_js(i, sc):
    gid, S = f"s{i}", sc["start"]
    out = []
    tr = "fade" if i == 0 else TRANSITIONS[1 + (i - 1) % 3]
    if tr == "fade":
        out.append(f'tl.fromTo("#{gid}",{{opacity:0,scale:1.08}},{{opacity:1,scale:1,duration:0.5,ease:"power2.out"}},{S:.2f});')
    elif tr == "pushup":
        out.append(f'tl.fromTo("#{gid}",{{yPercent:100}},{{yPercent:0,duration:0.45,ease:"power3.out"}},{S:.2f});')
    elif tr == "slideleft":
        out.append(f'tl.fromTo("#{gid}",{{xPercent:100}},{{xPercent:0,duration:0.45,ease:"power3.out"}},{S:.2f});')
    else:
        out.append(f'tl.fromTo("#{gid}",{{scale:1.25,opacity:0}},{{scale:1,opacity:1,duration:0.45,ease:"power3.out"}},{S:.2f});')
    out.append(f'tl.to("#{gid}-glow",{{scale:1.15,duration:2.3,ease:"sine.inOut",yoyo:true,repeat:1}},{S:.2f});')
    t = sc["type"]
    if t == "hook":
        if sc.get("ghost"):
            out.append(f'tl.to("#{gid}-ghost",{{x:-60,duration:{sc["clip"]:.2f},ease:"none"}},{S:.2f});')
        out.append(f'tl.from("#{gid} .pill",{{y:-40,opacity:0,duration:0.5,ease:"power3.out"}},{S+0.2:.2f});')
        for j in range(len(sc.get("lines", []))):
            out.append(f'tl.from("#{gid}-l{j}",{{y:60,opacity:0,duration:0.5,ease:"power3.out"}},{S+0.5+j*0.22:.2f});')
        if sc.get("highlight"):
            out.append(f'tl.fromTo("#{gid}-hl",{{scale:0.4,color:"{BRAND["cream"]}"}},{{scale:1,color:"{BRAND["coral"]}",duration:0.6,ease:"back.out(2)"}},{S+1.1:.2f});')
    elif t == "quote":
        out.append(f'tl.from("#{gid}-qm",{{scale:0.5,opacity:0,duration:0.6,ease:"back.out(1.6)"}},{S+0.4:.2f});')
        out.append(f'tl.from("#{gid}-qt",{{y:40,opacity:0,duration:0.6,ease:"power3.out"}},{S+0.6:.2f});')
        out.append(f'tl.from("#{gid}-qa",{{opacity:0,duration:0.5,ease:"power2.out"}},{S+1.1:.2f});')
    elif t == "keypoint":
        out.append(f'tl.from("#{gid}-label",{{x:-40,opacity:0,duration:0.5,ease:"power2.out"}},{S+0.4:.2f});')
        for j in range(len(sc.get("points", []))):
            out.append(f'tl.from("#{gid}-kp{j}",{{x:-30,opacity:0,duration:0.45,ease:"power2.out"}},{S+0.7+j*0.45:.2f});')
    elif t == "statement":
        out.append(f'tl.from("#{gid}-st",{{y:50,opacity:0,duration:0.6,ease:"power3.out"}},{S+0.4:.2f});')
        if sc.get("highlight"):
            out.append(f'tl.fromTo("#{gid}-hl",{{scale:0.5,color:"{BRAND["cream"]}"}},{{scale:1,color:"{BRAND["coral"]}",duration:0.6,ease:"back.out(2)"}},{S+0.9:.2f});')
    elif t in ("stat", "gauge", "trend"):
        out.append(f'tl.from("#{gid}-label",{{x:-40,opacity:0,duration:0.5,ease:"power2.out"}},{S+0.5:.2f});')
        out.append(f'tl.from("#{gid}-num",{{scale:0.6,opacity:0,duration:0.5,ease:"back.out(1.6)"}},{S+0.65:.2f});')
        cu = f'{S+0.75:.2f}'
        if t == "stat":
            pre, suf = sc.get("prefix", ""), sc.get("suffix", "")
            out.append(f'cu("#{gid}-num",{sc.get("from",0)},{sc.get("to",0)},{cu},1.4,v=>"{pre}"+Math.round(v)+"{suf}");')
            if sc.get("bar"):
                out.append(f'tl.fromTo("#{gid}-bar",{{height:0}},{{height:560,duration:1.4,ease:"power2.out"}},{cu});')
        elif t == "gauge":
            out.append(f'cu("#{gid}-num",{sc.get("from",1)},{sc.get("to",1)},{cu},1.3,v=>Math.round(v));')
            ratio = float(sc.get("to", 1)) / max(1e-6, float(sc.get("from", 1)))
            out.append(f'tl.fromTo("#{gid}-fill",{{scaleX:1}},{{scaleX:{ratio:.2f},duration:1.3,ease:"power2.out"}},{cu});')
        elif t == "trend":
            suf = sc.get("suffix", "%")
            out.append(f'cu("#{gid}-num",{sc.get("from",0)},{sc.get("to",0)},{cu},1.2,v=>Math.round(v)+"{suf}");')
            out.append(f'tl.to("#{gid}-glow",{{opacity:0.5,duration:0.6,ease:"power2.out"}},{cu});')
            out.append(f'tl.fromTo("#{gid}-line",{{strokeDashoffset:1200,strokeDasharray:1200}},{{strokeDashoffset:0,duration:1.4,ease:"power2.inOut"}},{S+0.7:.2f});')
        out.append(f'tl.from("#{gid}-sub",{{y:30,opacity:0,duration:0.5,ease:"power2.out"}},{S+1.6:.2f});')
        if t == "trend" and sc.get("closer"):
            out.append(f'tl.to("#{gid}-closer",{{opacity:1,y:-10,duration:0.6,ease:"power3.out"}},{S+4.3:.2f});')
    return "\n".join(out)


def build_html(scenes, total):
    parts = [scene_html(i, sc) for i, sc in enumerate(scenes)]
    js = "\n".join(scene_js(i, sc) for i, sc in enumerate(scenes))
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{CSS}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.2f}" data-width="1080" data-height="1920">
{''.join(parts)}
<div id="fade"></div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused:true }});
function cu(sel,from,to,t,dur,fmt){{const o={{v:from}},el=document.querySelector(sel);tl.to(o,{{v:to,duration:dur,ease:"power2.out",onUpdate:()=>{{el.textContent=fmt(o.v);}}}},t);}}
{js}
tl.to("#fade",{{opacity:1,duration:0.7,ease:"power2.in"}},{total-0.7:.2f});
window.__timelines["main"] = tl;
</script>
</body></html>
"""


def synth_vo(text, out_mp3):
    sh([sys.executable, "-m", "edge_tts", "--voice", NARRATOR, f"--rate={VO_RATE}",
        "--text", text, "--write-media", out_mp3])


def build_motion(spec, out_mp4, workdir, quality="standard"):
    os.makedirs(workdir, exist_ok=True)
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + os.path.dirname(FFMPEG)
    scenes = spec["scenes"]
    # ① VO + 길이 → 타이밍
    start = 0.0
    for i, sc in enumerate(scenes):
        mp3 = os.path.join(workdir, f"vo_{i}.mp3")
        synth_vo(sc["narration"], mp3)
        sc["_vo"] = mp3
        vis = probe_dur(mp3) + PAD
        sc["start"] = round(start, 2)
        sc["clip"] = round(vis + (0.5 if i < len(scenes) - 1 else 0.0), 2)
        start += vis - OVERLAP
    total = round(scenes[-1]["start"] + (probe_dur(scenes[-1]["_vo"]) + PAD), 2)
    # ③ HTML
    with open(os.path.join(PROJ, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_html(scenes, total))
    # ④ render
    silent = os.path.join(workdir, "silent.mp4")
    r = subprocess.run(f'npx --yes hyperframes@0.7.9 render --quality {quality} --output "{silent}"',
                       cwd=PROJ, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"render 실패\n{(r.stdout or '')[-1500:]}\n{(r.stderr or '')[-1500:]}")
    # ⑤ VO 트랙(장면 시작 정렬) + mux
    ins, filt, labs = [], [], []
    for i, sc in enumerate(scenes):
        ins += ["-i", sc["_vo"]]
        ms = int((sc["start"] + 0.3) * 1000)
        filt.append(f"[{i}]adelay={ms}|{ms}[a{i}]"); labs.append(f"[a{i}]")
    fc = ";".join(filt) + ";" + "".join(labs) + f"amix=inputs={len(scenes)}:normalize=0[a]"
    vo = os.path.join(workdir, "votrack.m4a")
    sh([FFMPEG, "-y", *ins, "-filter_complex", fc, "-map", "[a]", "-t", f"{total:.2f}",
        "-c:a", "aac", "-b:a", "192k", vo])
    os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
    sh([FFMPEG, "-y", "-i", silent, "-i", vo, "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_mp4])
    print(f"✅ {out_mp4}  ({total:.1f}s, {len(scenes)} scenes)")
    return out_mp4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    args = ap.parse_args()
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    wd = os.path.join(HERE, "motion", "_work")
    build_motion(spec, args.out, wd, args.quality)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
