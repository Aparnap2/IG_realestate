# IG Real Estate Lead Management System

A sophisticated AI-powered real estate lead management platform built with modern web technologies, featuring LangGraph-enhanced LLM capabilities, agentic AI patterns, and proactive engagement features.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8+-blue)
![React](https://img.shields.io/badge/React-19+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange)

## 🚀 Key Features

### 🤖 Advanced AI Capabilities
- **LangGraph Integration**: StateGraph patterns with Redis checkpoint persistence
- **Intelligent Model Routing**: Dynamic model selection based on task complexity
- **Agentic AI Patterns**: Supervisor-worker coordination with parallel processing
- **Proactive Engagement**: Context-aware intervention with configurable thresholds
- **Conversation Management**: Comprehensive conversation state tracking
- **Advanced Prompt Engineering**: Structured templates for different agent types

### 🏠 Real Estate Workflows
- **Lead Capture**: Multi-channel lead intake from Instagram, WhatsApp, and email
- **Intelligent Qualification**: Automated lead scoring and qualification
- **Property Matching**: AI-powered property recommendations
- **Booking Management**: Automated scheduling with calendar integration
- **CRM Integration**: Seamless HubSpot and Salesforce integration

### 🔧 Technical Excellence
- **Circuit Breaker Protection**: Robust error handling and graceful degradation
- **Redis Checkpoints**: Cross-session state persistence
- **Performance Monitoring**: Real-time metrics and SLA compliance
- **Security**: Rate limiting, authentication, and audit logging
- **Scalability**: Horizontal scaling with Redis clustering

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   LangGraph     │
│   (React)       │────│   (FastAPI)     │────│   Engine        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent         │    │   Redis         │    │   LLM           │
│   Coordinator   │────│   Checkpoint    │────│   Router        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Proactive     │    │   Conversation  │    │   Intelligent   │
│   Engagement    │────│   Context       │────│   Model         │
│   Engine        │    │   Manager       │    │   Selector      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ Tech Stack

### Backend
- **Python 3.12+**: Core runtime
- **FastAPI**: Web framework
- **LangGraph**: State management and agent coordination
- **Redis**: Caching and checkpoint persistence
- **Supabase**: Database and authentication
- **Alembic**: Database migrations
- **Celery**: Background task processing

### Frontend
- **React 19**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool
- **shadcn/ui**: Component library
- **Tailwind CSS**: Styling
- **React Query**: State management

### AI & LLM
- **OpenRouter**: Primary LLM provider
- **OpenAI GPT-4**: Secondary provider
- **Google Gemini**: Fallback provider
- **LangGraph**: Advanced state management
- **Intelligent Routing**: Dynamic model selection

### Integrations
- **HubSpot**: CRM integration
- **Google Calendar**: Scheduling
- **Meta/Instagram**: Social media
- **WhatsApp Business**: Messaging

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Redis server
- PostgreSQL database

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
# Edit .env with your API keys and configuration
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
# Configure Supabase credentials
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

# Start Redis
redis-server
```

2. **Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

## 📚 Key Components

### 🤖 Enhanced LLM Client (`backend/utils/llm_client.py`)
The heart of the AI system with LangGraph integration:

- **Intelligent Model Routing**: Routes requests to optimal models based on task complexity
- **LangGraph State Management**: StateGraph patterns with Redis checkpoint persistence
- **Agentic AI Patterns**: Supervisor-worker coordination with parallel processing
- **Conversation Context Management**: Comprehensive conversation state tracking
- **Proactive Engagement Engine**: Configurable thresholds with intelligent intervention strategies
- **Advanced Prompt Engineering**: Structured templates for different agent types
- **Circuit Breaker Protection**: Robust error handling with graceful degradation

### 📖 Documentation
For detailed technical documentation, see:
- [`backend/LANGGRAPH_ENHANCEMENT_DOCUMENTATION.md`](backend/LANGGRAPH_ENHANCEMENT_DOCUMENTATION.md) - Comprehensive LangGraph and AI features documentation

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Tests
```bash
cd frontend
pnpm test
```

### E2E Tests
```bash
cd frontend
pnpm test:e2e
```

## 📊 Key Features Deep Dive

### 🧠 LangGraph Integration
- **StateGraph Patterns**: Advanced conversation state management
- **Redis Checkpoint Persistence**: Cross-session state management
- **Cross-Component Synchronization**: Shared state across all system components
- **Versioning Support**: Checkpoint versioning for rollback and audit trails

### 🤖 Intelligent Agent Coordination
- **Dynamic Agent Selection**: Context-aware agent routing
- **Parallel Processing**: Concurrent request handling with semaphore control
- **Supervisor-Worker Patterns**: Coordinated multi-agent workflows
- **Error Isolation**: Fault-tolerant agent execution

### 🎯 Proactive Engagement
- **Context-Aware Interventions**: Intelligent timing based on conversation analysis
- **Configurable Thresholds**: Customizable engagement frequency limits
- **Multi-Channel Coordination**: Unified proactive engagement across channels
- **Deduplication**: Prevents duplicate interventions within cooldown periods

### 🔧 Model Routing Intelligence
- **Task Complexity Analysis**: Automatic complexity assessment
- **Capability Matching**: Model strengths aligned with task requirements
- **Performance Tracking**: Continuous optimization based on metrics
- **Fallback Strategies**: Graceful degradation when preferred models unavailable

## 🚀 Deployment

### Production Environment Variables
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# LLM APIs
OPENROUTER_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Feature Flags
PROACTIVE_ENGAGEMENT_ENABLED=true
INTELLIGENT_ROUTING_ENABLED=true
LANGGRAPH_ENABLED=true
```

### Docker Deployment
```bash
# Backend
docker build -f backend.dockerfile -t ig-realestate-backend .

# Frontend  
docker build -f frontend.dockerfile -t ig-realestate-frontend .

# Run with docker-compose
docker-compose up -d
```

## 📈 Performance & Monitoring

### Key Metrics
- **Response Time**: 2-5 seconds for LangGraph-enhanced requests
- **Throughput**: Up to 10 concurrent requests with semaphore control
- **Memory Usage**: ~100KB per conversation context
- **Redis Operations**: <10ms for checkpoint operations

### Health Monitoring
- **API Health Check**: `/api/health` endpoint
- **Circuit Breaker Status**: Real-time monitoring
- **Performance Metrics**: Built-in performance monitoring
- **Error Tracking**: Comprehensive error logging and tracking

## 🔐 Security

### Features
- **Rate Limiting**: API rate limiting to prevent abuse
- **Authentication**: JWT-based authentication
- **Circuit Breakers**: Protection against cascading failures
- **Audit Logging**: Comprehensive audit trails
- **Data Encryption**: Sensitive data encryption at rest and in transit

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript strict mode for frontend code
- Write comprehensive tests for new features
- Update documentation for API changes
- Use conventional commits for better tracking

## 📋 API Documentation

### Core Endpoints
- `POST /api/leads` - Create new lead
- `GET /api/leads/{id}` - Get lead by ID
- `PUT /api/leads/{id}` - Update lead
- `POST /api/webhooks/instagram` - Instagram webhook handler
- `POST /api/webhooks/whatsapp` - WhatsApp webhook handler
- `POST /api/webhooks/email` - Email webhook handler

### AI Enhancement Endpoints
- `POST /api/ai/analyze` - AI-powered lead analysis
- `POST /api/ai/qualify` - Intelligent lead qualification
- `POST /api/ai/route` - Intelligent agent routing
- `POST /api/ai/proactive` - Proactive engagement trigger

## 🗺️ Roadmap

### Phase 1 ✅ Completed
- [x] LangGraph Integration
- [x] Intelligent Model Routing
- [x] Redis Checkpoint System
- [x] Proactive Engagement Engine
- [x] Agent Coordination Patterns

### Phase 2 🔄 In Progress
- [ ] Advanced Conversation Flows
- [ ] Sentiment Analysis Integration
- [ ] Multi-Modal Support (Images, Documents)
- [ ] Voice Integration (Speech-to-Text, Text-to-Speech)

### Phase 3 📋 Planned
- [ ] ML-Based Proactive Timing
- [ ] Advanced Analytics Dashboard
- [ ] Mobile App Integration
- [ ] Advanced CRM Integrations

## 📞 Support

### Documentation
- [LangGraph Enhancement Documentation](backend/LANGGRAPH_ENHANCEMENT_DOCUMENTATION.md) - Detailed technical documentation
- [Frontend README](frontend/README.md) - Frontend-specific documentation

### Getting Help
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check the comprehensive documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **LangGraph Team** - For the amazing state management framework
- **FastAPI Team** - For the excellent web framework
- **shadcn/ui Team** - For the beautiful component library
- **OpenRouter** - For providing access to multiple LLM models
- **Redis Team** - For the powerful caching solution

---

**Built with ❤️ for modern real estate professionals**

*Last Updated: 2025-11-02*