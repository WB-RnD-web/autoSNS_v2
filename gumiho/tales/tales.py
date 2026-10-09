#!/usr/bin/env python3
"""Nine Tails Tales — 대본 규칙·검사·메타데이터(제목·설명·챕터·태그)·편성.

한 편 = NNN_slug.json 한 파일(사람이 쓴 견본은 gumiho/tales/scripts/, 루틴이 쓴 건 routine/tales 의 output/tales/).
★2026-10-09 개편(사용자): 한국 설화·조선 주제 금지(롱폼 0~15회). 27화부터 '해설(explainer)' 롱폼 — 살아남을 수 없는 곳·
  심해·만약 태양이 사라지면 같은 실제 과학·장소를 실제 숫자로. 주 1편 일요일 14:00 UTC(미 동부 10시), 10~12분.
  구미는 목소리만(그림에 구미·여우 금지). 1~26화(설화)는 catalog 에 남기되 retired — 편성에서 뺀다.
대본을 누가 썼든(사람·루틴) ★이 검사를 통과해야 렌더·업로드한다 — 루틴에게 한 '지시'는 안 지켜질 수 있어서
분량·장면 수·필드·출처·숫자는 코드가 강제한다.

    python gumiho/tales/tales.py check gumiho/tales/scripts/027_places-you-cant-survive.json
    python gumiho/tales/tales.py next --date 2026-10-17   # 그 주(일요일 공개)의 편 — 없으면 {"none": true}. 루틴은 이것만 쓴다

scene 한 칸:
  {"say": "내레이션(영어)", "img": "그림 프롬프트(영어)", "fx": "fog", "move": "in", "hold": 0.8, "note": "화면 주석", "key": "짧은 이름"}
  {"say": "...", "gumi": "front|bead|wink"}       # 구미 본인 그림(assets/tales)
  {"card": "II", "sub": "The Fox Bead"}            # 장 제목 카드(말 없음) — sub 가 있는 카드가 유튜브 챕터가 된다
  {"say": "...", "img": "...", "odds": "SURVIVAL ODDS: ZERO"}   # 해설편: 꼭지마다 한 번 — 화면 위 판정 띠
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
ROUTINE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "output", "tales")
CATALOG = os.path.join(HERE, "catalog.json")

CHANNEL = "Nine Tails Tales"
VOICE = os.environ.get("TALES_VOICE", "F2")          # 구미 목소리(Supertonic). F3·F4 는 쓰지 않는다(발음 실측)
WPM = 159                                            # F2 실측(2026-09-29) — 분량 추정용
GUMI = ("front", "bead", "wink")
FX = ("none", "dust", "fog", "embers", "snow", "rain", "fireflies")
MOVES = ("in", "out", "left", "right", "up", "down")
FORMATS = ("tale", "urban", "list", "versus", "behind", "mystery", "pov",   # catalog.format — 같은 틀이 연속되지 않게 섞는다(WRITING.md)
           "places", "zones", "whatif", "ranked", "abandoned")
# 해설편 형식(2026-10-09): places = N곳 카운트다운 · zones = 층·구역별로 내려가기 · whatif = 시간순(분·시간·년)
#   · ranked = 순위 · abandoned = 버려진/사람이 못 사는 실제 장소 한 곳 깊게
EXPLAINER_FORMATS = FORMATS[7:]
NEW_FROM = 27            # 27화부터 해설편 규칙(구미 그림 금지·실사·출처·숫자 대조). 1~26화는 설화(retired)
# behind(2026-10-01) — 유명 작품(KPop Demon Hunters·파묘) 속 진짜 한국 설화. 작품은 검색 입구, 이야기는 설화다.
# mystery(2026-10-01) — 실제 기록·장소의 미스터리(1609 조선 하늘 기록 등). 영어권 대형 공포 채널은 실화·실제 장소가 주류다.
# pov(2026-10-02) — 시청자를 주인공(you)으로 세우는 2인칭 이야기. 1주 형식 실험(catalog.sprint)에서 처음 시험한다.

# 분량: 8분이 넘어야 중간 광고가 붙는다. 너무 길면 한 주 안에 Spark 그림이 부담.
WORDS_MIN, WORDS_MAX = 1200, 2600
SCENES_MIN, SCENES_MAX = 30, 90
SAY_MAX_WORDS = 70          # 한 그림에 26초 넘게 머물지 않게
HOOK_MAX_WORDS = 45         # 첫 장면(콜드 오픈) — 첫 15초가 이탈을 가른다
SHORT_WORDS = (60, 150)     # 쇼츠 30~55초
SHORT_HOOK_WORDS, SHORT_HOOK_CHARS = 7, 38     # 쇼츠 위 두 줄 제목
TITLE_SEARCH_MAX = 70                          # 검색 결과에서 보이는 제목 길이(3화부터)
SHORT_LINES = (4, 9)
# 편당 쇼츠 2~3개(2026-10-01): short + shorts_extra 1~2개. 쇼츠 피드 시간은 YPP 에 안 들어가지만 새 채널의 유입 깔때기다.
# 같은 편에서 첫 장면·hook·각도가 다른 쇼츠를 나눠 올려 어떤 주제·첫 1초가 먹히는지 비교한다(3화부터 필수).
EXTRA_SHORTS = (1, 2)
# ★2026-10-05 사용자: "구미호 영상이 너무 조선 같은 분위기만 풍긴다 — 좀 글로벌하게". 그림 앞에 늘 'Joseon dynasty era'
#   가 붙어 엘리베이터 괴담·곤지암 같은 현대 이야기도 갓·한옥으로 그려졌다. 10화(10/14, 실험 주간 다음)부터는
#   대본이 시대(look)를 고른다. 그 전 편은 look 이 없어 예전 화풍 그대로다(실험 주간을 흔들지 않는다).
LOOKS = {
    "modern": "present day, contemporary setting, ",      # 지금도 도는 괴담·미신·장소 — 기본
    "joseon": "Korean folklore, Joseon dynasty era, ",    # 조선이 배경인 옛이야기
    "japan": "Japanese folklore, old Japan, ",
    "china": "Chinese folklore, ancient China, ",
    "myth": "timeless mythic East Asian setting, ",       # 신화·저승·하늘처럼 시대가 없는 곳
    "real": "real-world location on Earth or in space, scientifically accurate, ",   # 해설편(27화~) — 이것만
}
GLOBAL_FROM = 10
# 같은 날(10/5) 점검: 첫 구독자 4명 중 3명이 'Never Cut Your Nails at Night in Korea' 쇼츠에서 왔다. 규칙형 쇼츠
#   420·161회 vs 이야기형 11회. 10화부터 쇼츠 3개(본 쇼츠 + 추가 2) 중 하나 이상은 규칙형 제목('Korean Rules').
RULE_TITLE = re.compile(r"(?i)^\s*(never|don'?t|do not|if you|always|you should never|why you should never)\b")
# 10/6 점검: 대결 쇼츠 'Gumiho vs Kitsune vs Huli Jing: Which Fox Is Scariest?' 11시간 1,555회(좋아요 41) ·
#   규칙 쇼츠 445 · 이야기형 쇼츠 2~22. 피드가 미는 건 규칙형과 대결형뿐이었다 → 6화(스프린트 남은 편)부터
#   쇼츠 중 하나 이상은 규칙형 또는 대결형 제목. 10화부터는 그대로(추가 쇼츠 2개 포함 셋 중 하나 이상).
VERSUS_TITLE = re.compile(r"(?i)\bvs\.?\s")
SHORT_TITLE_FROM = 6


def feed_title(title: str) -> bool:
    """피드가 미는 쇼츠 제목 꼴 — 규칙형(Never/Don't/If You/Always) 또는 대결형(A vs B)."""
    return bool(RULE_TITLE.match(title or "") or VERSUS_TITLE.search(title or ""))
EXTRA_SHORTS_GLOBAL = (2, 2)
THUMB_MAX_WORDS = 4
# 몇 달 뒤에도 통해야 한다(역주행) — 날짜를 타는 말은 금지. 사실로 적는 연도(1994년 영화 등)는 괜찮다
DATED = re.compile(r"(?i)\b(this (year|week|month|halloween|summer|winter|season)|last (week|month|year)|recently|"
                   r"right now|these days|currently|trending|as of today)\b")
BANNED = re.compile(r"(?i)\b(fuck|shit|rape|porn|nude|naked|gore|dismember|suicide|decapitat)\w*")

AI_NOTE = ("Illustrations and the narrator's voice are AI-generated. Stories are researched from Korean folklore "
           "and retold by Nine Tails Tales; details vary between regional versions.")
ABOUT = ("Nine Tails Tales: Korean urban legends, real mysteries, ghost stories and myths, told by Gumi, "
         "a 1,000-year-old nine-tailed fox. A new tale every week.")

# ── 해설편(27화~, 2026-10-09) ────────────────────────────
# 10~12분: F2 159wpm·템포 0.97·장면당 0.65초·카드 2.4초로 1,450~1,750단어. 8분이 넘어야 중간 광고.
EX_WORDS = (1400, 1900)
EX_SCENES = (40, 80)
EX_SEGMENTS_MIN = 4          # 번호 꼭지(카드+sub) 최소 — VERDICT 카드는 빼고 센다
EX_EXTRA_SHORTS = (1, 2)     # 본편에 붙는 쇼츠 2~3개(매일 쇼츠는 RULES 쪽이 따로 낸다)
ODDS_MAX = 34                # 판정 띠 글자 수(화면 위 한 줄)
SOURCES_MIN = 3
VERDICT_CARD = "VERDICT"
# 사용자 10/9: 한국 설화·조선은 '쓰레기 주제'. 구미·여우 그림 금지. 유튜브 '진정성 없는 콘텐츠' 정책 — 남의 세계관(SCP·백룸) 금지.
FOLKLORE = re.compile(r"(?i)\b(folklore|folk ?tales?|gumiho|kumiho|gumi-?ho|nine[- ]tail(ed)?|kitsune|huli ?jing|"
                      r"hanbok|hanok|joseon|dokkaebi|jeoseung|mudang|shaman\w*|gat hat|yokai|yōkai|kappa|oni|tamamo|"
                      r"daji|jiangshi|urban legends?|(korean|japanese|chinese|asian|east asian) (legends?|myths?|mythology|"
                      r"ghosts?|monsters?|spirits?|superstitions?))\b")
FOX_IMG = re.compile(r"(?i)\b(fox|foxes|vixen|fox-?like|nine tails)\b")    # 그림 프롬프트에서만(구미를 그리지 않는다)
BANNED_TOPICS = re.compile(r"(?i)\b(scp|backrooms|creepypasta|slender ?man|five nights at freddy'?s|fnaf|"
                           r"skibidi|poppy playtime|siren head)\b")
# 본편에 붙는 쇼츠 = 본편 한 꼭지만 자른 것. 제목 꼴: How Long Would You Last… · What Happens If… · A vs B 크기·위험 비교
SINGLE_ITEM = re.compile(r"(?i)^\s*(how long (would|could|can) you (last|survive)|could you survive|can you survive|"
                         r"what (happens|would happen) (if|when|to)|what if|why (you|nobody|no one|humans?) (can'?t|could never|"
                         r"can never|will never)|how (deep|cold|hot|big|far|high|fast|dark|loud|toxic) is|"
                         r"what (you'?d|you would) see)\b|\bvs\.?\s")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
# 살아남는 시간·걸리는 시간은 작은 수라도 catalog 에 있는 '수 + 단위' 그대로만(리뷰 10/9: '10 SECONDS'·'ninety seconds' 통과)
TIME_UNIT = r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|decades?|centur(?:y|ies))"
TIME_NUM = re.compile(r"(?i)(\d[\d,]*(?:\.\d+)?)((?:\s*(?:–|-|to|and|or)\s*\d[\d,]*(?:\.\d+)?)*)\s*(?:[a-z]+\s+)?"
                      + TIME_UNIT + r"\b")
