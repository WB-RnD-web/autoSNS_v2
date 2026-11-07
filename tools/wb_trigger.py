"""왕별이 표 트리거 — 옛 '실행 스위치' 루틴 4개가 돌리던 bash 를 코드로 옮긴 것(.github/workflows/wb-triggers.yml).

    python tools/wb_trigger.py <which> --env <파일> [--date YYYY-MM-DD]

which: fortune · pulli · theme · name_year · name_am · name_surname · name_pm
스토리보드를 레포 안 경로(FILE)에 만들고, 워크플로가 읽을 BRANCH·FILE·MSG·WHO 를 --env 파일에 쓴다.
그날 차례가 아니면(띠별 테마 쉬는 날 · 내 것 찾기 하루 한 칸 순환) FILE 을 비워 둔다 = 건너뜀.
"내 것 찾기" 칸은 cron 이 어느 줄로 깨웠는지로 정한다(루틴은 시각으로 골랐다 — Actions 는 cron 이 늦게 돌 수 있어서).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = dt.timezone(dt.timedelta(hours=9))

# which → (브랜치, 커밋 이름, 스크립트, 내 것 찾기 칸, 커밋 메시지) — 옛 루틴 프롬프트의 값 그대로
SPECS = {
    "fortune": ("routine/fortune", "fortune-routine", "pipeline/fortune_card.py", None, "chore: 오늘 스토리보드(코드) fortune {d}"),
    "pulli": ("routine/fortune_pulli", "pulli-trigger", "pipeline/pulli_card.py", None, "chore: 풀이형 표 {d}"),
    "theme": ("routine/fortune_theme", "theme-trigger", "pipeline/theme_card.py", None, "chore: 띠별 테마 순위 표 {d}"),
    "name_year": ("routine/fortune_name", "name-trigger", "pipeline/name_card.py", "year", "chore: 내 것 찾기 표 {d} {s}"),
    "name_am": ("routine/fortune_name", "name-trigger", "pipeline/name_card.py", "am", "chore: 내 것 찾기 표 {d} {s}"),
    "name_surname": ("routine/fortune_name", "name-trigger", "pipeline/name_card.py", "surname", "chore: 내 것 찾기 표 {d} {s}"),
    "name_pm": ("routine/fortune_name", "name-trigger", "pipeline/name_card.py", "pm", "chore: 내 것 찾기 표 {d} {s}"),
}


def _run(args: list[str]) -> str:
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"실패: {' '.join(args)}")
    return r.stdout.strip()


def make(which: str, day: str) -> dict:
    """스토리보드를 만들고 {BRANCH, FILE, MSG, WHO} — 그날 차례가 아니면 FILE=''."""
    branch, who, script, base_slot, msg = SPECS[which]
    slot = None
    extra: list[str] = []
    if base_slot:
        # pm 은 음력 끝자리 날 lunar 로 바뀐다(name_card.resolve_slot) — 그 판단은 스크립트에 맡긴다
        slot = _run([script, "slot", "--date", day, "--slot", base_slot]).splitlines()[-1].strip()
        extra = ["--slot", slot]
    path = _run([script, "path", "--date", day, *extra]).splitlines()[-1].strip()
    if os.path.isabs(path):                  # fortune·pulli 는 절대경로를 낸다 — 레포 기준으로 맞춘다
        path = os.path.relpath(path, ROOT)
    path = path.replace("\\", "/")
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        os.remove(full)                      # 남은 파일로 '만들었다'고 착각하지 않게
    out = _run([script, "make", "--date", day, *extra, "--out", path])
    print(out[-600:])
    made = os.path.exists(full)
    return {"BRANCH": branch, "FILE": path if made else "", "MSG": msg.format(d=day, s=slot or ""), "WHO": who}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=sorted(SPECS))
    ap.add_argument("--env", required=True)
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    day = a.date or dt.datetime.now(KST).strftime("%Y-%m-%d")
    res = make(a.which, day)
    with open(a.env, "w", encoding="utf-8") as f:
        for k, v in res.items():
            f.write(f"{k}={shlex.quote(v)}\n")
    print(f"{a.which} {day}: " + (f"{res['BRANCH']} ← {res['FILE']}" if res["FILE"] else "오늘은 차례가 아님 — 건너뜀"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
