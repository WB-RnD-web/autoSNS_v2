#!/usr/bin/env bash
# 레포의 오프라인 테스트 전부(pipeline·tools·gumiho/tales·insta).
# 채널 맥박 PR(pulse.yml)이 PR 을 열기 전에 돌린다. 사람도 워크플로를 건드린 PR 전엔 이걸 돌린다(2026-10-01 #112 사고:
#   새 워크플로 하나가 test_ai_news 를 깨서 AI 소식 업로드가 하루 막혔다).
#   워크플로 전체 가드는 2026-10-24 부터 tools/test_workflows.py 에 있다(AI 소식을 접으며 test_ai_news 에서 옮김).
set -u
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
FAIL=0
LOG="$(mktemp)"
for t in $(ls pipeline/test_*.py tools/test_*.py gumiho/tales/test_*.py insta/test_*.py 2>/dev/null | sort); do
  if "$PY" "$t" > "$LOG" 2>&1; then
    echo "✅ $t"
  else
    echo "❌ $t"
    tail -25 "$LOG"
    FAIL=$((FAIL + 1))
  fi
done
rm -f "$LOG"
if [ "$FAIL" -ne 0 ]; then
  echo "❌ 실패 $FAIL개"
  exit 1
fi
echo "✅ 전부 통과"
