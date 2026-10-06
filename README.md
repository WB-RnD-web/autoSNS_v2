# data/ai-news-feed — 자동 생성(손대지 않는다)

- 만든 곳: .github/workflows/ai-news-feed.yml (main) · pipeline/ai_news_feed.py
- 읽는 곳: python pipeline/ai_news.py feed / check / push, ai-news-run.yml
- 파일: feed/ai/<DATE>_<am|pm>.json — 48시간 안 AI 기사(제목·주소·published_at·본문 앞 4,000자)
- 매번 고아 커밋 하나로 강제 push 한다(최근 4일치 파일만 남긴다).
- 마지막 생성: 2026-10-07 01:15 KST · run 37493864546
