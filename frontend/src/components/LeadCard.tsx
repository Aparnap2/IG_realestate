import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

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
}

interface LeadCardProps {
  lead: Lead
}

export function LeadCard({ lead }: LeadCardProps) {
  const getChannelBadge = (channel: string) => {
    switch (channel) {
      case 'ig':
        return <Badge variant="secondary">Instagram</Badge>
      case ' ':
        return <Badge variant="secondary"> </Badge>
      default:
        return <Badge variant="secondary">{channel}</Badge>
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'new':
        return <Badge variant="outline">New</Badge>
      case 'qualified':
        return <Badge variant="default">Qualified</Badge>
      case 'scheduled':
        return <Badge variant="default">Scheduled</Badge>
      case 'booked':
        return <Badge variant="default">Booked</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getScoreBadge = (score: number | null) => {
    if (score === null) return <Badge variant="outline">Not Scored</Badge>
    
    if (score > 0.7) {
      return <Badge variant="default">High ({score})</Badge>
    } else if (score > 0.4) {
      return <Badge variant="secondary">Medium ({score})</Badge>
    } else {
      return <Badge variant="outline">Low ({score})</Badge>
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">
            {lead.name || lead.user_id}
          </CardTitle>
          <div className="flex gap-2">
            {getChannelBadge(lead.channel)}
            {getStatusBadge(lead.status)}
            {getScoreBadge(lead.qualified_score)}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-gray-500 mb-2">{lead.message}</p>
        
        <div className="grid grid-cols-2 gap-2 text-sm">
          {lead.budget && (
            <div>
              <span className="font-medium">Budget:</span> ${lead.budget.toLocaleString()}
            </div>
          )}
          
          {lead.location && (
            <div>
              <span className="font-medium">Location:</span> {lead.location}
            </div>
          )}
          
          {lead.property_type && (
            <div>
              <span className="font-medium">Property:</span> {lead.property_type}
            </div>
          )}
          
          {lead.timeline && (
            <div>
              <span className="font-medium">Timeline:</span> {lead.timeline}
            </div>
          )}
          
          {lead.email && (
            <div>
              <span className="font-medium">Email:</span> {lead.email}
            </div>
          )}
          
          {lead.meeting_slot && (
            <div>
              <span className="font-medium">Meeting:</span> {new Date(lead.meeting_slot).toLocaleString()}
            </div>
          )}
        </div>
        
        <div className="mt-2 text-xs text-gray-400">
          {new Date(lead.created_at).toLocaleString()}
        </div>
      </CardContent>
    </Card>
  )
}