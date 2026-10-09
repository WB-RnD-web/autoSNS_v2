# Nine Tails Tales (개인 채널 → 영어 해설·생존 채널)

채널: https://www.youtube.com/@NineTailsTales (구 Gumiho Games, UCoPIsIO_ximUdyh-n_-rIfQ) · 왕별이와 무관.
★2026-10-09 개편: 사용자가 한국 설화·조선 주제를 금지했다. 20~39세 해외 시청자. 구미는 화면에 나오지 않고 목소리로만 진행한다.
- 롱폼: 해설편 주 1편(극한 장소·심해 구역별·what-if) — 27화부터, 일요일 14:00 UTC. 설화 1~26화는 `retired`(올리지 않음).
- 쇼츠: A 'How Long Would You Last…? Pt.N' 매일 20:00 UTC · B 'Ranked'·'Liminal Rules' 격일 23:30 UTC(10/13~10/26 시험, 10/27 판정).
  옛 규칙괴담 R001~R028 은 10/9 배정분에서 끝(rules.py 가 막는다). 작성법은 `WRITING_RULES.md`, 편성은 `shorts_catalog.json`.
- 채널 소개·재생목록 초안: `CHANNEL.md`.

## 흐름(전부 무료)
```
Tales 루틴(Claude, 토요일) ─ tales.py next --date 오늘 → 그 주(다음 날 일요일) 해설편 한 편
   └ output/tales/NNN_slug.json 작성(견본이 있으면 그대로 복사) → tales.py check ✅ → routine/tales 에 push
tales.yml(Actions) ─ 대본 재검사(retired 는 멈춤) → render_tale.py → upload_tale.py
   ├ 목소리: Spark Supertonic F2 (동시 2건, 캐시)
   ├ 그림:   Spark z-image-turbo 한 장씩(대기열 6 초과면 대기) · 실패 시 NVIDIA 무료 FLUX · 해설편은 실사 화풍(look "real")
   ├ 화면:   켄 번스 + 교차 전환 + 입자 + 비네트 + 꼭지별 판정 띠 (PIL → ffmpeg, 4프로세스)
   └ 소리:   내레이션 + 코드로 만든 배경음 + 카드 효과음, -14 LUFS
```
- 본편 약 10분(WRITING.md 분량) + 쇼츠(꼭지 하나씩 잘라 씀). 쇼츠 끝맺음은 "FULL VIDEO ↓" — 본편 링크를 짚는다.
- 공개 방식: 레포 변수 `TALES_PUBLISH` = `private`(기본) | `scheduled`(catalog date 일요일 14:00 UTC, 붙은 쇼츠는 본편 뒤 월·수·금 14:00 UTC).
  렌더가 늦으면 다음 주로 미루지 않고 지금+2시간 정각.
- 루틴이 `claude/*` 로 잘못 밀면 orphan-rescue 가 `routine/tales` 로 옮긴다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `catalog.json` | 편성표 — 해설편은 일요일 `date`·확인된 사실·주의점·출처(숫자마다 그 숫자가 적힌 페이지). 설화 1~26화는 `retired` |
| `WRITING.md` | 해설편 작성법(목소리·구조·판정 띠·분량·그림 프롬프트·쇼츠) |
| `scripts/027_places-you-cant-survive.json` | 해설편 견본(10/18 공개분 — 루틴이 그대로 복사) |
| `tales.py` | 대본 검사(금지어·facts 에 없는 숫자·출처·지어낸 생존 시간)·챕터·설명·태그·편성 |
| `render_tale.py` | 렌더(본편·쇼츠·썸네일·자막·한눈에 보기) |
| `upload_tale.py` | 업로드(비공개/예약) · ledger · 해설편 재생목록 `EX_PLAYLISTS` |
| `test_tales.py` | 오프라인 테스트 |
| `sleep.py` | 수면판 — ★`ENABLED = False`(2026-10-09, 설화 편을 다시 짓는 판이라 끔) |

## 로컬
```
python gumiho/tales/tales.py check gumiho/tales/scripts/027_places-you-cant-survive.json
python gumiho/tales/render_tale.py gumiho/tales/scripts/027_places-you-cant-survive.json --mock   # Spark 없이
python gumiho/tales/test_tales.py
python gumiho/tales/test_rules.py
```
