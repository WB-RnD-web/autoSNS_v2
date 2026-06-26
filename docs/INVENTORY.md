# autoSNS_v2 — M0 INVENTORY (v1 파악 + HyperFrames + 트리거 모델)

> 목적: v2는 **비주얼 레이어(정적 투샷 → HyperFrames 모션그래픽)만** 교체한다.
> TTS·자막·타이밍·업로드·이미지생성·dedupe는 **v1(`WB-RnD-web/autoSNS`)을 재사용**한다.
> 이 문서는 v1을 클론(`../autoSNS_v1_ref`)해 실제 코드를 읽고 정리한 것이다.

작성일: 2026-06-26 · 기준 커밋: v1 `main` HEAD / v2 `main`(README만)

---

## 0. v1 레포 구조 (핵심만)

```
pipeline/
  run_daily.py         # 오케스트레이터: 오늘 주제별 storyboard 루프 → generate→voice→assemble→upload
  generate_images.py   # 투샷 이미지 준비 (static refs | gemini)
  voice.py             # 이중 음성 TTS (edge-tts, 별이=남/별하=여)
  assemble.py          # ffmpeg: 에셋+음성+자막 → 9:16 mp4  ← ★ v2 교체 지점이 여기로 들어감
  upload_youtube.py    # YouTube Data API v3 업로드 (OAuth refresh token)
  collect_news.py      # (참고) 뉴스 RSS 수집·핫이슈 선정 — 현재는 루틴(Claude)이 대체
  config.py            # 공통 경로/규격
  requirements.txt / .env.example
.github/workflows/daily-news.yml   # ★ 트리거 = cron(09:00 KST) + workflow_dispatch (push 아님!)
.claude/skills/sns-reels-maker/SKILL.md  # 루틴(스토리보드 생성) 프롬프트 = JSON 스키마의 출처
output/news/<date>_<topic>_storyboard.json   # 루틴 산출물(시스템 계약). 실 샘플 다수 존재
characters/refs/   # 고정 캐릭터 이미지(static 백엔드가 사용)
```

데이터 흐름:
```
output/news/<date>_<topic>_storyboard.json   (입력 계약)
  → generate_images.py  → output/assets/<date>_<topic>_<assetId>.{png|jpg|mp4|mov}
  → voice.py            → output/assets/<date>_<topic>_voice_<n>.mp3
  → assemble.py         → output/renders/<date>_<topic>_final.mp4
  → upload_youtube.py   → YouTube
```
※ `output/assets/`, `output/renders/`, `*.mp4`, `*.mov` 는 **`.gitignore` 처리됨 → main에 안 올라감.**

---

## 1. 스토리보드 → 영상 변환부 (assemble.py) — 가장 중요

파일: `pipeline/assemble.py`

### 1-1. 타이밍/싱크 ★ (브리핑 핵심 질문 답)
- **실제 TTS 길이로 재계산한다.** `duration`/`captions_srt`는 추정치고 실사용 안 함.
- 로직 (`assemble()` 내부):
  ```python
  voice = find_voice(date, s["n"], topic)        # output/assets/<date>_<topic>_voice_<n>.mp3
  if voice:
      d = ffprobe_dur(voice)                      # ffprobe로 실제 mp3 길이 측정
      dur = round(d + 0.4, 2) if d else float(s["duration"])   # +0.4초 패딩
  else:
      dur = float(s["duration"])                  # 음성 없을 때만 JSON duration 폴백
  ```
- **함의(v2): 샷 길이는 음성이 결정한다.** v2의 HyperFrames 모션 베드는 이 `dur`(샷별 실제 음성길이+0.4s) 이상 길이여야 잘리지 않는다. 임의 타이밍 재발명 금지.

