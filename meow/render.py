"""Meow Remix — 고양이 쇼츠 렌더(대본·목소리 없음, 음악 + 한 줄 자막).

엔진 두 가지(기획 파일의 "engine", 없으면 5b):
- 5b  : 한 편 = 컷 4~7개. 컷마다 z-image 세로 그림 → 5B i2v 2초 → 앞 1.4초 × 1.2배 느리게.
        (5B 는 앞 1초가 제일 깨끗하고 끝으로 갈수록 뭉개진다 — 11/07 견본이 이것. 버벅임·깨짐으로 불합격)
- 14b : 한 편 = 컷 1~3개. 컷마다 720×1280 그림 → 스파크 "영상 HD"(hd:true) 한 번 = 720×1280·32fps·5초 완성본.
        서버 안에서 I2V-14B 480×832·81장 → SeedVR2 로 720 → RIFE ×2 를 이어 돌린다(11/09 열림). 늘리지 않고 그대로 쓴다.
'xfade' 가 있는 컷은 앞 컷과 겹쳐 녹아들게 이어 붙인다(음식 → 고양이 변신).
컷 그림은 "image"(새로 그림) 또는 "edit"(앞 컷 그림을 Qwen-Image-Edit 로 고쳐 만듦 — "from" 컷, 기본 1) 중 하나.
  ★11/09 HD 견본 첫눈 편: 컷마다 따로 그리니 2컷째 고양이 무늬가 바뀌었다 → 매일판은 2컷째를 edit 로(같은 고양이).

    python meow/render.py gen   meow/concepts/<file>.json [--only s01,s02]   # Spark 그림 전부 → 클립(캐시)
    python meow/render.py build meow/concepts/<file>.json [--only s01]       # ffmpeg 조립 → output/meow
    python meow/render.py check meow/concepts/<file>.json                     # 오프라인 검사

gen 은 이미 받은 그림·클립을 건너뛴다(중간에 끊겨도 다시 돌리면 이어서). 05:45~08:00 KST 에는 Spark 를 쓰지 않는다
(HD 클립은 20분 전부터 새로 넣지 않는다) — 종료 코드 75(워크플로는 다음 예비 실행에 맡긴다).

14B 판단은 응답 model 로 한다 — hd 없이 그림을 주면 서버는 5B 로 만든다(10/02 열 사고 뒤). 응답 model 에
14b 가 없으면 첫 컷에서 멈춘다(5B 81장은 몸이 늘어난다). HD 한 편 약 13분(생성 3·식힘 5·키우기/보간 4),
GPU 가 다른 일 중이면 최대 약 1시간 기다린다(11/09 저녁 식힘을 늘려 한 편 약 16분). 95°C 에 닿으면 status=error → 잠시 뒤 다시 요청(최대 2번).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("MEOW_OUT") or os.path.join(ROOT, "output", "meow")
WORK = os.environ.get("MEOW_WORK") or os.path.join(OUT, ".work")
MUSIC = os.path.join(HERE, "music")
KST = dt.timezone(dt.timedelta(hours=9))

W, H, FPS = 1080, 1920, 30
SHOT_SRC = 1.4                     # 5B 클립 2.04초 중 앞 1.4초만 — 1.5초를 넘으면 몸이 늘어나는 일이 잦다(11/07 견본 실측)
SLOW = 1.2                         # 살짝 느리게(1.4초 → 1.68초) — 귀여운 동작은 느린 쪽이 잘 읽힌다
# src = 컷마다 클립에서 쓰는 길이(초) · slow = 늘리는 배수 · fps = 완성 영상 fps · shots = 컷 수 범위
# 14b: HD 완성본 161장 ÷ 32fps = 5.03초 → 5초. 32fps 그대로(30 으로 맞추면 16장마다 한 장씩 버려져 튄다 — 11/07 버벅임 원인).
ENGINES = {"5b": {"src": SHOT_SRC, "slow": SLOW, "fps": FPS, "shots": (4, 7)},
           "14b": {"src": 5.0, "slow": 1.0, "fps": 32, "shots": (1, 3)}}
CAP_SIZE = 72
IMG_W, IMG_H = 768, 1344           # 5b 그림(5B 가 넓이 640×640 안으로 줄인다)
V14_W, V14_H = 720, 1280           # 14b 그림 = 완성본 크기(세로 0.8 미만 → 서버가 480×832 로 만들어 720×1280 으로)
HD_TIMEOUT = 5400                  # 한 컷 13분 + GPU 기다림 최대 약 1시간
HD_RETRY, HD_RETRY_WAIT = 2, 300   # 열 안전장치로 멈추면(status=error) 5분 쉬고 다시
FORMATS = {"morph", "dance", "meme", "game"}
# 그림 프롬프트에 들어가면 안 되는 것 — 글자(깨진 글자가 나온다)·실존 인물·상표·게임 캐릭터
BANNED = re.compile(r"\b(text|letters|logo|sign|caption|subtitle|phone|smartphone|minecraft|mario|pokemon|pikachu|"
                    r"fortnite|roblox|sonic|zelda|disney|marvel|starbucks|mcdonald|nike|taylor swift|elon)\b", re.I)


def ffmpeg() -> str:
    return os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tracks() -> dict:
    return {t["file"]: t for t in load(os.path.join(MUSIC, "tracks.json"))["tracks"]}


def credit(track_file: str) -> str:
    t = tracks()[track_file]
    lic = load(os.path.join(MUSIC, "tracks.json"))["license"]
    return f'Music: "{t["title"]}" Kevin MacLeod (incompetech.com). {lic}'


def stem(c: dict) -> str:
    return f"{c['id']}_{c['slug']}"


def engine(c: dict) -> str:
    return c.get("engine") or "5b"


def eng(c: dict) -> dict:
    return ENGINES[engine(c)]


def wrap(text: str, width: int = 20) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def check_concept(c: dict) -> list[str]:
    errs, cid = [], c.get("id", "?")
    for k in ("id", "slug", "format", "track", "seed", "caption", "title", "en_line", "ko_line", "shots"):
        if k not in c:
            errs.append(f"{cid}: {k} 없음")
    if errs:
        return errs
    if engine(c) not in ENGINES:
        return [f"{cid}: engine {engine(c)} 모름({'/'.join(ENGINES)})"]
    if c["format"] not in FORMATS:
        errs.append(f"{cid}: format {c['format']} 모름")
    if c["track"] not in tracks():
        errs.append(f"{cid}: 음악 {c['track']} 이 tracks.json 에 없음")
    if not re.fullmatch(r"[a-z0-9-]+", c["slug"]):
        errs.append(f"{cid}: slug 는 소문자·숫자·- 만")
    lo, hi = eng(c)["shots"]
    if not lo <= len(c["shots"]) <= hi:
        errs.append(f"{cid}: 컷 {len(c['shots'])}개({lo}~{hi})")
    if len(wrap(c["caption"])) > 2:
        errs.append(f"{cid}: 자막이 두 줄을 넘는다")
    if len(c["title"]) > 90:
        errs.append(f"{cid}: 제목이 길다")
    for i, s in enumerate(c["shots"]):
        if bool(s.get("image")) == bool(s.get("edit")):
            errs.append(f"{cid} 컷{i + 1}: 그림은 image 또는 edit 중 하나만")
        if s.get("edit") and not 1 <= int(s.get("from", 1)) <= i:
            errs.append(f"{cid} 컷{i + 1}: edit 는 앞 컷 그림에서(from 1~{i}) — 첫 컷은 image")
        for k in ("image", "edit", "motion"):
            for w in sorted({x.lower() for x in BANNED.findall(s.get(k, ""))}):
                errs.append(f"{cid} 컷{i + 1}: '{w}' 금지어({k})")
        if "static camera" not in s.get("motion", ""):
            errs.append(f"{cid} 컷{i + 1}: motion 에 'static camera' 가 없다(i2v 가 손 떨림을 지어낸다)")
        if s.get("xfade") and (i == 0 or not 0.1 <= s["xfade"] <= 0.8):
            errs.append(f"{cid} 컷{i + 1}: xfade 는 둘째 컷부터 0.1~0.8초")
        if s.get("sec") and float(s["sec"]) > eng(c)["src"]:
            errs.append(f"{cid} 컷{i + 1}: sec {s['sec']} > 클립 {eng(c)['src']}초")
    return errs


def check(doc: dict) -> list[str]:
    errs = []
    ids = [c.get("id") for c in doc["concepts"]]
    if len(ids) != len(set(ids)):
        errs.append("id 가 겹친다")
    for c in doc["concepts"]:
        errs += check_concept(c)
    return errs


# ── Spark ──────────────────────────────────────────────
def _spark():
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    import wbspark  # noqa: E402
    import requests  # noqa: E402
    return requests, wbspark._base(), wbspark._headers()


class SparkJobError(RuntimeError):
    """접수된 작업이 서버에서 실패(status=error/failed) — 거절(HTTP 4xx)과 달리 다시 해 볼 만하다."""


def _job(body: dict, out: str | None, timeout: int = 1500) -> dict:
    """작업을 넣고 끝날 때까지 기다린다 → 마지막 상태(job_id · 서버가 실제로 쓴 model·크기·길이…)."""
    requests, base, headers = _spark()
    r = requests.post(f"{base}/jobs", json=body, headers=headers, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Spark {body['type']} 거절 HTTP {r.status_code}: {r.text[:300]}")
    jid = r.json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            g = requests.get(f"{base}/jobs/{jid}", headers=headers, timeout=30)
            d = g.json() if g.ok else {}
        except (requests.RequestException, ValueError):   # 게이트웨이가 다시 켜지는 몇 초 — 쉬고 다시 본다
            time.sleep(10)
            continue
        if g.status_code == 404 or (g.ok and "status" not in d):
            # 게이트웨이가 다시 켜지면 진행 중이던 작업이 사라진다(11/09 18시 첫눈 컷2) — 다시 넣을 일
            raise SparkJobError(f"Spark {body['type']} {jid} 작업이 사라짐(게이트웨이 재시작?) HTTP {g.status_code}")
        if d.get("status") == "done":
            if out:
                f = requests.get(f"{base}/jobs/{jid}/file", headers=headers, timeout=300)
                if f.status_code != 200:
                    raise SparkJobError(f"Spark {body['type']} {jid} 결과 받기 실패 HTTP {f.status_code}")
                with open(out + ".part", "wb") as fh:
                    fh.write(f.content)
                os.replace(out + ".part", out)
            return {**d, "job_id": jid}
        if d.get("status") in ("error", "failed"):
            raise SparkJobError(f"Spark 오류 {body['type']}: {d.get('error')}")
        time.sleep(4)                  # running(HD 는 기다림·식힘 포함)·hold·queued 는 그냥 기다린다
    raise TimeoutError(f"Spark {body['type']} {jid} 시간 초과")


def quiet_hours(now: dt.datetime | None = None, ahead_min: int = 0) -> bool:
    """05:45~08:00 KST(아침 업로드 루틴 몫) — ahead_min 분 안에 그 시간에 들어가도 참(긴 HD 를 새로 넣지 않게)."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    for t in {now, now + dt.timedelta(minutes=ahead_min)}:
        if dt.time(5, 45) <= t.time() < dt.time(8, 0):
            return True
    return now.time() < dt.time(5, 45) and (now + dt.timedelta(minutes=ahead_min)).time() >= dt.time(8, 0)


