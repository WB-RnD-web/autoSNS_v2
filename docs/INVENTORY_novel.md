# INVENTORY — 소설(novel) 연재 파이프라인 M0 파악 보고

> 대상: autoSNS_v2 / main `fb2d249` 기준(최신 fetch·pull 완료).
> 목적: 소설(16:9 가로 · 약 10분 장편 · 정적 배경 1장 + 자막 번인 + 단일 내레이터)을 위한
> **별도** 파이프라인을 만들기 위해, 기존 쇼츠 스택에서 **재활용 가능한 것**과 **그대로 쓰면 안 되는 것**을 식별.

---

## 0) 레포 현황 요약

```
pipeline/
  config.py               공통 설정(경로/TZ/규격). VIDEO_W,H=1080x1920(9:16) — 쇼츠 전용
  voice.py                edge-tts TTS(별이=남/별하=여), 키 불필요 ★재활용
  motion_short.py         9:16 모션그래픽 렌더러(HyperFrames+GSAP) ✗소설 비재활용
  generate_images.py      static(고정이미지) | gemini(유료) 이미지 백엔드 △부분재활용
  upload_youtube.py       YouTube OAuth + videos.insert ★재활용(스코프 확장 필요)
  upload_from_storyboard.py  스토리보드→YT 메타 매핑(#shorts 자동부착) △메타로직만 참고
  run_pipeline.py         쇼츠 오케스트레이터 ✗소설 비재활용(별도 작성)
  ledger.py               dedupe ledger(cache 영속, 레포 미커밋) △패턴 참고
  upload_instagram.py/upload_threads.py/host_video.py  IG/Threads/Cloudinary(소설 무관)
.github/workflows/
  shorts.yml              쇼츠 트리거(push routine/** ·main, paths storyboard) ★패턴 재활용
docs/
  ROUTINE_PROMPT.md       쇼츠 루틴 프롬프트 — ★브랜치 리셋 패턴의 출처(주의)
```

소설 파이프라인은 위 쇼츠 자산을 **건드리지 않고** 별도 파일로 추가한다(과제 13).

---

## M0 질문별 결론

### 1) 재활용할 TTS · YouTube 업로드 모듈

**TTS — `pipeline/voice.py` + `motion_short.synth_vo()` (재활용 ✅)**
- 제공자: **edge-tts**(Microsoft Edge "읽어주기" / Azure Neural), **API 키 불필요·무료**. 로컬 설치본 `edge-tts 7.2.8` 확인.
- 호출 2가지:
  - 라이브러리: `edge_tts.Communicate(text, voice, rate, pitch).save(out_mp3)` (voice.py)
  - CLI: `python -m edge_tts --voice <V> --rate <R> --text <T> --write-media out.mp3` (motion_short.py)
  - ⚠️ CLI `--text` 인자 방식은 장문에서 명령행 길이 한계 위험 → 소설은 **라이브러리 API(save) 또는 stdin** 사용 권장.
- 포맷: **mp3**(단일 내레이터). 소설은 남/여 구분 불필요 → 단일 보이스(예 `ko-KR-InJoonNeural`/`ko-KR-HyunsuMultilingualNeural`) 1개로 낭독.
- 길이 측정: `ffprobe -show_entries format=duration` (motion_short.probe_dur) 재사용.

**YouTube 업로드 — `pipeline/upload_youtube.py` (재활용 ✅, 단 스코프 확장 필요 ⚠️)**
- 인증: OAuth Installed App. `pipeline/secrets/client_secret.json` + `token.json`(리프레시 토큰 자동 갱신). CI 에선 시크릿 `YT_CLIENT_SECRET_JSON`/`YT_TOKEN_JSON` → 파일로 떨군다(shorts.yml step 3).
- 업로드: `videos().insert(part="snippet,status", ...)` — `MediaFileUpload(resumable)`.
- 메타: `snippet.title/description/tags/categoryId`, `status.privacyStatus`, `selfDeclaredMadeForKids=False`.
- **현재 스코프 = `youtube.upload` 하나뿐** → 재생목록 API 호출 불가(5번 참조). 소설용은 별도 업로드 모듈에서 **확장 스코프 토큰**을 사용해야 한다.

### 2) ★TTS 길이 한계 — 실측 결과

**단일 합성으로 ~10분(목표) 달성 가능. 검증 완료.**
- 테스트: 한국어 **3,572자**를 `edge_tts.Communicate(...).save()` **단일 호출** →
  - 합성 시간 **27.2s**, mp3 **3.5MB**, 재생 길이 **583.4초 = 9분 43초**.
