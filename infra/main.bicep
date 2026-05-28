// Azure Streaming Content Protection Demo
// Main deployment template
targetScope = 'subscription'

@description('Primary deployment region')
param location string = 'centralus'

@description('Environment name')
param environment string = 'demo'

@description('Resource name prefix')
param prefix string = 'scp'

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${prefix}-${environment}'
  location: location
  tags: {
    project: 'streaming-content-protection'
    environment: environment
  }
}

// Deploy all resources into the resource group
module resources 'modules/resources.bicep' = {
  name: 'resources-deployment'
  scope: rg
  params: {
    location: location
    prefix: prefix
    environment: environment
  }
}

output resourceGroupName string = rg.name
output logAnalyticsWorkspaceId string = resources.outputs.logAnalyticsWorkspaceId
output eventHubNamespace string = resources.outputs.eventHubNamespace
output storageAccountName string = resources.outputs.storageAccountName
output functionAppName string = resources.outputs.functionAppName
