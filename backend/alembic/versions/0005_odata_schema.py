"""data_sources.odata_schema: поля объекта из $metadata 1С"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.add_column("data_sources", sa.Column("odata_schema", postgresql.JSONB))


def downgrade() -> None:
    op.drop_column("data_sources", "odata_schema")
