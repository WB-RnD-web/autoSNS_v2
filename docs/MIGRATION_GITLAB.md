# 사내 GitLab 이주 — 시크릿 전량 재발급 + 적용 가이드

**전제**: 기존 시크릿은 하나도 못 건진다고 가정한다(GitHub Secrets 는 쓰기 전용이라 읽을 수 없고,
로컬 파일이 최신인지 대조하는 것도 일이다). **전부 처음부터 새로 만든다.**

소요: 유튜브만 하면 **약 40분**, IG/Threads 까지 하면 **약 70분**.

> ⚠️ 먼저 확인할 것 두 가지 — 이 결과에 따라 구성이 달라진다.
> 1. **GitLab 이 사외에서 열리는가?** (폰 LTE 로 GitLab 주소 접속)
>    - 열림 → 루틴이 GitLab 에 직접 push. §5-A
>    - 안 열림 → GitHub 을 현관으로 두는 하이브리드. §5-B
> 2. **사내망에서 edge-tts 웹소켓이 뚫리는가?**
>    ```bash
>    pip install edge-tts && edge-tts --text "테스트" --write-media t.mp3
>    ```
>    실패하면 **모든 낭독(SCP·ASMR 나레이션)이 죽는다.** 방화벽에
>    `wss://speech.platform.bing.com` 을 열어야 한다.

---

## 1) 유튜브 — 토큰 3개 (제일 오래 걸린다, 25분)

### 1-1. 클라이언트 시크릿 (모든 토큰의 부모)

1. https://console.cloud.google.com → 프로젝트 선택(없으면 생성)
2. **API 및 서비스 → 라이브러리 → "YouTube Data API v3" → 사용 설정**
3. **API 및 서비스 → OAuth 동의 화면**
   - User Type: **외부**
   - 앱 이름/지원 이메일 채우기
   - **테스트 사용자**에 ★업로드에 쓸 구글 계정을 추가 (이걸 빠뜨리면 인증이 거부된다)
   - 게시 상태는 **테스트**로 둬도 된다(테스트 사용자는 정상 동작)
4. **사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 유형: **데스크톱 앱**
   - 만든 뒤 **JSON 다운로드** → 이게 `client_secret.json`

> ⚠️ 토큰 3개는 **전부 같은 클라이언트 시크릿**으로 발급해야 한다. 섞이면 리프레시가 깨진다.

### 1-2. 토큰 3개 발급 (로컬 PC, 브라우저 필요)

레포를 받아서 로컬에서 돌린다. **러너에서는 못 한다**(브라우저가 열려야 한다).

```bash
git clone <레포> && cd <레포>
python -m pip install -r pipeline/requirements.txt
mkdir -p pipeline/secrets
cp ~/Downloads/client_secret_*.json pipeline/secrets/client_secret.json
cd pipeline
```

세 토큰은 **스코프가 다르다.** 용도가 갈려 있어서 하나로 합치지 않는다.

| 파일 | 스코프 | 쓰는 곳 |
|---|---|---|
| `token.json` | `youtube.upload` | 뉴스 쇼츠 업로드 |
| `token_novel.json` | `youtube.upload` + `youtube` | SCP·ASMR 업로드 + **재생목록** |
| `token_forcessl.json` | `youtube.force-ssl` (+상위 포함) | **자막 트랙 · 제목/설명 현지화 · 쇼츠 댓글** |

**① `token_forcessl.json`** — 스크립트가 있다:

```bash
python yt_i18n.py --auth-only
```
브라우저가 열린다. ★**업로드에 쓸 그 구글 계정 / 그 채널**을 고른다.
"Google에서 확인하지 않은 앱" 경고 → **고급 → 안전하지 않음(계속)**.

**② `token_novel.json`** · **③ `token.json`** — 한 줄씩 실행:

```bash
python - <<'PY'
from google_auth_oauthlib.flow import InstalledAppFlow
S = "secrets/client_secret.json"
for out, scopes in [
    ("secrets/token_novel.json", ["https://www.googleapis.com/auth/youtube.upload",
                                  "https://www.googleapis.com/auth/youtube"]),
    ("secrets/token.json",       ["https://www.googleapis.com/auth/youtube.upload"]),
]:
    print(f"\n=== {out} 발급 — 같은 계정/같은 채널을 고르세요 ===")
    creds = InstalledAppFlow.from_client_secrets_file(S, scopes).run_local_server(port=0)
    open(out, "w").write(creds.to_json())
    print("✅", out)
PY
```

