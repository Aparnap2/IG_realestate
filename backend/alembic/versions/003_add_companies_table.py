"""Add companies table for multi-tenant support

Revision ID: 003
Revises: 002
Create Date: 2025-10-10 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create companies table
    op.create_table('companies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('industry', sa.String(), nullable=True, default='general'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('instagram_user_id', sa.String(), nullable=True),
        sa.Column('instagram_username', sa.String(), nullable=True),
        sa.Column('meta_app_id', sa.String(), nullable=True),
        sa.Column('access_token', sa.String(), nullable=True),
        sa.Column('webhook_verify_token', sa.String(), nullable=True),
        sa.Column('settings', postgresql.JSONB(), nullable=True, default='{}'),
        sa.Column('subscription_tier', sa.String(), nullable=True, default='starter'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_companies_slug', 'companies', ['slug'])
    op.create_index('idx_companies_is_active', 'companies', ['is_active'])
    op.create_index('idx_companies_industry', 'companies', ['industry'])
    
    # Enable RLS
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    
    # Create public read policy for active companies
    op.execute("""
        CREATE POLICY "Allow public read for active companies"
        ON companies
        FOR SELECT
        USING (is_active = true)
    """)


def downgrade():
    # Drop policies
    op.execute("DROP POLICY IF EXISTS \"Allow public read for active companies\" ON companies")
    
    # Drop indexes
    op.drop_index('idx_companies_industry', table_name='companies')
    op.drop_index('idx_companies_is_active', table_name='companies')
    op.drop_index('idx_companies_slug', table_name='companies')
    
    # Drop table
    op.drop_table('companies')