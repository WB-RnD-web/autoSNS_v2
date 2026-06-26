# autoSNS_v2

뉴스 → **HyperFrames 모션그래픽 쇼츠** → 유튜브 자동 업로드 파이프라인.

[v1(`WB-RnD-web/autoSNS`)](https://github.com/WB-RnD-web/autoSNS)의 "스토리보드 → 대본·이중음성·자막·타이밍·업로드"를 **그대로 재사용**하고,
정적 투샷 이미지 1장 자리만 **HyperFrames 애니메이션 베드**로 교체한 버전.

> ⚠️ **방향 전환**: 초기엔 "정적 투샷 켄번즈"(Path A)였으나, HyperFrames 강점인 **모션그래픽**으로 전면 재설계했다. 배경은 [docs/MOTION_PIVOT.md](docs/MOTION_PIVOT.md).

## 흐름
```
루틴 → output/news/<date>_<topic>_storyboard.json (main 커밋)
  → [push 트리거] GitHub Actions
     ① extract_scenes  스토리보드 → 장면 스펙(JSON) (Claude)        ← 신규
     ② motion_short    타입별 템플릿으로 모션그래픽 HTML → render    ← 신규(핵심)
                       + edge-tts 단일 내레이터 VO → 타이밍 동기 → mux
  → 유튜브 업로드 (privacy 준수, v1 재사용)
```

## 빠른 시작
```bash
cd pipeline
# 스펙 직접 지정(키 불필요):
python run_pipeline.py ../docs/samples/2026-06-26_economy_storyboard.json \
    --spec ../docs/samples/scene_spec_economy.json --no-upload
# → output/renders/<date>_<topic>_final.mp4

# 렌더러만 단독 실행:
python motion_short.py --spec ../docs/samples/scene_spec_economy.json --out ../output/renders/economy.mp4
```
자세한 셋업·시크릿·업로드: **[docs/SETUP.md](docs/SETUP.md)**

## 구조
| 경로 | 설명 |
|---|---|
| `pipeline/motion_short.py` | 핵심: 장면스펙 → 모션그래픽 HTML + VO 동기 + mux → mp4 |
| `pipeline/extract_scenes.py` | 스토리보드 → 장면스펙(Claude). 키 없으면 사전 스펙/`--spec` 폴백 |
| `pipeline/run_pipeline.py` | 오케스트레이터: 스토리보드 → 스펙 → 렌더 → 업로드(dedupe/로그) |
| `pipeline/motion/` | HyperFrames 프로젝트(템플릿 config + Pretendard woff2) |
| `pipeline/voice 설정·upload_youtube.py·config.py` | v1 재사용 |
| `pipeline/ledger.py` | 업로드 dedupe(main 미커밋, Actions cache 영속) |
| `.github/workflows/shorts.yml` | push to main 트리거 + 자기 재트리거 루프 가드 |

## 문서
- [docs/INVENTORY.md](docs/INVENTORY.md) — v1 파악 + 통합 설계
- [docs/M1](docs/M1_RENDER_REPORT.md)~[M6](docs/M6_REPORT.md) — 마일스톤 리포트
- [docs/SETUP.md](docs/SETUP.md) — 셋업·자격증명·시크릿

## 핵심 원칙
- v2는 **비주얼 레이어만** 바꾼다(음성·자막·타이밍·업로드·dedupe·이미지생성은 v1 재사용).
- 트리거 = main push(cron 아님), **파이프라인은 main에 커밋하지 않음**(루프 방지).
- 업로드 privacy는 JSON을 따름(정치=unlisted), 테스트는 강제 private.
- BGM 기본 off, 자막/음성 싱크는 v1 방식(실 TTS 길이 기반).
</content>
