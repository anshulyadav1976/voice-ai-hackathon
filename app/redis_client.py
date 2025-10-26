"""
Redis client for session and context management using Upstash
"""
from typing import Optional, Dict, Any
import json
from upstash_redis import Redis
from app.config import get_settings

settings = get_settings()


class RedisClient:
    """Wrapper for Upstash Redis operations"""
    
    def __init__(self):
        self.client = Redis(
            url=settings.upstash_redis_url,
            token=settings.upstash_redis_token
        )
    
    async def set_session(self, call_id: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """Store session data for a call"""
        key = f"session:{call_id}"
        ttl = ttl or settings.session_ttl_seconds
        try:
            self.client.set(key, json.dumps(data), ex=ttl)
            return True
        except Exception as e:
            print(f"Error setting session: {e}")
            return False
    
    async def get_session(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data for a call"""
        key = f"session:{call_id}"
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting session: {e}")
            return None
    
    async def update_session(self, call_id: str, data: Dict[str, Any]) -> bool:
        """Update existing session data"""
        existing = await self.get_session(call_id)
        if existing:
            existing.update(data)
            return await self.set_session(call_id, existing)
        return False
    
    async def delete_session(self, call_id: str) -> bool:
        """Delete session data"""
        key = f"session:{call_id}"
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
    
    async def set_value(self, key: str, value: str, expiry: int = None) -> bool:
        """Store a generic key-value pair with optional expiry (in seconds)"""
        try:
            if expiry:
                self.client.set(key, value, ex=expiry)
            else:
                self.client.set(key, value)
            return True
        except Exception as e:
            print(f"Error setting value for key {key}: {e}")
            return False
    
    async def get_value(self, key: str) -> Optional[str]:
        """Retrieve a generic value by key"""
        try:
            return self.client.get(key)
        except Exception as e:
            print(f"Error getting value for key {key}: {e}")
            return None
    
    async def set_user_profile(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Store user profile data"""
        key = f"user:{user_id}"
        try:
            self.client.set(key, json.dumps(data))
            return True
        except Exception as e:
            print(f"Error setting user profile: {e}")
            return False
    
    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve user profile data"""
        key = f"user:{user_id}"
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    async def set_checkin_flag(self, user_id: int, checkin_data: Dict[str, Any], ttl: int = None) -> bool:
        """Set a check-in flag for a user"""
        key = f"checkin:{user_id}"
        ttl = ttl or (settings.checkin_delay_hours * 3600)
        try:
            self.client.set(key, json.dumps(checkin_data), ex=ttl)
            return True
        except Exception as e:
            print(f"Error setting check-in flag: {e}")
            return False
    
    async def get_checkin_flag(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get check-in flag for a user"""
        key = f"checkin:{user_id}"
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting check-in flag: {e}")
            return None
    
    async def delete_checkin_flag(self, user_id: int) -> bool:
        """Delete check-in flag"""
        key = f"checkin:{user_id}"
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting check-in flag: {e}")
            return False
    
    async def add_turn_to_context(self, call_id: str, speaker: str, text: str) -> bool:
        """Add a conversation turn to the context buffer"""
        session = await self.get_session(call_id)
        if not session:
            return False
        
        turns = session.get("turns", [])
        turns.append({"speaker": speaker, "text": text})
        
        # Keep only last N turns
        if len(turns) > settings.context_turns_limit * 2:  # user + agent = 2x
            turns = turns[-(settings.context_turns_limit * 2):]
        
        session["turns"] = turns
        return await self.set_session(call_id, session)
    
    async def get_context(self, call_id: str) -> list:
        """Get conversation context (recent turns)"""
        session = await self.get_session(call_id)
        if session:
            return session.get("turns", [])
        return []


# Global Redis client instance
redis_client = RedisClient()