### 1-3. 검증 (넣기 전에 반드시)

```bash
python yt_i18n.py --check
```
채널명·클라이언트 ID·스코프가 찍힌다. **세 토큰의 채널이 같은지** 확인할 것.
다르면 다른 계정으로 로그인한 것 → 해당 토큰 파일 지우고 다시.

---

## 2) 이미지·음원 API (5분)

| 시크릿 | 발급처 | 방법 |
|---|---|---|
| `NVIDIA_API_KEY` | https://build.nvidia.com | 로그인 → 아무 모델 → **Get API Key** → `nvapi-...` 복사 |
| `FREESOUND_API_KEY` | https://freesound.org/apiv2/apply/ | 로그인 → 애플리케이션 이름 입력 → 생성 즉시 키 표시 |
| `WBSPARK_TOKEN` | 사내 wbSpark | 게이트웨이에 인증을 걸었다면 그 토큰. 안 걸었으면 **빈 값으로 둬도 된다** |

---

## 3) Instagram · Threads (30분 — 안 해도 유튜브는 정상)

**유튜브와 완전히 독립이다.** 나중에 하거나 아예 접어도 파이프라인은 돌아간다.
지금 부담되면 **이 절을 통째로 건너뛰고** IG/Threads 관련 변수를 비워두면
`upload_from_storyboard.py` 가 자동으로 스킵한다.

### 3-1. Cloudinary (IG Reels 임시 호스팅용)
https://cloudinary.com → 로그인 → **Dashboard 상단에 3개가 그대로 표시된다**
- `CLOUDINARY_CLOUD_NAME` · `CLOUDINARY_API_KEY` · `CLOUDINARY_API_SECRET`

