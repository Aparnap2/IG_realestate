-- AAA Real Estate Database Schema
-- Execute this in Supabase SQL Editor

-- Create leads table
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL CHECK (channel IN ('ig', 'whatsapp')),
    message TEXT NOT NULL,
    qualified_score FLOAT CHECK (qualified_score >= 0 AND qualified_score <= 1),
    budget INTEGER,
    location VARCHAR,
    property_type VARCHAR,
    timeline VARCHAR,
    desired_bedrooms INTEGER,
    name VARCHAR,
    email VARCHAR,
    meeting_slot TIMESTAMP WITH TIME ZONE,
    status VARCHAR DEFAULT 'new' CHECK (status IN ('new', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected')),
    history JSONB DEFAULT '[]'::jsonb,
    last_interaction_at TIMESTAMP WITH TIME ZONE,
    tcpa_opt_in BOOLEAN,
    consent_timestamp TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    error TEXT,
    raw_response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for leads table
CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_last_interaction_at ON leads(last_interaction_at);

-- Create properties table
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price INTEGER NOT NULL,
    location VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL,
    amenities JSONB DEFAULT '{}'::jsonb,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create configs table
CREATE TABLE IF NOT EXISTS configs (
    key VARCHAR PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create lead_events table for tracking lead lifecycle events
CREATE TABLE IF NOT EXISTS lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL CHECK (event_type IN ('created', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected', 'error')),
    event_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for lead_events table
CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_events_event_type ON lead_events(event_type);
CREATE INDEX IF NOT EXISTS idx_lead_events_created_at ON lead_events(created_at);

-- Insert sample data
INSERT INTO properties (price, location, property_type, amenities, details) VALUES
(250000, 'Miami', '1BHK', '{"pool": true, "parking": true}', '{"sqft": 800, "year_built": 2020}'),
(350000, 'Miami', '2BHK', '{"pool": true, "parking": true, "gym": true}', '{"sqft": 1200, "year_built": 2021}'),
(500000, 'Miami', '3BHK', '{"pool": true, "parking": true, "gym": true, "balcony": true}', '{"sqft": 1600, "year_built": 2022}'),
(300000, 'Orlando', '2BHK', '{"pool": false, "parking": true}', '{"sqft": 1100, "year_built": 2019}'),
(450000, 'Tampa', 'Condo', '{"pool": true, "parking": true, "gym": true, "concierge": true}', '{"sqft": 1400, "year_built": 2023}');

INSERT INTO configs (key, value) VALUES
('qualifier_prompt', 'Score this lead (0-1) for real estate interest based on: Budget: {budget}, Location: {location}, Type: {property_type}, Timeline: {timeline}. Provide JSON: {"score": 0.8, "reasoning": "explanation"}'),
('hitl_threshold', '0.9'),
('scheduler_prompt', 'You are a real estate scheduler. Help book property tours and consultations.'),
('followup_prompt', 'You are a real estate follow-up agent. Nurture leads with relevant property suggestions.');
