# M4 — 업로드 이식 리포트

> 목표: v1 유튜브 업로드 포팅 → 강제 private 드라이런 성공, `title/desc`=JSON, privacy 준수 확인.

작성일: 2026-06-26

## 포팅한 것 (v2 `pipeline/`)
- [pipeline/upload_youtube.py](../pipeline/upload_youtube.py) — v1 **그대로 복사**(YouTube Data API v3, OAuth refresh token, resumable upload).
- [pipeline/config.py](../pipeline/config.py) — v1 그대로(경로·env·load_dotenv).
- [pipeline/upload_from_storyboard.py](../pipeline/upload_from_storyboard.py) — **신규**: v1 `run_daily.process_topic`의 업로드 단계 매핑을 추출 + 드라이런/강제privacy 안전장치.
- `.env.example`, `requirements.txt` — v1에서 포팅.

## 메타 매핑 (v1 run_daily와 동일)
- **제목**: `hook_title` > `platforms.youtube.title` > `headline`, `#shorts` 자동 부착.
- **설명**: `platforms.youtube.description` 그대로.
- **privacy**: JSON `privacy` > env `DEFAULT_PRIVACY`. `--force-private`로 테스트 시 강제 private.
- 태그 `["뉴스","이슈","쇼츠","shorts"]`, categoryId `25`(News & Politics), `selfDeclaredMadeForKids=False`.

## 드라이런 검증 결과 ✓
| 샘플 | JSON privacy | 적용 privacy | 제목 |
|---|---|---|---|
| economy | public | **private** (`--force-private` 적용) | `이게 40년 만에 처음이라고? #shorts` |
| politics | unlisted | **unlisted** (force 없음 → JSON 존중) | `이틀 전에 집 3채 팔았다고? #shorts` |

→ **privacy 준수**(politics=unlisted) + **테스트 강제 private** + **title/desc=JSON** 모두 확인.

## 남은 것 (자격증명 필요)
- **실제 업로드는 YouTube OAuth 자격증명 필요** — 아직 미연결.
  - 로컬: `python upload_youtube.py --auth-only` 1회 → `pipeline/secrets/token.json` 발급 → 내용을 GitHub Secret `YT_TOKEN_JSON`에 저장 (+ `YT_CLIENT_SECRET_JSON`).
  - 자격증명 연결되면 `upload_from_storyboard.py --force-private`로 **실제 private 업로드 1건** 검증 가능.
- 시크릿 이름은 v1과 동일: `YT_CLIENT_SECRET_JSON`, `YT_TOKEN_JSON`, (옵션) `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, var `DEFAULT_PRIVACY`.

## 다음 (M5)
- GitHub Actions 배선: `on: push to main` + `paths: output/news/**`, deps(Node22+Chrome+ffmpeg+Pretendard) 설치, git diff로 신규 JSON 처리, 업로드(privacy 준수), **자기 재트리거 루프 가드**, 먼저 `workflow_dispatch`로 수동 검증.
- 그 전에 render(build.py)와 upload를 묶는 단일 엔트리포인트 정리 필요.
</content>
