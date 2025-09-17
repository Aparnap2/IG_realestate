import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useProperties } from '@/hooks/useProperties'

interface PropertyFormProps {
  property?: {
    id: string
    price: number
    location: string
    property_type: string
    amenities: Record<string, any> | null
    details: Record<string, any> | null
  }
  onSuccess?: () => void
  onCancel?: () => void
}

export function PropertyForm({ property, onSuccess, onCancel }: PropertyFormProps) {
  const [price, setPrice] = useState(property?.price?.toString() || '')
  const [location, setLocation] = useState(property?.location || '')
  const [propertyType, setPropertyType] = useState(property?.property_type || '')
  const [amenities, setAmenities] = useState(
    property?.amenities ? JSON.stringify(property.amenities, null, 2) : ''
  )
  const [details, setDetails] = useState(
    property?.details ? JSON.stringify(property.details, null, 2) : ''
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const { addProperty, updateProperty } = useProperties()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    
    try {
      // Parse JSON fields
      let parsedAmenities = null
      let parsedDetails = null
      
      if (amenities) {
        try {
          parsedAmenities = JSON.parse(amenities)
        } catch (err) {
          throw new Error('Invalid JSON in amenities field')
        }
      }
      
      if (details) {
        try {
          parsedDetails = JSON.parse(details)
        } catch (err) {
          throw new Error('Invalid JSON in details field')
        }
      }
      
      if (property) {
        // Update existing property
        await updateProperty({
          id: property.id,
          updates: {
            price: parseInt(price),
            location,
            property_type: propertyType,
            amenities: parsedAmenities,
            details: parsedDetails
          }
        })
      } else {
        // Add new property
        await addProperty({
          price: parseInt(price),
          location,
          property_type: propertyType,
          amenities: parsedAmenities,
          details: parsedDetails
        })
      }
      
      // Reset form
      setPrice('')
      setLocation('')
      setPropertyType('')
      setAmenities('')
      setDetails('')
      
      if (onSuccess) onSuccess()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="price">Price</Label>
        <Input
          id="price"
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
        />
      </div>
      
      <div>
        <Label htmlFor="location">Location</Label>
        <Input
          id="location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          required
        />
      </div>
      
      <div>
        <Label htmlFor="propertyType">Property Type</Label>
        <Input
          id="propertyType"
          value={propertyType}
          onChange={(e) => setPropertyType(e.target.value)}
          required
        />
      </div>
      
      <div>
        <Label htmlFor="amenities">Amenities (JSON)</Label>
        <Textarea
          id="amenities"
          value={amenities}
          onChange={(e) => setAmenities(e.target.value)}
          placeholder='{"pool": true, "parking": false}'
          rows={4}
        />
      </div>
      
      <div>
        <Label htmlFor="details">Details (JSON)</Label>
        <Textarea
          id="details"
          value={details}
          onChange={(e) => setDetails(e.target.value)}
          placeholder='{"sqft": 1200, "year_built": 2020}'
          rows={4}
        />
      </div>
      
      {error && <div className="text-red-500 text-sm">{error}</div>}
      
      <div className="flex space-x-2">
        <Button type="submit" disabled={loading}>
          {loading ? (property ? 'Updating...' : 'Adding...') : (property ? 'Update Property' : 'Add Property')}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}