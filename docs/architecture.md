# Architecture Overview

## Design Principles

1. **All Microsoft/Azure** - No third-party services except open-source tools
2. **Demo-First** - Optimized for compelling demonstrations, not production scale
3. **Observable** - Every action generates telemetry for Sentinel
4. **Automated Response** - Detection triggers immediate enforcement

## Component Details

### Auth Service (Azure Functions)

**Endpoints:**
- `POST /auth/token` - Issue JWT for user
- `POST /auth/validate` - Validate token (called by CDN)
- `POST /auth/revoke` - Revoke user session
- `GET /auth/sessions/{userId}` - List active sessions

**JWT Claims:**
```json
{
  "sub": "user001",
  "sid": "session-uuid",
  "iat": 1716912000,
  "exp": 1716915600,
  "region": "eastus",
  "device": "device-fingerprint-hash",
  "tier": "premium",
  "max_streams": 4
}
```

**Session Storage:** Azure Table Storage
- Partition: userId
- Row: sessionId
- Tracks: region, IP, device, created_at, last_seen

### Load Generator

**Deployment:** Azure Container Instances (multi-region)
- East US
- West Europe  
- Australia East

**Scenarios (configurable):**
```yaml
scenarios:
  normal:
    users: 100
    streams_per_user: 1
    duration: continuous
    
  credential_sharing:
    user: "user042"
    regions: ["eastus", "westeurope"]
    simultaneous: true
    
  concurrent_abuse:
    user: "user077"
    streams: 5  # exceeds limit of 3
    
  bot_scraping:
    pattern: rapid_sequential
    requests_per_second: 50
```

### Video Origin

**Simple approach for demo:**
- Pre-packaged HLS segments in Azure Blob
- FFMPEG used offline to create test content
- ClearKey encryption (optional)

**Content:**
- Big Buck Bunny or similar CC-licensed video
- 10-second segments
- Multiple bitrates (360p, 720p, 1080p)

### Telemetry Pipeline

```
Auth Service 
               
            {                 echo ___BEGIN___COMMAND_OUTPUT_MARKER___;                 PS1="";PS2="";unset HISTFILE;                 EC=$?;                 echo "___ SentinelBEGIN___ Log Analytics COMMAND_ Event Hub DONE_MARKER___$EC";             }
               
Load Gen 
```

**Event Schema:**
```json
{
  "timestamp": "2026-05-28T12:00:00Z",
  "event_type": "stream_start|stream_end|token_issued|token_revoked",
  "user_id": "user001",
  "session_id": "uuid",
  "client_ip": "203.0.113.42",
  "client_region": "eastus",
  "device_fingerprint": "hash",
  "content_id": "live-event-001",
  "status": "success|blocked|error"
}
```

### Sentinel Detection Rules

| Rule | Logic | Severity |
|------|-------|----------|
| Credential Sharing | Same userId from 2+ regions in 5 min | High |
| Concurrent Abuse | Active sessions > max_streams | Medium |
| Token Replay | Token used from different IP than issued | High |
| Geo Violation | Request from blackout region | Medium |
| Bot Pattern | >20 requests/min from single session | Medium |

### Response Playbooks

**Auto-Response (Logic Apps):**
1. Receive Sentinel incident
2. Extract userId/sessionId from alert
3. Call Auth Service `/revoke` endpoint
4. Update incident with action taken
5. (Optional) Send Teams notification

**Manual Response:**
- Dashboard "Kill Session" button
- SOC analyst review queue