NUM_WORDS = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
             r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
             r"million|billion|dozen)")
SPELLED_TIME = re.compile(r"(?i)\b" + NUM_WORDS + r"(?:[- ]" + NUM_WORDS + r")*(?:\s+[a-z]+)?\s+" + TIME_UNIT + r"\b")
SPELLED = re.compile(r"(?i)\b" + NUM_WORDS + r"\b")
# 판정 띠 이름 — 살아남는 시간처럼 읽히는 'TIME YOU'D LAST' 같은 이름은 쓰지 않는다(출처는 '의식이 버티는 시간'까지만 말한다)
ODDS_LABELS = ("SURVIVAL ODDS", "AWAKE FOR", "RISK")
FREE_NUM_MAX = 12            # 순위(#10)·'세 가지'처럼 작은 수는 자유. 그보다 큰 수는 catalog facts 에 있어야 한다
EX_AI_NOTE = ("Visuals and narration are AI-generated (altered or synthetic content): the images are illustrations, "
              "not real footage. Every number is researched from the sources listed above.")
EX_ABOUT = ("Nine Tails Tales: the most extreme places, depths and what-ifs, explained with real numbers. "
            "Narrated by Gumi, who has seen a lot and is impressed by very little. A new deep dive every Sunday.")


def explainer(s: dict) -> bool:
    """27화부터 해설편 규칙. 번호로 정한다(루틴이 format 을 빼먹어도 규칙을 피하지 못하게)."""
    return int(s.get("id") or 0) >= NEW_FROM


