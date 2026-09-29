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

`roster.json`에 있다.

| 이름 | 연결 | 모델 |
|---|---|---|
| Claude | `anthropic` | `claude-sonnet-5-5` |
| Gemma | `spark` | Spark 게이트웨이(Gemma 4 26B-A4B) |
| GPT-OSS | `openai` | `openai/gpt-oss-120b` |
| Nemotron | `openai` | `nvidia/nemotron-3-super-120b-a12b` |
| Qwen | `openai` | `qwen/qwen3.6-35b-a3b` |
| Llama | `openai` | `meta-llama/llama-4-maverick` |

- **Spark 게이트웨이:** 2026-09-29 실측으로 `model` 값을 무시하고 늘 Gemma 4가 답한다.
- **공개 모델 4종:** OpenRouter로 부른다. ID는 2026-09-29 OpenRouter 목록 기준이다.
  - 주소: 저장소 변수 `GUMIHO_OPENAI_BASE` = `https://openrouter.ai/api/v1`
  - 키: 시크릿 `GUMIHO_OPENAI_KEY`
- **비용 추정:** 편당(5판) 공개 모델 $0.1 미만, Claude 약 $0.7.

## 실행

```bash
python gumiho/test_gumiho.py                                     # 오프라인 테스트
python gumiho/run_match.py --matches 1 --backend spark           # 모든 자리를 Gemma로(점검용, 공개 금지)
python gumiho/render.py output/gumiho/matches/<판>.json --frames-only
```

- **Actions 수동 실행:** `.github/workflows/gumiho.yml`
- **업로드:** 시크릿 `YT_TOKEN_JSON_GUMIHO`가 필요하다. Gumiho 채널 계정으로 받은 OAuth 토큰이다.
