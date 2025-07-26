@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python -X utf8 server.py