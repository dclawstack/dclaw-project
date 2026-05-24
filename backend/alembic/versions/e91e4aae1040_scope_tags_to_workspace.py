"""scope tags to workspace

Revision ID: e91e4aae1040
Revises: 48ce4585b903
Create Date: 2026-05-24 07:39:50.513376

Backfill: any existing tags get adopted by the oldest workspace in the
table (creating a "Default workspace" if none exists). New tag CRUD is
workspace-scoped going forward.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e91e4aae1040'
down_revision: Union[str, None] = '48ce4585b903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the column as NULLABLE first so we can backfill before locking.
    op.add_column('tags', sa.Column('workspace_id', sa.Uuid(), nullable=True))

    bind = op.get_bind()
    existing_tags = bind.execute(sa.text("SELECT COUNT(*) FROM tags")).scalar() or 0
    if existing_tags:
        ws_row = bind.execute(
            sa.text("SELECT id FROM workspaces ORDER BY created_at ASC LIMIT 1")
        ).first()
        if ws_row is None:
            ws_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO workspaces (id, name, slug) VALUES (:id, :n, :s)"
                ),
                {"id": str(ws_id), "n": "Default workspace", "s": "default"},
            )
        else:
            ws_id = ws_row[0]
        bind.execute(
            sa.text("UPDATE tags SET workspace_id = :id WHERE workspace_id IS NULL"),
            {"id": str(ws_id)},
        )

    op.drop_index(op.f('ix_tags_name'), table_name='tags')
    with op.batch_alter_table('tags') as batch_op:
        batch_op.alter_column('workspace_id', existing_type=sa.Uuid(), nullable=False)
        batch_op.create_foreign_key(
            'fk_tags_workspace_id_workspaces',
            'workspaces',
            ['workspace_id'],
            ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_unique_constraint(
            'uq_tags_workspace_name', ['workspace_id', 'name']
        )
    op.create_index(op.f('ix_tags_name'), 'tags', ['name'], unique=False)
    op.create_index(op.f('ix_tags_workspace_id'), 'tags', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tags_workspace_id'), table_name='tags')
    op.drop_index(op.f('ix_tags_name'), table_name='tags')
    with op.batch_alter_table('tags') as batch_op:
        batch_op.drop_constraint('uq_tags_workspace_name', type_='unique')
        batch_op.drop_constraint('fk_tags_workspace_id_workspaces', type_='foreignkey')
        batch_op.drop_column('workspace_id')
    op.create_index(op.f('ix_tags_name'), 'tags', ['name'], unique=True)
