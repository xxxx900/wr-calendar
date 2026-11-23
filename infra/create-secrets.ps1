param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$secretNames = @(
    "OPENAI_API_KEY",
    "SUPABASE_ADMIN_URL",
    "SUPABASE_READONLY_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN"
)

if (-not (Test-Path $EnvFile)) {
    throw "Environment file not found: $EnvFile"
}

gcloud config set project $ProjectId | Out-Host

$values = @{}
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
        $values[$Matches[1]] = $Matches[2]
    }
}

$tempFiles = @()
try {
    foreach ($secretName in $secretNames) {
        if (-not $values.ContainsKey($secretName) -or [string]::IsNullOrWhiteSpace($values[$secretName])) {
            throw "Missing value for $secretName in $EnvFile"
        }

        $tempFile = Join-Path ([IO.Path]::GetTempPath()) ("wolf-ranch-$secretName-" + [guid]::NewGuid().ToString("N") + ".txt")
        [IO.File]::WriteAllText($tempFile, $values[$secretName], [Text.UTF8Encoding]::new($false))
        $tempFiles += $tempFile

        gcloud secrets describe $secretName --project $ProjectId *> $null
        if ($LASTEXITCODE -ne 0) {
            gcloud secrets create $secretName --replication-policy="automatic" --project $ProjectId
        }
        gcloud secrets versions add $secretName --data-file=$tempFile --project $ProjectId
    }
}
finally {
    foreach ($tempFile in $tempFiles) {
        Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Created or updated $($secretNames.Count) Secret Manager secrets in project $ProjectId."
Write-Host "LOCAL_DEVELOPMENT is intentionally not stored as a secret; Cloud Run sets it to false in service.yaml."
