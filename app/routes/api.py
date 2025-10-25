"""
Web UI API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
import os

from app.database import get_db
from app.models import User, Call, Transcript, Entity, Relation
from app.schemas import (
    CallResponse,
    CallDetailResponse,
    TranscriptResponse,
    EntityResponse,
    RelationResponse,
    GraphResponse,
    UserResponse
)
from app.services.audio_service import AudioService
from app.services.export_service import ExportService
from app.config import get_settings
import httpx

router = APIRouter()
audio_service = AudioService()
export_service = ExportService()
settings = get_settings()


@router.get("/calls", response_model=List[CallResponse])
async def get_calls(
    user_id: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of calls with metadata
    """
    try:
        query = select(Call).order_by(Call.start_time.desc())
        
        if user_id:
            query = query.where(Call.user_id == user_id)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        calls = result.scalars().all()
        
        return [CallResponse.model_validate(call) for call in calls]
        
    except Exception as e:
        print(f"Error getting calls: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving calls")


@router.get("/calls/{call_id}", response_model=CallDetailResponse)
async def get_call_details(
    call_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed call information with transcript
    """
    try:
        result = await db.execute(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.transcripts))
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Convert to response model
        call_data = CallResponse.model_validate(call)
        transcripts = [TranscriptResponse.model_validate(t) for t in call.transcripts]
        
        return CallDetailResponse(
            **call_data.model_dump(),
            transcripts=transcripts
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting call details: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving call details")


@router.get("/calls/{call_id}/audio")
async def get_call_audio(
    call_id: int,
    download: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audio file for download or streaming
    Returns the local audio file if available, otherwise the URL
    
    Args:
        call_id: The call ID
        download: If True, forces download. If False, streams in browser
    """
    try:
        result = await db.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Check for local audio file first
        local_path = audio_service.get_audio_file_path(call_id)
        
        if local_path and os.path.exists(local_path):
            # Determine media type from file extension
            ext = os.path.splitext(local_path)[1].lower()
            media_types = {
                '.wav': 'audio/wav',
                '.mp3': 'audio/mpeg',
                '.m4a': 'audio/mp4',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac'
            }
            media_type = media_types.get(ext, 'audio/wav')
            
            # Get filename for download
            filename = f"echodiary_call_{call_id}{ext}"
            
            # Serve local file
            return FileResponse(
                local_path,
                media_type=media_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{filename}"'
                }
            )
        
        # Fallback to URL if available
        if call.audio_url:
            return {"audio_url": call.audio_url, "local": False}
        
        raise HTTPException(status_code=404, detail="No audio recording available for this call")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting audio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error retrieving audio: {str(e)}")


