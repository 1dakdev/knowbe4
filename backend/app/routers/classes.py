import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_teacher
from app.auth.security import hash_secret
from app.database import get_db
from app.llm import gemini as gemini_client
from app.models.assessment_item import AssessmentItem, latest_score_for_student
from app.models.school_class import SchoolClass
from app.models.skill_dimension import SkillDimension
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.school_class import ClassCreateIn, ClassOut, RosterOut, ClassStatsOut
from app.schemas.student import StudentCreateIn, StudentCreatedOut, StudentOut, StudentProfileOut, StudentProfileDimensionOut

router = APIRouter()


def _get_owned_class(class_id: int, teacher: Teacher, db: Session) -> SchoolClass:
    school_class = db.get(SchoolClass, class_id)
    if school_class is None or school_class.teacher_id != teacher.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return school_class


@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreateIn,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = SchoolClass(
        school_id=current_teacher.school_id,
        teacher_id=current_teacher.id,
        name=payload.name,
        grade_level=payload.grade_level,
    )
    db.add(school_class)
    db.commit()
    db.refresh(school_class)
    return school_class


@router.get("/classes", response_model=list[ClassOut])
def list_classes(
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    return db.query(SchoolClass).filter(SchoolClass.teacher_id == current_teacher.id).all()


@router.get("/classes/{class_id}", response_model=RosterOut)
def get_roster(
    class_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    students = db.query(Student).filter(Student.class_id == school_class.id).all()
    student_outs = [
        StudentOut(
            id=s.id,
            full_name=s.full_name,
            grade_level=s.grade_level,
            latest_score=latest_score_for_student(s.id, db),
        )
        for s in students
    ]
    return RosterOut(
        id=school_class.id,
        name=school_class.name,
        grade_level=school_class.grade_level,
        students=student_outs,
    )


@router.post(
    "/classes/{class_id}/students", response_model=StudentCreatedOut, status_code=status.HTTP_201_CREATED
)
def add_student(
    class_id: int,
    payload: StudentCreateIn,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    pin = f"{secrets.randbelow(10000):04d}"

    student = Student(
        school_id=school_class.school_id,
        class_id=school_class.id,
        full_name=payload.full_name,
        grade_level=payload.grade_level,
        pin_hash=hash_secret(pin),
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return StudentCreatedOut(
        id=student.id, full_name=student.full_name, grade_level=student.grade_level, pin=pin
    )


@router.get("/classes/{class_id}/students/{student_id}/profile", response_model=StudentProfileOut)
def get_student_profile(
    class_id: int,
    student_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    student = db.get(Student, student_id)
    if student is None or student.class_id != school_class.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    dimensions = db.query(SkillDimension).all()
    dimension_results = []

    for dimension in dimensions:
        latest_assessment = (
            db.query(AssessmentItem)
            .filter(AssessmentItem.student_id == student_id, AssessmentItem.skill_dimension_id == dimension.id)
            .order_by(AssessmentItem.created_at.desc())
            .first()
        )

        if latest_assessment is None:
            dimension_results.append({
                "dimension_name": dimension.name,
                "score": None,
                "feedback": None,
                "available": False,
            })
        elif latest_assessment.answered_at is None:
            dimension_results.append({
                "dimension_name": dimension.name,
                "score": None,
                "feedback": None,
                "available": True,
            })
        else:
            dimension_results.append({
                "dimension_name": dimension.name,
                "score": latest_assessment.score,
                "feedback": latest_assessment.feedback,
                "available": True,
            })

    summary = "No assessments yet. Student will receive personalized learning insights once assessments are completed."
    if any(r["score"] is not None for r in dimension_results):
        try:
            summary = gemini_client.synthesize_profile_summary(dimension_results)
        except Exception:
            summary = "Assessment results available. Click 'Assess full profile' to generate personalized insights."

    dimensions_out = [
        StudentProfileDimensionOut(
            name=r["dimension_name"],
            available=r["available"],
            latest_score=r["score"],
            latest_feedback=r["feedback"],
        )
        for r in dimension_results
    ]

    return StudentProfileOut(summary=summary, dimensions=dimensions_out)


@router.get("/classes/{class_id}/stats", response_model=ClassStatsOut)
def get_class_stats(
    class_id: int,
    current_teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    school_class = _get_owned_class(class_id, current_teacher, db)
    students = db.query(Student).filter(Student.class_id == class_id).all()

    total_students = len(students)
    if total_students == 0:
        return ClassStatsOut(
            total_students=0,
            average_score=None,
            completion_rate=0.0,
            students_struggling=0,
            students_on_track=0,
            assessments_sent=0,
            assessments_completed=0,
        )

    scores = []
    students_struggling = 0
    students_on_track = 0
    assessments_sent = 0
    assessments_completed = 0

    for student in students:
        assessments = db.query(AssessmentItem).filter(AssessmentItem.student_id == student.id).all()
        assessments_sent += len(assessments)

        if assessments:
            completed = [a for a in assessments if a.answered_at is not None]
            assessments_completed += len(completed)

            if completed:
                avg_score = sum(a.score for a in completed if a.score is not None) / len(completed)
                scores.append(avg_score)

                if avg_score < 70:
                    students_struggling += 1
                elif avg_score >= 80:
                    students_on_track += 1

    average_score = sum(scores) / len(scores) if scores else None
    completion_rate = (assessments_completed / assessments_sent * 100) if assessments_sent > 0 else 0.0

    return ClassStatsOut(
        total_students=total_students,
        average_score=average_score,
        completion_rate=completion_rate,
        students_struggling=students_struggling,
        students_on_track=students_on_track,
        assessments_sent=assessments_sent,
        assessments_completed=assessments_completed,
    )
