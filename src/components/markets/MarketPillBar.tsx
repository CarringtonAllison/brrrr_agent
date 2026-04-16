import { useMarkets } from '../../contexts/MarketsContext'

export function MarketPillBar() {
  const { markets, activeMarketId, setActiveMarketId } = useMarkets()

  if (markets.length === 0) return null

  return (
    <div className="flex gap-2 flex-wrap">
      {markets.map(m => (
        <button
          key={m.id}
          onClick={() => setActiveMarketId(m.id)}
          className={[
            'px-3 py-1 rounded-full text-sm font-medium border transition-colors',
            activeMarketId === m.id
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400',
          ].join(' ')}
        >
          {m.name}
        </button>
      ))}
    </div>
  )
}
