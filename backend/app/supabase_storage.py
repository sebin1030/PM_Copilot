"""RLS-protected project persistence through the Supabase REST API."""
import json

import httpx

from .auth import current_access_token
from .config import SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL


class SupabaseStorageError(Exception):
    pass


def _headers():
    token = current_access_token()
    if not token:
        raise SupabaseStorageError("로그인 세션이 필요합니다.")
    return {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _request(method: str, path: str, *, body=None):
    try:
        with httpx.Client(timeout=15) as client:
            response = client.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers=_headers(), json=body)
    except httpx.HTTPError:
        raise SupabaseStorageError("프로젝트 저장소에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None
    if response.status_code >= 400:
        raise SupabaseStorageError("프로젝트를 저장하거나 불러오지 못했습니다. 권한과 DB 설정을 확인해 주세요.")
    try:
        return response.json()
    except ValueError:
        return None


def create(project: dict) -> dict:
    records = _request("POST", "projects", body={"project_id": project["projectId"], "payload": project})
    if not records:
        raise SupabaseStorageError("프로젝트 저장 결과를 받지 못했습니다.")
    return records[0]["payload"]


def get(project_id: str) -> dict:
    records = _request("GET", f"projects?project_id=eq.{project_id}&select=payload")
    if not records:
        raise FileNotFoundError(project_id)
    return records[0]["payload"]


def list_all() -> list[dict]:
    records = _request("GET", "projects?select=payload&order=updated_at.desc")
    return [row["payload"] for row in records]


def save(project: dict, expected_version: str | None) -> dict:
    # RLS scopes this request to the signed-in owner. The backend still rejects
    # stale versions before writing; a later migration can add an RPC for atomic CAS.
    current = get(project["projectId"])
    if expected_version and current.get("metadata", {}).get("updatedAt") != expected_version:
        from .storage import StorageConflict
        raise StorageConflict("프로젝트가 변경되었습니다. 새로고침 후 다시 시도해 주세요.")
    records = _request("PATCH", f"projects?project_id=eq.{project['projectId']}", body={"payload": project})
    if not records:
        raise SupabaseStorageError("프로젝트 저장 결과를 받지 못했습니다.")
    return records[0]["payload"]
