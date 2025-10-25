"""
Export service for transcripts and diary entries
Handles formatting and exporting conversation data
"""
from datetime import datetime
from typing import List
from app.models import Call, Transcript


class ExportService:
    """Service for exporting transcripts and diary entries"""
    
    @staticmethod
    def format_transcript_text(call: Call, transcripts: List[Transcript]) -> str:
        """
        Format transcript as clean, diary-style text
        
        Args:
            call: Call object
            transcripts: List of transcript entries
            
        Returns:
            Formatted text string
        """
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("ECHODIARY CONVERSATION")
        lines.append("=" * 60)
        lines.append("")
        
        # Metadata
        lines.append(f"Date: {call.start_time.strftime('%B %d, %Y at %I:%M %p')}")
        
        if call.duration_seconds:
            minutes = call.duration_seconds // 60
            seconds = call.duration_seconds % 60
            lines.append(f"Duration: {minutes}m {seconds}s")
        
        if call.mood_score:
            lines.append(f"Mood Score: {call.mood_score}/10")
        
        if call.mode:
            mode_names = {
                "reassure": "Reassurance Mode",
                "tough_love": "Tough Love Mode",
                "listener": "Listener Mode"
            }
            lines.append(f"Mode: {mode_names.get(call.mode, call.mode)}")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("CONVERSATION")
        lines.append("-" * 60)
        lines.append("")
        
        # Transcript
        for t in transcripts:
            speaker_label = "You" if t.speaker == "user" else "EchoDiary"
            timestamp = t.timestamp.strftime("%I:%M %p")
            
            lines.append(f"[{timestamp}] {speaker_label}:")
            lines.append(f"  {t.text}")
            lines.append("")
        
        # Summary
        if call.summary:
            lines.append("-" * 60)
            lines.append("REFLECTION")
            lines.append("-" * 60)
            lines.append("")
            lines.append(call.summary)
            lines.append("")
        
        # Tags
        if call.tags:
            lines.append("-" * 60)
            lines.append("TOPICS")
            lines.append("-" * 60)
            lines.append("")
            lines.append(", ".join(call.tags))
            lines.append("")
        
        # Footer
        lines.append("=" * 60)
        lines.append("End of conversation")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_transcript_markdown(call: Call, transcripts: List[Transcript]) -> str:
        """
        Format transcript as Markdown
        
        Args:
            call: Call object
            transcripts: List of transcript entries
            
        Returns:
            Formatted Markdown string
        """
        lines = []
        
        # Header
        lines.append("# 🎙️ EchoDiary Conversation")
        lines.append("")
        lines.append(f"**Date:** {call.start_time.strftime('%B %d, %Y at %I:%M %p')}")
        
        if call.duration_seconds:
            minutes = call.duration_seconds // 60
            seconds = call.duration_seconds % 60
            lines.append(f"**Duration:** {minutes}m {seconds}s")
        
        if call.mood_score:
            # Add mood emoji
            mood_emoji = "😊" if call.mood_score >= 7 else "😐" if call.mood_score >= 4 else "😔"
            lines.append(f"**Mood:** {mood_emoji} {call.mood_score}/10")
        
        if call.mode:
            mode_names = {
                "reassure": "💙 Reassurance",
                "tough_love": "💪 Tough Love",
                "listener": "👂 Listener"
            }
            lines.append(f"**Mode:** {mode_names.get(call.mode, call.mode)}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Transcript
        lines.append("## Conversation")
        lines.append("")
        
        for t in transcripts:
            speaker_label = "**You**" if t.speaker == "user" else "*EchoDiary*"
            timestamp = t.timestamp.strftime("%I:%M %p")
            
            lines.append(f"**[{timestamp}]** {speaker_label}")
            lines.append(f"> {t.text}")
            lines.append("")
        
        # Summary
        if call.summary:
            lines.append("---")
            lines.append("")
            lines.append("## 💭 Reflection")
            lines.append("")
            lines.append(call.summary)
            lines.append("")
        
        # Tags
        if call.tags:
            lines.append("---")
            lines.append("")
            lines.append("## 🏷️ Topics")
            lines.append("")
            lines.append(" · ".join([f"`{tag}`" for tag in call.tags]))
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def get_filename(call: Call, format: str = "txt") -> str:
        """
        Generate filename for export
        
        Args:
            call: Call object
            format: File format (txt, md, json)
            
        Returns:
            Filename string
        """
        date_str = call.start_time.strftime("%Y%m%d_%H%M%S")
        return f"echodiary_conversation_{date_str}.{format}"

