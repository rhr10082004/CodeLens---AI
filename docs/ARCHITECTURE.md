# Architecture and Security

## System overview

The browser sends source to the CodeLens API for static review. The API validates the request, checks authorization and limits, and dispatches the source to language-specific static analyzers. User code is treated as untrusted data throughout: the service does not import, compile, or execute submissions.

```mermaid
flowchart LR
    subgraph client["Client"]
        Browser["Browser<br/>React · TypeScript · Monaco"]
    end

    subgraph edge["Frontend delivery"]
        Vercel["Vercel<br/>Static app · /api proxy"]
    end

    subgraph backend["Application boundary · Render"]
        API["FastAPI<br/>Validation · Authentication · Authorization"]
        Review["Review service<br/>Size and language checks"]
        Static["Static analyzers<br/>Ruff · Bandit · ESLint · Checkstyle"]
    end

    subgraph data["Persistent and shared services"]
        DB[("PostgreSQL<br/>Users · Reviews · Revoked tokens")]
        Redis[("Redis-compatible Key Value<br/>Shared rate-limit counters")]
    end

    subgraph external["Optional outbound integrations"]
        Gemini["Google Gemini API<br/>Opt-in only"]
        GitHub["GitHub REST API<br/>Public repositories"]
    end

    Browser -->|"HTTPS · SPA assets"| Vercel
    Browser -->|"HTTPS · JSON · bearer token"| Vercel
    Vercel -->|"/api/* rewrite"| API
    API --> Review
    API <-->|"Account-scoped data"| DB
    API -->|"Per-IP quotas"| Redis
    Review -->|"Temporary files · timeout · no execution"| Static
    Review -.->|"Only after explicit consent<br/>and when configured"| Gemini
    API -.->|"Validated public-repository requests"| GitHub

    classDef client fill:#eaf2ff,stroke:#4775b8,color:#15263d
    classDef edge fill:#f0ebff,stroke:#7957b2,color:#271c3d
    classDef app fill:#e8f7f0,stroke:#388268,color:#17352c
    classDef store fill:#fff4df,stroke:#ba8230,color:#463116
    classDef external fill:#f3f4f6,stroke:#707985,color:#252a31
    class Browser client
    class Vercel edge
    class API,Review,Static app
    class DB,Redis store
    class Gemini,GitHub external
```

## Request and trust boundaries

1. **Browser to API:** Requests use HTTPS and JSON. Protected routes require a signed bearer token. Source is untrusted input even when the user is authenticated.
2. **API validation:** The API checks authentication, ownership, language, non-empty source, and the configured maximum request size before processing.
3. **Static analysis:** The backend invokes fixed analyzer executables with argument lists, temporary files, `shell=False`, and a 15-second timeout. Submitted code is not executed.
4. **Optional AI review:** Source is sent to Gemini only when the user opts in and the backend has a Gemini key. AI findings remain separate from static findings and are treated as unverified hypotheses.
5. **GitHub browsing:** Repository browsing is limited to public GitHub repositories and validated paths; repository contents are fetched as data, not cloned or run.
6. **Persistence:** Reviews are associated with their owner. Source and finding evidence are retained only when explicitly selected by the user or enabled by the server default; otherwise they are omitted or redacted in saved history.
7. **Rate limits:** Local development uses in-memory counters. The deployed service uses shared Redis-compatible storage; storage errors are surfaced rather than silently falling back to per-process counters.

## Authentication and data controls

- Passwords are stored as Argon2 hashes; plaintext passwords are not persisted.
- Signed access tokens carry a unique token ID. Logout stores the revoked token ID and expiry; protected endpoints reject revoked tokens.
- Users can access and delete only their own review history.
- Source and finding evidence are returned for the immediate review, but are omitted from persisted history unless retention is selected.
- AI-generated test scenarios are schema-validated descriptions. They are neither executable tests nor persisted records.
- Refresh-token rotation is not implemented.

## Analysis behavior

| Language | Analyzer | Execution boundary |
|---|---|---|
| Python | Ruff and Bandit | Static checks on a temporary source file |
| JavaScript / TypeScript | ESLint | Static checks using a temporary configuration |
| Java | Checkstyle, when Java and `CHECKSTYLE_JAR` are configured | Source parsing only; no compilation or execution |

Unavailable analyzers and provider errors are reported explicitly; the API does not fabricate successful results. The quality score is a simple static-finding triage aid, excludes AI hypotheses, and is not a security certification.

## Deployment topology and limitations

- **Frontend:** Vercel serves the static application and rewrites `/api/*` requests to the Render API.
- **API and database:** Render hosts FastAPI and PostgreSQL; Alembic migrations run when the container starts.
- **Rate limiting:** A Render Redis-compatible Key Value service shares counters across API instances.
- **Current plan:** These Render resources are on the Free plan. The API may sleep after inactivity, free Key Value data is not persistent across restarts, and free PostgreSQL expires after 30 days. This is demo infrastructure, not reliable production hosting.
- **Gemini:** No production `GEMINI_API_KEY` is currently configured. Gemini-powered features remain unavailable until one is added securely to the backend environment.

For table definitions, indexes, and relationships, see the [entity-relationship diagram](./ERD.md).
