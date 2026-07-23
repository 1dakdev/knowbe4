import pytest
from sqlalchemy.exc import IntegrityError

from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.student import Student, grade_tier
from app.models.teacher import Teacher


@pytest.fixture()
def school_and_teacher(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    teacher = Teacher(
        school_id=school.id,
        email="teacher@riverside.example",
        hashed_password="hashed",
        full_name="Ms. Jones",
    )
    db_session.add(teacher)
    db_session.flush()
    return school, teacher


def test_create_class_and_student(db_session, school_and_teacher):
    school, teacher = school_and_teacher

    school_class = SchoolClass(
        school_id=school.id, teacher_id=teacher.id, name="Grade 4 Homeroom", grade_level=4
    )
    db_session.add(school_class)
    db_session.flush()

    student = Student(
        school_id=school.id,
        class_id=school_class.id,
        full_name="Maya Chen",
        grade_level=4,
        pin_hash="hashed-pin",
    )
    db_session.add(student)
    db_session.flush()

    assert student.id is not None
    assert student.class_id == school_class.id


def test_student_requires_existing_class(db_session, school_and_teacher):
    school, _teacher = school_and_teacher

    db_session.add(
        Student(
            school_id=school.id,
            class_id=999999,
            full_name="Ghost Student",
            grade_level=4,
            pin_hash="hashed-pin",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "grade_level,expected_tier",
    [(0, "early"), (5, "early"), (6, "late"), (12, "late")],
)
def test_grade_tier(grade_level, expected_tier):
    assert grade_tier(grade_level) == expected_tier
