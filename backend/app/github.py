import base64
import binascii
import re
from urllib.parse import quote, unquote, urlparse

import httpx

from app.core.config import get_settings

GITHUB_API = "https://api.github.com"
SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java"}
OWNER_OR_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class GitHubError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def parse_repository_url(url: str) -> tuple[str, str]:
    try:
        parsed = urlparse(url.strip())
        path = [unquote(part) for part in parsed.path.strip("/").split("/")]
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Enter a valid public GitHub repository URL.") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(path) != 2
        or not all(OWNER_OR_REPO.fullmatch(part) for part in path)
        or path[0] in {".", ".."}
        or path[1] in {".", ".."}
    ):
        raise ValueError("Enter a URL in the form https://github.com/owner/repository.")
    repository = path[1][:-4] if path[1].lower().endswith(".git") else path[1]
    if not repository:
        raise ValueError("Repository name is missing.")
    return path[0], repository


def validate_repository_path(path: str) -> str:
    decoded = unquote(path)
    normalized = decoded.replace("\\", "/")
    segments = normalized.split("/")
    if (
        not decoded
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", decoded)
        or any(segment in {"", ".", ".."} for segment in segments)
        or "\x00" in decoded
    ):
        raise ValueError("Enter a valid repository-relative file path.")
    if "." + segments[-1].rsplit(".", 1)[-1].lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("This file extension is not supported.")
    return decoded


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CodeLens-AI",
    }
    token = get_settings().github_token
    if token:
        headers["Authorization"] = f"Bearer {token.get_secret_value()}"
    return headers


async def _get_json(client: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client.get(url, headers=_headers())
    except httpx.TimeoutException as exc:
        raise GitHubError("GitHub request timed out. Please retry.", 504) from exc
    except httpx.HTTPError as exc:
        raise GitHubError("GitHub is temporarily unavailable.", 502) from exc
    if response.status_code == 404:
        raise GitHubError("Public repository or file was not found.", 404)
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubError("GitHub API rate limit reached. Retry later or configure a GitHub token.", 429)
    if response.status_code == 401:
        raise GitHubError("The configured GitHub token was rejected.", 503)
    if response.status_code == 429:
        raise GitHubError("GitHub API rate limit reached. Retry later.", 429)
    if response.status_code >= 400:
        raise GitHubError(f"GitHub request failed (HTTP {response.status_code}).", 502)
    try:
        data = response.json()
    except ValueError as exc:
        raise GitHubError("GitHub returned an invalid response.", 502) from exc
    if not isinstance(data, dict):
        raise GitHubError("GitHub returned an invalid response.", 502)
    return data


async def repository_info(owner: str, repo: str) -> dict:
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        data = await _get_json(client, f"{GITHUB_API}/repos/{owner}/{repo}")
    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "default_branch": data.get("default_branch"),
        "html_url": data.get("html_url"),
        "private": data.get("private"),
        "size": data.get("size"),
    }


async def repository_files(owner: str, repo: str, default_branch: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        data = await _get_json(
            client,
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{quote(default_branch, safe='')}?recursive=1",
        )
    if data.get("truncated"):
        raise GitHubError("Repository tree is too large to browse completely.", 413)
    tree = data.get("tree")
    if not isinstance(tree, list):
        raise GitHubError("GitHub returned an invalid repository tree.", 502)
    files = []
    for item in tree:
        path = item.get("path")
        if item.get("type") != "blob" or not isinstance(path, str):
            continue
        try:
            path = validate_repository_path(path)
        except ValueError:
            continue
        size = item.get("size")
        if isinstance(size, int) and size <= get_settings().max_source_bytes:
            files.append({"path": path, "size": size, "sha": item.get("sha")})
    return files[:500]


async def repository_file(owner: str, repo: str, path: str) -> dict:
    safe_path = validate_repository_path(path)
    encoded_path = "/".join(quote(segment, safe="") for segment in safe_path.split("/"))
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        data = await _get_json(client, f"{GITHUB_API}/repos/{owner}/{repo}/contents/{encoded_path}")
    if data.get("type") != "file" or data.get("encoding") != "base64":
        raise GitHubError("The selected repository item is not a supported file.", 422)
    content = data.get("content")
    if not isinstance(content, str):
        raise GitHubError("GitHub did not return file content.", 502)
    try:
        compact_content = re.sub(r"\s+", "", content)
        raw = base64.b64decode(compact_content, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise GitHubError("GitHub returned invalid file content.", 502) from exc
    if len(raw) > get_settings().max_source_bytes:
        raise GitHubError("The selected file exceeds the configured size limit.", 413)
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitHubError("The selected file is not UTF-8 text.", 422) from exc
    return {"path": safe_path, "size": len(raw), "source_code": source}
