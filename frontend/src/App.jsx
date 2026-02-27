import { useState, useEffect } from 'react'
import axios from 'axios'
import Dashboard from './components/Dashboard'

function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchDashboard = async () => {
    try {
      const response = await axios.get('/api/dashboard')
      setData(response.data)
      setError(null)
    } catch (err) {
      setError(err.message)
      console.error('Error fetching dashboard:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-white flex items-center gap-2">
            <span>🛡️</span>
            Pytheus Watchdog
          </h1>
          <span className="text-xs text-slate-500">
            Auto-refresh: 30s
          </span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-4">
        {loading && (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p className="mt-2 text-slate-400 text-sm">Loading...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 mb-4 text-sm">
            <p className="text-red-200">Error: {error}</p>
          </div>
        )}

        {data && <Dashboard data={data} onRefresh={fetchDashboard} />}
      </main>
    </div>
  )
}

export default App
