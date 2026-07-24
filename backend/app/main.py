from fastapi import FastAPI

from app.routers import health, teacher_auth

app = FastAPI(title="K-12 Assessment Platform")

app.include_router(health.router)
app.include_router(teacher_auth.router)
