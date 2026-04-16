import { useCallback, useRef, useState } from 'react'
import type { BRRRRBreakdown } from '../../types'

interface WhatIfListing {
  id?: string
  price: number | null
  arv: number | null
  estimated_rent: number | null
  brrrr: BRRRRBreakdown | null
}

interface Props {
  listing: WhatIfListing
}

function fmt(n: number | null | undefined, prefix = '$'): string {
  if (n == null) return '—'
  return `${prefix}${Math.round(n).toLocaleString()}`
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  onChange: (v: number) => void
}) {
  const id = label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <label htmlFor={id} className="text-gray-600 font-medium">{label}</label>
        <span className="text-gray-900 font-semibold">{fmt(value)}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-blue-600"
      />
      <div className="flex justify-between text-xs text-gray-400">
        <span>{fmt(min)}</span>
        <span>{fmt(max)}</span>
      </div>
    </div>
  )
}

export function WhatIfSliders({ listing }: Props) {
  const [purchasePrice, setPurchasePrice] = useState(listing.price ?? 65_000)
  const [arv, setArv] = useState(listing.arv ?? 90_000)
  const [rent, setRent] = useState(listing.estimated_rent ?? 900)
  const [result, setResult] = useState<BRRRRBreakdown | null>(listing.brrrr)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchWhatIf = useCallback(async (pp: number, a: number, r: number) => {
    if (!listing.id) return
    try {
      const resp = await fetch(`/deals/${listing.id}/what-if`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purchase_price: pp, arv: a, estimated_rent: r }),
      })
      if (!resp.ok) return
      const data = await resp.json()
      setResult(data.brrrr)
    } catch { /* silent */ }
  }, [listing.id])

  function debounced(pp: number, a: number, r: number) {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchWhatIf(pp, a, r), 300)
  }

  function handlePurchase(v: number) { setPurchasePrice(v); debounced(v, arv, rent) }
  function handleArv(v: number) { setArv(v); debounced(purchasePrice, v, rent) }
  function handleRent(v: number) { setRent(v); debounced(purchasePrice, arv, v) }

  function reset() {
    setPurchasePrice(listing.price ?? 65_000)
    setArv(listing.arv ?? 90_000)
    setRent(listing.estimated_rent ?? 900)
    setResult(listing.brrrr)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">What-If Calculator</h3>
        <button
          onClick={reset}
          className="text-xs text-gray-500 hover:text-gray-700 border border-gray-300 rounded px-2 py-1"
        >
          Reset
        </button>
      </div>

      <div className="space-y-4">
        <Slider
          label="Purchase Price"
          value={purchasePrice}
          min={25_000}
          max={100_000}
          step={1_000}
          onChange={handlePurchase}
        />
        <Slider
          label="ARV"
          value={arv}
          min={50_000}
          max={200_000}
          step={5_000}
          onChange={handleArv}
        />
        <Slider
          label="Rent"
          value={rent}
          min={500}
          max={2_000}
          step={25}
          onChange={handleRent}
        />
      </div>

      {result && (
        <div className="bg-gray-50 rounded-lg p-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <span className="text-gray-600">Cashflow</span>
          <span className="font-semibold text-right">{fmt(result.monthly_cashflow)}/mo</span>
          <span className="text-gray-600">CoC Return</span>
          <span className="font-semibold text-right">
            {result.coc_return != null ? `${(result.coc_return * 100).toFixed(1)}%` : '∞'}
          </span>
          <span className="text-gray-600">DSCR</span>
          <span className="font-semibold text-right">{result.dscr.toFixed(2)}</span>
          <span className="text-gray-600">Grade</span>
          <span className="font-semibold text-right">{result.grade}</span>
        </div>
      )}
    </div>
  )
}
