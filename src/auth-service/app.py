"""Flask wrapper for Azure Functions app running in container"""
import os
import json
import uuid
import hashlib
import jwt as pyjwt
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from azure.data.tables import TableServiceClient
from azure.eventhub import EventHubProducerClient, EventData
from azure.identity import DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient

app = Flask(__name__)

# Configuration
STORAGE_ACCOUNT = os.environ.get("STORAGE_ACCOUNT_NAME", "stscpdemormalmdf22xfvm")
EVENT_HUB_NAMESPACE = os.environ.get("EVENT_HUB_NAMESPACE", "evhns-scp-demo-rmalmdf22xfvm")
EVENT_HUB_NAME = os.environ.get("EVENT_HUB_NAME", "streaming-events")
JWT_SECRET = os.environ.get("JWT_SECRET", "demo-secret-change-in-production")

# Log Analytics configuration
DCE_ENDPOINT = os.environ.get("DCE_ENDPOINT", "https://dce-scp-demo-rmalmdf22xfvm.centralus-1.ingest.monitor.azure.com")
DCR_IMMUTABLE_ID = os.environ.get("DCR_IMMUTABLE_ID", "")
STREAM_NAME = os.environ.get("STREAM_NAME", "Custom-StreamingEvents_CL")

# Azure clients - lazy initialization
_credential = None
_sessions_table = None
_producer = None
_logs_client = None

def get_credential():
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential

def get_sessions_table():
    global _sessions_table
    if _sessions_table is None:
        table_endpoint = f"https://{STORAGE_ACCOUNT}.table.core.windows.net"
        table_client = TableServiceClient(endpoint=table_endpoint, credential=get_credential())
        _sessions_table = table_client.get_table_client("sessions")
    return _sessions_table

def get_producer():
    global _producer
    if _producer is None:
        eventhub_fqdn = f"{EVENT_HUB_NAMESPACE}.servicebus.windows.net"
        _producer = EventHubProducerClient(
            fully_qualified_namespace=eventhub_fqdn,
            eventhub_name=EVENT_HUB_NAME,
            credential=get_credential()
        )
    return _producer

def get_logs_client():
    global _logs_client
    if _logs_client is None and DCE_ENDPOINT and DCR_IMMUTABLE_ID:
        _logs_client = LogsIngestionClient(endpoint=DCE_ENDPOINT, credential=get_credential())
    return _logs_client

# Demo users
DEMO_USERS = {f"user{i:03d}": {"tier": "premium" if i % 5 == 0 else "basic", 
                               "max_streams": 4 if i % 5 == 0 else 2} 
              for i in range(1, 101)}
DEMO_USERS["user042"] = {"tier": "basic", "max_streams": 2, "test_scenario": "credential_sharing"}
DEMO_USERS["user077"] = {"tier": "basic", "max_streams": 2, "test_scenario": "concurrent_abuse"}
DEMO_USERS["pirate001"] = {"tier": "blocked", "max_streams": 0, "blacklisted": True}

def send_event(event_type, data):
    """Send event to Event Hub and optionally Log Analytics."""
    now = datetime.now(timezone.utc)
    event_data = {"event_type": event_type, "timestamp": now.isoformat(), **data}
    
    # Send to Event Hub
    try:
        producer = get_producer()
        batch = producer.create_batch()
        batch.add(EventData(json.dumps(event_data)))
        producer.send_batch(batch)
    except Exception as e:
        print(f"Event Hub send failed: {e}")
    
    # Send to Log Analytics (if configured)
    try:
        logs_client = get_logs_client()
        if logs_client and DCR_IMMUTABLE_ID:
            log_entry = {
                "TimeGenerated": now.isoformat(),
                "EventType": event_type,
                "UserId": data.get("user_id", ""),
                "SessionId": data.get("session_id", ""),
                "ClientIP": data.get("client_ip", ""),
                "ClientRegion": data.get("region", ""),
                "DeviceFingerprint": data.get("device", ""),
                "ContentId": data.get("content_id", ""),
                "Status": "success",
                "MaxStreams": data.get("max_streams", 0),
                "Tier": data.get("tier", ""),
                "Reason": data.get("reason", ""),
            }
            logs_client.upload(rule_id=DCR_IMMUTABLE_ID, stream_name=STREAM_NAME, logs=[log_entry])
    except Exception as e:
        print(f"Log Analytics send failed: {e}")

