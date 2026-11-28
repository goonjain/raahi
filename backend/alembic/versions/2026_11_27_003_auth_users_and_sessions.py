"""003_auth_users_and_sessions

Revision ID: 003_auth
Revises: 002_social
Create Date: 2026-11-27 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003_auth'
down_revision: Union[str, Sequence[str], None] = '002_social'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'users' in existing_tables:
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        user_indexes = {idx['name'] for idx in inspector.get_indexes('users')}

        with op.batch_alter_table('users') as batch_op:
            if 'email' not in user_cols:
                batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
            if 'password_hash' not in user_cols:
                batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))

        if 'ix_users_email' not in user_indexes:
            op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if 'user_sessions' not in existing_tables:
        op.create_table(
            'user_sessions',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_user_sessions_id', 'user_sessions', ['id'])
        op.create_index('ix_user_sessions_token_hash', 'user_sessions', ['token_hash'], unique=True)
        op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
        op.create_index('ix_user_sessions_expires_at', 'user_sessions', ['expires_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'user_sessions' in existing_tables:
        op.drop_table('user_sessions')

    if 'users' in existing_tables:
        user_indexes = {idx['name'] for idx in inspector.get_indexes('users')}
        if 'ix_users_email' in user_indexes:
            op.drop_index('ix_users_email', table_name='users')
        user_cols = {col['name'] for col in inspector.get_columns('users')}
        with op.batch_alter_table('users') as batch_op:
            if 'password_hash' in user_cols:
                batch_op.drop_column('password_hash')
            if 'email' in user_cols:
                batch_op.drop_column('email')

