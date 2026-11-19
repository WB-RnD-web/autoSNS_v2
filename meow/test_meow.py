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
import subprocess
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
ck("화면 자막에서 이모지 빼기(글꼴에 없어 네모로 나온다 · 11/19)",
   R.wrap("The big tree just lit up 🎄") == ["The big tree just lit", "up"] or R.wrap("The big tree just lit up 🎄") == ["The big tree", "just lit up"],
   str(R.wrap("The big tree just lit up 🎄")))
ck("이모지만 빼고 글자·문장부호는 그대로", R.screen_text("Slap fight finals 🥊") == "Slap fight finals"
   and R.screen_text("Last-minute ⚽ penalty") == "Last-minute penalty" and R.screen_text("Wait… 5:59 PM?!") == "Wait… 5:59 PM?!"
   and R.screen_text("❤️ love") == "love", R.screen_text("❤️ love"))

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

# ── ★11/14 첫 1초: 결말 미리 보기(마지막 컷에서 첫 화면과 가장 다른 순간을 맨 앞에) ──
fgt = R.filtergraph({**c14, "caption": "First snow ever", "track": "funkorama.mp3"}, 4, 1.6)
ck("미리 보기: 입력 2번(마지막 컷 한 번 더)을 1.6초부터 TEASE 만큼 잘라 본편 앞에 붙이고 · 음악은 입력 3번 · 길이 = 본편 + TEASE",
   "[2:v]trim=1.6:2.4," in fgt and "[vt][a1]concat=n=2" in fgt and "[3:a]atrim=0:" + str(round(R.total(c14) + R.TEASE, 3)) in fgt
   and fgt.index("[vtz]drawtext") > fgt.index("[vt][a1]"), fgt[-700:])
_td = tempfile.mkdtemp()


def _clip(name, colors):
    """색이 바뀌는 시험 클립(색마다 1초 · 64×112)."""
    out = os.path.join(_td, name)
    ins = []
    for col in colors:
        ins += ["-f", "lavfi", "-i", f"color=c={col}:s=64x112:d=1:r=16"]
    subprocess.run([R.ffmpeg(), "-v", "error", "-y", *ins, "-filter_complex",
                    "".join(f"[{k}:v]" for k in range(len(colors))) + f"concat=n={len(colors)}:v=1:a=0,format=yuv420p[v]",
                    "-map", "[v]", out], check=True)
    return out


_a, _b, _s = _clip("a.mp4", ["black", "black"]), _clip("b.mp4", ["black", "white"]), _clip("s.mp4", ["black", "black"])
ck("가장 다른 순간(1초에 하얗게)부터 자른다 · 클립 끝을 넘으면 당긴다(1.6초 클립 → 0.8)",
   R.tease_at(_a, _b, 2.0, 1.0) == 1.0 and R.tease_at(_a, _b, 1.6, 1.0) == 0.8,
   str([R.tease_at(_a, _b, 2.0, 1.0), R.tease_at(_a, _b, 1.6, 1.0)]))
ck("첫 화면과 다를 게 없으면(정지) 미리 보기를 끈다", R.tease_at(_a, _s, 2.0, 1.0) is None)
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


built = []
R.images, R.clips, R.build = mk_images, mk_clips, (lambda c, beats=None: built.append(beats) or
                                                   {"stem": R.stem(c), "sec": 9.5, "video": "v.mp4"})
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


# 11/10 처럼 예전 규칙(두 번이면 막음)으로 막힌 편: 다시 돌리면 걸린 클립만 단순한 움직임으로 한 번 더
old_c = one("d6")["concepts"][0]
mk_images(old_c)
mk_clips(old_c)
D.save_state(old_c, {"fixes": {"2": {"vseed": 500 + 2 + D.BUMP}}, "stills": {"shots": []}, "clips_bad": [2],
                     "clips": {"clips": [{"clip": 2, "ok": False, "issues": ["extra limb"]}]},
                     "clips2": {"clips": [{"clip": 2, "ok": False, "issues": ["extra limb"]}]}, "blocked": "클립2: extra limb"})
