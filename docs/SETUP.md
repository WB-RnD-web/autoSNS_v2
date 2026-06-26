# autoSNS_v2 셋업 가이드

v2를 로컬/Actions에서 돌리기 위한 준비. (v1과 시크릿 이름 동일 — v1 것 재사용 가능)

## 로컬 실행

### 1. 도구
- **Node ≥ 22**, **Python 3.12**, **FFmpeg**(PATH 등록).
  - 현재 로컬은 FFmpeg를 `C:\Users\zxczx\tools\ffmpeg-...\bin`에 설치·PATH 등록함. `make_short.py`는 PATH에 없으면 이 경로로 폴백.
- Python 패키지: `pip install -r pipeline/requirements.txt` (+ `edge-tts`).
- HyperFrames는 `npx --yes hyperframes@0.7.9` 로 on-demand 실행(설치 불필요).

### 2. 폰트
- 자막 번인용 **Pretendard-Bold.otf**가 `pipeline/fonts/`에 번들됨(커밋). 추가 작업 불필요.

### 3. 영상 1편 만들기
```bash
cd pipeline
python make_short.py --storyboard ../docs/samples/2026-06-26_economy_storyboard.json
# 빠른 검증(앞 2샷, draft):
python make_short.py --storyboard <sb.json> --shots 2 --quality draft
```
결과: `output/renders/<date>_<topic>_final.mp4`

### 4. 업로드(자격증명 필요)
```bash
cd pipeline
# 매핑만 확인(자격증명 불필요):
python upload_from_storyboard.py --storyboard <sb.json> --video <final.mp4> --dry-run --force-private
# 실제 private 업로드:
python upload_from_storyboard.py --storyboard <sb.json> --video <final.mp4> --force-private
```

## YouTube 자격증명 발급 (최초 1회)
1. Google Cloud Console → OAuth 클라이언트(데스크톱) 생성 → `client_secret.json` 다운로드.
2. `pipeline/secrets/client_secret.json`에 둔다.
3. 토큰 발급:
   ```bash
   cd pipeline
   python upload_youtube.py --auth-only   # 브라우저 인증 → secrets/token.json 생성
   ```
4. `token.json` 내용 전체 → GitHub Secret `YT_TOKEN_JSON`, `client_secret.json` 내용 → `YT_CLIENT_SECRET_JSON`.

## GitHub Actions 시크릿/변수
| 종류 | 이름 | 필수 | 용도 |
|---|---|---|---|
| Secret | `YT_CLIENT_SECRET_JSON` | YouTube | OAuth client_secret.json 내용 |
| Secret | `YT_TOKEN_JSON` | YouTube | OAuth token.json(refresh token) 내용 |
| Secret | `ANTHROPIC_API_KEY` | ⬜ | 장면 스펙 자동 추출(루틴이 직접 스펙 출력하면 불필요) |
| Variable | `DEFAULT_PRIVACY` | ⬜ | JSON에 privacy 없을 때 폴백 |
| Secret | `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | IG·Threads | 공개 mp4 호스팅 |
| Secret | `IG_USER_ID` / `IG_ACCESS_TOKEN` | Instagram | IG Reels 게시 |
| Secret | `THREADS_USER_ID` / `THREADS_ACCESS_TOKEN` | Threads | Threads 게시 |

> 각 플랫폼은 **자격증명 있을 때만** 동작(없으면 자동 스킵). YouTube만 쓰려면 YT 2개만 넣으면 됨.

## Instagram Reels + Threads 셋업
IG/Threads 는 **공개 mp4 URL**을 가져가므로(파일 직접 업로드 불가) Cloudinary 로 호스팅 후 게시한다.

1. **Cloudinary** (무료): cloudinary.com 가입 → Dashboard 에서 `Cloud name` / `API Key` / `API Secret`
   → GitHub Secret `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET`
2. **Instagram**: 프로(비즈니스/크리에이터) 계정 + Facebook 페이지 연결 + Meta 개발자 앱
   → `instagram_content_publish` 권한, 장기 토큰 발급 → `IG_ACCESS_TOKEN`, IG 비즈니스 계정 ID → `IG_USER_ID`
3. **Threads**: Threads 프로 계정 + Meta 앱(Threads API) → `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`
4. 토큰은 **~60일마다 갱신** 필요. 본인 계정 자가게시는 보통 앱 개발모드로 가능.

로컬 테스트:
```bash
cd pipeline
python host_video.py --video ../output/renders/<...>_final.mp4 --public-id test   # 공개 URL 확인
python upload_instagram.py --video-url <URL> --caption "..."
python upload_threads.py --video-url <URL> --text "..."
```

## 주의
- 시크릿/`.env`/`secrets/`는 커밋 금지(`.gitignore` 처리됨).
- 산출물(mp4/output)도 커밋 안 함 → Actions 자기 재트리거 루프 방지.
</content>
