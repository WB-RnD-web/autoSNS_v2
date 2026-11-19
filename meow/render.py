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
# ★11/14 첫 1초(사용자 '첫 1초도 고쳐줘') — 11/7 호박파이: 쇼츠 피드에서 본 사람의 69.9% 가 넘겼다(계속 시청 30.1%).
#   영상이 거의 멈춘 그림으로 시작하고 변신·반전은 두 번째 컷(4.5초쯤)에야 나온다. → 마지막 컷에서 '영상 첫 화면과
#   가장 다른 순간'을 코드가 찾아 TEASE 초만큼 맨 앞에 먼저 보여 주고(결말 미리 보기) 본편으로 돌아간다.
#   concept 에 "tease": false 면 끈다. 처음 화면과 차이가 TEASE_MIN_DIFF(0~255 평균)보다 작으면 미리 볼 게 없어 끈다.
TEASE = 0.8
TEASE_MIN_DIFF = 3.0
IMG_W, IMG_H = 768, 1344           # 5b 그림(5B 가 넓이 640×640 안으로 줄인다)
V14_W, V14_H = 720, 1280           # 14b 그림 = 완성본 크기(세로 0.8 미만 → 서버가 480×832 로 만들어 720×1280 으로)
HD_TIMEOUT = 5400                  # 한 컷 13분 + GPU 기다림 최대 약 1시간
HD_RETRY, HD_RETRY_WAIT = 2, 300   # 열 안전장치로 멈추면(status=error) 5분 쉬고 다시
FORMATS = {"morph", "dance", "meme", "game"}
# ★11/19 효과(사용자: '이펙트가 안 느껴진다' → 효과판 견본이 '더 낫다'): 기획이 컷마다 효과음(sfx)·그 순간(beat)·강조(hit)·
#   컷 자막(caption)을 정하면, 조립이 그 순간에 효과음을 얹고 hit 컷은 줌인·번쩍·흔들림을 넣는다. 끄기: MEOW_FX=0(예전 그대로).
SFX_DIR = os.path.join(HERE, "sfx")
FX_MUSIC_VOL = 0.5                 # 효과음이 있으면 음악을 반쯤 줄인다(효과음이 묻히지 않게 — 11/19 효과판)
SHOT_CAP_MAX = 24                  # 컷 자막(펀치라인) 글자 수
SHOT_CAP_COLOR = "0xFFE14D"        # 컷 자막은 노란색 · 조금 크게(첫 자막과 구분)
HIT_ZOOM, HIT_ZOOM_SEC = 0.15, 0.5     # hit: 그 순간 1.15배로 확 당겼다가 0.5초에 걸쳐 돌아온다
HIT_SHAKE_SEC, HIT_SHAKE_PX = 0.3, 18  # 흔들림(가로 18px · 세로 12px)
HIT_FLASH_SEC = 0.08                   # 흰 번쩍
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


# ★11/19 자막 글꼴(Pretendard)에 이모지가 없어 'The big tree just lit up 🎄' 의 🎄 가 네모(□)로 그려졌다.
#   화면 자막에서만 그림 글자를 뺀다(유튜브 제목·설명의 이모지는 그대로 — 거기선 제대로 보인다).
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\uFE0E\uFE0F\u200D\u20E3]")


def screen_text(text: str) -> str:
    """화면에 그릴 자막 — 이모지를 빼고 빈칸을 하나로."""
    return " ".join(EMOJI.sub(" ", text).split())


def wrap(text: str, width: int = 20) -> list[str]:
    """자막 줄 나누기. 두 줄이면 길이를 맞춘다 — 앞에서부터 꽉 채우면 'Wait… this bun has / ears' 처럼
    마지막 한 단어만 넘어간다(11/09 매일판 시험). 두 줄로 안 되면 앞에서부터 채운다(검사가 세 줄을 막는다).
    이모지는 글꼴에 없어 네모로 나오므로 먼저 뺀다(screen_text)."""
    words = screen_text(text).split()
    if len(" ".join(words)) <= width:
        return [" ".join(words)] if words else []
    best, score = None, None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        if len(a) > width or len(b) > width:
            continue
        # 긴 줄이 짧을수록 · 문장부호 뒤에서 끊으면 덤('Leg day? / Never heard of it') · 같으면 윗줄이 긴 쪽
        sc = max(len(a), len(b)) - (6 if a[-1] in ".?!,…" else 0)
        if score is None or sc <= score:
            best, score = (a, b), sc
    if best:
        return list(best)
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def sfx_lib() -> dict:
    return load(os.path.join(SFX_DIR, "sfx.json"))