cl_calls.clear()
log.clear()
Q.review_clips = lambda c, which=None, cl=None: (cl_calls.append(which) or
                                                {"clips": [{"clip": i, "ok": True, "issues": []} for i in which or [1, 2]]})
code = D.render(one("d6"))
st = D.load_state(old_c)
ck("예전 규칙으로 막힌 편도 다시 돌리면 걸린 클립만 단순한 움직임으로 한 번 더 → 통과하면 나간다(0)",
   code == 0 and log == ["clip2"] and cl_calls == [[2]] and "blocked" not in st and st["clips_calm"] == [2]
   and st["fixes"]["2"]["motion"] == D.CALM_MOTION and st["fixes"]["2"]["vseed"] == 500 + 2 + 2 * D.BUMP,
   f"{code} {log} {cl_calls} {st}")
log.clear()
ck("세 번째까지 해 본 막힌 편은 그대로 3(다시 안 만든다)", D.render(one("d2")) == 3 and log == [])


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
# ★11/19 효과 편: 검수가 끝난 뒤 순간 찾기(비전) 한 번 → build(beats=) · 다시 돌아도 다시 안 묻는다 · 실패면 None(움직임)
fxb = {**base, "shots": [base["shots"][0], {**base["shots"][1], "sfx": ["slap"], "beat": "the paw lands", "hit": True}]}
asked_beats = []
real_fb = Q.find_beats
Q.find_beats = lambda c, cl=None: asked_beats.append(R.beat_shots(c)) or {"beats": {"2": 1.4}, "usd": 0.01}
built.clear()
_d = {"date": "2026-11-10", "concepts": [copy.deepcopy({**fxb, "id": "fx1"})]}
_r1 = D.render(_d)
_r2 = D.render(_d)
ck("효과 편: 순간 찾기(컷 2만) → build(beats={'2': 1.4}) · 두 번째 실행은 저장된 순간을 그대로", _r1 == 0 and _r2 == 0
   and asked_beats == [[2]] and built == [{"2": 1.4}, {"2": 1.4}], str([asked_beats, built]))
Q.find_beats = lambda c, cl=None: None
built.clear()
_d = {"date": "2026-11-10", "concepts": [copy.deepcopy({**fxb, "id": "fx2"})]}
ck("순간 찾기 실패면 beats 없이 build(움직임으로 대신)", D.render(_d) == 0 and built == [None], str(built))
built.clear()
ck("효과 없는 편은 순간 찾기를 안 부른다", D.render(one("fx3")) == 0 and built == [None] and asked_beats == [[2]])
Q.find_beats = real_fb
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

_wk = [dt.date(2026, 11, d) for d in range(9, 16)]
ck("하루 최대 12편: 편 a 는 매일 변신 · b 부터는 밈·춤·게임·변신을 요일로 — 바로 이웃한 편은 꼴이 다르다 · 넷 다 나온다",
   [PA.fmt_of(d) for d in _wk] == ["morph"] * 7 and len(PA.SLOTS) == 12
   and all(PA.fmt_of(d, x) != PA.fmt_of(d, y) for d in _wk for x, y in zip(PA.SLOTS[1:], PA.SLOTS[2:]))
   and all({PA.fmt_of(d, x) for x in PA.SLOTS} == set(PA.CYCLE) for d in _wk),
   str([[PA.fmt_of(d, x) for x in PA.SLOTS] for d in _wk]))
ck("파일·id: 편 a 는 예전 그대로(<날짜>.json · m261110) · b·c 는 -b·-c",
   PA.doc_name(dt.date(2026, 11, 10)) == "2026-11-10" and PA.doc_name(dt.date(2026, 11, 10), "c") == "2026-11-10-c"
   and PA.concept_id(dt.date(2026, 11, 10), "b") == "m261110b"
   and len({PA.seed_of(dt.date(2026, 11, 10), x) for x in PA.SLOTS}) == len(PA.SLOTS))
