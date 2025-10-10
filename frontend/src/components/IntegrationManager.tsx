import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase, type Company, type CompanyIntegration } from '../lib/supabase'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Textarea } from './ui/textarea'

interface IntegrationManagerProps {
  company: Company
}

interface IntegrationType {
  type: string
  name: string
  description: string
  icon: string
  fields: Array<{
    key: string
    label: string
    type: 'text' | 'password' | 'url' | 'textarea'
    required: boolean
    placeholder?: string
    description?: string
  }>
}

const AVAILABLE_INTEGRATIONS: IntegrationType[] = [
  {
    type: 'instagram',
    name: 'Instagram',
    description: 'Connect Instagram Business Account for lead capture',
    icon: '📷',
    fields: [
      { key: 'app_id', label: 'App ID', type: 'text', required: true, placeholder: 'Your Instagram App ID' },
      { key: 'app_secret', label: 'App Secret', type: 'password', required: true, placeholder: 'Your Instagram App Secret' },
      { key: 'access_token', label: 'Access Token', type: 'password', required: true, placeholder: 'Page Access Token' },
      { key: 'verify_token', label: 'Verify Token', type: 'text', required: true, placeholder: 'Webhook verify token' }
    ]
  },
  {
    type: 'whatsapp',
    name: 'WhatsApp Business',
    description: 'Connect WhatsApp Business API for messaging',
    icon: '💬',
    fields: [
      { key: 'phone_number_id', label: 'Phone Number ID', type: 'text', required: true, placeholder: 'WhatsApp Phone Number ID' },
      { key: 'access_token', label: 'Access Token', type: 'password', required: true, placeholder: 'WhatsApp Access Token' },
      { key: 'app_secret', label: 'App Secret', type: 'password', required: true, placeholder: 'WhatsApp App Secret' },
      { key: 'verify_token', label: 'Verify Token', type: 'text', required: true, placeholder: 'Webhook verify token' }
    ]
  },
  {
    type: 'slack',
    name: 'Slack',
    description: 'Connect Slack workspace for team notifications',
    icon: '💼',
    fields: [
      { key: 'bot_token', label: 'Bot Token', type: 'password', required: true, placeholder: 'xoxb-...' },
      { key: 'signing_secret', label: 'Signing Secret', type: 'password', required: true, placeholder: 'Slack signing secret' },
      { key: 'channel', label: 'Default Channel', type: 'text', required: false, placeholder: '#general' }
    ]
  },
  {
    type: 'email',
    name: 'Email',
    description: 'Connect email service for inbound email processing',
    icon: '📧',
    fields: [
      { key: 'provider', label: 'Provider', type: 'text', required: true, placeholder: 'sendgrid, mailgun, etc.' },
      { key: 'api_key', label: 'API Key', type: 'password', required: true, placeholder: 'Email service API key' },
      { key: 'webhook_secret', label: 'Webhook Secret', type: 'password', required: false, placeholder: 'Optional webhook secret' }
    ]
  }
]

