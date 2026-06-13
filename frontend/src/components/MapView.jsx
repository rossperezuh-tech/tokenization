import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { getLeads } from '../api'

const fmt = (n) => n == null ? '—' : (n >= 1e6 ? `$${(n/1e6).toFixed(2)}M` : `$${n.toLocaleString()}`)

// NYC default center — geocoding is TODO; sample leads have hardcoded coords
const BOROUGH_COORDS = {
  'Brooklyn':        [40.6782, -73.9442],
  'Queens':          [40.7282, -73.7949],
  'Manhattan':       [40.7831, -73.9712],
  'New York':        [40.7128, -74.0060],
  'Long Island City':[40.7447, -73.9485],
  'Bronx':           [40.8448, -73.8648],
}

function pinColor(score) {
  if (score >= 80) return '#ef4444'
  if (score >= 50) return '#eab308'
  return '#22c55e'
}

function jitter(coord) {
  return coord + (Math.random() - 0.5) * 0.006
}

export default function MapView() {
  const [leads, setLeads] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getLeads({ limit: 500 }).then(({ data }) => {
      const mapped = data.leads.map(l => {
        let lat = l.latitude
        let lng = l.longitude
        if (!lat || !lng) {
          const base = BOROUGH_COORDS[l.city] || BOROUGH_COORDS['New York']
          lat = jitter(base[0])
          lng = jitter(base[1])
        }
        return { ...l, _lat: lat, _lng: lng }
      })
      setLeads(mapped)
      setLoading(false)
    })
  }, [])

  const plotted = leads.filter(l => l._lat && l._lng)

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Map */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-gray-950/80 text-gray-400">
            Loading map…
          </div>
        )}
        <MapContainer
          center={[40.7128, -74.0060]}
          zoom={11}
          style={{ height: '100%', width: '100%' }}
          className="z-0"
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          {plotted.map(lead => (
            <CircleMarker
              key={lead.id}
              center={[lead._lat, lead._lng]}
              radius={lead.score >= 80 ? 10 : lead.score >= 50 ? 8 : 6}
              pathOptions={{
                color: pinColor(lead.score),
                fillColor: pinColor(lead.score),
                fillOpacity: 0.85,
                weight: 2,
              }}
              eventHandlers={{ click: () => setSelected(lead) }}
            >
              <Popup>
                <div className="text-xs">
                  <strong>{lead.address}</strong><br />
                  {lead.property_type} · {fmt(lead.asking_price)}<br />
                  Score: {lead.score}/100
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 z-10 bg-gray-900/90 border border-gray-700 rounded-lg px-3 py-2 text-xs space-y-1">
          <div className="font-semibold text-gray-300 mb-1">Score</div>
          {[['🔴', 'Hot (80+)', '#ef4444'], ['🟡', 'Warm (50–79)', '#eab308'], ['🟢', 'Cold (<50)', '#22c55e']].map(([e, l, c]) => (
            <div key={l} className="flex items-center gap-2 text-gray-400">
              <span style={{ color: c }}>●</span> {l}
            </div>
          ))}
          <div className="text-gray-600 pt-1">{plotted.length} leads plotted</div>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 bg-gray-900 border-l border-gray-800 overflow-y-auto">
        {selected ? (
          <div className="p-4">
            <div className="flex items-start justify-between mb-3">
              <h3 className="font-semibold text-white text-sm leading-tight">{selected.address}</h3>
              <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-white ml-2">×</button>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Score</span>
                <span className="font-semibold">{selected.score}/100</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Type</span>
                <span>{selected.property_type || '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Price</span>
                <span className="font-mono">{fmt(selected.asking_price)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Cap Rate</span>
                <span>{selected.cap_rate ? `${selected.cap_rate}%` : '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">DOM</span>
                <span>{selected.days_on_market ?? '—'} days</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Source</span>
                <span className="text-xs">{selected.source}</span>
              </div>
              {selected.reason_for_selling && (
                <div className="pt-2 border-t border-gray-800">
                  <div className="text-gray-500 text-xs mb-1">Reason</div>
                  <p className="text-xs text-gray-300 italic">"{selected.reason_for_selling}"</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-4">
            <h3 className="font-semibold text-white mb-3 text-sm">All Leads</h3>
            <div className="space-y-2">
              {leads.slice(0, 30).map(l => (
                <button
                  key={l.id}
                  onClick={() => setSelected(l)}
                  className="w-full text-left bg-gray-800 hover:bg-gray-700 rounded-lg px-3 py-2 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-white truncate max-w-[160px]">{l.address}</span>
                    <span className="text-xs font-mono" style={{ color: pinColor(l.score) }}>{l.score}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">{l.city} · {l.property_type}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
