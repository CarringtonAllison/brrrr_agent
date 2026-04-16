import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DealCard } from './DealCard'
import type { Listing } from '../../types'

const baseListing: Listing = {
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
  latitude: 41.4993,
  longitude: -81.6944,
  days_on_market: 30,
  listing_url: 'https://redfin.com/test',
  arv: 90_000,
  estimated_rent: 950,
  motivation_score: 7,
  motivation_signals: ['motivated seller'],
  brrrr: {
    cash_left_in_deal: 2000,
    monthly_cashflow: 150,
    coc_return: 0.18,
    dscr: 1.3,
    rent_to_price: 0.015,
    seventy_pct_rule_pass: true,
    grade: 'STRONG',
    grade_reasons: ['All STRONG thresholds met'],
  },
}

describe('DealCard', () => {
  it('renders address', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText('123 Elm St')).toBeInTheDocument()
  })

  it('renders price formatted', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText(/65,000/)).toBeInTheDocument()
  })

  it('renders grade badge', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText('STRONG')).toBeInTheDocument()
  })

  it('renders beds/baths/sqft', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText(/3\s*bd/i)).toBeInTheDocument()
    expect(screen.getByText(/1\s*ba/i)).toBeInTheDocument()
    expect(screen.getByText(/1,100/)).toBeInTheDocument()
  })

  it('renders cashflow', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText(/\$150\/mo/i)).toBeInTheDocument()
  })

  it('renders motivation score', () => {
    render(<DealCard listing={baseListing} />)
    expect(screen.getByText(/7\s*\/\s*10/)).toBeInTheDocument()
  })

  it('calls onSelect when clicked', async () => {
    const onSelect = vi.fn()
    render(<DealCard listing={baseListing} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('123 Elm St'))
    expect(onSelect).toHaveBeenCalledWith(baseListing)
  })

  it('applies highlighted style when isHighlighted', () => {
    const { container } = render(<DealCard listing={baseListing} isHighlighted />)
    expect(container.firstChild).toHaveClass('ring-2')
  })

  it('shows SKIP grade correctly', () => {
    render(<DealCard listing={{ ...baseListing, grade: 'SKIP' }} />)
    expect(screen.getByText('SKIP')).toBeInTheDocument()
  })

  it('handles null price gracefully', () => {
    render(<DealCard listing={{ ...baseListing, price: null }} />)
    expect(screen.getByText(/n\/a/i)).toBeInTheDocument()
  })
})
