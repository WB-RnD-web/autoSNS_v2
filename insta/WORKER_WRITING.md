# 인스타 밤 편 '심해 직장인' — 대본 쓰는 법

**11/08 부터 밤 편(c, 21:20)** 은 하루씩 번갈아요: 11/08 이 '위험한 진짜 이유'(DANGER_WRITING), 다음 날(11/09 = 1화) 이 '심해 직장인', 그다음 날 다시 카드 … (11/11 = 2화).
그날 꼴 catalog 가 바닥나면 그날은 밤 편이 없어요. 꼴·항목·회차는 코드가 날짜로 정해요. 대상은 한국 10~20대 직장인·학생.
목표: 첫 1초에 "아 나다ㅋㅋ" 하고 멈추고, 끝 '진짜 과학' 한 장까지 보게 만들기. 목소리는 없어요(글 + 잔잔한 피아노).

## 순서
1. `python insta/pick_plan.py next --slot c` 가 `kind: worker` 를 주면 이 문서를 따라요. `due: false`·`already_written: true` 면
   아무것도 하지 않고 끝내요. 한 번에 한 편.
2. **`entry` = `insta/worker_catalog.json` 의 그날 항목**이에요(사실·출처는 미리 확인해 뒀어요 — 웹을 찾아보지 않아요).
   `src_n`·`episode` 는 `next` 그대로, `sources` 는 entry 를 **그대로 복사**해요. **숫자는 `entry.facts` 에서만.**
   `situation`·`subtitle_idea`·`line_idea`·`scene_ideas`·`fact_idea` 는 출발점이고, `careful` 은 꼭 지켜요.
3. `exemplar`(견본 `insta/samples/worker_monday-9am.json`)와 같은 모양으로 `file` 이름 그대로 써요. 11/09(1화)는 견본을 그대로 써도 돼요.
4. `python insta/pick_reel.py check <파일>` 이 ✅ 가 될 때까지 고쳐요.

## 화면이 어떻게 나오나(약 16초 — 길이는 코드가 정해요)
- 0~6.2초 장면 1 · 6.2~10.8초 장면 2 — 위에 '심해 직장인 N화' 칩 + `subtitle` 칩, 아래에 큰 `line` 한 줄(0초부터 보여요).
- 마지막 5.6초 남색 '진짜 과학' 카드 — `fact.head`(두 줄까지) · `fact.body`(다섯 줄까지) · `fact.hl` 낱말은 노랑 · 출처 줄은 코드가
  entry `source_label` 로 붙여요. entry 에 `gauge` 가 있으면 왼쪽에 수심 게이지도 코드가 그려요.
- 캐릭터('블롭 대리' — 분홍 젤리 블롭피시, 처진 코, 남색 넥타이, 파란 목줄 사원증, 꼬리지느러미)는 코드가 늘 같은 기준 그림에서 편집해요.
  **장면 묘사에 캐릭터 생김새를 다시 쓰지 않아요** — 어디서 무엇을 하는지·표정·빛만.

## 쓰는 법
- `line`: 한국어 공감 한 줄(30자 · 두 줄까지 · 줄바꿈 `\n` 은 한 번까지). 구어체 짧게 — "출근만 하면 얼굴이 녹아요",
  "오후 3시,\n절전 모드 들어갑니다". 숫자는 시각('9시')만 — 그 밖의 숫자는 facts 에 있을 때만. **영어 줄은 쓰지 않아요**(`line_en` 없음).
- `subtitle`: 상황 칩 12자("월요일 아침 9시", "마감 하루 전").
- `shots`: 장면 두 개 `{scene, move, focus}`. `scene` 은 **영어**로 30~600자 — "the blobfish …" 로 시작해 장소·행동·표정·빛.
  장면 2 는 entry `cameo` 가 있으면 그 동료를 넣어요(**`cameo.look` 을 그대로 복사**). `move` 는 in(다가감)·out(물러남),
  `focus` 는 left·center·right(주인공이 화면 가운데에서 벗어나 있을 때만).
- `fact`: `head` 24자(두 줄까지 · '블롭피시도\n집에선 멀쩡해요'), `body` 90자 안(다섯 줄 안 — `\n` 으로 줄을 정해도 돼요),
  `hl` 은 body 안에 **그대로** 있는 낱말(줄바꿈을 걸치지 않게). 사실은 entry facts 를 쉬운 말로만 옮겨요 — 덧붙이거나 부풀리지 않아요.
- `caption`: 한 줄 40자 구어체("블롭피시 얼굴, 사실 '출근 얼굴'이었다"). 앞에 코드가 '심해 직장인 N화 · ' 를 붙여요.
  출처·AI 표시·해시태그도 코드가 붙여요.
- `question`: 열린 질문 한 줄 40자, '?' 로 끝("여러분 출근 얼굴은 몇 시에 제일 녹나요?").
- `hashtags`: 5개까지 · `bench.format` 필수.

## 금지 — check 가 막아요
- **부탁**: 댓글·저장·공유·팔로우·구독·좋아요·태그·링크 부탁 — 캡션 포함. **유튜브** 언급.
- **지어낸 숫자**: 화면·캡션의 숫자는 entry facts 에 있는 수만(시각 '9시'·'3시' 는 괜찮아요).
- 외모 비하 · 잔혹(피·상처·죽음) · 캐릭터·영화 IP(잔망루피·치이카와·디즈니·픽사 …) · 실존 인물 · 상표·지하철 노선 이름·로고.
- `scene`: 한글 X · text·letters·sign·label·logo·writing·portrait·selfie X · **phone X**(부정형으로 써도 폰이 생겨요) ·
  사람은 흐린 배경으로만.

## 모양
| 필드 | 규칙 |
|---|---|
| `date`·`kind`·`src_n`·`episode`·`slug` | kind `worker` · src_n·episode 는 next 그대로 · slug 영어 소문자·하이픈 |
| `subtitle` · `line` | 12자 · 30자(두 줄) — 한국어만 |
| `shots[2]` | `scene`(영어) · `move`(in/out) · `focus`(선택) |
| `fact` | `head` 24자 · `body` 90자 · `hl` |
| `sources` | entry 그대로 복사 |
| `caption` · `question` · `hashtags` · `bench.format` | 한 줄 40자 · '?' 로 끝 40자 · 5개까지 · 필수 |
