@echo off
REM ─────────────────────────────────────────────────────────────
REM  Windows CMD 에서 바로 쓰기 위한 래퍼.
REM  cmd.exe 는 .sh 를 실행하지 못한다 — Git for Windows 의 bash 를 찾아서 넘긴다.
REM
REM  사용:
REM    tools\strip_prompts_from_history.cmd check
REM    tools\strip_prompts_from_history.cmd run
REM    tools\strip_prompts_from_history.cmd push
REM ─────────────────────────────────────────────────────────────
setlocal

set "SH=%~dp0strip_prompts_from_history.sh"
if not exist "%SH%" (
  echo [error] 스크립트를 찾을 수 없습니다: %SH%
  exit /b 1
)

REM bash 찾기 — PATH 우선, 없으면 Git for Windows 기본 설치 경로
set "BASH="
for %%B in (bash.exe) do if not defined BASH set "BASH=%%~$PATH:B"
if not defined BASH if exist "%ProgramFiles%\Git\bin\bash.exe"      set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles%\Git\usr\bin\bash.exe"  set "BASH=%ProgramFiles%\Git\usr\bin\bash.exe"
if not defined BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined BASH if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not defined BASH (
  echo [error] bash 를 찾을 수 없습니다.
  echo         Git for Windows 가 설치돼 있어야 합니다: https://git-scm.com/download/win
  echo         또는 시작메뉴에서 "Git Bash" 를 열고 아래를 직접 실행하세요:
  echo             ./tools/strip_prompts_from_history.sh %1
  exit /b 1
)

echo [i] bash: %BASH%
"%BASH%" "%SH%" %1
exit /b %ERRORLEVEL%
