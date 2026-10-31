# 콘텐츠 채우기(refill) — 주간 채우기 루틴 안내서

너는 일주일에 한 번, **잘 돌고 있는 줄기가 바닥나기 전에 catalog 를 채우는** 편집자다. 목록(catalog)·끝 날짜가 바닥나면
그 줄기는 에러 없이 **조용히 멈춘다**(그날 `next` 가 '쓸 편 없음'을 주고 아무것도 안 올라간다). 그래서 바닥 14일 전에
2주 치를 붙여 **PR 하나**로 올린다. 머지는 사람이 한다.

규칙은 이 문서보다 **코드 검사가 먼저**다. `python tools/refill_check.py` 와 전체 테스트가 ✅ 가 아니면 PR 을 열지 않는다.
검사를 느슨하게 고쳐서 통과시키지 않는다(테스트·검사 파일은 건드리지 않는다).

## 순서

1. `git fetch origin` → `origin/main` 에서 새 브랜치 `refill/<줄기 id>-<YYYYMMDD>`(오늘 KST · 예: `refill/insta_sci-20261101`).
2. `python tools/runway.py --json` — `refillable: true` 이고 `days_left < 14` 인 줄기를 고른다. 한 PR 에 **한 줄기**.
   여러 줄기가 급하면 남은 날이 적은 것부터, 줄기마다 브랜치·PR 을 따로.
3. 그 줄기 절(`refill_doc` = 이 문서의 `#<줄기 id>`)대로 **끝에만** 붙인다 — 배치 크기만큼.
4. `python tools/refill_check.py` → ✅ 가 날 때까지 고친다(새 항목 from · 지난 편성 그대로 · 사실 근거 · 금지어).
5. 그 줄기의 테스트(각 절의 '테스트')를 돌린다. 될 수 있으면 `bash tools/run_tests.sh` 전체도(렌더 테스트처럼 이 환경에 없는
   도구가 필요한 것만 실패하면 괜찮다 — 전체는 6번 뒤 GitHub 이 다시 돌린다).
6. 커밋 — **제목 줄 = PR 제목, 본문 = PR 본문**(아래 템플릿 그대로) → `git push origin refill/<줄기 id>-<YYYYMMDD>`.
   push 하면 GitHub(`.github/workflows/refill-pr.yml`)이 채우기 검사 + 전체 테스트를 돌리고 **통과할 때만 PR 을 연다**.
   PR 은 직접 열지 않는다. 15분쯤 뒤
   `curl -s "https://api.github.com/repos/WB-RnD-web/autoSNS_v2/actions/workflows/refill-pr.yml/runs?branch=<브랜치>&per_page=1"`
   로 결과(conclusion)만 한 번 보고, 실패면 보고에 적는다(고치기는 다음 실행에서).

## 공통 규칙

- **끝에만 붙인다.** 이미 있는 항목은 고치지도, 지우지도, 순서를 바꾸지도, 중간에 끼우지도 않는다 — 지난·정해진 날짜가 바뀐다
  (`refill_check` 가 origin/main 과 날짜 → 편 표를 맞춰 보고 막는다).
- **새 항목마다 `from`(쓸 수 있는 첫날, `YYYY-MM-DD`)** 을 단다. 코드가 from 이후 그 줄기 자리(요일·슬롯)에 차례로 놓는다.
  - 고르는 법: `runway` 의 `last`(마지막 편 날) **다음 날**. 이미 바닥났으면(`days_left` 0) **내일**.
  - from 은 **내일(KST) 이후**여야 한다(`refill_check`). 사람이 머지할 틈이 필요하니 바닥났을 땐 내일보다 2~3일 뒤가 안전하다
    — 머지가 from 보다 늦으면 그 사이 편들은 지나간 날에 놓여 버려진다. (NT 쇼츠는 공개 하루 전에 쓴다.)
  - 마지막 편과 from 사이가 비어도 된다(그동안은 그 줄기가 쉰다). 한 배치는 보통 모두 같은 from.
