#!/usr/bin/env python3
"""
Run the LiveKit Voice Agent Worker
This handles actual phone calls
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.utils.logger import setup_logging, get_logger

# Set up logging
setup_logging()
logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info("Starting LiveKit Voice Agent Worker...")
    logger.info(f"LiveKit URL: {settings.LIVEKIT_URL}")
    logger.info(f"Business Name: {settings.BUSINESS_NAME}")
    
    try:
        # Try different voice agent implementations based on what's available
        try:
            # Try the full voice agent first
            from app.agents.voice_agent import run_worker
            logger.info("Using full voice agent implementation")
        except ImportError as e:
            logger.warning(f"Could not import full voice agent: {e}")
            try:
                # Try the simple version
                from app.agents.voice_agent_simple import run_worker
                logger.info("Using simple voice agent implementation")
            except ImportError:
                # Fall back to minimal version
                from app.agents.voice_agent_minimal import run_worker
                logger.info("Using minimal voice agent implementation")
        
        # Run the worker
        run_worker()
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)