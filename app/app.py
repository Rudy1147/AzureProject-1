import time
import logging
from typing import List
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.dao import SystemLogDAO, UserDAO
from app.exceptions import DatabaseConnectionError, LogCreationError, UserRegistrationError, InvalidCredentialsError

# Import cryptographic tools
from app.auth_util import create_access_token, decode_and_verify_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

log_dao = SystemLogDAO()
user_dao = UserDAO(system_log_dao=log_dao)

app = FastAPI(title="FastAPI Demo")
security = HTTPBearer()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def log_request_execution_latency(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    logging.info(f"HTTP {request.method} {request.url.path} processed in {time.time() - start_time:.4f}s")
    return response

class AuthPayload(BaseModel):
    username: str = Field(..., examples=["engineer_alpha"])
    password: str = Field(..., min_length=6, examples=["supersecret123"])

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class LogPayload(BaseModel):
    host: str; severity: str; message: str

def verify_sre_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Interceptor that parses out the bearer toekn and verifies signature fields"""
    token_string = credentials.credentials
    # Validate structure, expiration, and key signature details
    token_payload = decode_and_verify_token(token_string)

    # If successful, returns the subject claim (username)
    return {"identity": token_payload.get("sub")}

@app.post("/register", status_code=201)
async def register_account(payload: AuthPayload):
    try:
        user_dao.create_user(username=payload.username, password=payload.password)
        return {"status": "success", "detail": f"Account for user `{payload.username}` has been provisioned"}
    except UserRegistrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/login", response_model=TokenResponse, status_code=200)
async def login_and_issue_token(payload: AuthPayload):
    """Verifies profile match over database and issue JWT"""
    try:
        user_dao.authenticate_user(username=payload.username, password=payload.password)

        secure_token = create_access_token(username=payload.username)
        return {"access_token": secure_token, "token_type": "bearer"}
    except InvalidCredentialsError as exc:
        return HTTPException(status_code=401, detail=str(exc))

@app.post("/logs", status_code=201)
async def create_system_log(payload: LogPayload, user: dict = Depends(verify_sre_jwt_token)):
    """Protected post route parsing active token payload"""
    try:
        log_dao.insert_log(host=payload.host, severity=payload.severity, message=payload.message)
        return {"status": "success", "authenticated_as": user["identity"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/logs", status_code=200)
async def read_system_logs():
    return log_dao.get_all_logs()