### 1-2. 자막 번인 ★
- **`captions_srt`를 쓰지 않는다.** 샷별 `s["caption"]` 문자열을 ffmpeg `drawtext`로 직접 번인한다.
  - `wrap(text, width=16)`로 줄바꿈 → `textfile`로 drawtext.
  - 위치: 하단 `y=h-text_h-160` (쇼츠 하단 안전영역 고려), 가운데 정렬, 반투명 박스.
  - **화자 색 구분**: 별하=`#FFD23F`(노랑), 별이=`#5BC8FF`(하늘), 기본 white.
  - **자막 팝**: 등장 0.25초간 폰트 46→56px 보간.
  - 출처(credit) 워터마크: 우상단 `drawtext`.
- 폰트: `FONT_PATH` env (기본 `/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf`). Actions에선 `fonts-nanum` apt 설치.
  - ⚠️ 브랜드 폰트는 Pretendard 지정인데 **v1은 NanumGothicBold 사용 중**. v2 브랜드 토큰(Pretendard)과 불일치 → v2에서 폰트 번들/지정 필요.

### 1-3. 에셋 처리 ★★ (v2 통합 지점)
- `find_asset(date, asset_id, topic)`이 **이미 mp4/mov/png/jpg/webp 를 모두 지원**한다.
  탐색 순서: `<date>_<topic>_<assetId>.<ext>` → 없으면 `<date>_<assetId>.<ext>`, 확장자 `mp4,mov,png,jpg,jpeg,webp`.
- **정적 이미지일 때**: `zoompan`(켄번즈) + 화자별 좌우 팬(별하=좌, 별이=우) 적용.
- **비디오일 때**(`shot_clip_cmd`의 `is_img=False` 분기):
  ```
  scale=W:H:force_original_aspect_ratio=increase, crop=W:H, setsar=1, fps=30, <drawtext>
  ```
  즉 **비디오는 켄번즈 없이 scale+crop+자막만** 얹는다. 음성은 별도 mp3를 입힘. `-t dur`로 길이 컷.
- 컷 연결: `concat_xfade_cmd`가 샷 간 `xfade`(영상)+`acrossfade`(음성) 0.3초 크로스페이드. `XFADE<=0`이면 단순 concat.
- 출력 코덱: `libx264 / yuv420p / aac 128k / fps 30 / 1080x1920`. (faststart 플래그는 현재 없음 → v2에서 추가 검토)

### ★ v2 통합 결론(최소 변경 시나리오 = Path A)
> v1 `assemble.py`는 손대지 않거나 거의 안 대도 된다.
> **샷별 HyperFrames 애니메이션 mp4를 `output/assets/<date>_<topic>_<assetId>.mp4` 위치에 만들어 두면**,
> assemble.py가 그걸 비디오 베드로 인식해 자막·음성·전환을 v1 방식 그대로 입힌다.
> 단, 모든 샷이 `asset:"twoshot"` 하나를 재사용하므로 **샷마다 길이가 다른 베드가 필요** → 샷별 mp4를 따로 렌더하거나(파일명에 샷 구분 추가) assemble의 에셋 탐색을 샷별로 확장하는 소폭 수정이 필요. (M2에서 결정)

---

## 2. 이중 음성 TTS (voice.py)

- 엔진: **edge-tts** (Microsoft Edge 읽어주기, **API 키 불필요·무료**).
- 화자 매핑:
  | 화자 | 성별 | 기본 보이스 | rate | pitch | fallback |
  |---|---|---|---|---|---|
  | 별이 | 남 | `ko-KR-HyunsuMultilingualNeural` | -2% | +0Hz | `ko-KR-InJoonNeural` |
  | 별하 | 여 | `ko-KR-SunHiNeural` | +0% | +0Hz | `ko-KR-SunHiNeural` |
  - 전부 env로 덮어쓰기 가능 (`TTS_VOICE_*`, `TTS_RATE_*`, `TTS_PITCH_*`).
- 입력: 샷별 `s["line"]`. 출력: `output/assets/<date>_<topic>_voice_<n>.mp3`.
- 한 샷 실패해도 나머지 진행(해당 샷 무음), 기본→fallback 1회 재시도.
- **v2: 그대로 재사용.** HyperFrames의 자체 TTS(Kokoro)는 쓰지 않음.

---

## 3. 투샷 이미지 생성 (generate_images.py) — ★ 문서/코드 불일치 주의

