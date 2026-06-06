"""
Video downloader module.
Downloads TikTok and YouTube videos and extracts metadata.
"""
import yt_dlp
import os
import uuid
import asyncio
import logging
import requests
import re
from typing import Tuple, Optional

from config import DOWNLOADS_DIR

# Ensure download directory exists
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Import proxy settings
from config import PROXY_URL


async def download_tiktok_video(url: str) -> Tuple[str, Optional[str]]:
    """
    Downloads a TikTok video using multiple methods.
    Returns tuple (file_path, description).
    Raises exception with details on failure.
    """
    # Try method 1: yt-dlp with cookies/impersonation
    max_retries = 2
    for attempt in range(max_retries):
        try:
            filepath, description = await download_via_ytdlp(url)
            return (filepath, description)
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"yt-dlp attempt {attempt + 1} failed: {e}, retrying...")
                await asyncio.sleep(1)
            else:
                logging.warning(f"yt-dlp failed: {e}, trying tikwm API...")
    
    # Try method 2: tikwm.com API (most reliable for TikTok)
    try:
        filepath, description = await download_via_tikwm(url)
        return (filepath, description)
    except Exception as e:
        logging.warning(f"tikwm API failed: {e}, trying direct API...")
    
    # Try method 3: Direct API (last resort)
    try:
        filepath, description = await download_via_api(url)
        return (filepath, description)
    except Exception as e:
        logging.error(f"All download methods failed: {e}")
        raise Exception(f"Не удалось скачать видео. Попробуй другую ссылку или обнови yt-dlp: pip install -U yt-dlp")


async def download_via_tikwm(url: str) -> Tuple[str, Optional[str]]:
    """Download using tikwm.com API (reliable, no watermark)."""
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    description = None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }
    
    # Настройка прокси для requests
    proxies = None
    if PROXY_URL:
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL,
        }
        logging.info(f"Using proxy for tikwm: {PROXY_URL}")
    
    loop = asyncio.get_event_loop()
    
    try:
        # Use tikwm.com API
        api_url = f"https://www.tikwm.com/api/?url={url}"
        
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(api_url, headers=headers, proxies=proxies, timeout=30)
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('code') == 0 and data.get('data'):
                video_data = data['data']
                
                # Get description from multiple possible fields
                description = video_data.get('title') or video_data.get('desc') or ''
                
                # Also try to get author info
                author = video_data.get('author', {})
                author_name = author.get('nickname') or author.get('unique_id') or ''
                
                # Build full description with hashtags if available
                if not description and author_name:
                    description = f"@{author_name}"
                
                logging.info(f"tikwm description: {description[:100] if description else 'EMPTY'}...")
                
                # Get video URL (without watermark)
                video_url = video_data.get('play') or video_data.get('hdplay') or video_data.get('wmplay')
                
                if video_url:
                    logging.info(f"Got video URL from tikwm: {video_url[:50]}...")
                    
                    # Download video
                    video_response = await loop.run_in_executor(
                        None,
                        lambda: requests.get(video_url, headers=headers, proxies=proxies, timeout=120, stream=True)
                    )
                    
                    if video_response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in video_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        file_size = os.path.getsize(filepath)
                        if file_size > 10000:
                            logging.info(f"Downloaded via tikwm: {filepath} ({file_size} bytes)")
                            return (filepath, description)
                        else:
                            if os.path.exists(filepath):
                                os.remove(filepath)
        
        raise Exception("tikwm API failed to get video")
        
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise e


async def download_via_api(url: str) -> Tuple[str, Optional[str]]:
    """Download using TikTok API (no watermark). Returns (filepath, description)."""
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    description = None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Referer': 'https://www.tiktok.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    
    loop = asyncio.get_event_loop()
    
    try:
        # Get video info from TikTok's oembed API
        oembed_url = f"https://www.tiktok.com/oembed?url={url}"
        
        response = await loop.run_in_executor(
            None, 
            lambda: requests.get(oembed_url, headers=headers, timeout=30)
        )
        
        if response.status_code == 200:
            data = response.json()
            description = data.get('title', '')
            logging.info(f"Got TikTok description: {description[:100]}...")
            
            if 'thumbnail_url' in data:
                # Try to get video page
                video_response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(url, headers=headers, timeout=30, allow_redirects=True)
                )
                
                html = video_response.text
                
                # Try multiple patterns to find video URL
                download_patterns = [
                    r'"downloadAddr":"([^"]+)"',
                    r'"playAddr":"([^"]+)"',
                    r'"play_addr":\s*\{\s*"url_list":\s*\["([^"]+)"',
                    r'<video[^>]+src="([^"]+)"',
                ]
                
                for pattern in download_patterns:
                    match = re.search(pattern, html)
                    if match:
                        download_url = match.group(1).replace('\\u002F', '/').replace('\\u0026', '&')
                        
                        logging.info(f"Found download URL via pattern: {pattern[:30]}...")
                        
                        # Download with proper headers
                        video_headers = headers.copy()
                        video_headers['Range'] = 'bytes=0-'
                        
                        video_data = await loop.run_in_executor(
                            None,
                            lambda: requests.get(download_url, headers=video_headers, timeout=120, stream=True)
                        )
                        
                        if video_data.status_code in [200, 206]:
                            with open(filepath, 'wb') as f:
                                for chunk in video_data.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            file_size = os.path.getsize(filepath)
                            if file_size > 10000:  # At least 10KB
                                logging.info(f"Downloaded via API: {filepath} ({file_size} bytes)")
                                return (filepath, description)
                            else:
                                logging.warning(f"Downloaded file too small: {file_size} bytes")
                                if os.path.exists(filepath):
                                    os.remove(filepath)
        
        raise Exception("Could not extract download URL from TikTok")
            
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise e


