import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'
import { useEffect } from 'react'

export interface Lead {
  id: string
  user_id: string
  channel: string
  message: string
  qualified_score: number | null
  budget: number | null
  location: string | null
  property_type: string | null
  timeline: string | null
  name: string | null
  email: string | null
  meeting_slot: string | null
  status: string
  created_at: string
  history: Array<{message: string, timestamp: string, agent: string}> | null
}

export const useLeads = () => {
  const queryClient = useQueryClient()

  // TEMPORARY MOCK DATA FOR TESTING - Remove in production
  const mockLeads = [
    {
      id: 'mock-1',
      user_id: 'ig-user-123',
      channel: 'ig',
      message: 'Looking for a 3 bedroom house in Miami under $400k',
      qualified_score: 0.85,
      budget: 400000,
      location: 'Miami',
      property_type: '3BHK',
      timeline: '2-3 months',
      name: 'John Smith',
      email: 'john@example.com',
      meeting_slot: null,
      status: 'qualified' as const,
      created_at: '2025-10-13T10:30:00Z',
      history: [
        {message: 'Initial contact via Instagram', timestamp: '2025-10-13T10:30:00Z', agent: 'router'},
        {message: 'Qualified lead - high budget, clear requirements', timestamp: '2025-10-13T10:35:00Z', agent: 'qualifier'}
      ]
    },
    {
      id: 'mock-2',
      user_id: 'ig-user-456',
      channel: 'ig',
      message: 'Just browsing for investment properties',
      qualified_score: 0.3,
      budget: null,
      location: 'Fort Lauderdale',
      property_type: 'Condo',
      timeline: '6+ months',
      name: 'Sarah Johnson',
      email: 'sarah@example.com',
      meeting_slot: null,
      status: 'new' as const,
      created_at: '2025-10-13T09:15:00Z',
      history: [
        {message: 'Initial contact via Instagram', timestamp: '2025-10-13T09:15:00Z', agent: 'router'}
      ]
    },
    {
      id: 'mock-3',
      user_id: 'ig-user-789',
      channel: 'ig',
      message: 'Need a 2BHK apartment near downtown Miami, urgent',
      qualified_score: 0.7,
      budget: 350000,
      location: 'Miami',
      property_type: '2BHK',
      timeline: 'ASAP',
      name: 'Mike Davis',
      email: 'mike@example.com',
      meeting_slot: '2025-10-14T14:00:00Z',
      status: 'scheduled' as const,
      created_at: '2025-10-13T08:45:00Z',
      history: [
        {message: 'Initial contact via Instagram', timestamp: '2025-10-13T08:45:00Z', agent: 'router'},
        {message: 'Qualified lead - high urgency', timestamp: '2025-10-13T08:50:00Z', agent: 'qualifier'},
        {message: 'Tour scheduled for tomorrow at 2PM', timestamp: '2025-10-13T09:20:00Z', agent: 'scheduler'}
      ]
    }
  ];

  const { data: leads, isLoading, error } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => {
      // TEMPORARY: Return mock data - connect to real database in production
      await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
      return mockLeads;
      
      /* UNCOMMENT WHEN DATABASE IS READY
      const { data, error } = await supabase
        .from('leads')
        .select('*')
        .order('created_at', { ascending: false })

      if (error) throw error
      return data as Lead[]
      */
    }
  })

  // Subscribe to real-time changes
  useEffect(() => {
    const channel = supabase
      .channel('leads-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'leads',
        },
        (payload) => {
          queryClient.setQueryData(['leads'], (old: Lead[] | undefined) => [
            payload.new as Lead,
            ...(old || []),
          ])
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'leads',
        },
        (payload) => {
          queryClient.setQueryData(['leads'], (old: Lead[] | undefined) =>
            (old || []).map((lead) =>
              lead.id === payload.new.id ? (payload.new as Lead) : lead
            )
          )
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'DELETE',
          schema: 'public',
          table: 'leads',
        },
        (payload) => {
          queryClient.setQueryData(['leads'], (old: Lead[] | undefined) =>
            (old || []).filter((lead) => lead.id !== payload.old.id)
          )
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [queryClient])

  return { leads: leads || [], isLoading, error }
}