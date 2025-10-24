-- Simplified Instagram DM Automation Database Schema
-- Execute this in Supabase SQL Editor

-- Drop existing tables if they exist
DROP TABLE IF EXISTS lead_events CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS tour_schedules CASCADE;
DROP TABLE IF EXISTS properties CASCADE;
DROP TABLE IF EXISTS leads CASCADE;

-- Create simplified leads table for Instagram DM automation
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core identification
    instagram_id VARCHAR UNIQUE NOT NULL,
    instagram_username VARCHAR,
    name VARCHAR,
    phone VARCHAR,
    email VARCHAR,
    
    -- Qualification data
    budget INTEGER,
    desired_bedrooms INTEGER,
    location VARCHAR,
    timeline VARCHAR, -- "immediate" | "1-3months" | "3-6months" | "exploring"
    property_type VARCHAR,
    
    -- Engagement tracking
    engagement_score FLOAT DEFAULT 0 CHECK (engagement_score >= 0 AND engagement_score <= 1),
    engagement_trajectory VARCHAR DEFAULT 'stable' CHECK (engagement_trajectory IN ('escalating', 'cooling', 'stable')),
    last_interaction_at TIMESTAMP WITH TIME ZONE,
    
    -- Lead source & attribution
    source VARCHAR DEFAULT 'instagram' CHECK (source IN ('instagram', 'web')),
    utm_source VARCHAR,
    utm_medium VARCHAR,
    utm_campaign VARCHAR,
    
    -- Status & priority
    status VARCHAR DEFAULT 'new' CHECK (status IN ('new', 'qualifying', 'qualified', 'scheduled', 'toured', 'closed', 'lost')),
    priority VARCHAR DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    
    -- Fair housing compliance
    is_fair_housing_compliant BOOLEAN DEFAULT true,
    compliance_flags JSONB DEFAULT '{}'::jsonb,
    
    -- GDPR/TCPA compliance
    gdpr_consent TIMESTAMP WITH TIME ZONE,
    tcpa_consent TIMESTAMP WITH TIME ZONE,
    compliance_score FLOAT DEFAULT 1.0 CHECK (compliance_score >= 0 AND compliance_score <= 1),
    
    -- Agent interactions
    current_agent VARCHAR CHECK (current_agent IN ('router', 'qualifier', 'scheduler', 'followup', 'human')),
    agent_context JSONB DEFAULT '{}'::jsonb,
    
    -- Message thread tracking
    langgraph_thread_id VARCHAR UNIQUE,
    messages JSONB DEFAULT '[]'::jsonb,
    
    -- Legacy fields for backward compatibility
    channel VARCHAR DEFAULT 'instagram' CHECK (channel IN ('instagram', 'web', 'email')),
    user_id VARCHAR,
    qualified_score FLOAT CHECK (qualified_score >= 0 AND qualified_score <= 1),
    meeting_slot TIMESTAMP WITH TIME ZONE,
    history JSONB DEFAULT '[]'::jsonb,
    tcpa_opt_in BOOLEAN,
    consent_timestamp TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    error TEXT,
    raw_response JSONB,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for leads table
CREATE INDEX IF NOT EXISTS idx_leads_instagram_id ON leads(instagram_id);
CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
CREATE INDEX IF NOT EXISTS idx_leads_engagement_score ON leads(engagement_score);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_last_interaction_at ON leads(last_interaction_at);
CREATE INDEX IF NOT EXISTS idx_leads_langgraph_thread_id ON leads(langgraph_thread_id) WHERE langgraph_thread_id IS NOT NULL;

-- Create simplified properties table (no multi-tenant support)
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Property details
    mls_id VARCHAR UNIQUE, -- MLS listing ID
    price INTEGER NOT NULL,
    address TEXT NOT NULL,
    location VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL,
    bedrooms INTEGER,
    bathrooms DECIMAL(3,1),
    square_feet INTEGER,
    year_built INTEGER,
    
    -- Geographic coordinates for mapping
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Features & amenities
    amenities JSONB DEFAULT '{}'::jsonb,
    details JSONB DEFAULT '{}'::jsonb,
    description TEXT,
    
    -- Availability
    is_available BOOLEAN DEFAULT true,
    showing_availability JSONB DEFAULT '{}'::jsonb, -- Available showing times
    
    -- Agent performance tracking
    view_count INTEGER DEFAULT 0,
    inquiry_count INTEGER DEFAULT 0,
    tour_count INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5,4) DEFAULT 0.0,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for properties table
