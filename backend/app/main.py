import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_review import AIReviewError, generate_test_cases, review_source
from app.analysis import analyze, calculate_quality_score
from app.core.config import get_settings
from app.database import Base, engine, get_db
from app.github import (
    GitHubError,
    parse_repository_url,
    repository_file,
    repository_files,
    repository_info,
)
from app.models import Analysis, RevokedAccessToken, User
from app.retention import redact_finding_evidence
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    GitHubRepositoryRequest,
    LoginRequest,
    TokenResponse,
    TestCaseRequest,
    UserCreate,
    UserResponse,
)
from app.security import (
    AccessTokenClaims,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

settings = get_settings()
bearer = HTTPBearer(auto_error=False)


def create_limiter(storage_uri: str) -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        default_limits=["120/minute"],
        storage_uri=storage_uri,
        swallow_errors=False,
    )


limiter = create_limiter(settings.rate_limit_storage_uri.get_secret_value())


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="CodeLens AI API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

MAX_API_BODY_BYTES = settings.max_source_bytes + 16_384


class RequestSizeLimitMiddleware:
    def __init__(self, app, limit: int):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length", b"")
        if content_length.isdigit() and int(content_length) > self.limit:
            await self._reject(send)
            return
        chunks = []
        size = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                if message["type"] == "http.disconnect":
                    return
                continue
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await self._reject(send)
                return
            chunks.append(chunk)
            more_body = message.get("more_body", False)
        body = b"".join(chunks)
        replayed = False

        async def replay_body():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)

    async def _reject(self, send):
        body = b'{"detail":"Request body exceeds the configured size limit."}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})


app.add_middleware(RequestSizeLimitMiddleware, limit=MAX_API_BODY_BYTES)


def current_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AccessTokenClaims:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        return decode_access_token(credentials.credentials)
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.") from exc


def current_user(
    claims: AccessTokenClaims = Depends(current_token_claims),
    db: Session = Depends(get_db),
) -> User:
    revoked = db.get(RevokedAccessToken, claims.token_id)
    if revoked is not None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    user = db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    return user


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(select(1))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable.") from exc
    return {"status": "ok", "database": "connected"}


@app.post("/api/auth/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, body: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    user = User(name=body.name.strip(), email=str(body.email).lower(), hashed_password=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    return TokenResponse(access_token=create_access_token(user.id), user=UserResponse.model_validate(user))


@app.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return TokenResponse(access_token=create_access_token(user.id), user=UserResponse.model_validate(user))


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@app.post("/api/auth/logout", status_code=204)
@limiter.limit("30/minute")
def logout(
    request: Request,
    claims: AccessTokenClaims = Depends(current_token_claims),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        delete(RevokedAccessToken).where(
            RevokedAccessToken.expires_at <= datetime.now(timezone.utc)
        )
    )
    db.add(
        RevokedAccessToken(
            token_id=claims.token_id,
            user_id=user.id,
            expires_at=claims.expires_at,
        )
    )
    db.commit()
    return Response(status_code=204)


def _decode_analysis(row: Analysis) -> AnalysisResponse:
    data = json.loads(row.result_json)
    if not row.source_code:
        data = redact_finding_evidence(data)
    return AnalysisResponse(
        id=row.id,
        language=row.language,
        quality_score=row.quality_score,
        status=row.status,
        created_at=row.created_at or datetime.now(),
        source_code=row.source_code or None,
        **data,
    )


@app.post("/api/analyses", response_model=AnalysisResponse, status_code=201)
@limiter.limit("20/hour")
async def create_analysis(
    request: Request,
    body: AnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AnalysisResponse:
    source_bytes = body.source_code.encode("utf-8")
    if not source_bytes.strip():
        raise HTTPException(status_code=422, detail="Source code cannot be empty.")
    if len(source_bytes) > settings.max_source_bytes:
        raise HTTPException(status_code=413, detail="Source code exceeds the configured size limit.")
    analyzers, findings = analyze(body.language, body.source_code)
    ai_findings: list[dict] = []
    if body.include_ai:
        try:
            ai_findings = await review_source(body.language, body.source_code)
        except AIReviewError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    available_analyzers = [item for item in analyzers if item.available]
    score = calculate_quality_score(len(findings)) if available_analyzers else None
    analysis_status = (
        "completed"
        if len(available_analyzers) == len(analyzers)
        else "partial"
        if available_analyzers or ai_findings
        else "unavailable"
    )
    result_data = {
        "findings": [item.model_dump(mode="json") for item in findings],
        "ai_findings": ai_findings,
        "analyzers": [item.model_dump(mode="json") for item in analyzers],
    }
    retain_source = body.retain_source or settings.store_source_by_default
    persisted_result = result_data if retain_source else redact_finding_evidence(result_data)
    row = Analysis(
        user_id=user.id,
        language=body.language,
        source_code=body.source_code if retain_source else "",
        quality_score=score,
        status=analysis_status,
        result_json=json.dumps(persisted_result),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AnalysisResponse(
        id=row.id,
        language=body.language,
        quality_score=score,
        status=analysis_status,
        findings=findings,
        ai_findings=ai_findings,
        analyzers=analyzers,
        source_code=body.source_code,
        created_at=row.created_at or datetime.now(),
    )


@app.post("/api/test-cases")
@limiter.limit("10/hour")
async def create_test_cases(
    request: Request,
    body: TestCaseRequest,
    user: User = Depends(current_user),
) -> list[dict]:
    del user
    source_bytes = body.source_code.encode("utf-8")
    if not source_bytes.strip():
        raise HTTPException(status_code=422, detail="Source code cannot be empty.")
    if len(source_bytes) > settings.max_source_bytes:
        raise HTTPException(status_code=413, detail="Source code exceeds the configured size limit.")
    try:
        return await generate_test_cases(body.language, body.source_code)
    except AIReviewError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _github_error(exc: GitHubError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@app.post("/api/github/repository")
@limiter.limit("30/minute")
async def inspect_github_repository(
    request: Request,
    body: GitHubRepositoryRequest,
    user: User = Depends(current_user),
) -> dict:
    del user
    try:
        owner, repo = parse_repository_url(body.url)
        repository = await repository_info(owner, repo)
        if repository.get("private") is not False:
            raise HTTPException(status_code=403, detail="Only public GitHub repositories can be analyzed.")
        branch = repository.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise HTTPException(status_code=502, detail="GitHub repository has no default branch.")
        files = await repository_files(owner, repo, branch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubError as exc:
        raise _github_error(exc) from exc
    return {"repository": repository, "files": files}


@app.post("/api/github/file")
@limiter.limit("60/minute")
async def read_github_file(
    request: Request,
    body: GitHubRepositoryRequest,
    path: str,
    user: User = Depends(current_user),
) -> dict:
    del user
    try:
        owner, repo = parse_repository_url(body.url)
        return await repository_file(owner, repo, path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubError as exc:
        raise _github_error(exc) from exc


@app.get("/api/analyses", response_model=list[AnalysisSummary])
def list_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AnalysisSummary]:
    rows = db.scalars(
        select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc()).limit(100)
    )
    return [AnalysisSummary.model_validate(row) for row in rows]


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AnalysisResponse:
    row = db.scalar(select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return _decode_analysis(row)


@app.delete("/api/analyses/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    row = db.scalar(select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
