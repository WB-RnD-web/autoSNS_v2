#!/usr/bin/env python3
"""Korea Sleep Sounds — 해외 시청자용 8시간 '한국 풍경' 수면·공부 사운드 시리즈 (2026-09-27 시작).

왜 루틴이 아니라 코드인가:
  이 프로젝트에서 루틴에게 '~해라' 한 지시는 지켜지지 않았고, 날짜로 결정론적으로 배정한 것만 작동했다.
  앰비언트는 대본이 필요 없어 LLM 이 할 일도 없다 → 테마·문구를 여기 고정해 두고
  '날짜 → 몇 번째 슬롯 → 몇 번째 테마'로 배정한다. 루틴 사용량도 들지 않는다.

근거(2026-09-27 스튜디오 실측): ASMR 해외 시청자는 1회에 30~66분, 한국 시청자는 2~23분 봤다.
  ASMR 시청시간 절반 이상이 해외에서 나왔다. 그래서 기본 언어를 영어로 두고 한국어는 현지화로 붙인다.

일정: 매주 수·토 (korea-sounds.yml cron). 슬롯 = 2026-09-30(수)부터 센 반주(半週) 번호.
  수~금 → 그 주 첫 슬롯, 토~화 → 둘째 슬롯. 같은 날짜는 언제 돌려도 같은 테마다(재실행·ledger 안전).
  목록을 한 바퀴 돌면 제목에 'Vol. 2' 가 붙는다(같은 제목 반복 회피).

  python korea_sounds.py --date 2026-09-30 --out ../output/asmr     # 스펙 JSON 생성 → 경로 출력
  python korea_sounds.py --list                                     # 앞으로 16슬롯 일정
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import sys

START = dt.date(2026, 9, 30)          # 첫 슬롯(수)
HOURS = int(os.environ.get("KOREA_HOURS", "8"))
PLAYLIST = os.environ.get("KOREA_PLAYLIST", "Korea Sleep Sounds")

# 장면 프롬프트 공통 꼬리 — 사람·글자 없는 사진풍 16:9. ('sign' 같은 글자 낱말은 쓰지 않는다:
#   게이트웨이가 글자 모델로 돌린다 — wbspark.py 주석)
_TAIL = ("photorealistic, cinematic wide shot, soft natural light, calm and cozy mood, "
         "no people, 16:9 composition, highly detailed")

# 필드: id, en(장면 이름), hook(영어 제목 뒤쪽), ko(한국어 제목), ko_hook, emoji, motion,
#       mode, scene(배경 프롬프트), q(베드 쿼리), must(앵커), trig(트리거 쿼리·선택), gap(트리거 간격 초)
THEMES = [
    dict(id="hanok-rain", emoji="🌧️", motion="rain", mode="sleep",
         en="Rainy Night in a Korean Hanok", hook="Rain on Roof Tiles for Sleep",
         ko="한옥 처마 밑 빗소리", ko_hook="잠 잘 오는 한옥의 비 오는 밤",
         scene="Traditional Korean hanok courtyard at night in heavy rain, curved clay-tiled roof eaves "
               "dripping water, warm light glowing through paper lattice windows, wet stone path "
               "reflecting a small lantern, deep blue night",
         q=["rain on roof", "rain on tiles", "heavy rain night", "rain dripping gutter"], must=["rain"]),
    dict(id="jeju-waves", emoji="🌊", motion="lights", mode="sleep",
         en="Jeju Island Night Waves", hook="Ocean Sounds on Black Volcanic Rocks",
         ko="제주 밤바다 파도 소리", ko_hook="현무암 해변에 부서지는 파도",
         scene="Night seascape on Jeju Island, gentle waves washing over black volcanic basalt rocks, "
               "moonlight on the sea, distant fishing boat lights on the horizon, starry sky",
         q=["ocean waves rocks", "waves rocky shore", "sea waves night", "gentle ocean waves"],
         must=["wave", "waves", "ocean", "sea", "surf"]),
    dict(id="ondol-fire", emoji="🔥", motion="embers", mode="sleep",
         en="Wood Fire in a Korean Country House", hook="Crackling Fire Sounds on a Winter Night",
         ko="시골집 아궁이 장작불", ko_hook="겨울밤 타닥타닥 장작 타는 소리",
         scene="Inside an old Korean countryside house kitchen at night, a traditional clay wood-burning "
               "stove (agungi) with glowing crackling fire, iron cauldron on top, warm orange light on "
               "wooden beams and earthen walls, snow visible through a small window",
         q=["fireplace crackling", "wood fire burning", "campfire crackling", "wood stove fire"],
         must=["fire", "fireplace", "crackling", "campfire"]),
    dict(id="seoul-subway", emoji="🚇", motion="lights", mode="sleep",
         en="Late-Night Seoul Subway Ride", hook="Train Sounds for Sleep & Study",
         ko="늦은 밤 서울 지하철", ko_hook="덜컹거리는 열차 소리에 잠들기",
         scene="Empty Seoul subway car late at night, clean modern interior with long bench seats, "
               "soft fluorescent light, city lights streaking past the dark windows",
         q=["subway train interior", "train interior ambience", "metro ride", "train ride interior"],
         must=["train", "subway", "metro", "railway"]),
    dict(id="temple-snow", emoji="🏔️", motion="snow", mode="mixed", gap=[35, 95],
         en="Snowy Night at a Korean Mountain Temple", hook="Soft Wind & Distant Wind Chimes",
         ko="눈 내리는 산사의 밤", ko_hook="바람 소리와 멀리서 울리는 풍경",
         scene="Korean Buddhist mountain temple at night during gentle snowfall, colorful dancheong "
               "painted eaves covered with snow, a small bronze wind chime hanging from the roof corner, "
               "stone lanterns, pine trees, deep blue winter night",
         q=["winter wind night", "soft wind ambience", "cold wind mountain", "snow wind"],
         must=["wind"], trig=["wind chime", "small bell", "temple bell"]),
    dict(id="rice-field-summer", emoji="🐸", motion="fireflies", mode="sleep",
         en="Summer Night by a Korean Rice Field", hook="Frogs & Crickets Nature Sounds",
         ko="시골 논두렁 여름밤", ko_hook="개구리와 풀벌레 소리",
         scene="Korean countryside rice paddies on a summer night, reflections of a full moon in the "
               "flooded fields, a small old farmhouse with a warm light, fireflies, distant mountains",
         q=["frogs night", "frogs crickets night", "summer night insects", "night frogs pond"],
         must=["frog", "frogs", "crickets", "insects", "cicada"]),
    dict(id="library-rain", emoji="📚", motion="dust", mode="mixed", gap=[25, 70],
         en="Rainy Afternoon in a Korean Library", hook="Rain Sounds & Page Turning for Study",
         ko="비 오는 날 도서관", ko_hook="빗소리와 책장 넘기는 소리",
         scene="Quiet old Korean library reading room on a rainy afternoon, tall wooden bookshelves, "
               "a reading desk with an open book and a desk lamp, large window with raindrops, "
               "soft gray daylight",
         q=["rain on window", "rain window indoor", "rain against glass", "light rain indoor"],
         must=["rain"], trig=["page turn", "book page turning", "paper page"]),
    dict(id="busan-harbor", emoji="⚓", motion="lights", mode="sleep",
         en="Busan Harbor at Night", hook="Water Lapping & Distant Boats",
         ko="부산항의 밤", ko_hook="잔잔한 물결과 먼 뱃소리",
         scene="Busan harbor at night, fishing boats moored along a calm pier, colorful city lights on "
               "the hills reflecting on the dark water, a bridge glowing in the distance",
         q=["harbor ambience night", "water lapping boats", "port ambience", "marina water lapping"],
         must=["harbor", "harbour", "port", "boat", "boats", "marina"]),
    dict(id="pojangmacha-rain", emoji="☔", motion="rain", mode="sleep",
         en="Rain on a Seoul Street Food Tent", hook="Rain on Tarp Sounds for Sleep",
         ko="포장마차 비닐 위 빗소리", ko_hook="비 오는 서울 골목의 밤",
         scene="A cozy orange Korean street food tent (pojangmacha) on a rainy Seoul night, rain running "
               "down the clear plastic walls, warm light inside, steam rising, wet neon-lit alley",
         q=["rain on tarp", "rain on tent", "rain canvas", "rain on plastic"], must=["rain"]),
    dict(id="bamboo-forest", emoji="🎋", motion="dust", mode="sleep",
         en="Wind in a Korean Bamboo Forest", hook="Rustling Leaves for Deep Sleep",
         ko="담양 대나무 숲 바람", ko_hook="대숲을 스치는 바람 소리",
         scene="Dense green bamboo forest in Damyang, Korea, tall bamboo stalks swaying, soft sunbeams "
               "through the leaves, a narrow stone path, morning mist",
         q=["bamboo forest wind", "wind in trees", "forest wind leaves", "leaves rustling wind"],
         must=["wind", "bamboo", "leaves", "forest"]),
    dict(id="seoul-cafe", emoji="☕", motion="dust", mode="mixed", gap=[20, 60],
         en="Quiet Seoul Café", hook="Coffee Shop Ambience for Study & Focus",
         ko="조용한 서울 카페", ko_hook="공부·집중용 카페 소리",
         scene="Cozy small café in Seoul on a rainy evening, wooden tables, warm pendant lights, "
               "an espresso cup and an open notebook, rain-streaked window with blurred street lights",
         q=["cafe ambience", "coffee shop ambience", "cafe quiet murmur", "coffee shop background"],
         must=["cafe", "coffee", "restaurant"], trig=["coffee cup", "cup saucer", "spoon cup"]),
    dict(id="han-river-night", emoji="🌉", motion="lights", mode="sleep",
         en="Han River at Night", hook="Calm River Sounds for Sleep",
         ko="한강의 밤", ko_hook="잔잔한 강물 소리",
         scene="Han River in Seoul at night seen from the riverbank park, calm water reflecting "
               "colorful bridge lights and city skyline, gentle breeze, soft blue night",
         q=["river water night ambience", "river bank ambience", "gentle river water",
            "river flowing night"], must=["river"]),
    dict(id="temple-rain", emoji="🛕", motion="rain", mode="mixed", gap=[40, 110],
         en="Rain at a Korean Mountain Temple", hook="Rain Sounds & Wind Chimes for Sleep",
         ko="비 내리는 산사", ko_hook="빗소리와 처마 끝 풍경 소리",
         scene="Korean Buddhist temple in the mountains during soft rain, wet stone courtyard, colorful "
               "painted eaves with a small bronze wind chime, misty green forest, early evening",
         q=["rain on roof", "gentle rain forest", "rain soft steady", "rain on leaves"],
         must=["rain"], trig=["wind chime", "small bell"]),
    dict(id="mountain-stream", emoji="🏞️", motion="dust", mode="sleep",
         en="Mountain Stream in Seoraksan", hook="Flowing Water Sounds for Sleep & Focus",
         ko="설악산 계곡 물소리", ko_hook="맑은 계곡물 흐르는 소리",
         scene="Clear mountain stream flowing over smooth granite rocks in Seoraksan National Park, "
               "lush green forest, soft morning light, small waterfall",
         q=["mountain stream", "creek water flowing", "brook water", "stream rocks water"],
         must=["stream", "creek", "brook", "river", "water"]),
    dict(id="seoul-alley-snow", emoji="❄️", motion="snow", mode="sleep",
         en="Snowy Night in a Seoul Alley", hook="Quiet Winter Ambience for Sleep",
         ko="눈 오는 서울 골목", ko_hook="고요한 겨울밤의 소리",
         scene="Narrow old alley in Seoul on a snowy night, low houses with tiled roofs, warm window "
               "lights, a single street lamp, fresh snow covering the ground, quiet and peaceful",
         q=["winter night ambience", "snow night quiet", "soft winter wind", "quiet winter wind"],
         must=["winter", "snow", "wind"]),
    dict(id="palace-autumn", emoji="🍂", motion="leaves", mode="sleep",
         en="Autumn Wind at a Korean Palace", hook="Rustling Leaves & Gentle Breeze",
         ko="가을 고궁의 바람", ko_hook="낙엽 스치는 바람 소리",
         scene="Korean royal palace courtyard in autumn, red and golden maple trees, traditional wooden "
               "pavilion with colorful eaves, fallen leaves on the stone ground, late afternoon light",
         q=["autumn wind leaves", "wind rustling leaves", "dry leaves wind", "leaves wind gentle"],
         must=["wind", "leaves"]),
]


# 배정 순서(계절 반영): 가을 풍경은 10월에, 눈 테마는 11월 중순에, 여름밤은 맨 끝에 온다.
# ★순서를 바꾸면 이미 지난 날짜의 테마도 바뀐다 — 새 테마는 끝에만 덧붙일 것.
_ORDER = ["hanok-rain", "jeju-waves", "palace-autumn", "seoul-subway", "ondol-fire", "library-rain",
          "busan-harbor", "bamboo-forest", "pojangmacha-rain", "seoul-cafe", "han-river-night",
          "temple-snow", "mountain-stream", "seoul-alley-snow", "temple-rain", "rice-field-summer"]
THEMES.sort(key=lambda t: _ORDER.index(t["id"]))


def slot_for(d: dt.date) -> int:
    days = (d - START).days
    if days < 0:
        raise ValueError(f"{d} 는 시리즈 시작일 {START} 이전")
    return (days // 7) * 2 + (0 if days % 7 < 3 else 1)


def pick(d: dt.date) -> tuple[dict, int, int]:
    """(테마, 슬롯 번호, 권 번호)."""
    s = slot_for(d)
    return THEMES[s % len(THEMES)], s, s // len(THEMES) + 1


def build_spec(d: dt.date) -> dict:
    th, slot, vol = pick(d)
    vol_en = f" · Vol. {vol}" if vol > 1 else ""
    vol_ko = f" {vol}편" if vol > 1 else ""
    title = f"{th['emoji']} {th['en']}{vol_en} | {th['hook']} · {HOURS} Hours"
    if len(title) > 100:
        title = f"{th['emoji']} {th['en']}{vol_en} · {HOURS} Hours"[:100]
    ko_title = f"{th['emoji']} {th['ko']}{vol_ko} {HOURS}시간 | {th['ko_hook']}"[:100]
    talk = "No talking, no music — just the sound."
    desc = (f"{th['en']} — {th['hook'].lower()}, {HOURS} hours.\n"
            f"Put it on to fall asleep, study, or unwind. {talk}\n\n"
            f"Korea Sleep Sounds: a new Korean soundscape every Wednesday and Saturday.\n\n"
            f"Sound: Freesound (CC0) · Background: AI-generated image\n"
            f"#SleepSounds #Korea #ASMR #StudyMusic #Relaxing")
    ko_desc = (f"{th['ko']} {HOURS}시간. 잠들 때·공부할 때·쉴 때 틀어 두세요. 말소리·음악 없음.\n\n"
               f"매주 수·토 한국의 풍경 소리를 올립니다.\n"
               f"음원 Freesound(CC0) · 배경 AI 생성 이미지\n#수면 #백색소음 #ASMR #공부할때")
    fs = {"queries": th["q"], "must": th["must"]}
    if th.get("trig"):
        fs["trigger_queries"] = th["trig"]
    spec = {
        "date": d.isoformat(), "topic": "asmr", "series": "korea", "slot": slot, "vol": vol,
        "privacy": "public", "theme_id": th["id"], "theme_name": th["ko"],
        "mode": th["mode"], "narration_text": "", "duration_sec": HOURS * 3600,
        "motion": th["motion"], "bg_engine": "wbspark", "default_language": "en",
        "background": {"prompt": f"{th['scene']}, {_TAIL}"},
        "freesound": fs,
        "tags": ["sleep sounds", "korea", "korean ambience", "asmr", "study", "relaxing",
                 f"{HOURS} hours", th["en"].lower(), "white noise", "수면", "백색소음"],
        "platforms": {"youtube": {
            "title": title, "description": desc, "playlist": PLAYLIST,
            "playlist_description": "8-hour Korean soundscapes for sleep, study and relaxing. "
                                    "New every Wednesday and Saturday.",
            "thumbnail_text": "", "thumbnail_hook": "",
            "localizations": {"ko": {"title": ko_title, "description": ko_desc}},
        }},
        "credit": "음원 Freesound(CC0) · 배경 wbSpark 생성",
        "notes": f"Korea Sleep Sounds 슬롯 {slot} · {HOURS}시간 · 움직임 {th['motion']} · korea_sounds.py 가 생성",
    }
    if th.get("gap"):
        spec["trigger_gap"] = th["gap"]
    return spec


def kst_today() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()


def main() -> int:
    ap = argparse.ArgumentParser(description="Korea Sleep Sounds 스펙 생성")
    ap.add_argument("--date", default="", help="YYYY-MM-DD (비우면 오늘 KST)")
    ap.add_argument("--out", default="")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    d = dt.date.fromisoformat(a.date) if a.date else kst_today()
    if a.list:
        cur = max(d, START)
        for _ in range(len(THEMES)):
            while cur.weekday() not in (2, 5):   # 수·토
                cur += dt.timedelta(days=1)
            th, s, v = pick(cur)
            print(f"{cur} ({'수' if cur.weekday() == 2 else '토'})  슬롯 {s:>3}  {th['id']:<18} {th['motion']:<9} Vol.{v}")
            cur += dt.timedelta(days=1)
        return 0
    spec = build_spec(d)
    out_dir = a.out or "."
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{spec['date']}_korea-{spec['theme_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
