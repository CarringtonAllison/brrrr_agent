import { useScan } from '../../contexts/ScanContext'
import { useMarkets } from '../../contexts/MarketsContext'

export function ScanStatusBar() {
  const { isScanning, summary, sourceStatuses, triggerScan, stopScan } = useScan()
  const { activeMarketId } = useMarkets()

  if (!isScanning && !summary) {
    return (
      <div className="flex items-center gap-3">
        <button
          onClick={() => activeMarketId && triggerScan(activeMarketId)}
          disabled={!activeMarketId}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Scan
        </button>
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
