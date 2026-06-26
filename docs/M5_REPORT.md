# M5 — GitHub Actions 배선 리포트

> 목표: `on: push to main` + `paths: output/news/**`, deps 설치 → push diff로 신규 JSON 처리 → 업로드(privacy 준수), **자기 재트리거 루프 가드**. 먼저 `workflow_dispatch`로 수동 검증.

작성일: 2026-06-26 · 워크플로: [.github/workflows/shorts.yml](../.github/workflows/shorts.yml)

## 구성 요약
- **트리거**: `push`(branches: main, paths: `output/news/**_storyboard.json`) + `workflow_dispatch`(수동, 입력: storyboard/force_private/no_upload).
- **러너 셋업**: Node 22, Python 3.12, apt(ffmpeg + 헤드리스 Chrome 시스템 libs + fonts-nanum), `pip install -r requirements`, `npx hyperframes doctor`, `puppeteer browsers install chrome-headless-shell`.
- **자격증명**: 시크릿 → 파일(`YT_CLIENT_SECRET_JSON`, `YT_TOKEN_JSON` → `pipeline/secrets/*.json`).
- **대상 선정**: push면 `git diff --diff-filter=AM <before> <sha>`로 추가/변경된 storyboard만, dispatch면 입력 경로 또는 오늘 날짜 자동.
- **실행**: `python run_pipeline.py <files...> --force-private`(테스트 기본). 업로드는 privacy 준수(politics=unlisted), 자격증명 없으면 자동 skip.
- **산출물**: `output/renders/*.mp4`를 **artifacts**로만 업로드(7일 보관).

## ⚠️ 자기 재트리거 루프 가드 (핵심)
- `permissions: contents: read` — **레포에 쓰지 않음**.
- 워크플로가 **어떤 커밋/푸시도 하지 않음** → 새 push 미발생 → 루프 없음.
- 산출물(mp4/assets/renders)은 `.gitignore` 처리 → 애초에 커밋 대상 아님.
- dedupe ledger도 main에 쓰지 않음(현재는 git diff 기반 신규감지로 충분, 영구 ledger는 M6에서 artifacts/별도 브랜치로).

## ✅ 활성화 절차 (반드시 이 순서로)
1. **시크릿 등록** (Settings → Secrets and variables → Actions):
   - `YT_CLIENT_SECRET_JSON`, `YT_TOKEN_JSON` (필수, 업로드용 — [SETUP.md](SETUP.md) 참고)
   - (옵션) `GEMINI_API_KEY`, var `DEFAULT_PRIVACY`
2. **수동 검증 1 (렌더만)**: Actions → 이 워크플로 → Run workflow → `no_upload=true`, storyboard 비움(또는 샘플 경로). 렌더 성공·artifacts 확인.
3. **수동 검증 2 (강제 private 업로드)**: `force_private=true`, `no_upload=false`로 1건 업로드 → 유튜브 비공개 확인.
4. **운영 전환**: 검증 OK면 루틴이 `output/news/`에 커밋하는 push가 자동 트리거. (운영에서 JSON privacy를 그대로 따르려면 push 경로에서 `--force-private` 제거 — 현재는 안전상 push도 강제 private.)

## 로컬 검증 (이미 통과)
- `run_pipeline.py`로 economy 2샷: 렌더 OK + 업로드 매핑(dry-run, privacy=private) OK.
- 단일 엔트리포인트 `make_short.py`로 generate_images→voice→베드→자막/음성→xfade 전체 동작.

## 미검증(환경상 로컬 불가) — 수동 검증 필요
- **Actions 러너에서의 헤드리스 Chrome 부트스트랩**: `npx hyperframes`가 chrome-headless-shell 자동 다운로드 + apt 시스템 libs로 동작하는지 (M1 로컬은 Windows). → workflow_dispatch `no_upload=true`로 first-run 확인 필수.
- 무료 러너 누적 시간: 주제 5개 × 샷 ~15개 = 약 75 베드 렌더. M1 기준 베드당 ~10s지만 러너 2코어라 더 느릴 수 있음 → 60분 timeout. 초과 시 M6 캐싱/`--quality draft`/주제 분할.

## 다음 (M6 하드닝)
- npx/hyperframes/puppeteer-chrome 캐싱(actions/cache), 재시도, 타임아웃 튜닝.
- dedupe ledger(이미 업로드한 영상 재처리 방지) — artifacts 또는 별도 브랜치.
- 로깅/실패 알림.
</content>
