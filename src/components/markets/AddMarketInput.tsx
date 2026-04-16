import { useState, type FormEvent } from 'react'
import { useMarkets } from '../../contexts/MarketsContext'

export function AddMarketInput() {
  const { addMarket } = useMarkets()
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return

    // Expect "City ST" or "City ST 12345,12346"
    const parts = trimmed.split(/\s+/)
    if (parts.length < 2) {
      setError('Format: "City ST" e.g. "Cleveland OH"')
      return
    }

    const state = parts[parts.length - 1].toUpperCase()
    const city = parts.slice(0, -1).join(' ')

    setError('')
    setSubmitting(true)
    try {
      await addMarket({ name: trimmed, city, state, zip_codes: [] })
      setValue('')
    } catch {
      setError('Failed to add market')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder='Add market e.g. "Cleveland OH"'
        className="border border-gray-300 rounded px-3 py-1.5 text-sm flex-1 focus:outline-none focus:border-blue-400"
        disabled={submitting}
      />
      <button
        type="submit"
        disabled={submitting || !value.trim()}
        className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {submitting ? 'Adding…' : 'Add'}
      </button>
      {error && <p className="text-red-500 text-xs self-center">{error}</p>}
    </form>
  )
}
