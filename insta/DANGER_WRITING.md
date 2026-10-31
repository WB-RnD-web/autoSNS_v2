# 인스타 밤 편 '위험한 진짜 이유' — 대본 쓰는 법

**11/08 부터 밤 편(c, 21:20)** 은 하루씩 번갈아요: 11/08 이 이 카드(#1), 다음 날이 '심해 직장인'(WORKER_WRITING), 그다음 날 다시 카드(11/10 = #2) …
꼴·항목·번호는 코드가 날짜로 정해요. 제목은 무섭고, 끝은 귀엽고 해롭지 않은 **진짜** 사실 — "위험할 만큼 귀엽다"가 웃음이에요.
대상은 한국 10~20대. 목소리는 없어요(글 + 잔잔한 피아노).

## 순서
1. `python insta/pick_plan.py next --slot c` 가 `kind: danger` 를 주면 이 문서를 따라요. `due: false`·`already_written: true` 면
   아무것도 하지 않고 끝내요. 한 번에 한 편.
2. **`entry` = `insta/danger_catalog.json` 의 그날 항목**이에요(사실·출처는 미리 확인해 뒀어요 — 웹을 찾아보지 않아요).
   `src_n`·`card_no` 는 `next` 그대로, `title`·`sources` 는 entry 를 **그대로 복사**해요. **숫자는 `entry.facts` 에서만.**
   `tease_idea`·`payoff_idea`·`aside_idea`·`image`·`motion` 은 출발점이고, `careful` 은 꼭 지켜요.
3. `exemplar`(견본 `insta/samples/danger_jellyfish-sleep.json`)와 같은 모양으로 `file` 이름 그대로 써요. 11/08(#1)은 견본을 그대로 써도 돼요.
4. `python insta/pick_reel.py check <파일>` 이 ✅ 가 될 때까지 고쳐요.

## 화면이 어떻게 나오나(14초 — 시간은 코드가 정해요)
- 크림 바탕 흰 카드: 프로필 줄 + '동물 상식 · 위험한 진짜 이유 #N' · 굵은 두 줄 `title`('위험한'만 빨강) · 가운데 동물 그림
  (앞 1.4초는 살짝 움직이고, 그 뒤 천천히 다가가요).
- 2.2초 회색 `tease`(헛짚기) → 7.4초 큰 `payoff`(형광펜) → 9.6초 작은 `aside` → 출처 줄은 코드가 entry `source_label` 로 붙여요.
- 그림 위에 동그라미·화살표 같은 장식은 없어요(그림을 매번 새로 그려서 위치를 맞출 수 없어요).
- entry `image_note` 가 있으면(그림이 실제 종과 다를 수 있을 때) 코드가 캡션 AI 표시 줄에 밝혀요 — 대본에서 따로 안 써도 돼요.

## 쓰는 법
- `tease`: 헛짚기 한 줄 18자, '?' 로 끝("독침 때문에…?", "날카로운 이빨 때문에…?").
- `payoff`: 반전 한 줄 24자 — **한 줄에 들어가야** 해요(길면 check 가 막아요). 사실 그대로, 단정하기 어려우면 '~할 때도 있다'.
- `aside`: 덧붙임 한 줄 30자(선택 — 안 쓰면 필드를 빼요). 숫자는 facts 에서만.
- `image`: **영어** 30~600자 — 동물 한 마리(또는 같은 종 몇 마리) · 귀엽게 · 단순한 배경 · 가로 사진. entry `image` 를 그대로 써도 돼요.
- `motion`: 영어 한 줄(선택) — "…, static camera, very subtle movement" 로 끝.
- `caption`: 한 줄 40자 구어체("해파리, 뇌도 없으면서 잠은 잘 잠"). 앞에 코드가 '위험한 진짜 이유 #N · ' 를 붙이니 제목을 되풀이하지 않아요.
  출처·AI 표시·해시태그도 코드가 붙여요.
- `question`: 열린 질문 한 줄 40자, '?' 로 끝.
- `hashtags`: 5개까지 · `bench.format` 필수.

## 금지 — check 가 막아요
- **부탁**: 댓글·저장·공유·팔로우·구독·좋아요·태그·링크 부탁 — 캡션 포함. **유튜브** 언급.
- **지어낸 숫자**: 화면·캡션의 숫자는 entry facts 에 있는 수만.
- 진짜로 위험한 행동을 권하는 말("만져 봐"·"집에서 해 봐") · 잔혹 · 캐릭터·영화 IP · 실존 인물 · 상표.
- `image`·`motion`: 한글 X · text·letters·sign·label·logo·writing·portrait·selfie X · phone X · 사람 X.
- `sticker` 필드 X.

## 모양
| 필드 | 규칙 |
|---|---|
| `date`·`kind`·`src_n`·`card_no`·`slug` | kind `danger` · src_n·card_no 는 next 그대로 · slug 영어 소문자·하이픈 |
| `title` · `sources` | entry 그대로 복사 |
| `image` · `motion` | 영어 · motion 은 선택 |
| `tease` · `payoff` · `aside` | 18자('?' 로 끝) · 24자 한 줄 · 30자(선택) |
| `caption` · `question` · `hashtags` · `bench.format` | 한 줄 40자 · '?' 로 끝 40자 · 5개까지 · 필수 |
