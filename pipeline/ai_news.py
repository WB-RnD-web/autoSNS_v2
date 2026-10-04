#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 소식 쇼츠(하루 두 번 · 오전/저녁) — 루틴 대본을 ★코드로 검사한다.

2026-09-30. 왕별이 쇼츠에 'AI 소식' 토픽(topic=ai)을 더한다. 하루 2편(slot=am·pm),
같은 영상을 인스타(@zerocrew.studio)·쓰레드에도 올린다.

루틴 프롬프트의 "~해 주세요" 는 자주 무시된다(레포의 교훈). 그래서 지켜야 할 것은 전부
여기서 막는다 — 하나라도 못 넘으면 렌더도 업로드도 하지 않고 잡이 빨간불로 끝난다.
루틴은 git 을 손으로 만지지 않는다 — 슬롯·검사·올리기를 전부 이 파일로 한다:
    python pipeline/ai_news.py slot              # 지금 날짜·슬롯(am/pm)·파일 이름(시계로만 정한다)
    python pipeline/ai_news.py feed              # 오늘의 후보 기사(data/ai-news-feed) — ★출처는 여기서만
    python pipeline/ai_news.py feed --show ID    # 그 기사 본문 + 출처 뼈대(facts 는 본문에서 숫자째)
    python pipeline/ai_news.py history           # 최근 14일 AI 대본(같은 이야기·같은 형식 피하기)
    python pipeline/ai_news.py check <파일>      # 파이프라인과 똑같은 검사
    python pipeline/ai_news.py push <파일>       # 검사 통과 시 routine/ai_<slot> 에 올린다(= 실제 업로드)

피드(2026-10-01): 루틴 샌드박스는 기사 페이지를 못 연다(egress 차단). 원문은 ai-news-feed.yml 이
  인터넷이 열린 Actions 에서 받아 data/ai-news-feed 브랜치(feed/ai/<DATE>_<am|pm>.json)에 둔다
  (pipeline/ai_news_feed.py). 루틴은 git 으로 읽고, 검사는 출처를 이 피드와 대조한다.

막는 것
  · 이름·슬롯    output/news/<DATE>_ai_<am|pm>_storyboard.json · topic=ai · slot=am|pm
                 · date = 파일 날짜 = 오늘/어제(KST). 한 날짜에 슬롯 2개 = 하루 최대 2편
  · 출처         sources[] 마다 outlet·url·published_at·confirmed·facts, 그중 ★하나 이상은 48시간 안
  · 피드 대조    출처는 ★피드에 있는 기사만(URL) · published_at 은 피드 값 그대로 ·
                 facts·title 의 숫자는 전부 그 기사 본문(피드)에 있어야 한다
  · 중복         최근 14일 AI 대본(routine/ai_am·ai_pm 브랜치 + ledger + 유튜브 최근 업로드)과
                 출처 URL 이 같거나 제목이 비슷하면 탈락
  · 숫자         화면·제목·말에 쓴 아라비아 숫자는 전부 출처 facts 에 있어야 한다(지어낸 숫자 금지)
  · 확인 안 된 보도  confirmed=false 출처가 있으면 내레이션에 '보도됐/알려졌/전해졌…' 가 있어야 한다
  · 어려운 말     LLM·에이전트·딥페이크… 를 쓰면 glossary 에 쉬운 풀이를 두고 ★그 풀이를 말로 읽어야 한다
  · 첫 화면      hook 은 두 줄 · 렌더러(TOP_HOOK) 기준 글자 100px 이상 = 피드에서 한눈에 읽히는 큰 제목
  · 길이         읽는 글자 150~260자(≈30~50초) · 장면 4~7개 · 렌더 후 25~58초
  · 틀 돌려쓰기   format 이 직전 편과 달라야 · 최근 6편에 같은 format 2번까지 · 장면 구성이 최근 4편과 달라야
                 (하루 2편짜리 AI 쇼츠는 유튜브 '반복·대량 생산 콘텐츠' 정책의 표적이 되기 쉽다)
  · 캡션         인스타 ≤2,200자 · 쓰레드 ≤500자 · 둘 다 '왕별이' 언급 · 쓰레드 해시태그 딱 1개

★소재 단어(회사·제품 이름)는 규칙에 쓰지 않는다 — 모양·숫자·출처만 본다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

KST = dt.timezone(dt.timedelta(hours=9))

TOPIC = "ai"
SLOTS = {"am": "오전", "pm": "저녁"}           # 오전 ≈10:35 · 저녁 ≈19:15 KST 발행(루틴 cron 은 PR 참고)
BRANCHES = ("routine/ai_am", "routine/ai_pm")  # ★누적 브랜치 — 지난 대본이 곧 중복 검사 이력이다
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_ai_(am|pm)_storyboard\.json$")
BRAND = "일상공감뉴스 · AI"
ACCENT = "#5EC8D8"          # 거의 검정 배경(#0A0808) 대비 10:1 — 정치(#8FB0C9)·운세(금색)와 겹치지 않는 청록
MARKER = "AI 소식"            # 설명란 마지막 줄 'AI 소식 <날짜> <오전|저녁>' — 유튜브 쪽 중복 업로드 판정에 쓴다

# 피드 — 기사 원문(ai-news-feed.yml 이 Actions 에서 받아 둔다). ★main·routine/* 가 아닌 데이터 전용 브랜치.
FEED_BRANCH = "data/ai-news-feed"
FEED_DIR = "feed/ai"
FEED_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(am|pm)\.json$")
FEED_FILE_DAYS = 3          # 오늘 포함 4일치 파일을 본다(피드에서 밀려난 기사도 대조되게)
FEED_TIME_SLACK = 60        # published_at 이 피드와 이만큼(초) 넘게 다르면 탈락
# 피드 밖에서도 출처로 받아 줄 도메인 — 루틴이 ★실제로 열어 볼 수 있는 곳만. 지금은 없다(전부 egress 차단).
FEED_ALLOW_DOMAINS: tuple[str, ...] = ()

FRESH_HOURS = 48
DEDUPE_DAYS = 14
SIMILAR = 0.5               # 제목 글자쌍(bigram) 자카드 — 0.5 이상이면 같은 이야기로 본다
SCENES = (4, 7)
SAY_CHARS = (150, 260)      # Supertonic 실측 초당 ~5.2자 + 장면 전환 → 약 30~50초
CPS = 5.2
HOOK_LINES = 2
HOOK_MIN_PX = 100           # motion_short TOP_HOOK 기준. 8자 안쪽 두 줄이면 125~130px
HOOK_HL_MAX = 4
HOOK_TITLE_MAX = 24         # 유튜브 제목 = '<hook_title> #shorts'
HEADLINE_MAX = 40
IG_MAX = 2200
THREADS_MAX = 500
IG_TAGS_MAX = 5
CHANNEL = "왕별이"
GLOSS_MAX = 40
# 2026-10-04: 소식은 '10초 한 장'(news_card, 11초)으로 바뀌었다 — 아래 끝을 8초로. 위 끝(한 호흡)은 그대로.
DUR_SEC = (8.0, 58.0)
TYPES = ("hook", "stat", "gauge", "trend", "quote", "keypoint", "statement")

