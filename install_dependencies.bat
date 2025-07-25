@echo off
echo Installing database dependencies...
echo.

echo Installing pymssql...
pip install pymssql==2.2.7

echo.
echo Dependencies installed successfully!
echo.
echo You can now run:
echo   python update_listings_pymssql.py test
echo   python update_listings_pymssql.py
pause 