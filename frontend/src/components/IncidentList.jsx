export default function IncidentList({ incidents }) {
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

  return (
    <div className="space-y-1">
      {incidents.map(incident => (
        <div
          key={incident.id}
          className="flex items-center gap-3 text-sm py-1"
        >
          {severityBadge(incident.severity)}
          <span className="text-white font-medium">{incident.target_name}</span>
          <span className="text-slate-400 flex-1 truncate">{incident.title}</span>
          <span className="text-slate-500 text-xs">
            {incident.duration_minutes}m ago
          </span>
        </div>
      ))}
    </div>
  )
}
