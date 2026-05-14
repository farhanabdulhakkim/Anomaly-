import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/services'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', full_name: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handle = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await register(form)
        setMode('login')
        setError('Registered! Please login.')
      } else {
        const res = await login(form.email, form.password)
        localStorage.setItem('token', res.data.access_token)
        navigate('/')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-dark">
      <div className="bg-brand-card border border-brand-border rounded-xl p-8 w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold mt-2">Precision Agriculture Platform</h1>
          <p className="text-gray-400 text-sm mt-1">Drone Anomaly Detection System</p>
        </div>

        <div className="flex mb-6 bg-gray-800 rounded-lg p-1">
          {['login', 'register'].map((m) => (
            <button key={m} onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all
                ${mode === m ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'}`}>
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>

        <form onSubmit={handle} className="space-y-4">
          {mode === 'register' && (
            <input className="input-field" placeholder="Full Name"
              value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          )}
          <input className="input-field" type="email" placeholder="Email"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <input className="input-field" type="password" placeholder="Password"
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />

          {error && <p className={`text-sm ${error.includes('Registered') ? 'text-green-400' : 'text-red-400'}`}>{error}</p>}

          <button type="submit" disabled={loading}
            className="w-full bg-green-600 hover:bg-green-700 text-white py-2.5 rounded-lg font-semibold transition-all disabled:opacity-50">
            {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
          </button>
        </form>
      </div>

      <style>{`.input-field { width:100%; background:#111827; border:1px solid #374151; border-radius:8px; padding:10px 14px; color:#f9fafb; outline:none; } .input-field:focus { border-color:#22c55e; }`}</style>
    </div>
  )
}
