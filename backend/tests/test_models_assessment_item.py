import pytest
from sqlalchemy.exc import IntegrityError

from app.models.assessment_item import AssessmentItem, latest_score_for_student
from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.skill_dimension import SkillDimension
from app.models.student import Student
from app.models.teacher import Teacher


@pytest.fixture()
def student_and_dimension(db_session):
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    teacher = Teacher(
        school_id=school.id, email="t@riverside.example", hashed_password="hashed", full_name="Teacher"
    )
    db_session.add(teacher)
    db_session.flush()
    school_class = SchoolClass(school_id=school.id, teacher_id=teacher.id, name="Grade 4", grade_level=4)
    db_session.add(school_class)
    db_session.flush()
    student = Student(
        school_id=school.id, class_id=school_class.id, full_name="Maya Chen", grade_level=4,
        pin_hash="hashed-pin",
    )
    db_session.add(student)
    dimension = SkillDimension(
        key="math_reasoning", name="Mathematical Reasoning", rubric_description="0-100: ..."
    )
    db_session.add(dimension)
    db_session.flush()
    return student, dimension


def test_create_assessment_item(db_session, student_and_dimension):
    student, dimension = student_and_dimension

    item = AssessmentItem(
        student_id=student.id,
        skill_dimension_id=dimension.id,
        question_text="What is 2 + 2?",
        correct_answer="4",
    )
    db_session.add(item)
    db_session.flush()

    assert item.id is not None
    assert item.score is None
    assert item.answered_at is None


def test_assessment_item_requires_existing_student(db_session, student_and_dimension):
    _student, dimension = student_and_dimension

    db_session.add(
        AssessmentItem(
            student_id=999999,
            skill_dimension_id=dimension.id,
            question_text="What is 2 + 2?",
            correct_answer="4",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_latest_score_for_student_returns_none_when_no_scores(db_session, student_and_dimension):
    student, _dimension = student_and_dimension
    assert latest_score_for_student(student.id, db_session) is None


def test_latest_score_for_student_returns_most_recent_score(db_session, student_and_dimension):
    student, dimension = student_and_dimension

    db_session.add(
        AssessmentItem(
            student_id=student.id, skill_dimension_id=dimension.id, question_text="Q1",
            correct_answer="4", score=60,
        )
    )
    db_session.flush()
    db_session.add(
        AssessmentItem(
            student_id=student.id, skill_dimension_id=dimension.id, question_text="Q2",
            correct_answer="4", score=90,
        )
    )
    db_session.flush()

    assert latest_score_for_student(student.id, db_session) == 90
