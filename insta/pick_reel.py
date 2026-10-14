#!/usr/bin/env python3
"""인스타 '오늘의 골라보기' 릴스 렌더 — 보는 사람이 멈춰서 고르는 짧은 영상 5가지 (2026-10-07).

왜: 사용자 10/7 "유튜브 홍보는 아예 하지 말고 인스타 자체를 키우자 · 매일 바이럴을 찾아 벤치마킹해서 AI로 ·
  히트성 아이디어 몇 개를 로테이션으로". 로컬 크롬(@zerocrew.studio)으로 인스타 검색 상위를 잰 결과(10/7):
  심리테스트·성격테스트 517만~1,934만 · 상식 퀴즈 694만~1,407만 · 운세·사주·타로 135만~409만.
  다섯 꼴 모두 ★보는 사람이 멈춰서 고르는★ 꼴이다(왕별이 '내 것 찾기'와 같은 원리).

꼴(kind) — 편성은 pick_plan.py 가 날짜로 정한다:
  pick    그림 넷 중 하나 고르기 → 번호별 결과(그림 고르기형 심리테스트)
  card    뒤집힌 카드 넷 중 하나 → 앞면과 메시지(타로 고르기)
  quiz    상식 퀴즈 두세 문제 · 3초 세고 정답('이거 맞히면 상위 10%')
  balance 밸런스 게임 세 판 · 둘 중 하나(A·B)
  birth   태어난 달로 보는 표 한 장(12칸 · 내 달 찾기)
  sci     ★10/14 도파민 과학(심해·우주·극한 생존 · 2주 시험 10/15~10/28) — 골라보기가 아니다(회차 번호 없음).
          영어 쇼츠 shorts_catalog(survival·compare)의 출처 달린 facts 를 한국어로: 질문 훅 → 큰 숫자 박자 4~6개 → 판정.
          화면은 어두운 실사 그림 꽉 차게(천천히 다가감) · 위 훅 두 줄 · 가운데 노란 큰 숫자 + 흰 설명 ·
          compare 는 아래에 로그 막대 띠 · 끝 판정 + 열린 질문. 숫자는 그 항목 facts 에 있는 것만(check 가 막는다).

★남의 것을 베끼지 않는다: 빌리는 건 '꼴'뿐. 그림은 매번 새로 그리고(Spark z-image), 문구는 새로 쓰고,
  소리는 코드로 만든 배경음 + 우리 목소리(Supertonic F1). 인스타는 남의 영상·음원을 살짝 바꾼 재게시를 추천에서 뺀다.
화면은 파스텔(2030 인스타 테스트 계정의 밝은 결). 아래 약 25%(y 1480~)는 인스타 캡션·버튼 자리라 비운다.
캡션·커버(10/9): 회차 '오늘의 골라보기 #N' · 열린 질문 한 줄(10/11) · 해시태그 5개는 코드가 붙인다(caption_of·cover_of).

    python insta/pick_reel.py check <script.json> [...]
    python insta/pick_reel.py render <script.json> --out output/insta_pick_render [--work …] [--mock]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402  (회차 번호 = 편성 시작일 기준)
import render_reel as R  # noqa: E402  (글꼴·목소리·배경음·인코딩 도구를 같이 쓴다)

W, H, FPS, SR = R.W, R.H, R.FPS, R.SR
LZ = getattr(Image, "Resampling", Image).LANCZOS
BIL = getattr(Image, "Resampling", Image).BILINEAR
EXTENT = getattr(Image, "Transform", Image).EXTENT
KINDS = ("pick", "card", "quiz", "balance", "birth", "sci")
BG_TOP, BG_BOT = (246, 238, 255), (255, 236, 228)
INK, SUB, ACC, OK = (40, 32, 58), (110, 98, 130), (124, 92, 230), (46, 170, 110)
NUM_BG = [(255, 140, 140), (255, 186, 110), (110, 200, 160), (120, 160, 255)]
STYLE = ("dreamy pastel storybook illustration, soft diffused light, one subject centered on a plain soft pastel "
         "background, gentle colors, clean shapes, cozy and calm, high detail, ")
COUNT = 3
BANNED = ("치료", "완치", "진단", "우울증", "투자", "주식", "코인", "로또", "대박", "무조건", "죽음", "사망", "저주",
          "팔로우", "링크", "DM", "정확도")
# 캡션 고정 문구 — 대본 작가(루틴)가 지시를 안 지켜서 코드가 꼴마다 붙인다. 대본 caption 의 비슷한 줄은 뺀다(겹치지 않게).
# ★10/11: 10/9 의 '친구한테 보내서 물어봐요' + '몇 번? 숫자만 댓글로 남겨 줘요' 를 뺐다. 인스타(2024-06-02)는 참여를 대놓고
#   부탁하는 게시물을 추천하지 않는다고 했고, 예가 바로 '특정 단어·숫자·이모지로 댓글 달기'였다. 열린 질문은 괜찮다고 했다.
#   (socialmediatoday.com/news/instagram-says-using-certain-ctas-can-impact-post-reach/717732/) → 부탁 없는 열린 질문 한 줄만.
SERIES = "오늘의 골라보기"
ASK = {"pick": "어떤 그림이 제일 끌렸어요?", "card": "어떤 카드가 제일 끌렸어요?",
       "quiz": "제일 헷갈렸던 문제는 뭐였어요?", "balance": "제일 고르기 어려웠던 판은 뭐였어요?",
       "birth": "내 달 풀이, 맞는 것 같아요?",
       "sci": {"survival": "너라면 몇 초 버틸 것 같아요?", "compare": "제일 놀라운 건 뭐였어요?"}}   # sci 는 catalog 형식마다
ASK_WORDS = ("댓글", "보내", "공유", "태그", "친구")     # 대본 caption 에서 이런 말이 든 줄(첫 줄 빼고)은 뺀다(부탁 문구가 다시 끼지 않게)
# 화면·목소리에 나오면 안 되는 부탁 말(10/11) — caption 은 위 ASK_WORDS 로 줄째 빼고, 나머지 글·말은 check 가 막는다
ASK_BAN = ("댓글", "남겨 줘", "남겨줘", "보내 줘", "보내줘", "공유해", "태그해", "저장해")
HASHTAG_MAX = 5                                           # 인스타 2025-12-18부터 5개 제한 · 검색에만 돕고 도달은 안 늘린다
_SERIES_RE = re.compile(SERIES + r"\s*#\d+\s*[·|:-]?\s*")
_TAG_RE = re.compile(r"(?<!\S)#(?!\d+(?:\s|$))[^\s#]+")   # 본문 속 해시태그(숫자만인 #5 는 회차라 남긴다)

# ── sci(도파민 과학, 10/14) ────────────────────────────
SCI_BEATS = (4, 6)
SCI_HOOK_MAX, SCI_INTRO_MAX = 14, 50
SCI_BIG_MAX, SCI_SUB_MAX, SCI_SAY_MAX = 12, 24, 45
SCI_VERDICT_BIG_MAX, SCI_VERDICT_SAY_MAX = 12, 40
SCI_TEMPO = 1.1                                           # sci 만 조금 빠르게(다른 꼴은 R.TEMPO 그대로)
SCI_SEC = (18.0, 40.0)                                    # 전체 길이 — 넘으면 말을 조금 더 빠르게(최대 SCI_SPEEDUP)
SCI_SPEEDUP = 1.15
SCI_Y_MAX = 1430                                          # 그린 글자·막대의 아랫변 — 아래 25%(y 1440~)는 인스타 캡션·버튼 자리
# 어두운 실사(파스텔 STYLE 을 쓰지 않는다) — gumiho/tales/rules.py LOOKS 와 같은 결, 더 어둡게
SCI_LOOKS = {"deep": "photorealistic cinematic still, deep ocean, dark blue and black water, ",
             "space": "photorealistic cinematic still, outer space, deep black sky, ",
             "earth": "photorealistic cinematic still, documentary nature photography, moody light, ",
             "ancient": "photorealistic cinematic still, prehistoric Earth, documentary, "}
SCI_LOOK_TAIL = "dark cinematic mood, low-key dramatic lighting, deep shadows, high detail, vertical composition, "
SCI_INTRO_TAG = {"survival": "실제 숫자로 알아봐요", "compare": "작은 것부터 순서대로"}
_NUMS = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|trillion|만|억|조)?", re.I)
_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "만": 1e4, "억": 1e8, "조": 1e12}
_VERDICT_FREE = re.compile(r"\d+(?:\.\d+)?\s*%|\d{1,2}\s*위")      # 판정의 확률(0%)·순위(1위)는 facts 밖이어도 된다
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# 내용 한계 — 피·사체 같은 잔혹 묘사 · 실제 희생자·실존 인물 · 영화·만화 프랜차이즈(대본 글 + 그림 묘사 모두)
SCI_GORE = ("피투성이", "유혈", "핏물", "피가 끓", "피가 터", "시체", "시신", "사체", "내장", "토막", "참혹", "끔찍", "으깨",
            "짓이겨", "터져", "터진다", "blood", "gore", "gory", "corpse", "carcass", "dead body", "wound", "mutilat",
            "dismember", "injur", "decapitat")
SCI_PEOPLE = ("희생자", "사망자", "실종자", "유족", "카메론", "피카르", "베스코보", "가가린",
              "cameron", "piccard", "vescovo", "gagarin", "victim")
SCI_FRANCHISE = ("타이타닉", "쥬라기 공원", "쥬라기 월드", "쥐라기 공원", "쥐라기 월드", "인터스텔라", "스타워즈", "스타 워즈",
                 "마블", "고질라", "킹콩", "포켓몬", "디즈니", "픽사", "니모", "에일리언", "프레데터", "아마겟돈", "그래비티",
                 "마션", "트랜스포머", "해리포터", "스폰지밥", "titanic", "jurassic park", "jurassic world", "interstellar",
                 "star wars", "marvel", "godzilla", "king kong", "pokemon", "pokémon", "disney", "pixar", "nemo",
                 "armageddon", "the martian", "transformers", "harry potter", "spongebob")
# 그림: 글자 없는 장면 · 얼굴 클로즈업 없음 — 낱말 자체를 막는다(쓰는 법: 'plain dark water' 같은 긍정형으로)
SCI_IMG_BAN = re.compile(r"(?i)\b(text|letters?|words?|captions?|logos?|watermarks?|typography|signs?|labels?|"
                         r"faces?|facial|portraits?|selfies?|headshots?|close-?up of (?:a |the )?(?:man|woman|person|diver|astronaut))\b")
SRC_NAME = {"noaa": "NOAA", "nasa": "NASA", "rmg": "RMG", "faa": "FAA", "swri": "SwRI", "nps": "NPS", "cdc": "CDC",
            "esa": "ESA", "eso": "ESO", "usgs": "USGS", "nist": "NIST", "mbari": "MBARI", "wmo": "WMO", "nsidc": "NSIDC",
            "agu": "AGU", "csb": "CSB", "aps": "APS", "doi": "DOI", "usu": "USU", "ucr": "UCR", "uwa": "UWA", "usda": "USDA",
            "nejm": "NEJM", "ebi": "Europe PMC", "colorado": "CU Boulder", "weather": "NWS", "medlineplus": "MedlinePlus",
            "britannica": "Britannica", "nature": "Nature", "peerj": "PeerJ", "smithsonianmag": "Smithsonian",
            "calacademy": "Cal Academy", "nationalgeographic": "National Geographic", "scientificamerican": "Scientific American",
            "fishesoftexas": "Fishes of Texas", "tepapa": "Te Papa", "ufl": "Florida Museum",
            "schmidtocean": "Schmidt Ocean", "harmony": "Harmony Gold", "sandiegozoo": "San Diego Zoo",
            "einstein-online": "Einstein Online", "nssdc": "NASA"}
SRC_MAX = 4                                               # 캡션 출처 줄에 이름 몇 개까지(넘으면 '외')
ACC_SCI = R.ACCENT                                        # sci 큰 숫자 노랑(render_reel 과 같은 토큰)
# 말로 읽을 때만(화면 글자는 그대로) — 단위·분수·영하를 한글로 바꾼 뒤 insta.to_speech(숫자 한글 읽기)
SCI_SAY_MAP = [(re.compile(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)"), r"\2분의 \1"),
               (re.compile(r"-\s?(\d[\d,.]*)\s*(°C|℃|도)"), r"영하 \1도"),
               (re.compile(r"(\d)\s*(°C|℃)"), r"\1도"), (re.compile(r"(\d)\s*km/h"), r"\1킬로미터"),
               (re.compile(r"(\d)\s*km(?![A-Za-z])"), r"\1킬로미터"), (re.compile(r"(\d)\s*cm(?![A-Za-z])"), r"\1센티미터"),
               (re.compile(r"(\d)\s*mm(?![A-Za-z])"), r"\1밀리미터"), (re.compile(r"(\d)\s*m(?![A-Za-z/])"), r"\1미터"),
               (re.compile(r"(\d)\s*kg(?![A-Za-z])"), r"\1킬로그램"), (re.compile(r"(?<![A-Za-z])PSI(?![A-Za-z])"), "피에스아이"),
               (re.compile(r"(?<![A-Za-z])mph(?![A-Za-z])"), "마일")]


def load(p: str) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _texts(s: dict) -> list[str]:
    out = [*s.get("headline", []), s.get("say_intro", ""), s.get("say_outro", ""), s.get("outro_text", ""), s.get("caption", "")]
    for o in s.get("options", []):
        out += [o.get(k, "") for k in ("name", "result", "lines", "say")]
    for r in s.get("rounds", []):
        out += [r.get("q", ""), r.get("why", ""), r.get("say_q", ""), r.get("say_a", ""), r.get("say", ""),
                *r.get("choices", []), (r.get("a") or {}).get("label", ""), (r.get("b") or {}).get("label", "")]
    out += [c.get("text", "") for c in s.get("cells", [])]
    out += list(s.get("hook") or [])                      # sci
    for b in s.get("beats") or []:
        out += [b.get(k, "") for k in ("big", "sub", "say")]
    out += [(s.get("verdict") or {}).get(k, "") for k in ("big", "say")]
    return out


def check(s: dict) -> list[str]:
    errs = []
    kind = s.get("kind")
    if kind not in KINDS:
        return [f"kind 는 {KINDS}"]
    if kind == "sci":
        return check_sci(s) + _word_errs(s)
    if not (isinstance(s.get("headline"), list) and len(s["headline"]) == 2 and all(0 < len(x) <= 14 for x in s["headline"])):
        errs.append("headline 은 두 줄 · 줄마다 14자 이내")
    if not s.get("say_intro") or len(s["say_intro"]) > 50:
        errs.append("say_intro 1~50자")
    if not s.get("caption"):
        errs.append("caption 없음")
    if not s.get("bench", {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    try:                                                   # 회차 번호(#N)가 날짜로 정해진다 — 시작일 전은 #0 이하가 된다
        if dt.date.fromisoformat(s.get("date", "")) < P.START:
            errs.append(f"date 는 {P.START} 이후")
    except (TypeError, ValueError):
        errs.append("date 는 YYYY-MM-DD")
    if kind in ("pick", "card"):
        opts = s.get("options") or []
        if len(opts) != 4:
            errs.append("options 는 4개")
        for k, o in enumerate(opts, 1):
            need = ("img", "name", "result", "lines", "say") + (("reveal_img",) if kind == "card" else ())
            errs += [f"{k}번 {key} 없음" for key in need if not o.get(key)]
            if len(o.get("name", "")) > 8:
                errs.append(f"{k}번 name 8자 이내")
            if len(o.get("result", "")) > 12:
                errs.append(f"{k}번 result 12자 이내")
            if len(o.get("lines", "")) > 46:
                errs.append(f"{k}번 lines 46자 이내")
            if not o.get("say", "").startswith(f"{k}번") or len(o.get("say", "")) > 30:
                errs.append(f"{k}번 say 는 '{k}번'으로 시작 · 30자 이내(결과 한 마디만 읽는다)")
    elif kind == "quiz":
        rs = s.get("rounds") or []
        if not 2 <= len(rs) <= 3:
            errs.append("rounds 는 2~3개")
        for k, r in enumerate(rs, 1):
            ch = r.get("choices") or []
            if len(ch) != 4 or any(not c or len(c) > 12 for c in ch):
                errs.append(f"{k}번 문제 choices 4개 · 12자 이내")
            if r.get("answer") not in (0, 1, 2, 3):
                errs.append(f"{k}번 문제 answer 는 0~3")
            if not r.get("q") or len(r["q"]) > 40:
                errs.append(f"{k}번 문제 q 1~40자")
            if len(r.get("why", "")) > 40:
                errs.append(f"{k}번 문제 why 40자 이내")
            if not r.get("say_q") or not r.get("say_a"):
                errs.append(f"{k}번 문제 say_q·say_a 없음")
            elif r.get("answer") in (0, 1, 2, 3) and len(ch) == 4 and ch[r["answer"]] not in r["say_a"]:
                errs.append(f"{k}번 문제 say_a 에 정답 '{ch[r['answer']]}'이 없다")
    elif kind == "balance":
        rs = s.get("rounds") or []
        if len(rs) != 3:
            errs.append("rounds 는 3개")
        for k, r in enumerate(rs, 1):
            for side in ("a", "b"):
                x = r.get(side) or {}
                if not x.get("img") or not x.get("label") or len(x["label"]) > 12:
                    errs.append(f"{k}판 {side} img·label(12자 이내) 필요")
            if not r.get("say") or len(r["say"]) > 40:
                errs.append(f"{k}판 say 1~40자")
    elif kind == "birth":
        cells = s.get("cells") or []
        if [c.get("m") for c in cells] != list(range(1, 13)):
            errs.append("cells 는 1~12월 순서대로 12칸")
        if any(not c.get("text") or len(c["text"]) > 14 for c in cells):
            errs.append("cells text 1~14자")
        if not s.get("bg"):
            errs.append("bg(배경 그림 묘사) 없음")
    return errs + _word_errs(s)


def _word_errs(s: dict) -> list[str]:
    """모든 꼴 공통 — 금지어 · 부탁 말(caption 은 코드가 부탁 줄을 빼므로 화면·목소리 글만)."""
    errs = []
    hits = sorted({w for w in BANNED for t in _texts(s) if w in t})
    if hits:
        errs.append(f"금지어 {hits}")
    asks = sorted({w for w in ASK_BAN for t in _texts(dict(s, caption="")) if w in t})
    if asks:
        errs.append(f"댓글·보내기·저장 부탁 말 {asks} — 인스타는 참여를 대놓고 부탁하는 글을 추천하지 않는다(10/11). 열린 질문으로")
    return errs


# ── sci 검사 ──────────────────────────────────────────
def _num(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "").rstrip("."))
    except ValueError:
        return None


def _vals(text: str) -> list[tuple[str, list[float]]]:
    """글 속 수 → (원문, [값…]) — 콤마·단위는 무시하고, 만·억·조(million·billion)가 붙으면 곱한 값도 같이 본다
    (430만 = 4.3 million). rules.py unbacked_numbers 의 생각을 단순하게."""
    out = []
    for m in _NUMS.finditer(text or ""):
        v = _num(m.group(1))
        if v is None:
            continue
        vs = [v] + ([v * _MULT[m.group(2).lower()]] if m.group(2) else [])
        out.append((m.group(0).strip(), vs))
    return out


def fact_values(e: dict) -> list[float]:
    """catalog 항목 facts 의 수 전부(콤마 무시 · million·billion 은 곱한 값도)."""
    return [v for f in e.get("facts") or [] for _, vs in _vals(f.get("fact", "")) for v in vs]


def _backed(v: float, pool: list[float]) -> bool:
    return any(abs(v - p) <= 1e-9 * max(1.0, abs(p)) for p in pool)


def unbacked(text: str, pool: list[float]) -> list[str]:
    """facts 에 없는 수(원문 그대로)."""
    return [raw for raw, vs in _vals(text) if not any(_backed(v, pool) for v in vs)]


def sci_entry_of(s: dict) -> dict | None:
    try:
        return P.sci_entry(int(s.get("src_n")))
    except (TypeError, ValueError):
        return None


def sci_format(s: dict) -> str:
    return (sci_entry_of(s) or {}).get("format") or "survival"


def ask_of(s: dict) -> str:
    """끝 열린 질문(코드가 붙인다) — sci 는 catalog 형식마다(생존 · 비교)."""
    a = ASK[s["kind"]]
    return a[sci_format(s)] if isinstance(a, dict) else a


def _sci_number_texts(s: dict) -> list[tuple[str, str]]:
    """숫자를 facts 와 맞춰 볼 글(어디, 글) — 판정의 확률·순위는 뺀다."""
    out = [(f"hook[{i}]", t) for i, t in enumerate(s.get("hook") or []) if isinstance(t, str)]
    out += [("say_intro", s.get("say_intro") or ""), ("caption", s.get("caption") or "")]
    for k, b in enumerate(s.get("beats") or [], 1):
        out += [(f"{k}번 박자 {f}", b.get(f) or "") for f in ("big", "sub", "say")]
    v = s.get("verdict") or {}
    out += [(f"verdict.{f}", _VERDICT_FREE.sub("", v.get(f) or "")) for f in ("big", "say")]
    return out


def check_sci(s: dict) -> list[str]:
    """sci 대본 검사 — 길이·모양 · 그날 catalog 항목(src_n) · 숫자는 facts 에서만 · 출처는 catalog 그대로 · 내용 한계."""
    errs = []
    try:
        d = dt.date.fromisoformat(s.get("date", ""))
    except (TypeError, ValueError):
        return ["date 는 YYYY-MM-DD"]
    want = P.sci_n(d)
    if want is None:
        errs.append(f"{d} 는 sci 편이 없는 날 — sci 시험은 {P.SCI_FROM}~{P.SCI_TO}")
    elif s.get("src_n") != want:
        errs.append(f"src_n 은 그날 편성 항목 {want} 이어야 한다(SCI_ORDER) — 대본은 {s.get('src_n')}")
    e = sci_entry_of(s)
    if e is None:
        return errs + [f"src_n {s.get('src_n')!r} 은 shorts_catalog survival·compare 항목이 아니다"]
    if not _SLUG.fullmatch(s.get("slug") or ""):
        errs.append("slug 는 영어 소문자·숫자·하이픈")
    hook = s.get("hook")
    if not (isinstance(hook, list) and len(hook) == 2 and all(isinstance(x, str) and 0 < len(x) <= SCI_HOOK_MAX for x in hook)):
        errs.append(f"hook 은 두 줄 · 줄마다 {SCI_HOOK_MAX}자 이내")
    intro = s.get("say_intro") or ""
    if not intro or len(intro) > SCI_INTRO_MAX or not intro.rstrip().endswith("?"):
        errs.append(f"say_intro 1~{SCI_INTRO_MAX}자 · 물음표(?)로 끝나는 질문 하나")
    if intro.lstrip().startswith(("안녕", "여러분")):
        errs.append("say_intro 는 첫 문장이 바로 질문 — 인사·소개 없이")
    beats = s.get("beats") or []
    if not SCI_BEATS[0] <= len(beats) <= SCI_BEATS[1]:
        errs.append(f"beats 는 {SCI_BEATS[0]}~{SCI_BEATS[1]}개")
    if s.get("sources") != e.get("sources"):
        errs.append(f"sources 는 catalog {e['n']} 의 sources 를 그대로(순서까지) 옮긴다")
    srcs = e.get("sources") or []
    compare = e.get("format") == "compare"
    items = [float(x["value"]) for x in e.get("items_idea") or [] if isinstance(x.get("value"), (int, float))]
    prev = None
    for k, b in enumerate(beats, 1):
        for f, mx in (("big", SCI_BIG_MAX), ("sub", SCI_SUB_MAX), ("say", SCI_SAY_MAX)):
            if not isinstance(b.get(f), str) or not 0 < len(b[f]) <= mx:
                errs.append(f"{k}번 박자 {f} 1~{mx}자")
        if not b.get("img"):
            errs.append(f"{k}번 박자 img(영어 실사 그림 묘사) 없음")
        src = b.get("src")
        if not (isinstance(src, int) and not isinstance(src, bool) and 0 <= src < len(srcs)):
            errs.append(f"{k}번 박자 src 는 sources 번호(0~{len(srcs) - 1})")
        if compare:
            v = b.get("value")
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                errs.append(f"{k}번 박자 value(단위 {e.get('unit')}, 양수) 필요 — 막대 길이")
                continue
            if not _backed(float(v), fact_values(e) + items):
                errs.append(f"{k}번 박자 value {v:g} 는 catalog(facts·items_idea)에 없는 값")
            if prev is not None and v <= prev:
                errs.append(f"{k}번 박자 value — 작은 것부터 큰 것 순서로({prev:g} → {v:g})")
            prev = v
    v = s.get("verdict") or {}
    if not isinstance(v.get("big"), str) or not 0 < len(v["big"]) <= SCI_VERDICT_BIG_MAX:
        errs.append(f"verdict.big 1~{SCI_VERDICT_BIG_MAX}자")
    if not isinstance(v.get("say"), str) or not 0 < len(v["say"]) <= SCI_VERDICT_SAY_MAX:
        errs.append(f"verdict.say 1~{SCI_VERDICT_SAY_MAX}자")
    cap = (s.get("caption") or "").strip()
    if not cap or "\n" in cap:
        errs.append("caption 은 한 줄(훅) — 출처·질문·해시태그는 코드가 붙인다")
    if not s.get("bench", {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    # 숫자는 그 항목 facts 에 있는 것만(콤마·단위 무시 · 판정의 확률·순위는 예외)
    pool = fact_values(e)
    for where, t in _sci_number_texts(s):
        bad = unbacked(t, pool)
        if bad:
            errs.append(f"{where}: facts({e['n']})에 없는 숫자 {bad} — 숫자는 catalog facts 에서만")
    # 내용 한계 — 잔혹 묘사 · 실제 희생자·인물 · 프랜차이즈(글 + 그림 묘사) · 그림에 글자·얼굴 클로즈업 없음
    low = [t.lower() for t in _texts(s) + [b.get("img") or "" for b in beats] if isinstance(t, str)]
    for name, words in (("잔혹 묘사", SCI_GORE), ("실존 인물·희생자", SCI_PEOPLE), ("프랜차이즈 이름", SCI_FRANCHISE)):
        hits = sorted({w for w in words for t in low if w.lower() in t})
        if hits:
            errs.append(f"{name} 금지 {hits}")
    for k, b in enumerate(beats, 1):
        m = SCI_IMG_BAN.search(b.get("img") or "")
        if m:
            errs.append(f"{k}번 박자 img 에 '{m.group(0)}' — 그림엔 글자·얼굴 클로즈업이 없게(장면만 긍정형으로)")
    return errs


def warns(s: dict) -> list[str]:
    """막지는 않고 알리기만 한다(10/9) — 렌더 때 코드가 알아서 고친다."""
    out = []
    tags = s.get("hashtags") or []
    if len(tags) > HASHTAG_MAX:
        out.append(f"hashtags {len(tags)}개 — 앞 {HASHTAG_MAX}개만 쓴다(인스타 5개 제한) · 빠지는 것 {tags[HASHTAG_MAX:]}")
    lines = (s.get("caption") or "").strip().splitlines()[1:]
    if any(w in ln for ln in lines for w in ASK_WORDS) or SERIES in (s.get("caption") or ""):
        out.append("caption 의 댓글·보내기·회차 말은 코드가 붙인다 — 그 줄은 빼고 렌더한다")
    return out


# ── 그림 ──────────────────────────────────────────────
def gen(prompt: str, out: str, mock: bool, style: str = STYLE, aspect: str | None = None) -> None:
    """그림 한 장(Spark) — 골라보기는 파스텔 STYLE(가로 그대로), sci 는 어두운 실사 화풍 + 세로(aspect 9:16)."""
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return
    if mock:
        R.gen_image(prompt, out, True)
        return
    import wbspark
    for attempt in range(3):
        R.spark_wait()
        if wbspark.generate_image(style + prompt, out, no_llm=True, model=R.IMG_MODEL or None, timeout_sec=600,
                                  aspect=aspect):
            return
        time.sleep(10 + attempt * 20)
    raise RuntimeError(f"그림 실패: {prompt[:50]}")


def sci_style(s: dict) -> str:
    """sci 그림 화풍 — catalog look(deep·space·earth·ancient)으로 고른다. 파스텔 STYLE 은 쓰지 않는다."""
    return SCI_LOOKS.get((sci_entry_of(s) or {}).get("look"), SCI_LOOKS["earth"]) + SCI_LOOK_TAIL


def rounded(im: Image.Image, r: int) -> Image.Image:
    im = im.convert("RGBA")
    im.putalpha(R.rounded_mask(im.width, im.height, r))
    return im


def fade(im: Image.Image, a: float) -> Image.Image:
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im


def bg() -> Image.Image:
    g = Image.new("RGB", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
    return g.resize((W, H))


def ctext(d, y, text, f, fill):
    d.text(((W - R.tlen(d, text, f)) / 2, y), text, font=f, fill=fill)


def badge(d, cx, cy, r, label, color, f):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,), outline=(255, 255, 255), width=6)
    d.text((cx - R.tlen(d, label, f) / 2, cy - f.size * 0.62), label, font=f, fill=(255, 255, 255))


def shadow(im: Image.Image, box, r=40):
    x0, y0, x1, y1 = [int(v) for v in box]
    sh = Image.new("RGBA", (x1 - x0 + 60, y1 - y0 + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([30, 36, x1 - x0 + 30, y1 - y0 + 36], r, fill=(90, 60, 140, 60))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x0 - 30, y0 - 30))


def tile_of(path: str, w: int, h: int, r: int) -> Image.Image:
    return rounded(R.cover(Image.open(path).convert("RGB"), w, h), r)


# ── 화면 ──────────────────────────────────────────────
class Painter:
    """segs: [{kind, start, dur, ...}] — 꼴마다 그린다. 늘 위 두 줄 제목, 아래 25%는 비운다."""

    def __init__(self, s: dict, a: dict, segs: list[dict]):
        self.s, self.a, self.segs = s, a, segs
        self.base = bg().convert("RGBA")
        F = R.font
        self.f = {"head": F("head", 78), "head2": F("head", 62), "num": F("head", 58), "big": F("head", 84),
                  "line": F("bold", 50), "small": F("bold", 40), "chip": F("bold", 36)}
        self.cache: dict = {}
        self.for_cover = False                             # 커버를 그릴 때만 True(cover_of) — 회차 라벨 자리를 비운다

    def seg_at(self, t: float) -> dict:
        for sg in self.segs:
            if sg["start"] <= t < sg["start"] + sg["dur"]:
                return sg
        return self.segs[-1]

    def headline(self, d, y0=150, small=False):
        f = self.f["head2"] if small else self.f["head"]
        for i, line in enumerate(self.s["headline"]):
            ctext(d, y0 + i * (f.size + 18), line, f, INK if i == 0 else ACC)

    def countdown(self, d, left: float, y: int):
        n = max(1, math.ceil(left))
        p = 1 - (left - (n - 1))
        ctext(d, y, str(n), R.font("head", int(140 * (1.25 - 0.25 * min(1, p * 3)))), ACC)

    def frame(self, t: float) -> Image.Image:
        sg = self.seg_at(t)
        kind = "pick" if self.s["kind"] == "card" else self.s["kind"]
        return getattr(self, f"f_{kind}")(sg, t - sg["start"]).convert("RGB")

    def chip(self, d, y, text):
        d.rounded_rectangle([W / 2 - 90, y, W / 2 + 90, y + 60], 30, fill=ACC + (255,))
        ctext(d, y + 4, text, self.f["chip"], (255, 255, 255))

    # pick · card ─────────────────────────────────────
    def _grid(self) -> Image.Image:
        if "grid" not in self.cache:
            im = self.base.copy()
            d = ImageDraw.Draw(im)
            self.headline(d)
            tile, gap = 460, 36
            x0, y0 = (W - 2 * tile - gap) // 2, 400
            for k, p in enumerate(self.a["opts"]):
                x, y = x0 + (k % 2) * (tile + gap), y0 + (k // 2) * (tile + gap)
                shadow(im, (x, y, x + tile, y + tile))
                im.alpha_composite(tile_of(p, tile, tile, 40), (x, y))
                badge(d, x + 58, y + 58, 44, str(k + 1), NUM_BG[k], self.f["num"])
            self.cache["grid"] = im
        return self.cache["grid"]

    def _get(self, key, path, w, h, r):
        if key not in self.cache:
            self.cache[key] = tile_of(path, w, h, r)
        return self.cache[key]

    def f_pick(self, sg, lt):
        if sg["kind"] in ("intro", "outro"):
            im = self._grid().copy()
            d = ImageDraw.Draw(im)
            if sg["kind"] == "outro":
                ctext(d, 1405, self.s.get("outro_text", "몇 번 골랐어요?"), self.f["head2"], ACC)
            elif sg["dur"] - lt <= COUNT:
                self.countdown(d, sg["dur"] - lt, 1385)
            elif not self.for_cover:                       # 커버는 이 자리에 회차 라벨(제목이 이미 '골라 봐요')
                ctext(d, 1420, "하나 골라 보세요", self.f["line"], SUB)
            return im
        k = sg["k"]
        o = self.s["options"][k]
        card = self.s["kind"] == "card"
        face = self._get(f"big{k}", self.a["reveal"][k] if card else self.a["opts"][k], 700, 700, 56)
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if card and lt < 0.36:                               # 카드 뒤집기 — 가로로 접혔다 펴진다
            back = self._get(f"back{k}", self.a["opts"][k], 700, 700, 56)
            wv = max(8, int(700 * abs(1 - lt / 0.18)))
            big = (back if lt < 0.18 else face).resize((wv, 700), LZ)
        else:
            z = 1.0 + 0.04 * min(1, lt / max(0.1, sg["dur"]))
            big = face.resize((int(700 * z), int(700 * z)), LZ)
        im.alpha_composite(big, ((W - big.width) // 2, 300 - (big.height - 700) // 2))
        badge(d, (W - 700) // 2 + 66, 366, 54, str(k + 1), NUM_BG[k], R.font("head", 70))
        pop = min(1.0, lt / 0.25)
        head = f"{o['name']} → {o['result']}"
        fr = R.font("head", int(84 * (0.85 + 0.15 * pop)))
        if R.tlen(d, head, fr) > W - 120:
            fr = R.font("head", 64)
        ctext(d, 1040, head, fr, INK)
        fl, lines = R.fit_wrap(d, o["lines"], "bold", 50, 40, W - 170, 2)
        for i, ln in enumerate(lines):
            ctext(d, 1165 + i * (fl.size + 16), ln, fl, SUB)
        mx0 = (W - 4 * 150 - 3 * 30) // 2
        for j in range(4):
            m = self._get(f"mini{j}", self.a["opts"][j], 150, 150, 24)
            x, y = mx0 + j * 180, 1330
            im.alpha_composite(m if j == k else fade(m, 0.35), (x, y))
            if j == k:
                d.rounded_rectangle([x - 6, y - 6, x + 156, y + 156], 28, outline=NUM_BG[k], width=8)
            badge(d, x + 26, y + 26, 22, str(j + 1), NUM_BG[j], R.font("head", 30))
        return im

    # quiz ────────────────────────────────────────────
    def f_quiz(self, sg, lt):
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if sg["kind"] == "outro":
            ctext(d, 760, self.s.get("outro_text", "몇 개 맞혔어요?"), self.f["big"], ACC)
            return im
        intro = sg["kind"] == "intro"                         # ★첫 장면부터 1번 문제가 보인다(첫 1초가 멈추게 한다)
        k = 0 if intro else sg["k"]
        r = self.s["rounds"][k]
        self.chip(d, 290, f"{k + 1} / {len(self.s['rounds'])}")
        fq, ql = R.fit_wrap(d, r["q"], "head", 66, 50, W - 140, 3)
        for i, ln in enumerate(ql):
            ctext(d, 400 + i * (fq.size + 14), ln, fq, INK)
        reveal = (not intro) and lt >= sg["phase_at"]
        y0 = 400 + len(ql) * (fq.size + 14) + 50
        for j, c in enumerate(r["choices"]):
            y = y0 + j * 150
            good = reveal and j == r["answer"]
            fill = (232, 250, 240, 255) if good else (255, 255, 255, 150 if reveal else 235)
            d.rounded_rectangle([90, y, W - 90, y + 124], 30, fill=fill, outline=OK if good else (226, 216, 245),
                                width=6 if good else 3)
            badge(d, 160, y + 62, 38, str(j + 1), NUM_BG[j], self.f["chip"])
            d.text((230, y + 30), c, font=self.f["line"], fill=INK if (not reveal or good) else SUB)
            if good:
                d.text((W - 200, y + 34), "정답", font=self.f["small"], fill=OK)
        if intro:
            ctext(d, y0 + 4 * 150 + 30, "3초 안에 맞혀 보세요", self.f["line"], SUB)
        elif not reveal:
            if sg["phase_at"] - lt <= COUNT:
                self.countdown(d, sg["phase_at"] - lt, y0 + 4 * 150 + 10)
        elif r.get("why"):
            fw, wl = R.fit_wrap(d, r["why"], "bold", 44, 36, W - 160, 2)
            for i, ln in enumerate(wl):
                ctext(d, y0 + 4 * 150 + 20 + i * (fw.size + 12), ln, fw, SUB)
        return im

    # balance ─────────────────────────────────────────
    def f_balance(self, sg, lt):
        im = self.base.copy()
        d = ImageDraw.Draw(im)
        self.headline(d, 110, small=True)
        if sg["kind"] == "outro":
            ctext(d, 720, self.s.get("outro_text", "나는 A·B·?"), self.f["big"], ACC)
            ctext(d, 850, "너는 어느 쪽이었어요?", self.f["line"], SUB)
            return im
        intro = sg["kind"] == "intro"                         # ★첫 장면부터 1판 그림이 보인다
        k = 0 if intro else sg["k"]
        r = self.s["rounds"][k]
        if intro:
            lt = 1.0
        self.chip(d, 270, f"{k + 1} / 3")
        cw, chh = W - 180, 470
        for side, (y, col) in zip(("a", "b"), ((370, NUM_BG[0]), (900, NUM_BG[3]))):
            t = self._get(f"bal{k}{side}", self.a["bal"][k][side], cw, chh, 44)
            pop = min(1.0, max(0.0, (lt - (0 if side == "a" else 0.2)) / 0.25))
            shadow(im, (90, y, 90 + cw, y + chh), 44)
            im.alpha_composite(fade(t, 0.4 + 0.6 * pop), (90, y))
            lab, fl = r[side]["label"], self.f["line"]
            tw = R.tlen(d, lab, fl)
            d.rounded_rectangle([W / 2 - tw / 2 - 30, y + chh - 96, W / 2 + tw / 2 + 30, y + chh - 20], 36,
                                fill=(255, 255, 255, 235))
            ctext(d, y + chh - 92, lab, fl, INK)
            badge(d, 150, y + 60, 42, side.upper(), col, self.f["num"])
        d.ellipse([W / 2 - 62, 843, W / 2 + 62, 967], fill=(255, 255, 255, 255), outline=ACC, width=6)
        ctext(d, 868, "VS", self.f["head2"], ACC)
        left = sg["dur"] - lt
        if not intro and left <= COUNT:
            d.text((W - 160, 850), str(max(1, math.ceil(left))), font=R.font("head", 90), fill=ACC)
        return im

    # sci ─────────────────────────────────────────────
    # 어두운 실사 그림 꽉 차게(장면마다 천천히 다가감·좌우로 조금) · 위 훅 두 줄(내내) · 가운데 노란 큰 숫자(튀어나옴)
    # + 흰 설명 + 작은 출처 · compare 는 아래 로그 막대 띠 · 끝 = 판정 + 열린 질문. 그린 것은 모두 y ≤ SCI_Y_MAX.
    SCI_ZOOM, SCI_XF, SCI_POP = 0.08, 0.22, 0.24
    SCI_BIG_Y, SCI_BAR_TOP, SCI_BAR_ROW = 800, 1196, 38

    def _sci_init(self):
        if "sci_top" in self.cache:
            return
        s = self.s
        self.sci_fmt = sci_format(s)
        self.sci_srcs = s.get("sources") or []
        col = Image.new("L", (1, H))
        px = col.load()
        for y in range(H):                                   # 위(훅)·가운데(숫자)·아래(인스타 글) 어둡게
            top = 0.78 * max(0.0, 1 - y / 640) ** 1.4
            mid = 0.36 * math.exp(-((y - 930) / 360) ** 2)
            bot = 0.62 * max(0.0, (y - 1300) / (H - 1300))
            px[0, y] = int(255 * (1 - max(top, mid, bot)) * 0.9)
        self.cache["sci_shade"] = Image.merge("RGB", [col.resize((W, H))] * 3)
        top = Image.new("RGBA", (W, 620), (0, 0, 0, 0))
        d = ImageDraw.Draw(top)
        f = R.fit(d, s["hook"], "head", 104, 64, W - 120)
        for i, ln in enumerate(s["hook"]):
            d.text(((W - R.tlen(d, ln, f)) / 2, 236 + i * (f.size + 22)), ln, font=f, fill=(255, 255, 255),
                   stroke_width=6, stroke_fill=(0, 0, 0))
        self.cache["sci_top"] = top
        self.cache["sci_hook_bottom"] = 236 + 2 * (f.size + 22)
        vals = [b.get("value") for b in s["beats"] if isinstance(b.get("value"), (int, float)) and b["value"] > 0]
        self.sci_bars = self.sci_fmt == "compare" and len(vals) == len(s["beats"])
        if self.sci_bars:
            lo, hi = math.log10(min(vals)), math.log10(max(vals))
            self.sci_frac = [0.07 + 0.93 * ((math.log10(v) - lo) / (hi - lo) if hi > lo else 1.0) for v in vals]

    def _sci_img(self, i: int, end: bool = False) -> Image.Image:
        key = ("sci_img", i, end)
        if key not in self.cache:
            im = R.cover(Image.open(self.a["beats"][i]).convert("RGB"), round(W * 1.1), round(H * 1.1))
            im = ImageEnhance.Contrast(ImageEnhance.Brightness(im).enhance(0.86)).enhance(1.08)
            if end:                                          # 끝 판정: 흐리고 더 어둡게(글자가 주인공)
                im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(14))).enhance(0.62)
            self.cache[key] = im
        return self.cache[key]

    def _sci_layer(self, sg, t: float) -> Image.Image:
        """그 장면 그림 — 같은 그림이 이어지는 동안(img_t0 부터 img_dur) 천천히 다가가고(1 → 1.08) 좌우로 조금 흐른다."""
        im = self._sci_img(sg["img"], sg["kind"] == "verdict")
        p = R.ease(min(1.0, max(0.0, (t - sg["img_t0"]) / max(0.5, sg["img_dur"]))))
        z = 1.0 + self.SCI_ZOOM * p
        cw, ch = W / z, H / z
        side = 1 if sg["img_g"] % 2 == 0 else -1
        cx = im.width / 2 + side * (im.width - cw) / 2 * 0.6 * (2 * p - 1)
        cy = im.height / 2
        return im.transform((W, H), EXTENT, (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2), BIL)

    def sci_bg(self, t: float) -> Image.Image:
        """그 시각의 바탕(그림 + 어둡게) — 글자·막대는 없다(테스트: 아래 25% 는 이것과 같아야 한다).
        그림이 바뀌는 장면의 첫 SCI_XF 초는 앞 그림에서 섞어 넘어간다."""
        self._sci_init()
        sg = self.seg_at(t)
        fr = self._sci_layer(sg, t)
        k = self.segs.index(sg)
        lt = t - sg["start"]
        if k > 0 and lt < self.SCI_XF and self.segs[k - 1]["img_g"] != sg["img_g"]:
            fr = Image.blend(self._sci_layer(self.segs[k - 1], t), fr, R.ease(max(0.0, lt) / self.SCI_XF))
        return ImageChops.multiply(fr, self.cache["sci_shade"])

    def _sci_text_layer(self, key, lines, kind, hi, lo, width, fill, stroke=8):
        """글자 묶음(RGBA, 가운데 정렬) — 튀어나오게 키울 수 있게 따로 그린다."""
        if key not in self.cache:
            d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
            f = R.fit(d0, lines, kind, hi, lo, width)
            bbs = [d0.textbbox((0, 0), ln, font=f, stroke_width=stroke) for ln in lines]
            lh = f.size + 18
            w = int(max(b[2] - b[0] for b in bbs)) + 8
            h = int(lh * (len(lines) - 1) + max(b[3] for b in bbs)) + 8
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            for i, (ln, b) in enumerate(zip(lines, bbs)):
                d.text(((w - (b[2] - b[0])) / 2 - b[0], 4 + i * lh), ln, font=f, fill=fill, stroke_width=stroke,
                       stroke_fill=(0, 0, 0))
            self.cache[key] = im
        return self.cache[key]

    def _sci_pop(self, im, layer, cy, lt):
        """가운데 cy 에 붙인다 — 처음 SCI_POP 초는 크게 → 제자리(튀어나옴)."""
        q = R.ease(min(1.0, max(0.0, lt) / self.SCI_POP))
        sc = max(1.0, min(1.0 + 0.3 * (1 - q), (W - 40) / layer.width))   # 커져도 화면 폭 안
        ly = layer if sc == 1.0 else layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))), LZ)
        if q < 1:
            ly = fade(ly, 0.35 + 0.65 * q)
        im.alpha_composite(ly, (int((W - ly.width) / 2), int(cy - ly.height / 2)))
        return int(cy + layer.height / 2)

    def _sci_chip(self, d, y, text, f, fg=(226, 230, 238)):
        tw = R.tlen(d, text, f)
        d.rounded_rectangle([W / 2 - tw / 2 - 22, y, W / 2 + tw / 2 + 22, y + f.size + 22], (f.size + 22) // 2,
                            fill=(0, 0, 0, 150))
        ctext(d, y + 9, text, f, fg)

    def f_sci(self, sg, lt):
        self._sci_init()
        im = self.sci_bg(sg["start"] + lt).convert("RGBA")
        im.alpha_composite(self.cache["sci_top"], (0, 0))
        d = ImageDraw.Draw(im)
        if sg["kind"] == "intro":
            self._sci_chip(d, self.cache["sci_hook_bottom"] + 26, SCI_INTRO_TAG.get(self.sci_fmt, ""), R.font("bold", 40),
                           ACC_SCI)
            return im
        if sg["kind"] == "verdict":
            v = self.s["verdict"]
            big = self._sci_text_layer("sci_vbig", [v["big"]], "head", 170, 90, W - 120, ACC_SCI, 10)
            yb = self._sci_pop(im, big, self.SCI_BIG_Y, lt)
            ask = self._sci_text_layer("sci_ask", R.wrap(d, ask_of(self.s), R.font("bold", 66), W - 160)[:2], "bold",
                                       66, 44, W - 160, (255, 255, 255), 7)
            a = min(1.0, max(0.0, (lt - sg.get("ask_at", 0.6)) / 0.3))
            if a > 0:
                im.alpha_composite(fade(ask, a), (int((W - ask.width) / 2), yb + 60))
            return im
        k = sg["k"]
        b = self.s["beats"][k]
        big = self._sci_text_layer(("sci_big", k), [b["big"]], "head", 220, 110, W - 120, ACC_SCI, 10)
        yb = self._sci_pop(im, big, self.SCI_BIG_Y, lt)
        sub = self._sci_text_layer(("sci_sub", k), R.wrap(d, b["sub"], R.font("bold", 60), W - 140)[:2], "bold", 60, 42,
                                   W - 140, (255, 255, 255), 7)
        im.alpha_composite(sub, (int((W - sub.width) / 2), yb + 26))
        y = yb + 26 + sub.height + 20
        src = b.get("src")
        if isinstance(src, int) and 0 <= src < len(self.sci_srcs):
            self._sci_chip(d, y, f"출처 · {source_host(self.sci_srcs[src])}", R.font("bold", 30))
        if self.sci_bars:
            self._sci_bar_strip(d, k, lt)
        return im

    def _sci_bar_strip(self, d, k, lt):
        """compare: 작은 것부터 막대가 하나씩 자란다(로그 비율) — 지금 항목은 노랗게, 지난 것은 흰빛. 오른쪽에 큰 글자."""
        n = len(self.s["beats"])
        row = min(self.SCI_BAR_ROW, (SCI_Y_MAX - self.SCI_BAR_TOP) // max(1, n))
        x0, full = 120, W - 2 * 120 - 260                  # 막대 끝 ≤ x 700 · 값 글자도 오른쪽 버튼 열(x 960~) 앞에서 끝난다
        fv = R.font("bold", max(20, row - 12))
        for j in range(k + 1):
            g = R.ease(min(1.0, lt / 0.45)) if j == k else 1.0
            ln = max(10, full * self.sci_frac[j] * g)
            y = self.SCI_BAR_TOP + j * row
            col = ACC_SCI + (255,) if j == k else (235, 238, 245, 170)
            d.rounded_rectangle([x0, y + 4, x0 + ln, y + row - 6], (row - 10) // 2, fill=col)
            d.text((x0 + ln + 16, y + (row - fv.size) / 2 - 3), self.s["beats"][j]["big"], font=fv,
                   fill=ACC_SCI if j == k else (235, 238, 245), stroke_width=3, stroke_fill=(0, 0, 0))

    # birth ───────────────────────────────────────────
    def f_birth(self, sg, lt):
        if "birth" not in self.cache:
            im = self.base.copy()
            if self.a.get("bg"):
                b = R.cover(Image.open(self.a["bg"]).convert("RGB"), W, H).filter(ImageFilter.GaussianBlur(18))
                im = Image.blend(b, Image.new("RGB", (W, H), (255, 255, 255)), 0.62).convert("RGBA")
            d = ImageDraw.Draw(im)
            self.headline(d, 120)
            cw, chh, gx, gy = 300, 230, 18, 18
            x0, y0 = (W - 3 * cw - 2 * gx) // 2, 360
            for i, c in enumerate(self.s["cells"]):
                x, y = x0 + (i % 3) * (cw + gx), y0 + (i // 3) * (chh + gy)
                d.rounded_rectangle([x, y, x + cw, y + chh], 30, fill=(255, 255, 255, 225), outline=(226, 216, 245), width=3)
                d.text((x + 24, y + 18), f"{c['m']}월", font=self.f["num"], fill=NUM_BG[i % 4])
                ft, tl = R.fit_wrap(d, c["text"], "bold", 40, 30, cw - 40, 2)
                for j, ln in enumerate(tl):
                    d.text((x + 24, y + 100 + j * (ft.size + 10)), ln, font=ft, fill=INK)
            self.cache["birth"] = im
            self.cache["xy"] = (x0, y0, cw, chh, gx, gy)
        im = self.cache["birth"].copy()
        x0, y0, cw, chh, gx, gy = self.cache["xy"]
        k = int(lt / 0.12)                                   # 칸이 차례로 한 번 반짝
        if k < 12:
            x, y = x0 + (k % 3) * (cw + gx), y0 + (k // 3) * (chh + gy)
            ImageDraw.Draw(im).rounded_rectangle([x - 4, y - 4, x + cw + 4, y + chh + 4], 32, outline=ACC, width=8)
        return im


# ── 시간표 · 소리 ──────────────────────────────────────
def sci_speech(text: str) -> str:
    """sci 말 → TTS 로 보낼 글(단위·분수·영하를 한글로 → 숫자는 insta.to_speech 가 한글 읽기로)."""
    for rx, b in SCI_SAY_MAP:
        text = rx.sub(b, text)

    def num(m):                                           # insta.say_numbers 와 같되, 단위 없는 수 뒤 띄어쓰기는 남긴다
        unit = m.group(3)
        return R.I.read_number(m.group(1), unit) + ("" if unit else m.group(2))
    return R.I.to_speech(R.I.NUM_RE.sub(num, text))


def says_of(s: dict) -> list[str]:
    if s["kind"] == "sci":                                 # 말로 읽을 글(sci_speech) — plan 과 같은 열쇠
        return [sci_speech(x) for x in [s["say_intro"]] + [b["say"] for b in s["beats"]]
                + [s["verdict"]["say"], ask_of(s)]]
    out = [s["say_intro"]]
    out += [o["say"] for o in s.get("options", [])]
    for r in s.get("rounds", []):
        out += [x for x in (r.get("say_q"), r.get("say_a"), r.get("say")) if x]
    if s["kind"] != "birth":
        out.append(s.get("say_outro") or "몇 번 골랐어요?")
    return out


def plan(s: dict, dur: dict) -> tuple[list[dict], list[float]]:
    """장면(segs)과 틱 시각. dur = 말 → 초."""
    segs, ticks = [], []
    kind = s["kind"]

    def add(**kw):
        kw.setdefault("start", segs[-1]["start"] + segs[-1]["dur"] if segs else 0.0)
        segs.append(kw)
        return kw

    if kind == "sci":
        return _plan_sci(s, dur, add, segs, ticks)
    if kind in ("pick", "card"):
        d0 = max(6.5, dur[s["say_intro"]] + 0.4 + COUNT)
        add(kind="intro", dur=d0, say=s["say_intro"], at=0.3)
        ticks += [d0 - c for c in range(COUNT, 0, -1)]
        for k, o in enumerate(s["options"]):
            sg = add(kind="res", k=k, dur=dur[o["say"]] + 1.0, say=o["say"])
            sg["at"] = sg["start"] + 0.25
            ticks.append(sg["start"])
    elif kind == "quiz":
        add(kind="intro", dur=dur[s["say_intro"]] + 0.6, say=s["say_intro"], at=0.2)
        for k, r in enumerate(s["rounds"]):
            pa = dur[r["say_q"]] + 0.3 + COUNT
            sg = add(kind="q", k=k, dur=pa + dur[r["say_a"]] + 1.2, say=r["say_q"], phase_at=pa, say2=r["say_a"])
            sg["at"], sg["at2"] = sg["start"] + 0.2, sg["start"] + pa + 0.15
            ticks += [sg["start"]] + [sg["start"] + pa - c for c in range(COUNT, 0, -1)]
    elif kind == "balance":
        add(kind="intro", dur=dur[s["say_intro"]] + 0.5, say=s["say_intro"], at=0.2)
        for k, r in enumerate(s["rounds"]):
            sg = add(kind="r", k=k, dur=dur[r["say"]] + 0.4 + COUNT, say=r["say"])
            sg["at"] = sg["start"] + 0.2
            ticks += [sg["start"]] + [sg["start"] + sg["dur"] - c for c in range(COUNT, 0, -1)]
    else:  # birth — 짧게 · 다시 돈다
        add(kind="table", dur=max(9.0, dur[s["say_intro"]] + 5.0), say=s["say_intro"], at=0.3)
        ticks.append(0.05)
    if kind != "birth":
        out = s.get("say_outro") or "몇 번 골랐어요?"
        sg = add(kind="outro", dur=max(2.2, dur[out] + 0.9), say=out)
        sg["at"] = sg["start"] + 0.2
        ticks.append(sg["start"])
    return segs, ticks


def _plan_sci(s: dict, dur: dict, add, segs: list, ticks: list) -> tuple[list[dict], list[float]]:
    """sci: 질문(첫 그림) → 박자마다 그림·큰 숫자 → 끝 판정 + 열린 질문(코드). 18~40초(SCI_SEC) 안쪽으로."""
    intro = sci_speech(s["say_intro"])
    add(kind="intro", img=0, dur=dur[intro] + 0.55, say=intro, at=0.2)
    for k, b in enumerate(s["beats"]):
        sy = sci_speech(b["say"])
        sg = add(kind="beat", k=k, img=k, dur=dur[sy] + 0.45, say=sy)
        sg["at"] = sg["start"] + 0.2
        ticks.append(sg["start"])
    vs, ask = sci_speech(s["verdict"]["say"]), sci_speech(ask_of(s))
    sg = add(kind="verdict", img=len(s["beats"]) - 1, dur=1.0, say=vs, say2=ask)
    sg["at"] = sg["start"] + 0.3
    sg["at2"] = sg["at"] + dur[vs] + 0.35
    sg["ask_at"] = sg["at2"] - sg["start"] - 0.1             # 화면의 열린 질문은 말보다 살짝 먼저
    sg["dur"] = round(sg["at2"] - sg["start"] + dur[ask] + 1.2, 3)
    total = sg["start"] + sg["dur"]
    if total < SCI_SEC[0]:                                  # 너무 짧으면 끝 화면을 더 오래
        sg["dur"] = round(sg["dur"] + SCI_SEC[0] - total, 3)
    ticks.append(sg["start"])
    g = -1                                                  # 같은 그림이 이어지는 장면 묶음(첫 질문 + 1번 박자 = 한 그림)
    for i, x in enumerate(segs):
        x["n"] = i
        if i == 0 or (x["img"], x["kind"] == "verdict") != (segs[i - 1]["img"], segs[i - 1]["kind"] == "verdict"):
            g += 1
            t0 = x["start"]
        x["img_g"], x["img_t0"] = g, t0
    for x in segs:
        x["img_dur"] = sum(y["dur"] for y in segs if y["img_g"] == x["img_g"])
    return segs, ticks


def mix_audio(segs, ticks, got, total, wd) -> str:
    import numpy as np
    n = int(total * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for sg in segs:
        for say_k, at_k in (("say", "at"), ("say2", "at2")):
            if sg.get(say_k):
                v = R.wav_read(got[sg[say_k]])
                a = int(sg[at_k] * SR)
                voice[a:a + len(v)] += v[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = R.bed(n, seed=11)
    b *= vr * 0.18 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)
    win = int(SR * 0.2)
    duck = R.movavg(1 - 0.5 * np.clip(R.movavg(np.abs(voice), win) / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
    sfx = np.zeros(n, dtype="float32")
    rng = np.random.default_rng(5)
    for tt in ticks:
        tk = R.tick(rng) * vr * 1.1
        a = int(tt * SR)
        sfx[a:a + len(tk)] += tk[: max(0, n - a)]
    mix = (voice + b * duck + sfx)[: int(total * SR)]
    fo = int(SR * 0.5)
    mix[-fo:] *= np.linspace(1, 0, fo, dtype="float32")
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    R.wav_write(raw, mix)
    m4a = os.path.join(wd, "mix.m4a")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
          "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", m4a])
    return m4a


def assets(s: dict, wd: str, mock: bool) -> dict:
    def g(prompt, tag):
        p = os.path.join(wd, f"{tag}_{hashlib.sha1((STYLE + prompt + str(mock)).encode()).hexdigest()[:10]}.png")
        gen(prompt, p, mock)
        return p
    a: dict = {}
    if s["kind"] == "sci":                                  # 어두운 실사 · 세로(9:16) · catalog look 화풍
        style = sci_style(s)
        for k, b in enumerate(s["beats"]):
            p = os.path.join(wd, f"beat{k}_{hashlib.sha1((style + b['img'] + str(mock)).encode()).hexdigest()[:10]}.png")
            gen(b["img"], p, mock, style=style, aspect="9:16")
            a.setdefault("beats", []).append(p)
        return a
    if s["kind"] in ("pick", "card"):
        a["opts"] = [g(o["img"], f"opt{k}") for k, o in enumerate(s["options"])]
        if s["kind"] == "card":
            a["reveal"] = [g(o["reveal_img"], f"rev{k}") for k, o in enumerate(s["options"])]
    elif s["kind"] == "balance":
        a["bal"] = [{side: g(r[side]["img"], f"bal{k}{side}") for side in ("a", "b")} for k, r in enumerate(s["rounds"])]
    elif s["kind"] == "birth":
        a["bg"] = g(s["bg"], "bg")
    return a


def series_label(s: dict) -> str:
    d = dt.date.fromisoformat(s["date"])
    return f"{SERIES} #{P.series_no(d, P.slot_of(d, s.get('kind', '')))}"     # 10/13부터 하루 두 편 — 편 순서대로


def hashtags_of(s: dict) -> list[str]:
    """앞 5개만(겹친 것 빼고) — 10/9: 인스타 2025-12-18부터 5개 제한."""
    out: list[str] = []
    for t in s.get("hashtags") or []:
        if t and t not in out:
            out.append(t)
    return out[:HASHTAG_MAX]


def _hook(caption: str) -> str:
    """대본 caption 에서 코드가 붙이는 말(회차·본문 해시태그)과 부탁 줄(댓글·보내기)을 뺀 나머지."""
    text = _SERIES_RE.sub("", caption)
    lines = [re.sub(r"\s{2,}", " ", _TAG_RE.sub("", ln)).rstrip() for ln in text.strip().splitlines()]
    keep = lines[:1] + [ln for ln in lines[1:] if not any(w in ln for w in ASK_WORDS)]
    return "\n".join(keep).strip()


def source_host(url: str) -> str:
    """화면용 짧은 출처('oceanservice.noaa.gov' → 'noaa.gov')."""
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url or "").split("/")[0].lower())
    parts = host.split(".")
    keep = 3 if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("co", "ac", "edu", "org", "gov", "govt", "com", "net") else 2
    return ".".join(parts[-keep:])


def source_names(sources: list[str]) -> list[str]:
    """캡션 '출처:' 줄 — 기관 이름(겹친 것 빼고 순서대로): NOAA · RMG …"""
    out: list[str] = []
    for u in sources or []:
        label = source_host(u).split(".")[0]
        name = SRC_NAME.get(label) or (label.upper() if len(label) <= 4 else label.capitalize())
        if name not in out:
            out.append(name)
    return out


def caption_of(s: dict) -> str:
    # 10/9: 첫 줄 앞에 회차('오늘의 골라보기 #N') · 해시태그 5개 — 코드가 강제한다 · 10/11: 끝 줄은 부탁 없는 열린 질문 하나
    if s["kind"] == "sci":                                 # sci: 회차 없음 · 훅 한 줄 · 출처 · 열린 질문 · 해시태그 5개
        hook = (_hook(s.get("caption") or "").splitlines() or [" ".join(s.get("hook") or [])])[0]
        names = source_names(s.get("sources") or [])
        src = " · ".join(names[:SRC_MAX]) + (" 외" if len(names) > SRC_MAX else "")
        tags = hashtags_of(s)
        return f"{hook}\n\n출처: {src}\n\n{ask_of(s)}" + ("\n\n" + " ".join(tags) if tags else "")
    body = f"{series_label(s)} · {_hook(s['caption'])}"
    if s["kind"] in ("pick", "card"):
        body += "\n\n" + "\n".join(f"{k}번 {o['name']} — {o['result']}: {o['lines']}" for k, o in enumerate(s["options"], 1))
    elif s["kind"] == "quiz":
        body += "\n\n" + "\n".join(f"{k}번 문제 정답: {r['choices'][r['answer']]}" + (f" — {r['why']}" if r.get("why") else "")
                                   for k, r in enumerate(s["rounds"], 1))
    elif s["kind"] == "birth":
        body += "\n\n" + "\n".join(f"{c['m']}월 — {c['text']}" for c in s["cells"])
    body += f"\n\n{ASK[s['kind']]}"
    tags = hashtags_of(s)
    return body + ("\n\n" + " ".join(tags) if tags else "")


def cover_of(pa: Painter, s: dict) -> Image.Image:
    """커버 = 첫 장면 + 작은 회차 라벨(10/9). 라벨은 그리드 3:4 가운데 자르기(y 240~1680)에도 남고
    아래 25%(y 1440~, 캡션 자리)는 넘지 않게 y 1384~1432 에 둔다. 글꼴·색은 화면과 같은 토큰(bold · ACC).
    sci 는 골라보기가 아니라 회차가 없다 — 첫 프레임 그대로."""
    if s["kind"] == "sci":
        return pa.frame(0.0).convert("RGB")
    pa.for_cover = True
    try:
        im = pa.frame(0.5 if s["kind"] != "birth" else 2.0).convert("RGBA")
    finally:
        pa.for_cover = False
    d = ImageDraw.Draw(im)
    text, f = series_label(s), R.font("bold", 32)
    tw, (y0, y1) = R.tlen(d, text, f), (1384, 1432)
    d.rounded_rectangle([W / 2 - tw / 2 - 26, y0, W / 2 + tw / 2 + 26, y1], (y1 - y0) // 2, fill=(255, 255, 255, 255),
                        outline=ACC, width=3)
    bb = f.getbbox(text)
    ctext(d, y0 + (y1 - y0 - (bb[3] - bb[1])) / 2 - bb[1], text, f, ACC)
    return im.convert("RGB")


TH_TILE = 1080                                            # 쓰레드 캐러셀 한 장(정사각) — 번호만 얹는다(결과 글은 답글 스포일러)
TH_TABLE = (0, 40, W, 1390)                               # 쓰레드 태어난 달 표 = 제목+12칸만 4:5(1080×1350)로 자른다


def threads_images(pa: Painter, s: dict, out_dir: str, stem: str) -> list[str]:
    """쓰레드 2주 시험(10/11~10/24, pick_threads.py)에 붙일 그림 — pick·card 는 고르기 그림 4장(번호 배지),
    birth 는 표 한 장. quiz·balance 는 글+투표라 그림이 없다. 같은 그림(그림 캐시)·같은 글꼴·색 토큰을 쓴다."""
    out = []
    if s["kind"] in ("pick", "card"):
        for k, p in enumerate(pa.a["opts"]):
            im = R.cover(Image.open(p).convert("RGB"), TH_TILE, TH_TILE).convert("RGBA")
            badge(ImageDraw.Draw(im), 120, 120, 78, str(k + 1), NUM_BG[k], R.font("head", 96))
            dst = os.path.join(out_dir, f"{stem}_th{k + 1}.jpg")
            im.convert("RGB").save(dst, "JPEG", quality=90)
            out.append(dst)
    elif s["kind"] == "birth":
        pa.frame(0.0)                                      # 표(반짝임 없는 바탕)를 캐시에 그린다
        dst = os.path.join(out_dir, f"{stem}_th1.jpg")
        pa.cache["birth"].convert("RGB").crop(TH_TABLE).save(dst, "JPEG", quality=90)
        out.append(dst)
    return out


def _threads_images_safe(pa: Painter, s: dict, out_dir: str, stem: str) -> list[str]:
    """쓰레드 그림이 실패해도 릴스 렌더·인스타 게시는 그대로 간다(쓰레드 단계가 '그림 없음'으로 멈춘다)."""
    try:
        return threads_images(pa, s, out_dir, stem)
    except Exception as e:  # noqa: BLE001
        print(f"::warning title=쓰레드 그림 실패::{str(e)[:200]} — 릴스는 그대로 렌더한다")
        return []


def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    s = load(path)
    errs = check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    for w in warns(s):
        print(f"⚠️ {w}")
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    sci = s["kind"] == "sci"
    got, how = R.synth(says_of(s), os.path.join(wd, "voice"), mock, tempo=SCI_TEMPO if sci else None)
    dur = {t: R.wav_dur(p) for t, p in got.items()}
    segs, ticks = plan(s, dur)
    total = round(segs[-1]["start"] + segs[-1]["dur"], 3)
    if sci and total > SCI_SEC[1]:                         # 40초 넘으면 말만 조금 더 빠르게(최대 SCI_SPEEDUP)
        speech = sum(dur.values())
        factor = min(SCI_SPEEDUP, speech / max(1.0, speech - (total - SCI_SEC[1])))
        print(f"   ⏩ {total:.1f}초 > {SCI_SEC[1]} — 말 {factor:.2f}배")
        got = {t: R.retime(p_, factor, os.path.join(wd, "voice")) for t, p_ in got.items()}
        dur = {t: R.wav_dur(p_) for t, p_ in got.items()}
        segs, ticks = plan(s, dur)
        total = round(segs[-1]["start"] + segs[-1]["dur"], 3)
    if sci and total > SCI_SEC[1] + 2:
        raise SystemExit(f"sci 릴스 {total:.1f}초 > {SCI_SEC[1]} — 대본(say)을 줄일 것")
    m4a = mix_audio(segs, ticks, got, total, wd)
    pa = Painter(s, a, segs)
    silent = os.path.join(wd, "silent.mp4")
    R.encode(pa, total, silent)
    out = os.path.join(out_dir, f"{stem}.mp4")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-c:v", "copy", "-c:a", "copy", "-shortest", out])
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    cover_of(pa, s).save(cover, "JPEG", quality=90)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    picks = [0.5] + [sg["start"] + sg["dur"] * f for sg in segs for f in ((0.35, 0.9) if sg["kind"] == "q" else (0.7,))]
    tw, th = 360, 640
    sh_im = Image.new("RGB", (tw * 3, th * 2), (0, 0, 0))
    for i, tt in enumerate(picks[:6]):
        sh_im.paste(pa.frame(tt).resize((tw, th), LZ), ((i % 3) * tw, (i // 3) * th))
    sh_im.save(sheet, "JPEG", quality=85)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "src_n": s.get("src_n"), "video": out,
            "cover": cover,
            "sheet": sheet, "seconds": total, "voice": how, "caption": caption_of(s),
            "threads_images": _threads_images_safe(pa, s, out_dir, stem)}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="인스타 릴스('오늘의 골라보기' · sci) 검사·렌더")
    ap.add_argument("cmd", choices=["check", "render"])
    ap.add_argument("script", nargs="+")
    ap.add_argument("--out", default=os.path.join(R.ROOT, "output", "insta_pick_render"))
    ap.add_argument("--work", default=os.path.join(R.ROOT, "output", "insta_pick_work"))
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    bad = 0
    for p in a.script:
        if a.cmd == "check":
            s = load(p)
            errs, ws = check(s), warns(s)
            print(f"{'✅' if not errs else '❌'} {p}" + ("" if not errs else "\n   " + "\n   ".join(errs))
                  + "".join(f"\n   ⚠️ {w}" for w in ws))
            bad += bool(errs)
            continue
        meta = render(p, a.out, a.work, a.mock)
        print(json.dumps({k: meta[k] for k in ("video", "seconds", "voice")}, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
