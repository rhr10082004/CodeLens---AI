from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Language = Literal["python", "javascript", "typescript", "java"]


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AnalysisRequest(BaseModel):
    language: Language
    source_code: str = Field(min_length=1)
    include_ai: bool = False
    retain_source: bool = False


class TestCaseRequest(BaseModel):
    language: Language
    source_code: str = Field(min_length=1)


class GitHubRepositoryRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class Finding(BaseModel):
    id: str
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    file_path: str
    line: int | None = None
    evidence: str | None = None
    analyzer: str
    suggested_correction: str | None = None


class AnalyzerStatus(BaseModel):
    name: str
    available: bool
    message: str


class AnalysisResponse(BaseModel):
    id: int
    language: Language
    quality_score: int | None
    status: str
    findings: list[Finding]
    ai_findings: list[dict] = Field(default_factory=list)
    analyzers: list[AnalyzerStatus]
    source_code: str | None
    created_at: datetime


class AnalysisSummary(BaseModel):
    id: int
    language: Language
    quality_score: int | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
