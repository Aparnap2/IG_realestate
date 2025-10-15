# AAA Real Estate Lead Capture Agentic AI System

Production-grade Instagram DM automation system for real estate lead capture, qualification, and meeting scheduling. This is a portfolio piece for the AAA AI Automation Agency, demonstrating advanced agentic AI capabilities.

## 🎯 System Overview

The AAA Real Estate Lead Capture System automates the complete lead-to-booking workflow:

1. **Instagram DM Capture** → Webhook receives messages
2. **AI Lead Qualification** → Extracts budget, location, property type, timeline  
3. **Property Matching** → Queries database for relevant listings
4. **Intelligent Scoring** → Scores leads 0-1 based on qualification criteria
5. **Smart Routing** → Routes to Scheduler (>0.7) or Follow-up (≤0.7)
6. **HITL for High-Value** → Human review for leads >$500k budget
7. **Auto-Response** → Sends contextual replies via Instagram

## ✨ Key Features

- 🤖 **LangGraph Swarm Architecture** - Three autonomous agents (Qualifier, Scheduler, FollowUp)
- 📱 **Instagram Messaging API** - Real webhook integration with Meta's platform
- 🎯 **Smart Lead Qualification** - Rule-based + LLM scoring system
- 🏠 **Property Database** - Supabase with 7 sample properties across Florida
- 🔄 **Redis State Management** - Persistent conversation threads
- 👥 **Human-in-the-Loop** - Automatic escalation for premium leads
- 📊 **Real-time Dashboard** - React frontend with lead monitoring
- 🔗 **Production Ready** - Error handling, logging, scalable architecture

## 🚀 Quick Start

### 1. Database Setup
```bash
# Run the SQL in Supabase dashboard, then:
python create_production_db.py
```

### 2. Start Production Backend
```bash
cd backend && python main.py
```

### 3. Start Frontend Dashboard
```bash
cd frontend && pnpm install && pnpm run dev
```

### 4. Test the System
```bash
# Test lead processing
curl -X POST http://localhost:8000/api/webhooks/test \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_123", "message": "Looking for 2BHK in Miami, budget $350k"}'

# Test Instagram webhook format
curl -X POST http://localhost:8000/api/webhooks/instagram \
  -H "Content-Type: application/json" \
  -d '{"object":"instagram","entry":[{"messaging":[{"sender":{"id":"user_456"},"message":{"text":"3BHK in Miami Beach, budget $800k, need ASAP"}}]}]}'
```

## 📊 Live Demo Results

The system is fully operational with real data:

```json
{
  "high_value_lead": {
    "budget": 800000,
    "location": "Miami",
    "qualified_score": 1.0,
    "next_agent": "hitl",
    "interrupt_needed": true,
    "response": "Thank you for your interest! I found 1 premium properties. Let me connect you with our senior advisor."
  },
  "qualified_lead": {
    "budget": 350000,
    "qualified_score": 1.0,
    "next_agent": "scheduler", 
    "properties_found": 1,
    "response": "Great! I found 1 properties that match your criteria. Would you like to schedule a viewing?"
  }
}
```

## 🏗️ Architecture

### Production Backend Server
- **FastAPI Backend** (`backend/main.py`) - Main production server with comprehensive API
- **Instagram Webhooks** (`backend/api/webhooks.py`) - Canonical webhook implementation
- **LangGraph Agents** (`backend/agents/prd_compliant_workflow.py`) - PRD-compliant agent architecture
- **Production Processor** (`backend/tasks/production_lead_processing.py`) - Complete lead processing pipeline
- **Supabase Integration** - Lead storage, property matching, configuration
- **Redis State** - Thread persistence for multi-turn conversations

### Frontend Dashboard
- **React + Vite** - Modern development setup
- **shadcn/ui** - Production-ready components
- **Real-time Updates** - Live lead monitoring
- **Supabase Auth** - Secure authentication

## ⚠️ Deprecation Notices

