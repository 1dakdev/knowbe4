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
from app.schemas.assessment import (
    AssessmentAnswerIn,
    AssessmentGradedOut,
    AssessmentQuestionOut,
    AssessFullClassIn,
    AssessFullClassOut,
)
from pydantic import BaseModel


class TeachingRecommendationsOut(BaseModel):
    teaching_approach: str
    practice_activities: str
    resources: str
    learning_style: str
    next_steps: str


router = APIRouter()

_SUBJECT_DIMENSIONS = {
    "math": "math_reasoning",
    "english": "english_literacy",
    "science": "science_reasoning",
    "social-studies": "social_studies",
    "art": "arts_creativity",
    "pe": "physical_education",
    "music": "music_literacy",
    "computer-science": "computer_science",
}


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

    # Try to use math dimension, or create it
    dimension_key = "math_reasoning"
    dimension = db.query(SkillDimension).filter(SkillDimension.key == dimension_key).first()
    if dimension is None:
        dimension = SkillDimension(
            key=dimension_key,
            name="Math Reasoning",
            rubric_description="Ability to solve mathematical problems and reason through solutions",
        )
        db.add(dimension)
        db.flush()

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


@router.post("/classes/{class_id}/students/{student_id}/assess-profile")
def assess_full_profile(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    from app.models.school_class import SchoolClass
    from app.models.student import Student

    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    student = db.get(Student, student_id)
    if student is None or student.class_id != school_class.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    dimensions = db.query(SkillDimension).all()
    if not dimensions:
        raise HTTPException(status_code=500, detail="No skill dimensions available")

    created = []
    failed = []

    for dimension in dimensions:
        try:
            item = AssessmentItem(
                student_id=student.id,
                skill_dimension_id=dimension.id,
                question_text=f"Question for {dimension.name}: Please demonstrate your knowledge of this skill.",
                correct_answer="Sample answer",
            )
            db.add(item)
            created.append(dimension.name)
        except Exception as e:
            failed.append(dimension.name)

    db.commit()
    return {"created": created, "failed": failed}


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


@router.post("/classes/{class_id}/assess", response_model=AssessFullClassOut)
def assess_full_class(
    class_id: int,
    payload: AssessFullClassIn,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    subject = payload.subject
    topic = payload.topic

    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != current_teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    students = db.query(Student).filter(Student.class_id == class_id).all()
    if not students:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No students in class")

    # Get the dimension key for the subject
    dimension_key = _SUBJECT_DIMENSIONS.get(subject)
    if not dimension_key:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject}")

    # Try to find existing dimension, or create a default one
    dimension = db.query(SkillDimension).filter(SkillDimension.key == dimension_key).first()
    if dimension is None:
        # Create dimension if it doesn't exist
        subject_display = subject.replace("-", " ").title()
        dimension = SkillDimension(
            key=dimension_key,
            name=f"{subject_display} - {topic}",
            rubric_description=f"Assessment for {subject_display}: {topic}",
        )
        db.add(dimension)
        db.flush()

    # Hardcoded test questions by subject
    test_questions = {
        "math": {
            "question": f"Solve this {topic} problem: If you have 24 apples and divide them equally among 4 friends, how many does each friend get?",
            "answer": "6"
        },
        "science": {
            "question": f"Explain the importance of {topic} in daily life and provide two examples.",
            "answer": "Examples may vary but should include relevant applications"
        },
        "english": {
            "question": f"Write a short paragraph about {topic} using at least 3 descriptive adjectives.",
            "answer": "Student response should be descriptive and relevant"
        },
        "social-studies": {
            "question": f"Describe the historical significance of {topic} and its impact on society.",
            "answer": "Response should show understanding of historical context"
        },
        "art": {
            "question": f"Create or describe an artwork inspired by {topic}. What materials would you use?",
            "answer": "Creative response with reasoning"
        },
        "pe": {
            "question": f"Explain how {topic} contributes to physical fitness and list 3 benefits.",
            "answer": "Should demonstrate understanding of fitness concepts"
        },
        "music": {
            "question": f"Identify musical elements in {topic} and explain their purpose.",
            "answer": "Should show understanding of musical theory"
        },
        "computer-science": {
            "question": f"Describe how {topic} is used in computer programming. Provide an example.",
            "answer": "Response should demonstrate technical understanding"
        },
    }

    question_data = test_questions.get(subject, test_questions["science"])

    count = 0
    for student in students:
        try:
            item = AssessmentItem(
                student_id=student.id,
                skill_dimension_id=dimension.id,
                question_text=question_data["question"],
                correct_answer=question_data["answer"],
            )
            db.add(item)
            count += 1
        except Exception as e:
            pass

    db.commit()
    return {"count": count}


@router.get("/classes/{class_id}/students/{student_id}/teaching-recommendations", response_model=TeachingRecommendationsOut)
def get_student_teaching_recommendations(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(class_id, student_id, current_teacher, db)

    item = (
        db.query(AssessmentItem)
        .filter(AssessmentItem.student_id == student.id, AssessmentItem.answered_at != None)
        .order_by(AssessmentItem.answered_at.desc())
        .first()
    )

    if item is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No answered assessments found")

    try:
        recommendations = gemini_client.generate_teaching_recommendations(
            student_name=student.full_name,
            grade_level=student.grade_level,
            topic="Math",
            student_score=item.score,
            student_answer=item.student_answer,
            correct_answer=item.correct_answer,
            question_text=item.question_text,
            feedback=item.feedback,
        )
        return TeachingRecommendationsOut(**recommendations)
    except GeminiError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to generate recommendations")
