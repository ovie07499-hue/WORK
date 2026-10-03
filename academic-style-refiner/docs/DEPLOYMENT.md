# Deployment

## Requirements

- An Anthropic API key (`ANTHROPIC_API_KEY`) for real rewriting. Without one, set
  `REFINER_MOCK_LLM=true` to run the whole app against a deterministic offline rewriter.
- Docker, **or** Python 3.11+ and Node.js 20+.

## Option A: Docker (recommended)

```bash
cd academic-style-refiner
cp .env.example .env          # then set ANTHROPIC_API_KEY
docker compose up --build -d
open http://localhost:8000
```

The image builds the React app, installs the API and serves both from one container on
port 8000. It runs as a non-root user, with a read-only filesystem, and has a health check
on `/api/health`.

## Option B: Local development

```bash
# Backend (terminal 1)
cd academic-style-refiner/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export ANTHROPIC_API_KEY=sk-ant-...        # or: export REFINER_MOCK_LLM=true
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd academic-style-refiner/frontend
npm ci
npm run dev                                 # http://localhost:5173, proxies /api to :8000
```

Checks:

```bash
cd backend && pytest && ruff check app tests
cd frontend && npm run build               # type-checks, then bundles
```

## Option C: Without Docker in production

```bash
cd academic-style-refiner/frontend && npm ci && npm run build
cp -r dist ../backend/static
cd ../backend && pip install -r requirements.txt
ANTHROPIC_API_KEY=... uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Run it under a process manager (systemd, supervisord) and put it behind a reverse proxy.

## Reverse proxy

Terminate TLS at the proxy. Progress is streamed with Server-Sent Events, so response
buffering must be off for `/api/jobs/*/events` (the API already sends
`X-Accel-Buffering: no`, which nginx honours). Example nginx block:

```nginx
server {
    listen 443 ssl http2;
    server_name refiner.example.edu;
    client_max_body_size 6m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 900s;    # long documents stream for several minutes
        proxy_buffering off;
    }
}
```

## Access control and cost

Every refinement spends API credit, so do not expose the app publicly without
authentication. Put it behind your organisation's single sign-on (for example
oauth2-proxy, Cloudflare Access or an identity-aware proxy) and add per-user rate limits
at the proxy. Inside the app, `REFINER_MAX_ACTIVE_JOBS` caps concurrent documents
(further requests get HTTP 429) and `REFINER_MAX_WORDS` caps document size.

Rough cost (estimated from token counts, not yet measured): each paragraph makes two
calls, and every call resends the system prompt and the neighbouring paragraphs. A
10,000-word report of ~60 paragraphs therefore uses about 200k input and 70-80k output
tokens (including thinking), which is roughly **$2-3 on Claude Opus 5.5** ($4/$20 per
million input/output tokens), about half that on Claude Sonnet 5.5. Regenerating one
paragraph costs about 4 cents. Check real usage in the Claude Console after a few runs and
set a monthly spend limit there. Lower `REFINER_PASS1_EFFORT` or choose a cheaper model via
`REFINER_MODEL` to reduce cost.

## Scaling

Jobs live in the memory of the process that created them, so:

- Run **one uvicorn worker per container** (the default command does this).
- To scale out, run several containers behind a load balancer with **sticky sessions**
  (cookie or client-IP affinity), so a browser's SSE stream reaches the container holding
  its job. Paragraph regeneration, analysis and export are stateless and can go anywhere.
- Throughput per container is governed by `REFINER_CHUNK_CONCURRENCY` ×
  `REFINER_MAX_ACTIVE_JOBS` concurrent API requests; keep that product within your
  Anthropic rate limits. The SDK retries 429/5xx responses with exponential backoff.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Claude API key |
| `REFINER_MODEL` | `claude-opus-5-5` | Model for both stages (must support adaptive thinking and effort) |
| `REFINER_PASS1_EFFORT` | `medium` | Effort for the rewrite stage |
| `REFINER_PASS2_EFFORT` | `low` | Effort for the polish stage |
| `REFINER_MAX_OUTPUT_TOKENS` | `8000` | Max tokens per call |
| `REFINER_ENABLE_FALLBACKS` | `true` | Server-side fallback on declined requests (Claude API only; disable on Bedrock/Vertex/Foundry) |
| `REFINER_MOCK_LLM` | `false` | Offline deterministic rewriter for demos and tests |
| `REFINER_MAX_WORDS` | `10000` | Document size limit |
| `REFINER_MAX_UPLOAD_BYTES` | `5242880` | Upload size limit |
| `REFINER_MAX_CHUNK_WORDS` | `320` | Paragraphs longer than this are split into segments |
| `REFINER_CHUNK_CONCURRENCY` | `4` | Parallel API calls per job |
| `REFINER_MAX_ACTIVE_JOBS` | `8` | Concurrent jobs per process |
| `REFINER_JOB_TTL_SECONDS` | `1800` | Purge finished/abandoned jobs after this many seconds |
| `REFINER_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins (JSON list) when UI and API are on different origins |
| `REFINER_STATIC_DIR` | `static` | Folder with the built frontend |
