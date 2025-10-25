"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Voice webhook schemas
class TwilioCallRequest(BaseModel):
    """Twilio incoming call webhook payload"""
    CallSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str = "inbound"


class TwilioModeRequest(BaseModel):
    """User mode selection"""
    CallSid: str
    Digits: Optional[str] = None


# Session schemas
class SessionData(BaseModel):
    """Redis session data structure"""
    call_sid: str
    user_id: int
    mode: str
    start_time: datetime
    turns: List[Dict[str, str]] = []


# API Response schemas
class CallResponse(BaseModel):
    """Call details response"""
    id: int
    call_sid: str
    from_number: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    mode: str
    mood_score: Optional[float]
    sentiment: Optional[str]
    summary: Optional[str]
    tags: Optional[List[str]]
    
    class Config:
        from_attributes = True


class TranscriptResponse(BaseModel):
    """Transcript entry response"""
    id: int
    timestamp: datetime
    speaker: str
    text: str
    emotion: Optional[str]
    
    class Config:
        from_attributes = True


class EntityResponse(BaseModel):
    """Entity response"""
    id: int
    name: str
    entity_type: str
    mention_count: int
    properties: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class RelationResponse(BaseModel):
    """Relation response"""
    id: int
    entity1: EntityResponse
    entity2: EntityResponse
    relation_type: str
    context: Optional[str]
    
    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    """Knowledge graph response"""
    nodes: List[EntityResponse]
    edges: List[RelationResponse]


class CallDetailResponse(CallResponse):
    """Detailed call response with transcript"""
    transcripts: List[TranscriptResponse]
    audio_url: Optional[str] = None


# User schemas
class UserResponse(BaseModel):
    """User profile response"""
    id: int
    phone_number: str
    name: Optional[str]
    preferred_mode: str
    baseline_mood: float
    total_calls: int = 0
    
    class Config:
        from_attributes = True


# Check-in schemas
class CheckInCreate(BaseModel):
    """Create check-in request"""
    user_id: int
    call_id: Optional[int]
    scheduled_time: datetime
    reason: str
    delivery_method: str = "sms"


class CheckInResponse(BaseModel):
    """Check-in response"""
    id: int
    scheduled_time: datetime
    status: str
    reason: str
    delivery_method: str
    
    class Config:
        from_attributes = True

