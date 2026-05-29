"""
Event Processor - Bridges Event Hub events to Log Analytics

This Azure Function reads streaming events from Event Hub and sends them
to Log Analytics via the Data Collection Rule API, enabling Sentinel detection.
"""
import os
import json
import logging
import datetime
from azure.functions import EventHubEvent
from azure.identity import DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient

# Configuration
DCE_ENDPOINT = os.environ.get("DCE_ENDPOINT")  # Data Collection Endpoint
DCR_IMMUTABLE_ID = os.environ.get("DCR_IMMUTABLE_ID")  # DCR immutable ID
STREAM_NAME = os.environ.get("STREAM_NAME", "Custom-StreamingEvents_CL")

credential = DefaultAzureCredential()
logs_client = None

def get_logs_client():
    global logs_client
    if logs_client is None:
        logs_client = LogsIngestionClient(endpoint=DCE_ENDPOINT, credential=credential, logging_enable=True)
    return logs_client

def process_event(event_data: dict) -> dict:
    """Transform event data to Log Analytics format."""
    return {
        "TimeGenerated": event_data.get("timestamp", datetime.datetime.utcnow().isoformat()),
        "EventType": event_data.get("event_type", "unknown"),
        "UserId": event_data.get("user_id", ""),
        "SessionId": event_data.get("session_id", ""),
        "ClientIP": event_data.get("client_ip", ""),
        "ClientRegion": event_data.get("region", ""),
        "DeviceFingerprint": event_data.get("device", ""),
        "ContentId": event_data.get("content_id", ""),
        "Status": event_data.get("status", ""),
        "MaxStreams": event_data.get("max_streams", 0),
        "Tier": event_data.get("tier", ""),
        "Reason": event_data.get("reason", ""),
    }

def main(events: list[EventHubEvent]):
    """Process batch of events from Event Hub."""
    logging.info(f"Processing {len(events)} events")
    
    if not DCE_ENDPOINT or not DCR_IMMUTABLE_ID:
        logging.error("Missing DCE_ENDPOINT or DCR_IMMUTABLE_ID configuration")
        return
    
    logs = []
    for event in events:
        try:
            body = event.get_body().decode('utf-8')
            event_data = json.loads(body)
            logs.append(process_event(event_data))
        except Exception as e:
            logging.error(f"Error processing event: {e}")
    
    if logs:
        try:
            client = get_logs_client()
            client.upload(rule_id=DCR_IMMUTABLE_ID, stream_name=STREAM_NAME, logs=logs)
            logging.info(f"Uploaded {len(logs)} logs to Log Analytics")
        except Exception as e:
            logging.error(f"Error uploading to Log Analytics: {e}")
