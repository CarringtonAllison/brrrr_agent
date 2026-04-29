import { test, expect } from '@playwright/test'

const MARKET = {
  id: 'm-1',
  name: 'Cleveland OH',
  city: 'Cleveland',
  state: 'OH',
  zip_codes: ['44101'],
  created_at: '2026-04-29T00:00:00Z',
}

const STRONG_LISTING = {
  id: 'l-1',
  address: '123 Strong St',
  city: 'Cleveland',
  state: 'OH',
  zip_code: '44101',
  price: 55_000,
  beds: 3,
  baths: 1.5,
  sqft: 1100,
  source: 'redfin',
  grade: 'STRONG',
  latitude: 41.5,
  longitude: -81.7,
  days_on_market: 45,
  listing_url: 'https://redfin.com/test-1',
  arv: 120_000,
  estimated_rent: 1500,
  motivation_score: 6,
  motivation_signals: ['motivated seller'],
  brrrr: {
    cash_left_in_deal: 2000,
    monthly_cashflow: 220,
    coc_return: 0.18,
    dscr: 1.32,
    rent_to_price: 0.027,
    seventy_pct_rule_pass: true,
    grade: 'STRONG',
    grade_reasons: ['All STRONG thresholds met'],
  },
}

const GOOD_LISTING = {
  ...STRONG_LISTING,
  id: 'l-2',
  address: '456 Good Ave',
  grade: 'GOOD',
  brrrr: { ...STRONG_LISTING.brrrr, grade: 'GOOD' },
}

function sseBody(events: object[]): string {
  return events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
}

test.beforeEach(async ({ page }) => {
  await page.route('**/markets', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([MARKET]) })
    } else {
      await route.continue()
    }
  })

  await page.route('**/scans/m-1/start', async route => {
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ scan_id: 's-1', market_id: 'm-1' }),
    })
  })

  await page.route('**/scans/s-1/stream', async route => {
    const body = sseBody([
      { type: 'source_status', source: 'redfin', status: 'scraping', count: 0 },
      { type: 'source_status', source: 'redfin', status: 'done', count: 2 },
      { type: 'listing', listing: STRONG_LISTING },
      { type: 'listing', listing: GOOD_LISTING },
      { type: 'done', summary: { total: 2, strong: 1, good: 1 } },
    ])
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache' },
      body,
    })
  })
})

test('full scan flow: dashboard renders, scan triggers, listings appear with grades', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('link', { name: /BRRRR Deal Finder/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Cleveland OH$/ })).toBeVisible()

  await expect(page.getByText(/No listings yet/i)).toBeVisible()

  await page.getByRole('button', { name: /^Scan$/ }).click()

  await expect(page.getByText(/123 Strong St/)).toBeVisible({ timeout: 5000 })
  await expect(page.getByText(/456 Good Ave/)).toBeVisible()

  // Grade pills
  await expect(page.locator('text=STRONG').first()).toBeVisible()
  await expect(page.locator('text=GOOD').first()).toBeVisible()

  // Summary line after done
  await expect(page.getByText(/Found.*2.*deals/i)).toBeVisible({ timeout: 5000 })
})

test('clicking a deal navigates to detail page', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /^Scan$/ }).click()
  await expect(page.getByText(/123 Strong St/)).toBeVisible({ timeout: 5000 })

  await page.getByText(/123 Strong St/).first().click()
  await expect(page).toHaveURL(/\/deals\/l-1/)
  await expect(page.getByRole('heading', { name: /123 Strong St/ })).toBeVisible()
})
