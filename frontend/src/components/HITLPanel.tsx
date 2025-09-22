import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'

interface HITLLead {
  id: string
  user_id: string
  channel: string
  message: string
  qualified_score?: number
  budget?: number
  location?: string
  property_type?: string
  status: string
  created_at: string
}

export default function HITLPanel() {
  const [selectedLead, setSelectedLead] = useState<HITLLead | null>(null)
  const [feedback, setFeedback] = useState('')
  const queryClient = useQueryClient()

  const { data: pendingLeads, isLoading } = useQuery({
    queryKey: ['pending-leads'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('leads')
        .select('*')
        .eq('status', 'interrupted')
        .order('created_at', { ascending: false })
      
      if (error) throw error
      return data as HITLLead[]
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const reviewMutation = useMutation({
    mutationFn: async ({ leadId, action, feedback }: { leadId: string, action: string, feedback: string }) => {
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/hitl/human/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lead_id: leadId,
          action,
          feedback,
        }),
      })
      
      if (!response.ok) {
        throw new Error('Failed to review lead')
      }
      
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-leads'] })
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setSelectedLead(null)
      setFeedback('')
    },
  })

  const handleReview = (action: 'approve' | 'reject') => {
    if (!selectedLead) return
    
    reviewMutation.mutate({
      leadId: selectedLead.id,
      action,
      feedback: feedback || `Lead ${action}d by admin`,
    })
  }

  if (isLoading) {
    return (
      <div className="mt-8 bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Human-in-the-Loop Review
          </h3>
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="h-20 bg-gray-100 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!pendingLeads || pendingLeads.length === 0) {
    return (
      <div className="mt-8 bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Human-in-the-Loop Review
          </h3>
          <div className="text-center py-8">
            <div className="text-green-600 mb-2">✓</div>
            <p className="text-gray-500">No leads pending review</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-8 bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
          Human-in-the-Loop Review
          <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            {pendingLeads.length} pending
          </span>
        </h3>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Pending Leads List */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Pending Leads</h4>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {pendingLeads.map((lead) => (
                <div
                  key={lead.id}
                  className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                    selectedLead?.id === lead.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedLead(lead)}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="text-sm font-medium text-gray-900">
                      {lead.user_id}
                    </div>
                    <div className="flex space-x-2">
                      {lead.budget && lead.budget > 500000 && (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                          High Value
                        </span>
                      )}
                      {lead.qualified_score && lead.qualified_score > 0.9 && (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                          High Score
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 mb-2 truncate">
                    {lead.message}
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>
                      {lead.budget && `$${lead.budget.toLocaleString()}`}
                      {lead.location && ` • ${lead.location}`}
                      {lead.property_type && ` • ${lead.property_type}`}
                    </span>
                    <span>Score: {lead.qualified_score?.toFixed(2) || 'N/A'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Review Panel */}
          <div>
            {selectedLead ? (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-3">Review Lead</h4>
                <div className="bg-gray-50 p-4 rounded-lg mb-4">
                  <div className="space-y-2 text-sm">
                    <div><strong>User:</strong> {selectedLead.user_id}</div>
                    <div><strong>Channel:</strong> {selectedLead.channel}</div>
                    <div><strong>Message:</strong> {selectedLead.message}</div>
                    {selectedLead.budget && <div><strong>Budget:</strong> ${selectedLead.budget.toLocaleString()}</div>}
                    {selectedLead.location && <div><strong>Location:</strong> {selectedLead.location}</div>}
                    {selectedLead.property_type && <div><strong>Type:</strong> {selectedLead.property_type}</div>}
                    <div><strong>Score:</strong> {selectedLead.qualified_score?.toFixed(2) || 'N/A'}</div>
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Feedback (optional)
                  </label>
                  <textarea
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="Add your review comments..."
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                  />
                </div>

                <div className="flex space-x-3">
                  <button
                    onClick={() => handleReview('approve')}
                    disabled={reviewMutation.isPending}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50"
                  >
                    {reviewMutation.isPending ? 'Processing...' : 'Approve'}
                  </button>
                  <button
                    onClick={() => handleReview('reject')}
                    disabled={reviewMutation.isPending}
                    className="flex-1 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50"
                  >
                    {reviewMutation.isPending ? 'Processing...' : 'Reject'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Select a lead to review
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
