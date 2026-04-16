import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Listing, Grade } from '../../types'
import { GRADE_COLORS } from '../../types'

const PENDING_COLOR = '#6B7280'
const DEFAULT_CENTER: [number, number] = [39.8283, -98.5795] // geographic center of US
const DEFAULT_ZOOM = 4

function gradeColor(grade: Grade | null): string {
  if (!grade) return PENDING_COLOR
  return GRADE_COLORS[grade] ?? PENDING_COLOR
}

interface Props {
  listings: Listing[]
  onSelectListing?: (listing: Listing) => void
  highlightedId?: string | null
}

export function ListingsMap({ listings, onSelectListing, highlightedId }: Props) {
  const withCoords = listings.filter(l => l.latitude != null && l.longitude != null)

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      {withCoords.map(listing => {
        const isHighlighted = highlightedId === listing.id
        return (
          <CircleMarker
            key={listing.id ?? listing.address}
            center={[listing.latitude!, listing.longitude!]}
            radius={isHighlighted ? 10 : 7}
            pathOptions={{
              color: gradeColor(listing.grade),
              fillColor: gradeColor(listing.grade),
              fillOpacity: 0.85,
              weight: isHighlighted ? 3 : 1.5,
            }}
            // eslint-disable-next-line react/prop-types
            {...({ 'data-highlighted': isHighlighted ? 'true' : undefined } as object)}
            eventHandlers={{
              click: () => onSelectListing?.(listing),
            }}
          >
            <Tooltip>
              <div className="text-xs">
                <p className="font-semibold">{listing.address}</p>
                {listing.price && <p>${listing.price.toLocaleString()}</p>}
                {listing.grade && <p>{listing.grade}</p>}
              </div>
            </Tooltip>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}