# 형식 — 매번 같은 틀이면 '대량 생산'으로 읽힌다. 코드가 돌려쓰기를 막는다(check §틀).
FORMATS = {
    "explain": "무슨 일 → 왜 중요 → 내 생활엔",
    "guard":   "이런 수법 조심 → 막는 법 2~3가지",
    "compare": "전과 후 · 이전과 이번을 나란히",
    "number":  "숫자 하나로 시작 → 그 숫자의 뜻",
    "qa":      "시청자가 물을 질문 2~3개에 답",
    "myth":    "흔한 오해 → 실제 사실",
}
# '보통 사람에게 뭐가 달라지나' — 2주 뒤 어느 각도가 먹혔는지 가르는 기준이기도 하다.
ANGLES = ("일자리", "돈", "사기·딥페이크", "건강", "생활 도구", "가족·교육", "규칙·정책")
TAGS = ["AI", "인공지능", "AI뉴스", "AI소식", "쇼츠", "shorts"]

# 55세 이상 시청자에게 풀이 없이는 안 들리는 말. 쓰면 glossary 풀이를 ★말로 읽어야 한다.
JARGON = ("LLM", "AGI", "GPU", "NPU", "TPU", "API", "RAG", "SaaS",
          "파라미터", "매개변수", "토큰", "에이전트", "멀티모달", "파인튜닝", "미세조정", "추론 모델", "추론형",
          "벤치마크", "오픈소스", "온디바이스", "할루시네이션", "환각", "프롬프트", "딥페이크", "생성형",
          "머신러닝", "딥러닝", "데이터센터", "클라우드", "빅테크", "거대언어모델", "초거대")
# 확인 안 된 보도를 전할 때의 말끝
HEDGE = re.compile(r"(보도(됐|되었|했|하고|된)|전해졌|전했|알려졌|알려져|라고\s*(합니다|해요|했|밝혔|전했|주장)|"
                   r"주장|관측|추정|것으로\s*(보|알려|전해)|예정이라고|계획이라고|검토\s*중|확인되지\s*않)")
EXTRA_BAN = ("무조건",)
# 검색 결과·모음 링크는 출처가 아니다(원문 기사·공식 발표 주소를 써야 한다)
SEARCH_URL = re.compile(r"(?i)^https?://([^/]*\.)?(google\.[a-z.]+/search|news\.google\.com|search\.naver\.com|"
                        r"search\.daum\.net|bing\.com/search|duckduckgo\.com|t\.co/|bit\.ly/)")
SAMPLE_URL = re.compile(r"(?i)^https?://([^/]*\.)?example\.(com|org|net)/")
URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s/]+/\S+$")
TAG = re.compile(r"</?[a-zA-Z][^>]*>")
COUNT_WORD = re.compile(r"\d+\s*(?=가지|단계|번째)")   # '막는 법 3가지' 같은 구성 숫자는 사실 주장이 아니다


# ── 작은 도구들 ────────────────────────────────────────────
def is_ai(topic_or_sb) -> bool:
    t = topic_or_sb.get("topic") if isinstance(topic_or_sb, dict) else topic_or_sb
    t = str(t or "").strip().lower()
    return t == TOPIC or t.startswith(TOPIC + "_")


def slot_key(sb: dict) -> str:
    return f"{sb.get('date', '')}_{TOPIC}_{sb.get('slot', '')}"


def marker(sb: dict) -> str:
    return f"{MARKER} {sb.get('date', '')} {SLOTS.get(sb.get('slot'), sb.get('slot', ''))}"


def _slot_order(slot: str) -> int:
    return 1 if slot == "pm" else 0


def strip_tags(s) -> str:
    return TAG.sub("", s if isinstance(s, str) else "")


def spoken_chars(text: str) -> int:
    return len(re.findall(r"[가-힣A-Za-z0-9]", text or ""))


def norm_url(u: str) -> str:
    u = (u or "").strip()
    u = re.sub(r"#.*$", "", u)
    m = re.match(r"(?i)^https?://([^/?]+)(.*)$", u)
    if not m:
        return u.lower()
    host, rest = m.group(1).lower(), m.group(2)
    host = re.sub(r"^(www|m|mobile)\.", "", host)
    path, _, query = rest.partition("?")
    keep = [q for q in query.split("&") if q and not re.match(r"(?i)(utm_[a-z]+|fbclid|gclid|ref|from)=", q)]
    return host + path.rstrip("/") + (("?" + "&".join(keep)) if keep else "")


def parse_when(s) -> dt.datetime | None:
    s = str(s or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):          # 날짜만 → 그날 00:00 KST(보수적으로 오래된 쪽)
        try:
            return dt.datetime.fromisoformat(s).replace(tzinfo=KST)
        except ValueError:
            return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=KST)


def _norm_num(n: str) -> str:
    if "." in n:
        a, b = n.split(".", 1)
        a, b = a.lstrip("0") or "0", b.rstrip("0")
        return f"{a}.{b}" if b else a
    return n.lstrip("0") or "0"


def numbers(text: str) -> set[str]:
    """아라비아 숫자(천 단위 쉼표·소수 정규화). '3가지'·'2단계' 같은 구성 숫자는 뺀다."""
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", strip_tags(text or ""))
    t = COUNT_WORD.sub(" ", t)
    return {_norm_num(x) for x in re.findall(r"\d+(?:\.\d+)?", t)}


def _num_value(v) -> str | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = abs(v)
    return _norm_num(str(int(v)) if float(v).is_integer() else repr(float(v)))


def _bigrams(s: str) -> set[str]:
    n = re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())
    return {n[i:i + 2] for i in range(len(n) - 1)} if len(n) > 1 else ({n} if n else set())


def similarity(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    return len(A & B) / len(A | B) if A and B else 0.0


SCREEN_KEYS = ("lines", "points", "text", "sub", "label", "pill", "closer", "attr")


def _flat(v) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return " ".join(_flat(x) for x in v)
    return ""


def screen_text(sb: dict) -> str:
    parts = [sb.get("hook_title", ""), sb.get("headline", ""), sb.get("thumbnail_text", "")]
    for sc in sb.get("scenes") or []:
        parts += [_flat(sc.get(k)) for k in SCREEN_KEYS if sc.get(k)]
    return strip_tags(" ".join(p for p in parts if isinstance(p, str)))


def narration(sb: dict) -> str:
    return " ".join(str(sc.get("narration") or "") for sc in sb.get("scenes") or [])


def _has_term(text: str, term: str) -> bool:
    if re.fullmatch(r"[A-Za-z]+", term):
        return re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text, re.I) is not None
    return term in text


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ── 이력 ─────────────────────────────────────────────────
def entry(sb: dict, key: str | None = None) -> dict:
    """중복·돌려쓰기 판정에 쓰는 요약(ledger 에도 이 모양으로 남긴다)."""
    return {
        "key": key or slot_key(sb),
        "date": str(sb.get("date", "")),
        "slot": str(sb.get("slot", "")),
        "headline": str(sb.get("headline", "")),
        "hook_title": str(sb.get("hook_title", "")),
        "urls": sorted({norm_url(s.get("url", "")) for s in sb.get("sources") or []
                        if isinstance(s, dict) and s.get("url")}),
        "format": str(sb.get("format", "")),
        "angle": str(sb.get("angle", "")),
        "types": [str(sc.get("type", "")) for sc in sb.get("scenes") or []],
        "pill": str(((sb.get("scenes") or [{}])[0] or {}).get("pill", "")),
    }


def _git(*args: str, root: str | None = None) -> str:
    try:
        r = subprocess.run(["git", "-C", root or ROOT, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def fetch_branches(refs=BRANCHES, root: str | None = None) -> None:
    """루틴·파이프라인 둘 다 같은 이력을 보도록 원격 AI 브랜치를 받아 둔다(없으면 조용히 넘어간다)."""
    for ref in refs:
        _git("fetch", "-q", "origin", f"+refs/heads/{ref}:refs/remotes/origin/{ref}", root=root)


def entries_from_refs(refs=BRANCHES, root: str | None = None) -> list[dict]:
    out = []
    for ref in refs:
        r = f"origin/{ref}"
        for name in _git("ls-tree", "-r", "--name-only", r, "--", "output/news", root=root).splitlines():
            m = NAME_RE.match(os.path.basename(name.strip()))
            if not m:
                continue
            try:
                sb = json.loads(_git("show", f"{r}:{name.strip()}", root=root) or "null")
            except json.JSONDecodeError:
                continue
            if isinstance(sb, dict):
                sb.setdefault("date", m.group(1))
                sb.setdefault("slot", m.group(2))
                out.append(entry(sb, f"{m.group(1)}_{TOPIC}_{m.group(2)}"))
    return out


def entries_from_dirs(dirs) -> list[dict]:
    out = []
    for d in dirs or []:
        for p in sorted(glob.glob(os.path.join(d, "*_ai_*_storyboard.json"))):
            m = NAME_RE.match(os.path.basename(p))
            if not m:
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    sb = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(sb, dict):
                sb.setdefault("date", m.group(1))
                sb.setdefault("slot", m.group(2))
                out.append(entry(sb, f"{m.group(1)}_{TOPIC}_{m.group(2)}"))
    return out


def entries_from_ledger(led: dict | None) -> list[dict]:
    out = []
    for k, v in (led or {}).items():
        if isinstance(v, dict) and isinstance(v.get("ai"), dict):
            e = dict(v["ai"])
            e["key"] = k
            out.append(e)
    return out


def load_history(today: dt.date, exclude: str = "", *, ledger: dict | None = None, dirs=None,
                 refs=BRANCHES, days: int = DEDUPE_DAYS, root: str | None = None) -> list[dict]:
    """최근 days 일의 AI 대본 요약 — 최신 순. 같은 키는 한 번만(파일 > ledger)."""
    seen: dict[str, dict] = {}
    for e in entries_from_refs(refs, root) + entries_from_dirs(dirs) + entries_from_ledger(ledger):
        if e.get("key") and e["key"] not in seen:
            seen[e["key"]] = e
    lo = today - dt.timedelta(days=days)
    keep = []
    for k, e in seen.items():
        try:
            d = dt.date.fromisoformat(str(e.get("date", ""))[:10])
        except ValueError:
            continue
        if k != exclude and lo <= d <= today:
            keep.append(e)
    return sorted(keep, key=lambda e: (e.get("date", ""), _slot_order(e.get("slot", ""))), reverse=True)


# ── 피드(기사 원문 — data/ai-news-feed) ───────────────────────────
def feed_id(url: str) -> str:
    """기사 짧은 id — 정규화한 URL 의 해시 앞 8자리(피드를 여러 번 만들어도 같은 기사는 같은 id)."""
    return hashlib.sha1(norm_url(url).encode("utf-8")).hexdigest()[:8]


def _feed_doc(raw: str):
    try:
        doc = json.loads(raw or "null")
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def feed_docs_from_refs(refs=(FEED_BRANCH,), root: str | None = None) -> list[tuple[str, dict]]:
    out = []
    for ref in refs:
        r = f"origin/{ref}"
        for name in _git("ls-tree", "-r", "--name-only", r, "--", FEED_DIR, root=root).splitlines():
            base = os.path.basename(name.strip())
            if FEED_NAME_RE.match(base):
                doc = _feed_doc(_git("show", f"{r}:{name.strip()}", root=root))
                if doc:
                    out.append((base, doc))
    return out


def feed_docs_from_dirs(dirs) -> list[tuple[str, dict]]:
    out = []
    for d in dirs or []:
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            if FEED_NAME_RE.match(os.path.basename(p)):
                try:
                    with open(p, encoding="utf-8") as f:
                        doc = _feed_doc(f.read())
                except OSError:
                    doc = None
                if doc:
                    out.append((os.path.basename(p), doc))
    return out


def feed_index(docs, today: dt.date, days: int = FEED_FILE_DAYS) -> dict:
    """피드 파일들 → {files(최신 먼저), docs, by_url(정규화 URL → 판들), by_id, error}.
    같은 기사가 여러 파일에 있으면 판을 모두 모은다(최신 파일 판이 앞)."""
    lo, hi = today - dt.timedelta(days=days), today + dt.timedelta(days=1)
    keep = []
    for name, doc in docs:
        m = FEED_NAME_RE.match(name)
        try:
            d = dt.date.fromisoformat(m.group(1)) if m else None
        except ValueError:
            d = None
        if d and lo <= d <= hi:
            keep.append(((d.isoformat(), _slot_order(m.group(2))), name, doc))
    keep.sort(key=lambda x: x[0], reverse=True)
    files, by_url, by_id, used = [], {}, {}, {}
    for _, name, doc in keep:
        if name in used:
            continue
        used[name] = doc
        files.append(name)
        for it in doc.get("items") or []:
            if isinstance(it, dict) and it.get("url"):
                u = norm_url(it["url"])
                by_url.setdefault(u, []).append(it)
                by_id.setdefault(str(it.get("id") or feed_id(it["url"])), u)
    err = None if files else f"{FEED_BRANCH} 에 최근 {days + 1}일 피드 파일이 없다(ai-news-feed.yml 이 돌았나?)"
    return {"files": files, "docs": used, "by_url": by_url, "by_id": by_id, "error": err}


def load_feed(now: dt.datetime | None = None, refs=(FEED_BRANCH,), dirs=None, root: str | None = None) -> dict:
    """원격 피드 브랜치(먼저 fetch_branches((FEED_BRANCH,)))와 dirs 의 피드 파일을 읽는다."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    return feed_index(feed_docs_from_refs(refs, root) + feed_docs_from_dirs(dirs), now.date())


def feed_candidates(feed: dict, now: dt.datetime, skip_urls=(), hours: int = FRESH_HOURS) -> list[dict]:
    """고를 수 있는 기사 — 48시간 안 · skip_urls(14일 안 다룬 기사) 제외 · 최신 순. 기사마다 최신 판 하나."""
    now = now.astimezone(KST)
    skip = {norm_url(u) if "://" in u else u for u in skip_urls}
    out = []
    for u, vers in (feed or {}).get("by_url", {}).items():
        it = vers[0]
        w = parse_when(it.get("published_at"))
        if u in skip or not w or not (-1 <= (now - w).total_seconds() / 3600 <= hours):
            continue
        out.append(it)
    return sorted(out, key=lambda it: parse_when(it.get("published_at")), reverse=True)


def _feed_nums(text: str) -> set[str]:
    return numbers(unicodedata.normalize("NFKC", text or ""))


def _date_nums(when: dt.datetime | None) -> set[str]:
    """기사 날짜(연·월·일)는 본문에 안 적혀 있어도 기사의 일부로 본다('올해' = 2026)."""
    if not when:
        return set()
    k = when.astimezone(KST)
    return {str(k.year), str(k.year % 100), str(k.month), str(k.day)}


def _domain(url: str) -> str:
    m = re.match(r"(?i)^https?://([^/?#]+)", (url or "").strip())
    return re.sub(r"^(www|m|mobile)\.", "", m.group(1).lower()) if m else ""


def feed_problems(srcs, feed: dict | None) -> list[tuple[str, bool]]:
    """[(문제, 느슨 모드에서 경고로 내릴지)]. 출처는 피드의 기사만 · published_at 은 피드 값 ·
    facts·title 의 숫자는 그 기사 본문(피드)에 있어야 한다."""
    if feed is None or feed.get("error") or not feed.get("by_url"):
        why = (feed or {}).get("error") or "피드를 읽지 않았다"
        return [(f"출처 피드({FEED_BRANCH})와 대조할 수 없다: {why} — 원문 대조 없이는 올리지 않는다", True)]
    out = []
    for i, s in enumerate(srcs):
        if not isinstance(s, dict) or not str(s.get("url") or "").strip():
            continue
        vers = feed["by_url"].get(norm_url(s["url"]))
        if not vers:
            dom = _domain(s["url"])
            if not any(dom == d or dom.endswith("." + d) for d in FEED_ALLOW_DOMAINS):
                out.append((f"sources[{i}] {s['url']} 는 피드에 없는 기사다 — `python pipeline/ai_news.py feed` "
                            "목록의 기사만 출처로 쓴다(검색 결과·요약은 출처가 아니다)", True))
            continue
        theirs = [parse_when(v.get("published_at")) for v in vers]
        mine = parse_when(s.get("published_at"))
        if mine and not any(t and abs((mine - t).total_seconds()) <= FEED_TIME_SLACK for t in theirs):
            ref = next((v.get("published_at") for v in vers if v.get("published_at")), "?")
            out.append((f"sources[{i}].published_at {s.get('published_at')!r} 가 피드의 {ref!r} 와 다르다 "
                        "— 피드 값을 그대로 옮긴다", False))
        have: set[str] = set()
        for v, t in zip(vers, theirs):
            have |= _feed_nums(f"{v.get('title', '')}\n{v.get('text', '')}") | _date_nums(t)
        facts = " ".join(x for x in (s.get("facts") or []) if isinstance(x, str))
        miss = sorted(_feed_nums(f"{facts} {s.get('title', '')}") - have, key=float)
        if miss:
            out.append((f"sources[{i}] facts·title 의 숫자 {', '.join(miss)} 가 기사 본문(피드)에 없다 — "
                        f"`python pipeline/ai_news.py feed --show {feed_id(s['url'])}` 본문에서 숫자째 옮긴다", False))
    return out


# ── 검사 ─────────────────────────────────────────────────
def _url_problem(url: str) -> tuple[str, bool] | None:
    """(문제, 느슨 모드에서 경고로 내릴지) 또는 None."""
    url = (url or "").strip()
    if not url:
        return "url 이 없다", False
    if not URL_RE.match(url):
        return f"url 형식이 이상하다({url!r}) — 기사·발표 원문 주소(https://…/경로)", False
    if SEARCH_URL.match(url):
        return f"검색·모음 링크는 출처가 아니다({url}) — 원문 기사·공식 발표 주소", False
    if SAMPLE_URL.match(url):
        return f"견본 주소({url}) — 실제 출처가 아니다", True
    return None


def check(sb: dict, path: str = "", now: dt.datetime | None = None, history: list[dict] | None = None,
          lenient: bool = False, feed: dict | None = None) -> tuple[list[str], list[str]]:
    """(오류, 경고). 오류가 하나라도 있으면 올리지 않는다.

    feed = load_feed() 결과. ★None(안 읽음)이면 '대조할 수 없다'로 탈락 — 빠뜨려서 새는 일이 없게.
    lenient=True(수동 점검 전용)는 날짜·신선도·중복·돌려쓰기·견본 주소·피드에 없음만 경고로 내린다.
    형식·출처 모양·숫자(피드 본문 대조 포함)·용어·캡션 규칙은 느슨 모드에서도 오류다.
    """
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    history = history or []
    errs: list[str] = []
    soft: list[str] = []

    def bad(msg: str, relax: bool = False) -> None:
        (soft if relax else errs).append(msg)

    # ① 이름·슬롯·날짜 — 슬롯이 파일 이름에 박혀 있어야 같은 슬롯을 두 번 올리지 않는다
    name = os.path.basename(path or "")
    m = NAME_RE.match(name)
    if not m:
        bad(f"파일 이름 {name!r} — output/news/<DATE>_ai_<am|pm>_storyboard.json 이어야 한다")
    else:
        if str(sb.get("date")) != m.group(1):
            bad(f"date({sb.get('date')!r})가 파일 이름 날짜({m.group(1)})와 다르다")
        if sb.get("slot") != m.group(2):
            bad(f"slot({sb.get('slot')!r})이 파일 이름 슬롯({m.group(2)})과 다르다")
    if str(sb.get("topic", "")).strip().lower() != TOPIC:
        bad(f"topic 은 {TOPIC!r} 이어야 한다(지금 {sb.get('topic')!r})")
    if sb.get("slot") not in SLOTS:
        bad(f"slot 은 {'/'.join(SLOTS)} 중 하나({sb.get('slot')!r})")
    try:
        d = dt.date.fromisoformat(str(sb.get("date", "")))
        today = now.date()
        if not (today - dt.timedelta(days=1) <= d <= today):
            bad(f"대본 날짜 {d} 가 오늘({today})·어제가 아니다 — 늦게 도착한 원고는 올리지 않는다", True)
    except ValueError:
        d = None
        bad(f"date 형식 오류({sb.get('date')!r}) — YYYY-MM-DD")

    # ② 출처 — 하나 이상은 48시간 안
    srcs = sb.get("sources")
    fresh = 0
    if not isinstance(srcs, list) or not srcs:
        bad("sources 가 비었다 — {outlet, url, published_at, confirmed, facts} 를 1개 이상")
        srcs = []
    for i, s in enumerate(srcs):
        if not isinstance(s, dict):
            bad(f"sources[{i}] 가 객체가 아니다 — {{outlet, url, published_at, confirmed, facts}}")
            continue
        if not str(s.get("outlet", "")).strip():
            bad(f"sources[{i}].outlet(매체·기관 이름)이 없다")
        prob = _url_problem(s.get("url", ""))
        if prob:
            bad(f"sources[{i}]: {prob[0]}", prob[1])
        when = parse_when(s.get("published_at"))
        if not when:
            bad(f"sources[{i}].published_at 이 없거나 형식 오류({s.get('published_at')!r}) — "
                "예: 2026-09-30T09:12:00+09:00")
        else:
            age_h = (now - when).total_seconds() / 3600
            if age_h < -1:
                bad(f"sources[{i}].published_at {when.isoformat()} 가 미래다")
            elif age_h <= FRESH_HOURS and not prob:
                fresh += 1
        facts = s.get("facts")
        if not isinstance(facts, list) or not [f for f in facts if isinstance(f, str) and f.strip()]:
            bad(f"sources[{i}].facts 가 비었다 — 기사에서 옮긴 핵심 사실(숫자 포함) 1줄 이상")
        if not isinstance(s.get("confirmed"), bool):
            bad(f"sources[{i}].confirmed(true/false)가 없다 — 공식 발표·확정=true, 보도·유출·전망=false")
    if srcs and not fresh:
        bad(f"{FRESH_HOURS}시간 안에 나온 출처(url+published_at)가 하나도 없다 — 오늘의 소식이 아니다", True)

    # ②-b 피드 대조 — 루틴은 기사 페이지를 못 연다. 원문은 Actions 가 받아 둔 피드에만 있다.
    for msg, relax in feed_problems(srcs, feed):
        bad(msg, relax)

    # ③ 중복 — 최근 14일 AI 대본과 URL·제목
    mine_urls = {norm_url(s.get("url", "")) for s in srcs if isinstance(s, dict) and s.get("url")}
    my_titles = [t for t in (sb.get("headline", ""), sb.get("hook_title", "")) if t]
    for e in history:
        dup = mine_urls & set(e.get("urls") or [])
        if dup:
            bad(f"출처 URL 이 {e.get('key')} 와 겹친다: {sorted(dup)[0]} — 14일 안에 다룬 기사", True)
            continue
        for mt in my_titles:
            hit = next((t for t in (e.get("headline", ""), e.get("hook_title", ""))
                        if t and similarity(mt, t) >= SIMILAR), None)
            if hit:
                bad(f"제목 {mt!r} 이 {e.get('key')} 의 {hit!r} 와 비슷하다"
                    f"(유사도 {similarity(mt, hit):.2f}) — 14일 안에 다룬 이야기", True)
                break

    # ④ 틀 돌려쓰기 — 형식·장면 구성·pill
    scenes = sb.get("scenes") if isinstance(sb.get("scenes"), list) else []
    fmt = sb.get("format")
    if fmt not in FORMATS:
        bad(f"format 은 {', '.join(FORMATS)} 중 하나({fmt!r})")
    if sb.get("angle") not in ANGLES:
        bad(f"angle 은 {', '.join(ANGLES)} 중 하나({sb.get('angle')!r}) — '보통 사람에게 뭐가 달라지나'")
    here = (str(sb.get("date", "")), _slot_order(str(sb.get("slot", ""))))
    prev = [e for e in history if (e.get("date", ""), _slot_order(e.get("slot", ""))) < here]
    types = [str(sc.get("type", "")) for sc in scenes if isinstance(sc, dict)]
    pill = str((scenes[0] if scenes and isinstance(scenes[0], dict) else {}).get("pill", ""))
    if fmt in FORMATS and prev:
        if prev[0].get("format") == fmt:
            bad(f"format {fmt!r} 이 직전 편({prev[0].get('key')})과 같다 — 다른 형식으로", True)
        elif sum(e.get("format") == fmt for e in prev[:6]) >= 2:
            bad(f"format {fmt!r} 이 최근 6편에 이미 2번 — 다른 형식으로", True)
    for e in prev[:4]:
        if types and list(e.get("types") or []) == types:
            bad(f"장면 구성 {'-'.join(types)} 이 {e.get('key')} 와 똑같다 — 장면 종류·순서를 바꿔라", True)
            break
    if prev and pill and prev[0].get("pill") == pill:
        bad(f"pill {pill!r} 이 직전 편과 같다 — 사안에 맞게 바꿔라", True)

    # ⑤ 장면·첫 화면
    if not (SCENES[0] <= len(scenes) <= SCENES[1]):
        bad(f"장면 {len(scenes)}개 — {SCENES[0]}~{SCENES[1]}개")
    for i, sc in enumerate(scenes):
        if not isinstance(sc, dict) or sc.get("type") not in TYPES:
            bad(f"scenes[{i}].type 은 {', '.join(TYPES)} 중 하나")
            continue
        if not str(sc.get("narration") or "").strip():
            bad(f"scenes[{i}] 내레이션이 비었다")
        if sc["type"] == "statement" and sc.get("highlight") and sc["highlight"] not in (sc.get("text") or ""):
            bad(f"scenes[{i}].highlight 가 text 안에 글자 그대로 없다(효과가 안 걸린다)")
    hook = scenes[0] if scenes and isinstance(scenes[0], dict) else {}
    if hook.get("type") != "hook":
        bad("첫 장면은 type 'hook' 이어야 한다 — 화면 위 큰 두 줄 제목(TOP_HOOK)")
    else:
        lines = [strip_tags(x) for x in (hook.get("lines") or []) if isinstance(x, str) and x.strip()]
        hl = hook.get("highlight") or ""
        if len(lines) != HOOK_LINES:
            bad(f"hook.lines 는 딱 {HOOK_LINES}줄(지금 {len(lines)}줄) — 첫 화면 큰 제목")
        if not hl or not any(hl in ln for ln in lines):
            bad("hook.highlight 가 없거나 lines 안에 글자 그대로 없다")
        elif len(hl) > HOOK_HL_MAX:
            bad(f"hook.highlight {hl!r} 가 {len(hl)}자 — {HOOK_HL_MAX}자 이내")
        if lines:
            try:
                import motion_short as M
                px = M._uniform("h1", lines, M.BOX, big=hl if any(hl and hl in ln for ln in lines) else "",
                                big_ratio=M.TOP_BIG_RATIO)
                if px < HOOK_MIN_PX:
                    bad(f"첫 화면 제목이 {px}px 로 작아진다(기준 {HOOK_MIN_PX}px) — 한 줄을 8자 안쪽으로")
            except Exception as e:  # noqa: BLE001
                bad(f"첫 화면 글자 크기를 잴 수 없다: {e}")

    # ⑥ 길이
    say = spoken_chars(narration(sb))
    if not (SAY_CHARS[0] <= say <= SAY_CHARS[1]):
        bad(f"읽는 글자 {say}자(≈{say / CPS:.0f}초) — {SAY_CHARS[0]}~{SAY_CHARS[1]}자(≈30~50초)")

    # ⑦ 제목·금지어
    ht, hd = str(sb.get("hook_title", "")).strip(), str(sb.get("headline", "")).strip()
    if not ht or len(ht) > HOOK_TITLE_MAX:
        bad(f"hook_title {len(ht)}자 — 1~{HOOK_TITLE_MAX}자(유튜브 제목이 된다)")
    if not hd or len(hd) > HEADLINE_MAX:
        bad(f"headline {len(hd)}자 — 1~{HEADLINE_MAX}자(사실 그대로)")
    if ht and ht == hd:
        bad("headline 과 hook_title 이 같다 — headline 은 사실, hook_title 은 클릭 이유")
    try:
        import news_copy_check
        ban = tuple(news_copy_check.banlist()) + EXTRA_BAN
    except Exception:  # noqa: BLE001
        ban = EXTRA_BAN
    body = screen_text(sb) + " " + narration(sb)
    hits = [w for w in ban if w and w in body]
    if hits:
        bad("반응을 요구하는 말: " + ", ".join(hits) + " — 세기는 사실(숫자·출처)로 낸다")

    # ⑧ 숫자 — 화면·제목·말의 아라비아 숫자는 전부 출처 facts 에 있어야 한다
    allowed: set[str] = set()
    for s in srcs:
        if isinstance(s, dict):
            allowed |= numbers(" ".join(x for x in (s.get("facts") or []) if isinstance(x, str)))
            allowed |= numbers(str(s.get("title", "")))
    if d:
        allowed |= {str(d.year), str(d.year % 100), str(d.month), str(d.day)}
    used = numbers(screen_text(sb)) | numbers(narration(sb))
    for sc in scenes:
        if isinstance(sc, dict) and sc.get("type") in ("stat", "gauge", "trend"):
            v = _num_value(sc.get("to"))
            if v is not None:
                used.add(v)
    invented = sorted(used - allowed, key=lambda x: float(x))
    if invented:
        bad("출처 facts 에 없는 숫자: " + ", ".join(invented)
            + " — 숫자는 기사에서 옮긴 facts 에 그대로 있어야 한다(지어낸 숫자 금지)")

    # ⑨ 어려운 말 — glossary 풀이를 말로 읽는다
    gl = {}
    for g in sb.get("glossary") or []:
        if isinstance(g, dict) and g.get("term"):
            gl[str(g["term"]).strip().lower()] = str(g.get("plain") or "").strip()
    said = _ws(narration(sb))
    for term in JARGON:
        if not _has_term(body, term):
            continue
        plain = gl.get(term.lower())
        if not plain:
            bad(f"어려운 말 {term!r} — glossary 에 {{term, plain}} 쉬운 풀이를 넣고 그 풀이를 내레이션에서 읽어라")
        elif len(plain) > GLOSS_MAX:
            bad(f"{term!r} 풀이가 {len(plain)}자 — {GLOSS_MAX}자 이내 한 줄")
        elif _ws(plain) not in said:
            bad(f"{term!r} 풀이 {plain!r} 가 내레이션에 글자 그대로 없다 — 귀로 들어야 풀린다")

    # ⑩ 확인 안 된 보도
    if any(isinstance(s, dict) and s.get("confirmed") is False for s in srcs) and not HEDGE.search(said):
        bad("확인 안 된 보도(confirmed=false)인데 내레이션이 단정한다 — '~라고 보도됐어요/알려졌어요'")

    # ⑪ 캡션·설명
    plat = sb.get("platforms") if isinstance(sb.get("platforms"), dict) else {}
    yt = plat.get("youtube") or {}
    if not str(yt.get("description") or "").strip():
        bad("platforms.youtube.description 이 비었다")
    ig = str((plat.get("instagram") or {}).get("caption") or "")
    th = str((plat.get("threads") or {}).get("text") or "")
    if not ig.strip() or len(ig) > IG_MAX:
        bad(f"인스타 캡션 {len(ig)}자 — 1~{IG_MAX}자")
    elif CHANNEL not in ig:
        bad(f"인스타 캡션에 유튜브 채널 '{CHANNEL}' 언급이 없다")
    elif len(re.findall(r"#\S+", ig)) > IG_TAGS_MAX:
        n_ig = len(re.findall(r"#\S+", ig))
        bad(f"인스타 해시태그 {n_ig}개 — {IG_TAGS_MAX}개 이하")
    if not th.strip() or len(th) > THREADS_MAX:
        bad(f"쓰레드 글 {len(th)}자 — 1~{THREADS_MAX}자")
    else:
        if CHANNEL not in th:
            bad(f"쓰레드 글에 유튜브 채널 '{CHANNEL}' 언급이 없다")
        n_tag = len(re.findall(r"#\S+", th))
        if n_tag != 1:
            bad(f"쓰레드 해시태그 {n_tag}개 — 주제 태그 딱 1개(쓰레드는 태그 하나만 주제로 쓴다)")
    if not str(sb.get("thumbnail_hook") or "").strip():
        bad("thumbnail_hook(영어 배경 그림 프롬프트)이 비었다 — 비면 검정 배경 카드뉴스가 된다")

    return (errs, soft) if lenient else (errs + soft, [])


def check_duration(sec: float) -> str | None:
    if sec is None:
        return None
    if not (DUR_SEC[0] <= sec <= DUR_SEC[1]):
        return f"렌더 길이 {sec:.1f}초 — {DUR_SEC[0]:.0f}~{DUR_SEC[1]:.0f}초 밖(쇼츠·릴스 모두 한 호흡)"
    return None


# ── 렌더·업로드 준비 ────────────────────────────────────────
def normalize(sb: dict) -> dict:
    """루틴이 빠뜨려도 되는 모양 값은 ★코드가 채운다(검사로 떨어뜨릴 일이 아니다)."""
    sb.setdefault("accent", ACCENT)
    for i, sc in enumerate(sb.get("scenes") or []):
        if isinstance(sc, dict):
            sc["brand"] = BRAND
            if i == 0 and sc.get("type") == "hook":
                sc.setdefault("ghost", "AI")
    return sb


def youtube_description(sb: dict) -> str:
    """루틴 설명 + 출처 목록(주소·날짜) + 슬롯 표식 한 줄. 표식은 유튜브 쪽 중복 판정에 쓴다."""
    base = str(((sb.get("platforms") or {}).get("youtube") or {}).get("description") or "").strip()
    have = norm_url(base)
    rows = []
    for s in sb.get("sources") or []:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        w = parse_when(s.get("published_at"))
        when = f"{w.astimezone(KST).month}/{w.astimezone(KST).day}" if w else ""
        if norm_url(s["url"]) not in have:
            rows.append(f"· {s.get('outlet', '')} ({when}) {s['url']}".replace(" ()", ""))
    out = base
    if rows:
        out += "\n\n📰 출처\n" + "\n".join(rows)
    return (out + f"\n\n{marker(sb)}").strip()[:4900]


# ── 유튜브 쪽 이중 확인(ledger 캐시가 날아가도 같은 슬롯을 두 번 올리지 않게) ──────
def recent_uploads(yt, max_items: int = 100) -> list[dict]:
    """내 채널 최근 업로드(제목·설명). channels.list 1 + playlistItems.list 1~2 = 3 units 이하."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out, token = [], None
    while len(out) < max_items:
        r = yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50, pageToken=token).execute()
        for it in r.get("items", []):
            sn = it.get("snippet", {})
            out.append({"title": sn.get("title", ""), "description": sn.get("description", ""),
                        "published": sn.get("publishedAt", ""),
                        "video_id": (sn.get("resourceId") or {}).get("videoId")})
        token = r.get("nextPageToken")
        if not token:
            break
    return out


def youtube_conflicts(sb: dict, uploads: list[dict], now: dt.datetime | None = None) -> tuple[str | None, list[str]]:
    """(이미 올라간 영상 id 또는 None, 중복 오류들)."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    mk = marker(sb)
    mine_urls = {norm_url(s.get("url", "")) for s in sb.get("sources") or [] if isinstance(s, dict) and s.get("url")}
    errs = []
    for u in uploads:
        desc = u.get("description") or ""
        if f"{MARKER} 20" not in desc:
            continue                                  # AI 소식 영상만 본다
        if mk in desc:
            return u.get("video_id") or "?", []
        when = parse_when(u.get("published"))
        if when and (now - when).days > DEDUPE_DAYS:
            continue
        theirs = {norm_url(x) for x in re.findall(r"https?://\S+", desc)}
        if mine_urls & theirs:
            errs.append(f"출처 URL 이 이미 올린 영상({u.get('video_id')})과 겹친다")
            continue
        title = re.sub(r"\s*#shorts\s*$", "", u.get("title", ""), flags=re.I)
        for mt in (sb.get("hook_title", ""), sb.get("headline", "")):
            if mt and similarity(mt, title) >= SIMILAR:
                errs.append(f"제목 {mt!r} 이 이미 올린 영상({u.get('video_id')}) {title!r} 와 비슷하다")
                break
    return None, errs


# ── 루틴용 도구: 슬롯 정하기 · 검사 · 올리기(git 을 손으로 하지 않게) ───────────────
def slot_now(now: dt.datetime | None = None) -> tuple[str, str]:
    """지금(KST) 돌면 어느 슬롯인가 — ★시계로만 정한다(루틴이 고르지 않는다).

    05~15시 = 그날 오전(am) · 15~24시 = 그날 저녁(pm) · 0~5시 = 늦게 돈 ★전날 저녁(pm).
    """
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    if 5 <= now.hour < 15:
        return now.date().isoformat(), "am"
    if now.hour >= 15:
        return now.date().isoformat(), "pm"
    return (now.date() - dt.timedelta(days=1)).isoformat(), "pm"


def _run(args: list[str], cwd: str) -> tuple[int, str]:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def check_file(path: str, now: dt.datetime | None = None, root: str | None = None,
               lenient: bool = False) -> tuple[list[str], list[str], dict, list[dict]]:
    """파일 하나 검사(루틴 자기 점검·push 공용). 이미 원격 AI 브랜치에 있는 슬롯이면 오류.
    피드는 ★원격 피드 브랜치(origin/data/ai-news-feed)에서만 읽는다 — 로컬 파일로 바꿔 끼울 수 없다."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    with open(path, encoding="utf-8") as f:
        sb = json.load(f)
    key = slot_key(sb)
    news_dir = os.path.join(root or ROOT, "output", "news")
    hist = load_history(now.date(), exclude=key, dirs=[news_dir, os.path.dirname(os.path.abspath(path))], root=root)
    errs, warns = check(sb, path, now=now, history=hist, lenient=lenient, feed=load_feed(now, root=root))
    if key in {e["key"] for e in entries_from_refs(root=root)}:
        errs.append(f"{key} 는 이미 {'/'.join(BRANCHES)} 에 있다 — 같은 슬롯은 다시 올리지 않는다")
    return errs, warns, sb, hist


def push(path: str, now: dt.datetime | None = None, root: str | None = None,
         remote: str = "origin") -> tuple[bool, str]:
    """검사를 통과한 대본을 routine/ai_<slot> 에 올린다. ★세션 브랜치(claude/*)를 건드리지 않는다.

    임시 작업 폴더(git worktree)에서 원격 routine/ai_<slot>(없으면 main) 위에 파일 하나만 커밋해 push 한다.
    같은 슬롯 파일이 이미 있으면 올리지 않는다. 이 push 가 ai-news.yml 을 깨운다(= 실제 업로드).
    """
    root = root or ROOT
    name = os.path.basename(path)
    m = NAME_RE.match(name)
    if not m:
        return False, f"파일 이름 {name!r} — <DATE>_ai_<am|pm>_storyboard.json 이어야 한다"
    fetch_branches(BRANCHES + (FEED_BRANCH,), root=root)
    _run(["git", "fetch", "-q", "--no-tags", remote, f"+refs/heads/main:refs/remotes/{remote}/main"], root)
    errs, _, sb, _ = check_file(path, now=now, root=root)
    if errs:
        return False, "검사 실패 — 먼저 고쳐라:\n  " + "\n  ".join(errs)
    branch = f"routine/ai_{m.group(2)}"
    has_branch = _run(["git", "rev-parse", "--verify", "-q", f"{remote}/{branch}"], root)[0] == 0
    base = f"{remote}/{branch}" if has_branch else f"{remote}/main"
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="ai_news_push_")
    wt = os.path.join(tmp, "wt")
    rc, out = _run(["git", "worktree", "add", "-q", "--detach", wt, base], root)
    if rc:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f"작업 폴더를 못 만들었다({base}): {out[-300:]}"
    try:
        dest = os.path.join(wt, "output", "news", name)
        if os.path.exists(dest):
            return False, f"{branch} 에 {name} 가 이미 있다 — 같은 슬롯은 다시 올리지 않는다"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(path, dest)
        ident = [] if _run(["git", "config", "user.email"], root)[1] else [
            "-c", "user.name=AI 소식 루틴", "-c", "user.email=ai-news-routine@users.noreply.github.com"]
        _run(["git", "add", f"output/news/{name}"], wt)
        rc, out = _run(["git", *ident, "commit", "-q", "-m", f"chore: AI 소식 대본(루틴) {slot_key(sb)}"], wt)
        if rc:
            return False, f"커밋 실패: {out[-300:]}"
        rc, out = _run(["git", "push", "-q", remote, f"HEAD:refs/heads/{branch}"], wt)
        if rc:
            return False, f"push 실패 — push 를 한 번 더 돌려라: {out[-300:]}"
        return True, f"{branch} 에 올렸다({name}) — Actions(ai-news.yml)가 렌더·업로드한다"
    finally:
        _run(["git", "worktree", "remove", "--force", wt], root)
        shutil.rmtree(tmp, ignore_errors=True)


