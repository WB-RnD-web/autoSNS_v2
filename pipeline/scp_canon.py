#!/usr/bin/env python3
"""원작(canon) SCP 회차 — 번호 배정 + 원문 팩 (2026-09-27).

왜 이게 필요한가 (2026-09-27 확인):
  structure_rules 는 '3일에 한 번 원작 회차'를 날짜로 정해 두었지만 원작 회차가 한 번도 안 나왔다.
  루틴이 지시를 무시한 게 아니었다 — 스펙의 origin_note 에 이유가 적혀 있었다:
    "scp-wiki.wikidot.com·scpko.wiki·namu.wiki 세 경로 모두 EGRESS_BLOCKED(조직 네트워크 정책상 접근 차단)"
  루틴이 도는 클라우드 환경에서 위키 접속이 막혀 있어 원문을 못 읽었고, 프롬프트대로 오리지널로 내려갔다.
  → 원문을 ★레포에 미리 받아 둔다(scp/canon_pack/). 루틴은 인터넷 없이 `git show origin/main:…` 로 읽는다.
  → 어느 날 어느 번호인지도 ★코드가 정한다(assign). 루틴 판단에 맡기지 않는다.

배정 규칙:
  원작 회차 = 월요일(KST) 회차. SCP 루틴은 월·목 09:00 KST 에 돈다 → 주 1편 원작 · 1편 오리지널.
  몇 번째 원작 회차인지(= QUEUE 의 몇 번째 번호인지) = START(첫 월요일)부터 센 월요일 수.
  큐를 다 돌면 처음으로 돌아가지 않고 오리지널로 둔다(같은 원작 반복 방지) — 큐를 늘리면 이어진다.

라이선스: SCP 위키 본문은 CC BY-SA 3.0. 원작 회차 설명란에 ★저작자·원문 URL·라이선스를 넣는다
  (팩 파일 머리의 cite 줄 그대로). 원작 이미지는 쓰지 않는다(이미지별 라이선스가 다르다) — 그림은 우리가 새로 그린다.

  python scp_canon.py assign --date 2026-09-28        # 이 날짜 회차 배정(JSON)
  python scp_canon.py fetch 682 096 …                 # 원문 팩 받기(네트워크 되는 곳에서)
  python scp_canon.py list                            # 앞으로의 원작 일정
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "scp", "canon_pack")
START = dt.date(2026, 9, 28)          # 첫 원작 회차(월)

# 1차 16편(국내 인지도 순) + 2차 36편(위키 평점 순, 2026-09-27 실측) = 52편 ≈ 1년치 월요일.
# 뺀 것: 고어·자해·성적 주제가 핵심(610·231·008·058·882·1048·012·166·191·3199), 종교(343),
#        글이 아닌 형식(2521 기호 · 3125 특수 형식 · 6000 허브), 원문이 너무 짧음(529·005·017).
QUEUE = ["682", "096", "173", "049", "106", "3008", "087", "055",
         "035", "939", "914", "999", "2317", "1471", "426", "294",
         "5000", "093", "3000", "2006", "1000", "3001", "002", "076",
         "2000", "1762", "079", "701", "3930", "2718", "4000", "507",
         "1733", "140", "354", "1440", "184", "105", "015", "131",
         "3812", "066", "738", "239", "513", "303", "097", "1609",
         "053", "033", "447", "8000"]
NICK = {  # 한국 팬덤에서 통하는 통칭 — 제목 앞머리에 쓴다(원작은 번호·통칭이 곧 검색어)
    "682": "불사의 파충류", "096": "수줍은 자", "173": "조각상", "049": "역병 의사",
    "106": "늙은 노인", "3008": "무한한 이케아", "087": "계단", "055": "반-밈",
    "035": "빙의 가면", "939": "여러 목소리", "914": "태엽장치", "999": "간지럼 괴물",
    "2317": "다른 세계로 가는 문", "1471": "MalO", "426": "나는 토스터", "294": "커피 자판기",
    # 2차 — 3000번대 이후는 한국 지부 번역 제목(scpko.wikidot.com 목록), 나머지는 흔히 쓰는 통칭
    "5000": "왜?", "093": "홍해의 물체", "3000": "아난타세샤", "2006": "너무 무시무시한",
    "1000": "빅풋", "3001": "적색 현실", "002": "살아있는 방", "076": "아벨",
    "2000": "데우스 엑스 마키나", "1762": "용들이 간 곳", "079": "구식 AI", "701": "교수대 왕의 비극",
    "3930": "패턴 스크리머", "2718": "이후에 일어날 일", "4000": "금기", "507": "마지못한 차원 여행자",
    "1733": "시즌 개막전", "140": "다에바 연대기", "354": "붉은 웅덩이", "1440": "어디에서도 오지 않은 노인",
    "184": "건축가", "105": "아이리스", "015": "배관의 악몽", "131": "눈알 꼬마들",
    "3812": "내 뒤의 목소리", "066": "에릭의 장난감", "738": "악마의 거래", "239": "꼬마 마녀",
    "513": "소 방울", "303": "문지기", "097": "낡은 유원지", "1609": "의자의 잔해",
    "053": "어린 소녀", "033": "사라진 숫자", "447": "녹색 점액 공",
}


def is_canon_day(d: dt.date) -> bool:
    return d.weekday() == 0 and d >= START


def assign(d: dt.date) -> dict:
    """이 날짜 회차가 원작인지, 원작이면 어느 번호·어느 원문 파일인지."""
    if not is_canon_day(d):
        return {"date": d.isoformat(), "origin": "original"}
    idx = (d - START).days // 7
    if idx >= len(QUEUE):
        return {"date": d.isoformat(), "origin": "original", "note": "원작 큐 소진 — QUEUE 를 늘릴 것"}
    num = QUEUE[idx]
    path = f"scp/canon_pack/scp-{num}.md"
    meta = read_meta(os.path.join(ROOT, path))
    return {"date": d.isoformat(), "origin": "canon", "scp_number": f"SCP-{num}",
            "nickname": NICK.get(num, "") or "(없음 — 원문을 읽고 3~7자 한국어 통칭을 직접 짓는다)",
            "source_path": path,
            "source_url": meta.get("url", f"https://scp-wiki.wikidot.com/scp-{num}"),
            "cite": meta.get("cite", ""), "queue_index": idx}


def read_meta(path: str) -> dict:
    meta = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.startswith("<!--"):
                    if line.strip():
                        break
                    continue
                m = re.match(r"<!--\s*(\w+):\s*(.*?)\s*-->", line)
                if m:
                    meta[m.group(1)] = m.group(2)
    except OSError:
        pass
    return meta


def gate(spec: dict) -> list[str]:
    """업로드 전 강제 검사. 원작 차례인데 오리지널이거나 번호가 다르면 문제 목록을 돌려준다.

    예전엔 경고만 찍고 올렸다 → 10편 넘게 조용히 오리지널이 나갔다. 이제 원문이 레포에 있으니
    '못 읽었다'는 사유가 없다 → 빈 목록이 아니면 run_scp 가 업로드하지 않는다(끄기: SCP_CANON_GATE=0).
    """
    try:
        d = dt.date.fromisoformat(str(spec.get("date") or "")[:10])
    except ValueError:
        return []
    want = assign(d)
    if want["origin"] != "canon":
        return []
    out = []
    if str(spec.get("origin") or "").strip() != "canon":
        out.append(f"{d} 는 원작 회차({want['scp_number']} {want['nickname']})인데 origin="
                   f"{spec.get('origin')!r} 이다 — 원문은 레포 {want['source_path']} 에 있다")
    got = re.sub(r"[^0-9]", "", str(spec.get("scp_number") or "")).lstrip("0")
    if got != want["scp_number"].split("-")[1].lstrip("0"):
        out.append(f"원작 번호가 배정과 다르다: {spec.get('scp_number')!r} ≠ {want['scp_number']}")
    return out


def cite_for(spec: dict) -> str:
    """원작 회차의 CC BY-SA 저작자 표기 한 줄(팩 파일 머리의 cite)."""
    num = re.sub(r"[^0-9]", "", str(spec.get("scp_number") or ""))
    for cand in (num, num.zfill(3)):
        meta = read_meta(os.path.join(PACK, f"scp-{cand}.md"))
        if meta.get("cite"):
            return meta["cite"]
    return ""


# ── 원문 받기(네트워크 되는 곳에서만 — 루틴 환경은 막혀 있다) ──────────
def _page_text(raw: str) -> str:
    i = raw.find('id="page-content"')
    j = raw.find('class="licensebox"', i)
    k = raw.find('id="page-info-break"', i)
    end = min(x for x in (j, k, len(raw)) if x > i) if i >= 0 else len(raw)
    body = raw[i:end]
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", body)
    body = re.sub(r'(?is)<div class="collapsible-block-folded".*?</div>', "", body)   # '+ 펼치기' 링크
    body = re.sub(r"(?is)<div class=\"(?:scp-image-block|image-container)[^\"]*\".*?</div>\s*</div>", "", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    body = re.sub(r"(?i)</(p|div|h\d|li|tr|blockquote)>", "\n", body)
    body = re.sub(r"(?i)<li[^>]*>", "- ", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body).replace("\xa0", " ")
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n\n", body)
    lines = [l.strip() for l in body.splitlines()]
    # 위키 장식 줄: 평점 모듈 · 이전/다음 개체 내비 · 잘린 태그 조각
    lines = [l for l in lines
             if not re.match(r"^(rating:|«.*»$|<\w*$|id=\"page-content\">$)", l)]
    return "\n".join(lines).replace('id="page-content">', "").strip()


def _cite(raw: str) -> str:
    """'Cite this page as: "SCP-096" by Dr Dan, from the SCP Wiki. Source: …' — 태그를 먼저 벗긴다
    (CC BY-SA 가 <a> 안에 있어 원문 HTML 에서는 한 줄로 안 이어진다)."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    t = re.sub(r"\s+", " ", t)
    m = re.search(r"Cite this page as:\s*(.{0,500}?)\s*Licensed under CC BY-SA", t)
    if not m:
        return ""
    c = re.sub(r'"\s+(.*?)\s+"', r'"\1"', m.group(1))       # '" SCP-096 "' → '"SCP-096"'
    c = re.sub(r"\s+([.,])", r"\1", c).strip()
    return f"{c} Licensed under CC BY-SA 3.0."


