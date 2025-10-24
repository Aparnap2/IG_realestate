"""Add booking fields to leads table

Revision ID: 008
Revises: 007_add_enhanced_qualification_fields.py
Create Date: 2025-10-24 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '008_add_booking_fields_to_leads'
down_revision = '007_add_enhanced_qualification_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add booking-related fields to leads table."""
    
    # Add booking fields
    op.add_column('leads', sa.Column('calendar_event_id', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('meeting_link', sa.String(length=500), nullable=True))
    op.add_column('leads', sa.Column('booking_confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('rescheduled_count', sa.Integer(), server_default='0', nullable=False))
    
    # Add indexes for performance
    op.create_index('idx_leads_calendar_event_id', ['leads'], ['calendar_event_id'])
    op.create_index('idx_leads_booking_confirmed_at', ['leads'], ['booking_confirmed_at'])
    op.create_index('idx_leads_status_booking', ['leads'], ['status', 'booking_confirmed_at'])
    
    # Add comments for documentation
    op.execute("""
        COMMENT ON COLUMN leads.calendar_event_id IS 'Google Calendar event ID for booked meetings';
        COMMENT ON COLUMN leads.meeting_link IS 'Google Meet link for scheduled meetings';
        COMMENT ON COLUMN leads.booking_confirmed_at IS 'Timestamp when meeting was booked and confirmed';
        COMMENT ON COLUMN leads.rescheduled_count IS 'Number of times this meeting has been rescheduled';
    """)


def downgrade():
    """Remove booking fields from leads table."""
    
    # Remove indexes
    op.drop_index('idx_leads_status_booking', table_name='leads')
    op.drop_index('idx_leads_booking_confirmed_at', table_name='leads')
    op.drop_index('idx_leads_calendar_event_id', table_name='leads')
    
    # Remove columns
    op.drop_column('leads', 'rescheduled_count')
    op.drop_column('leads', 'booking_confirmed_at')
    op.drop_column('leads', 'meeting_link')
    op.drop_column('leads', 'calendar_event_id')