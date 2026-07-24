import pytest

from app.llm import gemini


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text):
        self._text = text

    def generate_content(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.models = _FakeModels(text)


def test_generate_question_math_reasoning_returns_numeric_answer(monkeypatch):
    fake_json = '{"question_text": "What is 2 + 2?", "correct_answer": "4"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_question(
        dimension_key="math_reasoning",
        dimension_name="Mathematical Reasoning",
        rubric_description="0-100: ability to reason through grade-appropriate quantitative problems.",
        grade_level=3,
    )

    assert result == {"question_text": "What is 2 + 2?", "correct_answer": "4"}


def test_generate_question_open_ended_returns_empty_correct_answer(monkeypatch):
    fake_json = '{"question_text": "How would you comfort a friend who is upset?"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_question(
        dimension_key="emotional_intelligence",
        dimension_name="Emotional Intelligence",
        rubric_description="0-100: judgment in scenario-based items about recognizing and responding to emotions.",
        grade_level=3,
    )

    assert result == {
        "question_text": "How would you comfort a friend who is upset?",
        "correct_answer": "",
    }


def test_generate_question_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.generate_question(
            dimension_key="math_reasoning",
            dimension_name="Mathematical Reasoning",
            rubric_description="rubric",
            grade_level=1,
        )


def test_grade_answer_parses_response(monkeypatch):
    fake_json = '{"score": 90, "feedback": "Correct, well done."}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.grade_answer(
        question_text="What is 2 + 2?",
        correct_answer="4",
        student_answer="4",
        rubric="0-100: ability to reason through grade-appropriate quantitative problems.",
    )

    assert result == {"score": 90, "feedback": "Correct, well done."}


def test_grade_answer_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.grade_answer(
            question_text="What is 2 + 2?", correct_answer="4", student_answer="4", rubric="rubric",
        )


def test_grade_answer_with_no_correct_answer_still_grades(monkeypatch):
    fake_json = '{"score": 75, "feedback": "Thoughtful, could be more specific."}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.grade_answer(
        question_text="How would you comfort a friend who is upset?",
        correct_answer="",
        student_answer="I would sit with them and listen.",
        rubric="0-100: judgment in scenario-based items about recognizing and responding to emotions.",
    )

    assert result == {"score": 75, "feedback": "Thoughtful, could be more specific."}


def test_synthesize_profile_summary_parses_response(monkeypatch):
    fake_text = "This student shows strong emotional intelligence and solid math reasoning."
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_text))

    result = gemini.synthesize_profile_summary(
        [
            {"dimension_name": "Mathematical Reasoning", "score": 90, "feedback": "Excellent work."},
            {"dimension_name": "Emotional Intelligence", "score": 85, "feedback": "Thoughtful responses."},
        ]
    )

    assert result == fake_text


def test_synthesize_profile_summary_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.synthesize_profile_summary(
            [{"dimension_name": "Mathematical Reasoning", "score": 90, "feedback": "Excellent."}]
        )