ck("변신 날 음악은 cute·morph 곡만 · 밈 날은 전부", "funkorama.mp3" not in PA.tracks_for("morph")
   and "fluffing-a-duck.mp3" in PA.tracks_for("morph") and set(PA.tracks_for("meme")) == set(T))
ck("id·seed 는 날짜로(다시 돌려도 같다)", PA.concept_id(dt.date(2026, 11, 10)) == "m261110"
   and PA.seed_of(dt.date(2026, 11, 10)) == PA.seed_of(dt.date(2026, 11, 10)) and 10000 <= PA.seed_of(dt.date(2026, 11, 10)) < 100000)
pdir = tempfile.mkdtemp()
ex = R.load(PA.EXAMPLE)["concept"]
tue, mon = dt.date(2026, 11, 13), dt.date(2026, 11, 9)      # 이름은 예전 그대로 — tue = 11/13(금) 편 b = 밈
SB = "b"
fresh = {**copy.deepcopy(ex), "slug": "kitten-first-umbrella", "title": "Kitten Meets Her First Umbrella ☔🐱"}
good = PA.finalize(fresh, tue, SB)
ck("예시를 새 소재로 바꾼 편은 매일판 검사 통과 · 코드가 id·꼴·engine·seed 를 넣는다",
   PA.check(good, tue, pdir, set(), SB) == [] and good["id"] == "m261113b" and good["format"] == "meme"
   and good["engine"] == "14b", str(PA.check(good, tue, pdir, set(), SB)))
ck("예시 그대로(이미 쓴 소재)는 막는다", any("이미 쓴" in x for x in PA.check(PA.finalize(ex, tue, SB), tue, pdir, set(), SB)))


def errs_of(day=tue, seen=frozenset(), slot=SB, **kw):
    c = copy.deepcopy(good)
    for k, v in kw.items():
        if k == "shot2":
            c["shots"][1] = v
        else:
            c[k] = v
    return " ".join(PA.check(PA.finalize(c, day, slot), day, pdir, set(seen), slot))


s2 = good["shots"][1]
ck("2컷째가 image 면 막는다(같은 고양이 = edit)", "edit" in errs_of(shot2={"image": "a kitten in snow", "motion": s2["motion"]}))
ck("edit 는 'Keep exactly the same' 로 시작", "Keep exactly" in errs_of(shot2={**s2, "edit": "Move the kitten outside."}))
ck("변신 편(a)에 춤 곡은 막는다", "허용 곡" in errs_of(day=mon, slot="a", track="funkorama.mp3"))
_e = errs_of(caption="This caption is definitely far too long ok")
ck("자막 40자·두 줄 넘으면 막는다", "caption" in _e or "자막" in _e, _e)
ck("ko_line 은 한국어", "ko_line" in errs_of(ko_line="first snow"))
ck("hashtags 에 #cat 없으면 막는다", "hashtags" in errs_of(hashtags=["#고양이", "#kitten", "#snow", "#cute"]))
ev = {"why_now": "x", "pattern": "y", "evidence": [{"title": "t", "url": "https://example.com/a"}]}
ck("검색에 없던 근거 주소는 막는다 · 검색에 나온 주소는 된다", "evidence" in errs_of(trend=ev)
   and "evidence" not in errs_of(trend=ev, seen={"https://example.com/a"}))
with open(os.path.join(pdir, "2026-11-12-b.json"), "w", encoding="utf-8") as fh:
    json.dump({"date": "2026-11-12", "concepts": [{**good, "slug": "yday", "title": "Y", "track": "investigations.mp3"}]}, fh)
