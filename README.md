# autoSNS_v2

뉴스 → **HyperFrames 모션그래픽 쇼츠** → 유튜브 자동 업로드 파이프라인.

[v1(`WB-RnD-web/autoSNS`)](https://github.com/WB-RnD-web/autoSNS)의 "스토리보드 → 대본·이중음성·자막·타이밍·업로드"를 **그대로 재사용**하고,
정적 투샷 이미지 1장 자리만 **HyperFrames 애니메이션 베드**로 교체한 버전.

## 흐름
```
루틴 → output/news/<date>_<topic>_storyboard.json (main 커밋)
  → [push 트리거] GitHub Actions
     ① generate_images (투샷 이미지, v1 재사용)
     ② voice          (이중음성 edge-tts, v1 재사용)
     ③ bed            (샷별 HyperFrames 모션 베드, v2 신규)
     ④ assemble       (자막 drawtext + 음성 + xfade, v1 포팅)
  → 유튜브 업로드 (privacy 준수, v1 포팅)
```

## 빠른 시작
```bash
cd pipeline
python make_short.py --storyboard ../docs/samples/2026-06-26_economy_storyboard.json
# → output/renders/<date>_<topic>_final.mp4
```
자세한 셋업·시크릿·업로드: **[docs/SETUP.md](docs/SETUP.md)**

## 구조
| 경로 | 설명 |
|---|---|
| `pipeline/make_short.py` | 단일 엔트리포인트: 스토리보드 1개 → 완성 mp4 |
| `pipeline/run_pipeline.py` | 오케스트레이터: 여러 스토리보드 → 렌더 → 업로드(dedupe/로그) |
| `pipeline/bed.py` | 화자별 켄번즈 모션 베드(하단 배너 크롭) |
| `pipeline/voice.py`·`generate_images.py`·`upload_youtube.py`·`config.py` | v1 포팅 |
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
