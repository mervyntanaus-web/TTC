import subprocess
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models.case import Case
from app.models.folder import Folder
from app.models.user import User, UserRole
from app.security import hash_password
from fake_storage import install as install_fake_storage


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", future=True)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session, tmp_path, monkeypatch):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    install_fake_storage(monkeypatch, tmp_path / "fake_s3")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def demo_user(db_session) -> User:
    user = User(
        name="Test Staff",
        email="staff@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.STAFF,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(client, demo_user) -> dict:
    resp = client.post("/auth/login", json={"email": demo_user.email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def demo_folder(db_session) -> Folder:
    case = Case(name="Test Case", retention_category="standard")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    folder = Folder(case_id=case.id, parent_id=None, name="Evidence")
    db_session.add(folder)
    db_session.commit()
    db_session.refresh(folder)
    return folder


@pytest.fixture()
def sample_mp4(tmp_path) -> Path:
    """A short, real MP4 (colour bars + a sine-wave audio track) generated
    with ffmpeg, used as ingestion/redaction test input instead of a
    hand-crafted fixture file."""
    path = tmp_path / "sample.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x240:rate=10:duration=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return path
