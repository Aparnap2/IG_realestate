"""Add HubSpot integration fields to leads table

Revision ID: 009
Revises: 008_add_booking_fields_to_leads
Create Date: 2025-10-24 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_add_hubspot_fields_to_leads'
down_revision = '008_add_booking_fields_to_leads'
branch_labels = None
depends_on = None


def upgrade():
    """Add HubSpot integration fields to leads table."""

    # Add HubSpot fields
    op.add_column('leads', sa.Column('hubspot_contact_id', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('hubspot_deal_id', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('hubspot_sync_status', sa.String(length=50), server_default='pending', nullable=False))
    op.add_column('leads', sa.Column('hubspot_last_synced_at', sa.DateTime(timezone=True), nullable=True))

    # Add indexes for performance
    op.create_index('idx_leads_hubspot_contact_id', ['leads'], ['hubspot_contact_id'])
    op.create_index('idx_leads_hubspot_deal_id', ['leads'], ['hubspot_deal_id'])
    op.create_index('idx_leads_hubspot_sync_status', ['leads'], ['hubspot_sync_status'])

    # Add comments for documentation
    op.execute("""
        COMMENT ON COLUMN leads.hubspot_contact_id IS 'HubSpot contact ID for CRM synchronization';
        COMMENT ON COLUMN leads.hubspot_deal_id IS 'HubSpot deal ID for booked meetings';
        COMMENT ON COLUMN leads.hubspot_sync_status IS 'Status of HubSpot synchronization (pending, synced, failed)';
        COMMENT ON COLUMN leads.hubspot_last_synced_at IS 'Timestamp of last successful HubSpot sync';
    """)


def downgrade():
    """Remove HubSpot integration fields from leads table."""

    # Remove indexes
    op.drop_index('idx_leads_hubspot_sync_status', table_name='leads')
    op.drop_index('idx_leads_hubspot_deal_id', table_name='leads')
    op.drop_index('idx_leads_hubspot_contact_id', table_name='leads')

    # Remove columns
    op.drop_column('leads', 'hubspot_last_synced_at')
    op.drop_column('leads', 'hubspot_sync_status')
    op.drop_column('leads', 'hubspot_deal_id')
    op.drop_column('leads', 'hubspot_contact_id')