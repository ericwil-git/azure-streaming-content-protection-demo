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
}

// Modules will be added here:
// - Log Analytics + Sentinel
// - Event Hub
// - Storage Account (video origin)
// - CDN / Front Door
// - Function App (auth service)
// - Container Instances (load generators - multi-region)

output resourceGroupName string = rg.name
output resourceGroupId string = rg.id
