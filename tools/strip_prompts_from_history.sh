#!/usr/bin/env bash
# 루틴 프롬프트 문서를 git 히스토리에서 ★완전히 제거한다.
#
# 왜: 레포를 public 으로 돌리면 히스토리 전체가 공개된다. 파일만 지우고 커밋해봐야
#     과거 커밋에서 그대로 읽힌다. 이 채널의 진짜 자산은 결과물(대본)이 아니라
#     '만드는 방법'(프롬프트)이라, 그것만 걷어내면 공개해도 잃는 게 거의 없다.
#
# ⚠️ 히스토리 재작성이다. 되돌릴 수 없다. 3단계로 나눠 놨으니 순서대로 할 것.
#
#   ./tools/strip_prompts_from_history.sh check   # 사전 점검만 (아무것도 안 바꾼다)
#   ./tools/strip_prompts_from_history.sh run     # 백업 + 재작성 + 검증 (★로컬만)
#   ./tools/strip_prompts_from_history.sh push    # 원격에 강제 반영 (★되돌릴 수 없는 지점)
#
set -euo pipefail

PROMPTS=(
  "docs/ROUTINE_PROMPT.md"
  "docs/ROUTINE_PROMPT_asmr.md"
  "docs/ROUTINE_PROMPT_novel.md"
  "docs/ROUTINE_PROMPT_scp.md"
)
# 지워졌는지 확인할 때 쓰는 지문 — 프롬프트 본문에만 나오는 문구
FINGERPRINTS=("RETENTION ARCHITECTURE" "콜드 오픈" "보여주지 않기")

ROOT="$(git rev-parse --show-toplevel)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${ROOT}/../autoSNS_backup-${STAMP}"

c_red() { printf '\033[31m%s\033[0m\n' "$*"; }
c_grn() { printf '\033[32m%s\033[0m\n' "$*"; }
c_ylw() { printf '\033[33m%s\033[0m\n' "$*"; }
die()   { c_red "✗ $*"; exit 1; }

# ─────────────────────────────────────────────────────────────
preflight() {
  echo "── 사전 점검 ──────────────────────────────────"
  cd "$ROOT"

  command -v git-filter-repo >/dev/null 2>&1 \
    || die "git-filter-repo 없음 →  pip install git-filter-repo"
  c_grn "✓ git-filter-repo"

  [ -z "$(git status --porcelain)" ] \
    || die "작업 트리가 깨끗하지 않다. 커밋하거나 stash 후 다시."
  c_grn "✓ 작업 트리 깨끗"

  local remote; remote="$(git remote get-url origin 2>/dev/null || echo '')"
  [ -n "$remote" ] || die "origin 원격이 없다."
  echo "  원격: $remote"

  # 지금 히스토리에 뭐가 있는지
  echo
  echo "  현재 히스토리:"
  printf "    커밋 %s개 · 브랜치(원격) %s개\n" \
    "$(git rev-list --all --count)" "$(git branch -r | grep -vc 'HEAD ->' || echo 0)"
  local hits=0
  for p in "${PROMPTS[@]}"; do
    local n; n="$(git log --all --oneline --name-only --pretty=format: -- "$p" 2>/dev/null | grep -c "$p" || true)"
    printf "    %-34s 커밋 %s개에 등장\n" "$p" "$n"
    hits=$((hits + n))
  done
  [ "$hits" -gt 0 ] || c_ylw "  (이미 히스토리에 없다 — 실행할 게 없을 수도)"

  echo
  c_ylw "⚠️ run 전에 반드시 처리할 것"
  echo "   1. 열려 있는 PR 을 전부 머지하거나 닫아라."
  echo "      (재작성하면 PR 의 커밋 SHA 가 전부 무효가 되어 이상하게 남는다)"
  echo "   2. 안 쓰는 원격 브랜치를 지워라 — 재작성 대상이 줄고 실수도 준다."
  echo "      git push origin --delete <branch>"
  echo "   3. 팀원이 이 레포를 클론해뒀다면 알려라. 재작성 후 pull 이 깨진다."
  echo "      (각자 다시 클론하는 게 제일 깔끔)"
  echo
  c_ylw "⚠️ 이 스크립트가 못 지우는 것 — 커밋 메시지"
  echo "   커밋 메시지 4건에 프롬프트 문구가 인용돼 있다(섹션 제목 수준)."
  echo "   본문 자체는 아니라 실질 유출은 아니지만, 완벽히 지우려면"
  echo "   filter-repo 의 --replace-message 를 추가로 써야 한다."
  echo
}

# ─────────────────────────────────────────────────────────────
do_backup() {
  echo "── 백업 ──────────────────────────────────────"
  [ -e "$BACKUP_DIR" ] && die "백업 경로가 이미 있다: $BACKUP_DIR"

  # ① 히스토리 통째 미러 (되돌리려면 이걸 쓴다)
  git clone --mirror "$ROOT" "${BACKUP_DIR}.git" >/dev/null 2>&1
  local n; n="$(git --git-dir="${BACKUP_DIR}.git" rev-list --all --count)"
  [ "$n" -gt 0 ] || die "백업 검증 실패(커밋 0개)"
  c_grn "✓ 미러 백업: ${BACKUP_DIR}.git (커밋 ${n}개)"

  # ② 프롬프트 원본 (지우기 전에 따로 빼둔다 — 사내 위키로 옮길 것)
  mkdir -p "${BACKUP_DIR}/prompts"
  for p in "${PROMPTS[@]}"; do
    [ -f "$ROOT/$p" ] && cp "$ROOT/$p" "${BACKUP_DIR}/prompts/" && echo "    보관: $p"
  done
  c_grn "✓ 프롬프트 원본: ${BACKUP_DIR}/prompts/"
  echo
  c_ylw "★ 이 두 경로를 지우지 마라. 되돌릴 유일한 수단이다."
  echo "   복구:  git push --force --mirror ${BACKUP_DIR}.git 의 원격으로"
  echo
}

