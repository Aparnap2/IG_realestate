import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Login from './components/Login'
import CompanySelector from './components/CompanySelector'
import { AuthProvider, useAuth } from './hooks/useAuth'
// import { Company } from './lib/supabase'

interface Company {
  id: string;
  name: string;
  domain?: string;
}

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

  return (
    <div className="min-h-screen bg-gray-50">
      <Routes>
        <Route 
          path="/" 
          element={
            <Dashboard 
              company={selectedCompany}
              onCompanyChange={() => setSelectedCompany(null)}
            />
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