def generate_device_fingerprint(request):
    ua = request.headers.get("User-Agent", "")
    return hashlib.sha256(ua.encode()).hexdigest()[:16]

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "auth-service", "version": "1.0.0"})

@app.route("/auth/token", methods=["POST"])
def issue_token():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    region = data.get("region", "unknown")
    
    if not user_id or user_id not in DEMO_USERS:
        return jsonify({"error": "Invalid user"}), 401
    
    user = DEMO_USERS[user_id]
    if user.get("blacklisted"):
        send_event("token_denied", {"user_id": user_id, "reason": "blacklisted"})
        return jsonify({"error": "Access denied"}), 403
    
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    device_fp = generate_device_fingerprint(request)
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0]
    
    token_payload = {
        "sub": user_id, "sid": session_id, "iat": now.timestamp(),
        "exp": (now + timedelta(hours=4)).timestamp(), "region": region,
        "device": device_fp, "tier": user["tier"], "max_streams": user["max_streams"], "ip": client_ip
    }
    token = pyjwt.encode(token_payload, JWT_SECRET, algorithm="HS256")
    
    try:
        sessions_table = get_sessions_table()
        sessions_table.upsert_entity({
            "PartitionKey": user_id, "RowKey": session_id, "region": region,
            "device_fingerprint": device_fp, "client_ip": client_ip, "created_at": now.isoformat(),
            "status": "active", "tier": user["tier"], "max_streams": user["max_streams"]
        })
    except Exception as e:
        print(f"Session store failed: {e}")
    
    send_event("token_issued", {
        "user_id": user_id, "session_id": session_id, 
        "region": region, "client_ip": client_ip,
        "device": device_fp, "tier": user["tier"], "max_streams": user["max_streams"]
    })
    
    return jsonify({"token": token, "session_id": session_id, "expires_in": 14400})

@app.route("/auth/validate", methods=["POST"])
def validate_token():
    data = request.get_json() or {}
    token = data.get("token")
    content_id = data.get("content_id", "live-stream-001")
    
    if not token:
        return jsonify({"valid": False, "error": "No token"}), 400
    
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "Invalid token"}), 401
    
    user_id, session_id = payload["sub"], payload["sid"]
    
    try:
        sessions_table = get_sessions_table()
        session = sessions_table.get_entity(user_id, session_id)
        if session.get("status") == "revoked":
            send_event("token_rejected", {"user_id": user_id, "session_id": session_id, "reason": "revoked"})
            return jsonify({"valid": False, "error": "Session revoked"}), 401
    except Exception as e:
        print(f"Session check failed: {e}")
    
    send_event("stream_heartbeat", {
        "user_id": user_id, "session_id": session_id, "content_id": content_id,
        "region": payload.get("region"), "device": payload.get("device"),
        "tier": payload.get("tier"), "max_streams": payload.get("max_streams")
    })
    return jsonify({"valid": True, "user_id": user_id, "session_id": session_id, "tier": payload.get("tier")})

@app.route("/auth/revoke", methods=["POST"])
def revoke_session():
    data = request.get_json() or {}
    user_id, session_id = data.get("user_id"), data.get("session_id")
    
    if not user_id or not session_id:
        return jsonify({"error": "Missing user_id or session_id"}), 400
    
    try:
        sessions_table = get_sessions_table()
        session = sessions_table.get_entity(user_id, session_id)
        session["status"] = "revoked"
        session["revoked_at"] = datetime.now(timezone.utc).isoformat()
        session["revoke_reason"] = data.get("reason", "manual")
        sessions_table.update_entity(session)
        send_event("session_revoked", {"user_id": user_id, "session_id": session_id, "reason": data.get("reason")})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/auth/sessions/<user_id>")
def list_sessions(user_id):
    try:
        sessions_table = get_sessions_table()
        sessions = list(sessions_table.query_entities(f"PartitionKey eq '{user_id}'"))
        return jsonify({"user_id": user_id, "sessions": [
            {"session_id": s["RowKey"], "region": s.get("region"), "status": s.get("status"),
             "created_at": s.get("created_at"), "client_ip": s.get("client_ip")} for s in sessions
        ]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
