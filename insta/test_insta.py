#!/usr/bin/env python3
"""인스타 릴스 회귀 테스트 — 네트워크 없이(가짜 목소리·그림·숫자). 영상은 낮은 fps 로 한 번 끝까지 만든다.

    python insta/test_insta.py
"""
from __future__ import annotations

import copy
import datetime as dt
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
ck("start 는 월요일", I._date(cat["start"]).weekday() == 0)
week = {d: I.format_for(f"2026-10-{d:02d}") for d in range(5, 12)}
ck("월·수·금 guide · 일 report · 화·목·토 쉼",
   week == {5: "guide", 6: None, 7: "guide", 8: None, 9: "guide", 10: None, 11: "report"}, str(week))
slugs = [t["slug"] for t in cat["topics"]]
ck("10/5 → 1번 · 10/7 → 2번 · 10/9 → 3번 · 10/12 → 4번",
   [I.assigned(d)["slug"] for d in ("2026-10-05", "2026-10-07", "2026-10-09", "2026-10-12")] == slugs[:4])
ck("일요일은 weekly-report", I.assigned("2026-10-11")["slug"] == I.REPORT_SLUG)
ck("start 이전 가이드 날은 쉼", I.assigned("2026-09-30")["format"] is None)
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
    host_env = os.environ.pop("INSTA_PUBLISH", None)
    ck("INSTA_PUBLISH 가 없으면 dry-run", not PR._on("INSTA_PUBLISH"))
    if host_env is not None:
        os.environ["INSTA_PUBLISH"] = host_env
ck("자막 조각: 첫 장면은 훅 한 문장을 통째로", len(R.caption_chunks("제 영어 설화 쇼츠, 넘기지 않고 본 사람이 11.9%뿐이었어요.", 42)) == 1)
ck("숫자 올라가기 모양 유지", R.count_up("1,285회", 0.5).endswith("회") and "," in R.count_up("1,285회", 1.0))
ck("배경음 20초·클리핑 없음", len(R.bed(R.SR * 20)) == R.SR * 20 and float(abs(R.bed(R.SR * 5)).max()) <= 1.0001)
for kind in ("head", "bold", "reg"):
    ck(f"한글 글꼴 '{kind}' = 실제 트루타입({os.path.basename(R.font_path(kind))})", R.font(kind, 80).size == 80)

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
