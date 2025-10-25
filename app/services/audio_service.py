"""
Audio file management service
Handles downloading and storing audio recordings from Layercode
"""
import os
import httpx
from pathlib import Path
from typing import Optional
from app.config import get_settings

settings = get_settings()


class AudioService:
    """Service for managing audio recordings"""
    
    def __init__(self):
        self.storage_path = Path(settings.audio_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    async def download_audio(self, audio_url: str, call_id: int) -> Optional[str]:
        """
        Download audio file from URL and save locally
        
        Args:
            audio_url: URL to download audio from (provided by Layercode/Twilio)
            call_id: Call ID for filename
            
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            # Determine file extension from URL or default to .wav
            ext = self._get_extension_from_url(audio_url) or ".wav"
            filename = f"call_{call_id}{ext}"
            filepath = self.storage_path / filename
            
            # Download audio file
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(audio_url, follow_redirects=True)
                response.raise_for_status()
                
                # Save to file
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                print(f"✅ Audio downloaded: {filepath}")
                return str(filepath)
                
        except Exception as e:
            print(f"❌ Error downloading audio: {e}")
            return None
    
    def _get_extension_from_url(self, url: str) -> Optional[str]:
        """Extract file extension from URL"""
        try:
            # Common audio extensions
            extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
            url_lower = url.lower()
            
            for ext in extensions:
                if ext in url_lower:
                    return ext
            
            return None
        except:
            return None
    
    def get_audio_file_path(self, call_id: int) -> Optional[str]:
        """
        Get local audio file path for a call if it exists
        
        Args:
            call_id: Call ID
            
        Returns:
            File path if exists, None otherwise
        """
        # Check for common extensions
        extensions = ['.wav', '.mp3', '.m4a', '.ogg']
        
        for ext in extensions:
            filename = f"call_{call_id}{ext}"
            filepath = self.storage_path / filename
            
            if filepath.exists():
                return str(filepath)
        
        return None
    
    def delete_audio_file(self, call_id: int) -> bool:
        """
        Delete audio file for a call
        
        Args:
            call_id: Call ID
            
        Returns:
            True if deleted, False otherwise
        """
        filepath = self.get_audio_file_path(call_id)
        
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"🗑️ Deleted audio file: {filepath}")
                return True
            except Exception as e:
                print(f"❌ Error deleting audio: {e}")
                return False
        
        return False

