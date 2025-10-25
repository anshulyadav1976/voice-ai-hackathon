"""
Layercode Webhook Handlers
Receives events from Layercode pipeline
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
import json

from app.database import AsyncSessionLocal
from app.models import User, Call, Transcript
from app.redis_client import redis_client
from app.services.openai_service import OpenAIService
from app.services.layercode_service import LayercodeService
from app.tasks import extract_and_store_entities, calculate_and_store_mood
from sqlalchemy import select

router = APIRouter()

openai_service = OpenAIService()
layercode_service = LayercodeService()


@router.post("/webhook/transcript")
async def handle_transcript_webhook(request: Request):
    """
    Main webhook endpoint for Layercode
    
    Handles multiple Layercode event types:
    - session.start: Call begins
    - message: User speaks (transcript)
    - session.update: Call updates
    - session.end: Call ends
    
    Returns SSE (Server-Sent Events) stream
    """
    data = None
    try:
        data = await request.json()
        
        # Log the incoming request for debugging
        print(f"📥 Layercode webhook received: {data}")
        
        # Extract event type (Layercode format)
        event_type = data.get("event") or data.get("type", "message")
        
        # Handle different event types
        if event_type == "session.start":
            return await handle_session_start(data)
        elif event_type == "session.end" or event_type == "session.complete":
            return await handle_session_end(data)
        elif event_type in ["message", "transcript", "session.update"]:
            return await handle_message(data)
        else:
            print(f"⚠️ Unknown event type: {event_type}")
            return {"status": "ok", "action": "continue"}
        
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        import traceback
        traceback.print_exc()
        
        # Return SSE stream even on error
        async def error_stream():
            turn_id = data.get("turn_id", "unknown") if data else "unknown"
            response_data = json.dumps({
                "type": "response.tts",
                "content": "I'm here with you. Please continue.",
                "turn_id": turn_id
            })
            yield f"data: {response_data}\n\n"
            
            end_data = json.dumps({"type": "response.end", "turn_id": turn_id})
            yield f"data: {end_data}\n\n"
        
        return StreamingResponse(error_stream(), media_type="text/event-stream")


async def handle_session_start(data: Dict[str, Any]) -> StreamingResponse:
    """Handle session.start event - returns SSE stream"""
    print(f"📞 Session starting: {data}")
    
    session_id = data.get("session_id") or data.get("call_id", "unknown")
    from_number = data.get("from") or data.get("caller", "unknown")
    turn_id = data.get("turn_id", session_id)
    
    # Initialize session
    await initialize_session(session_id, from_number)
    
    # Return SSE stream with welcome message
    async def welcome_stream():
        welcome_text = "Welcome to Echo Diary. I'm here to listen. How are you feeling today?"
        
        response_data = json.dumps({
            "type": "response.tts",
            "content": welcome_text,
            "turn_id": turn_id
        })
        yield f"data: {response_data}\n\n"
        
        end_data = json.dumps({"type": "response.end", "turn_id": turn_id})
        yield f"data: {end_data}\n\n"
    
    return StreamingResponse(welcome_stream(), media_type="text/event-stream")


async def handle_session_end(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle session.end event"""
    print(f"👋 Session ending: {data}")
    
    session_id = data.get("session_id") or data.get("call_id", "unknown")
    
    # Cleanup will happen in background
    # For now, just acknowledge
    return {"status": "ok", "message": "Session ended"}


