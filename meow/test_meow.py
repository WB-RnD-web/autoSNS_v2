"""Meow Remix 오프라인 검사(네트워크·Spark·ffmpeg 없이).

    python meow/test_meow.py
"""
from __future__ import annotations

import base64
import datetime as dt
import glob
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import post as P  # noqa: E402
import render as R  # noqa: E402

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
b = R.v14_body(png, "the kitten blinks, static camera", 7)
ck("14B 요청 = model i2v-14b · 720×1280 · 81장 · mp4 · 글 손질 없음 · 그림 base64",
   b["type"] == "video" and b["model"] == "i2v-14b" and (b["width"], b["height"], b["length"]) == (720, 1280, 81)
   and b["format"] == "mp4" and b["no_llm"] is True and b["speed"] in ("fast", "quality")
   and base64.b64decode(b["image"]) == b"\x89PNG fake", str({k: v for k, v in b.items() if k != "image"}))
ck("14B 판단은 응답 model 로(5B 로 돌면 아님)", R.is_14b({"model": "Wan2.2-I2V-A14B"}) and not R.is_14b(
    {"model": "wan2.2-ti2v-5b-i2v"}) and not R.is_14b({}))
pb = R.post_body({"job_id": "j1", "height": 1280}, None)
ck("후처리: 720p 면 RIFE ×2 만 · from_job", pb == {"type": "video_post", "interpolate": "rife", "multiplier": 2,
                                                  "from_job": "j1"}, str(pb))
pb = R.post_body({"job_id": "j1", "height": 1024}, png)
ck("후처리: 640급이면 SeedVR2 로 1280 까지 · 캐시된 클립은 파일째", pb.get("upscale") == "seedvr2"
   and pb.get("target_height") == 1280 and "from_job" not in pb and "video" in pb)
ck("후처리 스위치는 기본 꺼짐(서버에 아직 없음)", os.environ.get("MEOW_VIDEO_POST") == "1" or not R.video_post_on())

# gen: 응답이 5B 면 첫 컷에서 멈추고, 14B 면 원본·응답을 남긴다(Spark 없이 가짜 _job)
calls = []


def fake_job(model):
    def job(body, out, timeout=1500):
        calls.append(body)
        if out:
            with open(out, "wb") as f:
                f.write(b"x")
        return {"status": "done", "job_id": f"j{len(calls)}", "model": model if body["type"] == "video" else "z-image",
                "height": 1280}
    return job


R.WORK, R.quiet_hours = tmp, (lambda now=None: False)
cg = {**ok14, "id": "t1", "slug": "t"}
R._job = fake_job("wan2.2-ti2v-5b-i2v")
try:
    R.gen(cg)
    stopped = False
except SystemExit as e:
    stopped = "14B 아직 안 열림" in str(e)
d = os.path.join(tmp, "t1_t")
ck("5B 로 돌면 첫 컷에서 멈추고 14B 원본으로 남기지 않는다", stopped and not os.path.exists(os.path.join(d, "shot1_raw.mp4"))
   and os.path.exists(os.path.join(d, "shot1_not14b.mp4")) and len(calls) == 2)
os.environ.pop("MEOW_VIDEO_POST", None)
calls.clear()
R._job = fake_job("wan2.2-i2v-a14b")
R.gen(cg)
ck("14B 면 컷마다 원본+응답 json · 그림은 다시 안 뽑는다(캐시)", all(os.path.exists(os.path.join(d, f"shot{i}_raw{x}"))
   for i in (1, 2) for x in (".mp4", ".json")) and [b["type"] for b in calls] == ["video", "image", "video"], str(
    [b["type"] for b in calls]))
calls.clear()
os.environ["MEOW_VIDEO_POST"] = "1"
R.gen(cg)
os.environ.pop("MEOW_VIDEO_POST")
ck("스위치를 켜면 캐시된 원본에 후처리만(파일째) · build 는 후처리본을 쓴다",
   [b["type"] for b in calls] == ["video_post", "video_post"] and all("video" in b for b in calls)
   and R.clip_path(cg, 1).endswith("shot1_post.mp4"))

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
