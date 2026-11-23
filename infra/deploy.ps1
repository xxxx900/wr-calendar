param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$Repository = "calendar",
    [string]$Service = "wolf-ranch-calendar",
    [switch]$CreateSecrets
)

$ErrorActionPreference = "Stop"
$image = "$Region-docker.pkg.dev/$ProjectId/$Repository/calendar-api:latest"

gcloud config set project $ProjectId
if ($CreateSecrets) {
    & .\infra\create-secrets.ps1 -ProjectId $ProjectId
}
gcloud builds submit --tag $image .
(Get-Content .\infra\service.yaml -Raw) `
    -replace "REGION", $Region `
    -replace "PROJECT_ID", $ProjectId `
    | Set-Content .\infra\service.generated.yaml

gcloud run services replace .\infra\service.generated.yaml --region $Region
