"""merge_template_schema_and_model_column

Revision ID: c249ef0d6fe5
Revises: template_schema, a1234567890
Create Date: 2026-04-13 07:14:34.271817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c249ef0d6fe5'
down_revision: Union[str, None] = ('template_schema', 'a1234567890')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