- 환산: 한국어 약 **365자/분** → 10분 ≈ **3,600~3,800자**. 단일 호출로 무리 없음.
- 한계/주의:
  - edge-tts 는 내부적으로 WebSocket 스트리밍이라 매우 긴 1회 요청은 간헐적 네트워크 실패 가능 → **세그먼트 분할 + concat 권장**(아래).
  - CLI `--text`(motion_short 방식)는 OS 명령행 길이 제한에 걸릴 수 있음 → 라이브러리 save() 사용.

**설계 결론 — "세그먼트별 합성 → ffmpeg concat" 채택 (길이 때문이 아니라 자막 타이밍 때문에도 필요)**
- render-spec 의 `segments[]` 각각을 개별 mp3 로 합성 → `ffprobe` 로 길이 측정 →
  누적 오프셋으로 **자막(SRT/ASS) 타이밍** 산출 → 자막 번인 + 오디오 concat.
- 이렇게 하면 (a) 단일 장문 요청 실패 위험 분산, (b) **자막을 낭독에 정확히 정렬**(번인 핵심), (c) 단일 내레이터 톤 유지(보이스 1개) 를 동시에 만족.
- concat: ffmpeg concat demuxer(`-f concat`) 또는 `[a0][a1]...concat=n=N:v=0:a=1`.

### 3) 루틴 실행 런타임(shell+git+파일 R/W, Asia/Seoul TZ)

**가능 ✅.**
- 루틴(스토리보드/상태파일을 쓰는 주체)은 쇼츠와 동일하게 **Claude Code 에이전트가 git push** 로 동작(ROUTINE_PROMPT.md §5). shell·git·파일 R/W 전부 가능.
- 소설 루틴은 추가로 **상태 파일을 읽고 갱신**해야 함: `novel/library.json`, `novel/series/<id>/canon.json` 을 `git checkout routine/novel` 후 읽기 → 갱신 → 커밋. (쇼츠처럼 reset 하면 안 됨 — 10번 참조)
- TZ: shorts.yml 이 `env: TZ: Asia/Seoul`, 루틴은 `TZ=Asia/Seoul date +%F` 로 KST 강제(레포에 이미 확립된 관례). 소설 워크플로/루틴도 동일 적용.

### 4) 배경 이미지 생성(기존 모델)을 16:9로

**부분 재활용 △ — 호출은 재사용하되 비율 정규화는 ffmpeg 로.**
- 기존 `generate_images.py`:
  - `static` 백엔드 = `characters/refs/` 고정 이미지 복사(무료·항상 동작).
  - `gemini` 백엔드 = **유료 결제 필요**, `gemini-2.5-flash-image`, 입력은 프롬프트(+레퍼런스). **종횡비 파라미터 없음** — 출력 비율을 보장하지 않음.
- 소설 16:9(1920x1080) 전략:
  - 배경은 **series 당 1회** `background.prompt` 로 생성 → `series_id` 로 캐싱(`novel/series/<id>/bg.*` 또는 산출물 캐시)·재사용. 회차마다 **켄번즈(Ken Burns) 크롭/줌**으로 미세 변화.
  - 생성 이미지를 항상 ffmpeg `scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080` 로 **16:9 정규화**(모델이 정확히 16:9를 안 줘도 안전).
  - 무료 스택 우선: 배경 1장이므로 `gemini`(유료) 대신 정적/외부 무료 이미지도 허용. 렌더러는 **소스 불문 16:9로 정규화**하므로 백엔드 교체 자유.

### 5) ★YouTube 재생목록(playlist) API

**현재 모듈로는 불가 — 스코프 확장 필요 ⚠️ (액션 아이템).**
- `playlists.insert`(생성), `playlistItems.insert`(추가)는 **쓰기 스코프** 필요:
  `https://www.googleapis.com/auth/youtube` 또는 `youtube.force-ssl`.
- 현재 `upload_youtube.SCOPES = ["...auth/youtube.upload"]` 만 → 업로드 전용. 재생목록 호출 시 403.
- **필요 조치**: 소설 업로드 모듈에서 스코프를 `["...youtube.upload", "...youtube"]`(또는 force-ssl)로 잡고 **재인증 → 새 `token.json` 발급 → `YT_TOKEN_JSON` 시크릿 갱신**. (쇼츠 토큰과 분리하려면 `YT_TOKEN_JSON_NOVEL` 등 별도 시크릿 권장 — 쇼츠 무영향.)
- 동작: series 당 재생목록 1개. `series_title` 로 검색→없으면 `playlists.insert` 생성→ID 캐시(`canon.json` 또는 `library.json`) → 업로드 후 `playlistItems.insert` 로 회차 추가.

