from pydantic import BaseModel


class TeacherOut(BaseModel):
    id: int
    email: str
    full_name: str

    model_config = {"from_attributes": True}
