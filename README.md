# Azure Streaming Content Protection Demo

A demonstration environment showcasing AI-powered detection and automated response to streaming content piracy using Microsoft Azure.

## Overview

This demo simulates a live streaming platform with security monitoring that can detect and respond to:

- **Credential Sharing** - Same account streaming from multiple geographic locations
- **Concurrent Stream Abuse** - Users exceeding their allowed stream limit
- **Token Replay Attacks** - Stolen/shared tokens used from suspicious IPs
- **Geo-blocking Violations** - Access attempts from blackout regions
- **Anomalous Behavior** - Bot-like scraping or unusual access patterns

## Architecture

```

  Load Generators (Multi-Region)                                         
  East  West  Australia                                      Europe US 

                         
            {                 echo ___BEGIN___COMMAND_OUTPUT_MARKER___;                 PS1="";PS2="";unset HISTFILE;                 EC=$?;                 echo "___BEGIN___COMMAND_DONE_MARKER___$EC";             }
              
 Token validation, Geo-IP   Azure Front  Door                
              
                         
          
            {                 echo ___BEGIN___COMMAND_OUTPUT_MARKER___;                 PS1="";PS2="";unset HISTFILE;                 EC=$?;                 echo "___BEGIN___COMMAND_DONE_MARKER___$EC";             }                             
           
    Video Origin   Auth            Service   
  (  (Blob + CDN)   Azure            Func)   
           
         
  All events         
            {                 echo ___BEGIN___COMMAND_OUTPUT_MARKER___;                 PS1="";PS2="";unset HISTFILE;                 EC=$?;                 echo "___BEGIN___COMMAND_DONE_MARKER___$EC";             }

 Microsoft Sentinel                        
                                                                         
  Analytics Rules:              Automated Response:                      
 Geo-anomaly  Revoke token                          detection         
 Concurrency  Block session                         violation         
 Token abuse  Alert SOC dashboard                   patterns          

```

## Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Auth Service | Azure Functions (Python) | JWT token issuance, session tracking, revocation API |
| Video Origin | Azure Blob + FFMPEG | HLS/DASH segments with ClearKey encryption |
| CDN | Azure Front Door | Tokenized delivery, geo-fencing, access logs |
| Telemetry | Event Hub + Log Analytics | Real-time event ingestion |
| Detection | Microsoft Sentinel | KQL analytics rules for threat detection |
| Response | Logic Apps | Automated playbooks for enforcement |
| Load Generator | Azure Container Instances | Multi-region traffic simulation |

## Quick Start

### Prerequisites

- Azure subscription with Sentinel-capable features
- Azure CLI authenticated
- GitHub CLI (for CI/CD)

### Deploy

```bash
# Deploy infrastructure
az deployment sub create \
  --location eastus \
  --template-file infra/main.bicep \
  --parameters infra/parameters/demo.bicepparam

# Deploy applications
# (via GitHub Actions or manual)
```

## Demo Scenarios

1. **Normal Traffic** - Baseline of legitimate users streaming content
2. **Credential Sharing Attack** - User streams from NYC and London simultaneously
3. **Concurrent Abuse** - User exceeds 3-stream limit
4. **Bot Scraping** - Rapid automated requests detected and blocked

## Project Status


- [ ] Infrastructure (Bicep)
- [ ] Auth Service
- [ ] Load Generator
- [ ] Sentinel Rules
- [ ] Response Playbooks
- [ ] Demo Dashboard

## License

MIT
