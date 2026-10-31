#!/usr/bin/env python3
"""Nine Tails 3D 실화·what-if 쇼츠 오프라인 테스트 — 카탈로그 검사 · 편성표 · ledger · 업로드 가드 · mock 렌더.

    python gumiho/tales/test_story.py
네트워크·Spark·자격증명 없이 돈다. mock 렌더는 ffmpeg 가 있을 때만(없으면 건너뛴다고 알린다).
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import story as ST  # noqa: E402

FAIL = 0
UTC = dt.timezone.utc


def ck(name, cond, detail=""):
    global FAIL
    print(f"  {'✓' if cond else '✗'} {name}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAIL += 1


def kst(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=ST.KST)


cat = ST.load()
eps = ST.episodes(cat)

print("── 1. 카탈로그 ──")
errs = ST.check(cat)
ck("카탈로그 검사 통과(출처·사실·금지어·마네킹·길이·루프)", not errs, errs[:5])
ck("12편 이상(4주 분량)", len(eps) >= 12, len(eps))
fm = [e["format"] for e in eps]
ck("짧은 실화 절반 · what-if 절반(차이 1편 이하)", abs(fm.count("story") - fm.count("whatif")) <= 1, fm)
ck("첫 네 편 = 2차 견본 S1→S2→S3→S4(11/4 수부터)",
   [e["slug"] for e in eps[:4]] == ["helmet-filled-with-water", "struck-by-lightning-seven-times",
                                     "plane-door-at-35000-feet", "outrun-a-tsunami"] and eps[0]["from"] == "2026-11-04", [e["slug"] for e in eps[:4]])
ck("S4 는 'pulled back' 판(바다가 '사라졌다'고 하지 않는다 — 그림이 빠진 해저)",
   "pulled back" in ST.spoken(eps[3]) and "disappeared" not in ST.spoken(eps[3]))
ck("출처는 편마다 2개 이상 · https · 사실마다 출처 번호", all(
    len(e["sources"]) >= 2 and all(s["url"].startswith("https://") for s in e["sources"])
    and all(f["src"] for f in e["facts"]) for e in eps))
ck("5B 영상 클립 없음(깨짐을 자동으로 못 거른다)", '"video"' not in json.dumps(cat))
ck("편마다 조심할 점(careful)", all(len(e["careful"]) > 20 for e in eps))
ck("마지막 장면은 첫 그림으로(루프)", all(e["shots"][-1].get("reuse") == 0 and e["shots"][-1]["move"] == "loop_end" for e in eps))
ck("인물이 있는 편은 기준 그림 + 편집(얼굴 없는 마네킹으로 컷마다 이어진다)",
   all("mannequin" in e["character"]["prompt"] for e in eps if e.get("character"))
   and sum(1 for e in eps if e.get("character")) >= 6)

print("── 2. 검사가 막는 것 ──")
base = copy.deepcopy(eps[4])


def bad(mut, word):
    e = copy.deepcopy(base)
    mut(e)
    got = ST.check_episode(e)
    return any(word in x for x in got), got


cases = [
    ("화요일 편", lambda e: e.update({"from": "2026-11-17"}), "월·수·금"),
    ("첫 공개일(11/4) 전", lambda e: e.update({"from": "2026-11-02"}), "첫 공개일"),
    ("출처 1개", lambda e: e.update({"sources": e["sources"][:1]}), "출처는 2개"),
    ("http 출처", lambda e: e["sources"][0].update({"url": "http://example.com/x"}), "https"),
    ("없는 출처 번호", lambda e: e["facts"][0].update({"src": [9]}), "출처 번호"),
    ("설명에 링크", lambda e: e.update({"description": e["description"] + " https://x.y"}), "링크"),
    ("사람 그림에 마네킹 없음", lambda e: e["shots"][1].update({"prompt": "an astronaut floating in space"}), "mannequin"),
    ("글자·상표 금지어", lambda e: e["shots"][1].update({"prompt": "a spacecraft with a NASA logo"}), "금지어"),
    ("잔혹 내레이션", lambda e: e["shots"][1].update({"say": "There was blood everywhere."}), "금지어"),
    ("5B 클립", lambda e: e["shots"][1].update({"video": "moves"}), "5B"),
    ("긴 플래시", lambda e: e["shots"][3].update({"flash": [1.2]}), "flash"),
    ("앞 장면이 아닌 reuse", lambda e: e["shots"][6].update({"reuse": 20}), "reuse"),
    ("루프 없음", lambda e: e["shots"][-1].update({"move": "push_in"}), "루프"),
    ("내레이션 너무 김", lambda e: e["shots"][1].update({"say": "word " * 120}), "단어"),
    ("character 없는 edit", lambda e: e.pop("character"), "character"),
]
for name, mut, word in cases:
    hit, got = bad(mut, word)
    ck(f"막는다: {name}", hit, got[:3])
dup = copy.deepcopy(cat)
dup["episodes"].append(dict(copy.deepcopy(dup["episodes"][-1]), id=99, slug="dup-day"))
ck("같은 날 두 편 · 같은 제목은 막는다", any("같은 날" in x for x in ST.check(dup)) and any("제목" in x for x in ST.check(dup)))

print("── 3. 편성표 ──")
ck("모든 편이 월·수·금 22:00 KST = 13:00 UTC", all(ST.slot(e).hour == 13 and ST.slot(e).astimezone(ST.KST).hour == 22
                                                 and dt.date.fromisoformat(e["from"]).weekday() in (0, 2, 4) for e in eps))
nov = [dt.date(2026, 11, 4) + dt.timedelta(days=k) for k in range(27)]
posts = [d for d in nov if ST.is_post_day(d)]
ck("11/4~11/30 월·수·금 12일이 빠짐없이 한 편씩", [dt.date.fromisoformat(e["from"]) for e in eps[:12]] == posts and len(posts) == 12,
   [e["from"] for e in eps[:12]])
ck("마지막 날 · 남은 편(재고)", ST.last_date(cat) == dt.date.fromisoformat(eps[-1]["from"]) and ST.left(dt.date(2026, 11, 4), cat) == len(eps)
   and ST.left(dt.date(2026, 11, 5), cat) == len(eps) - 1)
ck("조용한 시간 05:45~08:00 KST(경계 포함·제외)", not ST.quiet(kst("2026-11-04T05:44")) and ST.quiet(kst("2026-11-04T05:45"))
   and ST.quiet(kst("2026-11-04T07:59")) and not ST.quiet(kst("2026-11-04T08:00")) and not ST.quiet(kst("2026-11-04T01:00")))
e1, e2 = eps[0], eps[1]
ck("예약 공개: 카탈로그 시각 · 1시간도 안 남았으면 지금+2시간 정각 · private 은 예약 없음",
   ST.publish_time(e1, "scheduled", kst("2026-11-04T01:00")) == "2026-11-04T13:00:00Z"
   and ST.publish_time(e1, "scheduled", kst("2026-11-04T21:30")) == "2026-11-04T14:00:00Z"
   and ST.publish_time(e1, "private", kst("2026-11-04T01:00")) is None)

print("── 4. 할 일(due) · ledger ──")
led = {}
ck("11/2: 아직 아니다(첫 편은 11/3 부터 만든다)", ST.due(kst("2026-11-02T01:00"), led, cat)[0] is None)
ck("11/3 밤(공개 전날): 1편", (ST.due(kst("2026-11-03T21:00"), led, cat)[0] or {}).get("id") == e1["id"])
ck("11/4 01:00: 1편", (ST.due(kst("2026-11-04T01:00"), led, cat)[0] or {}).get("id") == e1["id"])
led1 = {ST.stem(e1): {"short": "https://youtu.be/x"}}
ck("1편을 올렸으면 11/4 03:30 은 할 일 없음(2편은 11/5 부터)", ST.due(kst("2026-11-04T03:30"), led1, cat)[0] is None)
ck("11/5: 2편", (ST.due(kst("2026-11-05T01:00"), led1, cat)[0] or {}).get("id") == e2["id"])
late, why = ST.due(kst("2026-11-04T22:30"), led, cat)
ck("공개 시각을 놓쳤으면 이틀까지는 늦게라도", (late or {}).get("id") == e1["id"] and "놓쳤다" in why, why)
ck("이틀을 넘긴 편은 건너뛰고 다음 편(같은 편 몰아 올리기 없음)", (ST.due(kst("2026-11-07T01:00"), {}, cat)[0] or {}).get("id") == e2["id"])
all_done = {ST.stem(e): {"short": "u"} for e in eps}
ck("다 올렸으면 '남은 편 없음'(채우라는 말)", ST.due(kst("2026-12-30T01:00"), all_done, cat) == (None, "남은 편 없음 — story_catalog.json 끝에 편을 붙일 것"))
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "sub", "led.json")
    ST.save_ledger(led1, p)
    ck("ledger 저장·읽기", ST.load_ledger(p) == led1 and ST.load_ledger(os.path.join(td, "none.json")) == {})

print("── 5. 메타(제목·설명·출처) ──")
ok = True
for e in eps:
    md = ST.meta(e)
    ok &= len(md["title"]) <= 100 and len(md["description"]) <= 4900 and md["description"].endswith(ST.marker(e))
    ok &= all(s["url"] in md["description"] for s in e["sources"]) and "AI" in md["description"] and "shorts" in md["tags"]
ck("설명 = 카탈로그 설명 + 출처 링크 전부 + AI 고지 + 표식(4,900자 이하) · 제목 100자 이하", ok)
ck("표식은 편마다 다르다(유튜브에서 같은 편 찾기)", len({ST.marker(e) for e in eps}) == len(eps))
import upload_tale as UT  # noqa: E402
ck("업로드 status: 합성 콘텐츠 표시(containsSyntheticMedia) · 예약이면 비공개 + publishAt",
   UT.status_body("private", "2026-11-04T13:00:00Z") == {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                                                         "containsSyntheticMedia": True, "publishAt": "2026-11-04T13:00:00Z"})

print("── 6. 렌더 부품(그림·소리 없이) ──")
try:
    import story_reel as SR
    HAVE_PIL = True
except ImportError as ex:          # numpy·PIL 이 없는 환경
    HAVE_PIL = False
    print(f"  · story_reel 불러오기 실패({ex}) — 렌더 부품·mock 렌더 건너뜀")
if HAVE_PIL:
    toks, spoken = SR.parse_tokens([{"say": "{July 2013.|July, twenty thirteen.} Astronaut {44|Forty-four} minutes"}])
    ck("'{보이는|읽는}': 자막엔 숫자, 목소리는 읽는 말", [t["disp"] for t in toks] == ["July 2013.", "Astronaut", "44", "minutes"]
       and spoken == "July, twenty thirteen. Astronaut Forty-four minutes")
    ok = True
    for mv in SR.MOVES:
        for p in (0.0, 0.3, 0.7, 1.0):
            z, cx, cy = SR.cam_params(mv, p, p * 3, 3.0)
            ok &= z >= 1.0 and 0.4 <= cx <= 0.6 and 0.4 <= cy <= 0.6
    ck("카메라: 확대 1 이상(검은 테두리 없음) · 중심이 크게 안 흔들린다 · 회전 없음(값이 셋)", ok)
    ck("옛 대본의 shake·orbit 은 밀기와 같다(흔들림·회전 없음)", SR.cam_params("shake", 0.5, 1, 2) == SR.cam_params("push_in", 0.5, 1, 2)
       == SR.cam_params("orbit", 0.5, 1, 2))
    try:
        SR.font(40)
        HAVE_FONT = True
    except RuntimeError:
        HAVE_FONT = False
        print("  · 글꼴 없음 — 자막 크기 검사 건너뜀")
    if HAVE_FONT:
        im = SR.caption_img(["Everyone", "assumed", "his"], 1)
        ck("자막: 쇼츠 버튼(오른쪽 140px)·아래 20 % 밖", SR.CAP_CX + im.width / 2 <= SR.W - 140 + 20
           and SR.CAP_Y + im.height / 2 <= SR.H * 0.8)
    V = {"dur": 6.0, "tokens": [{"disp": d, "t0": 0.4 * k, "t1": 0.4 * k + 0.35, "shot": s}
                                for k, (d, s) in enumerate([("Water", 0), ("was", 0), ("crawling", 0), ("over", 0), ("his", 0),
                                                            ("eyes,", 0), ("and", 1), ("he", 1), ("was", 1), ("outside.", 1)])]}
    T = SR.build_timeline({"shots": [{}, {}]}, V)
    ck("시간표: 장면 시작이 늘어난다 · 자막은 2~3단어 · 첫 자막은 0초부터", T["starts"][0] == 0 and T["starts"][1] > 2
       and all(1 <= len(c["words"]) <= 3 for c in T["chunks"]) and T["chunks"][0]["t0"] == 0.0, T["chunks"])
    ck("효과음·배경음 이름이 검사 목록과 같다", set(SR.SFX) == set(ST.SFX) and set(SR.MOODS) == set(ST.MUSIC)
       and set(SR.MOVES) == set(ST.MOVES))

    print("── 7. mock 렌더(가짜 그림·목소리 · 앞 3장면) · 업로드 가드 ──")
    ff = SR.ffmpeg()
    if not (shutil.which(ff) or os.path.exists(ff)) or not HAVE_FONT:
        print("  · ffmpeg·글꼴 없음 — mock 렌더 건너뜀")
    else:
        with tempfile.TemporaryDirectory() as td:
            # procs=1: 하위 프로세스 없이(Windows spawn 은 이 테스트 파일을 다시 실행한다)
            res = SR.render(eps[0], out_dir=os.path.join(td, "out"), work=os.path.join(td, "work"), mock=True, procs=1,
                            limit_shots=3)
            r = subprocess.run([ff, "-hide_banner", "-i", res["video"]], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            ck("1080×1920 H.264 + AAC · 1초 시트·첫 2초·자막 파일", "1080x1920" in r.stderr and "h264" in r.stderr
               and "aac" in r.stderr and all(os.path.exists(res[k]) for k in ("sheet", "first2s", "srt")), r.stderr[-400:])
            ck("meta 에 mock 표시", json.load(open(res["video"][:-4] + "_meta.json", encoding="utf-8"))["mock"] is True)
            led_p = os.path.join(td, "led.json")
            # mock 결과를 이 편 이름으로 둔다 → upload 가 유튜브에 붙기 전에 막아야 한다
            out = os.path.join(td, "out")
            os.rename(res["video"][:-4] + "_meta.json", os.path.join(out, f"{ST.stem(eps[0])}_meta.json"))
            ck("mock 렌더는 올리지 않는다(유튜브에 붙기 전에 2로 끝난다)", ST.upload(eps[0]["id"], out, led_p) == 2
               and not os.path.exists(led_p))

print("── 8. 워크플로 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "nt-story.yml"), encoding="utf-8").read()
crons = re.findall(r'cron:\s*"([^"]+)"', wf)
ck("예약 세 번(01:00 · 03:30 · 10:00 KST) — 아침 업로드 시간대(05:45~08:00)는 비운다",
   crons == ["0 16 * * *", "30 18 * * *", "0 1 * * *"], crons)
ck("할 일은 story.py due 가 정한다 · 75(조용한 시간)는 실패가 아니다 · 업로드는 그때 건너뛴다",
   "story.py due" in wf and "rc -eq 75" in wf and "steps.render.outputs.quiet != '1'" in wf)
ck("읽기 권한만(push 없음) · ledger 는 실패해도 저장 · 받은 그림 캐시", re.search(r"(?m)^\s*contents:\s*read", wf) is not None
   and "contents: write" not in wf and not [ln for ln in wf.splitlines() if not ln.strip().startswith("#")
                                            and re.search(r"\bgit\b.*\bpush\b", ln.split(" #")[0])]
   and not re.search(r"(?m)^\s+push:", wf) and "nt-story-ledger-" in wf and "nt-story-work-" in wf)
ck("렌더 전 유튜브 표식 확인(seen) · 테스트·카탈로그 검사 먼저", wf.find("story.py seen") < wf.find("story_reel.py")
   and wf.find("test_story.py") < wf.find("story_reel.py"))

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
