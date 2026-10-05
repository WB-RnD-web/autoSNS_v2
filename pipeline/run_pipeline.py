#!/usr/bin/env python3
"""v2 오케스트레이터(모션그래픽): 스토리보드 → 장면스펙 → 모션그래픽 쇼츠 → 업로드.

각 스토리보드마다:
  ① 장면 스펙 확보:
     - --spec 로 직접 지정(단일) 또는
     - 미리 만든 output/specs/<date>_<topic>_spec.json 있으면 사용 또는
     - ANTHROPIC_API_KEY 있으면 extract_scenes 로 생성(→ specs 저장)
  ② motion_short.build_motion → output/renders/<date>_<topic>_final.mp4
  ③ 업로드(privacy 준수, ledger dedupe, 로그) — v1 재사용

루프 가드: main에 커밋하지 않음(산출물·ledger·spec 전부 .gitignore).

사용:
  python run_pipeline.py <sb.json> [...] --force-private
  python run_pipeline.py <sb.json> --spec <spec.json> --no-upload
  python run_pipeline.py --today
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import json
import os
import sys
import time

import config
import fortune_card
import theme_card
import pulli_card
import name_card
import news_card
import ledger as ledgermod
import ai_news
import motion_short
import news_copy_check
import upload_youtube
from upload_from_storyboard import build_meta

HERE = os.path.dirname(os.path.abspath(__file__))
SPECS_DIR = config.OUTPUT / "specs"


def today_storyboards():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return sorted(glob.glob(str(config.NEWS_DIR / f"{today}_*_storyboard.json")))


def has_credentials():
    token = config.env("YT_TOKEN", str(config.ROOT / "pipeline/secrets/token.json"))
    return bool(config.env("YT_TOKEN_JSON")) or os.path.exists(token)


# ── 쇼츠 토픽 일시정지 (2026-09-29) ──────────────────────────────
# 스튜디오 실측(8/31~9/28, '계속 시청함' = 피드에서 넘기지 않고 본 비율):
#   정치 30~59% · 운세 22~47% → 편당 ~1,000회
#   미장·국장 9~15% · 별자리 9~25% → 편당 30~350회(9/28 미장 30회)
# 채널 시청자(55세 이상 88%)와 안 맞는 토픽은 피드에서 85~90%가 넘긴다. 잠시 올리지 않고
# 되는 두 토픽(정치·운세)에 모은다. 루틴이 스토리보드를 올려도 ★코드가 렌더 전에 건너뛴다.
# 바꾸기: 레포 변수 SHORTS_PAUSED_TOPICS (쉼표 구분, 토픽 이름과 정확히 일치).
#   전부 재개 = "none". 비우거나 안 만들면 아래 기본값.
PAUSED_TOPICS_DEFAULT = "horoscope,zodiac,stock,stock_us"


def paused_topics() -> set[str]:
    raw = (os.environ.get("SHORTS_PAUSED_TOPICS") or "").strip() or PAUSED_TOPICS_DEFAULT
    if raw.lower() in ("none", "off", "0", "-"):
        return set()
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def is_paused(sb: dict) -> bool:
    topic = str(sb.get("topic") or "").strip().lower()
    return bool(topic) and topic in paused_topics()


# 그림체 토픽(운세 캐릭터·별자리 천체 일러스트)은 누가 봐도 그림이라 표시 대상이 아니다.
ILLUSTRATED_TOPICS = ("fortune", "horoscope", "zodiac", "star", "luck", "love")


def synthetic_label(sb: dict, spec: dict) -> bool | None:
    """AI 키비주얼을 깐 사실적(보도사진 톤) 쇼츠면 True. 키비주얼이 없으면 None(필드 안 보냄)."""
    if not spec.get("_bg"):
        return None
    topic = str(sb.get("topic") or spec.get("topic") or "").lower()
    return not any(topic.startswith(t) for t in ILLUSTRATED_TOPICS)


FORTUNE_TOPICS = ("fortune", "horoscope", "zodiac")
FORTUNE_PLAYLIST = "오늘의 띠별 운세 | 매일 아침 1위~12위"
FORTUNE_PLAYLIST_DESC = "매일 아침 올라오는 띠별 운세 1위부터 12위까지. 45~96년생 전부, 재미로 보는 운세예요."
# AI 소식(2026-09-30) — 하루 두 번. 과학·기술(28) + 재생목록.
# 띠별 테마 순위 표(2026-10-01, theme_card.py) — 매일 낮 12시. 아침 표와 재생목록을 나눈다(제목이 '매일 아침'이라).
THEME_PLAYLIST = "띠별 순위 특집 | 돈·자식·말년 복 1위~12위"
THEME_PLAYLIST_DESC = ("매일 낮 12시, 주제를 바꿔 12띠 순위를 한 장에 모아요. 돈 들어오는 띠, 자식 덕 보는 띠, "
                       "말년 복 있는 띠… 45~96년생 전부. 재미로 보는 운세예요.")
# '내 것 찾기' 표(2026-10-02, name_card.py) — 07:40 해 끝자리 · 09:40 이름 글자 · 13:40 성씨 · 15:40 태어난 달.
# ★재생목록 제목은 그대로 둔다 — 바꾸면 ensure_playlist 가 새 목록을 만든다.
NAME_PLAYLIST = "내 것 찾기 | 이름 글자·태어난 달로 보는 복"
NAME_PLAYLIST_DESC = ("내 이름 글자, 성씨, 태어난 해·달이 표에 있는지 찾아보세요. 매일 아침 7시 40분 태어난 해, 9시 40분 이름 한자, "
                      "오후 1시 40분 성씨, 3시 40분 태어난 달 순위가 올라와요. 재미로 보는 풀이예요.")
# 풀이형 표(2026-10-06, pulli_card.py — tables-v2) — 오늘 일진과 띠의 합·충으로 순위 + 이유. ★제목 바꾸지 않는다(새 목록이 생긴다).
PULLI_PLAYLIST = "띠별 일진 풀이 | 오늘 순위의 이유까지"
PULLI_PLAYLIST_DESC = ("오늘의 일진(60갑자)과 내 띠가 합인지 충인지로 12띠 순위를 매기고, 이유까지 풀어 드려요. "
                       "45~96년생 전부. 전통 일진 풀이를 재미로 정리한 운세예요.")
AI_PLAYLIST = "AI 소식 | 매일 오전·저녁, 쉽게 듣는 AI 뉴스"
AI_PLAYLIST_DESC = ("오늘 AI 세상에서 바뀐 것, 그리고 그게 내 일자리·돈·안전에 뭘 뜻하는지. "
                    "어려운 말은 쉽게 풀고, 출처는 설명란에 적어요.")


def category_for(topic: str) -> str:
    """운세·별자리는 엔터테인먼트(24), AI 소식은 과학·기술(28), 뉴스·주식은 뉴스·정치(25).

    2026-09-30 전엔 전부 25였다.
    """
    t = str(topic or "").lower()
    if t.startswith(FORTUNE_TOPICS):
        return "24"
    if ai_news.is_ai(t):
        return "28"
    return "25"


def playlist_for(topic: str) -> tuple[str, str] | None:
    """공개 업로드를 자동으로 넣을 재생목록(제목, 설명). 없으면 None."""
    t = str(topic or "").lower()
    if t == theme_card.TOPIC:
        return THEME_PLAYLIST, THEME_PLAYLIST_DESC
    if t == pulli_card.TOPIC:
        return PULLI_PLAYLIST, PULLI_PLAYLIST_DESC
    if t == name_card.TOPIC:
        return NAME_PLAYLIST, NAME_PLAYLIST_DESC
    if t.startswith(FORTUNE_TOPICS):
        return FORTUNE_PLAYLIST, FORTUNE_PLAYLIST_DESC
    if ai_news.is_ai(t):
        return AI_PLAYLIST, AI_PLAYLIST_DESC
    return None


def add_playlist(vid: str, title: str, desc: str) -> None:
    """쇼츠를 재생목록에 — 실패해도 업로드는 끝났다(경고만). 쿼터: playlists.list 1 + playlistItems.insert 50."""
    try:
        import upload_youtube_novel as N
        yt = N.get_service()
        pid = N.ensure_playlist(yt, title, desc, privacy="public")
        N.add_to_playlist(yt, pid, vid)
        print(f"   📂 재생목록에 추가: {title} ({pid})")
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 재생목록 실패(업로드는 성공): {e}")


def add_fortune_playlist(vid: str) -> None:
    """운세 쇼츠를 재생목록에 — 가장 많이 보는 콘텐츠인데 목록이 없었다."""
    add_playlist(vid, FORTUNE_PLAYLIST, FORTUNE_PLAYLIST_DESC)


def add_weekly_link(meta: dict, topic: str) -> str | None:
    """운세 쇼츠 설명 끝에 최신 '주간 띠별 운세 풀이' 롱폼 한 줄(2026-10-01, weekly_fortune.py).

    쇼츠 피드 시청은 YPP 시청 시간에 안 들어간다 — 표를 본 사람이 이어 볼 롱폼으로 보낸다.
    '주간 띠별 운세' 재생목록에서 공개된 가장 최근 영상을 찾는다(2~3 units). 없거나 실패하면 조용히 넘어간다.
    끄기: WEEKLY_LINK=0. 설명 형식은 그대로 두고 맨 끝에 한 줄만 붙인다."""
    if not str(topic or "").strip().lower().startswith("fortune"):
        return None
    if (config.env("WEEKLY_LINK", "1") or "1").strip() in ("0", "false", "False", "off"):
        return None
    try:
        import upload_youtube_novel as N
        import weekly_fortune
        vid = weekly_fortune.latest_public_video(N.get_service())
    except Exception as e:  # noqa: BLE001
        print(f"   (주간 운세 링크 건너뜀: {str(e)[:120]})")
        return None
    if vid:
        meta["description"] = weekly_fortune.append_link(meta["description"], vid)
        print(f"   🔗 주간 띠별 운세 풀이 링크: https://youtu.be/{vid}")
    return vid


# 쿼터가 바닥났다는 응답. 재시도해도 똑같이 거절되고 ★재시도마다 쿼터를 또 먹는다 → 바로 멈춘다.
#   videos.insert 는 2026-06-01 부터 자기 버킷(하루 100회)이고 나머지 호출은 10,000 units 를 나눠 쓴다.
QUOTA_REASONS = ("quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded")


def is_quota_error(e: BaseException) -> bool:
    return any(r in str(e) for r in QUOTA_REASONS)


def upload_with_retry(video, meta, retries=2):
    last = None
    for attempt in range(1, retries + 2):
        try:
            # 루틴이 스토리보드에 써준 번역을 그대로 넘긴다(없으면 yt_i18n 이 Spark 로 번역).
            return upload_youtube.upload(video, meta["title"], meta["description"],
                                         meta["privacy"], tags=meta["tags"],
                                         localizations=meta.get("localizations"),
                                         synthetic=meta.get("synthetic"),
                                         category=meta.get("category", "25"))
        except Exception as e:  # noqa: BLE001
            last = e
            if is_quota_error(e):
                sys.stderr.write(f"[upload] 쿼터 소진 — 재시도하지 않는다(재시도도 쿼터를 먹는다): {e}\n")
                print(f"::error title=유튜브 쿼터 소진::{str(e)[:200]} — 다음 쿼터일(16:00 KST, 겨울 17:00)에 다시")
                raise
            sys.stderr.write(f"[upload 재시도 {attempt}/{retries + 1}] {e}\n")
    raise last


def resolve_spec(sb_path, sb, args):
    """장면 스펙 확보: 직접 스펙 > --spec > 사전생성 파일 > LLM 추출."""
    # 루틴이 스펙을 직접 커밋한 경우(scenes 키 보유) → 그대로 사용(CI LLM 불필요)
    if isinstance(sb.get("scenes"), list) and sb["scenes"]:
        return sb
    if args.spec:
        with open(args.spec, encoding="utf-8") as f:
            return json.load(f)
    date, topic = sb.get("date", ""), sb.get("topic", "")
    pre = SPECS_DIR / f"{date}_{topic}_spec.json"
    if pre.exists():
        with open(pre, encoding="utf-8") as f:
            return json.load(f)
    if config.env("ANTHROPIC_API_KEY"):
        import extract_scenes
        spec = extract_scenes.extract_scenes(sb)
        SPECS_DIR.mkdir(parents=True, exist_ok=True)
        with open(pre, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        return spec
    raise RuntimeError("장면 스펙 없음 — --spec 지정, output/specs/ 사전생성, 또는 ANTHROPIC_API_KEY 필요")


def _prepare_bg(sb, spec, wd):
    """영상 배경 키비주얼(best-effort). 성공하면 spec['_bg'] 에 경로를 싣는다.

    검정 배경 + 글자만 있는 화면은 카드뉴스처럼 보여 첫 화면에서 스와이프된다.
    커버용으로 어차피 만들던 그림을 ★렌더 전에 당겨 만들어 영상 배경에도 깐다.
    같은 그림을 커버가 재사용하므로(sb['_bg_raw']) 생성 횟수는 그대로다.
    실패하면 아무것도 안 싣는다 → 렌더러는 기존 검정 배경으로 그린다.
    """
    if config.env("SHORTS_BG", "1") in ("0", "false", "False", ""):
        return None
    try:
        import cover_short
        timeout = int(config.env("SHORTS_BG_TIMEOUT", "240") or "240")
        bg = cover_short.build_bg(sb, os.path.join(wd, "keyvisual.png"), timeout_sec=timeout)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 키비주얼 예외 → 검정 배경: {e}\n")
        bg = None
    if bg:
        spec["_bg"] = bg
        sb["_bg_raw"] = bg
    return bg


def _prepare_cover(video, sb, base):
    """소셜 미리보기 커버 준비(best-effort). (커버이미지경로, 소셜영상경로, 소스태그) 반환.

    커버이미지: 루틴 thumbnail_hook 있으면 qwen-image 9:16 커버 → 없거나 실패하면 영상 프레임 폴백.
    소셜영상: 커버가 있으면 그 커버를 '첫 프레임'으로 구운 mp4(쓰레드용) → 실패/미커버면 원본.
    검은 미리보기를 절대 안 내보내는 게 목표라 실패는 전부 조용히 폴백한다.
    """
    if config.env("SHORTS_COVER", "1") in ("0", "false", "False", ""):
        return None, video, "off"
    try:
        import cover_short
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] cover_short 임포트 실패 → 커버 없이 진행: {e}\n")
        return None, video, "none"

    wd = str(config.OUTPUT / "_work" / "social" / base)
    timeout = int(config.env("SHORTS_COVER_TIMEOUT", "300") or "300")
    hold = float(config.env("SHORTS_COVER_HOLD", "0.7") or "0.7")
    grab_at = float(config.env("SHORTS_COVER_GRAB_SEC", "2.0") or "2.0")

    cover_img, src = None, "none"
    try:
        c = cover_short.build_cover(sb, os.path.join(wd, "cover.jpg"), wd, timeout_sec=timeout,
                                    raw=sb.get("_bg_raw"))
        if c:
            cover_img, src = c, "qwen"
        else:
            f = cover_short.grab_frame(video, os.path.join(wd, "framecover.jpg"), at_sec=grab_at)
            if f:
                cover_img, src = f, "frame"
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"[warn] 커버 생성 예외 → 폴백 시도: {e}\n")

    social_video = video
    if cover_img:
        try:
            baked = cover_short.prepend_cover(video, cover_img, os.path.join(wd, "social.mp4"), hold_sec=hold)
            if baked:
                social_video = baked
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[warn] 첫프레임 굽기 예외 → 원본 사용: {e}\n")
    return cover_img, social_video, src


def _on(name: str, default: str = "0") -> bool:
    return (config.env(name, default) or default).strip() in ("1", "true", "True", "yes")


# 인스타·쓰레드로도 보내는 토픽(정확히 일치). 인스타 계정이 'AI 유튜브 운영 기록'(@zerocrew.studio)이라
# ★AI 소식만 어울린다 — 뉴스·운세는 섞지 않는다(2026-09-30). 바꾸기: 레포 변수 SOCIAL_CROSSPOST_TOPICS
#   (쉼표 구분 · 전부 끄기 = none).
CROSSPOST_TOPICS_DEFAULT = "ai"


def crosspost_topics() -> set[str]:
    raw = (config.env("SOCIAL_CROSSPOST_TOPICS") or "").strip() or CROSSPOST_TOPICS_DEFAULT
    if raw.lower() in ("none", "off", "0", "-"):
        return set()
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def social_crosspost_on(topic: str | None = None) -> bool:
    """왕별이 쇼츠 → 인스타 릴스·쓰레드 크로스포스트 대상인가.

    ★토픽별(2026-09-30): SOCIAL_CROSSPOST_TOPICS(기본 'ai')에 든 토픽만.
    옛 스위치 SOCIAL_CROSSPOST=1 은 '전 토픽'으로 그대로 둔다(기본 꺼짐 — 인스타 계정을 바꿨다).
    실제 게시 여부는 따로 INSTA_PUBLISH=1 이 정한다(social_live) — 없으면 dry-run.
    """
    if _on("SOCIAL_CROSSPOST"):
        return True
    return str(topic or "").strip().lower() in crosspost_topics()


def social_live() -> bool:
    """insta/post_reel.py 와 같은 안전장치: INSTA_PUBLISH=1 일 때만 실제로 올린다(아니면 dry-run)."""
    return _on("INSTA_PUBLISH")


def do_social(video, sb, res):
    """IG Reels + Threads 업로드(자격증명 있을 때만). 공개 URL 은 Cloudinary 경유.

    미리보기(검은 화면) 대응:
      - 커버 확보(qwen-image 커버 → 실패 시 영상 프레임 폴백)
      - IG: cover_url 로 커버 지정 / Threads: 커버 API 없어 커버를 영상 첫 프레임으로 굽는다
      - YouTube 쇼츠는 이 함수와 무관(원본 res["video"] 그대로 업로드)
    ★INSTA_PUBLISH=1 이 아니면 dry-run(캡션만 보여 주고 아무것도 안 올린다). 쓰레드는 INSTA_THREADS=1 일 때만.
    """
    plat = sb.get("platforms", {})
    cap = plat.get("instagram", {}).get("caption", "")
    txt = plat.get("threads", {}).get("text", "")
    if not social_live():
        res["social"] = (f"[dry-run] IG 캡션 {len(cap)}자 · 쓰레드 {len(txt)}자 "
                         f"— 레포 변수 INSTA_PUBLISH=1 이면 게시{' (+쓰레드: INSTA_THREADS=1)' if not _on('INSTA_THREADS') else ''}")
        print(f"   🧪 {res['social']}\n── IG 캡션 ──\n{cap}\n── 쓰레드 ──\n{txt}\n──────────")
        return
    ig = config.env("IG_USER_ID") and config.env("IG_ACCESS_TOKEN")
    th = _on("INSTA_THREADS") and config.env("THREADS_USER_ID") and config.env("THREADS_ACCESS_TOKEN")
    if not ig and not th:
        return  # 자격증명 없음 → 조용히 스킵
    import host_video
    base = os.path.splitext(os.path.basename(video))[0]

    cover_img, social_video, cover_src = _prepare_cover(video, sb, base)

    # 소셜용 영상 호스팅(커버 구운 버전 우선). 커버를 못 구웠으면 원본 public_id 유지.
    video_pid = f"{base}_social" if social_video != video else base
    url = host_video.host(social_video, video_pid)
    if not url:
        res["social"] = "[skip] Cloudinary 자격증명 없음(공개 URL 불가)"
        print("   ⏭️  IG/Threads 스킵 — Cloudinary 자격증명 없음")
        return
    print(f"   공개 URL: {url}")

    # IG cover_url 용 커버 이미지 호스팅(있을 때만)
    cover_url, cover_pid = None, None
    if cover_img:
        cover_pid = f"{base}_cover"
        cover_url = host_video.host_image(cover_img, cover_pid)

    plat = sb.get("platforms", {})
    out = []
    ok = False  # 하나라도 게시 성공하면 True
    if ig:
        try:
            import upload_instagram
            mid = upload_instagram.publish_reel(
                url, plat.get("instagram", {}).get("caption", ""), cover_url=cover_url)
            out.append(f"IG:{mid}"); ok = True
        # ★SystemExit 까지 잡는다 — 업로더가 SystemExit 를 던지면 잡 전체가 exit 1 로 끝나고
        #   Cloudinary 정리·다음 스토리보드 처리가 통째로 빠졌다. 소셜 실패는 경고로만 남긴다.
        except (Exception, SystemExit) as e:  # noqa: BLE001
            out.append(f"IG실패:{e}")
            print(f"::warning title=Instagram 게시 실패::{e}")
    if th:
        try:
            import upload_threads
            tid = upload_threads.publish_thread(url, plat.get("threads", {}).get("text", ""))
            out.append(f"Threads:{tid}"); ok = True
        except (Exception, SystemExit) as e:  # noqa: BLE001
            out.append(f"Threads실패:{e}")
            print(f"::warning title=Threads 게시 실패::{e}")
    out.append(f"커버:{cover_src}")
    # 게시 성공 시 Cloudinary 원본 삭제(영상+커버). 전부 실패면 재시도 위해 보존.
    if ok:
        cleaned = host_video.cleanup(video_pid)
        if cover_pid:
            host_video.cleanup(cover_pid, resource_type="image")
        out.append("cloud정리✓" if cleaned else "cloud정리실패(수동확인)")
    else:
        out.append("cloud보존(게시 전부 실패)")
    res["social"] = " · ".join(out)


def ai_lenient(args) -> bool:
    """AI 검사 느슨 모드(날짜·신선도·중복을 경고로) — ★비공개이거나 안 올릴 때만 먹힌다."""
    want = getattr(args, "ai_lenient", False)
    safe = (getattr(args, "force_private", False) or getattr(args, "no_upload", False)
            or getattr(args, "dry_run_upload", False))
    if want and not safe:
        print("   ⚠️ --ai-lenient 무시 — 공개 업로드에서는 느슨 모드를 쓰지 않는다")
    return bool(want and safe)


def ai_precheck(sb_path, sb, args, led, res) -> bool:
    """AI 소식 대본 검사(렌더 전). 계속하면 True. 못 넘으면 res 에 이유를 적고 False.

    이력 = 누적 브랜치 routine/ai_am·ai_pm(워크플로가 fetch) + 같은 폴더 + ledger.
    피드 = data/ai-news-feed(워크플로가 fetch) — 루틴과 ★똑같은 대조를 여기서 다시 한다(루틴이 건너뛰어도 막힌다).
    실제로 올릴 때는 유튜브 최근 업로드도 본다(3 units) — ledger 캐시가 날아가도 같은 슬롯을 두 번 올리지 않게.
    """
    ai_news.normalize(sb)
    now = dt.datetime.now(ai_news.KST)
    key = ai_news.slot_key(sb)
    hist = ai_news.load_history(now.date(), exclude=key, ledger=led,
                                dirs=[os.path.dirname(os.path.abspath(sb_path))])
    feed = ai_news.load_feed(now)
    lenient = ai_lenient(args)
    errs, warns = ai_news.check(sb, sb_path, now=now, history=hist, lenient=lenient, feed=feed)
    print(f"   🤖 AI 소식 검사 · {key} · 이력 {len(hist)}편 · 피드 {len(feed['files'])}파일·기사 "
          f"{len(feed['by_url'])}건 · 읽는 글자 "
          f"{ai_news.spoken_chars(ai_news.narration(sb))}자{' · 느슨 모드' if lenient else ''}")
    for w in warns:
        print(f"::warning title=AI 소식 검사(느슨 모드)::{w}")
    if errs:
        for e in errs:
            print(f"::error title=AI 소식 검사::{e}")
        res["error"] = f"ai_check {len(errs)}건: {errs[0]}"
        return False
    if getattr(args, "no_upload", False) or getattr(args, "dry_run_upload", False) or not has_credentials():
        return True
    try:
        import upload_youtube_novel as N
        vid, dup = ai_news.youtube_conflicts(sb, ai_news.recent_uploads(N.get_service()), now)
    except Exception as e:  # noqa: BLE001
        print(f"   ⚠️ 유튜브 이중 확인 건너뜀(ledger·브랜치 이력만으로 판정): {str(e)[:160]}")
        return True
    if vid:
        res["skipped"] = "uploaded"
        res["uploaded"] = f"https://youtu.be/{vid} (이미 올라감)"
        print(f"   ⏭️  '{ai_news.marker(sb)}' 영상이 이미 채널에 있다({vid}) — 다시 올리지 않는다")
        if led is not None:
            ledgermod.mark(led, sb, vid, sb.get("privacy") or "public", time.time(),
                           getattr(args, "ledger_path", ledgermod.DEFAULT_PATH), extra={"ai": ai_news.entry(sb)})
        return False
    if dup and not lenient:
        for e in dup:
            print(f"::error title=AI 소식 중복::{e}")
        res["error"] = f"ai_check 중복 {len(dup)}건: {dup[0]}"
        return False
    return True


def process(sb_path, args, led):
    res = {"storyboard": os.path.basename(sb_path), "video": None,
           "uploaded": None, "social": None, "skipped": False, "error": None}
    with open(sb_path, encoding="utf-8") as f:
        sb = json.load(f)
    if is_paused(sb) and not getattr(args, "include_paused", False):
        res["skipped"] = "paused"
        print(f"   ⏸️  일시정지 토픽({sb.get('topic')}) — 렌더·업로드 안 함 "
              f"(재개: 레포 변수 SHORTS_PAUSED_TOPICS)")
        return res
    if led is not None and ledgermod.is_done(led, sb):
        res["skipped"] = True
        print(f"   ⏭️  ledger 처리됨({ledgermod.key_for(sb)}) — 건너뜀")
        return res
    is_ai = ai_news.is_ai(sb)
    if is_ai and not ai_precheck(sb_path, sb, args, led, res):
        return res
    # ★카피 점검 — 렌더 전에 본다. 밋밋하면 경고만 뜨고 계속 간다.
    # 테마 표는 문구가 전부 코드(theme_card.THEMES)에서 나온다 — 뉴스 카피 규칙(hook 수치 등)과 맞지 않아 건너뛴다.
    if not (theme_card.is_theme(sb) or name_card.is_name(sb) or pulli_card.is_pulli(sb)):
        news_copy_check.report(sb)
    try:
        spec = resolve_spec(sb_path, sb, args)
        spec.setdefault("topic", sb.get("topic", ""))
        # 운세는 격일로 '12띠 한 장 표'(fortune_card) — 기존 형식과 A/B
        if fortune_card.use_card(sb):
            spec = fortune_card.build_spec(sb)
            print("   🗂️ 운세 한 장 표 (격일 A/B · fortune_card)")
        elif news_card.use(sb):
            # 정치·주식·AI 소식은 '10초 한 장'(2026-10-04) — 루틴 대본에서 뽑는다. 끄기: 레포 변수 NEWS_CARD=0
            spec = news_card.build_spec(sb)
            print(f"   🗂️ 소식 한 장 ({spec['scenes'][0].get('layout')} · news_card)")
        suffix = f"_{sb.get('topic','')}" if sb.get("topic") else ""
        if sb.get("slot"):
            suffix += f"_{sb['slot']}"          # 하루 여러 편(AI 소식 am·pm) — 파일이 서로 덮지 않게
        out_mp4 = str(config.RENDERS_DIR / f"{sb.get('date','out')}{suffix}_final.mp4")
        wd = str(config.OUTPUT / "_work" / f"{sb.get('date','')}{suffix}")
        config.ensure_dirs()
        _prepare_bg(sb, spec, wd)
        res["video"] = motion_short.build_motion(spec, out_mp4, wd, quality=args.quality)
    except Exception as e:  # noqa: BLE001
        res["error"] = f"render: {e}"
        return res
    if is_ai:
        try:
            sec = motion_short.probe_dur(res["video"])
        except Exception:  # noqa: BLE001
            sec = None
        msg = ai_news.check_duration(sec)
        if msg:
            print(f"::error title=AI 소식 길이::{msg}")
            res["error"] = f"ai_check: {msg}"
            return res

    if args.no_upload:
        return res
    meta = build_meta(sb, args.force_private)
    meta["synthetic"] = synthetic_label(sb, spec)
    meta["category"] = category_for(sb.get("topic", ""))
    if is_ai:
        # 설명 = 루틴 설명 + 출처(주소·날짜) + 'AI 소식 <날짜> <오전|저녁>' 표식(유튜브 쪽 중복 판정)
        meta["description"] = ai_news.youtube_description(sb)
        meta["tags"] = list(ai_news.TAGS)
    # Supertonic 3 는 OpenRAIL-M(상업 이용 가능 · 사용 제한 · 출처 표기) — 설명란 끝에 한 줄.
    if motion_short.VO_BACKEND == "wbspark" and "Supertonic" not in meta["description"]:
        meta["description"] = f"{meta['description']}\n\n🎙️ Voice: Supertonic (Supertone · OpenRAIL-M)"
    try:
        import yt_i18n
        meta["localizations"] = yt_i18n.from_spec(sb) or None
    except Exception:  # noqa: BLE001
        meta["localizations"] = None
    if fortune_card.use_card(sb):
        # 표 날은 제목·설명을 표에 맞춘다(목소리 출처 줄은 유지). 루틴이 쓴 번역은 원래 형식의 제목이라 버린다.
        cm = fortune_card.meta(sb)
        credit = meta["description"][len(build_meta(sb, False)["description"]):]
        meta["title"] = f"{cm['title']} #shorts"
        meta["description"] = cm["description"] + credit
        meta["localizations"] = None
    if theme_card.is_theme(sb):
        # 테마 표 — 제목·설명은 theme_card 가 정한다(목소리 출처 줄은 유지). 번역은 넣지 않는다.
        tm = theme_card.meta(sb)
        credit = meta["description"][len(build_meta(sb, False)["description"]):]
        meta["title"] = f"{tm['title']} #shorts"
        meta["description"] = tm["description"] + credit
        meta["localizations"] = None
    if pulli_card.is_pulli(sb):
        # 풀이형 표 — 제목·설명(12띠 이유 전부)은 pulli_card 가 정한다(목소리 출처 줄은 유지). 번역은 넣지 않는다.
        pm = pulli_card.meta(sb)
        credit = meta["description"][len(build_meta(sb, False)["description"]):]
        meta["title"] = f"{pm['title']} #shorts"
        meta["description"] = pm["description"] + credit
        meta["localizations"] = None
    if name_card.is_name(sb):
        # 내 것 찾기 표 — 제목·설명은 name_card 가 정한다(목소리 출처 줄은 유지). 번역은 넣지 않는다.
        nm = name_card.meta(sb)
        credit = meta["description"][len(build_meta(sb, False)["description"]):]
        meta["title"] = f"{nm['title']} #shorts"
        meta["description"] = nm["description"] + credit
        meta["localizations"] = None
    print(f"   업로드 메타: title='{meta['title']}' privacy={meta['privacy']} "
          f"AI표시={meta['synthetic']} 번역={list(meta['localizations'] or [])}")
    if args.dry_run_upload:
        res["uploaded"] = f"[dry-run] privacy={meta['privacy']}"
        return res

    # ── YouTube (자격증명 있을 때) ──
    if has_credentials():
        add_weekly_link(meta, sb.get("topic", ""))
        try:
            vid = upload_with_retry(res["video"], meta)
            res["uploaded"] = f"https://youtu.be/{vid} ({meta['privacy']})"
            pl = playlist_for(sb.get("topic", ""))
            if pl and meta["privacy"] == "public":
                add_playlist(vid, *pl)
            if led is not None:
                ledgermod.mark(led, sb, vid, meta["privacy"], time.time(), args.ledger_path,
                               extra={"ai": ai_news.entry(sb)} if is_ai else None)
        except Exception as e:  # noqa: BLE001
            res["error"] = f"upload: {e}"
    else:
        res["uploaded"] = "[skip] YT 자격증명 없음"
        print("   ⏭️  YouTube 스킵(자격증명 없음).")

    # ── Instagram Reels + Threads — ★SOCIAL_CROSSPOST_TOPICS(기본 ai)에 든 토픽만, 실제 게시는 INSTA_PUBLISH=1 ──
    if not args.no_social and not social_crosspost_on(sb.get("topic")):
        res["social"] = "[skip] 크로스포스트 대상 토픽 아님(SOCIAL_CROSSPOST_TOPICS — 인스타는 AI 소식만)"
    elif not args.no_social and res["error"]:
        # 유튜브가 실패하면 ledger 가 안 남아 재실행된다 → 그때 인스타·쓰레드가 두 번 올라가지 않게 보류
        res["social"] = "[skip] 유튜브 업로드 실패 — 재실행 때 중복 게시되지 않게 인스타·쓰레드 보류"
    elif not args.no_social:
        try:
            do_social(res["video"], sb, res)
        except Exception as e:  # noqa: BLE001
            res["social"] = f"social실패:{e}"
    return res


def main():
    ap = argparse.ArgumentParser(description="v2 모션그래픽 파이프라인")
    ap.add_argument("storyboards", nargs="*")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--spec", help="장면 스펙 직접 지정(단일 스토리보드)")
    ap.add_argument("--no-upload", action="store_true", help="유튜브 업로드 안 함")
    ap.add_argument("--no-social", action="store_true", help="IG/Threads 업로드 안 함")
    ap.add_argument("--force-private", action="store_true")
    ap.add_argument("--dry-run-upload", action="store_true")
    ap.add_argument("--quality", default="standard", choices=["draft", "standard", "high"])
    ap.add_argument("--use-ledger", action="store_true")
    ap.add_argument("--ledger-path", default=ledgermod.DEFAULT_PATH)
    ap.add_argument("--log", default="")
    ap.add_argument("--include-paused", action="store_true",
                    help="일시정지 토픽도 처리(수동 테스트용 — SHORTS_PAUSED_TOPICS 무시)")
    ap.add_argument("--ai-lenient", action="store_true",
                    help="AI 소식 검사에서 날짜·신선도·중복을 경고로(수동 점검 — 비공개/업로드 없음일 때만 먹힌다)")
    args = ap.parse_args()
    config.load_dotenv()

    boards = list(args.storyboards)
    if args.today:
        boards += today_storyboards()
    boards = [b for b in dict.fromkeys(boards) if b.endswith("_storyboard.json")]
    if not boards:
        print("[stop] 처리할 스토리보드 없음. 경로 지정 또는 --today.", file=sys.stderr)
        return 1

    led = ledgermod.load(args.ledger_path) if args.use_ledger else None
    print(f"# 처리 {len(boards)}개: {', '.join(os.path.basename(b) for b in boards)}")
    results = []
    for b in boards:
        print(f"\n──── {os.path.basename(b)} ────")
        results.append(process(b, args, led))

    print("\n──────── 요약 ────────")
    rc = 0
    for r in results:
        line = f"  {r['storyboard']}: "
        if r["skipped"]:
            line += {"paused": "SKIP(일시정지 토픽)",
                     "uploaded": "SKIP(이미 유튜브에 있음)"}.get(r["skipped"], "SKIP(ledger)")
        else:
            line += f"video={'OK' if r['video'] else 'FAIL'}"
        if r["uploaded"]:
            line += f", yt={r['uploaded']}"
        if r.get("social"):
            line += f", social={r['social']}"
        if r["error"]:
            line += f"  ⚠️ {r['error']}"; rc = 1
        print(line)
    if args.log:
        os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
        with open(args.log, "w", encoding="utf-8") as f:
            json.dump({"results": results}, f, ensure_ascii=False, indent=2)
        print(f"\n로그: {args.log}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
