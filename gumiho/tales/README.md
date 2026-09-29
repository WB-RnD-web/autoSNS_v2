# Nine Tails Tales (개인 채널 → 영어 설화 채널)

채널: https://www.youtube.com/@NineTailsTales (구 Gumiho Games, UCoPIsIO_ximUdyh-n_-rIfQ) · 왕별이와 무관.
천 년 묵은 구미호 **구미**가 한국(중심)·일본·중국 설화를 영어로 들려준다. 13~30세 해외 시청자.

## 흐름(전부 무료)
```
Tales 루틴(Claude, 주 1회) ─ tales.py next --date 오늘 → 그 주의 설화 한 편
   └ output/tales/NNN_slug.json 작성 → tales.py check ✅ → routine/tales 에 push
tales.yml(Actions) ─ 대본 재검사 → render_tale.py → upload_tale.py(기본 비공개)
   ├ 목소리: Spark Supertonic F2 (동시 2건, 캐시)
   ├ 그림:   Spark z-image-turbo 한 장씩(대기열 6 초과면 대기) · 실패 시 NVIDIA 무료 FLUX
   ├ 화면:   켄 번스 + 교차 전환 + 입자 + 비네트 (PIL → ffmpeg, 4프로세스)
   └ 소리:   내레이션 + 코드로 만든 배경음(드론·바람·오음계) + 카드 효과음, -14 LUFS
```
- 본편 10~15분(1,700~2,300단어) + 쇼츠 35~55초(본편 장면 재사용, 결말은 숨김).
- 공개 방식: 레포 변수 `TALES_PUBLISH` = `private`(기본) | `scheduled`(다음 토요일 15:00 UTC, 쇼츠는 하루 전).
- 루틴이 `claude/*` 로 잘못 밀면 orphan-rescue 가 `routine/tales` 로 옮긴다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `catalog.json` | 편성표 — 번호·설화·확인된 사실·주의점·출처. 날짜로 편 번호가 정해진다(9/30(수) 주 = 2편, 7일마다 +1) |
| `WRITING.md` | 루틴이 따르는 작성법(목소리·구조·분량·그림 프롬프트·쇼츠) |
| `scripts/001_gumiho.json` | 사람이 쓴 1화(견본) |
| `tales.py` | 대본 검사(분량·장면·필드·금지어)·챕터·설명·태그·편성 |
| `render_tale.py` | 렌더(본편·쇼츠·썸네일·자막·한눈에 보기) |
| `upload_tale.py` | 업로드(비공개/예약) · ledger |
| `test_tales.py` | 오프라인 테스트 |

## 로컬
```
python gumiho/tales/tales.py check gumiho/tales/scripts/001_gumiho.json
python gumiho/tales/render_tale.py gumiho/tales/scripts/001_gumiho.json --mock   # Spark 없이
python gumiho/tales/test_tales.py
```
