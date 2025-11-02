# IG Real Estate Lead Management System

A sophisticated **pure agentic AI-powered** real estate lead management platform built with modern web technologies, featuring **LangGraph-enhanced LLM capabilities**, **rule-based agentic AI patterns**, and **intelligent proactive engagement** features.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8+-blue)
![React](https://img.shields.io/badge/React-19+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange)

## 🚀 Key Features

### 🤖 Pure Agentic AI Capabilities
- **Pure Rule-Based Intelligence**: No hardcoded ML dependencies - all decisions are transparent and explainable
- **LangGraph StateGraph Integration**: Supervisor-worker orchestration with Redis checkpoint persistence
- **Intelligent Model Routing**: Dynamic task complexity analysis with capability-based model selection
- **Agentic AI Patterns**: Parallel processing with Send API, Command objects, and intelligent agent coordination
- **Proactive Engagement Engine**: Context-aware intervention with configurable thresholds (1-2 interventions max)
- **Advanced Conversation Management**: 11-dimension state tracking with cross-component synchronization
- **Context-Aware Prompt Engineering**: Progressive disclosure strategies with personality adaptation

### 🏠 Real Estate Workflows
- **Lead Capture**: Multi-channel lead intake from Instagram, WhatsApp, and email
- **Intelligent Qualification**: Automated lead scoring with rule-based qualification
- **Property Matching**: AI-powered property recommendations with context preservation
- **Booking Management**: Automated scheduling with calendar integration
- **CRM Integration**: Seamless HubSpot and Salesforce integration

### 🔧 Technical Excellence
- **Circuit Breaker Protection**: Robust error handling with graceful degradation
- **Redis Checkpoint v2.0**: Cross-session state persistence with metadata versioning
- **Performance Monitoring**: Real-time metrics with >85% workflow success rate
- **Security**: Rate limiting, authentication, and comprehensive audit logging
- **Scalability**: Horizontal scaling with semaphore-controlled concurrent processing

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pure Agentic AI Engine                       │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   LangGraph     │   Supervisor    │   Intelligent Model         │
│   StateGraph    │   Worker        │   Router                    │
│   Orchestrator  │   Coordination  │   (Task Complexity Analysis)│
└─────────────────┴─────────────────┴─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Cross-Component State Manager                   │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Redis         │   Agent         │   Proactive Engagement      │
│   Checkpoint    │   Handoff       │   Engine                    │
│   v2.0          │   Coordinator   │   (Configurable Thresholds) │
└─────────────────┴─────────────────┴─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                Parallel Processing Architecture                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Task          │   Context-Aware │   Enhanced Prompt           │
│   Delegation    │   Prompt        │   Engineering Framework     │
│   Engine        │   Generation    │   (Progressive Disclosure)  │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

## 🛠️ Tech Stack

### Backend
- **Python 3.12+**: Core runtime with async/await patterns
- **FastAPI**: High-performance web framework with automatic API documentation
- **LangGraph**: Advanced state management with supervisor-worker patterns
- **Redis**: Caching and checkpoint persistence with metadata versioning
- **Supabase**: PostgreSQL database with Row Level Security
- **Alembic**: Database migrations with version control
- **Celery**: Distributed task queue for background processing

### Frontend
- **React 19**: Modern UI framework with hooks and context
- **TypeScript**: Full type safety with strict configuration
- **Vite**: Lightning-fast build tool and dev server
- **shadcn/ui**: Beautiful and accessible component library
- **Tailwind CSS**: Utility-first CSS framework
- **React Query**: Server state management with caching

### AI & LLM Infrastructure
- **OpenRouter**: Primary LLM provider with multiple model access
- **OpenAI GPT-4**: Secondary provider for specialized tasks
- **Google Gemini**: Fallback provider for reliability
- **LangGraph**: State management with Redis checkpoint integration
- **Intelligent Routing**: 5-level task complexity analysis
- **Capability Matching**: 7 agent capabilities mapped to optimal models

### External Integrations
- **HubSpot**: CRM integration with lead sync
- **Google Calendar**: Scheduling with conflict resolution
- **Meta/Instagram**: Social media lead capture
- **WhatsApp Business**: Messaging with webhook processing

## 🚀 Quick Start

### Prerequisites
- Python 3.12+ with pip
- Node.js 18+ with pnpm
- Redis server (v6.0+)
- PostgreSQL database (v12+)

### Backend Setup

1. **Clone and setup backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Environment configuration:**
```bash
cp .env.example .env
# Configure API keys, database URLs, and Redis connection
```

3. **Database setup:**
```bash
python scripts/setup_database.py
python scripts/apply_migrations.py
```

4. **Start the backend:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. **Navigate to frontend:**
```bash
cd frontend
```

2. **Install dependencies:**
```bash
pnpm install
```

3. **Environment setup:**
```bash
cp .env.example .env
# Configure Supabase credentials and API endpoints
```

4. **Start development server:**
```bash
pnpm run dev
```

### Redis Setup

1. **Install and start Redis:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# macOS
brew install redis

# Start Redis server
redis-server
```

2. **Verify Redis connection:**
```bash
redis-cli ping
# Should return: PONG
```

## 📚 Core Components

### 🤖 Enhanced LLM Client (`backend/utils/llm_client.py`)
The heart of the pure agentic AI system:

```python
# Pure Agentic AI Features
- Intelligent Model Routing with 5-level complexity analysis
- LangGraph StateGraph patterns with Redis checkpoint v2.0
- Supervisor-worker coordination with parallel processing
- Proactive engagement with configurable thresholds
- Context-aware prompt engineering with progressive disclosure
- Rule-based decisions (no hardcoded ML dependencies)
- Cross-component state synchronization
- Performance monitoring with >85% success rate
```

### 🔄 LangGraph Enhanced System (`backend/utils/langgraph_enhanced_agentic_system.py`)
Advanced agentic AI orchestration:

```python
# Supervisor-Worker Orchestration
- Central coordination with specialized worker agents
- Dynamic agent selection based on conversation context
- Seamless handoffs with validation and error handling
- Parallel processing with Send API implementation

# Cross-Component State Management  
- 11-dimension state tracking (EnhancedAgentState)
- Cross-component synchronization across all system parts
- Performance metrics integration with real-time tracking
- Context preservation between agent transitions
```

### ⚡ Parallel Coordination (`backend/utils/langgraph_parallel_coordination.py`)
Intelligent task distribution:

```python
# Task Delegation Engine
- Parallel execution with dependency management
- Semaphore-based concurrency control
- Workflow execution tracking with performance metrics
- Error resilience with comprehensive retry logic

# Agent Handoff Coordination
- Rule-based validation before agent transitions
- Context preservation across handoffs
- Performance optimization for seamless transitions
```

### 🎯 Proactive Engagement (`backend/utils/proactive_engagement.py`)
Intelligent intervention system:

```python
# Configurable Engagement
- inactivity_minutes threshold configuration
- max_interventions_per_hour/day limits
- 3 engagement strategies (gentle → direct → consultative)
- Intervention history tracking with audit trails

# Smart Re-engagement
- Time-based triggers with engagement level assessment
- Context-aware strategy selection
- Performance metrics for optimization
```

### 📖 Comprehensive Documentation
For detailed technical documentation, see:
- [`backend/ENHANCED_LANGGRAPH_PURE_AGENTIC_AI_DOCUMENTATION.md`](backend/ENHANCED_LANGGRAPH_PURE_AGENTIC_AI_DOCUMENTATION.md) - Complete 200+ page technical documentation
- [`backend/README.md`](backend/README.md) - Backend-specific documentation

## 🧪 Testing

### Comprehensive Test Suite
```bash
cd backend
# Run all tests including enhanced agentic AI system tests
pytest tests/test_enhanced_langgraph_agentic_ai_system.py -v

# Run pure agentic AI functionality tests
pytest tests/test_pure_agentic_llm_extraction.py -v

# Run proactive engagement tests
pytest tests/test_proactive_engagement.py -v

# Run full test suite
pytest tests/ -v --cov=utils --cov-report=html
```

### Frontend Testing
```bash
cd frontend
# Unit tests
pnpm test

# E2E tests with Playwright
pnpm test:e2e

# Component testing with coverage
pnpm test:coverage
```

## 📊 Performance & Capabilities

### 🚀 Enhanced System Performance
- **Response Time**: <2.0s for LangGraph checkpoint operations
- **Throughput**: Up to 10 concurrent requests with semaphore control
- **Memory Efficiency**: ~100KB per conversation context
- **Success Rate**: >85% workflow completion rate
- **Checkpoint Speed**: <2.0s save, <1.0s load for typical states

### 🧠 Pure Agentic AI Intelligence
- **Rule-Based Decisions**: 100% transparent and explainable
- **Context Awareness**: 11-dimension state tracking
- **Dynamic Routing**: 5-level task complexity analysis
- **Parallel Processing**: Concurrent execution with dependency management
- **Proactive Engagement**: Configurable intervention with 1-2 message limit

### 📈 Monitoring & Observability
- **Real-Time Metrics**: Performance monitoring with alerting
- **Health Checks**: Comprehensive system health monitoring
- **Audit Trails**: Complete interaction logging
- **Error Tracking**: Detailed error reporting and analysis

## 🚀 Deployment

### Production Environment Variables
```bash
# Enhanced Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CHECKPOINT_ENABLED=true
REDIS_CHECKPOINT_VERSION=v2.0

# Pure Agentic AI Features
PURE_AGENTIC_AI_ENABLED=true
LANGGRAPH_SUPERVISOR_ENABLED=true
PROACTIVE_ENGAGEMENT_ENABLED=true
INTELLIGENT_ROUTING_ENABLED=true
PARALLEL_PROCESSING_ENABLED=true

# LLM Provider Configuration
OPENROUTER_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
MODEL_ROUTING_STRATEGY=capability_based

# Database & Security
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
RATE_LIMIT_PER_MINUTE=60
AUDIT_LOGGING_ENABLED=true
```

### Docker Deployment
```bash
# Build and deploy with Docker Compose
docker-compose up -d

# Or build individually
docker build -f backend.dockerfile -t ig-realestate-backend .
docker build -f frontend.dockerfile -t ig-realestate-frontend .

# Scale with multiple backend instances
docker-compose up --scale backend=3
```

### Production Monitoring
```bash
# Health check endpoint
curl http://localhost:8000/api/health

# System metrics
curl http://localhost:8000/api/metrics

# Agentic AI performance metrics
curl http://localhost:8000/api/ai/metrics
```

## 🔐 Security & Compliance

### Security Features
- **Authentication**: JWT-based with refresh token rotation
- **Authorization**: Role-based access control (RBAC)
- **Rate Limiting**: Configurable per-endpoint limits
- **Circuit Breakers**: Protection against cascading failures
- **Data Encryption**: AES-256 encryption at rest and in transit

### Compliance & Audit
- **Comprehensive Audit Logging**: All user interactions logged
- **GDPR Compliance**: Data retention and deletion policies
- **SOC 2 Controls**: Security and availability controls
- **Data Privacy**: PII protection with field-level encryption

## 🤝 Contributing

### Development Guidelines
1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/pure-agentic-enhancement`
3. **Follow coding standards**:
   - Python: PEP 8 with type hints
   - TypeScript: Strict mode with ESLint
   - Documentation: Comprehensive docstrings
4. **Write tests**: Minimum 80% coverage for new features
5. **Update documentation**: Reflect all API changes
6. **Commit with conventional commits**: `feat(ai): add enhanced model routing`

### Pure Agentic AI Principles
- **Rule-Based Intelligence**: No hardcoded ML models
- **Transparent Decisions**: All AI decisions must be explainable
- **Context Preservation**: Maintain conversation state across components
- **Performance Optimization**: Target <2.0s response times
- **Error Resilience**: Graceful degradation with fallback strategies

## 📋 API Reference

### Core Lead Management
- `POST /api/leads` - Create new lead with AI analysis
- `GET /api/leads/{id}` - Get lead with enhanced context
- `PUT /api/leads/{id}` - Update lead with state synchronization
- `DELETE /api/leads/{id}` - Delete lead with audit logging

### Agentic AI Enhancement Endpoints
- `POST /api/ai/analyze` - Pure AI-powered lead analysis
- `POST /api/ai/qualify` - Rule-based lead qualification
- `POST /api/ai/route` - Intelligent agent routing
- `POST /api/ai/proactive` - Proactive engagement trigger
- `GET /api/ai/context/{conversation_id}` - Get conversation context
- `POST /api/ai/checkpoint/{conversation_id}` - Save checkpoint

### LangGraph Integration
- `POST /api/langgraph/supervisor` - Supervisor coordination
- `POST /api/langgraph/worker` - Worker agent processing
- `GET /api/langgraph/state/{conversation_id}` - Get graph state
- `POST /api/langgraph/transition` - Execute state transition

### System Monitoring
- `GET /api/health` - Comprehensive health check
- `GET /api/metrics` - Performance metrics
- `GET /api/audit/logs` - Audit trail access
- `GET /api/circuit-breaker/status` - Circuit breaker status

## 🗺️ Implementation Roadmap

### ✅ Phase 1: Pure Agentic AI Foundation (COMPLETED)
- [x] **LangGraph StateGraph Integration**: Supervisor-worker orchestration
- [x] **Intelligent Model Routing**: 5-level task complexity analysis
- [x] **Redis Checkpoint v2.0**: Cross-component state persistence
- [x] **Proactive Engagement Engine**: Configurable thresholds with limits
- [x] **Agent Coordination Patterns**: Parallel processing with Send API
- [x] **Context-Aware Prompt Engineering**: Progressive disclosure strategies
- [x] **Enhanced State Management**: 11-dimension tracking
- [x] **Performance Optimization**: >85% success rate, <2.0s response time

### 🔄 Phase 2: Advanced Agentic Intelligence (IN PROGRESS)
- [ ] **Multi-Modal Support**: Image and document processing
- [ ] **Voice Integration**: Speech-to-text and text-to-speech
- [ ] **Advanced Analytics**: Conversation flow analysis
- [ ] **Sentiment Analysis**: Rule-based sentiment detection

### 📋 Phase 3: Enterprise Features (PLANNED)
- [ ] **Advanced CRM Integrations**: Salesforce, Pipedrive
- [ ] **Mobile App SDK**: Native mobile integration
- [ ] **Advanced Reporting**: Business intelligence dashboards
- [ ] **Compliance Tools**: Industry-specific compliance features

## 📞 Support & Documentation

### 📚 Documentation Resources
- **[Enhanced LangGraph Documentation](backend/ENHANCED_LANGGRAPH_PURE_AGENTIC_AI_DOCUMENTATION.md)** - 200+ page comprehensive guide
- **[Backend README](backend/README.md)** - Detailed backend documentation
- **[Frontend README](frontend/README.md)** - Frontend-specific guide
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs (when running)

### 🆘 Getting Help
- **Issues**: [GitHub Issues](https://github.com/your-org/ig-realestate/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/ig-realestate/discussions)
- **Documentation**: Comprehensive guides and API reference
- **Community**: Join our Discord server for real-time help

### 🏆 Recognition
- **LangGraph Team**: For the revolutionary state management framework
- **FastAPI Team**: For the exceptional async web framework
- **OpenRouter**: For providing access to multiple high-quality LLM models
- **Redis Team**: For the powerful caching and persistence solution
- **shadcn/ui Team**: For the beautiful and accessible component library

---

**Built with ❤️ for modern real estate professionals leveraging pure agentic AI**

*Last Updated: 2025-11-02 | Version: 2.0.0 | Status: Production Ready*