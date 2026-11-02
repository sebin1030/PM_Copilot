from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    problem: str = ""
    target_users: list[str] = []
    platform: str = "Web"
    purpose: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=120)
    provider: Literal["openai", "anthropic", "gemini"] = "openai"


class GenerateRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    provider: Literal["openai", "anthropic", "gemini"] = "openai"


class ApprovalRequest(BaseModel):
    document_id: str = Field(min_length=1)
    status: Literal["APPROVED", "REJECTED"]


class ProjectResponse(BaseModel):
    project: dict[str, Any]



class ConnectionRequest(BaseModel):
    provider: Literal["openai", "anthropic", "gemini"]
    model: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    api_key: SecretStr = Field(min_length=1, max_length=512)
