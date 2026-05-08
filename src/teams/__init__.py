"""
Microsoft Teams integration module for the Learning Path system.

This module provides:
- AdaptiveCardBuilder: Rich card builders for bot responses
- LearningPathBot: Main activity handler for Microsoft Teams
- VoiceHandler: Voice interaction support
"""

from .adaptive_cards import AdaptiveCardBuilder
from .app import create_app
from .bot import LearningPathBot, create_bot
from .voice_handler import VoiceHandler

__all__ = ["AdaptiveCardBuilder", "LearningPathBot", "VoiceHandler", "create_bot", "create_app"]
