from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine
from app.routers import assessments, classes, health, student_auth, teacher_auth
from app.models.school import School
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.models.student import Student
from app.auth.security import hash_secret


def _init_demo_data():
    """Initialize demo data if database is empty."""
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if teachers exist
    if session.query(Teacher).first() is not None:
        return

    # Create demo school
    school = School(name="Demo School")
    session.add(school)
    session.commit()

    # Create demo teacher
    teacher = Teacher(
        school_id=school.id,
        email="mannie.opoku@gmail.com",
        full_name="Demo Teacher",
        hashed_password=hash_secret("1234")
    )
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
        ("Alice Johnson", "alice@demo.com", "1234"),
        ("Bob Smith", "bob@demo.com", "5678"),
        ("Charlie Brown", "charlie@demo.com", "9012"),
        ("Diana Prince", "diana@demo.com", "3456"),
        ("Evan Davis", "evan@demo.com", "7890"),
    ]

    for name, email, pin in students_data:
        student = Student(
            class_id=demo_class.id,
            full_name=name,
            email=email,
            student_pin=pin,
            grade_level=4,
        )
        session.add(student)

    session.commit()
    session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and demo data
    Base.metadata.create_all(bind=engine)
    _init_demo_data()
    yield
    # Shutdown
    pass


app = FastAPI(title="KnowBe4", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(teacher_auth.router)
app.include_router(classes.router)
app.include_router(student_auth.router)
app.include_router(assessments.router)


@app.get("/")
async def root():
    static_dir = Path(__file__).parent.parent / "static"
    return FileResponse(static_dir / "index.html", media_type="text/html")


@app.get("/student")
async def student_page():
    static_dir = Path(__file__).parent.parent / "static"
    return FileResponse(static_dir / "student.html", media_type="text/html")


app.mount("/ui", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="ui")