- **번호(id·n)는 그 줄기 앞 번호 + 1**, 겹치지 않게. slug 는 영어 소문자·하이픈, 겹치지 않게.
- **배치 크기 = 2주 치**(달력 기준이 다른 줄기는 표대로):

  | 줄기 | 파일 | 한 배치 | 자리 |
  |---|---|---|---|
  | `nt_shorts` | `gumiho/tales/shorts_catalog.json` | 28편(survival 14 · compare 7 · liminal 7) | A 매일 · B 하루 한 편 |
  | `nt_longform` | `gumiho/tales/catalog.json` `tales` | 2편 | 일요일 |
  | `wb_gunghap` | `pipeline/gunghap_card.py` `THEMES` | 6묶음 | 화·금 |
  | `wb_lf27` | `pipeline/longform_2027_more.json` | 12편 | 월·수·금 |
  | `insta_sci` | `insta/sci_extra.json` | 14편 | 매일 한 편(저녁·낮 번갈아) |
  | `insta_teardown` | `insta/teardown_catalog.json` `entries` | 10편 | 화·금 |

- **사실 규칙**(사실 줄기: `nt_shorts` survival·compare · `nt_longform` · `insta_sci` · `insta_teardown`):
  - facts 의 **모든 숫자는 출처를 직접 열어** 확인하고, 그 숫자가 든 원문 문장을 `evidence` 에 **그대로** 옮긴다.
    fact 마다 `{"fact": "...", "src": <sources 번호>, "evidence": "<원문 문장>"}`. 확인 못 한 숫자는 빼고, 지어내지 않는다.
  - 환산값(마일 → km, 화씨 → 섭씨, 2.45 billion …)은 fact 문장 안에 `(about 12 liters, converted)` 처럼 적는다 —
    대본 검사가 facts 에 있는 수만 허락한다.
  - 출처는 **기관·대학·표준 단체·학술지**를 먼저(.gov · .edu · NASA · NOAA · NIST · EPA · USGS · 학술지 doi).
    위키·블로그·제조사 홍보 페이지는 쓰지 않는다. https 주소만. 출처마다 fact 가 하나 이상.
  - **보는 사람이 보는 곳에 상표 X**(제목·화면 글·그림 묘사·캡션 '출처:' 에 나가는 출처 도메인 포함).
  - `careful` 에 단정하면 안 되는 것(추정치·'약'·'최대'·미국 기준 …)을 적는다 — 대본 작가가 그대로 지킨다.
- 내용 규칙은 줄기마다 이미 있는 **쓰는 법 문서**를 따른다(아래 각 절의 링크). 금지어는 코드가 막는다.

## 하지 말 것(어기면 사고)

- `routine/*` 브랜치에 push 금지 — 거기 push 는 **진짜 업로드**다. `main` 직접 push·force push 금지.
- `.github/` 워크플로 수정 금지. 테스트·검사(`tools/refill_check.py`·`tools/runway.py`·`test_*.py`)를 느슨하게 고치지 않는다.
- 지난 날짜·이미 편성된 항목을 바꾸지 않는다(위 '끝에만').
- 돈이 드는 서비스·유료 API·새 계정·로그인 금지. 렌더(Spark)는 돌리지 않는다 — catalog 만 채운다.
- 시험 중인 줄기(NT 쇼츠 · 인스타 병맛)는 판정이 '계속'일 때만 머지한다(PR 본문에 적는다).

---

<a id="nt_shorts"></a>
## Nine Tails 영어 쇼츠 — `gumiho/tales/shorts_catalog.json`

- 테스트: `python gumiho/tales/test_rules.py` · `python insta/test_pick.py`(인스타가 같은 catalog 를 읽는다)
- 자리: A `survival` 매일 20:00 UTC · B `compare`(first_publish 기준 짝수 날)·`liminal`(홀수 날) 23:30 UTC — 하루 두 편.
  세 형식 모두 같은 from 이면 코드(`rules.publish_dates`)가 알아서 번갈아 놓는다. 쓰는 날 = 공개 전날.
- **시험 줄기**: 판정일은 이 파일의 `judge`. 판정이 '계속'일 때만 머지(아니면 PR 을 닫는다).
- 번호: survival `1xx`(다음 115~) · compare `2xx`(208~) · liminal `3xx`(308~). `part` = 그 형식 앞 편 + 1.
- 배치: survival 14 + compare 7 + liminal 7 = 28편. 쓰는 법: `gumiho/tales/WRITING_RULES.md`.
- 제목 아이디어: survival `How Long Would You Last …?` · compare `A vs B vs C | … Comparison` · liminal `RULES …`/`Theory`.
  survival `situation` 36자 · `odds_idea` `0%` 꼴 · `teaser` 22자. 금지 주제(한국·설화·실존 피해자·프랜차이즈·SCP)는 막힌다.
  출처는 https + 믿을 만한 곳(rules.REPUTABLE). 편마다 숫자 있는 fact 3개 이상 · 다른 편과 숫자·출처 목록이 겹치지 않게.

