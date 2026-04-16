import type { Listing } from '../../types'
import { GRADE_CLASSES } from '../../types'

interface Props {
  listing: Listing
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  )
}

function fmt(n: number | null | undefined, prefix = '$'): string {
  if (n == null) return '—'
  return `${prefix}${Math.round(n).toLocaleString()}`
}

export function BRRRRBreakdown({ listing }: Props) {
  if (!listing.brrrr) {
    return <p className="text-gray-400 text-sm">No analysis available yet.</p>
  }

  const { brrrr } = listing
  const gradeClass = GRADE_CLASSES[brrrr.grade]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-900 text-lg">{listing.address}</h2>
        <span className={`px-3 py-1 text-sm font-bold rounded border ${gradeClass}`}>
          {brrrr.grade}
        </span>
      </div>

      {/* Key metrics */}
      <div className="bg-gray-50 rounded-lg p-4 space-y-0">
        <Row label="Purchase Price" value={fmt(listing.price)} />
        <Row label="After Repair Value (ARV)" value={fmt(listing.arv)} />
        <Row label="Estimated Rent" value={`${fmt(listing.estimated_rent)}/mo`} />
        <Row label="Monthly Cashflow" value={`${fmt(brrrr.monthly_cashflow)}/mo`} />
        <Row
          label="Cash-on-Cash Return"
          value={brrrr.coc_return != null ? `${(brrrr.coc_return * 100).toFixed(1)}%` : '∞ (no cash in deal)'}
        />
        <Row label="DSCR" value={brrrr.dscr.toFixed(2)} />
        <Row label="Rent-to-Price" value={`${(brrrr.rent_to_price * 100).toFixed(2)}%`} />
        <Row
          label="Cash Left in Deal"
          value={
            <span className={brrrr.cash_left_in_deal <= 5000 ? 'text-green-600' : ''}>
              {fmt(brrrr.cash_left_in_deal)}
            </span>
          }
        />
        <Row
          label="70% Rule"
          value={
            <span className={brrrr.seventy_pct_rule_pass ? 'text-green-600' : 'text-red-500'}>
              {brrrr.seventy_pct_rule_pass ? '✓ Pass' : '✗ Fail'}
              {' '}(70%)
            </span>
          }
        />
      </div>

      {/* Grade reasons */}
      {brrrr.grade_reasons.length > 0 && (
        <div className="text-xs text-gray-500 space-y-0.5">
          {brrrr.grade_reasons.map((r, i) => <p key={i}>{r}</p>)}
        </div>
      )}

      {/* Motivation signals */}
      {listing.motivation_signals && listing.motivation_signals.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Seller Signals ({listing.motivation_score}/10)
          </p>
          <div className="flex flex-wrap gap-1">
            {listing.motivation_signals.map(s => (
              <span key={s} className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded border border-amber-200">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source link */}
      {listing.listing_url && (
        <a
          href={listing.listing_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
        >
          View on {listing.source === 'redfin' ? 'Redfin' : listing.source} ↗
        </a>
      )}
    </div>
  )
}
