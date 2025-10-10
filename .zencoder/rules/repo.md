# Repository Rules and Testing Framework

## Testing Framework
- **Primary Framework**: Playwright
- **Test Directory**: `frontend/tests/e2e/`
- **Configuration**: `frontend/playwright.config.ts`
- **Backend Tests**: Python pytest in `backend/tests/`

## Project Structure
- **Frontend**: React (Vite + shadcn/ui) at `/frontend`
- **Backend**: FastAPI with LangGraph swarm at `/backend`
- **Database**: Supabase for auth/DB, Redis for state/caching
- **Integrations**: Meta (IG/WhatsApp), Google Calendar, HubSpot, OpenRouter

## Testing Strategy
- E2E tests with Playwright for frontend workflows
- Unit/integration tests with pytest for backend
- Full system tests for PRD compliance verification