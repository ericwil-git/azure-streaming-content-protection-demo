"""
Auth Service for Streaming Content Protection Demo
Handles token issuance, validation, session management, and revocation
Uses Azure Managed Identity for storage access
"""

import azure.functions as func
import jwt
import json
import uuid
import os
from datetime import datetime, timedelta, timezone
from azure.data.tables import TableServiceClient
from azure.eventhub import EventHubProducerClient, EventData
from azure.identity import DefaultAzureCredential

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "demo-secret-change-in-prod")
JWT_EXPIRY_HOURS = 4
EVENT_HUB_CONN = os.environ.get("EVENT_HUB_CONNECTION_STRING", "")
STORAGE_ACCOUNT = os.environ.get("STORAGE_ACCOUNT_NAME", "")
TABLE_CONN = os.environ.get("TABLE_STORAGE_CONNECTION_STRING", "")

# User database (simulated - in production use a real database)
USERS = {
    f"user{i:03d}": {
        "tier": "premium" if i % 3 == 0 else "basic",
        "max_streams": 4 if i % 3 == 0 else 2,
        "home_region": ["eastus", "westeurope", "australiaeast"][i % 3],
        "blacklisted": False
    }
    for i in range(1, 101)
}

# Add some specific test users
USERS.update({
    "user042": {"tier": "premium", "max_streams": 4, "home_region": "eastus", "blacklisted": False},
    "user077": {"tier": "basic", "max_streams": 3, "home_region": "westeurope", "blacklisted": False},
    "pirate001": {"tier": "premium", "max_streams": 4, "home_region": "eastus", "blacklisted": True},
})


def get_table_service():
    """Get Azure Table Storage service using managed identity"""
    if STORAGE_ACCOUNT:
        try:
            credential = DefaultAzureCredential()
            endpoint = f"https://{STORAGE_ACCOUNT}.table.core.windows.net"
            return TableServiceClient(endpoint=endpoint, credential=credential)
        except Exception as e:
            print(f"Failed to get table service with managed identity: {e}")
    
    if TABLE_CONN:
        try:
            return TableServiceClient.from_connection_string(TABLE_CONN)
        except Exception as e:
            print(f"Failed to get table service with connection string: {e}")
    
    return None


def send_event(event_type: str, data: dict):
    """Send event to Event Hub for Sentinel ingestion"""
    if not EVENT_HUB_CONN:
        print(f"Event Hub not configured, logging event: {event_type} - {data}")
        return
    
    try:
        event = {
            "TimeGenerated": datetime.now(timezone.utc).isoformat(),
            "EventType": event_type,
            **{k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in data.items()}
        }
        
        producer = EventHubProducerClient.from_connection_string(
            EVENT_HUB_CONN, 
            eventhub_name="streaming-events"
        )
        with producer:
            batch = producer.create_batch()
            batch.add(EventData(json.dumps(event)))
            producer.send_batch(batch)
        print(f"Event sent: {event_type}")
    except Exception as e:
        print(f"Failed to send event: {e}")


def store_session(user_id: str, session_id: str, data: dict):
    """Store session in Azure Table Storage"""
    try:
        service = get_table_service()
        if not service:
            print("Table storage not available")
            return
        
        client = service.get_table_client("sessions")
        entity = {
            "PartitionKey": user_id,
            "RowKey": session_id,
            "ClientIP": data.get("client_ip", "unknown"),
            "ClientRegion": data.get("client_region", "unknown"),
            "DeviceFingerprint": data.get("device_fingerprint", "unknown"),
            "CreatedAt": datetime.now(timezone.utc).isoformat(),
            "LastSeen": datetime.now(timezone.utc).isoformat(),
            "Status": "active",
            "MaxStreams": data.get("max_streams", 2)
        }
        client.upsert_entity(entity)
        print(f"Session stored: {user_id}/{session_id}")
    except Exception as e:
        print(f"Failed to store session: {e}")


