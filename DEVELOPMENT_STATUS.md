# Development Status

## Scope

CodeLens AI is being created as an independent project in this folder. It is separate from the existing stock-prediction project.

## Phase 1 — Workspace and architecture

- [x] Confirmed the active project folder was empty.
- [x] Established a standalone frontend/backend/docs layout and initial project configuration.

## Initial implementation

- [x] FastAPI backend, SQLAlchemy persistence, Argon2 hashing, signed access tokens, server-side logout revocation, and per-user analysis ownership.
- [x] React/TypeScript workspace with Monaco editor, language selection, analysis results, and review history.
- [x] Ruff and Bandit integration for Python with timeouts and no source execution.
- [x] ESLint static checks for JavaScript/TypeScript; optional Checkstyle integration for Java source.
- [x] Optional Gemini endpoint with Pydantic response validation, tested against mocked success and failure cases.
- [x] Gemini source-transfer opt-in clearly states that the full source is sent to Google; unchecked by default.
- [x] Public GitHub repository/file API endpoints and frontend file picker, tested with mocked metadata/tree/content/error cases.
- [x] Request-body size limit, per-IP rate limits, public-only GitHub restriction, and optional source retention.
- [x] Per-token logout revocation and retained-source details in review history.
- [x] Live read-only GitHub repository metadata, tree, and supported source file verified through the configured adapter.
- [x] Redis/Rediss storage is configurable for shared rate-limit counters; production rejects the process-local memory default.
- [x] Persisted source and analyzer/AI evidence are opt-in; legacy unretained evidence is redacted by Alembic migration.
- [x] On-demand AI test scenarios are source-dependent, authenticated, rate-limited, schema-validated (1–20 scenarios), disclose the Gemini source transfer, are not executable, and are not persisted.
- [x] Alembic initial migration, JSON reports, and finding filters/search.
- [x] Frontend and backend tests, setup/deployment configuration, and dependency lock file.
- [x] Quality score suppressed when no static analyzer completed; unsupported/unavailable analysis is visible.
- [x] Complete remaining pages/features, provision/verify Redis across instances, actual service deployments, and GitHub publishing.
- The detailed live checklist is in [TODO.md](./TODO.md).

## Verification

- Backend: `python -m pytest -q -p no:cacheprovider` — 62 passed; Ruff passed; Bandit reported no findings.
- Database: all Alembic migrations, including revocation, applied on an isolated fresh SQLite database; `alembic check` passed. Existing pre-revocation tokens require a fresh login.
- Frontend: 11 tests passed; production build passed; npm audit — 0 vulnerabilities.
- Live integration: public `psf/requests` metadata/tree and a supported source file were fetched successfully. Gemini review and scenario generation are validated with mocked provider responses; live Gemini access remains unverified.
- Render blueprint YAML parses. Docker image build could not be attempted because Docker is unavailable.
- Redis backend selection, environment-variable parsing, secret-safe configuration, and production rejection of process-local memory storage are tested; a live Redis server is not configured in this environment.
- The ignored demo SQLite database was initialized via `create_all` and has no Alembic revision marker; migration verification was kept isolated and did not alter demo history.
- Live Gemini/PostgreSQL and GitHub/Vercel/Render publishing have not been verified or deployed; only a public GitHub read was verified.