ck("어제 같은 편(b)과 같은 곡은 막는다", "어제" in errs_of(track="investigations.mp3"))
ck("어제 편 b 소재도 '이미 쓴' 목록에 들어간다", any(h["slug"] == "yday" for h in PA.history(pdir)))
um = PA.user_message(tue, pdir, SB)
ck("모델에게 가는 글 = 오늘 꼴·허용 곡·쓴 곡·예시·이미 쓴 소재", "format: meme" in um and "Short #2 of the day" in um
   and "Tracks already used (do not use): investigations.mp3" in um and "first-snow-kitten" in um
   and '"edit": "Keep exactly the same' in um, um[:300])


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
info = PA.write(tue, pdir, client=fc, slot=SB)
saved = R.load(os.path.join(pdir, "2026-11-13-b.json"))
ck("API: 읽기 실패면 오류를 붙여 다시 → 통과한 편을 저장(render.py 가 읽는 모양) · 편 b 는 -b 파일", info["ok"] and info["tries"] == 2
   and saved["concepts"][0]["id"] == "m261113b" and R.check(saved) == [] and "code checks failed" in str(fc.calls[1]["messages"][-1])
   and os.path.exists(os.path.join(pdir, "2026-11-13-b_api.json")) and info["usd"] > 0, str(info))
um_c = PA.user_message(tue, pdir, "c")
ck("편 c 는 오늘 앞 편(b)의 곡을 못 쓰고 그 편을 보고 다르게 쓴다", "merry-go.mp3" in PA.avoid_tracks(pdir, tue, "c")
   and "Kitten Meets Her First Umbrella" in um_c.split("## Today's other Shorts")[1].split("##")[0]
   and "앞 편" in errs_of(slot="c", track="merry-go.mp3"))
ck("API: 웹 검색·읽기 도구 · effort 설정", {t["name"] for t in fc.calls[0]["tools"]} == {"web_search", "web_fetch"}
   and fc.calls[0]["extra_body"]["output_config"]["effort"] == PA.EFFORT)
info = PA.write(dt.date(2026, 11, 12), pdir, client=_Client(["x", "y", "z"]))
sk = R.load(os.path.join(pdir, "2026-11-12.json"))
ck("API: 세 번 다 못 넘으면 그날은 skip(틀린 편을 만들지 않는다)", not info["ok"] and sk["concepts"] == [] and "skip" in sk)

ck("매일판 인스타 캡션 = 한국어·영어 한 줄 · 해시태그 · 음악 credit · AI 표시 · 2200자 안 / 쓰레드 500자 안",
   all(x in P.ig_caption(good) for x in (good["ko_line"], good["en_line"], "#cat", "CC BY 4.0", "AI"))
   and len(P.ig_caption(good)) <= 2200 and len(P.threads_text(good)) <= 500 and "Kevin MacLeod" in P.threads_text(good))

# 하루 편이 많아 그 꼴 곡이 동나면 오래된 겹침부터 풀어 한 곡은 남긴다 — 바로 앞 편 곡은 끝까지 피한다
mdir = tempfile.mkdtemp()
_m16 = dt.date(2026, 11, 16)                              # 월: a 변신 · b 밈 · c 춤 · d 게임 · e 변신
for _s, _t in zip("abcd", ["fluffing-a-duck.mp3", "merry-go.mp3", "funkorama.mp3", "monkeys-spinning-monkeys.mp3"]):
    with open(os.path.join(mdir, PA.doc_name(_m16, _s) + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"date": "2026-11-16", "concepts": [{**good, "id": "x" + _s, "slug": "s" + _s, "track": _t}]}, fh)
_av = PA.avoid_tracks(mdir, _m16, "e")
ck("변신 곡 3곡을 앞 편들이 다 썼으면 가장 오래된 것(a 의 곡)은 풀고 · 바로 앞 편(d) 곡은 그대로 피한다",
   PA.fmt_of(_m16, "e") == "morph" and "fluffing-a-duck.mp3" not in _av and "monkeys-spinning-monkeys.mp3" in _av
   and set(PA.tracks_for("morph")) - set(_av), str(_av))

# ── 조용한 시간이 곧 끝나면 기다렸다 바로(06~07시에 시작한 실행) ──
_kst = lambda h, m: dt.datetime(2026, 11, 13, h, m, tzinfo=R.KST)  # noqa: E731
_slept, _stub = [], R.quiet_hours
R.quiet_hours = REAL_QUIET
ck("06:30 에 시작하면 08:00 까지(약 90분) 기다렸다 바로 시작",
   R.wait_quiet(120, _kst(6, 30), sleep=_slept.append) is True and 5400 <= _slept[-1] <= 5460, str(_slept))
