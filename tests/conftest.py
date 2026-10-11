"""
Pytest fixtures and test configuration.
Provides in-memory SQLite and PostgreSQL database sessions and mock pipeline clients.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repository import DatabaseRepository
from app.services.llm_client import MockJordanianCohereClient
from app.retrieval.knowledge_base import SalesKnowledgeBase
from app.config import settings

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    """Creates a shared SQLite database engine for fast isolated unit testing."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    DatabaseRepository.initialize_schema_and_views(engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    """Provides an isolated database session per test with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_llm_client():
    return MockJordanianCohereClient()


@pytest.fixture
def sales_knowledge_base():
    return SalesKnowledgeBase()


@pytest.fixture
def sample_jordanian_transcript():
    return """[00:01] الموظف: ألو مرحبا أستاذ طارق، معك عمر من مبيعات الفايبر.
[00:06] العميل: يا هلا أهلاً وسهلاً.
[00:10] الموظف: العرض عنا اليوم باقة 300 ميجا بـ 25 دينار شامل الراوتر.
[00:18] العميل: والله يا غالي كتير غالي علي هالأيام والراتب طار وما بلحق.
[00:26] الموظف: باقة الـ 300 ميجا بتعطيك فايبر مباشر بدون تقطيع وبتوفر عليك باقات الموبايل.
[00:35] العميل: تمام، بس بدي استشير مرتي بالأول بنشوف المصاريف.
[00:42] الموظف: أكيد حقك، رح أبعثلك التفاصيل بمسج وبنرجع نتواصل بكرة.
[00:48] العميل: شكراً إلك ومع السلامة."""