def badge(s: dict) -> str:
    """썸네일·쇼츠 위 띠 문구. 설화편은 예전 그대로."""
    if not explainer(s):
        return "KOREAN LEGEND"
    return (s.get("badge") or {"whatif": "WHAT IF", "ranked": "RANKED"}.get(s.get("format", ""), "EXPLAINED")).upper()[:18]


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def words(t: str) -> int:
    return len((t or "").split())


def stats(s: dict) -> dict:
    sc = s.get("scenes") or []
    w = sum(words(x.get("say", "")) for x in sc)
    return {"scenes": len(sc), "words": w, "est_min": round(w / WPM + 0.6 * len(sc) / 60, 1),
            "images": len({x["img"] for x in sc if x.get("img")}),
            "chapters": sum(1 for x in sc if x.get("card") and x.get("sub"))}


def check(s: dict, path: str | None = None) -> list[str]:
    """문제 목록(비었으면 통과)."""
    errs = []
    need = ("id", "slug", "title", "thumb", "scenes", "short", "tags", "sources", "hook")
    for k in need:
        if not s.get(k):
            errs.append(f"'{k}' 없음")
    if errs:
        return errs
    if not isinstance(s["id"], int) or s["id"] < 1:
        errs.append("id 는 1 이상 정수")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s["slug"]):
        errs.append(f"slug 형식: {s['slug']!r}")
    if path:
        base = os.path.basename(path)
        want = f"{s['id']:03d}_{s['slug']}.json"
        if base != want:
            errs.append(f"파일 이름은 {want} 여야 한다(지금 {base})")
    if len(s["title"]) > 100:
        errs.append(f"제목 {len(s['title'])}자 > 100")
    elif s.get("id", 0) >= 3 and len(s["title"]) > TITLE_SEARCH_MAX:
        errs.append(f"제목 {len(s['title'])}자 > {TITLE_SEARCH_MAX} — 검색 결과에서 잘린다(검색어를 앞쪽에)")
    th = s["thumb"]
    if not th.get("text") or words(th["text"]) > THUMB_MAX_WORDS or len(th["text"]) > 22:
        errs.append(f"썸네일 문구는 {THUMB_MAX_WORDS}단어·22자 이하: {th.get('text')!r}")
    if not th.get("img"):
        errs.append("thumb.img(썸네일 그림 프롬프트) 없음")
    sc = s["scenes"]
    st = stats(s)
    is_ex = explainer(s)
    (s_lo, s_hi), (w_lo, w_hi) = (EX_SCENES, EX_WORDS) if is_ex else ((SCENES_MIN, SCENES_MAX), (WORDS_MIN, WORDS_MAX))
    if not s_lo <= st["scenes"] <= s_hi:
        errs.append(f"장면 {st['scenes']}개 — {s_lo}~{s_hi}")
    if not w_lo <= st["words"] <= w_hi:
        errs.append(f"내레이션 {st['words']}단어 — {w_lo}~{w_hi}" + ("(10~12분)" if is_ex else "(약 8~16분)"))
    if st["chapters"] < 3:
        errs.append(f"챕터 카드(sub 있는 card) {st['chapters']}개 — 3개 이상(유튜브 챕터 조건)")
    keys = set()
    for i, x in enumerate(sc):
        kinds = [k for k in ("img", "gumi", "card") if x.get(k)]
        if len(kinds) != 1:
            errs.append(f"장면 {i}: img·gumi·card 중 정확히 하나 ({kinds})")
            continue
        if x.get("card"):
            if x.get("say"):
                errs.append(f"장면 {i}: 카드에는 say 를 넣지 않는다")
        elif not x.get("say"):
            errs.append(f"장면 {i}: say 없음")
        if words(x.get("say", "")) > SAY_MAX_WORDS:
            errs.append(f"장면 {i}: {words(x['say'])}단어 > {SAY_MAX_WORDS} — 둘로 나눌 것")
        if x.get("gumi") and x["gumi"] not in GUMI:
            errs.append(f"장면 {i}: gumi 는 {GUMI}")
        if is_ex and x.get("gumi"):
            errs.append(f"장면 {i}: 해설편은 구미를 그리지 않는다(목소리만) — gumi 대신 img")
        if x.get("fx", "dust") not in FX:
            errs.append(f"장면 {i}: fx {x.get('fx')!r} ∉ {FX}")
        if x.get("move", "in") not in MOVES:
            errs.append(f"장면 {i}: move {x.get('move')!r} ∉ {MOVES}")
        if len(x.get("note", "")) > 60:
            errs.append(f"장면 {i}: note 60자 이하")
        if not 0 <= float(x.get("hold", 0)) <= 3:
            errs.append(f"장면 {i}: hold 0~3초")
        if x.get("key"):
            keys.add(x["key"])
        for f in ("say", "img", "note"):
            if BANNED.search(x.get(f, "")):
                errs.append(f"장면 {i}: 금지어 {BANNED.search(x[f]).group(0)!r}")
    for i in range(1, len(sc)):
        if sc[i].get("card") and sc[i - 1].get("card"):
            errs.append(f"장면 {i - 1}·{i}: 카드가 연달아 나온다 — 글자 화면만 5초 넘게 이어지면 이탈한다(TALE 카드가 1장을 겸한다)")
    for i, x in enumerate(sc):
        m = DATED.search(x.get("say", ""))
        if m:
            errs.append(f"장면 {i}: 날짜를 타는 표현 {m.group(0)!r} — 몇 달 뒤에 보는 사람에게도 맞게 쓴다")
    if not any(t.lower() in s["title"].lower() for t in s["tags"][:3]):
        errs.append("제목에 검색어가 없다 — 태그 앞 3개 중 하나(예: gumiho)를 제목에 넣는다(검색 유입이 오래 간다)")
    first = sc[0] if sc else {}
    if not (first.get("img") and first.get("say")):
        errs.append("첫 장면은 그림+내레이션(콜드 오픈)이어야 한다")
    elif words(first["say"]) > HOOK_MAX_WORDS:
        errs.append(f"첫 장면 {words(first['say'])}단어 > {HOOK_MAX_WORDS}")
    errs += short_errs(s["short"], keys, s, "쇼츠")
    extra = s.get("shorts_extra") or []
    if not isinstance(extra, list):
        errs.append("shorts_extra 는 목록이어야 한다")
        extra = []
    tid = s.get("id", 0)
    lo, hi = EX_EXTRA_SHORTS if is_ex else (EXTRA_SHORTS_GLOBAL if tid >= GLOBAL_FROM else EXTRA_SHORTS)
    if tid >= 3 and not sprint_day(tid) and not lo <= len(extra) <= hi:
        errs.append(f"쇼츠는 편당 {lo + 1}~{hi + 1}개 — shorts_extra {len(extra)}개({lo}~{hi}개 필요). "
                    "첫 장면·hook·각도가 다른 쇼츠로 어떤 게 먹히는지 비교한다")
    errs += look_errs(s)
    if tid >= SHORT_TITLE_FROM and not is_ex:
        alls = [s["short"]] + [x for x in extra if isinstance(x, dict)]
        if not any(feed_title(x.get("title", "")) for x in alls):
            errs.append("쇼츠 중 하나 이상은 규칙형 제목('Never … in Korea. Here's Why', 'Don't …', 'If You …') "
                        "또는 대결형('A vs B: Which … ?') — WRITING.md 'Korean Rules'")
    hooks = {(s["short"].get("hook") or s["thumb"].get("text", "")).strip().lower()}
    firsts = {first_src(s["short"])}
    titles = {s["short"].get("title", "").strip().lower()}
    for k, ex in enumerate(extra, start=2):
        lab = f"쇼츠{k}"
        if not isinstance(ex, dict):
            errs.append(f"{lab}: 객체가 아니다")
            continue
        errs += short_errs(ex, keys, s, lab)
        h = (ex.get("hook") or "").strip().lower()
        if not h:
            errs.append(f"{lab}: hook 필수 — 첫 1초 두 줄 제목이 다른 쇼츠와 달라야 한다")
        elif h in hooks:
            errs.append(f"{lab}: hook 이 다른 쇼츠와 같다")
        hooks.add(h)
        ls = ex.get("lines") or []
        if ls and ls[0].get("gumi"):
            errs.append(f"{lab}: 첫 줄은 구미가 아니라 장면(scene)·그림(img) — 첫 1초에 멈추게 하는 건 그림이다")
        f = first_src(ex)
        if f in firsts:
            errs.append(f"{lab}: 첫 장면 그림이 다른 쇼츠와 같다 — 첫 프레임을 다르게")
        firsts.add(f)
        tt = ex.get("title", "").strip().lower()
        if tt in titles:
            errs.append(f"{lab}: 제목이 다른 쇼츠와 같다")
        titles.add(tt)
    if len(",".join(s["tags"])) > 480:
        errs.append("태그 합계 480자 이하")
    if is_ex:
        errs += explainer_errs(s)
    return errs