def _print_history(hist: list[dict]) -> None:
    if not hist:
        print("(최근 AI 대본 없음)")
    for e in hist:
        print(f"· {e.get('key')} [{e.get('format')}/{e.get('angle')}] {e.get('hook_title')} | {e.get('headline')}")
        print(f"    장면 {'-'.join(e.get('types') or [])} · pill {e.get('pill')!r}")
        for u in e.get("urls") or []:
            print(f"    {u}")


def _hm(s) -> str:
    w = parse_when(s)
    return f"{w.astimezone(KST):%m/%d %H:%M}" if w else "?"


def feed_listing(feed: dict, now: dt.datetime, hist: list[dict] | None = None, show_all: bool = False) -> tuple[str, int]:
    """(루틴이 읽을 후보 목록 글, 후보 수)."""
    now = now.astimezone(KST)
    d, slot = slot_now(now)
    want = f"{d}_{slot}.json"
    used = sorted({u for e in hist or [] for u in e.get("urls") or []})
    lines = [f"📰 AI 소식 피드 — {FEED_BRANCH} · 이번 슬롯 {d} {slot}({SLOTS[slot]})"]
    if feed.get("error"):
        lines.append(f"❌ {feed['error']}")
        lines.append("   → 원문이 없으면 쓰지 않는다. 오늘 이 슬롯은 올리지 않고 사유만 남긴다.")
        return "\n".join(lines), 0
    files = feed.get("files") or []
    gen = (feed.get("docs", {}).get(files[0]) or {}).get("generated_at", "") if files else ""
    lines.append(f"   파일: {', '.join(files[:4])}{' …' if len(files) > 4 else ''} (최신 {_hm(gen)} 생성)")
    if want not in files:
        lines.append(f"   ⚠️ 이번 슬롯 파일({want})이 아직 없다 — 직전 파일들로 대신한다(피드 워크플로가 늦는 중)")
    cands = feed_candidates(feed, now, () if show_all else used)
    n_used = len(feed_candidates(feed, now)) - len(cands)
    lines.append(f"   후보 {len(cands)}건(48시간 안)" + (f" · 14일 안 다룬 기사 {n_used}건은 뺐다" if n_used > 0 else ""))
    lines.append("")
    for it in cands:
        tag = " · 공식 발표" if it.get("official") else ""
        lang = " · EN" if it.get("lang") == "en" else ""
        lines.append(f"[{it.get('id') or feed_id(it['url'])}] {_hm(it.get('published_at'))} · {it.get('outlet', '')}"
                     f"{tag}{lang} · 본문 {len(it.get('text') or ''):,}자")
        lines.append(f"    {it.get('title', '')}")
    lines.append("")
    lines.append("→ 고른 기사 본문 + 출처 뼈대: python pipeline/ai_news.py feed --show <id>  (여러 개면 id 를 이어서)")
    lines.append("  ★출처는 이 목록의 기사만. facts 는 --show 본문에서 숫자째 옮긴다. published_at 은 그대로 복사.")
    return "\n".join(lines), len(cands)


