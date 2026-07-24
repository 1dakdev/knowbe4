import json

from google import genai
from google.genai import types

from app.config import get_settings

_MODEL = "gemini-2.0-flash"


class GeminiError(Exception):
    pass


def _client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def generate_math_question(grade_level: int) -> dict:
    prompt = (
        f"Generate one math word problem appropriate for a student in grade {grade_level} "
        "(grade 0 means kindergarten). The problem must have a single numeric correct answer. "
        "Keep it to 1-2 sentences. Scale difficulty to the grade: grades 0-2 use single-step "
        "addition/subtraction with numbers under 20; grades 3-5 use multi-digit arithmetic or "
        "simple multiplication/division; grades 6-8 use multi-step arithmetic or basic algebra; "
        "grades 9-12 use algebra, geometry, or multi-step reasoning."
    )
    try:
        response = _client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "question_text": {"type": "string"},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["question_text", "correct_answer"],
                },
            ),
        )
        data = json.loads(response.text)
        return {"question_text": data["question_text"], "correct_answer": str(data["correct_answer"])}
    except Exception as exc:
        raise GeminiError(f"Question generation failed: {exc}") from exc


def grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> dict:
    prompt = (
        f"Question: {question_text}\n"
        f"Correct answer: {correct_answer}\n"
        f"Student's answer: {student_answer}\n"
        f"Grading rubric: {rubric}\n\n"
        "Score the student's answer from 0 to 100 based on correctness (a numeric answer "
        "equivalent to the correct answer should score highly) and give one brief sentence of "
        "feedback explaining the score."
    )
    try:
        response = _client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer"},
                        "feedback": {"type": "string"},
                    },
                    "required": ["score", "feedback"],
                },
            ),
        )
        data = json.loads(response.text)
        return {"score": int(data["score"]), "feedback": data["feedback"]}
    except Exception as exc:
        raise GeminiError(f"Grading failed: {exc}") from exc
