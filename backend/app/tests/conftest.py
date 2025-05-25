import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, StaticPool, create_engine

from app.models.user import User
from app.main import app  # Import your FastAPI app
from app.api.deps import get_db  # Import your get_db dependenc


@pytest.fixture(scope="session")
def test_engine():
    # Use an in-memory SQLite database with shared cache
    engine = create_engine(
        "sqlite:///:memory:?cache=shared",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool  # 👈 required to reuse the same memory db
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def connection(test_engine):
    with test_engine.connect() as conn:
        yield conn

@pytest.fixture(scope="function")
def db_session(connection):
    # Start a nested transaction and create a session for each test
    transaction = connection.begin_nested()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # Rollback after test to reset database

@pytest.fixture(scope="function")
def client(db_session):
    # Override the get_db dependency to use the test session
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

