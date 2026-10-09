#!/usr/bin/env python3
"""Nine Tails 쇼츠: 편성(날짜 → 그날 쓸 편 전부) · 대본 검사 · 메타.

    python gumiho/tales/rules.py next --date 2026-10-12     # 그날 쓸 편 전부(entries[] — 편마다 file·format·publish_at)
    python gumiho/tales/rules.py check output/tales_rules/R101_mariana-trench-floor.json

2026-10-09 사용자 결정: 한국 설화·조선 주제 금지('쓰레기 주제'). 타깃은 그대로 해외 영어권 20–39(Studio: 25–34 43%·
  남성 70%·미국 73%). 10/13–10/26 2주 시험(10/27 판정) — 새 쇼츠 라인업(shorts_catalog.json):
  A  survival  매일 20:00 UTC  "How Long Would You Last…? Pt.N" — 상황 큰 글자 + 0:00 시계 → 시각별 4–6 박자(실제 수치·출처) → "Gumi's odds: 2%"
  B1 compare   격일 23:30 UTC  "… Ranked by Size Pt.N" — 실측값 막대 + 마지막 반전
  B2 liminal   격일 23:30 UTC  "RULES to Follow if You Wake Up in an Empty Mall at 3 A.M." — 분명한 창작, 번호 규칙 + 루프
  근거(C:\\wbtmp\\research1009): 'How Long You'd Last in Every Prehistoric Era' 구독 3.2만 채널 1,090만 · 위험한 곳 Top10 중앙값
  87만(작은 채널 돌파 8) · 마리아나 해구 구독 2만 채널 280만 · 리미널 구독 1.3만 채널 180만 · 크기 비교 Pt.1→3 330만→473만 ·
  우리 쇼츠 중 피드가 민 건 versus·rules 뿐.
정책(YouTube '진정성 없는 콘텐츠' — 이름만 바꾼 AI 템플릿 채널 16곳이 2026-01 삭제됐다):
  편마다 다른 수치·논리·출처 · 같은 그림(프롬프트) 재사용 금지 · 숫자 있는 줄은 출처(sources) 필수 · 숫자는 catalog facts 에서만 ·
  실존 피해자·실존 인물·프랜차이즈·SCP·Backrooms 금지 · 구미는 목소리만(그림에 구미·여우 금지).
옛 동아시아 규칙괴담(rules_catalog.json)은 남겨 두되 10/9 배정분까지만(until) — 10/10부터 설화는 편성되지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import tales as T  # noqa: E402  (옛 형식 검사만 LOOKS · BANNED · DATED 를 같이 쓴다)

CATALOG = os.path.join(HERE, "rules_catalog.json")
SHORTS = os.path.join(HERE, "shorts_catalog.json")
OUT_DIR = "output/tales_rules"
OLD_FORMATS = ("rules", "versus", "pov")
NEW_FORMATS = ("survival", "compare", "liminal")
FORMATS = OLD_FORMATS + NEW_FORMATS
REACTS = ("shock", "smug", "scared", "laugh")       # 옛 형식의 치비 구미 리액션(assets/tales/chibi_<react>.png)
WORDS = (45, 95)            # 20–35초(F2 ≈ 159 wpm × 템포 0.97 + 줄 사이 쉼)
LINES = (5, 9)
SAY_MAX = 22                # 한 줄(한 화면) 최대 단어 — 화면이 3–6초마다 바뀐다
TEXT_MAX = 48               # 화면 큰 글자(규칙 문장) 최대 글자 수
HOOK_WORDS, HOOK_CHARS = 7, 38
TITLE_MAX = 100
# 규칙형 제목: tales.RULE_TITLE 보다 넓게 — 'If Someone Calls…', 'If a Kappa…' 같은 조건문도 규칙이다
RULE_TITLE = re.compile(r"(?i)^\s*(never|don'?t|do not|if\b|always|you should never|why you should never)")
VS_TITLE = re.compile(r"(?i)\bvs\.?\b")
POV_TITLE = re.compile(r"(?i)^\s*pov\b")
SHOW_GUMI = re.compile(r"(?i)\b(gumi|fox girl|nine[- ]tailed fox girl|silver[- ]haired (girl|woman))\b")

# ── 새 라인업(2026-10-13~) ─────────────────────────────
# 그림 화풍: 새 형식은 실사(현재·우주 배경). 실사라 업로드는 containsSyntheticMedia=true(upload_tale.status_body).
LOOKS = {
    "deep": "photorealistic cinematic still, deep ocean, ",
    "space": "photorealistic cinematic still, outer space, ",
    "earth": "photorealistic cinematic still, documentary nature photography, ",
    "ancient": "photorealistic cinematic still, prehistoric Earth, documentary, ",
    "liminal": "liminal space photograph, deserted and empty, eerie fluorescent light, wide angle, film grain, ",
}
LOOK_TAIL = "dramatic lighting, high detail, vertical composition, "
NEW_WORDS = {"survival": (70, 110), "compare": (60, 105), "liminal": (50, 92)}     # A 30–45초 · B 25–40초
BEATS = (4, 6)              # survival 시각 박자
ITEMS = (4, 6)              # compare 순위 항목(+ 마지막 반전 1)
LIM_LINES = (5, 8)
BEAT_SAY_MAX = 26
BEAT_TEXT_MAX = 34          # 박자 큰 글자("1,086 BAR")
SITUATION_MAX = 36          # 첫 1초 상황 글자("FLOOR OF THE MARIANA TRENCH")
NAME_MAX, LABEL_MAX = 22, 18
GUMI_MAX = 16
SURVIVAL_TITLE = re.compile(r"(?i)^how long would you last\b")
COMPARE_TITLE = re.compile(r"(?i)\b(ranked|by size)\b")
LIMINAL_TITLE = re.compile(r"(?i)\b(rules?|theory)\b")
PART_TITLE = re.compile(r"(?i)\bpt\.\s?(\d+)\b")
ODDS = re.compile(r"^(<\s?1|\d{1,3})%$")
CLOCK = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")
DAYS = re.compile(r"(?i)^day\s+(\d+)$")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
# 창작(liminal)에서 출처가 필요한 '사실처럼 보이는 숫자' — 단위·퍼센트·큰 수. 3 A.M.·RULE 2·FLOOR 4 는 이야기의 일부.
FACT_NUM = re.compile(r"(?i)(\d[\d,]*(?:\.\d+)?\s?(%|percent|°|degrees?|km|kilomet|met(er|re)s?\b|m\b|ft\b|feet|miles?|"
                      r"mph|kph|km/h|kg|tons?|years?|million|billion|people|deaths?)|\b\d{1,3}(,\d{3})+\b|\b\d{4,}\b)")
CLOCK_TIME = re.compile(r"(?i)\b\d{1,2}(:\d{2})?\s?(a\.?m\.?|p\.?m\.?)")
# 금지 주제(2026-10-09 사용자: 한국 설화·조선 금지) + 실존 피해자·인물 + 프랜차이즈 + SCP·Backrooms. 대본 모든 글자에 적용.
BANNED_TOPICS = re.compile(
    r"(?i)\b(korea\w*|joseon|goryeo|hanbok|hanok|gumiho|kumiho|dokkaebi|jeoseung|saja|gwishin|gwisin|jangsanbeom|"
    r"folklore|folk tale|legend says|kitsune|yokai|huli ?jing|nine[- ]tailed|fox(es)?|"
    r"scp|backrooms?|level 0|noclip\w*|poolrooms|"
    r"victims?|true story|real footage|body was found|"
    r"oceangate|titan submersible|titanic|dyatlov|akimov|toptunov|legasov|"
    r"marvel|pok[eé]mon|minecraft|fortnite|roblox|star wars|star trek|jurassic (park|world)|godzilla|king kong|"
    r"interstellar|gargantua|the meg|stranger things|squid game|five nights|fnaf|skibidi|disney|pixar|"
    r"harry potter|game of thrones|lord of the rings|hbo)\b")
# 욕설·날짜 타는 말 — tales.py(롱폼, 다른 작업이 바꾸는 중)와 떼어 여기 둔다(새 형식만 이걸 쓴다)
PROFANITY = re.compile(r"(?i)\b(fuck|shit|rape|porn|nude|naked|gore|dismember|suicide|decapitat)\w*")
DATED = re.compile(r"(?i)\b(this (year|week|month|halloween|summer|winter|season)|last (week|month|year)|recently|"
                   r"right now|these days|currently|trending|as of today)\b")
NO_FOX = re.compile(r"(?i)\b(gumi|fox\w*|vixen|kitsune|nine[- ]tail\w*|fox girl)\b")
IMG_TEXT = re.compile(r"(?i)\b(text|letters|words|sign that says|caption|logo|watermark)\b")
REPUTABLE = re.compile(r"(?i)(\.gov|\.mil|\.edu|\.int|nasa|noaa|usgs|nps\.gov|esa\.int|britannica\.com|si\.edu|smithsonian|"
                       r"nature\.com|science\.org|pnas\.org|peerj\.com|agupubs|wiley\.com|springer|sciencedirect|"
                       r"cambridge\.org|oup\.com|nih\.gov|who\.int|wmo\.int|mbari\.org|schmidtocean\.org|"
                       r"nhm\.ac\.uk|amnh\.org|ac\.uk|eso\.org|caltech|mit\.edu|iop\.org|aanda\.org|arxiv\.org|"
                       r"eventhorizontelescope\.org|whoi\.edu|nsidc\.org|bas\.ac\.uk|ucar\.edu|copernicus|"
                       r"nationalgeographic\.com|scientificamerican\.com|einstein-online\.info|sandiegozoo\.org|"
                       r"fishesoftexas\.org|harmony\.co\.za|mpg\.de|nist\.gov|aps\.org|doi\.org|rmg\.co\.uk|swri\.org|agu\.org|"
                       r"calacademy\.org|nejm\.org)")


def catalog(path: str = CATALOG) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def shorts(path: str = SHORTS) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 편성 ──────────────────────────────────────────────
def assigned(date: dt.date, cat: dict | None = None) -> dict | None:
    """옛 규칙괴담: start 부터 하루 한 편, 목록 순서대로. 시작 전·until 뒤·목록이 바닥나면 None."""
    cat = cat or catalog()
    if cat.get("until") and date > dt.date.fromisoformat(cat["until"]):
        return None                     # 2026-10-09 설화 금지 — 10/10부터 옛 목록은 쓰지 않는다
    k = (date - dt.date.fromisoformat(cat["start"])).days
    rs = cat["rules"]
    return rs[k] if 0 <= k < len(rs) else None


def day_of(n: int, cat: dict | None = None) -> dt.date:
    """옛 n 편의 배정일(assigned 의 역) — 업로드가 예약 공개일을 정할 때 쓴다."""
    cat = cat or catalog()
    return dt.date.fromisoformat(cat["start"]) + dt.timedelta(days=n - 1)


def publish_date(e: dict, sc: dict | None = None) -> dt.date:
    """새 편의 공개일. A(survival)는 매일, B 는 compare(짝수 날)·liminal(홀수 날)이 번갈아 — first_publish 부터 센다."""
    sc = sc or shorts()
    p0 = dt.date.fromisoformat(sc["first_publish"])
    fmt = e["format"]
    k = [x["n"] for x in sc[fmt]].index(e["n"])
    ser = sc["series"][fmt]
    step = ser.get("every", 1)
    return p0 + dt.timedelta(days=ser.get("offset", 0) + k * step)


def assign_date(e: dict, sc: dict | None = None) -> dt.date:
    """루틴이 그 편을 쓰는 날 = 공개 전날(옛 RULES 와 같은 '다음 날' 여유 — 12:00 UTC 루틴 + Spark 대기열)."""
    sc = sc or shorts()
    return publish_date(e, sc) - dt.timedelta(days=sc.get("write_ahead_days", 1))


def slot_of(e: dict, sc: dict | None = None) -> tuple[str, str]:
    """(슬롯 A|B, 'HH:MM' UTC)."""
    sc = sc or shorts()
    slot = sc["series"][e["format"]]["slot"]
    return slot, sc["slots"][slot]


def nominal_publish_at(e: dict, sc: dict | None = None) -> str:
    sc = sc or shorts()
    d = publish_date(e, sc)
    h, m = (int(x) for x in slot_of(e, sc)[1].split(":"))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_on(date: dt.date, sc: dict | None = None) -> list[dict]:
    sc = sc or shorts()
    out = [e for f in NEW_FORMATS for e in sc[f] if assign_date(e, sc) == date]
    return sorted(out, key=lambda e: slot_of(e, sc))


def entry(n: int, sc: dict | None = None) -> dict | None:
    sc = sc or shorts()
    return next((e for f in NEW_FORMATS for e in sc[f] if e["n"] == n), None)


def teaser_idea(e: dict, sc: dict | None = None) -> str | None:
    """다음 편 예고(화면 글자만, 목소리 없음) — 같은 시리즈 다음 편이 있을 때만. 매일(A)은 TOMORROW, 격일(B)은 요일."""
    sc = sc or shorts()
    rs = sc[e["format"]]
    k = [x["n"] for x in rs].index(e["n"])
    if k + 1 >= len(rs) or e["format"] == "liminal":     # liminal 은 끝 → 첫 장면 루프가 핵심(예고가 루프를 끊는다)
        return None
    nx = rs[k + 1]
    gap = (publish_date(nx, sc) - publish_date(e, sc)).days
    when = "TOMORROW" if gap == 1 else publish_date(nx, sc).strftime("%A").upper()
    return f"PT.{nx['part']} {when}: {nx['teaser']}"


def file_for(e: dict) -> str:
    return f"{OUT_DIR}/R{e['n']:03d}_{e['slug']}.json"


def stem_of(s: dict) -> str:
    return f"R{s['id']:03d}_{s['slug']}"


def on_date(date: dt.date) -> list[dict]:
    """그날 쓸 편 전부(옛 규칙괴담 + 새 라인업). 편마다 file·slot·format·publish_at."""
    out = []
    old = assigned(date)
    if old:
        cat = catalog()
        h, m = (int(x) for x in cat.get("publish_utc", "13:00").split(":"))
        d = date + dt.timedelta(days=1)
        at = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append({"file": file_for(old), "slot": "RULES", "publish_at": at, **old})
    sc = shorts()
    for e in new_on(date, sc):
        slot, _ = slot_of(e, sc)
        out.append({"file": file_for(e), "slot": slot, "publish_at": nominal_publish_at(e, sc),
                    "teaser_idea": teaser_idea(e, sc), **e})
    return out


def words(t: str) -> int:
    return len((t or "").split())


# ── 옛 형식 검사(rules·versus·pov) — 그대로 ─────────────
def check_old(s: dict, cat: dict | None = None) -> list[str]:
    cat = cat or catalog()
    errs: list[str] = []
    e = next((x for x in cat["rules"] if x["n"] == s.get("id")), None)
    if not e:
        return [f"id {s.get('id')!r} 가 rules_catalog 에 없다"]
    if s.get("slug") != e["slug"]:
        errs.append(f"slug {s.get('slug')!r} ≠ catalog {e['slug']!r}")
    fmt = s.get("format")
    if fmt != e["format"]:
        errs.append(f"format {fmt!r} ≠ catalog {e['format']!r}")
    if s.get("look") not in T.LOOKS:
        errs.append(f"look 필수 — {', '.join(T.LOOKS)} 중 하나")
    title = s.get("title", "")
    if not title.endswith("#shorts") or len(title) > TITLE_MAX:
        errs.append(f"title 은 {TITLE_MAX}자 이하, '#shorts' 로 끝난다")
    if fmt == "rules" and not RULE_TITLE.match(title):
        errs.append("rules 제목은 규칙형으로 시작(Never / Don't / If You / Always …)")
    if fmt == "versus" and not VS_TITLE.search(title):
        errs.append("versus 제목에 'vs' 가 있어야 한다")
    if fmt == "pov" and not POV_TITLE.match(title):
        errs.append("pov 제목은 'POV:' 로 시작")
    hook = s.get("hook", "")
    if not hook or words(hook) > HOOK_WORDS or len(hook) > HOOK_CHARS:
        errs.append(f"hook(화면 위 두 줄)은 2–{HOOK_WORDS}단어·{HOOK_CHARS}자 이하")
    ls = s.get("lines") or []
    if not LINES[0] <= len(ls) <= LINES[1]:
        errs.append(f"lines {len(ls)}개 — {LINES[0]}–{LINES[1]}개")
    total = sum(words(x.get("say", "")) for x in ls) + words((s.get("gumi") or {}).get("say", ""))
    if not WORDS[0] <= total <= WORDS[1]:
        errs.append(f"말 {total}단어 — {WORDS[0]}–{WORDS[1]}단어(20–35초)")
    rule_nos = []
    for i, x in enumerate(ls):
        if not x.get("say") or not x.get("img"):
            errs.append(f"줄 {i}: say·img 필수")
            continue
        if words(x["say"]) > SAY_MAX:
            errs.append(f"줄 {i}: {words(x['say'])}단어 > {SAY_MAX}")
        if x.get("text") and len(x["text"]) > TEXT_MAX:
            errs.append(f"줄 {i}: 화면 글자 {len(x['text'])}자 > {TEXT_MAX}")
        if SHOW_GUMI.search(x["img"]):
            errs.append(f"줄 {i}: 그림에 구미를 그리지 않는다(구미는 끝의 치비 리액션으로만 나온다)")
        if x.get("look") is not None and x["look"] not in T.LOOKS:
            errs.append(f"줄 {i}: look {x['look']!r}")
        if x.get("rule") is not None:
            rule_nos.append(x["rule"])
        for t_ in (x["say"], x.get("text", "")):
            if T.BANNED.search(t_ or ""):
                errs.append(f"줄 {i}: 금지어")
            m = T.DATED.search(t_ or "")
            if m:
                errs.append(f"줄 {i}: 날짜 타는 말 {m.group(0)!r}")
    if ls and not (ls[0].get("text") and ls[0].get("img")):
        errs.append("첫 줄은 그림 + 화면 큰 글자(경고문) — 첫 1초에 읽혀야 한다")
    if fmt == "rules":
        if len(rule_nos) < 4 or rule_nos != list(range(1, len(rule_nos) + 1)):
            errs.append(f"rules: 규칙 번호 1부터 차례로 4개 이상(rule: 1,2,3…) — 지금 {rule_nos}")
        if not s.get("loop_back"):
            errs.append("rules: loop_back 필수 — 마지막 규칙이 첫 줄과 어떻게 이어지는지(루프) 한 줄")
    if fmt == "versus" and not s.get("vote"):
        errs.append("versus: vote 필수 — 댓글로 묻는 한 줄")
    g = s.get("gumi") or {}
    if g.get("react") not in REACTS:
        errs.append(f"gumi.react — {', '.join(REACTS)} 중 하나(끝에 치비 구미)")
    if not g.get("say") or words(g["say"]) > 16:
        errs.append("gumi.say — 구미의 판정·한마디 16단어 이하")
    if not s.get("source") or len(s.get("source", "")) < 20:
        errs.append("source 필수 — 어느 전설·관습에서 온 규칙인지(설명란에 그대로 나간다)")
    tags = s.get("tags") or []
    if not 6 <= len(tags) <= 15:
        errs.append("tags 6–15개")
    return errs


# ── 새 형식 검사(survival·compare·liminal) ─────────────
def clock_sec(label: str) -> float | None:
    """'0:00'·'1:30'·'1:00:00'·'DAY 3' → 초. 못 읽으면 None."""
    label = (label or "").strip()
    m = CLOCK.match(label)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = DAYS.match(label)
    return int(m.group(1)) * 86400 if m else None


# 생존 시계(2026-10-10 검수: 마리아나 편 시계가 출처 없는 1:00 에서 멈췄다 — '생존 시간 지어내기 금지'):
#   시각 꼴(0:12 · 3:00:00 · DAY 3)은 그 편 facts 에 같은 수 + 단위(second/minute/hour/day)가 있을 때만.
#   출처에 시간이 없으면 낱말(INSTANT · SECONDS · MINUTES · HOURS · DAYS)로 — 순서(먼저 → 다음)만 보여 준다.
WORD_T = re.compile(r"^(INSTANT|SECONDS|MINUTES|HOURS|DAYS|WEEKS)(\s+[A-Z][A-Z ]{0,17})?$")
WORD_RANK = {"INSTANT": 0, "SECONDS": 1, "MINUTES": 60, "HOURS": 3600, "DAYS": 86400, "WEEKS": 604800}
UNITS = (("second", 1), ("minute", 60), ("hour", 3600), ("day", 86400))


def clock_word(label: str) -> str | None:
    m = WORD_T.match((label or "").strip())
    return m.group(1) if m else None


def clock_lb(label: str) -> float | None:
    """박자 시각의 아래 한계(초) — 순서 검사용. 낱말은 WORD_RANK."""
    w = clock_word(label)
    return float(WORD_RANK[w]) if w else clock_sec(label)


def _num_vals(text: str) -> list[float]:
    out = []
    for x in NUM.findall(text or ""):
        try:
            out.append(float(x.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def clock_backed(label: str, facts: list[str]) -> bool:
    """시각 꼴 박자가 facts 의 '수 + 단위'에 기대는가. 0:00(시작)은 늘 된다."""
    sec = clock_sec(label)
    if sec is None:
        return False
    if sec == 0:
        return True

    def has(v: float, unit: str) -> bool:
        for f in facts:
            if unit not in f.lower():
                continue
            if any(abs(x - v) <= 0.05 * v + 1e-9 or round(x) == v for x in _num_vals(f)):
                return True
        return False

    if DAYS.match(label.strip()):
        return has(sec / 86400, "day")
    if any(has(sec / k, u) for u, k in UNITS if sec / k >= 1):
        return True
    h, rem = divmod(int(sec), 3600)
    m, ss = divmod(rem, 60)
    parts = [(h, "hour"), (m, "minute"), (ss, "second")]
    return all(has(v, u) for v, u in parts if v)


def nums(text: str) -> set[str]:
    """글 속 숫자(쉼표 뺌) — '10,935 m' → {'10935'}."""
    return {x.replace(",", "").rstrip(".") for x in NUM.findall(text or "")}


def lines_of(s: dict) -> list[dict]:
    """형식마다 다른 줄 목록(beats·items·lines)을 한 가지로."""
    return s.get({"survival": "beats", "compare": "items"}.get(s.get("format"), "lines")) or []


def all_text(s: dict) -> list[tuple[str, str]]:
    out = [(k, s.get(k) or "") for k in ("title", "hook", "situation", "description_hook", "teaser", "loop_back")]
    for i, x in enumerate(lines_of(s)):
        for k in ("say", "text", "img", "name", "label"):
            out.append((f"줄 {i}.{k}", str(x.get(k) or "")))
    out.append(("gumi.say", (s.get("gumi") or {}).get("say", "")))
    out += [("tags", t) for t in (s.get("tags") or [])]
    return out


def _norm_img(p: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (p or "").lower()).strip()


def siblings(path: str) -> list[dict]:
    """같은 폴더의 다른 대본(누적 브랜치 routine/tales_rules) — 그림 재사용 검사용."""
    out = []
    for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(path)), "R*.json"))):
        if os.path.abspath(f) == os.path.abspath(path):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except (OSError, ValueError):
            pass
    return out


def check_new(s: dict, sc: dict | None = None, others: list[dict] | None = None) -> list[str]:
    sc = sc or shorts()
    errs: list[str] = []
    e = entry(s.get("id"), sc) if isinstance(s.get("id"), int) else None
    if not e:
        return [f"id {s.get('id')!r} 가 shorts_catalog 에 없다"]
    fmt = s.get("format")
    if fmt != e["format"]:
        return [f"format {fmt!r} ≠ catalog {e['format']!r}"]
    if s.get("slug") != e["slug"]:
        errs.append(f"slug {s.get('slug')!r} ≠ catalog {e['slug']!r}")
    if s.get("part") != e["part"]:
        errs.append(f"part {s.get('part')!r} ≠ catalog {e['part']}")
    if s.get("look") not in LOOKS:
        errs.append(f"look 필수 — {', '.join(LOOKS)} 중 하나")
    title = s.get("title", "")
    if not title.endswith("#shorts") or len(title) > TITLE_MAX:
        errs.append(f"title 은 {TITLE_MAX}자 이하, '#shorts' 로 끝난다")
    pm = PART_TITLE.search(title)
    if fmt in ("survival", "compare") and not (pm and int(pm.group(1)) == e["part"]):
        errs.append(f"제목에 'Pt.{e['part']}' 가 있어야 한다(시리즈 번호)")
    if fmt == "survival" and not SURVIVAL_TITLE.match(title):
        errs.append("survival 제목은 'How Long Would You Last …' 로 시작")
    if fmt == "compare" and not COMPARE_TITLE.search(title):
        errs.append("compare 제목에 'Ranked' 또는 'by Size'")
    if fmt == "liminal" and not LIMINAL_TITLE.search(title):
        errs.append("liminal 제목에 'Rules' 또는 'Theory'")
    hook = s.get("hook", "")
    if not hook or words(hook) > HOOK_WORDS or len(hook) > HOOK_CHARS:
        errs.append(f"hook(화면 위)은 2–{HOOK_WORDS}단어·{HOOK_CHARS}자 이하")
    # 금지 주제·금지어·날짜 타는 말 — 대본의 모든 글자
    for where, t_ in all_text(s):
        m = BANNED_TOPICS.search(t_)
        if m:
            errs.append(f"{where}: 금지 주제 {m.group(0)!r}(설화·한국·실존 피해자·프랜차이즈·SCP·Backrooms)")
        if PROFANITY.search(t_):
            errs.append(f"{where}: 금지어")
        m = DATED.search(t_)
        if m and where != "teaser":
            errs.append(f"{where}: 날짜 타는 말 {m.group(0)!r}")
    # 출처 — catalog 의 출처에서만(지어낸 URL 금지)
    srcs = s.get("sources") or []
    allowed = set(e.get("sources") or [])
    for u in srcs:
        if not re.match(r"^https?://", u or "") or u not in allowed:
            errs.append(f"sources: {u!r} 는 catalog 출처가 아니다 — catalog sources 에서 그대로 옮긴다")
    fact_nums = set().union(*[nums(f["fact"]) for f in e.get("facts") or []]) if e.get("facts") else set()
    ls = lines_of(s)
    imgs = []
    total = words((s.get("gumi") or {}).get("say", ""))
    for i, x in enumerate(ls):
        say, text, img = x.get("say") or "", x.get("text") or "", x.get("img") or ""
        total += words(say)
        if not say or not img:
            errs.append(f"줄 {i}: say·img 필수")
            continue
        if words(say) > BEAT_SAY_MAX:
            errs.append(f"줄 {i}: {words(say)}단어 > {BEAT_SAY_MAX}")
        if NO_FOX.search(img):
            errs.append(f"줄 {i}: 그림에 구미·여우를 그리지 않는다(구미는 목소리만)")
        if IMG_TEXT.search(img):
            errs.append(f"줄 {i}: 그림 프롬프트에 글자·로고 말 금지(화면 글자는 코드가 쓴다)")
        imgs.append(_norm_img(img))
        # 숫자 → 출처 필수(창작 liminal 은 '사실처럼 보이는 숫자'만)
        blob = f"{say} {text} {x.get('label') or ''}"
        if fmt == "liminal":
            need = bool(FACT_NUM.search(CLOCK_TIME.sub("", blob)))
            got = nums(CLOCK_TIME.sub("", blob)) if need else set()
        else:
            got = nums(blob)
            need = bool(got) or fmt in ("survival", "compare")   # survival·compare 는 줄마다 사실 한 개 = 출처 한 개
        si = x.get("src")
        if need:
            if not srcs:
                errs.append(f"줄 {i}: 숫자·사실이 있는데 sources 가 비었다 — 출처 없는 숫자는 못 올린다")
            elif not isinstance(si, int) or not 0 <= si < len(srcs):
                errs.append(f"줄 {i}: src(=sources 번호) 필수 — 지금 {si!r}")
        stray = sorted(n for n in got if n not in fact_nums)
        if stray and fmt != "liminal":
            errs.append(f"줄 {i}: 숫자 {', '.join(stray)} 가 catalog facts 에 없다 — 숫자는 facts 에서만")
        if fmt == "liminal" and got:
            errs.append(f"줄 {i}: 창작(liminal)에 사실처럼 보이는 숫자 {', '.join(sorted(got))} — 빼거나 시각·층 번호로")
    if len(set(imgs)) != len(imgs):
        errs.append("같은 그림 프롬프트를 두 번 쓰지 않는다(편 안에서도)")
    if others:
        seen = {_norm_img(x.get("img")) for o in others if o.get("id") != s.get("id") for x in lines_of(o)}
        dup = [i for i, p in enumerate(imgs) if p in seen]
        if dup:
            errs.append(f"줄 {dup}: 다른 편과 같은 그림 프롬프트 — 편마다 새 그림(재사용 금지)")
    lo, hi = NEW_WORDS[fmt]
    if not lo <= total <= hi:
        errs.append(f"말 {total}단어 — {lo}–{hi}단어")
    g = s.get("gumi") or {}
    if not g.get("say") or words(g["say"]) > GUMI_MAX:
        errs.append(f"gumi.say — 구미(목소리만)의 판정 한 줄 {GUMI_MAX}단어 이하")
    # 구미 한 줄의 숫자도 facts 에서만(확률 odds 는 판정이라 뺀다) — 비교('탐사선은 127분')는 여기로 온다
    g_stray = sorted(n for n in nums(g.get("say", "")) - nums(str(g.get("odds", ""))) if n not in fact_nums)
    if g_stray and fmt != "liminal":
        errs.append(f"gumi.say: 숫자 {', '.join(g_stray)} 가 catalog facts 에 없다")
    tz = s.get("teaser")
    if tz is not None:
        if fmt == "liminal":
            errs.append("liminal 은 teaser 없음 — 끝 → 첫 장면 루프가 핵심")
        elif f"PT.{e['part'] + 1}" not in tz.upper().replace(" ", "") or len(tz) > 44:
            errs.append(f"teaser 는 44자 이하, 'Pt.{e['part'] + 1}' 를 담는다(rules.py next 의 teaser_idea)")
    if fmt == "survival":
        errs += _check_survival(s, ls, g, e)
    elif fmt == "compare":
        errs += _check_compare(s, ls)
    else:
        errs += _check_liminal(s, ls)
    tags = s.get("tags") or []
    if not 6 <= len(tags) <= 15:
        errs.append("tags 6–15개")
    if not s.get("description_hook"):
        errs.append("description_hook 필수 — 설명 첫 줄")
    return errs


def _check_survival(s: dict, ls: list[dict], g: dict, e: dict) -> list[str]:
    errs = []
    sit = s.get("situation") or ""
    if not sit or len(sit) > SITUATION_MAX:
        errs.append(f"situation(첫 1초 큰 글자 — 'FLOOR OF THE MARIANA TRENCH') 필수·{SITUATION_MAX}자 이하")
    if not BEATS[0] <= len(ls) <= BEATS[1]:
        errs.append(f"beats {len(ls)}개 — {BEATS[0]}–{BEATS[1]}개")
    facts = [f["fact"] for f in e.get("facts") or []]
    prev = -1.0
    for i, x in enumerate(ls):
        t = (x.get("t") or "").strip()
        lb = clock_lb(t)
        if lb is None:
            errs.append(f"박자 {i}: t {t!r} — '0:12'·'3:00:00'·'DAY 3' 꼴 또는 낱말 INSTANT·SECONDS·MINUTES·HOURS·DAYS")
            continue
        if i == 0 and t != "0:00":
            errs.append("첫 박자는 t '0:00' — 첫 1초에 시계가 0:00")
        if not clock_word(t) and not clock_backed(t, facts):
            errs.append(f"박자 {i}: 시각 {t} 이 catalog facts 에 없다 — 생존 시간을 지어내지 않는다"
                        f"(facts 에 '수 + second/minute/hour/day'가 있을 때만, 없으면 INSTANT·SECONDS·MINUTES 같은 낱말)")
        if lb < prev:
            errs.append(f"박자 {i}: 시계가 앞으로만 간다({t})")
        prev = lb
        if not x.get("text") or len(x["text"]) > BEAT_TEXT_MAX:
            errs.append(f"박자 {i}: text(큰 글자) 필수·{BEAT_TEXT_MAX}자 이하")
    if not ODDS.match(str(g.get("odds", ""))):
        errs.append("gumi.odds — '2%'·'0%'·'<1%' 꼴(끝 화면 \"Gumi's odds\")")
    elif not re.search(r"(?i)\bodds\b", g.get("say", "")):
        errs.append("gumi.say 에 'odds' — 끝 한 줄은 \"Gumi's odds: …\"")
    return errs


def _check_compare(s: dict, ls: list[dict]) -> list[str]:
    errs = []
    if s.get("scale") not in ("linear", "log"):
        errs.append("scale — linear | log(자릿수가 크게 다르면 log)")
    if not s.get("unit"):
        errs.append("unit 필수(막대 단위)")
    ranked = [x for x in ls if not x.get("twist")]
    if not ls or not ls[-1].get("twist") or len(ranked) != len(ls) - 1:
        errs.append("마지막 한 줄만 twist: true(반전)")
    if not ITEMS[0] <= len(ranked) <= ITEMS[1]:
        errs.append(f"순위 항목 {len(ranked)}개 — {ITEMS[0]}–{ITEMS[1]}개 + 반전 1")
    vals = []
    for i, x in enumerate(ls):
        if not x.get("name") or len(x["name"]) > NAME_MAX:
            errs.append(f"항목 {i}: name 필수·{NAME_MAX}자 이하")
        if x.get("twist") and x.get("value") is None:
            if not x.get("text"):
                errs.append(f"항목 {i}: 값 없는 반전은 text(큰 글자) 필수")
            continue
        v = x.get("value")
        if not isinstance(v, (int, float)) or v <= 0:
            errs.append(f"항목 {i}: value(양수) 필수")
            continue
        if not x.get("label") or len(x["label"]) > LABEL_MAX:
            errs.append(f"항목 {i}: label('13 M') 필수·{LABEL_MAX}자 이하")
        if not x.get("twist"):
            vals.append(v)
    if vals != sorted(vals):
        errs.append("순위 항목은 작은 것 → 큰 것 순서(value 오름차순)")
    if not ls or not ls[0].get("img"):
        errs.append("첫 항목 그림 필수")
    return errs


def _check_liminal(s: dict, ls: list[dict]) -> list[str]:
    errs = []
    if s.get("fiction") is not True:
        errs.append("fiction: true 필수 — 리미널은 분명한 창작(화면·설명에 FICTION)")
    if not LIM_LINES[0] <= len(ls) <= LIM_LINES[1]:
        errs.append(f"lines {len(ls)}개 — {LIM_LINES[0]}–{LIM_LINES[1]}개")
    if ls and not (ls[0].get("text") and ls[0].get("img")):
        errs.append("첫 줄은 그림 + 화면 큰 글자 — 첫 1초에 읽혀야 한다")
    nos = [x["rule"] for x in ls if x.get("rule") is not None]
    if len(nos) < 4 or nos != list(range(1, len(nos) + 1)):
        errs.append(f"규칙 번호 1부터 차례로 4개 이상(rule: 1,2,3…) — 지금 {nos}")
    for i, x in enumerate(ls):
        if x.get("text") and len(x["text"]) > TEXT_MAX:
            errs.append(f"줄 {i}: 화면 글자 {len(x['text'])}자 > {TEXT_MAX}")
    if not s.get("loop_back"):
        errs.append("loop_back 필수 — 마지막 규칙이 첫 줄로 어떻게 이어지는지(루프)")
    return errs


def check(s: dict, cat: dict | None = None, others: list[dict] | None = None) -> list[str]:
    if s.get("format") in NEW_FORMATS or (isinstance(s.get("id"), int) and s["id"] > 100):
        return check_new(s, others=others)
    return check_old(s, cat)


# ── 메타(제목·설명·태그) ───────────────────────────────
DISCLOSURE = ("Illustrations and the narrator's voice are AI-generated. The rules come from real East Asian legends, "
              "superstitions and internet folklore — retold for fun, not instructions. 13+.")
DISCLOSURE_FACT = ("Visuals and narration are AI-generated (realistic, but not real footage). Every number comes from the "
                   "sources above; the scenario is hypothetical — please don't try any of this. Host: Gumi (voice only).")
DISCLOSURE_FICTION = ("This is FICTION — an original liminal-space story, not a real place or event. Visuals and narration "
                      "are AI-generated. Host: Gumi (voice only). 13+.")
HASHTAGS = {"survival": "#shorts #howlongwouldyoulast #survival #science #space",
            "compare": "#shorts #sizecomparison #ranked #science #space",
            "liminal": "#shorts #liminalspace #liminal #rules #creepy"}
BASE_TAGS = {"survival": ["how long would you last", "survival", "science shorts", "nine tails tales"],
             "compare": ["size comparison", "ranked", "science shorts", "nine tails tales"],
             "liminal": ["liminal space", "liminal rules", "creepy rules", "nine tails tales"]}


def playlist_for(s: dict, sc: dict | None = None) -> tuple[str, str] | None:
    if s.get("format") not in NEW_FORMATS:
        return None
    sc = sc or shorts()
    ser = sc["series"][s["format"]]
    return ser["playlist"], ser["playlist_desc"]


def meta(s: dict, long_link: str | None = None) -> dict:
    fmt = s["format"]
    if fmt in NEW_FORMATS:
        lines = [s.get("description_hook") or s["hook"].capitalize() + ".", ""]
        if s.get("sources"):
            lines += ["Sources:"] + [f"- {u}" for u in s["sources"]] + [""]
        pl = playlist_for(s)
        if pl:
            lines += [f"Series: {pl[0]}"]
        if long_link:
            lines += [f"More from Gumi: {long_link}"]
        lines += ["", DISCLOSURE_FICTION if fmt == "liminal" else DISCLOSURE_FACT, "", HASHTAGS[fmt]]
        tags = list(dict.fromkeys((s.get("tags") or []) + BASE_TAGS[fmt]))
        return {"title": s["title"][:TITLE_MAX], "description": "\n".join(lines)[:4900], "tags": tags[:15]}
    lines = [s.get("description_hook") or s["hook"].capitalize() + ".", "",
             f"Where this comes from: {s['source']}"]
    if s.get("vote"):
        lines += ["", f"Vote in the comments: {s['vote']}"]
    if long_link:
        lines += ["", f"Full tales from Gumi: {long_link}"]
    lines += ["", DISCLOSURE, "",
              "#shorts #scary #horror #rules #creepy #folklore #" + {"rules": "scaryrules", "versus": "monsterbattle",
                                                                      "pov": "pov"}[s["format"]]]
    tags = list(dict.fromkeys((s.get("tags") or []) + ["scary rules", "horror shorts", "asian folklore", "nine tails tales"]))
    return {"title": s["title"][:TITLE_MAX], "description": "\n".join(lines)[:4900], "tags": tags[:15]}


def source_label(u: str) -> str:
    """화면 아래 작은 출처 표시('noaa.gov')."""
    h = urlparse(u).netloc.lower()
    h = re.sub(r"^(www|en|science|solarsystem|oceanexplorer|oceanservice|earthobservatory|svs|nssdc)\.", "", h)
    return h


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next")
    n.add_argument("--date", default=dt.date.today().isoformat())
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    a = ap.parse_args()
    if a.cmd == "next":
        es = on_date(dt.date.fromisoformat(a.date))
        if not es:
            print(json.dumps({"date": a.date, "count": 0, "entries": [], "none": True,
                              "why": "이날은 쓸 편이 없다(시험 시작 전·목록 끝·설화 목록 종료) — 쓰지 않는다"},
                             ensure_ascii=False))
            return 0
        print(json.dumps({"date": a.date, "count": len(es), "entries": es}, ensure_ascii=False, indent=1))
        return 0
    bad = 0
    for f in a.files:
        with open(f, encoding="utf-8") as fh:
            errs = check(json.load(fh), others=siblings(f))
        print(("❌ " if errs else "✅ ") + f)
        for x in errs:
            print("   - " + x)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
