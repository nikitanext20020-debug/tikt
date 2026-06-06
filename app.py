"""
TikTok Watermark Bot - Desktop Application
Beautiful GUI for managing the bot with real-time logs and settings.
"""
import customtkinter as ctk
import threading
import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from tkinter import filedialog, messagebox
import queue

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Settings file
SETTINGS_FILE = "bot_settings.json"

class LogHandler(logging.Handler):
    """Custom log handler that sends logs to a queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)


class BotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("🎬 TikTok Watermark Bot")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Bot state
        self.bot_running = False
        self.bot_thread = None
        self.log_queue = queue.Queue()
        
        # Load settings
        self.settings = self.load_settings()
        
        # Setup UI
        self.setup_ui()
        
        # Setup logging
        self.setup_logging()
        
        # Start log updater
        self.update_logs()
    
    def load_settings(self):
        """Load settings from file."""
        defaults = {
            "watermark_scale": 17,
            "watermark_opacity": 70,
            "watermark_position": "bottom-right",
            "watermark_margin": 20,
            "ffmpeg_preset": "fast",
            "ffmpeg_crf": 23,
            "telegram_token": "8254121885:AAGIw8reJQxki0Gji7tstDXYmo-_AFi_06k",
            "admin_id": "8235497168"
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except:
                pass
        
        return defaults
    
    def save_settings(self):
        """Save settings to file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.log(f"Error saving settings: {e}")

    def setup_ui(self):
        """Setup the user interface."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        self.create_header()
        
        # Main content
        self.create_main_content()
        
        # Footer with status
        self.create_footer()
    
    def create_header(self):
        """Create header with title and controls."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)
        
        # Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        
        title = ctk.CTkLabel(
            title_frame, 
            text="🎬 TikTok Watermark Bot",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.pack(side="left")
        
        # Start/Stop button
        self.start_btn = ctk.CTkButton(
            header,
            text="▶ Запустить бота",
            font=ctk.CTkFont(size=16, weight="bold"),
            width=180,
            height=45,
            fg_color="#28a745",
            hover_color="#218838",
            command=self.toggle_bot
        )
        self.start_btn.grid(row=0, column=2, sticky="e")
    
    def create_main_content(self):
        """Create main content area with tabs."""
        # Tabview
        self.tabview = ctk.CTkTabview(self, height=400)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # Tabs
        self.tab_logs = self.tabview.add("📋 Логи")
        self.tab_settings = self.tabview.add("⚙️ Настройки")
        self.tab_watermark = self.tabview.add("🖼 Водяная марка")
        self.tab_info = self.tabview.add("ℹ️ Информация")
        
        # Setup each tab
        self.setup_logs_tab()
        self.setup_settings_tab()
        self.setup_watermark_tab()
        self.setup_info_tab()
    
    def setup_logs_tab(self):
        """Setup logs tab."""
        self.tab_logs.grid_columnconfigure(0, weight=1)
        self.tab_logs.grid_rowconfigure(0, weight=1)
        
        # Log text area
        self.log_text = ctk.CTkTextbox(
            self.tab_logs,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            self.tab_logs,
            text="🗑 Очистить логи",
            width=150,
            command=self.clear_logs
        )
        clear_btn.grid(row=1, column=0, sticky="e", padx=5, pady=5)

    def setup_settings_tab(self):
        """Setup settings tab."""
        self.tab_settings.grid_columnconfigure(1, weight=1)
        
        row = 0
        
        # Section: Telegram
        section_label = ctk.CTkLabel(
            self.tab_settings,
            text="📱 Telegram",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        section_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))
        row += 1
        
        # Token
        ctk.CTkLabel(self.tab_settings, text="Bot Token:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.token_entry = ctk.CTkEntry(self.tab_settings, width=400, show="*")
        self.token_entry.insert(0, self.settings.get("telegram_token", ""))
        self.token_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1
        
        # Admin ID
        ctk.CTkLabel(self.tab_settings, text="Admin ID:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.admin_entry = ctk.CTkEntry(self.tab_settings, width=200)
        self.admin_entry.insert(0, self.settings.get("admin_id", ""))
        self.admin_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1
        
        # Section: FFmpeg
        section_label = ctk.CTkLabel(
            self.tab_settings,
            text="🎥 FFmpeg",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        section_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        # Preset
        ctk.CTkLabel(self.tab_settings, text="Пресет:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.preset_combo = ctk.CTkComboBox(
            self.tab_settings,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"],
            width=150
        )
        self.preset_combo.set(self.settings.get("ffmpeg_preset", "fast"))
        self.preset_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1
        
        # CRF
        ctk.CTkLabel(self.tab_settings, text="Качество (CRF):").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        crf_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        crf_frame.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        self.crf_slider = ctk.CTkSlider(crf_frame, from_=18, to=28, number_of_steps=10, width=200)
        self.crf_slider.set(self.settings.get("ffmpeg_crf", 23))
        self.crf_slider.pack(side="left")
        
        self.crf_label = ctk.CTkLabel(crf_frame, text=f"{int(self.crf_slider.get())}")
        self.crf_label.pack(side="left", padx=10)
        self.crf_slider.configure(command=lambda v: self.crf_label.configure(text=f"{int(v)}"))
        row += 1
        
        # Save button
        save_btn = ctk.CTkButton(
            self.tab_settings,
            text="💾 Сохранить настройки",
            width=200,
            height=40,
            fg_color="#28a745",
            hover_color="#218838",
            command=self.save_all_settings
        )
        save_btn.grid(row=row, column=0, columnspan=2, pady=20)

    def setup_watermark_tab(self):
        """Setup watermark settings tab."""
        self.tab_watermark.grid_columnconfigure(1, weight=1)
        
        row = 0
        
        # Preview frame
        preview_frame = ctk.CTkFrame(self.tab_watermark)
        preview_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(
            preview_frame,
            text="🖼 Текущая водяная марка",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        self.wm_status_label = ctk.CTkLabel(
            preview_frame,
            text="Проверяю...",
            font=ctk.CTkFont(size=12)
        )
        self.wm_status_label.pack(pady=5)
        
        wm_btn_frame = ctk.CTkFrame(preview_frame, fg_color="transparent")
        wm_btn_frame.pack(pady=10)
        
        ctk.CTkButton(
            wm_btn_frame,
            text="📂 Выбрать файл",
            width=140,
            command=self.select_watermark
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            wm_btn_frame,
            text="🗑 Удалить",
            width=100,
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self.remove_watermark_file
        ).pack(side="left", padx=5)
        
        row += 1
        
        # Size slider
        ctk.CTkLabel(
            self.tab_watermark,
            text="📐 Размер водяной марки",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        size_frame = ctk.CTkFrame(self.tab_watermark, fg_color="transparent")
        size_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.size_slider = ctk.CTkSlider(size_frame, from_=5, to=50, number_of_steps=45, width=300)
        self.size_slider.set(self.settings.get("watermark_scale", 17))
        self.size_slider.pack(side="left", padx=10)
        
        self.size_label = ctk.CTkLabel(size_frame, text=f"{int(self.size_slider.get())}%", width=50)
        self.size_label.pack(side="left")
        self.size_slider.configure(command=lambda v: self.size_label.configure(text=f"{int(v)}%"))
        row += 1
        
        # Opacity slider
        ctk.CTkLabel(
            self.tab_watermark,
            text="🌫 Прозрачность",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        opacity_frame = ctk.CTkFrame(self.tab_watermark, fg_color="transparent")
        opacity_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.opacity_slider = ctk.CTkSlider(opacity_frame, from_=10, to=100, number_of_steps=90, width=300)
        self.opacity_slider.set(self.settings.get("watermark_opacity", 70))
        self.opacity_slider.pack(side="left", padx=10)
        
        self.opacity_label = ctk.CTkLabel(opacity_frame, text=f"{int(self.opacity_slider.get())}%", width=50)
        self.opacity_label.pack(side="left")
        self.opacity_slider.configure(command=lambda v: self.opacity_label.configure(text=f"{int(v)}%"))
        row += 1
        
        # Position
        ctk.CTkLabel(
            self.tab_watermark,
            text="📍 Позиция",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        pos_frame = ctk.CTkFrame(self.tab_watermark, fg_color="transparent")
        pos_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        self.position_var = ctk.StringVar(value=self.settings.get("watermark_position", "bottom-right"))
        
        positions = [
            ("↖ Верх-лево", "top-left"),
            ("↗ Верх-право", "top-right"),
            ("↙ Низ-лево", "bottom-left"),
            ("↘ Низ-право", "bottom-right")
        ]
        
        for text, value in positions:
            ctk.CTkRadioButton(
                pos_frame,
                text=text,
                variable=self.position_var,
                value=value
            ).pack(side="left", padx=10)
        row += 1
        
        # Margin
        ctk.CTkLabel(
            self.tab_watermark,
            text="📏 Отступ от края (px)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        margin_frame = ctk.CTkFrame(self.tab_watermark, fg_color="transparent")
        margin_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        
        self.margin_slider = ctk.CTkSlider(margin_frame, from_=0, to=100, number_of_steps=100, width=300)
        self.margin_slider.set(self.settings.get("watermark_margin", 20))
        self.margin_slider.pack(side="left", padx=10)
        
        self.margin_label = ctk.CTkLabel(margin_frame, text=f"{int(self.margin_slider.get())}px", width=50)
        self.margin_label.pack(side="left")
        self.margin_slider.configure(command=lambda v: self.margin_label.configure(text=f"{int(v)}px"))
        row += 1
        
        # Apply button
        ctk.CTkButton(
            self.tab_watermark,
            text="✅ Применить настройки",
            width=200,
            height=40,
            fg_color="#28a745",
            hover_color="#218838",
            command=self.apply_watermark_settings
        ).grid(row=row, column=0, columnspan=2, pady=20)
        
        # Check watermark status
        self.check_watermark_status()

    def setup_info_tab(self):
        """Setup info tab."""
        info_text = """
🎬 TikTok Watermark Bot v1.0

Этот бот позволяет:
• Скачивать TikTok видео без водяного знака
• Конвертировать горизонтальные видео в вертикальные
• Накладывать свою водяную марку
• Обрабатывать несколько видео сразу

📋 Команды бота:
• /start — начать работу
• /setwatermark — установить водяную марку
• /watermark — показать текущую марку
• /removewatermark — удалить марку

💡 Советы:
• Для PNG с прозрачностью отправляйте как документ
• Можно отправлять несколько ссылок сразу
• Если TikTok блокирует — используйте VPN

⚙️ Требования:
• Python 3.8+
• FFmpeg (должен быть в PATH)
• yt-dlp

📁 Файлы:
• Настройки: bot_settings.json
• Водяная марка: watermarks/current_watermark.png
• Загрузки: downloads/
        """
        
        info_label = ctk.CTkLabel(
            self.tab_info,
            text=info_text,
            font=ctk.CTkFont(size=13),
            justify="left"
        )
        info_label.pack(padx=20, pady=20, anchor="w")
    
    def create_footer(self):
        """Create footer with status."""
        footer = ctk.CTkFrame(self, height=40)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        footer.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        self.status_indicator = ctk.CTkLabel(
            footer,
            text="●",
            font=ctk.CTkFont(size=20),
            text_color="#dc3545"
        )
        self.status_indicator.grid(row=0, column=0, padx=(10, 5))
        
        self.status_label = ctk.CTkLabel(
            footer,
            text="Бот остановлен",
            font=ctk.CTkFont(size=13)
        )
        self.status_label.grid(row=0, column=1, sticky="w")
        
        # Version
        version_label = ctk.CTkLabel(
            footer,
            text="v1.0",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        version_label.grid(row=0, column=2, padx=10)
    
    def setup_logging(self):
        """Setup logging to capture bot logs."""
        # Create custom handler
        handler = LogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
        
        # Also capture aiogram logs
        aiogram_logger = logging.getLogger('aiogram')
        aiogram_logger.addHandler(handler)
    
    def update_logs(self):
        """Update log display from queue."""
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
            except:
                break
        
        self.after(100, self.update_logs)
    
    def log(self, message):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"{timestamp} - {message}")
    
    def clear_logs(self):
        """Clear log display."""
        self.log_text.delete("1.0", "end")

    def toggle_bot(self):
        """Start or stop the bot."""
        if self.bot_running:
            self.stop_bot()
        else:
            self.start_bot()
    
    def start_bot(self):
        """Start the bot in a separate thread."""
        # Save settings first
        self.save_all_settings()
        
        # Update config.py with current settings
        self.update_config_file()
        
        self.log("🚀 Запуск бота...")
        
        # Update UI
        self.bot_running = True
        self.start_btn.configure(
            text="⏹ Остановить бота",
            fg_color="#dc3545",
            hover_color="#c82333"
        )
        self.status_indicator.configure(text_color="#28a745")
        self.status_label.configure(text="Бот работает")
        
        # Start bot in thread
        self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
        self.bot_thread.start()
    
    def stop_bot(self):
        """Stop the bot."""
        self.log("⏹ Остановка бота...")
        
        self.bot_running = False
        self.start_btn.configure(
            text="▶ Запустить бота",
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.status_indicator.configure(text_color="#dc3545")
        self.status_label.configure(text="Бот остановлен")
        
        # Note: The bot will stop on next polling cycle
        self.log("✅ Бот остановлен. Перезапустите для применения новых настроек.")
    
    def run_bot_thread(self):
        """Run bot in separate thread."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Import and run bot
            from bot import main
            loop.run_until_complete(main())
            
        except Exception as e:
            self.log(f"❌ Ошибка бота: {e}")
            self.bot_running = False
            # Update UI in main thread
            self.after(0, self.on_bot_error)
    
    def on_bot_error(self):
        """Handle bot error - update UI."""
        self.start_btn.configure(
            text="▶ Запустить бота",
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.status_indicator.configure(text_color="#dc3545")
        self.status_label.configure(text="Бот остановлен (ошибка)")
    
    def save_all_settings(self):
        """Save all settings."""
        self.settings["telegram_token"] = self.token_entry.get()
        self.settings["admin_id"] = self.admin_entry.get()
        self.settings["ffmpeg_preset"] = self.preset_combo.get()
        self.settings["ffmpeg_crf"] = int(self.crf_slider.get())
        self.settings["watermark_scale"] = int(self.size_slider.get())
        self.settings["watermark_opacity"] = int(self.opacity_slider.get())
        self.settings["watermark_position"] = self.position_var.get()
        self.settings["watermark_margin"] = int(self.margin_slider.get())
        
        self.save_settings()
        self.update_config_file()
        self.log("💾 Настройки сохранены!")
    
    def update_config_file(self):
        """Update config.py with current settings."""
        config_content = f'''"""
Configuration for TikTok Watermark Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("WM_TELEGRAM_TOKEN", "{self.settings.get('telegram_token', '')}")

# Admin User ID (only this user can use the bot)
ADMIN_ID = os.getenv("WM_ADMIN_ID", "{self.settings.get('admin_id', '')}")

# Directories
DOWNLOADS_DIR = "downloads"
WATERMARK_DIR = "watermarks"

# Watermark settings
WATERMARK_POSITION = "{self.settings.get('watermark_position', 'bottom-right')}"
WATERMARK_OPACITY = {self.settings.get('watermark_opacity', 70) / 100}
WATERMARK_SCALE = {self.settings.get('watermark_scale', 17) / 100}
WATERMARK_MARGIN = {self.settings.get('watermark_margin', 20)}

# FFmpeg settings
FFMPEG_THREADS = 0
FFMPEG_PRESET = "{self.settings.get('ffmpeg_preset', 'fast')}"
FFMPEG_CRF = {self.settings.get('ffmpeg_crf', 23)}
'''
        
        try:
            with open("config.py", "w", encoding="utf-8") as f:
                f.write(config_content)
        except Exception as e:
            self.log(f"Ошибка обновления config.py: {e}")

    def apply_watermark_settings(self):
        """Apply watermark settings."""
        self.settings["watermark_scale"] = int(self.size_slider.get())
        self.settings["watermark_opacity"] = int(self.opacity_slider.get())
        self.settings["watermark_position"] = self.position_var.get()
        self.settings["watermark_margin"] = int(self.margin_slider.get())
        
        self.save_settings()
        self.update_config_file()
        
        self.log(f"✅ Настройки водяной марки применены:")
        self.log(f"   Размер: {self.settings['watermark_scale']}%")
        self.log(f"   Прозрачность: {self.settings['watermark_opacity']}%")
        self.log(f"   Позиция: {self.settings['watermark_position']}")
        self.log(f"   Отступ: {self.settings['watermark_margin']}px")
        
        if self.bot_running:
            self.log("⚠️ Перезапустите бота для применения изменений")
    
    def check_watermark_status(self):
        """Check if watermark file exists."""
        wm_path = os.path.join("watermarks", "current_watermark.png")
        if os.path.exists(wm_path):
            size = os.path.getsize(wm_path)
            self.wm_status_label.configure(
                text=f"✅ Установлена ({size // 1024} KB)",
                text_color="#28a745"
            )
        else:
            self.wm_status_label.configure(
                text="❌ Не установлена",
                text_color="#dc3545"
            )
    
    def select_watermark(self):
        """Open file dialog to select watermark."""
        filepath = filedialog.askopenfilename(
            title="Выберите водяную марку",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg"),
                ("PNG файлы", "*.png"),
                ("Все файлы", "*.*")
            ]
        )
        
        if filepath:
            try:
                # Create watermarks directory
                os.makedirs("watermarks", exist_ok=True)
                
                # Copy file
                import shutil
                dest = os.path.join("watermarks", "current_watermark.png")
                shutil.copy2(filepath, dest)
                
                self.log(f"✅ Водяная марка установлена: {os.path.basename(filepath)}")
                self.check_watermark_status()
                
            except Exception as e:
                self.log(f"❌ Ошибка: {e}")
                messagebox.showerror("Ошибка", f"Не удалось установить водяную марку:\n{e}")
    
    def remove_watermark_file(self):
        """Remove watermark file."""
        wm_path = os.path.join("watermarks", "current_watermark.png")
        if os.path.exists(wm_path):
            try:
                os.remove(wm_path)
                self.log("🗑 Водяная марка удалена")
                self.check_watermark_status()
            except Exception as e:
                self.log(f"❌ Ошибка удаления: {e}")
        else:
            self.log("ℹ️ Водяная марка не установлена")


def main():
    """Run the application."""
    app = BotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
