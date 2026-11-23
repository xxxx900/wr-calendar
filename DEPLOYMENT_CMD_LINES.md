# Wolf Ranch Calendar Deployment Guide

This guide covers building Docker containers, pushing images to Google Artifact Registry, and deploying to Google Cloud Run for both **Production** and **Test (UAT)** environments.

---

## 1. Automated Deployment Script (`deploy.ps1`)

Use [`deploy.ps1`](file:///C:/Users/jbk37/Projects/project_WR/deploy.ps1) to automate Docker builds, image pushes, and Cloud Run deployments.

### Quick Start Examples

```powershell
# Preview deployment commands (safe dry run)
.\deploy.ps1 -Environment test -Version v9 -DryRun

# Deploy both Frontend & Backend to Test (UAT)
.\deploy.ps1 -Environment test -Version v9

# Deploy both Frontend & Backend to Production
.\deploy.ps1 -Environment prod -Version v9

# Deploy Frontend only to Test
.\deploy.ps1 -Environment test -Component frontend -Version v9

# Deploy Backend only to Production
.\deploy.ps1 -Environment prod -Component backend -Version v9

# Sync Test secrets from .env.test into GCP Secret Manager (_TEST suffix)
.\deploy.ps1 -Environment test -SyncSecrets

# Sync Production secrets from .env into GCP Secret Manager
.\deploy.ps1 -Environment prod -SyncSecrets
```

### Script Parameter Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `-Version` | `string` | *(Required)* | Version tag for Docker images (e.g. `v9`, `1.0.0`). |
| `-Environment` | `"prod"` \| `"test"` | `"prod"` | Target environment. |
| `-Component` | `"all"` \| `"frontend"` \| `"backend"` | `"all"` | Which component to build and deploy. |
| `-SyncSecrets` | `switch` | `false` | Synchronizes `.env` or `.env.test` secrets to GCP Secret Manager. |
| `-DryRun` | `switch` | `false` | Prints all generated commands without executing them. |
| `-ProjectId` | `string` | `api-key-project-466812` | Google Cloud project ID. |
| `-Region` | `string` | `us-central1` | Google Cloud region. |
| `-Repository` | `string` | `community-repo` | Artifact Registry repository name. |

---

## 2. Environments & Configurations

### Production Environment (`-Environment prod`)
* **Frontend Service**: `calendar-frontend`
* **Frontend Image**: `us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:<version>`
* **Frontend URLs**:
  - App: `https://calendar-frontend-997634076075.us-central1.run.app`
  - API: `https://calendar-backend-997634076075.us-central1.run.app`
* **Backend Service**: `calendar-backend`
* **Backend Image**: `us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:<version>`
* **Secrets Used**: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_ADMIN_URL`, `SUPABASE_READONLY_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`.

### Test (UAT) Environment (`-Environment test`)
* **Configuration File**: [`.env.test`](file:///C:/Users/jbk37/Projects/project_WR/.env.test) (copy from [`.env.test.example`](file:///C:/Users/jbk37/Projects/project_WR/.env.test.example)).
* **Frontend Service**: `calendar-frontend-test`
* **Frontend Image**: `us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:<version>-test`
* **Frontend URLs**:
  - App: `https://calendar-frontend-test-997634076075.us-central1.run.app`
  - API: `https://calendar-backend-test-997634076075.us-central1.run.app`
* **Backend Service**: `calendar-backend-test`
* **Backend Image**: `us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:<version>-test`
* **Secrets Used**: `SUPABASE_URL_TEST`, `SUPABASE_ADMIN_URL_TEST`, `SUPABASE_READONLY_URL_TEST`, `SUPABASE_SERVICE_ROLE_KEY_TEST`, `SUPABASE_JWT_SECRET_TEST`, `UPSTASH_REDIS_REST_URL_TEST`, `UPSTASH_REDIS_REST_TOKEN_TEST`, `OPENAI_API_KEY_TEST` (or falls back to `OPENAI_API_KEY`).

---

## 3. Manual Raw Commands Reference

If executing commands manually in PowerShell:

### Production Deployment

#### Frontend
```powershell
docker build `
  --build-arg NEXT_PUBLIC_API_URL=https://calendar-backend-997634076075.us-central1.run.app `
  --build-arg NEXT_PUBLIC_APP_URL=https://calendar-frontend-997634076075.us-central1.run.app `
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://gndnixpetxzuymlliyow.supabase.co `
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_DtxiUj_TcChey_OhKpk2kQ_fCrFKZkB `
  -t us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8 `
  frontend;

docker push us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8;

gcloud run deploy calendar-frontend `
  --project=api-key-project-466812 `
  --image=us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8 `
  --region=us-central1 `
  --allow-unauthenticated `
  --min-instances=0 `
  --max-instances=3 `
  --memory=1Gi `
  --cpu=1
```

#### Backend
```powershell
docker build -t us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8 .;

docker push us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8;

gcloud run deploy calendar-backend `
  --project=api-key-project-466812 `
  --image=us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8 `
  --region=us-central1 `
  --allow-unauthenticated `
  --min-instances=0 `
  --max-instances=3 `
  --memory=1Gi `
  --cpu=1 `
  --timeout=600 `
  --set-env-vars="FRONTEND_ORIGIN=https://calendar-frontend-997634076075.us-central1.run.app" `
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest,SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,SUPABASE_READONLY_URL=SUPABASE_READONLY_URL:latest,UPSTASH_REDIS_REST_URL=UPSTASH_REDIS_REST_URL:latest,UPSTASH_REDIS_REST_TOKEN=UPSTASH_REDIS_REST_TOKEN:latest,SUPABASE_JWT_SECRET=SUPABASE_JWT_SECRET:latest,SUPABASE_ADMIN_URL=SUPABASE_ADMIN_URL:latest,SUPABASE_URL=SUPABASE_URL:latest"
```

### Test (UAT) Deployment

#### Frontend
```powershell
docker build `
  --build-arg NEXT_PUBLIC_API_URL=https://calendar-backend-test-997634076075.us-central1.run.app `
  --build-arg NEXT_PUBLIC_APP_URL=https://calendar-frontend-test-997634076075.us-central1.run.app `
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://<test-ref>.supabase.co `
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=<test-anon-key> `
  -t us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8-test `
  frontend;

docker push us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8-test;

gcloud run deploy calendar-frontend-test `
  --project=api-key-project-466812 `
  --image=us-central1-docker.pkg.dev/api-key-project-466812/community-repo/frontend:v8-test `
  --region=us-central1 `
  --allow-unauthenticated `
  --min-instances=0 `
  --max-instances=2 `
  --memory=1Gi `
  --cpu=1
```

#### Backend
```powershell
docker build -t us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8-test .;

docker push us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8-test;

gcloud run deploy calendar-backend-test `
  --project=api-key-project-466812 `
  --image=us-central1-docker.pkg.dev/api-key-project-466812/community-repo/backend:v8-test `
  --region=us-central1 `
  --allow-unauthenticated `
  --min-instances=0 `
  --max-instances=2 `
  --memory=1Gi `
  --cpu=1 `
  --timeout=600 `
  --set-env-vars="FRONTEND_ORIGIN=https://calendar-frontend-test-997634076075.us-central1.run.app" `
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest,SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY_TEST:latest,SUPABASE_READONLY_URL=SUPABASE_READONLY_URL_TEST:latest,UPSTASH_REDIS_REST_URL=UPSTASH_REDIS_REST_URL_TEST:latest,UPSTASH_REDIS_REST_TOKEN=UPSTASH_REDIS_REST_TOKEN_TEST:latest,SUPABASE_JWT_SECRET=SUPABASE_JWT_SECRET_TEST:latest,SUPABASE_ADMIN_URL=SUPABASE_ADMIN_URL_TEST:latest,SUPABASE_URL=SUPABASE_URL_TEST:latest"
```
