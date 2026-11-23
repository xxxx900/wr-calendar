<#
.SYNOPSIS
    Automated build, push, and deployment script for Wolf Ranch Community Calendar.
    Supports both Production and Test (UAT) environments.

.DESCRIPTION
    Builds Docker containers with the appropriate environment build arguments,
    pushes them to Google Artifact Registry, and deploys them to Google Cloud Run.
    Optionally synchronizes secrets to Google Cloud Secret Manager.

.PARAMETER Version
    The version tag for the Docker images (e.g., v8, v9, 1.0.0). Required for deployment.

.PARAMETER Environment
    Target deployment environment: 'prod' (default) or 'test'.

.PARAMETER Component
    Which service to deploy: 'all' (default), 'frontend', or 'backend'.

.PARAMETER SyncSecrets
    Switch to create or update Google Cloud Secret Manager secrets from the environment file (.env or .env.test).

.PARAMETER DryRun
    Switch to output the exact commands and configurations without executing them.

.PARAMETER ProjectId
    GCP Project ID. Defaults to 'api-key-project-466812'.

.PARAMETER Region
    GCP Region. Defaults to 'us-central1'.

.PARAMETER Repository
    Google Artifact Registry repository name. Defaults to 'community-repo'.

.PARAMETER EnvFile
    Explicit path to the environment file. Defaults to '.env' for prod and '.env.test' for test.

.EXAMPLE
    # Deploy test environment frontend and backend with version v9:
    .\deploy.ps1 -Environment test -Version v9

.EXAMPLE
    # Preview deployment commands for test backend without running them:
    .\deploy.ps1 -Environment test -Component backend -Version v9 -DryRun

.EXAMPLE
    # Sync test secrets from .env.test into GCP Secret Manager:
    .\deploy.ps1 -Environment test -SyncSecrets

.EXAMPLE
    # Deploy production frontend only:
    .\deploy.ps1 -Environment prod -Component frontend -Version v9
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Version,

    [ValidateSet("prod", "test")]
    [string]$Environment = "prod",

    [ValidateSet("all", "frontend", "backend")]
    [string]$Component = "all",

    [switch]$SyncSecrets,

    [switch]$DryRun,

    [string]$ProjectId = "api-key-project-466812",
    [string]$Region = "us-central1",
    [string]$Repository = "community-repo",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$message) {
    Write-Host "`n====> $message" -ForegroundColor Cyan
}

