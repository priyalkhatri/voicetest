"""
LiveKit Voice Agent for handling phone calls using the new Agent framework
"""
import os
import json
import logging
import asyncio
from typing import Dict, Optional, Any
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent, 
    AgentSession, 
    JobContext, 
    WorkerOptions, 
    cli,
    llm
)
from livekit.plugins import deepgram, openai, silero, neuphonic, groq

from app.config import settings
from app.services.ai_agent import ai_agent
from app.utils.logger import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class SalonReceptionist(Agent):
    """Voice agent for the salon that integrates with the knowledge base"""
    
    def __init__(self) -> None:
        # Create salon-specific instructions
        salon_info = settings.SALON_INFO
        
        instructions = f"""
        You are an AI receptionist for {salon_info['name']}. 
        You have VERY LIMITED knowledge and should ONLY answer these specific questions directly:
        
        1. Basic hours: "Our hours are {salon_info['hours']}"
        2. Location: "We're located at {salon_info['address']}"
        3. General services: "We offer {', '.join(salon_info['services'])}"
        
        FOR ALL OTHER QUESTIONS, including but not limited to:
        - Specific prices
        - Appointments or booking
        - Parking information
        - Discounts or special offers
        - Specific stylist information
        - Service details
        - Cancellations or rescheduling
        - ANY other questions
        
        You MUST respond with: "Let me check with my supervisor and get back to you."
        
        IMPORTANT: Do NOT attempt to answer questions you're not specifically programmed for.
        IMPORTANT: Do NOT make up information or provide general assistance.
        IMPORTANT: Keep all responses brief and professional.
        """
        
        super().__init__(instructions=instructions)
        self.ai_agent = ai_agent
        self.call_id: Optional[str] = None
        self.customer_id: Optional[str] = None
        self.customer_phone: Optional[str] = None
    
    def set_call_info(self, call_id: str, customer_id: str, customer_phone: str):
        """Set call information for tracking purposes"""
        self.call_id = call_id
        self.customer_id = customer_id
        self.customer_phone = customer_phone

async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent"""
    logger.info(f"Voice agent started for room {ctx.room.name}")
    
    # Connect to the room
    await ctx.connect()
    
    # Get participant information
    participant = None
    for p in ctx.room.remote_participants.values():
        participant = p
        break
    
    # Extract metadata
    room_sid = ctx.room.sid  # Note the await and parentheses
    call_id = f"call_{room_sid}"
    customer_phone = "unknown"
    
    if participant:
        try:
            metadata = json.loads(participant.metadata) if participant.metadata else {}
            call_id = metadata.get("callId", call_id)
            customer_phone = metadata.get("from", customer_phone)
        except Exception as e:
            logger.error(f"Error parsing participant metadata: {e}")
    
    customer_id = customer_phone.replace("+", "")
    
    logger.info(f"Starting voice assistant for call {call_id} from {customer_phone}")
    
    # Create call record
    call_record = await ai_agent.handle_incoming_call(
        call_id, customer_id, customer_phone
    )
    
    if not call_record:
        logger.error(f"Failed to create call record for {call_id}")
        return
    
    # Create our AI agent
    agent = SalonReceptionist()
    agent.set_call_info(call_id, customer_id, customer_phone)
    
    async def answer_question(question: str) -> str:
        """Check knowledge base or create help request if needed"""
        logger.info(f"Processing question: {question}")
        
        try:
            # Strictly follow the AI agent's decision logic
            result = await agent.ai_agent.answer_question(question)
            
            # If we need help, create the help request
            if result["needs_help"] and agent.call_id and agent.customer_id and agent.customer_phone:
                help_request = await agent.ai_agent.create_help_request(
                    question=question,
                    call_id=agent.call_id,
                    customer_id=agent.customer_id,
                    customer_phone=agent.customer_phone
                )
                
                if help_request:
                    logger.info(f"Created help request: {help_request.request_id}")
            
            return result["answer"]
        
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return "Let me check with my supervisor and get back to you."
        
    # Create agent session with components
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=groq.LLM(model="llama3-8b-8192"),
        tts=neuphonic.TTS(
            voice_id="e564ba7e-aa8d-46a2-96a8-8dffedade48f",
            api_key=settings.NEUPHONIC_API_KEY if settings.NEUPHONIC_API_KEY else None
        ),
        vad=silero.VAD.load(),
    )
    
    # Start the session
    await session.start(
        room=ctx.room,
        agent=agent,
    )
    
    # Initial greeting
    greeting = f"Thank you for calling {settings.SALON_INFO['name']}. This is your AI receptionist. How can I help you today?"
    await session.generate_reply(instructions=greeting)
    
    # Monitor for participant events
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"Participant {participant.identity} disconnected")
        asyncio.create_task(handle_call_ended(agent))
    
    # Keep the session alive
    await session.wait_for_completion()
    
    # Handle cleanup
    await handle_call_ended(agent)

async def handle_call_ended(agent: SalonReceptionist):
    """Handle cleanup when call ends"""
    if agent.call_id:
        # Calculate duration (this is a simplified version)
        duration_ms = 60000  # You'd calculate this from actual call duration
        await agent.ai_agent.handle_call_ended(agent.call_id, duration_ms)
        logger.info(f"Call {agent.call_id} ended")

def run_worker():
    """Run the voice agent worker"""
    logger.info("Starting LiveKit Voice Agent Worker...")
    logger.info(f"LiveKit URL: {settings.LIVEKIT_URL}")
    logger.info(f"Business Name: {settings.SALON_INFO['name']}")
    logger.info("STT: Deepgram | LLM: OpenAI | TTS: OpenAI")
    
    # Run the agent with CLI
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

if __name__ == "__main__":
    run_worker()