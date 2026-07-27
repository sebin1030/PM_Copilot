from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from .config import PROJECTS_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", name).strip("-").lower()
    return f"{slug or 'project'}-{uuid.uuid4().hex[:8]}"


def _project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9가-힣_-]+", project_id):
        raise ValueError("올바르지 않은 프로젝트 ID입니다.")
    return PROJECTS_DIR / project_id


def create_project(payload: dict) -> dict:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_id = _safe_id(payload["name"])
    now = utc_now()
    project = {
        "projectId": project_id,
        "projectInfo": {
            "name": payload["name"],
            "description": payload.get("description", ""),
            "problem": payload.get("problem", ""),
            "targetUsers": payload.get("target_users", []),
            "platform": payload.get("platform", "Web"),
            "purpose": payload.get("purpose", ""),
        },
        "goals": [],
        "features": [],
        "requirements": [],
        "documents": {},
        "research": [],
        "dataAnalysis": [],
        "evidenceRefs": [],
        "conversations": [],
        "approvals": [],
        "changeHistory": [],
        "metadata": {"version": "0.1.0", "createdAt": now, "updatedAt": now},
    }
    save_project(project)
    return project


def save_project(project: dict) -> dict:
    project = deepcopy(project)
    project["metadata"]["updatedAt"] = utc_now()
    directory = _project_dir(project["projectId"])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "documents").mkdir(exist_ok=True)
    (directory / "uploads").mkdir(exist_ok=True)
    path = directory / "project.json"
    temporary = directory / "project.json.tmp"
    temporary.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return project


def get_project(project_id: str) -> dict:
    path = _project_dir(project_id) / "project.json"
    if not path.exists():
        raise FileNotFoundError(project_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_projects() -> list[dict]:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for path in PROJECTS_DIR.glob("*/project.json"):
        try:
            project = json.loads(path.read_text(encoding="utf-8"))
            projects.append({
                "projectId": project["projectId"],
                "name": project["projectInfo"]["name"],
                "updatedAt": project["metadata"]["updatedAt"],
                "prdStatus": project.get("documents", {}).get("prd", {}).get("status"),
            })
        except (KeyError, json.JSONDecodeError):
            continue
    return sorted(projects, key=lambda item: item["updatedAt"], reverse=True)


def write_document(project_id: str, document_type: str, content: dict) -> Path:
    directory = _project_dir(project_id) / "documents"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{document_type}.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def upload_dir(project_id: str) -> Path:
    path = _project_dir(project_id) / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path