### 3-2. Meta 액세스 토큰
1. https://developers.facebook.com/apps → 기존 앱 선택(없으면 생성)
2. **Instagram** 제품 추가 → 비즈니스 계정 연결
3. **도구 → 그래프 API 탐색기**
   - 앱 선택 → 사용자 액세스 토큰 → 권한:
     `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
     `threads_basic`, `threads_content_publish`
   - **Generate Access Token** → 단기 토큰
4. **장기 토큰으로 교환**:
   ```bash
   curl -s "https://graph.facebook.com/v21.0/oauth/access_token\
   ?grant_type=fb_exchange_token&client_id=<앱ID>&client_secret=<앱시크릿>\
   &fb_exchange_token=<단기토큰>"
   ```
   → `IG_ACCESS_TOKEN`
5. **Threads 토큰**은 https://developers.facebook.com/apps → Threads API 에서 별도 발급
   → `THREADS_ACCESS_TOKEN`
6. **ID 조회**:
   ```bash
   curl -s "https://graph.facebook.com/v21.0/me/accounts?access_token=<토큰>"       # IG_USER_ID
   curl -s "https://graph.threads.net/v1.0/me?access_token=<스레드토큰>"            # THREADS_USER_ID
   ```

> `refresh_tokens.py` 가 60일마다 자동 갱신한다(앱 시크릿 불필요).
> GitLab 에서는 **스케줄 파이프라인**으로 돌린다 — §6 참조.

---

## 4) GitLab 에 넣기

**Settings → CI/CD → Variables → Add variable**

### 4-1. 타입 선택이 중요하다

| | 언제 | 왜 |
|---|---|---|
| **File** | JSON 4개 | 값이 파일로 떨어지고 변수엔 **경로**가 담긴다. 여러 줄 JSON 을 셸에서 이스케이프할 필요가 없다 |
| **Variable** | 나머지 전부 | 한 줄 문자열 |
| **Masked** ✅ | 한 줄 API 키 | 로그에 찍혀도 `[MASKED]` 로 가려진다 |
| **Masked** ❌ | JSON(File 타입) | 여러 줄이라 마스킹 불가 — 대신 File 타입이라 로그에 안 나온다 |

> ⚠️ **Protected 체크는 신중히.** Protected 변수는 **보호된 브랜치/태그에서만** 주입된다.
> 우리 CI 는 `routine/scp` 같은 브랜치에서 도니까, Protected 를 켰다면
> **Settings → Repository → Protected branches 에 `routine/*` 를 등록**해야 한다.
> 안 하면 변수가 비어서 "토큰 없음"으로 조용히 스킵된다. 헷갈리면 처음엔 Protected 를 끄고 시작.

### 4-2. 등록할 변수 전체

| 변수명 | 타입 | Masked | 값 |
|---|---|---|---|
| `YT_CLIENT_SECRET_JSON` | **File** | – | `client_secret.json` 내용 |
| `YT_TOKEN_JSON` | **File** | – | `token.json` 내용 |
| `YT_TOKEN_JSON_NOVEL` | **File** | – | `token_novel.json` 내용 |
| `YT_TOKEN_JSON_FORCESSL` | **File** | – | `token_forcessl.json` 내용 |
| `NVIDIA_API_KEY` | Variable | ✅ | `nvapi-...` |
| `FREESOUND_API_KEY` | Variable | ✅ | |
| `WBSPARK_TOKEN` | Variable | ✅ | (없으면 생략) |
| `CLOUDINARY_CLOUD_NAME` | Variable | – | |
| `CLOUDINARY_API_KEY` | Variable | ✅ | |
| `CLOUDINARY_API_SECRET` | Variable | ✅ | |
| `IG_USER_ID` | Variable | – | |
| `IG_ACCESS_TOKEN` | Variable | ✅ | |
| `THREADS_USER_ID` | Variable | – | |
| `THREADS_ACCESS_TOKEN` | Variable | ✅ | |

레포 변수(비밀 아님)는 **Variable** 로 같이 넣으면 된다:
`ASMR_PLAYLIST` · `SCP_PLAYLIST` · `SCP_SHORTS_PLAYLIST` · `DEFAULT_PRIVACY` · `I18N_LANGS` 등.

### 4-3. File 타입이면 스크립트가 이렇게 간단해진다

GitHub 에서는 이랬다:
```bash
printf '%s' "$YT_TOKEN_JSON" > pipeline/secrets/token.json
```
GitLab File 타입은 이미 파일이라 **복사만** 하면 된다:
```bash
cp "$YT_TOKEN_JSON" pipeline/secrets/token.json
```

---

## 5) 러너 + `.gitlab-ci.yml`

### 5-1. 러너 설치 (사내 서버, 1회)

```bash
curl -L "https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh" | sudo bash
sudo apt-get install -y gitlab-runner docker.io
sudo usermod -aG docker gitlab-runner

# 프로젝트 → Settings → CI/CD → Runners 에서 토큰 복사
sudo gitlab-runner register \
  --non-interactive \
  --url "https://gitlab.사내주소/" \
  --token "<러너 토큰>" \
  --executor docker \
  --docker-image "autosns/runner:1" \
  --docker-privileged=false
```

**동시 실행 수**를 올려두면 뉴스 4종이 병렬로 돈다:
`/etc/gitlab-runner/config.toml` → `concurrent = 4`

### 5-2. 러너 이미지 (apt 사고 방지)

GitHub 에서 `apt-get update` 가 9분 걸린 사고가 있었다. 이미지에 미리 구워두면 그 변수가 사라진다.

```dockerfile
# docker/Dockerfile.runner
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-nanum git curl ca-certificates \
      nodejs npm \
 && fc-cache -f && rm -rf /var/lib/apt/lists/*
COPY pipeline/requirements.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt
```
```bash
docker build -f docker/Dockerfile.runner -t autosns/runner:1 .
```

### 5-3. `.gitlab-ci.yml`

레포 루트에 둔다. GitHub Actions 4개(shorts/scp/scp-shorts/asmr)를 그대로 옮긴 것.

```yaml
stages: [render]

default:
  image: autosns/runner:1
  timeout: 90m
  before_script:
    - mkdir -p pipeline/secrets
    - '[ -n "$YT_CLIENT_SECRET_JSON" ] && cp "$YT_CLIENT_SECRET_JSON" pipeline/secrets/client_secret.json || true'
    - '[ -n "$YT_TOKEN_JSON" ] && cp "$YT_TOKEN_JSON" pipeline/secrets/token.json || true'
    - '[ -n "$YT_TOKEN_JSON_NOVEL" ] && cp "$YT_TOKEN_JSON_NOVEL" pipeline/secrets/token_novel.json || true'
    - '[ -n "$YT_TOKEN_JSON_FORCESSL" ] && cp "$YT_TOKEN_JSON_FORCESSL" pipeline/secrets/token_forcessl.json || true'

variables:
  TZ: Asia/Seoul
  GIT_DEPTH: "0"                 # push diff 계산에 히스토리가 필요하다
  I18N_LOCALIZE: "1"
  I18N_LANGS: "en,ja,zh-Hant"

# ── 뉴스 쇼츠 (별자리·운세·주식·정치) ──────────────────
news-shorts:
  stage: render
  rules:
    - if: '$CI_COMMIT_BRANCH =~ /^routine\//'
      changes: ["output/news/**/*_storyboard.json"]
  variables:
    I18N_CAPTIONS: "0"
    SHORTS_COVER: "1"
  script:
    - FILES=$(ls output/news/*_storyboard.json 2>/dev/null | tr '\n' ' ')
    - '[ -z "$(echo $FILES | tr -d " ")" ] && echo "신규 없음" && exit 0'
    - cd pipeline
    - python run_pipeline.py $(for f in $FILES; do echo "../$f"; done)
        --use-ledger --log ../output/run_log.json
  cache:
    key: ledger-news
    paths: [output/ledger.json]

# ── SCP 롱폼 (금) ─────────────────────────────────────
scp-longform:
  stage: render
  rules:
    - if: '$CI_COMMIT_BRANCH == "routine/scp"'
      changes: ["output/scp/**/*.json"]
    - if: '$CI_PIPELINE_SOURCE == "web"'          # 수동 실행
  variables:
    I18N_CAPTIONS: "1"
    SCP_FPS: "10"
  script:
    - |
      if [ -n "$SPEC" ]; then FILES="$SPEC"
      else FILES=$(git diff --name-only --diff-filter=AM HEAD~1 HEAD -- output/scp/ \
                   | grep -E '\.json$' | grep -v library.json | tr '\n' ' ' || true); fi
    - '[ -z "$(echo $FILES | tr -d " ")" ] && echo "신규 없음" && exit 0'
    - cd pipeline
    - python run_scp.py $(for f in $FILES; do echo "../$f"; done)
        --use-ledger --ledger-path ../output/scp_ledger.json
  cache:
    key: ledger-scp
    paths: [output/scp_ledger.json]

# ── SCP 쇼츠 (토 10:00 KST — 스케줄) ───────────────────
scp-shorts:
  stage: render
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule" && $JOB == "scp-shorts"'
    - if: '$CI_PIPELINE_SOURCE == "web"'
      when: manual
  script:
    - cd pipeline
    - python run_scp_shorts.py --latest-in ../output/scp
        --use-ledger --ledger-path ../output/scp_shorts_ledger.json
  cache:
    key: ledger-scp-shorts
    paths: [output/scp_shorts_ledger.json]

# ── ASMR (월) ─────────────────────────────────────────
asmr:
  stage: render
  timeout: 120m                                   # 3~4시간 트랙
  rules:
    - if: '$CI_COMMIT_BRANCH == "routine/asmr"'
      changes: ["output/asmr/**/*.json"]
    - if: '$CI_PIPELINE_SOURCE == "web"'
      when: manual
  script:
    - FILES=$(git diff --name-only --diff-filter=AM HEAD~1 HEAD -- output/asmr/ | grep '\.json$' | grep -v state.json | tr '\n' ' ' || true)
    - '[ -z "$(echo $FILES | tr -d " ")" ] && echo "신규 없음" && exit 0'
    - cd pipeline
    - python run_asmr.py $(for f in $FILES; do echo "../$f"; done)
        --use-ledger --ledger-path ../output/asmr_ledger.json
  cache:
    key: ledger-asmr
    paths: [output/asmr_ledger.json]
```

> **GitHub Actions 와 다른 점 3가지**
> 1. `paths:` → `rules: changes:`
> 2. `actions/cache` → `cache:` (키만 주면 된다)
> 3. `schedule:` cron → **Settings → CI/CD → Schedules** 에서 UI 로 등록하고,
>    변수 `JOB=scp-shorts` 를 그 스케줄에 붙인다. (cron 은 UTC 기준: 토 10:00 KST = `0 1 * * 6`)

### 5-A. GitLab 이 사외에서 열리는 경우 — 루틴이 직접 push

루틴 프롬프트 6개에서 **push 대상만** 바꾼다.

```bash
# 기존
git push origin routine/scp
# 변경
git remote set-url origin https://oauth2:<PROJECT_ACCESS_TOKEN>@gitlab.사내주소/<group>/<repo>.git
git push origin routine/scp
```
토큰은 **Settings → Access Tokens → Project Access Token**(role: Developer, scope: `write_repository`).
GitHub 쪽 워크플로는 전부 비활성화 → **Actions 분 소모 0**.

### 5-B. GitLab 이 내부망 전용인 경우 — 하이브리드

루틴은 **GitHub 에 그대로 push**(프롬프트 수정 0). GitLab 이 GitHub 을 당겨온다.

- **GitLab Premium 이면**: Settings → Repository → **Mirroring repositories** → Pull 방향으로 GitHub URL 등록
- **Free 면**: 스케줄 파이프라인으로 폴링(15~30분 간격)

```yaml
poll-github:
  stage: render
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule" && $JOB == "poll"'
  script:
    - git remote add gh https://$GH_TOKEN@github.com/WB-RnD-web/autoSNS_v2.git || true
    - git fetch gh 'refs/heads/routine/*:refs/remotes/gh/routine/*'
    - # 새 스펙이 있으면 해당 잡을 트리거
    - curl -X POST -F token=$CI_JOB_TOKEN -F ref=main $CI_API_V4_URL/projects/$CI_PROJECT_ID/trigger/pipeline
```
GitHub 은 **git 저장소로만** 남는다(Actions 끔 → 분 소모 0).

---

## 6) 토큰 자동 갱신 (Meta 60일)

GitHub 에서는 `refresh-tokens.yml` 이 돌았다. GitLab 에서는 스케줄 파이프라인 + API 로 바꾼다.

`refresh_tokens.py` 의 `set_secret()` 이 GitHub API 를 쓰므로 **GitLab API 로 바꿔야 한다**:
`PUT /api/v4/projects/:id/variables/:key` (Maintainer 토큰 필요).

> 이건 IG/Threads 를 쓸 때만 필요하다. 유튜브 토큰은 refresh_token 으로 무기한 갱신되므로
> 별도 스케줄이 필요 없다.

---

## 7) 순서 체크리스트

- [ ] **0.** edge-tts 웹소켓 테스트 (실패하면 여기서 멈추고 방화벽부터)
- [ ] **0.** GitLab 사외 접속 여부 확인 → 5-A / 5-B 결정
- [ ] **1.** 방화벽 egress 허용 신청 (아래 목록)
- [ ] **2.** 클라이언트 시크릿 + 유튜브 토큰 3개 발급 → `--check` 로 채널 일치 확인
- [ ] **3.** NVIDIA / Freesound 키
- [ ] **4.** GitLab CI/CD Variables 등록 (File 타입 주의, Protected 주의)
- [ ] **5.** 러너 설치 + 이미지 빌드
- [ ] **6.** `.gitlab-ci.yml` 커밋 → **수동 실행으로 1건 검증**(`force_private` 상당)
- [ ] **7.** 성공하면 GitHub Actions 워크플로 전부 비활성화
- [ ] **8.** (선택) IG/Threads 토큰 + 갱신 스케줄

### 방화벽 egress 허용 목록

**필수**
```
www.googleapis.com          443/HTTPS   유튜브 API
oauth2.googleapis.com       443/HTTPS   토큰 갱신
speech.platform.bing.com    443/WSS ★   낭독(edge-tts) — 웹소켓 업그레이드 허용 필수
ai.api.nvidia.com           443/HTTPS   이미지 생성
freesound.org               443/HTTPS   ASMR 음원
news.google.com             443/HTTPS   뉴스 수집
github.com, codeload.github.com  443    (5-B 하이브리드일 때)
wangbyul.com                443/HTTPS   qwen 커버(사내면 내부 경유)
```

**선택 — IG/Threads 쓸 때만**
```
api.cloudinary.com, res.cloudinary.com
graph.facebook.com, graph.threads.net, graph.instagram.com
```

**빌드용 — 러너 이미지를 미리 구우면 불필요**
```
pypi.org, files.pythonhosted.org, registry.npmjs.org, storage.googleapis.com, cdn.jsdelivr.net
```
