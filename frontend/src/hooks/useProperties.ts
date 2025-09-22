import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabaseClient'
import { useEffect } from 'react'

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

  // Subscribe to real-time changes
  useEffect(() => {
    const channel = supabase
      .channel('properties-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'properties',
        },
        (payload) => {
          queryClient.setQueryData(['properties'], (old: Property[] | undefined) => [
            payload.new as Property,
            ...(old || []),
          ])
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'properties',
        },
        (payload) => {
          queryClient.setQueryData(['properties'], (old: Property[] | undefined) =>
            (old || []).map((property) =>
              property.id === payload.new.id ? (payload.new as Property) : property
            )
          )
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'DELETE',
          schema: 'public',
          table: 'properties',
        },
        (payload) => {
          queryClient.setQueryData(['properties'], (old: Property[] | undefined) =>
            (old || []).filter((property) => property.id !== payload.old.id)
          )
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [queryClient])

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