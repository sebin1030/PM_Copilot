from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    problem: str = ""
    target_users: list[str] = []
    platform: str = "Web"
    purpose: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None


class GenerateRequest(BaseModel):
    model: str | None = None


class ApprovalRequest(BaseModel):
    status: Literal["APPROVED", "REJECTED"]


class ProjectResponse(BaseModel):
    project: dict[str, Any]

