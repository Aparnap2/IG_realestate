import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { useLeads } from '@/hooks/useLeads'
import { supabase } from '@/lib/supabaseClient'

interface HITLLead extends Lead {
  interrupt: boolean
}

export function HITLReview() {
  const { leads, isLoading } = useLeads()
  const [approvingLead, setApprovingLead] = useState<string | null>(null)
  const [feedback, setFeedback] = useState('')

  // Filter leads that need HITL review (interrupted leads)
  const hitlLeads = leads.filter((lead: any) => 
    lead.status === 'pending' && lead.interrupt
  )

  const handleApprove = async (leadId: string) => {
    setApprovingLead(leadId)
    
    try {
      // Call the backend API to approve the lead
      const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/api/human/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          thread_id: leadId,
          human_feedback: feedback
        })
      })
      
      if (!response.ok) {
        throw new Error('Failed to approve lead')
      }
      
      // Update the lead status in Supabase
      const { error } = await supabase
        .from('leads')
        .update({ 
          status: 'approved',
          interrupt: false
        })
        .eq('id', leadId)
      
      if (error) throw error
      
      setFeedback('')
      alert('Lead approved successfully!')
    } catch (err) {
      console.error('Error approving lead:', err)
      alert('Failed to approve lead. Please try again.')
    } finally {
      setApprovingLead(null)
    }
  }

  if (isLoading) {
    return <div>Loading HITL leads...</div>
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>HITL Review Queue</span>
            <Badge variant="secondary">{hitlLeads.length} pending</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {hitlLeads.length === 0 ? (
            <p className="text-muted-foreground">No leads pending HITL review.</p>
          ) : (
            <div className="space-y-4">
              {hitlLeads.map((lead: any) => (
                <Card key={lead.id}>
                  <CardContent className="pt-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <h3 className="font-semibold">Lead Details</h3>
                        <p><strong>Name:</strong> {lead.name || 'N/A'}</p>
                        <p><strong>Channel:</strong> {lead.channel}</p>
                        <p><strong>Budget:</strong> ${lead.budget?.toLocaleString() || 'N/A'}</p>
                        <p><strong>Location:</strong> {lead.location || 'N/A'}</p>
                        <p><strong>Property Type:</strong> {lead.property_type || 'N/A'}</p>
                        <p><strong>Score:</strong> {lead.qualified_score || 'N/A'}</p>
                      </div>
                      <div>
                        <h3 className="font-semibold">Message</h3>
                        <p className="text-sm text-muted-foreground">{lead.message}</p>
                        <div className="mt-4">
                          <label className="block text-sm font-medium mb-2">Human Feedback</label>
                          <Textarea
                            value={feedback}
                            onChange={(e) => setFeedback(e.target.value)}
                            placeholder="Enter your feedback for this lead..."
                            rows={3}
                          />
                        </div>
                        <div className="mt-4">
                          <Button
                            onClick={() => handleApprove(lead.id)}
                            disabled={approvingLead === lead.id}
                          >
                            {approvingLead === lead.id ? 'Approving...' : 'Approve & Resume'}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}