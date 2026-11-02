from datetime import datetime, timezone
import io
import uuid
from copy import deepcopy

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from pypdf import PdfReader

from .config import ALLOWED_ORIGINS, UPLOAD_LIMIT_BYTES
from .openai_service import chat, generate_prd
from .providers import check_connection, ProviderError
from .connections import session, credential, LOCK
from .auth import require_user
from .supabase_storage import SupabaseStorageError
from .renderers import prd_to_markdown
from .schemas import ApprovalRequest, ChatRequest, GenerateRequest, ProjectCreate, ConnectionRequest
from .storage import create_project, get_project, list_projects, save_project, upload_dir, StorageConflict


app = FastAPI(title="PM Copilot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_project(project_id: str) -> dict:
    try:
        return get_project(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")


@app.exception_handler(StorageConflict)
def conflict_handler(request, error):
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(ProviderError)
def provider_handler(request, error):
    return JSONResponse(status_code=502, content={"detail": str(error)})


@app.exception_handler(SupabaseStorageError)
def supabase_storage_handler(request, error):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "local-single-user"}


def connection_status(connections):
    return {"connections": [{"provider": provider, "model": value["model"]} for provider, value in connections.items()], "storage": "session", "expiresInHours": 8}


@app.get("/api/connections")
def connections(request: Request, response: Response, user=Depends(require_user)):
    return connection_status(session(request, response))


@app.post("/api/connections")
def connect(payload: ConnectionRequest, request: Request, response: Response, user=Depends(require_user)):
    state = session(request, response)
    check_connection(payload.provider, payload.api_key.get_secret_value(), payload.model)
    with LOCK:
        state[payload.provider] = {"key": payload.api_key.get_secret_value(), "model": payload.model}
        return connection_status(state)


@app.delete("/api/connections/{provider}")
def disconnect(provider: str, request: Request, response: Response, user=Depends(require_user)):
    state = session(request, response)
    with LOCK:
        state.pop(provider, None)
        return connection_status(state)


@app.get("/api/projects")
def projects(user=Depends(require_user)):
    return {"projects": list_projects()}


@app.post("/api/projects", status_code=201)
def new_project(payload: ProjectCreate, user=Depends(require_user)):
    return {"project": create_project(payload.model_dump())}


@app.get("/api/projects/{project_id}")
def project(project_id: str, user=Depends(require_user)):
    return {"project": load_project(project_id)}


@app.post("/api/projects/{project_id}/chat")
def project_chat(project_id: str, payload: ChatRequest, request: Request, user=Depends(require_user)):
    project_data = load_project(project_id)
    key = credential(request, payload.provider, payload.model)
    try:
        answer, model = chat(project_data, payload.message, payload.model, payload.provider, key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    now = datetime.now(timezone.utc).isoformat()
    project_data["conversations"].extend([
        {"role": "user", "content": payload.message, "createdAt": now},
        {"role": "assistant", "content": answer, "model": model, "provider": payload.provider, "createdAt": now},
    ])
    project_data = save_project(project_data, expected_version=project_data["metadata"]["updatedAt"])
    return {"message": answer, "model": model, "project": project_data}


@app.post("/api/projects/{project_id}/documents/prd/generate")
def create_prd(project_id: str, payload: GenerateRequest, request: Request, user=Depends(require_user)):
    project_data = load_project(project_id)
    key = credential(request, payload.provider, payload.model)
    try:
        prd, model = generate_prd(project_data, payload.model, payload.provider, key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    now = datetime.now(timezone.utc).isoformat()
    document = {"documentId": f"DOC-PRD-{uuid.uuid4().hex}", "type": "prd", "status": "NEEDS_APPROVAL", "version": project_data.get("prdRevision", 0) + 1, "model": model, "provider": payload.provider, "createdAt": now, "content": prd}
    project_data["prdRevision"] = document["version"]
    document["review"] = review_prd(prd)
    previous = project_data.get("drafts", {}).get("prd")
    if previous:
        project_data.setdefault("documentHistory", []).append(deepcopy(previous))
    project_data.setdefault("drafts", {})["prd"] = document
    project_data = save_project(project_data, expected_version=project_data["metadata"]["updatedAt"])
    return {"document": document, "project": project_data}


def review_prd(prd):
    warnings = []
    if not prd["features"] or not prd["requirements"]:
        warnings.append("기능 또는 요구사항이 비어 있습니다.")
    for item in prd["requirements"]:
        if not item["acceptanceCriteria"] or not all(c.strip() for c in item["acceptanceCriteria"]):
            warnings.append(f"{item['id']}: 수용 기준을 보완해 주세요.")
    if prd["questions"]:
        warnings.append(f"사용자 확인 사항 {len(prd['questions'])}건이 남아 있습니다.")
    return {"warnings": warnings, "kind": "구조 점검", "note": "내용의 정확성·예외 완전성은 사용자 검토가 필요합니다."}


@app.post("/api/projects/{project_id}/documents/prd/approval")
def approve_prd(project_id: str, payload: ApprovalRequest, user=Depends(require_user)):
    project_data = load_project(project_id)
    document = project_data.get("drafts", {}).get("prd")
    if not document or document["status"] != "NEEDS_APPROVAL":
        raise HTTPException(status_code=409, detail="검토할 초안이 없습니다.")
    if document["documentId"] != payload.document_id:
        raise HTTPException(status_code=409, detail="초안이 변경되었습니다. 새로고침 후 검토해 주세요.")
    document["status"] = payload.status
    document["approvedAt"] = datetime.now(timezone.utc).isoformat() if payload.status == "APPROVED" else None
    if payload.status == "APPROVED":
        old = project_data.get("documents", {}).get("prd")
        if old:
            project_data.setdefault("documentHistory", []).append(deepcopy(old))
        project_data["documents"]["prd"] = deepcopy(document)
        project_data["features"] = deepcopy(document["content"]["features"])
        project_data["requirements"] = deepcopy(document["content"]["requirements"])
    project_data["approvals"].append({"documentId": document["documentId"], "status": payload.status, "createdAt": datetime.now(timezone.utc).isoformat()})
    project_data = save_project(project_data, expected_version=project_data["metadata"]["updatedAt"])
    return {"document": document, "project": project_data}


@app.get("/api/projects/{project_id}/documents/prd/download", response_class=PlainTextResponse)
def download_prd(project_id: str, draft: bool = False, user=Depends(require_user)):
    project_data = load_project(project_id)
    document = project_data.get("drafts" if draft else "documents", {}).get("prd")
    if not document:
        raise HTTPException(status_code=404, detail="생성된 PRD가 없습니다.")
    return PlainTextResponse(("<!-- 미확정 초안 -->\n" if document["status"] != "APPROVED" else "") + prd_to_markdown(document["content"]), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="prd.md"'})


@app.post("/api/projects/{project_id}/upload")
async def upload_pdf(project_id: str, file: UploadFile = File(...), user=Depends(require_user)):
    project_data = load_project(project_id)
    if file.content_type != "application/pdf" or not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    content = await file.read(UPLOAD_LIMIT_BYTES + 1)
    if len(content) > UPLOAD_LIMIT_BYTES:
        raise HTTPException(status_code=413, detail="파일은 10MB 이하여야 합니다.")
    try:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    except Exception:
        raise HTTPException(status_code=400, detail="PDF 내용을 읽을 수 없습니다.")
    safe_name = f"upload-{uuid.uuid4().hex}.pdf"
    (upload_dir(project_id) / safe_name).write_bytes(content)
    project_data.setdefault("uploads", []).append({"fileName": file.filename, "storedName": safe_name, "extractedText": text[:50000]})
    project_data = save_project(project_data, expected_version=project_data["metadata"]["updatedAt"])
    return {"fileName": file.filename, "characters": len(text), "project": project_data}

