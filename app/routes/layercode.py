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
from app.services.audio_service import AudioService
from app.tasks import extract_and_store_entities, calculate_and_store_mood, generate_call_title
from sqlalchemy import select

router = APIRouter()

openai_service = OpenAIService()
layercode_service = LayercodeService()
audio_service = AudioService()


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
        elif event_type == "session.update":
            # Handle recording URL and other updates separately
            return await handle_session_update(data)
        elif event_type in ["message", "transcript", "user.transcript"]:
            # Only process actual message events
            return await handle_message(data)
        else:
            print(f"⚠️ Unknown event type: {event_type}")
            # Return empty SSE stream for unknown events
            async def empty_stream():
                yield "data: {}\n\n"
            return StreamingResponse(empty_stream(), media_type="text/event-stream")
        
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
                "turn_id": turn_id,
                "emotion": "calm",  # Calm, reassuring tone for errors
                "speaker": "default"
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
    
    # Get metadata from Layercode (includes mode, context_call_id, etc)
    metadata = data.get("metadata", {})
    
    # Initialize session with metadata
    session = await initialize_session(session_id, from_number, metadata)
    
    # Return SSE stream with welcome message
    async def welcome_stream():
        # Check if this is a continuation of a previous conversation
        if session.get("has_context"):
            context_summary = session.get("context_summary", "that conversation")
            welcome_text = f"Hey! I remember our conversation about {context_summary}. Want to talk more about that?"
        else:
            # More natural, varied welcome messages
            import random
            welcomes = [
                "Hey, I'm Echo. I'm here for you. What's on your mind?",
                "Hi! I'm Echo. Just so you know, this is your space. What's going on?",
                "Hey there! I'm Echo, and I'm all ears. What's happening with you?",
                "Hi! I'm Echo. Whatever you need to talk about, I'm here. What's up?"
            ]
            welcome_text = random.choice(welcomes)
        
        response_data = json.dumps({
            "type": "response.tts",
            "content": welcome_text,
            "turn_id": turn_id,
            "emotion": "warm",  # Warm, welcoming tone for Rime
            "speaker": "default"
        })
        yield f"data: {response_data}\n\n"
        
        end_data = json.dumps({"type": "response.end", "turn_id": turn_id})
        yield f"data: {end_data}\n\n"
    
    return StreamingResponse(welcome_stream(), media_type="text/event-stream")


async def handle_session_end(data: Dict[str, Any]) -> StreamingResponse:
    """Handle session.end event - must return SSE stream"""
    print(f"👋 Session ending: {data}")
    
    session_id = data.get("session_id") or data.get("call_id", "unknown")
    turn_id = data.get("turn_id", session_id)
    
    # Process the full transcript if available
    transcript_data = data.get("transcript", [])
    if transcript_data:
        print(f"📝 Full transcript received: {len(transcript_data)} turns")
    
    # Check for audio recording URL from Layercode (might come here or in session.update)
    audio_url = data.get("recording_url") or data.get("audio_url")
    
    if audio_url:
        print(f"🎵 Audio recording URL in session.end: {audio_url}")
        # Store it for the session
        session = await redis_client.get_session(session_id)
        if session:
            await redis_client.update_session(session_id, {"recording_url": audio_url})
    
    # Return SSE stream acknowledgment
    async def end_stream():
        # Just acknowledge the end, no content needed
        yield "data: {}\n\n"
    
    return StreamingResponse(end_stream(), media_type="text/event-stream")


async def handle_session_update(data: Dict[str, Any]) -> StreamingResponse:
    """Handle session.update event - for recording URLs and other updates"""
    print(f"🔄 Session update: {data}")
    
    session_id = data.get("session_id") or data.get("call_id", "unknown")
    recording_url = data.get("recording_url")
    recording_status = data.get("recording_status")
    
    if recording_url and recording_status == "completed":
        print(f"🎵 Recording completed, URL received: {recording_url}")
        
        # Get session and process
        session = await redis_client.get_session(session_id)
        if session and session.get("call_db_id"):
            call_id = session["call_db_id"]
            
            # Store URL in database and download
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(Call).where(Call.id == call_id)
                )
                call = result.scalar_one_or_none()
                
                if call:
                    call.audio_url = recording_url
                    await db.commit()
                    
                    # Download audio in background
                    try:
                        local_path = await audio_service.download_audio(recording_url, call_id)
                        if local_path:
                            print(f"✅ Audio downloaded: {local_path}")
                    except Exception as e:
                        print(f"❌ Error downloading audio: {e}")
                    
                    # Also trigger entity extraction if we haven't already
                    # Get full transcript
                    transcript_result = await db.execute(
                        select(Transcript)
                        .where(Transcript.call_id == call_id)
                        .order_by(Transcript.timestamp)
                    )
                    transcripts = transcript_result.scalars().all()
                    
                    if transcripts:
                        full_transcript = "\n".join([
                            f"{t.speaker}: {t.text}"
                            for t in transcripts
                        ])
                        
                        # Trigger background processing
                        print(f"🔄 Starting background processing for call {call_id}")
                        try:
                            await extract_and_store_entities(call_id, full_transcript)
                            await calculate_and_store_mood(call_id, full_transcript)
                            await generate_call_title(call_id, full_transcript)
                        except Exception as e:
                            print(f"❌ Background processing error: {e}")
                            import traceback
                            traceback.print_exc()
    
    # Return empty SSE stream
    async def update_stream():
        yield "data: {}\n\n"
    
    return StreamingResponse(update_stream(), media_type="text/event-stream")