function Write-Success([string]$message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Warn([string]$message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Parse-EnvFile([string]$filePath) {
    $map = @{}
    if (Test-Path $filePath) {
        foreach ($line in Get-Content $filePath) {
            $trimmed = $line.Trim()
            if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
            if ($trimmed -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
                $k = $Matches[1]
                $v = $Matches[2].Trim()
                if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                    $v = $v.Substring(1, $v.Length - 2)
                }
                $map[$k] = $v
            }
        }
    }
    return $map
}

function Invoke-CliCommand([string]$tool, [string[]]$cmdArgs) {
    Write-Host "`n> $tool $($cmdArgs -join ' ')" -ForegroundColor DarkGray
    if ($DryRun) {
        Write-Host "  (DRY-RUN) Would execute: $tool $($cmdArgs -join ' ')" -ForegroundColor Yellow
    } else {
        & $tool $cmdArgs
        if ($LASTEXITCODE -ne 0) {
            throw "$tool failed with exit code $LASTEXITCODE"
        }
    }
}

# --- Resolve Environment File ---
if (-not $EnvFile) {
    $EnvFile = if ($Environment -eq "test") { ".env.test" } else { ".env" }
}

$envMap = Parse-EnvFile -filePath $EnvFile

if (-not (Test-Path $EnvFile) -and $Environment -eq "test" -and -not $DryRun) {
    Write-Warn "Test environment file '$EnvFile' not found!"
    Write-Warn "Consider creating '$EnvFile' from '.env.test.example' to define test URLs and secrets."
}

# --- Service & Sizing Configuration ---
$isTest = ($Environment -eq "test")
$frontendService = if ($isTest) { "calendar-frontend-test" } else { "calendar-frontend" }
$backendService  = if ($isTest) { "calendar-backend-test" } else { "calendar-backend" }
$maxInstances    = if ($isTest) { "2" } else { "3" }

$imageTagSuffix = if ($isTest) { "-test" } else { "" }
$frontendImage  = "$Region-docker.pkg.dev/$ProjectId/$Repository/frontend:${Version}$imageTagSuffix"
$backendImage   = "$Region-docker.pkg.dev/$ProjectId/$Repository/backend:${Version}$imageTagSuffix"

# Default Production Fallbacks
$defaultProdApiUrl    = "https://calendar-backend-997634076075.us-central1.run.app"
$defaultProdAppUrl    = "https://calendar-frontend-997634076075.us-central1.run.app"
$defaultProdSupaUrl   = "https://gndnixpetxzuymlliyow.supabase.co"
$defaultProdSupaAnon  = "sb_publishable_DtxiUj_TcChey_OhKpk2kQ_fCrFKZkB"

# Resolved Frontend Build Args
$nextPublicApiUrl     = if ($envMap.ContainsKey("NEXT_PUBLIC_API_URL")) { $envMap["NEXT_PUBLIC_API_URL"] } elseif ($isTest) { "https://calendar-backend-test-997634076075.us-central1.run.app" } else { $defaultProdApiUrl }
$nextPublicAppUrl     = if ($envMap.ContainsKey("NEXT_PUBLIC_APP_URL")) { $envMap["NEXT_PUBLIC_APP_URL"] } elseif ($isTest) { "https://calendar-frontend-test-997634076075.us-central1.run.app" } else { $defaultProdAppUrl }
$nextPublicSupaUrl    = if ($envMap.ContainsKey("NEXT_PUBLIC_SUPABASE_URL")) { $envMap["NEXT_PUBLIC_SUPABASE_URL"] } else { $defaultProdSupaUrl }
$nextPublicSupaAnon   = if ($envMap.ContainsKey("NEXT_PUBLIC_SUPABASE_ANON_KEY")) { $envMap["NEXT_PUBLIC_SUPABASE_ANON_KEY"] } else { $defaultProdSupaAnon }

# Resolved Backend Environment Variables
$frontendOrigin       = if ($envMap.ContainsKey("FRONTEND_ORIGIN")) { $envMap["FRONTEND_ORIGIN"] } else { $nextPublicAppUrl }

# --- Secret Synchronization Logic ---
if ($SyncSecrets) {
    Write-Step "Synchronizing Secrets to GCP Secret Manager for Environment: $Environment ($ProjectId)"
    if (-not (Test-Path $EnvFile)) {
        throw "Cannot sync secrets: Environment file '$EnvFile' does not exist."
    }

    $secretsToSync = @(
        "SUPABASE_URL",
        "SUPABASE_ADMIN_URL",
        "SUPABASE_READONLY_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN"
    )

    if ($envMap.ContainsKey("OPENAI_API_KEY") -and [string]::IsNullOrWhiteSpace($envMap["OPENAI_API_KEY"]) -eq $false) {
        $secretsToSync += "OPENAI_API_KEY"
    }

    foreach ($key in $secretsToSync) {
        if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
            Write-Warn "Skipping '$key': Key missing or empty in $EnvFile"
            continue
        }

        $secretGcpName = if ($isTest) { "${key}_TEST" } else { $key }
        $secretVal = $envMap[$key]

        Write-Host "  -> Syncing $secretGcpName from $key..." -ForegroundColor Cyan
        if ($DryRun) {
            Write-Host "     (DRY-RUN) Would update secret $secretGcpName in $ProjectId" -ForegroundColor Yellow
        } else {
            gcloud secrets describe $secretGcpName --project $ProjectId *> $null
            if ($LASTEXITCODE -ne 0) {
                gcloud secrets create $secretGcpName --replication-policy="automatic" --project $ProjectId
            }
            $tempFile = Join-Path ([IO.Path]::GetTempPath()) ("gcp-secret-" + [guid]::NewGuid().ToString("N") + ".txt")
            try {
                [IO.File]::WriteAllText($tempFile, $secretVal, [Text.UTF8Encoding]::new($false))
                gcloud secrets versions add $secretGcpName --data-file=$tempFile --project $ProjectId | Out-Null
            } finally {
                Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
            }
            Write-Success "Secret $secretGcpName updated."
        }
    }
    Write-Success "Secret synchronization completed."

    # If Version is not supplied and user only called -SyncSecrets, exit cleanly
    if (-not $Version) {
        Write-Host "`nNo -Version provided. Completed secret synchronization only." -ForegroundColor Green
        exit 0
    }
}

# Ensure Version is provided for building/deploying
if (-not $Version) {
    Write-Host "Error: -Version parameter is required (e.g. -Version v9)" -ForegroundColor Red
    exit 1
}

Write-Step "Starting Deployment Pipeline"
Write-Host "  Environment  : $Environment"
Write-Host "  Version Tag  : $Version"
Write-Host "  Component    : $Component"
Write-Host "  GCP Project  : $ProjectId"
Write-Host "  Region       : $Region"
Write-Host "  Dry Run Mode : $DryRun"

