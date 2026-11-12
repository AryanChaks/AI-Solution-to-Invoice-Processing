import os
os.environ["DATABASE_URL"] = "sqlite:///./test_invoiceap.db"   # unit/integration tests never touch SQL Server
os.environ.setdefault("OLLAMA_MODEL", "")
import pytest
from app.database.connection import engine
from app.database import seed

@pytest.fixture(autouse=True)
def fresh_db():
    seed.reset(); seed.seed()
    yield
