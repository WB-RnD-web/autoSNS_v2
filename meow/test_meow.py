"""Meow Remix 오프라인 검사(네트워크·Spark·ffmpeg 없이).

    python meow/test_meow.py
"""
from __future__ import annotations

import base64
import datetime as dt
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import post as P  # noqa: E402
import render as R  # noqa: E402

REAL_JOB = R._job                  # 아래에서 가짜로 바꾸기 전에 진짜를 잡아 둔다
REAL_QUIET = R.quiet_hours

fails = 0


def ck(name: str, ok: bool, extra: str = ""):
    global fails
    print(("✅ " if ok else "❌ ") + name + (f" — {extra}" if extra and not ok else ""))
    fails += 0 if ok else 1


# ── 음악: 파일·라이선스 ──
T = R.tracks()
ck("tracks.json 의 곡 파일이 전부 있다", all(os.path.exists(os.path.join(R.MUSIC, f)) for f in T), str(T))
ck("음악 폴더에 tracks.json 에 없는 곡이 없다",
   {os.path.basename(p) for p in glob.glob(os.path.join(R.MUSIC, "*.mp3"))} == set(T))
ck("credit 줄 = 곡 제목 · 작곡가 · CC BY 4.0 링크", all(
    t["title"] in R.credit(f) and "Kevin MacLeod" in R.credit(f) and "creativecommons.org/licenses/by/4.0" in R.credit(f)
    for f, t in T.items()))

# ── 기획 파일 ──
for path in sorted(glob.glob(os.path.join(HERE, "concepts", "*.json"))):
    doc = R.load(path)
    errs = R.check(doc)
    ck(f"{os.path.basename(path)}: 검사 통과", not errs, "; ".join(errs[:5]))
    for c in doc["concepts"]:
        ck(f"{c['id']}: 길이 6~12초", 6 <= R.total(c) <= 12, str(R.total(c)))

# ── 검사가 막아야 하는 것 ──
bad = {"id": "x1", "slug": "x", "format": "morph", "track": "funkorama.mp3", "seed": 1, "caption": "hi",
       "title": "t", "en_line": "e", "ko_line": "k",
       "shots": [{"image": "a cat holding a phone with text on it", "motion": "moves"}] * 4}
e = R.check_concept(bad)
ck("금지어(phone·text)를 잡는다", any("phone" in x for x in e) and any("text" in x for x in e), str(e))
ck("motion 에 static camera 가 없으면 잡는다", any("static camera" in x for x in e))
ck("모르는 음악을 잡는다", any("음악" in x for x in R.check_concept({**bad, "track": "nope.mp3"})))
ck("자막 세 줄은 막는다", any("두 줄" in x for x in R.check_concept({**bad, "caption": "a very long caption that will " * 3})))

ck("자막 두 줄은 길이를 맞춘다(마지막 한 단어만 넘기지 않는다)",
   R.wrap("Wait… this bun has ears") == ["Wait…", "this bun has ears"] and R.wrap("Leg day? Never heard of it")
   == ["Leg day?", "Never heard of it"] and R.wrap("Me at 5:59 PM vs 6:00 PM") == ["Me at 5:59 PM", "vs 6:00 PM"],
   str([R.wrap("Wait… this bun has ears"), R.wrap("Me at 5:59 PM vs 6:00 PM")]))
ck("한 줄에 들어가면 한 줄 · 빈 자막은 빈 목록", R.wrap("When the beat drops") == ["When the beat drops"] and R.wrap("") == [])
ck("두 줄로 안 되면 세 줄(검사가 막는다)", len(R.wrap("a very long caption that will not fit in two short lines")) > 2)

# ── 조립 계획 ──
c = {"shots": [{}, {"xfade": 0.5}, {}, {"sec": 0.9}]}
p = R.plan(c)
ck("컷 길이 = 1.4초 × 1.2(느리게)", p[0]["dur"] == round(R.SHOT_SRC * R.SLOW, 3))
ck("xfade 컷은 앞 컷과 겹친다", p[1]["start"] == round(p[0]["dur"] - 0.5, 3))
ck("sec 를 주면 그 길이로 자른다", p[3]["dur"] == round(0.9 * R.SLOW, 3))
fg = R.filtergraph({**c, "caption": "When the beat drops", "track": "funkorama.mp3"}, 5)
ck("시간 단위를 맞춘다(concat 뒤 xfade 고장 방지)", fg.count("settb=1/30") >= 5)
ck("자막은 줄마다 가운데 drawtext", "cap0.txt" in fg and "(w-text_w)/2" in fg)
ck("음악은 영상 길이로 자르고 끝을 줄인다", "atrim=0:" in fg and "afade=t=out" in fg)

