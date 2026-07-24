from app.models.school import School


def _seed_school(db_session) -> School:
    school = School(name="Riverside Elementary")
    db_session.add(school)
    db_session.flush()
    return school


def test_signup_creates_teacher(client, db_session):
    _seed_school(db_session)
    db_session.commit()

    response = client.post(
        "/teachers/signup",
        json={"email": "ms.jones@riverside.example", "password": "correct-horse", "full_name": "Ms. Jones"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ms.jones@riverside.example"
    assert "password" not in body


def test_signup_rejects_duplicate_email(client, db_session):
    _seed_school(db_session)
    db_session.commit()

    client.post(
        "/teachers/signup",
        json={"email": "dupe@riverside.example", "password": "correct-horse", "full_name": "First"},
    )
    response = client.post(
        "/teachers/signup",
        json={"email": "dupe@riverside.example", "password": "another-pass", "full_name": "Second"},
    )
    assert response.status_code == 409


def test_login_with_correct_credentials(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "login@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )

    response = client.post(
        "/auth/teacher/login", json={"email": "login@riverside.example", "password": "correct-horse"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_rejects_wrong_password(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "wrongpass@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )

    response = client.post(
        "/auth/teacher/login", json={"email": "wrongpass@riverside.example", "password": "not-it"}
    )
    assert response.status_code == 401


def test_me_requires_valid_token(client, db_session):
    _seed_school(db_session)
    db_session.commit()
    client.post(
        "/teachers/signup",
        json={"email": "me@riverside.example", "password": "correct-horse", "full_name": "Teacher"},
    )
    login = client.post(
        "/auth/teacher/login", json={"email": "me@riverside.example", "password": "correct-horse"}
    )
    token = login.json()["access_token"]

    ok = client.get("/teachers/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == "me@riverside.example"

    unauthorized = client.get("/teachers/me")
    assert unauthorized.status_code == 401

    bad_token = client.get("/teachers/me", headers={"Authorization": "Bearer garbage"})
    assert bad_token.status_code == 401
