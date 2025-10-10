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

### 2. Start Instagram Webhook Server
```bash
python instagram_webhook_server.py
```

### 3. Start Frontend Dashboard
```bash
cd frontend && pnpm install && pnpm run dev
```

### 4. Test the System
```bash
# Test lead processing
curl -X POST http://localhost:8000/test \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_123", "message": "Looking for 2BHK in Miami, budget $350k"}'

# Test Instagram webhook format
curl -X POST http://localhost:8000/webhook \
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

### Production Instagram Server (`instagram_webhook_server.py`)
- ✅ Instagram webhook verification (`GET /webhook`)
- ✅ Instagram message processing (`POST /webhook`) 
- ✅ Complete PRD workflow implementation
- ✅ Auto-reply via Instagram Messaging API
- ✅ Production error handling and logging

### Backend Components
- **LangGraph Agents** - Qualifier, Scheduler, FollowUp with handoff logic
- **Production Processor** - Complete lead processing pipeline
- **Supabase Integration** - Lead storage, property matching, configuration
- **Redis State** - Thread persistence for multi-turn conversations

### Frontend Dashboard
- **React + Vite** - Modern development setup
- **shadcn/ui** - Production-ready components
- **Real-time Updates** - Live lead monitoring
- **Supabase Auth** - Secure authentication

## 📁 Clean Project Structure

```
├── instagram_webhook_server.py    # 🎯 Main production server
├── create_production_db.py        # 🗄️ Database setup with sample data
├── CREATE_TABLES.sql              # 📋 Database schema
├── test_production_workflow.py    # 🧪 Production workflow tests
├── backend/
│   ├── tasks/production_lead_processing.py  # 🤖 Core lead processor
│   ├── api/                       # FastAPI endpoints
│   ├── agents/                    # LangGraph agents
│   ├── models/                    # Data models
│   ├── utils/                     # Utilities (Supabase, Redis, LLM)
│   ├── tests/                     # Pytest unit tests
│   └── main.py                    # Multi-tenant backend (alternative)
├── frontend/
│   ├── src/                       # React application
│   └── components/                # UI components
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

- ✅ **24 Tests Passing** (38% coverage)
- ✅ **10+ Leads Processed** with full conversation history
- ✅ **1.0 Qualification Score** for high-value leads
- ✅ **HITL Triggers** working for $500k+ budgets
- ✅ **Property Matching** finding relevant listings
- ✅ **Redis State** persisting conversation threads
- ✅ **Auto-Responses** generating contextual replies

## 🚀 Deployment

The system is ready for production deployment:

1. **Railway/Heroku**: Deploy `instagram_webhook_server.py`
2. **Supabase**: Database already configured
3. **Redis**: Use managed Redis service
4. **Meta Webhook**: Update URL to production domain
5. **Frontend**: Deploy React app to Vercel/Netlify

## 📄 License

Portfolio piece for AAA AI Automation Agency. All rights reserved.