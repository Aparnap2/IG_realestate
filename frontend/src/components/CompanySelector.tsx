import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { supabase, type Company } from '../lib/supabase'
import { useAuth } from '../hooks/useAuth'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'

interface CompanySelectorProps {
  onCompanySelect: (company: Company) => void
  selectedCompany?: Company | null
}

export default function CompanySelector({ onCompanySelect, selectedCompany }: CompanySelectorProps) {
  const { user } = useAuth()
  const [isCreating, setIsCreating] = useState(false)

  const { data: userCompanies, isLoading } = useQuery({
    queryKey: ['user-companies', user?.id],
    queryFn: async () => {
      if (!user?.id) return []
      
      const { data, error } = await supabase
        .from('company_users')
        .select(`
          role,
          is_active,
          company:companies (
            id,
            name,
            slug,
            industry,
            settings,
            subscription_tier,
            is_active,
            created_at
          )
        `)
        .eq('user_id', user.id)
        .eq('is_active', true)
      
      if (error) throw error
      
      return data
        .filter(item => item.company && item.company.is_active)
        .map(item => ({
          ...item.company,
          user_role: item.role
        }))
    },
    enabled: !!user?.id,
  })

  const createCompanyMutation = async (companyData: {
    name: string
    slug: string
    industry: string
  }) => {
    if (!user?.id) throw new Error('User not authenticated')

    // Create company
    const { data: company, error: companyError } = await supabase
      .from('companies')
      .insert({
        name: companyData.name,
        slug: companyData.slug,
        industry: companyData.industry,
        settings: {
          branding: {
            primary_color: '#3B82F6',
            secondary_color: '#1F2937'
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
      })
      .select()
      .single()

    if (companyError) throw companyError

    // Add user as owner
    const { error: userError } = await supabase
      .from('company_users')
      .insert({
        company_id: company.id,
        user_id: user.id,
        role: 'owner',
        is_active: true,
        joined_at: new Date().toISOString()
      })

    if (userError) throw userError

    return company
  }

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

  const getRoleBadgeColor = (role: string) => {
    const colors = {
      owner: 'bg-yellow-100 text-yellow-800',
      admin: 'bg-red-100 text-red-800',
      member: 'bg-blue-100 text-blue-800',
      viewer: 'bg-gray-100 text-gray-800'
    }
    return colors[role as keyof typeof colors] || colors.viewer
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading your companies...</p>
        </div>
      </div>
    )
  }

  if (!userCompanies || userCompanies.length === 0) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Card>
          <CardHeader className="text-center">
            <CardTitle>Welcome to the Automation Platform</CardTitle>
            <CardDescription>
              You don't have access to any companies yet. Create your first company to get started.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button 
              onClick={() => setIsCreating(true)}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Create Your First Company
            </Button>
          </CardContent>
        </Card>

        {isCreating && (
          <CreateCompanyForm 
            onSubmit={createCompanyMutation}
            onCancel={() => setIsCreating(false)}
          />
        )}
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Select Company</h1>
        <p className="text-gray-600">Choose a company to access its automation dashboard</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {userCompanies.map((company: any) => (
          <Card 
            key={company.id}
            className={`cursor-pointer transition-all hover:shadow-lg ${
              selectedCompany?.id === company.id ? 'ring-2 ring-blue-500' : ''
            }`}
            onClick={() => onCompanySelect(company)}
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">{company.name}</CardTitle>
                  <CardDescription className="text-sm">@{company.slug}</CardDescription>
                </div>
                <Badge className={getRoleBadgeColor(company.user_role)}>
                  {company.user_role}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Badge className={getIndustryBadgeColor(company.industry)}>
                  {company.industry.replace('_', ' ').toUpperCase()}
                </Badge>
                
                <div className="text-sm text-gray-600">
                  <p>Tier: {company.subscription_tier}</p>
                  <p>Created: {new Date(company.created_at).toLocaleDateString()}</p>
                </div>

                {company.settings?.limits && (
                  <div className="text-xs text-gray-500 pt-2 border-t">
                    <p>Leads: {company.settings.limits.max_leads_per_month}/month</p>
                    <p>Integrations: {company.settings.limits.max_integrations}</p>
                    <p>Users: {company.settings.limits.max_users}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-6 text-center">
        <Button 
          variant="outline"
          onClick={() => setIsCreating(true)}
        >
          Create New Company
        </Button>
      </div>

      {isCreating && (
        <CreateCompanyForm 
          onSubmit={createCompanyMutation}
          onCancel={() => setIsCreating(false)}
        />
      )}
    </div>
  )
}

interface CreateCompanyFormProps {
  onSubmit: (data: { name: string; slug: string; industry: string }) => Promise<any>
  onCancel: () => void
}

function CreateCompanyForm({ onSubmit, onCancel }: CreateCompanyFormProps) {
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    industry: 'general'
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const industries = [
    { value: 'real_estate', label: 'Real Estate' },
    { value: 'ecommerce', label: 'E-commerce' },
    { value: 'saas', label: 'SaaS' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'general', label: 'General' }
  ]

  const handleNameChange = (name: string) => {
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim()

    setFormData({ ...formData, name, slug })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError('')

    try {
      await onSubmit(formData)
      onCancel() // Close form on success
      window.location.reload() // Refresh to show new company
    } catch (err: any) {
      setError(err.message || 'Failed to create company')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create New Company</CardTitle>
          <CardDescription>
            Set up a new company to start automating your workflows
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Company Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => handleNameChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Acme Corp"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Company Slug
              </label>
              <input
                type="text"
                value={formData.slug}
                onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="acme-corp"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Used in URLs: {formData.slug}.platform.com
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Industry
              </label>
              <select
                value={formData.industry}
                onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {industries.map(industry => (
                  <option key={industry.value} value={industry.value}>
                    {industry.label}
                  </option>
                ))}
              </select>
            </div>

            {error && (
              <div className="text-red-600 text-sm">{error}</div>
            )}

            <div className="flex space-x-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={onCancel}
                disabled={isSubmitting}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
              >
                {isSubmitting ? 'Creating...' : 'Create Company'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}