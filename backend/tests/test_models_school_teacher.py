import pytest
from sqlalchemy.exc import IntegrityError

from app.models.school import School
from app.models.teacher import Teacher


def test_create_school_and_teacher(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()

    teacher = Teacher(
        school_id=school.id,
        email="ms.jones@riverside.example",
        hashed_password="hashed",
        full_name="Ms. Jones",
    )
    db_session.add(teacher)
    db_session.flush()

    assert teacher.id is not None
    assert teacher.school_id == school.id


def test_teacher_email_must_be_unique(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()

    db_session.add(
        Teacher(
            school_id=school.id,
            email="dupe@riverside.example",
            hashed_password="hashed",
            full_name="First Teacher",
        )
    )
    db_session.flush()

    db_session.add(
        Teacher(
            school_id=school.id,
            email="dupe@riverside.example",
            hashed_password="hashed",
            full_name="Second Teacher",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
