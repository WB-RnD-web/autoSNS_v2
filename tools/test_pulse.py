#!/usr/bin/env python3
"""채널 맥박 회귀 테스트 — 네트워크 없이(가짜 레이더 데이터).

    python tools/test_pulse.py
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
import pulse as PU  # noqa: E402

FAIL = 0


def ck(name, cond, detail=""):
    global FAIL
    if cond:
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 20, 22, 0, tzinfo=UTC)               # 10/21 07:00 KST
STAMPS = [NOW - dt.timedelta(days=k, hours=1) for k in range(8, -1, -1)]   # 매일 21:00 UTC = 06:00 KST
DAY = "2026-10-21"
WB, NT = "UCBmHETsvCsvT0xOb99Yx19Q", "UCoPIsIO_ximUdyh-n_-rIfQ"


def st(t):
    return t.strftime("%Y-%m-%dT%H")


def vid(ch, niche, title, pub, dur, f):
    return {"ch": ch, "niche": niche, "title": title, "pub": pub.strftime("%Y-%m-%dT%H:%M:%SZ"), "dur": dur,
            "likes": 0, "comments": 0,
            "views": {st(s): int(f((s - pub).total_seconds() / 86400)) for s in STAMPS if s > pub}}


def make_radar(td):
    reg = {}
    # 왕별이 '태어난 달 표' — 매일 한 편, 새 편일수록 두 배(채널 상승) · 이틀 동안 자라고 멈춘다
    for k in range(1, 9):
        base = 1000 * 2 ** (8 - k)
        pub = NOW - dt.timedelta(days=k + 0.05)
        reg[f"m{k}"] = vid(WB, "own_wb", f"태어난 달로 보는 10월 순위 {k}", pub, 40, lambda a, b=base: b * min(a, 2) / 2)
    # 왕별이 매일 운세 표 — 어제 아침 스냅숏 뒤에 올라온 새 편(첫 스냅숏 전체가 증가)
    reg["fresh"] = vid(WB, "own_wb", "오늘 띠별 운세 1위~12위 | 10월 21일", NOW - dt.timedelta(hours=12), 8, lambda a: 300 * min(a, 1))
    # 왕별이 정치(08:30 KST) — 평소 첫 24시간 1,000회, 최근 3편만 100회(식는 중)
    for k in range(1, 10):
        pub = (NOW - dt.timedelta(days=k)).replace(hour=23, minute=30) - dt.timedelta(days=1)
        top = 100 if k <= 3 else 1000
        reg[f"p{k}"] = vid(WB, "own_wb", f"국감 {k}일째 공방 #shorts", pub, 40, lambda a, t=top: t * min(a, 1))
    # Nine Tails 이야기 쇼츠 — 2~8일 전 매일 한 편, 첫날 50회 뒤 멈춤 → 최근 이틀 업로드 없음(하락)
    for k in range(2, 9):
        pub = NOW - dt.timedelta(days=k, hours=3)
        reg[f"n{k}"] = vid(NT, "own_tales", f"The Cow That Wished {k}", pub, 50, lambda a: 50 * min(a, 1))
    # 왕별이 채널 전체: 6일 치 · 하루 증가가 매일 두 배 · 구독자는 줄어든다
    chans = {WB: {"name": "왕별이", "niche": "own_wb", "own": True, "snaps": {}}}
    tot = 100000
    for i, s in enumerate(STAMPS[-6:]):
        tot += 1000 * 2 ** i
        chans[WB]["snaps"][st(s)] = {"views": tot, "subs": 500 - i, "videos": 100 + i}
    trends = {"generated": (NOW - dt.timedelta(hours=1)).isoformat(timespec="minutes"), "niches": {
        "senior_kr": {"label": "시니어", "own": False, "tags": {
            "운동": {"label": "강세", "med": 3.4, "n": 7, "prev_med": None, "hit": 0.5},
            "약": {"label": "보통", "med": 1.0, "n": 7, "prev_med": None, "hit": 0.1},
            "형식: 쇼츠": {"label": "강세", "med": 2.0, "n": 9, "prev_med": None, "hit": 0.2}},
            "top": [{"id": "x1", "ch": "A", "title": "대박 영상", "ratio": 9.1, "views": 100000}]},
        "own_wb": {"label": "우리", "own": True, "tags": {"정치": {"label": "떡상", "med": 9, "n": 5}}, "top": []}}}
    for n, o in (("registry.json", reg), ("channels.json", chans), ("trends.json", trends)):
        PU.save(os.path.join(td, n), o)
    return reg


print("── 형식 분류(pulse_formats.json) ──")
F = PU.load_formats()
wb, nt = F["wb"]["rules"], F["nt"]["rules"]


def cls(rules, title, kst, dur=40):
    t = dt.datetime.fromisoformat(kst).replace(tzinfo=PU.KST).astimezone(UTC)
    return PU.classify({"title": title, "pub": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "dur": dur}, rules)


for want, args in [
    ("month", (wb, "태어난 달로 보는 10월 겹경사 순위 1위~12위", "2026-10-04T09:40")),
    ("daily", (wb, "오늘 띠별 운세 1위~12위 | 10월 5일", "2026-10-05T06:00")),
    ("theme", (wb, "말년 복 있는 띠 순위 1위~12위 | 10월 4일", "2026-10-04T12:00")),
    ("pulli", (wb, "오늘 귀인 만나는 띠 순위 1위~12위 | 10월 8일 을묘일 풀이 · 45~96년생 전부 #shorts", "2026-10-08T10:40")),
    ("bless", (wb, "띠별 아침 덕담 | 오늘 아침, 띠별로 드리는 한마디 · 10월 11일 · 45~96년생 전부 #shorts", "2026-10-11T10:40")),
    ("weekly", (wb, "이번 주 띠별 운세 10월 5일~11일", "2026-10-04T20:00", 600)),
    ("weekly_short", (wb, "이번 주 띠별 운세 1위~12위 | 10월 5일 월요일", "2026-10-05T06:00")),
    ("saeyeon_short", (wb, "택시 몰고 딸 결혼식 온 아버지… 사돈이 알아본 20년", "2026-10-04T19:40")),
    ("pol", (wb, "국감 하루 전, 대법원장 증인 논란 #shorts", "2026-10-05T08:43")),
    ("ai", (wb, "AI 쓰는 값, 1년 새 13분의 1 #shorts", "2026-10-04T19:09")),
    ("us", (wb, "일자리 2.9만, 내 주식은 웃었다 #shorts", "2026-10-03T07:18")),
    ("asmr", (wb, "🌊 Jeju Island Night Waves | Ocean Sounds · 8 Hours", "2026-10-03T09:57", 28801)),
    ("scp", (wb, "통가 해구에서 건진 잿빛 조직이 [SCP-9484] | SCP #shorts", "2026-09-24T09:41")),
    ("saeyeon_long", (wb, "한밤중 며느리가 시어머니를 집에서 내쫓은 이유", "2026-10-02T10:40", 5969)),
    ("rules", (nt, "Never Cut Your Nails at Night in Korea. Here's Why", "2026-10-04T22:00")),
    ("rules", (nt, "If Someone Calls Your Name Three Times at Night, Don't Answer #shorts", "2026-10-15T06:00")),
    ("versus", (nt, "Dokkaebi vs Kappa: Who Wins? #shorts", "2026-10-19T06:00")),
    ("pov", (nt, "POV: Something White Is Wiggling in the Rice Field #shorts", "2026-10-20T06:00")),
    ("story_short", (nt, "They Wished for a Daughter. Then the Cow Spoke", "2026-10-03T22:00")),
    ("episode", (nt, "Korea's Nine-Tailed Fox Is Darker Than Japan's", "2026-10-04T00:00", 900)),
    ("sleep", (nt, "Korean Folk Tales for Sleep · Rain", "2026-10-26T10:00", 7200)),
]:
    got = cls(*args)
    ck(f"{args[1][:28]} → {want}", got == want, got)
ck("규칙 key 는 채널 안에서 겹치지 않는다", all(len({r['key'] for r in c['rules']}) == len(c["rules"]) for c in F.values()))

print("── 시계열·추세 ──")
ck("추세: 꾸준히 오르면 상승 · 며칠째", PU.trend([1, 2, 4, 8, 16])["state"] == "up" and PU.trend([1, 2, 4, 8, 16])["streak"] == 4)
t = PU.trend([10, 50, 40, 30, 20, 10])
ck("추세: 꺾이면 하락으로 바뀌고 그날부터 센다(3일 평균이라 하루 늦게 꺾인다)", t["state"] == "down" and t["streak"] == 2, t)
t = PU.trend([1, 2, 4, 8, 8, 8, 8])
ck("추세: 오르다 멈추면 '상승'(오늘은 주춤)", t["state"] == "up" and t["today"] == "flat", t)
ck("추세: 사흘 미만은 판정하지 않는다", PU.trend([5, 9])["state"] == "short")
w = PU.window([1, 1, 1, 1, 4, 4, 4, 4])
ck("구간 비교: 최근 4일 평균 ÷ 그 전 4일", w["k"] == 4 and w["ratio"] == 4.0, w)
rec = {"pub": "2026-10-01T00:00:00Z", "views": {"2026-10-01T12": 100, "2026-10-02T12": 300}}
ck("첫 24시간 = 앞뒤 스냅숏 보간(12시간 100 · 36시간 300 → 24시간 200)", abs(PU.views_at(rec, 1.0) - 200) < 1e-6, PU.views_at(rec, 1.0))
ck("스냅숏 간격이 1.6일보다 넓으면 믿지 않는다", PU.views_at({"pub": rec["pub"], "views": {"2026-10-04T00": 900}}, 1.0) is None)
ck("한국식 숫자", PU.man(186810) == "18.7만" and PU.man(4200) == "4,200" and PU.man(None) == "–")

print("── build(가짜 레이더) ──")
with tempfile.TemporaryDirectory() as td:
    radar, out = os.path.join(td, "radar"), os.path.join(td, "out")
    reg = make_radar(radar)
    vs = PU.video_series({k: v for k, v in reg.items() if v["ch"] == WB})
    ck("하루 증가 = 아침 기준 24시간 · 날짜는 KST", vs[-1]["d"] == DAY and abs(vs[-1]["hours"] - 24) < 0.1, vs[-1])
    ck("새 영상은 앞 스냅숏 뒤에 올라왔으면 조회 전부가 증가", vs[-1]["per"]["fresh"] == reg["fresh"]["views"][st(STAMPS[-1])] == 137,
       vs[-1]["per"].get("fresh"))
    ck("앞 스냅숏부터 있던 영상은 차이만", vs[-1]["per"]["m1"] == reg["m1"]["views"][st(STAMPS[-1])] - reg["m1"]["views"][st(STAMPS[-2])])
    # 어제·그제 기록: FMT_COLD 이틀 연속 → 오늘 3일째 · 어제 예측
    for i, d in enumerate(("2026-10-19", "2026-10-20")):
        PU.save(os.path.join(out, d, "pulse.json"), {"date": d, "channels": {}, "flags": [
            {"id": "FMT_COLD:wb:pol", "level": "warn", "text": "x", "days": i + 1}] + ([{"id": "CH_UP:wb", "level": "good", "text": "x", "days": 1}] if d == "2026-10-19" else [])})
    PU.save(os.path.join(out, "2026-10-20", "fill.json"), {"summary": "어제 요약", "predictions": [
        {"text": "왕별이 하루 1천 이상", "metric": "views:wb", "op": ">=", "value": 1000},
        {"text": "왕별이 하루 10억 이상", "metric": "views:wb", "op": ">=", "value": 1e9},
        {"text": "NT 구독자", "metric": "subs:nt", "op": ">=", "value": 1}]})
    P = PU.build(radar, out, DAY, now=NOW)
    wbc, ntc = P["channels"]["wb"], P["channels"]["nt"]
    fl = {f["id"]: f for f in P["flags"]}
    ck("왕별이: 채널 전체 스냅숏 4일 이상 → 채널 기준", wbc["basis"] == "channel", wbc["basis"])
    ck("왕별이: 상승 며칠째", wbc["trend"]["state"] == "up" and wbc["trend"]["streak"] >= 3, wbc["trend"])
    ck("Nine Tails: 채널 스냅숏 없으면 영상 합 기준", ntc["basis"] == "videos")
    ck("CH_UP:wb (어제는 없고 그제 있었다 → 1일째)", "CH_UP:wb" in fl and fl["CH_UP:wb"]["days"] == 1, fl.get("CH_UP:wb"))
    ck("CH_DOWN:nt — 업로드가 끊기자 하락", "CH_DOWN:nt" in fl, sorted(fl))
    ck("NO_UPLOAD:nt — 지난 7일 5편인데 36시간 넘게 없음", "NO_UPLOAD:nt" in fl, ntc["last_pub_h"])
    ck("SUBS_DOWN:wb — 구독자 감소", "SUBS_DOWN:wb" in fl)
    ck("FMT_COLD:wb:pol — 최근 3편이 평소 절반 미만 · 3일째", "FMT_COLD:wb:pol" in fl and fl["FMT_COLD:wb:pol"]["days"] == 3,
       fl.get("FMT_COLD:wb:pol"))
    ck("FMT_HOT:wb:month — 첫 24시간이 평소의 3배 넘는 새 편", "FMT_HOT:wb:month" in fl, [f for f in fl if f.startswith("FMT")])
    ck("나쁜 신호가 먼저", P["flags"][0]["level"] == "bad", [f["level"] for f in P["flags"]])
    ck("오늘 조회를 끈 형식: 태어난 달 표가 1위", wbc["drivers"][0]["key"] == "month", wbc["drivers"][:2])
    ck("형식별 첫 24시간 표", {f["key"] for f in wbc["formats"]} >= {"month", "pol"})
    ck("트렌드: 참고 채널의 강세만(우리 채널·형식 줄·보통은 뺀다)",
       [r["tag"] for r in P["trends"]["rows"]] == ["운동"] and P["trends"]["hits"][0]["ratio"] == 9.1, P["trends"])
    ps = P["pred_scored"]
    ck("어제 예측 채점: 맞음·틀림·모름", [p["ok"] for p in ps] == [True, False, None], ps)
    ck("지난 날 요약", P["history"][-1]["summary"] == "어제 요약")
    ck("DATA_STALE 없음(1시간 전 데이터)", "DATA_STALE" not in fl)
    P2 = PU.build(radar, os.path.join(td, "out2"), DAY, now=NOW + dt.timedelta(hours=40))
    ck("데이터가 30시간 넘게 묵으면 DATA_STALE", any(f["id"] == "DATA_STALE" for f in P2["flags"]))

    print("── 실험 달력 ──")
    exps = {x["id"]: x for x in P["experiments"]}
    ck("남은 날 계산", exps["saeyeon-shorts"]["days_left"] == (dt.date(2026, 10, 17) - dt.date(2026, 10, 21)).days)
    real = PU.EXPERIMENTS
    PU.EXPERIMENTS = os.path.join(td, "exp.json")
    PU.save(PU.EXPERIMENTS, {"experiments": [
        {"id": "a", "ch": "wb", "title": "내일 판정", "start": "2026-10-01", "judge": "2026-10-22", "criterion": "c", "formats": ["month"], "owner": "pulse", "status": "running"},
        {"id": "b", "ch": "wb", "title": "지난 판정", "start": "2026-10-01", "judge": "2026-10-10", "criterion": "c", "formats": [], "owner": "pulse", "status": "running"},
        {"id": "c", "ch": "wb", "title": "로컬", "start": "2026-10-01", "judge": "2026-10-10", "criterion": "c", "formats": [], "owner": "local:x", "status": "running"},
        {"id": "d", "ch": "nt", "title": "시작 전", "start": "2026-11-01", "judge": "2026-10-21", "criterion": "c", "formats": [], "owner": "pulse", "status": "scheduled"}]})
    rows, ef = PU.exp_status(dt.date(2026, 10, 21), {"wb": {"_fby": {}}, "nt": {"_fby": {}}})
    ids = {f["id"]: f["level"] for f in ef}
    ck("판정 하루 전 = EXP_DUE(info) · 지난 판정(pulse) = warn · 로컬·시작 전은 안 띄움",
       ids == {"EXP_DUE:a": "info", "EXP_DUE:b": "warn"}, ids)
    PU.EXPERIMENTS = real
    ck("실제 실험 파일: 날짜·owner·형식 key 가 맞다", all(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["start"]) and (e["judge"] == "ongoing" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["judge"]))
        and (e["owner"] == "pulse" or e["owner"].startswith("local")) and e["ch"] in F
        and set(e["formats"]) <= {r["key"] for r in F[e["ch"]]["rules"]}
        for e in PU.load(PU.EXPERIMENTS)["experiments"]))

    print("── 수익화 진행(YPP) ──")
    realy = PU.YPP
    PU.YPP = os.path.join(td, "ypp.json")
    PU.save(PU.YPP, {"deadline": "2027-01-31", "tiers": [
        {"key": "fan", "label": "팬", "subs": 500, "uploads_90d": 3, "hours": 3000, "shorts": 3000000},
        {"key": "ads", "label": "광고", "subs": 1000, "hours": 4000, "shorts": 10000000}],
        "studio": {"wb": {"checked": "2026-10-14", "data_date": "2026-10-14", "subs": 400, "valid_shorts_90d": 1000000,
                          "valid_hours_365d": 600, "engaged_ratio": 0.5}}})
    ch_wb = PU.analyze_channel("wb", F["wb"], reg, PU.load(os.path.join(radar, "channels.json")), NOW)
    y, yf = PU.ypp_status(PU.load_ypp(), {"wb": ch_wb}, dt.date(2026, 10, 21))
    yw = y["wb"]
    after = sum(x["views"] for x in ch_wb["_main"] if x["d"] > "2026-10-14")
    ck("유효 Shorts 추정 = 스튜디오 값 + 유효 비율 × 그 뒤 조회", yw["valid"] == round(1000000 + 0.5 * after), (yw["valid"], after))
    ck("유효 하루 속도 = 유효 비율 × 최근 평균", yw["pace"] == round(0.5 * ch_wb["window"]["cur"]))
    ck("구독: 채널 스냅숏(499) · 하루 증감은 채널 스냅숏에서", yw["subs"] == 495 and yw["srate"] == -1.0, (yw["subs"], yw["srate"]))
    ids = {f["id"] for f in yf}
    fan = yw["tiers"][0]
    ck("구독이 줄면 구독 예상일은 없다(속도 음수)", fan["subs_eta"] is None and fan["eta_date"] is None)
    cap_ok = 90 * yw["pace"] >= 10_000_000
    ck("90일 최대(90 × 하루 유효)가 기준보다 작으면 YPP_PACE", ("YPP_PACE:wb:ads" in ids) == (not cap_ok), (yw["pace"], ids))
    PU.save(os.path.join(td, "ypp_dir", "studio.json"), {"studio": {"wb": {"checked": "2026-10-20", "data_date": "2026-10-19", "subs": 1200,
                                                                         "valid_shorts_90d": 12000000, "valid_hours_365d": 700, "engaged_ratio": 0.4}}})
    cal = PU.load_ypp(os.path.join(td, "ypp_dir"))
    ck("data/ypp 의 스튜디오 값이 더 새로우면 그것을 쓴다", cal["studio"]["wb"]["subs"] == 1200)
    ch_wb["subs"] = None
    y2, yf2 = PU.ypp_status(cal, {"wb": ch_wb}, dt.date(2026, 10, 21))
    ck("구독·유효 Shorts 둘 다 넘으면 YPP_READY(광고·팬 둘 다)", {"YPP_READY:wb:ads", "YPP_READY:wb:fan"} <= {f["id"] for f in yf2},
       [f["id"] for f in yf2])
    ck("기준 충족 문구", PU.ypp_when(y2["wb"]["tiers"][1]).startswith("기준 충족"))
    PU.YPP = realy
    real = PU.load(PU.YPP)
    ck("실제 YPP 파일: 두 단계 · 마감 · 유효 비율 0~1", [t["key"] for t in real["tiers"]] == ["fan", "ads"]
       and real["deadline"] == "2027-01-31" and 0 < real["studio"]["wb"]["engaged_ratio"] < 1)

    print("── fill.json 검사 ──")
    day = os.path.join(out, DAY)
    good = {
        "date": DAY, "summary": "왕별이는 표 쇼츠로 상승, Nine Tails 는 업로드가 끊겨 하락.",
        "channels": {"wb": {"state": "상승 4일째", "evidence": ["하루 조회 32,000 · 그 전의 ×4"], "guess": ["표가 끈다"]},
                     "nt": {"state": "하락", "evidence": ["마지막 업로드 51시간 전"], "guess": []}},
        "direction": [{"topic": "표 쇼츠", "verdict": "맞다", "why": "조회의 대부분"}],
        "trends": ["시니어 운동 3.4배 강세"],
        "flags": {f["id"]: "대응" for f in P["flags"]},
        "actions": [{"what": "RULES 발행 확인", "who": "local", "when": "내일"}],
        "pr": None,
        "predictions": [{"text": "왕별이 내일 3만 이상", "metric": "views:wb", "op": ">=", "value": 30000},
                        {"text": "표 비율 50% 이상", "metric": "share:wb:month", "op": ">=", "value": 0.5}],
        "review": "10억은 무리였다 — 과한 예측",
    }
    ck("모범 fill 통과", not PU.check_fill(P, good, day), PU.check_fill(P, good, day))

    def bad(mut, word):
        f = copy.deepcopy(good)
        mut(f)
        es = PU.check_fill(P, f, day)
        return any(word in x for x in es), es

    for name, mut, word in [
        ("플래그 하나라도 대응이 빠지면 거부", lambda f: f["flags"].pop("CH_DOWN:nt"), "빠짐"),
        ("없는 플래그 거부", lambda f: f["flags"].update({"CH_UP:nt": "x"}), "오늘 없는"),
        ("숫자 없는 근거 거부(추측으로)", lambda f: f["channels"]["wb"]["evidence"].append("표 쇼츠가 잘 된다"), "숫자"),
        ("채널 하나 빠지면 거부", lambda f: f["channels"].pop("nt"), "channels"),
        ("판정 말은 세 가지만", lambda f: f["direction"][0].update(verdict="좋다"), "direction"),
        ("예측이 없으면 거부", lambda f: f.update(predictions=[]), "predictions"),
        ("모르는 지표 거부", lambda f: f["predictions"].append({"text": "구독 천", "metric": "likes:wb", "op": ">=", "value": 1}), "predictions"),
        ("없는 형식 지표 거부", lambda f: f["predictions"].append({"text": "x 형식", "metric": "share:wb:nope", "op": ">=", "value": 1}), "predictions"),
        ("어제 채점이 있으면 review 필수", lambda f: f.pop("review"), "review"),
        ("날짜가 다르면 거부", lambda f: f.update(date="2026-10-20"), "date"),
        ("할 일 담당은 정해진 것만", lambda f: f["actions"].append({"what": "x 하기", "who": "boss", "when": "-"}), "actions"),
    ]:
        ok, es = bad(mut, word)
        ck(name, ok, es)

    print("── PR 제안 ──")
    good_pr = dict(good, pr={"slug": "pol-slot-check", "title": "정치 카드 편성 손질", "why": "정치 카드가 사흘째 평소 절반 미만",
                             "evidence": ["FMT_COLD:wb:pol"], "revert": "이 PR 을 revert"})
    ok_patch = ("diff --git a/tools/pulse_formats.json b/tools/pulse_formats.json\n--- a/tools/pulse_formats.json\n"
                "+++ b/tools/pulse_formats.json\n@@ -1 +1 @@\n-a\n+b\n")
    ck("pr 이 있는데 pr.patch 가 없으면 거부", any("pr.patch" in x for x in PU.check_fill(P, good_pr, day)))
    with open(os.path.join(day, "pr.patch"), "w", encoding="utf-8") as f:
        f.write(ok_patch)
    ck("3일째 플래그 근거 + 허용 경로 patch → 통과", not PU.check_fill(P, good_pr, day), PU.check_fill(P, good_pr, day))
    ck("pr 이 null 인데 patch 가 남아 있으면 거부", any("null" in x for x in PU.check_fill(P, good, day)))
    one_day = copy.deepcopy(good_pr)
    one_day["pr"]["evidence"] = ["CH_UP:wb"]
    ck("하루짜리 신호로는 PR 금지", any("3일 이상" in x for x in PU.check_fill(P, one_day, day)), PU.check_fill(P, one_day, day))
    for path in (".github/workflows/shorts.yml", "pipeline/secrets/token.json", "tools/pulse.py", "output/news/x.json", "tools/PULSE.md"):
        with open(os.path.join(day, "pr.patch"), "w", encoding="utf-8") as f:
            f.write(ok_patch.replace("tools/pulse_formats.json", path))
        ck(f"patch 가 {path} 를 건드리면 거부", any("건드리면 안 되는" in x for x in PU.check_fill(P, good_pr, day)))
    with open(os.path.join(day, "pr.patch"), "w", encoding="utf-8") as f:
        f.write(ok_patch.replace("-a\n+b\n", "".join(f"+l{i}\n" for i in range(PU.PATCH_MAX_LINES + 1))))
    ck("400줄 넘는 patch 거부", any("줄 이하" in x for x in PU.check_fill(P, good_pr, day)))
    with open(os.path.join(day, "pr.patch"), "w", encoding="utf-8") as f:
        f.write(ok_patch)
    PU.save(os.path.join(day, "fill.json"), good_pr)
    ck("check: 통과하면 report.md·page.html 생성", not PU.check(day) and os.path.exists(os.path.join(day, "page.html")))
    page = open(os.path.join(day, "page.html"), encoding="utf-8").read()
    ck("페이지: 제목 '채널 맥박' 이 맨 앞 · 다크 모드 토큰 · 비교 링크",
       page.startswith("<title>채널 맥박</title>") and 'prefers-color-scheme:dark' in page and ':root[data-theme="dark"]' in page
       and "compare/main...pulse/2026-10-21-pol-slot-check" in page)
    ck("페이지: 수익화까지(진행 막대)", "수익화까지" in page and 'class="meter"' in page)
    ck("페이지: 근거/추측 표시 · 신호마다 대응", "근거</span>" in page and "추측</span>" in page and page.count('class="resp"') == len(P["flags"]))
    ck("PR 브랜치 = pulse/<날짜>-<slug>", PU.pr_field(day, "branch") == "pulse/2026-10-21-pol-slot-check")
    body = PU.pr_field(day, "body")
    ck("PR 본문: 근거 플래그·되돌리기·보고서 링크·서명", "FMT_COLD:wb:pol" in body and "revert" in body
       and "routine/pulse/output/pulse/2026-10-21/report.md" in body and "Generated with [Claude Code]" in body)
    ck("verify-pr: 숫자를 다시 내도 근거가 3일째 → 통과", not PU.verify_pr(day, radar), PU.verify_pr(day, radar))
    P_t = PU.load(os.path.join(day, "pulse.json"))
    for f in P_t["flags"]:
        f["days"] = 9
    PU.save(os.path.join(day, "pulse.json"), P_t)
    fake = copy.deepcopy(good_pr)
    fake["pr"]["evidence"] = ["SUBS_DOWN:wb"]
    PU.save(os.path.join(day, "fill.json"), fake)
    ck("verify-pr: 루틴이 pulse.json 의 며칠째를 부풀려도 다시 낸 숫자로 막는다", PU.verify_pr(day, radar), "통과해 버림")

print("── 워크플로·안내서 ──")
wf = open(os.path.join(ROOT, ".github", "workflows", "pulse.yml"), encoding="utf-8").read()
push = [ln for ln in wf.splitlines() if "git" in ln and " push" in ln and not ln.strip().startswith("#")]
ck("트리거 = routine/pulse 의 output/pulse 만 · 코드는 main", '- "routine/pulse"' in wf and '- "output/pulse/**"' in wf and "ref: main" in wf)
ck("push 는 한 줄 · pulse/<날짜>-<slug> 브랜치로만(main·routine/* 아님)",
   len(push) == 1 and 'HEAD:refs/heads/$BR"' in push[0] and "BR=$(python tools/pulse.py pr" in wf, push)
ck("PR 전에: 다시 검사 → 근거 재확인 → 모든 테스트 → push", wf.index("pulse.py check") < wf.index("verify-pr")
   < wf.index("bash tools/run_tests.sh") < wf.index('git push origin "HEAD:refs/heads/$BR"'))
ck("열린 맥박 PR 이 있으면 새로 안 만든다 · 수동 실행은 PR 안 만든다", "grep '^pulse/'" in wf and "github.event_name == 'push'" in wf)
ck("어떤 다른 워크플로도 pulse/** push 에 반응하지 않는다(업로드가 깨어나지 않게)", not any(
    re.search(r'^\s*-\s*"?(pulse/|\*\*|pulse/\*\*)"?\s*$', ln) for n in os.listdir(os.path.join(ROOT, ".github", "workflows"))
    for ln in open(os.path.join(ROOT, ".github", "workflows", n), encoding="utf-8").read().splitlines()))
guide = open(os.path.join(HERE, "PULSE.md"), encoding="utf-8").read()
ck("안내서: fill.json 키·금지 경로·PR 조건이 코드와 같다", all(k in guide for k in ("summary", "evidence", "guess", "direction", "predictions", "review"))
   and all(p in guide for p in (".github/", "output/", "pipeline/secrets/")) and "3일 이상" in guide and "400줄" in guide)

print()
if FAIL:
    print(f"❌ 실패 {FAIL}건")
    sys.exit(1)
print("✅ 전부 통과")
