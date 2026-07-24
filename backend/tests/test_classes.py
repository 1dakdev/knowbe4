from app.models.school import School


def _signup_and_login(client, db_session, email="teacher@riverside.example") -> str:
    school = db_session.query(School).first()
    if school is None:
        db_session.add(School(name="Riverside Elementary"))
        db_session.commit()

    client.post(
        "/teachers/signup", json={"email": email, "password": "correct-horse", "full_name": "Teacher"}
    )
    login = client.post("/auth/teacher/login", json={"email": email, "password": "correct-horse"})
    return login.json()["access_token"]


def test_create_class_and_add_student(client, db_session):
    token = _signup_and_login(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    class_response = client.post(
        "/classes", json={"name": "Grade 4 Homeroom", "grade_level": 4}, headers=headers
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    student_response = client.post(
        f"/classes/{class_id}/students",
        json={"full_name": "Maya Chen", "grade_level": 4},
        headers=headers,
    )
    assert student_response.status_code == 201
    body = student_response.json()
    assert body["full_name"] == "Maya Chen"
    assert len(body["pin"]) == 4
    assert body["pin"].isdigit()

    roster = client.get(f"/classes/{class_id}", headers=headers)
    assert roster.status_code == 200
    roster_body = roster.json()
    assert roster_body["name"] == "Grade 4 Homeroom"
    assert len(roster_body["students"]) == 1
    assert roster_body["students"][0]["full_name"] == "Maya Chen"
    assert "pin" not in roster_body["students"][0]


def test_teacher_cannot_view_another_teachers_class(client, db_session):
    token_a = _signup_and_login(client, db_session, email="teacher.a@riverside.example")
    token_b = _signup_and_login(client, db_session, email="teacher.b@riverside.example")

    class_response = client.post(
        "/classes",
        json={"name": "Teacher A's Class", "grade_level": 4},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    class_id = class_response.json()["id"]

    response = client.get(f"/classes/{class_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 404


def test_create_class_requires_auth(client, db_session):
    response = client.post("/classes", json={"name": "No Auth Class", "grade_level": 4})
    assert response.status_code == 401
