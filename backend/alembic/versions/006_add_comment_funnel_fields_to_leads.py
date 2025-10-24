"""Add comment funnel fields to leads table

Revision ID: 006
Revises: 005_add_company_id_to_properties_table.py
Create Date: 2025-10-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '006'
down_revision = '005_add_company_id_to_properties_table.py'
branch_labels = None
depends_on = None


def upgrade():
    """Add comment funnel fields to leads table"""
    # Add new columns for comment-triggered DM funnel
    op.add_column('leads', sa.Column('qualification_stage', sa.Text(), nullable=True, comment='Current qualification stage (warmup, qualification, etc.)'))
    op.add_column('leads', sa.Column('last_question_sent', sa.Text(), nullable=True, comment='Last qualification question sent to lead'))
    op.add_column('leads', sa.Column('lead_magnet_sent_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when lead magnet was sent'))
    op.add_column('leads', sa.Column('last_dm_sent', sa.DateTime(timezone=True), nullable=True, comment='Timestamp of last DM sent to lead'))
    
    # Add indexes for performance
    op.create_index('idx_leads_qualification_stage', ['qualification_stage'])
    op.create_index('idx_leads_lead_magnet_sent_at', ['lead_magnet_sent_at'])
    op.create_index('idx_leads_last_dm_sent', ['last_dm_sent'])


def downgrade():
    """Remove comment funnel fields from leads table"""
    # Remove indexes
    op.drop_index('idx_leads_last_dm_sent')
    op.drop_index('idx_leads_lead_magnet_sent_at')
    op.drop_index('idx_leads_qualification_stage')
    
    # Remove columns
    op.drop_column('leads', 'last_dm_sent')
    op.drop_column('leads', 'lead_magnet_sent_at')
    op.drop_column('leads', 'last_question_sent')
    op.drop_column('leads', 'qualification_stage')