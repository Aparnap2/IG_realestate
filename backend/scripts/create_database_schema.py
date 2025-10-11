#!/usr/bin/env python3
"""
Script to create database schema in Supabase according to PRD specifications
"""
import os
import sys
from supabase import create_client

def create_database_schema():
    """Create database schema with tables and RLS policies"""
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        # Create leads table with compliance fields
        leads_sql = """
        CREATE TABLE IF NOT EXISTS leads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR NOT NULL,
            channel VARCHAR NOT NULL CHECK (channel IN ('ig')),
            message TEXT NOT NULL,
            qualified_score FLOAT CHECK (qualified_score >= 0 AND qualified_score <= 1),
            budget INTEGER,
            location VARCHAR,
            property_type VARCHAR,
            timeline VARCHAR,
            name VARCHAR,
            email VARCHAR,
            meeting_slot TIMESTAMP WITH TIME ZONE,
            status VARCHAR DEFAULT 'new' CHECK (status IN ('new', 'qualified', 'scheduled', 'booked')),
            history JSONB DEFAULT '[]'::jsonb,
            -- Compliance fields (PRD Section 2.6)
            gdpr_consent BOOLEAN DEFAULT FALSE,
            tcpa_opt_in BOOLEAN DEFAULT FALSE,
            consent_timestamp TIMESTAMP WITH TIME ZONE,
            consent_method VARCHAR,
            consent_ip VARCHAR,
            -- Engagement tracking (PRD Section 2.2)
            engagement_score FLOAT DEFAULT 0.0,
            engagement_trajectory VARCHAR DEFAULT 'stable' CHECK (engagement_trajectory IN ('escalating', 'cooling', 'stable')),
            last_interaction_at TIMESTAMP WITH TIME ZONE,
            -- Temporal context
            prior_interests JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        # Create properties table
        properties_sql = """
        CREATE TABLE IF NOT EXISTS properties (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            price INTEGER NOT NULL,
            location VARCHAR NOT NULL,
            property_type VARCHAR NOT NULL,
            amenities JSONB DEFAULT '{}'::jsonb,
            details JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        # Create configs table
        configs_sql = """
        CREATE TABLE IF NOT EXISTS configs (
            key VARCHAR PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        # Create audit_logs table (PRD Section 2.6: Immutable Audit Trail)
        audit_logs_sql = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR NOT NULL,
            entity_type VARCHAR NOT NULL DEFAULT 'system',
            entity_id VARCHAR NOT NULL,
            agent_type VARCHAR,
            payload JSONB NOT NULL,
            correlation_id UUID,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            hash VARCHAR NOT NULL,
            prev_hash VARCHAR,
            -- Compliance tracking
            policy_checks JSONB DEFAULT '{}'::jsonb,
            human_reviewed BOOLEAN DEFAULT FALSE,
            reviewed_by VARCHAR,
            reviewed_at TIMESTAMP WITH TIME ZONE,
            -- Indexing for performance
            CONSTRAINT audit_logs_hash_unique UNIQUE (hash)
        );
        """
        
        # Create system_errors table for audit system failures
        system_errors_sql = """
        CREATE TABLE IF NOT EXISTS system_errors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            failed_event_type VARCHAR,
            failed_payload JSONB,
            error TEXT NOT NULL,
            system VARCHAR NOT NULL,
            resolved BOOLEAN DEFAULT FALSE
        );
        """
        
        # Execute table creation
        print("Creating leads table...")
        supabase.rpc("exec_sql", {"sql": leads_sql}).execute()
        
        print("Creating properties table...")
        supabase.rpc("exec_sql", {"sql": properties_sql}).execute()
        
        print("Creating configs table...")
        supabase.rpc("exec_sql", {"sql": configs_sql}).execute()
        
        print("Creating audit_logs table...")
        supabase.rpc("exec_sql", {"sql": audit_logs_sql}).execute()
        
        print("Creating system_errors table...")
        supabase.rpc("exec_sql", {"sql": system_errors_sql}).execute()
        
        # Enable RLS
        print("Enabling RLS on tables...")
        supabase.rpc("exec_sql", {"sql": "ALTER TABLE leads ENABLE ROW LEVEL SECURITY;"}).execute()
        supabase.rpc("exec_sql", {"sql": "ALTER TABLE properties ENABLE ROW LEVEL SECURITY;"}).execute()
        supabase.rpc("exec_sql", {"sql": "ALTER TABLE configs ENABLE ROW LEVEL SECURITY;"}).execute()
        supabase.rpc("exec_sql", {"sql": "ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;"}).execute()
        supabase.rpc("exec_sql", {"sql": "ALTER TABLE system_errors ENABLE ROW LEVEL SECURITY;"}).execute()
        
        # Create indexes for performance
        print("Creating database indexes...")
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_id ON audit_logs(entity_id);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_correlation_id ON audit_logs(correlation_id);",
            "CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);",
            "CREATE INDEX IF NOT EXISTS idx_leads_engagement_score ON leads(engagement_score);",
            "CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);",
            "CREATE INDEX IF NOT EXISTS idx_properties_location ON properties(location);",
        ]
        
        for index_sql in indexes_sql:
            supabase.rpc("exec_sql", {"sql": index_sql}).execute()
        
        # Create RLS policies for leads
        leads_policies = [
            "DROP POLICY IF EXISTS leads_select_policy ON leads;",
            "CREATE POLICY leads_select_policy ON leads FOR SELECT USING (true);",
            "DROP POLICY IF EXISTS leads_insert_policy ON leads;",
            "CREATE POLICY leads_insert_policy ON leads FOR INSERT WITH CHECK (true);",
            "DROP POLICY IF EXISTS leads_update_policy ON leads;",
            "CREATE POLICY leads_update_policy ON leads FOR UPDATE USING (true);",
        ]
        
        # Create RLS policies for properties
        properties_policies = [
            "DROP POLICY IF EXISTS properties_select_policy ON properties;",
            "CREATE POLICY properties_select_policy ON properties FOR SELECT USING (true);",
            "DROP POLICY IF EXISTS properties_insert_policy ON properties;",
            "CREATE POLICY properties_insert_policy ON properties FOR INSERT WITH CHECK (true);",
            "DROP POLICY IF EXISTS properties_update_policy ON properties;",
            "CREATE POLICY properties_update_policy ON properties FOR UPDATE USING (true);",
        ]
        
        # Create RLS policies for configs
        configs_policies = [
            "DROP POLICY IF EXISTS configs_select_policy ON configs;",
            "CREATE POLICY configs_select_policy ON configs FOR SELECT USING (true);",
            "DROP POLICY IF EXISTS configs_insert_policy ON configs;",
            "CREATE POLICY configs_insert_policy ON configs FOR INSERT WITH CHECK (true);",
            "DROP POLICY IF EXISTS configs_update_policy ON configs;",
            "CREATE POLICY configs_update_policy ON configs FOR UPDATE USING (true);",
        ]
        
        print("Creating RLS policies...")
        for policy in leads_policies + properties_policies + configs_policies:
            supabase.rpc("exec_sql", {"sql": policy}).execute()
        
        # Insert default configurations
        default_configs = [
            {
                "key": "qualifier_prompt",
                "value": """Score this lead (0-1) for real estate interest based on:
Budget: {budget}
Location: {location}
Type: {property_type}
Timeline: {timeline}

DB properties: {db_results}

Scoring Rubric:
- Budget > $500k: +0.3
- Budget > $300k: +0.2  
- Budget > $100k: +0.1
- Location and property type match DB: +0.3
- Timeline < 6 months: +0.1

Provide your response as a JSON object with the following structure:
{
    "score": 0.8,
    "reasoning": "Explanation of the score"
}"""
            },
            {
                "key": "hitl_threshold",
                "value": "0.9"
            },
            {
                "key": "scheduler_prompt",
                "value": "You are a real estate scheduler. Help book property tours and consultations."
            },
            {
                "key": "followup_prompt", 
                "value": "You are a real estate follow-up agent. Nurture leads with relevant property suggestions."
            }
        ]
        
        print("Inserting default configurations...")
        for config in default_configs:
            supabase.table("configs").upsert(config).execute()
        
        # Insert sample properties
        sample_properties = [
            {
                "price": 250000,
                "location": "Miami",
                "property_type": "1BHK",
                "amenities": {"pool": True, "parking": True, "gym": False},
                "details": {"sqft": 800, "year_built": 2020, "floor": 5}
            },
            {
                "price": 350000,
                "location": "Miami", 
                "property_type": "2BHK",
                "amenities": {"pool": True, "parking": True, "gym": True},
                "details": {"sqft": 1200, "year_built": 2021, "floor": 8}
            },
            {
                "price": 500000,
                "location": "Miami",
                "property_type": "3BHK", 
                "amenities": {"pool": True, "parking": True, "gym": True, "balcony": True},
                "details": {"sqft": 1600, "year_built": 2022, "floor": 12}
            },
            {
                "price": 300000,
                "location": "Orlando",
                "property_type": "2BHK",
                "amenities": {"pool": False, "parking": True, "gym": False},
                "details": {"sqft": 1100, "year_built": 2019, "floor": 3}
            },
            {
                "price": 450000,
                "location": "Tampa",
                "property_type": "Condo",
                "amenities": {"pool": True, "parking": True, "gym": True, "concierge": True},
                "details": {"sqft": 1400, "year_built": 2023, "floor": 15}
            }
        ]
        
        print("Inserting sample properties...")
        for property_data in sample_properties:
            supabase.table("properties").insert(property_data).execute()
        
        print("Database schema created successfully!")
        print("Tables created: leads, properties, configs")
        print("RLS policies enabled and configured")
        print("Sample data inserted")
        
    except Exception as e:
        print(f"Error creating database schema: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_database_schema()