- **스토리보드 JSON은 `assets_needed[].model = "nano_banana_2"`** 라고 적지만, **실제 코드는 nano_banana를 호출하지 않는다.** `model` 필드는 현재 무시된다.
- 실제 백엔드 (`IMAGE_BACKEND` env):
  - **`static`(기본·무료)**: `characters/refs/`의 고정 캐릭터 이미지를 `assetId`에 매칭해 복사. (`twoshot`, `별`, `anchor` 등 키워드 매칭)
  - **`gemini`(유료)**: Google **Gemini 2.5 Flash Image**(`gemini-2.5-flash-image`, = ".env에서 nano-banana로 지칭")로 `prompt`+레퍼런스 이미지로 생성. `GEMINI_API_KEY` 필요.
- 캐싱/재사용: `reuse:true`지만 코드상 명시적 캐시는 없음. static은 매번 복사, gemini는 매번 생성. (assetId가 같으면 파일명 충돌로 덮어씀)
- 출력: `output/assets/<date>_<topic>_<assetId>.<ext>`.
- **v2 함의**: v2의 모션 베드는 이 투샷 **이미지를 입력으로** HyperFrames에서 애니메이션(켄번즈/패럴랙스/틸트)한다. 즉 generate_images로 만든 정적 투샷 → HyperFrames 모션 → assemble. 이미지 생성부는 v1 재사용.

---

## 4. 유튜브 업로드 (upload_youtube.py + run_daily.py)

- API: **YouTube Data API v3**, scope `youtube.upload`.
- 인증: OAuth 데스크톱 클라이언트. `client_secret.json` + `token.json`(refresh token 캐시) → 무인 갱신. 최초 1회 `--auth-only`로 토큰 발급 후 GitHub Secret에 저장.
- 업로드 메타 (`upload()`):
  - `title[:100]`, `description`, `tags`(기본 `["뉴스","이슈","쇼츠","shorts"]`), `categoryId="25"`(News & Politics), `selfDeclaredMadeForKids=False`.
- **메타 매핑은 run_daily.py가 담당** (`process_topic`의 upload 단계):
  - **제목 우선순위**: `hook_title` > `platforms.youtube.title` > `headline`, 그리고 `#shorts` 없으면 자동 추가.
    - (브리핑은 "title은 platforms.youtube.title 사용"이라 했으나, 실제 코드는 **hook_title 우선**. 단 샘플에선 `youtube.title`이 이미 `"<hook_title> #shorts"`라 결과는 거의 동일.)
  - **설명**: `platforms.youtube.description` 그대로.
  - **privacy**: `sb["privacy"]` 우선 → 없으면 `DEFAULT_PRIVACY` env. ★ 하드코딩 안 함, JSON 존중.
- **v2: 그대로 포팅.** (M4에서 강제 private 드라이런)

---

## 5. GitHub Actions / 시크릿 / dedupe

### 5-1. 트리거 모델 (브리핑 항목 ③) ★
- **v1 현행: cron 기반** — `.github/workflows/daily-news.yml`
  ```yaml
  on:
    schedule:
      - cron: "0 0 * * *"   # 00:00 UTC = 09:00 KST
    workflow_dispatch: { inputs: { stages, only } }
  ```
- **즉, v1에는 "push to main" 트리거가 없다.** 루틴이 오전에 storyboard를 main에 커밋해두면, 09:00 cron이 "오늘 날짜" 파일을 전부 찾아 처리하는 구조.
- **v2 설계(브리핑 지정)는 push 트리거** = v1과 다른 새 모델. M5에서 신규 작성:
  - `on: push: branches:[main], paths:['output/news/**']`
  - 먼저 `workflow_dispatch`로 수동 검증 후 활성화.

