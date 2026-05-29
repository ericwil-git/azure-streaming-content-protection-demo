#!/bin/bash
# Deploy load generators to multiple regions using Azure Container Instances

ACR_NAME="acrscpa2e257db"
ACR_SERVER="${ACR_NAME}.azurecr.io"
RESOURCE_GROUP="rg-scp-demo"
AUTH_URL="https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io"

# Regions for multi-region simulation
REGIONS=("eastus" "westeurope" "australiaeast")

# Get ACR credentials
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

echo "=== Deploying Load Generators ==="

for REGION in "${REGIONS[@]}"; do
    echo ""
    echo "Deploying to $REGION..."
    
    # Normal traffic generator
    az container create \
        --resource-group $RESOURCE_GROUP \
        --name "aci-loadgen-${REGION}-normal" \
        --image "${ACR_SERVER}/load-generator:v1" \
        --registry-login-server $ACR_SERVER \
        --registry-username $ACR_USER \
        --registry-password $ACR_PASS \
        --location $REGION \
        --os-type Linux \
        --cpu 0.5 \
        --memory 0.5 \
        --restart-policy Never \
        --environment-variables \
            AUTH_SERVICE_URL=$AUTH_URL \
            REGION=$REGION \
            SCENARIO=normal \
            INTENSITY=20 \
            DURATION=10 \
        --no-wait \
        -o none
    
    # Credential sharing generator (same user from this region)
    az container create \
        --resource-group $RESOURCE_GROUP \
        --name "aci-loadgen-${REGION}-sharing" \
        --image "${ACR_SERVER}/load-generator:v1" \
        --registry-login-server $ACR_SERVER \
        --registry-username $ACR_USER \
        --registry-password $ACR_PASS \
        --location $REGION \
        --os-type Linux \
        --cpu 0.5 \
        --memory 0.5 \
        --restart-policy Never \
        --environment-variables \
            AUTH_SERVICE_URL=$AUTH_URL \
            REGION=$REGION \
            SCENARIO=credential_sharing \
            INTENSITY=10 \
            DURATION=10 \
        --no-wait \
        -o none
    
    echo "  Deployed to $REGION"
done

echo ""
echo "=== Load generators deployed to ${#REGIONS[@]} regions ==="
echo "Run 'az container list -g $RESOURCE_GROUP -o table' to check status"