@router.get("/calls/{call_id}/export/text")
async def export_transcript_text(
    call_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Export conversation transcript as clean formatted text
    """
    try:
        # Get call with transcripts
        result = await db.execute(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.transcripts))
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if not call.transcripts:
            raise HTTPException(status_code=404, detail="No transcript available")
        
        # Format transcript
        formatted_text = export_service.format_transcript_text(call, call.transcripts)
        filename = export_service.get_filename(call, "txt")
        
        return PlainTextResponse(
            content=formatted_text,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting transcript: {e}")
        raise HTTPException(status_code=500, detail="Error exporting transcript")


@router.get("/calls/{call_id}/export/markdown")
async def export_transcript_markdown(
    call_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Export conversation transcript as Markdown
    """
    try:
        # Get call with transcripts
        result = await db.execute(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.transcripts))
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if not call.transcripts:
            raise HTTPException(status_code=404, detail="No transcript available")
        
        # Format transcript
        formatted_md = export_service.format_transcript_markdown(call, call.transcripts)
        filename = export_service.get_filename(call, "md")
        
        return PlainTextResponse(
            content=formatted_md,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting transcript: {e}")
        raise HTTPException(status_code=500, detail="Error exporting transcript")


@router.get("/graph", response_model=GraphResponse)
async def get_knowledge_graph(
    user_id: Optional[int] = None,
    limit_nodes: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db)
):
    """
    Get knowledge graph nodes and edges for visualization
    """
    try:
        # Get entities (nodes)
        entity_query = select(Entity).limit(limit_nodes)
        if user_id:
            entity_query = entity_query.where(Entity.user_id == user_id)
        
        entity_result = await db.execute(entity_query)
        entities = entity_result.scalars().all()
        
        # Get relations (edges) for these entities
        entity_ids = [e.id for e in entities]
        if entity_ids:
            relation_query = select(Relation).where(
                Relation.entity1_id.in_(entity_ids),
                Relation.entity2_id.in_(entity_ids)
            ).options(
                selectinload(Relation.entity1),
                selectinload(Relation.entity2)
            )
            
            relation_result = await db.execute(relation_query)
            relations = relation_result.scalars().all()
        else:
            relations = []
        
        # Convert to response models
        nodes = [EntityResponse.model_validate(e) for e in entities]
        edges = [RelationResponse.model_validate(r) for r in relations]
        
        return GraphResponse(nodes=nodes, edges=edges)
        
    except Exception as e:
        print(f"Error getting graph: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving knowledge graph")


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user profile and stats
    """
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get call count
        count_result = await db.execute(
            select(func.count(Call.id)).where(Call.user_id == user_id)
        )
        call_count = count_result.scalar()
        
        user_data = UserResponse.model_validate(user)
        user_data.total_calls = call_count
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving user profile")


@router.post("/reflection/{call_id}")
async def generate_reflection(
    call_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate 20-second reflection recap for a call
    Returns text recap (audio generation via Rime/Layercode handled separately)
    """
    try:
        # Get call with transcripts
        result = await db.execute(
            select(Call)
            .where(Call.id == call_id)
            .options(selectinload(Call.transcripts))
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Combine transcript text
        full_text = "\n".join([
            f"{t.speaker}: {t.text}"
            for t in call.transcripts
        ])
        
        if not full_text:
            raise HTTPException(status_code=400, detail="No transcript available")
        
        # Generate reflection using OpenAI
        from app.services.openai_service import OpenAIService
        openai_service = OpenAIService()
        
        reflection_prompt = f"""
Create a 20-second (about 50 words) empathetic reflection recap of this diary conversation.
Summarize key feelings, topics, and provide a warm closing thought.

Conversation:
{full_text}

Make it feel like a gentle, caring voice companion speaking directly to the user.
Keep it under 50 words for a 20-second audio clip.
"""
        
        reflection_text = await openai_service.generate_response(
            transcript=reflection_prompt,
            context=[],
            mode="reassure"
        )
        
        # Store reflection in call record
        call.summary = reflection_text
        await db.commit()
        
        return {
            "reflection": reflection_text,
            "status": "completed",
            "call_id": call_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating reflection: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating reflection: {str(e)}")


@router.get("/stats/{user_id}")
async def get_user_stats(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user statistics and mood trends
    """
    try:
        # Get average mood score
        mood_result = await db.execute(
            select(func.avg(Call.mood_score))
            .where(Call.user_id == user_id, Call.mood_score.isnot(None))
        )
        avg_mood = mood_result.scalar() or 5.0
        
        # Get total calls
        count_result = await db.execute(
            select(func.count(Call.id)).where(Call.user_id == user_id)
        )
        total_calls = count_result.scalar()
        
        # Get recent calls for trend
        recent_result = await db.execute(
            select(Call.mood_score, Call.start_time)
            .where(Call.user_id == user_id, Call.mood_score.isnot(None))
            .order_by(Call.start_time.desc())
            .limit(10)
        )
        recent_moods = [
            {"mood": row[0], "date": row[1].isoformat()}
            for row in recent_result.all()
        ]
        
        return {
            "total_calls": total_calls,
            "average_mood": round(avg_mood, 2),
            "mood_trend": recent_moods
        }
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")


@router.get("/config")
async def get_frontend_config():
    """
    Get configuration for frontend (non-sensitive data only)
    """
    return {
        "layercode_agent_id": settings.layercode_agent_id,
        "app_name": settings.app_name,
        "app_version": settings.app_version
    }


@router.post("/authorize")
async def authorize_layercode_session(request: dict):
    """
    Authorization endpoint for Layercode Web SDK
    
    This endpoint is called by the Layercode JS SDK to get a client_session_key.
    It acts as a secure proxy between the frontend and Layercode API.
    
    Based on: https://docs.layercode.com/sdk-reference/vanilla-js-sdk
    """
    try:
        # Validate API key is configured
        if not settings.layercode_api_key:
            raise HTTPException(
                status_code=500, 
                detail="Layercode API key not configured"
            )
        
        # The JS SDK will send agent_id, metadata, etc.
        agent_id = request.get("agent_id") or settings.layercode_agent_id
        
        if not agent_id:
            raise HTTPException(
                status_code=400,
                detail="agent_id is required"
            )
        
        # Call Layercode authorization API
        layercode_auth_url = "https://api.layercode.com/v1/agents/web/authorize_session"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                layercode_auth_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.layercode_api_key}"
                },
                json=request
            )
            
            if not response.is_success:
                error_text = response.text
                print(f"❌ Layercode authorization failed: {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Layercode authorization failed: {error_text}"
                )
            
            auth_data = response.json()
            print(f"✅ Layercode session authorized: {auth_data.get('conversation_id', 'new session')}")
            
            return auth_data
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in Layercode authorization: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Authorization error: {str(e)}"
        )