### 5-2. ⚠️ 자기 재트리거 루프 — 현재 위험도
- v1은 cron이라 루프 위험 없음. 게다가 **렌더 산출물이 `.gitignore`로 main에 커밋 안 됨** → 파이프라인이 main을 변경하지 않음.
- **v2가 push 트리거로 바뀌면**: 파이프라인이 main에 무엇이든 커밋하는 순간 무한루프. → **파이프라인은 main에 커밋 금지.** 산출물/로그/ledger는 Actions artifacts나 별도 브랜치. dedupe ledger도 main에 쓰지 말 것. (`[skip ci]` + `paths-ignore`는 보조)

### 5-3. GitHub Secrets / Vars (v1과 동일 이름 재사용)
| 종류 | 이름 | 용도 |
|---|---|---|
| Secret | `YT_CLIENT_SECRET_JSON` | OAuth client_secret.json 내용 |
| Secret | `YT_TOKEN_JSON` | OAuth token.json(refresh token) 내용 |
| Secret | `GEMINI_API_KEY` | (옵션) 이미지 생성 |
| Secret | `ANTHROPIC_API_KEY` | (옵션) 스마트 대본 |
| Var | `DEFAULT_PRIVACY` | JSON에 privacy 없을 때 폴백 (워크플로 기본 `'public'`) |
- 로컬 env(.env.example): 위 + `IG_*`, `THREADS_*`, `HIGGSFIELD_API_KEY`, `FONT_PATH`, `TTS_*`.
- `.gitignore`: `pipeline/.env`, `pipeline/secrets/`, `*.mp4`, `*.mov`, `output/assets/`, `output/renders/`.

### 5-4. dedupe(중복방지) — 실제 구현 ★ 브리핑과 차이
- **"이미 올린 뉴스 스킵" 같은 업로드 ledger는 v1에 없다.**
- 실제 중복 방지 장치:
  1. `collect_news.py`의 `seen` 집합은 **뉴스 키워드/제목 중복 제거**(토픽 선정 단계)일 뿐, 업로드 dedupe 아님.
  2. 파이프라인 전체가 **"오늘(KST) 날짜 파일만" 처리**하고 과거/최신으로 폴백 안 함 → cron 1일 1회 + 오늘파일 매칭이 사실상의 중복방지.
- **v2 함의**: push 트리거에선 "오늘 파일만" 가정이 깨진다(같은 파일 재push, 과거 파일 등). → v2는 **"이번 push에서 git diff로 추가/변경된 storyboard만 처리" + 처리완료 ledger(artifacts/별도 브랜치)** 를 M5/M6에서 신설해야 함.

---

## 6. 루틴 스토리보드 JSON 스키마 (실 샘플로 확정)

샘플 확보: `docs/samples/2026-06-26_economy_storyboard.json`(public), `docs/samples/2026-06-26_politics_storyboard.json`(unlisted).

- 브리핑 2번 스키마와 **실 샘플 일치 확인**. 키: `date, topic, privacy, topic_keyword, headline, hook_title, total_sec, shots[], assets_needed[], captions_srt, sources, credit, platforms{youtube,instagram,threads}, notes`.
- shots: 15개(샘플), 각 `{n,type:"anchor",asset:"twoshot",start,duration,speaker:"별하|별이",line,caption,visual}`.
- 모든 샷 `asset:"twoshot"` 1장 재사용 확인 → v2 모션은 "투샷 1장 애니메이션"이 출발점.
- `privacy`: economy=`public`, politics=`unlisted` 확인 → JSON 존중 필수.
- `captions_srt` 존재하나 **assemble.py가 안 씀**(위 1-2). 자막은 `shots[].caption` 기반.
- `notes`에 "배경음 없음·자막 번인" → BGM 기본 OFF 준수.

---

## 7. HyperFrames 스킬 (설치·핵심 파악)

- 설치: `npx skills add heygen-com/hyperframes` 완료. 스킬 본체 위치: `~/.codex/.tmp/plugins/plugins/hyperframes/skills/`
  (Windows/OneDrive에서 심볼릭링크 생성이 막혀 v2 폴더 `.agents/skills/`에는 링크가 안 잡힘 → **M1 전에 v2 레포로 실제 복사 필요**. 또는 렌더는 `npx hyperframes` CLI만 쓰면 스킬 파일 위치는 문서 참고용.)