```json
{"n": 115, "part": 15, "slug": "inside-venus-clouds", "format": "survival", "look": "space", "from": "2026-11-02",
 "title_idea": "How Long Would You Last in the Clouds of Venus?", "situation": "IN THE CLOUDS OF VENUS", "teaser": "VENUS CLOUDS",
 "sources": ["https://science.nasa.gov/venus/venus-facts/"],
 "facts": [{"fact": "…462 °C…", "src": 0, "evidence": "<NASA 페이지의 그 문장 그대로>"}],
 "beat_ideas": [{"t": "0:00", "what": "…", "fact": 0}], "odds_idea": "0%", "careful": ["…"]}
```
compare 는 `hook_idea`·`unit`·`scale`(linear|log)·`items_idea`(`{name, value, label, fact}` 4개 이상 오름차순 — value 는 facts 의 수)·`twist_idea`.
liminal(창작)은 `premise`·`setting`·`seeds`(4개 이상)·`twist_idea`·`careful` + `"facts": [], "sources": []`.

<a id="nt_longform"></a>
## Nine Tails 해설 롱폼 — `gumiho/tales/catalog.json` → `tales`

- 테스트: `python gumiho/tales/test_tales.py`
- 자리: 주 1편 일요일 14:00 UTC. **`date` 는 적지 않는다** — `from` 만 적으면 `tales.schedule` 이 from 이후 첫 일요일(앞 편 뒤)로 정한다.
- 번호: `id` = 마지막 편 + 1(30~). slug 겹침 X. `region: "GLOBAL"`. 배치 2편.
- `format` 은 해설편(`places`·`zones`·`whatif`·`ranked`·`abandoned`) — 같은 format 4편 넘게 연속 X. 설화·한국·일본·중국 주제 금지.
  `backlog` 제목에서 골라도 된다(골랐으면 backlog 에서 뺀다).
- facts 10개 이상(`{fact, src, evidence}`) · sources 3개 이상(https) · `angle` · `careful` · `shorts`(쇼츠 아이디어 2개).
  쓰는 법: `gumiho/tales/WRITING.md`. 날짜 타는 말(this week·recently·next Sunday …) 금지.

```json
{"id": 30, "slug": "every-planet-survival", "region": "GLOBAL", "format": "places", "look": "real", "from": "2026-11-02",
 "title_idea": "How Long Would You Survive on Every Planet in the Solar System?", "angle": "…",
 "facts": [{"fact": "…", "src": 0, "evidence": "…"}], "careful": ["…"],
 "sources": ["https://science.nasa.gov/…"], "shorts": ["…", "…"]}
```

<a id="wb_gunghap"></a>
## 띠 궁합표 — `pipeline/gunghap_card.py` → `THEMES`

- 테스트: `python pipeline/test_gunghap_card.py`
- 자리: 화·금 18:13 KST. 끝에 붙인 묶음은 `schedule` 이 from 이후 첫 화·금부터(앞 묶음 다음) 놓는다. 배치 6묶음.
- 번호: `id` = 영어 소문자 한 낱말(겹침 X). 묶음 하나 = 함수 하나(`_<id>(b)` → `([(짝 띠 번호, 관계 이름)…], [(조심할 띠 번호, 관계 이름)…])`)
  + `THEMES` 끝의 dict. 관계는 이 파일의 전통 지지 관계 도우미만 쓴다(`pair_of(YUKHAP|WONJIN, b)` · `samhap_mates` · `chung` ·
  `_by_el` · `sangsaeng`) — 새 '사실'을 지어내지 않는다. 관계 이름이 `ONE` 에 없으면 칸 한 줄(10자)도 함께 넣는다.
- **같은 표를 다시 올리지 않는다** — 좋은 짝·조심할 띠 조합이 기존 묶음과 같으면 테스트가 막는다. 근거(`why`)가 편마다 다르게.
- `card`(화면 제목) · `yt`(유튜브 제목 앞부분) · `cols`(표 머리 두 개) · `years`(`self` 또는 손주 `grand`) · `why` · `hook`
  (배경 그림 — 영어, 사람 없음, `no people` 로 끝) · `from`. 제목 95자 · 내레이션 80자 · 왕별이 금지어(의료·투자·겁주기) X.
  기준: 이 파일 맨 위 설명 · `pipeline/theme_card.py` `BANNED`.

