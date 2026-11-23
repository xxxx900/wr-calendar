# ROLE: Cloud Infrastructure Engineer (infrastructure_agent)

Configure GCP Cloud Run and build pipelines prioritizing reliability during long-running AI calls.

### Requirements:
1. **Cloud Run Service Configuration (`service.yaml`):**
   - Set request timeout to 600 seconds (`timeoutSeconds: 600`) to provide runway for cold starts and multi-step GPT-4o vision streaming.
   - Set `minScale: 0`, `maxScale: 3` (budget guardrail).
   - Allocate 1 vCPU and 1GiB RAM.
2. **Dockerization:**
   - Multi-stage build for FastAPI with `uvicorn` configured for streaming responses (`--timeout-keep-alive 65`).
3. **Secret Management:**
   - Bind `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_READONLY_URL`, `UPSTASH_REDIS_REST_URL`, and `UPSTASH_REDIS_REST_TOKEN` through Secret Manager environment variables.

Produce valid YAML, Dockerfile, and deployment scripts.