# ── 14b 엔진(스파크 Wan 2.2 I2V-14B · video_post) ──
c14 = {"engine": "14b", "shots": [{}, {"xfade": 0.6}]}
p = R.plan(c14)
ck("14b 컷 = 5초 그대로(늘리지 않음)", p[0]["dur"] == 5.0 and p[1]["start"] == 4.4, str(p))
fg = R.filtergraph({**c14, "caption": "First snow ever", "track": "funkorama.mp3"}, 3)
ck("14b 는 32fps(RIFE ×2 그대로·16fps 는 정확히 두 번씩)", "fps=32" in fg and "settb=1/32" in fg and "*1.0," in fg)
ok14 = {**bad, "engine": "14b", "shots": [{"image": "a kitten", "motion": "the kitten blinks, static camera"}] * 2}
ck("14b 견본 모양은 검사 통과", R.check_concept(ok14) == [], str(R.check_concept(ok14)))
ck("14b 는 컷 1~3개", any("컷 4개" in x for x in R.check_concept({**ok14, "shots": ok14["shots"] * 2})))
ck("모르는 engine 은 막는다", any("engine" in x for x in R.check_concept({**ok14, "engine": "7b"})))
ck("sec 가 클립보다 길면 막는다", any("sec" in x for x in R.check_concept(
    {**ok14, "shots": [{**ok14["shots"][0], "sec": 6}]})))
ck("engine 없으면 5b(11/07 견본 그대로)", R.engine({}) == "5b" and R.plan({"shots": [{}]})[0]["dur"] == round(1.4 * 1.2, 3))

tmp = tempfile.mkdtemp()
png = os.path.join(tmp, "a.png")
with open(png, "wb") as f:
    f.write(b"\x89PNG fake")
b = R.hd_body(png, "the kitten blinks, static camera", 7)
ck("HD 요청 = type video · hd true · 움직임 글 · seed · 그림 base64 (문서에 없는 키 없음)",
   set(b) == {"type", "hd", "prompt", "image", "seed"} and b["type"] == "video" and b["hd"] is True
   and b["seed"] == 7 and base64.b64decode(b["image"]) == b"\x89PNG fake", str({k: v for k, v in b.items() if k != "image"}))
ck("14B 판단은 응답 model 로(HD 이름엔 14b · 5B 로 돌면 아님)", R.is_14b(
    {"model": "wan2.2-i2v-14b-lightx2v4+seedvr2-3b+rife4.26"}) and not R.is_14b(
    {"model": "wan2.2-ti2v-5b-i2v"}) and not R.is_14b({}))

# 열 안전장치로 멈추면 쉬고 다시 · 횟수를 넘기면 포기 · 거절(4xx)은 다시 안 한다
n, slept = [0], []


def flaky(fails_before_ok):
    def job(body, out, timeout=1500):
        n[0] += 1
        ck_t.append(timeout)
        if n[0] <= fails_before_ok:
            raise R.SparkJobError("Spark 오류 video: 95C")
        return {"status": "done", "model": "x-14b"}
    return job


ck_t = []
R._job = flaky(2)
ok = R.hd_job({}, "x", sleep=slept.append)
ck("95°C 로 두 번 멈춰도 쉬고 다시 해서 받는다 · 한 컷 기다림 90분", ok["status"] == "done" and n[0] == 3
   and slept == [R.HD_RETRY_WAIT] * 2 and set(ck_t) == {R.HD_TIMEOUT} and R.HD_TIMEOUT >= 4800)
n[0], slept[:] = 0, []
R._job = flaky(9)
try:
    R.hd_job({}, "x", sleep=slept.append)
    gave_up = False
except R.SparkJobError:
    gave_up = True
ck("세 번 다 멈추면 포기(무한 반복 없음)", gave_up and n[0] == R.HD_RETRY + 1)


def reject(body, out, timeout=1500):
    n[0] += 1
    raise RuntimeError("Spark video 거절 HTTP 400")


n[0] = 0
R._job = reject
try:
    R.hd_job({}, "x", sleep=slept.append)
except RuntimeError:
    pass
ck("거절(HTTP 400)은 다시 보내지 않는다", n[0] == 1)

# _job: 게이트웨이가 다시 켜져 작업이 사라지면(404·status 없음) 다시 넣을 오류로 · 잠깐 끊김은 기다린다
class FakeResp:
    def __init__(self, code, js=None, content=b""):
        self.status_code, self._js, self.content, self.ok = code, js, content, code < 400

    def json(self):
        if self._js is None:
            raise ValueError("no json")
        return self._js


