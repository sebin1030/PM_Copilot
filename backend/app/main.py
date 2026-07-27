from datetime import datetime, timezone
import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pypdf import PdfReader

from .config import AVAILABLE_MODELS, CHAT_MODEL, DOCUMENT_MODEL, UPLOAD_LIMIT_BYTES
from .openai_service import chat, generate_prd, has_api_key
from .renderers import prd_to_markdown
from .schemas import ApprovalRequest, ChatRequest, GenerateRequest, ProjectCreate
from .storage import create_project, get_project, list_projects, save_project, upload_dir, write_document


app = FastAPI(title="PM Copilot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_project(project_id: str) -> dict:
    try:
        return get_project(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")


@app.get("/api/health")
def health():
    return {"status": "ok", "apiKeyConfigured": has_api_key()}


@app.get("/api/models")
def models():
    return {"models": AVAILABLE_MODELS, "defaults": {"chat": CHAT_MODEL, "document": DOCUMENT_MODEL}}


@app.get("/api/projects")
def projects():
    return {"projects": list_projects()}


@app.post("/api/projects", status_code=201)
def new_project(payload: ProjectCreate):
    return {"project": create_project(payload.model_dump())}


@app.get("/api/projects/{project_id}")
def project(project_id: str):
    return {"project": load_project(project_id)}


@app.post("/api/projects/{project_id}/chat")
def project_chat(project_id: str, payload: ChatRequest):
    project_data = load_project(project_id)
    if not has_api_key():
        raise HTTPException(status_code=503, detail=".env에 OPENAI_API_KEY를 설정해 주세요.")
    try:
        answer, model = chat(project_data, payload.message, payload.model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"OpenAI 호출 실패: {error}")
    now = datetime.now(timezone.utc).isoformat()
    project_data["conversations"].extend([
        {"role": "user", "content": payload.message, "createdAt": now},
        {"role": "assistant", "content": answer, "model": model, "createdAt": now},
    ])
    save_project(project_data)
    return {"message": answer, "model": model, "project": project_data}


@app.post("/api/projects/{project_id}/documents/prd/generate")
def create_prd(project_id: str, payload: GenerateRequest):
    project_data = load_project(project_id)
    if not has_api_key():
        raise HTTPException(status_code=503, detail=".env에 OPENAI_API_KEY를 설정해 주세요.")
    try:
        prd, model = generate_prd(project_data, payload.model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"PRD 생성 실패: {error}")
    now = datetime.now(timezone.utc).isoformat()
    document = {"documentId": "DOC-PRD-001", "type": "prd", "status": "NEEDS_APPROVAL", "version": "0.1.0", "model": model, "createdAt": now, "content": prd}
    project_data["documents"]["prd"] = document
    project_data["features"] = prd["features"]
    project_data["requirements"] = prd["requirements"]
    save_project(project_data)
    write_document(project_id, "prd", document)
    return {"document": document, "project": project_data}


@app.post("/api/projects/{project_id}/documents/prd/approval")
def approve_prd(project_id: str, payload: ApprovalRequest):
    project_data = load_project(project_id)
    document = project_data.get("documents", {}).get("prd")
    if not document:
        raise HTTPException(status_code=404, detail="생성된 PRD가 없습니다.")
    document["status"] = payload.status
    document["approvedAt"] = datetime.now(timezone.utc).isoformat() if payload.status == "APPROVED" else None
    project_data["approvals"].append({"documentId": document["documentId"], "status": payload.status, "createdAt": datetime.now(timezone.utc).isoformat()})
    save_project(project_data)
    write_document(project_id, "prd", document)
    return {"document": document, "project": project_data}


@app.get("/api/projects/{project_id}/documents/prd/download", response_class=PlainTextResponse)
def download_prd(project_id: str):
    project_data = load_project(project_id)
    document = project_data.get("documents", {}).get("prd")
    if not document:
        raise HTTPException(status_code=404, detail="생성된 PRD가 없습니다.")
    return PlainTextResponse(prd_to_markdown(document["content"]), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="prd.md"'})


@app.post("/api/projects/{project_id}/upload")
async def upload_pdf(project_id: str, file: UploadFile = File(...)):
    project_data = load_project(project_id)
    if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    content = await file.read(UPLOAD_LIMIT_BYTES + 1)
    if len(content) > UPLOAD_LIMIT_BYTES:
        raise HTTPException(status_code=413, detail="파일은 10MB 이하여야 합니다.")
    try:
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    except Exception:
        raise HTTPException(status_code=400, detail="PDF 내용을 읽을 수 없습니다.")
    safe_name = f"upload-{len(project_data.get('uploads', [])) + 1}.pdf"
    (upload_dir(project_id) / safe_name).write_bytes(content)
    project_data.setdefault("uploads", []).append({"fileName": file.filename, "storedName": safe_name, "extractedText": text[:50000]})
    save_project(project_data)
    return {"fileName": file.filename, "characters": len(text), "project": project_data}

