# Tag and push continuum:local to Alibaba Container Registry.
# Set env vars before running (no secrets in this script):
#   $env:REGISTRY, $env:NAMESPACE, $env:REGION, $env:TAG (optional)
param(
    [string]$Registry = $env:REGISTRY,
    [string]$Namespace = $env:NAMESPACE,
    [string]$Region = $(if ($env:REGION) { $env:REGION } else { "ap-southeast-1" }),
    [string]$Image = $(if ($env:IMAGE) { $env:IMAGE } else { "continuum" }),
    [string]$Tag = $(if ($env:TAG) { $env:TAG } else { "latest" }),
    [string]$LocalTag = $(if ($env:LOCAL_TAG) { $env:LOCAL_TAG } else { "continuum:local" })
)

if (-not $Registry) { throw "Set REGISTRY env var or -Registry" }
if (-not $Namespace) { throw "Set NAMESPACE env var or -Namespace" }

$Remote = "${Registry}.${Region}.cr.aliyuncs.com/${Namespace}/${Image}:${Tag}"

Write-Host "Tagging ${LocalTag} -> ${Remote}"
docker tag $LocalTag $Remote

Write-Host "Pushing ${Remote}"
docker push $Remote

Write-Host "Done. Pull on ECS with:"
Write-Host "  docker pull ${Remote}"
