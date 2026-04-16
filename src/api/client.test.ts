import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchMarkets, createMarket, deleteMarket, startScan, getScanStatus } from './client'

const mockFetch = vi.fn()
global.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  } as Response)
}

describe('fetchMarkets', () => {
  it('calls GET /markets', async () => {
    mockFetch.mockReturnValue(jsonResponse([]))
    await fetchMarkets()
    expect(mockFetch).toHaveBeenCalledWith('/markets', expect.objectContaining({ method: 'GET' }))
  })

  it('returns parsed market list', async () => {
    const markets = [{ id: '1', name: 'Cleveland OH' }]
    mockFetch.mockReturnValue(jsonResponse(markets))
    const result = await fetchMarkets()
    expect(result).toEqual(markets)
  })
})

describe('createMarket', () => {
  it('calls POST /markets with JSON body', async () => {
    const market = { name: 'Cleveland OH', city: 'Cleveland', state: 'OH', zip_codes: ['44101'] }
    mockFetch.mockReturnValue(jsonResponse({ id: '1', ...market, created_at: '' }))
    await createMarket(market)
    expect(mockFetch).toHaveBeenCalledWith('/markets', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(market),
    }))
  })

  it('returns created market', async () => {
    const created = { id: 'abc', name: 'Cleveland OH', city: 'Cleveland', state: 'OH', zip_codes: ['44101'], created_at: '' }
    mockFetch.mockReturnValue(jsonResponse(created))
    const result = await createMarket({ name: 'Cleveland OH', city: 'Cleveland', state: 'OH', zip_codes: ['44101'] })
    expect(result.id).toBe('abc')
  })

  it('throws on non-2xx response', async () => {
    mockFetch.mockReturnValue(jsonResponse({ detail: 'Bad request' }, 422))
    await expect(createMarket({ name: '', city: '', state: '', zip_codes: [] })).rejects.toThrow()
  })
})

describe('deleteMarket', () => {
  it('calls DELETE /markets/:id', async () => {
    mockFetch.mockReturnValue(Promise.resolve({ ok: true, status: 204 } as Response))
    await deleteMarket('market-1')
    expect(mockFetch).toHaveBeenCalledWith('/markets/market-1', expect.objectContaining({ method: 'DELETE' }))
  })

  it('throws on 404', async () => {
    mockFetch.mockReturnValue(jsonResponse({ detail: 'Not found' }, 404))
    await expect(deleteMarket('nope')).rejects.toThrow()
  })
})

describe('startScan', () => {
  it('calls POST /scans/:market_id/start', async () => {
    mockFetch.mockReturnValue(jsonResponse({ scan_id: 'scan-1', market_id: 'mkt-1' }))
    await startScan('mkt-1')
    expect(mockFetch).toHaveBeenCalledWith('/scans/mkt-1/start', expect.objectContaining({ method: 'POST' }))
  })

  it('returns scan_id and market_id', async () => {
    mockFetch.mockReturnValue(jsonResponse({ scan_id: 'scan-1', market_id: 'mkt-1' }))
    const result = await startScan('mkt-1')
    expect(result.scan_id).toBe('scan-1')
    expect(result.market_id).toBe('mkt-1')
  })
})

describe('getScanStatus', () => {
  it('calls GET /scans/:market_id/status', async () => {
    mockFetch.mockReturnValue(jsonResponse({ scan_id: null, is_active: false, market_id: 'mkt-1' }))
    await getScanStatus('mkt-1')
    expect(mockFetch).toHaveBeenCalledWith('/scans/mkt-1/status', expect.objectContaining({ method: 'GET' }))
  })
})
