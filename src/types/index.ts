export type Grade = 'STRONG' | 'GOOD' | 'MAYBE' | 'SKIP'

export interface Market {
  id: string
  name: string
  city: string
  state: string
  zip_codes: string[]
  created_at: string
}

export interface MarketCreate {
  name: string
  city: string
  state: string
  zip_codes: string[]
}

export interface BRRRRBreakdown {
  cash_left_in_deal: number
  monthly_cashflow: number
  coc_return: number | null
  dscr: number
  rent_to_price: number
  seventy_pct_rule_pass: boolean
  grade: Grade
  grade_reasons: string[]
}

export interface Listing {
  id?: string
  address: string
  city: string | null
  state: string | null
  zip_code: string | null
  price: number | null
  beds: number | null
  baths: number | null
  sqft: number | null
  source: string
  grade: Grade | null
  latitude: number | null
  longitude: number | null
  days_on_market: number | null
  listing_url: string | null
  arv: number | null
  estimated_rent: number | null
  motivation_score: number | null
  motivation_signals: string[]
  brrrr: BRRRRBreakdown | null
}

export type ScanEventType =
  | 'source_status'
  | 'listing'
  | 'analysis_update'
  | 'ai_review'
  | 'done'

export interface SourceStatusEvent {
  type: 'source_status'
  source: 'redfin' | 'craigslist' | 'zillow'
  status: 'scraping' | 'done' | 'error'
  count: number
}

export interface ListingEvent {
  type: 'listing'
  listing: Listing
}

export interface DoneEvent {
  type: 'done'
  summary: { total: number; strong: number; good: number }
}

export type ScanEvent = SourceStatusEvent | ListingEvent | DoneEvent

export interface ScanStatus {
  scan_id: string | null
  is_active: boolean
  market_id: string
}

export const GRADE_COLORS: Record<Grade, string> = {
  STRONG: '#22C55E',
  GOOD: '#3B82F6',
  MAYBE: '#F59E0B',
  SKIP: '#EF4444',
}

export const GRADE_CLASSES: Record<Grade, string> = {
  STRONG: 'text-green-600 bg-green-50 border-green-200',
  GOOD: 'text-blue-600 bg-blue-50 border-blue-200',
  MAYBE: 'text-amber-600 bg-amber-50 border-amber-200',
  SKIP: 'text-red-600 bg-red-50 border-red-200',
}