def revoke_session_in_storage(user_id: str, session_id: str = None):
    """Mark session(s) as revoked in storage"""
    try:
        service = get_table_service()
        if not service:
            return 0
        
        client = service.get_table_client("sessions")
        revoked_count = 0
        
        if session_id:
            try:
                entity = client.get_entity(user_id, session_id)
                entity["Status"] = "revoked"
                entity["RevokedAt"] = datetime.now(timezone.utc).isoformat()
                client.update_entity(entity)
                revoked_count = 1
            except:
                pass
        else:
            query = f"PartitionKey eq '{user_id}' and Status eq 'active'"
            for entity in client.query_entities(query):
                entity["Status"] = "revoked"
                entity["RevokedAt"] = datetime.now(timezone.utc).isoformat()
                client.update_entity(entity)
                revoked_count += 1
        
        return revoked_count
    except Exception as e:
        print(f"Failed to revoke session: {e}")
        return 0


def get_active_session_count(user_id: str) -> int:
    """Count active sessions for a user"""
    try:
        service = get_table_service()
        if not service:
            return 0
        
        client = service.get_table_client("sessions")
        query = f"PartitionKey eq '{user_id}' and Status eq 'active'"
        count = sum(1 for _ in client.query_entities(query))
        return count
    except Exception as e:
        print(f"Failed to count sessions: {e}")
        return 0


def is_session_revoked(user_id: str, session_id: str) -> bool:
    """Check if a session has been revoked"""
    try:
        service = get_table_service()
        if not service:
            return False
        
        client = service.get_table_client("sessions")
        entity = client.get_entity(user_id, session_id)
        return entity.get("Status") == "revoked"
    except:
        return False