async def handle_message(data: Dict[str, Any]) -> StreamingResponse:
    """Handle message/transcript event - user speech"""
    
    # Extract data (handle different Layercode formats)
    session_id = data.get("session_id") or data.get("call_id") or data.get("id", "unknown")
    call_sid = session_id  # Use session_id as call_sid
    turn_id = data.get("turn_id", session_id)
    
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
        "web"
    )
    
    print(f"📝 User message from {from_number}: {transcript_text[:100] if len(transcript_text) > 100 else transcript_text}")
    
    # Only process if we have text
    if not transcript_text.strip():
        print(f"⚠️ Empty transcript received, skipping")
        # Return empty SSE stream
        async def empty_stream():
            yield "data: {}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")
    
    # Get or create session
    session = await redis_client.get_session(call_sid)
    
    if not session:
        # First message - initialize session (might have metadata from Layercode)
        metadata = data.get("metadata", {})
        session = await initialize_session(call_sid, from_number, metadata)
    
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
    
    # Add context awareness if this is a continuation
    context_prefix = ""
    if session.get("has_context"):
        context_summary = session.get("context_summary", "our previous conversation")
        context_prefix = f"[Context: We previously talked about {context_summary}] "
    
    # Generate GPT response
    print(f"🤖 Generating response in '{mode}' mode...")
    response_text = await openai_service.generate_response(
        transcript=context_prefix + transcript_text,
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
    
    # Return SSE stream with response (with emotion metadata for Rime)
    turn_id = data.get("turn_id", call_sid)
    
    # Get appropriate emotion for the mode
    emotion = layercode_service.get_emotion_for_mode(mode)
    
    async def response_stream():
        response_data = json.dumps({
            "type": "response.tts",
            "content": response_text,
            "turn_id": turn_id,
            "emotion": emotion,  # Hint for Rime TTS
            "speaker": "default"  # Use Rime's default speaker (can configure in Layercode)
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
        
        # Get metadata if available
        metadata = data.get("metadata", {})
        
        # Initialize session with metadata
        await initialize_session(call_sid, from_number, metadata)
        
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
        
        # Check for audio recording URL
        audio_url = data.get("recording_url") or data.get("audio_url") or data.get("recordingUrl")
        
        print(f"👋 Call ended: {call_sid}, duration: {duration}s")
        if audio_url:
            print(f"🎵 Audio URL received: {audio_url}")
        
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
                    
                    # Store audio URL and download audio file
                    if audio_url:
                        call.audio_url = audio_url
                        
                        # Download audio file asynchronously
                        try:
                            local_path = await audio_service.download_audio(audio_url, call.id)
                            if local_path:
                                print(f"✅ Audio saved locally: {local_path}")
                            else:
                                print(f"⚠️ Audio URL stored but download failed")
                        except Exception as audio_error:
                            print(f"❌ Error downloading audio: {audio_error}")
                    
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
                        print(f"🔄 Starting background processing for call {call.id}")
                        try:
                            await extract_and_store_entities(call.id, full_transcript)
                            await calculate_and_store_mood(call.id, full_transcript)
                            await generate_call_title(call.id, full_transcript)
                        except Exception as e:
                            print(f"❌ Background processing error: {e}")
            
            # Cleanup session
            await redis_client.delete_session(call_sid)
        
        return {"status": "ok", "message": "Call finalized"}
        
    except Exception as e:
        print(f"❌ Error in call end: {e}")
        return {"status": "error", "message": str(e)}


async def initialize_session(call_sid: str, from_number: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Initialize a new call session
    Creates user and call records, sets up Redis session
    Supports loading context from previous conversations
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
        
        # Get mode from metadata or use user preference
        mode = metadata.get("mode", user.preferred_mode) if metadata else user.preferred_mode
        
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
                mode=mode
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
            "mode": mode,
            "turns": []
        }
        
        # Handle context from previous conversation if provided
        if metadata and metadata.get("context_call_id"):
            context_call_id = metadata["context_call_id"]
            print(f"🔗 Loading context from previous call {context_call_id}")
            
            try:
                # Load previous conversation
                context_result = await db.execute(
                    select(Call).where(Call.id == int(context_call_id))
                )
                context_call = context_result.scalar_one_or_none()
                
                if context_call:
                    # Load transcripts from context call
                    transcript_result = await db.execute(
                        select(Transcript)
                        .where(Transcript.call_id == context_call_id)
                        .order_by(Transcript.timestamp)
                    )
                    context_transcripts = transcript_result.scalars().all()
                    
                    # Build context summary for session
                    context_summary = context_call.summary or "previous conversation"
                    session_data["has_context"] = True
                    session_data["context_call_id"] = context_call_id
                    session_data["context_summary"] = context_summary
                    
                    print(f"✅ Loaded context: '{context_summary}' with {len(context_transcripts)} messages")
                else:
                    print(f"⚠️ Context call {context_call_id} not found")
            except Exception as e:
                print(f"❌ Error loading context: {e}")
        
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

