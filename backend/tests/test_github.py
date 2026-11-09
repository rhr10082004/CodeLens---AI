import pytest

from app.github import parse_repository_url, validate_repository_path


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
        ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
    ],
)
def test_parse_public_repository_url(url: str, expected: tuple[str, str]) -> None:
    assert parse_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/octocat/repo",
        "https://github.com.attacker.invalid/octocat/repo",
        "https://user@github.com/octocat/repo",
        "https://github.com/octocat/repo/tree/main",
        "https://github.com/octocat/../secret",
        "https://github.com/octocat/repo?tab=readme",
        "https://github.com/octocat/repo#readme",
    ],
)
def test_reject_unsafe_or_non_repository_urls(url: str) -> None:
    with pytest.raises(ValueError):
        parse_repository_url(url)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/main.py", "src/main.py"),
        ("frontend/app.tsx", "frontend/app.tsx"),
    ],
)
def test_supported_relative_paths(path: str, expected: str) -> None:
    assert validate_repository_path(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "../secret.py",
        "src/../../secret.py",
        "/root.py",
        "src\\..\\secret.py",
        "C:/project/src/main.py",
        "C:\\project\\src\\main.py",
        "README.md",
    ],
)
def test_reject_traversal_absolute_and_unsupported_paths(path: str) -> None:
    with pytest.raises(ValueError):
        validate_repository_path(path)
