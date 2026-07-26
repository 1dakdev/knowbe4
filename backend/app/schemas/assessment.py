from pydantic import BaseModel


class AssessmentQuestionOut(BaseModel):
    id: int
    question_text: str

    model_config = {"from_attributes": True}


class AssessmentAnswerIn(BaseModel):
    answer: str


class AssessmentGradedOut(BaseModel):
    score: int
    feedback: str


class AssessFullClassIn(BaseModel):
    subject: str
    topic: str


class AssessFullClassOut(BaseModel):
    count: int
