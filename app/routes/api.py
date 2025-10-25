"""
Web UI API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

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

router = APIRouter()


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
    db: AsyncSession = Depends(get_db)
):
    """
    Get audio URL for a call
    """
    try:
        result = await db.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if not call.audio_url:
            raise HTTPException(status_code=404, detail="No audio available")
        
        return {"audio_url": call.audio_url}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting audio: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving audio")


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

