import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ListingsMap } from './ListingsMap'
import type { Listing } from '../../types'

// Mock react-leaflet — jsdom doesn't support canvas/SVG map rendering
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  CircleMarker: ({ children, eventHandlers, ...rest }: { children?: React.ReactNode; eventHandlers?: { click?: () => void; mouseover?: () => void }; [key: string]: unknown }) => (
    <div
      data-testid="circle-marker"
      onClick={eventHandlers?.click}
      onMouseEnter={eventHandlers?.mouseover}
      {...rest}
    >
      {children}
    </div>
  ),
  Tooltip: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip">{children}</div>
  ),
  useMap: () => ({ setView: vi.fn(), fitBounds: vi.fn() }),
}))

vi.mock('leaflet', () => ({
  default: { icon: vi.fn() },
  icon: vi.fn(),
}))

const makeListings = (n = 3): Listing[] =>
  Array.from({ length: n }, (_, i) => ({
    id: `lst-${i}`,
    address: `${i} Main St`,
    city: 'Cleveland',
    state: 'OH',
    zip_code: '44101',
    price: 65_000 + i * 1000,
    beds: 3,
    baths: 1,
    sqft: 1100,
    source: 'redfin',
    grade: i === 0 ? 'STRONG' : 'GOOD',
    latitude: 41.4993 + i * 0.01,
    longitude: -81.6944 + i * 0.01,
    days_on_market: 30,
    listing_url: null,
    arv: 90_000,
    estimated_rent: 950,
    motivation_score: 5,
    motivation_signals: [],
    brrrr: null,
  }))

describe('ListingsMap', () => {
  it('renders map container', () => {
    render(<ListingsMap listings={[]} />)
    expect(screen.getByTestId('map-container')).toBeInTheDocument()
  })

  it('renders a marker for each listing with coordinates', () => {
    render(<ListingsMap listings={makeListings(3)} />)
    expect(screen.getAllByTestId('circle-marker')).toHaveLength(3)
  })

  it('skips listings without coordinates', () => {
    const listings = makeListings(2)
    listings[0].latitude = null
    render(<ListingsMap listings={listings} />)
    expect(screen.getAllByTestId('circle-marker')).toHaveLength(1)
  })

  it('calls onSelectListing when marker is clicked', async () => {
    const onSelect = vi.fn()
    render(<ListingsMap listings={makeListings(1)} onSelectListing={onSelect} />)
    await userEvent.click(screen.getByTestId('circle-marker'))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ address: '0 Main St' }))
  })

  it('highlights the selected listing marker', () => {
    const listings = makeListings(2)
    const { container } = render(<ListingsMap listings={listings} highlightedId="lst-0" />)
    // The highlighted marker should have a distinct data attribute or class
    const markers = container.querySelectorAll('[data-highlighted="true"]')
    expect(markers.length).toBe(1)
  })

  it('renders tile layer', () => {
    render(<ListingsMap listings={[]} />)
    expect(screen.getByTestId('tile-layer')).toBeInTheDocument()
  })
})
