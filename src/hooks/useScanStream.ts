import { useCallback, useRef, useState } from 'react'
import type { Listing, ScanEvent } from '../types'

interface SourceStatus {
  status: 'scraping' | 'done' | 'error'
  count: number
}

interface ScanStreamState {
  isScanning: boolean
  listings: Listing[]
  summary: { total: number; strong: number; good: number } | null
  sourceStatuses: Partial<Record<string, SourceStatus>>
  error: string | null
  startStream: (scanId: string) => void
  stopStream: () => void
}

const RECONNECT_DELAYS_MS = [1000, 2000, 4000]

export function useScanStream(): ScanStreamState {
  const [isScanning, setIsScanning] = useState(false)
  const [listings, setListings] = useState<Listing[]>([])
  const [summary, setSummary] = useState<{ total: number; strong: number; good: number } | null>(null)
  const [sourceStatuses, setSourceStatuses] = useState<Partial<Record<string, SourceStatus>>>({})
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const scanIdRef = useRef<string | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopStream = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    reconnectAttemptRef.current = 0
    setIsScanning(false)
  }, [])

  const openConnection = useCallback((scanId: string) => {
    const es = new EventSource(`/scans/${scanId}/stream`)
    esRef.current = es

    es.onopen = () => {
      reconnectAttemptRef.current = 0
      setError(null)
    }

    es.onmessage = (e: MessageEvent) => {
      let event: ScanEvent
      try {
        event = JSON.parse(e.data)
      } catch {
        return
      }

      if (event.type === 'listing') {
        setListings(prev => [...prev, event.listing])
      } else if (event.type === 'source_status') {
        setSourceStatuses(prev => ({
          ...prev,
          [event.source]: { status: event.status, count: event.count },
        }))
      } else if (event.type === 'ai_review') {
        setListings(prev => prev.map(l => {
          const lid = l.id ?? l.address
          if (lid !== event.listing_id) return l
          return { ...l, ai_review: event.review, negotiation: event.negotiation }
        }))
      } else if (event.type === 'done') {
        setSummary(event.summary)
        setIsScanning(false)
        es.close()
        esRef.current = null
        reconnectAttemptRef.current = 0
      }
    }

    es.onerror = () => {
      setError('Connection lost. Reconnecting…')
      es.close()
      esRef.current = null

      const attempt = reconnectAttemptRef.current
      if (attempt < RECONNECT_DELAYS_MS.length && scanIdRef.current) {
        const delay = RECONNECT_DELAYS_MS[attempt]
        reconnectAttemptRef.current = attempt + 1
        reconnectTimerRef.current = setTimeout(() => {
          if (scanIdRef.current) openConnection(scanIdRef.current)
        }, delay)
      } else {
        setError('Connection failed after multiple retries.')
        setIsScanning(false)
      }
    }
  }, [])

  const startStream = useCallback((scanId: string) => {
    esRef.current?.close()
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)

    setListings([])
    setSummary(null)
    setSourceStatuses({})
    setError(null)
    setIsScanning(true)
    scanIdRef.current = scanId
    reconnectAttemptRef.current = 0

    openConnection(scanId)
  }, [openConnection])

  return { isScanning, listings, summary, sourceStatuses, error, startStream, stopStream }
}
