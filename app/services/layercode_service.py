"""
Layercode Integration Service
Handles communication with Layercode for the voice pipeline
"""
from typing import Dict, Any, Optional
from app.config import get_settings

settings = get_settings()


class LayercodeService:
    """
    Service for Layercode webhook communication
    
    Layercode handles:
    - Twilio voice input
    - Deepgram STT
    - Rime TTS
    - Audio routing
    
    Our backend handles:
    - GPT-5 Nano responses
    - Database storage
    - Entity extraction
    - Business logic
    """
    
    def __init__(self):
        self.api_key = settings.layercode_api_key
    
    def format_response(
        self,
        text: str,
        emotion: str = "neutral",
        end_call: bool = False
    ) -> str:
        """
        Format response for Layercode
        
        Args:
            text: Response text to be spoken via Rime
            emotion: Voice emotion (warm, confident, calm, neutral)
            end_call: Whether to end the call after this response
            
        Returns:
            Just the text string - Layercode handles TTS automatically
        """
        # Layercode expects just the text response as a string
        # The TTS configuration is handled in the Layercode pipeline
        return text
    
    def get_emotion_for_mode(self, mode: str) -> str:
        """Map conversation mode to Rime emotion"""
        emotion_map = {
            "reassure": "warm",
            "tough_love": "confident",
            "listener": "calm"
        }
        return emotion_map.get(mode, "neutral")