CREATE INDEX IF NOT EXISTS idx_properties_mls_id ON properties(mls_id);
CREATE INDEX IF NOT EXISTS idx_properties_location ON properties(location);
CREATE INDEX IF NOT EXISTS idx_properties_property_type ON properties(property_type);
CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_is_available ON properties(is_available);
CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at);

-- Create configs table
CREATE TABLE IF NOT EXISTS configs (
    key VARCHAR PRIMARY KEY,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security (RLS) for all tables
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tour_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_events ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for leads table (simplified - no company scoping)
CREATE POLICY IF NOT EXISTS "Allow all access to leads"
    ON leads
    FOR ALL
    USING (true);

-- Create RLS policies for properties table (simplified - no company scoping)
CREATE POLICY IF NOT EXISTS "Allow all access to properties"
    ON properties
    FOR ALL
    USING (true);

-- Create RLS policies for configs table (global access)
CREATE POLICY IF NOT EXISTS "Allow all access to configs"
    ON configs
    FOR ALL
    USING (true);

-- Create RLS policies for audit_logs table (allow access for compliance)
CREATE POLICY IF NOT EXISTS "Allow all access to audit logs"
    ON audit_logs
    FOR ALL
    USING (true);

-- Create RLS policies for tour_schedules table (simplified - no company scoping)
CREATE POLICY IF NOT EXISTS "Allow all access to tour schedules"
    ON tour_schedules
    FOR ALL
    USING (true);

-- Create RLS policies for lead_events table (simplified - no company scoping)
CREATE POLICY IF NOT EXISTS "Allow all access to lead events"
    ON lead_events
    FOR ALL
    USING (true);

-- Create audit_logs table for compliance tracking
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event tracking
    event_type VARCHAR NOT NULL CHECK (event_type IN ('message_sent', 'tour_scheduled', 'policy_violation', 'lead_qualified', 'compliance_check', 'agent_action')),
    entity_type VARCHAR NOT NULL CHECK (entity_type IN ('lead', 'conversation', 'tour', 'agent')),
    entity_id VARCHAR NOT NULL,
    
    -- Agent context
    agent_type VARCHAR CHECK (agent_type IN ('router', 'qualifier', 'scheduler', 'followup', 'human')),
    agent_action VARCHAR,
    
    -- State snapshots for audit trail
    state_before JSONB,
    state_after JSONB,
    
    -- Policy & compliance
    policy_checks JSONB DEFAULT '{}'::jsonb,
    compliance_flags TEXT[] DEFAULT '{}',
    
    -- Human review
    human_reviewed BOOLEAN DEFAULT false,
    reviewed_by VARCHAR,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    -- Temporal
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Tamper detection
    hash_signature VARCHAR(64) NOT NULL,
    prev_hash VARCHAR(64),
    
    -- Additional data
    event_data JSONB DEFAULT '{}'::jsonb
);

