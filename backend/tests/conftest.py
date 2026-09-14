import os
import sys
from pathlib import Path

# Point the app at an isolated test database BEFORE any app module is imported
# (app.core.config / app.db.session read DATABASE_URL at import time).
TEST_DB_PATH = Path(__file__).resolve().parent / "test_sifguard.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["LLM_PROVIDER"] = ""
os.environ["LLM_API_KEY"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine, SessionLocal
import app.models  # noqa: F401 registers all models on Base.metadata
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def analyst_user(db_session):
    user = db_session.query(User).filter(User.email == "test.analyst@sifguard-oil.com").first()
    if not user:
        user = User(
            email="test.analyst@sifguard-oil.com", full_name="Test Analyst",
            role=UserRole.HSE_ANALYST, hashed_password=hash_password("TestPass@123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    user = db_session.query(User).filter(User.email == "test.admin@sifguard-oil.com").first()
    if not user:
        user = User(
            email="test.admin@sifguard-oil.com", full_name="Test Admin",
            role=UserRole.ADMIN, hashed_password=hash_password("TestPass@123"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def analyst_token(client, analyst_user):
    resp = client.post("/api/auth/login", json={"email": analyst_user.email, "password": "TestPass@123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_token(client, admin_user):
    resp = client.post("/api/auth/login", json={"email": admin_user.email, "password": "TestPass@123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(analyst_token):
    return {"Authorization": f"Bearer {analyst_token}"}
