# Build Continuum Docker image locally
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$Tag = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "continuum:local" }

Write-Host "Building ${Tag} from ${Root}"
docker build -t $Tag .

Write-Host "Done. Run: .\infra\scripts\run-local.ps1"
