<#
.SYNOPSIS
  wbSpark(qwen-image) 썸네일 후보 생성 랩 — ★로컬 전용(사내망에서만 게이트웨이 접근 가능).

.DESCRIPTION
  대본 한줄요약(Hook)을 시각화한 썸네일 후보를 여러 스타일 프리셋으로 생성한다.
  - 내용(장면) = Hook 에서       : 그때그때 주제 반영(하드코딩 아님)
  - 스타일(아트 톤) = 프리셋에서  : 장르/주제에 맞게 선택(항상 다크 아님)
  - 제목 텍스트는 굽지 않음        : 후에 또렷한 폰트로 오버레이(안 깨짐)

  wangbyul.com 은 내부 IP(10.10.100.1)로 풀려 사내망에서만 호출됨 → 이 랩은 로컬 실행 전용.
  프로덕션(CI) 연결은 별도(게이트웨이 공개화 or 사내 러너 or 로컬 사전생성) 결정 필요.

.EXAMPLE
  # 장르만 주면 어울리는 스타일 자동 선택
  .\thumbnail_lab.ps1 -Hook "밤마다 붉은 실이 스스로 풀리는 한옥 삯바느질 가게" -Title "실타래 EP1" -Genre 공포

.EXAMPLE
  # 스타일 직접 지정 + 스타일당 2장
  .\thumbnail_lab.ps1 -Hook "폐허가 된 마법 학원에 홀로 남은 소녀" -Styles epicfantasy,lightnovel -Count 2

.EXAMPLE
  # 여러 후보를 넓게 비교(장르 미지정 → 기본 2종)
  .\thumbnail_lab.ps1 -Hook "비 내리는 밤 골목, 우산 든 두 사람"
#>
param(
  [Parameter(Mandatory=$true)][string]$Hook,      # 대본 한줄요약(장면 묘사) — 썸네일 내용의 핵심
  [string]$Title = "",                            # 파일명/참고용(이미지에는 굽지 않음)
  [ValidateSet("로맨스","판타지","잔혹동화","추리","공포","")][string]$Genre = "",
  [string[]]$Styles = @(),                        # 비우면 Genre 기반 자동 선택
  [int]$Count = 1,                                # 스타일당 생성 장수
  [string]$OutDir = "$env:USERPROFILE\Desktop\wbspark_lab",
  [int]$TimeoutMin = 12                           # 장당 최대 대기(생성이 5~10분 걸림)
)

$ErrorActionPreference = "Stop"
$b = "https://wangbyul.com/wbSpark"

# ── 스타일 프리셋(아트 아이스테틱). 톤은 여기서, 내용은 Hook 에서. ──
$PRESETS = @{
  darkfantasy = "dark fantasy anime key visual, moody atmospheric anime illustration, dramatic chiaroscuro cinematic lighting, ominous tense mood, highly detailed"
  lightnovel  = "Japanese light novel cover illustration, glossy vibrant anime art, soft rim lighting, character-forward, sparkling delicate details, bright appealing"
  webtoon     = "Korean webtoon style illustration, clean bold lineart, vivid saturated colors, crisp dramatic lighting, modern polished"
  ghibli      = "Studio Ghibli style soft painterly anime, warm whimsical storybook mood, gentle natural light, nostalgic cozy"
  epicfantasy = "epic fantasy anime concept art, luminous magical atmosphere, grand cinematic scale, vibrant glowing colors, highly detailed"
}

# ── 장르 → 어울리는 스타일 기본값(주제 맞춤 — 로맨스/판타지는 밝게, 공포/추리만 다크) ──
$GENRE_MAP = @{
  "로맨스"   = @("lightnovel","ghibli")
  "판타지"   = @("epicfantasy","lightnovel")
  "잔혹동화" = @("darkfantasy","ghibli")
  "추리"     = @("darkfantasy","webtoon")
  "공포"     = @("darkfantasy")
}

# 공통 기술 접미사(제목 안 굽게 no text — 오버레이로 처리)
$TECH = "16:9 wide cinematic composition, poster key art, highly detailed, no text, no letters, no watermark"

# 스타일 결정: 명시 없으면 장르 기반, 장르도 없으면 기본 2종
if (-not $Styles -or $Styles.Count -eq 0) {
  if ($Genre -and $GENRE_MAP.ContainsKey($Genre)) { $Styles = $GENRE_MAP[$Genre] }
  else { $Styles = @("darkfantasy","lightnovel") }
}
$Styles = @($Styles | Where-Object { $PRESETS.ContainsKey($_) })
if (-not $Styles) { throw "유효한 스타일 없음. 가능: $($PRESETS.Keys -join ', ')" }

New-Item -ItemType Directory -Force $OutDir | Out-Null
$slug = ($Title -replace '[^\w가-힣]','_')
if (-not $slug) { $slug = "thumb" }
$slug = $slug.Substring(0, [Math]::Min(40, $slug.Length))

function New-Thumb {
  param([string]$Prompt, [string]$OutFile)
  $body = @{ type = "image"; prompt = $Prompt } | ConvertTo-Json -Compress
  $id = (irm "$b/jobs" -Method Post -ContentType "application/json; charset=utf-8" -Body $body).job_id
  if (-not $id) { throw "job_id 없음(제출 실패)" }
  $sw = [Diagnostics.Stopwatch]::StartNew()
  do {
    Start-Sleep 4
    $r = irm "$b/jobs/$id"
    Write-Host ("    · {0,4}s  status={1}" -f [int]$sw.Elapsed.TotalSeconds, $r.status)
    if ($r.status -in @("error","failed")) { throw "생성 실패: $($r | ConvertTo-Json -Compress)" }
    if ($sw.Elapsed.TotalMinutes -ge $TimeoutMin) { throw "타임아웃(${TimeoutMin}분)" }
  } until ($r.status -eq "done")
  irm "$b/jobs/$id/file" -OutFile $OutFile
}

Write-Host "# 썸네일 후보 생성"
Write-Host "  Hook  : $Hook"
Write-Host "  Genre : $(if($Genre){$Genre}else{'(미지정)'})"
Write-Host "  스타일: $($Styles -join ', ')  · 스타일당 $Count 장"
Write-Host "  저장  : $OutDir`n"

$made = @()
foreach ($s in $Styles) {
  for ($n = 1; $n -le $Count; $n++) {
    $prompt = "$Hook. $($PRESETS[$s]), $TECH"
    $file = Join-Path $OutDir ("{0}_{1}_{2}.png" -f $slug, $s, $n)
    Write-Host "▶ [$s #$n] 생성 중… (최대 ${TimeoutMin}분)"
    try {
      New-Thumb -Prompt $prompt -OutFile $file
      Write-Host "  ✅ $file`n"
      $made += $file
    } catch {
      Write-Host "  ❌ 실패: $($_.Exception.Message)`n"
    }
  }
}

Write-Host "──── 완료: $($made.Count)장 ────"
$made | ForEach-Object { Write-Host "  $_" }
if ($made) { Invoke-Item $OutDir }
