@echo off
cd /d "C:\AI\Work_Folders\News_Macros\live_news_dashboard"
start "Teemo Live News" cmd /c "timeout /t 2 /nobreak >nul & start \"\" http://127.0.0.1:8765"
python live_news_dashboard.py --interval 30 --port 8765
pause
