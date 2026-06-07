"""
Configuration for TikTok Watermark Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("WM_TELEGRAM_TOKEN", "8254121885:AAGIw8reJQxki0Gji7tstDXYmo-_AFi_06k")

# Admin User ID (only this user can use the bot)
ADMIN_ID = os.getenv("WM_ADMIN_ID", "8235497168")

# Directories
DOWNLOADS_DIR = "downloads"
WATERMARK_DIR = "watermarks"

# Watermark settings
WATERMARK_POSITION = "bottom-right"
WATERMARK_OPACITY = 0.78
WATERMARK_SCALE = 0.16
WATERMARK_MARGIN = 20

# Proxy settings (optional)
# Format: "http://user:pass@host:port" or "socks5://host:port" or None
PROXY_URL = os.getenv("WM_PROXY_URL", None)

# FFmpeg settings
FFMPEG_THREADS = 0
FFMPEG_PRESET = "fast"
FFMPEG_CRF = 28
