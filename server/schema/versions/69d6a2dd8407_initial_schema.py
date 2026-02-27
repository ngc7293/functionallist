"""Initial Schema

Revision ID: 69d6a2dd8407
Revises:
Create Date: 2026-02-27 10:07:20.722145

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString


# revision identifiers, used by Alembic.
revision: str = "69d6a2dd8407"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE item_id_seq START 1 INCREMENT 1")

    op.create_table(
        "list",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", AutoString(), nullable=False),
        sa.Column("description", AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", AutoString(), nullable=False),
        sa.Column("email", AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "list_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "item_id",
            sa.Integer(),
            server_default=sa.text("nextval('item_id_seq')"),
            nullable=True,
        ),
        sa.Column("display_name", AutoString(), nullable=True),
        sa.Column("checked", sa.Boolean(), nullable=True),
        sa.Column("occured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["list.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_list_event_list_id"), "list_event", ["list_id"], unique=False)
    op.create_index(op.f("ix_list_event_occured_at"), "list_event", ["occured_at"], unique=False)
    op.create_table(
        "list_user",
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["list.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("list_id", "user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("list_user")
    op.drop_index(op.f("ix_list_event_occured_at"), table_name="list_event")
    op.drop_index(op.f("ix_list_event_list_id"), table_name="list_event")
    op.drop_table("list_event")
    op.drop_table("user")
    op.drop_table("list")

    op.execute("DROP SEQUENCE item_id_seq")