def feed_show(feed: dict, ident: str) -> str | None:
    u = (feed.get("by_id") or {}).get(ident) or ((feed.get("by_url") or {}).get(norm_url(ident)) and norm_url(ident))
    vers = (feed.get("by_url") or {}).get(u or "")
    if not vers:
        return None
    it = vers[0]
    skel = {"outlet": it.get("outlet", ""), "title": it.get("title", ""), "url": it.get("url", ""),
            "published_at": it.get("published_at", ""),
            "confirmed": bool(it.get("official")),
            "facts": ["<아래 본문 문장을 숫자째 그대로>"]}
    return "\n".join([
        f"── [{it.get('id') or feed_id(it['url'])}] {it.get('outlet', '')} · {it.get('published_at', '')}"
        + (" · 공식 발표" if it.get("official") else ""),
        f"제목: {it.get('title', '')}",
        f"주소: {it.get('url', '')}",
        f"본문({len(it.get('text') or ''):,}자 / 원문 {it.get('text_chars', '?')}자, 앞부분):",
        "",
        it.get("text") or "",
        "",
        "출처 뼈대(sources[] 에 넣는다 — confirmed 는 공식 발표·확정이면 true, 한 매체 보도·전망이면 false):",
        json.dumps(skel, ensure_ascii=False),
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description="AI 소식 쇼츠 — 슬롯·이력·검사·올리기(루틴용)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sl = sub.add_parser("slot", help="지금 돌면 어느 날짜·슬롯인가(시계로만 정한다)")
    sl.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    fd = sub.add_parser("feed", help="오늘의 후보 기사(원문 피드) — 출처는 여기서만 고른다")
    fd.add_argument("--show", nargs="+", metavar="ID", help="이 기사들의 본문 + 출처 뼈대")
    fd.add_argument("--all", action="store_true", help="14일 안 다룬 기사도 보이기")
    fd.add_argument("--dir", help="(로컬 미리보기) 피드 브랜치 대신 이 폴더의 <DATE>_<slot>.json")
    fd.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    h = sub.add_parser("history", help="최근 14일 AI 대본(중복·형식 피하기용)")
    h.add_argument("--days", type=int, default=DEDUPE_DAYS)
    c = sub.add_parser("check", help="대본 검사(루틴은 push 전에 반드시)")
    c.add_argument("paths", nargs="+")
    c.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    c.add_argument("--lenient", action="store_true", help="수동 점검: 날짜·신선도·중복을 경고로")
    pu = sub.add_parser("push", help="검사 통과한 대본을 routine/ai_<slot> 에 올린다(= 실제 업로드가 시작된다)")
    pu.add_argument("path")
    for x in (h, c, fd):
        x.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):     # 윈도 콘솔(cp949)에서도 한글·기호가 깨져 죽지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    now = dt.datetime.fromisoformat(a.now).astimezone(KST) if getattr(a, "now", None) else dt.datetime.now(KST)
    if a.cmd == "slot":
        fetch_branches()
        d, slot = slot_now(now)
        name = f"{d}_{TOPIC}_{slot}_storyboard.json"
        import tempfile
        taken = f"{d}_{TOPIC}_{slot}" in {e["key"] for e in entries_from_refs()}
        out_dir = os.path.join(tempfile.gettempdir(), "ai_news")      # 레포 밖 — 세션 브랜치에 커밋될 일이 없다
        os.makedirs(out_dir, exist_ok=True)
        print(f"DATE={d}\nSLOT={slot}\nLABEL={SLOTS[slot]}\nNAME={name}\n"
              f"WRITE_TO={os.path.join(out_dir, name)}\n"
              f"BRANCH=routine/ai_{slot}\nTAKEN={'yes' if taken else 'no'}")
        return 0
    if a.cmd == "push":
        ok, msg = push(a.path)
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    if not a.no_fetch:
        fetch_branches(BRANCHES + (FEED_BRANCH,))
    if a.cmd == "feed":
        feed = load_feed(now, refs=() if a.dir else (FEED_BRANCH,), dirs=[a.dir] if a.dir else None)
        if a.show:
            miss = 0
            for ident in a.show:
                out = feed_show(feed, ident)
                print(out if out else f"❌ 피드에 {ident!r} 가 없다 — `python pipeline/ai_news.py feed` 목록의 id")
                print()
                miss += out is None
            return 1 if miss else 0
        text, n = feed_listing(feed, now, load_history(now.date(), dirs=[os.path.join(ROOT, "output", "news")]),
                               show_all=a.all)
        print(text)
        return 0 if n else 1
    if a.cmd == "history":
        _print_history(load_history(now.date(), dirs=[os.path.join(ROOT, "output", "news")], days=a.days))
        return 0

    bad = 0
    for p in a.paths:
        errs, warns, sb, hist = check_file(p, now=now, lenient=a.lenient)
        print(f"── {os.path.basename(p)} · 읽는 글자 {spoken_chars(narration(sb))}자"
              f"(≈{spoken_chars(narration(sb)) / CPS:.0f}초) · 이력 {len(hist)}편")
        for w in warns:
            print(f"   ⚠️ {w}")
        for e in errs:
            print(f"   ❌ {e}")
        if not errs:
            print("   ✅ 통과")
        bad += len(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
