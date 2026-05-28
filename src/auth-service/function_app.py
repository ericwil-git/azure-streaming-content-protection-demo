"""
Auth Service for Streaming Content Protection Demo
Handles token issuance, validation, and session management
"""

import azure.functions as func
import jwt
import json
import uuid
import os
from datetime import datetime, timedelta
from azure.data.tables import TableServiceClient
from azure.eventhub import EventHubProducerClient, EventData

app = func.FunctionApp()

# Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "demo-secret-change-in-prod")
JWT_EXPIRY_HOURS = 4
EVENT_HUB_CONN = os.environ.get("EVENT_HUB_CONNECTION_STRING")
TABLE_CONN = os.environ.get("TABLE_STORAGE_CONNECTION_STRING")

# User database (in production, this would be a real database)
USERS = {
    "user001": {"tier": "premium", "max_streams": 4, "home_region": "eastus"},
    "user002": {"tier": "basic", "max_streams": 2, "home_region": "westeurope"},
    "user003": {"tier": "premium", "max_streams": 4, "home_region": "australiaeast"},
    # ... more users
}

def send_event(event_type: str, data: dict):
    """Send event to Event Hub for Sentinel ingestion"""
    if not EVENT_HUB_CONN:
        return
    
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        **data
    }
    
    producer = EventHubProducerClient.from_connection_string(EVENT_HUB_CONN)
    with producer:
        batch = producer.create_batch()
        batch.add(EventData(json.dumps(event)))
        producer.send_batch(batch)


@app.route(route="auth/token", methods=["POST"])
def issue_token(req: func.HttpRequest) -> func.HttpResponse:
    """Issue a new JWT token for a user"""
    try:
        body = req.get_json()
        user_id = body.get("user_id")
        device_fingerprint = body.get("device_fingerprint", "unknown")
        client_ip = req.headers.get("X-Forwarded-For", "unknown")
        client_region = body.get("region", "unknown")
        
        if user_id not in USERS:
            return func.HttpResponse(
                json.dumps({"error": "Invalid user"}),
                status_code=401,
                mimetype="application/json"
            )
        
        user = USERS[user_id]
        session_id = str(uuid.uuid4())
        
        # Create JWT
        payload = {
            "sub": user_id,
            "sid": session_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
            "region": client_region,
            "device": device_fingerprint,
            "tier": user["tier"],
            "max_streams": user["max_streams"]
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        # Store session (for tracking)
        # TODO: Store in Azure Table Storage
        
        # Send event
        send_event("token_issued", {
            "user_id": user_id,
            "session_id": session_id,
            "client_ip": client_ip,
            "client_region": client_region,
            "device_fingerprint": device_fingerprint,
            "status": "success"
        })
        
        return func.HttpResponse(
            json.dumps({"token": token, "session_id": session_id}),
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
        
        # Decode and verify JWT
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        # TODO: Check session status (not revoked)
        # TODO: Check concurrent stream count
        # TODO: Check for geo anomaly
        
        send_event("token_validated", {
            "user_id": payload["sub"],
            "session_id": payload["sid"],
            "client_ip": client_ip,
            "client_region": client_region,
            "status": "success"
        })
        
        return func.HttpResponse(
            json.dumps({"valid": True, "user_id": payload["sub"]}),
            status_code=200,
            mimetype="application/json"
        )
        
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


@app.route(route="auth/revoke", methods=["POST"])
def revoke_session(req: func.HttpRequest) -> func.HttpResponse:
    """Revoke a user session (called by Sentinel playbook)"""
    try:
        body = req.get_json()
        user_id = body.get("user_id")
        session_id = body.get("session_id")
        reason = body.get("reason", "manual_revocation")
        
        # TODO: Mark session as revoked in Table Storage
        
        send_event("session_revoked", {
            "user_id": user_id,
            "session_id": session_id,
            "reason": reason,
            "status": "success"
        })
        
        return func.HttpResponse(
            json.dumps({"revoked": True}),
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
    user_id = req.route_params.get("user_id")
    
    # TODO: Query Table Storage for active sessions
    
    return func.HttpResponse(
        json.dumps({"user_id": user_id, "sessions": []}),
        status_code=200,
        mimetype="application/json"
    )
