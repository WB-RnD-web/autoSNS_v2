#!/usr/bin/env python3
"""사연 쇼츠(실사 AI) — 하루 한 편, 2주 시험(2026-10).

왜: 10/2 떡상 해부 — 55+ 시청자 채널에서 갑자기 뜬 쇼츠는 '실사 AI 사연'이었다.
    사용자가 섞어 쓰기 샘플(사진 + 결정적 장면 2개만 5B 영상)을 보고 시험을 정했다.
대본: 레포의 saeyeon_shorts/stories.json(14편). 루틴이 쓰지 않는다 — 루틴에 시킨 말은 안 지켜지고,
    번호로 정해 둔 것만 지켜졌다. 하루 한 편 = 아직 안 올린 가장 낮은 번호(ledger + 채널 표식 '사연 S001').
    14편이 끝나면 저절로 멈춘다.
그림·목소리·영상은 Spark(무료):
    그림 z-image 768x1344(no_llm) · 목소리 Supertonic · 'move' 장면만 wan2.2 5B 2초(카메라 고정 지시).
    ★영상은 서버 대기열이 비었을 때만 넣는다. 바쁨·실패·응답 없음이면 그 장면은 사진으로 가고 편은 멈추지 않는다
    (10/1·10/2 영상 작업 직후 서버가 두 번 뻗었다. 사용자가 보호장치를 넣은 뒤 5B 는 세 번 다 정상, 장면당 ~100초).
    그림·목소리가 끝내 안 나오면 그날은 올리지 않는다(다음 날 같은 편을 다시 시도).

    python pipeline/saeyeon_shorts.py check              # 대본 검사(오프라인)
    python pipeline/saeyeon_shorts.py due                # 다음 편 번호(없으면 빈 줄)
    python pipeline/saeyeon_shorts.py render N [--no-video]
    python pipeline/saeyeon_shorts.py upload N
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wbspark  # noqa: E402

ROOT = os.path.dirname(HERE)
STORIES = os.path.join(HERE, "saeyeon_shorts", "stories.json")
OUT = os.path.join(ROOT, "output", "saeyeon_shorts")
LEDGER = os.path.join(ROOT, "output", "saeyeon_shorts_ledger.json")

W, H, FPS = 1080, 1920, 24
GAP = 0.45                      # 장면 끝 숨 고르기(초)
VOICES = {f"{g}{i}" for g in "FM" for i in range(1, 6)}
TOP_MAX, SUB_MAX, SPEECH_MAX = 12, 20, 230    # 위 제목 줄당 한글 · 자막 글자 · 대사 글자(≈45초)
MOVE_MAX = 2
IMG_MODEL = os.environ.get("SAEYEON_IMG_MODEL", "z-image-turbo")
VIDEO_CUT = 1.9                 # 5B 결과(2.04초) 중 쓰는 앞부분
IDLE_WAIT = int(os.environ.get("SAEYEON_IDLE_WAIT", "480"))    # 영상 넣기 전 서버가 빌 때까지 기다리는 최대 초
BANNED_PROMPT = ("phone", "smartphone", "cellphone")           # 부정형으로 써도 오히려 폰이 생긴다(10/2 실측)
TAGS = ["사연", "사이다사연", "감동사연", "인생이야기", "사연쇼츠", "shorts"]
PLAYLIST_DESC = "하루 한 편, 1분 안에 끝나는 사이다·감동 사연 · 창작된 이야기이며 AI로 만들었습니다"


# ── 대본 ────────────────────────────────────────────────
def load(path: str = STORIES) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def story(data: dict, n: int) -> dict:
    for s in data["stories"]:
        if s["id"] == n:
            return s
    raise SystemExit(f"사연 {n} 없음")


def mark(n: int) -> str:
    return f"사연 S{n:03d}"


def hangul(s: str) -> int:
    return len(re.findall(r"[가-힣]", s))


def looks(s: dict) -> dict:
    return {k: v.get("look", k) for k, v in s["cast"].items()}


def prompt(data: dict, s: dict, sc: dict) -> str:
    return f"{data['style']}, {sc.get('place') or s['place']}, " + sc["shot"].format(**looks(s))


def speech_chars(s: dict) -> int:
    return sum(len(re.sub(r"\s", "", sc["say"])) for sc in s["scenes"])


def problems(data: dict) -> list[str]:
    out = []
    ids = [s["id"] for s in data["stories"]]
    if ids != list(range(1, len(ids) + 1)):
        out.append(f"번호가 1부터 이어지지 않는다: {ids}")
    slugs = [s["slug"] for s in data["stories"]]
    if len(slugs) != len(set(slugs)):
        out.append("slug 중복")
    for s in data["stories"]:
        k = f"[{s['id']}]"
        if len(s["top"]) != 2 or any(hangul(t) > TOP_MAX for t in s["top"]):
            out.append(f"{k} 위 제목 두 줄·줄당 한글 {TOP_MAX}자 이내: {s['top']}")
        if not s["title"] or len(s["title"]) > 90:
            out.append(f"{k} 제목 90자 이내: {len(s['title'])}")
        if speech_chars(s) > SPEECH_MAX:
            out.append(f"{k} 대사 {speech_chars(s)}자 > {SPEECH_MAX}(1분 넘을 수 있음)")
        moves = [sc for sc in s["scenes"] if sc.get("move")]
        if len(moves) > MOVE_MAX:
            out.append(f"{k} 영상 장면 {len(moves)} > {MOVE_MAX}")
        for sc in moves:
            if not sc["move"].startswith("static camera") or "subtle" not in sc["move"]:
                out.append(f"{k} 영상 지시는 'static camera … subtle' (흔들림 방지): {sc['move'][:40]}")
        if not 6 <= len(s["scenes"]) <= 10:
            out.append(f"{k} 장면 수 {len(s['scenes'])}")
        for i, sc in enumerate(s["scenes"]):
            who = s["cast"].get(sc["who"])
            if not who:
                out.append(f"{k}#{i} 배역 없음: {sc['who']}")
            elif who.get("voice") not in VOICES:
                out.append(f"{k}#{i} 목소리 {who.get('voice')}")
            if not sc["say"].strip() or not sc["sub"].strip() or len(sc["sub"]) > SUB_MAX:
                out.append(f"{k}#{i} 자막 1~{SUB_MAX}자: {sc['sub']!r}")
            try:
                p = prompt(data, s, sc)
            except (KeyError, IndexError) as e:
                out.append(f"{k}#{i} 그림 지시의 {{{e}}} 배역 없음")
                continue
            if "{" in p or any(b in (p + sc.get("move", "")).lower() for b in BANNED_PROMPT):
                out.append(f"{k}#{i} 그림 지시에 남은 괄호 또는 폰: {p[:80]}")
    return out


# ── 올린 기록 ───────────────────────────────────────────
def read_ledger(path: str = LEDGER) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_ledger(led: dict, path: str = LEDGER) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def due(data: dict, led: dict, seen: set[str] | None = None) -> int | None:
    seen = seen or set()
    for s in data["stories"]:
        if str(s["id"]) not in led and mark(s["id"]) not in seen:
            return s["id"]
    return None


def yt_service():
    """같은 채널의 youtube 스코프 토큰(token_novel). 없으면 None — 그때는 ledger 만 본다."""
    try:
        import upload_youtube_novel as U
        return U.get_service()
    except BaseException as e:  # noqa: BLE001 — 토큰 없을 때 SystemExit 도 삼킨다
        print(f"   (유튜브 확인 생략: {str(e)[:80]})", file=sys.stderr)
        return None


def channel_marks(yt, playlist_title: str) -> set[str]:
    """사연 재생목록 + 최근 업로드 50개에서 '사연 S001' 표식을 모은다(캐시가 날아가도 두 번 안 올리게)."""
    found = set()
    if yt is None:
        return found
    pls = []
    try:
        import upload_youtube_novel as U
        pid = U.find_playlist(yt, playlist_title)
        if pid:
            pls.append(pid)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 재생목록 조회 실패: {e}", file=sys.stderr)
    try:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        pls.append(ch["contentDetails"]["relatedPlaylists"]["uploads"])
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 업로드 목록 조회 실패: {e}", file=sys.stderr)
    for pid in pls:
        try:
            items = yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50).execute().get("items", [])
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ {pid} 조회 실패: {e}", file=sys.stderr)
            continue
        for it in items:
            text = (it["snippet"].get("description") or "") + " " + (it["snippet"].get("title") or "")
            found.update(re.findall(r"사연 S\d{3}", text))
    return found


# ── Spark ───────────────────────────────────────────────
def _get(path: str, timeout: int = 30) -> dict:
    import requests
    return requests.get(f"{wbspark._base()}{path}", headers=wbspark._headers(), timeout=timeout).json()


def job(payload: dict, timeout: int = 300, poll: float = 5.0) -> tuple[str | None, dict | None]:
    """제출 → 끝날 때까지. 응답 없음이 세 번 이어지면 서버가 힘든 것으로 보고 손을 뗀다."""
    import requests
    try:
        r = requests.post(f"{wbspark._base()}/jobs", json=payload, headers=wbspark._headers(), timeout=30)
        jid = r.json().get("job_id")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ {payload['type']} 제출 실패: {e}")
        return None, None
    t0, errs = time.time(), 0
    while time.time() - t0 < timeout:
        time.sleep(poll)
        try:
            d = _get(f"/jobs/{jid}", 60)
            errs = 0
        except Exception as e:  # noqa: BLE001
            errs += 1
            print(f"   ⚠️ 응답 없음 {errs}/3: {str(e)[:60]}")
            if errs >= 3:
                return jid, {"status": "unreachable"}
            continue
        if d.get("status") in ("done", "error", "failed"):
            print(f"   {payload['type']} {d.get('status')} · {d.get('model')} · {round(time.time() - t0)}초")
            return jid, d
    return jid, {"status": "timeout"}


def fetch(jid: str, path: str) -> bool:
    import requests
    try:
        f = requests.get(f"{wbspark._base()}/jobs/{jid}/file", headers=wbspark._headers(), timeout=300)
        if f.status_code != 200 or not f.content:
            return False
        with open(path, "wb") as fp:
            fp.write(f.content)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 파일 받기 실패: {e}")
        return False


def wait_idle(limit: int = IDLE_WAIT) -> bool:
    t0 = time.time()
    while True:
        try:
            q = _get("/queue", 20)
            if q.get("running", 1) == 0 and q.get("waiting", 1) == 0:
                return True
            print(f"   서버 사용 중 {q} — 기다림")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️ 대기열 확인 실패: {str(e)[:60]}")
        if time.time() - t0 > limit:
            return False
        time.sleep(20)


# ── 화면 ────────────────────────────────────────────────
FONT_PATHS = (
    "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
)


def font(size: int):
    from PIL import ImageFont
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    raise SystemExit("한글 굵은 글꼴 없음(fonts-nanum)")


def _wrap(d, text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for w_ in text.split(" "):
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) > width and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    return lines + [cur]


def overlay(top: list[str], sub: str, out: str) -> str:
    """위 제목(늘 보임) + 장면 자막을 한 장의 투명 PNG 로. 자막은 오른쪽 버튼 열(x>960)·아래 설명(y>1440)을 피한다."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("RGBA", (W, 560), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for y in range(560):
        bd.line([(0, y), (W, y)], fill=(0, 0, 0, int(215 * (1 - y / 560) ** 1.4)))
    im.alpha_composite(band)
    d = ImageDraw.Draw(im)
    size = 86
    while size > 60 and max(d.textlength(t, font=font(size)) for t in top) > W - 120:
        size -= 2
    f = font(size)
    for k, (t, col) in enumerate(zip(top, ((255, 255, 255), (255, 216, 77)))):
        tw = d.textlength(t, font=f)
        d.text(((W - tw) / 2, 190 + k * (size + 22)), t, font=f, fill=col, stroke_width=8, stroke_fill=(0, 0, 0))
    size = 72                   # 두 줄 · 너비 820(+테두리) 안에 들 때까지 줄인다(띄어쓰기 없는 긴 낱말도)
    while True:
        fs = font(size)
        lines = _wrap(d, sub, fs, 820)
        if size <= 48 or (len(lines) <= 2 and max(d.textlength(x, font=fs) for x in lines) <= 820):
            break
        size -= 4
    y = 1180 if len(lines) == 1 else 1140
    col = (255, 236, 140) if sub.startswith('"') else (255, 255, 255)
    for ln in lines:
        tw = d.textlength(ln, font=fs)
        d.text(((W - tw) / 2, y), ln, font=fs, fill=col, stroke_width=7, stroke_fill=(0, 0, 0))
        y += size + 18
    im.save(out)
    return out


