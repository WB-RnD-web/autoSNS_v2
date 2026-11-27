# data/meow — 자동 생성(손대지 않는다)

- 만든 곳: .github/workflows/meow-daily.yml · meow/plan_api.py — Meow Remix 매일 한 편 기획
- <날짜>.json = render.py·post.py 가 읽는 기획(편 하나 · 5초 컷 2개 · 2컷째는 1컷 그림 편집) 또는 skip
- <날짜>_api.json = 모델·꼴·시도·토큰·검색·달러
- stats.json = 분석 담당(meow/analyst.py) — 새 채널 최근 쇼츠 성적
- mix.json = 틀 자동 조정(meow/tuner.py) — 오늘 꼴 비율·미리 보기 끄는 편 비율·이유·지난 기록
- notes/<날짜>.md = 정리 노트(meow/notes.py) — 근거(숫자) + 해석(API · 추측 포함)
- 마지막 생성: 2026-11-28 00:37 KST · run 46025645620