# ─────────────────────────────────────────────────────────────
do_rewrite() {
  echo "── 히스토리 재작성 ────────────────────────────"
  cd "$ROOT"
  local before; before="$(git rev-list --all --count)"

  local args=()
  for p in "${PROMPTS[@]}"; do args+=(--path "$p"); done

  # --invert-paths = 지정한 경로'만' 제거. --force = 신선한 클론이 아니어도 진행.
  git filter-repo --force --invert-paths "${args[@]}"

  local after; after="$(git rev-list --all --count)"
  echo "  커밋 수: ${before} → ${after}"
  [ "$before" -ne "$after" ] && echo "    (프롬프트만 건드리던 커밋 $((before - after))개는 내용이 없어져 사라진다 — 정상)"
  c_grn "✓ 재작성 완료"
  echo
}

# ─────────────────────────────────────────────────────────────
do_verify() {
  echo "── 검증 ──────────────────────────────────────"
  cd "$ROOT"
  local fail=0

  # ① 경로가 히스토리 어디에도 없어야 한다
  for p in "${PROMPTS[@]}"; do
    local n; n="$(git log --all --oneline --name-only --pretty=format: -- "$p" 2>/dev/null | grep -c "$p" || true)"
    if [ "$n" -eq 0 ]; then c_grn "✓ 경로 제거됨: $p"
    else c_red "✗ 아직 남음($n건): $p"; fail=1; fi
  done

  # ② 내용(지문)이 ★프롬프트 파일에 남아있지 않아야 한다 — pickaxe 로 파일까지 짚는다.
  #    지문은 코드 주석("§E 보여주지 않기의 예외")이나 이 스크립트 자신에도 나온다.
  #    그건 개념 참조일 뿐 프롬프트 본문이 아니므로 실패로 치지 않고 어디에 있는지만 알린다.
  local SELF="tools/$(basename "$0")"
  for s in "${FINGERPRINTS[@]}"; do
    local files; files="$(git log --all -S"$s" --name-only --pretty=format: 2>/dev/null \
      | sort -u | grep -v '^$' | grep -vF "$SELF" || true)"
    if [ -z "$files" ]; then
      c_grn "✓ 내용 제거됨: \"$s\""
      continue
    fi
    local bad=""
    for p in "${PROMPTS[@]}"; do
      echo "$files" | grep -qF "$p" && bad="${bad} $p"
    done
    if [ -n "$bad" ]; then
      c_red "✗ 프롬프트 파일에 아직 남음: \"$s\" →$bad"; fail=1
    else
      c_ylw "· \"$s\" 는 다른 파일에도 있다(프롬프트 본문 아님 — 정상):"
      echo "$files" | sed 's/^/      /'
    fi
  done

  # ③ 시크릿이 새로 생기지 않았는지(공개 전 마지막 확인)
  local leak
  leak="$(git log --all -p --pretty=format: 2>/dev/null \
    | grep -aoE '(nvapi-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|EAA[A-Za-z0-9]{30,}|"refresh_token"[[:space:]]*:[[:space:]]*"[^"]{10,}|AIza[A-Za-z0-9_-]{20,})' \
    | sort -u | head -5 || true)"
  if [ -z "$leak" ]; then c_grn "✓ 히스토리에 자격증명 패턴 0건"
  else c_red "✗ 자격증명으로 보이는 문자열 발견 — 공개하지 마라:"; echo "$leak"; fail=1; fi

  echo
  [ "$fail" -eq 0 ] || die "검증 실패. push 하지 말 것. 백업으로 되돌려라."
  c_grn "✓ 검증 통과"
  echo
}

# ─────────────────────────────────────────────────────────────
do_push() {
  echo "── 원격 반영 (되돌릴 수 없는 지점) ─────────────"
  cd "$ROOT"

  git remote get-url origin >/dev/null 2>&1 \
    || die "origin 이 없다. filter-repo 가 지웠다 →  git remote add origin <URL>"

  echo "  원격: $(git remote get-url origin)"
  echo
  c_red "⚠️ 모든 브랜치·태그를 강제로 덮어쓴다. 백업 없이는 되돌릴 수 없다."
  printf "  계속하려면 정확히 'FORCE PUSH' 를 입력: "
  read -r ans
  [ "$ans" = "FORCE PUSH" ] || die "취소됨"

  git push --force --all origin
  git push --force --tags origin
  c_grn "✓ 강제 푸시 완료"
  echo
  c_ylw "다음 할 일 (docs/GO_PUBLIC.md 참조)"
  echo "   1. GitHub 웹에서 히스토리 확인 — 프롬프트가 안 보이는지"
  echo "   2. ★GitHub Support 에 GC 요청 (아래 §)"
  echo "   3. 그 다음에 public 전환"
  echo
}

# ─────────────────────────────────────────────────────────────
case "${1:-check}" in
  check) preflight ;;
  run)   preflight
         printf "\n계속하려면 'yes' 입력: "; read -r a; [ "$a" = "yes" ] || die "취소됨"
         do_backup; do_rewrite; do_verify
         c_grn "로컬 재작성 끝. 원격 반영은 →  $0 push" ;;
  push)  do_push ;;
  *)     die "사용법: $0 [check|run|push]" ;;
esac
