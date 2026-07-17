import time
import logging
from typing import List
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
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
    try:
        response = await call_next(request)
    except Exception as exc:
        duration = time.time() - start_time
        logging.error(
            f"HTTP {request.method} {request.url.path} failed after {duration:.4f}s"
            f"with an unhandled {exc.__class__.__name__}: {exc}"
        )
        raise
    duration = time.time() - start_time
    message = f"HTTP {request.method} {request.url.path} processed in {duration:.4f}s with status {response.status_code}"
    if response.status_code >= 500:
        logging.error(message)
    elif response.status_code >= 400:
        logging.warning(message)
    else:
        logging.info(message)
    return response

# Centralized exception handling for custom application errors
@app.exception_handler(DatabaseConnectionError)
async def handle_database_connection_error(request: Request, exc: DatabaseConnectionError):
    logging.error(f"HTTP {request.method} {request.url.path} could not reach the database: {exc}")
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


@app.exception_handler(LogCreationError)
async def handle_log_creation_error(request: Request, exc: LogCreationError):
    logging.error(f"HTTP {request.method} {request.url.path} failed to create a log entry: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(UserRegistrationError)
async def handle_user_registration_error(request: Request, exc: UserRegistrationError):
    logging.warning(f"HTTP {request.method} {request.url.path} rejected a registration attempt: {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsError)
async def handle_invalid_credentials_error(request: Request, exc: InvalidCredentialsError):
    logging.warning(f"HTTP {request.method} {request.url.path} rejected a login attempt: {exc}")
    return JSONResponse(status_code=401, content={"detail": str(exc)})

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
    user_dao.create_user(username=payload.username, password=payload.password)
    return {"status": "success", "detail": f"Account for user `{payload.username}` has been provisioned"}

@app.post("/login", response_model=TokenResponse, status_code=200)
async def login_and_issue_token(payload: AuthPayload):
    """Verifies profile match over database and issues JWT"""
    user_dao.authenticate_user(username=payload.username, password=payload.password)
    secure_token = create_access_token(username=payload.username)
    return {"access_token": secure_token, "token_type": "bearer"}

@app.post("/logs", status_code=201)
async def create_system_log(payload: LogPayload, user: dict = Depends(verify_sre_jwt_token)):
    """Protected post route parsing active token payload"""
    log_dao.insert_log(host=payload.host, severity=payload.severity, message=payload.message)
    return {"status": "success", "authenticated_as": user["identity"]}

@app.get("/logs", status_code=200)
async def read_system_logs(user: dict = Depends(verify_sre_jwt_token)):
    return log_dao.get_all_logs()