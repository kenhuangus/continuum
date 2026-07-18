# Smoke test: GET /v1/health
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:CONTINUUM_URL) { $env:CONTINUUM_URL } else { "http://127.0.0.1:8000" }
$Url = "$BaseUrl/v1/health"

Write-Host "GET $Url"
$response = Invoke-WebRequest -Uri $Url -UseBasicParsing
Write-Host "Status: $($response.StatusCode)"
Write-Host $response.Content

if ($response.StatusCode -ne 200) {
    exit 1
}
