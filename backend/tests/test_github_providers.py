import base64
import asyncio

import httpx
import pytest

import app.github as github


class FakeClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.requested_url: str | None = None
        self.requested_headers: dict[str, str] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url: str, headers: dict[str, str]):
        self.requested_url = url
        self.requested_headers = headers
        return self.response


def test_repository_info_success_and_api_path(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        200,
        json={
            "full_name": "sample/project",
            "description": "sample",
            "default_branch": "main",
            "html_url": "https://github.com/sample/project",
            "private": False,
            "size": 20,
        },
    )
    fake = FakeClient(response)
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: fake)
    result = asyncio.run(github.repository_info("sample", "project"))
    assert result["full_name"] == "sample/project"
    assert fake.requested_url == "https://api.github.com/repos/sample/project"


def test_repository_tree_filters_extensions_and_oversized_files(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(
        httpx.Response(
            200,
            json={
                "tree": [
                    {"type": "blob", "path": "src/main.py", "size": 100, "sha": "abc"},
                    {"type": "blob", "path": "README.md", "size": 100, "sha": "def"},
                    {"type": "blob", "path": "large.ts", "size": 300_000, "sha": "ghi"},
                    {"type": "tree", "path": "src", "size": 0, "sha": "jkl"},
                ]
            },
        )
    )
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: fake)
    files = asyncio.run(github.repository_files("sample", "project", "main"))
    assert [item["path"] for item in files] == ["src/main.py"]


def test_read_file_decodes_utf8_and_percent_encodes_path(monkeypatch: pytest.MonkeyPatch) -> None:
    content = base64.b64encode(b"print('hello')\n").decode()
    fake = FakeClient(
        httpx.Response(
            200,
            json={"type": "file", "encoding": "base64", "content": content},
        )
    )
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: fake)
    result = asyncio.run(github.repository_file("sample", "project", "src/main.py"))
    assert result["source_code"] == "print('hello')\n"
    assert fake.requested_url and "/contents/src/main.py" in fake.requested_url


@pytest.mark.parametrize(
    ("status_code", "headers", "expected_code"),
    [
        (404, {}, 404),
        (403, {"X-RateLimit-Remaining": "0"}, 429),
        (401, {}, 503),
    ],
)
def test_github_errors_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    headers: dict[str, str],
    expected_code: int,
) -> None:
    fake = FakeClient(httpx.Response(status_code, headers=headers, json={"message": "error"}))
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: fake)
    with pytest.raises(github.GitHubError) as raised:
        asyncio.run(github.repository_info("sample", "project"))
    assert raised.value.status_code == expected_code


def test_invalid_base64_or_non_utf8_file_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for content in ("%%%", base64.b64encode(b"\xff").decode()):
        malformed = FakeClient(
            httpx.Response(200, json={"type": "file", "encoding": "base64", "content": content})
        )
        monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: malformed)
        with pytest.raises(github.GitHubError):
            asyncio.run(github.repository_file("sample", "project", "src/main.py"))


def test_repository_request_has_no_redirect_follow_and_auth_not_in_url(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(httpx.Response(200, json={"full_name": "a/b"}))
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **_kwargs: fake)
    monkeypatch.setattr(github, "_headers", lambda: {"Authorization": "Bearer test-secret"})
    asyncio.run(github.repository_info("a", "b"))
    assert fake.requested_url and "test-secret" not in fake.requested_url
    assert fake.requested_headers == {"Authorization": "Bearer test-secret"}
