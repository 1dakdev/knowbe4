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


def test_generate_math_question_parses_response(monkeypatch):
    fake_json = '{"question_text": "What is 2 + 2?", "correct_answer": "4"}'
    monkeypatch.setattr(gemini, "_client", lambda: _FakeClient(fake_json))

    result = gemini.generate_math_question(grade_level=1)

    assert result == {"question_text": "What is 2 + 2?", "correct_answer": "4"}


def test_generate_math_question_wraps_errors(monkeypatch):
    def _raise_client():
        raise RuntimeError("network down")

    monkeypatch.setattr(gemini, "_client", _raise_client)

    with pytest.raises(gemini.GeminiError):
        gemini.generate_math_question(grade_level=1)


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
