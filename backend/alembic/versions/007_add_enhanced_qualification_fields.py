"""Add enhanced qualification fields to leads table

Revision ID: 007
Revises: 006_add_comment_funnel_fields_to_leads
Create Date: 2025-10-24 07:27:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_add_enhanced_qualification_fields'
down_revision = '006_add_comment_funnel_fields_to_leads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enhanced qualification fields to leads table."""
    
    # Add new qualification scoring fields
    op.add_column('leads', sa.Column('qualified_score', sa.Float(), nullable=True))
    op.add_column('leads', sa.Column('previous_score', sa.Float(), nullable=True))
    op.add_column('leads', sa.Column('score_delta', sa.Float(), nullable=True))
    
    # Update status field to include new values
    op.execute("ALTER TABLE leads ALTER COLUMN status TYPE VARCHAR(20)")
    op.execute("UPDATE leads SET status = 'new' WHERE status NOT IN ('new', 'qualified', 'nurturing', 'disqualified', 'scheduled', 'booked')")
    
    # Add qualification stage field
    op.add_column('leads', sa.Column('qualification_stage', sa.String(length=50), nullable=True))
    
    # Add asked_questions field as JSON array
    op.add_column('leads', sa.Column('asked_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add value delivery fields
    op.add_column('leads', sa.Column('lead_magnet_type', sa.String(length=100), nullable=True))
    op.add_column('leads', sa.Column('property_info_delivered', sa.Boolean(), nullable=True, default=False))
    op.add_column('leads', sa.Column('market_insights_sent', sa.Boolean(), nullable=True, default=False))
    
    # Add off-ramp fields
    op.add_column('leads', sa.Column('offramp_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('offramp_reason', sa.String(length=100), nullable=True))
    op.add_column('leads', sa.Column('newsletter_opt_in', sa.Boolean(), nullable=True))
    
    # Add Instagram DM automation fields
    op.add_column('leads', sa.Column('dm_count', sa.Integer(), nullable=True, default=0))
    op.add_column('leads', sa.Column('response_count', sa.Integer(), nullable=True, default=0))
    
    # Add indexes for performance
    op.create_index('idx_leads_qualified_score', 'leads', ['qualified_score'])
    op.create_index('idx_leads_status', 'leads', ['status'])
    op.create_index('idx_leads_qualification_stage', 'leads', ['qualification_stage'])
    op.create_index('idx_leads_offramp_sent_at', 'leads', ['offramp_sent_at'])


def downgrade() -> None:
    """Remove enhanced qualification fields from leads table."""
    
    # Drop indexes
    op.drop_index('idx_leads_offramp_sent_at', table_name='leads')
    op.drop_index('idx_leads_qualification_stage', table_name='leads')
    op.drop_index('idx_leads_status', table_name='leads')
    op.drop_index('idx_leads_qualified_score', table_name='leads')
    
    # Drop columns
    op.drop_column('leads', 'response_count')
    op.drop_column('leads', 'dm_count')
    op.drop_column('leads', 'newsletter_opt_in')
    op.drop_column('leads', 'offramp_reason')
    op.drop_column('leads', 'offramp_sent_at')
    op.drop_column('leads', 'market_insights_sent')
    op.drop_column('leads', 'property_info_delivered')
    op.drop_column('leads', 'lead_magnet_type')
    op.drop_column('leads', 'asked_questions')
    op.drop_column('leads', 'qualification_stage')
    op.drop_column('leads', 'score_delta')
    op.drop_column('leads', 'previous_score')
    op.drop_column('leads', 'qualified_score')