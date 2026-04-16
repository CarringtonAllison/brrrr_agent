import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CompsTable } from './CompsTable'

const comps = [
  {
    address: '100 Oak Ave',
    price: 85_000,
    sqft: 1150,
    beds: 3,
    baths: 1,
    sold_date: '2026-01-15',
    distance_miles: 0.3,
    score: 88,
    source: 'redfin',
  },
  {
    address: '200 Maple St',
    price: 92_000,
    sqft: 1300,
    beds: 3,
    baths: 1.5,
    sold_date: '2025-11-20',
    distance_miles: 0.7,
    score: 74,
    source: 'redfin',
  },
  {
    address: '300 Pine Rd',
    price: 78_000,
    sqft: 1050,
    beds: 2,
    baths: 1,
    sold_date: '2025-09-05',
    distance_miles: 1.1,
    score: 60,
    source: 'zillow',
  },
]

describe('CompsTable', () => {
  it('renders all comp addresses', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getByText('100 Oak Ave')).toBeInTheDocument()
    expect(screen.getByText('200 Maple St')).toBeInTheDocument()
    expect(screen.getByText('300 Pine Rd')).toBeInTheDocument()
  })

  it('renders sale prices', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getAllByText(/85,000/).length).toBeGreaterThan(0)
    expect(screen.getByText(/92,000/)).toBeInTheDocument()
  })

  it('renders distance', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getByText(/0\.3\s*mi/i)).toBeInTheDocument()
  })

  it('renders similarity score', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getByText(/88/)).toBeInTheDocument()
  })

  it('renders sold date', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getByText(/2026-01-15/)).toBeInTheDocument()
  })

  it('renders ARV estimate row', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    expect(screen.getByText(/arv estimate/i)).toBeInTheDocument()
  })

  it('renders empty state when no comps', () => {
    render(<CompsTable comps={[]} arv={null} />)
    expect(screen.getByText(/no comp/i)).toBeInTheDocument()
  })

  it('sorts by score descending by default', () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    const rows = screen.getAllByRole('row')
    // First data row (index 1, after header) should be highest score
    expect(rows[1]).toHaveTextContent('100 Oak Ave')
  })

  it('can sort by price when column header clicked', async () => {
    render(<CompsTable comps={comps} arv={85_000} />)
    // Default is score desc; clicking Price sorts by price desc first
    const priceHeader = screen.getAllByRole('columnheader').find(h => h.textContent?.includes('Price'))!
    await userEvent.click(priceHeader)
    const rows = screen.getAllByRole('row')
    // Price descending → highest price ($92k) is first data row
    expect(rows[1]).toHaveTextContent('92,000')
  })
})
