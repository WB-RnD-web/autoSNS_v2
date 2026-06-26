# M6 — 하드닝 리포트

> 목표: 캐싱·타임아웃·재시도·dedupe·로깅.

작성일: 2026-06-26

## 추가된 것

### 1. dedupe ledger ([pipeline/ledger.py](../pipeline/ledger.py))
- 키 `<date>_<topic>` 기준으로 **이미 업로드한 스토리보드 재처리 방지**.
- `run_pipeline.py --use-ledger`: ledger에 있으면 렌더/업로드 건너뜀(SKIP).
- 업로드 **성공 시에만** 마킹(dry-run/skip은 마킹 안 함).
- ⚠️ **main에 쓰지 않음** — ledger는 `output/ledger.json`(gitignore). Actions에선 `actions/cache`로 런 간 영속 → 자기 재트리거 루프 안전.
- 로컬 검증: 키 선등록 시 SKIP, 없으면 정상 처리 ✓.

### 2. 캐싱 (workflow)
- `actions/cache`: `~/.npm` + `~/.cache/puppeteer`(헤드리스 Chrome) — `npx hyperframes`·Chrome 재다운로드 방지.
- `setup-python` pip 캐시(requirements 기준).
- ledger 캐시: `key: ledger-<run_id>` + `restore-keys: ledger-` → 매 런 최신 ledger 복원·갱신.

### 3. 재시도
- **베드 렌더**(`bed.render_bed`): 전환적 Chrome 실패 시 최대 2회 재시도 + 출력 파일 유효성 검사.
- **업로드**(`run_pipeline.upload_with_retry`): 전환적 실패 시 최대 2회 재시도.

### 4. 로깅
- `run_pipeline.py --log <path>`: 스토리보드별 결과(video/uploaded/skipped/error)를 JSON으로 기록.
- workflow: `output/run_log.json` + `output/ledger.json` + 렌더 mp4를 **artifacts**로 업로드.

### 5. 타임아웃
- workflow `timeout-minutes: 60`. 베드 렌더는 quality `draft/standard/high` 선택 가능(CI는 standard, 필요시 draft로 단축).

## 검증 (로컬)
- `--use-ledger --log` 정상 동작, dedupe SKIP 확인, JSON 로그 생성 확인.
- 전체 pipeline 모듈 `py_compile` 통과, workflow YAML 유효(11 steps).

## 남은 것(환경상 로컬 불가 — Actions에서 검증)
- 실제 러너에서 캐시 히트율·헤드리스 Chrome 부트스트랩·누적 렌더 시간.
- 실제 업로드 + ledger 마킹(자격증명 필요).

## 강화 여지(선택, 차후)
- ledger를 별도 `ledger` 브랜치로 두면 cache 만료에도 강한 보장(현재는 cache+git diff로 충분).
- 실패 알림(Slack/이슈), 부분 실패 시 재시도 큐.
</content>
