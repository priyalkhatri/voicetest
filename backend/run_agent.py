#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.agents.voice_agent import run_worker
from app.config import settings
from app.utils.logger import setup_logging, get_logger

# Set up logging
setup_logging()
logger = get_logger(__name__)

if __name__ == "__main__":
    logger.info("Starting LiveKit Voice Agent Worker...")
    logger.info(f"LiveKit URL: {settings.LIVEKIT_URL}")
    
    try:
        # Let LiveKit CLI handle all the command line parsing
        run_worker()
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)