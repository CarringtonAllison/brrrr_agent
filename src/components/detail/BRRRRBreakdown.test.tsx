import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BRRRRBreakdown } from './BRRRRBreakdown'
import type { Listing } from '../../types'

const listing: Listing = {
  id: 'lst-1',
  address: '123 Elm St',
  city: 'Cleveland',
  state: 'OH',
  zip_code: '44101',
  price: 65_000,
  beds: 3,
  baths: 1,
  sqft: 1100,
  source: 'redfin',
  grade: 'STRONG',
  latitude: null,
  longitude: null,
  days_on_market: 30,
  listing_url: 'https://redfin.com/test',
  arv: 90_000,
  estimated_rent: 950,
  motivation_score: 7,
  motivation_signals: ['motivated seller', 'price reduced'],
  brrrr: {
    cash_left_in_deal: 2_500,
    monthly_cashflow: 148,
    coc_return: 0.17,
    dscr: 1.28,
    rent_to_price: 0.0146,
    seventy_pct_rule_pass: true,
    grade: 'STRONG',
    grade_reasons: ['All STRONG thresholds met'],
  },
}

describe('BRRRRBreakdown', () => {
  it('renders purchase price', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/65,000/)).toBeInTheDocument()
  })

  it('renders ARV', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/90,000/)).toBeInTheDocument()
  })

  it('renders cash left in deal', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/2,500/)).toBeInTheDocument()
  })

  it('renders monthly cashflow', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/\$148/)).toBeInTheDocument()
  })

  it('renders CoC return as percentage', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/17\.0%/)).toBeInTheDocument()
  })

  it('renders DSCR', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/1\.28/)).toBeInTheDocument()
  })

  it('renders grade badge', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText('STRONG')).toBeInTheDocument()
  })

  it('renders 70% rule pass indicator', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/70% Rule/i)).toBeInTheDocument()
  })

  it('renders motivation signals', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/motivated seller/i)).toBeInTheDocument()
  })

  it('renders estimated rent', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByText(/950/)).toBeInTheDocument()
  })

  it('handles null brrrr gracefully', () => {
    render(<BRRRRBreakdown listing={{ ...listing, brrrr: null }} />)
    expect(screen.getByText(/no analysis/i)).toBeInTheDocument()
  })

  it('renders listing url link when present', () => {
    render(<BRRRRBreakdown listing={listing} />)
    expect(screen.getByRole('link', { name: /redfin/i })).toBeInTheDocument()
  })
})
