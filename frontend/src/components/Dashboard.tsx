import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useLeads } from '../hooks/useLeads'
import { useQuery } from '@tanstack/react-query'
import { supabase, type Company } from '../lib/supabase'
import LeadsTable from './LeadsTable'
import MetricsCards from './MetricsCards'
import HITLPanel from './HITLPanel'
import { Button } from './ui/button'
import { Badge } from './ui/badge'

interface DashboardProps {
  company: Company
  onCompanyChange: () => void
}

export default function Dashboard({ company, onCompanyChange }: DashboardProps) {
  const { user, loading, signOut } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) {
      navigate('/login')
    }
  }, [user, loading, navigate])

  const { data: leads, isLoading } = useLeads()

  // Calculate metrics from mock leads
  const metrics = leads ? {
    total: leads.length,
    qualified: leads.filter(l => l.qualified_score && l.qualified_score > 0.7).length,
    scheduled: leads.filter(l => l.status === 'scheduled').length,
    avgScore: leads.reduce((acc, l) => acc + (l.qualified_score || 0), 0) / leads.length
  } : { total: 0, qualified: 0, scheduled: 0, avgScore: 0 }

  const { data: integrations } = useQuery({
    queryKey: ['integrations', company.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('company_integrations')
        .select('*')
        .eq('company_id', company.id)
        .eq('is_active', true)

      if (error) throw error
      return data
    },
    enabled: !!user && !!company.id,
  })

  const getIndustryBadgeColor = (industry: string) => {
    const colors = {
      real_estate: 'bg-blue-100 text-blue-800',
      ecommerce: 'bg-green-100 text-green-800',
      saas: 'bg-purple-100 text-purple-800',
      healthcare: 'bg-red-100 text-red-800',
      general: 'bg-gray-100 text-gray-800'
    }
    return colors[industry as keyof typeof colors] || colors.general
  }

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
            <div className="flex items-center space-x-4">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  {company.name}
                </h1>
                <div className="flex items-center space-x-2 mt-1">
                  <p className="text-gray-600">Automation Dashboard</p>
                  <Badge className={getIndustryBadgeColor(company.industry)}>
                    {company.industry.replace('_', ' ').toUpperCase()}
                  </Badge>
                  <Badge variant="outline">
                    {company.subscription_tier}
                  </Badge>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Button
                variant="outline"
                onClick={() => navigate('/admin/lead-magnets')}
                className="text-sm"
              >
                Lead Magnets
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate('/admin/conversations')}
                className="text-sm"
              >
                Conversations
              </Button>
              <Button
                variant="outline"
                onClick={onCompanyChange}
                className="text-sm"
              >
                Switch Company
              </Button>
              <Button
                variant="destructive"
                onClick={signOut}
                className="text-sm"
              >
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Company Stats Overview */}
          <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-sm font-medium text-gray-500">Active Integrations</h3>
              <p className="text-2xl font-bold text-gray-900">
                {integrations?.length || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-sm font-medium text-gray-500">Monthly Limit</h3>
              <p className="text-2xl font-bold text-gray-900">
                {company.settings?.limits?.max_leads_per_month || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-sm font-medium text-gray-500">Max Users</h3>
              <p className="text-2xl font-bold text-gray-900">
                {company.settings?.limits?.max_users || 0}
              </p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <h3 className="text-sm font-medium text-gray-500">Features</h3>
              <div className="flex flex-wrap gap-1 mt-1">
                {company.settings?.features?.hitl_enabled && (
                  <Badge variant="secondary" className="text-xs">HITL</Badge>
                )}
                {company.settings?.features?.analytics_enabled && (
                  <Badge variant="secondary" className="text-xs">Analytics</Badge>
                )}
                {company.settings?.features?.custom_workflows && (
                  <Badge variant="secondary" className="text-xs">Workflows</Badge>
                )}
              </div>
            </div>
          </div>

          {/* Metrics Cards */}
          <MetricsCards metrics={metrics} />

          {/* HITL Panel */}
          {company.settings?.features?.hitl_enabled && (
            <HITLPanel company={company} />
          )}

          {/* Leads Table */}
          <div className="mt-8">
            <LeadsTable leads={leads} isLoading={isLoading} company={company} />
          </div>
        </div>
      </main>
    </div>
  )
}
