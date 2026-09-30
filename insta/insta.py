#!/usr/bin/env python3
"""인스타 릴스 '0원으로 AI 유튜브 채널을 굴리는 실제 기록' — 편성·대본 검사·숫자 자리표시자.

한 편 = output/insta/<YYYY-MM-DD>_<slug>.json 한 파일(루틴이 routine/insta 에 push). 견본은 insta/samples/.
누가 썼든 ★이 검사를 통과해야 렌더·게시한다 — 루틴에게 한 '지시'는 안 지켜질 수 있어서
요일·주제·분량·숫자·금지 표현은 코드가 강제한다.

    python insta/insta.py next --date 2026-10-05     # 그날 올릴 것(요일 → 형식, 날짜 → 주제). 루틴은 이것만 따른다
    python insta/insta.py check output/insta/2026-10-05_claude-routine-rules.json
    python insta/insta.py resolve <file> [--stats output/insta_render/stats.json]   # 숫자를 채운 결과(화면·말)

편성(코드가 정한다 — KST 날짜 기준)
  월·수·금 = guide(따라 하는 가이드, 주제는 catalog 순서대로 날짜로 배정) · 일 = report(주간 성적표) · 화·목·토 = 쉼

숫자 규칙 ★
  대본(말·제목·화면 글자·캡션)에 숫자를 직접 쓰지 않는다. 숫자는 전부 자리표시자로:
    {{fact.<key>}}          catalog 의 확인된 실측값(주제 nums → 공통 nums 순)
    {{wb.subs}} {{ntt.week.views}} …   렌더 때 YouTube Data API 로 채우는 실제 값(stats.py)
    {{vid.<key>.views}}     catalog videos 의 영상 하나의 현재 공개 조회수
    {{week.range}}          성적표 기간(예: 9월 24일~9월 30일)
  검사기는 자리표시자 밖의 숫자(0-9)와 '천 회'·'두 배' 같은 한글 숫자 주장을 거절한다.
  말(TTS)로 나갈 때는 코드가 한글 읽기로 바꾼다(1,285회 → 천이백팔십오 회, 6시간 → 여섯 시간).

scene 한 칸:  {"say": "내레이션(해요체)", "show": {<화면 하나>}, "hold": 0.4}
화면(show) 종류 — 전부 코드가 데이터로 그린다(스크린샷·터미널·설정 화면 없음):
  {"img": "영어 그림 프롬프트"}                          Spark z-image-turbo 그림
  {"gumi": "front|bead|wink"}                             구미 초상(레포 그림)
  {"thumb": "<videos key | wb.week.top | ntt.week.top>", "label": "…"}   유튜브 공개 썸네일(i.ytimg.com)
  {"stat": "{{fact.x}}", "label": "…", "tone": "good|bad|neutral"}       큰 숫자 하나
  {"vs": [{"label": "…", "value": "{{…}}", "tone": "bad"}, {…, "tone": "good"}]}   전·후 두 칸
  {"bars": [{"label": "…", "value": "{{…}}"}, …], "hi": 1}               막대 2~6개
  {"steps": ["…", "…"], "hi": 0}                           번호 목록(hi 강조, -1 = 전부)
  {"flow": ["…", "…", "…"]}                                흐름도(위→아래)
  {"chat": [{"who": "me|ai", "text": "…"}, …]}             말풍선(지시 vs 결과 같은 장면)
  {"text": "…", "sub": "…"}                                큰 문장 하나
  {"week": "wb|ntt|both"}                                  주간 성적표 카드(숫자는 전부 stats)
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATALOG = os.path.join(HERE, "catalog.json")
SAMPLES = os.path.join(HERE, "samples")
ROUTINE_DIR = os.path.join(ROOT, "output", "insta")

WEEKDAY_KO = "월화수목금토일"
FORMAT_BY_WEEKDAY = {0: "guide", 2: "guide", 4: "guide", 6: "report"}   # 월·수·금 가이드 · 일 성적표
REPORT_SLUG = "weekly-report"
FORMATS = ("guide", "report")

# ── 분량 ────────────────────────────────────────────────
# 릴스 30~45초. Supertonic F1 한국어 실측(2026-09-30 견본 렌더): 읽는 글자(공백·문장부호 제외) 초당 5.6자
# + 장면마다 쉼 0.5초 + 끝 0.7초 → 230자·8장면 ≈ 45초, 150자·5장면 ≈ 30초.
# 렌더러가 실제 길이로 한 번 더 막는다(30초 미만은 끝 화면을 늘리고, 45초 넘으면 최대 1.12배 빠르게).
CPS = float(os.environ.get("INSTA_CPS", "5.6"))
SAY_CHARS = (150, 230)          # 말(TTS로 읽는 한글 기준, 공백·문장부호 제외) 전체
SCENES = (4, 9)
SAY_MAX = 75                    # 한 장면 말(화면 글자 기준) — 길면 한 그림에 너무 오래 머문다
HOOK_MAX = 45                   # 첫 장면 말 — 첫 1~2초 안에 요점
HEAD_LINES = (1, 2)
HEAD_UNITS = 12.5               # 제목 한 줄 폭(한글 1칸 기준) — 렌더러가 글자 크기를 맞춘다
HASHTAGS = (1, 5)               # 해시태그는 분류용 — 5개 이하
CAPTION_MAX = 1800              # 인스타 2,200자 - 꼬리말·해시태그 자리
HOOK_LINE_MAX = 45              # 캡션 첫 줄(더 보기 전에 보이는 부분)
STEPS_MIN = 3

# ── 금지 표현 ──────────────────────────────────────────
# 돈 주장·과장·낚시·홍보(채널 링크·구독 요청은 코드가 붙이는 마지막 줄에만)
MONEY = re.compile(r"(부업|재테크|패시브\s*인컴|자동\s*수익|수익\s*(인증|보장|폭발|대박)|떼돈|억대|평생\s*(소득|수익)|"
                   r"돈\s*(을|이)?\s*(벌|번다|벌었|들어와|복)|(한\s*달|하루|일주일|월)\s*(만에|에)?\s*\S{0,6}\s*벌(어|었|기|고)|"
                   r"월급\s*(만큼|이상|넘)|현금\s*흐름)")
HYPE = re.compile(r"(대박|역대급|충격|경악|무조건|떡상|폭발|터졌|터진다|레전드|소름|실화|"
                  r"아무도\s*모르는|모르면\s*손해|초간단|누구나\s*쉽게|클릭\s*한\s*번|단\s*몇\s*분\s*만에|알고리즘\s*(해킹|정복|뚫)|"
                  r"100\s*%|백\s*퍼센트)")
BAIT = re.compile(r"(댓글\s*(에|로|을)?\s*\S{0,10}\s*(남기|달아|적어|쓰)\S*\s*(면|시면)|DM\s*(주|보내|으로)|"
                  r"좋아요\s*(눌|부탁)|팔로우\s*(하|해|부탁|필수)|구독\s*(하|해|과|좀|부탁|눌)|공유\s*(부탁|해\s*주))")
PROMO = re.compile(r"(?i)(https?://|www\.|youtu\.?be|youtube\.com|instagram\.com|@[a-z0-9_.]+|프로필\s*링크|"
                   r"채널\s*링크|놀러\s*오|구독(?!자)|팔로우)")
# 날짜를 타는 말(가이드는 몇 달 뒤에 봐도 맞아야 한다 — 저장해 두고 보는 콘텐츠). 절대 날짜는 사실 자리표시자로
DATED = re.compile(r"(오늘|어제|내일|이번\s*주|지난\s*주|다음\s*주|이번\s*달|지난\s*달|올해|작년|내년|요즘|최근|방금|"
                   r"며칠\s*전|현재|지난밤|요새)")
# 자리표시자를 피해 한글로 쓴 숫자 주장('천 회', '수만 명', '두 배') — 작은 개수('세 가지', '두 번')는 괜찮다
UNITS = r"(회|명|원|시간|퍼센트|편|배|개|분|초|뷰|번|건|위|점|단어|장면|달|주|년)"
KO_NUM = re.compile(r"(?<![가-힣])(?:[일이삼사오육칠팔구]?[십백천만억]|수[십백천만억]|몇[십백천만])+\s*" + UNITS
                    + r"|(?<![가-힣])(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*배")
# 화면·글에 비밀·계정 정보처럼 보이는 것(실수로라도 나가면 안 된다)
SECRET = re.compile(r"(?i)(ghp_\w+|github_pat_\w+|\bsk-[a-z0-9]{8,}|IGAA\w+|AIza[\w-]{10,}|ya29\.\w+|1//0\w+|"
                    r"client_secret|access_token|refresh_token|password\s*[:=]|passwd|bearer\s+\w+|"
                    r"[\w.+-]+@[\w-]+\.(com|net|kr|org|io)|[A-Za-z0-9_\-]{32,})")
# 그림 프롬프트: 글자·화면이 들어가는 그림 금지(글자 모델로 새고, 가짜 터미널·설정 화면이 그려질 수 있다)
IMG_BANNED = re.compile(r"(?i)\b(text|letters?|words?|sign|signage|logo|caption|title|watermark|typography|screen|"
                        r"monitor|terminal|code|dashboard|interface|ui|website|screenshot|app|laptop|smartphone|"
                        r"phone|chart|graph|nude|naked|gore|blood|celebrity)\b")
DIGIT = re.compile(r"[0-9０-９]")
PH = re.compile(r"\{\{\s*([a-z0-9_.]+)\s*\}\}")
STEP_LINE = re.compile(r"^\s*(?:\d{1,2}[.)]|[①-⑩])\s*\S")
STEP_MARK = re.compile(r"^\s*(?:\d{1,2}[.)]|[①-⑩])\s*")
BULLET_LINE = re.compile(r"^\s*(?:\d{1,2}[.)]|[①-⑩]|[•·\-▪️✔✅])\s*\S")

VISUALS = ("img", "gumi", "thumb", "stat", "vs", "bars", "steps", "flow", "chat", "text", "week")
DATA_VISUALS = ("stat", "vs", "bars", "thumb", "week")
GUMI = ("front", "bead", "wink")

# 렌더 때 stats.py 가 채우는 값(채널별). 단위가 붙은 문자열로 나온다 — 조사는 단위에 맞춰 쓴다.
STAT_KEYS = ("subs", "views", "videos", "name", "week.uploads", "week.views", "week.top_title", "week.top_views")
VID_FIELDS = ("views", "likes", "comments", "title")
CHANNELS = ("wb", "ntt")
# 검사 단계(아직 stats 없음)에서 길이를 어림할 때 쓰는 대표값
STAT_SAMPLE = {"subs": "194명", "views": "143,930회", "videos": "462편", "name": "왕별이", "week.uploads": "20편",
               "week.views": "12,345회", "week.top_title": "오늘 띠별 운세 한 장 표", "week.top_views": "1,285회",
               "vid.views": "1,285회", "vid.likes": "12개", "vid.comments": "3개", "vid.title": "영상 제목 예시"}

FOOTER = ("기록 중인 채널: 왕별이(한국어) · Nine Tails Tales(영어) — 프로필에서 볼 수 있어요.\n"
          "목소리와 일부 그림은 AI로 만들었어요. 숫자는 유튜브 실측이에요.")


# ── 읽기 ────────────────────────────────────────────────
def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def catalog() -> dict:
    return load(CATALOG)


# ── 한국어 숫자 읽기(말용) ─────────────────────────────
_D = "영일이삼사오육칠팔구"
_NAT1 = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉"}
_NAT10 = {1: "열", 2: "스물", 3: "서른", 4: "마흔", 5: "쉰", 6: "예순", 7: "일흔", 8: "여든", 9: "아흔"}
# 고유어로 읽는 단위: 여섯 시간 · 열두 띠 · 두 배 · 세 가지(99까지) / 세 편 · 네 단어(20까지 — 75장면은 칠십오 장면)
NATIVE_99 = ("시간", "개", "명", "가지", "번", "살", "띠", "배", "달", "마리", "사람")
NATIVE_20 = ("편", "장", "곳", "줄", "건", "대", "군데", "권", "잔", "채", "통", "단어", "장면")
NATIVE_UNITS = NATIVE_99 + NATIVE_20
SINO_UNITS = ("개월", "퍼센트", "%", "회", "원", "년", "월", "일", "분", "초", "위", "주", "점", "층", "뷰", "호", "화", "기")
_UNIT_RE = "|".join(sorted(NATIVE_UNITS + SINO_UNITS, key=len, reverse=True))
NUM_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)(\s*)(" + _UNIT_RE + r")?")


def _sino4(n: int) -> str:
    s = ""
    for val, name in ((1000, "천"), (100, "백"), (10, "십")):
        d, n = divmod(n, val)
        if d:
            s += ("" if d == 1 else _D[d]) + name
    if n:
        s += _D[n]
    return s


def sino(n: int) -> str:
    """한자어 수: 1285 → 천이백팔십오, 20000000 → 이천만, 10000 → 만."""
    if n == 0:
        return "영"
    out, k = [], 0
    while n > 0:
        n, r = divmod(n, 10000)
        if r:
            s = _sino4(r)
            if k == 1 and s == "일":
                s = ""
            out.append(s + ("", "만", "억", "조")[k])
        k += 1
    return "".join(reversed(out))


def native(n: int) -> str:
    """고유어 수(단위 앞, 1~99): 6 → 여섯, 12 → 열두, 20 → 스무, 21 → 스물한."""
    t, o = divmod(n, 10)
    if t == 2 and o == 0:
        return "스무"
    return _NAT10.get(t, "") + _NAT1.get(o, "")


def read_number(num: str, unit: str | None) -> str:
    raw = num.replace(",", "")
    if "." in raw:
        a, b = raw.split(".", 1)
        s = f"{sino(int(a))} 점 {''.join(_D[int(c)] for c in b)}"
        return s + (" 퍼센트" if unit in ("%", "퍼센트") else (f" {unit}" if unit else ""))
    n = int(raw)
    if (unit in NATIVE_99 and 0 < n < 100) or (unit in NATIVE_20 and 0 < n <= 20):
        return f"{native(n)} {unit}"
    if unit == "월" and 1 <= n <= 12:
        return {6: "유월", 10: "시월"}.get(n, sino(n) + "월")
    if unit in ("%", "퍼센트"):
        return f"{sino(n)} 퍼센트"
    if unit in ("년", "월", "일", "개월"):          # 날짜는 붙여 읽는다: 이천이십칠년 이월 일일
        return sino(n) + unit
    return sino(n) + (f" {unit}" if unit else "")


def say_numbers(text: str) -> str:
    """글 속 아라비아 숫자(+단위)를 한글 읽기로."""
    return NUM_RE.sub(lambda m: read_number(m.group(1), m.group(3)), text)


# 말로 읽을 때만 바꾸는 외래어·약어(화면 글자는 그대로)
SAY_MAP = [
    (r"Nine Tails Tales", "나인 테일즈 테일즈"), (r"YouTube", "유튜브"), (r"GitHub Actions", "깃허브 액션즈"),
    (r"GitHub", "깃허브"), (r"Actions", "액션즈"), (r"Claude", "클로드"), (r"DGX Spark", "디지엑스 스파크"),
    (r"Spark", "스파크"), (r"Supertonic", "슈퍼토닉"), (r"z-image-turbo", "제트 이미지 터보"),
    (r"qwen-image", "큐웬 이미지"), (r"gemma", "젬마"), (r"JSON", "제이슨"), (r"API", "에이피아이"),
    (r"YPP", "와이피피"), (r"GPU", "지피유"), (r"AI", "에이아이"), (r"UTC", "유티씨"), (r"cron", "크론"),
    (r"Shorts", "쇼츠"), (r"PR", "피알"), (r"CTR", "클릭률"), (r"ASMR", "에이에스엠알"), (r"SCP", "에스씨피"),
    (r"Opus", "오퍼스"), (r"LLM", "엘엘엠"), (r"TTS", "티티에스"), (r"Reels", "릴스"), (r"push", "푸시"),
]
_SAY_MAP = [(re.compile(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])"), b) for a, b in SAY_MAP]


def to_speech(text: str) -> str:
    """화면 글자 → TTS 로 보낼 말(숫자·약어를 한글 읽기로, 꾸밈 기호 제거)."""
    t = say_numbers(text)
    for rx, b in _SAY_MAP:
        t = rx.sub(b, t)
    t = t.replace("→", ", ").replace("·", ", ").replace("~", "에서 ")
    t = re.sub(r"[\"“”‘’'「」『』《》<>\[\]{}()*_#|]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def speech_len(text: str) -> int:
    """읽는 분량 = 말로 바꾼 글자 수(공백·문장부호 제외)."""
    return len(re.sub(r"[\s.,!?…:;\-–—'\"“”‘’]", "", to_speech(text)))


def width_units(s: str) -> float:
    """제목 폭 어림(한글 1칸 기준)."""
    w = 0.0
    for c in s:
        if c == " ":
            w += 0.3
        elif ord(c) >= 0x1100:
            w += 1.0
        elif c in ".,:;!'|":
            w += 0.3
        else:
            w += 0.6
    return w


# ── 편성(날짜 → 형식·주제) ───────────────────────────────
def _date(d) -> dt.date:
    return d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))


def format_for(date) -> str | None:
    return FORMAT_BY_WEEKDAY.get(_date(date).weekday())


def guide_index(date) -> int:
    """catalog.start(가이드 요일)부터 이 날짜 전까지의 가이드 날 수 = 이 날 가이드의 catalog 순번(0부터)."""
    start = _date(catalog()["start"])
    d = _date(date)
    return sum(1 for k in range((d - start).days) if (start + dt.timedelta(days=k)).weekday() in (0, 2, 4))


def assigned(date) -> dict:
    """그날 올릴 것 — {date, weekday, format, slug, file, topic}. 쉬는 날이면 format=None."""
    d = _date(date)
    fmt = format_for(d)
    out = {"date": d.isoformat(), "weekday": WEEKDAY_KO[d.weekday()], "format": fmt, "slug": None, "topic": None}
    if fmt == "report":
        out["slug"] = REPORT_SLUG
    elif fmt == "guide":
        cat = catalog()
        if d < _date(cat["start"]):
            out["format"] = None
            out["note"] = f"가이드는 {cat['start']}(월)부터"
            return out
        i = guide_index(d)
        topics = cat["topics"]
        if i >= len(topics):
            out["note"] = f"catalog 끝 — {i + 1}번째 주제가 필요하다(지금 {len(topics)}개). insta/catalog.json 에 추가할 것"
            return out
        out["topic"] = topics[i]
        out["slug"] = topics[i]["slug"]
    if out["slug"]:
        out["file"] = f"output/insta/{d.isoformat()}_{out['slug']}.json"
    return out


def topic_entry(slug: str) -> dict | None:
    return next((t for t in catalog()["topics"] if t["slug"] == slug), None)


def written(date) -> list[str]:
    d = _date(date).isoformat()
    return sorted(glob.glob(os.path.join(ROUTINE_DIR, f"{d}_*.json")))


def recent_changes(date, days: int = 7) -> list[str]:
    """성적표용 — 그 주에 main 에 합쳐진 PR 제목(git log). 루틴이 '이번 주 바꾼 것'을 지어내지 않게."""
    until = _date(date) + dt.timedelta(days=1)
    since = until - dt.timedelta(days=days)
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "origin/main", "--merges", f"--since={since}",
                              f"--until={until}", "--format=%b%x1f"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=20).stdout or ""
    except Exception:  # noqa: BLE001
        return []
    return [b.strip().splitlines()[0] for b in out.split("\x1f") if b.strip()][:12]


# ── 자리표시자 ──────────────────────────────────────────
def _nums(entry: dict | None) -> dict:
    cat = catalog()
    n = dict(cat.get("nums", {}))
    if entry:
        n.update(entry.get("nums", {}))
    return n


def _videos(entry: dict | None) -> dict:
    cat = catalog()
    v = dict(cat.get("videos", {}))
    if entry:
        v.update(entry.get("videos", {}))
    return v


def known_keys(entry: dict | None, fmt: str) -> set[str]:
    keys = {f"fact.{k}" for k in _nums(entry)}
    keys |= {f"{c}.{k}" for c in CHANNELS for k in STAT_KEYS}
    keys |= {f"vid.{k}.{f}" for k in _videos(entry) for f in VID_FIELDS}
    if fmt == "report":
        keys.add("week.range")
    return keys


def fmt_count(n: int, unit: str) -> str:
    return f"{n:,}{unit}"


def _ko_date(d: dt.date) -> str:
    return f"{d.month}월 {d.day}일"


def context(entry: dict | None, stats: dict | None, date=None, sample: bool = False) -> dict:
    """자리표시자 → (화면 글자, 말). sample=True 면 stats 가 없어도 대표값으로 채운다(검사용 길이 어림)."""
    ctx = {}
    for k, v in _nums(entry).items():
        ctx[f"fact.{k}"] = (v["v"], v.get("say") or to_speech(v["v"]))
    cat = catalog()
    chans = (stats or {}).get("channels", {})
    vids = (stats or {}).get("videos", {})
    for c in CHANNELS:
        ch = chans.get(c)
        name = cat["channels"][c]
        if ch:
            wk = ch.get("week") or {}
            top = wk.get("top") or {}
            vals = {"subs": fmt_count(ch["subs"], "명"), "views": fmt_count(ch["views"], "회"),
                    "videos": fmt_count(ch["videos"], "편"), "name": name["name"],
                    "week.uploads": fmt_count(wk.get("uploads", 0), "편"),
                    "week.views": fmt_count(wk.get("views", 0), "회"),
                    "week.top_title": top.get("title") or "새 영상 없음",
                    "week.top_views": fmt_count(top.get("views", 0), "회")}
        elif sample:
            vals = dict(STAT_SAMPLE, name=name["name"])
        else:
            vals = {"name": name["name"]}
        for k, v in vals.items():
            if k in STAT_KEYS:
                spoken = name.get("say", v) if k == "name" else to_speech(v)
                ctx[f"{c}.{k}"] = (v, spoken)
    for key, vid in _videos(entry).items():
        st = vids.get(vid)
        for f in VID_FIELDS:
            if st and f in st:
                v = st[f] if f == "title" else fmt_count(int(st[f]), {"views": "회", "likes": "개", "comments": "개"}[f])
            elif sample:
                v = STAT_SAMPLE[f"vid.{f}"]
            else:
                continue
            ctx[f"vid.{key}.{f}"] = (v, to_speech(v))
    if date:
        d = _date(date)
        a = d - dt.timedelta(days=6)
        rng = f"{_ko_date(a)}~{_ko_date(d)}"
        ctx["week.range"] = (rng, f"{to_speech(_ko_date(a))}부터 {to_speech(_ko_date(d))}까지")
    return ctx


class Missing(KeyError):
    pass


def resolve(text: str, ctx: dict, mode: str = "show") -> str:
    """mode='show' → 화면 글자, 'say' → TTS 로 보낼 말."""
    miss = [m.group(1) for m in PH.finditer(text or "") if m.group(1) not in ctx]
    if miss:
        raise Missing(f"채울 수 없는 자리표시자 {sorted(set(miss))} — stats.json(렌더 전 stats.py)이나 catalog nums 확인")
    out = PH.sub(lambda m: ctx[m.group(1)][0 if mode == "show" else 1], text or "")
    return to_speech(out) if mode == "say" else out


# ── 검사 ────────────────────────────────────────────────
def _texts_of_show(show: dict) -> list[tuple[str, str]]:
    """화면에 글자로 나가는 필드 (이름, 글)."""
    out = []
    for k in ("label", "text", "sub", "stat"):
        if isinstance(show.get(k), str):
            out.append((k, show[k]))
    for k in ("steps", "flow"):
        for i, s in enumerate(show.get(k) or []):
            out.append((f"{k}[{i}]", s if isinstance(s, str) else ""))
    for k in ("vs", "bars"):
        for i, it in enumerate(show.get(k) or []):
            if isinstance(it, dict):
                out.append((f"{k}[{i}].label", it.get("label", "")))
                out.append((f"{k}[{i}].value", it.get("value", "")))
    for i, it in enumerate(show.get("chat") or []):
        if isinstance(it, dict):
            out.append((f"chat[{i}]", it.get("text", "")))
    return out


def _check_show(i: int, show, entry: dict | None, errs: list[str]):
    if not isinstance(show, dict):
        errs.append(f"장면 {i}: show 는 객체")
        return
    kinds = [k for k in VISUALS if k in show]
    if len(kinds) != 1:
        errs.append(f"장면 {i}: show 는 {VISUALS} 중 정확히 하나 ({kinds})")
        return
    k = kinds[0]
    v = show[k]
    if k == "img":
        if not isinstance(v, str) or not 20 <= len(v) <= 320:
            errs.append(f"장면 {i}: img 프롬프트 20~320자(영어 한 문장)")
        elif re.search(r"[가-힣]", v):
            errs.append(f"장면 {i}: img 프롬프트는 영어로")
        elif IMG_BANNED.search(v):
            errs.append(f"장면 {i}: img 에 {IMG_BANNED.search(v).group(0)!r} — 글자·화면·차트가 들어가는 그림 금지"
                        f"(글자 모델로 새고, 가짜 화면이 그려진다). 숫자·화면은 stat/bars/steps 로 코드가 그린다")
    elif k == "gumi" and v not in GUMI:
        errs.append(f"장면 {i}: gumi 는 {GUMI}")
    elif k == "thumb":
        vids = _videos(entry)
        if v not in vids and v not in ("wb.week.top", "ntt.week.top"):
            errs.append(f"장면 {i}: thumb {v!r} 는 catalog videos 키이거나 wb.week.top·ntt.week.top")
    elif k == "stat":
        if not PH.search(v or ""):
            errs.append(f"장면 {i}: stat 은 자리표시자 숫자({{{{fact.…}}}} 등)")
    elif k in ("vs", "bars"):
        n = (2, 2) if k == "vs" else (2, 6)
        if not isinstance(v, list) or not n[0] <= len(v) <= n[1]:
            errs.append(f"장면 {i}: {k} 는 {n[0]}~{n[1]}칸")
        else:
            for j, it in enumerate(v):
                if not isinstance(it, dict) or not it.get("label") or not PH.search(it.get("value", "")):
                    errs.append(f"장면 {i}: {k}[{j}] 는 label + 자리표시자 value")
                elif width_units(it["label"]) > 11:
                    errs.append(f"장면 {i}: {k}[{j}].label 이 길다(한글 11자 안쪽)")
    elif k in ("steps", "flow"):
        n = (2, 5)
        if not isinstance(v, list) or not n[0] <= len(v) <= n[1]:
            errs.append(f"장면 {i}: {k} 는 {n[0]}~{n[1]}줄")
        else:
            for j, s in enumerate(v):
                if not isinstance(s, str) or not s.strip() or width_units(s) > (16 if k == "steps" else 12):
                    errs.append(f"장면 {i}: {k}[{j}] 는 {'16' if k == 'steps' else '12'}칸 안쪽 한 줄")
            if k == "steps" and not -1 <= int(show.get("hi", -1)) < len(v):
                errs.append(f"장면 {i}: steps.hi 는 -1 ~ {len(v) - 1}")
    elif k == "chat":
        if not isinstance(v, list) or not 1 <= len(v) <= 4:
            errs.append(f"장면 {i}: chat 은 1~4개 말풍선")
        else:
            for j, it in enumerate(v):
                if not isinstance(it, dict) or it.get("who") not in ("me", "ai") or not it.get("text"):
                    errs.append(f"장면 {i}: chat[{j}] = {{who: me|ai, text}}")
                elif len(it["text"]) > 40:
                    errs.append(f"장면 {i}: chat[{j}] 40자 이하")
    elif k == "text":
        if not isinstance(v, str) or not v.strip() or width_units(v) > 26:
            errs.append(f"장면 {i}: text 는 한글 26칸 안쪽(두 줄)")
        if width_units(show.get("sub", "")) > 22:
            errs.append(f"장면 {i}: sub 는 22칸 안쪽")
    elif k == "week" and v not in ("wb", "ntt", "both"):
        errs.append(f"장면 {i}: week 는 wb|ntt|both")
    for name, t in _texts_of_show(show):
        _check_text(f"장면 {i} {name}", t, errs, dated=False)


def _check_text(where: str, t: str, errs: list[str], dated: bool, promo: bool = True):
    if not t:
        return
    bare = PH.sub("", t)
    if DIGIT.search(bare):
        errs.append(f"{where}: 숫자 {DIGIT.search(bare).group(0)!r} 를 직접 썼다 — 숫자는 {{{{fact.…}}}}·{{{{wb.…}}}} 자리표시자로만"
                    f" ({bare[:40]!r})")
    m = KO_NUM.search(bare)
    if m:
        errs.append(f"{where}: 한글로 쓴 숫자 주장 {m.group(0)!r} — 자리표시자로")
    for rx, why in ((MONEY, "돈 주장"), (HYPE, "과장 표현"), (BAIT, "참여 낚시")):
        m = rx.search(bare)
        if m:
            errs.append(f"{where}: {why} {m.group(0)!r} 금지")
    if promo and PROMO.search(bare):
        errs.append(f"{where}: 홍보·링크 {PROMO.search(bare).group(0)!r} — 채널 안내는 코드가 캡션 마지막 줄에만 붙인다")
    if dated and DATED.search(bare):
        errs.append(f"{where}: 날짜를 타는 표현 {DATED.search(bare).group(0)!r} — 가이드는 몇 달 뒤에 봐도 맞아야 한다"
                    f"(날짜는 {{{{fact.…}}}} 로 절대 날짜)")


def _all_strings(o, path="") -> list[tuple[str, str]]:
    if isinstance(o, str):
        return [(path, o)]
    if isinstance(o, dict):
        return [x for k, v in o.items() for x in _all_strings(v, f"{path}.{k}" if path else k)]
    if isinstance(o, list):
        return [x for i, v in enumerate(o) for x in _all_strings(v, f"{path}[{i}]")]
    return []


def check(s: dict, path: str | None = None, strict: bool | None = None) -> list[str]:
    """문제 목록(비었으면 통과). strict = 편성(날짜·요일·주제·파일 이름)까지 본다 — output/insta/ 의 파일은 늘 strict."""
    errs = []
    for k in ("date", "format", "topic", "headline", "scenes", "caption", "hashtags"):
        if not s.get(k):
            errs.append(f"'{k}' 없음")
    if errs:
        return errs
    try:
        d = _date(s["date"])
    except ValueError:
        return [f"date 형식 YYYY-MM-DD: {s['date']!r}"]
    fmt = s["format"]
    if fmt not in FORMATS:
        return [f"format 은 {FORMATS}"]
    if strict is None:
        strict = bool(path) and os.path.abspath(os.path.dirname(path)) == os.path.abspath(ROUTINE_DIR)
    entry = topic_entry(s["topic"]) if fmt == "guide" else None
    if fmt == "guide" and not entry:
        errs.append(f"topic {s['topic']!r} 가 catalog 에 없다")
    if fmt == "report" and s["topic"] != REPORT_SLUG:
        errs.append(f"report 의 topic 은 {REPORT_SLUG!r}")
    if strict:
        a = assigned(d)
        if a["format"] is None:
            errs.append(f"{d}({a['weekday']})는 올리지 않는 날 — 월·수·금 가이드, 일 성적표")
        elif a["format"] != fmt:
            errs.append(f"{d}({a['weekday']})는 {a['format']} 날인데 format={fmt!r}")
        elif a["slug"] != s["topic"]:
            errs.append(f"{d} 주제는 {a['slug']!r}(insta.py next --date {d}) — {s['topic']!r} 아님")
        if path:
            want = f"{d.isoformat()}_{s['topic']}.json"
            if os.path.basename(path) != want:
                errs.append(f"파일 이름은 {want} 여야 한다(지금 {os.path.basename(path)})")
    # 제목(위 두 줄)
    head = s["headline"]
    ctx = context(entry, None, d, sample=True)
    known = known_keys(entry, fmt)
    if not isinstance(head, list) or not HEAD_LINES[0] <= len(head) <= HEAD_LINES[1]:
        errs.append("headline 은 1~2줄 목록")
    else:
        for j, ln in enumerate(head):
            _check_text(f"제목 {j + 1}줄", ln, errs, dated=fmt == "guide")
            try:
                w = width_units(resolve(ln, ctx))
            except Missing:
                w = width_units(ln)
            if not ln.strip() or w > HEAD_UNITS:
                errs.append(f"제목 {j + 1}줄 폭 {w:.1f}칸 > {HEAD_UNITS} — 한 줄에 한글 12자 안쪽({ln!r})")
    # 장면
    sc = s["scenes"]
    if not SCENES[0] <= len(sc) <= SCENES[1]:
        errs.append(f"장면 {len(sc)}개 — {SCENES[0]}~{SCENES[1]}")
    total = 0
    kinds = set()
    used, said = set(), set()
    for i, x in enumerate(sc):
        say = x.get("say", "")
        if not say:
            errs.append(f"장면 {i}: say 없음")
            continue
        _check_text(f"장면 {i} say", say, errs, dated=fmt == "guide")
        used |= set(PH.findall(say))
        said |= set(PH.findall(say))
        try:
            shown = resolve(say, ctx)
            total += speech_len(shown)
        except Missing:
            shown = say
        if len(shown) > SAY_MAX:
            errs.append(f"장면 {i}: 말 {len(shown)}자 > {SAY_MAX} — 둘로 나눌 것")
        if i == 0 and len(shown) > HOOK_MAX:
            errs.append(f"첫 장면 말 {len(shown)}자 > {HOOK_MAX} — 첫 줄에 요점만")
        if not 0 <= float(x.get("hold", 0)) <= 2:
            errs.append(f"장면 {i}: hold 0~2초")
        _check_show(i, x.get("show"), entry, errs)
        if isinstance(x.get("show"), dict):
            kinds |= {k for k in VISUALS if k in x["show"]}
            for _, t in _texts_of_show(x["show"]):
                used |= set(PH.findall(t))
    if not SAY_CHARS[0] <= total <= SAY_CHARS[1]:
        errs.append(f"말 분량 {total}자 — {SAY_CHARS[0]}~{SAY_CHARS[1]}자(약 30~45초, 공백·문장부호 빼고 읽는 글자)")
    if fmt == "guide":
        if len(kinds) < 2:
            errs.append("화면 종류가 한 가지뿐 — 두 가지 이상 섞는다")
        if entry and entry.get("nums") and not any(k.startswith(("fact.", "vid.", "wb.", "ntt.")) for k in said):
            errs.append("말에 실측 숫자가 하나도 없다 — 이 주제의 nums 를 {{fact.…}} 로 한 번 이상 말한다(이 계정은 실제 기록이다)")
        if not kinds & set(DATA_VISUALS):
            errs.append(f"숫자 화면이 없다 — {DATA_VISUALS} 중 하나 이상")
        if sc and "저장" not in sc[-1].get("say", ""):
            errs.append("마지막 장면 말에 '저장'이 없다 — '저장해 두고 그대로 따라 해 보세요' 같은 한 줄로 끝낸다")
    else:
        if "week" not in kinds:
            errs.append("성적표에는 week 화면이 있어야 한다")
        for c in CHANNELS:
            if not any(k.startswith(c + ".") for k in used):
                errs.append(f"성적표 말·화면에 {c} 숫자가 없다 — 두 채널 다 {{{{{c}.…}}}} 로")
    # 자리표시자 이름
    every = {m for _, t in _all_strings(s) for m in PH.findall(t)}
    bad = sorted(every - known)
    if bad:
        errs.append(f"모르는 자리표시자 {bad} — insta.py next 가 보여 주는 목록에서만")
    # 캡션
    cap = s["caption"]
    _check_text("캡션", "\n".join(ln for ln in cap.splitlines() if not STEP_LINE.match(ln))
                + "\n" + "\n".join(STEP_MARK.sub("", ln) for ln in cap.splitlines() if STEP_LINE.match(ln)),
                errs, dated=fmt == "guide")
    if "#" in cap:
        errs.append("캡션 본문에 # 금지 — 해시태그는 hashtags 필드(코드가 끝에 붙인다)")
    lines = [ln for ln in cap.splitlines()]
    try:
        first = resolve(lines[0], ctx) if lines else ""
    except Missing:
        first = lines[0] if lines else ""
    if not first.strip() or len(first) > HOOK_LINE_MAX:
        errs.append(f"캡션 첫 줄(훅) 1~{HOOK_LINE_MAX}자 — 지금 {len(first)}자")
    if len(cap) > CAPTION_MAX:
        errs.append(f"캡션 {len(cap)}자 > {CAPTION_MAX}")
    if fmt == "guide":
        n = sum(1 for ln in lines if STEP_LINE.match(ln))
        if n < STEPS_MIN:
            errs.append(f"캡션에 따라 할 단계가 {n}줄 — '1. …' 형식으로 {STEPS_MIN}줄 이상(캡션이 매뉴얼이다)")
        if not any("저장" in ln for ln in lines):
            errs.append("캡션에 '저장' 줄이 없다(예: 저장해 두고 그대로 따라 해 보세요)")
    else:
        if sum(1 for ln in lines if BULLET_LINE.match(ln)) < 3:
            errs.append("성적표 캡션은 항목 3줄 이상(• 또는 1.)")
    # 해시태그
    tags = s["hashtags"]
    if not isinstance(tags, list) or not HASHTAGS[0] <= len(tags) <= HASHTAGS[1]:
        errs.append(f"해시태그 {HASHTAGS[0]}~{HASHTAGS[1]}개(분류용)")
    else:
        for t in tags:
            if not re.fullmatch(r"#[0-9A-Za-z가-힣_]{1,24}", t or ""):
                errs.append(f"해시태그 형식 '#단어'(공백 없이): {t!r}")
        if len(set(tags)) != len(tags):
            errs.append("해시태그 중복")
    # 비밀·계정 정보(어느 필드든)
    for where, t in _all_strings(s):
        m = SECRET.search(PH.sub("", t))
        if m and not where.endswith(".img"):
            errs.append(f"{where}: 비밀·계정 정보처럼 보이는 글 {m.group(0)[:12]!r}… — 화면·글에 절대 금지")
    return errs


def estimate(s: dict) -> dict:
    entry = topic_entry(s.get("topic", "")) if s.get("format") == "guide" else None
    ctx = context(entry, None, s.get("date"), sample=True)
    chars = 0
    for x in s.get("scenes", []):
        try:
            chars += speech_len(resolve(x.get("say", ""), ctx))
        except Missing:
            chars += speech_len(x.get("say", ""))
    n = len(s.get("scenes", []))
    holds = sum(float(x.get("hold", 0)) for x in s.get("scenes", []))
    return {"scenes": n, "chars": chars, "est_sec": round(chars / CPS + 0.5 * n + 0.7 + holds, 1)}


# ── 캡션(게시용) ────────────────────────────────────────
def final_caption(s: dict, ctx: dict) -> str:
    body = resolve(s["caption"], ctx).strip()
    return f"{body}\n\n{FOOTER}\n\n" + " ".join(s["hashtags"])


def threads_text(s: dict, ctx: dict, limit: int = 480) -> str:
    """쓰레드는 500자 — 첫 줄 + 단계 + 저장 줄."""
    lines = resolve(s["caption"], ctx).strip().splitlines()
    keep = [lines[0], ""] + [ln for ln in lines[1:] if STEP_LINE.match(ln) or BULLET_LINE.match(ln) or "저장" in ln]
    out = "\n".join(keep)
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


# ── CLI ─────────────────────────────────────────────────
def _next(date: str) -> int:
    a = assigned(date)
    if a["format"] is None:
        print(json.dumps({"date": a["date"], "weekday": a["weekday"], "post": False,
                          "message": a.get("note") or "올리지 않는 날 — 월·수·금 가이드, 일 성적표"}, ensure_ascii=False))
        return 0
    if not a["slug"]:
        print(json.dumps({"date": a["date"], "post": False, "error": a.get("note")}, ensure_ascii=False))
        return 1
    entry = a["topic"]
    fmt = a["format"]
    ctx = context(entry, None, a["date"], sample=False)
    ph = {}
    for k in sorted(known_keys(entry, fmt)):
        if k in ctx and k.startswith("fact."):
            ph[k] = f"{ctx[k][0]}  (말: {ctx[k][1]})"
        elif k.startswith(("wb.", "ntt.")):
            if fmt == "report" or k.split(".", 1)[1] in ("subs", "views", "videos", "name"):
                ph[k] = "렌더 때 실제 값 — 단위 포함: " + {"subs": "…명", "views": "…회", "videos": "…편", "name": "채널 이름",
                                                   "uploads": "…편", "top_title": "영상 제목", "top_views": "…회"}[k.rsplit(".", 1)[-1]]
        elif k.startswith("vid.") and k.endswith((".views", ".title")):
            ph[k] = "렌더 때 실제 값" + (" — …회" if k.endswith(".views") else " — 영상 제목")
        elif k == "week.range":
            ph[k] = context(None, None, a["date"])["week.range"][0]
    out = {"date": a["date"], "weekday": a["weekday"], "post": True, "format": fmt, "file": a["file"],
           "already_written": bool(written(a["date"])), "placeholders": ph}
    if entry:
        out["topic"] = entry
    else:
        out["recent_changes"] = recent_changes(a["date"])
    out["exemplar"] = f"insta/samples/{'first-second' if fmt == 'guide' else 'weekly-report'}.json"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for p in sys.argv[2:]:
            s = load(p)
            errs = check(s, p)
            e = estimate(s)
            print(f"{'✅' if not errs else '❌'} {os.path.basename(p)} · {s.get('format')} · 장면 {e['scenes']}"
                  f" · 말 {e['chars']}자 · 약 {e['est_sec']}초")
            for x in errs:
                print(f"   ✗ {x}")
            bad += bool(errs)
        return 1 if bad else 0
    if len(sys.argv) >= 2 and sys.argv[1] == "next":
        date = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[2] == "--date" else \
            dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
        return _next(date)
    if len(sys.argv) >= 3 and sys.argv[1] == "resolve":
        s = load(sys.argv[2])
        stats = load(sys.argv[4]) if len(sys.argv) >= 5 and sys.argv[3] == "--stats" else None
        entry = topic_entry(s["topic"]) if s["format"] == "guide" else None
        ctx = context(entry, stats, s["date"], sample=stats is None)
        print("제목: " + " / ".join(resolve(h, ctx) for h in s["headline"]))
        for i, x in enumerate(s["scenes"]):
            print(f"[{i}] 화면: {resolve(x['say'], ctx)}\n    말:   {resolve(x['say'], ctx, 'say')}")
        print("\n── 캡션 ──\n" + final_caption(s, ctx))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
