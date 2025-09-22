import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import LeadsTable from './LeadsTable'
import MetricsCards from './MetricsCards'
import HITLPanel from './HITLPanel'

export default function Dashboard() {
  const { user, loading, signOut } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) {
      navigate('/login')
    }
  }, [user, loading, navigate])

  const { data: leads, isLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('leads')
        .select('*')
        .order('created_at', { ascending: false })
      
      if (error) throw error
      return data
    },
    enabled: !!user,
  })

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('leads')
        .select('status, qualified_score')
      
      if (error) throw error
      
      const total = data.length
      const qualified = data.filter(l => l.qualified_score && l.qualified_score > 0.7).length
      const scheduled = data.filter(l => l.status === 'scheduled').length
      const avgScore = data.reduce((acc, l) => acc + (l.qualified_score || 0), 0) / total
      
      return { total, qualified, scheduled, avgScore }
    },
    enabled: !!user,
  })

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>
  }

  if (!user) {
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                AAA Real Estate Dashboard
              </h1>
              <p className="text-gray-600">Lead Management & Analytics</p>
            </div>
            <button
              onClick={signOut}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Metrics Cards */}
          <MetricsCards metrics={metrics} />

          {/* HITL Panel */}
          <HITLPanel />

          {/* Leads Table */}
          <div className="mt-8">
            <LeadsTable leads={leads} isLoading={isLoading} />
          </div>
        </div>
      </main>
    </div>
  )
}
