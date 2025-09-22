# README.md
# AAA Real Estate Lead Capture Agentic AI System

This is a portfolio piece for the AAA AI Automation Agency, demonstrating an advanced agentic AI system for real estate lead capture, qualification, and meeting scheduling.

## System Overview

The AAA Real Estate Lead Capture Agentic AI System automates lead capture from Instagram and WhatsApp, qualifies leads based on real estate-specific criteria (budget, location, property type), schedules property tours or consultations, and logs interactions to HubSpot and Supabase.

The system features a LangGraph-based swarm of autonomous agents (Qualifier, Scheduler, FollowUp) that communicate via defined patterns, persist state with Redis checkpoints, and use Supabase queries for context. A React dashboard (Vite + shadcn/ui) enables monitoring, customization, configuration, and data management, secured by Supabase auth.

## Key Features

1. **Lead Ingestion**: Capture webhooks from Instagram Graph API and WhatsApp Business API
2. **Agentic Conversation and Qualification**: LangGraph swarm with three agents for lead processing
3. **Meeting Scheduling**: Automated Google Calendar event booking
4. **Human-in-the-Loop (HITL)**: Interrupt for high-value leads
5. **Admin Dashboard**: Real-time monitoring and configuration
6. **Persistence and State Management**: Redis for state and query caching
7. **Error Handling**: Robust error handling with retries and escalations

## Technology Stack

- **Backend**: Python, FastAPI, LangGraph, Celery, Redis, Supabase
- **Frontend**: React (Vite), shadcn/ui
- **AI/ML**: OpenRouter (LLM provider)
- **Integrations**: Instagram, WhatsApp, Google Calendar, HubSpot

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker and Docker Compose
- Supabase account
- API keys for integrations (Meta, Google, HubSpot, OpenRouter)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Run the backend:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   pnpm install
   ```

3. Run the frontend:
   ```bash
   pnpm run dev
   ```

### Docker Setup

You can also run the entire system using Docker Compose:

```bash
docker-compose up --build
```

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Quality

```bash
# Format code
black .

# Check for issues
flake8 .

# Type checking
mypy .
```

## Project Structure

```
.
├── backend/
│   ├── api/          # API endpoints
│   ├── agents/       # LangGraph agents
│   ├── tools/        # Agent tools
│   ├── utils/        # Utility functions
│   ├── models/       # Data models
│   ├── schemas/      # Pydantic schemas
│   ├── config/       # Configuration
│   ├── tasks/        # Celery tasks
│   ├── tests/        # Unit tests
│   ├── main.py       # FastAPI application
│   ├── celery_app.py # Celery application
│   ├── workflow.py   # LangGraph workflow
│   └── ...
├── frontend/
│   ├── src/          # React source code
│   ├── components/   # UI components
│   └── ...
├── docker-compose.yml
├── backend.dockerfile
├── frontend.dockerfile
└── ...
```

## Queueing System

This system uses Redis as the message broker and result backend for Celery tasks. While the original PRD specified RabbitMQ, we've chosen Redis for its simplicity and performance in this context. Redis provides excellent performance for our use case and is easier to set up and maintain.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

## License

This is a portfolio piece for demonstration purposes. All rights reserved by AAA AI Automation Agency.