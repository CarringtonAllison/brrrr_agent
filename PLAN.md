# BRRRR Deal Finder — Build Plan

> **This file tracks what's built, what's next, and how to pick up work on any machine.**
> Update this file as phases complete. Commit it with your work.

## Quick Start (New Machine)

```bash
git clone https://github.com/CarringtonAllison/brrrr_agent.git
cd brrrr_agent

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows
pip install -r requirements.txt
pytest                          # verify 132 tests pass
cd ..

# Frontend
npm install
npm test                        # verify 1 test passes
```

## Current Status

**Last updated:** 2026-04-16
**Current phase:** Phase 3 COMPLETE — starting Phase 4
**Total backend tests:** 239 passing
**Total frontend tests:** 1 passing
**Commits so far:** 20

---

## What's Built

### Phase 0: Scaffold [COMPLETE]
- [x] GitHub repo: https://github.com/CarringtonAllison/brrrr_agent
- [x] React 19 + TypeScript + Vite frontend scaffold
- [x] FastAPI backend with Python venv
- [x] Tailwind CSS v4, Leaflet, react-leaflet, react-router installed
- [x] Testing configured: pytest (backend), vitest (frontend), playwright (e2e)
- [x] `.gitignore`, `.env.example`, `CLAUDE.md`, `README.md`

### Phase 1: Backend Foundation [COMPLETE]
- [x] `brrrr_calculator.py` — 28 tests
  - Reno budget (22% standard, 30% for <$50k)
  - All-in cost with time-based holding ($500/mo x 4mo)
  - Monthly mortgage amortization
  - Refi at 75% LTV with $3,500 closing
  - Cashflow (50% rule), CoC return, DSCR
  - 70% rule pass/fail
  - Max purchase price reverse-solver
  - Deal grading: STRONG/GOOD/MAYBE/SKIP
  - Full analysis pipeline
- [x] `prefilter.py` — 24 tests
  - Price ($25k-$100k), beds (2-5), property type, sqft (700+), DOM (120)
- [x] `database.py` — 21 tests
  - SQLite with WAL mode, address normalization, fuzzy matching (rapidfuzz 88%)
  - Market CRUD, listing upsert with price change tracking
  - Full schema: markets, listings, pipeline_runs, comp_cache, rental_comps, geocode_cache, scraper_health
- [x] `config.py` — all settings with env var loading
- [x] `models.py` — Pydantic models for API
- [x] `main.py` + `routers/markets.py` — 6 tests
  - FastAPI app factory, CORS for localhost:5173
  - Health endpoint, market CRUD (GET/POST/DELETE)

---

## What's Next

### Phase 2: Scrapers [COMPLETE]
- [x] `geocoder.py` — 11 tests
  - Bounding box math for radius-based comp search
  - pgeocode (offline) for ZIP centroid lookups
  - find_nearby_zips: all ZIPs within N miles, sorted by distance
  - Census Bureau geocoder for street address → lat/lon
  - In-memory caching for geocode results
- [x] `scrapers/redfin_api.py` — 13 tests
  - parse_redfin_response strips `{}&&` prefix
  - Extract active listings and sold comps from GIS endpoint
  - URL builders for GIS (active/sold) and similars/solds
  - RedfinScraper class with exponential backoff on 429s
  - Browser-realistic headers, configurable delays
- [x] `scrapers/craigslist_rss.py` — 12 tests
  - RSS URL builder for for-sale and rental feeds
  - Parse price, beds, sqft from CL title format
  - BeautifulSoup extraction for address + description from listing pages
  - CraigslistScraper class with rate limiting
- [x] `scrapers/zillow_scraper.py` — 8 tests
  - DOM extraction from Zillow property cards
  - Cloudflare/CAPTCHA detection
  - Playwright + stealth async scraper (graceful failure)
- [x] `scrapers/scraper_manager.py` — 8 tests
  - Cross-source dedup via normalized address + fuzzy match
  - Merge: Redfin preferred for numerics, CL for descriptions
  - ScraperManager orchestrating Redfin → Craigslist (Zillow async)

### Phase 3: Analysis Pipeline [COMPLETE]

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Test tiered comp filtering, scoring, weighted ARV | `tests/test_comp_analyzer.py` | ✅ 31 tests |
| 2 | Implement comp analyzer | `comp_analyzer.py` | ✅ |
| 3 | Test rental median calc, outlier removal, fallback | `tests/test_rental_estimator.py` | ✅ 22 tests |
| 4 | Implement rental estimator | `rental_estimator.py` | ✅ |
| 5 | Test keyword matching, scoring | `tests/test_motivation_detector.py` | ✅ 31 tests |
| 6 | Implement motivation detector | `motivation_detector.py` | ✅ |
| 7 | Test SSE event generation, phase progression | `tests/test_orchestrator.py` | ✅ 14 tests |
| 8 | Implement orchestrator (async generator → SSE) | `agents/orchestrator.py` | ✅ |
| 9 | Test scan trigger, SSE stream endpoints | `tests/test_scans_router.py` | ✅ 9 tests |
| 10 | Implement scan router | `routers/scans.py` | ✅ |

