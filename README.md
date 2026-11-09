# CodeLens AI

CodeLens AI is a code intelligence workspace combining static analysis with optional Gemini-assisted review. Submitted source is analyzed as data and is never executed by the application.

> This is a standalone project, separate from the stock-prediction application.

**Live application:** [https://codelens-ai-eight-ivory.vercel.app/](https://codelens-ai-eight-ivory.vercel.app/)

The frontend is deployed on Vercel and the FastAPI backend is deployed on Render at [https://codelens-ai-api-a59o.onrender.com](https://codelens-ai-api-a59o.onrender.com). Vercel proxies `/api/*` requests to the backend. The API health check, database connection, login route, and Vercel-origin CORS were verified. Free Render services can sleep when idle; the free PostgreSQL database expires after 30 days and must be upgraded or migrated before expiry to avoid data loss.

## Contents

- [Features](#features)
- [Technology](#technology)
- [Architecture](#architecture)
- [Entity-relationship diagram](#entity-relationship-diagram)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Run tests](#run-tests)
- [API](#api)
- [Deployment](#deployment)
- [Security and limitations](#security-and-limitations)
- [Project structure](#project-structure)
- [Contributing and license](#contributing-and-license)

## Features

- React and TypeScript frontend with Monaco Editor, review results, and analysis history.
- FastAPI backend with registration, login, signed access tokens, server-side logout/revocation, and per-user review ownership.
- SQLAlchemy persistence with SQLite locally and PostgreSQL support.
- Python Ruff and Bandit analysis; JavaScript/TypeScript ESLint analysis using an isolated temporary configuration; optional Java Checkstyle when configured.
- Public GitHub repository browsing through the API. Repository code is neither cloned nor executed.
- Optional Gemini review with validated structured output. The opt-in explicitly discloses that the full source is sent to Google; static analyzer findings and AI-generated hypotheses remain separate.
- On-demand AI test-scenario generation for source available in the active review. It returns validated scenario descriptions, never executable tests; results are neither run nor saved.
- Review deletion, JSON report downloads, and source details when the source was retained.
- Full source and finding evidence are retained with review history only when requested. They are still available in the immediate review response.
- Registration/login, analysis, and GitHub endpoints have per-IP rate limits. Local development uses in-memory limits; production requires a shared Redis-compatible store.

Tool-based analysis is explicitly marked unavailable when its analyzer is missing or fails; no successful results are fabricated. AI recommendations are hypotheses that require developer verification.
AI test-scenario generation requires authentication, is limited to 10 requests per hour, and sends the supplied source to Gemini. It is unavailable when the active review has no source or Gemini is not configured.

## Technology

### Application stack

- **Frontend:** React 18, TypeScript, Vite 8, and Monaco Editor.
- **Backend:** Python 3.11+, FastAPI, and Pydantic.
- **Data layer:** SQLAlchemy and Alembic; SQLite for local development and PostgreSQL for the hosted service.
- **Authentication and rate limiting:** Argon2 password hashing, signed JWT bearer tokens with server-side revocation, and Redis-compatible shared rate-limit storage.
- **Static analysis:** Ruff and Bandit for Python; ESLint for JavaScript/TypeScript; optional Checkstyle for Java. These are analysis tools, not language models.
- **Deployment and CI:** Docker, GitHub Actions, Vercel for the frontend/API proxy, and Render for the backend and data services.

### LLM integration

- **Provider:** Google Gemini API.
- **Default model:** `gemini-2.5-flash` (configurable through `GEMINI_MODEL`).
- **Use cases:** Opt-in code review and structured AI test-scenario generation.
- **Privacy:** Source is sent to Gemini only after the user explicitly opts in.
- **Current availability:** The integration is implemented, but the deployed backend does not have `GEMINI_API_KEY` configured. These AI features are therefore unavailable in production until an authorized key is added to Render.
- **Verification:** Provider behavior is covered by mocked tests; live Gemini API calls have not been verified. Gemini is the only LLM provider currently integrated.

## Architecture

```mermaid
flowchart LR
  Browser[React + Monaco] --> API[FastAPI]
  API --> Auth[JWT auth]
  API --> DB[(SQLite / PostgreSQL)]
  API --> Limits[(Redis shared rate limits)]
  API --> Py[Python: Ruff + Bandit]
  API --> JS[JavaScript/TypeScript: ESLint]
  API --> Java[Java: optional Checkstyle]
  API -. Optional backend key .-> Gemini[Gemini API]
  API --> GitHub[GitHub REST API]
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for workflow, scoring, and data handling.

## Entity-relationship diagram

View the database entities, keys, indexes, and relationships in the [ER diagram](docs/ERD.md).

## Quick start

Requirements: Python 3.11+, Node.js 20.19+ (or 22.12+), and npm.

1. Copy `.env.example` to `.env` and set a unique random `JWT_SECRET_KEY` with at least 32 characters.
2. Start the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   uvicorn app.main:app --reload --port 8001
   ```

3. In a separate terminal, start the frontend:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

The local API is `http://127.0.0.1:8001`; the Vite frontend is `http://127.0.0.1:5173`. FastAPI's interactive API documentation is at `/docs`. SQLite tables are created automatically during local development.

### Local development links

When both local development servers are running:

- Frontend: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- Backend health: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)
- Backend API documentation: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

These are local loopback links, not public hosting: they work only on the computer running the servers. The backend must be running on port `8001` for the frontend's default local API setting to connect. The default CORS configuration allows both `localhost` and `127.0.0.1` on port `5173`.

## Configuration

See `.env.example` for all variables.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL; defaults to local SQLite. PostgreSQL URL schemes are normalized to psycopg. |
| `JWT_SECRET_KEY` | Required signing secret; use a random 32+ character value. |
| `RATE_LIMIT_STORAGE_URI` | Defaults to `memory://` locally. Production requires a shared Redis URL (`redis://` or `rediss://`); keep credentials in deployment secrets. |
| `CORS_ORIGINS` | Comma-separated exact browser origins. |
| `GEMINI_API_KEY` | Optional backend-only Gemini key. |
| `GITHUB_TOKEN` | Optional token for higher GitHub API limits; public read access works without it. |
| `CHECKSTYLE_JAR` | Optional Checkstyle JAR location. Java source is checked as text and is never compiled or executed. |
| `STORE_SOURCE_BY_DEFAULT` | Defaults to `false`; source retention can also be chosen for each analysis. |
| `MAX_SOURCE_BYTES` | Maximum UTF-8 source size, defaults to 200,000 bytes. |
| `FRONTEND_NODE_MODULES_PATH` | Optional path to frontend Node modules for the backend's ESLint adapter. Docker sets this automatically. |
| `VITE_API_BASE_URL` | Frontend API origin; this is a URL, never a secret. |

For PostgreSQL, use a SQLAlchemy URL such as `postgresql+psycopg://user:password@localhost:5432/codelens`. Never put secrets in `VITE_` variables.

The source and finding evidence are returned to the browser for the immediate review, but are omitted from persisted history unless retention is selected. Gemini review is off by default; enabling it sends the full source to Google. Do not enable it for code you are not authorized to share, or that contains secrets.

After applying database migrations, signing out revokes only the current bearer token. Existing pre-migration tokens without a unique token identifier must be replaced by signing in again.

## Run tests

```powershell
cd backend
python -m pytest -q
python -m ruff check app tests

cd ..\frontend
npm ci
npm run build
npm test
npm audit
```

Provider tests use mocked responses. The public GitHub read path was also checked once against `psf/requests`; real Gemini access and hosted service availability still depend on external credentials/services.

## API

Base URL: `http://127.0.0.1:8001`; OpenAPI UI: `/docs`. Request/response details are in [docs/API.md](docs/API.md).

Main routes:

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `POST /api/auth/logout` — revoke the current access token server-side.
- `POST /api/analyses`, `GET /api/analyses`, `GET /api/analyses/{id}`, `DELETE /api/analyses/{id}`
- `POST /api/github/repository`, `POST /api/github/file?path=...`
- `GET /health`

Analysis and GitHub endpoints require `Authorization: Bearer <token>`.

## Deployment

The frontend is deployed to Vercel and the backend, PostgreSQL, and Redis-compatible Key Value service are deployed through the root `render.yaml` Blueprint. All three Render services currently use the Free plan. Vercel proxies `/api/*` through `frontend/vercel.json`, so no API environment variable is required. The Render Docker startup applies Alembic migrations before starting FastAPI.

Free Render resources are suitable for a temporary demo, not reliable production: the web service spins down after 15 minutes idle and can take about a minute to wake; the free PostgreSQL database expires 30 days after creation, then has a 14-day upgrade window before deletion; free Key Value data is not persisted across restarts. Migrate/upgrade before database expiry and use paid persistent services for production reliability.

## Security and limitations

- Submitted source and public GitHub repository contents are never executed.
- Keep secrets in backend environment variables; never commit `.env`, databases, credentials, or build outputs.
- Protected analysis routes enforce user ownership.
- The quality score is `max(0, 100 - 5 × static finding count)`, is not severity-weighted, and is not a security certification. It is omitted if no analyzer completes.
- Gemini output is schema-validated but remains an untrusted AI hypothesis.
- Gemini review is opt-in. When enabled, the full source is transmitted to Google's Gemini API; users must have permission to share that source and should remove secrets first.
- Full source and static/AI finding evidence are retained only when explicitly selected, or when `STORE_SOURCE_BY_DEFAULT=true` is enabled by the server administrator. Without retention, source/evidence remain available in the immediate response but are omitted from saved history. An Alembic data migration redacts evidence from existing records that did not retain source.
- `POST /api/auth/logout` revokes the current access token; the browser clears local state immediately and reports if server revocation cannot be reached. Existing access tokens must be refreshed by signing in again after deployment of the revocation migration.
- Rate limiting uses shared Redis storage when configured. Production rejects process-local memory storage, and Redis storage errors are not swallowed or replaced with local counters. Provision and monitor the Redis service separately. Refresh-token rotation is not implemented.
- Java analysis requires Java plus a configured Checkstyle JAR; no compilation/execution is performed.
- Gemini-powered review remains unavailable until a valid backend `GEMINI_API_KEY` is configured.

## Project structure

```text
backend/
  app/                 FastAPI endpoints, models, auth, analyzers, providers
  migrations/          Alembic environment and schema revisions
  tests/               Backend/provider/analyzer tests
  Dockerfile            Container deployment
frontend/
  src/                 React UI, API client, types, tests, styles
  vercel.json           SPA routing for Vercel
docs/                   API and architecture documentation
TODO.md                 Live progress checklist
DEVELOPMENT_STATUS.md   Phase summary and validation
render.yaml             Render backend/database blueprint
```

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). License: [MIT](LICENSE).
