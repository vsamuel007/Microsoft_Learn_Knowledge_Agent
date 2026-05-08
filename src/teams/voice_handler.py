"""Voice helper for the Teams bot, independent of the removed legacy orchestrator."""
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional

try:
    import azure.cognitiveservices.speech as speechsdk
    _SPEECH_SDK_AVAILABLE = True
except ImportError:
    speechsdk = None  # type: ignore[assignment]
    _SPEECH_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


class VoiceHandler:
    """
    Handles voice interactions in Microsoft Teams.

    This helper only converts audio and lightweight intents. The Teams bot now routes
    resulting commands directly to MCP-based Foundry agents.
    """
    
    def __init__(self, speech_key: Optional[str] = None, speech_region: Optional[str] = None):
        """
        Initialize voice handler with Azure Speech Service credentials.

        Credentials can be passed directly or loaded from environment variables
        SPEECH_KEY and SPEECH_REGION as fallback.

        Args:
            speech_key: Azure Speech Service API key
            speech_region: Azure Speech Service region
        """
        self.speech_key = speech_key or os.getenv("SPEECH_KEY")
        self.speech_region = speech_region or os.getenv("SPEECH_REGION")
        self.speech_config = None

        if self.speech_key and self.speech_region:
            self._initialize_speech_config()
    
    def _initialize_speech_config(self):
        """Initialize Azure Speech SDK configuration."""
        if not _SPEECH_SDK_AVAILABLE:
            logger.warning("azure-cognitiveservices-speech is not installed; voice features disabled.")
            return

        try:
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                region=self.speech_region,
            )
            # Configure default neural voice
            self.speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            logger.info("Speech configuration initialized successfully")
        except Exception as e:
            logger.error("Error initializing speech config: %s", e)
            self.speech_config = None
    
    async def transcribe_audio(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Transcribe audio input to text.

        Args:
            audio_data: Raw audio bytes (PCM 16-bit 16 kHz mono recommended)

        Returns:
            Dictionary with transcription result
        """
        if not self.speech_config:
            return {"success": False, "error": "Speech service not configured"}

        try:
            # Feed raw bytes into a push stream so the SDK reads from memory
            push_stream = speechsdk.audio.PushAudioInputStream()
            push_stream.write(audio_data)
            push_stream.close()
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config,
            )

            # Run the blocking SDK call off the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, speech_recognizer.recognize_once)

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Extract confidence from JSON result property
                json_str = result.properties.get_property(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult
                )
                confidence = None
                if json_str:
                    nbest = json.loads(json_str).get("NBest", [])
                    confidence = nbest[0].get("Confidence") if nbest else None

                return {"success": True, "text": result.text, "confidence": confidence}

            elif result.reason == speechsdk.ResultReason.NoMatch:
                return {"success": False, "error": "No speech could be recognized"}

            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                return {"success": False, "error": f"Speech recognition canceled: {cancellation.reason}"}

            return {"success": False, "error": "Unhandled recognition result"}

        except Exception as e:
            logger.error("Error in speech transcription: %s", e)
            return {"success": False, "error": str(e)}
    
    async def synthesize_speech(self, text: str) -> Dict[str, Any]:
        """
        Convert text to speech.

        Args:
            text: Text to convert to speech

        Returns:
            Dictionary with synthesis result
        """
        if not self.speech_config:
            return {"success": False, "error": "Speech service not configured"}

        try:
            # Output to memory (no speaker/file) so we can return raw audio bytes
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None,
            )

            # speak_text_async returns a ResultFuture; resolve off the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: speech_synthesizer.speak_text_async(text).get()
            )

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return {"success": True, "audio_data": result.audio_data}

            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                return {"success": False, "error": f"Speech synthesis canceled: {cancellation.reason}"}

            return {"success": False, "error": "Unhandled synthesis result"}

        except Exception as e:
            logger.error("Error in speech synthesis: %s", e)
            return {"success": False, "error": str(e)}
    
    def process_voice_command(self, command_text: str) -> Dict[str, Any]:
        """
        Process voice command and extract intent
        
        Args:
            command_text: Transcribed voice command
            
        Returns:
            Dictionary with intent and parameters
        """
        command_lower = command_text.lower()
        
        # Simple intent recognition (in production, use LUIS or similar)
        if "create" in command_lower and "learning path" in command_lower:
            return {
                "intent": "create_learning_path",
                "parameters": {
                    "role": self._extract_role(command_text)
                }
            }
        
        elif "my skills" in command_lower or "show skills" in command_lower:
            return {
                "intent": "view_skills",
                "parameters": {}
            }
        
        elif "search" in command_lower or "find" in command_lower or "learn" in command_lower:
            return {
                "intent": "search_resources",
                "parameters": {
                    "query": self._extract_search_query(command_text)
                }
            }
        
        else:
            return {
                "intent": "unknown",
                "parameters": {
                    "raw_text": command_text
                }
            }
    
    @staticmethod
    def _extract_role(text: str) -> str:
        """Extract role name from command text."""
        match = re.search(r'for (.+)', text, re.IGNORECASE)
        return match.group(1).strip() if match else ""
    
    @staticmethod
    def _extract_search_query(text: str) -> str:
        """Extract search query from command text."""
        patterns = [
            r'learn (?:about )?(.+)',
            r'find (.+)',
            r'search for (.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return text


# Example usage
async def example_voice_interaction():
    """Example of voice interaction."""
    voice_handler = VoiceHandler(
        speech_key=os.getenv("SPEECH_KEY"),
        speech_region=os.getenv("SPEECH_REGION", "eastus"),
    )
    
    # Transcribe audio
    # audio_data = load_audio_file("user_command.wav")
    # transcription = await voice_handler.transcribe_audio(audio_data)
    # print(f"Transcribed: {transcription}")
    
    # Process command
    command = "Create learning path for Azure Solutions Architect"
    intent = voice_handler.process_voice_command(command)
    print(f"Intent: {intent}")

    # Synthesize response
    response_text = "I'm sending your request to LearningPathAgent. This will take a moment."
    synthesis = await voice_handler.synthesize_speech(response_text)
    print(f"Synthesis result: {synthesis['success']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_voice_interaction())