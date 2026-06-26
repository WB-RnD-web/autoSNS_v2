# M3 — Path A 완성본 리포트

> 목표: 실제 스토리보드 JSON → 다중 shot(15개) 샷별 베드 + 전환 + 마감 → **로컬 완성 쇼츠 1편**.

작성일: 2026-06-26 · 대상: economy 스토리보드(15샷) · 빌드: [render/m3-short/build.py](../render/m3-short/build.py)

## 결과물
- `render/m3-short/out/2026-06-26_economy_final.mp4`
- **h264 / 1080×1920 / yuv420p / 30fps / AAC / +faststart / 75.3s / 18MB** ✓
- 빌드 시간: **199.5s (3.3분)** — 15 베드 렌더 + 15 자막/음성 합성 + xfade 이어붙이기 (로컬 28코어)

## 파이프라인 (샷별 루프 → 이어붙이기)
`build.py`가 스토리보드를 읽어 샷마다:
1. **음성** edge-tts(화자별 보이스, v1 설정) → `dur = 실측 + 0.4`
2. **베드** 화자(별하=우/별이=좌)에 맞춘 HTML 생성 → HyperFrames render → `beds/bed_N.mp4`
3. **합성** v1 assemble 비디오경로 포팅(자막 drawtext 화자색 + 출처 + 음성) → `shots/shot_N.mp4`

마지막: 전 샷을 **v1 `concat_xfade_cmd` 방식(xfade fade 0.3s + acrossfade)** 으로 이어붙임.

## 해결한 이슈
- **하단 배너 크롭** — 베드에서 ① 상단기준 켄번즈 줌(scale 1.40→1.54, origin y=12%)로 배너를 프레임 밖으로 + ② **브랜드 잉크 lower-third 밴드**(하단부 완전 불투명)로 잔상까지 차단. 결과: 배너 완전 제거 + 자막 backing 확보.
- **화자별 연출** — 별하/별이에 따라 켄번즈 기준점·드리프트·스포트라이트 위치·코랄 글로우 좌우 분기. 자막색도 화자색(별하 #FFD23F / 별이 #5BC8FF).
- **모션 연속성** — 켄번즈(전 구간) + 미세 스웨이(회전 yoyo) + 스포트라이트 호흡. M1의 "정지처럼 보임" 문제 해소.

## ⚠️ 발견/주의

### 1. ★ 실제 영상 길이 75s (JSON `total_sec:50`보다 김)
- 샷별 edge-tts 실측 합 ≈ 79s(xfade 겹침 후 75.3s). 대본 추정(50s)보다 **약 50% 김**.
- 원인: edge-tts(SunHi/Hyunsu) 읽기 속도가 대본 추정보다 느림. (M2에서도 샷1이 4s 추정→5.38s 실측)
- **영향**: YouTube Shorts 길이 정책(현재 최대 3분)엔 문제없음. 단 "1분 티키타카" 의도보다 길어짐.
- **선택지**: (a) 그대로 둠(Shorts 3분 내 OK), (b) TTS `rate`를 +8~12%로 올려 ~55s로 단축(자연스러움 약간 ↓), (c) 루틴이 대사를 더 짧게. → M4 이후 톤 보고 결정 권장.

### 2. 출처 워터마크 가독성
- 우상단 출처 텍스트가 밝은 스튜디오 배경 위에서 다소 흐림(v1과 동일한 그림자 처리). 필요시 작은 반투명 박스 추가 검토(소폭).

### 3. 자막팝(동적 fontsize)은 여전히 Linux 전용
- 로컬 Windows ffmpeg 크래시 회피로 정적 fontsize. 프로덕션(Actions ubuntu)에서 `CAPTION_POP=1`.

## 결론 / 다음
- **Path A 완성**: "정적 투샷 → HyperFrames 모션 베드 교체, 나머지 v1 그대로"가 **실제 스토리보드 1편 전체에서 동작** 확인.
- Path B(스키마 확장 씬)는 선택 — 현재 Path A 퀄로 충분하면 보류, 토픽별 다양화가 필요하면 이후 도입.
- **다음 M4**: v1 유튜브 업로드 포팅 → 강제 private 드라이런, `title/desc`=JSON, privacy 준수 확인.
</content>
