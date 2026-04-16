import { useParams, useNavigate } from 'react-router'
import { useScan } from '../contexts/ScanContext'
import { BRRRRBreakdown } from '../components/detail/BRRRRBreakdown'
import { WhatIfSliders } from '../components/detail/WhatIfSliders'
import { AIAnalysis } from '../components/detail/AIAnalysis'

export function DealDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { listings } = useScan()
  const navigate = useNavigate()

  const listing = listings.find(l => (l.id ?? l.address) === id)

  if (!listing) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Listing not found.</p>
        <button onClick={() => navigate('/')} className="mt-4 text-blue-600 hover:underline text-sm">
          ← Back to dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <button onClick={() => navigate(-1)} className="text-blue-600 hover:underline text-sm">
        ← Back
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <BRRRRBreakdown listing={listing} />
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <WhatIfSliders listing={listing} />
        </div>
      </div>

      {listing.id && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <AIAnalysis listingId={listing.id} />
        </div>
      )}
    </div>
  )
}
