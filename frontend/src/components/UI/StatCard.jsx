const colors = {
  green:  'text-green-400',
  blue:   'text-blue-400',
  yellow: 'text-yellow-400',
  red:    'text-red-400',
  purple: 'text-purple-400',
}

export default function StatCard({ label, value, color = 'green', small = false }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-gray-400 text-xs mb-1">{label}</p>
      <p className={`font-bold ${colors[color]} ${small ? 'text-lg' : 'text-2xl'}`}>{value}</p>
    </div>
  )
}
