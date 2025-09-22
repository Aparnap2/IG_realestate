import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'
import { useEffect } from 'react'

interface Lead {
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

  const { data: leads, isLoading, error } = useQuery({
    queryKey: ['leads'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('leads')
        .select('*')
        .order('created_at', { ascending: false })

      if (error) throw error
      return data as Lead[]
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