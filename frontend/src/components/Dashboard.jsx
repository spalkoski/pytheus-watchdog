import TargetTable from './TargetTable'
import IncidentList from './IncidentList'
import DeadManSwitchList from './DeadManSwitchList'

export default function Dashboard({ data, onRefresh }) {
  const activeIncidentCount = data.active_incidents.length

  return (
    <div className="space-y-4">
      {/* Compact Stats Bar */}
      <div className="flex items-center justify-between bg-slate-800 rounded-lg px-4 py-3 border border-slate-700">
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Uptime (24h):</span>
            <span className={`font-semibold ${data.uptime_percentage >= 99 ? 'text-green-400' : data.uptime_percentage >= 95 ? 'text-yellow-400' : 'text-red-400'}`}>
              {data.uptime_percentage.toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Checks:</span>
            <span className="font-semibold text-blue-400">{data.total_checks_24h.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Incidents:</span>
            <span className={`font-semibold ${activeIncidentCount === 0 ? 'text-green-400' : 'text-red-400'}`}>
              {activeIncidentCount}
            </span>
          </div>
        </div>
        <button
          onClick={onRefresh}
          className="px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-200 rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Active Incidents */}
      {data.active_incidents.length > 0 && (
        <section className="bg-red-900/20 border border-red-800 rounded-lg p-3">
          <h2 className="text-sm font-semibold text-red-300 mb-2 flex items-center gap-2">
            <span>⚠️</span> Active Incidents ({data.active_incidents.length})
          </h2>
          <IncidentList incidents={data.active_incidents} onDelete={onRefresh} />
        </section>
      )}

      {/* Monitored Services Table */}
      <section>
        <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wide">
          Monitored Services
        </h2>
        <TargetTable targets={data.targets} />
      </section>

      {/* Dead Man's Switches */}
      {data.deadman_switches.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wide">
            Dead Man's Switches
          </h2>
          <DeadManSwitchList switches={data.deadman_switches} />
        </section>
      )}
    </div>
  )
}
