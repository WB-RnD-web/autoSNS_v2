#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 소식 피드 — 기사 원문을 ★인터넷이 열린 곳(GitHub Actions)에서 받아 data/ai-news-feed 브랜치에 둔다.

왜 (2026-09-30 첫 저녁 편이 아무것도 못 올렸다):
  루틴 샌드박스에서 WebSearch 는 되지만 기사 페이지 WebFetch 는 egress 프록시에 막힌다
  (EGRESS_BLOCKED: www.seoul.co.kr · m.sedaily.com · m.news.nate.com). 검색 요약만으로는 숫자가
  서로 달라 루틴이 옳게 건너뛰었다 — 이대로면 거의 매번 같다.
  SCP 위키 때(PR #71)와 같은 해법: 원문은 인터넷이 열린 곳에서 받아 git 에 두고, 루틴은 git 으로 읽는다.
    ai-news-feed.yml(09:37·18:37 KST) → 이 파일 build → data/ai-news-feed 의 feed/ai/<DATE>_<am|pm>.json
    루틴: python pipeline/ai_news.py feed          → 후보 목록(여기서만 고른다)
          python pipeline/ai_news.py feed --show ID → 본문 + 출처 뼈대(facts 는 본문에서 숫자째 옮긴다)
    검사: ai_news.check 가 출처 URL·published_at·facts 숫자를 이 피드와 대조한다(루틴·Actions 둘 다).

    python pipeline/ai_news_feed.py build --dir <feed/ai 폴더>   # 받아서 <DATE>_<slot>.json(+오래된 파일 정리)
    python pipeline/ai_news_feed.py probe                        # 피드 주소마다 몇 건 오는지(점검)

지키는 것
  · 무료·공개 RSS/Atom 과 공식 보도자료 피드만(로그인·유료벽 없음). robots.txt 를 지킨다.
  · User-Agent 에 이름과 레포 주소를 밝힌다. 같은 호스트는 1초 간격, 기사 페이지는 피드당 10건·한 번에 110건 이하.
  · 48시간 안 · AI 관련(한/영 키워드 — AI 전문 피드는 전부)만. URL 로 중복 제거.
  · 본문은 앞 4,000자(피드 본문이 충분하면 페이지를 열지 않는다). 과기정통부 보도자료는 본문이 첨부에만
    있어서, 부처가 '기계판독용'으로 함께 올리는 ODT 첨부를 읽는다.
  · 기사 페이지가 막히면(OpenAI 403 등) 공식 발표는 피드 요약만이라도 남긴다(목록에 '본문 150자'처럼 보인다).
표준 라이브러리만 쓴다(워크플로에 pip 설치 없음).
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import glob
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ai_news as A  # noqa: E402  (슬롯·URL 정규화·id 를 검사 쪽과 똑같이 쓴다)

KST = A.KST
UTC = dt.timezone.utc
UA = "autoSNS-ai-news-feed/1.0 (+https://github.com/WB-RnD-web/autoSNS_v2; RSS reader, 2 runs/day)"
WINDOW_HOURS = A.FRESH_HOURS          # 48
TEXT_MAX = 4000
TEXT_MIN = 200                        # 이보다 짧으면(요약 한 줄뿐) 숫자를 옮길 재료가 못 된다
TEXT_MIN_OFFICIAL = 100               # 공식 발표는 요약만 있어도 남긴다(OpenAI 는 기사 페이지가 403)
FEED_BODY_ENOUGH = 1200               # 피드 본문이 이만큼 있으면 페이지를 열지 않는다(짧으면 맛보기 — The Verge 등)
PER_SOURCE = 10                       # 한 피드에서 고르는 후보(최신 순) = 한 호스트에 여는 페이지 상한
PAGE_BUDGET = 110                     # 한 번에 여는 기사 페이지 수 상한(피드를 돌아가며 나눠 쓴다)
HOST_GAP = 1.0                        # 같은 호스트 요청 간격(초)
KEEP_DAYS = 3                         # 브랜치에 남기는 파일(오늘 포함 4일치)
MAX_BYTES = 6_000_000
LINK_ON, LINK_OFF = chr(1), chr(2)    # 링크 글 표시 — 한 줄이 거의 링크면(관련 기사·태그 목록) 버린다
ZWSP, BOM = chr(0x200B), chr(0xFEFF)

# 2026-09-30 이 PC 에서 전부 열어 봤다(건수는 PR 설명). 정책브리핑(korea.kr) RSS 는 서비스가 중단됐다
# (사이트 공지 '정책브리핑 RSS 서비스 제공 중단 안내') — 부처 보도자료는 부처 RSS 로 직접 받는다.
# 못 쓴 것: 경찰청·개인정보위(RSS 없음) · Anthropic·Meta(RSS 없음) · MS AI 블로그(410) · 디지털데일리·뉴시스(깨진 XML)
SOURCES: list[dict] = [
    # 공식 보도자료
    {"id": "msit", "outlet": "과학기술정보통신부", "lang": "ko", "official": True, "ai_only": False,
     "url": "https://www.msit.go.kr/user/rss/rss.do?bbsSeqNo=94"},
    {"id": "fsc", "outlet": "금융위원회", "lang": "ko", "official": True, "ai_only": False,
     "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"},
    {"id": "newswire_it", "outlet": "뉴스와이어(기업 보도자료)", "lang": "ko", "official": True, "ai_only": False,
     "url": "https://api.newswire.co.kr/rss/industry/600"},
    # 국내 매체
    {"id": "yna", "outlet": "연합뉴스", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://www.yna.co.kr/rss/news.xml"},
    {"id": "yna_industry", "outlet": "연합뉴스", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://www.yna.co.kr/rss/industry.xml"},
    {"id": "aitimes", "outlet": "AI타임스", "lang": "ko", "official": False, "ai_only": True,
     "url": "https://www.aitimes.com/rss/allArticle.xml"},
    {"id": "etnews", "outlet": "전자신문", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://rss.etnews.com/Section901.xml"},
    {"id": "zdnet_kr", "outlet": "지디넷코리아", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://feeds.feedburner.com/zdkorea"},
    {"id": "bloter", "outlet": "블로터", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://www.bloter.net/rss/allArticle.xml"},
    {"id": "hankyung_it", "outlet": "한국경제", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://www.hankyung.com/feed/it"},
    {"id": "donga_it", "outlet": "동아일보", "lang": "ko", "official": False, "ai_only": False,
     "url": "https://rss.donga.com/science.xml"},
    # 해외 — 공식 발표
    {"id": "openai", "outlet": "OpenAI", "lang": "en", "official": True, "ai_only": True,
     "url": "https://openai.com/news/rss.xml"},
    {"id": "google_ai", "outlet": "Google", "lang": "en", "official": True, "ai_only": True,
     "url": "https://blog.google/technology/ai/rss/"},
    {"id": "deepmind", "outlet": "Google DeepMind", "lang": "en", "official": True, "ai_only": True,
     "url": "https://deepmind.google/blog/rss.xml"},
    {"id": "nvidia", "outlet": "NVIDIA", "lang": "en", "official": True, "ai_only": False,
     "url": "https://blogs.nvidia.com/feed/"},
    # 해외 매체(AI 분류 피드)
    {"id": "verge_ai", "outlet": "The Verge", "lang": "en", "official": False, "ai_only": True,
     "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"id": "techcrunch_ai", "outlet": "TechCrunch", "lang": "en", "official": False, "ai_only": True,
     "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
]

# AI 관련 판정 — 제목에 있거나, 본문에 3번 이상. (소재 단어로 '검사'하지는 않는다 — 이건 후보 거르기일 뿐)
AI_RE = re.compile(
    r"(?<![A-Za-z])(?:A\.?I|AGI|LLMs?|GPTs?|ChatGPT|OpenAI|GenAI|DeepMind)(?![A-Za-z])"
    r"|(?i:artificial intelligence|machine learning|deep learning|generative|chatbot|deepfake|"
    r"large language model|neural network)"
    r"|인공지능|생성형|챗GPT|챗지피티|챗봇|딥페이크|거대언어모델|초거대|머신러닝|딥러닝|오픈AI|제미나이|코파일럿")
AI_TEXT_HITS = 3


def ai_hits(text: str) -> int:
    return len(AI_RE.findall(text or ""))


def is_ai(title: str, text: str = "") -> bool:
    return ai_hits(title) > 0 or ai_hits(text) >= AI_TEXT_HITS


# ── 날짜 ────────────────────────────────────────────────────
def parse_date(s, default_tz=KST) -> dt.datetime | None:
    """RFC 822(pubDate) · ISO 8601 · '2026-09-30 18:22:02'(시간대 없음 → default_tz)."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if not s:
        return None
    d = None
    if re.match(r"^[A-Za-z]{3},? ", s) or re.search(r" [+-]\d{2}:?\d{2}$| (GMT|UT|UTC|KST)$", s):
        t = re.sub(r" ([+-]\d{2}):(\d{2})$", r" \1\2", s).replace(" KST", " +0900")
        try:
            d = email.utils.parsedate_to_datetime(t)
        except (TypeError, ValueError, IndexError):
            d = None
    if d is None:
        t = s.replace("Z", "+00:00").replace(".", "-", 2) if re.match(r"^\d{4}\.\d{2}\.\d{2}", s) else \
            s.replace("Z", "+00:00")
        t = re.sub(r"^(\d{4}-\d{2}-\d{2}) (\d)", r"\1T\2", t)
        t = re.sub(r"(\.\d{1,6})\d*", r"\1", t)                    # 3.9 fromisoformat 은 소수 6자리까지
        t = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", t)
        try:
            d = dt.datetime.fromisoformat(t)
        except ValueError:
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?", t)
            if not m:
                return None
            d = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            int(m.group(4) or 0), int(m.group(5) or 0))
    if d.tzinfo is None:
        d = d.replace(tzinfo=default_tz)
    return d


def iso_kst(d: dt.datetime) -> str:
    return d.astimezone(KST).replace(microsecond=0).isoformat()


# ── RSS/Atom ───────────────────────────────────────────────
_XML_ENT = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")
_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _decode(body: bytes, content_type: str = "") -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    head = body[:2048].decode("ascii", "ignore")
    m2 = re.search(r"""encoding=["']([\w-]+)["']""", head) or re.search(r"""<meta[^>]+charset=["']?([\w-]+)""", head, re.I)
    for enc in [x.group(1) for x in (m, m2) if x] + ["utf-8", "cp949"]:
        try:
            return body.decode("cp949" if enc.lower() in ("euc-kr", "ks_c_5601-1987", "ksc5601") else enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", "replace")


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _kid_text(el, *names) -> str:
    for c in el:
        if _local(c.tag) in names:
            t = (c.text or "").strip() or "".join(c.itertext()).strip()
            if t:
                return t
    return ""


def _link(el) -> str:
    """기사 주소. CDATA 안에 '&amp;' 를 그대로 둔 피드(과기정통부)가 있어 한 번 풀어 준다."""
    for c in el:
        if _local(c.tag) == "link":
            href = c.get("href")
            if href and c.get("rel", "alternate") == "alternate":
                return html.unescape(href.strip())
            if (c.text or "").strip():
                return html.unescape(c.text.strip())
    for c in el:
        if _local(c.tag) == "guid" and (c.text or "").startswith("http") and c.get("isPermaLink", "true") != "false":
            return html.unescape(c.text.strip())
    return ""


def parse_feed(body, default_tz=KST, content_type: str = "") -> list[dict]:
    """RSS 2.0 · RSS 1.0(RDF) · Atom → [{title, url, published(datetime|None), body(html)}]."""
    text = body if isinstance(body, str) else _decode(body, content_type)
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text.lstrip(BOM))
    text = _BAD_XML.sub("", _XML_ENT.sub("&amp;", text))
    root = ET.fromstring(text)
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", _kid_text(el, "title")))
        url = _link(el)
        when = None
        for nm in ("pubDate", "published", "date", "issued", "updated"):
            when = parse_date(_kid_text(el, nm), default_tz)
            if when:
                break
        raw = _kid_text(el, "encoded") or _kid_text(el, "content") or ""
        summ = _kid_text(el, "description") or _kid_text(el, "summary") or ""
        out.append({"title": re.sub(r"\s+", " ", title).strip(), "url": url, "published": when,
                    "body": raw if len(raw) >= len(summ) else summ, "summary": summ})
    return out


# ── HTML → 본문 ─────────────────────────────────────────────
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP = {"script", "style", "noscript", "iframe", "svg", "form", "button", "nav", "header", "footer", "aside",
        "figure", "figcaption", "select", "textarea", "template", "head", "object", "video", "audio", "canvas",
        "title"}
BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table", "section",
         "article", "blockquote", "pre", "dd", "dt", "hr", "main", "td"}
JUNK = re.compile(r"(?i)(?:^|[-_\s])(related|relate|recommend|share|sharing|sns|social|comment|reply|banner|advert|"
                  r"ads?|popular|ranking|copyright|caption|subscribe|newsletter|tags?|keyword|byline|breadcrumb|"
                  r"photo|img|image|thumb|toolbar|util|menu|gnb|lnb|footer|header|sidebar|aside|more|list)"
                  r"(?:$|[-_\s\d])")
HINT = re.compile(r"(?i)(article[-_]?view[-_]?content|article[-_]?body|articlebody|article[-_]?txt|articletxt|"
                  r"article[-_]?text|article__content|article[-_]content|story[-_]news|news[-_]?(body|content|text)|"
                  r"view[-_]?(cont|content|text)|entry[-_]content|post[-_]content|body[-_]text|release[-_]body|"
                  r"cont[-_]?view|bbs[-_]?view|board[-_]?view)")
BOILER = re.compile(r"(?i)(저작권자|무단\s*전재|재배포\s*금지|무단\s*복제|copyright|all rights reserved|ⓒ|©|"
                    r"기사\s*제보|구독하기|좋아요|공유하기|카카오톡|페이스북|트위터|네이버\s*채널|"
                    r"sign up for|subscribe to|newsletter|read the full story|첨부파일을\s*참고|바로보기가\s*지원|"
                    r"검색\s*선호\s*출처|기사를\s*더\s*자주|구독하고\s*무제한|투자\s*권유)")


class _Node:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, attrs, [], parent


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "li") and self.cur.tag == tag:             # <p> 는 다음 <p> 가 닫는다
            self.cur = self.cur.parent
        n = _Node(tag, {k: (v or "") for k, v in attrs}, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(_Node(tag, {k: (v or "") for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def _walk(n):
    """문서 순서로 모든 노드(반복문 — 안 닫힌 태그가 많아 깊어진 트리에서도 재귀 한도에 안 걸린다)."""
    stack = [n]
    while stack:
        x = stack.pop()
        yield x
        stack.extend(k for k in reversed(x.kids) if isinstance(k, _Node))


def _junk(n) -> bool:
    if n.tag in SKIP or "hidden" in n.attrs:
        return True
    ident = f"{n.attrs.get('class', '')} {n.attrs.get('id', '')}"
    return bool(JUNK.search(ident)) and not HINT.search(ident)


def _raw_text(n, out):
    """n 아래 글을 문서 순서로(반복문). 블록 태그는 줄을 바꾸고, 링크 글은 LINK_ON…LINK_OFF 로 감싼다."""
    stack = [(k, False) for k in reversed(n.kids)]
    while stack:
        k, closing = stack.pop()
        if isinstance(k, str):
            out.append(k)
        elif closing:
            out.append(LINK_OFF if k.tag == "a" else "")
            out.append("\n" if k.tag in BLOCK else "")
        elif not _junk(k):
            out.append("\n" if k.tag in BLOCK else "")
            out.append(LINK_ON if k.tag == "a" else "")
            stack.append((k, True))
            stack.extend((c, False) for c in reversed(k.kids))


def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", html.unescape(s or ""))
    lines = []
    for ln in s.split("\n"):
        if LINK_ON in ln:
            plain = ln.replace(LINK_ON, "").replace(LINK_OFF, "").strip()
            link = sum(len(x.strip()) for x in re.findall(f"{LINK_ON}([^{LINK_OFF}]*)", ln))
            if plain and link >= 0.5 * len(plain):
                continue
            ln = ln.replace(LINK_ON, "").replace(LINK_OFF, "")
        ln = re.sub(r"[^\S\n]+", " ", ln.replace(ZWSP, "")).strip()
        if len(ln) < 2 or (BOILER.search(ln) and len(ln) < 120):
            continue
        if not lines or lines[-1] != ln:
            lines.append(ln)
    return "\n".join(lines)


def node_text(n) -> str:
    out: list[str] = []
    _raw_text(n, out)
    return clean_text("".join(out))


def html_to_text(fragment: str) -> str:
    """피드 본문(HTML 조각) → 글. 두 번 이스케이프된 조각(&lt;p&gt;)은 한 번 풀고, 주석(한글 문서
    붙여넣기의 <!--[data-hwpjson]{…}--> 같은 수만 자짜리)은 버린다."""
    frag = fragment or ""
    if frag.count("&lt;") > frag.count("<"):
        frag = html.unescape(frag)
    frag = re.sub(r"<!--.*?(-->|$)", " ", frag, flags=re.S)
    t = _Tree()
    t.feed(frag)
    t.close()
    return node_text(t.root)


def _jsonld_body(tree) -> tuple[str, str]:
    """(articleBody, datePublished) — 뉴스 사이트 상당수가 JSON-LD 에 본문을 통째로 둔다."""
    for n in _walk(tree.root):
        if n.tag != "script" or "ld+json" not in n.attrs.get("type", ""):
            continue
        raw = "".join(k for k in n.kids if isinstance(k, str)).strip()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if isinstance(d.get("@graph"), list):
                    stack.extend(d["@graph"])
                body = d.get("articleBody")
                if isinstance(body, str) and len(body) >= TEXT_MIN:
                    return clean_text(re.sub(r"<[^>]+>", "\n", body)), str(d.get("datePublished") or "")
    return "", ""


def _meta(tree, *names) -> str:
    for n in _walk(tree.root):
        if n.tag == "meta" and (n.attrs.get("property") in names or n.attrs.get("name") in names):
            if n.attrs.get("content"):
                return n.attrs["content"].strip()
    return ""


def _score(n) -> int:
    """직접 가진 글(텍스트 조각 + 바로 아래 <p>) 길이. 링크 글은 뺀다."""
    s = 0
    for k in n.kids:
        if isinstance(k, str):
            s += len(k.strip())
        elif k.tag == "p" and not _junk(k):
            t = node_text(k)
            links = sum(len(node_text(a)) for a in _walk(k) if a.tag == "a")
            s += max(0, len(t) - 2 * links)
    return s


def extract_article(page: str) -> dict:
    """{text, how, published, title} — JSON-LD articleBody → 본문 칸(id/class 힌트) → 글이 가장 많은 칸."""
    tree = _Tree()
    try:
        tree.feed(page or "")
        tree.close()
    except Exception:  # noqa: BLE001 — 깨진 HTML 도 받은 데까지는 쓴다
        pass
    published = _meta(tree, "article:published_time", "og:article:published_time", "datePublished",
                      "pubdate", "publish-date", "article:published")
    title = _meta(tree, "og:title", "twitter:title")
    body, ld_date = _jsonld_body(tree)
    if body:
        return {"text": body, "how": "jsonld", "published": published or ld_date, "title": title}
    hints = []
    for n in _walk(tree.root):
        ident = f"{n.attrs.get('class', '')} {n.attrs.get('id', '')}"
        if n.tag not in SKIP and HINT.search(ident):
            hints.append((n, node_text(n)))
    top = max((len(t) for _, t in hints), default=0)
    if top >= TEXT_MIN:
        # 본문 칸이 겹쳐 있으면(바깥 칸 = 본문 + 관련 기사) 글의 70% 이상을 가진 가장 안쪽 칸
        def depth(x):
            k = 0
            while x.parent is not None:
                x, k = x.parent, k + 1
            return k
        n, best = max(((n, t) for n, t in hints if len(t) >= 0.7 * top), key=lambda nt: depth(nt[0]))
        return {"text": best, "how": "page", "published": published, "title": title}
    cands = [(_score(n), n) for n in _walk(tree.root) if n.tag in ("div", "article", "section", "main", "td")
             and not _junk(n)]
    cands = [c for c in cands if c[0] > 0]
    if cands:
        n = max(cands, key=lambda c: c[0])[1]
        return {"text": node_text(n), "how": "page", "published": published, "title": title}
    return {"text": "", "how": "", "published": published, "title": title}


# 과기정통부 보도자료는 본문이 첨부(HWPX·ODT)에만 있다. ODT 는 부처가 '기계판독용'으로 따로 올려 두는 파일이다
#   (다운로드 확인 창 문구). ODT = zip 안의 content.xml — 표준 라이브러리로 읽는다.
ODT_LINK = re.compile(r"fn_download\(\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'odt'\s*\)")


def odt_attachment(page: str, page_url: str) -> tuple[str, bytes] | None:
    """(POST 주소, 폼 데이터) — 과기정통부 게시판의 ODT 첨부. 없으면 None."""
    m = ODT_LINK.search(page or "")
    if not m or "msit.go.kr" not in urllib.parse.urlsplit(page_url).netloc:
        return None
    form = urllib.parse.urlencode({"atchFileNo": m.group(1), "fileOrd": m.group(2), "fileBtn": "A"}).encode()
    return urllib.parse.urljoin(page_url, "/ssm/file/fileDown.do"), form


def odt_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        x = z.read("content.xml").decode("utf-8", "replace")
    x = re.sub(r"<text:(p|h)\b[^>]*>", "\n", x)
    x = re.sub(r"<text:(s|tab|line-break)\b[^>]*/>", " ", x)
    return clean_text(re.sub(r"<[^>]+>", "", x))


def trim(text: str, n: int = TEXT_MAX) -> str:
    if len(text) <= n:
        return text
    cut = text[:n]
    k = max(cut.rfind("\n"), cut.rfind(". "), cut.rfind("다."))
    return (cut[:k + 2] if k > n * 0.8 else cut).rstrip()


# ── 가져오기(예의 있게) ──────────────────────────────────────
class Http:
    """User-Agent 를 밝히고, robots.txt 를 지키고, 같은 호스트는 HOST_GAP 초 간격."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.last: dict[str, float] = {}
        self.calls = 0

    def _raw(self, url: str, data: bytes | None = None, referer: str = "") -> tuple[str, bytes, str]:
        host = urllib.parse.urlsplit(url).netloc.lower()
        wait = HOST_GAP - (time.time() - self.last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.time()
        self.calls += 1
        headers = {"User-Agent": UA, "Accept-Language": "ko,en;q=0.8",
                   "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,text/html;q=0.9,*/*;q=0.5"}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.geturl(), r.read(MAX_BYTES), r.headers.get("Content-Type", "")

    def allowed(self, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                _, body, ct = self._raw(base + "/robots.txt")
                rp.parse(_decode(body, ct).splitlines())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    rp.parse(["User-agent: *", "Disallow: /"])     # 표준: 막혀 있으면 전부 금지로 본다
                else:
                    rp.parse([])                                    # 404 등: 규칙 없음 = 허용
            except Exception:  # noqa: BLE001
                rp.parse([])
            self.robots[base] = rp
        return self.robots[base].can_fetch(UA, url)

    def get(self, url: str, data: bytes | None = None, referer: str = "") -> tuple[str, bytes, str]:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt 가 막는다: {url}")
        return self._raw(url, data, referer)


# ── 모으기 ──────────────────────────────────────────────────
def collect(now: dt.datetime, sources=None, http=None, window_hours: int = WINDOW_HOURS,
            page_budget: int = PAGE_BUDGET, log=print) -> tuple[list[dict], list[dict]]:
    """(기사들, 피드별 통계). 기사 = {id, source, outlet, official, lang, title, url, published_at, text,
    text_chars, text_from, fetched_at}."""
    now = now.astimezone(KST)
    http = http or Http()
    sources = SOURCES if sources is None else sources
    lo, hi = now - dt.timedelta(hours=window_hours), now + dt.timedelta(hours=1)
    stats, queues = [], []
    for src in sources:
        st = {"id": src["id"], "outlet": src["outlet"], "url": src["url"], "ok": False,
              "entries": 0, "candidates": 0, "kept": 0, "error": None}
        stats.append(st)
        tz = KST if src.get("lang", "ko") == "ko" else UTC
        try:
            _, body, ct = http.get(src["url"])
            entries = parse_feed(body, tz, ct)
        except Exception as e:  # noqa: BLE001 — 피드 하나가 죽어도 나머지는 간다
            st["error"] = f"{type(e).__name__}: {str(e)[:160]}"
            log(f"  ✗ {src['id']:14s} {st['error']}")
            continue
        st["ok"], st["entries"] = True, len(entries)
        mine = []
        for e in entries:
            if not e["url"] or not e["published"] or not (lo <= e["published"] <= hi):
                continue
            if not src.get("ai_only") and not ai_hits(e["title"] + " " + html_to_text(e["summary"] or e["body"])):
                continue
            mine.append(e)
        mine.sort(key=lambda e: e["published"], reverse=True)
        mine = mine[:PER_SOURCE]
        st["candidates"] = len(mine)
        queues.append([(src, st, e) for e in mine])

    # 피드를 돌아가며 하나씩 — 페이지 예산이 앞 피드(국내)에서 다 떨어져 뒤 피드(해외)가 굶지 않게
    cands = [q[i] for i in range(max((len(q) for q in queues), default=0)) for q in queues if i < len(q)]
    items, seen = [], set()
    for src, st, e in cands:
        key = A.norm_url(e["url"])
        if key in seen:
            continue
        text, how = html_to_text(e["body"]), "feed"
        if len(text) < FEED_BODY_ENOUGH:                     # 피드엔 요약뿐 — 페이지(또는 첨부)에서 본문을
            if page_budget > 0:
                page_budget -= 1
                try:
                    final, body, ct = http.get(e["url"])
                    page = _decode(body, ct)
                    art = extract_article(page)
                    att = odt_attachment(page, final)
                    if att:
                        try:
                            _, blob, _ = http.get(att[0], att[1], referer=final)
                            t2 = odt_text(blob)
                            if len(t2) > len(art["text"]):
                                art = {"text": t2, "how": "odt"}
                        except Exception as ex:  # noqa: BLE001
                            log(f"    · 첨부 못 읽음({src['id']}): {type(ex).__name__} {e['url'][:80]}")
                    if len(art["text"]) > len(text):
                        text, how = art["text"], art["how"]
                except Exception as ex:  # noqa: BLE001
                    log(f"    · 페이지 못 읽음({src['id']}): {type(ex).__name__} {e['url'][:80]}")
        if len(text) < (TEXT_MIN_OFFICIAL if src.get("official") else TEXT_MIN):
            continue
        if not src.get("ai_only") and not is_ai(e["title"], text):
            continue
        seen.add(key)
        st["kept"] += 1
        items.append({
            "id": A.feed_id(e["url"]), "source": src["id"], "outlet": src["outlet"],
            "official": bool(src.get("official")), "lang": src.get("lang", "ko"),
            "title": e["title"], "url": e["url"].strip(), "published_at": iso_kst(e["published"]),
            "text": trim(text), "text_chars": len(text), "text_from": how, "fetched_at": iso_kst(now)})
    items.sort(key=lambda it: it["published_at"], reverse=True)
    return items, stats


def build(out_dir: str, now: dt.datetime | None = None, sources=None, http=None,
          keep_days: int = KEEP_DAYS, log=print) -> tuple[str, dict]:
    """feed/ai/<DATE>_<slot>.json 을 쓴다. 같은 슬롯 파일이 이미 있으면 합친다(피드에서 밀려난 기사도 남게).
    keep_days 보다 오래된 파일은 지운다."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    date, slot = A.slot_now(now)
    items, stats = collect(now, sources, http, log=log)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}_{slot}.json")
    lo = now - dt.timedelta(hours=WINDOW_HOURS)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f).get("items") or []
        except (OSError, ValueError):
            old = []
        have = {A.norm_url(it["url"]) for it in items}
        for it in old:
            if not isinstance(it, dict) or not it.get("url") or A.norm_url(it["url"]) in have:
                continue
            w = A.parse_when(it.get("published_at"))
            if w and w >= lo:
                items.append(it)
        items.sort(key=lambda it: it["published_at"], reverse=True)
    doc = {"version": 1, "date": date, "slot": slot, "generated_at": iso_kst(now),
           "window_hours": WINDOW_HOURS, "text_max": TEXT_MAX, "user_agent": UA,
           "sources": stats, "items": items}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    cutoff = now.date() - dt.timedelta(days=keep_days)
    for p in glob.glob(os.path.join(out_dir, "*.json")):
        m = A.FEED_NAME_RE.match(os.path.basename(p))
        if m and dt.date.fromisoformat(m.group(1)) < cutoff:
            os.remove(p)
            log(f"  - 지움(오래됨): {os.path.basename(p)}")
    return path, doc


def main() -> int:
    ap = argparse.ArgumentParser(description="AI 소식 피드 — 기사 원문을 받아 JSON 으로")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="받아서 <DATE>_<slot>.json 쓰기")
    b.add_argument("--dir", required=True, help="feed/ai 폴더")
    b.add_argument("--now", help="기준 시각(ISO) — 테스트용")
    b.add_argument("--only", help="이 피드 id 만(쉼표) — 점검용")
    sub.add_parser("probe", help="피드 주소마다 몇 건 오는지")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):     # 윈도 콘솔(cp949)에서도 기호가 깨져 죽지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    srcs = SOURCES
    if getattr(a, "only", None):
        want = set(a.only.split(","))
        srcs = [s for s in SOURCES if s["id"] in want]
    if a.cmd == "probe":
        http = Http()
        for s in SOURCES:
            try:
                _, body, ct = http.get(s["url"])
                es = parse_feed(body, KST if s["lang"] == "ko" else UTC, ct)
                dates = [e["published"] for e in es if e["published"]]
                span = f"{min(dates):%m-%d %H:%M} ~ {max(dates):%m-%d %H:%M}" if dates else "-"
                print(f"✓ {s['id']:14s} {len(es):4d}건 · {span}")
            except Exception as e:  # noqa: BLE001
                print(f"✗ {s['id']:14s} {type(e).__name__}: {str(e)[:120]}")
        return 0
    now = dt.datetime.fromisoformat(a.now).astimezone(KST) if a.now else dt.datetime.now(KST)
    t0 = time.time()
    path, doc = build(a.dir, now, srcs)
    ok = [s for s in doc["sources"] if s["ok"]]
    print(f"\n📰 {os.path.basename(path)} · 기사 {len(doc['items'])}건 · 피드 {len(ok)}/{len(doc['sources'])} 응답 · "
          f"{time.time() - t0:.0f}초")
    for s in doc["sources"]:
        mark = "✓" if s["ok"] else "✗"
        print(f"  {mark} {s['id']:14s} 피드 {s['entries']:4d} · 후보 {s['candidates']:2d} · 담음 {s['kept']:2d}"
              + (f" · {s['error']}" if s["error"] else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
