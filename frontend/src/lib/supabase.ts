import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Missing Supabase environment variables:', { supabaseUrl: !!supabaseUrl, supabaseAnonKey: !!supabaseAnonKey })
  throw new Error('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Database types for TypeScript
export interface Company {
  id: string
  name: string
  slug: string
  industry: string
  settings: {
    branding?: {
      logo_url?: string
      primary_color?: string
      secondary_color?: string
    }
    features?: {
      hitl_enabled?: boolean
      analytics_enabled?: boolean
      custom_workflows?: boolean
    }
    limits?: {
      max_leads_per_month?: number
      max_integrations?: number
      max_users?: number
    }
  }
  subscription_tier: 'starter' | 'professional' | 'enterprise'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CompanyUser {
  id: string
  company_id: string
  user_id: string
  role: 'owner' | 'admin' | 'member' | 'viewer'
  permissions: {
    leads?: { read: boolean; write: boolean; delete: boolean }
    integrations?: { read: boolean; write: boolean; delete: boolean }
    workflows?: { read: boolean; write: boolean; delete: boolean }
    settings?: { read: boolean; write: boolean; delete: boolean }
  }
  invited_by?: string
  invited_at: string
  joined_at?: string
  is_active: boolean
  created_at: string
}

export interface CompanyIntegration {
  id: string
  company_id: string
  integration_type: string
  integration_name: string
  credentials: Record<string, any>
  settings: {
    webhook_url?: string
    auto_respond?: boolean
    business_hours?: {
      enabled: boolean
      timezone: string
      schedule: Record<string, any>
    }
  }
  webhook_secret?: string
  is_active: boolean
  last_sync_at?: string
  sync_status: 'pending' | 'active' | 'error' | 'disabled'
  error_message?: string
  created_at: string
  updated_at: string
}

export interface Workflow {
  id: string
  company_id: string
  name: string
  description?: string
  trigger_type: 'webhook' | 'schedule' | 'manual' | 'event'
  trigger_config: {
    conditions: any[]
    filters: Record<string, any>
  }
  agents_config: {
    agents: any[]
    edges: any[]
    settings: Record<string, any>
  }
  industry_template?: string
  is_active: boolean
  version: number
  created_by?: string
  last_run_at?: string
  run_count: number
  success_rate: number
  created_at: string
  updated_at: string
}

export interface Lead {
  id: string
  company_id: string
  user_id: string
  channel: string
  message: string
  qualified_score?: number
  budget?: number
  location?: string
  property_type?: string
  timeline?: string
  name?: string
  email?: string
  meeting_slot?: string
  status: 'new' | 'qualified' | 'scheduled' | 'booked' | 'interrupted' | 'approved' | 'rejected'
  history: Array<{
    message: string
    timestamp: string
    agent: string
    details?: string
  }>
  created_at: string
}

export interface Property {
  id: string
  company_id: string
  price: number
  location: string
  property_type: string
  amenities: Record<string, any>
  details: Record<string, any>
  created_at: string
}

export interface Config {
  key: string
  value: string
  company_id: string
  created_at: string
  updated_at: string
}