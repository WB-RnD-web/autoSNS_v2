"""왕별이 표 트리거 — 옛 '실행 스위치' 루틴 4개가 돌리던 bash 를 코드로 옮긴 것(.github/workflows/wb-triggers.yml).

    python tools/wb_trigger.py <which> --env <파일> [--date YYYY-MM-DD]

which: fortune · pulli · theme · name_year · name_am · name_surname · name_pm · wisdom
스토리보드를 레포 안 경로(FILE)에 만들고, 워크플로가 읽을 BRANCH·FILE·MSG·WHO 를 --env 파일에 쓴다.
그날 차례가 아니면(띠별 테마 쉬는 날 · 내 것 찾기 하루 한 칸 순환) FILE 을 비워 둔다 = 건너뜀.
"내 것 찾기" 칸은 cron 이 어느 줄로 깨웠는지로 정한다(루틴은 시각으로 골랐다 — Actions 는 cron 이 늦게 돌 수 있어서).

★2026-11-18 미리 만들고 예약 공개:
  GitHub 예약이 6~10시간씩 늦게 돌아 표가 새벽(01~04시)에 올라갔다(11/17 말년 지혜 03:57 · 11/18 내 것 찾기 01:32).
  이제 cron 은 공개 시각(SLOT_KST)보다 LEAD_H 시간 먼저 깨운다. 어느 편인지는 '지금'이 아니라
  '깨운 cron 이 맡은 공개 시각'으로 정한다(target) — 늦게 돌아도 날짜가 하루 밀리지 않는다.
  스토리보드에 publish_at(그 편의 공개 시각, KST)을 적고, run_pipeline 이 그 시각이 아직 안 왔으면
  비공개 + 예약 공개로 올린다(이미 지났으면 바로 공개 — 예전과 같다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
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
    # 2026-11-15 말년 지혜 표(11/17~11/30 2주 시험 · 17:40) — 운세 표에 더해 하루 한 편. 편이 없는 날은 make 가 안 쓴다 = 건너뜀
    "wisdom": ("routine/wisdom", "wisdom-trigger", "pipeline/wisdom_card.py", None, "chore: 말년 지혜 표 {d}"),
}


# 공개 시각(KST) — 예전 cron 시각 그대로. wb-triggers.yml 의 cron 은 이보다 LEAD_H 시간 먼저다(테스트가 맞춰 본다).
SLOT_KST = {"fortune": "06:00", "name_year": "07:40", "name_am": "09:40", "pulli": "10:40", "theme": "12:00",
            "name_surname": "13:40", "name_pm": "15:40", "wisdom": "17:40"}
LEAD_H = 12              # 11/16~11/18 실측 지연 최대 약 10시간 — 그보다 넉넉히


def slot_dt(which: str, day: dt.date) -> dt.datetime:
    hh, mm = (int(x) for x in SLOT_KST[which].split(":"))
    return dt.datetime.combine(day, dt.time(hh, mm), KST)


def target(which: str, now: dt.datetime) -> dt.datetime:
    """이 실행이 맡은 공개 시각 = '공개 시각 − LEAD_H' 가 이미 지난 것 중 가장 늦은 것.
    cron 은 공개 LEAD_H 시간 전에 깨우므로, 제때 돌면 그 편 · 몇 시간 늦게 돌아도 같은 편(날짜가 안 밀린다)."""
    now = now.astimezone(KST)
    cands = [slot_dt(which, now.date() + dt.timedelta(days=k)) for k in (-1, 0, 1)]
    return max(s for s in cands if s - dt.timedelta(hours=LEAD_H) <= now)


def stamp(path: str, publish_at: dt.datetime) -> None:
    """만든 스토리보드에 공개 시각을 적는다(run_pipeline.publish_at_for 가 읽는다)."""
    with open(path, encoding="utf-8") as f:
        sb = json.load(f)
    sb["publish_at"] = publish_at.astimezone(KST).isoformat(timespec="minutes")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sb, f, ensure_ascii=False, indent=1)


def _run(args: list[str]) -> str:
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"실패: {' '.join(args)}")
    return r.stdout.strip()


def make(which: str, day: str, publish_at: dt.datetime | None = None) -> dict:
    """스토리보드를 만들고 {BRANCH, FILE, MSG, WHO} — 그날 차례가 아니면 FILE=''. publish_at 이 있으면 파일에 적는다."""
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
    if made and publish_at is not None:
        stamp(full, publish_at)
    m = msg.format(d=day, s=slot or "") + (f" · 공개 {publish_at.astimezone(KST):%m/%d %H:%M}" if publish_at else "")
    return {"BRANCH": branch, "FILE": path if made else "", "MSG": m, "WHO": who}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=sorted(SPECS))
    ap.add_argument("--env", required=True)
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    if a.date:                                   # 손으로 날짜를 주면 그날 공개 시각(이미 지났으면 바로 공개)
        when = slot_dt(a.which, dt.date.fromisoformat(a.date))
    else:
        when = target(a.which, dt.datetime.now(KST))
    day = when.strftime("%Y-%m-%d")
    print(f"{a.which}: 공개 {when:%Y-%m-%d %H:%M} KST 편을 만든다(지금 {dt.datetime.now(KST):%m-%d %H:%M})")
    res = make(a.which, day, when)
    with open(a.env, "w", encoding="utf-8") as f:
        for k, v in res.items():
            f.write(f"{k}={shlex.quote(v)}\n")
    print(f"{a.which} {day}: " + (f"{res['BRANCH']} ← {res['FILE']}" if res["FILE"] else "오늘은 차례가 아님 — 건너뜀"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
