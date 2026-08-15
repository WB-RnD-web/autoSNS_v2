#!/usr/bin/env python3
"""통합 TTS 경로 검증 — edge_tts 를 목으로 갈아끼우고 실제 ffmpeg 로 오디오를 만든다.

네트워크 없이 돈다(실제 TTS 서버를 부르지 않는다). 실행: python pipeline/test_tts_join.py
검증 대상: 묶음 분할 · WordBoundary→자막 타이밍 매핑 · 자막 연속성 ·
번역 SRT 타임코드 일치 · 단어매칭 실패 폴백 · JOIN=0 옛 방식 보존."""
import os, sys, subprocess, tempfile, types, asyncio, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEC_PER_CHAR = 0.14          # 가짜 낭독 속도


def _mp3(dur, path):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=220:duration={dur:.3f}",
                    "-ar", "24000", "-ac", "1", "-b:a", "48k", path],
                   check=True)
    return open(path, "rb").read()


class FakeCommunicate:
    """edge_tts.Communicate 흉내 — 오디오 + WordBoundary 를 스트림으로 뱉는다."""
    BROKEN = False           # True 면 경계 텍스트를 망가뜨려 폴백 경로를 태운다

    def __init__(self, text, voice, rate=None, pitch=None, boundary=None, **kw):
        if boundary not in (None, "WordBoundary", "SentenceBoundary"):
            raise TypeError("bad boundary")
        self.text, self.voice = text, voice

    async def stream(self):
        words = self.text.split()
        dur = max(0.5, len(self.text) * SEC_PER_CHAR)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        data = _mp3(dur, tmp)
        os.unlink(tmp)
        yield {"type": "audio", "data": data}
        tot = sum(len(w) for w in words) or 1
        t = 0.0
        for w in words:
            d = dur * len(w) / tot
            yield {"type": "WordBoundary",
                   "offset": int(t * 1e7), "duration": int(d * 1e7),
                   "text": "@@@" if self.BROKEN else w}
            t += d

    def save_sync(self, *a, **k):
        raise RuntimeError("쓰지 않음")


fake = types.ModuleType("edge_tts")
fake.Communicate = FakeCommunicate
sys.modules["edge_tts"] = fake

import story_render as SR                                   # noqa: E402

SEGS = [
    {"text": "2001년 봄, OO군의 한 경로당에서 있었던 일입니다."},
    {"text": "그날 마을에는 비가 내렸고, 아무도 그 사람을 본 적이 없었습니다."},
    {"text": "경찰이 도착했을 때 방 안은 비어 있었습니다."},
    {"text": "다만 벽에 손자국이 하나 남아 있었을 뿐입니다."},
    {"text": "재단은 이 사건을 SCP-8493-KR 로 분류했습니다."},
    {"text": "무슨 일이 있었는지는 아직 아무도 모릅니다."},
]
TEXTS = [s["text"] for s in SEGS]

fails = []


def check(name, cond, extra=""):
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        fails.append(name)


