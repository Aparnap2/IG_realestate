"""Initial migration - create leads, properties, and configs tables

Revision ID: 001
Revises: 
Create Date: 2025-09-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create leads table
    op.create_table('leads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('qualified_score', sa.Float(), nullable=True),
        sa.Column('budget', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('property_type', sa.String(), nullable=True),
        sa.Column('timeline', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('meeting_slot', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='new'),
        sa.Column('history', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create properties table
    op.create_table('properties',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column('property_type', sa.String(), nullable=False),
        sa.Column('amenities', postgresql.JSONB(), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create configs table
    op.create_table('configs',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('key')
    )
    
    # Create indexes
    op.create_index('idx_leads_user_id', 'leads', ['user_id'])
    op.create_index('idx_leads_status', 'leads', ['status'])
    op.create_index('idx_leads_created_at', 'leads', ['created_at'])
    op.create_index('idx_properties_location', 'properties', ['location'])
    op.create_index('idx_properties_price', 'properties', ['price'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_leads_user_id', table_name='leads')
    op.drop_index('idx_leads_status', table_name='leads')
    op.drop_index('idx_leads_created_at', table_name='leads')
    op.drop_index('idx_properties_location', table_name='properties')
    op.drop_index('idx_properties_price', table_name='properties')
    
    # Drop tables
    op.drop_table('configs')
    op.drop_table('properties')
    op.drop_table('leads')