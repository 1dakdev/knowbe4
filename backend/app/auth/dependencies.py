from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models.teacher import Teacher

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise unauthorized
    if payload.get("role") != "teacher":
        raise unauthorized
    teacher = db.get(Teacher, int(payload["sub"]))
    if teacher is None:
        raise unauthorized
    return teacher
