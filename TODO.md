# CodeLens AI — Progress and Todo List

This list reflects the current implementation in this standalone project. A checked box means the item has been implemented and the listed checks passed; it does not mean an external service or production deployment has been verified.

## Completed

- [x] Created a separate CodeLens AI project in this folder; it is not integrated with the stock-prediction project.
- [x] Added project setup, security, architecture, API, contributing, license, environment example, and development-status documentation.
- [x] Built the React + TypeScript frontend with a responsive dark/light workspace, Monaco editor, language selection, auth screens, analysis display, and review history.
- [x] Implemented FastAPI registration/login, Argon2 password hashing, signed access tokens, authenticated routes, and account-scoped review history/deletion.
- [x] Added SQLite local persistence and PostgreSQL-compatible SQLAlchemy configuration.
- [x] Implemented Python Ruff and Bandit integrations with analyzer availability reporting and execution timeouts; submitted code is not executed.
- [x] Added an honest unavailable state and suppressed the quality score if no static analyzer completed.
- [x] Added optional Gemini review with validated Pydantic response structure; a real API call has not been verified.
- [x] Added public GitHub repository browsing and supported-file loading UI, URL/path validation, file-size checks, and rate-limit/error handling.
- [x] Added an API request-body size limit and tests for unauthorized access, repository URL validation, and oversized requests.
- [x] Made full source retention opt-in per analysis; source remains temporarily available in the immediate response but is omitted from persisted history unless selected.
- [x] Added per-IP rate limits to registration, login, analysis, and GitHub routes using an in-process limiter.
- [x] Added initial Alembic schema migration and verified it on a throwaway SQLite database.
- [x] Added optional Checkstyle for Java and tests for Checkstyle XML result parsing; source is never compiled or executed.
- [x] Added isolated ESLint invocation for JavaScript/TypeScript with actual rule/line tests.
- [x] Added mocked GitHub metadata/tree/content/error tests and mocked Gemini response/schema/missing-key/provider-error/timeout tests.
- [x] Added static finding search and severity filters plus JSON report downloads.
- [x] Added Render, Vercel, and Docker deployment configuration (not deployed).
- [x] Added frontend file upload validation for supported extensions, empty files, and the 200 KB client-side limit.
- [x] Added server-side per-IP rate-limit test and public-repository-only enforcement.
- [x] Added source retention behavior tests and clarified retained evidence limitations.
- [x] Added frontend API-service and registration form tests.
- [x] Added authenticated logout endpoint that revokes only the active token, with a client-visible warning if remote revocation fails.
- [x] Added explicit, default-off disclosure before sending source to Google Gemini.
- [x] Made source and static/AI evidence retention opt-in, redacted snippets from saved and legacy unretained reviews, and documented the policy in the UI and API.
- [x] Added shared Redis/Rediss rate-limit storage configuration and a production guard against process-local fallback.
- [x] Added per-token server-side logout revocation and immediate local sign-out.
- [x] Added source detail to saved reviews, showing retained code or a clear explanation when history omitted it.
- [x] Verified read-only live GitHub metadata, repository tree, and supported source-file retrieval against the public `psf/requests` repository.
- [x] Verified backend: `python -m pytest -q -p no:cacheprovider` — 62 passed; Ruff passed; Bandit reported no findings.
- [x] Applied Alembic migrations through `0003_revoked_access_tokens` and passed `alembic check` on a fresh isolated SQLite database.
- [x] Verified Redis backend selection, secret-safe settings, and production rejection of in-memory rate limits; a live Redis service was unavailable for cross-instance testing.
- [x] Verified Alembic migration applies and `alembic check` reports no model/schema drift on SQLite.
- [x] Verified evidence-retention migration redacts legacy static/AI snippets only for reviews without retained source.
- [x] Verified frontend: 12 tests passed; production build passed; `npm audit` — 0 vulnerabilities.
- [x] Prevented production API calls from falling back to a visitor's localhost; the sign-in screen now explains when the backend is not configured, and saved-review requests use the shared API client.
- [x] GitHub Actions run `42593496295` passed frontend tests/build, backend tests, Docker image build, and container `/health` smoke test.
- [x] Redeployed the frontend to Vercel after validation; confirmed HTTP 200 and verified the production API-unconfigured notice is in the deployed JavaScript.
- [x] Validated Render YAML syntax.

## In progress / next

- [x] Verified Checkstyle 10.23.0 with Java 21 against a Java sample and confirmed its XML finding output.
- [x] Created and deployed the frontend to the public Vercel `codelens-ai` project; configured the `frontend/` root, Vite build, `dist` output, and Node 24.x runtime.
- [x] Deployed the CodeLens FastAPI backend, PostgreSQL database, and Redis-compatible Key Value service to Render on free plans; verified `/health`, database connectivity, API routes, and Vercel-origin CORS.
- [x] Configured Vercel to proxy `/api/*` to the live Render API so the frontend can use the backend without a Vercel environment variable.
- [x] Build and smoke-test the production Docker image through GitHub Actions; Docker is unavailable locally.
- [x] Add source-evidence redaction/retention policy for snippets that analyzers or AI may include inside persisted finding details.
- [x] Add report downloads and static finding filters/search.
- [x] Add optional, structured AI test-scenario generation for source available in the active review; disclose Gemini source transfer, require at least one scenario, and ensure generated scenarios are neither executable, executed, nor saved.
- [x] Add source code to persisted review detail views when the user opted into retention.
- [x] Add landing, about, documentation, settings, and profile pages; current UI is a login and review workspace.
- [x] Add server-side logout/revocation; refresh-token rotation remains unimplemented.
- [x] Clarified Gemini source-sharing consent in the review UI and documentation.
- [x] Provisioned a shared Render Key Value service for rate limits; free-tier persistence/reliability limitations remain.
- [x] Verified Redis rate-limit counters are shared across two local FastAPI instances using an isolated Redis database.
- [x] Captured the local sign-in screen and analyzed workspace in the session; screenshots are visual references, not committed assets.
- [x] Authenticated GitHub CLI, scanned staged source for common credential formats, excluded local environment/database/cache files, and pushed the initial commit to `rhr10082004/CodeLens---AI`.
- [x] Verified the public GitHub repository and live Vercel frontend.
- [x] Verified the Render API and PostgreSQL health; Gemini calls still require a configured API key.

## Known environment notes

- Local Docker availability varies by environment; the production image was built and smoke-tested in GitHub Actions.
- Two local FastAPI instances shared rate-limit counters through the installed Redis service; production still requires a managed/shared Redis service.
- Demo DB is created with SQLAlchemy `create_all` and has no Alembic revision marker; do not run `alembic upgrade head` directly against this local DB. Migration validation used a fresh throwaway database.
- Checkstyle was verified with a real Checkstyle 10.23.0 JAR and Java 21.
- The local demo frontend and API are running at `http://127.0.0.1:5173` and `http://127.0.0.1:8001`; the demo account uses the isolated ignored SQLite database.
- Changes are pushed to the public GitHub repository on `main`; pre-existing untracked `file.jpe` and `file.jpg` remain untouched.
- The frontend is deployed at `https://codelens-ai-eight-ivory.vercel.app/`; the CodeLens API is deployed at `https://codelens-ai-api-a59o.onrender.com` and the Vercel `/api/*` rewrite targets it.
- Render's free Postgres expires 30 days after creation and is deleted after a further 14-day grace period if not upgraded. The free web service sleeps after 15 minutes idle; free Redis-compatible Key Value data is lost on restart. These free resources are for demo/testing rather than reliable production.
- Existing pre-revocation access tokens must be replaced with a fresh login after applying migration `0003`.
