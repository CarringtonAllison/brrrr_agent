import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MarketsProvider, useMarkets } from './MarketsContext'
import * as client from '../api/client'
import type { Market } from '../types'

vi.mock('../api/client')

const mockMarket: Market = {
  id: 'mkt-1',
  name: 'Cleveland OH',
  city: 'Cleveland',
  state: 'OH',
  zip_codes: ['44101'],
  created_at: '2026-01-01T00:00:00Z',
}

function TestConsumer() {
  const { markets, activeMarketId, setActiveMarketId, addMarket, removeMarket, loading } = useMarkets()
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="count">{markets.length}</div>
      <div data-testid="active">{activeMarketId ?? 'none'}</div>
      {markets.map(m => (
        <div key={m.id} data-testid={`market-${m.id}`}>{m.name}</div>
      ))}
      <button onClick={() => addMarket({ name: 'Test', city: 'Test', state: 'OH', zip_codes: ['44101'] })}>
        add
      </button>
      <button onClick={() => markets[0] && removeMarket(markets[0].id)}>remove</button>
      <button onClick={() => setActiveMarketId('mkt-1')}>select</button>
    </div>
  )
}

function renderWithProvider() {
  return render(
    <MarketsProvider>
      <TestConsumer />
    </MarketsProvider>
  )
}

describe('MarketsContext', () => {
  beforeEach(() => {
    vi.mocked(client.fetchMarkets).mockResolvedValue([mockMarket])
    vi.mocked(client.createMarket).mockResolvedValue({ ...mockMarket, id: 'mkt-2', name: 'Test' })
    vi.mocked(client.deleteMarket).mockResolvedValue(undefined)
  })

  it('loads markets on mount', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'))
    expect(screen.getByTestId('market-mkt-1').textContent).toBe('Cleveland OH')
  })

  it('shows loading true initially', () => {
    renderWithProvider()
    expect(screen.getByTestId('loading').textContent).toBe('true')
  })

  it('shows loading false after fetch', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))
  })

  it('addMarket calls API and updates state', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'))

    await act(async () => {
      await userEvent.click(screen.getByText('add'))
    })

    expect(client.createMarket).toHaveBeenCalledWith({ name: 'Test', city: 'Test', state: 'OH', zip_codes: ['44101'] })
    expect(screen.getByTestId('count').textContent).toBe('2')
  })

  it('removeMarket calls API and updates state', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'))

    await act(async () => {
      await userEvent.click(screen.getByText('remove'))
    })

    expect(client.deleteMarket).toHaveBeenCalledWith('mkt-1')
    expect(screen.getByTestId('count').textContent).toBe('0')
  })

  it('setActiveMarketId updates active market', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('false'))

    await act(async () => {
      await userEvent.click(screen.getByText('select'))
    })

    expect(screen.getByTestId('active').textContent).toBe('mkt-1')
  })

  it('auto-selects first market on load', async () => {
    renderWithProvider()
    await waitFor(() => expect(screen.getByTestId('active').textContent).toBe('mkt-1'))
  })
})
