# BRRRR Deal Finder

An interactive real estate deal finder for BRRRR (Buy, Rehab, Rent, Refinance, Repeat) investors. Scrapes listings from multiple sources, analyzes deals with AI-powered comp analysis, and displays results on an interactive map.

## Features

- **Multi-source scraping** — Redfin, Craigslist, Zillow
- **Interactive map** — Color-coded pins by deal grade (Leaflet + OpenStreetMap)
- **Real-time scanning** — Watch listings appear as they're scraped via SSE
- **BRRRR analysis** — Full financial breakdown with corrected formulas
- **AI deal review** — Claude analyzes comps, validates rent, checks flood zones
- **What-If calculator** — Adjust parameters and see metrics update instantly
- **Negotiation insights** — AI-powered offer strategy based on seller motivation

## Tech Stack

- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS
- **Backend:** FastAPI + SQLite
- **Maps:** Leaflet + OpenStreetMap (free)
- **AI:** Claude Sonnet + Haiku with tool-use

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Playwright browsers (`npx playwright install chromium`)

### Setup

```bash
# Clone
git clone https://github.com/CarringtonAllison/brrrr_agent.git
cd brrrr_agent

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env  # edit with your API keys

# Frontend
cd ..
npm install

# Run
cd backend && uvicorn main:app --reload --port 8000 &
npm run dev
```

Open http://localhost:5173

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for deal analysis |
| `GMAIL_ADDRESS` | No | Gmail for email digest |
| `GMAIL_APP_PASSWORD` | No | Gmail app password |
| `NOTIFY_EMAIL` | No | Email to receive digest |
| `HUD_API_KEY` | No | HUD Fair Market Rents API (free) |

## Running Tests

```bash
# Backend (314 tests)
cd backend && source venv/bin/activate && pytest

# Frontend (75 tests)
npm test

# E2E (5 Playwright tests, requires browser)
npx playwright test
```

## API Endpoints

```
GET    /health
GET    /markets
POST   /markets
DELETE /markets/{id}
POST   /scans/{market_id}/start
GET    /scans/{market_id}/status
GET    /scans/{scan_id}/stream            (SSE: source_status | listing | ai_review | done)
GET    /markets/{id}/listings
GET    /listings/{id}
GET    /listings/{id}/comps
POST   /deals/{id}/what-if                (re-run BRRRR with overrides)
POST   /deals/{id}/ask                    (free-form Q&A via Claude Sonnet)
GET    /deals/{id}/sensitivity            (price × interest-rate matrix)
GET    /settings                          (pre-filter thresholds)
PUT    /settings
```

## License

MIT
