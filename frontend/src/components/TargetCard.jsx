export default function TargetCard({ target }) {
  const statusText = {
    up: '🟢 UP',
    down: '🔴 DOWN',
    degraded: '🟡 DEGRADED',
    unknown: '⚪ UNKNOWN'
  }

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-white">{target.name}</h3>
          <p className="text-xs text-slate-500 uppercase">{target.type}</p>
          {target.url && (
            <a
              href={target.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300 hover:underline truncate block mt-1"
              title={target.url}
            >
              {target.url.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium flex-shrink-0 ml-2 ${
          target.status === 'up' ? 'bg-green-900/50 text-green-300' :
          target.status === 'down' ? 'bg-red-900/50 text-red-300' :
          'bg-gray-900/50 text-gray-300'
        }`}>
          {statusText[target.status] || statusText.unknown}
        </div>
      </div>

      <div className="space-y-2">
        {target.response_time !== null && (
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Response Time:</span>
            <span className="text-white font-medium">{target.response_time.toFixed(0)}ms</span>
          </div>
        )}

        {target.last_check && (
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Last Check:</span>
            <span className="text-white font-medium">
              {new Date(target.last_check).toLocaleTimeString()}
            </span>
          </div>
        )}

        <div className="pt-3 mt-3 border-t border-slate-700 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">24h Uptime:</span>
            <span className="text-slate-300 font-medium">{target.uptime_24h?.toFixed(2)}%</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">7d Uptime:</span>
            <span className="text-slate-300 font-medium">{target.uptime_7d?.toFixed(2)}%</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">30d Uptime:</span>
            <span className="text-slate-300 font-medium">{target.uptime_30d?.toFixed(2)}%</span>
          </div>
        </div>

        {target.url && (
          <div className="pt-3 mt-1">
            <a
              href={target.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 rounded transition-colors"
            >
              <span>Open</span>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
