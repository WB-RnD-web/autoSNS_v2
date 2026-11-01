#!/usr/bin/env python3
"""Nine Tails Tales 재개(2026-11) — 얼굴 없는 3D 실화·what-if 쇼츠: 카탈로그 검사 · 편성 · ledger · 업로드.

    python gumiho/tales/story.py check                 # story_catalog.json 전부 검사
    python gumiho/tales/story.py plan                  # 편성표(공개일 · 제목 · 출처 수)
    python gumiho/tales/story.py due [--now 2026-11-04T01:00:00+09:00]   # 지금 만들 편 id(없으면 빈 줄)
    python gumiho/tales/story.py seen 1                # 유튜브에 이미 있으면 0(ledger 에 적는다)
    python gumiho/tales/story.py upload 1              # 렌더 결과를 비공개 + 예약 공개(publishAt)로
렌더는 story_reel.py(그림·목소리·화면 — 무거운 의존성은 거기에만).

왜(10/31 사용자 결정 '2차 수준으로 재개'): 미국에서 얼굴 없는 3D 실화·what-if 쇼츠가 터지는 중(벤치마크 문서
  DL9vxyd…). 옛 쇼츠(34편 중앙값 74회)는 숫자 나열·정지 그림·약한 질문·형식 섞기로 실패했다.
★대본은 미리 다 써 둔다 — 제작 때 LLM 을 부르지 않는다(이 레포 원칙: 코드로 정해진 것만 지켜진다).
  편마다 사실(facts)은 실제로 연 출처(sources) 번호를 단다 · 실존 인물은 공개된 사실만, 얼굴 없는 마네킹으로만 그린다
  (사람을 뜻하는 말이 들어간 그림 프롬프트는 'mannequin' 이 없으면 검사가 막는다) · 아동 공포·가짜 실화·명예훼손 금지.
편성: 월·수·금 22:00 KST(13:00 UTC) 예약 공개. 렌더는 공개 당일 새벽(01:00·03:30 KST, 예비 10:00) — 05:45~08:00 KST 는
  Spark 를 쓰지 않는다(아침 업로드 루틴). 같은 편 두 번 안 올린다: ledger(Actions 캐시) + 설명란 표식 확인 두 겹.
이 모듈은 표준 라이브러리만 쓴다(콘텐츠 재고 tools/runway.py 가 맥박·루틴 환경에서 읽는다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CATALOG = os.path.join(HERE, "story_catalog.json")
OUT = os.path.join(ROOT, "output", "nt_story")
WORK = os.path.join(OUT, ".work")
LEDGER = os.path.join(ROOT, "output", "gumiho", "story_ledger.json")
KST = dt.timezone(dt.timedelta(hours=9))
START = dt.date(2026, 11, 4)          # 첫 공개(수) — 사용자가 머지해야 시작된다
DAYS = (0, 2, 4)                      # 월·수·금
SLOT_UTC = (13, 0)                    # 22:00 KST
QUIET = ((5, 45), (8, 0))             # KST — 아침 업로드 루틴이 Spark 를 쓴다
LATE_DAYS = 2                         # 공개일을 놓쳤으면 이틀까지는 늦게라도(지금+2시간) 올린다
# ★11/01 매일 트렌드 편(trend_api.py — Claude API 가 그날 뜨는 것을 우리 꼴로): 카탈로그 사이 날(화·목·토·일)에 21:30 KST.
#   data/nt-trend/<쓴 날>.json 을 읽기 전용으로 받아 편성에 합친다. 카탈로그 편과 id·표식·ledger 키가 겹치지 않는다
#   (id = 쓴 날 YYYYMMDD · 표식 'Trend <쓴 날>' · 키 'trend_<쓴 날>_<slug>'). 맥박이 따로 세게 시각도 다르다(story3d_trend).
TREND_DIR = os.environ.get("NT_TREND_DIR") or os.path.join(ROOT, "output", "nt_trend")
TREND_START = dt.date(2026, 11, 5)    # 첫 트렌드 공개(목) — 첫 화(11/4 카탈로그) 다음 날
TREND_DAYS = (1, 3, 5, 6)             # 화·목·토·일
TREND_SLOT_UTC = (12, 30)             # 21:30 KST
TREND_AHEAD = 2                       # 쓴 날 +1~+2일 안에 빈 자리가 없으면 그날은 쓰지 않는다(묵은 트렌드가 쌓이지 않게)
PLAYLIST = "True Stories & What Ifs | Nine Tails Tales"
PLAYLIST_DESC = ("Short true stories and what-if questions, retold as faceless 3D reconstructions. "
                 "Every fact is sourced in the description.")
BASE_TAGS = ["shorts", "true story", "what if", "3d animation", "science", "survival", "nine tails tales"]
FORMATS = ("story", "whatif")
WORDS = (110, 200)                    # 내레이션 단어 수(≈ 42~77초)
SHOTS = (12, 32)
HUMAN = re.compile(r"(?i)\b(man|men|woman|women|person|people|boy|girl|child|children|kid|kids|astronauts?|rangers?|"
                   r"pilots?|passengers?|tourists?|crowd|crew|engineers?|family|sprinter|runner|guard|stewardess|sailors?|"
                   r"officers?|figures?|humans?|workers?|students?|scientists?|doctors?|nurses?|hands?|arms?|"
                   r"face|faces|silhouettes?|swimmers?|skydiver|jumper)\b")
PROMPT_BANNED = re.compile(r"(?i)\b(phone|text|letters?|logo|signs?|caption|pixar|disney|marvel|blood|gore|corpse|"
                           r"dead bod(y|ies)|skull|wound)\b")
SAY_BANNED = re.compile(r"(?i)(blood|gore|corpse|decapitat|mutilat|suicid|killed himself|shot himself|subscribe|"
                        r"like and|comment below|#)")
FX = ("none", "float", "dust", "rain", "embers", "smoke", "snow", "spray", "debris")
MOVES = ("hook", "push_in", "pull_out", "pan_left", "pan_right", "drift_left", "drift_right", "tilt_up", "punch",
         "shake", "orbit", "loop_end")
SFX = ("hit", "boom", "thud", "whoosh", "suck", "thunder", "zap", "fire", "drip", "water", "alarm", "radio", "hiss",
       "rumble", "wind", "siren", "heartbeat", "fizz", "crash")
MUSIC = ("space", "storm", "tension", "ocean")
TOKEN = re.compile(r"\{([^|}]*)\|([^}]*)\}|(\S+)")


# ── 카탈로그 ────────────────────────────────────────────
def load(path: str = CATALOG) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def episodes(cat: dict | None = None) -> list[dict]:
    return sorted((cat or load())["episodes"], key=lambda e: e["from"])


def is_trend(e: dict) -> bool:
    return e.get("kind") == "trend"


def load_trends(dir_: str | None = None, quiet_errors: bool = False) -> list[dict]:
    """data/nt-trend 의 트렌드 편(건너뛴 날·검사 실패는 뺀다)."""
    import glob
    out = []
    for p in sorted(glob.glob(os.path.join(dir_ or TREND_DIR, "20??-??-??.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                e = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(e, dict) or e.get("skip") or not is_trend(e):
            continue
        errs = check_episode(e)
        if errs:
            if not quiet_errors:
                print(f"   ✗ 트렌드 편 {os.path.basename(p)} 검사 실패 — 편성에서 뺀다: {errs[:2]}", file=sys.stderr)
            continue
        out.append(e)
    return out


def schedule(cat: dict | None = None, trends: list[dict] | None = None) -> list[dict]:
    """카탈로그(월·수·금 22:00) + 트렌드(화·목·토·일 21:30) — 공개 시각 순."""
    return sorted(episodes(cat) + list(trends or []), key=slot)


def find(key, cat: dict | None = None, trends: list[dict] | None = None) -> dict:
    key = str(key)
    for e in schedule(cat, trends):
        if stem(e) == key or e["slug"] == key or (not is_trend(e) and str(e["id"]) == key.lstrip("0")):
            return e
    raise KeyError(f"편성에 없는 편: {key}")


def stem(e: dict) -> str:
    return f"trend_{e['written']}_{e['slug']}" if is_trend(e) else f"{e['id']:03d}_{e['slug']}"


def cache_keys(key, trends: list[dict] | None = None) -> tuple[str, str]:
    """워크플로 캐시 이름 — (stem, 옛 이름). due 는 stem 을 내니 수동 실행도 stem 으로 맞춘다.
    옛 이름: 카탈로그 편 id 숫자. 11/01 1화 렌더 시험(run 41254007355)이 'nt-story-work-1-' 로 그림을 남겼다."""
    e = find(key, trends=trends)
    return stem(e), ("" if is_trend(e) else str(e["id"]))


def marker(e: dict) -> str:
    """설명란 끝 표식 — ledger 캐시가 날아가도 유튜브에서 같은 편을 찾는다."""
    return f"Nine Tails Tales · Trend {e['written']}" if is_trend(e) else f"Nine Tails Tales · Story {e['id']:03d}"


def trend_slot(written: dt.date, taken: set) -> dt.date | None:
    """D일에 쓴 트렌드 편의 공개일 = D+1 이후(첫 트렌드일 전이면 그날부터) 비어 있는 첫 화·목·토·일.
    TREND_AHEAD 일보다 멀면 None(그날은 쓰지 않는다). 첫 트렌드일 전에 쓴 편은 첫 주(TREND_START+3일) 안이면 받는다."""
    d = max(written + dt.timedelta(days=1), TREND_START)
    while d.weekday() not in TREND_DAYS or d in taken:
        d += dt.timedelta(days=1)
    limit = max(written + dt.timedelta(days=TREND_AHEAD), TREND_START + dt.timedelta(days=3))
    return d if d <= limit else None


def spoken(e: dict) -> str:
    return " ".join(m.group(2) if m.group(3) is None else m.group(3) for sh in e["shots"] for m in TOKEN.finditer(sh["say"]))


def check_episode(e: dict) -> list[str]:
    errs = []
    lab = f"{e.get('id')}:{e.get('slug')}"

    def bad(msg):
        errs.append(f"{lab} {msg}")
    for k in ("id", "slug", "from", "format", "title", "description", "shots", "facts", "sources", "careful", "music"):
        if k not in e:
            bad(f"'{k}' 없음")
    if errs:
        return errs
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", e["slug"]):
        bad("slug 는 소문자·숫자·하이픈")
    try:
        d = dt.date.fromisoformat(e["from"])
        if is_trend(e):
            w = dt.date.fromisoformat(str(e.get("written", "")))
            if d.weekday() not in TREND_DAYS or d < TREND_START or d <= w:
                bad(f"트렌드 편 from {d} 은 {TREND_START} 이후 화·목·토·일 · 쓴 날({w}) 뒤")
            if e["id"] != int(w.strftime("%Y%m%d")):
                bad("트렌드 편 id 는 쓴 날 YYYYMMDD")
            tr = e.get("trend") or {}
            ev = tr.get("evidence") or []
            if not str(tr.get("why_now", "")).strip() or not str(tr.get("pattern", "")).strip() or not 1 <= len(ev) <= 3 \
                    or any(not str(x.get("url", "")).startswith("https://") for x in ev):
                bad("trend: why_now · pattern · evidence 1~3개(https url)")
        else:
            if d.weekday() not in DAYS:
                bad(f"from {d} 은 월·수·금이 아니다")
            if d < START:
                bad(f"from {d} 은 첫 공개일 {START} 전")
            if not isinstance(e["id"], int) or not 1 <= e["id"] <= 999:
                bad("카탈로그 id 는 1~999(트렌드 편 id 와 안 겹치게)")
    except ValueError:
        bad(f"from·written 날짜 형식 {e['from']} / {e.get('written')}")
    if e["format"] not in FORMATS:
        bad(f"format 은 {FORMATS}")
    if e["music"] not in MUSIC:
        bad(f"music 은 {MUSIC}")
    if not 10 <= len(e["title"]) <= 100:
        bad(f"제목 길이 {len(e['title'])}(10~100)")
    if re.search(r"https?://", e["description"]) or len(e["description"]) > 1500:
        bad("설명에 링크를 넣지 않는다(출처는 meta 가 붙인다) · 1500자 이하")
    if not str(e["careful"]).strip():
        bad("careful(조심할 점)이 비었다")
    src = e["sources"]
    if len(src) < 2:
        bad("출처는 2개 이상")
    urls = [s.get("url", "") for s in src]
    if any(not re.fullmatch(r"https://\S+", u) for u in urls) or len(set(urls)) != len(urls):
        bad("출처 url 은 https · 겹치지 않게")
    if any(not s.get("title") or not s.get("used") for s in src):
        bad("출처마다 title·used(무엇에 썼나)")
    if len(e["facts"]) < 3:
        bad("facts 3개 이상")
    for f in e["facts"]:
        if not f.get("claim") or not f.get("src") or any(not isinstance(i, int) or not 0 <= i < len(src) for i in f["src"]):
            bad(f"fact 출처 번호가 틀렸다: {str(f)[:60]}")
    cited = {i for f in e["facts"] for i in f.get("src", [])}
    if len(cited) < len(src):
        bad(f"facts 가 안 쓴 출처가 있다 {sorted(set(range(len(src))) - cited)}")
    ch = e.get("character")
    if ch and (not isinstance(ch.get("seed"), int) or "mannequin" not in ch.get("prompt", "")):
        bad("character 는 seed(정수) + 'mannequin' 이 든 prompt")
    shots = e["shots"]
    if not SHOTS[0] <= len(shots) <= SHOTS[1]:
        bad(f"장면 {len(shots)}개({SHOTS[0]}~{SHOTS[1]})")
    for i, sh in enumerate(shots):
        w = f"장면 {i}"
        if not sh.get("say", "").strip():
            bad(f"{w}: say 없음")
        if SAY_BANNED.search(sh.get("say", "")):
            bad(f"{w}: 금지어 '{SAY_BANNED.search(sh['say']).group(0)}'")
        kinds = [k for k in ("prompt", "edit", "reuse") if k in sh]
        if len(kinds) != 1:
            bad(f"{w}: prompt·edit·reuse 중 하나만({kinds})")
            continue
        if "reuse" in sh:
            j = sh["reuse"]
            if not isinstance(j, int) or not 0 <= j < i or "reuse" in shots[j]:
                bad(f"{w}: reuse {j} 는 앞 장면(그림을 가진 장면)이어야")
        if "edit" in sh and not ch:
            bad(f"{w}: edit 는 character 가 있어야")
        text = sh.get("prompt") or sh.get("edit") or ""
        if PROMPT_BANNED.search(text):
            bad(f"{w}: 그림 금지어 '{PROMPT_BANNED.search(text).group(0)}'(글자 깨짐·상표·잔혹)")
        if "prompt" in sh and HUMAN.search(text) and "mannequin" not in text:
            bad(f"{w}: 사람이 나오면 'mannequin'(얼굴 없는 3D) — '{HUMAN.search(text).group(0)}'")
        if sh.get("move", "push_in") not in MOVES:
            bad(f"{w}: move {sh.get('move')}")
        if sh.get("fx", "none") not in FX:
            bad(f"{w}: fx {sh.get('fx')}")
        if sh.get("sfx") and sh["sfx"] not in SFX:
            bad(f"{w}: sfx {sh['sfx']}")
        if "focus" in sh and (len(sh["focus"]) != 3 or not 0.8 <= sh["focus"][2] <= 1.6):
            bad(f"{w}: focus [x, y, 확대 0.8~1.6]")
        if any(not 0 <= t <= 0.6 for t in sh.get("flash", [])):
            bad(f"{w}: flash 는 장면 앞 0.6초 안에서만(하얀 화면은 짧게)")
        if "video" in sh:
            bad(f"{w}: 5B 영상 클립은 쓰지 않는다(깨짐을 자동으로 못 거른다)")
    if shots:
        if "reuse" in shots[0]:
            bad("첫 장면은 새 그림(결정적 장면)")
        if shots[-1].get("reuse") != 0 or shots[-1].get("move") != "loop_end":
            bad("마지막 장면은 첫 그림으로 돌아간다(reuse 0 · move loop_end — 루프)")
    n = len(spoken(e).split())
    if not WORDS[0] <= n <= WORDS[1]:
        bad(f"내레이션 {n}단어({WORDS[0]}~{WORDS[1]} ≈ 42~77초)")
    return errs


def check(cat: dict | None = None) -> list[str]:
    cat = cat or load()
    eps = cat["episodes"]
    errs = [x for e in eps for x in check_episode(e)]
    ids = [e.get("id") for e in eps]
    if len(set(ids)) != len(ids):
        errs.append("id 가 겹친다")
    if len({e.get("slug") for e in eps}) != len(eps):
        errs.append("slug 가 겹친다")
    froms = [e.get("from") for e in eps]
    if len(set(froms)) != len(froms):
        errs.append("같은 날 두 편")
    if froms != sorted(froms) or ids != sorted(ids):
        errs.append("카탈로그는 id·from 순서대로(끝에만 붙인다)")
    titles = [e.get("title", "").lower() for e in eps]
    if len(set(titles)) != len(titles):
        errs.append("제목이 겹친다")
    return errs


# ── 편성 ────────────────────────────────────────────────
def slot(e: dict) -> dt.datetime:
    d = dt.date.fromisoformat(e["from"])
    return dt.datetime(d.year, d.month, d.day, *(TREND_SLOT_UTC if is_trend(e) else SLOT_UTC), tzinfo=dt.timezone.utc)


def last_date(cat: dict | None = None) -> dt.date | None:
    eps = episodes(cat)
    return dt.date.fromisoformat(eps[-1]["from"]) if eps else None


def left(today: dt.date, cat: dict | None = None) -> int:
    return sum(1 for e in episodes(cat) if dt.date.fromisoformat(e["from"]) >= today)


def is_post_day(d: dt.date) -> bool:
    return d >= START and d.weekday() in DAYS


def quiet(now: dt.datetime) -> bool:
    k = now.astimezone(KST)
    m = k.hour * 60 + k.minute
    return QUIET[0][0] * 60 + QUIET[0][1] <= m < QUIET[1][0] * 60 + QUIET[1][1]


def load_ledger(path: str = LEDGER) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_ledger(led: dict, path: str = LEDGER):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def due(now: dt.datetime, led: dict, cat: dict | None = None, trends: list[dict] | None = None) -> tuple[dict | None, str]:
    """지금 만들 편 — 아직 안 올렸고 · 공개일 전날~당일(공개 30분 전까지) · 놓쳤으면 LATE_DAYS 일까지. 이른 편 먼저.
    카탈로그와 트렌드 편을 공개 시각 순으로 함께 본다(검수에 걸려 안 올린 트렌드 편 = skipped 도 끝난 것)."""
    today = now.astimezone(KST).date()
    for e in schedule(cat, trends):
        rec = led.get(stem(e), {})
        if rec.get("short") or rec.get("skipped"):
            continue
        d = dt.date.fromisoformat(e["from"])
        if today < d - dt.timedelta(days=1):
            return None, f"다음 편 {stem(e)} 은 {d - dt.timedelta(days=1)} 부터"
        if now < slot(e) - dt.timedelta(minutes=30):
            return e, f"{stem(e)} · 예약 {slot(e):%Y-%m-%d %H:%M}Z"
        if today <= d + dt.timedelta(days=LATE_DAYS):
            return e, f"{stem(e)} · 공개 시각을 놓쳤다 → 늦게라도(지금+2시간)"
    return None, "남은 편 없음 — story_catalog.json 끝에 편을 붙일 것"


def publish_time(e: dict, mode: str, now: dt.datetime | None = None) -> str | None:
    """scheduled: 카탈로그 시각(1시간도 안 남았거나 지났으면 지금+2시간 정각) · private: 예약 없음."""
    if mode != "scheduled":
        return None
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    want = slot(e)
    if want < now + dt.timedelta(hours=1):
        want = (now + dt.timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
    return want.strftime("%Y-%m-%dT%H:%M:%SZ")


def meta(e: dict) -> dict:
    src = "\n".join(f"• {s['title']}: {s['url']}" for s in e["sources"])
    desc = (f"{e['description'].strip()}\n\nSources:\n{src}\n\n"
            "Visuals are 3D reconstructions made with AI, and the narration is synthetic. "
            "People are shown as faceless figures on purpose.\n\n" + marker(e))
    tags = list(dict.fromkeys(e.get("tags", []) + BASE_TAGS))
    return {"title": e["title"], "description": desc, "tags": tags}


# ── 업로드 ──────────────────────────────────────────────
def on_youtube(yt, mark: str) -> str | None:
    """채널 최근 업로드 50개에서 표식을 찾는다(2 units)."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    for it in yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50).execute().get("items", []):
        sn = it["snippet"]
        if mark in sn.get("description", ""):
            return f"https://youtu.be/{sn['resourceId']['videoId']}"
    return None


