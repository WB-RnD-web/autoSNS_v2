# Gumiho Games (@GumihoGames)

영어 채널. AI 모델 6개가 한국 서바이벌 예능식 게임을 하고, 구미호 '구미'가 진행한다. 왕별이와는 토큰·재생목록이 따로다.

## 흐름

1. `run_match.py` — 같은 게임을 N판 돌린다. seed = 날짜×100 + 판 번호. 역할·순서·투표·승패는 코드가 정한다.
2. `drama_score` — 코드가 매긴 점수로 볼 만한 판을 고른다. 모델 답을 메운 비율이 15%를 넘거나 욕설 필터에 걸린 판은 버린다.
3. `render.py` — 비트마다 화면 한 장(PIL 1920×1080)을 만든다. 목소리는 Spark Supertonic 영어 프리셋이다. ffmpeg로 mp4, 자막, 챕터, 썸네일을 만든다.
4. `upload.py` — **항상 비공개로 올린다.** 사람이 스튜디오에서 확인하고 공개한다. 점검용 판은 코드가 업로드를 막는다.

## 형식

시청자는 처음부터 여우가 누군지 안다. 모든 발언 옆에는 그 모델의 속마음(thought)이 뜬다. 출연자끼리는 서로의 속마음을 모른다.

## Spark 사용 원칙

Spark는 공용 서버다. 2026-09-29에 작업이 몰려 한 번 멈췄다. 그래서 다음을 지킨다.
- LLM은 한 번에 한 건만 보낸다.
- `/queue`의 대기가 `GUMIHO_SPARK_MAX_WAITING`(6)을 넘으면 기다린다.
- 실패하면 점점 길게 쉬었다가 다시 보낸다.
- 목소리 합성은 동시 2건까지 보낸다.
- 그림은 기본 해상도만 쓴다.

## 출연진

`roster.json`은 **후보 목록(우선순위 순)**이다. 실제 출연 6명은 대국 전에 코드가 정한다.

- **출연 전 점검:** `players.select_cast`가 후보마다 짧은 질문을 한 번 던진다. 45초 안에 형식대로 답한 모델만 출연한다.
- **대기 명단:** 떨어진 모델 자리는 뒤쪽 후보가 채운다. 같은 이름이 여러 줄이면 뒤 줄은 그 이름의 대체 모델이다(예: Kimi K3 → K2.6).
- **대국 중 실패:** 한 턴은 75초만 기다리고 그 턴만 메운다. 메움이 15%를 넘으면 그 판은 버린다.
- **현재 우선순위:** Gemma(Spark) · GPT-OSS · Nemotron · Kimi · DeepSeek · GLM · Mistral · Phi · Jamba · Granite.
- **2026-09-29 실측:**
  - Mistral Large 2는 이 계정에서 404(열려 있지 않음)가 났다.
  - DeepSeek v4.1 Flash는 3분 넘게 응답하지 않는 일이 잦았다.
- **Spark 게이트웨이:** `model` 값을 무시하고 늘 Gemma 4가 답한다(실측). 다른 모델을 Spark에서 돌리려면 게이트웨이에 모델 라우팅을 넣어야 한다.
- **돈이 드는 호출 금지(사용자 원칙, 2026-09-29).** 공개 모델은 왕별이의 `NVIDIA_API_KEY`(무료)로만 부른다.
  - Claude API·OpenRouter 같은 유료 경로는 `GUMIHO_ALLOW_PAID=1`이 없으면 코드가 실행을 멈춘다.

## 실행

```bash
python gumiho/test_gumiho.py                                     # 오프라인 테스트
python gumiho/run_match.py --matches 1 --backend spark           # 모든 자리를 Gemma로(점검용, 공개 금지)
python gumiho/render.py output/gumiho/matches/<판>.json --frames-only
```

- **Actions 수동 실행:** `.github/workflows/gumiho.yml`
- **업로드:** 시크릿 `YT_TOKEN_JSON_GUMIHO`가 필요하다. Gumiho 채널 계정으로 받은 OAuth 토큰이다.
