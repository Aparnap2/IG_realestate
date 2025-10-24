import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Company } from '../lib/supabase'

interface Conversation {
  id: string
  user_id: string
  instagram_id: string
  name?: string
  email?: string
  status: string
  qualified_score?: number
  last_dm_sent?: string
  dm_count?: number
  response_count?: number
  hubspot_contact_id?: string
  hubspot_deal_id?: string
  calendar_event_id?: string
  meeting_link?: string
  created_at: string
  updated_at: string
}

interface Message {
  id: string
  lead_id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface AdminConversationsProps {
  company: Company
}

export default function AdminConversations({ company }: AdminConversationsProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadConversations()
  }, [company.id, filter])

  useEffect(() => {
    if (selectedConversation) {
      loadMessages(selectedConversation.id)
    }
  }, [selectedConversation])

  const loadConversations = async () => {
    try {
      setLoading(true)
      let query = supabase
        .from('leads')
        .select('*')
        .eq('channel', 'instagram')
        .order('updated_at', { ascending: false })
        .limit(100)

      // Apply filters
      if (filter === 'qualified') {
        query = query.gte('qualified_score', 0.75)
      } else if (filter === 'nurturing') {
        query = query.lt('qualified_score', 0.75).gte('qualified_score', 0.4)
      } else if (filter === 'disqualified') {
        query = query.lt('qualified_score', 0.4)
      } else if (filter === 'booked') {
        query = query.not('calendar_event_id', 'is', null)
      }

      const { data, error } = await query

      if (error) throw error
      setConversations(data || [])
    } catch (error) {
      console.error('Error loading conversations:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMessages = async (leadId: string) => {
    try {
      setMessagesLoading(true)
      const { data, error } = await supabase
        .from('messages')
        .select('*')
        .eq('lead_id', leadId)
        .order('timestamp', { ascending: true })

      if (error) throw error
      setMessages(data || [])
    } catch (error) {
      console.error('Error loading messages:', error)
    } finally {
      setMessagesLoading(false)
    }
  }

  const getStatusColor = (status: string, score?: number) => {
    if (status === 'booked') return 'bg-green-100 text-green-800'
    if (status === 'scheduled') return 'bg-blue-100 text-blue-800'
    if (score && score >= 0.75) return 'bg-purple-100 text-purple-800'
    if (score && score >= 0.4) return 'bg-yellow-100 text-yellow-800'
    return 'bg-red-100 text-red-800'
  }

  const getStatusText = (conversation: Conversation) => {
    if (conversation.calendar_event_id) return 'Booked'
    if (conversation.status === 'scheduled') return 'Scheduled'
    if (conversation.qualified_score && conversation.qualified_score >= 0.75) return 'Qualified'
    if (conversation.qualified_score && conversation.qualified_score >= 0.4) return 'Nurturing'
    return 'Disqualified'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Conversations</h1>
          <p className="text-gray-600 mt-2">Monitor and manage Instagram DM conversations</p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Conversations</option>
            <option value="qualified">Qualified</option>
            <option value="nurturing">Nurturing</option>
            <option value="disqualified">Disqualified</option>
            <option value="booked">Booked</option>
          </select>
          <div className="text-sm text-gray-500">
            {conversations.length} conversations
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Conversations List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-md">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Recent Conversations</h2>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  onClick={() => setSelectedConversation(conversation)}
                  className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 ${
                    selectedConversation?.id === conversation.id ? 'bg-blue-50 border-blue-200' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <h3 className="text-sm font-medium text-gray-900 truncate">
                          {conversation.name || `User ${conversation.instagram_id.slice(-4)}`}
                        </h3>
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(conversation.status, conversation.qualified_score)}`}>
                          {getStatusText(conversation)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mb-1">
                        {conversation.email || 'No email'}
                      </p>
                      <div className="flex items-center space-x-3 text-xs text-gray-400">
                        <span>{conversation.dm_count || 0} DMs</span>
                        <span>{conversation.response_count || 0} responses</span>
                        {conversation.qualified_score && (
                          <span>Score: {(conversation.qualified_score * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mt-2">
                    {new Date(conversation.updated_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Conversation Details */}
        <div className="lg:col-span-2">
          {selectedConversation ? (
            <div className="bg-white rounded-lg shadow-md">
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">
                      {selectedConversation.name || `User ${selectedConversation.instagram_id.slice(-4)}`}
                    </h2>
                    <p className="text-sm text-gray-600">
                      Instagram ID: {selectedConversation.instagram_id}
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`inline-flex px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(selectedConversation.status, selectedConversation.qualified_score)}`}>
                      {getStatusText(selectedConversation)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Conversation Stats */}
              <div className="p-4 border-b border-gray-200 bg-gray-50">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{selectedConversation.dm_count || 0}</div>
                    <div className="text-xs text-gray-600">DMs Sent</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{selectedConversation.response_count || 0}</div>
                    <div className="text-xs text-gray-600">Responses</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {selectedConversation.qualified_score ? (selectedConversation.qualified_score * 100).toFixed(0) : 0}%
                    </div>
                    <div className="text-xs text-gray-600">Qualification</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600">
                      {selectedConversation.calendar_event_id ? 'Yes' : 'No'}
                    </div>
                    <div className="text-xs text-gray-600">Booked</div>
                  </div>
                </div>

                {/* Integration Status */}
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Integrations</h3>
                  <div className="flex items-center space-x-4 text-sm">
                    <span className={selectedConversation.hubspot_contact_id ? 'text-green-600' : 'text-gray-400'}>
                      HubSpot: {selectedConversation.hubspot_contact_id ? 'Connected' : 'Not Connected'}
                    </span>
                    <span className={selectedConversation.calendar_event_id ? 'text-green-600' : 'text-gray-400'}>
                      Calendar: {selectedConversation.calendar_event_id ? 'Booked' : 'Not Booked'}
                    </span>
                    {selectedConversation.meeting_link && (
                      <a href={selectedConversation.meeting_link} target="_blank" rel="noopener noreferrer"
                         className="text-blue-600 hover:text-blue-800">
                        Meeting Link
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="p-4">
                <h3 className="text-lg font-semibold mb-4">Conversation History</h3>
                {messagesLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No messages yet
                  </div>
                ) : (
                  <div className="space-y-4 max-h-96 overflow-y-auto">
                    {messages.map((message) => (
                      <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-start' : 'justify-end'}`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                            message.role === 'user'
                              ? 'bg-gray-100 text-gray-900'
                              : 'bg-blue-600 text-white'
                          }`}
                        >
                          <p className="text-sm">{message.content}</p>
                          <p className="text-xs mt-1 opacity-70">
                            {new Date(message.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-md p-8 text-center">
              <div className="text-gray-400 mb-4">
                <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Conversation</h3>
              <p className="text-gray-600">Choose a conversation from the list to view details and message history.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}