def segments(sc: list[dict]) -> list[int]:
    """장면마다 꼭지 번호(-1 = 첫 카드 전 콜드 오픈·인사). sub 있는 카드가 새 꼭지를 연다."""
    seg, k = [], -1
    for x in sc:
        if x.get("card") and x.get("sub"):
            k += 1
        seg.append(k)
    return seg


def fact_numbers(e: dict | None) -> set[str] | None:
    """catalog 편의 facts·angle·careful 에 적힌 숫자들(쉼표 뺀 꼴). 편이 없으면 None(대조 안 함)."""
    if not e:
        return None
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(fact_text(e))}


def _unit(u: str) -> str:
    u = u.lower()
    for k, v in (("sec", "second"), ("min", "minute"), ("hour", "hour"), ("hr", "hour"), ("day", "day"),
                 ("week", "week"), ("month", "month"), ("year", "year"), ("decade", "decade"), ("centur", "century")):
        if u.startswith(k):
            return v
    return u


def time_pairs(text: str) -> set[tuple[str, str]]:
    """'1–2 minutes' · '9 to 12 seconds' · '4.6 billion years' → {(수, 단위)}."""
    out = set()
    for m in TIME_NUM.finditer(text or ""):
        unit = _unit(m.group(3))
        for n in [m.group(1)] + NUM.findall(m.group(2) or ""):
            out.add((n.replace(",", "").rstrip("."), unit))
    return out


def fact_text(e: dict | None) -> str:
    if not e:
        return ""
    return " ".join([e.get("title_idea", ""), e.get("angle", "")] + list(e.get("facts") or []) + list(e.get("careful") or []))


def time_errs(lab: str, text: str, e: dict | None) -> list[str]:
    """시간 주장(수 + 단위)은 catalog facts 에 같은 꼴로 있어야 한다. 글자로 쓴 수 + 단위('ninety seconds')도 같다."""
    if not e:
        return []
    ft = fact_text(e)
    errs = []
    bad = sorted(f"{n} {u}" for n, u in time_pairs(text) - time_pairs(ft))
    if bad:
        errs.append(f"{lab}: 시간 {bad[:4]} 이 catalog facts 에 없다 — 출처에 있는 시간만(수 + 단위 그대로)")
    low = " ".join(ft.lower().split())
    for m in SPELLED_TIME.finditer(text or ""):
        if " ".join(m.group(0).lower().split()) not in low:
            errs.append(f"{lab}: 글자로 쓴 시간 {m.group(0)!r} — 숫자로 쓰고 catalog facts 에 있는 것만")
    return errs


def src_urls(xs) -> set[str]:
    return {u.rstrip(").,") for x in (xs or []) for u in re.findall(r"https?://\S+", str(x))}


def loose_numbers(text: str, known: set[str], tid: int) -> list[str]:
    """대본 숫자 중 catalog 에 없는 것 — 루틴이 지어낸 통계를 막는다(2026-10-09: 편마다 조사한 사실만)."""
    out = []
    for n in NUM.findall(text or ""):
        v = n.replace(",", "").rstrip(".")
        try:
            small = float(v) <= FREE_NUM_MAX
        except ValueError:
            continue
        if small or v == str(tid) or v in known:
            continue
        out.append(n)
    return out