class FakeReq:
    class RequestException(Exception):
        pass

    def __init__(self, gets):
        self.gets = list(gets)

    def post(self, *a, **k):
        return FakeResp(200, {"job_id": "jx"})

    def get(self, url, **k):
        g = self.gets.pop(0)
        if isinstance(g, Exception):
            raise g
        return g


real_spark, real_sleep = R._spark, R.time.sleep
R._job = REAL_JOB
R.time.sleep = lambda s: None
for name, gets in [("404", [FakeResp(404, {"detail": "not found"})]), ("status 없음", [FakeResp(200, {"detail": "x"})])]:
    R._spark = lambda gets=gets: (FakeReq(gets), "http://x", {})
    try:
        R._job({"type": "video"}, None)
        lost = False
    except R.SparkJobError as e:
        lost = "사라짐" in str(e)
    ck(f"작업이 사라지면({name}) 다시 넣을 오류(SparkJobError)", lost)
fq = FakeReq([FakeReq.RequestException("reset"), FakeResp(502, None), FakeResp(200, {"status": "running"}),
              FakeResp(200, {"status": "done", "model": "m"}), FakeResp(200, None, b"MP4")])
R._spark = lambda: (fq, "http://x", {})
outp = os.path.join(tmp, "o.mp4")
info = R._job({"type": "video"}, outp)
ck("잠깐 끊김·502 는 기다렸다가 받는다", info["model"] == "m" and open(outp, "rb").read() == b"MP4")
R._spark = lambda: (FakeReq([FakeResp(200, {"status": "done"}), FakeResp(409, {"detail": "not yet"})]), "http://x", {})
try:
    R._job({"type": "video"}, outp + "2")
    bad = True
except R.SparkJobError:
    bad = os.path.exists(outp + "2")
ck("결과 받기가 200 이 아니면 오류 글을 mp4 로 저장하지 않는다", not bad)
class DownReq(FakeReq):
    def __init__(self, gets, post_exc=None, post_code=200):
        super().__init__(gets)
        self.post_exc, self.post_code = post_exc, post_code

    def post(self, *a, **k):
        if self.post_exc:
            raise self.post_exc
        return FakeResp(self.post_code, {"job_id": "jx"})


for name, fr in [("접수 연결 끊김", DownReq([], post_exc=FakeReq.RequestException("refused"))),
                 ("게이트웨이 503", DownReq([], post_code=503))]:
    R._spark = lambda fr=fr: (fr, "http://x", {})
    try:
        R._job({"type": "video"}, None)
        down = None
    except R.SparkDown as e:
        down = e
    ck(f"스파크가 꺼져 있으면({name}) SparkDown(종료 코드 75 · 조용한 시간과 같은 처리)",
       down is not None and down.code == 75 and isinstance(down, R.QuietHours))
R._spark = lambda: (DownReq([FakeReq.RequestException("reset")] * 3), "http://x", {})
try:
    R._job({"type": "video"}, None, down_after=0)
    down = False
except R.SparkDown:
    down = True
ck("작업을 넣은 뒤 계속 안 닿으면(down_after 동안) SparkDown — 잠깐 끊김은 위에서처럼 기다린다", down)
R._spark, R.time.sleep = real_spark, real_sleep

# gen: 응답이 5B 면 첫 컷에서 멈추고, 14B 면 클립·응답을 남긴다(Spark 없이 가짜 _job)
calls = []


def fake_job(model):
    def job(body, out, timeout=1500):
        calls.append(body)
        if out:
            with open(out, "wb") as f:
                f.write(b"x")
        return {"status": "done", "job_id": f"j{len(calls)}", "model": model if body["type"] == "video" else "z-image",
                "height": 1280, "fps": 32}
    return job


R.WORK, R.quiet_hours = tmp, (lambda now=None, ahead_min=0: False)
cg = {**ok14, "id": "t1", "slug": "t"}
R._job = fake_job("wan2.2-ti2v-5b-i2v")
try:
    R.gen(cg)
    stopped = False
except SystemExit as e:
    stopped = "14B 아님" in str(e)
d = os.path.join(tmp, "t1_t")
ck("5B 로 돌면 첫 컷에서 멈추고 14B 클립으로 남기지 않는다", stopped and not os.path.exists(os.path.join(d, "shot1_raw.mp4"))
   and os.path.exists(os.path.join(d, "shot1_not14b.mp4")) and [b["type"] for b in calls] == ["image", "image", "video"],
   str([b["type"] for b in calls]))