@app.route(route="auth/token", methods=["POST"])
def issue_token(req: func.HttpRequest) -> func.HttpResponse:
    """Issue a new JWT token for a user"""
    try:
        body = req.get_json()
        user_id = body.get("user_id")
        device_fingerprint = body.get("device_fingerprint", "unknown")
        client_ip = req.headers.get("X-Forwarded-For", req.headers.get("X-Real-IP", "unknown"))
        client_region = body.get("region", "unknown")
        
        if not user_id:
            return func.HttpResponse(
                json.dumps({"error": "user_id required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        if user_id not in USERS:
            send_event("token_denied", {
                "UserId": user_id,
                "ClientIP": client_ip,
                "ClientRegion": client_region,
                "Status": "invalid_user",
                "Reason": "User not found"
            })
            return func.HttpResponse(
                json.dumps({"error": "Invalid user"}),
                status_code=401,
                mimetype="application/json"
            )
        
        user = USERS[user_id]
        
        if user.get("blacklisted", False):
            send_event("token_denied", {
                "UserId": user_id,
                "ClientIP": client_ip,
                "ClientRegion": client_region,
                "Status": "blacklisted",
                "Reason": "User is blacklisted"
            })
            return func.HttpResponse(
                json.dumps({"error": "Access denied"}),
                status_code=403,
                mimetype="application/json"
            )
        
        active_count = get_active_session_count(user_id)
        if active_count >= user["max_streams"]:
            send_event("token_denied", {
                "UserId": user_id,
                "ClientIP": client_ip,
                "ClientRegion": client_region,
                "Status": "concurrent_limit",
                "Reason": f"Active streams ({active_count}) >= max ({user['max_streams']})",
                "MaxStreams": user["max_streams"]
            })
            return func.HttpResponse(
                json.dumps({
                    "error": "Concurrent stream limit reached",
                    "active_streams": active_count,
                    "max_streams": user["max_streams"]
                }),
                status_code=429,
                mimetype="application/json"
            )
        
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        payload = {
            "sub": user_id,
            "sid": session_id,
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
            "region": client_region,
            "device": device_fingerprint,
            "tier": user["tier"],
            "max_streams": user["max_streams"],
            "ip": client_ip
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        store_session(user_id, session_id, {
            "client_ip": client_ip,
            "client_region": client_region,
            "device_fingerprint": device_fingerprint,
            "max_streams": user["max_streams"]
        })
        
        send_event("token_issued", {
            "UserId": user_id,
            "SessionId": session_id,
            "ClientIP": client_ip,
            "ClientRegion": client_region,
            "DeviceFingerprint": device_fingerprint,
            "Status": "success",
            "MaxStreams": user["max_streams"]
        })
        
        return func.HttpResponse(
            json.dumps({
                "token": token,
                "session_id": session_id,
                "expires_in": JWT_EXPIRY_HOURS * 3600,
                "max_streams": user["max_streams"]
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="auth/validate", methods=["POST"])
def validate_token(req: func.HttpRequest) -> func.HttpResponse:
    """Validate a token and check for abuse patterns"""
    try:
        body = req.get_json()
        token = body.get("token")
        client_ip = req.headers.get("X-Forwarded-For", "unknown")
        client_region = body.get("region", "unknown")
        
        if not token:
            return func.HttpResponse(
                json.dumps({"valid": False, "error": "Token required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return func.HttpResponse(
                json.dumps({"valid": False, "error": "Token expired"}),
                status_code=401,
                mimetype="application/json"
            )
        except jwt.InvalidTokenError:
            return func.HttpResponse(
                json.dumps({"valid": False, "error": "Invalid token"}),
                status_code=401,
                mimetype="application/json"
            )
        
        user_id = payload["sub"]
        session_id = payload["sid"]
        
        if is_session_revoked(user_id, session_id):
            send_event("token_rejected", {
                "UserId": user_id,
                "SessionId": session_id,
                "ClientIP": client_ip,
                "ClientRegion": client_region,
                "Status": "revoked",
                "Reason": "Session has been revoked"
            })
            return func.HttpResponse(
                json.dumps({"valid": False, "error": "Session revoked"}),
                status_code=401,
                mimetype="application/json"
            )
        
        user = USERS.get(user_id, {})
        if user.get("blacklisted", False):
            send_event("token_rejected", {
                "UserId": user_id,
                "SessionId": session_id,
                "ClientIP": client_ip,
                "ClientRegion": client_region,
                "Status": "blacklisted",
                "Reason": "User is blacklisted"
            })
            return func.HttpResponse(
                json.dumps({"valid": False, "error": "Access denied"}),
                status_code=403,
                mimetype="application/json"
            )
        
        send_event("stream_heartbeat", {
            "UserId": user_id,
            "SessionId": session_id,
            "ClientIP": client_ip,
            "ClientRegion": client_region,
            "DeviceFingerprint": payload.get("device", "unknown"),
            "Status": "success",
            "MaxStreams": payload.get("max_streams", 2)
        })
        
        return func.HttpResponse(
            json.dumps({
                "valid": True,
                "user_id": user_id,
                "session_id": session_id,
                "tier": payload.get("tier"),
                "max_streams": payload.get("max_streams")
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"valid": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="auth/revoke", methods=["POST"])
def revoke_session(req: func.HttpRequest) -> func.HttpResponse:
    """Revoke a user session (called by Sentinel playbook or admin)"""
    try:
        body = req.get_json()
        user_id = body.get("user_id")
        session_id = body.get("session_id")
        reason = body.get("reason", "manual_revocation")
        
        if not user_id:
            return func.HttpResponse(
                json.dumps({"error": "user_id required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        revoked_count = revoke_session_in_storage(user_id, session_id)
        
        send_event("session_revoked", {
            "UserId": user_id,
            "SessionId": session_id or "all",
            "Reason": reason,
            "Status": "success"
        })
        
        return func.HttpResponse(
            json.dumps({
                "revoked": True,
                "user_id": user_id,
                "session_id": session_id,
                "revoked_count": revoked_count,
                "reason": reason
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="auth/sessions/{user_id}", methods=["GET"])
def list_sessions(req: func.HttpRequest) -> func.HttpResponse:
    """List active sessions for a user"""
    try:
        user_id = req.route_params.get("user_id")
        
        service = get_table_service()
        if not service:
            return func.HttpResponse(
                json.dumps({"user_id": user_id, "sessions": [], "note": "Storage not configured"}),
                status_code=200,
                mimetype="application/json"
            )
        
        client = service.get_table_client("sessions")
        query = f"PartitionKey eq '{user_id}'"
        sessions = []
        for entity in client.query_entities(query):
            sessions.append({
                "session_id": entity["RowKey"],
                "client_ip": entity.get("ClientIP"),
                "client_region": entity.get("ClientRegion"),
                "status": entity.get("Status"),
                "created_at": entity.get("CreatedAt"),
                "last_seen": entity.get("LastSeen")
            })
        
        return func.HttpResponse(
            json.dumps({
                "user_id": user_id,
                "sessions": sessions,
                "active_count": sum(1 for s in sessions if s["status"] == "active")
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "storage_configured": bool(STORAGE_ACCOUNT or TABLE_CONN),
            "eventhub_configured": bool(EVENT_HUB_CONN)
        }),
        status_code=200,
        mimetype="application/json"
    )
