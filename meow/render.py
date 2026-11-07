"""Meow Remix — 고양이 쇼츠 렌더(대본·목소리 없음, 음악 + 한 줄 자막).

엔진 두 가지(기획 파일의 "engine", 없으면 5b):
- 5b  : 한 편 = 컷 4~7개. 컷마다 z-image 세로 그림 → 5B i2v 2초 → 앞 1.4초 × 1.2배 느리게.
        (5B 는 앞 1초가 제일 깨끗하고 끝으로 갈수록 뭉개진다 — 11/07 견본이 이것. 버벅임·깨짐으로 불합격)
- 14b : 한 편 = 컷 1~3개. 컷마다 그림 → Wan 2.2 I2V-14B 720×1280·81장(16fps, 약 5초)을 늘리지 않고 그대로.
        후처리 스위치(MEOW_VIDEO_POST=1)를 켜면 video_post 로 SeedVR2 업스케일(필요할 때만) + RIFE ×2(32fps).
'xfade' 가 있는 컷은 앞 컷과 겹쳐 녹아들게 이어 붙인다(음식 → 고양이 변신).

    python meow/render.py gen   meow/concepts/<file>.json [--only s01,s02]   # Spark 그림·클립(캐시)
    python meow/render.py build meow/concepts/<file>.json [--only s01]       # ffmpeg 조립 → output/meow
    python meow/render.py check meow/concepts/<file>.json                     # 오프라인 검사

gen 은 이미 받은 클립을 건너뛴다(중간에 끊겨도 다시 돌리면 이어서). 05:45~08:00 KST 에는 Spark 를 쓰지 않는다.

14B 판단은 응답 model 로 한다 — 열 시험(11/09) 전에는 "i2v-14b" 를 보내도 서버가 5B 로 돌리고
model=wan2.2-ti2v-5b-i2v 로 답한다(스파크 담당자 11/07). 그러면 첫 컷에서 멈춘다(5B 81장은 몸이 늘어난다).
video_post 는 아직 서버에 없다(「알 수 없는 type」) — 열렸다고 하면 MEOW_VIDEO_POST=1.
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
# 14b: 81장 ÷ 16fps = 5.06초 → 5초. 32fps = RIFE ×2 그대로(30 으로 맞추면 16장마다 한 장씩 버려져 튄다).
#      후처리가 꺼져 있으면 16fps 를 정확히 두 번씩 보여 준다(30 으로 맞추면 고르지 않게 겹친다 — 11/07 버벅임 원인).
ENGINES = {"5b": {"src": SHOT_SRC, "slow": SLOW, "fps": FPS, "shots": (4, 7)},
           "14b": {"src": 5.0, "slow": 1.0, "fps": 32, "shots": (1, 3)}}
CAP_SIZE = 72
IMG_W, IMG_H = 768, 1344           # 5b 그림(5B 가 넓이 640×640 안으로 줄인다)
V14_W, V14_H, V14_LEN = 720, 1280, 81   # 14b — 16의 배수 · 그림도 같은 크기로 뽑아 비율이 안 틀어지게
V14_MODEL = os.environ.get("MEOW_VIDEO_MODEL") or "i2v-14b"
V14_SPEED = os.environ.get("MEOW_SPEED") or "fast"     # fast = 4스텝(서버 기본·열 적음) | quality = 20스텝
POST_H = 1280                      # video_post 업스케일 목표 높이(세로 720p) — 클립이 이보다 낮을 때만 SeedVR2
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
        for k in ("image", "motion"):
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


def _job(body: dict, out: str | None, timeout: int = 1500) -> dict:
    """작업을 넣고 끝날 때까지 기다린다 → 마지막 상태(job_id · 서버가 실제로 쓴 model·크기·길이…)."""
    requests, base, headers = _spark()
    r = requests.post(f"{base}/jobs", json=body, headers=headers, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Spark {body['type']} 거절 HTTP {r.status_code}: {r.text[:300]}")
    jid = r.json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = requests.get(f"{base}/jobs/{jid}", headers=headers, timeout=30).json()
        if d["status"] == "done":
            if out:
                b = requests.get(f"{base}/jobs/{jid}/file", headers=headers, timeout=300).content
                with open(out + ".part", "wb") as f:
                    f.write(b)
                os.replace(out + ".part", out)
            return {**d, "job_id": jid}
        if d["status"] in ("error", "failed"):
            raise RuntimeError(f"Spark 오류 {body['type']}: {d.get('error')}")
        time.sleep(4)                  # 'hold'(식히는 중)·queued 는 그냥 기다린다
    raise TimeoutError(f"Spark {body['type']} {jid} 시간 초과")


def quiet_hours(now: dt.datetime | None = None) -> bool:
    t = (now or dt.datetime.now(KST)).astimezone(KST).time()
    return dt.time(5, 45) <= t < dt.time(8, 0)


def video_post_on() -> bool:
    return os.environ.get("MEOW_VIDEO_POST") == "1"


def is_14b(info: dict) -> bool:
    return "14b" in str(info.get("model", "")).lower()


def v14_body(png: str, motion: str, seed: int) -> dict:
    with open(png, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    return {"type": "video", "model": V14_MODEL, "image": img, "prompt": motion, "width": V14_W, "height": V14_H,
            "length": V14_LEN, "speed": V14_SPEED, "seed": seed, "format": "mp4", "no_llm": True}


def post_body(raw_info: dict, raw_mp4: str | None) -> dict | None:
    """업스케일은 클립이 세로 720p 보다 낮을 때만(14B 가 640급까지만 열리는 경우) · 보간은 늘 ×2."""
    body = {"type": "video_post", "interpolate": "rife", "multiplier": 2}
    if int(raw_info.get("height") or 0) < POST_H:
        body.update({"upscale": "seedvr2", "target_height": POST_H})
    if raw_mp4:                        # 결과는 1시간 뒤 서버에서 지워진다 — 캐시된 클립은 파일째 보낸다
        with open(raw_mp4, "rb") as f:
            body["video"] = base64.b64encode(f.read()).decode()
    else:
        body["from_job"] = raw_info["job_id"]
    return body


def _save(path: str, info: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)


def clip_path(c: dict, i: int) -> str:
    """build 가 쓸 컷 i 의 클립 — 14b 는 후처리본이 있으면 그것, 없으면 원본."""
    d = os.path.join(WORK, stem(c))
    if engine(c) == "5b":
        return os.path.join(d, f"shot{i}.mp4")
    post = os.path.join(d, f"shot{i}_post.mp4")
    return post if os.path.exists(post) else os.path.join(d, f"shot{i}_raw.mp4")


def gen(c: dict) -> list[str]:
    d = os.path.join(WORK, stem(c))
    os.makedirs(d, exist_ok=True)
    v14 = engine(c) == "14b"
    for i, s in enumerate(c["shots"], 1):
        png = os.path.join(d, f"shot{i}.png")
        raw = os.path.join(d, f"shot{i}_raw.mp4" if v14 else f"shot{i}.mp4")
        post = os.path.join(d, f"shot{i}_post.mp4")
        need_post = v14 and video_post_on() and not os.path.exists(post)
        if os.path.exists(raw) and not need_post:
            continue
        if quiet_hours():
            raise SystemExit("05:45~08:00 KST — Spark 쓰지 않는 시간")
        t0, fresh, img_job = time.time(), None, None
        if not os.path.exists(png):
            w, h = (V14_W, V14_H) if v14 else (IMG_W, IMG_H)
            img_job = _job({"type": "image", "prompt": s["image"], "width": w, "height": h,
                            "no_llm": True, "seed": c["seed"] + i}, png)["job_id"]
        if not os.path.exists(raw):
            if v14:
                info = _job(v14_body(png, s["motion"], c["seed"] + i), raw + ".tmp", timeout=3600)
                if not is_14b(info):
                    os.replace(raw + ".tmp", os.path.join(d, f"shot{i}_not14b.mp4"))
                    raise SystemExit(f"{stem(c)} 컷{i}: 14B 아직 안 열림(응답 model={info.get('model')}) — 열린 뒤 다시")
                os.replace(raw + ".tmp", raw)
                _save(raw.replace(".mp4", ".json"), info)
                fresh = info
            else:
                body = {"type": "video", "prompt": s["motion"], "fast": True, "length": 49, "fps": 16, "mp4": True,
                        "no_llm": True}
                if img_job:
                    body["from_job"] = img_job
                else:
                    with open(png, "rb") as f:
                        body["image"] = base64.b64encode(f.read()).decode()
                _job(body, raw)
        if need_post:
            info = fresh or load(raw.replace(".mp4", ".json"))
            pi = _job(post_body(info, None if fresh else raw), post + ".tmp", timeout=3600)
            os.replace(post + ".tmp", post)
            _save(post.replace(".mp4", ".json"), pi)
        print(f"   {stem(c)} 컷{i} {round(time.time() - t0)}초", flush=True)
    return [clip_path(c, i) for i in range(1, len(c["shots"]) + 1)]


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


def font_path() -> str:
    for p in (os.environ.get("MEOW_FONT"), os.path.join(ROOT, "output", "insta_render", ".fonts", "Pretendard-ExtraBold.ttf"),
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
    raw_only = [os.path.basename(p) for p in clips if p.endswith("_raw.mp4")]
    if raw_only:
        print(f"   {stem(c)}: 후처리 없는 16fps 원본으로 조립 {raw_only}", flush=True)
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
            gen(c)
            print(f"✅ {stem(c)} 클립 {len(c['shots'])}개", flush=True)
        else:
            m = build(c)
            print(f"✅ {m['stem']} {m['sec']}초 → {m['video']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
