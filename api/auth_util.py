import os
from fastapi import HTTPException, status
import jwt

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "7bca9c84e2a3928e1d2c4b5d6e7f8a90123456789abcdef0123456789abcdef")
JWT_ALGORITHM = "HS256"

def decode_and_verify_token(token: str) -> dict:
    """Decodes token payload and validates signatures and time claims"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please re-authenticate",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed or invalid authorization token signature",
            headers={"WWW-Authenticate": "Bearer"}
        )