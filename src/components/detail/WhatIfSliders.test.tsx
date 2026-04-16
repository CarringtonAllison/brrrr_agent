import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WhatIfSliders } from './WhatIfSliders'

const mockFetch = vi.fn()
global.fetch = mockFetch

const baseListing = {
  id: 'lst-1',
  price: 65_000,
  arv: 90_000,
  estimated_rent: 950,
  brrrr: {
    cash_left_in_deal: 2_500,
    monthly_cashflow: 148,
    coc_return: 0.17,
    dscr: 1.28,
    rent_to_price: 0.0146,
    seventy_pct_rule_pass: true,
    grade: 'STRONG' as const,
    grade_reasons: [],
  },
}

const mockWhatIfResult = {
  brrrr: {
    cash_left_in_deal: 5_000,
    monthly_cashflow: 200,
    coc_return: 0.20,
    dscr: 1.35,
    rent_to_price: 0.016,
    seventy_pct_rule_pass: true,
    grade: 'STRONG' as const,
    grade_reasons: [],
  },
}

beforeEach(() => {
  mockFetch.mockReset()
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(mockWhatIfResult),
  })
})

describe('WhatIfSliders', () => {
  it('renders purchase price slider', () => {
    render(<WhatIfSliders listing={baseListing} />)
    expect(screen.getByLabelText(/purchase price/i)).toBeInTheDocument()
  })

  it('renders ARV slider', () => {
    render(<WhatIfSliders listing={baseListing} />)
    expect(screen.getByLabelText(/arv/i)).toBeInTheDocument()
  })

  it('renders rent slider', () => {
    render(<WhatIfSliders listing={baseListing} />)
    expect(screen.getByLabelText(/rent/i)).toBeInTheDocument()
  })

  it('shows current values on sliders', () => {
    render(<WhatIfSliders listing={baseListing} />)
    const purchaseSlider = screen.getByLabelText(/purchase price/i) as HTMLInputElement
    expect(Number(purchaseSlider.value)).toBe(65_000)
  })

  it('calls what-if API when slider changes', async () => {
    render(<WhatIfSliders listing={baseListing} />)
    const slider = screen.getByLabelText(/purchase price/i)
    fireEvent.change(slider, { target: { value: '70000' } })
    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith(
      '/deals/lst-1/what-if',
      expect.objectContaining({ method: 'POST' }),
    ))
  })

  it('displays updated cashflow after API response', async () => {
    render(<WhatIfSliders listing={baseListing} />)
    const slider = screen.getByLabelText(/purchase price/i)
    fireEvent.change(slider, { target: { value: '70000' } })
    await waitFor(() => expect(screen.getByText(/\$200\/mo/i)).toBeInTheDocument())
  })

  it('shows baseline values initially', () => {
    render(<WhatIfSliders listing={baseListing} />)
    expect(screen.getByText(/\$148\/mo/i)).toBeInTheDocument()
  })

  it('has a reset button that restores original values', async () => {
    render(<WhatIfSliders listing={baseListing} />)
    const slider = screen.getByLabelText(/purchase price/i)
    fireEvent.change(slider, { target: { value: '70000' } })
    await waitFor(() => mockFetch.mock.calls.length > 0)

    await userEvent.click(screen.getByRole('button', { name: /reset/i }))
    const resetSlider = screen.getByLabelText(/purchase price/i) as HTMLInputElement
    expect(Number(resetSlider.value)).toBe(65_000)
  })
})
