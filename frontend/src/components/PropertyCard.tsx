import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface Property {
  id: string
  price: number
  location: string
  property_type: string
  amenities: Record<string, any> | null
  details: Record<string, any> | null
}

interface PropertyCardProps {
  property: Property
  onEdit?: (property: Property) => void
  onDelete?: (id: string) => void
}

export function PropertyCard({ property, onEdit, onDelete }: PropertyCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle>
            {property.property_type} in {property.location}
          </CardTitle>
          <Badge variant="secondary">${property.price.toLocaleString()}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {property.amenities && (
          <div className="mb-2">
            <h4 className="font-medium text-sm mb-1">Amenities</h4>
            <p className="text-sm text-gray-500">
              {Object.entries(property.amenities)
                .map(([key, value]) => `${key}: ${value}`)
                .join(", ")}
            </p>
          </div>
        )}
        
        {property.details && (
          <div>
            <h4 className="font-medium text-sm mb-1">Details</h4>
            <p className="text-sm text-gray-500">
              {Object.entries(property.details)
                .map(([key, value]) => `${key}: ${value}`)
                .join(", ")}
            </p>
          </div>
        )}
        
        <div className="flex justify-end space-x-2 mt-4">
          {onEdit && (
            <button
              onClick={() => onEdit(property)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Edit
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(property.id)}
              className="text-sm text-red-600 hover:text-red-800"
            >
              Delete
            </button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}