- 핵심 개념:
  - **HTML = 영상의 소스.** composition = HTML + `data-*`(타이밍) + GSAP 타임라인 + CSS.
  - 렌더: **`npx hyperframes render`** → 헤드리스 Chrome로 프레임 캡처 + FFmpeg 인코딩 → mp4.
    - 요구사항: **Node ≥ 22, FFmpeg, Chrome**. 플래그: `--fps 24/30/60`, `--quality draft/standard/high`, `--output`, `--docker`(재현성), `--gpu`.
  - CLI: `init`(스캐폴드), `lint`, `inspect`(헤드리스 레이아웃 검사), `preview`, `render`, `tts`(Kokoro), `transcribe`, `doctor`.
  - 캡션/자막 컴포넌트(`references/captions.md`), 트랜지션 카탈로그, 오디오리액티브, 타이포 등 풍부.
  - 규칙: 결정론적(no `Math.random`/`Date.now`), 무한반복 금지, 비디오는 `muted` + 별도 `<audio>`, 타임라인 `window.__timelines` 등록.
- **자막 합성 결정(Path A)**: HyperFrames가 자막까지 합성할 수도 있으나, **v1 자산 합치기 최소화를 위해 자막은 v1 ffmpeg drawtext 유지**, HyperFrames는 **투샷 모션 베드(mp4)만 렌더**가 1순위. (captions.md 방식은 Path B/후순위에서 검토.)

### ⚠️ Actions 실현성 리스크 (HyperFrames in CI)
- 헤드리스 Chrome 필요 → 러너에 Chrome + 시스템 libs 설치(Playwright/Puppeteer `install-deps`). Node 22 필요(v1 워크플로는 Python만 설치 중 → v2는 Node 셋업 추가).
- 50초·30fps ≈ 1500프레임 → 렌더 무겁고 느릴 수 있음. M1에서 **로컬 렌더 1회 시간·RAM 실측**으로 무료 러너 가능성 판단.

---

## 8. v2가 바꾸는 것 / 유지하는 것 (요약)

| 영역 | v1 | v2 |
|---|---|---|
| 대본 생성(루틴) | sns-reels-maker 스킬 → main 커밋 | **유지** |
| 투샷 이미지 | static refs / gemini | **유지**(모션 입력으로 사용) |
| 비주얼 베드 | 정적 이미지 + ffmpeg 켄번즈 | **★ HyperFrames 애니메이션 mp4로 교체** |
| TTS | edge-tts 이중음성 | **유지** |
| 자막 | ffmpeg drawtext(caption) | **유지**(Path A) |
| 타이밍 | 실 TTS 길이 기반 | **유지** |
| 합치기/전환 | ffmpeg xfade | **유지**(베드만 교체) |
| 업로드 | YouTube v3, JSON privacy | **유지/포팅** |
| 트리거 | cron 09:00 | **★ push to main (신규, 루프가드)** |
| dedupe | 오늘파일+cron 1회 | **★ git diff + ledger(신규)** |

---

## 9. 다음 단계(M1) 전 확인 필요 사항 / 결정 포인트

1. **자막 책임 주체**: Path A에서 자막을 v1 ffmpeg drawtext로 유지(권장) vs HyperFrames captions 합성 — 권장안대로 진행할지.
2. **샷별 베드 길이**: 모든 샷이 `twoshot` 1장 재사용인데 샷 길이는 음성마다 다름 → (a) 샷별 mp4 개별 렌더 vs (b) 충분히 긴 1개를 샷마다 트림. assemble 에셋 탐색 소폭 수정 필요.
3. **폰트**: v1 NanumGothicBold vs v2 브랜드 Pretendard — v2부터 Pretendard 번들 적용할지.
4. **HyperFrames 스킬 파일**을 v2 레포로 실제 복사(심볼릭링크 실패) 할지.
5. **렌더 위치**: M1 실측 후 무료 러너 불가 시 "렌더 로컬 / 업로드만 Actions" 분리 검토.
</content>
</invoke>
