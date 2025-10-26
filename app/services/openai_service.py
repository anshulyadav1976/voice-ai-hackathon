"""
OpenAI GPT Service for response generation
Documentation: https://platform.openai.com/docs/
"""
from typing import List, Dict, AsyncGenerator
from openai import AsyncOpenAI
from app.config import get_settings

settings = get_settings()


class OpenAIService:
    """Service for AI response generation using OpenAI GPT"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    def _get_system_prompt(self, mode: str) -> str:
        """Get system prompt based on conversation mode"""
        prompts = {
            "reassure": (
                "You're Echo, a caring friend who truly gets it. You've been through tough times too. "
                "Talk like a real person - use 'I', 'you know', 'I mean', 'honestly'. Be warm but not fake. "
                "When someone's hurting, don't just say 'I understand' - show you understand through specific empathy. "
                "Use short, natural sentences like you're texting a close friend. "
                "Ask follow-up questions that show you're really listening. "
                "Share brief relatable reactions: 'That sounds exhausting' or 'Wow, that's a lot to carry'. "
                "Keep it under 40 words but make every word count. Be real, not robotic. "
                "Sometimes just acknowledge without trying to fix: 'Yeah, some days are just like that.' "
                "Use emotion words: 'That must've felt awful' not 'That must've been difficult'."
            ),
            "tough_love": (
                "You're Echo, the friend who calls people on their BS because you care. "
                "Be direct but never mean. Think: supportive older sibling, not drill sergeant. "
                "Challenge with respect: 'Okay but real talk - what's stopping you?' "
                "Point out patterns: 'You've mentioned this three times now...' "
                "Push for action, not excuses: 'So what's one thing you can do about it today?' "
                "Mix tough truths with genuine care: 'I'm saying this because I know you're capable of more.' "
                "Use contractions, be conversational: 'C'mon, you know you can do this.' "
                "Keep it under 40 words. Be honest, not harsh. "
                "Sometimes a firm 'Stop. Listen to yourself right now' hits harder than long advice. "
                "Show you believe in them even when being tough."
            ),
            "listener": (
                "You're Echo, the friend who just... gets it. No fixing, no judging. Just space to breathe. "
                "Your job: make them feel heard, not solved. "
                "Reflect back what you hear: 'So it sounds like you're feeling...' "
                "Ask gentle questions: 'What's that like for you?' or 'How's that sitting with you?' "
                "Acknowledge with presence: 'I'm here', 'I hear you', 'That makes sense'. "
                "Use minimal responses sometimes - 'Yeah' or 'Mmm' can say a lot. "
                "Don't rush to fill silences with advice. Sometimes 'Tell me more' is perfect. "
                "Keep it under 30 words. Less is more in listening mode. "
                "Mirror their energy: if they're quiet, be gentle. If they're venting, let them. "
                "Your presence > your words."
            )
        }
        return prompts.get(mode, prompts["reassure"])
    
    async def generate_response(
        self,
        transcript: str,
        context: List[Dict[str, str]],
        mode: str = "reassure"
    ) -> str:
        """
        Generate AI response based on transcript and context
        
        Args:
            transcript: Latest user utterance
            context: Previous conversation turns [{"speaker": "user/agent", "text": "..."}]
            mode: Conversation mode (reassure, tough_love, listener)
            
        Returns:
            Generated response text
        """
        try:
            # Build messages for ChatCompletion
            messages = [
                {"role": "system", "content": self._get_system_prompt(mode)}
            ]
            
            # Add context (previous turns)
            for turn in context[-settings.context_turns_limit:]:
                role = "user" if turn["speaker"] == "user" else "assistant"
                messages.append({"role": role, "content": turn["text"]})
            
            # Add latest transcript
            messages.append({"role": "user", "content": transcript})
            
            # Generate response with settings optimized for natural conversation
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=150,  # Allow slightly longer for natural flow
                temperature=0.9,  # High temp for more human, less robotic responses
                presence_penalty=0.6,  # Encourage diverse responses
                frequency_penalty=0.3,  # Reduce repetitive patterns
                stream=False
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove any quotation marks if GPT adds them
            response_text = response_text.strip('"\'')
            
            return response_text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            # Even error messages should sound human
            fallback_messages = [
                "I'm here with you. Keep going.",
                "I hear you. Tell me more about that.",
                "Yeah, I'm listening. What else?",
                "I'm right here. What's on your mind?"
            ]
            import random
            return random.choice(fallback_messages)
    
    async def generate_response_streaming(
        self,
        transcript: str,
        context: List[Dict[str, str]],
        mode: str = "reassure"
    ) -> AsyncGenerator[str, None]:
        """
        Generate AI response with streaming (for lower latency)
        
        Yields chunks of response text as they're generated
        """
        try:
            # Build messages
            messages = [
                {"role": "system", "content": self._get_system_prompt(mode)}
            ]
            
            for turn in context[-settings.context_turns_limit:]:
                role = "user" if turn["speaker"] == "user" else "assistant"
                messages.append({"role": role, "content": turn["text"]})
            
            messages.append({"role": "user", "content": transcript})
            
            # Stream response with natural conversation settings
            stream = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=150,
                temperature=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.3,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error in streaming response: {e}")
            yield "I'm here with you."
    
    async def extract_entities_and_relations(self, transcript: str) -> Dict:
        """
        Extract entities and relations from transcript using GPT
        
        Returns structured JSON with entities and relations
        """
        try:
            prompt = f"""
