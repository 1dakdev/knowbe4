import json

from google import genai
from google.genai import types

from app.config import get_settings

_MODEL = "gemini-2.5-flash"


class GeminiError(Exception):
    pass


def _client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def generate_question(
    dimension_key: str, dimension_name: str, rubric_description: str, grade_level: int, topic: str = None
) -> dict:
    if dimension_key == "math_reasoning":
        topic_note = f" The topic is: {topic}." if topic else ""
        prompt = (
            f"Generate one math word problem appropriate for a student in grade {grade_level} "
            "(grade 0 means kindergarten). The problem must have a single numeric correct answer. "
            "Keep it to 1-2 sentences. Scale difficulty to the grade: grades 0-2 use single-step "
            "addition/subtraction with numbers under 20; grades 3-5 use multi-digit arithmetic or "
            "simple multiplication/division; grades 6-8 use multi-step arithmetic or basic algebra; "
            f"grades 9-12 use algebra, geometry, or multi-step reasoning.{topic_note}"
        )
        schema = {
            "type": "object",
            "properties": {
                "question_text": {"type": "string"},
                "correct_answer": {"type": "string"},
            },
            "required": ["question_text", "correct_answer"],
        }
    else:
        topic_note = f" Focus on this topic: {topic}." if topic else ""
        prompt = (
            f"Generate one assessment question about {topic if topic else dimension_name} "
            f"appropriate for a student in grade {grade_level} (grade 0 means kindergarten). "
            "Keep it to 2-4 sentences, including any scenario or short passage needed. "
            "The question should be graded based on understanding and critical thinking."
        )
        schema = {
            "type": "object",
            "properties": {"question_text": {"type": "string"}},
            "required": ["question_text"],
        }

    try:
        client = _client()
        response = client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        data = json.loads(response.text)
        if dimension_key == "math_reasoning":
            return {"question_text": data["question_text"], "correct_answer": str(data["correct_answer"])}
        return {"question_text": data["question_text"], "correct_answer": ""}
    except Exception as exc:
        raise GeminiError(f"Question generation failed: {exc}") from exc


def grade_answer(question_text: str, correct_answer: str, student_answer: str, rubric: str) -> dict:
    if correct_answer:
        answer_line = f"Correct answer: {correct_answer}\n"
        correctness_note = "a numeric answer equivalent to the correct answer should score highly"
    else:
        answer_line = ""
        correctness_note = "there is no single correct answer — grade based solely on the rubric"
    prompt = (
        f"Question: {question_text}\n"
        f"{answer_line}"
        f"Student's answer: {student_answer}\n"
        f"Grading rubric: {rubric}\n\n"
        f"Score the student's answer from 0 to 100 based on correctness ({correctness_note}) "
        "and give one brief sentence of feedback explaining the score."
    )
    try:
        client = _client()
        response = client.models.generate_content(
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
        score = max(0, min(100, int(data["score"])))
        return {"score": score, "feedback": data["feedback"]}
    except Exception as exc:
        raise GeminiError(f"Grading failed: {exc}") from exc


def synthesize_profile_summary(results: list[dict]) -> str:
    lines = "\n".join(
        f"- {r['dimension_name']}: {r['score']}/100 — {r['feedback']}" for r in results
    )
    prompt = (
        "Here are a student's assessment results across several skill dimensions:\n"
        f"{lines}\n\n"
        "Write a short paragraph (3-4 sentences) for their teacher summarizing this student's "
        "strengths, where they're struggling, and how they seem to learn best, based only on "
        "this data. Be specific and actionable, not generic."
    )
    try:
        client = _client()
        response = client.models.generate_content(model=_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as exc:
        raise GeminiError(f"Profile summary failed: {exc}") from exc