class QuietHours(SystemExit):
    """Spark 를 쓰지 않는 시간 — 종료 코드 75(실패가 아니다: 다음 실행이 받은 그림·클립부터 잇는다)."""

    def __init__(self):
        super().__init__(75)


def _guard(ahead_min: int = 0) -> None:
    if quiet_hours(ahead_min=ahead_min):
        print("⏸️ 05:45~08:00 KST — Spark 쓰지 않는 시간(다음 실행이 잇는다)", flush=True)
        raise QuietHours()


def is_14b(info: dict) -> bool:
    return "14b" in str(info.get("model", "")).lower()


def hd_body(png: str, motion: str, seed: int) -> dict:
    """스파크 영상 HD — 문서에 있는 키만(오타·모르는 키는 접수 때 400)."""
    with open(png, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    return {"type": "video", "hd": True, "prompt": motion, "image": img, "seed": seed}


def hd_job(body: dict, out: str, sleep=time.sleep) -> dict:
    for k in range(HD_RETRY + 1):
        try:
            return _job(body, out, timeout=HD_TIMEOUT)
        except SparkJobError as e:
            if k == HD_RETRY:
                raise
            print(f"   {e} — {HD_RETRY_WAIT // 60}분 쉬고 다시({k + 1}/{HD_RETRY})", flush=True)
            sleep(HD_RETRY_WAIT)
    raise AssertionError


def _save(path: str, info: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)


def clip_path(c: dict, i: int) -> str:
    """build 가 쓸 컷 i 의 클립."""
    return os.path.join(WORK, stem(c), f"shot{i}.mp4" if engine(c) == "5b" else f"shot{i}_raw.mp4")


def shot_png(c: dict, i: int) -> str:
    return os.path.join(WORK, stem(c), f"shot{i}.png")


def img_size(c: dict) -> tuple[int, int]:
    return (V14_W, V14_H) if engine(c) == "14b" else (IMG_W, IMG_H)


def image_body(c: dict, i: int, s: dict) -> dict:
    """컷 i(1부터) 그림 요청 — edit 면 앞 컷 그림 + 지시문(Qwen-Image-Edit-2511 · 구도·크기는 원본을 따른다)."""
    seed = int(s.get("seed", c["seed"] + i))
    if s.get("edit"):
        with open(shot_png(c, int(s.get("from", 1))), "rb") as f:
            img = base64.b64encode(f.read()).decode()
        return {"type": "image", "image": img, "edit": s["edit"], "prompt": s["edit"], "seed": seed}
    w, h = img_size(c)
    return {"type": "image", "prompt": s["image"], "width": w, "height": h, "no_llm": True, "seed": seed}


def img_job(body: dict, out: str, tries: int = 3, wait: int = 30, sleep=time.sleep) -> dict:
    for k in range(tries):
        try:
            return _job(body, out, timeout=900)
        except (SparkJobError, TimeoutError) as e:
            if k == tries - 1:
                raise
            print(f"   그림 {e} — {wait}초 쉬고 다시", flush=True)
            sleep(wait)
    raise AssertionError


def fit_image(src: str, dst: str, w: int, h: int) -> None:
    """편집 결과는 원본 비율을 16 배수로 맞춘 크기(11/09 실측 720×1280 → 752×1392) — 컷 크기로 채워 가운데 자른다."""
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", src, "-vf",
                    f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}", dst], check=True)


