import { createContext, useContext, useCallback, type ReactNode } from 'react'
import { useScanStream } from '../hooks/useScanStream'
import { startScan } from '../api/client'
import type { Listing } from '../types'

interface ScanContextValue {
  isScanning: boolean
  listings: Listing[]
  summary: { total: number; strong: number; good: number } | null
  sourceStatuses: Partial<Record<string, { status: string; count: number }>>
  error: string | null
  triggerScan: (marketId: string) => Promise<void>
  stopScan: () => void
}

const ScanContext = createContext<ScanContextValue | null>(null)

export function ScanProvider({ children }: { children: ReactNode }) {
  const { isScanning, listings, summary, sourceStatuses, error, startStream, stopStream } = useScanStream()

  const triggerScan = useCallback(async (marketId: string) => {
    const { scan_id } = await startScan(marketId)
    startStream(scan_id)
  }, [startStream])

  return (
    <ScanContext.Provider value={{ isScanning, listings, summary, sourceStatuses, error, triggerScan, stopScan: stopStream }}>
      {children}
    </ScanContext.Provider>
  )
}

export function useScan(): ScanContextValue {
  const ctx = useContext(ScanContext)
  if (!ctx) throw new Error('useScan must be used inside ScanProvider')
  return ctx
}
