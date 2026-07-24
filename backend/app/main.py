from fastapi import FastAPI

from app.routers import classes, health, student_auth, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
app.include_router(classes.router)
app.include_router(student_auth.router)