def fx_on(c: dict) -> bool:
    """이 편에 효과가 있나(효과음·hit·컷 자막·배경 소리 중 하나라도) — MEOW_FX=0 이면 늘 아니다(예전 조립 그대로)."""
    if os.environ.get("MEOW_FX", "1") == "0":
        return False
    return bool(c.get("ambience")) or any(s.get("sfx") or s.get("hit") or s.get("caption") for s in c.get("shots") or [])


def beat_shots(c: dict) -> list[int]:
    """순간(beat)을 찾아야 하는 컷(1부터) — 효과음이나 hit 가 있는 컷."""
    return [i for i, s in enumerate(c.get("shots") or [], 1) if s.get("sfx") or s.get("hit")]


def sfx_files(c: dict) -> set[str]:
    lib = sfx_lib()
    out = {lib["sounds"][n]["file"] for s in c.get("shots") or [] for n in s.get("sfx") or [] if n in lib["sounds"]}
    if c.get("ambience") in lib["ambience"]:
        out.add(lib["ambience"][c["ambience"]]["file"])
    return out


def sfx_credit(c: dict, short: bool = False) -> str:
    """CC BY 효과음을 썼으면 표기 한 줄(CC0 은 표기 의무 없음) · 안 썼으면 빈 글."""
    if not fx_on(c):
        return ""
    src = sfx_lib()["sources"]
    by = sorted({(v["title"], v["author"], v["license"]) for f, v in src.items() if f in sfx_files(c) and v["license"] != "CC0"})
    if short:
        return " · ".join(f"🔊 {a} · {lic}" for _, a, lic in by)
    return " · ".join(f'Sound: "{t}" {a} (opengameart.org). Licensed under Creative Commons: By Attribution 4.0 License '
                      f"http://creativecommons.org/licenses/by/4.0/" if lic == "CC BY 4.0" else f'Sound: "{t}" {a}. {lic}'
                      for t, a, lic in by)


def check_fx(c: dict) -> list[str]:
    errs, cid, lib, hits = [], c.get("id", "?"), sfx_lib(), 0
    for i, s in enumerate(c["shots"]):
        fx = s.get("sfx") or []
        if not isinstance(fx, list) or len(fx) > 2:
            errs.append(f"{cid} 컷{i + 1}: sfx 는 0~2개 목록")
            fx = []
        for n in fx:
            if n not in lib["sounds"]:
                errs.append(f"{cid} 컷{i + 1}: 모르는 sfx '{n}'({'/'.join(lib['sounds'])})")
        if (fx or s.get("hit")) and not str(s.get("beat") or "").strip():
            errs.append(f"{cid} 컷{i + 1}: sfx·hit 가 있으면 beat(그 순간 설명)가 있어야 한다")
        hits += bool(s.get("hit"))
        if s.get("caption") is not None:
            t = screen_text(str(s["caption"]))
            if i == 0:
                errs.append(f"{cid} 컷1: 첫 컷 자막은 편의 caption — 컷 caption 은 둘째 컷부터")
            elif not t or len(t) > SHOT_CAP_MAX or len(wrap(t)) > 2:
                errs.append(f"{cid} 컷{i + 1}: 컷 caption 은 1~{SHOT_CAP_MAX}자(이모지 빼고)")
    if hits > 1:
        errs.append(f"{cid}: hit 는 한 컷만")
    if c.get("ambience") and c["ambience"] not in lib["ambience"]:
        errs.append(f"{cid}: 모르는 ambience '{c['ambience']}'({'/'.join(lib['ambience'])})")
    return errs


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
    return errs + check_fx(c)


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


DOWN_AFTER = 600                   # 게이트웨이가 이만큼(초) 내내 안 닿으면 '스파크 꺼짐'(정전·재부팅) — 다음 실행에 맡긴다


