$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
Set-Location $Backend
if (-not (Test-Path .venv\Scripts\python.exe)) { throw "Chưa cài backend. Chạy scripts\install_backend.ps1 trước." }
if (-not (Test-Path .env)) { throw "Thiếu backend\.env. Copy .env.example thành .env và chỉnh cấu hình." }
& .\.venv\Scripts\python.exe app.py
