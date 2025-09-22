import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useLeads } from '@/hooks/useLeads'

// Mock data for demonstration
const mockMetrics = {
  totalLeads: 1247,
  qualifiedLeads: 342,
  scheduledMeetings: 189,
  conversionRate: 27.4,
  avgQualificationScore: 0.72
}

export function MetricsDashboard() {
  const { leads } = useLeads()
  const [metrics, setMetrics] = useState(mockMetrics)

  useEffect(() => {
    if (leads && leads.length > 0) {
      // Calculate real metrics from leads data
      const totalLeads = leads.length
      const qualifiedLeads = leads.filter(lead => lead.qualified_score && lead.qualified_score > 0.7).length
      const scheduledMeetings = leads.filter(lead => lead.meeting_slot).length
      const conversionRate = totalLeads > 0 ? (qualifiedLeads / totalLeads * 100) : 0
      const avgQualificationScore = leads.reduce((sum, lead) => 
        sum + (lead.qualified_score || 0), 0) / totalLeads || 0
      
      setMetrics({
        totalLeads,
        qualifiedLeads,
        scheduledMeetings,
        conversionRate: parseFloat(conversionRate.toFixed(1)),
        avgQualificationScore: parseFloat(avgQualificationScore.toFixed(2))
      })
    }
  }, [leads])

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.totalLeads.toLocaleString()}</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Qualified Leads</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.qualifiedLeads.toLocaleString()}</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Scheduled Meetings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.scheduledMeetings.toLocaleString()}</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.conversionRate}%</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Avg Qual Score</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.avgQualificationScore}</div>
        </CardContent>
      </Card>
    </div>
  )
}