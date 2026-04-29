import type { Listing } from '../../types'
import { GRADE_CLASSES } from '../../types'

interface Props {
  listing: Listing
  onSelect?: (listing: Listing) => void
  isHighlighted?: boolean
}

function fmt(n: number | null | undefined, prefix = '$'): string {
  if (n == null) return 'N/A'
  return `${prefix}${Math.round(n).toLocaleString()}`
}

export function DealCard({ listing, onSelect, isHighlighted }: Props) {
  const gradeClass = listing.grade ? GRADE_CLASSES[listing.grade] : 'text-gray-500 bg-gray-50 border-gray-200'

  return (
    <div
      onClick={() => onSelect?.(listing)}
      className={[
        'bg-white border rounded-lg p-4 cursor-pointer hover:shadow-md transition-shadow',
        isHighlighted ? 'ring-2 ring-blue-400' : '',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 truncate">{listing.address}</p>
          <p className="text-sm text-gray-500">{[listing.city, listing.state].filter(Boolean).join(', ')}</p>
        </div>
        {listing.grade && (
          <span className={`px-2 py-0.5 text-xs font-bold rounded border ${gradeClass}`}>
            {listing.grade}
          </span>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-xl font-bold text-gray-900">{fmt(listing.price)}</span>
      </div>

      <div className="mt-2 flex gap-3 text-sm text-gray-600">
        {listing.beds != null && <span>{listing.beds}&nbsp;bd</span>}
        {listing.baths != null && <span>{listing.baths}&nbsp;ba</span>}
        {listing.sqft != null && <span>{listing.sqft.toLocaleString()}&nbsp;sqft</span>}
      </div>

      {listing.brrrr && (
        <div className="mt-3 border-t pt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
          <span>Cashflow</span>
          <span className="font-medium text-right">
            {fmt(listing.brrrr.monthly_cashflow)}/mo
          </span>
          {listing.brrrr.coc_return != null && (
            <>
              <span>CoC</span>
              <span className="font-medium text-right">
                {(listing.brrrr.coc_return * 100).toFixed(1)}%
              </span>
            </>
          )}
        </div>
      )}

      {listing.motivation_score != null && (
        <div className="mt-2 text-xs text-gray-500">
          Motivation: <span className="font-medium">{listing.motivation_score}&nbsp;/&nbsp;10</span>
        </div>
      )}

      {/* AI review status: subtle pill so users know a verdict is coming or arrived */}
      {(listing.grade === 'STRONG' || listing.grade === 'GOOD' || listing.grade === 'MAYBE') && (
        <div className="mt-2 text-xs">
          {listing.ai_review ? (
            <span className="inline-flex items-center gap-1 text-purple-700">
              AI: <strong>{listing.ai_review.verdict}</strong>
              <span className="text-purple-400">({Math.round(listing.ai_review.confidence * 100)}% conf)</span>
            </span>
          ) : (
            <span className="text-gray-400 italic">AI review pending…</span>
          )}
        </div>
      )}
    </div>
  )
}
