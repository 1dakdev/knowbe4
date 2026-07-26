#!/usr/bin/env python
"""Initialize demo data for testing the student dashboard."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.database import Base, enable_sqlite_foreign_keys, sqlite_connect_args
from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.student import Student
from app.auth.security import hash_secret

settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=sqlite_connect_args(settings.database_url),
)
enable_sqlite_foreign_keys(engine, settings.database_url)
Base.metadata.create_all(bind=engine)

Session = sessionmaker(bind=engine)
session = Session()

# Clear existing data in correct order (respecting foreign keys)
from app.models.assessment_item import AssessmentItem
session.query(AssessmentItem).delete()
session.query(Student).delete()
session.query(SchoolClass).delete()
session.query(Teacher).delete()
session.query(School).delete()
session.commit()

# Create demo school
school = School(name="Demo School")
session.add(school)
session.commit()

# Create demo teacher (password hash doesn't matter for demo)
teacher = Teacher(school_id=school.id, email="demo@demo.com", full_name="Demo Teacher", hashed_password="")
session.add(teacher)
session.commit()

# Create demo class
demo_class = SchoolClass(
    school_id=school.id,
    teacher_id=teacher.id,
    name="Grade 2",
    grade_level=2,
)
session.add(demo_class)
session.commit()

# Create demo student (ID: 4, PIN: 1234)
demo_student = Student(
    school_id=school.id,
    class_id=demo_class.id,
    full_name="Demo Student",
    grade_level=2,
    pin_hash=hash_secret("1234"),
)
session.add(demo_student)
session.commit()

print("Demo data created successfully")
print(f"  School: {school.name}")
print(f"  Teacher: {teacher.full_name} ({teacher.email})")
print(f"  Class: {demo_class.name}")
print(f"  Student: {demo_student.full_name} (ID: {demo_student.id}, PIN: 1234, Grade: {demo_student.grade_level})")

session.close()
