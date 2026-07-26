from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.assessment_item import AssessmentItem

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    teacher_count = db.query(Teacher).count()
    student_count = db.query(Student).count()
    assessment_count = db.query(AssessmentItem).count()
    return {
        "status": "ok",
        "teachers": teacher_count,
        "students": student_count,
        "assessments": assessment_count,
        "demo_ready": teacher_count > 0 and student_count > 0
    }
