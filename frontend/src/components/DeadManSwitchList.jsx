export default function DeadManSwitchList({ switches }) {
  const statusBadge = (status) => {
    const styles = {
      ok: 'bg-green-900/50 text-green-300',
      overdue: 'bg-yellow-900/50 text-yellow-300',
      critical: 'bg-red-900/50 text-red-300',
      unknown: 'bg-slate-700 text-slate-400'
    }
    const labels = {
      ok: 'OK',
      overdue: 'OVERDUE',
      critical: 'CRITICAL',
      unknown: '—'
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.unknown}`}>
        {labels[status] || labels.unknown}
      </span>
    )
  }

  const formatInterval = (seconds) => {
    if (seconds >= 86400) return `${Math.floor(seconds / 86400)}d`
    if (seconds >= 3600) return `${Math.floor(seconds / 3600)}h`
    return `${Math.floor(seconds / 60)}m`
  }

  const formatPacificTime = (dateStr) => {
    if (!dateStr) return 'Never'
    // Backend sends naive UTC datetimes - ensure they're parsed as UTC
    const utcStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
    const date = new Date(utcStr)
    const time = date.toLocaleString('en-US', {
      timeZone: 'America/Los_Angeles',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
    return `${time} PT`
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-700/50">
          <tr className="text-left text-xs text-slate-400 uppercase">
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Name</th>
            <th className="px-4 py-2 font-medium">Interval</th>
            <th className="px-4 py-2 font-medium">Last Ping</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700">
          {switches.map(sw => (
            <tr key={sw.id} className="hover:bg-slate-700/30">
              <td className="px-4 py-2">
                {statusBadge(sw.status)}
              </td>
              <td className="px-4 py-2 text-white font-medium">
                {sw.name}
              </td>
              <td className="px-4 py-2 text-slate-400">
                {formatInterval(sw.expected_interval)}
              </td>
              <td className="px-4 py-2 text-slate-400 text-xs">
                {formatPacificTime(sw.last_ping)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
