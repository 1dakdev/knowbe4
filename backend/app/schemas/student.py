from pydantic import BaseModel


class StudentCreateIn(BaseModel):
    full_name: str
    grade_level: int


class StudentOut(BaseModel):
    id: int
    full_name: str
    grade_level: int

    model_config = {"from_attributes": True}


class StudentCreatedOut(StudentOut):
    pin: str
