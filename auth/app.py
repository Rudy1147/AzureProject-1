import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from auth_util import create_access_token
from dao import UserDAO
from exceptions import UserRegistrationError, InvalidCredentialsError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

user_dao = UserDAO()
app = FastAPI(title="Auth Service", root_path="/auth")

SERVICE_NAME = "auth-service"

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

@app.exception_handler(UserRegistrationError)
async def handle_registration_error(request: Request, exc: UserRegistrationError):
    logging.warning(f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} rejected a registration attempt: {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.exception_handler(InvalidCredentialsError)
async def handle_invalid_credentials(request: Request, exc: InvalidCredentialsError):
    logging.warning(f"[{SERVICE_NAME}] HTTP {request.method} {request.url.path} rejected a login attempt: {exc}")
    return JSONResponse(status_code=401, content={"detail": str(exc)})

class AuthPayload(BaseModel):
    username: str = Field(..., examples=["engineer_alpha"])
    password: str = Field(..., min_length=6)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@app.post("/register", status_code=201)
async def register_account(payload: AuthPayload):
    user_dao.create_user(username=payload.username, password=payload.password)
    return {"status": "success", "detail": f"Account for user `{payload.username}` has been provisioned"}

@app.post("/login", response_model=TokenResponse, status_code=200)
async def login_and_issue_token(payload: AuthPayload):
    user_dao.authenticate_user(username=payload.username, password=payload.password)
    token = create_access_token(username=payload.username)
    return {"access_token": token, "token_type": "bearer"}