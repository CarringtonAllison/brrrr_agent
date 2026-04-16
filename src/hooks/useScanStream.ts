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
  startStream: (scanId: string) => void
  stopStream: () => void
}

export function useScanStream(): ScanStreamState {
  const [isScanning, setIsScanning] = useState(false)
  const [listings, setListings] = useState<Listing[]>([])
  const [summary, setSummary] = useState<{ total: number; strong: number; good: number } | null>(null)
  const [sourceStatuses, setSourceStatuses] = useState<Partial<Record<string, SourceStatus>>>({})
  const esRef = useRef<EventSource | null>(null)

  const stopStream = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setIsScanning(false)
  }, [])

  const startStream = useCallback((scanId: string) => {
    // Close any existing connection
    esRef.current?.close()

    // Reset state
    setListings([])
    setSummary(null)
    setSourceStatuses({})
    setIsScanning(true)

    const es = new EventSource(`/scans/${scanId}/stream`)
    esRef.current = es

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
      } else if (event.type === 'done') {
        setSummary(event.summary)
        setIsScanning(false)
        es.close()
        esRef.current = null
      }
    }

    es.onerror = () => {
      setIsScanning(false)
    }
  }, [])

  return { isScanning, listings, summary, sourceStatuses, startStream, stopStream }
}