ck("조용한 시간이 아니면(09:00) · 너무 오래 남았으면(05:30 → 150분) 기다리지 않는다",
   R.wait_quiet(120, _kst(9, 0), sleep=_slept.append) is False and R.wait_quiet(120, _kst(5, 30), sleep=_slept.append) is False
   and len(_slept) == 1)
R.quiet_hours = _stub

# ── 인스타·쓰레드에 올릴 편 고르기(post.py pick) — 11/11~13 0편 사고 ──
qdir = tempfile.mkdtemp()
for _d, _id, _sl in (("2026-11-11", "m261111", "pepero"), ("2026-11-12", "m261112", "buns"), ("2026-11-13", "m261113", "chess")):
    with open(os.path.join(qdir, f"{_d}.json"), "w", encoding="utf-8") as fh:
        json.dump({"date": _d, "concepts": [{**good, "id": _id, "slug": _sl}]}, fh)
with open(os.path.join(qdir, "2026-11-13-b.json"), "w", encoding="utf-8") as fh:
    json.dump({"date": "2026-11-13", "concepts": [{**good, "id": "m261113b", "slug": "bee"}]}, fh)
_now = dt.datetime(2026, 11, 13, 4, 0, tzinfo=dt.timezone.utc)          # 13:00 KST
_p, _why = P.pick(qdir, {}, now=_now)
ck("★11/15 최근 2일(어제·오늘) 편 중 안 올린 것을 유튜브 공개 순서로 — 오래된 날부터(11/11 은 창 밖)",
   _p and _p.endswith("2026-11-12.json"), f"{_p} {_why}")
_old = {"m261112_buns": {"ig": "1", "threads": "2", "at": "2026-11-12T20:00:00Z"}}
_p, _ = P.pick(qdir, _old, now=_now)
ck("어제 편을 올렸으면 오늘 편 a", _p and _p.endswith("2026-11-13.json"), str(_p))
_old["m261113_chess"] = {"ig": "3", "threads": "4", "at": "2026-11-13T00:00:00Z"}
_p, _ = P.pick(qdir, _old, now=_now)
ck("★11/15 편 a 다음은 같은 날 편 b(편 a 만 가던 것 고침)", _p and _p.endswith("2026-11-13-b.json"), str(_p))
ck("--slots 'a' 면 예전처럼 편 a 만(편 b 는 고르지 않는다)", P.pick(qdir, _old, now=_now, slots="a")[0] is None)
_p, _ = P.pick(qdir, {}, now=_now, has_out=lambda st: st != "m261112_buns")
ck("완성본이 없는 편(렌더 실패·검수에 막힘)은 건너뛰고 다음 편", _p and _p.endswith("2026-11-13.json"), str(_p))
_led = {"m261112_buns": {"ig": "1", "threads": "2", "at": "2026-11-13T02:30:00Z"}}
ck("마지막 게시 뒤 1.75시간 안이면 쉰다(몰아 올리지 않게)", P.pick(qdir, _led, now=_now)[0] is None)
_p, _ = P.pick(qdir, _led, now=_now + dt.timedelta(hours=0.5))
ck("1.75시간 지나면(매시 예약의 두 번째 = 약 2시간 간격) 다음 안 올린 편", _p and _p.endswith("2026-11-13.json"), str(_p))
ck("최근 2일 밖(11/16 에 11/14 이전)은 고르지 않는다",
   P.pick(qdir, {}, now=dt.datetime(2026, 11, 16, 4, 0, tzinfo=dt.timezone.utc))[0] is None)
ck("인스타만 올라가고 쓰레드가 실패한 편은 다시 고른다(쓰레드만 마저)",
   (P.pick(qdir, {"m261112_buns": {"ig": "1"}}, now=_now)[0] or "").endswith("2026-11-12.json"))
