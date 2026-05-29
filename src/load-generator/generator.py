"""
Load Generator for Streaming Content Protection Demo

Simulates various streaming scenarios:
- Normal traffic from legitimate users
- Credential sharing (same user from multiple regions)
- Concurrent stream abuse (exceeding max streams)
- Geo-blocking violations

Deployed as Azure Container Instances in multiple regions.
"""
import os
import sys
import json
import time
import random
import asyncio
import aiohttp
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

# Configuration
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "https://ca-auth-service.mangobush-cf26b4c9.centralus.azurecontainerapps.io")
REGION = os.environ.get("REGION", "eastus")
SCENARIO = os.environ.get("SCENARIO", "normal")  # normal, credential_sharing, concurrent_abuse, mixed
INTENSITY = int(os.environ.get("INTENSITY", "10"))  # requests per minute
DURATION_MINUTES = int(os.environ.get("DURATION", "5"))

# Demo user pools
NORMAL_USERS = [f"user{i:03d}" for i in range(1, 100) if i not in [42, 77]]
CREDENTIAL_SHARE_USER = "user042"
CONCURRENT_ABUSE_USER = "user077"

@dataclass
class Session:
    user_id: str
    token: str
    session_id: str
    created_at: float
    region: str

class LoadGenerator:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.stats = {
            "tokens_issued": 0,
            "validations": 0,
            "errors": 0,
            "denied": 0,
            "start_time": None,
        }
    
    async def get_token(self, session: aiohttp.ClientSession, user_id: str, region: str) -> Optional[Session]:
        """Request a new token from the auth service."""
        try:
            async with session.post(
                f"{AUTH_SERVICE_URL}/auth/token",
                json={"user_id": user_id, "region": region},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.stats["tokens_issued"] += 1
                    return Session(
                        user_id=user_id,
                        token=data["token"],
                        session_id=data["session_id"],
                        created_at=time.time(),
                        region=region
                    )
                elif resp.status == 403:
                    self.stats["denied"] += 1
                    print(f"[DENIED] User {user_id} access denied")
                else:
                    self.stats["errors"] += 1
                    print(f"[ERROR] Token request failed: {resp.status}")
        except Exception as e:
            self.stats["errors"] += 1
            print(f"[ERROR] Token request exception: {e}")
        return None

    async def validate_token(self, session: aiohttp.ClientSession, user_session: Session, content_id: str = "live-stream-001"):
        """Validate a token (simulate heartbeat)."""
        try:
            async with session.post(
                f"{AUTH_SERVICE_URL}/auth/validate",
                json={"token": user_session.token, "content_id": content_id},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    self.stats["validations"] += 1
                elif resp.status == 401:
                    self.stats["denied"] += 1
                    data = await resp.json()
                    print(f"[REJECTED] User {user_session.user_id}: {data.get('error')}")
                else:
                    self.stats["errors"] += 1
        except Exception as e:
            self.stats["errors"] += 1

    async def run_normal_traffic(self, session: aiohttp.ClientSession):
        """Simulate normal legitimate streaming traffic."""
        # Pick a random user
        user_id = random.choice(NORMAL_USERS)
        
        # Either start a new session or validate existing
        if user_id not in self.sessions or random.random() < 0.1:
            # Start new session
            user_session = await self.get_token(session, user_id, REGION)
            if user_session:
                self.sessions[user_id] = user_session
                print(f"[NEW] {user_id} started session from {REGION}")
        else:
            # Heartbeat existing session
            await self.validate_token(session, self.sessions[user_id])

    async def run_credential_sharing(self, session: aiohttp.ClientSession):
        """Simulate credential sharing - same user from multiple regions."""
        # This generator always uses the credential sharing test user
        # Multiple instances in different regions will trigger detection
        
        if CREDENTIAL_SHARE_USER not in self.sessions or random.random() < 0.3:
            # Get new token from this region
            user_session = await self.get_token(session, CREDENTIAL_SHARE_USER, REGION)
            if user_session:
                self.sessions[CREDENTIAL_SHARE_USER] = user_session
                print(f"[CREDENTIAL_SHARE] {CREDENTIAL_SHARE_USER} logged in from {REGION}")
        else:
            # Heartbeat
            await self.validate_token(session, self.sessions[CREDENTIAL_SHARE_USER])

    async def run_concurrent_abuse(self, session: aiohttp.ClientSession):
        """Simulate concurrent stream abuse - exceeding max allowed streams."""
        # Start multiple sessions for the same user to exceed limit
        session_key = f"{CONCURRENT_ABUSE_USER}_{random.randint(1, 10)}"
        
        if session_key not in self.sessions:
            user_session = await self.get_token(session, CONCURRENT_ABUSE_USER, REGION)
            if user_session:
                self.sessions[session_key] = user_session
                # Count active sessions for this user
                active = sum(1 for k in self.sessions if k.startswith(CONCURRENT_ABUSE_USER))
                print(f"[CONCURRENT_ABUSE] {CONCURRENT_ABUSE_USER} has {active} concurrent sessions")
        else:
            await self.validate_token(session, self.sessions[session_key])

    async def run_mixed(self, session: aiohttp.ClientSession):
        """Run a mix of scenarios."""
        choice = random.random()
        if choice < 0.7:
            await self.run_normal_traffic(session)
        elif choice < 0.85:
            await self.run_credential_sharing(session)
        else:
            await self.run_concurrent_abuse(session)

    async def run(self):
        """Main loop."""
        print(f"=== Load Generator Starting ===")
        print(f"Auth Service: {AUTH_SERVICE_URL}")
        print(f"Region: {REGION}")
        print(f"Scenario: {SCENARIO}")
        print(f"Intensity: {INTENSITY} requests/minute")
        print(f"Duration: {DURATION_MINUTES} minutes")
        print("=" * 40)
        
        self.stats["start_time"] = time.time()
        end_time = self.stats["start_time"] + (DURATION_MINUTES * 60)
        interval = 60.0 / INTENSITY
        
        scenario_func = {
            "normal": self.run_normal_traffic,
            "credential_sharing": self.run_credential_sharing,
            "concurrent_abuse": self.run_concurrent_abuse,
            "mixed": self.run_mixed,
        }.get(SCENARIO, self.run_normal_traffic)
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                await scenario_func(session)
                await asyncio.sleep(interval + random.uniform(-0.5, 0.5))
        
        self.print_stats()

    def print_stats(self):
        elapsed = time.time() - self.stats["start_time"]
        print("\n" + "=" * 40)
        print("=== Load Generator Complete ===")
        print(f"Duration: {elapsed:.1f}s")
        print(f"Tokens Issued: {self.stats['tokens_issued']}")
        print(f"Validations: {self.stats['validations']}")
        print(f"Denied: {self.stats['denied']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 40)

async def main():
    generator = LoadGenerator()
    await generator.run()

if __name__ == "__main__":
    asyncio.run(main())
