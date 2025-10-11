# Phase 1 Setup Guide - Router Agent + Compliance

This guide walks through setting up the Phase 1 implementation with Router Agent, compliance gates, and audit logging.

## Prerequisites

1. **Environment Setup**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Create `backend/.env` with:
   ```env
   # Core Settings
   ENVIRONMENT=development
   DEBUG=true
   
   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   
   # Redis
   REDIS_URL=redis://localhost:6379
   
   # LLM
   OPENROUTER_API_KEY=your_openrouter_key
   LLM_MODEL=anthropic/claude-3.5-sonnet
   
   # Instagram (for testing - use test credentials)
   INSTAGRAM_PAGE_ACCESS_TOKEN=test_token
   INSTAGRAM_VERIFY_TOKEN=test_verify_token
   INSTAGRAM_APP_SECRET=test_secret
   
   # Security
   SECRET_KEY=your-secret-key-for-development
   AUDIT_SALT=your-audit-salt-for-development
   
   # Feature Flags (Phase 1)
   ENABLE_ROUTER_AGENT=true
   ENABLE_COMPLIANCE_CHECKS=true
   ENABLE_AUDIT_LOGGING=true
   ENABLE_REAL_INSTAGRAM_API=false
   ENABLE_TEMPORAL_GRAPH=false
   ENABLE_GOOGLE_CALENDAR=false
   ```

## Step 1: Database Setup

1. **Create Database Schema**
   ```bash
   cd backend
   python scripts/create_database_schema.py
   ```

2. **Verify Tables Created**
   Check Supabase dashboard for:
   - `leads` (with new compliance fields)
   - `properties`
   - `configs`
   - `audit_logs` (new)
   - `system_errors` (new)

## Step 2: Test Phase 1 Components

1. **Run Unit Tests**
   ```bash
   cd backend
   python -m pytest tests/test_phase1_implementation.py -v
   ```

2. **Test Router Agent**
   ```python
   # backend/test_router_manual.py
   import asyncio
   from agents.router import RouterAgent
   from models.lead import Lead
   
   async def test_router():
       lead = Lead(
           user_id="test_123",
           channel="ig",
           message="I'm looking for a 3BR house under $400k"
       )
       
       state = {
           "lead": lead,
           "messages": [{"role": "user", "content": lead.message}]
       }
       
       router = RouterAgent()
       result = await router.process(state)
       
       print(f"Routed to: {result['current_agent']}")
       print(f"Intent: {result['agent_decision']['intent']}")
       print(f"Confidence: {result['agent_decision']['confidence']}")
   
   asyncio.run(test_router())
   ```

3. **Test Compliance Tools**
   ```python
   # backend/test_compliance_manual.py
   import asyncio
   from tools.compliance import fair_housing_evaluator
   
   async def test_compliance():
       # Test safe message
       result1 = await fair_housing_evaluator("Beautiful 2BR apartment with modern amenities")
       print(f"Safe message passed: {result1['passed']}")
       
       # Test violation
       result2 = await fair_housing_evaluator("Perfect for young professionals")
       print(f"Violation detected: {not result2['passed']}")
       print(f"Violations: {result2['violations']}")
   
   asyncio.run(test_compliance())
   ```

4. **Test Audit Logging**
   ```python
   # backend/test_audit_manual.py
   from utils.audit import audit_log_event, query_audit_events
   
   # Log test event
   event_id = audit_log_event("test_event", {
       "test_data": "Phase 1 testing",
       "timestamp": "2024-01-01T00:00:00Z"
   })
   
   print(f"Event logged: {event_id}")
   
   # Query events
   events = query_audit_events(event_type="test_event", limit=5)
   print(f"Found {len(events)} events")
   ```

## Step 3: Integration Testing

1. **Test Full Workflow**
   ```python
   # backend/test_workflow_manual.py
   from workflow import create_workflow, validate_workflow_config
   
   # Validate configuration
   config = validate_workflow_config()
   print("Workflow config:", config)
   
   # Create workflow
   workflow = create_workflow()
   print("Workflow created successfully")
   ```

2. **Test Instagram Webhook (Mock)**
   ```bash
   # Start the FastAPI server
   cd backend
   python main.py
   
   # In another terminal, test webhook
   curl -X POST http://localhost:8000/webhook/instagram \
     -H "Content-Type: application/json" \
     -d '{
       "object": "instagram",
       "entry": [{
         "id": "test_page",
         "messaging": [{
           "sender": {"id": "test_user"},
           "message": {"text": "I want a 2BR apartment under $300k"}
         }]
       }]
     }'
   ```

## Step 4: Monitoring & Validation

1. **Check Audit Logs**
   ```sql
   -- In Supabase SQL editor
   SELECT event_type, entity_id, timestamp, payload 
   FROM audit_logs 
   ORDER BY timestamp DESC 
   LIMIT 10;
   ```

2. **Verify Compliance Tracking**
   ```sql
   -- Check for compliance events
   SELECT * FROM audit_logs 
   WHERE event_type IN ('fair_housing_check', 'compliance_violation')
   ORDER BY timestamp DESC;
   ```

3. **Monitor System Health**
   ```bash
   curl http://localhost:8000/status
   ```

## Expected Results

After successful Phase 1 setup:

✅ **Router Agent Active**
- All messages go through intent classification
- Confidence scoring works (>0.6 for auto-routing)
- Low confidence messages route to human review

✅ **Compliance Gates Working**
- Fair housing violations detected and blocked
- Neutral alternatives generated automatically
- All compliance checks logged to audit trail

✅ **Audit Logging Operational**
- Every agent decision logged with tamper-evident hash
- Hash chain integrity maintained
- Compliance events tracked for GDPR/TCPA

✅ **Database Schema Updated**
- New compliance fields in leads table
- Audit logs table with proper indexing
- System errors table for fallback logging

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Start Redis locally
   redis-server
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Supabase Connection Issues**
   - Verify SUPABASE_URL and SUPABASE_KEY in .env
   - Check Supabase project is active
   - Ensure RLS policies allow service role access

3. **LLM API Errors**
   - Verify OPENROUTER_API_KEY is valid
   - Check API quota/billing
   - Test with simpler model if needed

4. **Import Errors**
   ```bash
   # Ensure Python path is correct
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
   ```

### Validation Commands

```bash
# Test all Phase 1 components
cd backend
python -c "
from workflow import validate_workflow_config
from tools.compliance import fair_housing_evaluator
from utils.audit import audit_log_event
import asyncio

async def validate():
    # Test workflow
    config = validate_workflow_config()
    print('Workflow:', config['overall_health'])
    
    # Test compliance
    result = await fair_housing_evaluator('test message')
    print('Compliance:', result['passed'])
    
    # Test audit
    event_id = audit_log_event('validation', {'test': True})
    print('Audit:', event_id != 'audit_failed')

asyncio.run(validate())
"
```

## Next Steps

Once Phase 1 is working:

1. **Phase 2 Preparation**
   - Set up Neo4j for temporal knowledge graph
   - Configure Google Calendar API credentials
   - Plan property availability integration

2. **Production Readiness**
   - Set up proper Instagram app with Meta
   - Configure production Redis (managed service)
   - Set up monitoring (Sentry, Langfuse)

3. **Testing & Validation**
   - Run end-to-end tests with real Instagram webhooks
   - Validate compliance with sample fair housing scenarios
   - Test audit log integrity over time

The Phase 1 implementation provides the foundation for all subsequent phases, ensuring compliance and auditability from day one.