import { useEffect, useState } from 'react'
import { useScan } from '../../contexts/ScanContext'
import { useMarkets } from '../../contexts/MarketsContext'
import { getScanStatus } from '../../api/client'

function relativeTime(iso: string | null | undefined): string | null {
  if (!iso) return null
  const ms = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(ms) || ms < 0) return null
  const minutes = Math.floor(ms / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function ScanStatusBar() {
  const { isScanning, summary, sourceStatuses, error, triggerScan, stopScan } = useScan()
  const { activeMarketId } = useMarkets()
  const [lastCompletedAt, setLastCompletedAt] = useState<string | null>(null)

  useEffect(() => {
    if (!activeMarketId || isScanning) return
    let cancelled = false
    getScanStatus(activeMarketId)
      .then(s => { if (!cancelled) setLastCompletedAt(s.last_completed_at ?? null) })
      .catch(() => { /* silent */ })
    return () => { cancelled = true }
  }, [activeMarketId, isScanning, summary])

  if (!isScanning && !summary) {
    const freshness = relativeTime(lastCompletedAt)
    return (
      <div className="flex items-center gap-3">
        <button
          onClick={() => activeMarketId && triggerScan(activeMarketId)}
          disabled={!activeMarketId}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Scan
        </button>
        {freshness && (
          <span className="text-xs text-gray-500">Last scan: {freshness}</span>
        )}
      </div>
    )
  }

  if (isScanning) {
    const sources = Object.entries(sourceStatuses)
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          Scanning…
        </span>
        {sources.map(([src, s]) => (
          <span key={src} className="text-gray-500">
            {src}: {s?.count ?? 0}
          </span>
        ))}
        {error && <span className="text-amber-600 text-xs">{error}</span>}
        <button onClick={stopScan} className="ml-2 text-gray-400 hover:text-gray-600 text-xs">
          Stop
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-4 text-sm text-gray-600">
      <span>
        Found <strong>{summary?.total}</strong> deals
        {summary?.strong ? ` · ${summary.strong} STRONG` : ''}
        {summary?.good ? ` · ${summary.good} GOOD` : ''}
      </span>
      <button
        onClick={() => activeMarketId && triggerScan(activeMarketId)}
        className="px-3 py-1 border border-gray-300 rounded text-sm hover:border-blue-400"
      >
        Rescan
      </button>
    </div>
  )
}