### Legacy Components
The following components have been deprecated during PRD alignment and should not be used in new deployments:

- **`instagram_webhook_server.py`** - ❌ DEPRECATED
  - **Reason**: Duplicate webhook implementation
  - **Replacement**: Use `backend/api/webhooks.py` with FastAPI backend
  - **Migration**: See Migration section below

- **`backend/agents/enhanced_workflow.py`** - ❌ DEPRECATED
  - **Reason**: Non-PRD compliant implementation
  - **Replacement**: Use `backend/agents/prd_compliant_workflow.py`

- **`backend/agents/enhanced_agents.py`** - ❌ DEPRECATED
  - **Reason**: Duplicate agent implementations
  - **Replacement**: Use canonical agents in `backend/agents/`

- **`backend/agents/modular_agents.py`** - ❌ DEPRECATED
  - **Reason**: Outdated architecture
  - **Replacement**: Use `backend/agents/prd_compliant_workflow.py`

- **`package-lock.json`** - ❌ DEPRECATED
  - **Reason**: Package manager inconsistency
  - **Replacement**: Use `pnpm-lock.yaml` (pnpm is now standard)

### Legacy Frontend Components
- **`frontend/src/components/LeadTable.tsx`** - ❌ DEPRECATED
  - **Reason**: Duplicate component
  - **Replacement**: Use `frontend/src/components/LeadsTable.tsx`

## 📁 Clean Project Structure

```
├── backend/
│   ├── main.py                    # 🎯 Main FastAPI production server
│   ├── api/webhooks.py            # 📱 Canonical Instagram webhook implementation
│   ├── agents/
│   │   ├── prd_compliant_workflow.py  # 🤖 PRD-compliant agent architecture
│   │   ├── router.py              # 🧭 Router agent for intent classification
│   │   ├── qualifier.py           # 🔍 Lead qualification agent
│   │   ├── scheduler.py           # 📅 Meeting scheduling agent
│   │   └── followup.py            # 🔄 Nurture and follow-up agent
│   ├── tasks/
│   │   └── production_lead_processing.py  # 🏭 Lead processing pipeline
│   ├── tools/                     # 🛠️ Agent tools and utilities
│   ├── models/                    # 📋 Data models
│   ├── utils/                     # 🔧 Utilities (Supabase, Redis, LLM)
│   └── tests/                     # 🧪 Comprehensive test suite
├── frontend/
│   ├── src/                       # ⚛️ React application
│   │   ├── components/            # 🎨 UI components
│   │   │   ├── LeadsTable.tsx     # 📊 Lead management table
│   │   │   ├── Dashboard.tsx      # 📈 Main dashboard
│   │   │   └── HITLPanel.tsx      # 👥 Human-in-the-loop interface
│   │   └── hooks/                 # 🎣 React hooks
│   └── tests/e2e/                 # 🎭 End-to-end tests
├── instagram_webhook_server.py    # ❌ DEPRECATED - Use backend/api/webhooks.py
├── create_production_db.py        # 🗄️ Database setup with sample data
├── CREATE_TABLES.sql              # 📋 Database schema
└── Product Requirements Document (PRD).md
```

## 🔧 Configuration

### Environment Variables (`backend/.env`)
```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# OpenRouter LLM
OPENROUTER_API_KEY=sk-or-v1-your-key

# Instagram Integration
INSTAGRAM_VERIFY_TOKEN=aaa_real_estate_verify_token_2025
META_PAGE_ACCESS_TOKEN=your-page-access-token

# Redis
REDIS_URL=redis://localhost:6379/0
```

## 📱 Instagram Integration Setup

Following the Instagram Messaging API guide:

1. **Create Meta App** with Messenger product
2. **Connect Instagram Business Account**
3. **Configure Webhook**: `https://yourdomain.com/webhook`
4. **Set Verify Token**: `aaa_real_estate_verify_token_2025`
5. **Subscribe to**: `messages`, `messaging_postbacks`
6. **Get Page Access Token** and set in environment

