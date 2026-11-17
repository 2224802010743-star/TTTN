$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
Set-Location $Backend
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Chưa tìm thấy Python Launcher. Cài Python 3.12 x64 và bật Add Python to PATH." }
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Đã tạo backend\.env. Hãy sửa secret và DATABASE_URL trước khi chạy." -ForegroundColor Yellow }
Write-Host "Cài xong. Xem README_VI.md để sửa .env và tạo database trước khi chạy." -ForegroundColor Green
