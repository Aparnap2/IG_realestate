interface MetricsCardsProps {
  metrics?: {
    total: number
    qualified: number
    scheduled: number
    avgScore: number
  }
}

export default function MetricsCards({ metrics }: MetricsCardsProps) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white overflow-hidden shadow rounded-lg animate-pulse">
            <div className="p-5">
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
              <div className="h-8 bg-gray-200 rounded w-1/3"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  const cards = [
    {
      name: 'Total Leads',
      value: metrics.total,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      name: 'Qualified Leads',
      value: metrics.qualified,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      name: 'Scheduled Tours',
      value: metrics.scheduled,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      name: 'Avg Score',
      value: metrics.avgScore.toFixed(2),
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.name} className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className={`w-8 h-8 rounded-md ${card.bgColor} flex items-center justify-center`}>
                  <div className={`w-4 h-4 rounded ${card.color.replace('text-', 'bg-')}`}></div>
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    {card.name}
                  </dt>
                  <dd className={`text-lg font-medium ${card.color}`}>
                    {card.value}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
