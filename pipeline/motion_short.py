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

import textfit as TF

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "motion")
W, H, FPS = 1080, 1920, 30
NARRATOR = os.environ.get("VO_VOICE", "ko-KR-SunHiNeural")
VO_RATE = os.environ.get("VO_RATE", "+6%")
PAD = 0.6        # 내레이션 뒤 여유
OVERLAP = 0.4    # 장면 전환 겹침
BRAND = {"ink": "#0A0808", "cream": "#EDD9BC", "coral": "#D97757", "red": "#E5484D"}

# ── 글자 박스 ──────────────────────────────────────────────
# .wrap 이 left:80px width:920px 이므로 글자가 쓸 수 있는 폭은 920px 이다.
# 여태 폰트 크기가 ★하드코딩이라(.h1=130px) 대본이 길어지면 그냥 3줄이 되거나 넘쳤다.
# 아래 값을 textfit.fit() 에 넘겨 ★글자 수에 맞춰 크기를 정한다.
BOX = 920
BOX_KP = 836          # keypoint 는 번호(58px)+gap(26px)을 뺀 나머지
# ★줄 수를 아끼려고 폰트를 과하게 줄이면 쇼츠에서 안 읽힌다.
#   세로는 남는다(.wrap 아래로 1,000px 넘게 비어 있다) → ★줄을 늘리고 글자는 지킨다.
FIT = {              # 요소: (기본 크기, 최소 크기, 최대 줄 수)
    "h1":        (130, 84,  1),   # 훅 — 스펙이 이미 줄을 나눠 준다 → 줄당 1줄
    "statement": (116, 78,  3),
    "quote":     (90,  62,  3),
    "kp":        (68,  54,  3),
    "sub":       (48,  34,  2),
    "label":     (48,  34,  1),
    "closer":    (72,  54,  2),
    "attr":      (44,  32,  1),
}
BIG_RATIO_H1 = 230 / 130   # .h1 .big 은 본문보다 1.77배 크다 — 폭 계산에 반영해야 한다

# ── 토픽별 액센트 ─────────────────────────────────────────
# 전부 같은 코랄이면 주식이든 운세든 화면이 똑같아 보인다 — 채널이 밋밋해지는 원인 하나.
# 스펙에 accent 가 있으면 ★그게 우선이고, 없을 때만 토픽으로 고른다(기존 동작 보존).
TOPIC_ACCENT = {
    "politics": "#D97757",   # 코랄 — 기존 뉴스 톤
    "economy":  "#E5484D",   # 적색
    "stock":    "#E5484D",   # 국장/미장
    "market":   "#E5484D",
    "zodiac":   "#7C6BD6",   # 인디고 — 별자리
    "star":     "#7C6BD6",
    "fortune":  "#C9A227",   # 금색 — 운세
    "luck":     "#C9A227",
    "love":     "#E0559B",
}


def topic_accent(topic: str, default: str = "#D97757") -> str:
    """topic 슬러그로 액센트 색. 접두사 매칭이라 stock_us·zodiac_daily 도 잡힌다."""
    t = (topic or "").strip().lower()
    if not t:
        return default
    if t in TOPIC_ACCENT:
        return TOPIC_ACCENT[t]
    for k, v in TOPIC_ACCENT.items():
        if t.startswith(k):
            return v
    return default


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

/* ── 가독성 ────────────────────────────────────────────────
   ★한국어는 브라우저 기본값(word-break:normal)에서 음절 단위로 끊긴다.
     "정부가 발표한" → "정부가 발표 / 한"  ← 읽다가 걸린다. keep-all 이 어절 단위로 만든다.
   줄바꿈 위치 자체는 textfit.py 가 <br/> 로 박아 넣지만, 폰트 로딩·폭 추정 오차로
   브라우저가 한 번 더 감을 때를 대비한 ★안전망이다. */
.h1,.statement,.sub,.label,.kp,.quote-text,.quote-attr,.closer{
  word-break:keep-all;overflow-wrap:break-word;}
/* 카운트업 도중 숫자 폭이 달라져 글자가 좌우로 들썩이는 걸 막는다.
   filter 를 0 으로 명시해 두는 건 GSAP 이 blur(18px) → none 보간에서
   막히지 않게 하기 위해서다(끝값이 none 이 아니라 blur(0px) 이 된다). */