calls.clear()
R._job = fake_job("wan2.2-i2v-14b-lightx2v4+seedvr2-3b+rife4.26")
R.gen(cg)
ck("14B 면 컷마다 클립+응답 json · 그림은 다시 안 뽑는다(캐시) · 모든 영상 요청이 hd", all(
    os.path.exists(os.path.join(d, f"shot{i}_raw{x}")) for i in (1, 2) for x in (".mp4", ".json"))
   and [b["type"] for b in calls] == ["video", "video"] and all(b.get("hd") for b in calls if b["type"] == "video"),
   str([b["type"] for b in calls]))
calls.clear()
R.gen(cg)
ck("다시 돌리면 받은 클립은 건너뛴다 · build 는 그 클립을 쓴다", calls == [] and R.clip_path(cg, 1).endswith("shot1_raw.mp4"))

# ── 편집 컷(2컷째 = 1컷 그림 Qwen 편집 — 같은 고양이) ──
okE = {**ok14, "shots": [{"image": "a calico kitten on a windowsill", "motion": "the kitten blinks, static camera"},
                         {"edit": "Keep exactly the same calico kitten. Move it outdoors into snow.",
                          "motion": "the kitten looks up, static camera"}]}
ck("edit 컷 모양은 검사 통과", R.check_concept(okE) == [], str(R.check_concept(okE)))
ck("첫 컷이 edit 면 막는다", any("첫 컷은 image" in x for x in R.check_concept({**okE, "shots": [okE["shots"][1]] * 2})))
ck("image·edit 둘 다 있거나 둘 다 없으면 막는다", any("하나만" in x for x in R.check_concept(
    {**okE, "shots": [okE["shots"][0], {**okE["shots"][1], "image": "x"}]})) and any("하나만" in x for x in R.check_concept(
        {**okE, "shots": [okE["shots"][0], {"motion": "m, static camera"}]})))
ck("edit 지시문의 금지어도 잡는다", any("phone" in x for x in R.check_concept(
    {**okE, "shots": [okE["shots"][0], {**okE["shots"][1], "edit": "Keep the cat, add a phone"}]})))

ce = {**okE, "id": "e1", "slug": "e"}
de = os.path.join(tmp, "e1_e")
os.makedirs(de, exist_ok=True)
with open(os.path.join(de, "shot1.png"), "wb") as f:
    f.write(b"PNG1")
be = R.image_body(ce, 2, ce["shots"][1])
ck("편집 요청 = type image · 1컷 그림 base64 · edit 지시문 · seed(크기는 안 보냄 — 원본을 따른다)",
   set(be) == {"type", "image", "edit", "prompt", "seed"} and base64.b64decode(be["image"]) == b"PNG1"
   and be["edit"] == ce["shots"][1]["edit"] and be["seed"] == ce["seed"] + 2, str({k: v for k, v in be.items() if k != "image"}))
calls.clear()
fits = []
real_fit = R.fit_image


def fake_fit(src, dst, w, h):
    fits.append((os.path.basename(src), os.path.basename(dst), w, h))
    with open(dst, "wb") as fh:
        fh.write(b"FIT")


R.fit_image = fake_fit
R.images(ce)
ck("이미 있는 1컷 그림은 다시 안 그리고, 2컷 편집 결과는 720×1280 으로 맞춘다",
   [b["type"] for b in calls] == ["image"] and "edit" in calls[0] and fits == [("shot2_edit.png", "shot2.png", 720, 1280)],
   str(fits))
R.fit_image = real_fit

n[0], slept[:] = 0, []
R._job = flaky(2)
ck("그림 실패는 30초 쉬고 다시(최대 3번)", R.img_job({}, "x", sleep=slept.append)["status"] == "done" and slept == [30, 30])
R._job = fake_job("wan2.2-i2v-14b-lightx2v4+seedvr2-3b+rife4.26")


# ── 조용한 시간(05:45~08:00 KST) ──
def K(h, m):
    return dt.datetime(2026, 11, 10, h, m, tzinfo=R.KST)


R.quiet_hours = REAL_QUIET
ck("05:45~08:00 은 쉰다 · 08:00 부터 된다", R.quiet_hours(K(5, 45)) and R.quiet_hours(K(7, 59)) and not R.quiet_hours(K(8, 0)))
ck("HD(20분 앞)는 05:25 부터 새로 넣지 않는다 · 05:20 은 된다", R.quiet_hours(K(5, 30), 20) and not R.quiet_hours(K(5, 20), 20))
ck("자정 근처는 상관없다", not R.quiet_hours(K(23, 50), 20) and not R.quiet_hours(K(0, 40), 20))
ck("조용한 시간이면 종료 코드 75(실패 아님)", R.QuietHours().code == 75)
R.quiet_hours = lambda now=None, ahead_min=0: False