## 🧪 Testing

```bash
# Run backend tests
cd backend && pytest

# Test production workflow
python test_production_workflow.py

# Check system health
curl http://localhost:8000/health

# View recent leads
curl http://localhost:8000/leads
```

## 📈 Production Metrics

- ✅ **100+ Tests Passing** (60%+ backend coverage, 90%+ on critical files)
- ✅ **39 E2E Tests** with 100% pass rate
- ✅ **Complete PRD Alignment** - All requirements implemented
- ✅ **Compliance-by-Design** - Fair Housing, GDPR, and TCPA compliance
- ✅ **Temporal Memory** - Engagement trajectory tracking
- ✅ **Multi-constraint Scheduling** - Google Calendar integration
- ✅ **Revenue Intelligence** - Attribution and analytics

## 🚀 Deployment

The system is ready for production deployment:

1. **Railway/Heroku**: Deploy `backend/main.py` (FastAPI server)
2. **Supabase**: Database already configured
3. **Redis**: Use managed Redis service
4. **Meta Webhook**: Update URL to production domain (`/api/webhooks/instagram`)
5. **Frontend**: Deploy React app to Vercel/Netlify

## 🔄 Migration Guide

### Migrating from Legacy Webhook Server

If you're currently using the deprecated `instagram_webhook_server.py`, follow these steps:

1. **Update Webhook URL in Meta Dashboard**
   ```
   Old: https://yourdomain.com/webhook
   New: https://yourdomain.com/api/webhooks/instagram
   ```

2. **Update Environment Variables**
   ```bash
   # Add these to your backend/.env
   FASTAPI_HOST=0.0.0.0
   FASTAPI_PORT=8000
   ```

3. **Update Deployment Configuration**
   ```bash
   # Old deployment command
   python instagram_webhook_server.py
   
   # New deployment command
   cd backend && python main.py
   ```

4. **Update API Endpoints**
   ```bash
   # Old endpoints
   GET /webhook
   POST /webhook
   GET /health
   GET /leads
   
   # New endpoints
   GET /api/webhooks/instagram
   POST /api/webhooks/instagram
   GET /api/health
   GET /api/leads
   ```

### Migrating from Legacy Agent Implementation

If you're using the deprecated agent files:

1. **Update Imports**
   ```python
   # Old imports
   from backend.agents.enhanced_workflow import EnhancedWorkflow
   
   # New imports
   from backend.agents.prd_compliant_workflow import PRDCompliantWorkflow
   ```

2. **Update Agent Initialization**
   ```python
   # Old initialization
   workflow = EnhancedWorkflow()
   
   # New initialization
   workflow = PRDCompliantWorkflow()
   ```

### Database Schema Updates

The PRD alignment introduced new database fields:

```sql
-- New fields added to leads table
ALTER TABLE leads ADD COLUMN gdpr_consent TIMESTAMP;
ALTER TABLE leads ADD COLUMN tcpa_consent TIMESTAMP;
ALTER TABLE leads ADD COLUMN compliance_score FLOAT;
ALTER TABLE leads ADD COLUMN engagement_trajectory JSONB;

-- New audit_logs table
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES leads(id),
  event_type VARCHAR(50) NOT NULL,
  event_data JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  hash_signature VARCHAR(64) NOT NULL
);
```

Run the migration script:
```bash
cd backend && python scripts/apply_entity_type_migration.py
```

### Package Manager Migration

If you're still using npm:

1. **Install pnpm**
   ```bash
   npm install -g pnpm
   ```

2. **Remove npm lockfile**
   ```bash
   rm package-lock.json
   ```

3. **Install dependencies with pnpm**
   ```bash
   pnpm install
   ```

4. **Update scripts in package.json**
   ```json
   {
     "scripts": {
       "dev": "pnpm run dev",
       "build": "pnpm run build",
       "test": "pnpm run test"
     }
   }
   ```

## 📄 License

Portfolio piece for AAA AI Automation Agency. All rights reserved.