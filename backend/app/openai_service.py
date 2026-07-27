import json
import os

from openai import OpenAI

from .config import AVAILABLE_MODELS, CHAT_MODEL, DOCUMENT_MODEL


PRD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "problem": {"type": "string"},
        "targetUsers": {"type": "array", "items": {"type": "string"}},
        "goals": {"type": "array", "items": {"type": "string"}},
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["P0", "P1", "P2"]},
                },
                "required": ["id", "name", "description", "priority"],
                "additionalProperties": False,
            },
        },
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "acceptanceCriteria": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "title", "description", "acceptanceCriteria"],
                "additionalProperties": False,
            },
        },
        "successMetrics": {"type": "array", "items": {"type": "string"}},
        "outOfScope": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "summary", "problem", "targetUsers", "goals", "features", "requirements", "successMetrics", "outOfScope", "assumptions", "questions"],
    "additionalProperties": False,
}


def has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def ensure_model(model: str | None, default: str) -> str:
    allowed = {item["id"] for item in AVAILABLE_MODELS}
    selected = model or default
    if selected not in allowed:
        raise ValueError("지원하지 않는 모델입니다.")
    return selected


def chat(project: dict, message: str, model: str | None = None) -> tuple[str, str]:
    selected = ensure_model(model, CHAT_MODEL)
    client = OpenAI()
    context = {
        "projectInfo": project["projectInfo"],
        "goals": project.get("goals", []),
        "features": project.get("features", []),
        "requirements": project.get("requirements", []),
    }
    response = client.responses.create(
        model=selected,
        reasoning={"effort": "low"},
        instructions=(
            "너는 PM Copilot의 Intake Agent다. 사용자의 아이디어를 구체화하고 빠진 정보를 질문한다. "
            "확인되지 않은 사실을 확정하지 말고, 한 번에 가장 중요한 질문을 최대 3개만 한다. 한국어로 간결하게 답한다."
        ),
        input=f"현재 Project JSON:\n{json.dumps(context, ensure_ascii=False)}\n\n사용자 메시지:\n{message}",
    )
    return response.output_text, selected


def generate_prd(project: dict, model: str | None = None) -> tuple[dict, str]:
    selected = ensure_model(model, DOCUMENT_MODEL)
    client = OpenAI()
    response = client.responses.create(
        model=selected,
        reasoning={"effort": "medium"},
        instructions=(
            "너는 PRD 작성 전문 PM이다. Project JSON과 대화 내용을 근거로 실행 가능한 PRD를 작성한다. "
            "근거가 없는 내용은 assumptions에, 추가 확인이 필요한 내용은 questions에 기록한다. "
            "기능 ID는 FEAT-001, 요구사항 ID는 REQ-001 형식으로 작성한다."
        ),
        input=json.dumps(project, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "pm_copilot_prd",
                "strict": True,
                "schema": PRD_SCHEMA,
            }
        },
    )
    return json.loads(response.output_text), selected

