import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const backendUrl = import.meta.env.VITE_BACKEND_URL

interface ConversionRatesResponse {
  industry_type: string
  overall_rate: number
  channel_breakdown: {
    channel: string
    rate: number
    leads: number
  }[]
  time_to_conversion: {
    average_days: number
    distribution: {
      range: string
      count: number
    }[]
  }
  trend: {
    date: string
    rate: number
  }[]
}

interface LeadLifecycleResponse {
  user_id: string
  journey_stages: {
    stage: string
    start_time: string
    end_time: string
    duration_hours: number
  }[]
  qualification_progression: {
    score: number
    timestamp: string
  }[]
  engagement_events: {
    event_type: string
    timestamp: string
    channel: string
  }[]
  conversion_events: {
    event_type: string
    timestamp: string
    value: number
  }[]
}

interface SystemPerformanceResponse {
  component: string
  health: 'healthy' | 'warning' | 'critical'
  response_time: number
  success_rate: number
  throughput: number
  error_rate: number
  uptime: number
  last_updated: string
}

interface ABTestResultResponse {
  test_id: string
  name: string
  status: 'running' | 'completed' | 'paused'
  variant_a: {
    conversion_rate: number
    users: number
    confidence: number
  }
  variant_b: {
    conversion_rate: number
    users: number
    confidence: number
  }
  significance: number
  winner: 'A' | 'B' | 'inconclusive'
  start_date: string
  end_date?: string
}

interface OptimizationRecommendationResponse {
  id: string
  type: 'optimization' | 'alert' | 'insight'
  priority: 'high' | 'medium' | 'low'
  title: string
  description: string
  expected_impact: string
  action_items: string[]
  industry_type?: string
  component?: string
  created_at: string
}

// Hook for conversion rates analytics
export function useConversionRates(industryType: string = 'all', dateRange: string = '30d') {
  return useQuery({
    queryKey: ['analytics', 'conversion-rates', industryType, dateRange],
    queryFn: async (): Promise<ConversionRatesResponse> => {
      const response = await fetch(
        `${backendUrl}/api/analytics/conversion-rates?industry_type=${industryType}&date_range=${dateRange}`
      )
      if (!response.ok) {
        throw new Error('Failed to fetch conversion rates')
      }
      return response.json()
    },
    enabled: !!backendUrl,
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  })
}

// Hook for lead lifecycle analysis
export function useLeadLifecycle(userId: string) {
  return useQuery({
    queryKey: ['analytics', 'lead-lifecycle', userId],
    queryFn: async (): Promise<LeadLifecycleResponse> => {
      const response = await fetch(
        `${backendUrl}/api/analytics/lead-lifecycle?user_id=${userId}`
      )
      if (!response.ok) {
        throw new Error('Failed to fetch lead lifecycle')
      }
      return response.json()
    },
    enabled: !!backendUrl && !!userId,
  })
}

// Hook for system performance metrics
export function useSystemPerformance(component?: string, dateRange: string = '24h') {
  return useQuery({
    queryKey: ['analytics', 'system-performance', component, dateRange],
    queryFn: async (): Promise<SystemPerformanceResponse[]> => {
      const url = new URL(`${backendUrl}/api/analytics/system-performance`)
      if (component) url.searchParams.set('component', component)
      url.searchParams.set('date_range', dateRange)
      
      const response = await fetch(url.toString())
      if (!response.ok) {
        throw new Error('Failed to fetch system performance')
      }
      return response.json()
    },
    enabled: !!backendUrl,
    refetchInterval: 60 * 1000, // Refetch every minute for real-time monitoring
  })
}

// Hook for A/B testing results
export function useABTestResults(testId?: string) {
  return useQuery({
    queryKey: ['analytics', 'ab-tests', testId],
    queryFn: async (): Promise<ABTestResultResponse[]> => {
      const url = new URL(`${backendUrl}/api/analytics/ab-tests`)
      if (testId) url.searchParams.set('test_id', testId)
      
      const response = await fetch(url.toString())
      if (!response.ok) {
        throw new Error('Failed to fetch A/B test results')
      }
      return response.json()
    },
    enabled: !!backendUrl,
    refetchInterval: 2 * 60 * 1000, // Refetch every 2 minutes
  })
}

