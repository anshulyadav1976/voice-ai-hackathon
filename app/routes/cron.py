"""
Cron and scheduled task endpoints
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
from typing import List

from app.database import get_db
from app.models import CheckIn, User, Call
from app.redis_client import redis_client
from app.services.openai_service import OpenAIService
from app.config import get_settings

router = APIRouter()
settings = get_settings()

openai_service = OpenAIService()

# Note: Check-in delivery (SMS/calls) now handled via Layercode API
# See LAYERCODE_SETUP.md for outbound call configuration


@router.post("/checkins")
async def process_checkins(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Process pending check-ins
    This endpoint should be called by a cron job every 15-30 minutes
    """
    try:
        # Get pending check-ins that are due
        result = await db.execute(
            select(CheckIn).where(
                and_(
                    CheckIn.status == "pending",
                    CheckIn.scheduled_time <= datetime.utcnow()
                )
            )
        )
        checkins = result.scalars().all()
        
        processed_count = 0
        for checkin in checkins:
            # Add background task to process each check-in
            background_tasks.add_task(process_checkin, checkin.id)
            processed_count += 1
        
        return {
            "status": "success",
            "checkins_queued": processed_count
        }
        
    except Exception as e:
        print(f"Error processing check-ins: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


async def process_checkin(checkin_id: int):
    """
    Background task to process a single check-in
    """
    from app.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # Get check-in
            result = await db.execute(
                select(CheckIn).where(CheckIn.id == checkin_id)
            )
            checkin = result.scalar_one_or_none()
            
            if not checkin or checkin.status != "pending":
                return
            
            # Get user
            user_result = await db.execute(
                select(User).where(User.id == checkin.user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                checkin.status = "failed"
                await db.commit()
                return
            
            # Generate personalized check-in message
            message = await generate_checkin_message(checkin, user)
            
            # TODO: Integrate with Layercode for outbound SMS/calls
            # For now, we'll just log the check-in and mark as completed
            
            print(f"📞 Check-in scheduled for {user.phone_number}")
            print(f"💬 Message: {message}")
            print(f"📋 Method: {checkin.delivery_method}")
            
            # In production, call Layercode API here to trigger outbound call/SMS
            # Example:
            # if checkin.delivery_method == "sms":
            #     await layercode_api.send_sms(user.phone_number, message)
            # elif checkin.delivery_method == "call":
            #     await layercode_api.trigger_outbound_call(user.phone_number, message)
            
            # Mark as completed (in production, only after successful delivery)
            checkin.status = "completed"
            checkin.message = message
            checkin.completed_at = datetime.utcnow()
            checkin.success = True
            
            await db.commit()
            
        except Exception as e:
            print(f"Error processing check-in {checkin_id}: {e}")


async def generate_checkin_message(checkin: CheckIn, user: User) -> str:
    """
    Generate personalized check-in message using OpenAI
    """
    try:
        # Get user profile from Redis
        user_profile = await redis_client.get_user_profile(user.id)
        
        prompt = f"""
Generate a brief, caring check-in message for a user named {user.name or 'friend'}.

Context: {checkin.reason}

The message should:
- Be warm and genuine
- Reference the context briefly
- Show you care
- Be under 100 words for SMS

Return only the message text, no quotes or formatting.
"""
        
        context = []
        if user_profile:
            context = [{"speaker": "system", "text": f"User baseline mood: {user_profile.get('baseline_mood', 5)}"}]
        
        message = await openai_service.generate_response(
            transcript=prompt,
            context=context,
            mode="reassure"
        )
        
        return message
        
    except Exception as e:
        print(f"Error generating check-in message: {e}")
        return f"Hi! Just checking in on you. Hope you're doing okay. Reply anytime if you want to talk. - EchoDiary"


@router.post("/cleanup")
async def cleanup_old_sessions():
    """
    Clean up expired Redis sessions
    This can be called periodically
    """
    try:
        # Redis handles TTL automatically, but we can do manual cleanup if needed
        return {"status": "success", "message": "Cleanup completed"}
        
    except Exception as e:
        print(f"Error in cleanup: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/health")
async def cron_health():
    """
    Health check for cron system
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

