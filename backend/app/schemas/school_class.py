from pydantic import BaseModel

from app.schemas.student import StudentOut


class ClassCreateIn(BaseModel):
    name: str
    grade_level: int


class ClassOut(BaseModel):
    id: int
    name: str
    grade_level: int

    model_config = {"from_attributes": True}


class RosterOut(ClassOut):
    students: list[StudentOut]


class ClassStatsOut(BaseModel):
    total_students: int
    average_score: float | None
    completion_rate: float
    students_struggling: int
    students_on_track: int
    assessments_sent: int
    assessments_completed: int
