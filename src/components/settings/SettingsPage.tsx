import { useState, useEffect } from 'react'

interface Settings {
  interest_rate: number
  loan_term_years: number
  refi_ltv: number
  expense_ratio: number
  rehab_months: number
  monthly_hold_cost: number
}

const DEFAULTS: Settings = {
  interest_rate: 7.5,
  loan_term_years: 30,
  refi_ltv: 75,
  expense_ratio: 50,
  rehab_months: 4,
  monthly_hold_cost: 500,
}

function Field({ label, value, onChange, suffix = '' }: {
  label: string
  value: number
  onChange: (v: number) => void
  suffix?: string
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <label className="text-sm text-gray-700">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={value}
          onChange={e => onChange(Number(e.target.value))}
          className="w-24 text-right border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-400"
        />
        {suffix && <span className="text-sm text-gray-500 w-6">{suffix}</span>}
      </div>
    </div>
  )
}

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(DEFAULTS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    fetch('/settings', { method: 'GET' })
      .then(r => r.json())
      .then(data => setSettings({ ...DEFAULTS, ...data }))
      .catch(() => { /* use defaults */ })
  }, [])

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings(prev => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  async function handleSave() {
    setSaving(true)
    try {
      await fetch('/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      setSaved(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto p-6">
      <h1 className="text-xl font-bold text-gray-900 mb-6">Settings</h1>
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <Field label="Interest Rate" value={settings.interest_rate} onChange={v => update('interest_rate', v)} suffix="%" />
        <Field label="Loan Term" value={settings.loan_term_years} onChange={v => update('loan_term_years', v)} suffix="yr" />
        <Field label="Refi LTV" value={settings.refi_ltv} onChange={v => update('refi_ltv', v)} suffix="%" />
        <Field label="Expense Ratio (50% Rule)" value={settings.expense_ratio} onChange={v => update('expense_ratio', v)} suffix="%" />
        <Field label="Rehab Duration" value={settings.rehab_months} onChange={v => update('rehab_months', v)} suffix="mo" />
        <Field label="Monthly Hold Cost" value={settings.monthly_hold_cost} onChange={v => update('monthly_hold_cost', v)} suffix="$" />
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {saved && <span className="text-green-600 text-sm">Saved!</span>}
      </div>
    </div>
  )
}