ck("편 이름: a = <날짜>.json · b~ = <날짜>-b.json(meow-daily 와 같다) · 편 목록 = matrix",
   P.plan_name("2026-11-13", "a") == "2026-11-13.json" and P.plan_name("2026-11-13", "l") == "2026-11-13-l.json"
   and P.SLOTS.split() == list("abcdefghijkl"))

# ── 매일판 공개 시각 · 다른 채널 막기 ──
utc = dt.timezone.utc
ck("매일판 공개 = 기획 날짜 10:00 KST(= 01:00 UTC) · '32:00' 은 다음 날 08:00 KST(하루 12편의 끝 편)",
   P.slot_at("2026-11-10", "10:00") == dt.datetime(2026, 11, 10, 1, 0, tzinfo=utc)
   and P.slot_at("2026-11-10", "32:00") == dt.datetime(2026, 11, 10, 23, 0, tzinfo=utc))
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
    def __init__(self, title, handle, cid="UCnew"):
        self.t, self.h, self.c = title, handle, cid

    def channels(self):
        return self

    def list(self, **k):
        return _Ex({"items": [{"id": self.c, "snippet": {"title": self.t, "customUrl": self.h},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})

    def playlistItems(self):
        return types.SimpleNamespace(list=lambda **k: _Ex({"items": [{"snippet": {"description": "Meow Remix · 2026-11-10 m261110"}}]}))


try:
    P.uploaded_text(_YT("왕별이", "@wangbyul"))
    wrong_ok = True
except SystemExit:
    wrong_ok = False
ck("토큰이 다른 채널(왕별이)이면 멈춘다", not wrong_ok)
_cid = P.CHANNEL_ID


def _stops(yt):
    try:
        P.uploaded_text(yt)
        return False
    except SystemExit:
        return True


P.CHANNEL_ID = "UCnew"
ck("★11/14 새 고양이 채널(id)이면 최근 업로드 설명을 읽는다 · 옛 채널(이름이 같아도)·다른 채널이면 멈춘다",
   "m261110" in P.uploaded_text(_YT("Meow Remix Cats", "@x", "UCnew"))
   and _stops(_YT("Meow Remix Cats", "@meowremixcats", P.OLD_CHANNEL_ID)) and _stops(_YT("Meow Remix", "@x", "UCother")))
P.CHANNEL_ID = ""
ck("새 채널 id 가 비어 있으면 아무 데도 안 올린다", _stops(_YT("Meow Remix Cats", "@x", "UCnew")))
P.CHANNEL_ID = _cid
ck("seen: 남았으면 10(오류 1 과 구별)", P.NOT_YET == 10)


# ── ★11/19 효과(효과음·순간·hit·컷 자막) ──
LIB = R.sfx_lib()
ck("효과음 파일이 전부 있고 · 출처마다 작성자·라이선스·주소 · CC0 아니면 CC BY 4.0 만",
   all(os.path.exists(os.path.join(R.SFX_DIR, x["file"])) for x in list(LIB["sounds"].values()) + list(LIB["ambience"].values()))
   and set(LIB["sources"]) == {x["file"] for x in list(LIB["sounds"].values()) + list(LIB["ambience"].values())}
   and all(v["author"] and v["url"].startswith("https://opengameart.org/") and v["license"] in ("CC0", "CC BY 4.0")
           for v in LIB["sources"].values()))
fxc = {**okE, "id": "f1", "slug": "f", "format": "game", "title": "T", "seed": 1, "caption": "Slap fight finals",
       "en_line": "a", "ko_line": "가", "hashtags": ["#cat"], "tags": ["cat"],
       "track": "funkorama.mp3", "ambience": "crowd",
       "shots": [{**okE["shots"][0], "sfx": ["whoosh"], "beat": "the swing passes"},
                 {**okE["shots"][1], "sfx": ["slap", "punch"], "beat": "the paw lands", "hit": True, "caption": "ONE PAW. 🥊"}]}
ck("효과 편 모양은 검사 통과", R.check_concept(fxc) == [], str(R.check_concept(fxc)))


def fx_errs(**kw):
    c = copy.deepcopy(fxc)
    for k, v in kw.items():
        if k.startswith("s"):
            c["shots"][int(k[1:]) - 1].update(v)
        else:
            c[k] = v
    return " ".join(R.check_concept(c))


ck("모르는 효과음·3개 이상·beat 없는 효과음·hit 두 컷·첫 컷 caption·25자 컷 자막·모르는 배경 소리는 막는다",
   "모르는 sfx" in fx_errs(s1={"sfx": ["boing"]}) and "0~2개" in fx_errs(s1={"sfx": ["slap", "punch", "thud"]})
   and "beat" in fx_errs(s1={"beat": ""}) and "hit 는 한 컷만" in fx_errs(s1={"hit": True})
   and "컷1" in fx_errs(s1={"caption": "x"}) and "컷 caption" in fx_errs(s2={"caption": "x" * 25})
   and "ambience" in fx_errs(ambience="rain"))
ck("효과 판단: 효과 칸이 하나라도 있으면 켬 · MEOW_FX=0 이면 끔 · 예전 편은 끔",
   R.fx_on(fxc) and not R.fx_on(okE) and R.beat_shots(fxc) == [1, 2])
os.environ["MEOW_FX"] = "0"
ck("MEOW_FX=0 이면 효과·표기 없음(예전 조립)", not R.fx_on(fxc) and R.sfx_credit(fxc) == "")
os.environ.pop("MEOW_FX")
ev = R.fx_events(fxc, {1: 2.0, 2: 0.5}, R.TEASE)
p14 = R.plan(fxc)
ck("효과음 시각 = 미리 보기 0.8 + 컷 시작 + 순간 − lead(휙은 0.15초 먼저) · 배경 소리는 0초",
   ev[0] == ("crowd.mp3", 0.0, 0.22) and ev[1] == ("whoosh.wav", round(0.8 + 2.0 - 0.15, 3), 0.9)
   and ev[2] == ("slap.wav", round(0.8 + p14[1]["start"] + 0.5, 3), 1.0) and ev[3][0] == "punch.wav", str(ev))
fgx = R.filtergraph(fxc, 2 + 1 + 1 + len(ev), 1.6, {1: 2.0, 2: 0.5}, ev)
ck("효과 조립: 음악은 미리 보기 다음 입력(3번)·반으로 줄임 · 효과음은 4번부터 adelay · 모두 섞고 리미터",
   "[3:a]atrim=0:" in fgx and f"volume={R.FX_MUSIC_VOL}" in fgx and "[4:a]aformat" in fgx and "adelay=2650:all=1" in fgx
   and f"amix=inputs={len(ev) + 1}" in fgx and "alimiter" in fgx, fgx[-900:])
ck("hit 컷(2)만 줌인·흔들림·번쩍 — 순간 0.5초에", fgx.count("eval=frame,crop=") == 1 and "[1:v]" in fgx.split("eq=brightness")[0]
   .rsplit(";", 1)[-1] and "between(t\\,0.5\\,0.58)" in fgx, fgx[:1500])
ck("hit 컷은 앞 컷과 겹치지 않고 바로 자른다(xfade 무시) · hit 아닌 컷은 예전처럼 겹친다",
   p14[1]["xfade"] == 0 and p14[1]["start"] == p14[0]["dur"] and "[v0][v1]concat" in fgx
   and R.plan({**fxc, "shots": [fxc["shots"][0], {**fxc["shots"][1], "hit": False, "xfade": 0.5}]})[1]["xfade"] == 0.5, str(p14))
cps = R.captions(fxc, R.TEASE)
ck("자막: 편 caption 은 0초~컷2 시작 · 컷2 자막(이모지 빼고)은 그다음부터 노란색",
   cps[0]["start"] == 0.0 and cps[0]["end"] == round(0.8 + p14[1]["start"], 3) and cps[1]["lines"] == ["ONE PAW."]
   and cps[1]["beat"] and cps[1]["end"] is None and "enable='lt(t" in fgx and "enable='gte(t" in fgx
   and R.SHOT_CAP_COLOR in fgx, str(cps))
ck("CC BY 소리(관중)를 쓰면 설명란·인스타·쓰레드에 표기 · CC0 만 쓰면 표기 없음",
   "Gregor Quendel" in R.sfx_credit(fxc) and "Gregor Quendel" in P.yt_meta({"date": "2026-11-19"}, fxc)["description"]
   and "Gregor Quendel" in P.ig_caption({**fxc, "ko_line": "가", "en_line": "a", "hashtags": ["#cat"]})
   and R.sfx_credit({**fxc, "ambience": None}) == "", R.sfx_credit(fxc))

# 순간 찾기(비전) — 가짜 클라이언트
import qa_api as Q  # noqa: E402,F811


class _Msg:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.usage = types.SimpleNamespace(input_tokens=3000, output_tokens=50)


class _Cl:
    def __init__(self, text):
        self.text, self.sent = text, []
        self.messages = types.SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.sent.append(kw)
        return _Msg(self.text)


ck("격자 칸 → 초(1칸 = 0.2초 · 12칸 = 4.6초)", Q.frame_sec(1) == 0.2 and Q.frame_sec(12) == 4.6)
_fd = tempfile.mkdtemp()
R.WORK = _fd
fcl = {**fxc, "id": "q1"}
os.makedirs(os.path.join(_fd, R.stem(fcl)), exist_ok=True)
for _i in (1, 2):
    subprocess.run([R.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=72x128:d=5:r=16", "-pix_fmt", "yuv420p",
                    R.clip_path(fcl, _i)], check=True)
cl = _Cl('{"beats": [{"clip": 1, "frame": 4}, {"clip": 2, "frame": 1}]}')
res = Q.find_beats(fcl, cl)
ck("순간 찾기: 효과 컷마다 12칸 격자 한 장 + 순간 설명 → {'1': 1.4, '2': 0.2}",
   res and res["beats"] == {"1": 1.4, "2": 0.2} and len([b for b in cl.sent[0]["messages"][0]["content"]
                                                         if b["type"] == "image"]) == 2
   and "the paw lands" in json.dumps(cl.sent[0]["messages"][0]["content"]), str(res))
ck("답에 컷이 빠지거나 칸이 범위 밖이면 None(움직임으로 대신)",
   Q.find_beats(fcl, _Cl('{"beats": [{"clip": 1, "frame": 4}]}')) is None
   and Q.find_beats(fcl, _Cl('{"beats": [{"clip": 1, "frame": 13}, {"clip": 2, "frame": 1}]}')) is None)
ck("효과 컷이 없으면 묻지 않는다", Q.find_beats({**okE, "id": "q2", "slug": "q", "title": "T"}, _Cl("{}")) is None)

# 진짜 ffmpeg 로 효과 편 조립(짧은 시험 클립 · 미리 보기 · 효과음 · hit · 컷 자막) — 그래프가 실제로 도는지
fb = {**fcl, "shots": [{**fcl["shots"][0], "sec": 1.5}, {**fcl["shots"][1], "sec": 1.5}]}
for _i in (1, 2):
    subprocess.run([R.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=72x128", "-frames:v", "1",
                    R.shot_png(fb, _i)], check=True)
_out = R.OUT
R.OUT = tempfile.mkdtemp()
try:
    m = R.build(fb, beats={"1": 0.6, "2": 0.4})
    okb = os.path.getsize(m["video"]) > 0 and m["fx"]["beats"] == {"1": 0.6, "2": 0.4} and m["fx"]["beat_src"] == "vision"
    r = subprocess.run([R.ffmpeg(), "-i", m["video"]], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    okb = okb and "Audio:" in r and "1080x1920" in r
    m2 = R.build(fb)
    okb = okb and m2["fx"]["beat_src"] == "motion" and set(m2["fx"]["beats"]) == {"1", "2"}
except (subprocess.CalledProcessError, SystemExit, OSError) as e:
    okb, r = False, str(e)
ck("진짜 조립: 효과음·hit·컷 자막 편이 1080×1920 + 소리로 나온다 · 순간이 없으면 움직임으로", okb, r[-600:])
R.OUT = _out

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
