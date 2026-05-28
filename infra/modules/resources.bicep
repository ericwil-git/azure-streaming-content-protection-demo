// All resources for Streaming Content Protection Demo
param location string
param prefix string
param environment string

var uniqueSuffix = uniqueString(resourceGroup().id)
var workspaceName = 'log-${prefix}-${environment}'
var eventHubNamespaceName = 'evhns-${prefix}-${environment}-${uniqueSuffix}'
var eventHubName = 'streaming-events'
var storageAccountName = 'st${prefix}${environment}${uniqueSuffix}'
var functionAppName = 'func-${prefix}-${environment}-${uniqueSuffix}'
var appServicePlanName = 'asp-${prefix}-${environment}'
var appInsightsName = 'appi-${prefix}-${environment}'

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// Enable Microsoft Sentinel
resource sentinel 'Microsoft.SecurityInsights/onboardingStates@2024-03-01' = {
  name: 'default'
  scope: logAnalytics
  properties: {}
}

// Event Hub Namespace
resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: eventHubNamespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    isAutoInflateEnabled: false
  }
}

// Event Hub for streaming events
resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: eventHubName
  properties: {
    partitionCount: 4
    messageRetentionInDays: 1
  }
}

// Event Hub Authorization Rule for sending
resource eventHubSendRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2024-01-01' = {
  parent: eventHub
  name: 'send-rule'
  properties: {
    rights: ['Send']
  }
}

// Event Hub Authorization Rule for listening (for Log Analytics)
resource eventHubListenRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2024-01-01' = {
  parent: eventHub
  name: 'listen-rule'
  properties: {
    rights: ['Listen']
  }
}

// Consumer group for Log Analytics
resource consumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: eventHub
  name: 'loganalytics'
  properties: {}
}

// Storage Account - NO public blob access (use SAS tokens for CDN)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false  // Compliant with policy
    allowSharedKeyAccess: true
  }
}

// Blob Services
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    cors: {
      corsRules: [
        {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'HEAD', 'OPTIONS']
          allowedHeaders: ['*']
          exposedHeaders: ['*']
          maxAgeInSeconds: 3600
        }
      ]
    }
  }
}

// Blob container for video segments (private - use SAS)
resource videoContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'video-segments'
  properties: {
    publicAccess: 'None'
  }
}

// Table storage for session tracking
resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {}
}

resource sessionsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'sessions'
}

resource usersTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'users'
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// App Service Plan for Functions (Consumption)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true  // Linux
  }
}

// Function App for Auth Service
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'EVENT_HUB_CONNECTION_STRING'
          value: eventHubSendRule.listKeys().primaryConnectionString
        }
        {
          name: 'TABLE_STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${az.environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccount.name
        }
        {
          name: 'STORAGE_ACCOUNT_KEY'
          value: storageAccount.listKeys().keys[0].value
        }
        {
          name: 'JWT_SECRET'
          value: uniqueString(resourceGroup().id, 'jwt-secret')
        }
      ]
      cors: {
        allowedOrigins: ['*']
      }
    }
  }
}

// Data Collection Endpoint for custom logs
resource dataCollectionEndpoint 'Microsoft.Insights/dataCollectionEndpoints@2023-03-11' = {
  name: 'dce-${prefix}-${environment}'
  location: location
  properties: {
    networkAcls: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// Custom log table for streaming events
resource streamingEventsTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: logAnalytics
  name: 'StreamingEvents_CL'
  properties: {
    schema: {
      name: 'StreamingEvents_CL'
      columns: [
        { name: 'TimeGenerated', type: 'datetime' }
        { name: 'EventType', type: 'string' }
        { name: 'UserId', type: 'string' }
        { name: 'SessionId', type: 'string' }
        { name: 'ClientIP', type: 'string' }
        { name: 'ClientRegion', type: 'string' }
        { name: 'DeviceFingerprint', type: 'string' }
        { name: 'ContentId', type: 'string' }
        { name: 'Status', type: 'string' }
        { name: 'MaxStreams', type: 'int' }
        { name: 'Reason', type: 'string' }
      ]
    }
    retentionInDays: 30
    totalRetentionInDays: 30
  }
}

// Data Collection Rule for streaming events
resource dataCollectionRule 'Microsoft.Insights/dataCollectionRules@2023-03-11' = {
  name: 'dcr-${prefix}-${environment}'
  location: location
  properties: {
    dataCollectionEndpointId: dataCollectionEndpoint.id
    streamDeclarations: {
      'Custom-StreamingEvents_CL': {
        columns: [
          { name: 'TimeGenerated', type: 'datetime' }
          { name: 'EventType', type: 'string' }
          { name: 'UserId', type: 'string' }
          { name: 'SessionId', type: 'string' }
          { name: 'ClientIP', type: 'string' }
          { name: 'ClientRegion', type: 'string' }
          { name: 'DeviceFingerprint', type: 'string' }
          { name: 'ContentId', type: 'string' }
          { name: 'Status', type: 'string' }
          { name: 'MaxStreams', type: 'int' }
          { name: 'Reason', type: 'string' }
        ]
      }
    }
    destinations: {
      logAnalytics: [
        {
          workspaceResourceId: logAnalytics.id
          name: 'logAnalyticsDestination'
        }
      ]
    }
    dataFlows: [
      {
        streams: ['Custom-StreamingEvents_CL']
        destinations: ['logAnalyticsDestination']
        transformKql: 'source'
        outputStream: 'Custom-StreamingEvents_CL'
      }
    ]
  }
  dependsOn: [streamingEventsTable]
}

// Outputs
output logAnalyticsWorkspaceId string = logAnalytics.id
output logAnalyticsWorkspaceName string = logAnalytics.name
output eventHubNamespace string = eventHubNamespace.name
output eventHubName string = eventHub.name
output storageAccountName string = storageAccount.name
output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output dataCollectionEndpointUrl string = dataCollectionEndpoint.properties.logsIngestion.endpoint
output dataCollectionRuleId string = dataCollectionRule.id