def images(c: dict) -> list[str]:
    """컷 그림 전부(편집 컷의 원본이 먼저 있어야 한다 — 순서대로). 이미 있는 그림은 건너뛴다."""
    os.makedirs(os.path.join(WORK, stem(c)), exist_ok=True)
    for i, s in enumerate(c["shots"], 1):
        png = shot_png(c, i)
        if os.path.exists(png):
            continue
        _guard(5)
        t0 = time.time()
        if s.get("edit"):
            tmp = png[:-4] + "_edit.png"
            info = img_job(image_body(c, i, s), tmp)
            fit_image(tmp, png, *img_size(c))
        else:
            info = img_job(image_body(c, i, s), png)
        print(f"   {stem(c)} 그림{i} {info.get('model')} {info.get('width')}×{info.get('height')} · "
              f"{round(time.time() - t0)}초", flush=True)
    return [shot_png(c, i) for i in range(1, len(c["shots"]) + 1)]


def clips(c: dict) -> list[str]:
    d = os.path.join(WORK, stem(c))
    v14 = engine(c) == "14b"
    for i, s in enumerate(c["shots"], 1):
        png = shot_png(c, i)
        raw = clip_path(c, i)
        if os.path.exists(raw):
            continue
        if not os.path.exists(png):
            raise SystemExit(f"{stem(c)} 컷{i}: 그림 없음 — images 먼저")
        _guard(20 if v14 else 3)
        t0 = time.time()
        vseed = int(s.get("vseed", c["seed"] + i))
        if v14:
            info = hd_job(hd_body(png, s["motion"], vseed), raw + ".tmp")
            if not is_14b(info):
                os.replace(raw + ".tmp", os.path.join(d, f"shot{i}_not14b.mp4"))
                raise SystemExit(f"{stem(c)} 컷{i}: 14B 아님(응답 model={info.get('model')}) — 멈춤")
            os.replace(raw + ".tmp", raw)
            _save(raw.replace(".mp4", ".json"), info)
            print(f"   {stem(c)} 컷{i} {info.get('width')}×{info.get('height')} {info.get('fps')}fps "
                  f"{info.get('duration_sec')}초 · 서버 {info.get('elapsed')}초", flush=True)
        else:
            with open(png, "rb") as f:
                img = base64.b64encode(f.read()).decode()
            _job({"type": "video", "prompt": s["motion"], "fast": True, "length": 49, "fps": 16, "mp4": True,
                  "no_llm": True, "image": img}, raw)
        print(f"   {stem(c)} 컷{i} {round(time.time() - t0)}초", flush=True)
    return [clip_path(c, i) for i in range(1, len(c["shots"]) + 1)]


