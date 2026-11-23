# Starts the local Docker stack. The frontend build needs a dev admin token baked in.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

$env:LOCAL_DEV_TOKEN = (& $python (Join-Path $PSScriptRoot "dev_token.py") admin --days 365).Trim()
if (-not $env:LOCAL_DEV_TOKEN) { throw "dev_token.py printed no token" }

Set-Location $root
docker compose up --build @args
