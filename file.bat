@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo  ============================================
echo   موسوعة الفلورا العراقية
echo   Iraqi Flora Encyclopedia — PHP/Hostinger Runtime
echo  ============================================
echo.

where php >nul 2>&1
if errorlevel 1 (
  echo [خطأ] PHP غير موجود في PATH.
  echo ثبّت PHP 8.1+ أو شغّل المشروع على Hostinger/Apache.
  pause
  exit /b 1
)

echo تشغيل الواجهة على http://127.0.0.1:8765/
echo اضغط Ctrl+C لإيقاف الخادم.
echo.

php -S 127.0.0.1:8765 router.php
if errorlevel 1 (
  echo.
  echo فشل تشغيل خادم PHP.
  pause
  exit /b 1
)

endlocal