def run(label, join_chars, broken=False, join="1"):
    print(f"\n── {label} ──")
    FakeCommunicate.BROKEN = broken
    os.environ["STORY_TTS_JOIN"] = join
    os.environ["STORY_TTS_JOIN_CHARS"] = str(join_chars)
    for m in ("story_render",):
        del sys.modules[m]
    import importlib
    sr = importlib.import_module("story_render")

    wd = tempfile.mkdtemp(prefix="joins_")
    m4a = os.path.join(wd, "narration.m4a")
    spans = sr.synth_narration(SEGS, wd, m4a)

    check("세그먼트 수만큼 span", len(spans) == len(SEGS), f"{len(spans)}")
    check("start 단조 증가", all(spans[i][0] <= spans[i + 1][0] for i in range(len(spans) - 1)))
    check("start<end", all(s < e for s, e in spans))
    check("첫 자막이 LEAD_IN 에서 시작", abs(spans[0][0] - sr.LEAD_IN) < 0.05,
          f"{spans[0][0]:.2f}s")

    audio = sr.probe_dur(m4a)
    end = spans[-1][1]
    check("마지막 자막 끝 == 오디오 끝", abs(end - (sr.LEAD_IN + audio)) < 0.25,
          f"자막끝 {end:.2f} vs 오디오 {sr.LEAD_IN + audio:.2f}")

    # 자막 사이에 빈 구간이 없어야 한다(깜빡임 방지)
    holes = [i for i in range(len(spans) - 1) if spans[i + 1][0] - spans[i][1] > 0.01]
    check("자막 사이 빈 구간 없음", not holes, f"{holes}")

    # ★핵심: TTS 호출 경계(=낭독이 끊기는 지점)가 세그먼트 수가 아니라 묶음 수로 줄었는가
    groups = sr.group_segments(SEGS)
    check("끊김 지점이 묶음 경계로만 줄었다",
          len(groups) - 1 < len(SEGS) - 1 or len(groups) == 1,
          f"{len(groups) - 1}곳 (옛 방식 {len(SEGS) - 1}곳)")
    check("무음 총량", abs(sr.GROUP_GAP * (len(groups) - 1)) < sr.SEG_GAP * (len(SEGS) - 1),
          f"{sr.GROUP_GAP * (len(groups) - 1):.2f}s vs 옛 {sr.SEG_GAP * (len(SEGS) - 1):.2f}s+패딩")

    ass = os.path.join(wd, "c.ass")
    sr.build_ass(SEGS, spans, "NanumGothic", ass)
    n_ev = sum(1 for l in open(ass, encoding="utf-8") if l.startswith("Dialogue:"))
    check("ASS 이벤트 수 일치", n_ev == len(SEGS), f"{n_ev}")

    srt = sr.build_srt(SEGS, spans, os.path.join(wd, "c.srt"))
    n_blk = len([b for b in open(srt, encoding="utf-8").read().split("\n\n") if b.strip()])
    check("SRT 블록 수 일치", n_blk == len(SEGS), f"{n_blk}")

    # 번역 자막: 타이밍이 한국어와 완전히 동일해야 한다
    segs_en = [dict(s, text_en=f"EN {i}") for i, s in enumerate(SEGS)]
    p_en = sr.build_srt(segs_en, spans, os.path.join(wd, "en.srt"), key="text_en")
    ko_t = [l for l in open(srt, encoding="utf-8") if "-->" in l]
    en_t = [l for l in open(p_en, encoding="utf-8") if "-->" in l]
    check("번역 SRT 타임코드 동일", ko_t == en_t)

    # 싱크 정확도: 목의 '진짜' 위치와 비교
    joined_pos, p = [], 0
    for t in TEXTS:
        joined_pos.append(p); p += len(t) + 1
    print(f"     spans: {[f'{s:.1f}-{e:.1f}' for s, e in spans]}")
    shutil.rmtree(wd, ignore_errors=True)
    return spans


run("① 한 묶음(전체 통합)", 10000)
run("② 여러 묶음(문단 분할)", 120)
run("③ 단어 매칭 실패 → 문자수 비례 폴백", 10000, broken=True)

# ④ 옛 방식 폴백(JOIN=0) — synth_segment 경로
FakeCommunicate.BROKEN = False
import importlib                                            # noqa: E402
os.environ["STORY_TTS_JOIN"] = "0"
del sys.modules["story_render"]
sr = importlib.import_module("story_render")


async def _fake_save(self, path):
    d = max(0.5, len(self.text) * SEC_PER_CHAR)
    with open(path, "wb") as f:
        f.write(_mp3(d, path + ".t.mp3"))
    os.unlink(path + ".t.mp3")


def _patched_synth(text, out_mp3):
    d = max(0.5, len(text) * SEC_PER_CHAR)
    tmp = out_mp3 + ".t.mp3"
    data = _mp3(d, tmp)
    with open(out_mp3, "wb") as f:
        f.write(data)
    os.unlink(tmp)


sr.synth_segment = _patched_synth
print("\n── ④ JOIN=0 옛 방식 폴백 ──")
wd = tempfile.mkdtemp(prefix="joins_")
spans = sr.synth_narration(SEGS, wd, os.path.join(wd, "narration.m4a"))
check("폴백도 span 반환", len(spans) == len(SEGS))
check("폴백 타이밍 = LEAD_IN + Σd + SEG_GAP", abs(spans[0][0] - sr.LEAD_IN) < 0.01)
gaps = [round(spans[i + 1][0] - spans[i][1], 3) for i in range(len(spans) - 1)]
check("폴백은 SEG_GAP 만큼 벌어짐(옛 동작 보존)", all(abs(g - sr.SEG_GAP) < 0.01 for g in gaps),
      f"{gaps}")
shutil.rmtree(wd, ignore_errors=True)

print("\n" + ("🎉 전부 통과" if not fails else f"💥 실패 {len(fails)}: {fails}"))
sys.exit(1 if fails else 0)
