"""add users workspaces and project workspace fk

Revision ID: 727eec711a17
Revises: 6831bbb89104
Create Date: 2026-05-24 06:42:26.537216

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '727eec711a17'
down_revision: Union[str, None] = '6831bbb89104'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the new auth tables.
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table(
        'workspaces',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workspaces_slug'), 'workspaces', ['slug'], unique=True)

    op.create_table(
        'workspace_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'member', 'viewer', name='workspacerole'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_member'),
    )
    op.create_index(op.f('ix_workspace_members_user_id'), 'workspace_members', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspace_members_workspace_id'), 'workspace_members', ['workspace_id'], unique=False)

    # 2. Add `projects.workspace_id` as NULLABLE first so we can backfill it.
    op.add_column('projects', sa.Column('workspace_id', sa.Uuid(), nullable=True))

    # 3. Backfill: any pre-existing projects get adopted by a single
    #    "Default workspace" row so the NOT NULL + FK constraints can hold.
    #
    #    We ALSO seed a placeholder user and a workspace_members row for
    #    that user so the legacy projects aren't permanently invisible.
    #    Operators are expected to log in as `legacy@example.com` (the
    #    bcrypt hash below corresponds to "change-me-now"; rotate
    #    immediately) and re-assign ownership before granting other
    #    users access.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'projects' in inspector.get_table_names():
        existing = bind.execute(sa.text("SELECT COUNT(*) FROM projects")).scalar() or 0
        if existing:
            default_ws = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO workspaces (id, name, slug) VALUES (:id, :name, :slug)"
                ),
                {"id": str(default_ws), "name": "Default workspace", "slug": "default"},
            )
            bind.execute(
                sa.text("UPDATE projects SET workspace_id = :id WHERE workspace_id IS NULL"),
                {"id": str(default_ws)},
            )

            # Seed a legacy admin user so the default workspace has at
            # least one member that can sign in and re-assign projects.
            # Compute the bcrypt hash at runtime — a hardcoded literal
            # rotates with the bcrypt library's salt format and can't be
            # validated at code-review time. Operators MUST rotate this
            # password immediately after first login.
            import bcrypt as _bcrypt

            legacy_user = uuid.uuid4()
            legacy_password = b"change-me-now"
            legacy_hash = _bcrypt.hashpw(
                legacy_password, _bcrypt.gensalt()
            ).decode("ascii")
            bind.execute(
                sa.text(
                    "INSERT INTO users (id, email, hashed_password, full_name, is_active)"
                    " VALUES (:id, :email, :pw, :name, 1)"
                ),
                {
                    "id": str(legacy_user),
                    "email": "legacy@example.com",
                    "pw": legacy_hash,
                    "name": "Legacy Admin",
                },
            )
            bind.execute(
                sa.text(
                    "INSERT INTO workspace_members (id, workspace_id, user_id, role)"
                    " VALUES (:mid, :wid, :uid, :role)"
                ),
                {
                    "mid": str(uuid.uuid4()),
                    "wid": str(default_ws),
                    "uid": str(legacy_user),
                    "role": "owner",
                },
            )

    # 4. Lock the column down + add the FK. Use batch_alter_table so this
    #    works on SQLite (which can't ALTER columns or ADD constraints).
    with op.batch_alter_table('projects') as batch_op:
        batch_op.alter_column('workspace_id', existing_type=sa.Uuid(), nullable=False)
        batch_op.create_foreign_key(
            'fk_projects_workspace_id_workspaces',
            'workspaces',
            ['workspace_id'],
            ['id'],
            ondelete='CASCADE',
        )
    op.create_index(op.f('ix_projects_workspace_id'), 'projects', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_projects_workspace_id'), table_name='projects')
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_constraint('fk_projects_workspace_id_workspaces', type_='foreignkey')
        batch_op.drop_column('workspace_id')
    op.drop_index(op.f('ix_workspace_members_workspace_id'), table_name='workspace_members')
    op.drop_index(op.f('ix_workspace_members_user_id'), table_name='workspace_members')
    op.drop_table('workspace_members')
    op.drop_index(op.f('ix_workspaces_slug'), table_name='workspaces')
    op.drop_table('workspaces')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
