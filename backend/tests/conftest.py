import os

# Override settings before any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["IS_TESTING"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.core.security import hash_password, create_access_token  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.camera import Camera, ConnectionType  # noqa: E402

engine = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ── Shared plan fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def basic_plan(db):
    plan = Plan(
        name="Básico",
        max_cameras=3,
        retention_days=30,
        email_alerts=False,
        realtime_alerts=False,
        price_monthly=99.90,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@pytest.fixture
def pro_plan(db):
    plan = Plan(
        name="Profissional",
        max_cameras=10,
        retention_days=90,
        email_alerts=True,
        realtime_alerts=True,
        price_monthly=299.90,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# ── Shared user/client fixtures ───────────────────────────────────────────────

@pytest.fixture
def super_admin_user(db):
    user = User(
        email="sa@sistema.com",
        name="Super Admin",
        password_hash=hash_password("Admin@123"),
        role=UserRole.super_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_a(db, basic_plan):
    c = Client(name="Cliente A", email="a@test.com", plan_id=basic_plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def client_b(db, basic_plan):
    c = Client(name="Cliente B", email="b@test.com", plan_id=basic_plan.id, is_active=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def admin_a(db, client_a):
    user = User(
        email="admin@client-a.com",
        name="Admin A",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_admin,
        client_id=client_a.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_a(db, client_a):
    user = User(
        email="user@client-a.com",
        name="User A",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=client_a.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_b(db, client_b):
    user = User(
        email="user@client-b.com",
        name="User B",
        password_hash=hash_password("Admin@123"),
        role=UserRole.client_user,
        client_id=client_b.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Shared camera fixtures ────────────────────────────────────────────────────

@pytest.fixture
def camera_rtsp_a(db, client_a):
    cam = Camera(
        client_id=client_a.id,
        name="RTSP-A",
        location="Entrada",
        connection_type=ConnectionType.rtsp,
        rtsp_url="rtsp://192.168.0.1/stream",
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@pytest.fixture
def camera_agent_a(db, client_a):
    cam = Camera(
        client_id=client_a.id,
        name="Agent-A",
        location="Saída",
        connection_type=ConnectionType.agent,
        agent_token="token-agent-a-" + "x" * 18,
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@pytest.fixture
def camera_b(db, client_b):
    cam = Camera(
        client_id=client_b.id,
        name="Agent-B",
        location="Portão",
        connection_type=ConnectionType.agent,
        agent_token="token-agent-b-" + "y" * 18,
        is_active=True,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


# ── Authenticated HTTP client helpers ─────────────────────────────────────────

def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _auth_header(user: User) -> dict:
    return {"Authorization": f"Bearer {_tok(user)}"}