def _job(body: dict, out: str | None, timeout: int = 1500, down_after: int = DOWN_AFTER) -> dict:
    """작업을 넣고 끝날 때까지 기다린다 → 마지막 상태(job_id · 서버가 실제로 쓴 model·크기·길이…).
    스파크에 아예 안 닿으면(접수 실패 · 10분 내내 끊김) SparkDown — 실패가 아니라 다음 실행이 잇는다(11/18 정전 대비)."""
    requests, base, headers = _spark()
    try:
        r = requests.post(f"{base}/jobs", json=body, headers=headers, timeout=120)
    except requests.RequestException as e:
        raise SparkDown(f"Spark 접수 안 됨: {str(e)[:150]}") from None
    if r.status_code in (502, 503, 504):
        raise SparkDown(f"Spark 게이트웨이 HTTP {r.status_code}")
    if r.status_code >= 400:
        raise RuntimeError(f"Spark {body['type']} 거절 HTTP {r.status_code}: {r.text[:300]}")
    jid = r.json()["job_id"]
    t0, lost = time.time(), None
    while time.time() - t0 < timeout:
        try:
            g = requests.get(f"{base}/jobs/{jid}", headers=headers, timeout=30)
            d = g.json() if g.ok else {}
        except (requests.RequestException, ValueError):   # 게이트웨이가 다시 켜지는 몇 초 — 쉬고 다시 본다
            lost = lost or time.time()
            if time.time() - lost >= down_after:
                raise SparkDown(f"Spark {body['type']} {jid} — {down_after // 60}분 내내 안 닿음") from None
            time.sleep(10)
            continue
        lost = None
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


class SparkDown(QuietHours):
    """스파크에 닿지 않는다(정전·재부팅 · 11/18 09~12시 정전 예고) — 조용한 시간과 같이 75로 끝내고 다음 실행이 잇는다."""

    def __init__(self, why: str = ""):
        super().__init__()
        self.why = why
        print(f"⏸️ 스파크 꺼짐 — {why} (다음 실행이 잇는다)", flush=True)


