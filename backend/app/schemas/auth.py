from pydantic import BaseModel, EmailStr


class TeacherSignupIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class TeacherLoginIn(BaseModel):
    email: EmailStr
    password: str


class StudentLoginIn(BaseModel):
    student_id: int
    pin: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