def explainer_errs(s: dict) -> list[str]:
    """해설편 규칙(27화~): 실사·구미 그림 없음·설화 금지·출처·숫자 대조·꼭지마다 판정·끝 판정과 다음 주 예고·한 꼭지 쇼츠."""
    errs = []
    sc = s["scenes"]
    if s.get("look") != "real":
        errs.append("해설편 look 은 'real'(실사·영화 같은 화면)")
    for i, x in enumerate(sc):
        if x.get("look") not in (None, "real"):
            errs.append(f"장면 {i}: 해설편은 장면 look 도 real 만")
    # 금지 주제 — 제목·설명·태그·말·그림·쇼츠 전부
    shorts = [s["short"]] + [x for x in (s.get("shorts_extra") or []) if isinstance(x, dict)]
    texts = [("제목", s["title"]), ("hook", s["hook"]), ("썸네일", s["thumb"].get("text", "")),
             ("썸네일 그림", s["thumb"].get("img", "")), ("태그", " , ".join(s["tags"]))]
    texts += [(f"장면 {i}", " ".join(str(x.get(f, "")) for f in ("say", "img", "note", "odds", "sub", "card")))
              for i, x in enumerate(sc)]
    for k, sh_ in enumerate(shorts, start=1):
        texts += [(f"쇼츠{k}", " ".join([sh_.get("title", ""), sh_.get("hook", "")]
                                        + [f"{ln.get('say', '')} {ln.get('img', '')}" for ln in sh_.get("lines") or []]))]
    for lab, t in texts:
        m = FOLKLORE.search(t) or BANNED_TOPICS.search(t)
        if m:
            errs.append(f"{lab}: 금지 주제 {m.group(0)!r} — 한국·동아시아 설화·조선·남의 세계관(SCP·백룸)은 쓰지 않는다")
    imgs = [("썸네일 그림", s["thumb"].get("img", ""))] + [(f"장면 {i}", x.get("img", "")) for i, x in enumerate(sc)]
    imgs += [(f"쇼츠{k}", ln.get("img", "")) for k, sh_ in enumerate(shorts, start=1) for ln in sh_.get("lines") or []]
    for lab, t in imgs:
        m = FOX_IMG.search(t or "")
        if m:
            errs.append(f"{lab}: 그림에 {m.group(0)!r} — 구미·여우는 그리지 않는다(목소리만)")
    # 재사용 정지 화면 금지(정책): 본편 장면마다 새 그림 — 같은 프롬프트 두 번이면 같은 그림이 두 번 나온다
    seen: dict = {}
    for i, x in enumerate(sc):
        if x.get("img"):
            if x["img"].strip().lower() in seen:
                errs.append(f"장면 {i}: 그림 프롬프트가 장면 {seen[x['img'].strip().lower()]} 와 같다 — 장면마다 새 그림")
            seen.setdefault(x["img"].strip().lower(), i)
    # 출처: 편마다 직접 조사한 출처(이름 + 링크) 3개 이상 — 설명란에도 그대로 나간다
    srcs = s.get("sources") or []
    if len(srcs) < SOURCES_MIN:
        errs.append(f"출처 {len(srcs)}개 — {SOURCES_MIN}개 이상(NASA·NOAA·USGS·Britannica·논문 등)")
    for j, x in enumerate(srcs):
        if not re.search(r"https?://\S+\.\S+", str(x)):
            errs.append(f"출처 {j}: 링크(https://…)가 없다 — 이름과 주소를 같이")
    ent = entry(s["id"])
    if ent:
        extra_urls = src_urls(srcs) - src_urls(ent.get("sources"))
        if extra_urls:
            errs.append(f"출처 링크 {sorted(extra_urls)[:3]} 가 catalog 출처에 없다 — catalog 편의 sources 에서만 고른다")
    mine = src_urls(srcs)
    # 콜드 오픈: 첫 장면에 가장 센 숫자(첫 10초)
    if sc and not NUM.search(sc[0].get("say", "")):
        errs.append("첫 장면에 숫자가 없다 — 가장 극단적인 사실(숫자)로 연다")
    if not any("gumi" in (x.get("say") or "").lower() for x in sc[:5]):
        errs.append("앞 5장면 안에 구미의 짧은 인사(이름)가 없다")
    # 꼭지: 번호 카드 + 꼭지마다 판정 띠(odds) 하나
    seg = segments(sc)
    cards = [(i, x) for i, x in enumerate(sc) if x.get("card") and x.get("sub")]
    vi = next((i for i, x in cards if str(x["card"]).upper() == VERDICT_CARD), None)
    numbered = [(i, x) for i, x in cards if i != vi]
    if len(numbered) < EX_SEGMENTS_MIN:
        errs.append(f"번호 꼭지 {len(numbered)}개 — {EX_SEGMENTS_MIN}개 이상(카드 + sub)")
    for k, (ci, cx) in enumerate(cards):
        if ci == vi:
            continue
        n_odds = sum(1 for i, x in enumerate(sc) if seg[i] == k and x.get("odds"))
        if n_odds != 1:
            errs.append(f"꼭지 '{cx['sub']}': 판정 띠(odds) {n_odds}개 — 꼭지마다 정확히 하나")
        # 꼭지 출처: 그 꼭지의 숫자가 나온 페이지(쇼츠 설명란에 그 꼭지 것만 나간다)
        cs = cx.get("src") or []
        if not isinstance(cs, list) or not 1 <= len(cs) <= 5:
            errs.append(f"꼭지 '{cx['sub']}': 카드에 src(이 꼭지 출처 1~5개, sources 중에서)가 없다")
        elif src_urls(cs) - mine or len(src_urls(cs)) < len(cs):
            errs.append(f"꼭지 '{cx['sub']}': src 는 대본 sources 에 있는 출처(링크 포함)만")
    known_ = fact_numbers(ent)
    for i, x in enumerate(sc):
        od = x.get("odds")
        if not od:
            continue
        if len(od) > ODDS_MAX or not x.get("say"):
            errs.append(f"장면 {i}: odds 는 말이 있는 장면에 {ODDS_MAX}자 이하")
        lab_, _, val = od.partition(":")
        if lab_.strip().upper() not in ODDS_LABELS or not val.strip():
            errs.append(f"장면 {i}: odds 는 '{' / '.join(ODDS_LABELS)}: …' 꼴 — 살아남는 시간처럼 읽히는 이름 금지")
        if SPELLED.search(od):
            errs.append(f"장면 {i}: odds 에 글자로 쓴 수 {SPELLED.search(od).group(0)!r} — 숫자로(catalog 에 있는 것만)")
        if known_ is not None:
            miss = [n for n in NUM.findall(od) if n.replace(",", "").rstrip(".") not in known_]
            if miss:
                errs.append(f"장면 {i}: odds 숫자 {miss} 가 catalog facts 에 없다(작은 수도)")
    if vi is None:
        errs.append(f"끝 판정 카드 {{'card': '{VERDICT_CARD}', 'sub': \"Gumi's Verdict\"}} 가 없다")
    else:
        if vi < len(sc) * 0.75:
            errs.append("VERDICT 카드는 끝 4분의 1 안에")
        if not any("verdict" in (x.get("say") or "").lower() for x in sc[vi + 1:]):
            errs.append("VERDICT 카드 뒤에 구미의 판정 한 줄('My verdict: …')이 없다")
    if not any(re.search(r"(?i)\bnext\b", x.get("say") or "") for x in sc[-3:]):
        errs.append("마지막 3장면 안에 다음 주 예고('Next Sunday, …')가 없다")
    # 숫자 대조 — catalog 편의 facts 에 없는 큰 수는 지어낸 것으로 본다
    known = known_
    if known is not None:
        loose = loose_numbers(f"{s['title']} {s['thumb'].get('text', '')} {s['hook']}", known, s["id"])
        for i, x in enumerate(sc):
            txt = f"{x.get('say', '')} {x.get('odds', '')} {x.get('note', '')}"
            loose += loose_numbers(txt, known, s["id"])
            errs += time_errs(f"장면 {i}", txt, ent)
        for k, sh_ in enumerate(shorts, start=1):
            txt = " ".join([sh_.get("title", ""), sh_.get("hook", "")] + [ln.get("say", "") for ln in sh_.get("lines") or []])
            loose += loose_numbers(txt, known, s["id"])
            errs += time_errs("쇼츠" if k == 1 else f"쇼츠{k}", txt, ent)
        errs += time_errs("제목·썸네일", f"{s['title']} {s['thumb'].get('text', '')} {s['hook']}", ent)
        if loose:
            errs.append(f"catalog facts 에 없는 숫자 {sorted(set(loose))[:6]} — 조사한 사실의 숫자만 쓴다(없으면 빼거나 말로)")
    # 쇼츠: 본편 한 꼭지만 자른 것 — 쓰는 장면이 모두 한 꼭지 안 + 제목 꼴
    key_seg = {x["key"]: seg[i] for i, x in enumerate(sc) if x.get("key")}
    for k, sh_ in enumerate(shorts, start=1):
        lab = "쇼츠" if k == 1 else f"쇼츠{k}"
        if any(ln.get("gumi") for ln in sh_.get("lines") or []):
            errs.append(f"{lab}: 해설편 쇼츠에 구미 그림 금지 — scene 또는 img")
        used = [ln["scene"] for ln in sh_.get("lines") or [] if ln.get("scene")]
        segs = {key_seg.get(u) for u in used} - {None}
        if len(used) < 2:
            errs.append(f"{lab}: 본편 장면(scene)을 2개 이상 쓴다 — 본편 한 꼭지를 자른 쇼츠")
        elif len(segs) > 1:
            errs.append(f"{lab}: 장면이 여러 꼭지에서 왔다({sorted(segs)}) — 한 꼭지(한 장소·한 구역·한 시점)만")
        if not SINGLE_ITEM.search(sh_.get("title", "")):
            errs.append(f"{lab}: 제목 꼴 — 'How Long Would You Last…' · 'What Happens If…' · 'A vs B' 같은 한 꼭지 질문")
    return errs