# ── 매일판 검수 흐름(daily.py) — Spark·API 없이 ──
import copy  # noqa: E402

import daily as D  # noqa: E402
import qa_api as Q  # noqa: E402

base = {**okE, "id": "d1", "slug": "dd", "format": "meme", "title": "T", "seed": 500}
log = []
real_fns = (R.images, R.clips, R.build, Q.review_stills, Q.review_clips)


def mk_images(c):
    for i, s in enumerate(c["shots"], 1):
        p = R.shot_png(c, i)
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(f"{s.get('image') or s.get('edit')}|{s.get('seed', c['seed'] + i)}")
            log.append(f"draw{i}")


def mk_clips(c):
    for i, s in enumerate(c["shots"], 1):
        p = R.clip_path(c, i)
        if not os.path.exists(p):
            with open(p, "w") as fh:
                fh.write(str(s.get("vseed", c["seed"] + i)))
            log.append(f"clip{i}")


def one(cid):
    return {"date": "2026-11-10", "concepts": [copy.deepcopy({**base, "id": cid})]}


R.images, R.clips, R.build = mk_images, mk_clips, (lambda c: {"stem": R.stem(c), "sec": 9.5, "video": "v.mp4"})
Q.review_stills, Q.review_clips = (lambda c, cl=None: None), (lambda c, which=None, cl=None: None)
ck("검수 키가 없으면 검수 없이 완성(0)", D.render(one("d1")) == 0 and log == ["draw1", "draw2", "clip1", "clip2"], str(log))

st_calls, cl_calls = [], []


def rs(c, cl=None):
    st_calls.append(1)
    if len(st_calls) == 1:
        return {"shots": [{"shot": 1, "ok": False, "issues": ["anatomy: five legs"], "fix": "a calico kitten with four legs"},
                          {"shot": 2, "ok": True, "issues": [], "fix": ""}], "usd": 0.01}
    return {"shots": [{"shot": i, "ok": True, "issues": [], "fix": ""} for i in (1, 2)], "usd": 0.01}


def rc(c, which=None, cl=None):
    cl_calls.append(which)
    return {"clips": [{"clip": i, "ok": i != 2, "issues": [] if i != 2 else ["melting: body stretches"]}
                      for i in which or [1, 2]], "usd": 0.01}


Q.review_stills, Q.review_clips = rs, rc
log.clear()
code = D.render(one("d2"))
st = R.load(os.path.join(tmp, "d2_dd", "qa.json"))
with open(R.shot_png({**base, "id": "d2"}, 1), encoding="utf-8") as fh:
    redrawn = fh.read()
ck("그림 검수에 걸린 1컷은 fix 글·새 seed 로 다시 · 그 그림을 편집한 2컷도 다시",
   st["fixes"]["1"]["text"] == "a calico kitten with four legs" and st["fixes"]["1"]["seed"] == 500 + 1 + D.BUMP
   and st["fixes"]["2"]["seed"] == 500 + 2 + D.BUMP and log.count("draw1") == 2 and log.count("draw2") == 2
   and len(st_calls) == 2 and redrawn == "a calico kitten with four legs|1501", str(st))
ck("영상 검수에 걸린 클립은 새 seed 로 다시 → 또 걸리면 동작을 줄여 마지막 한 번 → 그래도 걸리면 그날은 안 올린다(3)",
   code == 3 and "blocked" in st and cl_calls == [None, [2], [2]] and log.count("clip2") == 3 and log.count("clip1") == 1
   and st["fixes"]["2"]["vseed"] == 500 + 2 + 2 * D.BUMP and st["fixes"]["2"]["motion"] == D.CALM_MOTION
   and st["clips_calm"] == [2], f"{code} {cl_calls} {log}")
ck("마지막 한 번의 움직임 글도 검사 통과(static camera·금지어 없음)",
   R.check_concept({**okE, "shots": [okE["shots"][0], {**okE["shots"][1], "motion": D.CALM_MOTION}]}) == [])
log.clear()
ck("막힌 편은 다시 돌려도 바로 3(스파크·API 안 씀)", D.render(one("d2")) == 3 and log == [])


cl_calls.clear()


def rc_third_ok(c, which=None, cl=None):
    cl_calls.append(which)
    bad = len(cl_calls) < 3                      # 처음·두 번째는 클립 1 이 걸리고, 동작을 줄인 세 번째는 통과
    return {"clips": [{"clip": i, "ok": not (bad and i == 1), "issues": ["extra limb"] if bad and i == 1 else []}
                      for i in which or [1, 2]], "usd": 0.01}


