export default function StatsOverview({ uptime, totalChecks, activeIncidents, onRefresh }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="text-sm text-slate-400 mb-1">Uptime (24h)</div>
        <div className={`text-3xl font-bold ${uptime >= 99 ? 'text-green-400' : uptime >= 95 ? 'text-yellow-400' : 'text-red-400'}`}>
          {uptime.toFixed(2)}%
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="text-sm text-slate-400 mb-1">Total Checks (24h)</div>
        <div className="text-3xl font-bold text-blue-400">
          {totalChecks.toLocaleString()}
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="text-sm text-slate-400 mb-1">Active Incidents</div>
        <div className={`text-3xl font-bold ${activeIncidents === 0 ? 'text-green-400' : 'text-red-400'}`}>
          {activeIncidents}
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 flex items-center justify-center">
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          🔄 Refresh
        </button>
      </div>
    </div>
  )
}