def look_errs(s: dict) -> list[str]:
    """10화부터 look 필수. 장면마다 look 을 바꿀 수도 있다(현대 이야기 속 옛 회상 장면 등)."""
    errs = []
    lk = s.get("look")
    if lk is None:
        if s.get("id", 0) >= GLOBAL_FROM:
            errs.append(f"look 필수(10화부터) — {', '.join(LOOKS)} 중 하나. 지금도 도는 괴담·미신은 modern")
    elif lk not in LOOKS:
        errs.append(f"look {lk!r} — {', '.join(LOOKS)} 중 하나")
    for i, x in enumerate(s.get("scenes") or []):
        if x.get("look") is not None and x["look"] not in LOOKS:
            errs.append(f"장면 {i}: look {x['look']!r} — {', '.join(LOOKS)} 중 하나")
    return errs


def first_src(sh: dict) -> str:
    """쇼츠 첫 줄의 그림 출처 — 쇼츠끼리 첫 프레임이 겹치는지 본다."""
    ln = (sh.get("lines") or [{}])[0]
    return str(ln.get("scene") or ln.get("img") or f"gumi:{ln.get('gumi')}")


def short_errs(sh: dict, keys: set, s: dict, label: str = "쇼츠") -> list[str]:
    """쇼츠 한 편 검사(본 쇼츠·추가 쇼츠 공통)."""
    errs = []
    lines = sh.get("lines") or []
    sw = sum(words(ln.get("say", "")) for ln in lines)
    if not SHORT_LINES[0] <= len(lines) <= SHORT_LINES[1]:
        errs.append(f"{label} 줄 {len(lines)} — {SHORT_LINES}")
    if not SHORT_WORDS[0] <= sw <= SHORT_WORDS[1]:
        errs.append(f"{label} {sw}단어 — {SHORT_WORDS}(30~55초)")
    if not sh.get("title") or len(sh["title"]) > 100:
        errs.append(f"{label} 제목 1~100자")
    # 쇼츠 위에 끝까지 떠 있는 두 줄 제목(없으면 썸네일 문구) — 첫 1초에 읽혀야 한다
    hook = sh.get("hook") or s["thumb"].get("text", "")
    if not 2 <= len(hook.split()) <= SHORT_HOOK_WORDS or len(hook) > SHORT_HOOK_CHARS:
        errs.append(f"{label} hook {hook!r} — 2~{SHORT_HOOK_WORDS}단어·{SHORT_HOOK_CHARS}자 이하(화면 위 두 줄)")
    for j, ln in enumerate(lines):
        src = [k for k in ("scene", "gumi", "img") if ln.get(k)]
        if len(src) != 1:
            errs.append(f"{label} {j}: scene·gumi·img 중 하나")
        elif ln.get("scene") and ln["scene"] not in keys:
            errs.append(f"{label} {j}: scene key {ln['scene']!r} 가 본편에 없다")
        if ln.get("gumi") and ln["gumi"] not in GUMI:
            errs.append(f"{label} {j}: gumi 는 {GUMI}")
    return errs


# ── 메타데이터 ──────────────────────────────────────────
def ts(sec: float) -> str:
    sec = int(round(max(0.0, sec)))
    h, rem = divmod(sec, 3600)
    m, s_ = divmod(rem, 60)
    return f"{h}:{m:02d}:{s_:02d}" if h else f"{m:02d}:{s_:02d}"


