# 인스타·쓰레드 릴스·카드 — 0원으로 AI 유튜브 채널을 굴리는 실제 기록

인스타 계정(예전엔 왕별이 뉴스 쇼츠 크로스포스트)을 **한국어 가이드형 운영 기록**으로 바꾼다. 두 채널(왕별이·Nine Tails Tales)을
굴리며 실제로 잰 숫자만, 따라 할 수 있게. 홍보는 프로필·캡션 마지막 줄에만(코드가 붙인다).

## 흐름(전부 무료)
```
인스타 루틴(Claude, 월·수·금·일) ─ insta.py next --date 오늘 → 그날 형식·주제(코드가 날짜로 정한다)
   └ output/insta/<date>_<slug>.json 작성 → insta.py check ✅ → routine/insta 에 push
insta.yml(Actions) ─ 대본 재검사 → stats.py(두 채널 실제 숫자, YouTube Data API 읽기) → render_reel.py + render_cards.py → post_reel.py
   ├ 숫자: 대본엔 {{fact.…}}·{{wb.…}}·{{ntt.…}}·{{vid.…}} 자리표시자만 → 렌더 때 채움(말은 한글 읽기로)
   ├ 목소리: Spark Supertonic F1(왕별이 쇼츠와 같은 목소리, 한 문장씩) · 실패 시 edge-tts
   ├ 화면: 위 두 줄 제목 고정 · 가운데 실물(그림·썸네일·숫자 카드·표) · 자막 · 아래 진행자 자리(INSTA_HOST)
   ├ 소리: 코드로 만든 배경음 + 덕킹, -14 LUFS
   ├ 카드: 같은 대본 → 4:5 JPEG 1080×1350 슬라이드(훅 제목 · 장면마다 한 장 · 저장·팔로우 끝장), 옆으로 넘겨 보기
   └ 게시: ★INSTA_PUBLISH=1 일 때만(기본 dry-run — 호출 순서만 출력) · Cloudinary 공개 URL → 인스타(+INSTA_THREADS=1 이면 쓰레드)
```
- 형식(코드가 요일로 정한다 — `insta.publish_formats`): 릴스·카드는 **매 편 둘 다** 만든다.

  | | 월·수·금 가이드 | 일 성적표 |
  |---|---|---|
  | 인스타 | 릴스 | 카드(캐러셀) |
  | 쓰레드(`INSTA_THREADS=1`) | 카드 | 카드 |

  한쪽 렌더가 실패하면 있는 다른 형식으로 올리고 잡은 실패로 표시한다. 올린 형식은 ledger 와 `posted.json` 에 `formats` 로 남는다.
- 편성: **월·수·금 가이드**(catalog 순서대로, `start` 부터) · **일 주간 성적표** · 화·목·토 쉼.
- 루틴이 `claude/*` 로 잘못 밀면 orphan-rescue 가 `routine/insta` 로 옮긴다.
- 왕별이 쇼츠의 인스타·쓰레드 크로스포스트는 `SOCIAL_CROSSPOST`(기본 0)로 꺼져 있다.

## 레포 변수
| 변수 | 기본 | 뜻 |
|---|---|---|
| `INSTA_PUBLISH` | (없음 = dry-run) | `1` 이면 routine/insta push 때 실제 게시 |
| `INSTA_THREADS` | `0` | `1` 이면 쓰레드에도 |
| `INSTA_IG_FORMAT` | `auto` | 인스타 형식 덮어쓰기: `auto`(위 표) · `reel` · `cards` · `both`(릴스와 카드 둘 다 — 하루 두 게시물) |
| `INSTA_THREADS_FORMAT` | `auto` | 쓰레드 형식 덮어쓰기: `auto`(= 카드) · `cards` · `reel` |
| `INSTA_HOST` | `none` | `gumi` = 아래에 구미 원형 초상('AI 진행자' 표시) |
| `INSTA_VOICE` | `F1` | Supertonic 프리셋(F3·F4 는 숫자 발음 오류 — 쓰지 않는다) |
| `SOCIAL_CROSSPOST` | `0` | 왕별이 쇼츠 → 인스타·쓰레드 크로스포스트(shorts.yml) |

## 파일
| 파일 | 하는 일 |
|---|---|
| `catalog.json` | 가이드 주제 13개(확인된 사실·숫자·주의점·출처) + 두 채널 ID. 새 주제는 **끝에** 붙인다 |
| `WRITING.md` | 루틴이 따르는 작성법 |
| `samples/` | 견본(가이드 `first-second` · 성적표 `weekly-report`) · `samples/cards/` = 가이드 견본 카드 8장(썸네일은 실제, 조회수는 mock) |
| `insta.py` | 편성·검사·자리표시자·한글 숫자 읽기·게시 캡션 |
| `stats.py` | 두 채널 공개 숫자 → stats.json(토큰은 읽기만, 파일에 다시 쓰지 않음) |
| `render_reel.py` | 1080×1920 릴스·커버·한눈에 보기·메타 |
| `render_cards.py` | 1080×1350 카드(캐러셀) 2~10장·한눈에 보기·메타(`<stem>_cards.json` — 캡션·쓰레드 글·주제 태그). 릴스 글꼴·색·그림 캐시를 그대로 |
| `post_reel.py` | 게시(기본 dry-run — 가짜 전송으로 API 호출 순서 출력, 날짜·중복·mock 가드, 형식 정하기, ledger) |
| `posted.json` | 올린 편 기록(다시 올리지 않게) — `{"<date>_<slug>": {"formats": {"ig": ["reel"], "threads": ["cards"]}, "ids": {…}}}`. 로컬에서 실제로 올리면 자동으로 적힌다(커밋해 둘 것). Actions 는 레포에 쓰지 않으므로 ledger 캐시에만 |
| `test_insta.py` | 오프라인 테스트 |

## 로컬
```
python insta/insta.py next --date 2026-10-05
python insta/insta.py check insta/samples/first-second.json
python insta/render_reel.py insta/samples/first-second.json --mock          # Spark·네트워크 없이
python insta/render_cards.py insta/samples/first-second.json --mock         # 카드(output/insta_render/*_card01.jpg …)
INSTA_THREADS=1 python insta/post_reel.py insta/samples/weekly-report.json --today 2026-10-04   # dry-run 호출 순서
python insta/test_insta.py
```