def wav_dur(p: str) -> float:
    with wave.open(p) as w:
        return w.getnframes() / w.getframerate()


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("ffmpeg 없음")


def _fit(w: int, h: int) -> str:
    """비율 유지하고 꽉 채운 뒤 가운데 자르기 — 늘이지 않는다(10/2 샘플이 늘어나 있었다)."""
    return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"


def _zoom(nf: int, zin: bool) -> str:
    z = "min(zoom+0.0009,1.12)" if zin else "if(eq(on,0),1.12,max(zoom-0.0009,1.0))"
    return f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{H}:fps={FPS}"


def still_filter(dur: float, zin: bool) -> str:
    return f"[0:v]{_fit(W * 2, H * 2)},{_zoom(int(dur * FPS) + 1, zin)}[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]"


def video_filter(dur: float, cut: float) -> str:
    """영상 앞부분(cut 초) → 그 마지막 프레임에서 이어지는 느린 줌 → 자막."""
    return (f"[0:v]trim=0:{cut},setpts=PTS-STARTPTS,fps={FPS},{_fit(W, H)},unsharp=5:5:0.5,setsar=1[a];"
            f"[1:v]{_fit(W * 2, H * 2)},{_zoom(int((dur - cut) * FPS) + 2, True)},unsharp=5:5:0.5,setsar=1[b];"
            f"[a][b]concat=n=2:v=1:a=0[c];[c][2:v]overlay=0:0,format=yuv420p[v]")


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-ar", "44100", "-ac", "1", "-af", "apad"]


