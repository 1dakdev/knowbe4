from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import assessments, classes, health, student_auth, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
app.include_router(classes.router)
app.include_router(student_auth.router)
app.include_router(assessments.router)

app.mount("/ui", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="ui")
