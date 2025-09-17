import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LeadTable } from "@/components/LeadTable"
import { PropertyCard } from "@/components/PropertyCard"
import { PropertyForm } from "@/components/PropertyForm"
import { ConfigForm } from "@/components/ConfigForm"
import { useLeads } from '@/hooks/useLeads'
import { useProperties } from '@/hooks/useProperties'
import { useConfigs } from '@/hooks/useConfigs'
import { useAuth } from '@/hooks/useAuth'

export function Dashboard() {
  const { leads, isLoading: leadsLoading } = useLeads()
  const { properties, isLoading: propertiesLoading, deleteProperty } = useProperties()
  const { configs } = useConfigs()
  const { signOut } = useAuth()
  
  const [activeTab, setActiveTab] = useState("leads")
  const [editingProperty, setEditingProperty] = useState<any | null>(null)

  // Find specific configs
  const qualifierPrompt = configs.find(c => c.key === "qualifier_prompt")?.value || ""
  const schedulerPrompt = configs.find(c => c.key === "scheduler_prompt")?.value || ""
  const followupPrompt = configs.find(c => c.key === "followup_prompt")?.value || ""

  const handleEditProperty = (property: any) => {
    setEditingProperty(property)
    setActiveTab("add-property")
  }

  const handleDeleteProperty = async (id: string) => {
    if (window.confirm("Are you sure you want to delete this property?")) {
      try {
        await deleteProperty(id)
      } catch (err) {
        console.error("Failed to delete property:", err)
        alert("Failed to delete property. Please try again.")
      }
    }
  }

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Real Estate Lead Dashboard</h1>
        <Button onClick={signOut}>Sign Out</Button>
      </div>
      
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="leads">Leads</TabsTrigger>
          <TabsTrigger value="properties">Properties</TabsTrigger>
          <TabsTrigger value="add-property">
            {editingProperty ? "Edit Property" : "Add Property"}
          </TabsTrigger>
          <TabsTrigger value="configs">Configurations</TabsTrigger>
        </TabsList>
        
        <TabsContent value="leads" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Lead Pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <LeadTable leads={leads} loading={leadsLoading} />
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="properties" className="mt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {propertiesLoading ? (
              <p>Loading properties...</p>
            ) : (
              properties.map((property) => (
                <PropertyCard
                  key={property.id}
                  property={property}
                  onEdit={handleEditProperty}
                  onDelete={handleDeleteProperty}
                />
              ))
            )}
          </div>
        </TabsContent>
        
        <TabsContent value="add-property" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>
                {editingProperty ? "Edit Property" : "Add New Property"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <PropertyForm
                property={editingProperty}
                onSuccess={() => {
                  setEditingProperty(null)
                  setActiveTab("properties")
                }}
                onCancel={() => {
                  setEditingProperty(null)
                  setActiveTab("properties")
                }}
              />
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="configs" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card>
              <CardHeader>
                <CardTitle>Qualifier Prompt</CardTitle>
              </CardHeader>
              <CardContent>
                <ConfigForm
                  keyName="qualifier_prompt"
                  initialValue={qualifierPrompt}
                  label="Qualifier Agent Prompt"
                  description="Prompt used by the qualifier agent to score leads"
                />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Scheduler Prompt</CardTitle>
              </CardHeader>
              <CardContent>
                <ConfigForm
                  keyName="scheduler_prompt"
                  initialValue={schedulerPrompt}
                  label="Scheduler Agent Prompt"
                  description="Prompt used by the scheduler agent to book meetings"
                />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>FollowUp Prompt</CardTitle>
              </CardHeader>
              <CardContent>
                <ConfigForm
                  keyName="followup_prompt"
                  initialValue={followupPrompt}
                  label="FollowUp Agent Prompt"
                  description="Prompt used by the followup agent to nurture leads"
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}