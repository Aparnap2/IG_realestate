import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'
import { useEffect } from 'react'

interface Config {
  key: string
  value: string
}

export const useConfigs = () => {
  const queryClient = useQueryClient()

  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['configs'],
    queryFn: async () => {
      const { data, error } = await supabase.from('configs').select('*')
      if (error) throw error
      return data as Config[]
    }
  })

  // Subscribe to real-time changes
  useEffect(() => {
    const channel = supabase
      .channel('configs-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'configs',
        },
        (payload) => {
          queryClient.setQueryData(['configs'], (old: Config[] | undefined) => [
            payload.new as Config,
            ...(old || []),
          ])
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'configs',
        },
        (payload) => {
          queryClient.setQueryData(['configs'], (old: Config[] | undefined) =>
            (old || []).map((config) =>
              config.key === payload.new.key ? (payload.new as Config) : config
            )
          )
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'DELETE',
          schema: 'public',
          table: 'configs',
        },
        (payload) => {
          queryClient.setQueryData(['configs'], (old: Config[] | undefined) =>
            (old || []).filter((config) => config.key !== payload.old.key)
          )
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [queryClient])

  const updateConfigMutation = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      const { data, error } = await supabase
        .from('configs')
        .upsert({ key, value })
        .select()

      if (error) throw error
      return data as Config[]
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configs'] })
    }
  })

  return {
    configs: configs || [],
    isLoading,
    error,
    updateConfig: updateConfigMutation.mutateAsync
  }
}