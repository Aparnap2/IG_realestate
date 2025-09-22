"""Seed data for leads, properties, and configs tables

Revision ID: 002
Revises: 001
Create Date: 2025-09-17 10:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid
from datetime import datetime, timedelta

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Insert sample properties
    properties_data = [
        {
            'id': str(uuid.uuid4()),
            'price': 350000,
            'location': 'Miami',
            'property_type': '2BHK',
            'amenities': {
                'parking': True,
                'gym': True,
                'pool': False
            },
            'details': {
                'bedrooms': 2,
                'bathrooms': 2,
                'area': 1200
            }
        },
        {
            'id': str(uuid.uuid4()),
            'price': 450000,
            'location': 'Miami',
            'property_type': '3BHK',
            'amenities': {
                'parking': True,
                'gym': True,
                'pool': True
            },
            'details': {
                'bedrooms': 3,
                'bathrooms': 2,
                'area': 1800
            }
        },
        {
            'id': str(uuid.uuid4()),
            'price': 275000,
            'location': 'Fort Lauderdale',
            'property_type': '2BHK',
            'amenities': {
                'parking': True,
                'gym': False,
                'pool': True
            },
            'details': {
                'bedrooms': 2,
                'bathrooms': 1,
                'area': 1000
            }
        },
        {
            'id': str(uuid.uuid4()),
            'price': 650000,
            'location': 'Miami Beach',
            'property_type': 'Condo',
            'amenities': {
                'parking': True,
                'gym': True,
                'pool': True,
                'beach_access': True
            },
            'details': {
                'bedrooms': 2,
                'bathrooms': 2,
                'area': 1400
            }
        }
    ]
    
    properties_table = sa.table('properties',
        sa.column('id', sa.String),
        sa.column('price', sa.Integer),
        sa.column('location', sa.String),
        sa.column('property_type', sa.String),
        sa.column('amenities', postgresql.JSONB),
        sa.column('details', postgresql.JSONB)
    )
    
    op.bulk_insert(properties_table, properties_data)
    
    # Insert sample configs
    configs_data = [
        {
            'key': 'qualifier_prompt',
            'value': 'Score this lead (0-1) for real estate interest based on budget, location, property type, and timeline. High score if budget >$100k, location/type match, timeline <6 months.'
        },
        {
            'key': 'scheduler_prompt',
            'value': 'Book a meeting with this lead based on their availability and property preferences.'
        },
        {
            'key': 'followup_prompt',
            'value': 'Send a follow-up message to this lead with relevant property recommendations.'
        },
        {
            'key': 'hitl_threshold',
            'value': '0.9'
        }
    ]
    
    configs_table = sa.table('configs',
        sa.column('key', sa.String),
        sa.column('value', sa.Text)
    )
    
    op.bulk_insert(configs_table, configs_data)


def downgrade():
    # Delete seed data
    op.execute("DELETE FROM configs")
    op.execute("DELETE FROM properties")