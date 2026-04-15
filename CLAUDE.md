# BRRRR Deal Finder

## Overview
Full-stack BRRRR real estate deal finder. React frontend + FastAPI backend + AI-powered deal analysis.

## Project Structure
- `backend/` — FastAPI application (Python)
- `src/` — React frontend (TypeScript)
- Tests are colocated: `foo.py` → `test_foo.py`, `Foo.tsx` → `Foo.test.tsx`

## Development
- Backend: `cd backend && uvicorn main:app --reload --port 8000`
- Frontend: `npm run dev` (Vite on port 5173, proxied to backend)
- Backend tests: `cd backend && pytest`
- Frontend tests: `npm test`
- E2E tests: `npx playwright test`

## Conventions
- TDD: write failing tests first, then implement
- Commit frequently with concise imperative messages
- Named exports only (no default exports)
- Type hints on all Python functions
- TypeScript strict mode
- Tailwind CSS for all styling
