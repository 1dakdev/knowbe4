from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.teacher import Teacher

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    teacher_count = db.query(Teacher).count()
    return {
        "status": "ok",
        "teachers": teacher_count,
        "demo_ready": teacher_count > 0
    }
