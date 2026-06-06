"""
Video processing module.
Handles video orientation detection, conversion to vertical, and watermark overlay.
"""
import os
import subprocess
import logging
import uuid
import shutil
from typing import Tuple, Optional

from config import (
    DOWNLOADS_DIR, FFMPEG_THREADS, FFMPEG_PRESET, FFMPEG_CRF,
    WATERMARK_POSITION, WATERMARK_OPACITY, WATERMARK_SCALE, WATERMARK_MARGIN
)

def find_ffmpeg() -> Tuple[Optional[str], Optional[str]]:
    """Find ffmpeg and ffprobe executables."""
    # Check local bin folder first
    local_ffmpeg = os.path.join("bin", "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
    local_ffprobe = os.path.join("bin", "ffprobe.exe" if os.name == 'nt' else "ffprobe")
    
    if os.path.exists(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK):
        ffmpeg = local_ffmpeg
    else:
        ffmpeg = shutil.which("ffmpeg")
    
    if os.path.exists(local_ffprobe) and os.access(local_ffprobe, os.X_OK):
        ffprobe = local_ffprobe
    else:
        ffprobe = shutil.which("ffprobe")
    
    return ffmpeg, ffprobe

FFMPEG_PATH, FFPROBE_PATH = find_ffmpeg()

def get_video_dimensions(file_path: str) -> Tuple[int, int]:
    """
    Get video dimensions using ffprobe.
    Returns (width, height) tuple.
    """
    if not FFPROBE_PATH:
        logging.warning("ffprobe not found, trying imageio fallback")
        return _get_dimensions_imageio(file_path)
    
    try:
        cmd = [
            FFPROBE_PATH,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
    except Exception as e:
        logging.error(f"ffprobe error: {e}")
    
    return _get_dimensions_imageio(file_path)

def _get_dimensions_imageio(file_path: str) -> Tuple[int, int]:
    """Fallback: get dimensions using imageio."""
    try:
        import imageio.v3 as iio
        props = iio.improps(file_path, plugin="pyav")
        return props.shape[1], props.shape[0]  # width, height
    except Exception as e:
        logging.error(f"imageio error: {e}")
        return 1080, 1920  # Default vertical

def is_vertical_video(file_path: str) -> bool:
    """Check if video is vertical (height > width)."""
    width, height = get_video_dimensions(file_path)
    return height > width

def convert_to_vertical(file_path: str) -> str:
    """
    Convert horizontal video to vertical (9:16) with black bars.
    Returns path to converted video.
    """
    if not FFMPEG_PATH:
        logging.warning("ffmpeg not found, skipping conversion")
        return file_path
    
    width, height = get_video_dimensions(file_path)
    
    # Already vertical
    if height > width:
        logging.info("Video is already vertical, skipping conversion")
        return file_path
    
    # Calculate output dimensions (9:16 aspect ratio)
    target_width = 1080
    target_height = 1920
    
    # Scale video to fit width, then pad to fill height
    output_path = file_path.replace('.mp4', '_vertical.mp4')
    
    try:
        cmd = [
            FFMPEG_PATH,
            '-i', file_path,
            '-vf', f'scale={target_width}:-2,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264',
            '-preset', FFMPEG_PRESET,
            '-crf', str(FFMPEG_CRF),
            '-threads', str(FFMPEG_THREADS),
            '-c:a', 'aac',
            '-b:a', '192k',
            '-y',
            output_path
        ]
        
        logging.info(f"Converting to vertical: {file_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logging.info(f"Conversion successful: {output_path}")
            # Remove original
            os.remove(file_path)
            return output_path
        else:
            logging.error(f"Conversion failed: {result.stderr}")
            return file_path
            
    except Exception as e:
        logging.error(f"Conversion error: {e}")
        return file_path


def add_watermark(video_path: str, watermark_path: str,
                  position: str = None,
                  opacity: float = None,
                  scale: float = None,
                  margin: int = None) -> str:
    """
    Add watermark overlay to video.
    Returns path to watermarked video.
    """
    if not FFMPEG_PATH:
        logging.warning("ffmpeg not found, skipping watermark")
        return video_path
    
    if not os.path.exists(watermark_path):
        logging.warning(f"Watermark not found: {watermark_path}")
        return video_path
    
    # Use defaults from config if not specified
    position = position or WATERMARK_POSITION
    opacity = opacity if opacity is not None else WATERMARK_OPACITY
    scale = scale if scale is not None else WATERMARK_SCALE
    margin = margin if margin is not None else WATERMARK_MARGIN
    
    # Get video dimensions for scaling
    vid_width, vid_height = get_video_dimensions(video_path)
    wm_width = int(vid_width * scale)
    
    # Calculate position
    if position == "top-left":
        overlay_pos = f"{margin}:{margin}"
    elif position == "top-right":
        overlay_pos = f"W-w-{margin}:{margin}"
    elif position == "bottom-left":
        overlay_pos = f"{margin}:H-h-{margin}"
    else:  # bottom-right (default)
        overlay_pos = f"W-w-{margin}:H-h-{margin}"
    
    output_path = video_path.replace('.mp4', '_wm.mp4')
    
    try:
        # Build filter: scale watermark, set opacity, overlay
        filter_complex = (
            f"[1:v]scale={wm_width}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={overlay_pos}"
        )
        
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-i', watermark_path,
            '-filter_complex', filter_complex,
            '-c:v', 'libx264',
            '-preset', FFMPEG_PRESET,
            '-crf', str(FFMPEG_CRF),
            '-threads', str(FFMPEG_THREADS),
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        logging.info(f"Adding watermark to: {video_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logging.info(f"Watermark added: {output_path}")
            # Remove original
            os.remove(video_path)
            return output_path
        else:
            logging.error(f"Watermark failed: {result.stderr}")
            return video_path
            
    except Exception as e:
        logging.error(f"Watermark error: {e}")
        return video_path


def process_video(file_path: str, watermark_path: Optional[str] = None) -> str:
    """
    Full video processing pipeline:
    1. Convert to vertical if needed
    2. Add watermark if configured
    
    Returns path to processed video.
    """
    logging.info(f"Processing video: {file_path}")
    
    # Step 1: Convert to vertical if horizontal
    if not is_vertical_video(file_path):
        file_path = convert_to_vertical(file_path)
    
    # Step 2: Add watermark if provided
    if watermark_path and os.path.exists(watermark_path):
        file_path = add_watermark(file_path, watermark_path)
    
    logging.info(f"Processing complete: {file_path}")
    return file_path


def cleanup_file(file_path: str) -> bool:
    """Delete a file safely."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Cleaned up: {file_path}")
            return True
    except Exception as e:
        logging.error(f"Cleanup error: {e}")
    return False
