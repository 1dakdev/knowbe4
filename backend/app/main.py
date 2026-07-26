from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import assessments, classes, health, student_auth, teacher_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    Base.metadata.create_all(bind=engine)
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
