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
}

export function ConfigForm({ keyName, initialValue, label, description }: ConfigFormProps) {
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

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor={keyName}>{label}</Label>
        {description && <p className="text-sm text-gray-500">{description}</p>}
        <Textarea
          id={keyName}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={4}
        />
      </div>
      
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {success && <div className="text-green-500 text-sm">Configuration updated successfully!</div>}
      
      <Button type="submit" disabled={loading}>
        {loading ? 'Saving...' : 'Save Configuration'}
      </Button>
    </form>
  )
}