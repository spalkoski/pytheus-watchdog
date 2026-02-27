import { useState } from 'react'

export default function IncidentList({ incidents, onDelete }) {
  const [deleting, setDeleting] = useState(null)

  const severityBadge = (severity) => {
    const styles = {
      critical: 'bg-red-800 text-red-200',
      warning: 'bg-yellow-800 text-yellow-200',
      info: 'bg-blue-800 text-blue-200'
    }
    return (
      <span className={`px-1.5 py-0.5 rounded text-xs font-medium uppercase ${styles[severity] || 'bg-slate-700 text-slate-300'}`}>
        {severity}
      </span>
    )
  }

  const handleDelete = async (incidentId) => {
    if (deleting) return
    setDeleting(incidentId)
    try {
      const response = await fetch(`/api/incidents/${incidentId}`, {
        method: 'DELETE'
      })
      if (response.ok && onDelete) {
        onDelete(incidentId)
      }
    } catch (error) {
      console.error('Failed to delete incident:', error)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="space-y-1">
      {incidents.map(incident => (
        <div
          key={incident.id}
          className="flex items-center gap-3 text-sm py-1 group"
        >
          {severityBadge(incident.severity)}
          <span className="text-white font-medium">{incident.target_name}</span>
          <span className="text-slate-400 flex-1 truncate">{incident.title}</span>
          <span className="text-slate-500 text-xs">
            {incident.duration_minutes}m ago
          </span>
          <button
            onClick={() => handleDelete(incident.id)}
            disabled={deleting === incident.id}
            className="opacity-0 group-hover:opacity-100 px-2 py-0.5 text-xs bg-red-800 hover:bg-red-700 text-red-200 rounded transition-all disabled:opacity-50"
            title="Delete incident"
          >
            {deleting === incident.id ? '...' : 'x'}
          </button>
        </div>
      ))}
    </div>
  )
}