def fetch(nums: list[str]) -> int:
    import urllib.request
    os.makedirs(PACK, exist_ok=True)
    bad = 0
    for n in nums:
        url = f"https://scp-wiki.wikidot.com/scp-{n}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ SCP-{n}: {e}")
            bad += 1
            continue
        text, cite = _page_text(raw), _cite(raw)
        if len(text) < 800 or not cite:
            print(f"  ✗ SCP-{n}: 본문 {len(text)}자 · cite {'있음' if cite else '없음'} — 확인 필요")
            bad += 1
        out = os.path.join(PACK, f"scp-{n}.md")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"<!-- number: SCP-{n} -->\n<!-- url: {url} -->\n<!-- cite: {cite} -->\n"
                    f"<!-- fetched: {dt.date.today().isoformat()} -->\n"
                    "<!-- license: CC BY-SA 3.0 — 원작 회차 설명란에 cite 줄을 그대로 넣는다. "
                    "원작 이미지는 쓰지 않는다. -->\n\n")
            f.write(text + "\n")
        print(f"  ✓ SCP-{n}: {len(text):,}자 · {cite[:80]}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="원작 SCP 회차 배정·원문 팩")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assign")
    a.add_argument("--date", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("nums", nargs="*")
    sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "assign":
        print(json.dumps(assign(dt.date.fromisoformat(args.date)), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "fetch":
        return fetch(args.nums or QUEUE)
    d = START
    for _ in range(len(QUEUE)):
        a = assign(d)
        print(f"{d} (월)  {a.get('scp_number', '-'):<9} {a.get('nickname', '')}  "
              f"{'✓' if os.path.exists(os.path.join(ROOT, a.get('source_path', '-'))) else '✗ 팩 없음'}")
        d += dt.timedelta(days=7)
    return 0


if __name__ == "__main__":
    sys.exit(main())
