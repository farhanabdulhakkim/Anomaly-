import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, GeoJSON, Polyline, CircleMarker, useMap, LayerGroup } from 'react-leaflet'
import { getAnalytics, getAnomalyGeoJSON, getGridGeoJSON, getMission, getMissionPlan } from '../api/services'
import api from '../api/client'
import StatCard from '../components/UI/StatCard'

// Auto-fit map to grid bounds
function FitBounds({ geojson }) {
  const map = useMap()
  useEffect(() => {
    if (!geojson?.features?.length) return
    const coords = geojson.features.flatMap(f =>
      f.geometry.coordinates[0].map(([lon, lat]) => [lat, lon])
    )
    if (coords.length) map.fitBounds(coords, { padding: [40, 40] })
  }, [geojson])
  return null
}

const cellColor = (count) => {
  if (count === 0) return '#00C853'
  if (count === 1) return '#FFD600'
  if (count === 2) return '#FF6D00'
  return '#D50000'
}

export default function MissionMap() {
  const { fieldId, missionId } = useParams()
  const navigate = useNavigate()

  const [mission, setMission]         = useState(null)
  const [analytics, setAnalytics]     = useState(null)
  const [gridGeoJSON, setGridGeoJSON] = useState(null)
  const [anomalyGeoJSON, setAnomalyGeoJSON] = useState(null)
  const [flightPath, setFlightPath]   = useState(null)
  const [waypoints, setWaypoints]     = useState([])
  const [layers, setLayers]           = useState({ grid: true, path: true, anomalies: true, waypoints: true })
  const [activeTab, setActiveTab]     = useState('leaflet') // 'leaflet' | 'folium'

  useEffect(() => { fetchAll() }, [missionId])

  const fetchAll = async () => {
    const [mRes, aRes, gRes, anRes] = await Promise.all([
      getMission(fieldId, missionId),
      getAnalytics(fieldId, missionId).catch(() => ({ data: null })),
      getGridGeoJSON(fieldId),
      getAnomalyGeoJSON(fieldId, missionId),
    ])
    setMission(mRes.data)
    setAnalytics(aRes.data)
    setGridGeoJSON(gRes.data)
    setAnomalyGeoJSON(anRes.data)

    // Fetch flight path as GeoJSON from backend
    try {
      const pathRes = await api.get(`/api/fields/${fieldId}/missions/${missionId}/flight-path`)
      setFlightPath(pathRes.data)
    } catch { /* flight path optional */ }

    // Fetch waypoints if plan was uploaded
    try {
      const planRes = await getMissionPlan(fieldId, missionId)
      if (planRes.data?.waypoints?.length) {
        setWaypoints(planRes.data.waypoints.filter(w => w.lat !== 0 || w.lon !== 0))
      }
    } catch { /* plan optional */ }
  }

  const gridStyle = (feature) => {
    const anomaly = anomalyGeoJSON?.features?.find(
      f => f.properties.row === feature.properties.row && f.properties.col === feature.properties.col
    )
    const count = anomaly?.properties?.anomaly_count || 0
    return {
      fillColor: cellColor(count),
      fillOpacity: count > 0 ? 0.6 : 0.12,
      color: '#ffffff',
      weight: 0.5,
      opacity: 0.4,
    }
  }

  const onEachCell = (feature, layer) => {
    const anomaly = anomalyGeoJSON?.features?.find(
      f => f.properties.row === feature.properties.row && f.properties.col === feature.properties.col
    )
    const count   = anomaly?.properties?.anomaly_count || 0
    const density = anomaly?.properties?.density || 0
    layer.bindPopup(
      `<div style="font-size:13px;line-height:1.6">
        <b>Cell [${feature.properties.row}, ${feature.properties.col}]</b><br/>
        Status: <b style="color:${count > 0 ? '#ef4444' : '#22c55e'}">${count > 0 ? 'ANOMALY' : 'NORMAL'}</b><br/>
        Anomaly count: <b>${count}</b><br/>
        Density: <b>${(density * 100).toFixed(1)}%</b>
      </div>`
    )
    layer.on('mouseover', () => layer.setStyle({ weight: 2, opacity: 1 }))
    layer.on('mouseout',  () => layer.setStyle({ weight: 0.5, opacity: 0.4 }))
  }

  // Extract anomaly cell centres for CircleMarkers
  const anomalyCentres = anomalyGeoJSON?.features
    ?.filter(f => f.properties.anomaly_count > 0)
    ?.map(f => {
      const coords = f.geometry.coordinates[0]
      const lats = coords.map(c => c[1])
      const lons = coords.map(c => c[0])
      return {
        lat: (Math.min(...lats) + Math.max(...lats)) / 2,
        lon: (Math.min(...lons) + Math.max(...lons)) / 2,
        count: f.properties.anomaly_count,
        density: f.properties.density,
        row: f.properties.row,
        col: f.properties.col,
      }
    }) || []

  if (!mission) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
      Loading map...
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">

      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-4 flex-shrink-0">
        <button onClick={() => navigate(`/fields/${fieldId}`)}
          className="text-gray-400 hover:text-white text-sm px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-500 transition-all">
          Back
        </button>
        <div className="flex-1">
          <h1 className="font-bold text-white">{mission.name}</h1>
          <p className="text-gray-400 text-xs">
            {mission.drone_model} &nbsp;·&nbsp; {mission.anomaly_mode.replace('_', ' ')} &nbsp;·&nbsp;
            {mission.total_points} points &nbsp;·&nbsp; {mission.duration_s?.toFixed(1)}s
            {mission.flight_date && <span> &nbsp;·&nbsp; {new Date(mission.flight_date).toLocaleDateString()}</span>}
          </p>
        </div>
      </header>

      {/* Tab bar */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 flex gap-1 flex-shrink-0">
        {[['leaflet', 'GPS Grid Map'], ['folium', 'CNN Folium Map']].map(([key, label]) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key ? 'border-green-500 text-white' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <aside className="w-64 bg-gray-900 border-r border-gray-800 p-4 overflow-y-auto flex-shrink-0 space-y-5">

          {/* Stats */}
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3">Mission Stats</p>
            <div className="space-y-2">
              <StatCard label="Anomaly Cells"  value={mission.anomaly_cell_count}  color="red"    small />
              <StatCard label="Anomaly Points" value={mission.anomaly_point_count} color="yellow" small />
              <StatCard label="Total Points"   value={mission.total_points}        color="blue"   small />
              <StatCard label="Duration"       value={`${mission.duration_s?.toFixed(1)}s`} color="green" small />
            </div>
          </div>

          {/* Analytics */}
          {analytics && (
            <div>
              <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3">Analytics</p>
              <div className="space-y-2">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs">Avg Anomaly Density</p>
                  <p className="font-bold text-yellow-400 text-lg">{(analytics.avg_anomaly_density * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs">Max Anomaly Density</p>
                  <p className="font-bold text-red-400 text-lg">{(analytics.max_anomaly_density * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs">Clean Cells</p>
                  <p className="font-bold text-green-400 text-lg">{analytics.clean_cells}</p>
                </div>
                {analytics.anomaly_reduction_pct !== null && analytics.anomaly_reduction_pct !== undefined && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs">vs Previous Mission</p>
                    <p className={`font-bold text-lg ${analytics.anomaly_reduction_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {analytics.anomaly_reduction_pct >= 0 ? 'Down' : 'Up'} {Math.abs(analytics.anomaly_reduction_pct).toFixed(1)}%
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Layer Toggles */}
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3">Layers</p>
            {[
              ['grid',      'Grid Overlay'],
              ['path',      'Flight Path'],
              ['anomalies', 'Anomaly Points'],
              ['waypoints', 'Waypoints'],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center justify-between mb-2 cursor-pointer">
                <span className="text-sm text-gray-300">{label}</span>
                <div onClick={() => setLayers(l => ({ ...l, [key]: !l[key] }))}
                  className={`w-9 h-5 rounded-full transition-colors relative ${layers[key] ? 'bg-green-600' : 'bg-gray-700'}`}>
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${layers[key] ? 'translate-x-4' : 'translate-x-0.5'}`} />
                </div>
              </label>
            ))}
          </div>

          {/* Legend */}
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold tracking-wider mb-3">Legend</p>
            {[
              ['#00C853', 'No anomaly'],
              ['#FFD600', 'Low (1 detection)'],
              ['#FF6D00', 'Medium (2 detections)'],
              ['#D50000', 'High (3+ detections)'],
            ].map(([color, label]) => (
              <div key={color} className="flex items-center gap-2 mb-2">
                <div className="w-4 h-4 rounded flex-shrink-0" style={{ background: color }} />
                <span className="text-xs text-gray-300">{label}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-3 mb-2">
              <div className="w-5 h-1 bg-blue-400 rounded flex-shrink-0" />
              <span className="text-xs text-gray-300">Flight path</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-3 h-3 rounded-full bg-red-500 flex-shrink-0" />
              <span className="text-xs text-gray-300">Anomaly point</span>
            </div>
            {waypoints.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-purple-400 flex-shrink-0" />
                <span className="text-xs text-gray-300">Waypoint ({waypoints.length})</span>
              </div>
            )}
          </div>

        </aside>

        {/* Map */}
        <div className="flex-1 relative">
          {activeTab === 'folium' ? (
            <iframe
              src={`/api/fields/${fieldId}/missions/${missionId}/map-html`}
              className="w-full h-full border-0"
              title="Folium CNN Map"
            />
          ) : (
          <MapContainer
            center={[11.3399, 77.7204]}
            zoom={18}
            style={{ height: '100%', width: '100%' }}
            zoomControl={true}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution="&copy; OpenStreetMap contributors"
              maxZoom={22}
            />

            {/* Auto-fit to grid */}
            {gridGeoJSON && <FitBounds geojson={gridGeoJSON} />}

            {/* Grid overlay */}
            {layers.grid && gridGeoJSON && (
              <GeoJSON
                key={`grid-${missionId}-${anomalyGeoJSON?.features?.length}`}
                data={gridGeoJSON}
                style={gridStyle}
                onEachFeature={onEachCell}
              />
            )}

            {/* Flight path polyline */}
            {layers.path && flightPath?.coordinates?.length > 1 && (
              <Polyline
                positions={flightPath.coordinates.map(([lon, lat]) => [lat, lon])}
                color="#60a5fa"
                weight={2.5}
                opacity={0.85}
                dashArray="8, 6"
              />
            )}

            {/* Anomaly cell centre markers */}
            {layers.anomalies && anomalyCentres.map((a, i) => (
              <CircleMarker key={i}
                center={[a.lat, a.lon]}
                radius={5}
                color="#dc2626"
                fillColor="#ef4444"
                fillOpacity={0.9}
                weight={1.5}
              >
              </CircleMarker>
            ))}

            {/* Autopilot waypoints */}
            {layers.waypoints && waypoints.map((w, i) => (
              <CircleMarker key={`wp-${i}`}
                center={[w.lat, w.lon]}
                radius={6}
                color="#a855f7"
                fillColor="#c084fc"
                fillOpacity={0.9}
                weight={2}
              >
              </CircleMarker>
            ))}

          </MapContainer>
          )}
        </div>
      </div>
    </div>
  )
}
