"""
SQLAlchemy database models for EchoDiary
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """User profile and preferences"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User preferences
    preferred_mode = Column(String(20), default="reassure")  # reassure, tough_love, listener
    baseline_mood = Column(Float, default=5.0)
    
    # Relationships
    calls = relationship("Call", back_populates="user", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="user", cascade="all, delete-orphan")


class Call(Base):
    """Individual call records"""
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Twilio details
    call_sid = Column(String(100), unique=True, index=True, nullable=False)
    from_number = Column(String(20), nullable=False)
    
    # Call metadata
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Conversation details
    mode = Column(String(20), default="reassure")  # conversation mode chosen
    mood_score = Column(Float, nullable=True)  # 1-10 scale
    sentiment = Column(String(20), nullable=True)  # positive, neutral, negative
    
    # Audio storage
    audio_url = Column(String(500), nullable=True)
    audio_duration = Column(Integer, nullable=True)
    
    # Summary
    summary = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["stressed", "work", "family"]
    
    # Relationships
    user = relationship("User", back_populates="calls")
    transcripts = relationship("Transcript", back_populates="call", cascade="all, delete-orphan")
    relations = relationship("Relation", back_populates="call", cascade="all, delete-orphan")


class Transcript(Base):
    """Conversation transcripts (turn by turn)"""
    __tablename__ = "transcripts"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Turn details
    timestamp = Column(DateTime, default=datetime.utcnow)
    speaker = Column(String(20), nullable=False)  # "user" or "agent"
    text = Column(Text, nullable=False)
    
    # Optional metadata
    confidence = Column(Float, nullable=True)  # STT confidence score
    emotion = Column(String(50), nullable=True)  # detected emotion
    
    # Relationships
    call = relationship("Call", back_populates="transcripts")


class Entity(Base):
    """Knowledge graph entities"""
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Entity details
    name = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)  # Person, Place, Org, Topic, Emotion
    
    # Metadata
    first_mentioned = Column(DateTime, default=datetime.utcnow)
    last_mentioned = Column(DateTime, default=datetime.utcnow)
    mention_count = Column(Integer, default=1)
    
    # Additional properties (JSON for flexibility)
    properties = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="entities")
    relations_from = relationship(
        "Relation",
        foreign_keys="Relation.entity1_id",
        back_populates="entity1",
        cascade="all, delete-orphan"
    )
    relations_to = relationship(
        "Relation",
        foreign_keys="Relation.entity2_id",
        back_populates="entity2",
        cascade="all, delete-orphan"
    )


class Relation(Base):
    """Knowledge graph relations between entities"""
    __tablename__ = "relations"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Relation details
    entity1_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    entity2_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    relation_type = Column(String(50), nullable=False)  # met_with, argued_with, worked_on, felt, went_to
    
    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    context = Column(Text, nullable=True)  # Optional context snippet
    
    # Relationships
    call = relationship("Call", back_populates="relations")
    entity1 = relationship("Entity", foreign_keys=[entity1_id], back_populates="relations_from")
    entity2 = relationship("Entity", foreign_keys=[entity2_id], back_populates="relations_to")


class CheckIn(Base):
    """Scheduled check-ins for users"""
    __tablename__ = "checkins"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)  # Reference to triggering call
    
    # Schedule details
    scheduled_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Status
    status = Column(String(20), default="pending")  # pending, completed, failed, cancelled
    completed_at = Column(DateTime, nullable=True)
    
    # Check-in details
    reason = Column(Text, nullable=True)  # Why check-in was scheduled
    message = Column(Text, nullable=True)  # Generated message
    delivery_method = Column(String(20), default="sms")  # sms or call
    
    # Result
    twilio_sid = Column(String(100), nullable=True)  # Twilio message/call SID
    success = Column(Boolean, default=False)

