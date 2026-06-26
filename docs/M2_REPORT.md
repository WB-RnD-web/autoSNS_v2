# M2 — 단일 shot 리포트

> 목표: 실제 JSON shot 1개 → 투샷 **애니메이션 베드** + v1 음성(edge-tts) + v1 자막(ffmpeg drawtext) → 단일 shot mp4.

작성일: 2026-06-26 · 대상: economy 스토리보드 shot #1 (별하)

## 입력
- 대사: `"야, 나 오늘 아침에 애플 뉴스 보고 진짜 손 떨렸잖아."` (speaker=별하)
- 투샷 이미지: v1 `characters/refs/왕별이 뉴스데스크.png` (768×1376 ≈ **정확히 9:16**)

## 파이프라인 (3단계, 전부 v1 재사용 + 베드만 신규)
1. **음성** — edge-tts, 별하=`ko-KR-SunHiNeural` (v1 voice.py 설정 그대로). → `assets/voice_1.mp3`
   - **실측 길이 5.38s** vs JSON `duration:4` → **1.78초 차이**. v1의 "실 TTS 길이 재계산"이 왜 필수인지 입증. 샷 길이 = 5.38 + 0.4 = **5.78s**.
2. **베드(신규)** — [render/m2-shot/bed/index.html](../render/m2-shot/bed/index.html), HyperFrames.
   - 투샷 이미지에 **강한 켄번즈(scale 1.04→1.18 + 화자쪽 드리프트)** + **미세 스웨이(회전 yoyo)** + **별하(우측) 스포트라이트 호흡** + 코랄 그레이드/비네트/그레인.
   - 레이어 분리(#frame opacity / #sway rotation / #kb scale·translate)로 GSAP 트윈 충돌 0 → lint 0경고.
   - `data-duration`을 음성 길이(5.78s)에 맞춰 주입. → `bed/renders/bed.mp4`
3. **합성** — [render/m2-shot/assemble_shot.py](../render/m2-shot/assemble_shot.py), v1 `assemble.shot_clip_cmd`의 **비디오-에셋 경로 포팅**.
   - `scale=increase, crop, fps=30, drawtext(caption, 화자색 #FFD23F), drawtext(credit)` + 음성 apad + libx264/yuv420p/aac + `+faststart`.
   - 자막은 v1 방식(`shots[].caption` → drawtext) 그대로. 폰트만 **Pretendard-Bold.otf**로 교체(브랜드 토큰).
   - → `out/shot1_final.mp4` : **h264 / 1080×1920 / yuv420p / 30fps / 5.78s + AAC** ✓

## ⚠️ 발견 이슈 (다음 단계에 영향)

### 1. ★ 투샷 이미지에 박힌 텍스트가 자막과 충돌 (콘텐츠)
- v1 ref 투샷 하단에 **"@BYEORI & @BYEOLHA" / "BREAKING NEWS"** 가 **이미지에 구워져** 있음.
- v2 자막(하단 번인)이 이 배너 위에 겹쳐 지저분함.
- **해결안(M3에서 결정 필요)**: (a) 베드에서 하단을 화면 밖으로 켄번즈/크롭, (b) **배너 없는 깨끗한 투샷 생성**(gemini 백엔드 프롬프트에서 텍스트 제거 지시), (c) 자막 위치 상향. → (b)+(a) 권장.

### 2. 로컬 Windows ffmpeg = 동적 fontsize 크래시 (환경)
- v1 "자막 팝"(시간가변 `fontsize` 표현식)이 **로컬 Windows ffmpeg 8.1.1 static 빌드에서 크래시**(0xC0000005). 정적 fontsize는 정상.
- **프로덕션(Actions ubuntu, apt ffmpeg)에선 v1이 잘 쓰는 표현식 = 문제없음.** 로컬 증명만 정적 fontsize 사용(`CAPTION_POP=1`로 강제 활성 가능).

### 3. 베드 ↔ assemble 에셋 연결 (M3 작업)
- v1 `assemble.find_asset`은 asset id=`twoshot` 1개를 전 샷 공유로 탐색. **샷별 베드("샷별 mp4 개별 렌더" 결정)** 를 받으려면 샷별 파일명(예: `<date>_<topic>_twoshot_shot<n>.mp4`) 탐색 분기를 assemble에 소폭 추가해야 함.

## 결론
- **핵심 가설 검증 완료**: "정적 투샷 자리만 HyperFrames 애니메이션 mp4로 교체, 나머지(음성·자막·타이밍·코덱)는 v1 그대로" 가 **실제로 동작**.
- 모션도 M1 대비 확연히 강해짐(켄번즈 줌 + 스웨이 + 스포트라이트).
- 다음(M3): 다중 shot(15개) 샷별 베드 렌더 → v1 xfade 이어붙이기 → 완성 쇼츠 1편. + 위 이슈 1·3 처리.
</content>
