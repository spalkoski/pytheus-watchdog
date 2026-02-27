export default function TargetTable({ targets }) {
  const formatPacificTime = (dateStr) => {
    if (!dateStr) return '—'
    const date = new Date(dateStr)
    const time = date.toLocaleTimeString('en-US', {
      timeZone: 'America/Los_Angeles',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    })
    return `${time} PT`
  }

  const statusBadge = (status) => {
    const styles = {
      up: 'bg-green-900/50 text-green-300',
      down: 'bg-red-900/50 text-red-300',
      degraded: 'bg-orange-900/50 text-orange-300',
      unknown: 'bg-slate-700 text-slate-400'
    }
    const labels = {
      up: 'UP',
      down: 'DOWN',
      degraded: 'ISSUES',
      unknown: '—'
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.unknown}`}>
        {labels[status] || labels.unknown}
      </span>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-700/50">
          <tr className="text-left text-xs text-slate-400 uppercase">
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Service</th>
            <th className="px-4 py-2 font-medium">Response</th>
            <th className="px-4 py-2 font-medium">Uptime 24h</th>
            <th className="px-4 py-2 font-medium">Last Check</th>
            <th className="px-4 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700">
          {targets.map(target => (
            <tr key={target.name} className="hover:bg-slate-700/30">
              <td className="px-4 py-2">
                {statusBadge(target.status)}
              </td>
              <td className="px-4 py-2">
                <div className="font-medium text-white">{target.name}</div>
                {target.url && (
                  target.type === 'ping' ? (
                    <span className="text-xs text-slate-500">
                      {target.url}
                    </span>
                  ) : (
                    <a
                      href={target.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-slate-500 hover:text-blue-400 truncate block max-w-xs"
                    >
                      {target.url.replace(/^https?:\/\//, '')}
                    </a>
                  )
                )}
                {target.ai_summary && (
                  <div className="text-xs text-blue-400/80 mt-1 italic">
                    {target.ai_summary}
                  </div>
                )}
              </td>
              <td className="px-4 py-2 text-slate-300">
                {target.response_time !== null ? `${target.response_time.toFixed(0)}ms` : '—'}
              </td>
              <td className="px-4 py-2">
                <span className={`${
                  target.uptime_24h >= 99.9 ? 'text-green-400' :
                  target.uptime_24h >= 99 ? 'text-green-300' :
                  target.uptime_24h >= 95 ? 'text-yellow-400' :
                  'text-red-400'
                }`}>
                  {target.uptime_24h?.toFixed(1)}%
                </span>
              </td>
              <td className="px-4 py-2 text-slate-400 text-xs">
                {formatPacificTime(target.last_check)}
              </td>
              <td className="px-4 py-2">
                {target.url && target.type !== 'ping' && (
                  <a
                    href={target.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-500 hover:text-slate-300"
                    title="Open in new tab"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
