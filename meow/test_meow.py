"""Meow Remix 오프라인 검사(네트워크·Spark·ffmpeg 없이).

    python meow/test_meow.py
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import sys

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

t = P.publish_times(3, 45, dt.datetime(2026, 11, 7, 3, 0, tzinfo=dt.timezone.utc))
ck("예약 공개 = 20분 뒤부터 45분 간격", t == ["2026-11-07T03:20:00Z", "2026-11-07T04:05:00Z", "2026-11-07T04:50:00Z"], str(t))

print(f"\n{'❌ 실패 ' + str(fails) + '개' if fails else '✅ 전부 통과'}")
sys.exit(1 if fails else 0)