// Hook for optimization recommendations
export function useOptimizationRecommendations(industryType?: string) {
  return useQuery({
    queryKey: ['analytics', 'recommendations', industryType],
    queryFn: async (): Promise<OptimizationRecommendationResponse[]> => {
      const url = new URL(`${backendUrl}/api/analytics/recommendations`)
      if (industryType && industryType !== 'all') {
        url.searchParams.set('industry_type', industryType)
      }
      
      const response = await fetch(url.toString())
      if (!response.ok) {
        throw new Error('Failed to fetch optimization recommendations')
      }
      return response.json()
    },
    enabled: !!backendUrl,
    refetchInterval: 10 * 60 * 1000, // Refetch every 10 minutes
  })
}

// Hook for tracking conversions
export function useTrackConversion() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: {
      user_id: string
      industry_type: string
      conversion_type: string
      value: number
      metadata?: Record<string, any>
    }) => {
      const response = await fetch(`${backendUrl}/api/analytics/track-conversion`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      
      if (!response.ok) {
        throw new Error('Failed to track conversion')
      }
      
      return response.json()
    },
    onSuccess: () => {
      // Invalidate related queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['analytics', 'conversion-rates'] })
      queryClient.invalidateQueries({ queryKey: ['analytics', 'recommendations'] })
    },
  })
}

// Hook for creating A/B tests
export function useCreateABTest() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: {
      name: string
      description: string
      variant_a: Record<string, any>
      variant_b: Record<string, any>
      traffic_split: number
      target_metric: string
    }) => {
      const response = await fetch(`${backendUrl}/api/analytics/create-ab-test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      
      if (!response.ok) {
        throw new Error('Failed to create A/B test')
      }
      
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics', 'ab-tests'] })
    },
  })
}

// Hook for pausing/resuming A/B tests
export function useUpdateABTest() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: {
      test_id: string
      action: 'pause' | 'resume' | 'stop'
    }) => {
      const response = await fetch(`${backendUrl}/api/analytics/update-ab-test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      
      if (!response.ok) {
        throw new Error('Failed to update A/B test')
      }
      
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics', 'ab-tests'] })
    },
  })
}

// Hook for dismissing recommendations
export function useDismissRecommendation() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: {
      recommendation_id: string
      reason?: string
    }) => {
      const response = await fetch(`${backendUrl}/api/analytics/dismiss-recommendation`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      
      if (!response.ok) {
        throw new Error('Failed to dismiss recommendation')
      }
      
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics', 'recommendations'] })
    },
  })
}

// Hook for real-time analytics updates (WebSocket)
export function useRealTimeAnalytics() {
  const [socket, setSocket] = useState<WebSocket | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!backendUrl) return

    const wsUrl = backendUrl.replace('http', 'ws') + '/ws/analytics'
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('Analytics WebSocket connected')
      setSocket(ws)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        // Update relevant queries based on message type
        switch (data.type) {
          case 'conversion_update':
            queryClient.invalidateQueries({ queryKey: ['analytics', 'conversion-rates'] })
            break
          case 'performance_update':
            queryClient.invalidateQueries({ queryKey: ['analytics', 'system-performance'] })
            break
          case 'ab_test_update':
            queryClient.invalidateQueries({ queryKey: ['analytics', 'ab-tests'] })
            break
          case 'recommendation_update':
            queryClient.invalidateQueries({ queryKey: ['analytics', 'recommendations'] })
            break
        }
        
        setLastUpdate(new Date())
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('Analytics WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('Analytics WebSocket disconnected')
      setSocket(null)
      
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        if (backendUrl) {
          const newWs = new WebSocket(wsUrl)
          setSocket(newWs)
        }
      }, 5000)
    }

    return () => {
      ws.close()
    }
  }, [backendUrl, queryClient])

  return { socket, lastUpdate }
}