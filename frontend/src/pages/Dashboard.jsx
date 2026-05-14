import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listFields, createField } from '../api/services'
import StatCard from '../components/UI/StatCard'

export default function Dashboard() {
  const [fields, setFields] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', rice_type: '', soil_type: '', irrigation_type: '', area_hectares: '', cell_size_m: 10 })
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { fetchFields() }, [])

  const fetchFields = async () => {
    try {
      const res = await listFields()
      setFields(res.data)
    } catch { navigate('/login') }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await createField({
        ...form,
        area_hectares: parseFloat(form.area_hectares) || null,
        cell_size_m: parseInt(form.cell_size_m),
        boundary_geojson: {
          type: 'Polygon',
          coordinates: [[[77.7195,11.3390],[77.7213,11.3390],[77.7213,11.3408],[77.7195,11.3408],[77.7195,11.3390]]]
        }
      })
      setShowForm(false)
      fetchFields()
    } catch (err) {
      alert(err.response?.data?.detail || 'Error creating field')
    } finally { setLoading(false) }
  }

  const logout = () => { localStorage.removeItem('token'); navigate('/login') }

  return (
    <div className="min-h-screen bg-brand-dark">
      {/* Header */}
      <header className="bg-gray-900 border-b border-brand-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="font-bold text-lg">Precision Agriculture Platform</h1>
            <p className="text-gray-400 text-xs">Drone Anomaly Detection</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setShowForm(true)}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium">
            + New Field
          </button>
          <button onClick={logout} className="text-gray-400 hover:text-white text-sm px-3 py-2">Logout</button>
        </div>
      </header>

      <div className="p-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Fields" value={fields.length} color="green" />
          <StatCard label="Total Missions" value={fields.reduce((s, f) => s + (f.mission_count || 0), 0)} color="blue" />
          <StatCard label="Grid Resolution" value="10m x 10m" color="yellow" />
          <StatCard label="Detection Mode" value="Rule Based" color="red" />
        </div>

        {/* Fields Grid */}
        <h2 className="text-lg font-semibold mb-4">Your Fields</h2>
        {fields.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p>No fields yet. Create your first field to get started.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {fields.map((f) => (
              <div key={f.id} onClick={() => navigate(`/fields/${f.id}`)}
                className="bg-brand-card border border-brand-border rounded-xl p-5 cursor-pointer hover:border-green-500 transition-all">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-semibold text-white">{f.name}</h3>
                  <span className="bg-green-900 text-green-300 text-xs px-2 py-1 rounded-full">{f.rice_type || 'N/A'}</span>
                </div>
                <div className="space-y-1 text-sm text-gray-400">
                  <p>Soil: {f.soil_type || '—'} &nbsp;|&nbsp; Irrigation: {f.irrigation_type || '—'}</p>
                  <p>Area: {f.area_hectares ? `${f.area_hectares} ha` : '—'}</p>
                  <p>Grid: {f.n_rows && f.n_cols ? `${f.n_rows} x ${f.n_cols} cells` : 'Generating...'}</p>
                </div>
                <div className="mt-4 pt-3 border-t border-brand-border text-xs text-gray-500">
                  Created {new Date(f.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Field Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-brand-card border border-brand-border rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Create New Field</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              {[['name','Field Name',true],['rice_type','Rice Type'],['soil_type','Soil Type'],['irrigation_type','Irrigation Type'],['area_hectares','Area (hectares)']].map(([key, label, req]) => (
                <input key={key} className="w-full bg-gray-800 border border-brand-border rounded-lg px-3 py-2 text-sm outline-none focus:border-green-500"
                  placeholder={label} required={req} value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
              ))}
              <select className="w-full bg-gray-800 border border-brand-border rounded-lg px-3 py-2 text-sm outline-none"
                value={form.cell_size_m} onChange={(e) => setForm({ ...form, cell_size_m: e.target.value })}>
                <option value={5}>5m x 5m grid</option>
                <option value={10}>10m x 10m grid</option>
                <option value={20}>20m x 20m grid</option>
              </select>
              <p className="text-xs text-gray-500">Note: Boundary will use default Erode, TN coordinates. Update via API for custom boundaries.</p>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="flex-1 border border-brand-border text-gray-400 py-2 rounded-lg text-sm">Cancel</button>
                <button type="submit" disabled={loading}
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg text-sm font-medium disabled:opacity-50">
                  {loading ? 'Creating...' : 'Create Field'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