def chapters(s: dict, starts: list[float]) -> str:
    """유튜브 챕터: 0:00 부터, sub 있는 카드마다. starts = 장면별 시작 초."""
    rows = [("00:00", "Cold open")]
    for x, t in zip(s["scenes"], starts):
        if x.get("card") and x.get("sub"):
            # 'TALE 001' 카드는 본편 시작, 로마 숫자 카드는 장 제목
            if explainer(s):
                c = str(x["card"])
                label = x["sub"] if c.upper() == VERDICT_CARD else (f"{c} {x['sub']}" if c.startswith("#")
                                                                     else f"{c}: {x['sub']}")
            else:
                label = f"Tale: {x['sub']}" if x["card"].startswith("TALE") else f"{x['card']}. {x['sub']}"
            rows.append((ts(t), label))
    # 유튜브 규칙: 첫 챕터 0:00, 각 10초 이상 — 너무 붙은 항목은 뺀다
    out, last = [], -99
    for stamp, label in rows:
        sec = sum(int(p) * 60 ** k for k, p in enumerate(reversed(stamp.split(":"))))
        if sec - last >= 10 or not out:
            out.append(f"{stamp} {label}")
            last = sec
    return "\n".join(out)


def hashtags(tags: list[str], n: int = 3) -> str:
    out = []
    for x in tags:
        h = re.sub(r"[^a-z0-9]", "", x.lower())
        if h and h not in out:
            out.append(h)
    return " ".join(f"#{h}" for h in out[:n])


DESC_MAX_BYTES = 4900        # 유튜브 설명 한도 5,000바이트(—·• 는 3바이트)


def short_sources(s: dict, sh_: dict) -> list[str]:
    """쇼츠가 자른 꼭지의 출처(카드 src). 꼭지를 못 찾으면 대본 출처 앞 3개."""
    sc = s.get("scenes") or []
    seg = segments(sc)
    key_seg = {x["key"]: seg[i] for i, x in enumerate(sc) if x.get("key")}
    used = {key_seg.get(ln.get("scene")) for ln in sh_.get("lines") or [] if ln.get("scene")} - {None}
    cards = [x for x in sc if x.get("card") and x.get("sub")]
    if len(used) == 1:
        k = used.pop()
        if 0 <= k < len(cards) and cards[k].get("src"):
            return list(cards[k]["src"])
    return list(s.get("sources") or [])[:3]


def ex_meta(s: dict, starts: list[float] | None = None, short_of: str | None = None,
            more: list[tuple[str, str]] | None = None) -> dict:
    """해설편 메타: 출처를 설명란에 그대로(정책: 편마다 조사한 사실) · AI 고지 · 설화 태그 없음."""
    tags = list(dict.fromkeys(s["tags"] + ["nine tails tales", "explained"]))
    src = "\n".join(f"• {x}" for x in s["sources"])
    chap = chapters(s, starts) if starts else ""
    more_txt = ("Watch next:\n" + "\n".join(f"▶ {t} — {u}" for t, u in more[:4]) + "\n\n") if more else ""
    # 출처·AI 고지는 잘리지 않게 앞쪽에. 유튜브 설명은 5,000바이트까지 — 넘치면 '다음 영상'·소개·챕터 순으로 뺀다
    parts = [f"{s['hook']}\n\n", f"{chap}\n\n" if chap else "", f"Sources:\n{src}\n\n", f"{EX_AI_NOTE}\n\n",
             f"{EX_ABOUT}\n\n", more_txt, hashtags(s["tags"])]
    for drop in (5, 4, 1):
        if len("".join(parts).encode("utf-8")) <= DESC_MAX_BYTES:
            break
        parts[drop] = ""
    desc = "".join(parts)
    out = {"title": s["title"][:100], "description": desc, "tags": tags}

    def sd(sh_: dict) -> str:
        own = short_sources(s, sh_)
        return (f"{sh_.get('desc') or s['hook']}\n\n"
                + (f"Full video: {short_of}\n\n" if short_of else "Full video on the channel.\n\n")
                + "Sources:\n" + "\n".join(f"• {x}" for x in own)
                + f"\n\n{EX_AI_NOTE}\n\n#shorts " + hashtags(s["tags"], 2))
    out["short"] = {"title": s["short"]["title"][:100], "description": sd(s["short"]), "tags": tags[:15]}
    out["shorts_extra"] = [{"title": ex["title"][:100], "description": sd(ex), "tags": tags[:15]}
                           for ex in (s.get("shorts_extra") or []) if isinstance(ex, dict) and ex.get("title")]
    return out


def meta(s: dict, starts: list[float] | None = None, short_of: str | None = None,
         more: list[tuple[str, str]] | None = None) -> dict:
    if explainer(s):
        return ex_meta(s, starts, short_of, more)
    tags = list(dict.fromkeys(s["tags"] + ["nine tails tales", "korean folklore", "korean mythology"]))
    src = "\n".join(f"• {x}" for x in s["sources"])
    chap = chapters(s, starts) if starts else ""
    # 앞서 올린 편 링크 — 새 편이 옛 편을, 옛 편의 검색 유입이 새 편을 끌어 준다(역주행)
    more_txt = ("More tales from Gumi:\n" + "\n".join(f"▶ {t} — {u}" for t, u in more[:4]) + "\n\n") if more else ""
    desc = (f"{s['hook']}\n\n"
            f"Tale {s['id']:03d} of 1,000 — told by Gumi, a 1,000-year-old gumiho.\n\n"
            + (f"{chap}\n\n" if chap else "")
            + more_txt
            + f"Sources & further reading:\n{src}\n\n{ABOUT}\n\n{AI_NOTE}\n\n"
            + "#gumiho #koreanfolklore #koreanmythology")
    out = {"title": s["title"][:100], "description": desc[:4900], "tags": tags}
    sdesc = (f"{s['hook']}\n\n"
             + (f"Full tale: {short_of}\n\n" if short_of else "Full tale on the channel.\n\n")
             + f"{AI_NOTE}\n\n#shorts #gumiho #koreanfolklore #koreanlegend")
    out["short"] = {"title": s["short"]["title"][:100], "description": sdesc, "tags": tags[:15]}
    out["shorts_extra"] = [{"title": ex["title"][:100], "description": sdesc, "tags": tags[:15]}
                           for ex in (s.get("shorts_extra") or []) if isinstance(ex, dict) and ex.get("title")]
    return out


