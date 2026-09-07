@echo off
REM wbSpark 라우팅 점검 - cmd 에서 실행하거나 이 파일을 더블클릭.
REM   "no text" 접미사가 Qwen-Image(30GB)를 부르는지 확인한다.
REM   읽기 전용 - 서버 설정을 바꾸지 않는다.
REM
REM   사용:  check-wbspark-route.bat
REM          check-wbspark-route.bat --with-llm      (실제 경로도 함께)
REM          check-wbspark-route.bat --dry-run       (서버 안 부르고 확인만)

chcp 65001 1>NUL 2>NUL
setlocal
cd /d "%~dp0.."

set PYEXE=
where python 1>NUL 2>NUL && set PYEXE=python
if "%PYEXE%"=="" where py 1>NUL 2>NUL && set PYEXE=py
if "%PYEXE%"=="" (
  echo [!] python 을 찾을 수 없습니다. Python 3 를 설치하고 PATH 에 넣어주세요.
  goto :done
)

%PYEXE% tools\wbspark_route_check.py %*

:done
REM 더블클릭으로 열렸을 때만 창을 붙잡는다 (cmd 에서 실행하면 그냥 끝난다)
echo %cmdcmdline% | find /i "%~0" 1>NUL 2>NUL && pause
endlocal
