from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm import gemini as gemini_client
from app.llm.gemini import GeminiError
from app.models.assessment_item import AssessmentItem
from app.models.student import Student


class ParentQuestionsIn(BaseModel):
    student_name: str


class ParentQuestionsOut(BaseModel):
    student_name: str
    questions: list[str]


router = APIRouter(prefix="/api/parents", tags=["parents"])


@router.post("/questions", response_model=ParentQuestionsOut)
def get_parent_questions(
    payload: ParentQuestionsIn,
    db: Session = Depends(get_db),
):

    student_name = payload.student_name.strip()
    if not student_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student name required")

    student = (
        db.query(Student)
        .filter(Student.full_name.ilike(f"%{student_name}%"))
        .first()
    )

    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    latest_assessment = (
        db.query(AssessmentItem)
        .filter(
            AssessmentItem.student_id == student.id,
            AssessmentItem.answered_at != None
        )
        .order_by(AssessmentItem.answered_at.desc())
        .first()
    )

    if not latest_assessment:
        return ParentQuestionsOut(
            student_name=student.full_name,
            questions=[
                "What was the most interesting thing you learned today?",
                "Can you explain one thing you learned to me?",
                "What part was challenging for you?",
                "Did you help any classmates today?",
                "What are you most excited to learn about next?",
            ]
        )

    topic = latest_assessment.skill_dimension.name if latest_assessment.skill_dimension else "mathematics"

    try:
        questions = gemini_client.generate_parent_conversation_questions(
            student_name=student.full_name,
            grade_level=student.grade_level,
            topic=topic,
            student_score=latest_assessment.score or 0,
        )
        return ParentQuestionsOut(
            student_name=student.full_name,
            questions=questions if questions else [
                "What did you learn today?",
                "What was the easiest part of your lesson?",
                "What part was tricky for you?",
                "Do you have any questions about what we're learning?",
            ]
        )
    except GeminiError:
        return ParentQuestionsOut(
            student_name=student.full_name,
            questions=[
                "What was the most interesting thing you learned today?",
                "Can you teach me one thing you learned?",
                "What was challenging for you?",
                "Who did you work with today?",
                "How are you feeling about what you're learning?",
            ]
        )