.num{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1;filter:blur(0px);}
/* 어절 단위 등장 — 공백을 span ★안에 넣어야 keep-all 이 유지된다(_words 참고) */
.w{display:inline-block;will-change:transform,opacity;}
/* 하이라이트 뒤를 훑고 지나가는 마커 */
.hlwrap{position:relative;display:inline-block;z-index:0;}
.mark{position:absolute;left:-8px;top:6%;height:88%;width:calc(100% + 16px);
  background:#D97757;opacity:.24;border-radius:10px;transform:scaleX(0);
  transform-origin:left center;z-index:-1;}
/* 상단 진행 바 — 쇼츠는 '얼마나 남았나'가 보이면 이탈이 준다 */
#progbase{position:absolute;left:0;top:0;width:1080px;height:10px;
  background:rgba(237,217,188,.12);z-index:60;}
#prog{position:absolute;left:0;top:0;width:1080px;height:10px;background:#D97757;
  transform-origin:left center;transform:scaleX(0);z-index:61;}
"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _allow_b(s):
    # <b>..</b> 만 허용
    return esc(s).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;br/&gt;", "<br/>")


# ── 글자 맞춤 헬퍼 ────────────────────────────────────────
def _fit(kind, text, box=BOX, big="", big_ratio=1.0, esc_fn=None):
    """FIT 표대로 크기를 정하고 <br/> 로 줄을 박은 HTML 을 돌려준다."""
    base, mn, ml = FIT[kind]
    px, lines = TF.fit(text, box, base, min_px=mn, max_lines=ml,
                       big=big, big_ratio=big_ratio)
    e = esc_fn or esc
    return px, "<br/>".join(e(ln) for ln in lines)


def _uniform(kind, texts, box=BOX, big="", big_ratio=1.0):
    """여러 줄/여러 항목의 크기를 ★가장 작은 값으로 통일한다.

    항목마다 크기가 다르면 글자가 들쭉날쭉해 보인다 — 훅 3줄, 키포인트 목록처럼
    나란히 놓이는 것들은 크기가 같아야 정렬이 깔끔하다.
    """
    base, mn, ml = FIT[kind]
    sizes = [TF.fit(t, box, base, min_px=mn, max_lines=ml,
                    big=(big if big and big in t else ""), big_ratio=big_ratio)[0]
             for t in texts if t]
    return min(sizes) if sizes else base


def _words(line, hl="", hl_html="", state=None, esc_fn=None, cls="w"):
    """어절마다 <span class="w"> — 단어 단위로 툭툭 튀어나오는 등장용.

    ★공백을 span ★안에 넣는다. 밖에 두면 줄바꿈이 span 경계에서 일어나
    keep-all 이 무의미해진다.
    ★<b> 가 든 텍스트에는 쓰지 마라 — 어절 경계에서 태그가 갈라져 중첩이 깨진다.
    """
    e = esc_fn or esc
    out = []
    for w, sp in TF.tokens(line, hl):
        inner = e(w)
        if hl and hl_html and state is not None and not state["used"] and hl in w:
            inner = inner.replace(e(hl), hl_html.format(e(hl)), 1)
            state["used"] = True
        # ★공백은 원문에 있었을 때만 넣는다 — 하이라이트가 어절 중간을 끊는 경우
        #   없던 띄어쓰기가 생기면 "몇 번째 였나요?" 처럼 글이 틀어진다.
        out.append(f'<span class="{cls}">{inner}{"&nbsp;" if sp else ""}</span>')
    return "".join(out)


