from app.models.school import School
from app.models.skill_dimension import SkillDimension


def _seed_math_dimension(db_session):
    if db_session.query(SkillDimension).filter(SkillDimension.key == "math_reasoning").first() is None:
        db_session.add(
            SkillDimension(
                key="math_reasoning",
                name="Mathematical Reasoning",
                rubric_description="0-100: ability to reason through grade-appropriate quantitative problems.",
            )
        )
        db_session.commit()


def _setup_class_with_student(client, db_session, email="assess@riverside.example"):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()
    _seed_math_dimension(db_session)

    client.post(
        "/teachers/signup", json={"email": email, "password": "correct-horse", "full_name": "Teacher"}
    )
    login = client.post("/auth/teacher/login", json={"email": email, "password": "correct-horse"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    class_response = client.post("/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers)
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    ).json()
    return headers, class_id, student_response["id"], student_response["pin"]


def _stub_generate(monkeypatch, question_text="What is 2 + 2?", correct_answer="4"):
    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.generate_question",
        lambda dimension_key, dimension_name, rubric_description, grade_level: {
            "question_text": question_text,
            "correct_answer": correct_answer,
        },
    )


def test_teacher_generates_assessment_for_student(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)

    response = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["question_text"] == "What is 2 + 2?"
    assert "correct_answer" not in body
    assert "id" in body


def test_generate_assessment_requires_owned_student(client, db_session, monkeypatch):
    headers_a, class_id_a, student_id_a, _pin = _setup_class_with_student(
        client, db_session, email="a@riverside.example"
    )
    client.post(
        "/teachers/signup", json={"email": "b@riverside.example", "password": "correct-horse", "full_name": "B"}
    )
    login_b = client.post(
        "/auth/teacher/login", json={"email": "b@riverside.example", "password": "correct-horse"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    _stub_generate(monkeypatch)

    response = client.post(
        f"/classes/{class_id_a}/students/{student_id_a}/assessments", headers=headers_b
    )

    assert response.status_code == 404


def test_generate_assessment_returns_502_on_gemini_failure(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)

    from app.llm.gemini import GeminiError

    def _raise(dimension_key, dimension_name, rubric_description, grade_level):
        raise GeminiError("boom")

    monkeypatch.setattr("app.routers.assessments.gemini_client.generate_question", _raise)

    response = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    assert response.status_code == 502


def test_student_answers_assessment_and_gets_graded(client, db_session, monkeypatch):
    headers, class_id, student_id, pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    item = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers).json()

    student_login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    monkeypatch.setattr(
        "app.routers.assessments.gemini_client.grade_answer",
        lambda question_text, correct_answer, student_answer, rubric: {
            "score": 100, "feedback": "Correct!",
        },
    )

    response = client.post(f"/assessments/{item['id']}/answer", json={"answer": "4"}, headers=student_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 100
    assert body["feedback"] == "Correct!"


def test_student_cannot_answer_another_students_assessment(client, db_session, monkeypatch):
    headers, class_id, student_id, _pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    item = client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers).json()

    other = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Other Student", "grade_level": 4}, headers=headers
    ).json()
    other_login = client.post(
        "/auth/student/login", json={"student_id": other["id"], "pin": other["pin"]}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.post(f"/assessments/{item['id']}/answer", json={"answer": "4"}, headers=other_headers)

    assert response.status_code == 404


def test_pending_assessments_lists_only_unanswered(client, db_session, monkeypatch):
    headers, class_id, student_id, pin = _setup_class_with_student(client, db_session)
    _stub_generate(monkeypatch)
    client.post(f"/classes/{class_id}/students/{student_id}/assessments", headers=headers)

    student_login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    response = client.get("/auth/student/assessments/pending", headers=student_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["question_text"] == "What is 2 + 2?"
