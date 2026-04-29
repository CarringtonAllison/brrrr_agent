import type { Listing, Market, MarketCreate, ScanStatus } from '../types'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...init.headers },
    ...init,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `HTTP ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

export function fetchMarkets(): Promise<Market[]> {
  return request('/markets', { method: 'GET' })
}

export function createMarket(data: MarketCreate): Promise<Market> {
  return request('/markets', { method: 'POST', body: JSON.stringify(data) })
}

export function deleteMarket(id: string): Promise<void> {
  return request(`/markets/${id}`, { method: 'DELETE' })
}

export function startScan(marketId: string): Promise<{ scan_id: string; market_id: string }> {
  return request(`/scans/${marketId}/start`, { method: 'POST' })
}

export function getScanStatus(marketId: string): Promise<ScanStatus> {
  return request(`/scans/${marketId}/status`, { method: 'GET' })
}

export function fetchMarketListings(marketId: string): Promise<Listing[]> {
  return request(`/markets/${marketId}/listings`, { method: 'GET' })
}
