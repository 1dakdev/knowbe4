from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import assessments, classes, health, student_auth, teacher_auth

app = FastAPI(title="KnowBe4")

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


@app.get("/student")
async def student_page():
    static_dir = Path(__file__).parent.parent / "static"
    return FileResponse(static_dir / "student.html", media_type="text/html")


app.mount("/ui", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="ui")
