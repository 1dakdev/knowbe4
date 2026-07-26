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
from app.models.assessment_item import AssessmentItem
from app.models.skill_dimension import SkillDimension
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

# Create demo teacher with proper password hash
teacher = Teacher(school_id=school.id, email="mannie.opoku@gmail.com", full_name="Demo Teacher", hashed_password=hash_secret("1234"))
session.add(teacher)
session.commit()

# Create demo class
demo_class = SchoolClass(
    school_id=school.id,
    teacher_id=teacher.id,
    name="Grade 4",
    grade_level=4,
)
session.add(demo_class)
session.commit()

# Create demo students
students_data = [
    {"name": "Alice Johnson", "pin": "1001"},
    {"name": "Bob Smith", "pin": "1002"},
    {"name": "Charlie Brown", "pin": "1003"},
    {"name": "Diana Prince", "pin": "1004"},
    {"name": "Ethan Hunt", "pin": "1005"},
    {"name": "Fiona Green", "pin": "1006"},
]

students = []
for student_data in students_data:
    student = Student(
        school_id=school.id,
        class_id=demo_class.id,
        full_name=student_data["name"],
        grade_level=4,
        pin_hash=hash_secret(student_data["pin"]),
    )
    session.add(student)
    session.commit()
    students.append(student)

print("Demo data created successfully")
print(f"  School: {school.name}")
print(f"  Teacher: {teacher.full_name} ({teacher.email})")
print(f"  Class: {demo_class.name}")
print(f"  Students:")
for s in students:
    print(f"    - {s.full_name} (ID: {s.id}, PIN: {students_data[students.index(s)]['pin']})")

session.close()