-- Create tour_schedules table for advanced scheduling
CREATE TABLE IF NOT EXISTS tour_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Lead and property relationship
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    property_ids UUID[] NOT NULL, -- Array of property IDs to tour
    
    -- Schedule details
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    status VARCHAR DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
    
    -- Google Calendar integration
    google_calendar_event_id VARCHAR UNIQUE,
    google_meet_link VARCHAR,
    
    -- No-show prediction
    no_show_risk FLOAT DEFAULT 0.5 CHECK (no_show_risk >= 0 AND no_show_risk <= 1),
    
    -- Agent performance tracking
    agent_efficiency_score DECIMAL(5,4), -- How well the tour was optimized
    travel_time_optimized BOOLEAN DEFAULT false,
    
    -- Notifications
    confirmation_sent_at TIMESTAMP WITH TIME ZONE,
    reminder_sent_at TIMESTAMP WITH TIME ZONE,
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create lead_events table for tracking lead lifecycle events
CREATE TABLE IF NOT EXISTS lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL CHECK (event_type IN ('created', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected', 'error', 'message', 'assistant_response', 'qualification', 'property_search')),
    event_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for lead_events table
CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_events_event_type ON lead_events(event_type);
CREATE INDEX IF NOT EXISTS idx_lead_events_created_at ON lead_events(created_at);

-- Insert enhanced sample data
INSERT INTO properties (mls_id, price, address, location, property_type, bedrooms, bathrooms, square_feet, year_built, latitude, longitude, amenities, details, description) VALUES
('MIA001', 250000, '123 Ocean Dr #1B', 'Miami Beach', 'Condo', 1, 1, 800, 2020, 25.7907, -80.1300, '{"pool": true, "parking": true, "gym": true}', '{"view": "ocean", "floor": "1"}', 'Beautiful oceanview condo in the heart of South Beach'),
('MIA002', 350000, '456 Brickell Ave #12A', 'Miami', 'Condo', 2, 2, 1200, 2021, 25.7617, -80.1918, '{"pool": true, "parking": true, "gym": true, "concierge": True}', '{"view": "city", "floor": "12"}', 'Modern Brickell condo with amazing city views'),
('MIA003', 500000, '789 Coral Way #3B', 'Coral Gables', 'House', 3, 2.5, 1600, 2022, 25.7517, -80.2580, '{"pool": true, "parking": true, "garden": True, "balcony": True}', '{"lot_size": "5000 sq ft", "garage": "2 car"}', 'Lovely Coral Gables home with pool and garden'),
('ORL001', 300000, '321 Main St #5C', 'Orlando', 'Condo', 2, 2, 1100, 2019, 28.5383, -81.3789, '{"parking": true, "gym": false}', '{"view": "park", "floor": "5"}', 'Affordable Orlando condo near downtown'),
('TAM001', 450000, '654 Beach Blvd #2A', 'Tampa', 'Condo', 2, 2, 1400, 2023, 27.9474, -82.4584, '{"pool": true, "parking": True, "gym": True, "beach_access": True}', '{"view": "gulf", "floor": "2"}', 'Gulf-facing condo with beautiful sunset views'),
('MIA004', 750000, '999 Sunset Dr', 'Miami', 'House', 4, 3, 2200, 2020, 25.7010, -80.3050, '{"pool": True, "parking": True, "garden": True, "outdoor_kitchen": True}', '{"lot_size": "8000 sq ft", "garage": "3 car"}', 'Luxury Miami home with resort-style backyard'),
('FLL001', 425000, '111 Las Olas Blvd #8B', 'Fort Lauderdale', 'Condo', 2, 2, 1300, 2021, 26.1224, -80.1433, '{"pool": True, "parking": True, "gym": True, "waterfront": True}', '{"view": "intracoastal", "floor": "8"}', 'Waterfront condo with boat access'),
('WPB001', 375000, '222 Palm Beach Rd', 'West Palm Beach', 'House', 3, 2, 1800, 2018, 26.7125, -80.0519, '{"pool": false, "parking": True, "garden": True}', '{"lot_size": "6000 sq ft", "garage": "2 car"}, 'Charming West Palm home perfect for families');

-- Insert simplified configs
INSERT INTO configs (key, value) VALUES
('qualifier_prompt', '{"system": "You are a real estate qualification specialist. Score leads 0-1 and extract key information.", "instruction": "Analyze the lead message and provide: score (0-1), budget, location, property_type, timeline, reasoning, and next_actions."}', 'hitl_threshold', '0.9'),
('scheduler_prompt', '{"system": "You are a real estate scheduling expert using Google Calendar optimization.", "instruction": "Coordinate property tours, optimize travel time, and handle cancellations proactively."}', 'followup_prompt', '{"system": "You are a real estate nurture specialist with temporal memory.", "instruction": "Provide personalized property recommendations based on lead history and market changes."}'),
('fair_housing_rules', '{"prohibited_patterns": ["families with children", "church|synagogue|mosque", "safe|dangerous neighborhood", "perfect for (young|elderly)"], "required_disclaimer": "Equal Housing Opportunity. All properties shown without regard to race, color, religion, sex, handicap, familial status, or national origin."}', 'compliance_settings', '{"strict_mode": true, "auto_block_violations": true, "audit_all_messages": true}');

-- Create alerts for policy violations
CREATE OR REPLACE FUNCTION check_compliance_flags()
RETURNS TRIGGER AS $$
BEGIN
    -- If compliance flags indicate violation, log it
    IF NEW.compliance_flags::text LIKE '%violation%' OR NEW.is_fair_housing_compliant = false THEN
        INSERT INTO audit_logs (event_type, entity_type, entity_id, agent_type, policy_checks, compliance_flags, hash_signature, event_data)
        VALUES (
            'policy_violation',
            'lead',
            NEW.id::text,
            NEW.current_agent,
            NEW.compliance_flags,
            ARRAY['fair_housing_violation'],
            md5(NEW.id || NEW.compliance_flags::text || now()::text),
            json_build_object('lead_data', row_to_json(NEW))
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for compliance checking
CREATE TRIGGER trigger_compliance_check
    AFTER INSERT OR UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION check_compliance_flags();

-- Create trigger for updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tour_schedules_updated_at
    BEFORE UPDATE ON tour_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
