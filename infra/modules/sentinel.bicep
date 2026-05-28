// Microsoft Sentinel deployment
// Includes: Log Analytics workspace, Sentinel solution, analytics rules

param location string
param prefix string
param environment string

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}-${environment}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Enable Sentinel
resource sentinel 'Microsoft.SecurityInsights/onboardingStates@2024-03-01' = {
  name: 'default'
  scope: logAnalytics
  properties: {}
}

output workspaceId string = logAnalytics.id
output workspaceName string = logAnalytics.name