def wait_quiet(max_min: int, now: dt.datetime | None = None, sleep=time.sleep) -> bool:
    """조용한 시간(05:45~08:00 KST)이고 08:00 까지 max_min 분 안이면 기다렸다가 돌아온다(참).
    GitHub 예약이 몇 시간씩 늦어 06~07시에 시작한 실행이 75로 끝나면 다음 예비는 낮에야 돈다(11/11~13 실측) — 그래서 기다린다."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    if not quiet_hours(now, ahead_min=20):
        return False
    end = dt.datetime.combine(now.date(), dt.time(8, 0), KST)
    wait = (end - now).total_seconds()
    if wait <= 0 or wait > max_min * 60:
        return False
    print(f"⏳ 조용한 시간 — 08:00 KST 까지 {int(wait // 60)}분 기다렸다가 바로 시작", flush=True)
    sleep(wait + 30)
    return True


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
    on = fx_on(c)
    for i, s in enumerate(c["shots"]):
        # ★11/19 hit 컷은 겹치지 않고 바로 자른다 — 겹치는 동안 번쩍·줌이 오면 두 화면이 뒤섞여 흐려진다(견본 실측)
        x = float(s.get("xfade") or 0) if i and not (on and s.get("hit")) else 0.0
        dur = round(float(s.get("sec") or e["src"]) * e["slow"], 3)
        start = t - x
        rows.append({"dur": dur, "xfade": x, "start": round(start, 3)})
        t = start + dur
    return rows


def total(c: dict) -> float:
    """본편 길이(결말 미리 보기 TEASE 는 빼고 — build 가 더한다)."""
    p = plan(c)
    return round(p[-1]["start"] + p[-1]["dur"], 3)


def _gray(path: str, sec: float, fps: int = 8, w: int = 32, h: int = 56) -> list[bytes]:
    """클립 앞 sec 초를 fps 장씩 작은 흑백으로(비교용)."""
    r = subprocess.run([ffmpeg(), "-v", "error", "-t", str(sec), "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    n, b = w * h, r.stdout
    return [b[i:i + n] for i in range(0, len(b) - n + 1, n)]


def tease_at(first_clip: str, last_clip: str, src: float, slow: float, fps: int = 8) -> float | None:
    """마지막 컷 안에서 영상 첫 화면과 가장 다른 순간 — 그 순간부터 자를 시작 초(원본 클립 기준 · 끝을 넘으면 당긴다).
    차이가 TEASE_MIN_DIFF 보다 작으면 None(미리 볼 게 없다)."""
    ref = _gray(first_clip, 0.2, fps)[:1]
    fr = _gray(last_clip, src, fps)
    if not ref or not fr:
        return None
    r0 = ref[0]
    diffs = [sum(abs(a - b) for a, b in zip(r0, f)) / len(f) for f in fr]
    k = max(range(len(diffs)), key=diffs.__getitem__)
    if diffs[k] < TEASE_MIN_DIFF:
        return None
    span = TEASE / slow          # 그 순간부터(가운데로 자르면 앞 절반이 아직 안 바뀐 화면 — 11/14 합성 클립 실측)
    return round(min(k / fps, max(src - span, 0.0)), 3)


def motion_peak(clip: str, src: float, fps: int = 16) -> float:
    """클립에서 화면이 가장 크게 바뀌는 순간(초) — 순간 찾기(비전)가 없을 때 대신 쓴다. 앞 0.2초는 뺀다."""
    fr = _gray(clip, src, fps)
    d = [sum(abs(a - b) for a, b in zip(fr[k], fr[k - 1])) / len(fr[k]) for k in range(1, len(fr))]
    if not d:
        return 0.0
    sm = [sum(d[max(0, k - 1):k + 2]) / len(d[max(0, k - 1):k + 2]) for k in range(len(d))]
    lo = min(len(sm) - 1, int(0.2 * fps))
    k = max(range(lo, len(sm)), key=sm.__getitem__)
    return round((k + 1) / fps, 3)


def beat_times(c: dict, clips: list[str], beats: dict | None = None) -> dict[int, float]:
    """컷(1부터) → 클립 안 순간(초). beats(비전이 찾은 것 · {"1": 초})가 없으면 움직임이 가장 큰 순간."""
    e, out = eng(c), {}
    for i in beat_shots(c):
        src = float(c["shots"][i - 1].get("sec") or e["src"])
        t = (beats or {}).get(str(i))
        if t is None:
            try:
                t = motion_peak(clips[i - 1], src)
            except (subprocess.CalledProcessError, OSError, IndexError):
                t = src / 2
        out[i] = round(min(max(float(t), 0.0), max(src - 0.05, 0.0)), 3)
    return out


def fx_events(c: dict, bt: dict[int, float], t0: float = 0.0) -> list[tuple[str, float, float]]:
    """효과음 (파일, 영상 안 시각, 크기) — 컷 순간에서 lead 만큼 먼저(휙은 동작 직전에) · 배경 소리는 0초부터."""
    lib, p, slow, ev = sfx_lib(), plan(c), eng(c)["slow"], []
    if c.get("ambience") in lib["ambience"]:
        a = lib["ambience"][c["ambience"]]
        ev.append((a["file"], 0.0, float(a["vol"])))
    for i, s in enumerate(c["shots"], 1):
        for n in s.get("sfx") or []:
            x = lib["sounds"][n]
            at = t0 + p[i - 1]["start"] + bt.get(i, 0.0) * slow - float(x.get("lead", 0))
            ev.append((x["file"], round(max(at, 0.0), 3), float(x["vol"])))
    return ev


def _hit(t: float) -> str:
    """hit 컷(1080×1920 이 된 뒤)에 붙이는 줌인·흔들림·번쩍 — t = 컷 안 시각(초). 흔들리는 동안엔 늘 1.06배 넘게 당겨져 있어
    가장자리가 비지 않는다(흔들림 0.3초 < 줌 0.5초)."""
    z = f"(1+{HIT_ZOOM}*if(between(t\\,{t}\\,{round(t + HIT_ZOOM_SEC, 3)})\\,1-(t-{t})/{HIT_ZOOM_SEC}\\,0))"
    sh = f"between(t\\,{t}\\,{round(t + HIT_SHAKE_SEC, 3)})"
    return (f"scale=w='{W}*{z}':h=-2:eval=frame,"
            f"crop={W}:{H}:x='(in_w-{W})/2+if({sh}\\,{HIT_SHAKE_PX}*sin(t*90)\\,0)':"
            f"y='(in_h-{H})/2+if({sh}\\,{int(HIT_SHAKE_PX * 2 / 3)}*cos(t*110)\\,0)',"
            f"eq=brightness='if(between(t\\,{t}\\,{round(t + HIT_FLASH_SEC, 3)})\\,0.45\\,0)':eval=frame,")


def captions(c: dict, t0: float = 0.0) -> list[dict]:
    """화면 자막 목록 — 편 caption 은 처음부터, 컷 caption 이 있으면 그 컷 시작부터 바꾼다(노란색 · 조금 크게)."""
    p, out = plan(c), []
    rows = [(0.0, c["caption"], False)]
    if fx_on(c):
        rows += [(t0 + p[i]["start"], s["caption"], True) for i, s in enumerate(c["shots"]) if i and s.get("caption")]
    for k, (st, text, beat) in enumerate(rows):
        end = rows[k + 1][0] if k + 1 < len(rows) else None
        out.append({"start": round(st, 3), "end": None if end is None else round(end, 3), "lines": wrap(text),
                    "beat": beat, "key": "cap" if k == 0 else f"cap_s{k}_"})
    return out


def filtergraph(c: dict, n_inputs: int, tease_start: float | None = None, bt: dict[int, float] | None = None,
                events: list | None = None) -> str:
    """tease_start 가 있으면 입력 len(shots) 번 = 마지막 컷 클립 한 번 더(결말 미리 보기) · 음악은 그다음 입력
    (★11/19 효과음 events 가 있으면 음악 뒤에 효과음 입력이 차례로 — 없으면 음악이 맨 끝 입력 그대로)."""
    e, p = eng(c), plan(c)
    slow, fps = e["slow"], e["fps"]
    on = fx_on(c)
    hit_i = next((i for i, s in enumerate(c["shots"], 1) if s.get("hit")), None) if on else None
    parts = []
    for i, r in enumerate(p):
        # 세로 클립 → 1080x1920: 높이를 맞춰 키운 뒤 가로를 가운데로 자른다
        src = round(r["dur"] / slow, 3)
        fx = _hit(round((bt or {}).get(i + 1, 0.0) * slow, 3)) if hit_i == i + 1 else ""
        parts.append(f"[{i}:v]trim=0:{src},setpts=(PTS-STARTPTS)*{slow},fps={fps},"
                     f"scale=-2:{H}:flags=lanczos,crop={W}:{H},{fx}setsar=1,format=yuv420p,settb=1/{fps}[v{i}]")
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
    if tease_start is not None:
        k, src = len(p), round(TEASE / slow, 3)
        parts.append(f"[{k}:v]trim={tease_start}:{round(tease_start + src, 3)},setpts=(PTS-STARTPTS)*{slow},fps={fps},"
                     f"scale=-2:{H}:flags=lanczos,crop={W}:{H},setsar=1,format=yuv420p,settb=1/{fps}[vt]")
        parts.append(f"[vt][{acc}]concat=n=2:v=1:a=0,settb=1/{fps}[vtz]")
        acc, tl = "vtz", round(tl + TEASE, 3)
    # 자막은 줄마다 drawtext 하나 — 한 번에 그리면 줄이 가운데로 안 모인다 · ★11/19 컷 자막은 그 컷부터(enable)
    dts = []
    for cp in captions(c, TEASE if tease_start is not None else 0.0):
        size = int(CAP_SIZE * 1.15) if cp["beat"] else CAP_SIZE
        color = SHOT_CAP_COLOR if cp["beat"] else "white"
        if cp["end"] is not None and cp["start"] > 0:
            when = f":enable='between(t\\,{cp['start']}\\,{cp['end']})'"
        elif cp["end"] is not None:
            when = f":enable='lt(t\\,{cp['end']})'"
        elif cp["start"] > 0:
            when = f":enable='gte(t\\,{cp['start']})'"
        else:
            when = ""
        for k in range(len(cp["lines"])):
            name = f"{cp['key']}{k}.txt"
            dts.append(f"drawtext=fontfile=font.ttf:textfile={name}:fontsize={size}:fontcolor={color}:borderw=8:"
                       f"bordercolor=black:x=(w-text_w)/2:y={int(H * 0.10 + k * size * 1.25)}{when}")
    parts.append(f"[{acc}]" + ",".join(dts) + ",format=yuv420p[vout]")
    ev = events or []
    a = n_inputs - 1 - len(ev)
    if not ev:
        parts.append(f"[{a}:a]atrim=0:{tl},asetpts=PTS-STARTPTS,afade=t=in:d=0.05,"
                     f"afade=t=out:st={max(tl - 0.7, 0)}:d=0.7[aout]")
        return ";".join(parts)
    parts.append(f"[{a}:a]atrim=0:{tl},asetpts=PTS-STARTPTS,volume={FX_MUSIC_VOL},afade=t=in:d=0.05,"
                 f"afade=t=out:st={max(tl - 0.7, 0)}:d=0.7[m]")
    for k, (_f, at, vol) in enumerate(ev):
        parts.append(f"[{a + 1 + k}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={vol},"
                     f"adelay={int(round(at * 1000))}:all=1,apad=whole_dur={tl}[x{k}]")
    parts.append("[m]" + "".join(f"[x{k}]" for k in range(len(ev))) +
                 f"amix=inputs={len(ev) + 1}:normalize=0:duration=first,alimiter=limit=0.95[aout]")
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


def build(c: dict, beats: dict | None = None) -> dict:
    """beats = 비전이 찾은 컷 순간({"1": 초} · qa_api.find_beats) — 없으면 움직임이 가장 큰 순간."""
    d = os.path.join(WORK, stem(c))
    clips = [clip_path(c, i) for i in range(1, len(c["shots"]) + 1)]
    miss = [p for p in clips if not os.path.exists(p)]
    if miss:
        raise SystemExit(f"{stem(c)}: 클립 없음 {len(miss)}개 — gen 먼저")
    os.makedirs(OUT, exist_ok=True)
    shutil.copyfile(font_path(), os.path.join(d, "font.ttf"))
    for cp in captions(c):
        for k, line in enumerate(cp["lines"]):
            with open(os.path.join(d, f"{cp['key']}{k}.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(line)
    t = tracks()[c["track"]]
    fps = eng(c)["fps"]
    video = os.path.abspath(os.path.join(OUT, f"{stem(c)}.mp4"))
    cmd = [ffmpeg(), "-v", "error", "-y"]
    for p in clips:
        cmd += ["-i", os.path.abspath(p)]
    ts = None
    if c.get("tease", True):
        last = c["shots"][-1]
        try:
            ts = tease_at(clips[0], clips[-1], float(last.get("sec") or eng(c)["src"]), eng(c)["slow"])
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"   결말 미리 보기 건너뜀: {e}", flush=True)
    if ts is not None:
        cmd += ["-i", os.path.abspath(clips[-1])]
    cmd += ["-ss", str(t.get("start", 0)), "-i", os.path.join(MUSIC, c["track"])]
    bt, ev = {}, []
    if fx_on(c):
        bt = beat_times(c, clips, beats)
        ev = fx_events(c, bt, TEASE if ts is not None else 0.0)
        for f_, _at, _v in ev:
            cmd += ["-i", os.path.join(SFX_DIR, f_)]
    n_in = len(clips) + (ts is not None) + 1 + len(ev)
    cmd += ["-filter_complex", filtergraph(c, n_in, ts, bt, ev), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video]
    subprocess.run(cmd, check=True, cwd=d)
    tl = round(total(c) + (TEASE if ts is not None else 0), 3)
    # 표지 = 고른 컷의 원본 그림(움직이기 전이라 제일 깨끗하다) · 글자 없이 — 인스타 격자에서 잘리지 않게
    k = int(c.get("cover_shot") or len(c["shots"]))
    cover = video.replace(".mp4", "_cover.jpg")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", os.path.join(d, f"shot{k}.png"), "-vf",
                    f"scale=-2:{H}:flags=lanczos,crop={W}:{H}", "-q:v", "2", cover], check=True)
    sheet = video.replace(".mp4", "_sheet.jpg")
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", video, "-vf",
                    f"fps=2,scale=270:-1,tile={int(tl * 2) + 1}x1", "-frames:v", "1", sheet], check=True)
    meta = {"id": c["id"], "slug": c["slug"], "stem": stem(c), "video": video, "cover": cover, "sheet": sheet,
            "sec": tl, "track": c["track"], "credit": credit(c["track"]), "engine": engine(c), "tease": ts,
            "fx": {"beats": {str(k): v for k, v in bt.items()}, "sounds": [[f_, at] for f_, at, _v in ev],
                   "beat_src": "vision" if beats else "motion", "sfx_credit": sfx_credit(c)} if fx_on(c) else None}
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
