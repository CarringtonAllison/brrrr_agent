import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useScanStream } from './useScanStream'

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  onopen: ((e: Event) => void) | null = null
  readyState = 0
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  emit(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }

  emitError() {
    this.onerror?.(new Event('error'))
  }

  close = vi.fn(() => { this.readyState = MockEventSource.CLOSED })
}

beforeEach(() => {
  MockEventSource.instances = []
  vi.stubGlobal('EventSource', MockEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useScanStream', () => {
  it('starts with inactive status', () => {
    const { result } = renderHook(() => useScanStream())
    expect(result.current.isScanning).toBe(false)
    expect(result.current.listings).toEqual([])
  })

  it('startStream opens an EventSource', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })
    expect(MockEventSource.instances.length).toBe(1)
    expect(MockEventSource.instances[0].url).toContain('scan-1')
  })

  it('isScanning becomes true after startStream', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })
    expect(result.current.isScanning).toBe(true)
  })

  it('appends listing events to listings', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    const listing = { address: '123 Main', grade: 'STRONG', price: 65000 }
    act(() => {
      MockEventSource.instances[0].emit({ type: 'listing', listing })
    })

    expect(result.current.listings).toHaveLength(1)
    expect(result.current.listings[0].address).toBe('123 Main')
  })

  it('sets summary on done event', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emit({ type: 'done', summary: { total: 5, strong: 2, good: 1 } })
    })

    expect(result.current.summary).toEqual({ total: 5, strong: 2, good: 1 })
    expect(result.current.isScanning).toBe(false)
  })

  it('closes EventSource on done event', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emit({ type: 'done', summary: { total: 0, strong: 0, good: 0 } })
    })

    expect(MockEventSource.instances[0].close).toHaveBeenCalled()
  })

  it('stopStream closes EventSource', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })
    act(() => { result.current.stopStream() })
    expect(MockEventSource.instances[0].close).toHaveBeenCalled()
    expect(result.current.isScanning).toBe(false)
  })

  it('tracks source statuses', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emit({ type: 'source_status', source: 'redfin', status: 'done', count: 10 })
    })

    expect(result.current.sourceStatuses.redfin).toEqual({ status: 'done', count: 10 })
  })

  it('clears state on new startStream call', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emit({ type: 'listing', listing: { address: '1 Main' } })
    })
    expect(result.current.listings).toHaveLength(1)

    act(() => { result.current.startStream('scan-2') })
    expect(result.current.listings).toHaveLength(0)
  })

  it('closes previous EventSource when restarting', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })
    act(() => { result.current.startStream('scan-2') })
    expect(MockEventSource.instances[0].close).toHaveBeenCalled()
  })

  it('merges ai_review events onto matching listing', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emit({
        type: 'listing',
        listing: { id: 'l-1', address: '1 Elm', grade: 'STRONG' },
      })
    })

    act(() => {
      MockEventSource.instances[0].emit({
        type: 'ai_review',
        listing_id: 'l-1',
        review: { verdict: 'STRONG', summary: 'solid', confidence: 0.9 },
        negotiation: { offer_range_low: 50000, offer_range_high: 60000 },
      })
    })

    expect(result.current.listings[0].ai_review?.verdict).toBe('STRONG')
    expect(result.current.listings[0].negotiation?.offer_range_high).toBe(60000)
  })

  it('exposes connection error state on EventSource error', () => {
    const { result } = renderHook(() => useScanStream())
    act(() => { result.current.startStream('scan-1') })

    act(() => {
      MockEventSource.instances[0].emitError()
    })

    expect(result.current.error).not.toBeNull()
  })
})