```python
def _siblings(b):
    """형제·자매 궁합 — 삼합(한 팀)을 좋게, 해(서로 손해)를 조심할 짝으로."""
    mates, nm = samhap_mates(b)
    return [(x, f"{nm} 삼합") for x in mates], [(pair_of(HAE, b), "해")]


THEMES.append({"id": "siblings", "card": "형제·자매 궁합표", "yt": "형제·자매 띠 궁합표", "cols": ("한 팀 되는 띠", "손해 보는 띠"),
               "fn": _siblings, "years": "self", "why": "…", "hook": "… no people", "from": "2026-11-03"})
```
(도우미가 쓰는 관계표 `HAE` 등은 `pulli_card` 에서 가져온다 — 필요하면 import 줄에 더한다.)

<a id="wb_lf27"></a>
## 2027 정미년 깊이 보기 이어 가기 — `pipeline/longform_2027_more.json`

- 테스트: `python pipeline/test_longform_2027.py`
- 자리: 월·수·금 20:00 KST. E01~E16(11/02~12/07)은 코드가 정한 편 — 그 뒤로 `episodes` 에 E17~ 을 적으면
  from 이후 첫 월·수·금부터(앞 편 다음) 이어진다. 배치 12편. **적은 뒤** `python pipeline/longform_2027.py catalog --write`
  (커밋된 `longform_2027_catalog.json` 이 코드 출력과 같아야 테스트가 통과한다).
- 사실(신살·삼재·합충·좋은 달·행운)은 코드가 띠마다 계산한다(`ddi_facts`) — 웹 숫자를 넣지 않는다.
- 명세 검사(`longform_2027.more_errs`, 틀리면 그 편부터 편성되지 않는다): `id` 앞 편 다음(E17, E18 …) · `from` ·
  `animals`(12띠 이름) · `title`('2027년 …띠'로 시작 · 100자 · 금지어·한자 X · 살 낱말은 조언 틀 안 — sal_frame) ·
  `thumb`{big, sub, pill} · `angle`(앞 편들과 무엇이 다른지) · `chapters` 10개 이상(`c01`… · layout `card`·`table`(`sinsal12`·
  `months3`·`months1`·`people12`)·`years`·`qa`·`lucky` · 4가지 이상 · `years` 장이 그 편 띠의 1930~2009년생을 빠짐없이) ·
  `qa_seeds` 3~5개. 같은 띠를 다시 다룰 땐 주제를 좁혀(재물·건강·가족·달력 …) **편마다 새 정보**로 — 반복 영상 X.
  쓰는 법: `pipeline/LONGFORM_2027_WRITING.md`.

```json
{"episodes": [
 {"id": "E17", "from": "2026-12-09", "animals": ["양"],
  "title": "2027년 양띠 재물운 깊이 보기 | 돈이 도는 달과 지킬 것 · 출생연도별 풀이",
  "thumb": {"big": "2027 양띠", "sub": "재물운", "pill": "돈이 도는 달"}, "angle": "양띠 재물만 깊게 — …",
  "chapters": [{"id": "c01", "layout": "card", "topic": "money", "title": "…"},
               {"id": "c08", "layout": "years", "animal": "양", "years": [1931, 1943, 1955], "title": "출생연도별 풀이 ① …"}],
  "qa_seeds": ["…", "…", "…"]}]}
```

<a id="insta_sci"></a>
## 인스타 sci(도파민 과학 · 속이 보이는 과학) — `insta/sci_extra.json`

- 테스트: `python insta/test_pick.py`
- 자리: 하루 한 편, 저녁·낮 번갈아(11/08~ 은 항목이 남은 날만 — `pick_plan.open_plan`). 화·금은 뜯어보기가 먼저 쓴다.
  배치 14편. `from` 이 없는 항목은 편성되지 않는다.
- 번호: `n` 904~950(앞 번호 + 1). `survival` 또는 `compare` 목록 끝에. 모양은 901~903 과 같다 + fact 마다 `evidence`.
- 검사: `insta/pick_reel.py entry_errs`(모양 · beat_ideas·hook_idea 의 숫자는 facts 에 · 잔혹·실존 인물·프랜차이즈 X · from).
  쓰는 법: `insta/SCI_WRITING.md`(숫자는 facts 에서만 · 부탁 금지 · 잔혹 묘사 금지).
- 구미호 쇼츠(shorts_catalog)의 survival·compare 항목을 인스타에도 쓰려면 그 항목에 `insta_from` 을 단다(복사하지 않는다).

