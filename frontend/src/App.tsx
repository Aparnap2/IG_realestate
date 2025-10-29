import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Login from './components/Login'
import CompanySelector from './components/CompanySelector'
import AdminLeadMagnets from './pages/AdminLeadMagnets'
import AdminConversations from './pages/AdminConversations'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { Company } from './lib/supabase'

const queryClient = new QueryClient()

function AppContent() {
  const { user, loading } = useAuth()
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null)

  // Load selected company from localStorage
  useEffect(() => {
    if (user) {
      const savedCompanyId = localStorage.getItem('selectedCompanyId')
      if (savedCompanyId) {
        // You might want to validate this company ID still exists and user has access
        // For now, we'll let the CompanySelector handle the validation
      }
    }
  }, [user])

  // Save selected company to localStorage
  const handleCompanySelect = (company: Company) => {
    setSelectedCompany(company)
    localStorage.setItem('selectedCompanyId', company.id)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <Login />
  }

  // TEMPORARY: Auto-select mock company for testing
  if (!selectedCompany) {
    const mockCompany: Company = {
      id: 'mock-company-123',
      name: 'AAA Real Estate Test',
      slug: 'aaa-real-estate-test',
      industry: 'Real Estate',
      subscription_tier: 'professional' as const,
      is_active: true,
      created_at: '2025-10-13T00:00:00Z',
      updated_at: '2025-10-13T00:00:00Z',
      settings: {
        branding: {
          primary_color: '#3b82f6'
        },
        features: {
          hitl_enabled: true,
          analytics_enabled: true,
          custom_workflows: true
        },
        limits: {
          max_leads_per_month: 1000,
          max_integrations: 5,
          max_users: 10
        }
      }
    }
    
    // Auto-select for testing
    setSelectedCompany(mockCompany)
    localStorage.setItem('selectedCompanyId', mockCompany.id)
  }

  // Skip company selector for now
  /* 
  if (!selectedCompany) {
    return (
      <div className="min-h-screen bg-gray-50">
        <CompanySelector 
          onCompanySelect={handleCompanySelect}
          selectedCompany={selectedCompany}
        />
      </div>
    )
  }
  */

  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route
          path="/"
          element={
            selectedCompany ? (
              <Dashboard
                company={selectedCompany}
                onCompanyChange={() => setSelectedCompany(null)}
              />
            ) : (
              <div>Loading company data...</div>
            )
          }
        />
        <Route
          path="/admin/lead-magnets"
          element={
            selectedCompany ? (
              <AdminLeadMagnets company={selectedCompany} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/admin/conversations"
          element={
            selectedCompany ? (
              <AdminConversations company={selectedCompany} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/admin/analytics"
          element={
            selectedCompany ? (
              <AnalyticsDashboard />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/company"
          element={
            <CompanySelector
              onCompanySelect={handleCompanySelect}
              selectedCompany={selectedCompany}
            />
          }
        />
        {/* Catch-all route for invalid paths */}
        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <AppContent />
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
