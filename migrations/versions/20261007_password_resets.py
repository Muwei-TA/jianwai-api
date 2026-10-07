"""Add one-use password reset links.

Revision ID: 20261007_password_resets
Revises: 01cb45f9a35a
"""
from alembic import op
import sqlalchemy as sa

revision = '20261007_password_resets'
down_revision = '01cb45f9a35a'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('password_resets',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(32),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('used',sa.Boolean(),nullable=False))
    op.create_index('ix_password_resets_user_id','password_resets',['user_id'])

def downgrade():
    op.drop_index('ix_password_resets_user_id',table_name='password_resets')
    op.drop_table('password_resets')
