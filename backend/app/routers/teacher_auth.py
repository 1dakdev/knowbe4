from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_teacher
from app.auth.security import create_access_token, hash_secret, verify_secret
from app.config import get_settings
from app.database import get_db
from app.models.school import School
from app.models.teacher import Teacher
from app.schemas.auth import TeacherLoginIn, TeacherSignupIn, Token
from app.schemas.teacher import TeacherOut

router = APIRouter()


@router.post("/teachers/signup", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def signup(payload: TeacherSignupIn, db: Session = Depends(get_db)):
    existing = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    school = db.query(School).first()
    if school is None:
        raise HTTPException(status_code=500, detail="No school configured for this pilot")

    teacher = Teacher(
        school_id=school.id,
        email=payload.email,
        hashed_password=hash_secret(payload.password),
        full_name=payload.full_name,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.post("/auth/teacher/login", response_model=Token)
def login(payload: TeacherLoginIn, db: Session = Depends(get_db)):
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    teacher = db.query(Teacher).filter(Teacher.email == payload.email).first()
    if teacher is None or not verify_secret(payload.password, teacher.hashed_password):
        raise unauthorized

    settings = get_settings()
    token = create_access_token(
        subject=str(teacher.id), role="teacher", expires_minutes=settings.access_token_expire_minutes
    )
    return Token(access_token=token)


@router.get("/teachers/me", response_model=TeacherOut)
def me(current_teacher: Teacher = Depends(get_current_teacher)):
    return current_teacher
