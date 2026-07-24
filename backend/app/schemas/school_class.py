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