Q.review_stills, Q.review_clips = (lambda c, cl=None: {"shots": [{"shot": i, "ok": True, "issues": [], "fix": ""}
                                                                  for i in (1, 2)]}), rc_third_ok
log.clear()
ck("동작을 줄인 세 번째가 통과하면 그날 편은 나간다(0)", D.render(one("d4")) == 0 and cl_calls == [None, [1], [1]]
   and log.count("clip1") == 3, f"{cl_calls} {log}")


def quiet_clips(c):
    raise R.QuietHours()


R.clips = quiet_clips
Q.review_stills, Q.review_clips = (lambda c, cl=None: None), (lambda c, which=None, cl=None: None)
ck("조용한 시간에 걸리면 75 · 받은 그림은 남는다", D.render(one("d3")) == 75 and os.path.exists(R.shot_png({**base, "id": "d3"}, 1)))
R.clips = mk_clips
log.clear()
ck("다음 실행이 받은 그림부터 이어서 완성(0)", D.render(one("d3")) == 0 and log == ["clip1", "clip2"], str(log))


def down_clips(c):
    raise R.SparkDown("시험")


R.clips = down_clips
ck("스파크가 꺼져 있으면(정전) 75 — 실패가 아니라 다음 실행이 잇는다", D.render(one("d5")) == 75)
R.clips = mk_clips
ck("기획이 skip 이면 아무것도 안 한다(0)", D.render({"date": "2026-11-11", "skip": "검사 실패", "concepts": []}) == 0)
ck("편집 원본을 다시 그리면 그 그림을 쓰는 편집 컷도 다시(이어서 편집한 것까지)",
   D.dependents({"shots": [{"image": "a"}, {"edit": "b"}, {"edit": "c", "from": 2}, {"image": "d"}]}, 1) == [2, 3])
R.images, R.clips, R.build, Q.review_stills, Q.review_clips = real_fns

rows = Q.parse('```json\n{"shots":[{"shot":1,"ok":false,"issues":["text: logo"],"fix":"x"},{"shot":2,"ok":true}]}\n```',
               "shots", {1, 2})
ck("검수 답 읽기(코드 울타리·빠진 칸 괜찮음)", rows[0]["ok"] is False and rows[1]["issues"] == []
   and [r["shot"] for r in Q.flagged({"shots": rows}, "shots")] == [1])
try:
    Q.parse('{"shots":[{"shot":1,"ok":true}]}', "shots", {1, 2})
    miss = False
except ValueError:
    miss = True
ck("답에 빠진 컷이 있으면 읽기 실패(→ 검수 없이 간다)", miss)
_key = os.environ.pop("ANTHROPIC_API_KEY", None)
ck("키가 없으면 검수하지 않는다(None)", Q.client() is None and Q.review_stills(base) is None)
if _key:
    os.environ["ANTHROPIC_API_KEY"] = _key

# ── 매일 기획(plan_api.py) — API 없이 ──
import types  # noqa: E402

import plan_api as PA  # noqa: E402

ck("꼴은 요일로(11/9 월 변신 · 11/10 화 밈 · 11/11 수 춤 · 11/13 금 게임)",
   [PA.fmt_of(dt.date(2026, 11, d)) for d in (9, 10, 11, 13)] == ["morph", "meme", "dance", "game"])
ck("변신 날 음악은 cute·morph 곡만 · 밈 날은 전부", "funkorama.mp3" not in PA.tracks_for("morph")
   and "fluffing-a-duck.mp3" in PA.tracks_for("morph") and set(PA.tracks_for("meme")) == set(T))
ck("id·seed 는 날짜로(다시 돌려도 같다)", PA.concept_id(dt.date(2026, 11, 10)) == "m261110"
   and PA.seed_of(dt.date(2026, 11, 10)) == PA.seed_of(dt.date(2026, 11, 10)) and 10000 <= PA.seed_of(dt.date(2026, 11, 10)) < 100000)
pdir = tempfile.mkdtemp()
ex = R.load(PA.EXAMPLE)["concept"]
tue, mon = dt.date(2026, 11, 10), dt.date(2026, 11, 9)
fresh = {**copy.deepcopy(ex), "slug": "kitten-first-umbrella", "title": "Kitten Meets Her First Umbrella ☔🐱"}
good = PA.finalize(fresh, tue)
ck("예시를 새 소재로 바꾼 편은 매일판 검사 통과 · 코드가 id·꼴·engine·seed 를 넣는다",
   PA.check(good, tue, pdir, set()) == [] and good["id"] == "m261110" and good["format"] == "meme" and good["engine"] == "14b",
   str(PA.check(good, tue, pdir, set())))
