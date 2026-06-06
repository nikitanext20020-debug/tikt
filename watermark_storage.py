"""
Watermark storage module.
Handles saving, loading, and removing watermark images.
"""
import os
import logging
from config import WATERMARK_DIR

WATERMARK_FILE = os.path.join(WATERMARK_DIR, "current_watermark.png")

def ensure_watermark_dir():
    """Ensure watermark directory exists."""
    if not os.path.exists(WATERMARK_DIR):
        os.makedirs(WATERMARK_DIR)
        logging.info(f"Created watermark directory: {WATERMARK_DIR}")

async def save_watermark(file_bytes: bytes) -> str:
    """
    Save watermark image from bytes.
    Returns the path to saved watermark.
    """
    ensure_watermark_dir()
    
    with open(WATERMARK_FILE, 'wb') as f:
        f.write(file_bytes)
    
    logging.info(f"Watermark saved to: {WATERMARK_FILE}")
    return WATERMARK_FILE

def get_watermark_path() -> str | None:
    """
    Get path to current watermark if it exists.
    Returns None if no watermark is configured.
    """
    if os.path.exists(WATERMARK_FILE):
        return WATERMARK_FILE
    return None

def remove_watermark() -> bool:
    """
    Remove current watermark.
    Returns True if removed, False if didn't exist.
    """
    if os.path.exists(WATERMARK_FILE):
        os.remove(WATERMARK_FILE)
        logging.info("Watermark removed")
        return True
    return False

def watermark_exists() -> bool:
    """Check if watermark is configured."""
    return os.path.exists(WATERMARK_FILE)
