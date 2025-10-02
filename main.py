import re
import os
import logging
import telebot
import yt_dlp
from threading import Thread
from flask import Flask

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Увеличенные таймауты для длинных треков
import telebot.apihelper
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 600  # 10 минут на отправку файла

# Flask для веб-сервера
app = Flask(__name__)

@app.route('/')
def home():
    return "🎵 YouTube Music Bot is running! Send /start to bot in Telegram"

@app.route('/health')
def health():
    return "OK"

def extract_youtube_url(text):
    """Извлекает YouTube URL из текста сообщения"""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|shorts/|.+[?&]v=)?([^&=%\?]{11})'
    )
    match = re.search(youtube_regex, text)
    if match:
        video_id = match.group(6)
        return f"https://youtu.be/{video_id}"
    
    # Дополнительная проверка для разных форматов ссылок
    patterns = [
        r'youtu\.be/([^&=%\?]{11})',
        r'youtube\.com/watch\?v=([^&=%\?]{11})',
        r'youtube\.com/embed/([^&=%\?]{11})',
        r'youtube\.com/v/([^&=%\?]{11})',
        r'youtube\.com/shorts/([^&=%\?]{11})'  # ← ДОБАВЬ ЗАПЯТУЮ ЗДЕСЬ!
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            video_id = match.group(1)
            return f"https://youtu.be/{video_id}"
    
    return None
    
def download_and_send_audio(chat_id, url):
    mp3_path = None
    filename = None
    try:
        bot.send_message(chat_id, f"🎵 Начинаю обработку: {url}")

        # Создаем папку downloads
        os.makedirs("downloads", exist_ok=True)

        # Сначала получаем информацию о видео
        ydl_info_opts = {
            'quiet': True,
            'no_warnings': True,
            # 🔧 ПАРАМЕТРЫ ДЛЯ ОБХОДА БЛОКИРОВКИ
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    
    # 🔧 ДОБАВЬ ПРОВЕРКУ НА None
    if info is None:
        bot.send_message(chat_id, "❌ YouTube заблокировал запрос. Попробуйте другую ссылку или повторите позже.")
        return
    
    duration = info.get('duration', 0)
    title = info.get('title', 'Аудио')
        
        # Выбираем качество в зависимости от длительности
        if duration > 3600:  # > 1 час
            quality = '96'
            bot.send_message(chat_id, f"⏱️ Длинный трек ({duration//60} мин). Использую качество 96 kbps...")
        elif duration > 1800:  # > 30 минут
            quality = '128'
            bot.send_message(chat_id, f"⏱️ Трек на {duration//60} минут. Качество: 128 kbps")
        else:
            quality = '192'
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            # 🔧 ПАРАМЕТРЫ ДЛЯ ОБХОДА БЛОКИРОВКИ
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
        }

        bot.send_message(chat_id, "⬇️ Загружаю аудио...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_path = os.path.splitext(filename)[0] + '.mp3'

        # Проверяем размер файла
        file_size = os.path.getsize(mp3_path) / (1024 * 1024)  # в МБ
        logger.info(f"Размер файла: {file_size:.2f} МБ")
        
        if file_size > 50:
            bot.send_message(chat_id, f"⚠️ Файл слишком большой ({file_size:.1f} МБ). Telegram лимит 50 МБ. Попробуйте более короткое видео.")
            return

        # Отправка аудио с увеличенным таймаутом
        bot.send_message(chat_id, f"📤 Отправляю файл ({file_size:.1f} МБ)...")
        
        with open(mp3_path, 'rb') as audio_file:
            bot.send_audio(
                chat_id, 
                audio_file,
                title=title[:64],
                performer=info.get('uploader', 'Unknown')[:64],
                duration=duration,
                timeout=600
            )

        bot.send_message(chat_id, "✅ Готово! Наслаждайтесь музыкой!")

    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {str(e)}", exc_info=True)
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}\n\nПопробуйте еще раз или выберите другое видео.")
    
    finally:
        # Удаляем временные файлы
        try:
            if mp3_path and os.path.exists(mp3_path):
                os.remove(mp3_path)
            if filename and os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            logger.warning(f"Не удалось удалить временные файлы: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
        "🎶 Привет! Просто отправь мне ссылку на YouTube видео, "
        "и я преобразую его в MP3!\n\n"
        "Пример: https://youtu.be/3QqwjYC3EAg"
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = extract_youtube_url(message.text)
    if not url:
        bot.reply_to(message, "❌ Это не похоже на ссылку YouTube. Пришлите корректную ссылку.")
        return

    # Запускаем в отдельном потоке чтобы не блокировать бота
    thread = Thread(target=download_and_send_audio, args=(message.chat.id, url))
    thread.start()

def run_bot():
    """Запуск бота с автоматическим перезапуском при ошибках"""
    logger.info("----- Запуск YouTube Music Bot на Koyeb -----")
    while True:
        try:
            bot.infinity_polling(timeout=120, long_polling_timeout=120)
        except Exception as e:
            logger.error(f"Ошибка бота: {e}")
            import time
            time.sleep(10)
            logger.info("Перезапуск бота...")

if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=8000)