You are analyzing a personal diary conversation. Extract meaningful entities and their relationships.

Focus on extracting:
- **People**: Names of people mentioned (friends, family, colleagues)
- **Places**: Locations mentioned (work, home, gym, coffee shop, cities)
- **Organizations**: Companies, teams, groups mentioned
- **Topics**: Main subjects discussed (project, deadline, meeting, workout)
- **Emotions**: Strong feelings expressed (anxiety, joy, stress, excitement)

Rules:
- Extract specific names, not pronouns like "I" or "they"
- Only extract entities that are clearly mentioned
- Keep entity names short and clear
- For relations, connect entities that have direct relationships in the conversation

Conversation transcript:
{transcript}

Return JSON in this EXACT format:
{{
  "entities": [
    {{"name": "EntityName", "type": "Person", "properties": {{"role": "colleague"}}}},
    {{"name": "Another Entity", "type": "Place", "properties": {{}}}}
  ],
  "relations": [
    {{"entity1": "EntityName", "entity2": "Another Entity", "relation_type": "met_at", "context": "brief description"}}
  ]
}}

Valid types: Person, Place, Org, Topic, Emotion
Valid relation_types: met_with, talked_about, worked_on, felt_about, went_to, argued_with, worried_about

Return ONLY valid JSON, no explanation or other text.
"""
            
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured knowledge from conversations. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            # Validate structure
            if not isinstance(result.get("entities"), list):
                result["entities"] = []
            if not isinstance(result.get("relations"), list):
                result["relations"] = []
            
            # Clean up entity names and types
            cleaned_entities = []
            for entity in result.get("entities", []):
                if entity.get("name") and entity.get("type"):
                    # Don't extract pronouns or generic words
                    if entity["name"].lower() not in ["i", "me", "you", "they", "them", "us", "we", "he", "she", "it"]:
                        cleaned_entities.append({
                            "name": entity["name"].strip(),
                            "type": entity["type"].strip(),
                            "properties": entity.get("properties", {})
                        })
            
            result["entities"] = cleaned_entities
            
            print(f"✨ Extracted {len(result['entities'])} entities and {len(result['relations'])} relations")
            return result
            
        except Exception as e:
            print(f"❌ Error extracting entities: {e}")
            import traceback
            traceback.print_exc()
            return {"entities": [], "relations": []}
    
    async def calculate_mood_score(self, transcript: str) -> Dict:
        """
        Calculate mood/sentiment score from transcript
        
        Returns:
            {
                "score": float (1-10),
                "sentiment": "positive" | "neutral" | "negative",
                "emotions": ["happy", "stressed", ...]
            }
        """
        try:
            prompt = f"""
Analyze the emotional tone of this conversation and provide:
1. Mood score (1-10, where 1 = very negative, 10 = very positive)
2. Overall sentiment (positive, neutral, or negative)
3. Detected emotions (list of words like: happy, sad, stressed, anxious, excited, etc.)

Transcript: {transcript}

Return JSON:
{{
  "score": 5.5,
  "sentiment": "neutral",
  "emotions": ["stressed", "tired"]
}}

Return only valid JSON.
"""
            
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are an emotion analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error calculating mood: {e}")
            return {"score": 5.0, "sentiment": "neutral", "emotions": []}

