#!/usr/bin/env python3
"""인스타 병맛(bm) 릴스 두 꼴 — 골라보기 자리 2주 시험 10/25~11/07 (2026-10-20, 편성은 pick_plan.BM_*).

왜: 10/15~10/20 sci 중앙값 약 440 vs 골라보기 약 117(사용자 승인 10/20 '1번 ㄱㄱ'). 조사(10/20): 황당한 질문에 진짜 숫자로
  정색하고 답하는 쇼츠가 터진다(원리뷰 '해파리에 쏘였을 때 오줌을 누면?' 632만 · 김블루 50편 중앙값 121만 · 희본 869만),
  사람 일을 하는 AI 동물이 가장 새 범주(상위 50 중 49%가 최근 30일 · 꿀잼식빵 705만). 브레인롯 캐릭터는 피한다
  (한국 중앙값 약 2.5천 · 22개+ 캐릭터 상표·저작권 소송). 움직이는 영상(AI 드라마·병맛 애니)은 정지 그림으로 못 한다.

꼴(kind) — 날짜로 번갈아(pick_plan.bm_kind):
  bm_paper  A '이거 진짜 논문임' 18~23초 · 무표정 여자 목소리(Supertonic F1) ~임/~함 반말
            0초부터 말 + 밝은 실사 황당 그림 + 노란 큰 제목(펀치 줌) → 코드가 그린 '도장' 카드(하얀 번쩍 + 쿵) →
            숫자 박자 2~3개 → 펀치라인 → 0.4초 멈춤·무음 → '띠용'(코드로 만든 소리) + 살짝 흔들림 → (다음: … 끝 카드)
  bm_animal B '정색 동물 다큐' 18~22초 · 동물 한 종이 사람 일을 한다(손님도 동물 · 사람은 안 그린다 · 같은 동물 묘사를 장면마다 복사)
            다큐 내레이션(F1, 정색) + 진짜 동물 사실 하나(출처·숫자 검사) → 사건 → 0.5초 무음 → 동물의 한마디는
            ★다른 목소리(edge-tts ko-KR-InJoonNeural, -10~-35%, 무료) 말풍선 → 펀치 → 끝 카드 + 띠용
숫자: 화면·말·캡션의 모든 숫자는 그 대본 facts 에 있는 수만(콤마·단위 무시 · 만·억은 곱한 값도 — pick_reel 의 sci 검사 그대로).
  facts 마다 src → sources(URL). 캡션 = 짧은 구어체 한 줄 + '출처: <도메인>' + 해시태그 5개까지(코드가 붙인다 · 회차 없음).
화면: 1080×1920 · 그린 것은 모두 y ≤ BM_Y_MAX(1400) — 아래 25%(y 1440~)는 인스타 캡션·버튼 자리(흔들림 여유 포함).
  번쩍(flash)·흔들림(shake)은 화면 전체 효과라 바탕(bg_at)에도 같이 들어간다(테스트는 바탕과 다른 곳만 '그린 것'으로 본다).

    python insta/pick_reel.py check <bm 대본.json>          # pick_reel 이 이 모듈로 넘긴다
    python insta/pick_reel.py render <bm 대본.json> --out … [--mock]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick_plan as P  # noqa: E402
import pick_reel as K  # noqa: E402  (숫자 검사·금지어·출처 이름·그림 생성·해시태그를 같이 쓴다)
import render_reel as R  # noqa: E402  (글꼴·목소리·배경음·인코딩)

W, H, FPS, SR = R.W, R.H, R.FPS, R.SR
LZ = getattr(Image, "Resampling", Image).LANCZOS
BIL = getattr(Image, "Resampling", Image).BILINEAR
EXTENT = getattr(Image, "Transform", Image).EXTENT
PAPER, ANIMAL = P.BM_KINDS
KINDS = P.BM_KINDS
SERIES = P.BM_SERIES                                      # 화면 꼴 이름(작은 칩) · B 끝 카드 제목
TYPES = {PAPER: ("hook", "stamp", "beat", "punch"), ANIMAL: ("hook", "fact", "beat", "incident", "quote", "punch")}
N_LINES = (5, 7)
HEAD_MAX, SAY_MAX, SUB_MAX, BIG_MAX, STAMP_MAX = 13, 32, 32, 10, 16
TOPIC_MAX, NEXT_MAX, END_MAX, CAPTION_MAX, QUOTE_MAX = 20, 14, 16, 40, 20
QUOTE_RATE = (-35, -10)                                   # edge-tts 빠르기(%) — 느리고 무표정하게
QUOTE_RATE_DEFAULT = -20
QUOTE_VOICE = os.environ.get("INSTA_BM_QUOTE_VOICE", "ko-KR-InJoonNeural")
QUOTE_FALLBACK = "M1"                                     # edge 가 막히면 Supertonic 남자 목소리(느리게) — 다른 목소리는 지킨다
TEMPO = 0.95                                              # 정색은 조금 느리게
CPS = 5.6                                                 # 길이 어림 = 읽는 글자(insta.speech_len, 공백·부호 빼고)/초 — F1 실측 5.9(×0.95 → 5.6, 10/20)
SPEEDUP = 1.15                                            # 길면 말만 이만큼까지 빠르게
GAP = 0.45                                                # 줄 사이 쉼(정색 개그는 쉼이 반)
GAP_MAX = 0.9                                             # 짧은 대본은 끝을 늘이기 전에 줄 사이 쉼부터 이만큼까지 늘린다
STAMP_LEAD, STAMP_HIT = 0.34, 0.16                        # 도장: 쾅 찍히는 시각 · 그 뒤 말
FREEZE = 0.4                                              # A 펀치 뒤 멈춤·무음
SILENCE = 0.5                                             # B 사건 뒤 무음(동물 한마디 전)
BOING_HOLD = 1.25                                         # 띠용 뒤 남는 시간(A)
END_HOLD = 1.5                                            # 끝 카드(B · A 의 '다음:')
SHAKE_DUR, FLASH_DUR, POP_DUR = 0.5, 0.24, 0.22
BM_Y_MAX = 1400                                           # 그린 것의 아랫변(흔들림 3% 확대 + 12px 를 더해도 1440 안쪽)
YEL, WHITE, BLACK = R.ACCENT, (255, 255, 255), (0, 0, 0)
STAMP_RED = (214, 38, 52)
STYLE = {PAPER: "bright cheerful photorealistic photo, natural daylight, high-key soft lighting, vivid colors, sharp focus, "
                "funny everyday scene, clean simple background, vertical composition, ",
         ANIMAL: "bright photorealistic wildlife documentary photo of an animal doing a human job, natural daylight, "
                 "vivid colors, sharp focus, cute, vertical composition, "}

# ── 내용 한계(글 + 그림 묘사 모두, 소문자로 본다) ─────────
BRAINROT = ("브레인롯", "brainrot", "brain rot", "퉁퉁퉁", "사후르", "tung tung", "sahur", "트랄랄레로", "tralalero",
            "봄바르디로", "bombardiro", "크로코딜로", "crocodilo", "리릴리", "lirili", "발레리나 카푸치나", "ballerina cappuccina",
            "카푸치노 아사시노", "cappuccino assassino", "파타핌", "patapim", "침판지니", "chimpanzini", "italian brainrot")
CHARACTERS = ("치이카와", "chiikawa", "먼작귀", "하치와레", "hachiware", "김햄찌", "햄찌", "포켓몬", "pokemon", "pokémon", "피카츄",
              "pikachu", "짱구", "뽀로로", "pororo", "펭수", "pengsoo", "핑구", "pingu", "산리오", "sanrio", "헬로키티", "hello kitty",
              "쿠로미", "kuromi", "디즈니", "disney", "픽사", "pixar", "미키마우스", "mickey mouse", "스폰지밥", "spongebob", "도라에몽",
              "doraemon", "카카오프렌즈", "춘식이", "잔망루피", "마다가스카", "madagascar", "해피 피트", "해피피트", "happy feet",
              "쿵푸팬더", "쿵푸 팬더", "kung fu panda", "주토피아", "zootopia", "라따뚜이", "ratatouille", "미니언", "minion",
              "스누피", "snoopy", "가필드", "garfield", "톰과 제리", "tom and jerry", "곰돌이 푸", "winnie the pooh", "패러디",
              "parody", "명장면", "영화 장면", "movie scene")
CELEBS = ("아이유", "bts", "방탄소년단", "블랙핑크", "blackpink", "뉴진스", "newjeans", "에스파", "아이브", "세븐틴", "손흥민",
          "유재석", "강호동", "백종원", "침착맨", "김구라", "이영지", "머스크", "elon musk", "트럼프", "donald trump", "바이든", "biden",
          "윤석열", "이재명", "김정은", "시진핑", "푸틴", "putin", "테일러 스위프트", "taylor swift", "아인슈타인", "einstein")
SEXUAL = ("섹시", "야한", "19금", "성인용", "야동", "성관계", "sexy", "nude", "nsfw", "lingerie", "bikini", "erotic")
BODY = ("뚱뚱", "뚱보", "돼지같", "돼지 같", "못생", "살쪄", "살 쪄", "비만", "추녀", "추남", "얼굴 평가", "몸매 평가", "ugly",
        "obese")
DANGER = ("따라 해", "따라해", "집에서 해 보", "집에서 해봐", "직접 해 보", "직접 해봐", "먹어 봐", "먹어봐", "마셔 봐", "마셔봐",
          "챌린지", "challenge")
BRAND = re.compile(r"(?i)\d+\s*호선|신분당선|경의중앙선|수인분당선|공항철도|메트로|\b(?:metro|subway line|line \d+|logos?|"
                   r"starbucks|mcdonald'?s|coca[- ]cola|nike|samsung|iphone|gs25|7-eleven|seven eleven|kakao|naver)\b|"
                   r"스타벅스|맥도날드|코카콜라|나이키|삼성전자|아이폰|세븐일레븐|카카오톡|카카오프렌즈|네이버|쿠팡|배민")
# 사람 낱말 — 사람·여러 사람 역할(손님들·승객들…)은 막고, 동물에 붙는 한 사람 직업(cashier·driver·a raccoon customer)은 둔다
HUMAN = re.compile(r"(?i)\b(person|persons|people|man|men|woman|women|human|humans|boy|boys|girl|girls|child|children|"
                   r"guy|guys|lady|ladies|gentleman|gentlemen|businessman|businesswoman|customers|passengers|commuters|"
                   r"shoppers|tourists|workers|employees|students|staff|pedestrians|audience)\b")
SAY_BAN = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]|킹받|띠용|[\U0001F000-\U0010FFFF☀-➿]")   # TTS 가 'ㅋㅋ'·이모지·효과음 이름을 읽지 않게
NATIVE_TENS = re.compile(r"(?<![가-힣])(스물|서른|마흔|쉰|예순|일흔|여든|아흔)")   # 숫자는 아라비아 숫자로(facts 와 맞춰 본다)
ASK_EXTRA = ("팔로우", "구독", "좋아요 눌", "좋아요 부탁", "공유 부탁", "저장 부탁", "태그 부탁", "링크", "DM", "보내 줘", "보내줘",
             "댓글")                                       # + pick_reel.ASK_BAN(댓글·남겨 줘·공유해·태그해·저장해 …)
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_DIGIT = re.compile(r"\d")
_HANGUL = re.compile(r"[가-힣]")


def load(p: str) -> dict:
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def lines_of(s: dict) -> list[dict]:
    return [x for x in (s.get("lines") or []) if isinstance(x, dict)]


def _texts(s: dict) -> list[tuple[str, str]]:
    """검사할 글(어디, 글) — 화면·목소리·캡션 모두."""
    out = [(f"headline[{i}]", t) for i, t in enumerate(s.get("headline") or []) if isinstance(t, str)]
    out += [(f, s.get(f) or "") for f in ("topic", "next", "end", "caption", "animal_ko") if isinstance(s.get(f) or "", str)]
    for k, x in enumerate(lines_of(s), 1):
        out += [(f"{k}번 줄 {f}", x.get(f) or "") for f in ("say", "sub", "big", "stamp") if isinstance(x.get(f) or "", str)]
    return out


def speech(text: str, who: str = "f1") -> str:
    """말로 읽을 글 — 단위·숫자를 한글 읽기로(sci 와 같은 길) · F1 은 말줄임표를 쉼표로."""
    t = K.sci_speech(text)
    return t if who == "quote" else re.sub(r"\s*…\s*", ", ", t).strip(" ,")


def fact_pool(s: dict) -> list[float]:
    return K.fact_values({"facts": [f for f in s.get("facts") or [] if isinstance(f, dict)]})


def source_hosts(s: dict) -> list[str]:
    out: list[str] = []
    for u in s.get("sources") or []:
        h = K.source_host(u)
        if h and h not in out:
            out.append(h)
    return out


# ── 검사 ──────────────────────────────────────────────
def check(s: dict) -> list[str]:
    errs = []
    kind = s.get("kind")
    if kind not in KINDS:
        return [f"kind 는 {KINDS}"]
    try:
        d = dt.date.fromisoformat(s.get("date", ""))
    except (TypeError, ValueError):
        return ["date 는 YYYY-MM-DD"]
    want = P.bm_kind(d)
    if want is None:
        errs.append(f"{d} 는 병맛 편이 없는 날 — 병맛 시험은 {P.BM_FROM}~{P.BM_TO}")
    elif want != kind:
        errs.append(f"{d} 병맛 꼴은 {want} — 대본은 {kind}(꼴은 코드가 날짜로 정한다)")
    if not _SLUG.fullmatch(s.get("slug") or ""):
        errs.append("slug 는 영어 소문자·숫자·하이픈")
    topic = s.get("topic")
    if not isinstance(topic, str) or not 0 < len(topic) <= TOPIC_MAX:
        errs.append(f"topic(한국어 소재 이름) 1~{TOPIC_MAX}자")
    hl = s.get("headline")
    if not (isinstance(hl, list) and len(hl) == 2 and all(isinstance(x, str) and 0 < len(x) <= HEAD_MAX for x in hl)):
        errs.append(f"headline 은 두 줄 · 줄마다 {HEAD_MAX}자 이내")
    errs += _check_sources(s)
    ls = lines_of(s)
    if len(ls) != len(s.get("lines") or []) or not N_LINES[0] <= len(ls) <= N_LINES[1]:
        errs.append(f"lines 는 {N_LINES[0]}~{N_LINES[1]}줄(객체)")
    errs += _check_lines(s, kind, ls)
    errs += _check_numbers(s)
    errs += _check_words(s)
    cap = s.get("caption")
    if not isinstance(cap, str) or not cap.strip() or "\n" in cap.strip() or len(cap.strip()) > CAPTION_MAX:
        errs.append(f"caption 은 한 줄 · {CAPTION_MAX}자 이내(짧은 구어체) — 출처·해시태그는 코드가 붙인다")
    elif "#" in cap or "출처" in cap:
        errs.append("caption 에 '#'·'출처' 를 쓰지 않는다 — 코드가 붙인다")
    tags = s.get("hashtags")
    if not isinstance(tags, list) or len(tags) > K.HASHTAG_MAX or not all(
            isinstance(t, str) and re.fullmatch(r"#[^\s#]+", t) for t in tags):
        errs.append(f"hashtags 는 '#낱말' {K.HASHTAG_MAX}개까지")
    if not (s.get("bench") or {}).get("format"):
        errs.append("bench.format(어떤 바이럴 꼴을 빌렸는지) 없음")
    if kind == PAPER and s.get("next") is not None and (not isinstance(s["next"], str) or not 0 < len(s["next"]) <= NEXT_MAX):
        errs.append(f"next('다음:' 끝 카드 소재)는 1~{NEXT_MAX}자 — 안 쓰면 필드를 빼요")
    if kind == ANIMAL and s.get("end") is not None and (not isinstance(s["end"], str) or not 0 < len(s["end"]) <= END_MAX):
        errs.append(f"end(끝 카드 한 줄)는 1~{END_MAX}자")
    if not errs:                                          # 시간표 — 첫 말은 0.0초 · 길이 어림
        lo, hi = P.BM_SEC[kind]
        segs, ev = plan(s, est_durations(s))
        total = segs[-1]["start"] + segs[-1]["dur"]
        v0 = ev["voices"][0]
        if v0["at"] != 0.0 or v0["k"] != 0:
            errs.append("첫 줄(hook) 말은 0.0초에 시작해야 한다")
        if not lo - 3.0 <= total <= hi + 2.0:
            errs.append(f"길이 어림 {total:.1f}초 — {lo:g}~{hi:g}초에 맞게 말을 늘리거나 줄일 것(어림 {CPS}자/초)")
    return errs


def _check_sources(s: dict) -> list[str]:
    errs = []
    srcs = s.get("sources")
    if not (isinstance(srcs, list) and srcs and all(isinstance(u, str) and re.match(r"https?://[^\s/]+\.[^\s/]+", u)
                                                     for u in srcs)):
        return ["sources 는 출처 URL(https://…) 목록 — 하나 이상"]
    facts = s.get("facts")
    if not (isinstance(facts, list) and facts):
        return ["facts 는 [{fact, src}] 하나 이상 — 숫자는 여기서만"]
    used = set()
    for k, f in enumerate(facts):
        if not (isinstance(f, dict) and isinstance(f.get("fact"), str) and f["fact"].strip()):
            errs.append(f"facts[{k}].fact 없음")
            continue
        src = f.get("src")
        if not (isinstance(src, int) and not isinstance(src, bool) and 0 <= src < len(srcs)):
            errs.append(f"facts[{k}].src 는 sources 번호(0~{len(srcs) - 1})")
        else:
            used.add(src)
    unused = [i for i in range(len(srcs)) if i not in used]
    if unused and not errs:
        errs.append(f"sources {unused} 를 쓰는 fact 가 없다 — 안 쓰는 출처는 뺀다")
    return errs


def _check_lines(s: dict, kind: str, ls: list[dict]) -> list[str]:
    errs = []
    if not ls:
        return errs
    types = [x.get("type") for x in ls]
    bad = sorted({str(t) for t in types if t not in TYPES[kind]})
    if bad:
        errs.append(f"lines.type {bad} — {kind} 는 {TYPES[kind]}")
    if types[0] != "hook" or types.count("hook") != 1:
        errs.append("첫 줄만 hook(0초부터 말하는 황당한 한 줄)")
    if types[-1] != "punch" or types.count("punch") != 1:
        errs.append("펀치라인(punch) 한 줄이 맨 끝에 있어야 한다")
    if not ls[0].get("img"):
        errs.append("첫 줄(hook)에 img(첫 화면 그림)가 있어야 한다")
    nsrc = len(s.get("sources") or [])
    for k, x in enumerate(ls, 1):
        t = x.get("type")
        say = x.get("say")
        mx = QUOTE_MAX if t == "quote" else SAY_MAX
        if not isinstance(say, str) or not 0 < len(say) <= mx:
            errs.append(f"{k}번 줄 say 1~{mx}자")
            continue
        sp = speech(say, "quote" if t == "quote" else "f1")
        if SAY_BAN.search(say):
            errs.append(f"{k}번 줄 say 에 '{SAY_BAN.search(say).group(0)}' — 목소리가 ㅋㅋ·킹받·띠용·이모지를 읽지 않게"
                        "(화면용 웃음은 sub·caption 에)")
        if re.search(r"[A-Za-z]", sp):
            errs.append(f"{k}번 줄 say 에 영어 — 한글로 써요(목소리가 읽는다): {sp[:30]}")
        if NATIVE_TENS.search(say):
            errs.append(f"{k}번 줄 say 의 '{NATIVE_TENS.search(say).group(0)}…' — 숫자는 아라비아 숫자로(코드가 facts 와 맞춰 보고 읽어 준다)")
        for f, mx2 in (("sub", SUB_MAX), ("big", BIG_MAX), ("stamp", STAMP_MAX)):
            if x.get(f) is not None and (not isinstance(x[f], str) or not 0 < len(x[f]) <= mx2):
                errs.append(f"{k}번 줄 {f} 1~{mx2}자")
        img = x.get("img")
        if img is not None:
            if not isinstance(img, str) or not img.strip() or _HANGUL.search(img):
                errs.append(f"{k}번 줄 img 는 영어 그림 묘사")
            else:
                m = K.SCI_IMG_BAN.search(img)
                if m:
                    errs.append(f"{k}번 줄 img 에 '{m.group(0)}' — 그림엔 글자·얼굴 클로즈업이 없게(장면만 긍정형으로)")
                if kind == ANIMAL:
                    m = HUMAN.search(img)
                    if m:
                        errs.append(f"{k}번 줄 img 에 '{m.group(0)}' — 사람은 안 그린다(손님·승객도 그 동물로: 'penguins')")
                    if isinstance(s.get("animal"), str) and s["animal"] and s["animal"] not in img:
                        errs.append(f"{k}번 줄 img 에 animal 묘사가 그대로 없다 — 장면마다 같은 동물 묘사를 복사해 넣는다")
        src = x.get("src")
        has_num = any(_DIGIT.search(x.get(f) or "") for f in ("say", "sub", "big", "stamp") if isinstance(x.get(f), str))
        if src is not None and not (isinstance(src, int) and not isinstance(src, bool) and 0 <= src < nsrc):
            errs.append(f"{k}번 줄 src 는 sources 번호(0~{nsrc - 1})")
        elif has_num and src is None:
            errs.append(f"{k}번 줄에 숫자가 있으면 src(출처 번호)가 있어야 한다")
        if t == "stamp" and not (isinstance(x.get("stamp"), str) and x["stamp"] and src is not None):
            errs.append(f"{k}번 줄 stamp: 도장 글(stamp)과 src 가 있어야 한다(예: '2019 이그노벨 물리학상')")
        if t == "fact" and src is None:
            errs.append(f"{k}번 줄 fact 는 src(출처 번호)가 있어야 한다")
        if t == "quote":
            r = x.get("rate", QUOTE_RATE_DEFAULT)
            if isinstance(r, bool) or not isinstance(r, int) or not QUOTE_RATE[0] <= r <= QUOTE_RATE[1]:
                errs.append(f"{k}번 줄 quote rate 는 {QUOTE_RATE[0]}~{QUOTE_RATE[1]}(%) 정수")
    if kind == PAPER:
        if types.count("stamp") != 1 or types.index("stamp") not in (1, 2):
            errs.append("도장(stamp) 한 줄 — 2번째나 3번째 줄에(믿음 카드)")
        if not 2 <= types.count("beat") <= 3:
            errs.append("숫자 박자(beat) 2~3줄")
        nums = sum(1 for x in ls if x.get("type") != "punch"
                   and any(_DIGIT.search(x.get(f) or "") for f in ("say", "big", "stamp") if isinstance(x.get(f), str)))
        if nums < 2:
            errs.append(f"숫자가 든 줄이 {nums}개 — 진짜 숫자 박자가 2개 이상(도장 포함)")
    else:
        animal = s.get("animal")
        if not isinstance(animal, str) or not 12 <= len(animal) <= 160 or _HANGUL.search(animal):
            errs.append("animal 은 영어 동물 묘사 12~160자(장면마다 그대로 복사한다)")
        elif HUMAN.search(animal):
            errs.append(f"animal 묘사에 사람 낱말 '{HUMAN.search(animal).group(0)}'")
        if not isinstance(s.get("animal_ko"), str) or not 0 < len(s["animal_ko"]) <= 8:
            errs.append("animal_ko(동물 이름, 한국어) 1~8자")
        blob = " ".join([str(animal or ""), str(s.get("animal_ko") or "")] + [str(x.get("img") or "") + str(x.get("say") or "")
                                                                         for x in ls]).lower()
        if re.search(r"hamster|햄스터", blob) and re.search(r"office|desk|cubicle|사무실|회사|출근|퇴근|야근", blob):
            errs.append("햄스터 + 사무실은 피한다(김햄찌 계정과 겹친다) — 다른 동물이나 다른 일로")
        if not 1 <= types.count("fact") <= 2:
            errs.append("진짜 동물 사실(fact) 1~2줄 — 출처 있는 숫자")
        if types.count("incident") != 1 or types.count("quote") != 1:
            errs.append("사건(incident) 한 줄 + 동물 한마디(quote) 한 줄")
        elif types.index("quote") != types.index("incident") + 1:
            errs.append("동물 한마디(quote)는 사건(incident) 바로 다음(그 사이 0.5초 무음)")
        imgs = [x.get("img") for x in ls if x.get("img")]
        if len(imgs) < 3:
            errs.append("그림(img)은 3장 이상 — 장면이 바뀌어야 한다")
    return errs


def unbacked(text: str, pool: list[float]) -> list[str]:
    """facts 에 없는 수 — sci 검사(pick_reel.unbacked)와 같되, 만·억·million 이 붙으면 ★곱한 값으로만 맞춰 본다
    ('100만 개'가 facts 의 100 으로 통과하지 않게)."""
    out = []
    for raw, vs in K._vals(text):
        v = vs[-1]                                        # 단위가 붙으면 곱한 값, 아니면 그 수
        if not K._backed(v, pool):
            out.append(raw)
    return out


def _check_numbers(s: dict) -> list[str]:
    pool = fact_pool(s)
    errs = []
    for where, t in _texts(s):
        bad = unbacked(t, pool)
        if bad:
            errs.append(f"{where}: facts 에 없는 숫자 {bad} — 숫자는 그 대본 facts 에서만")
    return errs


def _hits(words, texts: list[str]) -> list[str]:
    """낱말 목록에서 글에 든 것 — 영어 낱말은 낱말 경계로(trumpet·debts·muskrat 같은 다른 낱말을 막지 않게), 한글은 그대로 포함."""
    out = set()
    for w in words:
        wl = w.lower()
        if re.search(r"[a-z]", wl):
            rx = re.compile(r"(?<![a-z])" + re.escape(wl) + r"(?![a-z])")
            if any(rx.search(t) for t in texts):
                out.add(w)
        elif any(wl in t for t in texts):
            out.add(w)
    return sorted(out)


def _check_words(s: dict) -> list[str]:
    errs = []
    texts = [t for _, t in _texts(s)]
    hits = sorted({w for w in K.BANNED for t in texts if w in t})
    if hits:
        errs.append(f"금지어 {hits}")
    asks = sorted({w for w in K.ASK_BAN + ASK_EXTRA for t in texts if w in t})
    if asks:
        errs.append(f"댓글·공유·저장·팔로우 부탁 말 {asks} — 인스타는 참여를 대놓고 부탁하는 글을 추천하지 않는다(캡션 포함)")
    low = [t.lower() for t in texts + [x.get("img") or "" for x in lines_of(s)] + [s.get("animal") or ""] if isinstance(t, str)]
    for name, words in (("잔혹 묘사", K.SCI_GORE), ("브레인롯", BRAINROT), ("캐릭터·영화 IP", CHARACTERS + K.SCI_FRANCHISE),
                        ("실존 인물", CELEBS + K.SCI_PEOPLE), ("성적인 말", SEXUAL), ("외모 비하", BODY),
                        ("따라 하면 위험", DANGER)):
        hits = _hits(words, low)
        if hits:
            errs.append(f"{name} 금지 {hits}")
    for t in low:
        m = BRAND.search(t)
        if m:
            errs.append(f"상표·노선 이름 금지 '{m.group(0)}'(지하철 노선·로고·브랜드 없이)")
            break
    return errs


def warns(s: dict) -> list[str]:
    return []


# ── 시간표 ────────────────────────────────────────────
def says_of(s: dict) -> list[tuple[str, str]]:
    """(말, 누구) — 누구 = f1(내레이션) | quote(동물 한마디, 다른 목소리)."""
    return [(speech(x["say"], "quote" if x["type"] == "quote" else "f1"), "quote" if x["type"] == "quote" else "f1")
            for x in lines_of(s)]


def est_durations(s: dict) -> dict:
    """말 → 초 어림(CPS) — 대본 검사·테스트."""
    return {t: round(0.1 + R.I.speech_len(t) / CPS * (1.3 if who == "quote" else 1.0), 3) for t, who in says_of(s)}


def plan(s: dict, dur: dict, gap: float = GAP) -> tuple[list[dict], dict]:
    """장면(segs)과 소리 사건(voices·sfx·bed_off). dur = 말(speech) → 초.
    seg: {kind, k(줄 번호|None), start, dur, img(그림 번호), hold(멈춘 화면 시각|None)}."""
    ls = lines_of(s)
    kind = s["kind"]
    segs: list[dict] = []
    ev: dict = {"voices": [], "sfx": [], "bed_off": [], "flash": [], "shake": []}
    img_of, cur = [], -1
    for i, x in enumerate(ls):
        if x.get("img"):
            cur = i
        img_of.append(max(0, cur))

    def add(**kw):
        kw.setdefault("start", round(segs[-1]["start"] + segs[-1]["dur"], 3) if segs else 0.0)
        kw.setdefault("hold", None)
        kw["dur"] = round(kw["dur"], 3)
        segs.append(kw)
        return kw

    def voice(k, at):
        x = ls[k]
        who = "quote" if x["type"] == "quote" else "f1"
        t = speech(x["say"], who)
        ev["voices"].append({"k": k, "text": t, "who": who, "at": round(at, 3), "dur": dur[t], "rate": x.get("rate", QUOTE_RATE_DEFAULT)})
        return dur[t]

    for k, x in enumerate(ls):
        t = x["type"]
        if t == "hook":
            sg = add(kind="hook", k=k, img=img_of[k], dur=0.0, start=0.0)
            sg["dur"] = round(voice(k, 0.0) + gap, 3)
            ev["sfx"].append(("pop", 0.0))
        elif t == "stamp":
            sg = add(kind="stamp", k=k, img=img_of[k], dur=0.0)
            hit = sg["start"] + STAMP_HIT
            sg["dur"] = round(STAMP_LEAD + voice(k, sg["start"] + STAMP_LEAD) + gap, 3)
            ev["sfx"].append(("thump", round(hit, 3)))
            ev["flash"].append(round(hit, 3))
        elif t == "punch":
            sg = add(kind="punch", k=k, img=img_of[k], dur=0.0)
            sg["dur"] = round(0.1 + voice(k, sg["start"] + 0.1) + (0.05 if kind == PAPER else 0.35), 3)
        elif t == "quote":                                # B: 사건 뒤 0.5초 무음(그림도 멈춤) → 다른 목소리 한마디
            prev = segs[-1]
            sl = add(kind="silence", k=k - 1, img=prev["img"], dur=SILENCE, hold=round(prev["start"] + prev["dur"] - 1e-3, 3))
            ev["bed_off"].append((sl["start"], None))
            sg = add(kind="quote", k=k, img=img_of[k], dur=0.0)
            sg["dur"] = round(0.05 + voice(k, sg["start"] + 0.05) + 0.35, 3)
        else:                                             # beat · fact · incident
            sg = add(kind=t, k=k, img=img_of[k], dur=0.0)
            tail = 0.1 if t == "incident" else gap
            sg["dur"] = round(0.08 + voice(k, sg["start"] + 0.08) + tail, 3)
            ev["sfx"].append(("tick", round(sg["start"], 3)))
    last = segs[-1]
    if kind == PAPER:                                     # 0.4초 멈춤·무음 → 띠용 + 흔들림 → (다음: …)
        fz = add(kind="freeze", k=last["k"], img=last["img"], dur=FREEZE, hold=round(last["start"] + last["dur"] - 1e-3, 3))
        ev["bed_off"].append((fz["start"], None))
        bo = add(kind="boing", k=last["k"], img=last["img"], dur=BOING_HOLD)
        ev["sfx"].append(("boing", bo["start"]))
        ev["shake"].append(bo["start"])
        if s.get("next"):
            add(kind="end", k=None, img=last["img"], dur=END_HOLD)
    else:                                                 # 끝 카드 + 띠용
        en = add(kind="end", k=None, img=last["img"], dur=END_HOLD)
        ev["sfx"].append(("boing", en["start"]))
        ev["shake"].append(en["start"])
    return segs, ev


def total_of(segs: list[dict]) -> float:
    return round(segs[-1]["start"] + segs[-1]["dur"], 3)


def pad_to(segs: list[dict], lo: float) -> None:
    """너무 짧으면 마지막 화면을 늘린다."""
    t = total_of(segs)
    if t < lo:
        segs[-1]["dur"] = round(segs[-1]["dur"] + lo - t, 3)


# ── 소리 ──────────────────────────────────────────────
def sfx_pop():
    import numpy as np
    n = int(SR * 0.14)
    t = np.arange(n) / SR
    f = 950 * np.exp(-t * 22) + 260
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 26)
    return (0.8 * y).astype("float32")


def sfx_thump():
    """도장 쿵 — 낮게 떨어지는 사인 + 짧은 잡음(코드로 만든다)."""
    import numpy as np
    n = int(SR * 0.42)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n) * np.exp(-t * 60)
    noise = np.convolve(noise, np.ones(18) / 18, mode="same")          # 거친 저역 통과
    return (0.95 * body + 0.5 * noise).astype("float32")


def sfx_boing():
    """'띠용' — 튀어 오르는 음높이 + 줄어드는 떨림(용수철)."""
    import numpy as np
    n = int(SR * 0.8)
    t = np.arange(n) / SR
    base = 170 + 260 * (1 - np.exp(-t / 0.05))
    wob = 1 + 0.22 * np.sin(2 * np.pi * 11 * t) * np.exp(-t * 3.2)
    ph = 2 * np.pi * np.cumsum(base * wob) / SR
    env = np.minimum(1, t / 0.006) * np.exp(-t * 3.4)
    y = (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)) * env
    return (0.7 * y).astype("float32")


SFX = {"pop": sfx_pop, "thump": sfx_thump, "boing": sfx_boing}
SFX_GAIN = {"pop": 0.9, "thump": 1.4, "boing": 1.15, "tick": 0.55}


def _fake(text: str, out: str, hz: float, sec: float) -> None:
    import numpy as np
    n = int(SR * max(0.6, sec))
    t = np.arange(n) / SR
    R.wav_write(out, 0.05 * np.sin(2 * math.pi * hz * t) * (0.6 + 0.4 * np.sin(2 * math.pi * 3 * t)))


def _edge(text: str, out_mp3: str, voice: str, rate: int) -> bool:
    r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={rate:+d}%", "--text", text,
                        "--write-media", out_mp3], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000


def synth(s: dict, wd: str, mock: bool) -> tuple[dict, str]:
    """말 → wav. 내레이션 = Supertonic F1(R.synth, TEMPO) · 동물 한마디 = edge-tts InJoon(느리게) — 막히면 Supertonic M1 느리게.
    mock = 가짜 소리(길이는 CPS 어림 · 한마디는 낮은 음)."""
    os.makedirs(wd, exist_ok=True)
    pairs = says_of(s)
    rates = {speech(x["say"], "quote"): int(x.get("rate", QUOTE_RATE_DEFAULT)) for x in lines_of(s) if x["type"] == "quote"}
    got, used = {}, []
    if mock:
        est = est_durations(s)
        for t, who in pairs:
            p = os.path.join(wd, f"m_{R.h16(t, who)}.wav")
            _fake(t, p, 140 if who == "quote" else 230, est[t] - 0.1)
            got[t] = p
        return got, "mock"
    f1 = [t for t, who in pairs if who == "f1"]
    g, how = R.synth(f1, wd, False, tempo=TEMPO)
    got.update(g)
    used.append(how)
    for t, who in pairs:
        if who != "quote":
            continue
        rate = rates.get(t, QUOTE_RATE_DEFAULT)
        out = os.path.join(wd, f"q_{R.h16(QUOTE_VOICE, rate, t)}.wav")
        if not (os.path.exists(out) and os.path.getsize(out) > 1000):
            raw = out[:-4] + "_raw.mp3"
            ok, via = False, f"edge:{QUOTE_VOICE}{rate:+d}%"
            for attempt in range(3):
                if _edge(t, raw, QUOTE_VOICE, rate):
                    ok = True
                    break
                time.sleep(2 + attempt * 4)
            af = ""
            if not ok:                                    # edge 가 막히면(403 등) Supertonic 남자 목소리를 느리게 — 목소리는 여전히 다르다
                import wbspark
                raw = out[:-4] + "_raw.wav"
                ok = wbspark.tts(t, raw, QUOTE_FALLBACK, timeout_sec=300)
                via = f"supertonic:{QUOTE_FALLBACK}(edge 실패)"
                af = f"atempo={max(0.65, 1 + rate / 100):.3f},"
            if not ok:
                raise RuntimeError(f"동물 한마디 목소리 실패: {t}")
            R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af",
                  f"{af}silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                  f"silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                  "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])
            os.remove(raw)
            used.append(via)
            print(f"   🎙️ {via} · {t}", flush=True)
        else:
            used.append(f"edge:{QUOTE_VOICE}(cache)")
        got[t] = out
    return got, ",".join(dict.fromkeys(u for u in used if u))


def mix_audio(segs: list[dict], ev: dict, got: dict, total: float, wd: str) -> str:
    """목소리 + 배경음(멈춤·무음 구간부터는 끈다) + 효과음(펑·쿵·틱·띠용) → -14 LUFS m4a."""
    import numpy as np
    n = int(total * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for v in ev["voices"]:
        w = R.wav_read(got[v["text"]])
        a = int(v["at"] * SR)
        voice[a:a + len(w)] += w[: max(0, n - a)]
    act = np.abs(voice) > 1e-4
    vr = float(np.sqrt(np.mean(voice[act] ** 2))) if act.any() else 0.1
    b = R.bed(n, seed=19)
    b *= vr * 0.12 / (float(np.sqrt(np.mean(b ** 2))) + 1e-9)
    env = np.ones(n, dtype="float32")
    for st, _ in ev["bed_off"]:                           # 끄고 나면 끝까지 끈다(정색 개그의 무음)
        env[int(st * SR):] = 0
    env = R.movavg(env, int(SR * 0.03)).astype("float32")
    win = int(SR * 0.2)
    duck = R.movavg(1 - 0.5 * np.clip(R.movavg(np.abs(voice), win) / (vr * 0.5 + 1e-9), 0, 1), win).astype("float32")
    sfx = np.zeros(n, dtype="float32")
    rng = np.random.default_rng(5)
    for name, tt in ev["sfx"]:
        x = R.tick(rng) if name == "tick" else SFX[name]()
        x = x * vr * SFX_GAIN[name] / (float(np.sqrt(np.mean(x ** 2))) + 1e-9) * 0.5
        a = int(tt * SR)
        sfx[a:a + len(x)] += x[: max(0, n - a)]
    mix = (voice + b * duck * env + sfx)[: int(total * SR)]
    fo = int(SR * 0.35)
    mix[-fo:] *= np.linspace(1, 0, fo, dtype="float32")
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    raw = os.path.join(wd, "mix.wav")
    R.wav_write(raw, mix)
    m4a = os.path.join(wd, "mix.m4a")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
          "-ar", str(SR), "-c:a", "aac", "-b:a", "192k", m4a])
    return m4a


# ── 그림 ──────────────────────────────────────────────
def brighten(im: Image.Image) -> Image.Image:
    """밝고 선명하게(10/14 sci 교훈: 첫 화면이 어두우면 피드에서 안 멈춘다) — autocontrast → 평균 밝기가 낮으면 감마로 끌어올림."""
    im = ImageOps.autocontrast(im.convert("RGB"), cutoff=0.5)
    mean = sum(ImageOps.grayscale(im).resize((64, 112)).getdata()) / (64 * 112)
    if mean < 128:
        g = math.log(132 / 255) / math.log(max(8.0, mean) / 255)
        lut = [min(255, int(255 * (i / 255) ** g + 0.5)) for i in range(256)]
        im = im.point(lut * 3)
    return ImageEnhance.Color(im).enhance(1.08)


def assets(s: dict, wd: str, mock: bool) -> dict:
    """줄마다 그림(img 가 있는 줄만 새로 · 없으면 앞 그림을 잇는다) — Spark z-image 세로 9:16, 밝은 실사 화풍."""
    style = STYLE[s["kind"]]
    out = {}
    for k, x in enumerate(lines_of(s)):
        if not x.get("img"):
            continue
        p = os.path.join(wd, f"img{k}_{hashlib.sha1((style + x['img'] + str(mock)).encode()).hexdigest()[:10]}.png")
        K.gen(x["img"], p, mock, style=style, aspect="9:16")
        out[k] = p
    return {"imgs": out}


# ── 화면 ──────────────────────────────────────────────
def _layer(lines: list[str], kind: str, hi: int, lo: int, width: float, fill, stroke: int = 8, gap: int = 16):
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    f = R.fit(d0, lines, kind, hi, lo, width)
    bbs = [d0.textbbox((0, 0), ln, font=f, stroke_width=stroke) for ln in lines]
    lh = f.size + gap
    w = int(max(b[2] - b[0] for b in bbs)) + 8
    h = int(lh * (len(lines) - 1) + max(b[3] for b in bbs)) + 8
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (ln, b) in enumerate(zip(lines, bbs)):
        d.text(((w - (b[2] - b[0])) / 2 - b[0], 4 + i * lh), ln, font=f, fill=fill, stroke_width=stroke, stroke_fill=BLACK)
    return im


def _scaled(layer: Image.Image, sc: float) -> Image.Image:
    if abs(sc - 1) < 1e-3:
        return layer
    return layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))), LZ)


class Painter:
    """segs/ev 대로 그린다 — frame(t) = 바탕(그림·그늘) + 글·카드 + 번쩍·흔들림. bg_at(t) = 같은 바탕·번쩍·흔들림, 글 없음."""

    def __init__(self, s: dict, a: dict, segs: list[dict], ev: dict):
        self.s, self.a, self.segs, self.ev = s, a, segs, ev
        self.ls = lines_of(s)
        self.kind = s["kind"]
        self.cache: dict = {}
        col = Image.new("L", (1, H))
        px = col.load()
        for y in range(H):                                # 위(제목)·아래(인스타 글)만 살짝 어둡게 — 그림은 밝게 둔다
            top = 0.42 * max(0.0, 1 - y / 560) ** 1.5
            bot = 0.38 * max(0.0, (y - 1480) / (H - 1480))
            px[0, y] = int(255 * (1 - max(top, bot)))
        self.shade = Image.merge("RGB", [col.resize((W, H))] * 3)
        self.groups = self._img_groups()

    # 시각 → 장면
    def seg_at(self, t: float) -> dict:
        for sg in self.segs:
            if sg["start"] <= t < sg["start"] + sg["dur"]:
                return sg
        return self.segs[-1]

    def _img_groups(self) -> dict:
        """같은 그림이 이어지는 동안(시작·길이) — 천천히 다가가는 움직임을 그 묶음 전체에 걸쳐."""
        out: dict = {}
        for sg in self.segs:
            g = out.setdefault(sg["img"], [sg["start"], 0.0])
            g[1] = sg["start"] + sg["dur"] - g[0]
        return out

    def _img(self, i: int, blur: bool = False) -> Image.Image:
        key = ("img", i, blur)
        if key not in self.cache:
            p = self.a["imgs"].get(i) or next(iter(self.a["imgs"].values()))
            im = brighten(R.cover(Image.open(p).convert("RGB"), round(W * 1.1), round(H * 1.1)))
            if blur:
                im = Image.blend(im.filter(ImageFilter.GaussianBlur(16)), Image.new("RGB", im.size, WHITE), 0.18)
            self.cache[key] = im
        return self.cache[key]

    def _eff(self, t: float) -> tuple[dict, float]:
        """멈춤(freeze·silence) 장면은 앞 장면 끝 시각으로 그린다."""
        sg = self.seg_at(t)
        if sg.get("hold") is not None:
            return self.seg_at(sg["hold"]), sg["hold"]
        return sg, t

    def _bg(self, t: float) -> Image.Image:
        sg, te = self._eff(t)
        end = sg["kind"] == "end"
        im = self._img(sg["img"], blur=end)
        t0, gd = self.groups.get(sg["img"], [sg["start"], sg["dur"]])
        p = R.ease(min(1.0, max(0.0, (te - t0) / max(0.5, gd))))
        z = 1.0 + 0.06 * p
        if te < POP_DUR:                                   # 0초 펀치 줌(크게 → 제자리)
            z += 0.10 * (1 - R.ease(te / POP_DUR))
        cw, ch = W / z, H / z
        cx, cy = im.width / 2, im.height / 2
        fr = im.transform((W, H), EXTENT, (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2), BIL)
        return ImageChops.multiply(fr, self.shade)

    def _post(self, im: Image.Image, t: float) -> Image.Image:
        """번쩍(도장) · 흔들림(띠용) — 바탕에도 같게(테스트가 비교한다)."""
        for ft in self.ev["flash"]:
            if ft <= t < ft + FLASH_DUR:
                im = Image.blend(im, Image.new("RGB", (W, H), WHITE), 0.82 * (1 - (t - ft) / FLASH_DUR))
        for st in self.ev["shake"]:
            if st <= t < st + SHAKE_DUR:
                q = (t - st) / SHAKE_DUR
                amp = 12 * (1 - q)
                dx, dy = amp * math.sin(t * 95), amp * 0.7 * math.cos(t * 77)
                z = 1.03
                cw, ch = W / z, H / z
                cx, cy = W / 2 - dx, H / 2 - dy
                im = im.transform((W, H), EXTENT, (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2), BIL)
        return im

    def bg_at(self, t: float) -> Image.Image:
        return self._post(self._bg(t), t)

    def frame(self, t: float) -> Image.Image:
        im = self._bg(t).convert("RGBA")
        self._overlay(im, t)
        return self._post(im.convert("RGB"), t)

    # 글·카드
    def _head_big(self):
        if "hb" not in self.cache:
            self.cache["hb"] = _layer(list(self.s["headline"]), "head", 132, 78, W - 90, YEL, 12, 20)
        return self.cache["hb"]

    def _head_small(self):
        if "hs" not in self.cache:
            self.cache["hs"] = _layer(list(self.s["headline"]), "head", 66, 44, W - 120, YEL, 7, 12)
        return self.cache["hs"]

    def _chip(self, d, y: int, text: str, size: int = 34, fg=WHITE, bg=(0, 0, 0, 165)):
        f = R.font("bold", size)
        tw = R.tlen(d, text, f)
        bb = f.getbbox("가")
        hh = bb[3] + 20
        d.rounded_rectangle([W / 2 - tw / 2 - 24, y, W / 2 + tw / 2 + 24, y + hh], hh // 2, fill=bg)
        d.text((W / 2 - tw / 2, y + 10 - bb[1] // 2), text, font=f, fill=fg)
        return y + hh

    def _sub(self, k: int):
        key = ("sub", k)
        if key not in self.cache:
            x = self.ls[k]
            text = x.get("sub") or x["say"]
            d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
            f, lines = R.fit_wrap(d0, text, "bold", 66, 46, W - 120, 2)
            self.cache[key] = _layer(lines, "bold", f.size, f.size, W - 120, WHITE, 8, 14)
        return self.cache[key]

    def _big(self, k: int):
        key = ("big", k)
        if key not in self.cache:
            self.cache[key] = _layer([self.ls[k]["big"]], "head", 190, 96, W - 110, YEL, 11)
        return self.cache[key]

    def _punch(self, k: int):
        key = ("punch", k)
        if key not in self.cache:
            x = self.ls[k]
            d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
            f, lines = R.fit_wrap(d0, x.get("sub") or x["say"], "head", 96, 64, W - 120, 3)
            self.cache[key] = _layer(lines, "head", f.size, f.size, W - 120, WHITE, 10, 18)
        return self.cache[key]

    def _stamp(self, k: int):
        key = ("stamp", k)
        if key not in self.cache:
            text = self.ls[k]["stamp"]
            d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
            f = R.fit(d0, [text], "head", 92, 52, 700)
            tw = R.tlen(d0, text, f)
            w, h = int(tw + 120), int(f.size * 1.0 + 110)
            card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(card)
            d.rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=(255, 255, 255, 236), outline=STAMP_RED + (255,), width=14)
            d.rounded_rectangle([22, 22, w - 23, h - 23], 18, outline=STAMP_RED + (255,), width=4)
            bb = d.textbbox((0, 0), text, font=f)
            d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], (h - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=STAMP_RED)
            self.cache[key] = card.rotate(7, resample=Image.BICUBIC, expand=True)
        return self.cache[key]

    def _bubble(self, k: int):
        key = ("bubble", k)
        if key not in self.cache:
            text = self.ls[k].get("sub") or self.ls[k]["say"]
            d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
            f, lines = R.fit_wrap(d0, text, "head", 70, 46, W - 300, 2)
            lh = f.size + 16
            tw = max(R.tlen(d0, ln, f) for ln in lines)
            w, h = int(tw + 100), int(lh * len(lines) + 70)
            im = Image.new("RGBA", (w, h + 60), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([3, 3, w - 3, h - 3], 44, fill=(255, 255, 255, 250), outline=BLACK + (255,), width=6)
            d.polygon([(w * 0.22, h - 8), (w * 0.17, h + 54), (w * 0.36, h - 8)], fill=(255, 255, 255, 250))
            d.line([(w * 0.22, h - 4), (w * 0.17, h + 54), (w * 0.36, h - 4)], fill=BLACK, width=6)
            for i, ln in enumerate(lines):
                bb = d.textbbox((0, 0), ln, font=f)
                d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], 34 + i * lh - bb[1] // 2), ln, font=f, fill=(20, 20, 24))
            self.cache[key] = im
        return self.cache[key]

    def _paste(self, im, layer, cy: float, sc: float = 1.0, a: float = 1.0, cx: float = W / 2):
        ly = _scaled(layer, sc)
        if a < 1:
            ly = K.fade(ly, a)
        full_h = ly.height
        x, y = int(cx - ly.width / 2), int(cy - ly.height / 2)
        y = min(y, BM_Y_MAX - full_h)                       # 아래 25% 를 넘지 않게
        sx, sy = max(0, -x), max(0, -y)                     # 화면 밖(왼쪽·위)으로 나간 만큼 잘라서 붙인다(도장이 크게 날아올 때)
        if sx or sy:
            ly = ly.crop((sx, sy, ly.width, ly.height))
        im.alpha_composite(ly, (max(0, x), max(0, y)))
        return y + full_h                                    # 붙인 것의 아랫변

    def _src_chip(self, d, y: int, k: int):
        src = self.ls[k].get("src")
        srcs = self.s.get("sources") or []
        if isinstance(src, int) and 0 <= src < len(srcs):
            self._chip(d, min(y, BM_Y_MAX - 70), f"출처 · {K.source_host(srcs[src])}", 30, (232, 236, 244))

    def _overlay(self, im: Image.Image, t: float):
        sg, te = self._eff(t)
        lt = te - sg["start"]
        d = ImageDraw.Draw(im)
        kind = sg["kind"]
        if kind == "end":
            self._end_card(im, d, lt)
            return
        if kind == "hook":                                  # 0~2초: 크고 노란 제목(튀어나옴) + 꼴 이름
            q = R.ease(min(1.0, lt / POP_DUR))
            hb = self._head_big()
            sc = max(1.0, min(1.18 - 0.18 * q, (W - 24) / hb.width))   # 커져도 화면 폭 안
            yb = self._paste(im, hb, 250 + hb.height / 2, sc)
            self._chip(d, yb + 24, SERIES[self.kind], 38, YEL)
        else:
            hs = self._head_small()
            yb = self._paste(im, hs, 132 + hs.height / 2)
            self._chip(d, yb + 14, SERIES[self.kind], 30)
        k = sg["k"]
        x = self.ls[k] if k is not None else {}
        pop = R.ease(min(1.0, max(0.0, lt) / POP_DUR))
        if kind == "stamp":                                 # 쾅: 크게 → 제자리(STAMP_HIT 에 닿는다)
            q = min(1.0, max(0.0, lt) / STAMP_HIT)
            sc = 2.1 - 1.1 * (q ** 2)
            y = self._paste(im, self._stamp(k), 820, sc, 0.25 + 0.75 * q)
            if q >= 1:
                self._src_chip(d, y + 28, k)
        elif kind in ("punch", "boing"):
            sc = 1.0
            if kind == "boing":                             # 띠용 — 한 번 커졌다 돌아온다
                sc = 1.0 + 0.14 * math.sin(math.pi * min(1.0, lt / 0.32))
            pl = self._punch(k)
            self._paste(im, pl, 840, max(1.0, min(sc, (W - 24) / pl.width)))   # 커져도 화면 폭 안
            return
        elif kind == "quote":
            q = R.ease(min(1.0, max(0.0, lt) / 0.16))
            self._paste(im, self._bubble(k), 760, 0.6 + 0.4 * q, 0.4 + 0.6 * q)
            return
        elif x.get("big"):
            y = self._paste(im, self._big(k), 820, 1.0 + 0.28 * (1 - pop), 0.35 + 0.65 * pop)
            self._src_chip(d, y + 26, k)
        elif kind in ("fact", "beat") and x.get("src") is not None:
            self._src_chip(d, 1080, k)
        if kind != "hook" or x.get("sub"):                  # 첫 줄은 큰 제목이 곧 자막(따로 sub 를 줄 때만)
            sb = self._sub(k)
            self._paste(im, sb, BM_Y_MAX - 8 - sb.height / 2)

    def _end_card(self, im, d, lt):
        q = R.ease(min(1.0, max(0.0, lt) / 0.25))
        if self.kind == PAPER:
            nx = self.s.get("next") or ""
            top = _layer(["다음 편"], "bold", 54, 40, W - 200, WHITE, 6)
            mid = _layer([nx], "head", 120, 70, W - 120, YEL, 11)
            y = self._paste(im, top, 700, 1.0, q)
            self._paste(im, mid, y + 40 + mid.height / 2, 1.0 + 0.15 * (1 - q), q)
        else:
            title = self.cache.setdefault("end_t", _layer([SERIES[ANIMAL]], "head", 112, 70, W - 120, YEL, 11))
            sub = self.cache.setdefault("end_s", _layer([self.s.get("end") or f"{self.s.get('animal_ko', '')} 편 끝."],
                                                        "bold", 64, 44, W - 160, WHITE, 7))
            y = self._paste(im, title, 780, 1.0 + 0.2 * (1 - q), q)
            self._paste(im, sub, y + 40 + sub.height / 2, 1.0, q)


# ── 캡션·커버·한눈에 보기 ──────────────────────────────
def caption_of(s: dict) -> str:
    """짧은 구어체 한 줄 + '출처: 도메인' + 해시태그 5개까지 — 회차·열린 질문 없음(병맛은 골라보기가 아니다)."""
    hook = (s.get("caption") or "").strip().splitlines()[0] if (s.get("caption") or "").strip() else s["headline"][0]
    hook = re.sub(r"\s{2,}", " ", K._TAG_RE.sub("", hook)).strip()
    hosts = source_hosts(s)
    src = " · ".join(hosts[:K.SRC_MAX]) + (" 외" if len(hosts) > K.SRC_MAX else "")
    tags = K.hashtags_of(s)
    return f"{hook}\n\n출처: {src}" + ("\n\n" + " ".join(tags) if tags else "")


COVER_T = 0.35                                            # 커버 = 펀치 줌이 자리 잡은 첫 장면(제목·꼴 이름·밝은 그림)


def cover_of(pa: Painter) -> Image.Image:
    return pa.frame(COVER_T)


def sheet_times(segs: list[dict]) -> list[float]:
    out = [0.0]
    for sg in segs:
        f = {"stamp": STAMP_HIT + 0.04, "boing": 0.12, "freeze": 0.2, "silence": 0.25, "end": 0.6}.get(sg["kind"])
        out.append(round(sg["start"] + (f if f is not None else sg["dur"] * 0.6), 3))
    return out[:10]


def contact_sheet(pa: Painter, segs: list[dict], out: str) -> None:
    times = sheet_times(segs)
    tw, th = 216, 384
    cols = 5
    rows = math.ceil(len(times) / cols)
    sh = Image.new("RGB", (tw * cols, th * rows), (0, 0, 0))
    d = ImageDraw.Draw(sh)
    for i, t in enumerate(times):
        x, y = (i % cols) * tw, (i // cols) * th
        sh.paste(pa.frame(t).resize((tw, th), LZ), (x, y))
        d.text((x + 8, y + 6), f"{t:.2f}s {pa.seg_at(t)['kind']}", fill=(255, 255, 0), font=R.font("bold", 20),
               stroke_width=2, stroke_fill=BLACK)
    sh.save(out, "JPEG", quality=88)


def first_frame_brightness(pa: Painter) -> float:
    """첫 화면 평균 밝기(0~255) — 0.0초 프레임."""
    g = ImageOps.grayscale(pa.frame(0.0)).resize((108, 192))
    return sum(g.getdata()) / (108 * 192)


# ── 렌더 ──────────────────────────────────────────────
def render(path: str, out_dir: str, work: str, mock: bool = False) -> dict:
    s = load(path)
    errs = check(s)
    if errs:
        raise SystemExit("대본 검사 실패:\n  " + "\n  ".join(errs))
    stem = f"{s['date']}_{s['kind']}_{s['slug']}"
    wd = os.path.join(work, stem)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    a = assets(s, wd, mock)
    got, how = synth(s, os.path.join(wd, "voice"), mock)
    dur = {t: R.wav_dur(p) for t, p in got.items()}
    lo, hi = P.BM_SEC[s["kind"]]
    segs, ev = plan(s, dur)
    total = total_of(segs)
    if total > hi:                                        # 길면 말만 조금 빠르게(최대 SPEEDUP)
        speech_sum = sum(dur.values())
        factor = min(SPEEDUP, speech_sum / max(1.0, speech_sum - (total - hi)))
        print(f"   ⏩ {total:.1f}초 > {hi:g} — 말 {factor:.2f}배")
        got = {t: R.retime(p_, factor, os.path.join(wd, "voice")) for t, p_ in got.items()}
        dur = {t: R.wav_dur(p_) for t, p_ in got.items()}
        segs, ev = plan(s, dur)
        total = total_of(segs)
    if total > hi + 0.3:
        raise SystemExit(f"병맛 릴스 {total:.1f}초 > {hi:g} — 대본(say)을 줄일 것")
    if total < lo:                                        # 짧으면 줄 사이 쉼부터 늘리고(정색 쉼), 그래도 모자라면 끝 화면을 늘린다
        n_gap = sum(1 for x in lines_of(s) if x["type"] in ("hook", "stamp", "beat", "fact"))
        segs, ev = plan(s, dur, min(GAP_MAX, GAP + (lo - total) / max(1, n_gap)))
        total = total_of(segs)
    pad_to(segs, lo)
    total = total_of(segs)
    m4a = mix_audio(segs, ev, got, total, wd)
    pa = Painter(s, a, segs, ev)
    silent = os.path.join(wd, "silent.mp4")
    R.encode(pa, total, silent)
    out = os.path.join(out_dir, f"{stem}.mp4")
    R.sh([R.ffmpeg(), "-y", "-loglevel", "error", "-i", silent, "-i", m4a, "-c:v", "copy", "-c:a", "copy", "-shortest", out])
    cover = os.path.join(out_dir, f"{stem}_cover.jpg")
    cover_of(pa).save(cover, "JPEG", quality=90)
    sheet = os.path.join(out_dir, f"{stem}_sheet.jpg")
    contact_sheet(pa, segs, sheet)
    meta = {"script": path, "date": s["date"], "kind": s["kind"], "slug": s["slug"], "video": out, "cover": cover,
            "sheet": sheet, "seconds": total, "voice": how, "caption": caption_of(s), "threads_images": [],
            "first_frame_brightness": round(first_frame_brightness(pa), 1),
            "sfx": [[n, t] for n, t in ev["sfx"]], "voices": [[v["who"], v["at"]] for v in ev["voices"]]}
    with open(os.path.join(out_dir, f"{stem}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta
