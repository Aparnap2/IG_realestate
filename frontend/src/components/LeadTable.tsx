import { Lead } from "@/hooks/useLeads"

interface LeadTableProps {
  leads: Lead[]
  loading: boolean
}

export function LeadTable({ leads, loading }: LeadTableProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
        ))}
      </div>
    )
  }

  if (leads.length === 0) {
    return <div className="text-center py-8 text-gray-500">No leads found</div>
  }

  return (
    <div className="rounded-md border">
      <table className="w-full">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Channel</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Budget</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Property</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timeline</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {leads.map((lead) => (
            <tr key={lead.id}>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{lead.name || lead.user_id}</td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                  {lead.channel}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                  {lead.status}
                </span>
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                {lead.qualified_score !== null ? lead.qualified_score.toFixed(2) : 'N/A'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">
                {lead.budget ? `$${lead.budget.toLocaleString()}` : 'N/A'}
              </td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{lead.location || 'N/A'}</td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{lead.property_type || 'N/A'}</td>
              <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-500">{lead.timeline || 'N/A'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}