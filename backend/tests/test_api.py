from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage, RedisStorage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.main as main
from app.main import app
from app.schemas import AnalyzerStatus, Finding


def test_limiter_can_use_shared_redis_storage_without_connecting() -> None:
    limiter = main.create_limiter("rediss://user:password@redis.example.com:6380/0")

    assert isinstance(limiter.limiter.storage, RedisStorage)


def test_local_limiter_uses_in_memory_storage() -> None:
    limiter = main.create_limiter("memory://")

    assert isinstance(limiter.limiter.storage, MemoryStorage)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main, "engine", engine)
    main.limiter.reset()

    def override_get_db() -> Generator[Session, None, None]:
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    main.limiter.reset()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"name": "Code Reviewer", "email": email, "password": "a-long-test-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_registration_login_and_protected_identity(client: TestClient) -> None:
    token = register(client, "first@example.com")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == "first@example.com"
    duplicate = client.post(
        "/api/auth/register",
        json={"name": "Code Reviewer", "email": "first@example.com", "password": "a-long-test-password"},
    )
    assert duplicate.status_code == 409
    login = client.post(
        "/api/auth/login",
        json={"email": "first@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_logout_revokes_only_the_current_access_token(client: TestClient) -> None:
    token = register(client, "logout@example.com")
    second_login = client.post(
        "/api/auth/login",
        json={"email": "logout@example.com", "password": "a-long-test-password"},
    )
    assert second_login.status_code == 200
    first_headers = {"Authorization": f"Bearer {token}"}
    second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}

    assert client.get("/api/auth/me", headers=first_headers).status_code == 200
    assert client.post("/api/auth/logout", headers=first_headers).status_code == 204
    assert client.get("/api/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/auth/me", headers=second_headers).status_code == 200
    assert client.post("/api/auth/logout", headers=first_headers).status_code == 401


def test_logout_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 401


def test_analysis_history_is_scoped_to_authenticated_user(client: TestClient) -> None:
    first_token = register(client, "one@example.com")
    second_token = register(client, "two@example.com")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    created = client.post(
        "/api/analyses",
        headers=first_headers,
        json={"language": "python", "source_code": "print('not executed')", "retain_source": True},
    )
    assert created.status_code == 201
    analysis_id = created.json()["id"]
    assert created.json()["quality_score"] == 100
    assert created.json()["source_code"] == "print('not executed')"
    assert len(client.get("/api/analyses", headers=first_headers).json()) == 1
    assert client.get("/api/analyses", headers=second_headers).json() == []
    assert client.get(f"/api/analyses/{analysis_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/analyses/{analysis_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/analyses/{analysis_id}", headers=first_headers).status_code == 204


def test_source_is_not_retained_unless_explicitly_requested(client: TestClient) -> None:
    token = register(client, "retention@example.com")
    response = client.post(
        "/api/analyses",
        headers={"Authorization": f"Bearer {token}"},
        json={"language": "java", "source_code": "class Example {}"},
    )
    assert response.status_code == 201
    assert response.json()["source_code"] == "class Example {}"
    analysis_id = response.json()["id"]
    reread = client.get(
        f"/api/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reread.status_code == 200
    assert reread.json()["source_code"] is None


def test_finding_evidence_is_retained_only_with_source_opt_in(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = "sensitive source excerpt"
    finding = Finding(
        id="test-finding",
        title="Example issue",
        description="A test finding.",
        severity="medium",
        file_path="main.py",
        line=1,
        evidence=evidence,
        analyzer="Test",
        suggested_correction=None,
    )

    def fake_analyze(_language: str, _source: str) -> tuple[list[AnalyzerStatus], list[Finding]]:
        return [AnalyzerStatus(name="Test", available=True, message="Completed.")], [finding]

    async def fake_review(_language: str, _source: str) -> list[dict]:
        return [
            {
                "title": "AI example",
                "explanation": "A test AI finding.",
                "severity": "low",
                "evidence": evidence,
                "line_start": 1,
                "line_end": 1,
                "why_it_matters": "Testing evidence retention.",
                "recommended_fix": "Review the source.",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(main, "analyze", fake_analyze)
    monkeypatch.setattr(main, "review_source", fake_review)
    token = register(client, "evidence-retention@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    request = {
        "language": "python",
        "source_code": "print('private')",
        "include_ai": True,
    }

    created = client.post("/api/analyses", headers=headers, json=request)
    assert created.status_code == 201
    assert created.json()["findings"][0]["evidence"] == evidence
    assert created.json()["ai_findings"][0]["evidence"] == evidence
    analysis_id = created.json()["id"]

    reread = client.get(f"/api/analyses/{analysis_id}", headers=headers)
    assert reread.status_code == 200
    assert reread.json()["source_code"] is None
    assert reread.json()["findings"][0]["evidence"] is None
    assert reread.json()["ai_findings"][0]["evidence"] is None

    retained = client.post(
        "/api/analyses",
        headers=headers,
        json={**request, "retain_source": True},
    )
    assert retained.status_code == 201
    retained_id = retained.json()["id"]
    retained_read = client.get(f"/api/analyses/{retained_id}", headers=headers)
    assert retained_read.status_code == 200
    assert retained_read.json()["source_code"] == request["source_code"]
    assert retained_read.json()["findings"][0]["evidence"] == evidence
    assert retained_read.json()["ai_findings"][0]["evidence"] == evidence


def test_test_case_endpoint_requires_auth_and_limits_source_size(client: TestClient) -> None:
    body = {"language": "python", "source_code": "print('hello')"}
    assert client.post("/api/test-cases", json=body).status_code == 401

    token = register(client, "test-cases@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    oversized = {"language": "python", "source_code": "x" * (main.settings.max_source_bytes + 1)}
    response = client.post("/api/test-cases", headers=headers, json=oversized)
    assert response.status_code == 413


def test_test_case_endpoint_returns_scenarios_without_persisting_them(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generate(language: str, source: str) -> list[dict]:
        assert language == "python"
        assert source == "print('hello')"
        return [
            {
                "name": "Normal input",
                "purpose": "Check standard behavior.",
                "input_data": "'hello'",
                "expected_result": "The greeting is produced.",
                "category": "normal",
            }
        ]

    monkeypatch.setattr(main, "generate_test_cases", fake_generate)
    token = register(client, "test-cases-api@example.com")
    response = client.post(
        "/api/test-cases",
        headers={"Authorization": f"Bearer {token}"},
        json={"language": "python", "source_code": "print('hello')"},
    )

    assert response.status_code == 200
    assert response.json()[0]["category"] == "normal"
    assert client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"}).json() == []


def test_test_case_provider_error_is_explicit_and_does_not_save_history(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(_language: str, _source: str) -> list[dict]:
        raise main.AIReviewError("Gemini is not configured.")

    monkeypatch.setattr(main, "generate_test_cases", unavailable)
    token = register(client, "test-cases-error@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/test-cases",
        headers=headers,
        json={"language": "python", "source_code": "print('hello')"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini is not configured."
    assert client.get("/api/analyses", headers=headers).json() == []


def test_unavailable_analyzer_does_not_receive_a_perfect_score(client: TestClient) -> None:
    token = register(client, "java-review@example.com")
    response = client.post(
        "/api/analyses",
        headers={"Authorization": f"Bearer {token}"},
        json={"language": "java", "source_code": "class Example {}"},
    )
    assert response.status_code == 201
    assert response.json()["quality_score"] is None
    assert response.json()["status"] == "unavailable"


def test_github_routes_require_authentication_and_reject_non_github_urls(client: TestClient) -> None:
    unauthenticated = client.post(
        "/api/github/repository",
        json={"url": "https://github.com/octocat/Hello-World"},
    )
    assert unauthenticated.status_code == 401

    token = register(client, "github@example.com")
    response = client.post(
        "/api/github/repository",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://github.com.attacker.invalid/octocat/Hello-World"},
    )
    assert response.status_code == 422


def test_github_browse_route_returns_repository_files_without_live_network(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def repo_info(_owner: str, _repo: str) -> dict:
        return {
            "full_name": "sample/project",
            "description": "A test repository",
            "default_branch": "main",
            "html_url": "https://github.com/sample/project",
            "private": False,
            "size": 1,
        }

    async def repo_files(_owner: str, _repo: str, _branch: str) -> list[dict]:
        return [{"path": "main.py", "size": 10, "sha": "abc"}]

    monkeypatch.setattr(main, "repository_info", repo_info)
    monkeypatch.setattr(main, "repository_files", repo_files)
    token = register(client, "browse@example.com")
    response = client.post(
        "/api/github/repository",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://github.com/sample/project"},
    )
    assert response.status_code == 200
    assert response.json()["repository"]["full_name"] == "sample/project"
    assert response.json()["files"][0]["path"] == "main.py"


def test_github_browse_route_rejects_private_repository(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def private_repo(_owner: str, _repo: str) -> dict:
        return {"private": True}

    monkeypatch.setattr(main, "repository_info", private_repo)
    token = register(client, "private-repo@example.com")
    response = client.post(
        "/api/github/repository",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://github.com/sample/private"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only public GitHub repositories can be analyzed."


def test_api_rejects_oversized_content_before_route_processing(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        headers={"Content-Length": str(300_000)},
        content=b"",
    )
    assert response.status_code == 413


def test_registration_is_rate_limited_per_client_ip(client: TestClient) -> None:
    for index in range(10):
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Rate Limit",
                "email": f"rate-{index}@example.com",
                "password": "a-long-test-password",
            },
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/auth/register",
        json={
            "name": "Rate Limit",
            "email": "rate-blocked@example.com",
            "password": "a-long-test-password",
        },
    )
    assert blocked.status_code == 429
