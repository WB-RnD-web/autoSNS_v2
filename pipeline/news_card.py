#!/usr/bin/env python3
"""소식 쇼츠 '10초 한 장' (2026-10-04) — 정치·주식·AI 루틴 스토리보드를 한 화면 카드로 바꾼다.

왜: 9/26~10/3 쇼츠 45편 점검(https://claude.ai/artifact/YWuak69HPF1z3azJhSXors) — 8~10초 한 장 표는 2천~1만 회,
  40초대 소식 낭독(AI 35 · 미장 99 · 국장 88 · 정치 637회 중앙값)은 바닥이었다. 사용자: "끄지 말고 보여주는 형태
  자체를 획기적으로" → 샘플 3장(찬반 한 장 · 내 돈 성적표 · 오늘 해 둘 3가지)을 보고 "세 가지 다 바로 전환".

  정치 → 찬반(debate): 핵심 숫자 + 양쪽 말을 같은 크기로 + ⭕/❌ 댓글로 한 표. 편들지 않는다(양쪽 말 그대로).
  주식 → 성적표(board): 오르면 빨강 ▲ · 내리면 파랑 ▼ · 한 줄 정리 · '투자 권유 아님'.
  AI   → 체크리스트(check): 오늘 해 둘 것 + 가족에게 공유.
  모양이 안 맞는 대본(양쪽 말이 없다 등)은 요점(bullets) 카드로 — 어떤 대본이 와도 한 장은 나온다.

★루틴은 그대로 둔다(대본 모양 hook·stat·trend·keypoint·statement 에서 뽑는다). 새 사실·숫자를 만들지 않는다.
끄기: 레포 변수 NEWS_CARD=0 (예전 40초 형식으로).

    python pipeline/news_card.py <storyboard.json>      # 카드 스펙 미리보기
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

WEEKDAY = "월화수목금토일"
MIN_TOTAL = 11.0                 # 목소리 한 줄(5~8초) 뒤에도 화면을 붙잡아 둔다 — 읽고·찾고·댓글 달 시간
UNITS = ("시간", "년", "명", "원", "%", "배", "개", "건", "곳", "조", "억", "만", "위", "점", "일", "주", "달", "분", "초", "회", "채", "대")
CHECK_LABEL = re.compile(r"해\s*볼|해\s*둘|할\s*일|체크|방법|지키|팁|가지|하세요|챙길")
SIDE_SPLIT = re.compile(r"\s*[—–-]{1,2}\s*")
# 양쪽 말로 볼 수 있는 이름 — '배달 수수료 — 내 주문 가격' 같은 설명 줄을 찬반으로 오해하지 않게
SIDE_NAME = re.compile(r"여당|야당|여권|야권|정부|대통령실|청와대|국회|찬성|반대|與|野|민주|국민의힘|진보|보수|노동계|경영계|"
                       r"노조|사측|시민단체|업계|의료계|학계|검찰|법원|여|야")
SIDE_LABEL = re.compile(r"반응|입장|찬반|여야|공방|엇갈|대립|맞서|vs|VS")
FIGURE = re.compile(r"^[▲▼+\-−]?\s*\d[\d,.]*\s*(%|%p|원|달러|명|만|억|조|배|개|건|곳|bp|포인트|p|위|점)?\s*[↑↓]?$")


def kind(sb: dict) -> str | None:
    t = str(sb.get("topic") or "").lower()
    if t.startswith("politics"):
        return "politics"
    if t.startswith("stock"):
        return "stock"
    if t.startswith("ai"):
        return "ai"
    return None


def use(sb: dict) -> bool:
    if os.environ.get("NEWS_CARD", "1").strip().lower() in ("0", "false", "off"):
        return False
    return kind(sb) is not None and bool(sb.get("scenes"))


# ── 글자 손질 ───────────────────────────────────────────
def plain(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def keep_b(s) -> str:
    """<b> 만 남기고 나머지 태그는 지운다(렌더가 <b> 를 금색으로)."""
    s = re.sub(r"<(?!/?b>)[^>]+>", "", str(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def unquote(s: str) -> str:
    return plain(s).strip(" \"'“”‘’「」")


def fmt_num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return plain(v)
    if f.is_integer():
        return f"{int(f):,}"
    return f"{f:,.2f}".rstrip("0").rstrip(".")


def unit_after(num: str, *texts) -> str:
    """숫자 바로 뒤 단위를 같은 장면 글에서 찾는다(78 → '78년 만에' → 년). 없으면 ''."""
    n = num.replace(",", ",?")
    for t in texts:
        m = re.search(rf"{n}\s*({'|'.join(map(re.escape, UNITS))})", plain(t))
        if m:
            return m.group(1)
    return ""


def split_title(t: str) -> list[str]:
    """제목을 한 줄(≤11자) 또는 고른 두 줄로."""
    t = plain(t)
    if len(t.replace(" ", "")) <= 11 or " " not in t:
        return [t]
    words = t.split(" ")
    best, cut = None, 1
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        d = abs(len(a) - len(b))
        if best is None or d < best:
            best, cut = d, i
    return [" ".join(words[:cut]), " ".join(words[cut:])]


# ── 대본에서 뽑기 ──────────────────────────────────────
def _scenes(sb, *types):
    return [sc for sc in sb.get("scenes") or [] if isinstance(sc, dict) and sc.get("type") in types]


def big_stat(sb: dict) -> dict | None:
    for sc in _scenes(sb, "stat", "trend", "gauge"):
        if sc.get("to") is None:
            continue
        num = fmt_num(sc.get("to")).lstrip("-")
        unit = (sc.get("suffix") or "") if sc.get("type") != "trend" else (sc.get("suffix") or "%")
        unit = unit or unit_after(num, sc.get("sub"), sc.get("narration"), sc.get("label"))
        d = "flat"
        if sc.get("type") == "trend":
            d = "down" if sc.get("dir") == "down" or str(sc.get("to")).startswith("-") else "up"
        return {"label": plain(sc.get("label")), "num": f"{plain(sc.get('prefix'))}{num}", "unit": plain(unit),
                "sub": keep_b(sc.get("sub")), "dir": d}
    return None


def sides(sb: dict) -> list[dict]:
    """'여당 — "…"' 꼴 요점 두 개 → 양쪽 말. 왼쪽 이름이 짧고(≤6자) 서로 다르며, 요점 제목이 '반응·입장·찬반…'이거나
    양쪽 이름이 둘 다 진영·주체(여당·야당·정부·노조…)여야 한다 — 설명 줄('배달 수수료 — 내 주문 가격')은 찬반이 아니다."""
    for sc in _scenes(sb, "keypoint"):
        out = []
        for p in sc.get("points") or []:
            parts = SIDE_SPLIT.split(plain(p), maxsplit=1)
            if len(parts) == 2 and 1 <= len(parts[0]) <= 6 and parts[1]:
                out.append({"h": parts[0], "q": unquote(parts[1])})
        if len(out) >= 2 and out[0]["h"] != out[1]["h"] and (
                SIDE_LABEL.search(plain(sc.get("label"))) or all(SIDE_NAME.search(o["h"]) for o in out[:2])):
            return out[:2]
    return []


def board_rows(sb: dict) -> list[dict]:
    rows = []
    for sc in _scenes(sb, "trend", "stat"):
        if sc.get("to") is None:
            continue
        num = fmt_num(sc.get("to"))
        suf = (sc.get("suffix") or "%") if sc.get("type") == "trend" else (sc.get("suffix") or "")
        suf = suf or unit_after(num, sc.get("sub"), sc.get("narration"), sc.get("label"))
        try:
            to = float(sc.get("to"))
        except (TypeError, ValueError):
            to = 0.0
        if sc.get("type") == "trend":
            down = sc.get("dir") == "down" or to < 0
            d = "down" if down else ("up" if to > 0 else "flat")
            v = f"{num.lstrip('-')}{suf}"                  # ▲▼ 는 렌더가 도형으로 그린다(dir)
        else:
            d, v = "flat", f"{plain(sc.get('prefix'))}{num}{suf}"
        rows.append({"k": plain(sc.get("label")), "s": plain(sc.get("sub"))[:22], "v": v, "dir": d})
    for sc in _scenes(sb, "keypoint"):
        for p in sc.get("points") or []:
            m = re.search(r"<b>(.*?)</b>", str(p))
            if not m or not FIGURE.match(plain(m.group(1))):
                continue                                   # 숫자만 표에 싣는다('인상 기대' 같은 말은 빼고)
            v = plain(m.group(1))
            k = plain(str(p)[:m.start()]).strip(" ,·—-")
            rest = plain(str(p)[m.end():]).strip(" ,·—-")
            if not k:
                k, rest = rest, ""
            d = "up" if "↑" in v or v.startswith(("▲", "+")) else "down" if "↓" in v or v.startswith(("▼", "-", "−")) else "flat"
            v = v.replace("↑", "").replace("↓", "").lstrip("▲▼+-− ").strip()
            if k:
                rows.append({"k": k[:14], "s": rest[:22], "v": v, "dir": d})
    seen, out = set(), []
    for r in rows:
        if r["k"] and r["k"] not in seen:
            seen.add(r["k"])
            out.append(r)
    return out[:4]


def checklist(sb: dict) -> tuple[str, list[str]]:
    for sc in _scenes(sb, "keypoint"):
        if CHECK_LABEL.search(plain(sc.get("label"))) and len(sc.get("points") or []) >= 2:
            return plain(sc.get("label")), [plain(p) for p in sc["points"][:3]]
    return "", []


def bullets(sb: dict) -> tuple[str, list[str]]:
    for sc in _scenes(sb, "keypoint"):
        if sc.get("points"):
            return plain(sc.get("label")), [keep_b(p) for p in sc["points"][:3]]
    return "", []


def statements(sb: dict) -> list[str]:
    return [plain(sc.get("text")) for sc in _scenes(sb, "statement") if sc.get("text")]


def hook_title(sb: dict) -> str:
    if sb.get("hook_title"):
        return plain(sb["hook_title"])
    h = _scenes(sb, "hook")
    return plain(" ".join(h[0].get("lines") or [])) if h else plain(sb.get("headline"))


def first_narration(sb: dict) -> str:
    for sc in sb.get("scenes") or []:
        if isinstance(sc, dict) and sc.get("narration"):
            return plain(sc["narration"])
    return hook_title(sb)


# ── 카드 ────────────────────────────────────────────────
def build_scene(sb: dict) -> dict:
    k = kind(sb)
    try:
        d = dt.date.fromisoformat(str(sb.get("date"))[:10])
        day = f"{d.month}월 {d.day}일 {WEEKDAY[d.weekday()]}요일"
    except ValueError:
        day = ""
    t = str(sb.get("topic") or "").lower()
    st = statements(sb)
    sc = {"type": "news", "brand": "", "foot": "※ 보도 내용을 옮겼어요 · 출처는 설명란", "narration": first_narration(sb)}
    if k == "politics":
        sd = sides(sb)
        q = next((x for x in reversed(st) if x.endswith("?")), "여러분 생각은?")
        sc.update(pill=f"{day} · 오늘의 쟁점", title=split_title(hook_title(sb)), title2=q, big=big_stat(sb),
                  ox=["맞다", "아니다"], ask="댓글로 한 표 남겨 주세요", brand="왕별이 · 오늘의 쟁점")
        if sd:
            sc.update(layout="debate", sides=sd, foot="※ 양쪽 말을 그대로 옮겼어요 · 출처는 설명란")
        else:
            lab, pts = bullets(sb)
            sc.update(layout="bullets", label=lab, items=pts)
    elif k == "stock":
        us = t.startswith("stock_us")
        rows = board_rows(sb)
        sc.update(pill=f"{day} · {'간밤 미국장' if us else '오늘 국장'}",
                  title=[f"{'간밤 미국장' if us else '오늘 국장'} 성적표"], title2=hook_title(sb),
                  verdict=st[0] if st else "", brand="왕별이 · 내 돈 성적표",
                  foot="※ 보도 수치를 옮겼어요 · 투자 권유가 아닙니다")
        if len(rows) >= 2:
            sc.update(layout="board", rows=rows)
        else:
            lab, pts = bullets(sb)
            sc.update(layout="bullets", label=lab, items=pts, big=big_stat(sb))
    else:
        lab, items = checklist(sb)
        sc.update(pill=f"{day} · 오늘의 AI", title=split_title(hook_title(sb)), big=big_stat(sb),
                  share="부모님·자녀에게 공유해 주세요", brand="왕별이 · 오늘의 AI")
        if items:
            sc.update(layout="check", title2=lab, items=items)
        else:
            lab, pts = bullets(sb)
            sc.update(layout="bullets", title2=st[0] if st else lab, label=lab, items=pts)
    return sc


def build_spec(sb: dict) -> dict:
    return {"topic": sb.get("topic", ""), "date": sb.get("date"), "accent": sb.get("accent") or "#C9A227",
            "_min_total": MIN_TOTAL, "scenes": [build_scene(sb)]}


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        _sb = json.load(f)
    print(json.dumps({"use": use(_sb), "spec": build_spec(_sb)}, ensure_ascii=False, indent=1))
