import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useConfigs } from '@/hooks/useConfigs'

interface ConfigFormProps {
  keyName: string
  initialValue: string
  label: string
  description?: string
  type?: 'text' | 'number' | 'textarea'
  step?: string
  min?: string
  max?: string
}

export function ConfigForm({ 
  keyName, 
  initialValue, 
  label, 
  description,
  type = 'textarea',
  step,
  min,
  max
}: ConfigFormProps) {
  const [value, setValue] = useState(initialValue)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  
  const { updateConfig } = useConfigs()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccess(false)
    
    try {
      await updateConfig(keyName, value)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const renderInput = () => {
    switch (type) {
      case 'textarea':
        return (
          <Textarea
            id={keyName}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={4}
          />
        )
      case 'number':
        return (
          <Input
            id={keyName}
            type="number"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            step={step}
            min={min}
            max={max}
          />
        )
      default:
        return (
          <Input
            id={keyName}
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        )
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor={keyName}>{label}</Label>
        {description && <p className="text-sm text-gray-500">{description}</p>}
        {renderInput()}
      </div>
      
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {success && <div className="text-green-500 text-sm">Configuration updated successfully!</div>}
      
      <Button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save Configuration'}
      </Button>
    </form>
  )
}