def gen(c: dict) -> list[str]:
    images(c)
    return clips(c)


# ── 조립 ───────────────────────────────────────────────
def plan(c: dict) -> list[dict]:
    """컷마다 쓸 길이·앞 컷과 겹칠 길이·영상 안 시작 시각."""
    e, rows, t = eng(c), [], 0.0
    for i, s in enumerate(c["shots"]):
        x = float(s.get("xfade") or 0) if i else 0.0
        dur = round(float(s.get("sec") or e["src"]) * e["slow"], 3)
        start = t - x
        rows.append({"dur": dur, "xfade": x, "start": round(start, 3)})
        t = start + dur
    return rows


def total(c: dict) -> float:
    p = plan(c)
    return round(p[-1]["start"] + p[-1]["dur"], 3)


def filtergraph(c: dict, n_inputs: int) -> str:
    e, p = eng(c), plan(c)
    slow, fps = e["slow"], e["fps"]
    parts = []
    for i, r in enumerate(p):
        # 세로 클립 → 1080x1920: 높이를 맞춰 키운 뒤 가로를 가운데로 자른다
        src = round(r["dur"] / slow, 3)
        parts.append(f"[{i}:v]trim=0:{src},setpts=(PTS-STARTPTS)*{slow},fps={fps},"
                     f"scale=-2:{H}:flags=lanczos,crop={W}:{H},setsar=1,format=yuv420p,settb=1/{fps}[v{i}]")
    acc = "v0"
    for i in range(1, len(p)):
        r, nxt = p[i], f"a{i}"
        if r["xfade"]:
            parts.append(f"[{acc}][v{i}]xfade=transition=fade:duration={r['xfade']}:offset={r['start']}[{nxt}]")
        else:
            # concat 은 시간 단위(timebase)를 바꾼다 → 다음 xfade 가 '안 맞는다'며 멈춘다(11/07 s05) — 다시 맞춘다
            parts.append(f"[{acc}][v{i}]concat=n=2:v=1:a=0,settb=1/{fps}[{nxt}]")
        acc = nxt
    tl = total(c)
    # 자막은 줄마다 drawtext 하나 — 한 번에 그리면 줄이 가운데로 안 모인다
    n = len(wrap(c["caption"]))
    dts = [f"drawtext=fontfile=font.ttf:textfile=cap{k}.txt:fontsize={CAP_SIZE}:fontcolor=white:borderw=8:"
           f"bordercolor=black:x=(w-text_w)/2:y={int(H * 0.10 + k * CAP_SIZE * 1.25)}" for k in range(n)]
    parts.append(f"[{acc}]" + ",".join(dts) + ",format=yuv420p[vout]")
    a = n_inputs - 1
    parts.append(f"[{a}:a]atrim=0:{tl},asetpts=PTS-STARTPTS,afade=t=in:d=0.05,"
                 f"afade=t=out:st={max(tl - 0.7, 0)}:d=0.7[aout]")
    return ";".join(parts)


