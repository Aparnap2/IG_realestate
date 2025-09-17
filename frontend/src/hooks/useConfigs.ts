import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'

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