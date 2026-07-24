import time
import logging
from fastapi import FastAPI, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth_util import decode_and_verify_token
from dao import SystemLogDAO
from exceptions import DatabaseConnectionError, LogCreationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

log_dao = SystemLogDAO()
app = FastAPI(title="API Service", root_path="/api")
security = HTTPBearer()

SERVICE_NAME = "api-service"

@app.middleware("http")
async def log_request(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration = time.time() - start_time
        logging.error(
            f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} "
            f"failed after {duration:.4f}s with an unhandled {exc.__class__.__name__}: {exc}"
        )
        raise
    duration = time.time() - start_time
    message = f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} processed in {duration:.4f}s with status {response.status_code}"
    (logging.error if response.status_code >= 500 else logging.warning if response.status_code >= 400 else logging.info)(message)
    return response

@app.exception_handler(DatabaseConnectionError)
async def handle_db_error(request: Request, exc: DatabaseConnectionError):
    logging.error(f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} could not reach the database: {exc}")
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

@app.exception_handler(LogCreationError)
async def handle_log_creation_error(request: Request, exc: LogCreationError):
    logging.error(f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} failed to create a log entry: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})

def verify_sre_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_and_verify_token(credentials.credentials)
    return {"identity": payload.get("sub")}

class LogPayload(BaseModel):
    host: str
    severity: str
    message: str

@app.post("/logs", status_code=201)
async def create_system_log(payload: LogPayload, user: dict = Depends(verify_sre_jwt_token)):
    log_dao.insert_log(host=payload.host, severity=payload.severity, message=payload.message)
    return {"status": "success", "authenticated_as": user["identity"]}

@app.get("/logs", status_code=200)
async def read_system_logs(user: dict = Depends(verify_sre_jwt_token)):
    return log_dao.get_all_logs()