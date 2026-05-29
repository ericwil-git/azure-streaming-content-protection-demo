# Streaming Content Protection Demo - Walkthrough

## Prerequisites

- Access to Azure Portal (FDPO tenant)
- Browser with Sentinel access
- Terminal for running load generators

## Key URLs

| Component | URL |
|-----------|-----|
| Auth Service | https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io |
| Sentinel | https://portal.azure.com/#view/Microsoft_Azure_Security_Insights/MainMenuBlade/~/Overview/id/%2Fsubscriptions%2Fa80ade45-139e-4ad0-855f-374b089cdbd9%2Fresourcegroups%2Frg-scp-demo%2Fproviders%2Fmicrosoft.operationalinsights%2Fworkspaces%2Flog-scp-demo |
| GitHub Repo | https://github.com/ericwil-git/azure-streaming-content-protection-demo |

## Demo Flow (15 minutes)

### 1. Introduction (2 min)

"Today I'll demonstrate how Azure Sentinel can detect and automatically respond to streaming content piracy - specifically credential sharing and concurrent stream abuse."

Show the architecture diagram:
- Load generators in 3 regions simulating users
- Auth service validating streaming tokens
 Log Analytics
- Sentinel detecting anomalies and auto-revoking sessions

### 2. Show Normal Operation (2 min)

```bash
# Health check
curl https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/health

# Issue a token
curl -X POST https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user001", "region": "eastus"}'
```

### 3. Trigger Credential Sharing (3 min)

"Now let's simulate credential sharing - the same user logging in from multiple geographic regions."

```bash
# User042 logs in from East US
curl -X POST https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user042", "region": "eastus"}'

# Same user from West Europe (different continent!)
curl -X POST https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user042", "region": "westeurope"}'

# Check sessions - now in 2 regions
curl https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/auth/sessions/user042
```

### 4. Show Sentinel Detection (3 min)

 Credential Sharing Detected

Show the KQL query detecting users in 2+ regions within 5 minutes.

"The system detected user042 streaming from both the US and Europe simultaneously - physically impossible without credential sharing."

### 5. Show Automated Response (3 min)

 Playbooks

"When this detection fires, our Logic App automatically:
1. Retrieves all active sessions for the user
2. Revokes each session via the auth service API
3. Adds a comment to the incident"

Show the revoked sessions:
```bash
curl https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io/auth/sessions/user042
```

### 6. Business Value Summary (2 min)

- **Detection Time**: Seconds, not hours
- **Response Time**: Automated, not manual
- **Revenue Protection**: Every shared credential is lost revenue
- **Scalable**: Works for millions of concurrent users
- **All Azure**: No third-party licensing required

## Demo Reset

To reset the demo state:
```bash
# Clean up load generator containers
az container delete -g rg-scp-demo -n aci-loadgen-eastus --yes
az container delete -g rg-scp-demo -n aci-loadgen-westeurope --yes
az container delete -g rg-scp-demo -n aci-loadgen-australiaeast --yes
```
