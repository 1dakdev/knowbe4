import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_teacher
from app.auth.security import hash_secret
from app.database import get_db
from app.models.assessment_item import latest_score_for_student
from app.models.school_class import SchoolClass
from app.models.student import Student
from app.models.teacher import Teacher
from app.schemas.school_class import ClassCreateIn, ClassOut, RosterOut
from app.schemas.student import StudentCreateIn, StudentCreatedOut, StudentOut

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
