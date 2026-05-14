import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { getFieldTrend } from '../../api/services'

export default function TrendChart({ fieldId }) {
  const [data, setData] = useState([])

  useEffect(() => {
    getFieldTrend(fieldId).then(res => {
      setData(res.data.trend.map(t => ({
        name: t.mission_name,
        anomaly_cells: t.anomaly_cells,
        anomaly_points: t.total_anomaly_points,
      })))
    }).catch(() => {})
  }, [fieldId])

  if (!data.length) return null

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
        <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
        <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }} />
        <Legend />
        <Line type="monotone" dataKey="anomaly_cells" stroke="#f87171" strokeWidth={2} dot={{ fill: '#f87171' }} name="Anomaly Cells" />
        <Line type="monotone" dataKey="anomaly_points" stroke="#fbbf24" strokeWidth={2} dot={{ fill: '#fbbf24' }} name="Anomaly Points" />
      </LineChart>
    </ResponsiveContainer>
  )
}
