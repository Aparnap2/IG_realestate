import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'

interface Property {
  id: string
  price: number
  location: string
  property_type: string
  amenities: Record<string, any> | null
  details: Record<string, any> | null
}

export const useProperties = () => {
  const queryClient = useQueryClient()

  const { data: properties, isLoading, error } = useQuery({
    queryKey: ['properties'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('properties')
        .select('*')
        .order('location')

      if (error) throw error
      return data as Property[]
    }
  })

  const addPropertyMutation = useMutation({
    mutationFn: async (property: Omit<Property, 'id'>) => {
      const { data, error } = await supabase
        .from('properties')
        .insert(property)
        .select()

      if (error) throw error
      return data as Property[]
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    }
  })

  const updatePropertyMutation = useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<Property> }) => {
      const { data, error } = await supabase
        .from('properties')
        .update(updates)
        .eq('id', id)
        .select()

      if (error) throw error
      return data as Property[]
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    }
  })

  const deletePropertyMutation = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase.from('properties').delete().eq('id', id)
      if (error) throw error
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['properties'] })
    }
  })

  return {
    properties: properties || [],
    isLoading,
    error,
    addProperty: addPropertyMutation.mutateAsync,
    updateProperty: updatePropertyMutation.mutateAsync,
    deleteProperty: deletePropertyMutation.mutateAsync
  }
}