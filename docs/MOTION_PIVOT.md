# 방향 전환 — 모션그래픽 파이프라인 (중요)

작성일: 2026-06-26

## 왜 바꿨나
초기 구현(M0~M6)은 브리핑의 **Path A = "정적 투샷 이미지를 켄번즈로 애니메이션"** 이었다.
결과물이 "사진 한 장이 좌우로 움직이는" 수준이라 기대(진짜 방송 같은 영상)에 못 미쳤다.

레퍼런스(인스타 `moongi_adventures`, #hyperframes)를 분석한 결과:
- **같은 HyperFrames + Claude 스택**, 별도 MCP 없음.
- 고퀄의 정체 = **모션그래픽**(키네틱 타이포·카운트업 숫자·차트·글로우·장면전환). 캐릭터 립싱크가 아님.
- 즉 HyperFrames의 강점(모션그래픽)을 써야 했고, 이는 원래 목표("뉴스 → 모션그래픽 쇼츠") 그대로다.

→ 캐릭터/투샷 애니메이션을 버리고 **모션그래픽 중심 + 단일 내레이터 VO**로 전면 재설계.

## 새 아키텍처
```
스토리보드 JSON (루틴 산출)
  → extract_scenes.py : Claude로 장면 스펙(JSON) 추출  ← 신규
       (hook / stat / gauge / trend, 각 장면 단일 내레이션 1줄)
  → motion_short.py   : 타입별 템플릿으로 HyperFrames HTML 생성       ← 신규(핵심)
       + edge-tts 단일 내레이터 VO → 장면 타이밍 동기 → render → mux
  → output/renders/<date>_<topic>_final.mp4
  → upload_youtube (privacy 준수)  ← v1 재사용
```

## 장면 타입 (현재)
- **hook** — 키네틱 후크 타이틀(BREAKING + 강조 토큰 팝 + 고스트 텍스트)
- **stat** — 절대 수치 카운트업(+$200) + 상승 막대
- **gauge** — 배수(1→4배) + 게이지 바 성장
- **trend** — 추세 %(-6%) + 라인차트 드로잉 + 마무리(closer)

스펙 예시: [samples/scene_spec_economy.json](samples/scene_spec_economy.json)

## 장면 스펙 확보 3경로 (run_pipeline)
1. `--spec <file>` 직접 지정
2. 사전 생성 `output/specs/<date>_<topic>_spec.json`
3. `ANTHROPIC_API_KEY` 있으면 LLM 자동 추출(→ specs 저장)

## 유지된 것 (v1 재사용)
- edge-tts(보이스만 단일 내레이터로), 업로드(privacy/title/desc), dedupe ledger, 캐싱, 워크플로 트리거·루프가드.

## 폐기된 것
- `bed.py`, `make_short.py`, `bedproj/`, ffmpeg 자막 drawtext(자막은 이제 모션그래픽 텍스트), 투샷 켄번즈.

## 검증 (로컬)
- economy 스펙 → 25초 모션그래픽 쇼츠(VO 동기) 생성 확인. 렌더러는 스펙만 바꾸면 재사용.

## 미검증 (환경 필요)
- LLM 추출(extract_scenes): 로컬에 ANTHROPIC_API_KEY 없어 미실행 → CI 또는 키 연결 시 검증 필요.
  대안: 루틴이 스펙을 직접 emit(Path B)하면 CI LLM 호출 불필요.
- 다른 토픽(정치/주식/해외) 스펙 품질.
</content>
