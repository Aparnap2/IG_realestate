# AGENTS.md - Repository Guidelines

## Build/Lint/Test Commands
- **Frontend**: Use Vite (npm run dev, npm run build). No explicit lint script; rely on TypeScript strict mode.
- **Backend**: Run tests with `pytest backend/tests/` (from backend dir). For single test: `pytest backend/tests/test_file.py::test_function`.
- **E2E Tests**: Use Playwright: `npx playwright test frontend/tests/e2e/`.
- **Coverage**: Pytest includes `--cov=. --cov-report=html` for backend.

## Code Style Guidelines
- **Frontend (React/TypeScript)**: Use strict TypeScript (tsconfig.json). Imports: Relative paths or @/ aliases. Components: PascalCase, hooks: camelCase. Error handling: Try-catch in async functions.
- **Backend (Python/FastAPI)**: Docstrings for functions/classes. Imports: Standard library first, then third-party. Naming: snake_case for functions/variables, PascalCase for classes. Error handling: Try-except with specific exceptions.
- **General**: Follow existing patterns; use interfaces for types. No comments unless asked. From .zencoder/rules/repo.md: Use Playwright for E2E, pytest for backend unit/integration tests.