# ── 장면 HTML ─────────────────────────────────────────────
def scene_html(i, sc, acc):
    t = sc["type"]
    gid = f"s{i}"
    glow = f'<div class="glow" id="{gid}-glow" style="width:760px;height:760px;left:-160px;top:280px;background:radial-gradient(circle,{acc},{acc}00);opacity:.45;"></div>'
    grain = '<div class="grain"></div>'
    brand = f'<div class="brand">{esc(sc.get("brand","일상공감뉴스"))}</div>'
    body = ""
    if t == "hook":
        lines = sc.get("lines", [])
        hl = sc.get("highlight", "")
        ghost = f'<div class="ghost" id="{gid}-ghost">{esc(sc.get("ghost",""))}</div>' if sc.get("ghost") else ""
        pill = f'<div class="pillrow"><span class="pill" id="{gid}-pill"><span class="dot"></span>{esc(sc.get("pill","BREAKING"))}</span></div>'
        # 세 줄이 제각각 다른 크기면 지저분하다 → 가장 작은 값으로 통일.
        fs = _uniform("h1", lines, BOX, big=hl, big_ratio=BIG_RATIO_H1)
        big_px = int(round(fs * BIG_RATIO_H1))
        st = {"used": False}
        hl_html = f'<span class="big" id="{gid}-hl" style="font-size:{big_px}px">{{}}</span>'
        lhtml = [f'<div class="h1" id="{gid}-l{j}" style="font-size:{fs}px">'
                 + _words(ln, hl, hl_html, st) + "</div>"
                 for j, ln in enumerate(lines)]
        body = ghost + pill + '<div class="wrap" style="top:560px">' + "".join(lhtml) + "</div>"
    elif t == "stat":
        bar = (f'<div class="barbase"></div><div class="bar" id="{gid}-bar"></div>') if sc.get("bar") else ""
        lp, lh = _fit("label", sc.get("label", ""))
        sp, sh = _fit("sub", sc.get("sub", ""), esc_fn=_allow_b)
        body = (bar + '<div class="wrap">'
                + f'<div class="label" id="{gid}-label" style="font-size:{lp}px">{lh}</div>'
                + f'<div class="num" id="{gid}-num" style="margin-top:18px;">{esc(sc.get("prefix",""))}0{esc(sc.get("suffix",""))}</div>'
                + f'<div class="sub" id="{gid}-sub" style="font-size:{sp}px">{sh}</div></div>')
    elif t == "gauge":
        lp, lh = _fit("label", sc.get("label", ""))
        sp, sh = _fit("sub", sc.get("sub", ""), esc_fn=_allow_b)
        body = (f'<div class="track"></div><div class="fill" id="{gid}-fill"></div>'
                + '<div class="wrap">'
                + f'<div class="label" id="{gid}-label" style="font-size:{lp}px">{lh}</div>'
                + f'<div style="margin-top:10px;"><span class="num" id="{gid}-num">{int(sc.get("from",1))}</span><span class="num" style="font-size:200px;">{esc(sc.get("unit","배"))}</span></div>'
                + f'<div class="sub" id="{gid}-sub" style="font-size:{sp}px">{sh}</div></div>')
    elif t == "trend":
        down = sc.get("dir", "down") == "down"
        col = BRAND["red"] if down else "#3FB950"
        path = "M0,40 L230,70 L460,55 L690,150 L920,320" if down else "M0,320 L230,250 L460,270 L690,120 L920,40"
        lp, lh = _fit("label", sc.get("label", ""))
        sp, sh = _fit("sub", sc.get("sub", ""), esc_fn=_allow_b)
        if sc.get("closer"):
            cp, ch = _fit("closer", sc.get("closer", ""), esc_fn=_allow_b)
            closer = f'<div class="closer" id="{gid}-closer" style="font-size:{cp}px">{ch}</div>'
        else:
            closer = ""
        glow = glow.replace(acc, col).replace('opacity:.45', 'opacity:0').replace(f'id="{gid}-glow"', f'id="{gid}-glow" data-col="{col}"')
        body = ('<div class="wrap">'
                + f'<div class="label" id="{gid}-label" style="color:{col};font-size:{lp}px">{lh}</div>'
                + f'<div class="num" id="{gid}-num" style="color:{col};margin-top:10px;">0{esc(sc.get("suffix","%"))}</div>'
                + f'<div class="sub" id="{gid}-sub" style="font-size:{sp}px">{sh}</div></div>'
                + f'<svg viewBox="0 0 920 360" preserveAspectRatio="none"><path id="{gid}-line" d="{path}" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                + closer)
    elif t == "quote":
        qp, qh = _fit("quote", sc.get("text", ""), esc_fn=_allow_b)
        ap, ah = _fit("attr", sc.get("attr", ""))
        body = ('<div class="wrap" style="top:520px">'
                + f'<div class="quote-mark" id="{gid}-qm">&ldquo;</div>'
                + f'<div class="quote-text" id="{gid}-qt" style="font-size:{qp}px">{qh}</div>'
                + f'<div class="quote-attr" id="{gid}-qa" style="font-size:{ap}px">{ah}</div></div>')
    elif t == "keypoint":
        pts_txt = sc.get("points", [])
        fs = _uniform("kp", pts_txt, BOX_KP)
        lp, lh = _fit("label", sc.get("label", ""))
        items = []
        for j, ptxt in enumerate(pts_txt):
            # ★통일된 fs 기준으로 다시 감는다 — 항목마다 제 크기로 감아 두고
            #   더 작은 크기로 그리면 필요 이상으로 줄이 늘어난다.
            ph = "<br/>".join(_allow_b(ln)
                              for ln in TF.wrap(ptxt, fs, BOX_KP * 0.94))
            items.append(f'<div class="kp" id="{gid}-kp{j}" style="font-size:{fs}px">'
                         f'<span class="b">{j+1}</span><span>{ph}</span></div>')
        body = ('<div class="wrap" style="top:480px">'
                + f'<div class="label" id="{gid}-label" style="font-size:{lp}px">{lh}</div>'
                + "".join(items) + "</div>")
    elif t == "statement":
        text = sc.get("text", "")
        hl = sc.get("highlight", "")
        # .statement .big 은 ★색만 바뀐다(크기 동일) → big_ratio = 1.0
        base, mn, ml = FIT["statement"]
        fs, lines = TF.fit(text, BOX, base, min_px=mn, max_lines=ml, big=hl)
        st = {"used": False}
        hl_html = (f'<span class="hlwrap"><span class="mark" id="{gid}-mark"></span>'
                   f'<span class="big" id="{gid}-hl">{{}}</span></span>')
        inner = "<br/>".join(_words(ln, hl, hl_html, st) for ln in lines)
        body = (f'<div class="wrap" style="top:560px">'
                f'<div class="statement" id="{gid}-st" style="font-size:{fs}px">{inner}</div></div>')
    cls = "scene clip trend" if t == "trend" else "scene clip"
    return (f'<div id="{gid}" class="{cls}" data-start="{sc["start"]:.2f}" '
            f'data-duration="{sc["clip"]:.2f}" data-track-index="{i}" style="z-index:{i+1}">'
            + glow + grain + body + brand + "</div>")


# ── 장면 JS(GSAP) ─────────────────────────────────────────
TRANSITIONS = ["fade", "pushup", "slideleft", "zoom"]


def scene_js(i, sc, acc):
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
        # 필이 한 번 두근 — 정지 화면이 아니라는 신호
        out.append(f'tl.to("#{gid}-pill",{{scale:1.06,duration:0.5,ease:"sine.inOut",yoyo:true,repeat:3,transformOrigin:"left center"}},{S+0.8:.2f});')
        # ★줄 통째가 아니라 ★어절 단위로 튀어나온다 — 같은 시간에 움직임이 훨씬 많다
        for j in range(len(sc.get("lines", []))):
            out.append(f'tl.from("#{gid}-l{j} .w",{{y:70,opacity:0,rotateX:-45,transformPerspective:700,duration:0.42,ease:"back.out(1.7)",stagger:0.055}},{S+0.45+j*0.26:.2f});')
        if sc.get("highlight"):
            out.append(f'tl.fromTo("#{gid}-hl",{{scale:0.4,color:"{BRAND["cream"]}"}},{{scale:1,color:"{acc}",duration:0.6,ease:"back.out(2.4)"}},{S+1.1:.2f});')
            out.append(f'tl.to("#{gid}-hl",{{scale:1.06,duration:0.28,ease:"sine.inOut",yoyo:true,repeat:1}},{S+1.75:.2f});')
    elif t == "quote":
        out.append(f'tl.from("#{gid}-qm",{{scale:0.5,opacity:0,duration:0.6,ease:"back.out(1.6)"}},{S+0.4:.2f});')
        out.append(f'tl.from("#{gid}-qt",{{y:40,opacity:0,duration:0.6,ease:"power3.out"}},{S+0.6:.2f});')
        out.append(f'tl.from("#{gid}-qa",{{opacity:0,duration:0.5,ease:"power2.out"}},{S+1.1:.2f});')
    elif t == "keypoint":
        out.append(f'tl.from("#{gid}-label",{{x:-40,opacity:0,duration:0.5,ease:"power2.out"}},{S+0.4:.2f});')
        for j in range(len(sc.get("points", []))):
            out.append(f'tl.from("#{gid}-kp{j}",{{x:-30,opacity:0,duration:0.45,ease:"power2.out"}},{S+0.7+j*0.45:.2f});')
    elif t == "statement":
        out.append(f'tl.from("#{gid}-st .w",{{y:56,opacity:0,duration:0.44,ease:"power3.out",stagger:0.06}},{S+0.35:.2f});')
        if sc.get("highlight"):
            out.append(f'tl.fromTo("#{gid}-hl",{{color:"{BRAND["cream"]}"}},{{color:"{acc}",duration:0.45,ease:"power2.out"}},{S+0.95:.2f});')
            # 형광펜으로 그은 듯 뒤를 훑고 지나간다
            out.append(f'tl.fromTo("#{gid}-mark",{{scaleX:0}},{{scaleX:1,duration:0.5,ease:"power3.out"}},{S+0.95:.2f});')
    elif t in ("stat", "gauge", "trend"):
        out.append(f'tl.from("#{gid}-label",{{x:-40,opacity:0,duration:0.5,ease:"power2.out"}},{S+0.5:.2f});')
        out.append(f'tl.from("#{gid}-num",{{scale:0.6,opacity:0,filter:"blur(18px)",duration:0.5,ease:"back.out(1.7)"}},{S+0.65:.2f});')
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
            down = sc.get("dir", "down") == "down"
            suf = sc.get("suffix", "%")
            out.append(f'cu("#{gid}-num",{sc.get("from",0)},{sc.get("to",0)},{cu},1.2,v=>Math.round(v)+"{suf}");')
            out.append(f'tl.to("#{gid}-glow",{{opacity:0.5,duration:0.6,ease:"power2.out"}},{cu});')
            out.append(f'tl.fromTo("#{gid}-line",{{strokeDashoffset:1200,strokeDasharray:1200}},{{strokeDashoffset:0,duration:1.4,ease:"power2.inOut"}},{S+0.7:.2f});')
            if down:
                # 선이 바닥을 찍는 순간 화면이 한 번 흔들린다
                out.append(f'tl.to("#{gid}",{{x:-14,duration:0.055,ease:"none",yoyo:true,repeat:5}},{S+1.95:.2f});')
                out.append(f'tl.set("#{gid}",{{x:0}},{S+2.3:.2f});')
        out.append(f'tl.from("#{gid}-sub",{{y:30,opacity:0,duration:0.5,ease:"power2.out"}},{S+1.6:.2f});')
        if t == "trend" and sc.get("closer"):
            out.append(f'tl.to("#{gid}-closer",{{opacity:1,y:-10,duration:0.6,ease:"power3.out"}},{S+4.3:.2f});')
    return "\n".join(out)


def build_html(scenes, total, acc="#D97757"):
    css = f":root{{--acc:{acc};}}\n" + CSS.replace("#D97757", "var(--acc,#D97757)")
    parts = [scene_html(i, sc, acc) for i, sc in enumerate(scenes)]
    js = "\n".join(scene_js(i, sc, acc) for i, sc in enumerate(scenes))
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{css}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.2f}" data-width="1080" data-height="1920">
{''.join(parts)}
<div id="progbase"></div><div id="prog"></div>
<div id="fade"></div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused:true }});
function cu(sel,from,to,t,dur,fmt){{const o={{v:from}},el=document.querySelector(sel);tl.to(o,{{v:to,duration:dur,ease:"power2.out",onUpdate:()=>{{el.textContent=fmt(o.v);}}}},t);}}
{js}
// 상단 진행 바 — 전체 길이에 걸쳐 선형으로 찬다(남은 분량이 보이면 이탈이 준다)
tl.fromTo("#prog",{{scaleX:0}},{{scaleX:1,duration:{total:.2f},ease:"none"}},0);
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
        acc = spec.get("accent") or topic_accent(spec.get("topic", ""))
        f.write(build_html(scenes, total, acc))
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
