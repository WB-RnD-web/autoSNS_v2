# 레포 공개 전환 런북

**목적**: GitHub Actions 분 무제한(public 레포 + standard runner) 을 얻는다.
**대가**: 히스토리 전체가 공개된다 → 그 전에 **프롬프트 문서를 히스토리에서 걷어낸다.**

이 레포에서 실제로 지킬 가치가 있는 건 결과물이 아니라 **만드는 방법**이다.

| 공개되는 것 | 실질 손실 |
|---|---|
| 파이프라인 코드 | 거의 없음 — ffmpeg 조합이다 |
| `output/**` 스펙 JSON (대본) | 거의 없음 — **이미 유튜브에 영상으로 공개된 내용** |
| `scp/library.json` | 사소 — 쓴 번호·다음 로테이션 |
| **`docs/ROUTINE_PROMPT_*.md` (65KB)** | 🔴 **이게 전부다** — 이것만 걷어내면 된다 |

파이프라인도 워크플로도 이 문서들을 **읽지 않는다.** 루틴에 붙여넣는 용도라 빼도 아무것도 안 깨진다.

---

## 0. 시작 전 확정

- [ ] **조직 레포 공개가 회사 정책상 가능한가** — `WB-RnD-web` 조직 자산이다. 승인 필요할 수 있음
- [ ] 프롬프트를 옮길 곳 정함 (사내 위키 / private gist / 로컬)
- [ ] 팀원에게 공지 — 히스토리 재작성 후 기존 클론은 pull 이 깨진다(다시 클론해야 함)

## 1. 정리 (재작성 전에)

- [ ] **열린 PR 전부 머지 또는 닫기**
      재작성하면 PR 의 커밋 SHA 가 전부 무효가 되어 이상하게 남는다
- [ ] **안 쓰는 원격 브랜치 삭제** — 재작성 대상이 줄고 실수도 준다
      ```bash
      git branch -r | grep -v 'HEAD\|main\|routine/' # 목록 확인 후
      git push origin --delete <branch>
      ```
- [ ] 작업 트리 커밋/stash 로 비우기

## 2. 히스토리에서 프롬프트 제거

```bash
pip install git-filter-repo

./tools/strip_prompts_from_history.sh check   # 점검만 — 아무것도 안 바꾼다
./tools/strip_prompts_from_history.sh run     # 백업 + 재작성 + 검증 (★로컬만)
```

`run` 이 하는 일:
1. **미러 백업** `../autoSNS_backup-<시각>.git` — 되돌릴 유일한 수단
2. **프롬프트 원본 보관** `../autoSNS_backup-<시각>/prompts/` — 사내 위키로 옮길 것
3. `git filter-repo --invert-paths` 로 4개 경로를 전 히스토리에서 제거
4. **검증** — 경로 0건 · 내용 지문 0건 · 자격증명 패턴 0건

검증이 하나라도 실패하면 스크립트가 멈춘다. **그 상태로 push 하지 마라.**

- [ ] `run` 통과
- [ ] 백업 경로 2개를 안전한 곳에 복사 (다른 디스크 / 사내 스토리지)
- [ ] `../autoSNS_backup-*/prompts/` 를 사내 위키로 옮김

## 3. 원격 반영 — ★되돌릴 수 없는 지점

```bash
./tools/strip_prompts_from_history.sh push    # 'FORCE PUSH' 입력 요구
```

- [ ] 실행
- [ ] GitHub 웹에서 확인: `docs/` 에 프롬프트 없음 · 과거 커밋에서도 안 보임
- [ ] 루틴 브랜치(`routine/scp`, `routine/asmr`) 도 정상인지 확인

> **재작성 직후 주의** — 루틴이 다음에 돌 때 `git pull --ff-only` 가 실패할 수 있다.
> 루틴은 매번 새로 클론하므로 대개 문제없지만, 첫 런은 로그를 확인할 것.

## 4. ★GitHub Support 에 GC 요청 (public 전환 전에)

force-push 로 참조가 끊긴 커밋도 GitHub 에는 **한동안 SHA 로 접근 가능**하게 남는다.
private 인 동안은 팀만 볼 수 있지만, **public 으로 돌리는 순간 SHA 를 아는 사람은 볼 수 있다.**

https://support.github.com/contact 에 요청:

> Repository: WB-RnD-web/autoSNS_v2
> We rewrote history with git-filter-repo to remove sensitive documents.
> Please garbage-collect unreachable objects and purge cached views
> before we change the repository visibility to public.

- [ ] 요청 보냄 (일자: ______)
- [ ] 처리 확인 (일자: ______)

> 현실적 위험은 낮다 — 끊긴 커밋의 40자 SHA 를 알아야 접근할 수 있고, 어디에도 노출되지 않는다.
> 다만 되돌릴 수 없는 작업이라 표준 절차를 밟는 쪽이 맞다.
> **급하면 이 단계를 건너뛰고 공개해도 실질 위험은 크지 않다** — 판단은 각자.

## 5. 공개 전환

Settings → General → 맨 아래 **Danger Zone → Change visibility → Make public**

- [ ] 전환
- [ ] Actions 탭에서 런 1건 성공 확인
- [ ] **Settings → Actions → General** 에서 fork PR 정책 확인
      (기본값이면 fork PR 에 시크릿이 주입되지 않는다 — 그대로 두면 된다)

## 6. 공개 후 확인

- [ ] **Actions 로그에 토큰이 안 찍히는지** 최근 런 1건을 열어서 눈으로 확인
      GitHub 이 등록된 시크릿은 `***` 로 가리지만, **파생값(JSON 을 파싱해 꺼낸 일부)은 안 가려진다**
- [ ] `.gitignore` 가 `pipeline/secrets/` · `pipeline/.env` 를 막고 있는지 재확인
- [ ] GitHub Pro 결제 해지 판단 (public 이면 분이 무제한이라 불필요)
- [ ] 백업 미러는 **최소 1개월 보관** 후 폐기

---

## 되돌리기

공개 전환은 Settings 에서 다시 private 로 돌릴 수 있다(이미 클론된 건 되돌릴 수 없다).

히스토리는 백업 미러로 복원한다:
```bash
cd ../autoSNS_backup-<시각>.git
git push --force --mirror <원격 URL>
```

---

## 이 방법을 안 골랐을 때의 대안

| | 비용 | 작업량 | 분 |
|---|---|---|---|
| **public 전환** | $0 | 반나절 | 무제한 |
| GitHub Pro | $4/월 | 클릭 한 번 | 3,000 (실측 사용 ~1,400) |
| 사내 GitLab 이주 | $0 | 1~2주 + 토큰 전량 재발급 | 무제한 |

Pro 로도 충분하다는 점은 짚어둔다 — **공개 전환은 "돈"이 아니라 "$4 를 안 내겠다"는 선택**이다.
프롬프트를 걷어내면 잃는 게 거의 없다는 게 이 문서의 결론이지만,
조직 자산을 공개하는 결정 자체는 기술 판단이 아니다.
