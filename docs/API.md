# API

Base URL in local development: `http://127.0.0.1:8001`.

FastAPI's interactive OpenAPI UI is served at `/docs`.

## Authentication

- `POST /api/auth/register` — create an account.
- `POST /api/auth/login` — obtain a bearer access token.
- `GET /api/auth/me` — get the authenticated user.
- `POST /api/auth/logout` — revoke the presented access token; after a successful response it cannot be used for protected endpoints.
- Previously issued access tokens need to be replaced by signing in again after the revocation migration is applied.

Pass `Authorization: Bearer <access-token>` to protected endpoints.

## Analysis

- `POST /api/analyses` — analyze source code; JSON body includes `language`, `source_code`, and optional `include_ai`.
- Analysis requests accept `retain_source` (default `false`). The immediate response includes source and finding evidence for the open review, but future reads omit them unless retention is selected or enabled by server configuration.
- `GET /api/analyses` — list the current user's analyses.
- `GET /api/analyses/{analysis_id}` — retrieve one owned analysis.
- The review detail includes `source_code` only when source retention was enabled; otherwise it is `null`.
- `DELETE /api/analyses/{analysis_id}` — delete one owned analysis.
- `POST /api/test-cases` — authenticated, on-demand Gemini scenario generation; body includes `language` and non-empty `source_code`. Limited to 10 requests per hour per client IP. The supplied source is sent to Gemini; the response contains 1–20 validated scenario descriptions, not executable code. Scenarios are not executed or persisted, and provider/configuration errors are returned explicitly.
- Test-case generation requires source in the active review. It cannot be used for saved reviews whose source was not retained.
- `POST /api/github/repository` — browse a public GitHub repository by its canonical URL.
- `POST /api/github/file?path=...` — load a supported repository-relative source path; JSON body uses the same repository `url`.

Requests have configured source-size limits. Source is never executed. Analyzer availability, AI output, and any errors are reported explicitly.
Rate limits are keyed by client IP. Local development uses in-memory counters; production requires the shared store configured by `RATE_LIMIT_STORAGE_URI`.

## Health

- `GET /health` — API and database health status.