async def download_via_ytdlp(url: str) -> Tuple[str, Optional[str]]:
    """Download using yt-dlp (primary method). Returns (filepath, description)."""
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    description = None
    
    ydl_opts = {
        'outtmpl': filepath,
        'format': 'best[ext=mp4]/best',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'prefer_free_formats': False,
        'socket_timeout': 60,
        'retries': 5,
        'extractor_retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        },
        'extract_flat': False,
        'ignoreerrors': False,
    }
    
    # Добавляем прокси если настроен
    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL
        logging.info(f"Using proxy for yt-dlp: {PROXY_URL}")
    
    loop = asyncio.get_event_loop()
    
    try:
        # Download and get info in one call
        info = await loop.run_in_executor(None, _download_with_info, url, ydl_opts)
        if info:
            description = info.get('description', info.get('title', ''))
            logging.info(f"Got description from yt-dlp: {description[:100] if description else 'None'}...")
        
        if not os.path.exists(filepath):
            raise Exception("File not created after download")
        
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            os.remove(filepath)
            raise Exception("Downloaded file is empty")
        
        logging.info(f"Downloaded via yt-dlp: {filepath} ({file_size} bytes)")
        return (filepath, description)
        
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise Exception(f"Download failed for {url}: {str(e)}")


def _download_with_info(url, opts):
    """Download and return info dict."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info


def _download(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def _get_info_sync(url: str) -> dict:
    """Get video info synchronously."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        return {
            'author': info.get('uploader', 'Unknown'),
            'title': info.get('description', info.get('title', '')),
            'duration': info.get('duration', 0),
        }


async def get_tiktok_info(url: str) -> Optional[dict]:
    """Get TikTok video information without downloading."""
    loop = asyncio.get_event_loop()
    
    try:
        return await loop.run_in_executor(None, _get_info_sync, url)
    except Exception as e:
        logging.error(f"Error getting video info: {e}")
        return None


async def download_youtube_video(url: str) -> Tuple[str, Optional[str]]:
    """
    Downloads a YouTube video (including Shorts) using yt-dlp.
    Returns tuple (file_path, description).
    """
    filename = f"{uuid.uuid4()}.mp4"
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    description = None
    
    ydl_opts = {
        'outtmpl': filepath,
        'format': 'best[ext=mp4][height<=1080]/best[ext=mp4]/best',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'socket_timeout': 60,
        'retries': 5,
        'extractor_retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
    }
    
    loop = asyncio.get_event_loop()
    
    try:
        info = await loop.run_in_executor(None, _download_with_info, url, ydl_opts)
        if info:
            # YouTube has title, not description for shorts
            title = info.get('title', '')
            desc = info.get('description', '')
            # Use title as main description, add channel name
            channel = info.get('channel', info.get('uploader', ''))
            
            if title:
                description = title
                if channel:
                    description = f"{title}\n\n📺 {channel}"
            elif desc:
                description = desc[:500]
            
            logging.info(f"Got YouTube description: {description[:100] if description else 'None'}...")
        
        if not os.path.exists(filepath):
            raise Exception("File not created after download")
        
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            os.remove(filepath)
            raise Exception("Downloaded file is empty")
        
        logging.info(f"Downloaded YouTube video: {filepath} ({file_size} bytes)")
        return (filepath, description)
        
    except Exception as e:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise Exception(f"YouTube download failed: {str(e)}")


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube link."""
    youtube_patterns = [
        r'youtube\.com/watch',
        r'youtube\.com/shorts',
        r'youtu\.be/',
        r'youtube\.com/v/',
        r'youtube\.com/embed/',
    ]
    return any(re.search(pattern, url) for pattern in youtube_patterns)


def is_tiktok_url(url: str) -> bool:
    """Check if URL is a TikTok link."""
    return 'tiktok.com' in url