**Key details:**
- Comp analyzer: 3 sources (Redfin similars/solds + GIS sold + Zillow sold). Tiered filtering (starts tight, widens if < 3 comps). Similarity scoring 0-100: distance(30) + recency(25) + sqft(20) + beds(15) + baths(10). Weighted ARV percentiles. Exclude distressed sales.
- Rental estimator: Craigslist rental data → median + IQR outlier removal. 7-day cache. Fallback: 1.1% of ARV / 12.
- Motivation detector: keyword tiers (high/medium/low signals). Regex for condition patterns. Score 1-10.
- Orchestrator: async generator yielding SSE events. Scrape → prefilter → analysis (parallel with scraping) → AI review (concurrency=3). Pipeline checkpointing to DB.

### Phase 4: React Frontend — Core [NOT STARTED]

| # | Task | File | Status |
|---|------|------|--------|
| 1 | TypeScript type definitions | `src/types/*.ts` | |
| 2 | Test + implement API client | `src/api/` | |
| 3 | Test + implement MarketsContext | `src/contexts/MarketsContext.tsx` | |
| 4 | Implement MarketPillBar + AddMarketInput | `src/components/markets/` | |
| 5 | Test + implement ListingsMap (Leaflet) | `src/components/map/` | |
| 6 | Test + implement DealCard + list + filters | `src/components/listings/` | |
| 7 | Test + implement useScanStream SSE hook | `src/hooks/useScanStream.ts` | |
| 8 | Implement ScanContext + ScanStatusBar | `src/contexts/ScanContext.tsx` | |

**Key details:**
- Leaflet + OpenStreetMap (free, no API key). Color-coded pins: green(STRONG), blue(GOOD), amber(MAYBE), gray(pending).
- SSE via EventSource → `useScanStream` hook. Batch updates with requestAnimationFrame.
- Map ↔ card sync: hover card highlights pin, click pin scrolls to card.
- Client-side filtering (no API calls for filter changes).
- If cached data < 6 hours old, show instantly with "Rescan" option.

### Phase 5: React Frontend — Detail + Interactivity [NOT STARTED]

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Test + implement BRRRRBreakdown | `src/components/detail/BRRRRBreakdown.tsx` | |
| 2 | Deal detail page with routing | `src/App.tsx` routes | |
| 3 | Test + implement CompsTable | `src/components/detail/CompsTable.tsx` | |
| 4 | Implement AIAnalysis component | `src/components/detail/AIAnalysis.tsx` | |
| 5 | Test + implement WhatIfSliders | `src/components/detail/WhatIfSliders.tsx` | |
| 6 | Implement useMapSync hook | `src/hooks/useMapSync.ts` | |
| 7 | Implement Settings page | `src/components/settings/` | |

**Key details:**
- What-If Calculator: sliders for purchase/rehab/rent → hit `/deals/{id}/what-if` (pure math, <100ms).
- "Ask Claude" text input → `/deals/{id}/ask` (tool-use enabled, 3-10s).
- Sensitivity matrix: price x rate → CoC heatmap.

### Phase 6: Claude AI Agents + Tools [NOT STARTED]

| # | Task | File | Status |
|---|------|------|--------|
| 1 | Test all tool implementations | `tests/test_tools.py` | |
| 2 | Implement tools | `agents/tools.py` | |
| 3 | Test deal analyst (tool-use loop, JSON parse, fallback) | `tests/test_deal_analyst.py` | |
| 4 | Implement deal analyst (Sonnet) | `agents/deal_analyst.py` | |
| 5 | Test negotiation agent (offer clamping) | `tests/test_negotiation_agent.py` | |
| 6 | Implement negotiation agent (Haiku) | `agents/negotiation_agent.py` | |
| 7 | Wire agents into orchestrator Stage 3 | `agents/orchestrator.py` | |
| 8 | Test + implement /deals endpoints | `routers/deals.py` | |

**Key details:**
- deal_analyst (Sonnet) tools: calculate_brrrr_scenarios, lookup_rental_comps (HUD+Census), lookup_property_taxes (Census), check_flood_zone (FEMA), calculate_max_purchase_price, estimate_rehab_costs, lookup_area_demographics (Census).
- negotiation_agent (Haiku) tools: analyze_seller_motivation, calculate_max_purchase_price.
- System prompt: "Never accept numbers at face value. Always run at least one downside scenario."
- Offer range is code-clamped: offer_range_high can never exceed max_purchase_breakeven.
- All data sources free: Census ACS, FEMA NFHL, HUD FMR APIs.

### Phase 7: E2E Tests + Polish [NOT STARTED]

