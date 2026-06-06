"""
TikTok Watermark Bot
Downloads TikTok videos, converts to vertical, adds watermark, sends to user.
"""
import asyncio
import logging
import sys
import os
import re
import uuid
from typing import List

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_TOKEN, ADMIN_ID, DOWNLOADS_DIR, SEND_TO_TELEGRAM
from downloader import download_tiktok_video, download_youtube_video, is_youtube_url, is_tiktok_url
from video_processor import process_video, cleanup_file
from watermark_storage import (
    save_watermark, get_watermark_path, remove_watermark, watermark_exists
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

# Ensure directories exist
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs("watermarks", exist_ok=True)


def validate_config():
    """Validate required configuration."""
    if not TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is missing!")
        sys.exit(1)
    
    if not ADMIN_ID:
        logging.error("ADMIN_ID is missing! Set WM_ADMIN_ID environment variable.")
        sys.exit(1)


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return str(user_id) == str(ADMIN_ID)


def extract_tiktok_urls(text: str) -> List[str]:
    """Extract all TikTok URLs from text."""
    pattern = r'https?://[^\s]*tiktok\.com/[^\s]*'
    urls = re.findall(pattern, text)
    # Remove duplicates while preserving order
    return list(dict.fromkeys(urls))


def extract_youtube_urls(text: str) -> List[str]:
    """Extract all YouTube URLs from text (including Shorts)."""
    patterns = [
        r'https?://(?:www\.)?youtube\.com/shorts/[^\s]+',
        r'https?://(?:www\.)?youtube\.com/watch\?[^\s]+',
        r'https?://youtu\.be/[^\s]+',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, text))
    # Remove duplicates while preserving order
    return list(dict.fromkeys(urls))


def format_description(description: str) -> str:
    """Format TikTok description for message caption."""
    if not description or not description.strip():
        return ""
    
    description = description.strip()
    
    # Extract hashtags (including unicode hashtags)
    hashtags = re.findall(r'#[\w\u0400-\u04FF]+', description, re.UNICODE)
    
    # Clean description (remove hashtags for cleaner display)
    clean_desc = re.sub(r'#[\w\u0400-\u04FF]+', '', description, flags=re.UNICODE).strip()
    # Remove multiple spaces
    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
    
    result = ""
    
    # Add description if exists
    if clean_desc:
        # Telegram caption limit is 1024 chars, leave room for hashtags
        result += f"📝 <b>Описание:</b>\n{clean_desc[:400]}\n\n"
    
    # Add hashtags if exist
    if hashtags:
        hashtags_text = ' '.join(hashtags[:15])  # Limit to 15 hashtags
        result += f"🏷 <b>Хэштеги:</b>\n{hashtags_text}"
    
    # If only hashtags in original description
    if not clean_desc and hashtags:
        result = f"🏷 <b>Хэштеги:</b>\n{' '.join(hashtags[:15])}"
    
    return result.strip()


# Initialize bot
validate_config()

