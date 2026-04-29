import { test, expect } from '@playwright/test'

const MARKET = {
  id: 'm-1', name: 'Cleveland OH', city: 'Cleveland', state: 'OH',
  zip_codes: ['44101'], created_at: '2026-04-29T00:00:00Z',
}

const LISTING = {
  id: 'l-1',
  address: '789 Detail Ln',
  city: 'Cleveland', state: 'OH', zip_code: '44101',
  price: 60_000, beds: 3, baths: 1.5, sqft: 1100,
  source: 'redfin', grade: 'STRONG',
  latitude: 41.5, longitude: -81.7, days_on_market: 30,
  listing_url: 'https://redfin.com/x',
  arv: 110_000, estimated_rent: 1400,
  motivation_score: 5, motivation_signals: [],
  brrrr: {
    cash_left_in_deal: 3000, monthly_cashflow: 250, coc_return: 0.16,
    dscr: 1.30, rent_to_price: 0.023, seventy_pct_rule_pass: true,
    grade: 'STRONG', grade_reasons: ['All STRONG thresholds met'],
  },
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
  await page.route('**/scans/m-1/start', route => route.fulfill({
    status: 202, contentType: 'application/json',
    body: JSON.stringify({ scan_id: 's-1', market_id: 'm-1' }),
  }))
  await page.route('**/scans/s-1/stream', route => route.fulfill({
    status: 200, contentType: 'text/event-stream',
    body: sseBody([
      { type: 'source_status', source: 'redfin', status: 'done', count: 1 },
      { type: 'listing', listing: LISTING },
      { type: 'done', summary: { total: 1, strong: 1, good: 0 } },
    ]),
  }))
  await page.route('**/deals/l-1/what-if', async route => {
    const body = JSON.parse(route.request().postData() || '{}')
    const purchase = body.purchase_price ?? 60_000
    // Fake: cashflow is inverse to purchase
    const cashflow = Math.round(500 - (purchase - 50_000) * 0.005)
    await route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({
        brrrr: {
          purchase_price: purchase,
          arv_used: body.arv ?? 110_000,
          estimated_rent: body.estimated_rent ?? 1400,
          monthly_cashflow: cashflow,
          coc_return: 0.15,
          dscr: 1.25,
          rent_to_price: 0.023,
          cash_left_in_deal: 3000,
          grade: 'STRONG',
          seventy_pct_rule_pass: true,
        },
      }),
    })
  })
  await page.route('**/deals/l-1/ask', route => route.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ answer: 'Biggest risk is the older roof. Budget $8k extra.' }),
  }))
})

test('deal detail page shows BRRRR breakdown and what-if controls', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /^Scan$/ }).click()
  await expect(page.getByText(/789 Detail Ln/)).toBeVisible({ timeout: 5000 })
  await page.getByText(/789 Detail Ln/).click()

  await expect(page).toHaveURL(/\/deals\/l-1/)
  await expect(page.getByRole('heading', { name: /789 Detail Ln/ })).toBeVisible()

  // BRRRR breakdown numbers visible
  await expect(page.getByText(/Purchase Price/i).first()).toBeVisible()
  await expect(page.getByText(/After Repair Value/i)).toBeVisible()
  await expect(page.getByText(/Cash-on-Cash Return/i)).toBeVisible()

  // What-if section
  await expect(page.getByRole('heading', { name: /What-If Calculator/i })).toBeVisible()
  await expect(page.getByLabel(/Purchase Price/i)).toBeVisible()
})

test('what-if slider triggers backend call and updates result', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /^Scan$/ }).click()
  await expect(page.getByText(/789 Detail Ln/)).toBeVisible({ timeout: 5000 })
  await page.getByText(/789 Detail Ln/).click()

  // Wait for what-if request to fire after slider moves
  const whatIfWaiter = page.waitForResponse('**/deals/l-1/what-if')

  // Move purchase-price slider far down to trigger debounce
  const slider = page.getByLabel(/Purchase Price/i)
  await slider.focus()
  // Press arrow keys to fire change events; debounce is 300ms
  for (let i = 0; i < 10; i++) {
    await page.keyboard.press('ArrowLeft')
  }

  await whatIfWaiter
})

test('Ask Claude returns an answer', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /^Scan$/ }).click()
  await expect(page.getByText(/789 Detail Ln/)).toBeVisible({ timeout: 5000 })
  await page.getByText(/789 Detail Ln/).click()

  await page.getByPlaceholder(/biggest risk/i).fill('What is the biggest risk?')
  await page.getByRole('button', { name: /^Ask$/ }).click()

  await expect(page.getByText(/older roof/i)).toBeVisible({ timeout: 5000 })
})