def _pretendard() -> str | None:
    """견본과 같은 Pretendard ExtraBold — 레포의 woff2 를 fontTools 로 ttf 로(인스타 렌더와 같은 캐시 폴더)."""
    dst = os.path.join(ROOT, "output", "insta_render", ".fonts", "Pretendard-ExtraBold.ttf")
    if os.path.exists(dst):
        return dst
    src = os.path.join(ROOT, "pipeline", "motion", "assets", "fonts", "Pretendard-ExtraBold.woff2")
    try:
        from fontTools.ttLib import TTFont  # woff2 는 brotli 가 있어야 풀린다
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        f = TTFont(src)
        f.flavor = None
        f.save(dst)
        return dst
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ Pretendard 변환 실패(대체 글꼴): {str(e)[:100]}")
        return None


def font_path() -> str:
    for p in (os.environ.get("MEOW_FONT"), _pretendard(),
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if p and os.path.exists(p):
            return p
    raise SystemExit("자막 글꼴 없음(MEOW_FONT)")


def build(c: dict) -> dict:
    d = os.path.join(WORK, stem(c))
    clips = [clip_path(c, i) for i in range(1, len(c["shots"]) + 1)]
    miss = [p for p in clips if not os.path.exists(p)]
    if miss:
        raise SystemExit(f"{stem(c)}: 클립 없음 {len(miss)}개 — gen 먼저")
    os.makedirs(OUT, exist_ok=True)
    shutil.copyfile(font_path(), os.path.join(d, "font.ttf"))
    for k, line in enumerate(wrap(c["caption"])):
        with open(os.path.join(d, f"cap{k}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(line)
    t = tracks()[c["track"]]
    fps = eng(c)["fps"]
    video = os.path.abspath(os.path.join(OUT, f"{stem(c)}.mp4"))
    cmd = [ffmpeg(), "-v", "error", "-y"]
    for p in clips:
        cmd += ["-i", os.path.abspath(p)]
    cmd += ["-ss", str(t.get("start", 0)), "-i", os.path.join(MUSIC, c["track"])]
    cmd += ["-filter_complex", filtergraph(c, len(clips) + 1), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video]
    subprocess.run(cmd, check=True, cwd=d)
    tl = total(c)
    # 표지 = 고른 컷의 원본 그림(움직이기 전이라 제일 깨끗하다) · 글자 없이 — 인스타 격자에서 잘리지 않게
    k = int(c.get("cover_shot") or len(c["shots"]))
    cover = video.replace(".mp4", "_cover.jpg")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", os.path.join(d, f"shot{k}.png"), "-vf",
                    f"scale=-2:{H}:flags=lanczos,crop={W}:{H}", "-q:v", "2", cover], check=True)
    sheet = video.replace(".mp4", "_sheet.jpg")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", video, "-vf",
                    f"fps=2,scale=270:-1,tile={int(tl * 2) + 1}x1", "-frames:v", "1", sheet], check=True)
    meta = {"id": c["id"], "slug": c["slug"], "stem": stem(c), "video": video, "cover": cover, "sheet": sheet,
            "sec": tl, "track": c["track"], "credit": credit(c["track"]), "engine": engine(c)}
    with open(video.replace(".mp4", "_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "build", "check"])
    ap.add_argument("concepts")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    doc = load(a.concepts)
    errs = check(doc)
    if errs:
        print("❌ 검사 실패\n  " + "\n  ".join(errs))
        return 1
    if a.cmd == "check":
        print(f"✅ {len(doc['concepts'])}편 · 컷 {sum(len(c['shots']) for c in doc['concepts'])}개")
        return 0
    only = {x for x in a.only.split(",") if x}
    for c in doc["concepts"]:
        if only and c["id"] not in only:
            continue
        if a.cmd == "gen":
            try:
                gen(c)
            except QuietHours:
                return 75
            print(f"✅ {stem(c)} 클립 {len(c['shots'])}개", flush=True)
        else:
            m = build(c)
            print(f"✅ {m['stem']} {m['sec']}초 → {m['video']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
