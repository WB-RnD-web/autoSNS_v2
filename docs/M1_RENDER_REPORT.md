# M1 — 렌더 증명 리포트

> 목표: 하드코딩 HyperFrames 컴포지션 1개를 **로컬에서 mp4 렌더 성공** + 시간·RAM 실측 → Actions 실현성 판단.

작성일: 2026-06-26 · 컴포지션: [render/m1-proof/index.html](../render/m1-proof/index.html)

## 무엇을 렌더했나
- **9:16 앵커 투샷 모션 베드** (자막·음성 없는 순수 비주얼 베드 — 결정사항대로 자막은 M2부터 v1 ffmpeg가 담당).
- 5초, 1080×1920, 30fps (= 150프레임). 실제 샷 1개 길이에 근접한 대표 샘플.
- 모션: 켄번즈(무대 줌인) + 화자 패럴랙스(별이 좌/별하 우) + 진입 애니메이션 + **화자 강조 팝**(별하 스케일+스포트라이트 펄스) + 그레인/비네트/코랄 엠버.
- 브랜드 토큰 적용: ink `#0A0808`, cream `#EDD9BC`, coral `#D97757`, **폰트 Pretendard(woff2 번들 + @font-face)** — 한글 정상 렌더 확인.

## 렌더 환경 (`hyperframes doctor`)
- HyperFrames 0.7.9, Node v24.14.0
- CPU 28코어(i7-14700KF), RAM 31.8GB, Chrome(headless-shell) 자동 설치됨
- **FFmpeg/FFprobe는 미설치 상태였음 → 직접 설치**: Gyan.dev 정적 빌드 8.1.1을 `C:\Users\zxczx\tools\ffmpeg-...\bin`에 두고 User PATH 등록. (v1 파이프라인도 ffmpeg 필요하므로 공통 사용)

## 실측 결과

| 설정 | Wall time | Peak RAM* | 출력 |
|---|---|---|---|
| 기본 (standard, 30fps, workers=auto→**5**) | **12.5 s** | ~5.3 GB | 2.15 MB |
| `--workers 2` (무료 러너 시뮬) | **13.8 s** | ~4.9 GB | 2.1 MB |

\* Peak RAM은 `node`+`chrome*` 프로세스 합산이라 **사용자 브라우저까지 잡혔을 수 있어 상한치**로 해석. 실제 렌더 전용 footprint는 더 낮음. 내부 trace 기준 capture 7.9s + encode 0.9s + assemble 0.05s.

### 출력 규격 검증 (ffprobe)
```
codec=h264  1080x1920  pix_fmt=yuv420p  fps=30/1  duration=5.0
```
→ 브랜드 기술규격(9:16 H.264/yuv420p) 충족. (`+faststart`는 v2 합치기 단계 ffmpeg에서 부여 예정)

## Actions 실현성 판단 ✅ 가능

- **2 workers로도 거의 동일 속도**(이 컴포지션이 GPU-라이트). 무료 러너(2코어/7GB)에서 RAM 여유, 타임아웃 무리 없음.
- 5초=약 13초(약 2.7x 실시간). **단, v2는 "샷별 mp4 개별 렌더"** 결정이므로 50초 1편이 아니라 **샷 ~15개 × 짧은 렌더**로 쪼개짐. 주제 5개면 약 75개 짧은 렌더가 누적되는 게 실제 비용 → 캐싱/병렬/스킵으로 관리(M6).
- **러너 셋업 비용이 관건**(렌더 자체보다): v1 워크플로는 Python만 설치 → v2는 **Node 22 + Chrome(+system libs) + Pretendard 폰트 + ffmpeg** 추가 설치 필요. Chrome 시스템 라이브러리는 Playwright/Puppeteer `install-deps`로 해결, Chrome 바이너리·npm·hyperframes 캐싱 권장.

## 메모 / 다음 단계 영향
- `workers=auto`가 28코어에서 **5**를 선택 → HyperFrames 내부 상한이 있는 듯. 러너에선 어차피 코어 수에 맞춰짐.
- 폰트 파이프라인 확립: lint가 미선언 font-family를 에러로 잡음 → **반드시 @font-face + woff2 번들**. body 폰트 스택에 미번들 별칭("Pretendard Variable") 두면 에러 → 정리함.
- M2에서: 실제 투샷 이미지를 베드 입력으로 받고, 샷별 음성 길이에 맞춰 `data-duration`을 동적 주입하는 구조 설계.
</content>
