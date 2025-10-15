"""Add entity_type column to audit_logs table

Revision ID: 004
Revises: 003
Create Date: 2025-10-14 06:21:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Add entity_type column to audit_logs table
    op.add_column('audit_logs', sa.Column('entity_type', sa.String(), nullable=False, server_default='system'))
    
    # Create index for entity_type
    op.create_index('idx_audit_logs_entity_type', 'audit_logs', ['entity_type'])


def downgrade():
    # Drop index
    op.drop_index('idx_audit_logs_entity_type', table_name='audit_logs')
    
    # Drop column
    op.drop_column('audit_logs', 'entity_type')