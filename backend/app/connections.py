"""Single-process local MVP: per-browser credentials expire after eight hours."""
import secrets
import time
from threading import RLock
from fastapi import HTTPException, Request, Response

SESSIONS = {}
LOCK = RLock()
TTL = 8 * 60 * 60


def session(request: Request, response: Response):
    with LOCK:
        now = time.time()
        for token in list(SESSIONS):
            if SESSIONS[token]["expires"] <= now:
                del SESSIONS[token]
        token = request.cookies.get("pm_session")
        if token not in SESSIONS:
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {"expires": now + TTL, "connections": {}}
            response.set_cookie("pm_session", token, httponly=True, samesite="strict", secure=request.url.scheme == "https", max_age=TTL, path="/api")
        response.headers["Cache-Control"] = "no-store"
        return SESSIONS[token]["connections"]


def credential(request, provider, model):
    with LOCK:
        state = SESSIONS.get(request.cookies.get("pm_session"), {})
        connection = state.get("connections", {}).get(provider)
        if state.get("expires", 0) <= time.time() or not connection:
            raise HTTPException(400, "설정에서 해당 AI를 연결해 주세요. 연결은 8시간 후 만료됩니다.")
        if connection["model"] != model:
            raise HTTPException(400, "모델이 변경되었습니다. 연결 설정을 다시 확인해 주세요.")
        return connection["key"]
