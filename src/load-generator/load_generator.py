"""
Load Generator for Streaming Content Protection Demo
Simulates various user behaviors and attack patterns
"""

import asyncio
import aiohttp
import yaml
import random
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict
from faker import Faker

fake = Faker()


class StreamingClient:
    """Simulates a single streaming client"""
    
    def __init__(self, user_id: str, region: str, auth_url: str, cdn_url: str):
        self.user_id = user_id
        self.region = region
        self.auth_url = auth_url
        self.cdn_url = cdn_url
        self.session_id = None
        self.token = None
        self.device_fingerprint = hashlib.sha256(
            f"{user_id}-{uuid.uuid4()}".encode()
        ).hexdigest()[:16]
    
    async def authenticate(self, session: aiohttp.ClientSession) -> bool:
        """Get auth token"""
        try:
            async with session.post(
                f"{self.auth_url}/auth/token",
                json={
                    "user_id": self.user_id,
                    "device_fingerprint": self.device_fingerprint,
                    "region": self.region
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data["token"]
                    self.session_id = data["session_id"]
                    return True
                return False
        except Exception as e:
            print(f"Auth failed for {self.user_id}: {e}")
            return False
    
    async def stream(self, session: aiohttp.ClientSession, duration_seconds: int):
        """Simulate streaming with heartbeats"""
        if not self.token:
            return
        
        start_time = datetime.utcnow()
        heartbeat_interval = 10  # seconds
        
        while (datetime.utcnow() - start_time).seconds < duration_seconds:
            # Simulate fetching video segments
            segment = random.randint(1, 100)
            try:
                async with session.get(
                    f"{self.cdn_url}/stream/segment_{segment}.ts",
                    headers={"Authorization": f"Bearer {self.token}"}
                ) as resp:
                    if resp.status == 403:
                        print(f"Session blocked for {self.user_id}")
                        return
            except Exception:
                pass
            
            await asyncio.sleep(heartbeat_interval)


class LoadGenerator:
    """Orchestrates multiple streaming clients"""
    
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.auth_url = self.config["endpoints"]["auth"]
        self.cdn_url = self.config["endpoints"]["cdn"]
        self.region = self.config["region"]
    
    async def run_normal_traffic(self, num_users: int, duration: int):
        """Generate normal user traffic"""
        print(f"Starting normal traffic: {num_users} users for {duration}s")
        
        async with aiohttp.ClientSession() as session:
            clients = []
            for i in range(num_users):
                user_id = f"user{i:03d}"
                client = StreamingClient(
                    user_id, self.region, self.auth_url, self.cdn_url
                )
                clients.append(client)
            
            # Authenticate all
            auth_tasks = [c.authenticate(session) for c in clients]
            await asyncio.gather(*auth_tasks)
            
            # Stream
            stream_tasks = [c.stream(session, duration) for c in clients]
            await asyncio.gather(*stream_tasks)
    
    async def run_credential_sharing(self, user_id: str, regions: List[str]):
        """Simulate credential sharing attack"""
        print(f"Starting credential sharing: {user_id} from {regions}")
        
        async with aiohttp.ClientSession() as session:
            # Create clients in different regions with same user
            clients = [
                StreamingClient(user_id, region, self.auth_url, self.cdn_url)
                for region in regions
            ]
            
            # All authenticate simultaneously
            auth_tasks = [c.authenticate(session) for c in clients]
            await asyncio.gather(*auth_tasks)
            
            # All stream simultaneously
            stream_tasks = [c.stream(session, 300) for c in clients]
            await asyncio.gather(*stream_tasks)
    
    async def run_concurrent_abuse(self, user_id: str, num_streams: int):
        """Simulate concurrent stream abuse"""
        print(f"Starting concurrent abuse: {user_id} with {num_streams} streams")
        
        async with aiohttp.ClientSession() as session:
            clients = [
                StreamingClient(user_id, self.region, self.auth_url, self.cdn_url)
                for _ in range(num_streams)
            ]
            
            auth_tasks = [c.authenticate(session) for c in clients]
            await asyncio.gather(*auth_tasks)
            
            stream_tasks = [c.stream(session, 300) for c in clients]
            await asyncio.gather(*stream_tasks)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--scenario", choices=[
        "normal", "credential_sharing", "concurrent_abuse"
    ])
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()
    
    generator = LoadGenerator(args.config)
    
    if args.scenario == "normal":
        asyncio.run(generator.run_normal_traffic(args.users, args.duration))
    elif args.scenario == "credential_sharing":
        asyncio.run(generator.run_credential_sharing(
            "user042", ["eastus", "westeurope"]
        ))
    elif args.scenario == "concurrent_abuse":
        asyncio.run(generator.run_concurrent_abuse("user077", 5))
