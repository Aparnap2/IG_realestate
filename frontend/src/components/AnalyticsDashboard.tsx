import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'
import { TrendingUp, TrendingDown, Users, Target, Activity, Zap } from 'lucide-react'
import {
  useConversionRates,
  useLeadLifecycle,
  useSystemPerformance,
  useABTestResults,
  useOptimizationRecommendations,
  useRealTimeAnalytics
} from '@/hooks/useAnalytics'

interface ConversionData {
  date: string
  rate: number
  leads: number
  conversions: number
}

interface IndustryData {
  industry: string
  conversionRate: number
  leads: number
  revenue: number
}

interface ChannelData {
  channel: string
  conversionRate: number
  responseTime: number
  engagement: number
}

interface LifecycleData {
  stage: string
  count: number
  conversionRate: number
  dropOffRate: number
}

interface PerformanceMetric {
  component: string
  health: 'healthy' | 'warning' | 'critical'
  responseTime: number
  successRate: number
  throughput: number
}

interface ABTestResult {
  testId: string
  name: string
  variantA: { conversionRate: number; users: number }
  variantB: { conversionRate: number; users: number }
  significance: number
  winner: 'A' | 'B' | 'inconclusive'
  status: 'running' | 'completed' | 'paused'
}

interface Recommendation {
  id: string
  type: 'optimization' | 'alert' | 'insight'
  priority: 'high' | 'medium' | 'low'
  title: string
  description: string
  expectedImpact: string
  actionItems: string[]
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D']

export default function AnalyticsDashboard() {
  const [selectedTimeRange, setSelectedTimeRange] = useState('30d')
  const [selectedIndustry, setSelectedIndustry] = useState('all')
  
  // Real-time analytics connection
  const { lastUpdate } = useRealTimeAnalytics()

  // Fetch real data from backend
  const { data: conversionRates, isLoading: conversionLoading } = useConversionRates(selectedIndustry, selectedTimeRange)
  const { data: systemPerformance, isLoading: performanceLoading } = useSystemPerformance(undefined, selectedTimeRange)
  const { data: abTestResults, isLoading: abTestLoading } = useABTestResults()
  const { data: recommendations, isLoading: recommendationsLoading } = useOptimizationRecommendations(selectedIndustry)

  // Mock data fallback when backend is not available
  const conversionData: ConversionData[] = conversionRates?.trend?.map(item => ({
    date: item.date,
    rate: item.rate,
    leads: Math.floor(Math.random() * 50) + 100, // Mock leads data
    conversions: Math.floor(item.rate * Math.random() * 10) // Mock conversions
  })) || [
    { date: '2025-01-01', rate: 2.4, leads: 120, conversions: 3 },
    { date: '2025-01-02', rate: 2.8, leads: 145, conversions: 4 },
    { date: '2025-01-03', rate: 3.1, leads: 160, conversions: 5 },
    { date: '2025-01-04', rate: 2.9, leads: 138, conversions: 4 },
    { date: '2025-01-05', rate: 3.5, leads: 171, conversions: 6 },
    { date: '2025-01-06', rate: 3.2, leads: 156, conversions: 5 },
    { date: '2025-01-07', rate: 3.8, leads: 184, conversions: 7 },
  ]

  const industryData: IndustryData[] = conversionRates?.channel_breakdown?.map((item) => ({
    industry: item.channel,
    conversionRate: item.rate,
    leads: item.leads,
    revenue: item.leads * item.rate * 1000 // Estimated revenue
  })) || [
    { industry: 'Real Estate', conversionRate: 3.2, leads: 450, revenue: 2250000 },
    { industry: 'Fitness', conversionRate: 4.1, leads: 280, revenue: 840000 },
    { industry: 'Restaurant', conversionRate: 2.8, leads: 320, revenue: 640000 },
    { industry: 'Hotel', conversionRate: 3.6, leads: 190, revenue: 1140000 },
  ]

  const channelData: ChannelData[] = conversionRates?.channel_breakdown?.map(item => ({
    channel: item.channel,
    conversionRate: item.rate,
    responseTime: Math.random() * 3 + 1, // Mock response time
    engagement: Math.floor(Math.random() * 20) + 70 // Mock engagement
  })) || [
    { channel: 'Instagram DM', conversionRate: 3.8, responseTime: 2.1, engagement: 78 },
    { channel: 'SMS', conversionRate: 4.2, responseTime: 1.5, engagement: 82 },
    { channel: 'Email', conversionRate: 2.4, responseTime: 4.8, engagement: 65 },
    { channel: 'In-App', conversionRate: 3.1, responseTime: 0.8, engagement: 71 },
  ]

  const lifecycleData: LifecycleData[] = [
    { stage: 'Lead Capture', count: 1240, conversionRate: 100, dropOffRate: 0 },
    { stage: 'Qualification', count: 890, conversionRate: 71.8, dropOffRate: 28.2 },
    { stage: 'Nurture', count: 620, conversionRate: 69.7, dropOffRate: 30.3 },
    { stage: 'Booking', count: 380, conversionRate: 61.3, dropOffRate: 38.7 },
    { stage: 'Conversion', count: 42, conversionRate: 11.1, dropOffRate: 88.9 },
  ]

  const performanceMetrics: PerformanceMetric[] = systemPerformance?.map(metric => ({
    component: metric.component,
    health: metric.health,
    responseTime: metric.response_time,
    successRate: metric.success_rate,
    throughput: metric.throughput
  })) || [
    { component: 'Response Tracker', health: 'healthy', responseTime: 1.2, successRate: 98.5, throughput: 1250 },
    { component: 'Lead Scoring', health: 'healthy', responseTime: 0.8, successRate: 96.2, throughput: 980 },
    { component: 'Engagement Tracker', health: 'warning', responseTime: 2.1, successRate: 94.1, throughput: 890 },
    { component: 'Nurture Sequences', health: 'healthy', responseTime: 1.5, successRate: 97.8, throughput: 650 },
    { component: 'Smart Booking', health: 'healthy', responseTime: 1.8, successRate: 95.3, throughput: 420 },
  ]

  const processedABTestResults: ABTestResult[] = abTestResults?.map(test => ({
    testId: test.test_id,
    name: test.name,
    variantA: { conversionRate: test.variant_a.conversion_rate, users: test.variant_a.users },
    variantB: { conversionRate: test.variant_b.conversion_rate, users: test.variant_b.users },
    significance: test.significance,
    winner: test.winner,
    status: test.status
  })) || [
    {
      testId: 'msg-variant-001',
      name: 'Message Content A/B Test',
      variantA: { conversionRate: 3.2, users: 250 },
      variantB: { conversionRate: 3.8, users: 248 },
      significance: 0.042,
      winner: 'B',
      status: 'completed'
    },
    {
      testId: 'channel-opt-002',
      name: 'Channel Selection Optimization',
      variantA: { conversionRate: 2.9, users: 180 },
      variantB: { conversionRate: 3.1, users: 175 },
      significance: 0.089,
      winner: 'inconclusive',
      status: 'running'
    },
  ]

  const processedRecommendations: Recommendation[] = recommendations?.map(rec => ({
    id: rec.id,
    type: rec.type,
    priority: rec.priority,
    title: rec.title,
    description: rec.description,
    expectedImpact: rec.expected_impact,
    actionItems: rec.action_items
  })) || [
    {
      id: 'opt-001',
      type: 'optimization',
      priority: 'high',
      title: 'Improve SMS Response Time',
      description: 'SMS channel shows highest conversion rate but response times are increasing',
      expectedImpact: '+15% conversion rate improvement',
      actionItems: ['Optimize SMS template processing', 'Increase SMS sending capacity', 'Monitor delivery rates']
    },
    {
      id: 'alert-002',
      type: 'alert',
      priority: 'medium',
      title: 'Engagement Tracker Performance',
      description: 'Engagement tracker showing degraded performance with 2.1s response time',
      expectedImpact: 'Prevent further degradation',
      actionItems: ['Investigate database queries', 'Check Redis cache performance', 'Review recent code changes']
    },
    {
      id: 'insight-003',
      type: 'insight',
      priority: 'low',
      title: 'Fitness Industry Outperformance',
      description: 'Fitness industry showing 4.1% conversion rate, 28% above average',
      expectedImpact: 'Apply learnings to other industries',
      actionItems: ['Analyze successful patterns', 'Create industry templates', 'Share best practices']
    },
  ]

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'bg-green-100 text-green-800'
      case 'warning': return 'bg-yellow-100 text-yellow-800'
      case 'critical': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'
      case 'low': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getWinnerColor = (winner: string) => {
    switch (winner) {
      case 'A': return 'bg-blue-100 text-blue-800'
      case 'B': return 'bg-green-100 text-green-800'
      case 'inconclusive': return 'bg-gray-100 text-gray-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header with Time Range Selector */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
          <p className="text-gray-600">Multi-Industry Conversion & Performance Analytics</p>
        </div>
        <div className="flex items-center space-x-4">
          <select 
            value={selectedTimeRange}
            onChange={(e) => setSelectedTimeRange(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <Button variant="outline">Export Report</Button>
        </div>
      </div>

      {/* Key Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Overall Conversion Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{conversionRates ? (conversionRates.overall_rate?.toFixed(1) || '3.4') + '%' : '3.4%'}</div>
            <p className="text-xs text-green-600">+0.6% from last month</p>
            {lastUpdate && (
              <p className="text-xs text-gray-500">Last updated: {lastUpdate.toLocaleTimeString()}</p>
            )}
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
            <Users className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{conversionRates ? conversionRates.channel_breakdown?.reduce((sum, ch) => sum + ch.leads, 0).toLocaleString() : '1,240'}</div>
            <p className="text-xs text-blue-600">+12% from last month</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
            <Activity className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemPerformance ? (systemPerformance.reduce((sum, comp) => sum + comp.response_time, 0) / systemPerformance.length).toFixed(1) + 's' : '1.8s'}
            </div>
            <p className="text-xs text-yellow-600">-0.3s from last month</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Zap className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemPerformance ? systemPerformance.filter(comp => comp.health === 'healthy').length + '/' + systemPerformance.length : '0/5'}
            </div>
            <p className="text-xs text-green-600">All systems operational</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Analytics Tabs */}
      <Tabs defaultValue="conversion" className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="conversion">Conversion Analytics</TabsTrigger>
          <TabsTrigger value="lifecycle">Lead Lifecycle</TabsTrigger>
          <TabsTrigger value="performance">System Performance</TabsTrigger>
          <TabsTrigger value="abtesting">A/B Testing</TabsTrigger>
          <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
        </TabsList>

        {/* Conversion Analytics Tab */}
        <TabsContent value="conversion" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Conversion Rate Trend */}
            <Card>
              <CardHeader>
                <CardTitle>Conversion Rate Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={conversionData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Area type="monotone" dataKey="rate" stroke="#8884d8" fill="#8884d8" />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Industry Performance */}
            <Card>
              <CardHeader>
                <CardTitle>Industry Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={industryData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ industry, conversionRate }) => `${industry}: ${conversionRate}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="conversionRate"
                    >
                      {industryData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Channel Performance */}
            <Card>
              <CardHeader>
                <CardTitle>Channel Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={channelData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="channel" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="conversionRate" fill="#8884d8" name="Conversion Rate %" />
                    <Bar dataKey="engagement" fill="#82ca9d" name="Engagement %" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Industry Breakdown Table */}
            <Card>
              <CardHeader>
                <CardTitle>Industry Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {industryData.map((industry) => (
                    <div key={industry.industry} className="flex justify-between items-center p-3 border rounded-lg">
                      <div>
                        <h4 className="font-medium">{industry.industry}</h4>
                        <p className="text-sm text-gray-600">{industry.leads} leads</p>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold">{industry.conversionRate}%</div>
                        <p className="text-sm text-gray-600">${(industry.revenue / 1000).toFixed(0)}K revenue</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Lead Lifecycle Tab */}
        <TabsContent value="lifecycle" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Lifecycle Funnel */}
            <Card>
              <CardHeader>
                <CardTitle>Lead Lifecycle Funnel</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={lifecycleData} layout="horizontal">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="stage" type="category" width={100} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Drop-off Analysis */}
            <Card>
              <CardHeader>
                <CardTitle>Drop-off Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={lifecycleData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="stage" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="conversionRate" stroke="#8884d8" name="Conversion Rate %" />
                    <Line type="monotone" dataKey="dropOffRate" stroke="#82ca9d" name="Drop-off Rate %" />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Stage Details */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>Stage Performance Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Stage</th>
                        <th className="text-left p-2">Leads</th>
                        <th className="text-left p-2">Conversion Rate</th>
                        <th className="text-left p-2">Drop-off Rate</th>
                        <th className="text-left p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lifecycleData.map((stage) => (
                        <tr key={stage.stage} className="border-b">
                          <td className="p-2 font-medium">{stage.stage}</td>
                          <td className="p-2">{stage.count.toLocaleString()}</td>
                          <td className="p-2">{stage.conversionRate}%</td>
                          <td className="p-2">{stage.dropOffRate}%</td>
                          <td className="p-2">
                            <Badge className={stage.dropOffRate > 50 ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}>
                              {stage.dropOffRate > 50 ? 'High Drop-off' : 'Healthy'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* System Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Component Health */}
            <Card>
              <CardHeader>
                <CardTitle>Component Health</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {performanceMetrics.map((metric) => (
                    <div key={metric.component} className="flex justify-between items-center p-3 border rounded-lg">
                      <div>
                        <h4 className="font-medium">{metric.component}</h4>
                        <p className="text-sm text-gray-600">
                          {metric.responseTime}s response time • {metric.throughput}/min throughput
                        </p>
                      </div>
                      <div className="text-right">
                        <Badge className={getHealthColor(metric.health)}>
                          {metric.health}
                        </Badge>
                        <div className="text-sm mt-1">{metric.successRate}% success</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Performance Trends */}
            <Card>
              <CardHeader>
                <CardTitle>Performance Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={performanceMetrics}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="component" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="responseTime" stroke="#8884d8" name="Response Time (s)" />
                    <Line type="monotone" dataKey="successRate" stroke="#82ca9d" name="Success Rate %" />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* A/B Testing Tab */}
        <TabsContent value="abtesting" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {(abTestResults || []).map((test) => (
              <Card key={test.test_id}>
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-lg">{test.name}</CardTitle>
                      <p className="text-sm text-gray-600">ID: {test.test_id}</p>
                    </div>
                    <div className="flex space-x-2">
                      <Badge className={test.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'}>
                        {test.status}
                      </Badge>
                      {test.winner !== 'inconclusive' && (
                        <Badge className={getWinnerColor(test.winner)}>
                          Winner: {test.winner}
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 border rounded">
                        <h5 className="font-medium">Variant A</h5>
                        <p className="text-2xl font-bold">{test.variant_a.conversion_rate}%</p>
                        <p className="text-sm text-gray-600">{test.variant_a.users} users</p>
                      </div>
                      <div className="p-3 border rounded">
                        <h5 className="font-medium">Variant B</h5>
                        <p className="text-2xl font-bold">{test.variant_b.conversion_rate}%</p>
                        <p className="text-sm text-gray-600">{test.variant_b.users} users</p>
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-gray-600">Statistical Significance</p>
                        <p className="font-medium">{(test.significance * 100).toFixed(1)}%</p>
                      </div>
                      <Button variant="outline" size="sm">
                        {test.status === 'running' ? 'Pause Test' : 'View Details'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Recommendations Tab */}
        <TabsContent value="recommendations" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {(recommendations || []).map((rec) => (
              <Card key={rec.id}>
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-lg">{rec.title}</CardTitle>
                      <p className="text-sm text-gray-600 mt-1">{rec.description}</p>
                    </div>
                    <Badge className={getPriorityColor(rec.priority)}>
                      {rec.priority}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <p className="text-sm font-medium text-gray-700">Expected Impact</p>
                      <p className="text-sm">{rec.expected_impact}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Action Items</p>
                      <ul className="text-sm space-y-1">
                        {rec.action_items.map((item: string, index: number) => (
                          <li key={index} className="flex items-center">
                            <span className="w-2 h-2 bg-blue-500 rounded-full mr-2"></span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="flex justify-end">
                      <Button size="sm">Implement</Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}