def upload(key, out_dir: str = OUT, ledger: str = LEDGER, mode: str = "scheduled", trends: list[dict] | None = None) -> int:
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    e = find(key, trends=load_trends() if trends is None else trends)
    errs = check_episode(e)
    if errs:
        print("::error::카탈로그 검사 실패 — 올리지 않는다\n  " + "\n  ".join(errs))
        return 2
    st = stem(e)
    with open(os.path.join(out_dir, f"{st}_meta.json"), encoding="utf-8") as f:
        rm = json.load(f)
    if rm.get("mock"):
        print("::error::mock 렌더(가짜 그림·목소리)는 올리지 않는다")
        return 2
    led = load_ledger(ledger)
    if led.get(st, {}).get("short"):
        print(f"⏭️ 이미 올림: {led[st]['short']}")
        return 0
    if rm.get("qa_block"):                  # 트렌드 편이 그림 검수에서 두 번 걸렸다 — 올리지 않고 사유를 남긴다
        led[st] = {"skipped": f"그림 검수 실패: {rm.get('qa_failed')}", "title": e["title"]}
        save_ledger(led, ledger)
        print(f"::warning::{st} 그림 검수 실패({rm.get('qa_failed')}) — 올리지 않는다(트렌드 편)")
        return 0
    import upload_tale as UT
    import upload_youtube_novel as U
    yt = U.get_service()
    dup = on_youtube(yt, marker(e))
    if dup:
        print(f"⏭️ 유튜브에 이미 있다('{marker(e)}'): {dup} — ledger 에만 적는다")
        led[st] = {"short": dup, "title": e["title"]}
        save_ledger(led, ledger)
        return 0
    md = meta(e)
    at = publish_time(e, mode)
    facts = UT.shorts_facts(rm["video"])
    print(f"   {UT.facts_line(facts)}")
    vid = UT.insert(yt, rm["video"], md, "private", at)     # status_body: containsSyntheticMedia=True · publishAt
    done = {"short": f"https://youtu.be/{vid}", "title": md["title"], "publish_at": at, "shorts": facts,
            "kind": e.get("kind", "catalog"), "qa": {k: rm.get(k) for k in ("qa_failed", "qa_fixed", "qa_usd") if k in rm}}
    led[st] = done
    save_ledger(led, ledger)
    print(f"✅ {st} {done['short']} · {'예약 ' + at if at else '비공개'}")
    done["captions"] = UT.captions(yt, vid, rm["srt"])
    try:
        pid = U.ensure_playlist(yt, PLAYLIST, PLAYLIST_DESC, privacy="public")
        U.add_to_playlist(yt, pid, vid)
        done["playlist"] = True
    except Exception as ex:  # noqa: BLE001
        print(f"   ⚠️ 재생목록 실패(업로드는 성공): {ex}")
    done["langs"] = UT.localize(vid, md["title"], md["description"])
    led[st] = done
    save_ledger(led, ledger)
    print(json.dumps({st: done}, ensure_ascii=False))
    return 0


