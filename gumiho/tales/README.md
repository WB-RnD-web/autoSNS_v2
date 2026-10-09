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
  쇼츠 끝 3~5초는 코드가 붙이는 끝맺음(말 + 카드 + 아래 화살표 → '관련 동영상' 링크, 2026-10-09 · render_tale.CTA_*).
- 공개 방식: 레포 변수 `TALES_PUBLISH` = `private`(기본) | `scheduled`(다음 토요일 15:00 UTC, 쇼츠는 하루 전).
- 루틴이 `claude/*` 로 잘못 밀면 orphan-rescue 가 `routine/tales` 로 옮긴다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `catalog.json` | 편성표 — 번호·설화·형식(tale·urban·list·versus·behind·mystery)·확인된 사실·주의점·출처. 날짜로 편 번호가 정해진다(9/30(수) 주 = 2편, 7일마다 +1) |
| `WRITING.md` | 루틴이 따르는 작성법(목소리·구조·분량·그림 프롬프트·쇼츠) |
| `scripts/001_gumiho.json` | 사람이 쓴 1화(견본) |
| `tales.py` | 대본 검사(분량·장면·필드·금지어)·챕터·설명·태그·편성 |
| `render_tale.py` | 렌더(본편·쇼츠·썸네일·자막·한눈에 보기) |
| `upload_tale.py` | 업로드(비공개/예약) · ledger |
| `test_tales.py` | 오프라인 테스트 |
| `sleep/NNN_slug.json` | 수면판(월 1회) spec — 묶을 편·새 연결 내레이션·render_from·publish_at |
| `sleep.py` | 수면판 검사·due·렌더·업로드(편을 자르고 느리게·어둡게·빗소리로 다시 짓는다) |
| `test_sleep.py` | 수면판 오프라인 테스트(가짜 편 두 개로 끝까지 렌더) |

## 수면판(Sleep Edition, 월 1회)
```
tales-sleep.yml(매일 12:41 KST) ─ sleep.py due → render_from 지남·대본 다 있음·안 올림
   └ seen(유튜브 표식 'Sleep Edition NNN' 확인) → sleep.py render → sleep.py upload(publish_at 예약)
```
- 같은 영상을 이어 붙이기만 하면 재사용 콘텐츠다 → 새 연결 내레이션(인트로·편 사이·아웃트로)·새로 그린 그림·
  느린 목소리(0.92)·긴 전환·어두운 화면·빗소리·끝 10분 비 화면으로 다시 짓는다.
- 편에서 가져오는 범위는 코드가 자른다: TALE 카드부터, 마지막 카드 뒤 '댓글/다음 편' 줄 앞까지. 장 카드·화면 주석·
  '지난 편/다음 편' 말은 뺀다.
- 다음 수면판은 `sleep/002_*.json` 을 PR 로 추가한다(render_from 은 묶을 마지막 편이 공개된 다음 날).

## 로컬
```
python gumiho/tales/tales.py check gumiho/tales/scripts/001_gumiho.json
python gumiho/tales/render_tale.py gumiho/tales/scripts/001_gumiho.json --mock   # Spark 없이
python gumiho/tales/test_tales.py
```
