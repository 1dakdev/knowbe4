from app.models.school import School


def _create_class_with_student(client, db_session):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()

    client.post(
        "/teachers/signup",
        json={"email": "roster@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "roster@riverside.example", "password": "correct-horse"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    class_response = client.post("/classes", json={"name": "Grade 4", "grade_level": 4}, headers=headers)
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students", json={"full_name": "Maya Chen", "grade_level": 4}, headers=headers
    )
    student_body = student_response.json()
    return student_body["id"], student_body["pin"]


def test_student_login_with_correct_pin(client, db_session):
    student_id, pin = _create_class_with_student(client, db_session)

    response = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_student_login_rejects_wrong_pin(client, db_session):
    student_id, _pin = _create_class_with_student(client, db_session)

    response = client.post("/auth/student/login", json={"student_id": student_id, "pin": "0000"})
    assert response.status_code == 401


def test_student_login_rejects_unknown_student_id(client, db_session):
    response = client.post("/auth/student/login", json={"student_id": 999999, "pin": "1234"})
    assert response.status_code == 401


def test_student_me_requires_valid_student_token(client, db_session):
    student_id, pin = _create_class_with_student(client, db_session)
    login = client.post("/auth/student/login", json={"student_id": student_id, "pin": pin})
    token = login.json()["access_token"]

    ok = client.get("/auth/student/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["full_name"] == "Maya Chen"

    unauthorized = client.get("/auth/student/me")
    assert unauthorized.status_code == 401


def test_teacher_token_cannot_access_student_me(client, db_session):
    if db_session.query(School).first() is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "cross@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "cross@riverside.example", "password": "correct-horse"}
    )
    teacher_token = login.json()["access_token"]

    response = client.get("/auth/student/me", headers={"Authorization": f"Bearer {teacher_token}"})
    assert response.status_code == 401
