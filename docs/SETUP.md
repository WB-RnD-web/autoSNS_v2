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
| Secret | `YT_CLIENT_SECRET_JSON` | ✅(업로드) | OAuth client_secret.json 내용 |
| Secret | `YT_TOKEN_JSON` | ✅(업로드) | OAuth token.json(refresh token) 내용 |
| Secret | `GEMINI_API_KEY` | ⬜ | 투샷 이미지 생성(gemini 백엔드) |
| Secret | `ANTHROPIC_API_KEY` | ⬜ | (옵션) 스마트 대본 |
| Variable | `DEFAULT_PRIVACY` | ⬜ | JSON에 privacy 없을 때 폴백(기본 private) |

## 투샷 이미지 백엔드
- 기본 `static`: `characters/refs/`의 고정 투샷 이미지를 사용(무료, 항상 동작). 현재 `왕별이 뉴스데스크.png` 번들됨.
- `gemini`: `IMAGE_BACKEND=gemini` + `GEMINI_API_KEY` → 텍스트 없는 깨끗한 투샷 생성 가능(배너 충돌 근본 해결안).

## 주의
- 시크릿/`.env`/`secrets/`는 커밋 금지(`.gitignore` 처리됨).
- 산출물(mp4/output)도 커밋 안 함 → Actions 자기 재트리거 루프 방지.
</content>
