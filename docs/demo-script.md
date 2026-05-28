# Demo Script

## Setup (Before Demo)

1. Ensure all infrastructure is deployed
2. Start load generators with "normal" scenario
3. Open Sentinel dashboard in browser
4. Have Auth Service logs visible (optional)

## Demo Flow (15 minutes)

### Act 1: The Platform (2 min)

**Say:** "This is a live streaming platform - similar to what major sports leagues use. We have users around the world watching content right now."

**Show:**
- Dashboard with world map of active streams
- Normal traffic metrics (users, sessions, bandwidth)
- "Everything looks healthy"

---

### Act 2: The Attack (3 min)

**Say:** "Now let's simulate what happens when credentials are compromised. User 'user042' is a legitimate subscriber in New York. But someone in Europe just obtained their credentials..."

**Action:** Trigger credential sharing scenario

**Show:**
- Second stream appears from different region
- Both streams active simultaneously

**Say:** "In a traditional system, this would go unnoticed. The pirate gets free access, the legitimate user might not even know."

---

### Act 3: Detection (3 min)

**Say:** "Watch what happens in Sentinel..."

**Show:**
- Alert fires within 30-60 seconds
- Highlight the detection rule: "Same user streaming from NYC and London simultaneously - that's physically impossible"
- Show the evidence: IPs, regions, timestamps

**Say:** "The AI has already correlated these signals and determined this is credential sharing with high confidence."

---

### Act 4: Automated Response (3 min)

**Say:** "Now the magic happens. Our playbook automatically takes action..."

**Show:**
- Logic App execution starting
- Auth Service receiving revoke call
- Session being terminated

**Say:** "The unauthorized session is killed. The pirate sees this..."

**Show:** (if possible)
- Player error on the "pirate" client
- Or load generator logs showing blocked response

**Say:** "The legitimate user in New York is unaffected - only the suspicious session was terminated."

---

### Act 5: Evidence Trail (2 min)

**Say:** "Everything is logged for compliance and legal action."

**Show:**
- Full audit trail in Sentinel
- Incident details: who, what, when, where
- Response actions taken

**Say:** "If this were a serial pirate operation, we now have evidence for legal proceedings."

---

### Act 6: Scale & Flexibility (2 min)

**Say:** "This same system handles:"

- **Concurrent stream abuse** - Demo: user exceeds their plan limit
- **Geo-blocking** - Demo: access from blackout region blocked
- **Token attacks** - Explain token replay detection

**Say:** "All using Azure-native services - Sentinel, Logic Apps, Functions - integrated with your existing security operations."

---

## Closing

**Say:** "Questions? We can also discuss how this integrates with your existing DRM and watermarking solutions for complete coverage."

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Alert doesn't fire | Check Event Hub ingestion, verify rule is enabled |
| Playbook doesn't run | Check Logic App permissions to Sentinel |
| Load generator not sending | Verify Container Instance is running |
