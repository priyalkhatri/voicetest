"""
LiveKit Voice Agent for handling phone calls
"""
import logging
import asyncio
from typing import Dict, Optional, Any
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice_assistant import VoiceAssistant, AssistantOptions, TranscriptionForwarder

from app.services.ai_agent import ai_agent
from app.services.speech_services import speech_services
from app.utils.logger import get_logger

logger = get_logger(__name__)

class SalonVoiceAgent:
    """
    Voice Agent for the AI receptionist
    Handles phone conversations using LiveKit Agents framework
    """
    
    def __init__(self):
        """Initialize the voice agent"""
        self.ai_agent = ai_agent
        self.active_assistants: Dict[str, VoiceAssistant] = {}
    
    async def entrypoint(self, ctx: JobContext):
        """
        Main entry point for the voice agent
        Called when a new phone call arrives
        """
        try:
            # Get the room and participant information
            room = ctx.room
            participant = await self._get_caller_participant(room)
            
            if not participant:
                logger.error("No caller participant found")
                return
            
            # Extract caller information from metadata
            metadata = self._parse_participant_metadata(participant)
            call_id = metadata.get("callId", f"call_{room.sid}")
            phone_number = metadata.get("from", "unknown")
            customer_id = phone_number.replace("+", "")
            
            logger.info(f"Starting voice agent for call {call_id} from {phone_number}")
            
            # Create a new call record
            call_record = await self.ai_agent.handle_incoming_call(
                call_id, customer_id, phone_number
            )
            
            if not call_record:
                logger.error(f"Failed to create call record for {call_id}")
                return
            
            # Set up the voice assistant
            assistant = await self._create_voice_assistant(ctx, call_id)
            self.active_assistants[call_id] = assistant
            
            # Start the conversation
            await assistant.start(room)
            
            # Greet the caller
            greeting = f"Thank you for calling {self.ai_agent.salon_info['name']}. How can I help you today?"
            await assistant.say(greeting)
            
            # Wait for the conversation to end
            await self._handle_conversation(ctx, assistant, call_id)
            
        except Exception as e:
            logger.error(f"Error in voice agent: {e}", exc_info=True)
        finally:
            # Clean up
            if call_id in self.active_assistants:
                del self.active_assistants[call_id]
    
    async def _get_caller_participant(self, room: rtc.Room) -> Optional[rtc.RemoteParticipant]:
        """Get the caller participant from the room"""
        # In telephony, the caller is usually the first remote participant
        for participant in room.remote_participants.values():
            return participant
        return None
    
    def _parse_participant_metadata(self, participant: rtc.RemoteParticipant) -> Dict[str, Any]:
        """Parse metadata from the participant"""
        try:
            import json
            metadata = json.loads(participant.metadata) if participant.metadata else {}
            return metadata
        except Exception as e:
            logger.error(f"Error parsing participant metadata: {e}")
            return {}
    
    async def _create_voice_assistant(self, ctx: JobContext, call_id: str) -> VoiceAssistant:
        """Create and configure the voice assistant"""
        # Create a custom function handler for the AI
        async def llm_function(user_input: str) -> str:
            """Process user input and return AI response"""
            try:
                # Process the question through our AI agent
                result = await self.ai_agent.process_call_question(call_id, user_input)
                if result:
                    return result["answer"]
                else:
                    return "I'm sorry, I didn't understand that. Could you please repeat?"
            except Exception as e:
                logger.error(f"Error processing user input: {e}")
                return "I'm having trouble processing your request. Please try again."
        
        # Configure the voice assistant
        options = AssistantOptions(
            vad_enabled=True,  # Voice Activity Detection
            interrupt_speech=True,  # Allow interruptions
            transcription_speed=0.8,  # Slightly slower for phone quality
            loop_delay=0.3,  # Small delay between turns
        )
        
        # Create the voice assistant
        assistant = VoiceAssistant(
            llm=llm_function,
            tts=self._create_tts_function(),
            stt=self._create_stt_function(),
            options=options
        )
        
        # Add transcription forwarder for logging
        assistant.add_transcription_forwarder(
            TranscriptionForwarder(
                on_user_speech=lambda text: logger.info(f"User: {text}"),
                on_agent_speech=lambda text: logger.info(f"Agent: {text}")
            )
        )
        
        return assistant
    
    def _create_stt_function(self):
        """Create speech-to-text function for the voice assistant"""
        async def stt_function(audio_data: bytes) -> str:
            """Convert speech to text"""
            try:
                text = await speech_services.transcribe(audio_data, {
                    "model": "nova-2-phonecall",  # Optimized for phone calls
                    "language": "en-US"
                })
                return text
            except Exception as e:
                logger.error(f"STT error: {e}")
                return ""
        
        return stt_function
    
    def _create_tts_function(self):
        """Create text-to-speech function for the voice assistant"""
        async def tts_function(text: str) -> bytes:
            """Convert text to speech"""
            try:
                audio_data = await speech_services.synthesize_speech(text, {
                    "voice_id": "professional_female",  # Professional voice for business
                    "speed": 1.0
                })
                return audio_data
            except Exception as e:
                logger.error(f"TTS error: {e}")
                return b""
        
        return tts_function
    
    async def _handle_conversation(self, ctx: JobContext, assistant: VoiceAssistant, call_id: str):
        """Handle the ongoing conversation"""
        try:
            # Wait for the conversation to complete
            await assistant.join()
            
            # Calculate call duration
            duration_ms = assistant.get_duration_ms() if hasattr(assistant, 'get_duration_ms') else 0
            
            # Handle call ended
            await self.ai_agent.handle_call_ended(call_id, duration_ms)
            
            logger.info(f"Call {call_id} ended, duration: {duration_ms}ms")
            
        except Exception as e:
            logger.error(f"Error handling conversation: {e}")

# Create a global instance
voice_agent = SalonVoiceAgent()

# Worker options for LiveKit
worker_options = WorkerOptions(
    entrypoint_fnc=voice_agent.entrypoint,
    prewarm_fnc=lambda: logger.info("Voice agent prewarming...")
)

# Export the worker function for use with LiveKit CLI
def run_worker():
    """Run the voice agent worker"""
    cli.run_app(worker_options)

# For running the agent as a worker
if __name__ == "__main__":
    run_worker()