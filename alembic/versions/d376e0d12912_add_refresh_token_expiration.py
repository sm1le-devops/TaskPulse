"""add refresh token expiration

Revision ID: d376e0d12912
Revises: dd94558e7400
Create Date: 2026-09-14 20:38:18.730617

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d376e0d12912"
down_revision: Union[str, Sequence[str], None] = "dd94558e7400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text(
                """
                UPDATE refresh_tokens
                SET expires_at = NOW() + INTERVAL '7 days'
                WHERE expires_at IS NULL
                """
            )
        )
    else:
        connection.execute(
            sa.text(
                """
                UPDATE refresh_tokens
                SET expires_at = datetime('now', '+7 days')
                WHERE expires_at IS NULL
                """
            )
        )

    op.alter_column(
        "refresh_tokens",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "expires_at")