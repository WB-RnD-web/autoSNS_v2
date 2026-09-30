#!/usr/bin/env python3
"""인스타 릴스 회귀 테스트 — 네트워크 없이(가짜 목소리·그림·숫자). 영상은 낮은 fps 로 한 번 끝까지 만든다.

    python insta/test_insta.py
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import glob
import io
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import insta as I          # noqa: E402
import post_reel as PR     # noqa: E402
import render_cards as RC  # noqa: E402
import render_reel as R    # noqa: E402
import stats as ST         # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


GUIDE_P = os.path.join(HERE, "samples", "first-second.json")
REPORT_P = os.path.join(HERE, "samples", "weekly-report.json")
G, RP = I.load(GUIDE_P), I.load(REPORT_P)


def errs_of(s, strict=False, path=None):
    return I.check(s, path, strict=strict)


def has(errs, word):
    return any(word in e for e in errs)


def with_say(s, i, text):
    x = copy.deepcopy(s)
    x["scenes"][i]["say"] = text
    return x


print("── 견본 ──")
for p, s in ((GUIDE_P, G), (REPORT_P, RP)):
    e = I.check(s, p)
    ck(f"{os.path.basename(p)} 통과", not e, str(e[:3]))
    fake = os.path.join(I.ROUTINE_DIR, f"{s['date']}_{s['topic']}.json")
    e = I.check(s, fake, strict=True)
    ck(f"{os.path.basename(p)} 는 편성(날짜·요일·주제)과도 맞다", not e, str(e[:3]))

print("── 편성(요일 → 형식, 날짜 → 주제) ──")
cat = I.catalog()
ck("start 는 가이드 요일(월·수·금)", I._date(cat["start"]).weekday() in (0, 2, 4))
week = {d: I.format_for(f"2026-10-{d:02d}") for d in range(5, 12)}
ck("월·수·금 guide · 일 report · 화·목·토 쉼",
   week == {5: "guide", 6: None, 7: "guide", 8: None, 9: "guide", 10: None, 11: "report"}, str(week))
slugs = [t["slug"] for t in cat["topics"]]
ck("9/30 → 1번 · 10/2 → 2번 · 10/5 → 3번 · 10/7 → 4번",
   [I.assigned(d)["slug"] for d in ("2026-09-30", "2026-10-02", "2026-10-05", "2026-10-07")] == slugs[:4])
ck("일요일은 weekly-report", I.assigned("2026-10-11")["slug"] == I.REPORT_SLUG)
ck("start 이전 가이드 날은 쉼", I.assigned("2026-09-28")["format"] is None)
ck("같은 날짜는 늘 같은 주제(결정론)", I.assigned("2026-10-21") == I.assigned("2026-10-21"))
last = I._date(cat["start"])
while I.assigned(last)["slug"] != slugs[-1]:
    last += dt.timedelta(days=1)
ck("catalog 끝나면 next 가 멈추고 알린다", I.assigned(last + dt.timedelta(days=2 if last.weekday() != 4 else 3)).get("note", "")
   .startswith("catalog 끝"))
left = sum(1 for k in range(0, 400) if I.assigned(dt.date.today() + dt.timedelta(days=k)).get("topic")) if \
    dt.date.today() >= I._date(cat["start"]) else len(slugs)
if left < 6:
    print(f"::warning title=인스타 catalog 거의 끝::남은 가이드 주제 {left}개 — insta/catalog.json 끝에 추가할 것")
ck("다른 주제로 쓰면 막힌다", has(errs_of(dict(G, date="2026-10-05"), strict=True), "주제는"))
ck("요일과 형식이 다르면 막힌다", has(errs_of(dict(RP, date="2026-10-05"), strict=True), "guide 날"))
ck("쉬는 날(화)은 막힌다", has(errs_of(dict(G, date="2026-10-06"), strict=True), "올리지 않는 날"))
ck("파일 이름이 날짜_주제와 다르면 막힌다",
   has(I.check(G, os.path.join(I.ROUTINE_DIR, "2026-10-12_other.json"), strict=True), "파일 이름"))

print("── 숫자는 자리표시자로만 ──")
ck("말에 숫자를 직접 쓰면 막힌다", has(errs_of(with_say(G, 1, "조회는 1,285회였어요.")), "숫자"))
ck("제목에 숫자를 직접 쓰면 막힌다", has(errs_of(dict(G, headline=["첫 화면", "11.9% vs 57.4%"])), "숫자"))
ck("화면 글자(steps)에 숫자를 쓰면 막힌다",
   has(errs_of(dict(G, scenes=G["scenes"][:-1] + [dict(G["scenes"][-1], show={"steps": ["1단계 캡처", "보기"]})])), "숫자"))
ck("한글 숫자 주장('천 회')도 막힌다", has(errs_of(with_say(G, 1, "조회가 천 회를 넘었어요.")), "한글로 쓴 숫자"))
ck("'두 배'도 막힌다", has(errs_of(with_say(G, 1, "조회가 두 배로 늘었어요.")), "한글로 쓴 숫자"))
ck("작은 개수('세 가지')는 괜찮다", not has(errs_of(with_say(G, 1, "첫 화면에서 볼 건 세 가지예요.")), "숫자"))
ck("모르는 자리표시자는 막힌다", has(errs_of(with_say(G, 1, "조회는 {{fact.nope}}였어요.")), "모르는 자리표시자"))
ck("캡션의 단계 번호(1. 2. 3.)는 괜찮다", not has(errs_of(G), "캡션: 숫자"))
ck("캡션 본문 숫자는 막힌다", has(errs_of(dict(G, caption=G["caption"] + "\n조회 147회")), "숫자"))
ck("가이드에 실측 숫자가 하나도 없으면 막힌다",
   has(errs_of(dict(G, scenes=[dict(x, say=re.sub(r"\{\{[^}]+\}\}", "그만큼", x["say"])) for x in G["scenes"]],
                    headline=["첫 화면이 가른 차이"],
                    caption=re.sub(r"\{\{[^}]+\}\}", "그만큼", G["caption"]))), "실측 숫자"))

print("── 금지 표현·형식 ──")
ck("과장(대박)은 막힌다", has(errs_of(with_say(G, 2, "이거 대박이에요.")), "과장"))
ck("돈 주장은 막힌다", has(errs_of(with_say(G, 2, "한 달 만에 돈을 벌었어요.")), "돈 주장"))
ck("참여 낚시(댓글 남기면)는 막힌다", has(errs_of(with_say(G, 2, "댓글에 자료라고 남기면 보내 드려요.")), "참여 낚시"))
ck("구독 요청은 막힌다", has(errs_of(with_say(G, 2, "구독하고 보세요.")), "홍보"))
ck("'구독자'라는 낱말은 괜찮다", not has(errs_of(with_say(G, 2, "구독자가 늘진 않았어요.")), "홍보"))
ck("링크는 막힌다", has(errs_of(dict(G, caption=G["caption"] + "\nhttps://youtu.be/x")), "홍보"))
ck("가이드에 날짜 타는 말(요즘)은 막힌다", has(errs_of(with_say(G, 2, "요즘 이게 제일 중요해요.")), "날짜를 타는"))
ck("성적표는 '이번 주'를 써도 된다", not has(errs_of(RP), "날짜를 타는"))
ck("해시태그 6개는 막힌다", has(errs_of(dict(G, hashtags=[f"#태그{c}" for c in "가나다라마바"])), "해시태그"))
ck("캡션에 # 은 막힌다", has(errs_of(dict(G, caption=G["caption"] + " #쇼츠")), "# 금지"))
ck("캡션에 단계가 없으면 막힌다", has(errs_of(dict(G, caption="첫 줄\n저장해 두세요")), "단계"))
ck("캡션에 '저장'이 없으면 막힌다", has(errs_of(dict(G, caption=G["caption"].replace("저장", "기억"))), "저장"))
ck("마지막 장면에 '저장'이 없으면 막힌다", has(errs_of(with_say(G, -1, "첫 화면만 캡처해서 따로 보세요.")), "마지막 장면"))
ck("그림 프롬프트에 화면(screen)은 막힌다",
   has(errs_of(dict(G, scenes=G["scenes"][:2] + [dict(G["scenes"][2], show={"img": "a laptop screen showing code in a dark room"})]
                    + G["scenes"][3:])), "글자·화면"))
ck("그림 프롬프트는 영어로", has(errs_of(dict(G, scenes=[dict(G["scenes"][0], show={"img": "책상 위의 노트북과 커피 한 잔, 아침 햇살"})]
                                             + G["scenes"][1:])), "영어로"))
ck("비밀처럼 보이는 글은 막힌다", has(errs_of(dict(G, caption=G["caption"] + "\nghp_abcdefghijklmnop")), "비밀"))
ck("이메일도 막힌다", has(errs_of(dict(G, caption=G["caption"] + "\nme@example.com")), "비밀"))
ck("말이 너무 짧으면 막힌다", has(errs_of(dict(G, scenes=[dict(x, say="짧아요. 저장") for x in G["scenes"][:4]])), "말 분량"))
ck("제목 3줄은 막힌다", has(errs_of(dict(G, headline=["하나", "둘", "셋"])), "1~2줄"))
ck("제목 한 줄이 너무 길면 막힌다", has(errs_of(dict(G, headline=["첫 화면이 가른 차이가 너무 커서 놀랐어요", "끝"])), "폭"))
ck("성적표는 두 채널 숫자가 다 있어야", has(errs_of(dict(RP, scenes=[x for x in RP["scenes"] if "ntt" not in json.dumps(x)],
                                                   caption=RP["caption"])), "ntt 숫자"))

print("── 숫자 읽기(말) ──")
cases = {"1,285회": "천이백팔십오 회", "6시간": "여섯 시간", "12띠": "열두 띠", "57.4%": "오십칠 점 사 퍼센트",
         "8,000시간": "팔천 시간", "2,000만 회": "이천만 회", "2027년 2월 1일": "이천이십칠년 이월 일일", "10월": "시월",
         "75장면": "칠십오 장면", "20편": "스무 편", "0회": "영 회", "2배": "두 배", "36시간": "서른여섯 시간"}
bad = {k: I.to_speech(k) for k, v in cases.items() if I.to_speech(k) != v}
ck("숫자·단위 한글 읽기", not bad, str(bad))
ck("약어는 한글로 읽는다", I.to_speech("AI가 GitHub Actions로") == "에이아이가 깃허브 액션즈로", I.to_speech("AI가 GitHub Actions로"))
nums_bad = [(t["slug"], k) for t in cat["topics"] for k, v in t.get("nums", {}).items()
            if re.search(r"[~:]|\d\.\d+만", v["v"]) and not v.get("say")]
nums_bad += [("공통", k) for k, v in cat.get("nums", {}).items() if re.search(r"[~:]", v["v"]) and not v.get("say")]
ck("범위(~)·시각(:) 숫자는 읽는 말(say)을 따로 적었다", not nums_bad, str(nums_bad))

print("── 자리표시자 채우기 ──")
st = ST.mock(dt.date(2026, 10, 4))
entry = I.topic_entry(G["topic"])
ctx = I.context(entry, st, G["date"])
ck("화면 = 숫자, 말 = 한글", I.resolve("{{fact.continued}}", ctx) == "11.9%"
   and I.resolve("{{fact.continued}}", ctx, "say") == "십일 점 구 퍼센트")
ck("채널 숫자(stats) — 단위 포함", ctx["wb.subs"][0] == "194명" and ctx["ntt.name"][1] == "나인 테일즈 테일즈")
ck("영상 조회수(stats)", ctx["vid.ep1_short.views"][0].endswith("회"))
try:
    I.resolve("{{wb.subs}}", I.context(entry, None, G["date"]))
    ck("stats 가 없으면 채널 숫자에서 멈춘다", False)
except I.Missing:
    ck("stats 가 없으면 채널 숫자에서 멈춘다", True)
cap = I.final_caption(G, ctx)
ck("게시 캡션: 자리표시자 없음·꼬리말·해시태그", "{{" not in cap and "기록 중인 채널" in cap and cap.rstrip().endswith("#AI유튜브"))
ck("게시 캡션 2,200자 이하", len(cap) <= 2200, str(len(cap)))
ck("쓰레드 글 500자 이하", len(I.threads_text(G, ctx)) <= 500)
ck("성적표 기간", I.context(None, None, "2026-10-04")["week.range"][0] == "9월 28일~10월 4일")
ck("통계 제목 정리(해시태그 제거)", ST.clean_title("오늘 운세 1위 #shorts #운세") == "오늘 운세 1위")

print("── 렌더(가짜 목소리·그림, 낮은 fps로 끝까지) ──")
R.FPS = 6
with tempfile.TemporaryDirectory() as td:
    for p, host in ((GUIDE_P, "none"), (REPORT_P, "gumi")):
        res = R.render(p, os.path.join(td, "out"), os.path.join(td, "work"), stats_path=None, mock=True, host=host)
        ck(f"{os.path.basename(p)} 렌더 {res['sec']}초 — 30~45초", R.MIN_SEC <= res["sec"] <= R.MAX_SEC + 0.5)
        ck(f"{os.path.basename(p)} mp4·커버·한눈에 보기·메타", all(os.path.exists(res[k]) for k in ("video", "cover", "sheet")))
        ck(f"{os.path.basename(p)} 메타는 mock 표시(게시 불가)", res["mock"] and res["stats_mock"])
        from PIL import Image
        cov = Image.open(res["cover"]).convert("RGB")
        ck(f"{os.path.basename(p)} 커버 1080×1920", cov.size == (R.W, R.H))
        head = cov.crop(R.HEAD)
        bright = sum(1 for px in head.getdata() if px[0] > 200 and px[1] > 170)
        ck(f"{os.path.basename(p)} 첫 프레임에 두 줄 제목이 보인다", bright > 5000, str(bright))
        pan = cov.crop(R.PANEL)
        ck(f"{os.path.basename(p)} 첫 프레임에 실물 화면이 차 있다", len(set(pan.resize((48, 48)).getdata())) > 20)
        # 게시 가드
        meta = I.load(os.path.join(td, "out", f"{res['stem']}_meta.json"))
        s = I.load(p)
        why = PR.blockers(s, p, meta, {}, I._date(s["date"]))
        ck(f"{os.path.basename(p)} mock 은 게시 안 함", has(why, "mock"))
        why = PR.blockers(s, p, dict(meta, mock=False, stats_mock=False), {}, I._date(s["date"]) + dt.timedelta(days=5))
        ck(f"{os.path.basename(p)} 옛 날짜 원고는 게시 안 함", has(why, "늦게 도착"))
        why = PR.blockers(s, p, dict(meta, mock=False, stats_mock=False), {res["stem"]: {}}, I._date(s["date"]))
        ck(f"{os.path.basename(p)} 이미 올린 편은 게시 안 함", has(why, "이미 올린"))
        why = PR.blockers(s, p, dict(meta, mock=False, stats_mock=False), {}, I._date(s["date"]))
        ck(f"{os.path.basename(p)} 조건이 맞으면 게시 가능", not why, str(why))
        # 카드도 같은 곳에 렌더 → post_reel dry-run 이 요일 형식대로 호출 순서를 만든다(네트워크·토큰 없이)
        cres = RC.render(p, os.path.join(td, "out"), os.path.join(td, "work"), mock=True)
        ck(f"{os.path.basename(p)} 카드 메타는 mock 표시(게시 불가)", cres["mock"] and cres["stats_mock"])
        why = PR.blockers(s, p, meta, {}, I._date(s["date"]), cards=cres, need=("cards",))
        ck(f"{os.path.basename(p)} mock 카드는 게시 안 함", has(why, "mock"))
        keep = {k: os.environ.pop(k, None) for k in ("INSTA_PUBLISH", "INSTA_THREADS", "INSTA_IG_FORMAT",
                                                       "INSTA_THREADS_FORMAT", "GITHUB_STEP_SUMMARY")}
        os.environ["INSTA_THREADS"] = "1"
        argv, buf = sys.argv, io.StringIO()
        sys.argv = ["post_reel.py", p, "--renders", os.path.join(td, "out"), "--ledger", os.path.join(td, "led.json"),
                    "--posted", os.path.join(td, "posted.json"), "--today", s["date"]]
        try:
            with contextlib.redirect_stdout(buf):
                rc = PR.main()
        finally:
            sys.argv = argv
            os.environ.pop("INSTA_THREADS", None)
            os.environ.update({k: v for k, v in keep.items() if v is not None})
        o = buf.getvalue()
        ig_call = '"media_type": "REELS"' if s["format"] == "guide" else '"media_type": "CAROUSEL"'
        ck(f"{os.path.basename(p)} dry-run: 인스타 {'릴스' if s['format'] == 'guide' else '카드'} + 쓰레드 카드 호출 순서를 보여 준다",
           rc == 0 and "이 순서로 호출한다" in o and ig_call in o and "threads_publish" in o
           and "graph.instagram.com/{IG_USER_ID}/media_publish" in o, o[-600:])
        ck(f"{os.path.basename(p)} dry-run 은 기록하지 않고 토큰도 쓰지 않는다",
           not os.path.exists(os.path.join(td, "posted.json")) and "access_token" not in o)
    host_env = os.environ.pop("INSTA_PUBLISH", None)
    ck("INSTA_PUBLISH 가 없으면 dry-run", not PR._on("INSTA_PUBLISH"))
    if host_env is not None:
        os.environ["INSTA_PUBLISH"] = host_env
ck("자막 조각: 첫 장면은 훅 한 문장을 통째로", len(R.caption_chunks("제 영어 설화 쇼츠, 넘기지 않고 본 사람이 11.9%뿐이었어요.", 42)) == 1)
ck("숫자 올라가기 모양 유지", R.count_up("1,285회", 0.5).endswith("회") and "," in R.count_up("1,285회", 1.0))
ck("배경음 20초·클리핑 없음", len(R.bed(R.SR * 20)) == R.SR * 20 and float(abs(R.bed(R.SR * 5)).max()) <= 1.0001)
for kind in ("head", "bold", "reg"):
    ck(f"한글 글꼴 '{kind}' = 실제 트루타입({os.path.basename(R.font_path(kind))})", R.font(kind, 80).size == 80)

print("── 카드(캐러셀) ──")
for p, s in ((GUIDE_P, G), (REPORT_P, RP)):
    pl = RC.card_plan(s)
    ck(f"{os.path.basename(p)} 카드 {pl['count']}장 — 5~9장(최대 {RC.MAX_SLIDES})", 5 <= pl["count"] <= 9)
    ck(f"{os.path.basename(p)} 훅 = 첫 장면 화면", pl["hook"]["scenes"] == [0])
pl = RC.card_plan(G)
ck("강조(hi)만 다른 같은 단계 화면은 한 장으로(말은 첫 장면 것)",
   any(x["scenes"] == [5, 6] and x["text"] == G["scenes"][5]["say"] for x in pl["points"]),
   str([x["scenes"] for x in pl["points"]]))
many = dict(G, scenes=[G["scenes"][0]]
            + [{"say": f"그림 {k}", "show": {"img": f"a calm lake at dawn number {k}"}} for k in range(6)]
            + [{"say": f"숫자 {k}", "show": {"stat": "{{fact.continued}}", "label": f"라벨 {k}"}} for k in range(6)])
pl = RC.card_plan(many)
kinds = [x["kind"] for x in pl["points"]]
ck("장면이 많으면 10장으로 — 분위기 그림(img)부터, 뒤에서부터 뺀다",
   pl["count"] == RC.MAX_SLIDES and kinds.count("img") == 2 and kinds.count("stat") == 6
   and [x["scenes"][0] for x in pl["points"]][:2] == [1, 2], str(kinds))

with tempfile.TemporaryDirectory() as td:
    from PIL import Image
    for p in (GUIDE_P, REPORT_P):
        n = os.path.basename(p)
        a = RC.render(p, os.path.join(td, "a"), os.path.join(td, "work"), mock=True)
        ims, shape = [], []
        for x in a["cards"]:
            with Image.open(x) as im:                 # 닫아 둔다(윈도는 열린 파일을 못 지운다)
                shape.append((im.format, im.size))
                ims.append(im.convert("RGB"))
        ck(f"{n} 카드 {a['count']}장 — {RC.MIN_SLIDES}~{RC.MAX_SLIDES}", RC.MIN_SLIDES <= a["count"] <= RC.MAX_SLIDES)
        ck(f"{n} 카드는 전부 1080×1350 JPEG(4:5)", all(sh == ("JPEG", (1080, 1350)) for sh in shape), str(shape))
        ck(f"{n} 카드는 게시 규격 통과(2~10장·크기·형식)", not PR.card_problems(a))
        hook = ims[0]
        bright = sum(1 for px in hook.crop(RC.HOOK_HEAD).getdata() if px[0] > 200 and px[1] > 170)
        ck(f"{n} 첫 장에 큰 제목이 보인다", bright > 20000, str(bright))
        ck(f"{n} 제목은 격자 미리보기(1:1 가운데·3:4) 안",
           RC.SQUARE[1] <= RC.HOOK_TAG_Y and RC.HOOK_HEAD[3] <= RC.SQUARE[3]
           and RC.GRID34[0] <= RC.HOOK_HEAD[0] and RC.HOOK_HEAD[2] <= RC.GRID34[2])
        box = (RC.PANEL_XY[0], RC.PANEL_XY[1], RC.PANEL_XY[0] + R.PW, RC.PANEL_XY[1] + R.PH)
        ck(f"{n} 가운데 장에 실물 화면이 차 있다", len(set(ims[1].crop(box).resize((48, 48)).getdata())) > 20)
        b = RC.render(p, os.path.join(td, "b"), os.path.join(td, "work"), mock=True)
        same = all(open(x, "rb").read() == open(y, "rb").read() for x, y in zip(a["cards"], b["cards"]))
        ck(f"{n} 같은 대본 → 같은 카드(결정론)", same and a["count"] == b["count"])
        tags = I.load(p)["hashtags"]
        ck(f"{n} 카드 캡션: 자리표시자 없음·2,200자 안·해시태그 끝",
           "{{" not in a["caption"] and len(a["caption"]) <= 2200 and a["caption"].rstrip().endswith(tags[-1]))
        ck(f"{n} 쓰레드 글 500자 안·해시태그 없음·주제 태그 하나",
           I.threads_len(a["threads"]) <= 500 and "#" not in a["threads"] and a["topic_tag"] == tags[0].lstrip("#"))
    ck("카드 꼬리말: 목소리 말 없음 · AI 그림 표시는 있을 때만",
       "목소리" not in I.card_footer(True) and "AI" in I.card_footer(True) and "AI로" not in I.card_footer(False))

print("── 게시 형식(요일 → 어디에 무엇을) ──")
fm = lambda d, **e: I.publish_formats(d, env=e)  # noqa: E731
ck("월·수·금(가이드) → 인스타 릴스 · 쓰레드 카드",
   all(fm(d)["ig"] == ["reel"] and fm(d)["threads"] == "cards" for d in ("2026-10-05", "2026-10-07", "2026-10-09")))
ck("일(성적표) → 인스타 카드 · 쓰레드 카드", fm("2026-10-11")["ig"] == ["cards"] and fm("2026-10-11")["threads"] == "cards")
ck("auto 는 기본과 같다", fm("2026-10-05", INSTA_IG_FORMAT="auto", INSTA_THREADS_FORMAT="auto") == fm("2026-10-05"))
ck("INSTA_IG_FORMAT=both → 릴스+카드", fm("2026-10-05", INSTA_IG_FORMAT="both")["ig"] == ["reel", "cards"])
ck("INSTA_IG_FORMAT=cards → 월요일도 카드", fm("2026-10-05", INSTA_IG_FORMAT="cards")["ig"] == ["cards"])
ck("INSTA_IG_FORMAT=reel → 일요일도 릴스", fm("2026-10-11", INSTA_IG_FORMAT="reel")["ig"] == ["reel"])
ck("INSTA_THREADS_FORMAT=reel → 쓰레드 릴스", fm("2026-10-11", INSTA_THREADS_FORMAT="reel")["threads"] == "reel")
bad = fm("2026-10-05", INSTA_IG_FORMAT="gif", INSTA_THREADS_FORMAT="x")
ck("모르는 값은 기본으로 + 경고", bad["ig"] == ["reel"] and bad["threads"] == "cards" and len(bad["warn"]) == 2)
sun = fm("2026-10-11")
ck("일요일 카드 렌더가 없으면 인스타는 릴스로 대신", PR.route(sun, True, False, False)["ig"] == ["reel"])
ck("쓰레드는 INSTA_THREADS 없으면 안 올린다", PR.route(sun, True, True, False)["threads"] is None)
ck("쓰레드 카드 렌더가 없으면 릴스로 대신", PR.route(sun, True, False, True)["threads"] == "reel")
ck("both 인데 릴스가 없으면 카드만", PR.route(fm("2026-10-05", INSTA_IG_FORMAT="both"), False, True, True)["ig"] == ["cards"])

print("── 쓰레드 글·캡션 길이 ──")
ctx_g = I.context(I.topic_entry(G["topic"]), ST.mock(dt.date(2026, 10, 4)), G["date"])
long_g = dict(G, caption="첫 화면이 전부였어요.\n\n따라 하는 법\n" + "\n".join(
    f"{k}. 이 단계는 설명이 아주 길어서 쓰레드 글자 수를 넘기게 만드는 줄이에요, 정말로 길어요" for k in range(1, 16))
    + "\n\n저장해 두고 그대로 해 보세요.")
t = I.threads_text(long_g, ctx_g)
ck("쓰레드 글: 500자 안 · 첫 줄·저장 줄은 남기고 뒤 단계부터 줄 단위로 덜어 낸다",
   I.threads_len(t) <= 500 and t.startswith("첫 화면이 전부였어요.") and "저장해 두고" in t and "…" not in t
   and "15." not in t and "1. " in t, t[-200:])
ck("쓰레드 글자 수: 이모지는 UTF-8 바이트로 센다", I.threads_len("가😀") == 5 and I.threads_len("가나") == 2)
ck("쓰레드 주제 태그 = 첫 해시태그(# 없이)", I.topic_tag(G) == "유튜브쇼츠" and I.topic_tag({"hashtags": ["#A.I&B"]}) == "AIB")
huge = dict(G, caption="첫 줄\n" + "가" * 3000)
ck("인스타 캡션은 길어도 2,200자 안(꼬리말·해시태그는 남긴다)",
   len(I.card_caption(huge, ctx_g)) <= 2200 and I.card_caption(huge, ctx_g).rstrip().endswith("#AI유튜브")
   and len(I.final_caption(huge, ctx_g)) <= 2200)

print("── 게시 호출 순서(가짜 전송 — 네트워크 없음) ──")
with tempfile.TemporaryDirectory() as td:
    cards_m = {"cards": [os.path.join(td, f"c{k}.jpg") for k in range(1, 4)], "caption": "카드 캡션", "threads": "쓰레드 글"}
    reel_m = {"video": os.path.join(td, "v.mp4"), "cover": os.path.join(td, "cover.jpg"), "caption": "릴스 캡션",
              "threads": "쓰레드 릴스 글"}
    dry = PR.DryBackend()
    with contextlib.redirect_stdout(io.StringIO()):
        res = PR.publish({"ig": ["cards"], "threads": "cards", "notes": []}, None, cards_m, G, dry)
    posts = [(u.split("/")[-1], b) for m, u, b in dry.calls if m == "POST"]
    ig = [(e, b) for e, b in posts if e in ("media", "media_publish")]
    th = [(e, b) for e, b in posts if e in ("threads", "threads_publish")]
    ck("인스타 카드: 장마다 컨테이너(is_carousel_item) → CAROUSEL(children·caption) → media_publish",
       [e for e, _ in ig] == ["media"] * 4 + ["media_publish"]
       and all(b.get("is_carousel_item") == "true" and b.get("image_url", "").endswith(".jpg") for _, b in ig[:3])
       and ig[3][1].get("media_type") == "CAROUSEL" and ig[3][1].get("children") == "dry1,dry2,dry3"
       and ig[3][1].get("caption") == "카드 캡션" and ig[4][1] == {"creation_id": "dry4"}, str(ig))
    ck("쓰레드 카드: IMAGE 컨테이너(is_carousel_item) → CAROUSEL(children·text·topic_tag) → threads_publish",
       [e for e, _ in th] == ["threads"] * 4 + ["threads_publish"]
       and all(b.get("media_type") == "IMAGE" and b.get("is_carousel_item") == "true" for _, b in th[:3])
       and th[3][1].get("media_type") == "CAROUSEL" and th[3][1].get("children") == "dry6,dry7,dry8"
       and th[3][1].get("text") == "쓰레드 글" and th[3][1].get("topic_tag") == "유튜브쇼츠"
       and th[4][1] == {"creation_id": "dry9"}, str(th))
    gets = [u for m, u, _ in dry.calls if m == "GET"]
    ck("컨테이너마다 상태를 확인한 뒤 게시(인스타·쓰레드 각 4번)", len(gets) == 8, str(gets))
    ck("가짜 전송: 토큰 없음 · 공개 URL 도 가짜",
       all("access_token" not in b for _, _, b in dry.calls)
       and all(b.get("image_url", "https://dry-run.invalid/").startswith("https://dry-run.invalid/") for _, _, b in dry.calls))
    ck("게시 결과 id(인스타·쓰레드 카드)", res["ig"] == {"cards": "dry5"} and res["threads"] == {"cards": "dry10"}, str(res))
    ck("성공하면 올린 카드 원본을 지운다(무료 한도)",
       sum(1 for c in dry.calls if c[0] == "CLEANUP") == sum(1 for c in dry.calls if c[0] == "HOST") == 3)
    dry = PR.DryBackend()
    with contextlib.redirect_stdout(io.StringIO()):
        res = PR.publish({"ig": ["reel"], "threads": None, "notes": []}, reel_m, None, G, dry)
    posts = [(u.split("/")[-1], b) for m, u, b in dry.calls if m == "POST"]
    ck("인스타 릴스: REELS(video_url·cover_url) → 상태 확인 → media_publish",
       [e for e, _ in posts] == ["media", "media_publish"] and posts[0][1].get("media_type") == "REELS"
       and posts[0][1].get("cover_url", "").endswith("_cover.jpg") and res["ig"] == {"reel": "dry2"}, str(posts))
    led = {}
    lp, pp = os.path.join(td, "led.json"), os.path.join(td, "posted.json")
    PR.record(led, G, {"ig": {"reel": "111"}, "threads": {"cards": "222"}, "errors": {}}, lp, pp, now=0)
    stem = f"{G['date']}_{G['topic']}"
    rec = I.load(pp)[stem]
    ck("기록: posted.json·ledger 에 형식까지", rec["formats"] == {"ig": ["reel"], "threads": ["cards"]}
       and rec["ids"] == {"ig_reel": "111", "threads_cards": "222"} and stem in I.load(lp))
    ck("기록한 편은 다시 올리지 않는다", has(PR.blockers(G, GUIDE_P, {}, PR.load_ledger(lp, pp), I._date(G["date"]),
                                                need=()), "이미 올린"))

with open(os.path.join(ROOT, ".github", "workflows", "insta.yml"), encoding="utf-8") as f:
    wf = f.read()
ck("insta.yml: 카드 렌더 + 형식 변수(기본 auto) + 카드 결과물",
   "insta/render_cards.py" in wf and "INSTA_IG_FORMAT: ${{ vars.INSTA_IG_FORMAT || 'auto' }}" in wf
   and "INSTA_THREADS_FORMAT: ${{ vars.INSTA_THREADS_FORMAT || 'auto' }}" in wf and "_card[0-9][0-9].jpg" in wf)
sample_cards = sorted(glob.glob(os.path.join(HERE, "samples", "cards", "*.jpg")))
ck(f"견본 카드 {len(sample_cards)}장(insta/samples/cards) — 1080×1350",
   RC.MIN_SLIDES <= len(sample_cards) <= RC.MAX_SLIDES and not PR.card_problems({"cards": sample_cards}))

print("── 미아 감시·복구 · 왕별이 크로스포스트 끔 ──")
import find_orphan_storyboards as FO  # noqa: E402
ck("미아 감시가 output/insta 를 본다", "output/insta/*.json" in FO.WATCH)
ck("미아 복구 목적지 = routine/insta", FO.guess_topic("output/insta/2026-10-05_claude-routine-rules.json") == "insta")
with open(os.path.join(ROOT, ".github", "workflows", "orphan-rescue.yml"), encoding="utf-8") as f:
    ck("orphan-rescue 트리거에 output/insta", "output/insta/**.json" in f.read())
with open(os.path.join(ROOT, "pipeline", "run_pipeline.py"), encoding="utf-8") as f:
    src = f.read()
ck("왕별이 쇼츠 → 인스타 크로스포스트는 SOCIAL_CROSSPOST 뒤에(기본 끔)",
   'SOCIAL_CROSSPOST' in src and 'def social_crosspost_on' in src)
with open(os.path.join(ROOT, ".github", "workflows", "shorts.yml"), encoding="utf-8") as f:
    ck("shorts.yml 이 SOCIAL_CROSSPOST 변수를 넘긴다(기본 0)", "SOCIAL_CROSSPOST: ${{ vars.SOCIAL_CROSSPOST || '0' }}" in f.read())

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
