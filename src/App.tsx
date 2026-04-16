import { useState } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router'
import { MarketsProvider } from './contexts/MarketsContext'
import { ScanProvider } from './contexts/ScanContext'
import { MarketPillBar } from './components/markets/MarketPillBar'
import { AddMarketInput } from './components/markets/AddMarketInput'
import { ScanStatusBar } from './components/listings/ScanStatusBar'
import { DealCard } from './components/listings/DealCard'
import { ListingsMap } from './components/map/ListingsMap'
import { SettingsPage } from './components/settings/SettingsPage'
import { DealDetailPage } from './pages/DealDetailPage'
import { useScan } from './contexts/ScanContext'
import type { Listing } from './types'

function Dashboard() {
  const { listings } = useScan()
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  function selectListing(l: Listing) {
    const id = l.id ?? l.address
    setSelectedId(id)
  }

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
              onSelect={(l: Listing) => {
                selectListing(l)
                navigate(`/deals/${l.id ?? l.address}`)
              }}
            />
          ))
        )}
      </div>
      <div className="flex-1 rounded-lg overflow-hidden border border-gray-200">
        <ListingsMap
          listings={listings}
          highlightedId={selectedId}
          onSelectListing={(l: Listing) => {
            selectListing(l)
            navigate(`/deals/${l.id ?? l.address}`)
          }}
        />
      </div>
    </div>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between gap-4">
        <Link to="/" className="text-lg font-bold text-gray-900 shrink-0 hover:text-blue-600">
          BRRRR Deal Finder
        </Link>
        <div className="flex-1 max-w-sm">
          <MarketPillBar />
        </div>
        <div className="flex-1 max-w-xs">
          <AddMarketInput />
        </div>
        <ScanStatusBar />
        <Link to="/settings" className="text-sm text-gray-500 hover:text-gray-700 shrink-0">
          Settings
        </Link>
      </header>
      <main className="flex-1 p-4">
        {children}
      </main>
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <MarketsProvider>
        <ScanProvider>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/deals/:id" element={<DealDetailPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Layout>
        </ScanProvider>
      </MarketsProvider>
    </BrowserRouter>
  )
}