# ── 다음 편 ──────────────────────────────────────────────
def sprint() -> dict:
    """1주 형식 실험(2026-10-02 사용자: '매일 새로운 주제·새로운 방식, 쇼츠랑 롱폼 1주일').
    catalog.sprint = {"from", "to", "first_id", "resume_from"} — from~to 하루 한 편(first_id 부터), 그 뒤 resume_from(수)부터 다시 주 1편."""
    return load(CATALOG).get("sprint") or {}


def sprint_day(tale_id: int):
    """스프린트 편이면 그 편의 날짜(date), 아니면 None. 스프린트 편은 그날 15:00 UTC 공개 · 추가 쇼츠 없음."""
    import datetime as dt
    sp = sprint()
    if not sp:
        return None
    f, t = dt.date.fromisoformat(sp["from"]), dt.date.fromisoformat(sp["to"])
    k = tale_id - sp["first_id"]
    return f + dt.timedelta(days=k) if 0 <= k <= (t - f).days else None


def weekly() -> dict:
    """2026-10-10~ 편성(catalog.weekly): 편마다 date(일요일) · publish_utc 14:00 · window_days(그 주 며칠 전부터 쓸 수 있나)."""
    return load(CATALOG).get("weekly") or {}


def publish_at(e: dict) -> str:
    """편의 예약 공개 시각(UTC ISO) — 일요일 14:00 UTC(미 동부 10:00)."""
    return f"{e['date']}T{weekly().get('publish_utc', '14:00')}:00Z"


def weekly_entry(d) -> dict | None:
    """날짜 d 에 쓸 편 — date(공개 일요일) 기준 window_days 일 전 ~ 당일. 루틴은 토요일에 돈다(공개 하루 전).
    retired(설화) 편은 절대 고르지 않는다. 없으면 None(그 주는 쉰다 — 10/10~10/17 처럼)."""
    import datetime as dt
    win = int(weekly().get("window_days", 6))
    for e in load(CATALOG)["tales"]:
        if e.get("retired") or not e.get("date"):
            continue
        p = dt.date.fromisoformat(e["date"])
        if p - dt.timedelta(days=win) <= d <= p:
            return e
    return None


def assigned_id(date: str) -> int | None:
    """날짜 → 편 번호. ★2026-10-10 부터는 weekly_entry(일요일 편, 없으면 None).
    그 전(기록용): catalog.start(수요일)부터 7일마다 +1 · 스프린트(10/4~10/9) 하루 한 편."""
    import datetime as dt
    d = dt.date.fromisoformat(date)
    wk = weekly()
    if wk and d >= dt.date.fromisoformat(wk["from"]):
        e = weekly_entry(d)
        return e["id"] if e else None
    sp = sprint()
    if sp:
        f, t = dt.date.fromisoformat(sp["from"]), dt.date.fromisoformat(sp["to"])
        last = sp["first_id"] + (t - f).days
        if f <= d <= t:
            return sp["first_id"] + (d - f).days
        if d > t:
            r = dt.date.fromisoformat(sp["resume_from"])
            return last + 1 + (d - r).days // 7 if d >= r else last
    start = dt.date.fromisoformat(load(CATALOG)["start"])
    return 2 + max(0, (d - start).days // 7)


def entry(tale_id: int | None) -> dict | None:
    return next((e for e in load(CATALOG)["tales"] if e["id"] == tale_id), None)


def retired(tale_id: int) -> bool:
    """편성에서 뺀 편(2026-10-09 설화 금지) — 렌더·업로드 전에 막는다."""
    e = entry(tale_id)
    return bool(e and e.get("retired"))


def written_ids() -> set[int]:
    ids = set()
    for d in (SCRIPTS, ROUTINE_DIR):
        for p in glob.glob(os.path.join(d, "*.json")):
            m = re.match(r"(\d{3})_", os.path.basename(p))
            if m:
                ids.add(int(m.group(1)))
    return ids


def next_entry(date: str | None = None) -> dict | None:
    """date 가 있으면 그 주의 편(결정론적). 없으면 catalog 에서 대본이 없는 가장 앞 번호."""
    if date:
        return entry(assigned_id(date))
    done = written_ids()
    return next((e for e in load(CATALOG)["tales"]
                 if e["id"] not in done and not e.get("done") and not e.get("retired")), None)


def teaser_for(e: dict) -> dict:
    """끝의 다음 주 예고용 — 다음 편(없으면 backlog 첫 줄). 루틴이 지어내지 않게 next 가 같이 준다."""
    cat = load(CATALOG)
    later = sorted((x for x in cat["tales"] if not x.get("retired") and x.get("date", "") > e.get("date", "")),
                   key=lambda x: x["date"])
    if later:
        return {"title": later[0]["title_idea"], "angle": later[0].get("angle", ""), "date": later[0]["date"],
                "line": f"Next Sunday: {later[0]['title_idea']}"}
    # 다음 편이 아직 편성되지 않았다 — backlog 제목을 약속하면 안 나올 수도 있다(리뷰 10/9)
    return {"title": "", "angle": "", "date": None, "line": "A new one next Sunday."}


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        bad = 0
        for p in sys.argv[2:]:
            s = load(p)
            errs = check(s, p)
            if retired(s.get("id", 0)):          # 워크플로 '대본 검사' 단계 — 설화 편은 렌더·업로드까지 가지 않는다
                errs.append(f"{s['id']}화는 retired(2026-10-09 설화 금지) — 렌더·업로드하지 않는다")
            st = stats(s)
            print(f"{'✅' if not errs else '❌'} {os.path.basename(p)} · 장면 {st['scenes']} · {st['words']}단어"
                  f" · 약 {st['est_min']}분 · 그림 {st['images']} · 챕터 {st['chapters']}")
            for e in errs:
                print(f"   ✗ {e}")
            bad += bool(errs)
        return 1 if bad else 0
    if len(sys.argv) >= 2 and sys.argv[1] == "next":
        date = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[2] == "--date" else None
        e = next_entry(date)
        if not e or e.get("retired"):
            print(json.dumps({"none": True, "why": "nothing to write for this date (no episode this week, or catalog "
                              "empty) — write nothing and stop"}, ensure_ascii=False))
            return 0
        f = f"{e['id']:03d}_{e['slug']}.json"
        e = dict(e, file=f, already_written=os.path.exists(os.path.join(ROUTINE_DIR, f)))
        if e.get("date"):
            ex_ = os.path.join(SCRIPTS, f)
            e.update(publish_at=publish_at(e), teaser=teaser_for(e),
                     exemplar_ready=os.path.exists(ex_))   # 사람이 쓴 그 편 대본이 scripts/ 에 있으면 그대로 옮긴다
        print(json.dumps(e, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
