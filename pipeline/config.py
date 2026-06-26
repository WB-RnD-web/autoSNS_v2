"""autoSNS 파이프라인 공통 설정.

매일 09:00 배치: 뉴스 수집 → 핫이슈 선정 → 스토리보드 → (생성) → 합치기 → 업로드.
생성(Higgsfield) 단계는 결제·연결 후 끼운다. 그 외 단계는 지금도 동작.
"""
from __future__ import annotations
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
NEWS_DIR = OUTPUT / "news"        # 선정된 토픽/스토리보드 json·md
ASSETS_DIR = OUTPUT / "assets"    # 생성된 이미지/영상 클립
RENDERS_DIR = OUTPUT / "renders"  # 합쳐진 최종 mp4

# ── 콘텐츠 규격 ──────────────────────────────────────────
TIMEZONE = "Asia/Seoul"
RECENCY_HOURS = 18          # 최근 N시간 기사만 후보로
TARGET_DURATION_SEC = 40    # 30~45초 목표
MAX_CLIP_SEC = 15           # 영상 모델 1회 생성 상한
VIDEO_W, VIDEO_H = 1080, 1920  # 9:16

# ── 뉴스 소스(RSS) ───────────────────────────────────────
# Google 뉴스 RSS(여러 매체 집계 → 교차 등장 키워드로 화제성 측정에 유리). 카테고리 넓게.
FEEDS = [
    "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",                                    # 톱
    "https://news.google.com/rss/headlines/section/topic/WORLD?hl=ko&gl=KR&ceid=KR:ko",       # 세계
    "https://news.google.com/rss/headlines/section/topic/NATION?hl=ko&gl=KR&ceid=KR:ko",      # 사회/정치
    "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",    # 경제
    "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko",  # 기술
    "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ko&gl=KR&ceid=KR:ko",     # 과학
    "https://news.google.com/rss/headlines/section/topic/HEALTH?hl=ko&gl=KR&ceid=KR:ko",      # 건강
    "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=ko&gl=KR&ceid=KR:ko",      # 스포츠
    "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=ko&gl=KR&ceid=KR:ko",  # 연예
]

# ── 핫이슈 점수 가중치 ───────────────────────────────────
W_SOURCES = 1.0   # 키워드를 다룬 '서로 다른 매체 수'(교차 화제성)
W_VOLUME = 0.4    # 등장 기사 수
W_RECENCY = 0.6   # 최신성

# 키워드에서 제외할 한국어 조사/일반어·뉴스 상투어
STOPWORDS = set("""
은 는 이 가 을 를 에 의 도 와 과 및 등 으로 로 에서 에게 까지 부터 만 보다 처럼 한 두 그 저 이번
것 수 더 또 위해 관련 종합 속보 단독 영상 사진 오늘 내일 어제 올해 지난 대한 통해 밝혀 했다 한다 된다
기자 뉴스 연합뉴스 뉴스1 뉴시스 조선일보 중앙일보 동아일보 한겨레 경향신문 한국경제 매일경제 머니투데이 서울신문 국민일보 세계일보 헤럴드 ytn kbs mbc sbs jtbc the a an of to in on
한국 국내 우리 우리나라 국민 세계 글로벌 전국 지역 만에 이유 정도 관계자 이날 당시 최근 무단 배포 재배포 저작권 공식 가능 상황
""".split())


def ensure_dirs() -> None:
    for d in (NEWS_DIR, ASSETS_DIR, RENDERS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: pathlib.Path | None = None) -> None:
    """의존성 없이 pipeline/.env 를 환경변수로 로드(있으면)."""
    path = path or (ROOT / "pipeline" / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
