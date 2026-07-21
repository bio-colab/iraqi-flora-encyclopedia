@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   موسوعة الفلورا العراقية
echo   Iraqi Flora Encyclopedia — Frontend
echo  ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo [خطأ] Python غير موجود في PATH.
    echo ثبّت Python 3.10+ من https://www.python.org/
    pause
    exit /b 1
  )
  set "PY=py -3"
) else (
  set "PY=python"
)

echo تشغيل الواجهة على http://127.0.0.1:8765/
echo اضغط Ctrl+C لإيقاف الخادم.
echo.

%PY% tools\web_server.py --host 127.0.0.1 --port 8765
if errorlevel 1 (
  echo.
  echo فشل تشغيل الخادم.
  pause
  exit /b 1
)

endlocal