ck("예시 그대로(이미 쓴 소재)는 막는다", any("이미 쓴" in x for x in PA.check(PA.finalize(ex, tue), tue, pdir, set())))


def errs_of(day=tue, seen=frozenset(), **kw):
    c = copy.deepcopy(good)
    for k, v in kw.items():
        if k == "shot2":
            c["shots"][1] = v
        else:
            c[k] = v
    return " ".join(PA.check(PA.finalize(c, day), day, pdir, set(seen)))


s2 = good["shots"][1]
ck("2컷째가 image 면 막는다(같은 고양이 = edit)", "edit" in errs_of(shot2={"image": "a kitten in snow", "motion": s2["motion"]}))
ck("edit 는 'Keep exactly the same' 로 시작", "Keep exactly" in errs_of(shot2={**s2, "edit": "Move the kitten outside."}))
ck("변신 날 춤 곡은 막는다", "허용 곡" in errs_of(day=mon, track="funkorama.mp3"))
_e = errs_of(caption="This caption is definitely far too long ok")
ck("자막 40자·두 줄 넘으면 막는다", "caption" in _e or "자막" in _e, _e)
ck("ko_line 은 한국어", "ko_line" in errs_of(ko_line="first snow"))
ck("hashtags 에 #cat 없으면 막는다", "hashtags" in errs_of(hashtags=["#고양이", "#kitten", "#snow", "#cute"]))
ev = {"why_now": "x", "pattern": "y", "evidence": [{"title": "t", "url": "https://example.com/a"}]}
ck("검색에 없던 근거 주소는 막는다 · 검색에 나온 주소는 된다", "evidence" in errs_of(trend=ev)
   and "evidence" not in errs_of(trend=ev, seen={"https://example.com/a"}))
with open(os.path.join(pdir, "2026-11-09.json"), "w", encoding="utf-8") as fh:
    json.dump({"date": "2026-11-09", "concepts": [{**good, "slug": "yday", "title": "Y", "track": "investigations.mp3"}]}, fh)
ck("어제와 같은 곡은 막는다", "어제" in errs_of(track="investigations.mp3"))
ck("어제 편 소재는 '이미 쓴' 목록에 들어간다", any(h["slug"] == "yday" for h in PA.history(pdir)))
um = PA.user_message(tue, pdir)
ck("모델에게 가는 글 = 오늘 꼴·허용 곡·어제 곡·예시·이미 쓴 소재", "format: meme" in um
   and "Yesterday's track (do not use): investigations.mp3" in um and "first-snow-kitten" in um
   and '"edit": "Keep exactly the same' in um)


class _Msg:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.stop_reason = "end_turn"
        self.usage = types.SimpleNamespace(input_tokens=1000, output_tokens=500, cache_creation_input_tokens=0,
                                           cache_read_input_tokens=0,
                                           server_tool_use=types.SimpleNamespace(web_search_requests=2, web_fetch_requests=0))


class _Stream:
    def __init__(self, m):
        self.m = m

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.m


class _Client:
    def __init__(self, texts):
        self.texts, self.calls, self.messages = list(texts), [], self

    def stream(self, **kw):
        self.calls.append(kw)
        return _Stream(_Msg(self.texts.pop(0)))


out_c = {k: v for k, v in good.items() if k not in ("id", "format", "engine", "seed")}
out_c["track"] = "merry-go.mp3"
fc = _Client(["not json", json.dumps(out_c, ensure_ascii=False)])
info = PA.write(tue, pdir, client=fc)
saved = R.load(os.path.join(pdir, "2026-11-10.json"))
ck("API: 읽기 실패면 오류를 붙여 다시 → 통과한 편을 저장(render.py 가 읽는 모양)", info["ok"] and info["tries"] == 2
   and saved["concepts"][0]["id"] == "m261110" and R.check(saved) == [] and "code checks failed" in str(fc.calls[1]["messages"][-1])
   and os.path.exists(os.path.join(pdir, "2026-11-10_api.json")) and info["usd"] > 0, str(info))
ck("API: 웹 검색·읽기 도구 · effort 설정", {t["name"] for t in fc.calls[0]["tools"]} == {"web_search", "web_fetch"}
   and fc.calls[0]["extra_body"]["output_config"]["effort"] == PA.EFFORT)
