import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.VITE_SUPABASE_URL 
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY 
const supabase = createClient(supabaseUrl, supabaseKey)

async function setupTestDatabase() {
  console.log('Setting up test database...')
  
  try {
    // Insert test properties
    const testProperties = [
      {
        id: 'prop-1',
        price: 250000,
        location: 'Miami',
        property_type: '1BHK',
        amenities: { pool: true, parking: true },
        details: { sqft: 800, year_built: 2020 }
      },
      {
        id: 'prop-2',
        price: 350000,
        location: 'Miami',
        property_type: '2BHK',
        amenities: { pool: true, parking: true, gym: true },
        details: { sqft: 1200, year_built: 2021 }
      },
      {
        id: 'prop-3',
        price: 600000,
        location: 'Miami',
        property_type: '3BHK',
        amenities: { pool: true, parking: true, gym: true, balcony: true },
        details: { sqft: 1600, year_built: 2022 }
      }
    ]
    
    for (const prop of testProperties) {
      try {
        await supabase.table('properties').upsert(prop)
        console.log(`✓ Property: ${prop.property_type} - $${prop.price.toLocaleString()}`)
      } catch (error) {
        console.log(`Property insert: ${error.message}`)
      }
    }
    
    // Insert test configs
    const testConfigs = [
      {
        key: 'qualifier_prompt',
        value: 'Score this lead (0-1) based on budget, location, property type. Return JSON: {"score": 0.8, "reasoning": "explanation"}'
      },
      {
        key: 'hitl_threshold',
        value: '0.9'
      }
    ]
    
    for (const config of testConfigs) {
      try {
        await supabase.table('configs').upsert(config)
        console.log(`✓ Config: ${config.key}`)
      } catch (error) {
        console.log(`Config insert: ${error.message}`)
      }
    }
    
    // Insert test leads
    const testLeads = [
      {
        id: 'lead-1',
        user_id: 'test_user_low_score',
        channel: 'ig',
        message: 'Looking for cheap apartment',
        qualified_score: 0.3,
        budget: 150000,
        location: 'Miami',
        property_type: '1BHK',
        status: 'new',
        history: []
      },
      {
        id: 'lead-2',
        user_id: 'test_user_high_score',
        channel: 'whatsapp',
        message: 'Need luxury 3BHK in Miami, budget 600k',
        qualified_score: 0.95,
        budget: 600000,
        location: 'Miami',
        property_type: '3BHK',
        status: 'interrupted',
        history: [{ message: 'High-value lead flagged for HITL', timestamp: '2024-01-01T10:00:00Z', agent: 'qualifier' }]
      }
    ]
    
    for (const lead of testLeads) {
      try {
        await supabase.table('leads').upsert(lead)
        console.log(`✓ Lead: ${lead.user_id} - Score: ${lead.qualified_score}`)
      } catch (error) {
        console.log(`Lead insert: ${error.message}`)
      }
    }
    
    console.log('✓ Test database setup complete!')
    
  } catch (error) {
    console.error('Database setup error:', error.message)
    process.exit(1)
  }
}

setupTestDatabase()
