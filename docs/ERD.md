# CodeLens AI Entity-Relationship Diagram

The diagram reflects the SQLAlchemy models and Alembic migrations.

```mermaid
erDiagram
    USERS {
        int id PK
        string name
        string email UK
        string hashed_password
        datetime created_at
    }

    ANALYSES {
        int id PK
        int user_id FK
        string language
        text source_code
        int quality_score "nullable"
        string status
        text result_json
        datetime created_at
    }

    REVOKED_ACCESS_TOKENS {
        string token_id PK
        int user_id FK
        datetime expires_at
    }

    USERS ||--o{ ANALYSES : owns
    USERS ||--o{ REVOKED_ACCESS_TOKENS : revokes
```

## Relationships and indexes

- Deleting a user cascades to that user's analyses and revoked-token records.
- `users.email` has a unique index.
- `analyses` has a composite index on `(user_id, created_at)` for account-scoped history.
- `revoked_access_tokens` has an index on `expires_at` for expired-token cleanup.
- Analysis findings and analyzer results are serialized in `analyses.result_json`; they are not separate relational tables.
- Access tokens are signed JWTs. Only revoked tokens are persisted, keyed by their token ID.
