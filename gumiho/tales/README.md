# Nine Tails Tales (개인 채널 → 영어 해설·생존 채널)

채널: https://www.youtube.com/@NineTailsTales (구 Gumiho Games, UCoPIsIO_ximUdyh-n_-rIfQ) · 왕별이와 무관.

## ★2026-11 재개: 얼굴 없는 3D 실화·what-if 쇼츠(이게 지금 도는 유일한 줄기)
10/27 판정 '가망 없음'으로 쉬던 채널을 10/31 사용자 결정('2차 견본 수준으로 재개')으로 다시 연다. 아래 옛 롱폼·쇼츠 루틴은 꺼진 그대로다.
- 대본: `story_catalog.json` — 미리 다 써 둔다(루틴·LLM 없음). 편마다 공개일 `from`(월·수·금) · 제목·설명 · 장면(말 + 그림) ·
  사실(facts, 실제로 연 출처 번호) · 출처(sources) · 조심할 점(careful). 사람은 얼굴 없는 마네킹으로만(검사가 막는다).
- 검사·편성·업로드: `story.py`(check · plan · due · seen · upload) · 렌더: `story_reel.py`(Spark 그림 + qwen 편집으로 인물 유지 ·
  느린 밀기/패닝 · 카라오케 자막 · edge-tts Andrew · -15 LUFS). ★5B 영상 클립·패럴랙스는 쓰지 않는다(깨짐 0 이 먼저).
- 워크플로 `nt-story.yml`: 01:00·03:30·10:00 KST 에 깨서 공개 전날~당일 편을 렌더 → 비공개 + 22:00 KST 예약 공개.
  05:45~08:00 KST 는 Spark 를 쓰지 않는다(다음 예비가 잇는다). ledger 캐시 + 설명란 표식으로 두 번 안 올린다.
- 판정: `tools/pulse_experiments.json` 'nt-relaunch-3d'(12/02). 편을 더할 땐 카탈로그 끝에 붙이고 `python gumiho/tales/story.py check`.

## (옛) 2026-10 구성 — 꺼짐
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