info = PA.write(dt.date(2026, 11, 12), pdir, client=_Client(["x", "y", "z"]))
sk = R.load(os.path.join(pdir, "2026-11-12.json"))
ck("API: 세 번 다 못 넘으면 그날은 skip(틀린 편을 만들지 않는다)", not info["ok"] and sk["concepts"] == [] and "skip" in sk)

ck("매일판 인스타 캡션 = 한국어·영어 한 줄 · 해시태그 · 음악 credit · AI 표시 · 2200자 안 / 쓰레드 500자 안",
   all(x in P.ig_caption(good) for x in (good["ko_line"], good["en_line"], "#cat", "CC BY 4.0", "AI"))
   and len(P.ig_caption(good)) <= 2200 and len(P.threads_text(good)) <= 500 and "Kevin MacLeod" in P.threads_text(good))

# ── 매일판 공개 시각 · 다른 채널 막기 ──
utc = dt.timezone.utc
ck("매일판 공개 = 기획 날짜 10:00 KST(= 01:00 UTC)", P.slot_at("2026-11-10", "10:00") == dt.datetime(2026, 11, 10, 1, 0, tzinfo=utc))
ck("공개 시각이 아직이면 그 시각 · 지났으면 20분 뒤",
   P.publish_times(1, 45, dt.datetime(2026, 11, 9, 16, 0, tzinfo=utc), P.slot_at("2026-11-10", "10:00")) == ["2026-11-10T01:00:00Z"]
   and P.publish_times(1, 45, dt.datetime(2026, 11, 10, 2, 0, tzinfo=utc), P.slot_at("2026-11-10", "10:00"))
   == ["2026-11-10T02:20:00Z"])


class _Ex:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class _YT:
    def __init__(self, title, handle):
        self.t, self.h = title, handle

    def channels(self):
        return self

    def list(self, **k):
        return _Ex({"items": [{"snippet": {"title": self.t, "customUrl": self.h},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})

    def playlistItems(self):
        return types.SimpleNamespace(list=lambda **k: _Ex({"items": [{"snippet": {"description": "Meow Remix · 2026-11-10 m261110"}}]}))


try:
    P.uploaded_text(_YT("왕별이", "@wangbyul"))
    wrong_ok = True
except SystemExit:
    wrong_ok = False
ck("토큰이 다른 채널(왕별이)이면 멈춘다", not wrong_ok)
ck("고양이 채널(이름 바꾸기 전 Nine Tails Tales 포함)이면 최근 업로드 설명을 읽는다",
   "m261110" in P.uploaded_text(_YT("Nine Tails Tales", "@meowremixcats")) and "m261110" in P.uploaded_text(_YT("Meow Remix", "@x")))
ck("seen: 남았으면 10(오류 1 과 구별)", P.NOT_YET == 10)


# ── 올라갈 글 ──
doc = R.load(sorted(glob.glob(os.path.join(HERE, "concepts", "*.json")))[0])
for c in doc["concepts"]:
    md = P.yt_meta(doc, c)
    ok = (R.credit(c["track"]) in md["description"] and P.mark(doc, c) in md["description"]
          and "AI-generated" in md["description"] and "instagram" not in md["description"].lower())
    ck(f"{c['id']}: 유튜브 설명 = 음악 credit · AI 표시 · 중복 표식 · 인스타 태그 없음", ok)
    ck(f"{c['id']}: 인스타 캡션에 음악 credit · AI 표시 · 2200자 안", "CC BY 4.0" in P.ig_caption(c)
       and "AI" in P.ig_caption(c) and len(P.ig_caption(c)) <= 2200)
    ck(f"{c['id']}: 쓰레드 글 500자 안 · credit", len(P.threads_text(c)) <= 500 and "Kevin MacLeod" in P.threads_text(c))
    ck(f"{c['id']}: 유튜브 홍보·댓글 부탁 없음", not any(w in P.ig_caption(c) + P.threads_text(c)
                                                for w in ("youtube", "유튜브", "댓글", "구독", "팔로우")))

ck("업로드 메타에 'zxx' 오디오 언어가 없다(유튜브가 400 으로 거절)", '"zxx"' not in open(os.path.join(HERE, "post.py"), encoding="utf-8").read())
t = P.publish_times(3, 45, dt.datetime(2026, 11, 7, 3, 0, tzinfo=dt.timezone.utc))
ck("예약 공개 = 20분 뒤부터 45분 간격", t == ["2026-11-07T03:20:00Z", "2026-11-07T04:05:00Z", "2026-11-07T04:50:00Z"], str(t))

print(f"\n{'❌ 실패 ' + str(fails) + '개' if fails else '✅ 전부 통과'}")
sys.exit(1 if fails else 0)