# ── CLI ─────────────────────────────────────────────────
def plan_text(cat: dict | None = None, trends: list[dict] | None = None) -> str:
    rows = []
    for e in schedule(cat, trends):
        d = dt.date.fromisoformat(e["from"])
        rows.append(f"{d:%m/%d}({'월화수목금토일'[d.weekday()]}) {slot(e).astimezone(KST):%H:%M} KST · {stem(e)} [{e['format']}] {e['title']} · "
                    f"출처 {len(e['sources'])} · {len(spoken(e).split())}단어")
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Nine Tails 3D 실화·what-if 쇼츠")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap.add_argument("--trend-dir", default=TREND_DIR, help="data/nt-trend 를 받은 폴더(읽기 전용)")
    sub.add_parser("check")
    sub.add_parser("plan")
    d = sub.add_parser("due")
    d.add_argument("--now")
    d.add_argument("--ledger", default=LEDGER)
    ts = sub.add_parser("trend-slot", help="D일에 쓸 트렌드 편의 공개일(빈 자리가 없으면 빈 줄)")
    ts.add_argument("--day", required=True)
    k = sub.add_parser("key", help="캐시 이름: stem 한 줄 + 옛 이름 한 줄(트렌드 편은 빈 줄)")
    k.add_argument("episode")
    s = sub.add_parser("seen")
    s.add_argument("episode")
    s.add_argument("--ledger", default=LEDGER)
    u = sub.add_parser("upload")
    u.add_argument("episode")
    u.add_argument("--out", default=OUT)
    u.add_argument("--ledger", default=LEDGER)
    u.add_argument("--mode", default=os.environ.get("NT_STORY_PUBLISH", "scheduled"), choices=["private", "scheduled"])
    a = ap.parse_args()
    if a.cmd == "check":
        errs = check()
        for e in episodes():
            print(f"{'❌' if check_episode(e) else '✅'} {stem(e)} · {e['from']} · {len(spoken(e).split())}단어 · "
                  f"출처 {len(e['sources'])}")
        for x in errs:
            print(f"   ✗ {x}")
        return 1 if errs else 0
    trends = load_trends(a.trend_dir)
    if a.cmd == "plan":
        print(plan_text(trends=trends))
        return 0
    if a.cmd == "trend-slot":
        d = trend_slot(dt.date.fromisoformat(a.day), {dt.date.fromisoformat(e["from"]) for e in trends})
        print(d.isoformat() if d else "")
        return 0
    if a.cmd == "due":
        now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=KST)
        e, why = due(now, load_ledger(a.ledger), trends=trends)
        print(f"   · {why}", file=sys.stderr)
        if e and quiet(now):
            print("   · 05:45~08:00 KST — Spark 를 쓰지 않는다(다음 예비 실행이 만든다)", file=sys.stderr)
            return 0
        if e:
            print(stem(e))
        return 0
    if a.cmd == "key":
        for k in cache_keys(a.episode, trends=trends):
            print(k)
        return 0
    if a.cmd == "seen":
        sys.path.insert(0, os.path.join(ROOT, "pipeline"))
        import upload_youtube_novel as U
        e = find(a.episode, trends=trends)
        url = on_youtube(U.get_service(), marker(e))
        if not url:
            print(f"   유튜브에 '{marker(e)}' 없음 — 만든다")
            return 1
        led = load_ledger(a.ledger)
        led[stem(e)] = {"short": url, "title": e["title"]}
        save_ledger(led, a.ledger)
        print(f"⏭️ 이미 올라가 있다: {url}")
        return 0
    if a.cmd == "upload":
        return upload(a.episode, a.out, a.ledger, a.mode, trends=trends)
    return 1


if __name__ == "__main__":
    sys.exit(main())
