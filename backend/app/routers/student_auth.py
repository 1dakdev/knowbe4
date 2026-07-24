from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_student
from app.auth.security import create_access_token, verify_secret
from app.config import get_settings
from app.database import get_db
from app.models.student import Student
from app.schemas.auth import StudentLoginIn, Token
from app.schemas.student import StudentOut

router = APIRouter()


@router.post("/auth/student/login", response_model=Token)
def login(payload: StudentLoginIn, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    student = db.get(Student, payload.student_id)
    if student is None or not verify_secret(payload.pin, student.pin_hash):
        raise unauthorized

    settings = get_settings()
    token = create_access_token(
        subject=str(student.id),
        role="student",
        expires_minutes=settings.student_token_expire_minutes,
        extra_claims={"class_id": student.class_id},
    )
    return Token(access_token=token)


@router.get("/auth/student/me", response_model=StudentOut)
def me(current_student: Student = Depends(get_current_student)):
    return current_student
