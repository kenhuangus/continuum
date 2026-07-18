# Run Continuum via docker compose (local smoke)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

if (-not (Test-Path ".env")) {
    Write-Warning ".env not found — copy .env.example to .env first"
}

Write-Host "Starting Continuum on http://127.0.0.1:8000/"
docker compose up --build
