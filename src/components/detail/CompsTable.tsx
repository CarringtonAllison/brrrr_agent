import { useState } from 'react'

interface Comp {
  address: string
  price: number
  sqft?: number | null
  beds?: number | null
  baths?: number | null
  sold_date?: string | null
  distance_miles?: number | null
  score?: number | null
  source?: string
}

type SortKey = 'score' | 'price' | 'distance_miles' | 'sold_date'

interface Props {
  comps: Comp[]
  arv: number | null
}

function fmt(n: number | null | undefined, prefix = '$'): string {
  if (n == null) return '—'
  return `${prefix}${Math.round(n).toLocaleString()}`
}

export function CompsTable({ comps, arv }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortAsc, setSortAsc] = useState(false)

  if (comps.length === 0) {
    return <p className="text-gray-400 text-sm">No comp data available.</p>
  }

  const sorted = [...comps].sort((a, b) => {
    const av = (a[sortKey] ?? -Infinity) as number
    const bv = (b[sortKey] ?? -Infinity) as number
    return sortAsc ? av - bv : bv - av
  })

  function handleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  function ColHeader({ label, col }: { label: string; col: SortKey }) {
    const active = sortKey === col
    return (
      <th
        onClick={() => handleSort(col)}
        className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-700 select-none"
      >
        {label}{active ? (sortAsc ? ' ↑' : ' ↓') : ''}
      </th>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Address</th>
            <ColHeader label="Price" col="price" />
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Beds/Baths</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Sqft</th>
            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Sold</th>
            <ColHeader label="Distance" col="distance_miles" />
            <ColHeader label="Score" col="score" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sorted.map((c, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium text-gray-900">{c.address}</td>
              <td className="px-3 py-2">{fmt(c.price)}</td>
              <td className="px-3 py-2 text-gray-600">{c.beds ?? '—'} / {c.baths ?? '—'}</td>
              <td className="px-3 py-2 text-gray-600">{c.sqft?.toLocaleString() ?? '—'}</td>
              <td className="px-3 py-2 text-gray-600">{c.sold_date ?? '—'}</td>
              <td className="px-3 py-2 text-gray-600">{c.distance_miles != null ? `${c.distance_miles} mi` : '—'}</td>
              <td className="px-3 py-2">
                {c.score != null && (
                  <span className="inline-block px-1.5 py-0.5 bg-blue-50 text-blue-700 text-xs rounded">
                    {Math.round(c.score)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
        {arv != null && (
          <tfoot className="bg-gray-50 border-t-2 border-gray-300">
            <tr>
              <td className="px-3 py-2 font-semibold text-gray-700">ARV Estimate</td>
              <td className="px-3 py-2 font-semibold text-gray-900">{fmt(arv)}</td>
              <td colSpan={5} />
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