# ==============================================================================
# 1. FRONTEND BUILD & DEPLOY
# ==============================================================================
if ($Component -in @("all", "frontend")) {
    Write-Step "Building Frontend Docker Image: $frontendImage"
    Write-Host "  NEXT_PUBLIC_API_URL           = $nextPublicApiUrl"
    Write-Host "  NEXT_PUBLIC_APP_URL           = $nextPublicAppUrl"
    Write-Host "  NEXT_PUBLIC_SUPABASE_URL      = $nextPublicSupaUrl"
    $maskedKey = if ($nextPublicSupaAnon.Length -gt 6) { "***" + $nextPublicSupaAnon.Substring($nextPublicSupaAnon.Length - 6) } else { "***" }
    Write-Host "  NEXT_PUBLIC_SUPABASE_ANON_KEY = $maskedKey"

    $dockerBuildFrontendArgs = @(
        "build",
        "--build-arg", "NEXT_PUBLIC_API_URL=$nextPublicApiUrl",
        "--build-arg", "NEXT_PUBLIC_APP_URL=$nextPublicAppUrl",
        "--build-arg", "NEXT_PUBLIC_SUPABASE_URL=$nextPublicSupaUrl",
        "--build-arg", "NEXT_PUBLIC_SUPABASE_ANON_KEY=$nextPublicSupaAnon",
        "-t", $frontendImage,
        "frontend"
    )
    Invoke-CliCommand "docker" $dockerBuildFrontendArgs

    Write-Step "Pushing Frontend Docker Image: $frontendImage"
    Invoke-CliCommand "docker" @("push", $frontendImage)

    Write-Step "Deploying to Cloud Run: $frontendService"
    $gcloudDeployFrontendArgs = @(
        "run", "deploy", $frontendService,
        "--project=$ProjectId",
        "--image=$frontendImage",
        "--region=$Region",
        "--allow-unauthenticated",
        "--min-instances=0",
        "--max-instances=$maxInstances",
        "--memory=1Gi",
        "--cpu=1"
    )
    Invoke-CliCommand "gcloud" $gcloudDeployFrontendArgs
    Write-Success "Frontend deployed successfully to $frontendService!"
}

# ==============================================================================
# 2. BACKEND BUILD & DEPLOY
# ==============================================================================
if ($Component -in @("all", "backend")) {
    Write-Step "Building Backend Docker Image: $backendImage"
    Invoke-CliCommand "docker" @("build", "-t", $backendImage, ".")

    Write-Step "Pushing Backend Docker Image: $backendImage"
    Invoke-CliCommand "docker" @("push", $backendImage)

    # Construct Cloud Run Secret Bindings
    if ($isTest) {
        $openAiSecret = "OPENAI_API_KEY=OPENAI_API_KEY:latest"
        if (-not $DryRun) {
            gcloud secrets describe OPENAI_API_KEY_TEST --project $ProjectId *> $null
            if ($LASTEXITCODE -eq 0) {
                $openAiSecret = "OPENAI_API_KEY=OPENAI_API_KEY_TEST:latest"
            }
        }

        $secretsString = "$openAiSecret," +
            "SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY_TEST:latest," +
            "SUPABASE_READONLY_URL=SUPABASE_READONLY_URL_TEST:latest," +
            "UPSTASH_REDIS_REST_URL=UPSTASH_REDIS_REST_URL_TEST:latest," +
            "UPSTASH_REDIS_REST_TOKEN=UPSTASH_REDIS_REST_TOKEN_TEST:latest," +
            "SUPABASE_JWT_SECRET=SUPABASE_JWT_SECRET_TEST:latest," +
            "SUPABASE_ADMIN_URL=SUPABASE_ADMIN_URL_TEST:latest," +
            "SUPABASE_URL=SUPABASE_URL_TEST:latest"
    } else {
        $secretsString = "OPENAI_API_KEY=OPENAI_API_KEY:latest," +
            "SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest," +
            "SUPABASE_READONLY_URL=SUPABASE_READONLY_URL:latest," +
            "UPSTASH_REDIS_REST_URL=UPSTASH_REDIS_REST_URL:latest," +
            "UPSTASH_REDIS_REST_TOKEN=UPSTASH_REDIS_REST_TOKEN:latest," +
            "SUPABASE_JWT_SECRET=SUPABASE_JWT_SECRET:latest," +
            "SUPABASE_ADMIN_URL=SUPABASE_ADMIN_URL:latest," +
            "SUPABASE_URL=SUPABASE_URL:latest"
    }

    Write-Step "Deploying to Cloud Run: $backendService"
    Write-Host "  FRONTEND_ORIGIN = $frontendOrigin"
    Write-Host "  Secrets Bound   = $secretsString"

    $gcloudDeployBackendArgs = @(
        "run", "deploy", $backendService,
        "--project=$ProjectId",
        "--image=$backendImage",
        "--region=$Region",
        "--allow-unauthenticated",
        "--min-instances=0",
        "--max-instances=$maxInstances",
        "--memory=1Gi",
        "--cpu=1",
        "--timeout=600",
        "--set-env-vars=FRONTEND_ORIGIN=$frontendOrigin",
        "--set-secrets=$secretsString"
    )
    Invoke-CliCommand "gcloud" $gcloudDeployBackendArgs
    Write-Success "Backend deployed successfully to $backendService!"
}

Write-Step "Deployment pipeline finished successfully!"
