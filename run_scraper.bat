@echo off
echo ==========================================
echo     Foxtons Scraper - Full Pipeline
echo ==========================================
echo.

echo [1/3] Starting Initial URL Collection...
echo ==========================================
@REM python initial_urls_collection.py
if %errorlevel% neq 0 (
    echo ERROR: Initial URL collection failed!
    pause
    exit /b %errorlevel%
)
echo Initial URL collection completed successfully!
echo.

echo [2/3] Starting Secondary URL Collection...
echo ==========================================
@REM python secondary_urls_collection.py
if %errorlevel% neq 0 (
    echo ERROR: Secondary URL collection failed!
    pause
    exit /b %errorlevel%
)
echo Secondary URL collection completed successfully!
echo.

echo [3/3] Starting Listing Details Extraction...
echo ==========================================
python listing_details.py
if %errorlevel% neq 0 (
    echo ERROR: Listing details extraction failed!
    pause
    exit /b %errorlevel%
)
echo Listing details extraction completed successfully!
echo.

echo ==========================================
echo     All scripts completed successfully!
echo ==========================================
echo.
pause 