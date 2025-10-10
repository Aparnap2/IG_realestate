# AAA Real Estate System Setup Instructions

## Phase 1: Database Setup (Supabase)

### Step 1: Create Tables in Supabase Dashboard

1. Go to your Supabase project: https://supabase.com/dashboard/project/jobtrksybjbpkdloyghf
2. Navigate to **SQL Editor**
3. Copy and paste the following SQL commands:

```sql
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
    name VARCHAR,
    email VARCHAR,
    meeting_slot TIMESTAMP WITH TIME ZONE,
    status VARCHAR DEFAULT 'new' CHECK (status IN ('new', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected')),
    history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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
```

4. Click **Run** to execute the SQL

### Step 2: Insert Sample Data

After creating tables, run:

```bash
cd backend
source .venv/bin/activate
python create_sample_data.py
```

## Phase 2: Backend Setup

### Step 1: Start Redis
```bash
docker-compose up -d redis
```

### Step 2: Test Backend
```bash
cd backend
source .venv/bin/activate
python -c "from utils.supabase_client import supabase; print('✅ Backend connected to Supabase')"
```

### Step 3: Run Backend Server
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Start Celery Worker (in new terminal)
```bash
cd backend
source .venv/bin/activate
celery -A celery_app worker --loglevel=info
```

## Phase 3: Frontend Setup

### Step 1: Install Dependencies
```bash
cd frontend
pnpm install
```

### Step 2: Start Frontend
```bash
cd frontend
pnpm run dev
```

## Phase 4: Test the Complete Workflow

### Step 1: Test API Endpoints
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test webhook endpoint (simulate Instagram message)
curl -X POST http://localhost:8000/webhook/ig \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_123"},
        "message": {"text": "Looking for 2BHK in Miami, budget $350k"}
      }]
    }]
  }'
```

### Step 2: Check Frontend Dashboard
1. Open http://localhost:5173
2. Login with test credentials (if configured)
3. View leads dashboard
4. Monitor real-time updates

## Phase 5: Integration Testing

### Test the Complete PRD Workflow:

1. **Lead Arrival**: Send message via webhook
2. **Qualification**: Check lead scoring in dashboard
3. **Scheduling**: Verify calendar integration
4. **HITL**: Test human-in-the-loop for high-value leads
5. **Follow-up**: Check nurturing messages

## Troubleshooting

### Common Issues:

1. **Supabase Connection Error**: Check environment variables in `backend/.env`
2. **Redis Connection Error**: Ensure Redis is running with `docker-compose up -d redis`
3. **Frontend Import Errors**: Check that all dependencies are installed with `pnpm install`
4. **API Key Issues**: Verify all API keys are properly configured

### Debug Commands:

```bash
# Test Redis connection
redis-cli ping

# Test Supabase connection
cd backend && source .venv/bin/activate && python -c "from utils.supabase_client import supabase; print(supabase.table('properties').select('*').limit(1).execute())"

# Check backend logs
cd backend && source .venv/bin/activate && python main.py

# Check frontend build
cd frontend && pnpm run build
```

## Next Steps

Once the system is running:

1. Configure real Instagram/WhatsApp webhooks
2. Set up Google Calendar integration
3. Configure HubSpot CRM integration
4. Test with real lead data
5. Monitor system performance and logs