| # | Task | Status |
|---|------|--------|
| 1 | Playwright E2E: full scan flow | |
| 2 | Playwright E2E: deal detail + what-if | |
| 3 | Optional email digest (notifier.py) | |
| 4 | Loading skeletons, error states | |
| 5 | Cache freshness indicators, SSE reconnect | |
| 6 | Final README.md, CLAUDE.md updates | |

---

## Development Workflow

### TDD Cycle
1. **Red:** Write failing test → commit: `"add failing test for {feature}"`
2. **Green:** Implement → commit: `"implement {feature}"`
3. **Refactor** if needed → commit: `"refactor {feature}"`

### Commit Rules
- **No AI/Claude references in commits** — no Co-Authored-By, no "Claude", no "AI-generated"
- Concise, imperative mood: `"add brrrr calculator with mortgage formula"`
- Multiple commits per phase (3-6 minimum)

### Running Tests
```bash
# Backend (from backend/)
source venv/bin/activate    # or venv\Scripts\activate on Windows
pytest -v                   # all tests
pytest tests/test_foo.py -v # single file

# Frontend (from project root)
npm test                    # vitest run
npm run test:watch          # vitest watch mode

# E2E (from project root)
npx playwright test         # requires dev server running
```

### Running the App
```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
npm run dev
# → http://localhost:5173
```

---

## Architecture Quick Reference

### SSE Event Protocol
```typescript
type ScanEvent =
  | { type: "source_status"; source: "redfin"|"craigslist"|"zillow"; status: "scraping"|"done"|"error"; count: number }
  | { type: "listing"; listing: Listing }
  | { type: "analysis_update"; listing_id: string; brrrr: BRRRRAnalysis }
  | { type: "ai_review"; listing_id: string; review: DealReview }
  | { type: "done"; summary: { total: number; strong: number; good: number } }
```

### API Endpoints
```
GET    /health
GET    /markets                         ← DONE
POST   /markets                         ← DONE
DELETE /markets/{id}                    ← DONE
POST   /scans/{market_id}/start
GET    /scans/{scan_id}/stream          (SSE)
GET    /scans/{market_id}/status
GET    /markets/{id}/listings
GET    /listings/{id}
GET    /listings/{id}/comps
POST   /deals/{id}/what-if
POST   /deals/{id}/ask
GET    /deals/{id}/sensitivity
GET    /settings
PUT    /settings
```

### BRRRR Grading
```
SKIP   — 70% rule fails OR no comp data
STRONG — cash_left <= $5k, coc >= 15%, rent_ratio >= 1.2%, dscr >= 1.25, rent achievable
GOOD   — cash_left <= $15k, coc >= 12%, rent_ratio >= 1.0%, dscr >= 1.20
MAYBE  — cash_left <= $25k, coc >= 8%, rent_ratio >= 0.8%, dscr >= 1.10
SKIP   — anything else
```

### Grade Colors
```
STRONG  → #22C55E (green)
GOOD    → #3B82F6 (blue)
MAYBE   → #F59E0B (amber)
SKIP    → #EF4444 (red)
Pending → #6B7280 (gray)
```

### File Map (what exists)
```
backend/
  main.py              ✅ FastAPI app factory + health endpoint
  config.py            ✅ All settings, env vars
  models.py            ✅ Pydantic API models
  database.py          ✅ SQLite + normalization + CRUD
  brrrr_calculator.py  ✅ Full BRRRR formula engine
  prefilter.py         ✅ Listing pre-filter
  geocoder.py          ✅ Bounding box, ZIP proximity, Census geocoder
  comp_analyzer.py     ✅ Phase 3
  rental_estimator.py  ✅ Phase 3
  motivation_detector.py ✅ Phase 3
  routers/
    markets.py         ✅ Market CRUD
    scans.py           ✅ Phase 3
    listings.py        ⬜ Phase 4
    deals.py           ⬜ Phase 6
  scrapers/
    redfin_api.py      ✅ GIS active/sold + similars/solds + retry
    craigslist_rss.py  ✅ RSS for-sale + rentals + page extraction
    zillow_scraper.py  ✅ Playwright + stealth + CF detection
    scraper_manager.py ✅ Cross-source dedup + merge
  agents/
    orchestrator.py    ✅ Phase 3
    deal_analyst.py    ⬜ Phase 6
    negotiation_agent.py ⬜ Phase 6
    tools.py           ⬜ Phase 6
  notifier.py          ⬜ Phase 7
  tests/
    test_smoke.py         ✅
    test_brrrr_calculator.py ✅ 28 tests
    test_prefilter.py     ✅ 24 tests
    test_database.py      ✅ 21 tests
    test_markets_router.py ✅ 6 tests
    test_comp_analyzer.py  ✅ 31 tests
    test_rental_estimator.py ✅ 22 tests
    test_motivation_detector.py ✅ 31 tests
    test_orchestrator.py   ✅ 14 tests
    test_scans_router.py   ✅ 9 tests
src/
  App.tsx              ✅ Minimal shell
  App.test.tsx         ✅ 1 smoke test
  main.tsx             ✅
  index.css            ✅ Tailwind import
```