# Создаем бота (сессия будет создана в main)
bot = Bot(
    token=TELEGRAM_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle /start command."""
    if not is_admin(message.from_user.id):
        return
    
    wm_status = "✅ Установлена" if watermark_exists() else "❌ Не установлена"
    
    text = (
        "👋 <b>TikTok & YouTube Watermark Bot</b>\n\n"
        "Отправь мне ссылку на TikTok или YouTube Shorts, и я:\n"
        "1. Скачаю видео\n"
        "2. Конвертирую в вертикальный формат (если нужно)\n"
        "3. Наложу твою водяную марку\n"
        "4. Отправлю готовое видео\n\n"
        "📹 <b>Или отправь видео напрямую</b> — я сделаю его вертикальным и добавлю водяную марку!\n\n"
        f"🖼 Водяная марка: {wm_status}\n\n"
        "<b>Команды:</b>\n"
        "/setwatermark — установить водяную марку (отправь с картинкой)\n"
        "/watermark — показать текущую водяную марку\n"
        "/removewatermark — удалить водяную марку\n\n"
        "💡 Можно отправлять несколько ссылок сразу!\n"
        "🎬 Поддерживаются: TikTok, YouTube Shorts, обычные YouTube видео"
    )
    
    await message.answer(text)


# State for waiting watermark
waiting_for_watermark = {}


@dp.message(Command("setwatermark"))
async def cmd_set_watermark(message: types.Message):
    """Handle /setwatermark command."""
    if not is_admin(message.from_user.id):
        return
    
    # Check if message has photo attached
    if message.photo:
        # Photo attached - save it
        photo = message.photo[-1]
        status_msg = await message.answer("⏳ Сохраняю водяную марку...")
        
        try:
            file = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file.file_path)
            await save_watermark(file_bytes.read())
            await status_msg.edit_text("✅ Водяная марка установлена!")
        except Exception as e:
            logging.error(f"Error saving watermark: {e}")
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # No photo - wait for next message with file
    waiting_for_watermark[message.from_user.id] = True
    await message.answer(
        "📤 <b>Отправь картинку для водяной марки</b>\n\n"
        "Для PNG с прозрачностью — отправь как <b>файл</b> (документ).\n"
        "Для обычной картинки — можно как фото."
    )


@dp.message(Command("watermark"))
async def cmd_show_watermark(message: types.Message):
    """Handle /watermark command - show current watermark."""
    if not is_admin(message.from_user.id):
        return
    
    wm_path = get_watermark_path()
    
    if not wm_path:
        await message.answer("❌ Водяная марка не установлена.\n\nИспользуй /setwatermark с картинкой.")
        return
    
    try:
        photo = FSInputFile(wm_path)
        await message.answer_photo(photo, caption="🖼 Текущая водяная марка")
    except Exception as e:
        logging.error(f"Error showing watermark: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message(Command("removewatermark"))
async def cmd_remove_watermark(message: types.Message):
    """Handle /removewatermark command."""
    if not is_admin(message.from_user.id):
        return
    
    if remove_watermark():
        await message.answer("✅ Водяная марка удалена.")
    else:
        await message.answer("ℹ️ Водяная марка не была установлена.")


@dp.message(F.photo)
async def handle_photo_with_watermark(message: types.Message):
    """Handle photo messages - check if waiting for watermark."""
    if not is_admin(message.from_user.id):
        return
    
    # Check if waiting for watermark
    if message.from_user.id in waiting_for_watermark:
        del waiting_for_watermark[message.from_user.id]
        
        photo = message.photo[-1]
        status_msg = await message.answer("⏳ Сохраняю водяную марку...")
        
        try:
            file = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file.file_path)
            await save_watermark(file_bytes.read())
            await status_msg.edit_text("✅ Водяная марка установлена!")
        except Exception as e:
            logging.error(f"Error saving watermark: {e}")
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # Check if caption contains /setwatermark
    if message.caption and "/setwatermark" in message.caption.lower():
        await cmd_set_watermark(message)


@dp.message(F.document)
async def handle_document(message: types.Message):
    """Handle document messages - for PNG watermarks or video files."""
    if not is_admin(message.from_user.id):
        return
    
    doc = message.document
    
    # Check if waiting for watermark OR caption has /setwatermark
    is_waiting = message.from_user.id in waiting_for_watermark
    has_command = message.caption and "/setwatermark" in message.caption.lower()
    
    # Handle watermark upload
    if is_waiting or has_command:
        # Clear waiting state
        if is_waiting:
            del waiting_for_watermark[message.from_user.id]
        
        # Check if it's an image
        if not doc.mime_type or not doc.mime_type.startswith('image/'):
            await message.answer("❌ Это не изображение. Отправь PNG или JPG файл.")
            return
        
        status_msg = await message.answer("⏳ Сохраняю водяную марку (PNG с прозрачностью)...")
        
        try:
            file = await bot.get_file(doc.file_id)
            file_bytes = await bot.download_file(file.file_path)
            await save_watermark(file_bytes.read())
            await status_msg.edit_text("✅ Водяная марка установлена! (прозрачность сохранена)")
        except Exception as e:
            logging.error(f"Error saving watermark: {e}")
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # Handle video file upload
    if doc.mime_type and doc.mime_type.startswith('video/'):
        await process_uploaded_video(message, doc)


@dp.message(F.video)
async def handle_video(message: types.Message):
    """Handle video messages - process and add watermark."""
    if not is_admin(message.from_user.id):
        return
    
    await process_uploaded_video(message, message.video)


async def process_uploaded_video(message: types.Message, video_file):
    """Process uploaded video file - convert to vertical and add watermark."""
    status_msg = await message.answer("⏳ Загружаю видео...")
    
    file_path = None
    
    try:
        # Download video from Telegram
        file = await bot.get_file(video_file.file_id)
        
        # Generate unique filename
        filename = f"{uuid.uuid4()}.mp4"
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        
        await status_msg.edit_text("⏬ Скачиваю видео из Telegram...")
        
        # Download file
        file_bytes = await bot.download_file(file.file_path)
        with open(file_path, 'wb') as f:
            f.write(file_bytes.read())
        
        logging.info(f"Downloaded video from Telegram: {file_path}")
        
        # Get watermark path
        watermark_path = get_watermark_path()
        
        # Process video
        await status_msg.edit_text("🔄 Обрабатываю видео...")
        processed_path = process_video(file_path, watermark_path)
        file_path = processed_path  # Update for cleanup
        
        # Send processed video
        await status_msg.edit_text("📤 Отправляю видео...")
        
        video = FSInputFile(processed_path)
        
        # Отправляем с повторными попытками
        max_send_attempts = 3
        for attempt in range(max_send_attempts):
            try:
                await message.answer_video(
                    video, 
                    caption="✅ Видео обработано!"
                )
                break
            except Exception as send_error:
                if attempt < max_send_attempts - 1:
                    logging.warning(f"Send attempt {attempt + 1} failed: {send_error}, retrying...")
                    await asyncio.sleep(2)
                else:
                    raise send_error
        
        # Delete status message
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error processing uploaded video: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:200]}")
    
    finally:
        # Cleanup с задержкой
        if file_path and os.path.exists(file_path):
            await asyncio.sleep(1)
            cleanup_file(file_path)


@dp.message(F.text.regexp(r"https?://.*tiktok\.com/.*"))
async def handle_tiktok_links(message: types.Message):
    """Handle messages with TikTok links."""
    if not is_admin(message.from_user.id):
        return
    
    urls = extract_tiktok_urls(message.text)
    
    if not urls:
        return
    
    # Get watermark path
    watermark_path = get_watermark_path()
    
    if len(urls) == 1:
        # Single video
        await process_single_video(message, urls[0], watermark_path, platform="tiktok")
    else:
        # Multiple videos
        await process_multiple_videos(message, urls, watermark_path, platform="tiktok")


@dp.message(F.text.regexp(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/.*"))
async def handle_youtube_links(message: types.Message):
    """Handle messages with YouTube links (including Shorts)."""
    if not is_admin(message.from_user.id):
        return
    
    urls = extract_youtube_urls(message.text)
    
    if not urls:
        return
    
    # Get watermark path
    watermark_path = get_watermark_path()
    
    if len(urls) == 1:
        # Single video
        await process_single_video(message, urls[0], watermark_path, platform="youtube")
    else:
        # Multiple videos
        await process_multiple_videos(message, urls, watermark_path, platform="youtube")


async def process_single_video(message: types.Message, url: str, watermark_path: str = None, platform: str = "tiktok"):
    """Process a single video from TikTok or YouTube."""
    platform_name = "YouTube" if platform == "youtube" else "TikTok"
    status_msg = await message.answer(f"⏳ Скачиваю {platform_name} видео...")
    
    file_path = None
    description = None
    
    try:
        # Step 1: Download
        await status_msg.edit_text("⏬ Скачиваю видео...")
        
        if platform == "youtube":
            file_path, description = await download_youtube_video(url)
        else:
            file_path, description = await download_tiktok_video(url)
        
        logging.info(f"Downloaded video, description: {description[:100] if description else 'None'}...")
        
        # Step 2: Process (convert + watermark)
        await status_msg.edit_text("🔄 Обрабатываю видео...")
        processed_path = process_video(file_path, watermark_path)
        file_path = processed_path  # Update for cleanup
        
        # Step 3: Send or save
        if SEND_TO_TELEGRAM:
            # РЕЖИМ: Отправка в Telegram (закомментирован, но можно включить)
            await status_msg.edit_text("📤 Отправляю видео...")
            
            # Format caption with description and hashtags
            caption = format_description(description)
            logging.info(f"Sending video with caption: {caption[:200] if caption else 'EMPTY'}...")
            
            video = FSInputFile(processed_path)
            
            # Отправляем с повторными попытками при таймауте
            max_send_attempts = 3
            for attempt in range(max_send_attempts):
                try:
                    await message.answer_video(
                        video, 
                        caption=caption if caption else None, 
                        parse_mode=ParseMode.HTML
                    )
                    break  # Успешно отправили
                except Exception as send_error:
                    if attempt < max_send_attempts - 1:
                        logging.warning(f"Send attempt {attempt + 1} failed: {send_error}, retrying...")
                        await asyncio.sleep(2)
                    else:
                        raise send_error
            
            # Send description separately if caption was empty
            if not caption and description:
                await message.answer(f"📝 <b>Описание:</b>\n{description[:500]}", parse_mode=ParseMode.HTML)
            elif not caption:
                await message.answer("✅ Готово!\n\n💡 Описание не удалось получить")
        else:
            # РЕЖИМ: Только сохранение в папку (текущий режим)
            file_name = os.path.basename(processed_path)
            file_size_mb = os.path.getsize(processed_path) / (1024 * 1024)
            
            result_text = (
                f"✅ <b>Видео готово!</b>\n\n"
                f"📁 Файл: <code>{file_name}</code>\n"
                f"📊 Размер: {file_size_mb:.2f} МБ\n"
                f"📂 Папка: <code>{DOWNLOADS_DIR}</code>\n\n"
            )
            
            if description:
                caption = format_description(description)
                if caption:
                    result_text += f"\n{caption}"
            
            await message.answer(result_text, parse_mode=ParseMode.HTML)
            
            # НЕ удаляем файл - оставляем в папке
            file_path = None  # Чтобы cleanup не удалил
        
        # Delete status message
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error processing video: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:200]}")
    
    finally:
        # Cleanup только если отправляли в Telegram
        if SEND_TO_TELEGRAM and file_path and os.path.exists(file_path):
            await asyncio.sleep(1)
            cleanup_file(file_path)


async def process_multiple_videos(message: types.Message, urls: List[str], watermark_path: str = None, platform: str = "tiktok"):
    """Process multiple videos from TikTok or YouTube."""
    total = len(urls)
    success_count = 0
    error_count = 0
    platform_name = "YouTube" if platform == "youtube" else "TikTok"
    
    status_msg = await message.answer(f"📦 Обработка {total} {platform_name} видео...\n\n⏳ Подготовка...")
    
    processed_files = []  # Список обработанных файлов
    
    for idx, url in enumerate(urls, 1):
        file_path = None
        description = None
        
        try:
            # Update progress
            await status_msg.edit_text(
                f"📦 Обработка {idx}/{total}\n\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Ошибок: {error_count}\n\n"
                f"⏬ Скачиваю..."
            )
            
            # Download
            if platform == "youtube":
                file_path, description = await download_youtube_video(url)
            else:
                file_path, description = await download_tiktok_video(url)
            
            logging.info(f"Video {idx}: description = {description[:100] if description else 'None'}...")
            
            # Update progress
            await status_msg.edit_text(
                f"📦 Обработка {idx}/{total}\n\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Ошибок: {error_count}\n\n"
                f"🔄 Обрабатываю..."
            )
            
            # Process
            processed_path = process_video(file_path, watermark_path)
            file_path = processed_path
            
            # Небольшая задержка чтобы файл точно освободился
            await asyncio.sleep(0.5)
            
            logging.info(f"Video {idx} processed, starting upload to Telegram...")
            
            if SEND_TO_TELEGRAM:
                # РЕЖИМ: Отправка в Telegram
                # Send video with caption
                caption = format_description(description)
                logging.info(f"Video {idx} caption: {caption[:100] if caption else 'EMPTY'}...")
                
                video = FSInputFile(processed_path)
                
                # Отправляем с повторными попытками
                max_send_attempts = 3
                for attempt in range(max_send_attempts):
                    try:
                        logging.info(f"Video {idx} upload attempt {attempt + 1}...")
                        await message.answer_video(
                            video, 
                            caption=caption if caption else None, 
                            parse_mode=ParseMode.HTML
                        )
                        logging.info(f"Video {idx} uploaded successfully!")
                        break
                    except Exception as send_error:
                        if attempt < max_send_attempts - 1:
                            logging.warning(f"Video {idx} send attempt {attempt + 1} failed: {send_error}, retrying...")
                            await asyncio.sleep(2)
                        else:
                            raise send_error
                
                # Send description separately if caption was empty but description exists
                if not caption and description:
                    await message.answer(f"📝 <b>Описание:</b>\n{description[:500]}", parse_mode=ParseMode.HTML)
            else:
                # РЕЖИМ: Только сохранение
                file_name = os.path.basename(processed_path)
                file_size_mb = os.path.getsize(processed_path) / (1024 * 1024)
                processed_files.append({
                    'name': file_name,
                    'size': file_size_mb,
                    'description': description
                })
                logging.info(f"Video {idx} saved: {file_name}")
                # НЕ удаляем файл
                file_path = None
            
            success_count += 1
            
        except Exception as e:
            logging.error(f"Error processing {url}: {e}")
            error_count += 1
            await message.answer(f"❌ Ошибка ({idx}/{total}):\n{str(e)[:100]}\n\n🔗 {url}")
        
        finally:
            # Cleanup только если отправляли в Telegram
            if SEND_TO_TELEGRAM and file_path and os.path.exists(file_path):
                await asyncio.sleep(1)  # Ждём 1 секунду
                cleanup_file(file_path)
        
        # Small delay between videos
        if idx < total:
            await asyncio.sleep(1)
    
    # Final summary
    if SEND_TO_TELEGRAM:
        await status_msg.edit_text(
            f"🎉 <b>Обработка завершена!</b>\n\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"📊 Всего: {total}"
        )
    else:
        # Показываем список сохранённых файлов
        summary = f"🎉 <b>Обработка завершена!</b>\n\n"
        summary += f"✅ Успешно: {success_count}\n"
        summary += f"❌ Ошибок: {error_count}\n"
        summary += f"📊 Всего: {total}\n\n"
        summary += f"📂 Папка: <code>{DOWNLOADS_DIR}</code>\n\n"
        
        if processed_files:
            summary += "<b>Сохранённые файлы:</b>\n"
            for i, file_info in enumerate(processed_files[:10], 1):  # Показываем первые 10
                summary += f"{i}. <code>{file_info['name']}</code> ({file_info['size']:.1f} МБ)\n"
            
            if len(processed_files) > 10:
                summary += f"\n... и ещё {len(processed_files) - 10} файлов"
        
        await status_msg.edit_text(summary, parse_mode=ParseMode.HTML)


async def main():
    """Start the bot."""
    logging.info("Starting TikTok & YouTube Watermark Bot...")
    logging.info(f"Admin ID: {ADMIN_ID}")
    logging.info(f"Watermark configured: {watermark_exists()}")
    
    # Создаем новый бот с правильной сессией
    from aiohttp import ClientTimeout
    from aiogram.client.session.aiohttp import AiohttpSession
    
    # Создаем сессию с увеличенными таймаутами
    # Важно: передаем timeout как число (в секундах), а не ClientTimeout объект
    session = AiohttpSession()
    
    # Создаем новый бот с этой сессией
    bot_with_timeout = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )
    
    # Устанавливаем числовой таймаут (aiogram ожидает число)
    bot_with_timeout.session.timeout = 600  # 10 минут в секундах
    
    try:
        await dp.start_polling(bot_with_timeout)
    finally:
        await bot_with_timeout.session.close()


if __name__ == "__main__":
    asyncio.run(main())
