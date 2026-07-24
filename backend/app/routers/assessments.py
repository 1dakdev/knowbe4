from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_student, get_current_teacher
from app.database import get_db
from app.llm import gemini as gemini_client
from app.llm.gemini import GeminiError
from app.models.assessment_item import AssessmentItem
from app.models.school_class import SchoolClass
from app.models.skill_dimension import SkillDimension
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.assessment import AssessmentAnswerIn, AssessmentGradedOut, AssessmentQuestionOut

router = APIRouter()

_MATH_DIMENSION_KEY = "math_reasoning"


def _get_owned_student(class_id: int, student_id: int, teacher: Teacher, db: Session) -> Student:
    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    student = db.get(Student, student_id)
    if student is None or student.class_id != school_class.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.post(
    "/classes/{class_id}/students/{student_id}/assessments",
    response_model=AssessmentQuestionOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_assessment(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(class_id, student_id, current_teacher, db)
    dimension = db.query(SkillDimension).filter(SkillDimension.key == _MATH_DIMENSION_KEY).first()
    if dimension is None:
        raise HTTPException(status_code=500, detail="math_reasoning skill dimension not seeded")

    try:
        generated = gemini_client.generate_question(
            dimension_key=dimension.key,
            dimension_name=dimension.name,
            rubric_description=dimension.rubric_description,
            grade_level=student.grade_level,
        )
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Question generation failed")

    item = AssessmentItem(
        student_id=student.id,
        skill_dimension_id=dimension.id,
        question_text=generated["question_text"],
        correct_answer=generated["correct_answer"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/assessments/{item_id}/answer", response_model=AssessmentGradedOut)
def answer_assessment(
    item_id: int,
    payload: AssessmentAnswerIn,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    item = db.get(AssessmentItem, item_id)
    if item is None or item.student_id != current_student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    if item.answered_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already answered")

    dimension = db.get(SkillDimension, item.skill_dimension_id)

    try:
        graded = gemini_client.grade_answer(
            question_text=item.question_text,
            correct_answer=item.correct_answer,
            student_answer=payload.answer,
            rubric=dimension.rubric_description,
        )
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Grading failed")

    item.student_answer = payload.answer
    item.score = graded["score"]
    item.feedback = graded["feedback"]
    item.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)

    return AssessmentGradedOut(score=item.score, feedback=item.feedback)


@router.get("/auth/student/assessments/pending", response_model=list[AssessmentQuestionOut])
def list_pending_assessments(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return (
        db.query(AssessmentItem)
        .filter(AssessmentItem.student_id == current_student.id, AssessmentItem.answered_at.is_(None))
        .all()
    )
