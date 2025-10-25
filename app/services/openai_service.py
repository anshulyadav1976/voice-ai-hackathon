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
                "You are a warm, caring, emotionally intelligent voice companion. "
                "Your role is to provide reassurance and emotional support. "
                "Listen deeply, validate feelings, and offer gentle encouragement. "
                "Keep responses under 50 words. Be empathetic and calming."
            ),
            "tough_love": (
                "You are a direct, honest, supportive voice companion. "
                "Your role is to provide tough love - be real and constructive. "
                "Challenge gently but firmly, encourage action and growth. "
                "Keep responses under 50 words. Be honest but caring."
            ),
            "listener": (
                "You are a patient, non-judgmental voice companion. "
                "Your role is to simply listen and acknowledge. "
                "Reflect back what you hear, ask gentle questions. "
                "Keep responses under 50 words. Be present and attentive."
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
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
                stream=False
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm here with you. Tell me more."
    
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
            
            # Stream response
            stream = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature,
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
Extract entities and relations from this conversation transcript.

Transcript: {transcript}

Return a JSON object with:
- "entities": list of {{name, type, properties}} where type is: Person, Place, Org, Topic, or Emotion
- "relations": list of {{entity1, entity2, relation_type}} where relation_type is: met_with, argued_with, worked_on, felt, or went_to

Example:
{{
  "entities": [
    {{"name": "Sarah", "type": "Person", "properties": {{"role": "colleague"}}}},
    {{"name": "stressed", "type": "Emotion", "properties": {{"intensity": "high"}}}}
  ],
  "relations": [
    {{"entity1": "I", "entity2": "Sarah", "relation_type": "argued_with"}}
  ]
}}

Return only valid JSON, no other text.
"""
            
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts structured data."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            import json
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error extracting entities: {e}")
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