```json
{"n": 904, "slug": "inside-a-hurricane-eye", "format": "survival", "look": "earth", "from": "2026-11-08",
 "title_idea": "How Long Would You Last in the Eye of a Hurricane?", "situation": "EYE OF A HURRICANE", "teaser": "HURRICANE EYE",
 "sources": ["https://www.nhc.noaa.gov/…"], "facts": [{"fact": "…", "src": 0, "evidence": "…"}],
 "beat_ideas": [{"t": "0:00", "what": "…", "fact": 0}], "odds_idea": null, "careful": ["…"]}
```

<a id="insta_teardown"></a>
## 과학으로 뜯어보는 물건(teardown) — `insta/teardown_catalog.json` → `entries`

- 테스트: `python insta/test_pick.py`
- 자리: 화·금 sci 자리(11/09 주~). 배치 10편(5주). 비거나 바닥나면 그날은 보통 sci.
- 번호: `n` 961~(앞 번호 + 1). `"series": "teardown"` · `"format": "teardown"` · `"look": "object"` · `from`.
- 모양: 951~960 과 같다 — `topic_ko`·`topic_en`·`title_idea`·`teaser`·`hook_idea`(두 줄)·`why_idea`·`steps`(세 박자)·
  `result_idea`·`sources`·`facts`{fact, src, evidence}·`mechanism_refs`(숫자 없는 원리 근거 {note, src, evidence})·
  `beat_ideas`(`{beat, view: cutaway, img, label, fact}` — img 는 영어, 글자·로고·얼굴 X)·`careful`.
  아이디어 글(hook·why·steps·result·label)의 숫자도 facts 에 있어야 한다(환산값은 facts 에 — 화면엔 `24.5억 번` 처럼).
- **상표·모델 이름 X**(글·그림·**출처 도메인** — 제조사 홍보 페이지는 출처로 쓰지 않는다) · "직접 열어 보세요" X ·
  안전·건강 단정 X. 쓰는 법: `insta/SCI_WRITING.md` '뜯어보기'.

---

## 채우지 않는 줄기

- 끝없음(날짜 순환·매일 루틴): 06:13 매일 운세 · 띠 테마/나이 표 · 내 것 찾기 · 풀이형 표 · 인스타 골라보기.
- 꺼짐·일부러 끝냄: 수면판(설화 금지로 꺼짐) · 신년운세 1차 묶음(시리즈가 이어받음) · 주간 롱폼(깊이 보기가 대신).
- 사람과 정하는 것: 06:13 신년운세 시리즈(편 설계 — 코드 PR) · 인스타 병맛 시험(판정 11/08 — 이어 가려면 `BM_TO`·`BM_ORDER` 코드 PR).
- 아직 이 루틴 밖(refill_check 미지원): 인스타 밤 편 `insta_worker`(`insta/worker_catalog.json` · `insta/WORKER_WRITING.md`)·
  `insta_danger`(`insta/danger_catalog.json` · `insta/DANGER_WRITING.md`) — 2026-11-08 시작, 16편씩(12/08·12/09 까지).
  채울 땐 같은 사실 규칙(evidence·기관 출처) + 끝에만 + from, 번호 worker 517~ · danger 617~ (`python insta/test_bc.py`).
  이런 줄기가 바닥나면 PR 대신 맥박 보고서 `actions` 에 남긴다.

## PR 템플릿

- 브랜치: `refill/<줄기 id>-<YYYYMMDD>` · 제목: `채우기: <줄기 이름> <N>편(<첫 날>~<마지막 날>)`

```markdown
## 무엇을 붙였나
- 줄기: <줄기 id> — <파일>
- 항목: <번호 범위>(<N>편) · from <날짜>
- 편성: <첫 날> ~ <마지막 날>(python tools/runway.py --date <머지 예정일> 의 그 줄기 줄)

## 출처
- <번호>: <URL> — <기관·학교·표준 단체 이름>
- …(사실 줄기만 — 숫자마다 evidence 를 catalog 에 적었다)

## 검사
- python tools/refill_check.py ✅(출력 붙이기)
- 그 줄기 테스트 ✅ · 전체 테스트는 refill-pr.yml 이 PR 을 열기 전에 다시 돌렸다

## 머지
- 시험 중인 줄기(NT 쇼츠·bm)는 판정이 '계속'일 때만 머지
- from(<날짜>) 전에 머지해야 첫 편부터 나간다

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
