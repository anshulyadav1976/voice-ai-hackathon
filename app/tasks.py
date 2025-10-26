"""
Background task handlers for EchoDiary
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import List, Dict

from app.database import AsyncSessionLocal
from app.models import Call, Transcript, Entity, Relation, CheckIn, User
from app.services.openai_service import OpenAIService
from app.redis_client import redis_client
from app.config import get_settings

settings = get_settings()
openai_service = OpenAIService()


async def extract_and_store_entities(call_id: int, transcript_text: str):
    """
    Extract entities and relations from transcript and store in database
    """
    print(f"\n🔍 Starting entity extraction for call {call_id}")
    print(f"📝 Transcript length: {len(transcript_text)} characters")
    
    async with AsyncSessionLocal() as db:
        try:
            # Get call
            result = await db.execute(
                select(Call).where(Call.id == call_id)
            )
            call = result.scalar_one_or_none()
            
            if not call:
                print(f"❌ Call {call_id} not found in database")
                return
            
            print(f"📞 Processing call for user {call.user_id}")
            
            # Extract entities and relations using GPT
            print("🤖 Calling OpenAI for entity extraction...")
            extracted = await openai_service.extract_entities_and_relations(transcript_text)
            
            print(f"📊 Extracted data: {len(extracted.get('entities', []))} entities, {len(extracted.get('relations', []))} relations")
            
            if extracted.get("entities"):
                for e in extracted["entities"]:
                    print(f"  - Entity: {e.get('name')} ({e.get('type')})")
            
            # Store entities
            entity_map = {}  # name -> entity_id
            
            for entity_data in extracted.get("entities", []):
                # Check if entity already exists for this user
                existing_result = await db.execute(
                    select(Entity).where(
                        Entity.user_id == call.user_id,
                        Entity.name == entity_data["name"],
                        Entity.entity_type == entity_data["type"]
                    )
                )
                existing_entity = existing_result.scalar_one_or_none()
                
                if existing_entity:
                    # Update existing entity
                    existing_entity.mention_count += 1
                    existing_entity.last_mentioned = datetime.utcnow()
                    if entity_data.get("properties"):
                        existing_entity.properties = entity_data["properties"]
                    entity_map[entity_data["name"]] = existing_entity.id
                    print(f"  ↻ Updated existing entity: {entity_data['name']}")
                else:
                    # Create new entity
                    new_entity = Entity(
                        user_id=call.user_id,
                        name=entity_data["name"],
                        entity_type=entity_data["type"],
                        properties=entity_data.get("properties", {})
                    )
                    db.add(new_entity)
                    await db.flush()
                    entity_map[entity_data["name"]] = new_entity.id
                    print(f"  ✨ Created new entity: {entity_data['name']}")
            
            await db.commit()
            print(f"💾 Committed {len(entity_map)} entities to database")
            
            # Store relations
            relations_added = 0
            for relation_data in extracted.get("relations", []):
                entity1_name = relation_data.get("entity1")
                entity2_name = relation_data.get("entity2")
                
                if entity1_name in entity_map and entity2_name in entity_map:
                    relation = Relation(
                        call_id=call_id,
                        entity1_id=entity_map[entity1_name],
                        entity2_id=entity_map[entity2_name],
                        relation_type=relation_data["relation_type"],
                        context=relation_data.get("context", "")
                    )
                    db.add(relation)
                    relations_added += 1
                    print(f"  🔗 Added relation: {entity1_name} -{relation_data['relation_type']}-> {entity2_name}")
            
            await db.commit()
            print(f"✅ Entity extraction complete for call {call_id}: {len(entity_map)} entities, {relations_added} relations\n")
            
        except Exception as e:
            print(f"❌ Error extracting entities for call {call_id}: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()


async def calculate_and_store_mood(call_id: int, transcript_text: str):
    """
    Calculate mood score from transcript and update call record
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get call
            result = await db.execute(
                select(Call).where(Call.id == call_id)
            )
            call = result.scalar_one_or_none()
            
            if not call:
                return
            
            # Calculate mood using GPT
            mood_data = await openai_service.calculate_mood_score(transcript_text)
            
            # Update call record
            call.mood_score = mood_data.get("score", 5.0)
            call.sentiment = mood_data.get("sentiment", "neutral")
            call.tags = mood_data.get("emotions", [])
            
            await db.commit()
            
            print(f"✅ Mood score for call {call_id}: {call.mood_score}")
            
            # Check if we need to schedule a check-in
            if call.mood_score < settings.mood_negative_threshold:
                await schedule_checkin(call, mood_data)
            
        except Exception as e:
            print(f"Error calculating mood: {e}")
            await db.rollback()


async def schedule_checkin(call: Call, mood_data: Dict):
    """
    Schedule a check-in for a user based on low mood score
    """
    async with AsyncSessionLocal() as db:
        try:
            # Calculate check-in time (default: 24 hours later)
            checkin_time = datetime.utcnow() + timedelta(hours=settings.checkin_delay_hours)
            
            # Create check-in record
            checkin = CheckIn(
                user_id=call.user_id,
                call_id=call.id,
                scheduled_time=checkin_time,
                reason=f"Low mood detected (score: {call.mood_score}). Emotions: {', '.join(mood_data.get('emotions', []))}",
                delivery_method="sms"  # Default to SMS
            )
            db.add(checkin)
            await db.commit()
            
            # Also set flag in Redis for quick lookup
            await redis_client.set_checkin_flag(
                call.user_id,
                {
                    "checkin_id": checkin.id,
                    "scheduled_time": checkin_time.isoformat(),
                    "reason": checkin.reason
                }
            )
            
            print(f"✅ Scheduled check-in for user {call.user_id} at {checkin_time}")
            
        except Exception as e:
            print(f"Error scheduling check-in: {e}")
            await db.rollback()


async def generate_call_title(call_id: int, transcript_text: str):
    """
    Generate a short, descriptive title for the call using GPT
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get call
            result = await db.execute(
                select(Call).where(Call.id == call_id)
            )
            call = result.scalar_one_or_none()
            
            if not call:
                return
            
            # Generate title using GPT
            prompt = f"""
Generate a short, descriptive title (5-8 words max) for this diary conversation.
The title should capture the main topic or emotion discussed.

Examples of good titles:
- "Stressed about work deadline"
- "Excited about new promotion"
- "Worried about relationship with Sarah"
- "Feeling anxious about presentation"
- "Happy about gym progress"
- "Reflecting on family visit"

Conversation:
{transcript_text}

Return ONLY the title, nothing else. No quotes, no punctuation at the end.
"""
            
            title = await openai_service.generate_response(
                transcript=prompt,
                context=[],
                mode="listener"
            )
            
            # Clean up the title
            title = title.strip().strip('"').strip("'").strip('.')
            
            # Limit length
            if len(title) > 80:
                title = title[:77] + "..."
            
            call.summary = title
            await db.commit()
            
            print(f"✅ Generated title for call {call_id}: '{title}'")
            
        except Exception as e:
            print(f"❌ Error generating title: {e}")
            await db.rollback()