export default function IntegrationManager({ company }: IntegrationManagerProps) {
  const [selectedIntegration, setSelectedIntegration] = useState<IntegrationType | null>(null)
  const [isConfiguring, setIsConfiguring] = useState(false)
  const queryClient = useQueryClient()

  const { data: integrations, isLoading } = useQuery({
    queryKey: ['company-integrations', company.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('company_integrations')
        .select('*')
        .eq('company_id', company.id)
        .order('created_at', { ascending: false })
      
      if (error) throw error
      return data as CompanyIntegration[]
    }
  })

  const createIntegrationMutation = useMutation({
    mutationFn: async (integrationData: {
      integration_type: string
      integration_name: string
      credentials: Record<string, any>
      settings: Record<string, any>
    }) => {
      const { data, error } = await supabase
        .from('company_integrations')
        .insert({
          company_id: company.id,
          ...integrationData,
          webhook_secret: integrationData.credentials.webhook_secret || integrationData.credentials.verify_token,
          is_active: true,
          sync_status: 'pending'
        })
        .select()
        .single()

      if (error) throw error
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-integrations', company.id] })
      setIsConfiguring(false)
      setSelectedIntegration(null)
    }
  })

  const toggleIntegrationMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const { data, error } = await supabase
        .from('company_integrations')
        .update({ is_active, sync_status: is_active ? 'pending' : 'disabled' })
        .eq('id', id)
        .select()
        .single()

      if (error) throw error
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-integrations', company.id] })
    }
  })

  const deleteIntegrationMutation = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase
        .from('company_integrations')
        .delete()
        .eq('id', id)

      if (error) throw error
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-integrations', company.id] })
    }
  })

  const getStatusBadgeColor = (status: string) => {
    const colors = {
      active: 'bg-green-100 text-green-800',
      pending: 'bg-yellow-100 text-yellow-800',
      error: 'bg-red-100 text-red-800',
      disabled: 'bg-gray-100 text-gray-800'
    }
    return colors[status as keyof typeof colors] || colors.disabled
  }

  const getWebhookUrl = (integrationType: string) => {
    const baseUrl = window.location.origin.replace('localhost:5173', 'localhost:8000') // Dev adjustment
    return `${baseUrl}/webhook/${integrationType}?company_id=${company.id}`
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Integrations</h2>
          <p className="text-gray-600">Connect external services to automate your workflows</p>
        </div>
        <Button
          onClick={() => setIsConfiguring(true)}
          className="bg-blue-600 hover:bg-blue-700"
        >
          Add Integration
        </Button>
      </div>

      {/* Existing Integrations */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {integrations?.map((integration) => {
          const integrationType = AVAILABLE_INTEGRATIONS.find(t => t.type === integration.integration_type)
          
          return (
            <Card key={integration.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl">{integrationType?.icon || '🔗'}</span>
                    <div>
                      <CardTitle className="text-lg">{integration.integration_name}</CardTitle>
                      <CardDescription>{integrationType?.name || integration.integration_type}</CardDescription>
                    </div>
                  </div>
                  <Badge className={getStatusBadgeColor(integration.sync_status)}>
                    {integration.sync_status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {integration.error_message && (
                    <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                      {integration.error_message}
                    </div>
                  )}
                  
                  <div className="text-sm text-gray-600">
                    <p>Created: {new Date(integration.created_at).toLocaleDateString()}</p>
                    {integration.last_sync_at && (
                      <p>Last sync: {new Date(integration.last_sync_at).toLocaleDateString()}</p>
                    )}
                  </div>

                  <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                    <p className="font-medium">Webhook URL:</p>
                    <p className="break-all">{getWebhookUrl(integration.integration_type)}</p>
                  </div>

                  <div className="flex space-x-2">
                    <Button
                      size="sm"
                      variant={integration.is_active ? "outline" : "default"}
                      onClick={() => toggleIntegrationMutation.mutate({
                        id: integration.id,
                        is_active: !integration.is_active
                      })}
                      disabled={toggleIntegrationMutation.isPending}
                    >
                      {integration.is_active ? 'Disable' : 'Enable'}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        if (confirm('Are you sure you want to delete this integration?')) {
                          deleteIntegrationMutation.mutate(integration.id)
                        }
                      }}
                      disabled={deleteIntegrationMutation.isPending}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Add Integration Modal */}
      {isConfiguring && (
        <IntegrationConfigModal
          company={company}
          availableIntegrations={AVAILABLE_INTEGRATIONS}
          onSubmit={(data) => createIntegrationMutation.mutate(data)}
          onCancel={() => {
            setIsConfiguring(false)
            setSelectedIntegration(null)
          }}
          isSubmitting={createIntegrationMutation.isPending}
        />
      )}
    </div>
  )
}

interface IntegrationConfigModalProps {
  company: Company
  availableIntegrations: IntegrationType[]
  onSubmit: (data: any) => void
  onCancel: () => void
  isSubmitting: boolean
}

function IntegrationConfigModal({ 
  company, 
  availableIntegrations, 
  onSubmit, 
  onCancel, 
  isSubmitting 
}: IntegrationConfigModalProps) {
  const [selectedType, setSelectedType] = useState<IntegrationType | null>(null)
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [integrationName, setIntegrationName] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedType) return

    onSubmit({
      integration_type: selectedType.type,
      integration_name: integrationName || selectedType.name,
      credentials: formData,
      settings: {
        webhook_url: `${window.location.origin.replace('localhost:5173', 'localhost:8000')}/webhook/${selectedType.type}?company_id=${company.id}`,
        auto_respond: true,
        business_hours: {
          enabled: false,
          timezone: 'UTC',
          schedule: {}
        }
      }
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>Add Integration</CardTitle>
          <CardDescription>
            Connect a new service to {company.name}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedType ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {availableIntegrations.map((integration) => (
                <Card 
                  key={integration.type}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => setSelectedType(integration)}
                >
                  <CardHeader>
                    <div className="flex items-center space-x-3">
                      <span className="text-3xl">{integration.icon}</span>
                      <div>
                        <CardTitle className="text-lg">{integration.name}</CardTitle>
                        <CardDescription className="text-sm">
                          {integration.description}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center space-x-3 pb-4 border-b">
                <span className="text-3xl">{selectedType.icon}</span>
                <div>
                  <h3 className="text-lg font-semibold">{selectedType.name}</h3>
                  <p className="text-sm text-gray-600">{selectedType.description}</p>
                </div>
              </div>

              <div>
                <Label htmlFor="integration_name">Integration Name</Label>
                <Input
                  id="integration_name"
                  value={integrationName}
                  onChange={(e) => setIntegrationName(e.target.value)}
                  placeholder={selectedType.name}
                />
              </div>

              {selectedType.fields.map((field) => (
                <div key={field.key}>
                  <Label htmlFor={field.key}>
                    {field.label}
                    {field.required && <span className="text-red-500 ml-1">*</span>}
                  </Label>
                  {field.type === 'textarea' ? (
                    <Textarea
                      id={field.key}
                      value={formData[field.key] || ''}
                      onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                      placeholder={field.placeholder}
                      required={field.required}
                    />
                  ) : (
                    <Input
                      id={field.key}
                      type={field.type}
                      value={formData[field.key] || ''}
                      onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                      placeholder={field.placeholder}
                      required={field.required}
                    />
                  )}
                  {field.description && (
                    <p className="text-xs text-gray-500 mt-1">{field.description}</p>
                  )}
                </div>
              ))}

              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Webhook Configuration</h4>
                <p className="text-sm text-blue-800 mb-2">
                  Use this URL in your {selectedType.name} webhook configuration:
                </p>
                <code className="text-xs bg-blue-100 p-2 rounded block break-all">
                  {`${window.location.origin.replace('localhost:5173', 'localhost:8000')}/webhook/${selectedType.type}?company_id=${company.id}`}
                </code>
              </div>

              <div className="flex space-x-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setSelectedType(null)}
                  disabled={isSubmitting}
                  className="flex-1"
                >
                  Back
                </Button>
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
                  {isSubmitting ? 'Creating...' : 'Create Integration'}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}