import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db_cursor

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "demo-only-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

security_optional = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_access_token(user_data: Dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_data["id"]),
        "email": user_data["email"],
        "full_name": user_data["full_name"],
        "role": user_data["role"],
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, email, password_hash, full_name, role FROM users WHERE LOWER(email) = LOWER(%s);",
            (email.strip(),),
        )
        user = cur.fetchone()

    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None

    return {
        "id": str(user["id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> Optional[Dict[str, Any]]:
    """
    Si el cliente envía Authorization: Bearer <token>, valida el JWT y devuelve el usuario.
    Si no envía header, permite operar en modo single-user (cumpliendo Sección 7 del assessment).
    """
    if credentials is None or not credentials.credentials:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {
            "id": payload["sub"],
            "email": payload.get("email", ""),
            "full_name": payload.get("full_name", ""),
            "role": payload.get("role", "plant_engineer"),
        }
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )


def get_current_user(
    user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Dependencia OBLIGATORIA: exige un JWT válido (401 si falta)."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user