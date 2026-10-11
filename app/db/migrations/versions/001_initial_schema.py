"""Initial schema and Power BI views

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pathlib import Path

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Base tables are created from metadata
    from app.db.models import Base
    from app.db.repository import DEFAULT_CATEGORY_LOOKUPS, CategoryLookupModel
    from sqlalchemy.orm import Session
    
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # Load Power BI reporting views
    views_path = Path(__file__).resolve().parent.parent.parent.parent / "reporting" / "views.sql"
    if views_path.exists():
        with open(views_path, "r", encoding="utf-8") as f:
            sql_views = f.read()
        op.execute(sa.text(sql_views))

    # Populate category lookups if empty
    session = Session(bind=bind)
    if session.query(CategoryLookupModel).count() == 0:
        for item in DEFAULT_CATEGORY_LOOKUPS:
            session.add(CategoryLookupModel(**item))
        session.commit()


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS v_call_dashboard_detail CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_dim_agents CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_fact_coaching CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_fact_leakages CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_fact_objections CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_fact_call_assessments CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_dim_categories CASCADE;"))
    op.execute(sa.text("DROP VIEW IF EXISTS v_dim_calls CASCADE;"))

    from app.db.models import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
