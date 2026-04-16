import { useState } from 'react'
import { MarketsProvider } from './contexts/MarketsContext'
import { ScanProvider } from './contexts/ScanContext'
import { MarketPillBar } from './components/markets/MarketPillBar'
import { AddMarketInput } from './components/markets/AddMarketInput'
import { ScanStatusBar } from './components/listings/ScanStatusBar'
import { DealCard } from './components/listings/DealCard'
import { ListingsMap } from './components/map/ListingsMap'
import { useScan } from './contexts/ScanContext'
import type { Listing } from './types'

function Dashboard() {
  const { listings } = useScan()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  return (
    <div className="flex h-full gap-4">
      <div className="w-80 shrink-0 overflow-y-auto flex flex-col gap-2 pr-1">
        {listings.length === 0 ? (
          <p className="text-gray-400 text-sm text-center mt-8">No listings yet — start a scan.</p>
        ) : (
          listings.map(listing => (
            <DealCard
              key={listing.id ?? listing.address}
              listing={listing}
              isHighlighted={selectedId === (listing.id ?? listing.address)}
              onSelect={(l: Listing) => setSelectedId(l.id ?? l.address)}
            />
          ))
        )}
      </div>
      <div className="flex-1 rounded-lg overflow-hidden border border-gray-200">
        <ListingsMap
          listings={listings}
          highlightedId={selectedId}
          onSelectListing={(l: Listing) => setSelectedId(l.id ?? l.address)}
        />
      </div>
    </div>
  )
}

export function App() {
  return (
    <MarketsProvider>
      <ScanProvider>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between gap-4">
            <h1 className="text-lg font-bold text-gray-900 shrink-0">BRRRR Deal Finder</h1>
            <div className="flex-1 max-w-sm">
              <MarketPillBar />
            </div>
            <div className="flex-1 max-w-xs">
              <AddMarketInput />
            </div>
            <ScanStatusBar />
          </header>
          <main className="flex-1 p-4">
            <Dashboard />
          </main>
        </div>
      </ScanProvider>
    </MarketsProvider>
  )
}
