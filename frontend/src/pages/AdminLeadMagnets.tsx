import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Company } from '../lib/supabase'

interface LeadMagnet {
  id: string
  type: string
  title: string
  description: string
  delivery_text: string
  file_url?: string
  thumbnail_url?: string
  active: boolean
  created_at: string
  updated_at: string
}

interface AdminLeadMagnetsProps {
  company: Company
}

export default function AdminLeadMagnets({ company }: AdminLeadMagnetsProps) {
  const [leadMagnets, setLeadMagnets] = useState<LeadMagnet[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [showUploadForm, setShowUploadForm] = useState(false)
  const [formData, setFormData] = useState({
    type: '',
    title: '',
    description: '',
    delivery_text: '',
    file: null as File | null,
    thumbnail: null as File | null
  })

  useEffect(() => {
    loadLeadMagnets()
  }, [company.id])

  const loadLeadMagnets = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('lead_magnets')
        .select('*')
        .eq('company_id', company.id)
        .order('created_at', { ascending: false })

      if (error) throw error
      setLeadMagnets(data || [])
    } catch (error) {
      console.error('Error loading lead magnets:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (file: File, bucket: string): Promise<string> => {
    const fileExt = file.name.split('.').pop()
    const fileName = `${Date.now()}-${Math.random().toString(36).substring(2)}.${fileExt}`
    const filePath = `${company.id}/${bucket}/${fileName}`

    const { error: uploadError } = await supabase.storage
      .from('lead-magnets')
      .upload(filePath, file)

    if (uploadError) throw uploadError

    const { data } = supabase.storage
      .from('lead-magnets')
      .getPublicUrl(filePath)

    return data.publicUrl
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setUploading(true)

    try {
      let fileUrl = ''
      let thumbnailUrl = ''

      // Upload files if provided
      if (formData.file) {
        fileUrl = await handleFileUpload(formData.file, 'files')
      }

      if (formData.thumbnail) {
        thumbnailUrl = await handleFileUpload(formData.thumbnail, 'thumbnails')
      }

      // Create lead magnet record
      const { error } = await supabase
        .from('lead_magnets')
        .insert({
          company_id: company.id,
          type: formData.type,
          title: formData.title,
          description: formData.description,
          delivery_text: formData.delivery_text,
          file_url: fileUrl || null,
          thumbnail_url: thumbnailUrl || null,
          active: true
        })

      if (error) throw error

      // Reset form and reload
      setFormData({
        type: '',
        title: '',
        description: '',
        delivery_text: '',
        file: null,
        thumbnail: null
      })
      setShowUploadForm(false)
      await loadLeadMagnets()

    } catch (error) {
      console.error('Error creating lead magnet:', error)
      alert('Error creating lead magnet. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const toggleActive = async (magnet: LeadMagnet) => {
    try {
      const { error } = await supabase
        .from('lead_magnets')
        .update({ active: !magnet.active })
        .eq('id', magnet.id)

      if (error) throw error
      await loadLeadMagnets()
    } catch (error) {
      console.error('Error updating lead magnet:', error)
    }
  }

  const deleteMagnet = async (magnet: LeadMagnet) => {
    if (!confirm('Are you sure you want to delete this lead magnet?')) return

    try {
      const { error } = await supabase
        .from('lead_magnets')
        .delete()
        .eq('id', magnet.id)

      if (error) throw error
      await loadLeadMagnets()
    } catch (error) {
      console.error('Error deleting lead magnet:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Lead Magnets</h1>
          <p className="text-gray-600 mt-2">Manage your lead magnet content and delivery</p>
        </div>
        <button
          onClick={() => setShowUploadForm(!showUploadForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          {showUploadForm ? 'Cancel' : 'Add Lead Magnet'}
        </button>
      </div>

      {showUploadForm && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Upload New Lead Magnet</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                <select
                  value={formData.type}
                  onChange={(e) => setFormData({...formData, type: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="">Select type...</option>
                  <option value="first_time_buyer_guide">First Time Buyer Guide</option>
                  <option value="market_report">Market Report</option>
                  <option value="investment_guide">Investment Guide</option>
                  <option value="neighborhood_guide">Neighborhood Guide</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Text</label>
              <textarea
                value={formData.delivery_text}
                onChange={(e) => setFormData({...formData, delivery_text: e.target.value})}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={4}
                placeholder="Text to send when delivering this lead magnet..."
                required
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">File (PDF, Video, etc.)</label>
                <input
                  type="file"
                  accept=".pdf,.mp4,.mov,.avi,.jpg,.png"
                  onChange={(e) => setFormData({...formData, file: e.target.files?.[0] || null})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Thumbnail Image</label>
                <input
                  type="file"
                  accept=".jpg,.png,.jpeg"
                  onChange={(e) => setFormData({...formData, thumbnail: e.target.files?.[0] || null})}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => setShowUploadForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={uploading}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {uploading ? 'Uploading...' : 'Create Lead Magnet'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold">Your Lead Magnets</h2>
        </div>

        {leadMagnets.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            No lead magnets yet. Create your first one to get started!
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {leadMagnets.map((magnet) => (
              <div key={magnet.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <h3 className="text-lg font-medium text-gray-900">{magnet.title}</h3>
                      <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                        magnet.active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {magnet.active ? 'Active' : 'Inactive'}
                      </span>
                      <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                        {magnet.type.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                    <p className="text-gray-600 mt-1">{magnet.description}</p>
                    <p className="text-sm text-gray-500 mt-2 font-mono bg-gray-50 p-2 rounded">
                      {magnet.delivery_text}
                    </p>
                    <div className="flex items-center space-x-4 mt-3 text-sm text-gray-500">
                      {magnet.file_url && (
                        <a href={magnet.file_url} target="_blank" rel="noopener noreferrer"
                           className="text-blue-600 hover:text-blue-800">
                          📎 View File
                        </a>
                      )}
                      {magnet.thumbnail_url && (
                        <a href={magnet.thumbnail_url} target="_blank" rel="noopener noreferrer"
                           className="text-blue-600 hover:text-blue-800">
                          🖼️ View Thumbnail
                        </a>
                      )}
                      <span>Created: {new Date(magnet.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={() => toggleActive(magnet)}
                      className={`px-3 py-1 text-sm rounded-md ${
                        magnet.active
                          ? 'bg-red-100 text-red-800 hover:bg-red-200'
                          : 'bg-green-100 text-green-800 hover:bg-green-200'
                      }`}
                    >
                      {magnet.active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => deleteMagnet(magnet)}
                      className="px-3 py-1 text-sm bg-red-100 text-red-800 rounded-md hover:bg-red-200"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}