async def handle_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle message/transcript event"""
    
    # Extract data (handle different Layercode formats)
    session_id = data.get("session_id") or data.get("call_id") or data.get("id", "unknown")
    call_sid = session_id  # Use session_id as call_sid
    
    # Get transcript text
    transcript_text = (
        data.get("text") or 
        data.get("transcript") or 
        data.get("message", {}).get("content") or
        data.get("content") or
        ""
    )
    
    # Check if final
    is_final = data.get("is_final", True)
    
    # Get caller
    from_number = (
        data.get("from") or 
        data.get("caller") or 
        data.get("phone_number") or
        "unknown"
    )
    
    print(f"📝 Message from {from_number}: {transcript_text[:100] if len(transcript_text) > 100 else transcript_text}")
    
    # Only process if we have text
    if not transcript_text.strip():
        return {"status": "ok", "action": "continue"}
    
    # Get or create session
    session = await redis_client.get_session(call_sid)
    
    if not session:
        # First message - initialize session
        session = await initialize_session(call_sid, from_number)
    
    # Store user transcript in database
    async with AsyncSessionLocal() as db:
        transcript_entry = Transcript(
            call_id=session["call_db_id"],
            speaker="user",
            text=transcript_text,
            timestamp=datetime.utcnow()
        )
        db.add(transcript_entry)
        await db.commit()
    
    # Add to context
    await redis_client.add_turn_to_context(call_sid, "user", transcript_text)
    
    # Get conversation context
    context = await redis_client.get_context(call_sid)
    mode = session.get("mode", "reassure")
    
    # Generate GPT response
    print(f"🤖 Generating response in '{mode}' mode...")
    response_text = await openai_service.generate_response(
        transcript=transcript_text,
        context=context,
        mode=mode
    )
    
    print(f"💬 GPT Response: {response_text}")
    
    # Store agent response in database
    async with AsyncSessionLocal() as db:
        agent_transcript = Transcript(
            call_id=session["call_db_id"],
            speaker="agent",
            text=response_text,
            timestamp=datetime.utcnow()
        )
        db.add(agent_transcript)
        await db.commit()
    
    # Add to context
    await redis_client.add_turn_to_context(call_sid, "agent", response_text)
    
    # Return SSE stream with response
    turn_id = data.get("turn_id", call_sid)
    
    async def response_stream():
        response_data = json.dumps({
            "type": "response.tts",
            "content": response_text,
            "turn_id": turn_id
        })
        yield f"data: {response_data}\n\n"
        
        end_data = json.dumps({"type": "response.end", "turn_id": turn_id})
        yield f"data: {end_data}\n\n"
    
    return StreamingResponse(response_stream(), media_type="text/event-stream")


@router.post("/webhook/call-start")
async def handle_call_start(request: Request):
    """
    Called when a call starts in Layercode
    Used to initialize session and ask for mode
    """
    try:
        data = await request.json()
        
        call_id = data.get("call_id")
        call_sid = data.get("call_sid", call_id)
        from_number = data.get("from", "unknown")
        
        print(f"📞 Call started from {from_number}")
        
        # Initialize session
        await initialize_session(call_sid, from_number)
        
        # Return initial greeting
        return layercode_service.format_response(
            text="Welcome to Echo Diary. I'm here to listen. How are you feeling today?",
            emotion="warm"
        )
        
    except Exception as e:
        print(f"❌ Error in call start: {e}")
        return layercode_service.format_response(
            text="Welcome to Echo Diary.",
            emotion="neutral"
        )


@router.post("/webhook/call-end")
async def handle_call_end(request: Request):
    """
    Called when call ends in Layercode
    Finalize processing and cleanup
    """
    try:
        data = await request.json()
        
        call_id = data.get("call_id")
        call_sid = data.get("call_sid", call_id)
        duration = data.get("duration_seconds", 0)
        
        print(f"👋 Call ended: {call_sid}, duration: {duration}s")
        
        # Get session
        session = await redis_client.get_session(call_sid)
        
        if session:
            # Update call record
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Call).where(Call.id == session["call_db_id"])
                )
                call = result.scalar_one_or_none()
                
                if call:
                    call.end_time = datetime.utcnow()
                    call.duration_seconds = duration
                    await db.commit()
                    
                    # Get full transcript for post-processing
                    transcript_result = await db.execute(
                        select(Transcript)
                        .where(Transcript.call_id == call.id)
                        .order_by(Transcript.timestamp)
                    )
                    transcripts = transcript_result.scalars().all()
                    
                    # Combine transcript
                    full_transcript = "\n".join([
                        f"{t.speaker}: {t.text}" 
                        for t in transcripts
                    ])
                    
                    # Trigger background processing immediately
                    if full_transcript:
                        print(f"🔄 Starting entity extraction for call {call.id}")
                        try:
                            await extract_and_store_entities(call.id, full_transcript)
                            await calculate_and_store_mood(call.id, full_transcript)
                        except Exception as e:
                            print(f"❌ Background processing error: {e}")
            
            # Cleanup session
            await redis_client.delete_session(call_sid)
        
        return {"status": "ok", "message": "Call finalized"}
        
    except Exception as e:
        print(f"❌ Error in call end: {e}")
        return {"status": "error", "message": str(e)}


async def initialize_session(call_sid: str, from_number: str) -> Dict[str, Any]:
    """
    Initialize a new call session
    Creates user and call records, sets up Redis session
    """
    async with AsyncSessionLocal() as db:
        # Get or create user
        result = await db.execute(
            select(User).where(User.phone_number == from_number)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(phone_number=from_number)
            db.add(user)
            await db.flush()
        
        # Check if call already exists (for repeated test calls)
        call_result = await db.execute(
            select(Call).where(Call.call_sid == call_sid)
        )
        call = call_result.scalar_one_or_none()
        
        if not call:
            # Create new call record
            call = Call(
                user_id=user.id,
                call_sid=call_sid,
                from_number=from_number,
                start_time=datetime.utcnow(),
                mode=user.preferred_mode
            )
            db.add(call)
            await db.commit()
            await db.refresh(call)
        
        # Initialize Redis session
        session_data = {
            "call_sid": call_sid,
            "user_id": user.id,
            "call_db_id": call.id,
            "start_time": datetime.utcnow().isoformat(),
            "mode": user.preferred_mode,
            "turns": []
        }
        
        await redis_client.set_session(call_sid, session_data)
        
        return session_data


@router.get("/health")
async def health_check():
    """Health check for Layercode webhook"""
    return {
        "status": "healthy",
        "service": "layercode-webhook",
        "timestamp": datetime.utcnow().isoformat()
    }