---

## ★ 상태/브랜치 — 쇼츠와의 결정적 차이 (주의)

| 항목 | 쇼츠(기존) | 소설(신규, 반드시) |
| --- | --- | --- |
| 브랜치 | `routine/<topic>` — **매일 리셋** | `routine/novel` — **영구 누적** |
| 루틴 git | `git checkout -B routine/<slug> origin/main` → `push -f` (ROUTINE_PROMPT.md:123,126) | `git fetch && git checkout routine/novel`(원격 추적, **reset/`-B origin/main` 금지**) → commit → `git push`(force 아님) |
| 상태 파일 | 없음(매일 새 storyboard 1개) | `novel/library.json`, `novel/series/<id>/canon.json` **누적 커밋** |
| 산출물 | `.gitignore`(mp4/assets/renders) — 미커밋 | 동일(렌더 산출물은 유튜브로만, 레포 미커밋) |
| 파이프라인 커밋 | 안 함(`permissions: contents: read`) | **안 함**(동일) — 파이프라인은 상태파일을 쓰지 않는다 |

- ⚠️ **쇼츠의 `checkout -B routine/<slug> origin/main` + `push -f` 패턴을 소설에 쓰면 canon/library 가 매일 날아간다.** 소설 루틴 프롬프트는 이 패턴을 **금지**하고, 원격 `routine/novel` 을 추적·누적하도록 작성해야 함.
- `.gitignore` 확인: 현재 `novel/` 경로를 무시하는 규칙 없음 → `novel/**/*.json` 은 정상 커밋된다. (단 `*.mp4` 등 산출물은 무시 — 의도대로.)

## 트리거 루프 가드(쇼츠에서 확립, 소설도 동일 적용)

- shorts.yml: `permissions: contents: read` — **워크플로가 레포에 커밋/푸시하지 않음** → 자기 재트리거 없음. 소설 워크플로도 동일하게 `contents: read`.
- 소설 워크플로 트리거: `on.push: branches: [routine/novel], paths: [output/novel/**/ep*.json]` + `workflow_dispatch`.
- 처리 대상: 이 push 의 **git diff 로 새로 추가된 `output/novel/**/ep*.json` 만** 렌더(과제 9).

---

## 다음 단계에 필요한 입력(차단 요소)

- **Part A(소설 루틴 프롬프트 + render-spec JSON 스키마)가 이번 대화에 미첨부.**
  M0(파악)은 완료했으나, **6번(스키마 파서) 이후 구축**은 render-spec 의 정확한 필드
  (`segments[]` 구조, `background.prompt`, `narration_full`, `platforms.youtube.title/description`,
  `series_id`/`series_title`, `content_rating`, `episode` 번호 등)가 필요.
- → Part A 원문을 주시면 그 스키마에 맞춰 파서·렌더러·업로드를 구현한다.

## 재활용/신규 매핑 한눈에

| 기능 | 소스 | 소설에서 |
| --- | --- | --- |
| TTS | `voice.py`/`motion_short.synth_vo` (edge-tts) | ✅ 재활용(단일 보이스, 세그먼트 합성+concat) |
| 길이 측정 | `motion_short.probe_dur` (ffprobe) | ✅ 재활용 |
| YT 인증 | `upload_youtube.get_service` | ✅ 재활용 + **스코프 확장** |
| YT 업로드 | `upload_youtube.upload` | △ 참고(16:9 일반영상·#shorts 금지·재생목록 추가로 신규 래퍼) |
| 메타 매핑 | `upload_from_storyboard.build_meta` | △ 참고(#shorts 부착 로직 **제거**) |
| 이미지 | `generate_images._gemini_one`/static | △ 재활용 + **ffmpeg 16:9 정규화·series 캐시** |
| ledger/dedupe | `ledger.py` | △ 패턴 참고(키=series_id+episode, cache 영속) |
| 렌더러 | `motion_short.py`(HyperFrames) | ✗ **비재활용** — 신규 정적배경+자막번인 렌더러 |
| 오케스트레이터 | `run_pipeline.py` | ✗ **비재활용** — 신규 `run_novel.py` |
| 워크플로 | `shorts.yml` | △ 패턴 참고 — 신규 `novel.yml`(트리거/루프가드 동일 사상) |
