import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchMarkets, createMarket as apiCreate, deleteMarket as apiDelete } from '../api/client'
import type { Market, MarketCreate } from '../types'

interface MarketsContextValue {
  markets: Market[]
  activeMarketId: string | null
  setActiveMarketId: (id: string | null) => void
  addMarket: (data: MarketCreate) => Promise<void>
  removeMarket: (id: string) => Promise<void>
  loading: boolean
  error: string | null
}

const MarketsContext = createContext<MarketsContextValue | null>(null)

export function MarketsProvider({ children }: { children: ReactNode }) {
  const [markets, setMarkets] = useState<Market[]>([])
  const [activeMarketId, setActiveMarketId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchMarkets()
      .then(ms => {
        setMarkets(ms)
        if (ms.length > 0) setActiveMarketId(ms[0].id)
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  async function addMarket(data: MarketCreate) {
    const created = await apiCreate(data)
    setMarkets(prev => [...prev, created])
  }

  async function removeMarket(id: string) {
    await apiDelete(id)
    setMarkets(prev => prev.filter(m => m.id !== id))
    if (activeMarketId === id) {
      setActiveMarketId(markets.find(m => m.id !== id)?.id ?? null)
    }
  }

  return (
    <MarketsContext.Provider value={{ markets, activeMarketId, setActiveMarketId, addMarket, removeMarket, loading, error }}>
      {children}
    </MarketsContext.Provider>
  )
}

export function useMarkets(): MarketsContextValue {
  const ctx = useContext(MarketsContext)
  if (!ctx) throw new Error('useMarkets must be used inside MarketsProvider')
  return ctx
}