def run(*args: str) -> None:
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", *args], check=True)


# ── 만들기 ──────────────────────────────────────────────
def render(n: int, video: bool = True, data: dict | None = None) -> dict:
    data = data or load()
    s = story(data, n)
    work = os.path.join(OUT, f"{n:03d}_{s['slug']}")
    os.makedirs(work, exist_ok=True)
    size = wbspark.ASPECT_SIZE["9:16"]
    video_ok = video and os.environ.get("SAEYEON_VIDEO", "1") != "0"
    used, parts = [], []
    for i, sc in enumerate(s["scenes"]):
        img, wav = os.path.join(work, f"img{i}.png"), os.path.join(work, f"v{i}.wav")
        vid = os.path.join(work, f"vid{i}.mp4")
        ij = None
        if not os.path.exists(img) or (sc.get("move") and video_ok and not os.path.exists(vid)):
            body = wbspark.image_body(prompt(data, s, sc), model=IMG_MODEL, aspect="9:16", no_llm=True)
            for attempt in range(2):
                ij, d = job(body, timeout=300)
                if d and d.get("status") == "done" and fetch(ij, img):
                    break
                ij = None
            else:
                raise SystemExit(f"그림 {i} 실패 — 오늘은 올리지 않는다")
        if not os.path.exists(wav):
            voice = s["cast"][sc["who"]]["voice"]
            if not any(wbspark.tts(sc["say"], wav, voice) for _ in range(2)):
                raise SystemExit(f"목소리 {i} 실패 — 오늘은 올리지 않는다")
        if sc.get("move") and video_ok and ij and not os.path.exists(vid):
            if wait_idle():
                vj, d = job({"type": "video", "from_job": ij, "fast": True, "no_llm": True, "length": 49,
                             "fps": 16, "mp4": True, "prompt": sc["move"]}, timeout=600, poll=10)
                status = (d or {}).get("status")
                if status == "done" and fetch(vj, vid):
                    pass
                elif status in ("unreachable", "timeout"):
                    print("   ⚠️ 서버가 힘들어 보여 이번 편 남은 영상은 사진으로")
                    video_ok = False
            else:
                print(f"   서버가 {IDLE_WAIT}초 넘게 바빠 영상 대신 사진")
        dur = wav_dur(wav) + GAP
        ov = overlay(s["top"], sc["sub"], os.path.join(work, f"ov{i}.png"))
        part = os.path.join(work, f"part{i}.mp4")
        if os.path.exists(vid):
            hold = os.path.join(work, f"hold{i}.png")
            run("-i", vid, "-vf", f"select='eq(n\\,{round(VIDEO_CUT * 24)})'", "-frames:v", "1", hold)
            run("-i", vid, "-i", hold, "-i", ov, "-i", wav, "-filter_complex", video_filter(dur, VIDEO_CUT),
                "-map", "[v]", "-map", "3:a", "-t", f"{dur:.2f}", *ENC, part)
            used.append(i)
        else:
            run("-loop", "1", "-i", img, "-i", ov, "-i", wav, "-filter_complex", still_filter(dur, i % 2 == 0),
                "-map", "[v]", "-map", "2:a", "-t", f"{dur:.2f}", *ENC, part)
        parts.append((part, dur))
        print(f"  {i + 1}/{len(s['scenes'])} {'영상' if i in used else '사진'} {dur:.1f}초 · {sc['sub']}")
    lst = os.path.join(work, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p, _ in parts)
    final = os.path.join(OUT, f"saeyeon_{n:03d}.mp4")
    run("-f", "concat", "-safe", "0", "-i", lst, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100",
        "-c:v", "copy", "-c:a", "aac", final)
    sheet = os.path.join(OUT, f"saeyeon_{n:03d}_sheet.jpg")
    t, picks = 0.0, []
    for _, dur in parts:
        picks.append(t + dur * 0.6)
        t += dur
    sel = "+".join(f"between(t\\,{p:.2f}\\,{p + 0.05:.2f})" for p in picks)
    run("-i", final, "-vf", f"select='{sel}',scale=216:-1,tile={len(picks)}x1", "-frames:v", "1", "-vsync", "0", sheet)
    m = meta(s) | {"id": n, "video": final, "sheet": sheet, "duration": round(t, 1), "moving": used}
    with open(os.path.join(OUT, f"saeyeon_{n:03d}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    print(f"✅ {final} · {t:.1f}초 · 영상 장면 {used or '없음'}")
    return m


def meta(s: dict) -> dict:
    desc = (f"{s['title']}\n\n"
            "※ 창작된 이야기입니다. 그림·영상·목소리는 AI로 만들었습니다.\n"
            "여러분이라면 어떻게 하셨을까요? 댓글로 들려주세요 🙏\n\n"
            "#사연 #사이다사연 #감동사연 #인생이야기 #shorts\n\n"
            f"{mark(s['id'])}")
    return {"title": s["title"][:100], "description": desc, "tags": TAGS}


def upload(n: int) -> dict:
    data = load()
    s = story(data, n)
    led = read_ledger()
    if str(n) in led:
        print(f"이미 올림(ledger): {led[str(n)]}")
        return led[str(n)]
    yt = yt_service()
    if mark(n) in channel_marks(yt, data["playlist"]):
        print(f"이미 채널에 있음: {mark(n)} — 기록만 남긴다")
        led[str(n)] = {"url": "", "at": dt.datetime.now().isoformat(timespec="seconds"), "note": "seen"}
        write_ledger(led)
        return led[str(n)]
    with open(os.path.join(OUT, f"saeyeon_{n:03d}_meta.json"), encoding="utf-8") as f:
        m = json.load(f)
    import upload_youtube_novel as U
    privacy = os.environ.get("SAEYEON_PUBLISH", "public")
    res = U.publish(m["video"], m["title"], m["description"], privacy, playlist_title=data["playlist"],
                    tags=m["tags"], category_id="24", synthetic=True, audio_language="ko",
                    default_language="ko", i18n_langs=[], playlist_description=PLAYLIST_DESC)
    led[str(n)] = {"url": res["url"], "at": dt.datetime.now().isoformat(timespec="seconds"),
                   "privacy": res.get("privacy"), "moving": m.get("moving")}
    write_ledger(led)
    print(f"✅ 사연 {n} 업로드: {res['url']}")
    return led[str(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description="사연 쇼츠")
    ap.add_argument("cmd", choices=["check", "due", "render", "upload"])
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    data = load()
    if a.cmd == "check":
        bad = problems(data)
        for b in bad:
            print("✗", b)
        print(f"{'❌' if bad else '✅'} 사연 {len(data['stories'])}편 · 문제 {len(bad)}")
        return 1 if bad else 0
    if a.cmd == "due":
        n = due(data, read_ledger(), channel_marks(yt_service(), data["playlist"]))
        print(n or "")
        return 0
    if not a.n:
        ap.error("편 번호가 필요하다")
    if a.cmd == "render":
        render(a.n, video=not a.no_video, data=data)
    else:
        upload(a.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
