import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getField, listMissions, createMission, uploadTelemetry } from '../api/services'
import api from '../api/client'
import StatCard from '../components/UI/StatCard'
import TrendChart from '../components/Charts/TrendChart'

export default function FieldDetail() {
  const { fieldId } = useParams()
  const navigate = useNavigate()
  const [field, setField] = useState(null)
  const [missions, setMissions] = useState([])
  const [showMissionForm, setShowMissionForm] = useState(false)
  const [missionForm, setMissionForm] = useState({
    name: '', drone_model: '', flight_altitude_m: 30, anomaly_mode: 'rule_based'
  })
  const [uploading, setUploading] = useState(null)
  const [uploadingPlan, setUploadingPlan] = useState(null)
  const [uploadingVideo, setUploadingVideo] = useState(null)
  const [videoFiles, setVideoFiles] = useState({}) // missionId -> {video, csv}
  const [loading, setLoading] = useState(false)
  const [flightDates, setFlightDates] = useState({})
  const [activeTab, setActiveTab] = useState('missions')

  useEffect(() => { fetchData() }, [fieldId])

  const fetchData = async () => {
    const [fRes, mRes] = await Promise.all([getField(fieldId), listMissions(fieldId)])
    setField(fRes.data)
    setMissions(mRes.data)
  }

  const handleCreateMission = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await createMission(fieldId, {
        ...missionForm,
        flight_altitude_m: parseFloat(missionForm.flight_altitude_m)
      })
      setShowMissionForm(false)
      fetchData()
    } catch (err) { alert(err.response?.data?.detail || 'Error') }
    finally { setLoading(false) }
  }

  // Upload autopilot plan (.waypoints / .plan)
  const handleUploadPlan = async (missionId, file) => {
    setUploadingPlan(missionId)
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post(`/api/fields/${fieldId}/missions/${missionId}/upload-plan`, form)
      fetchData()
      alert('Mission plan uploaded successfully.')
    } catch (err) { alert(err.response?.data?.detail || 'Plan upload failed') }
    finally { setUploadingPlan(null) }
  }

  // Upload drone log + flight date, then run pipeline
  const handleUploadLog = async (missionId, file) => {
    setUploading(missionId)
    try {
      const form = new FormData()
      form.append('file', file)
      if (flightDates[missionId]) {
        form.append('flight_date', new Date(flightDates[missionId]).toISOString())
      }
      await api.post(`/api/fields/${fieldId}/missions/${missionId}/upload-telemetry`, form)
      fetchData()
    } catch (err) { alert(err.response?.data?.detail || 'Upload failed') }
    finally { setUploading(null) }
  }

  // Upload video + GPS CSV → CNN pipeline
  const handleUploadVideo = async (missionId) => {
    const files = videoFiles[missionId]
    if (!files?.video || !files?.csv) return alert('Select both a video and a CSV file')
    setUploadingVideo(missionId)
    try {
      const form = new FormData()
      form.append('video', files.video)
      form.append('csv_file', files.csv)
      await api.post(`/api/fields/${fieldId}/missions/${missionId}/upload-video`, form)
      fetchData()
    } catch (err) { alert(err.response?.data?.detail || 'Video upload failed') }
    finally { setUploadingVideo(null) }
  }

  const statusColor = (s) => ({
    completed: 'text-green-400 bg-green-900/30',
    failed: 'text-red-400 bg-red-900/30',
    processing: 'text-yellow-400 bg-yellow-900/30',
    pending: 'text-gray-400 bg-gray-800'
  }[s] || 'text-gray-400 bg-gray-800')

  if (!field) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
      Loading...
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <button onClick={() => navigate('/')}
          className="text-gray-400 hover:text-white text-sm px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-500 transition-all">
          Back
        </button>
        <div className="flex-1">
          <h1 className="font-bold text-lg text-white">{field.name}</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            {field.rice_type && <span className="mr-2">Rice: {field.rice_type}</span>}
            {field.soil_type && <span className="mr-2">Soil: {field.soil_type}</span>}
            {field.n_rows && field.n_cols && <span>Grid: {field.n_rows} x {field.n_cols} cells ({field.cell_size_m}m)</span>}
          </p>
        </div>
        <button onClick={() => setShowMissionForm(true)}
          className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all">
          + New Mission
        </button>
      </header>

      <div className="p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Missions" value={missions.length} color="green" />
          <StatCard label="Grid Cells" value={field.n_rows && field.n_cols ? field.n_rows * field.n_cols : '--'} color="blue" />
          <StatCard label="Cell Size" value={`${field.cell_size_m}m`} color="yellow" />
          <StatCard label="Area" value={field.area_hectares ? `${field.area_hectares} ha` : '--'} color="purple" />
        </div>

        {/* Trend Chart */}
        {missions.filter(m => m.status === 'completed').length > 1 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="font-semibold mb-4 text-white">Anomaly Trend Across Missions</h2>
            <TrendChart fieldId={fieldId} />
          </div>
        )}

        {/* Missions List */}
        <div>
          <h2 className="font-semibold text-lg text-white mb-4">Missions</h2>

          {missions.length === 0 ? (
            <div className="text-center py-12 text-gray-500 bg-gray-900 border border-gray-800 rounded-xl">
              <p className="text-lg font-medium mb-1">No missions yet</p>
              <p className="text-sm">Create a mission, upload the autopilot plan, then upload the drone log to run analysis.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {missions.map((m) => (
                <div key={m.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">

                  {/* Mission Header */}
                  <div className="px-5 py-4 flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-white">{m.name}</h3>
                      <p className="text-sm text-gray-400 mt-0.5">
                        {m.drone_model || 'Unknown drone'} &nbsp;·&nbsp; {m.anomaly_mode.replace('_', ' ')} &nbsp;·&nbsp; v{m.version}
                        {m.flight_date && <span> &nbsp;·&nbsp; {new Date(m.flight_date).toLocaleDateString()}</span>}
                      </p>
                    </div>
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${statusColor(m.status)}`}>
                      {m.status.toUpperCase()}
                    </span>
                  </div>

                  {/* Two-panel workflow */}
                  <div className="border-t border-gray-800 grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-gray-800">

                    {/* Panel 1: Mission Planner Plan */}
                    <div className="px-5 py-4">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
                        Mission Planner Autopilot Plan
                      </p>
                      {m.waypoint_filename ? (
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-2 h-2 rounded-full bg-green-400"></div>
                          <span className="text-sm text-green-400 font-medium">{m.waypoint_filename}</span>
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500 mb-3">No plan uploaded yet</p>
                      )}
                      <label className="inline-flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-all">
                        {uploadingPlan === m.id ? 'Uploading...' : m.waypoint_filename ? 'Replace Plan' : 'Upload .waypoints / .plan'}
                        <input type="file" accept=".waypoints,.plan,.txt,.json" className="hidden"
                          onChange={(e) => e.target.files[0] && handleUploadPlan(m.id, e.target.files[0])} />
                      </label>
                      {m.waypoints && (
                        <p className="text-xs text-gray-500 mt-2">{m.waypoints.length} waypoints loaded</p>
                      )}
                    </div>

                    {/* Panel 2: Drone Log Upload */}
                    <div className="px-5 py-4">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
                        Drone Flight Log
                      </p>

                      {m.status === 'completed' ? (
                        <>
                          <div className="grid grid-cols-3 gap-2 mb-3">
                            <div className="bg-gray-800 rounded-lg p-2 text-center">
                              <p className="text-red-400 font-bold text-lg">{m.anomaly_cell_count}</p>
                              <p className="text-gray-500 text-xs">Anomaly Cells</p>
                            </div>
                            <div className="bg-gray-800 rounded-lg p-2 text-center">
                              <p className="text-yellow-400 font-bold text-lg">{m.anomaly_point_count}</p>
                              <p className="text-gray-500 text-xs">Points</p>
                            </div>
                            <div className="bg-gray-800 rounded-lg p-2 text-center">
                              <p className="text-blue-400 font-bold text-lg">{m.total_points}</p>
                              <p className="text-gray-500 text-xs">Total</p>
                            </div>
                          </div>
                          <button onClick={() => navigate(`/fields/${fieldId}/missions/${m.id}`)}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg text-sm font-medium transition-all">
                            View Map & Analytics
                          </button>
                        </>
                      ) : (
                        <>
                          {/* Flight date picker */}
                          <div className="mb-3">
                            <label className="text-xs text-gray-400 block mb-1">Flight Date</label>
                            <input type="date"
                              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-green-500"
                              value={flightDates[m.id] || ''}
                              onChange={(e) => setFlightDates({ ...flightDates, [m.id]: e.target.value })} />
                          </div>

                          {/* Log file upload */}
                          <label className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg text-sm font-medium cursor-pointer transition-all">
                            {uploading === m.id ? 'Processing...' : 'Upload Drone Log (.xls / .csv)'}
                            <input type="file" accept=".xls,.csv" className="hidden"
                              onChange={(e) => e.target.files[0] && handleUploadLog(m.id, e.target.files[0])} />
                          </label>

                          {m.status === 'failed' && (
                            <p className="text-xs text-red-400 mt-2">Previous upload failed. Try again.</p>
                          )}
                        </>
                      )}
                    </div>

                    {/* Panel 3: CNN Video Pipeline */}
                    <div className="px-5 py-4">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
                        CNN Video Detection
                      </p>
                      <div className="space-y-2 mb-3">
                        <div>
                          <label className="text-xs text-gray-400 block mb-1">Drone Video (.mp4)</label>
                          <label className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 px-3 py-2 rounded-lg text-xs cursor-pointer transition-all">
                            {videoFiles[m.id]?.video ? videoFiles[m.id].video.name : 'Choose video...'}
                            <input type="file" accept=".mp4,video/*" className="hidden"
                              onChange={(e) => e.target.files[0] && setVideoFiles(v => ({ ...v, [m.id]: { ...v[m.id], video: e.target.files[0] } }))} />
                          </label>
                        </div>
                        <div>
                          <label className="text-xs text-gray-400 block mb-1">ArduPilot GPS Log (.csv)</label>
                          <label className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 px-3 py-2 rounded-lg text-xs cursor-pointer transition-all">
                            {videoFiles[m.id]?.csv ? videoFiles[m.id].csv.name : 'Choose CSV...'}
                            <input type="file" accept=".csv" className="hidden"
                              onChange={(e) => e.target.files[0] && setVideoFiles(v => ({ ...v, [m.id]: { ...v[m.id], csv: e.target.files[0] } }))} />
                          </label>
                        </div>
                      </div>
                      <button
                        onClick={() => handleUploadVideo(m.id)}
                        disabled={uploadingVideo === m.id || !videoFiles[m.id]?.video || !videoFiles[m.id]?.csv}
                        className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white py-2 rounded-lg text-xs font-medium transition-all">
                        {uploadingVideo === m.id ? 'Running CNN...' : 'Run CNN Pipeline'}
                      </button>
                      {m.status === 'completed' && (
                        <button
                          onClick={() => navigate(`/fields/${fieldId}/missions/${m.id}`)}
                          className="w-full mt-2 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg text-xs font-medium transition-all">
                          View Folium Map
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Mission Modal */}
      {showMissionForm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-1 text-white">Create New Mission</h2>
            <p className="text-xs text-gray-400 mb-5">
              After creating, upload the autopilot plan and drone log separately.
            </p>
            <form onSubmit={handleCreateMission} className="space-y-3">
              {[
                ['name', 'Mission Name', 'text', true],
                ['drone_model', 'Drone Model (e.g. DJI Phantom 4)', 'text', false],
                ['flight_altitude_m', 'Flight Altitude (m)', 'number', false],
              ].map(([key, placeholder, type, req]) => (
                <input key={key} type={type}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-green-500"
                  placeholder={placeholder} required={req} value={missionForm[key]}
                  onChange={(e) => setMissionForm({ ...missionForm, [key]: e.target.value })} />
              ))}
              <select
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white outline-none"
                value={missionForm.anomaly_mode}
                onChange={(e) => setMissionForm({ ...missionForm, anomaly_mode: e.target.value })}>
                <option value="rule_based">Rule Based (Altitude Variance)</option>
                <option value="random">Random (Testing)</option>
                <option value="model">CNN Model</option>
              </select>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowMissionForm(false)}
                  className="flex-1 border border-gray-700 text-gray-400 hover:text-white py-2 rounded-lg text-sm transition-all">
                  Cancel
                </button>
                <button type="submit" disabled={loading}
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition-all">
                  {loading ? 'Creating...' : 'Create Mission'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
